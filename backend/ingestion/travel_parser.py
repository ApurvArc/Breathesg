"""
Corporate Travel CSV Parser — Concur Expense Report Format

Handles Concur standard expense export with these expense type codes:
- AIRFR: Air travel (flight segments)
- HOTEL: Hotel/lodging
- CARRT: Car rental
- TAXCB: Taxi/cab
- UBERT: Rideshare (Uber/Lyft)
- TRAIN: Rail/train

Key complexities handled:
- IATA code resolution -> lat/lon -> Haversine great-circle distance
- DEFRA 8% routing uplift on computed distance
- Haul classification (short < 3700km, long >= 3700km)
- Cabin class normalization (Y/C/F codes -> ECONOMY/BUSINESS/FIRST)
- Hotel country code -> DEFRA regional factor
- Car rental: fuel type inference from vendor/car class
- Missing IATA codes -> FLAGGED for analyst
- All travel -> Scope 3, Category 6 (GHG Protocol Business Travel)
"""
from decimal import Decimal
from datetime import date
from typing import Optional
import csv
import io

from ingestion.factors import (
    DEFRA_2025_AVIATION,
    DEFRA_2025_HOTEL,
    DEFRA_2025_GROUND,
    AVG_KM_PER_RENTAL_DAY,
    SHORT_HAUL_MAX_KM,
    ROUTING_UPLIFT,
    classify_flight_haul,
    normalize_cabin_class,
)
from ingestion.airports import flight_distance_km, get_airport

# ---------------------------------------------------------------------------
# Concur column name aliases (highly configurable per company)
# ---------------------------------------------------------------------------
CONCUR_COLUMN_ALIASES = {
    'Report_ID':           ['Report ID', 'ReportID', 'Report Key', 'report_id'],
    'Report_Name':         ['Report Name', 'ReportName', 'report_name'],
    'Employee_Name':       ['Employee Name', 'EmployeeName', 'Traveler Name', 'employee_name'],
    'Employee_ID':         ['Employee ID', 'EmployeeID', 'employee_id', 'User ID'],
    'Department':          ['Department', 'department', 'Dept'],
    'Cost_Center':         ['Cost Center', 'CostCenter', 'cost_center'],
    'Transaction_Date':    ['Transaction Date', 'Expense Date', 'Travel Date', 'Date', 'transaction_date'],
    'Expense_Type_Code':   ['Expense Type Code', 'ExpenseTypeCode', 'Type Code', 'expense_type_code'],
    'Expense_Type':        ['Expense Type', 'ExpenseType', 'Type', 'Category'],
    'Vendor':              ['Vendor', 'vendor', 'Supplier', 'Airline', 'Hotel Name'],
    'Amount':              ['Amount', 'amount', 'Total Amount', 'Net Amount'],
    'Currency':            ['Currency', 'currency', 'Transaction Currency'],
    'Origin':              ['Origin', 'City From', 'From City', 'Departure City', 'Origin Airport'],
    'Destination':         ['Destination', 'City To', 'To City', 'Arrival City', 'Destination Airport'],
    'Class_of_Service':    ['Class of Service', 'Cabin Class', 'Class', 'Service Class', 'cabin_class'],
    'Hotel_Nights':        ['Hotel Nights', 'Nights', 'Number of Nights', 'hotel_nights'],
    'Distance':            ['Miles', 'Kilometers', 'Distance', 'KM', 'distance_km'],
    'Distance_Unit':       ['Distance Unit', 'Miles/KM', 'Unit'],
    'City':                ['City', 'Hotel City', 'city'],
    'Country':             ['Country', 'Hotel Country', 'country'],
    'Country_Code':        ['Country Code', 'CountryCode', 'country_code'],
}

_CONCUR_ALIAS_MAP = {}
for canonical, aliases in CONCUR_COLUMN_ALIASES.items():
    for alias in aliases:
        _CONCUR_ALIAS_MAP[alias.lower().strip()] = canonical
    _CONCUR_ALIAS_MAP[canonical.lower().strip()] = canonical

