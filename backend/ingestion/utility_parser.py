"""
Utility Electricity CSV Parser

Supports multiple real-world export formats:
1. Green Button CSV (PG&E / SCE / ConEd pattern) - US standard
2. Octopus Energy half-hourly CSV - UK
3. UK MPAN half-hourly wide format (48 time columns)
4. ENERGY STAR Portfolio Manager (ESPM) monthly template
5. Generic monthly bill CSV (fallback)

Critical behaviours:
- Wh vs kWh detection (UK smart meters export Wh, common source of 1000x error)
- Calendarization: splits billing periods across calendar month boundaries
  using linear daily rate allocation (most defensible for audit)
- Estimated read flagging (NOTES='Estimated', Status='E')
- Billing period sanity check: flag if <25 or >35 days
"""
import csv
import io
import re
from decimal import Decimal
from datetime import date, datetime, timedelta
from typing import NamedTuple

from ingestion.factors import (
    UK_GRID_KG_CO2E_PER_KWH,
    UK_GRID_TD_KG_CO2E_PER_KWH,
    get_egrid_factor_kg_per_kwh,
)


class BillingPeriod(NamedTuple):
    start: date
    end: date
    kwh: Decimal
    cost: Decimal | None
    meter_id: str
    is_estimated: bool
    notes: str


# ---------------------------------------------------------------------------
# Format detection heuristics
# ---------------------------------------------------------------------------

def detect_utility_format(headers: list[str]) -> str:
    """
    Identify which utility CSV format we're dealing with.
    Returns format identifier string.
    """
    h = [c.lower().strip() for c in headers]
    h_str = ','.join(h)

    # Octopus UK: 'consumption (kwh)', 'start', 'end'
    if 'consumption (kwh)' in h_str or ('consumption' in h_str and 'start' in h_str and 'end' in h_str):
        return 'OCTOPUS_UK'

    # UK HH wide format: has columns like '00:00', '00:30', '01:00'
    time_cols = [c for c in h if re.match(r'^\d{2}:\d{2}$', c)]
    if len(time_cols) >= 48:
        return 'UK_HH_WIDE'

    # Green Button (PG&E / SCE / ConEd): 'type', 'date', 'start time'
    if 'type' in h and 'date' in h and ('start time' in h or 'start date' in h):
        return 'GREEN_BUTTON'

    # ESPM: 'start date', 'end date', 'quantity', 'units'
    if 'start date' in h and 'end date' in h and 'quantity' in h and 'units' in h:
        return 'ESPM'

    # National Grid / generic bill summary
    if any(kw in h_str for kw in ['period_start', 'period start', 'kwh_total', 'kwh used', 'kwh total']):
        return 'BILL_SUMMARY'

    return 'UNKNOWN'


def skip_metadata_rows(lines: list[str], delimiter: str) -> list[str]:
    """
    Many utility exports have 5-10 lines of account metadata before the
    actual CSV headers. Skip lines until we find one that looks like headers.
    Heuristic: header row has > 3 comma/semicolon-separated values where
    most are non-numeric strings.
    """
    for i, line in enumerate(lines):
        parts = line.split(delimiter)
        if len(parts) >= 3:
            non_numeric = sum(1 for p in parts if not re.match(r'^[\d.,$-]+$', p.strip()))
            if non_numeric >= 2:
                return lines[i:]
    return lines


# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------

def to_kwh(value: Decimal, unit: str) -> tuple[Decimal, str]:
    """
    Convert any energy unit to kWh. Returns (kwh_value, warning_or_empty).
    Critical: Wh -> kWh is the most common 1000x error in UK smart meter exports.
    """
    u = unit.lower().strip()
    warning = ''
    if u == 'wh':
        # UK smart meter exports in Wh -- 1000x scaling trap
        warning = 'unit_converted_wh_to_kwh'
        return value / Decimal('1000'), warning
    elif u == 'mwh':
        return value * Decimal('1000'), warning
    elif u == 'kwh':
        return value, warning
    elif u == 'therms':
        return value * Decimal('29.307'), warning
    elif u == 'ccf':
        return value * Decimal('29.3'), warning
    elif u == 'mcf':
        return value * Decimal('293.0'), warning
    elif u == 'mmbtu':
        return value * Decimal('293.07'), warning
    elif u == 'btu':
        return value / Decimal('3412.14'), warning
    elif u == 'kbtu':
        return value / Decimal('3.412'), warning
    else:
        return value, f'unknown_unit:{unit}'


def parse_date_flexible(s: str) -> date | None:
    """Parse date in multiple formats common in utility exports."""
    s = s.strip()
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y',
                '%Y%m%d', '%m-%d-%Y', '%d.%m.%Y'):
        try:
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    # Try ISO 8601 with time component (Octopus UK)
    try:
        return datetime.fromisoformat(s[:10]).date()
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Calendarization: split billing period across calendar months
# ---------------------------------------------------------------------------

def calendarize_billing_period(
    start: date, end: date, total_kwh: Decimal
) -> list[tuple[date, date, Decimal]]:
    """
    Allocate energy consumption proportionally across calendar months.

    Algorithm (linear daily rate):
    1. daily_rate = total_kwh / billing_days
    2. For each calendar month the period overlaps:
       - count days in that month within the billing period
       - allocate = daily_rate * days_in_month

    Returns list of (month_start, month_end, allocated_kwh) tuples.
    This is the most defensible, auditor-transparent methodology per the
    architecture blueprint.
    """
    if start is None or end is None:
        return [(start, end, total_kwh)]

    billing_days = (end - start).days
    if billing_days <= 0:
        return [(start, end, total_kwh)]

    daily_rate = total_kwh / Decimal(billing_days)

    # Group by calendar month
    monthly_days: dict[tuple[int, int], int] = {}
    current = start
    while current < end:
        key = (current.year, current.month)
        monthly_days[key] = monthly_days.get(key, 0) + 1
        current += timedelta(days=1)

    result = []
    for (year, month), days in monthly_days.items():
        import calendar
        month_start = max(start, date(year, month, 1))
        last_day = calendar.monthrange(year, month)[1]
        month_end = min(end, date(year, month, last_day))
        allocated = daily_rate * Decimal(days)
        result.append((month_start, month_end, allocated))

    return result


# ---------------------------------------------------------------------------
# Format-specific parsers
# ---------------------------------------------------------------------------

def parse_green_button(reader: csv.DictReader) -> list[BillingPeriod]:
    """
    Parse PG&E / SCE / ConEd Green Button CSV format.
    Handles both interval data (15-min) and bill totals.
    Aggregates interval data to billing-period totals.
    """
    periods = []
    interval_data: dict[str, list] = {}  # date_str -> [kwh values]

    for row in reader:
        type_val = row.get('TYPE', '').lower()
        if 'export' in type_val:  # Solar NEM export -- skip
            continue
        if 'electric' not in type_val and 'usage' not in type_val:
            continue

        usage_str = row.get('USAGE', '') or row.get('Usage', '')
        units_str = row.get('UNITS', '') or row.get('Units', 'kWh')
        notes = row.get('NOTES', '') or row.get('Notes', '')
        is_estimated = 'estimated' in notes.lower()

        try:
            usage_val = Decimal(usage_str.replace(',', ''))
        except Exception:
            continue

        kwh, unit_warning = to_kwh(usage_val, units_str)

        # Check if interval (has START TIME column) or billing period (has START DATE)
        start_date_str = row.get('START DATE', '') or row.get('Start Date', '')
        end_date_str = row.get('END DATE', '') or row.get('End Date', '')
        date_str = row.get('DATE', '') or row.get('Date', '')
        start_time = row.get('START TIME', '')

        if start_date_str and end_date_str:
            # Bill totals format
            start = parse_date_flexible(start_date_str)
            end = parse_date_flexible(end_date_str)
            if start and end:
                periods.append(BillingPeriod(
                    start=start, end=end, kwh=kwh,
                    cost=None, meter_id='',
                    is_estimated=is_estimated, notes=notes
                ))
        elif date_str and start_time:
            # Interval data: aggregate by month
            key = date_str[:7]  # YYYY-MM
            interval_data.setdefault(key, []).append(float(kwh))

    # Aggregate interval data to monthly periods
    if interval_data:
        for month_key, values in sorted(interval_data.items()):
            year, month = int(month_key[:4]), int(month_key[5:])
            import calendar
            last_day = calendar.monthrange(year, month)[1]
            periods.append(BillingPeriod(
                start=date(year, month, 1),
                end=date(year, month, last_day),
                kwh=Decimal(str(sum(values))),
                cost=None, meter_id='',
                is_estimated=False, notes='Aggregated from interval data'
            ))

    return periods