# Expense type code -> canonical type
EXPENSE_TYPE_MAP = {
    'AIRFR': 'AIR', 'AIR': 'AIR', 'AIRFARE': 'AIR',
    'HOTEL': 'HOTEL', 'LODGING': 'HOTEL', 'ACCOMMODATION': 'HOTEL',
    'CARRT': 'CAR', 'CAR RENTAL': 'CAR', 'RENTAL CAR': 'CAR', 'VEHICLE': 'CAR',
    'TAXCB': 'TAXI', 'TAXI': 'TAXI', 'CAB': 'TAXI',
    'UBERT': 'TAXI', 'RIDESHARE': 'TAXI', 'UBER': 'TAXI', 'LYFT': 'TAXI',
    'TRAIN': 'RAIL', 'RAIL': 'RAIL', 'RAILROAD': 'RAIL', 'METRO': 'RAIL',
    'BUS': 'BUS',
}

CATEGORY_MAP = {
    'AIR':  'BUSINESS_TRAVEL_AIR',
    'HOTEL': 'BUSINESS_TRAVEL_HOTEL',
    'CAR':  'BUSINESS_TRAVEL_GROUND',
    'TAXI': 'BUSINESS_TRAVEL_GROUND',
    'RAIL': 'BUSINESS_TRAVEL_RAIL',
    'BUS':  'BUSINESS_TRAVEL_GROUND',
}


def normalize_concur_headers(fieldnames: list[str]) -> dict[str, str]:
    """Map raw Concur header -> canonical field name."""
    return {f: _CONCUR_ALIAS_MAP.get(f.lower().strip(), f) for f in fieldnames}


def parse_travel_date(s: str) -> date | None:
    from datetime import datetime
    for fmt in ('%Y-%m-%d', '%m/%d/%Y', '%d/%m/%Y', '%d-%m-%Y', '%m-%d-%Y'):
        try:
            return datetime.strptime(s.strip(), fmt).date()
        except (ValueError, AttributeError):
            continue
    return None


def extract_iata(s: str) -> str:
    """Extract 3-letter IATA code from a string that may contain city names."""
    s = s.strip().upper()
    # Direct 3-letter match
    if len(s) == 3 and s.isalpha():
        return s
    # Look for parenthetical IATA code: 'London (LHR)' or 'LHR - Heathrow'
    import re
    match = re.search(r'\b([A-Z]{3})\b', s)
    if match:
        return match.group(1)
    return s[:3] if len(s) >= 3 else s


def resolve_country_code(row: dict) -> str:
    """Extract ISO country code from hotel booking row."""
    # Try explicit country code fields first
    cc = row.get('Country_Code', '').strip().upper()
    if len(cc) == 2:
        return cc
    # Fall back to country name mapping
    country_name = row.get('Country', '').strip().lower()
    COUNTRY_NAME_TO_CODE = {
        'united kingdom': 'GB', 'uk': 'GB', 'england': 'GB', 'britain': 'GB',
        'united states': 'US', 'usa': 'US', 'us': 'US', 'america': 'US',
        'germany': 'DE', 'deutschland': 'DE',
        'france': 'FR',
        'spain': 'ES', 'espana': 'ES',
        'canada': 'CA',
        'australia': 'AU',
        'india': 'IN',
        'singapore': 'SG',
        'japan': 'JP', 'nippon': 'JP',
        'china': 'CN',
        'uae': 'AE', 'united arab emirates': 'AE', 'dubai': 'AE',
        'maldives': 'MV',
        'costa rica': 'CR',
        'netherlands': 'NL', 'holland': 'NL',
        'switzerland': 'CH',
        'sweden': 'SE',
        'norway': 'NO',
        'denmark': 'DK',
        'brazil': 'BR',
        'mexico': 'MX',
        'south africa': 'ZA',
        'kenya': 'KE',
        'south korea': 'KR', 'korea': 'KR',
    }
    return COUNTRY_NAME_TO_CODE.get(country_name, 'DEFAULT')