def parse_octopus_uk(reader: csv.DictReader) -> list[BillingPeriod]:
    """
    Parse Octopus Energy UK half-hourly CSV.
    Format: Consumption (kWh), Start, End
    Aggregates 30-min intervals to daily/monthly totals.
    """
    monthly: dict[str, Decimal] = {}

    for row in reader:
        val_str = (row.get('Consumption (kWh)') or
                   row.get('consumption_wh') or  # Hildebrand Glow format
                   row.get('Consumption') or '').strip()
        start_str = (row.get('Start') or row.get('timestamp') or '').strip()
        units_hint = 'wh' if 'consumption_wh' in (row.keys() or []) else 'kwh'

        if not val_str or not start_str:
            continue
        try:
            val = Decimal(val_str)
        except Exception:
            continue

        kwh, _ = to_kwh(val, units_hint)
        dt = parse_date_flexible(start_str[:10])
        if dt:
            key = f'{dt.year}-{dt.month:02d}'
            monthly[key] = monthly.get(key, Decimal('0')) + kwh

    periods = []
    for month_key, total_kwh in sorted(monthly.items()):
        year, month = int(month_key[:4]), int(month_key[5:])
        import calendar
        last_day = calendar.monthrange(year, month)[1]
        periods.append(BillingPeriod(
            start=date(year, month, 1), end=date(year, month, last_day),
            kwh=total_kwh, cost=None, meter_id='', is_estimated=False,
            notes='Aggregated from 30-min UK HH intervals'
        ))
    return periods


def parse_espm(reader: csv.DictReader) -> list[BillingPeriod]:
    """Parse ENERGY STAR Portfolio Manager monthly upload template."""
    periods = []
    for row in reader:
        start_str = row.get('Start Date', '')
        end_str = row.get('End Date', '')
        qty_str = row.get('Quantity', '')
        units = row.get('Units', 'kWh')
        is_est = row.get('Estimation', '').lower() == 'yes'

        start = parse_date_flexible(start_str)
        end = parse_date_flexible(end_str)
        if not start or not end or not qty_str:
            continue
        try:
            qty = Decimal(qty_str.replace(',', ''))
        except Exception:
            continue

        kwh, _ = to_kwh(qty, units)
        periods.append(BillingPeriod(
            start=start, end=end, kwh=kwh, cost=None,
            meter_id=row.get('Meter Name', ''),
            is_estimated=is_est, notes=''
        ))
    return periods