def process_flight_row(row: dict) -> dict:
    """Compute CO2e for an air travel expense row."""
    result = {
        'scope': '3',
        'category': 'BUSINESS_TRAVEL_AIR',
        'parse_warnings': [],
        'parse_status': 'PENDING',
    }

    origin_raw = row.get('Origin', '')
    dest_raw = row.get('Destination', '')
    origin_iata = extract_iata(origin_raw)
    dest_iata = extract_iata(dest_raw)

    result['origin_iata'] = origin_iata
    result['destination_iata'] = dest_iata

    dist_km, error = flight_distance_km(origin_iata, dest_iata)
    if error:
        result['parse_warnings'].append(f'airport_unresolved:{error}')
        result['parse_status'] = 'FLAGGED'
        return result

    dist_decimal = Decimal(str(round(dist_km, 2)))
    result['distance_km'] = dist_decimal

    cabin_raw = row.get('Class_of_Service', 'ECONOMY')
    cabin = normalize_cabin_class(cabin_raw)
    result['cabin_class'] = cabin

    haul = classify_flight_haul(dist_decimal)
    factor_key = (haul, cabin)
    factor = DEFRA_2025_AVIATION.get(factor_key,
             DEFRA_2025_AVIATION.get((haul, 'AVERAGE'), Decimal('0.15')))

    co2e_kg = dist_decimal * factor
    result['co2e_kg'] = co2e_kg
    result['normalized_quantity'] = dist_decimal
    result['normalized_unit'] = 'passenger-km'
    result['raw_quantity'] = dist_decimal
    result['raw_unit'] = 'km'
    result['emission_factor_value'] = str(factor)
    result['emission_factor_source'] = 'DEFRA_2025'
    result['haul_type'] = haul

    return result


def process_hotel_row(row: dict) -> dict:
    """Compute CO2e for a hotel stay expense row."""
    result = {
        'scope': '3',
        'category': 'BUSINESS_TRAVEL_HOTEL',
        'parse_warnings': [],
        'parse_status': 'PENDING',
    }

    # Nights
    nights_str = row.get('Hotel_Nights', '').strip()
    try:
        nights = int(float(nights_str)) if nights_str else 1
    except (ValueError, TypeError):
        nights = 1
        result['parse_warnings'].append('hotel_nights_assumed_1')

    country_code = resolve_country_code(row)
    factor = DEFRA_2025_HOTEL.get(country_code, DEFRA_2025_HOTEL['DEFAULT'])

    co2e_kg = Decimal(str(nights)) * factor
    result['co2e_kg'] = co2e_kg
    result['hotel_nights'] = nights
    result['hotel_country_code'] = country_code
    result['normalized_quantity'] = Decimal(str(nights))
    result['normalized_unit'] = 'room-night'
    result['raw_quantity'] = Decimal(str(nights))
    result['raw_unit'] = 'nights'
    result['emission_factor_value'] = str(factor)
    result['emission_factor_source'] = 'DEFRA_2025'

    return result


def process_ground_row(row: dict, transport_type: str) -> dict:
    """Compute CO2e for car rental, taxi, or rail expense."""
    result = {
        'scope': '3',
        'category': CATEGORY_MAP.get(transport_type, 'BUSINESS_TRAVEL_GROUND'),
        'parse_warnings': [],
        'parse_status': 'PENDING',
    }

    # Distance
    dist_str = row.get('Distance', '').strip()
    dist_unit = row.get('Distance_Unit', 'km').strip().lower()
    try:
        dist_raw = Decimal(dist_str.replace(',', '')) if dist_str else None
    except Exception:
        dist_raw = None

    if dist_raw is None:
        # Estimate from rental duration: avg 80 km/day
        dist_raw = AVG_KM_PER_RENTAL_DAY
        result['parse_warnings'].append('distance_estimated_from_avg_daily')

    # Convert miles to km
    if 'mile' in dist_unit or dist_unit == 'mi':
        dist_km = dist_raw * Decimal('1.60934')
    else:
        dist_km = dist_raw

    # Select emission factor
    if transport_type == 'RAIL':
        factor_key = 'RAIL_UK'
        factor = DEFRA_2025_GROUND['RAIL_UK']
    elif transport_type in ('TAXI', 'BUS'):
        factor_key = 'TAXI'
        factor = DEFRA_2025_GROUND['TAXI']
    else:
        # Car rental: try to infer fuel type
        vendor = row.get('Vendor', '').lower()
        if 'electric' in vendor or 'ev' in vendor or 'tesla' in vendor:
            factor_key = 'CAR_EV'
        elif 'hybrid' in vendor or 'prius' in vendor:
            factor_key = 'CAR_HYBRID'
        elif 'diesel' in vendor:
            factor_key = 'CAR_DIESEL'
        else:
            factor_key = 'CAR_PETROL'  # default
        factor = DEFRA_2025_GROUND[factor_key]

    co2e_kg = dist_km * factor
    result['co2e_kg'] = co2e_kg
    result['distance_km'] = dist_km
    result['normalized_quantity'] = dist_km
    result['normalized_unit'] = 'km'
    result['raw_quantity'] = dist_raw
    result['raw_unit'] = dist_unit
    result['emission_factor_value'] = str(factor)
    result['emission_factor_source'] = 'DEFRA_2025'

    return result