def parse_bill_summary(reader: csv.DictReader) -> list[BillingPeriod]:
    """Parse generic monthly bill summary CSV."""
    periods = []
    for row in reader:
        # Try multiple column name variants
        start_str = (row.get('Period_Start') or row.get('Period Start') or
                     row.get('Start Date') or row.get('start_date') or '')
        end_str = (row.get('Period_End') or row.get('Period End') or
                   row.get('End Date') or row.get('end_date') or '')
        kwh_str = (row.get('kWh_Total') or row.get('kWh Used') or
                   row.get('Usage (kWh)') or row.get('Electricity (kWh)') or
                   row.get('kwh') or '')
        units = row.get('Units', 'kWh')

        start = parse_date_flexible(start_str)
        end = parse_date_flexible(end_str)
        if not start or not end or not kwh_str:
            continue
        try:
            kwh = Decimal(kwh_str.replace(',', ''))
        except Exception:
            continue

        kwh, _ = to_kwh(kwh, units)
        periods.append(BillingPeriod(
            start=start, end=end, kwh=kwh, cost=None,
            meter_id=row.get('Account_Number', ''),
            is_estimated=False, notes=''
        ))
    return periods


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def parse_utility_csv(
    file_content: bytes,
    grid_region_code: str = 'GB',  # default to UK
    facility_country: str = 'GB',
) -> tuple[list[dict], dict]:
    """
    Main utility CSV parser entry point.

    Returns:
        (records, metadata) where records is a list of normalized period dicts
        ready for StagingRecord creation.
    """
    for encoding in ('utf-8-sig', 'utf-8', 'cp1252', 'iso-8859-1'):
        try:
            text = file_content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = file_content.decode('utf-8', errors='replace')
        encoding = 'utf-8 (with replacement)'

    lines = text.splitlines()

    # Detect delimiter
    first_line = lines[0] if lines else ''
    delimiter = ';' if first_line.count(';') > first_line.count(',') else ','
    if first_line.count('\t') > max(first_line.count(';'), first_line.count(',')):
        delimiter = '\t'

    # Skip metadata header rows
    lines = skip_metadata_rows(lines, delimiter)
    if not lines:
        return [], {'error': 'No data rows found after skipping metadata'}

    reader = csv.DictReader(io.StringIO('\n'.join(lines)), delimiter=delimiter)
    headers = list(reader.fieldnames or [])
    fmt = detect_utility_format(headers)

    # Parse billing periods by format
    if fmt == 'GREEN_BUTTON':
        periods = parse_green_button(reader)
    elif fmt == 'OCTOPUS_UK':
        periods = parse_octopus_uk(reader)
    elif fmt == 'ESPM':
        periods = parse_espm(reader)
    else:
        periods = parse_bill_summary(reader)

    # Resolve emission factor
    if facility_country == 'GB':
        ef_scope2_kg = UK_GRID_KG_CO2E_PER_KWH
        ef_td_kg = UK_GRID_TD_KG_CO2E_PER_KWH
    else:
        ef_scope2_kg = get_egrid_factor_kg_per_kwh(grid_region_code)
        ef_td_kg = Decimal('0.0')  # US T&D accounted separately if needed

    records = []
    today = date.today()

    for idx, period in enumerate(periods, start=1):
        warnings = []
        status = 'PENDING'

        # Billing period sanity check
        if period.start is None or period.end is None:
            warnings.append('unparseable_billing_date')
            status = 'FLAGGED'
        else:
            billing_days = (period.end - period.start).days
            if billing_days < 25:
                warnings.append('billing_period_too_short')
                status = 'FLAGGED'
            elif billing_days > 35:
                warnings.append('billing_period_too_long')
                status = 'FLAGGED'

        # Estimated read flag
        if period.is_estimated:
            warnings.append('estimated_read')
            status = 'FLAGGED'

        # Zero usage
        if period.kwh == 0:
            warnings.append('zero_consumption')
            status = 'FLAGGED'

        # Future date check
        if period.end and period.end > today:
            warnings.append('suspicious_date:future')
            status = 'FLAGGED'

        # Calendarize if billing period crosses month boundary
        is_calendarized = period.start.month != period.end.month
        if is_calendarized:
            sub_periods = calendarize_billing_period(period.start, period.end, period.kwh)
        else:
            sub_periods = [(period.start, period.end, period.kwh)]

        for sub_start, sub_end, sub_kwh in sub_periods:
            co2e_kg = sub_kwh * ef_scope2_kg
            td_co2e_kg = sub_kwh * ef_td_kg

            records.append({
                'row_number': idx,
                'raw_json': {
                    'period_start': str(period.start),
                    'period_end': str(period.end),
                    'total_kwh': str(period.kwh),
                    'meter_id': period.meter_id,
                    'notes': period.notes,
                    'is_estimated': period.is_estimated,
                },
                'parse_status': status,
                'parse_warnings': warnings,
                'scope': '2',
                'category': 'ELECTRICITY',
                'period_start': sub_start,
                'period_end': sub_end,
                'activity_date': sub_start,
                'raw_quantity': period.kwh,
                'raw_unit': 'KWH',
                'normalized_quantity': sub_kwh,
                'normalized_unit': 'KWH',
                'co2e_kg': co2e_kg,
                'source_entity': period.meter_id,
                'source_description': f'Grid electricity - {grid_region_code}',
                'source_reference': '',
                'is_estimated': period.is_estimated,
                'is_calendarized': is_calendarized,
                # T&D Scope 3 stored in notes (would be separate ledger entry in full build)
                'td_co2e_kg': td_co2e_kg,
            })

    metadata = {
        'format': fmt,
        'encoding': encoding,
        'delimiter': delimiter,
        'periods_found': len(periods),
        'records_after_calendarization': len(records),
        'grid_factor_kg_per_kwh': str(ef_scope2_kg),
    }

    return records, metadata