def parse_travel_csv(file_content: bytes) -> tuple[list[dict], dict]:
    """
    Main entry point for Concur corporate travel CSV parsing.
    Returns (records, metadata).
    """
    for encoding in ('utf-8-sig', 'utf-8', 'cp1252'):
        try:
            text = file_content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        text = file_content.decode('utf-8', errors='replace')
        encoding = 'utf-8 (replacement)'

    delimiter = ',' 
    first_line = text.split('\n')[0]
    if first_line.count('\t') > first_line.count(','):
        delimiter = '\t'

    reader = csv.DictReader(io.StringIO(text), delimiter=delimiter)
    header_map = normalize_concur_headers(list(reader.fieldnames or []))

    records = []
    today = date.today()

    for row_num, raw_row in enumerate(reader, start=2):
        # Re-key with canonical names
        row = {header_map.get(k, k): v for k, v in raw_row.items()}
        raw_json = dict(raw_row)  # verbatim

        # Determine expense type
        type_code = row.get('Expense_Type_Code', '').strip().upper()
        type_name = row.get('Expense_Type', '').strip().upper()
        canonical_type = EXPENSE_TYPE_MAP.get(type_code) or EXPENSE_TYPE_MAP.get(type_name, 'UNKNOWN')

        if canonical_type == 'UNKNOWN':
            records.append({
                'row_number': row_num, 'raw_json': raw_json,
                'parse_status': 'SKIPPED',
                'skip_reason': f'Unknown expense type: {type_code or type_name}',
                'parse_warnings': [],
            })
            continue

        # Parse date
        date_str = row.get('Transaction_Date', '').strip()
        activity_date = parse_travel_date(date_str)
        warnings = []
        status = 'PENDING'

        if not activity_date:
            warnings.append('unparseable_date')
            status = 'FLAGGED'
        elif activity_date > today:
            warnings.append('suspicious_date:future')
            status = 'FLAGGED'

        # Route to type-specific processor
        if canonical_type == 'AIR':
            emission_data = process_flight_row(row)
        elif canonical_type == 'HOTEL':
            emission_data = process_hotel_row(row)
        else:
            emission_data = process_ground_row(row, canonical_type)

        # Merge results
        warnings.extend(emission_data.pop('parse_warnings', []))
        if emission_data.get('parse_status') == 'FLAGGED':
            status = 'FLAGGED'

        record = {
            'row_number': row_num,
            'raw_json': raw_json,
            'parse_status': status,
            'parse_warnings': warnings,
            'scope': '3',
            'activity_date': activity_date,
            'period_start': activity_date,
            'period_end': activity_date,
            'source_entity': row.get('Employee_ID', '').strip(),
            'source_description': row.get('Employee_Name', '').strip(),
            'source_reference': row.get('Report_ID', '').strip(),
            **emission_data,
        }
        records.append(record)

    # Stats
    air = sum(1 for r in records if r.get('category') == 'BUSINESS_TRAVEL_AIR')
    hotel = sum(1 for r in records if r.get('category') == 'BUSINESS_TRAVEL_HOTEL')
    ground = sum(1 for r in records if r.get('category') in ('BUSINESS_TRAVEL_GROUND', 'BUSINESS_TRAVEL_RAIL'))

    metadata = {
        'encoding': encoding,
        'total_rows': len(records),
        'air_rows': air,
        'hotel_rows': hotel,
        'ground_rows': ground,
    }

    return records, metadata
