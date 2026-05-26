"""
SAP MB51 Flat-File CSV Parser

Handles the extreme real-world variability of SAP exports:
- German/English column headers (language-dependent ALV export)
- Semicolon delimiters with comma decimals (German locale) vs comma delimiters with period decimals
- BUDAT date format: DD.MM.YYYY, YYYYMMDD, MM/DD/YYYY, YYYY-MM-DD
- MATNR with leading zeros (18-char padded)
- German unit of measure abbreviations (L, KG, KWH, M3, TO, ST)
- Movement type filtering (only consumption movements, not receipts)
- Reversal document detection (262 cancels 261, must net correctly)
- Trailing whitespace and leading zeros on plant codes
"""
import csv
import io
import re
from decimal import Decimal, InvalidOperation
from datetime import date, datetime
from typing import Iterator

from ingestion.factors import DEFRA_2025_FUEL

# ─────────────────────────────────────────────────────────────────────────────
# Column header mapping: canonical_name -> list of known aliases
# (German headers appear when SAP session language is DE)
# ─────────────────────────────────────────────────────────────────────────────
SAP_COLUMN_ALIASES = {
    'MBLNR': ['Document Number', 'Belegnummer', 'Mat. Doc.', 'Material Document'],
    'MJAHR': ['Year', 'Jahr', 'Document Year'],
    'BUDAT': ['Posting Date', 'Buchungsdatum', 'Pstng Date', 'Buch.datum'],
    'BLDAT': ['Document Date', 'Belegdatum', 'Doc. Date'],
    'MATNR': ['Material', 'Materialnummer', 'Mat.'],
    'MAKTX': ['Material Description', 'Materialkurztext', 'Mat. Descript.', 'Short Text', 'Kurztext'],
    'BWART': ['Movement Type', 'Bewegungsart', 'Mvt', 'Mvt Type', 'Bew.art'],
    'MENGE': ['Quantity', 'Menge', 'Qty', 'Qty in UnE'],
    'MEINS': ['Unit of Measure', 'Basismengeneinheit', 'Base Unit', 'Mengeneinheit', 'BUn', 'UoM'],
    'WERKS': ['Plant', 'Werk'],
    'LGORT': ['Storage Location', 'Lagerort', 'SLoc'],
    'KOSTL': ['Cost Center', 'Kostenstelle', 'CostCtr'],
    'AUFNR': ['Order', 'Auftrag', 'Prod.Order'],
    'DMBTR': ['Amount in LC', 'Betrag in HW', 'LC Amount', 'Wert HW'],
    'WAERS': ['Currency', 'Währung', 'Curr.'],
    'BUKRS': ['Company Code', 'Buchungskreis', 'CoCd'],
    'LIFNR': ['Vendor', 'Lieferant', 'Vendor/Supplying Plant'],
    'EBELN': ['Purchase Order', 'Bestellnummer', 'Purch.Doc.'],
    'EBELP': ['PO Item', 'Bestellposition', 'Item'],
}

# Reverse lookup: alias -> canonical
_ALIAS_TO_CANONICAL = {}
for canonical, aliases in SAP_COLUMN_ALIASES.items():
    for alias in aliases:
        _ALIAS_TO_CANONICAL[alias.lower().strip()] = canonical
    _ALIAS_TO_CANONICAL[canonical.lower().strip()] = canonical

# Movement types that represent actual consumption (include in emissions)
CONSUMPTION_MOVEMENT_TYPES = {'201', '221', '261', '281', '291', '551'}
# Movement types that are receipts (exclude)
RECEIPT_MOVEMENT_TYPES = {'101', '121', '501', '531'}
# Reversal movement types and what they reverse
REVERSAL_MAP = {'202': '201', '262': '261', '282': '281', '292': '291'}

# German unit abbreviation -> canonical unit
SAP_UNIT_MAP = {
    'L': 'L', 'LT': 'L', 'LTR': 'L',         # Litre
    'KG': 'KG',                                   # Kilogram
    'G': 'KG',                                    # Gram -> will multiply by 0.001
    'T': 'KG', 'TO': 'KG', 'MT': 'KG',          # Metric ton -> kg (×1000)
    'KWH': 'KWH', 'KWh': 'KWH',                  # Kilowatt-hour
    'MWH': 'KWH', 'MWh': 'KWH',                  # MWh -> will multiply by 1000
    'M3': 'M3', 'm3': 'M3', 'CBM': 'M3',        # Cubic metre
    'GAL': 'L',                                   # US Gallon -> L (×3.78541)
    'UKGAL': 'L',                                 # UK Gallon -> L (×4.54609)
    'ST': 'ST',                                   # Piece (skip for emissions)
}

# Unit conversion to canonical: (canonical_unit, multiplier)
SAP_UNIT_CONVERSIONS = {
    'G':     ('KG',  Decimal('0.001')),
    'T':     ('KG',  Decimal('1000')),
    'TO':    ('KG',  Decimal('1000')),
    'MT':    ('KG',  Decimal('1000')),
    'MWH':   ('KWH', Decimal('1000')),
    'MWh':   ('KWH', Decimal('1000')),
    'GAL':   ('L',   Decimal('3.78541')),
    'UKGAL': ('L',   Decimal('4.54609')),
}

# Material keyword -> (fuel_type, scope, category)
MATERIAL_FUEL_KEYWORDS = {
    'diesel':      ('DIESEL', '1', 'FUEL_COMBUSTION'),
    'petrol':      ('PETROL', '1', 'FUEL_COMBUSTION'),
    'gasoline':    ('PETROL', '1', 'FUEL_COMBUSTION'),
    'benzin':      ('PETROL', '1', 'FUEL_COMBUSTION'),  # German
    'kraftstoff':  ('DIESEL', '1', 'FUEL_COMBUSTION'),  # German: fuel
    'gas':         ('NATGAS', '1', 'FUEL_COMBUSTION'),
    'erdgas':      ('NATGAS', '1', 'FUEL_COMBUSTION'),  # German: natural gas
    'natgas':      ('NATGAS', '1', 'FUEL_COMBUSTION'),
    'lpg':         ('LPG',    '1', 'FUEL_COMBUSTION'),
    'propane':     ('LPG',    '1', 'FUEL_COMBUSTION'),
    'propan':      ('LPG',    '1', 'FUEL_COMBUSTION'),  # German
    'heizol':      ('HEATING_OIL', '1', 'FUEL_COMBUSTION'),  # German: heating oil
    'heating oil': ('HEATING_OIL', '1', 'FUEL_COMBUSTION'),
    'fuel oil':    ('HEATING_OIL', '1', 'FUEL_COMBUSTION'),
    'electricity': ('', '2', 'ELECTRICITY'),
    'elektrizitat': ('', '2', 'ELECTRICITY'),  # German
    'strom':       ('', '2', 'ELECTRICITY'),   # German: electricity
    'elec':        ('', '2', 'ELECTRICITY'),
}


def detect_sap_format(raw_content: str) -> dict:
    """
    Detect delimiter, decimal separator, and date format from raw CSV content.
    Returns format hints dict.
    """
    hints = {
        'delimiter': ',',
        'decimal_sep': '.',
        'date_format': 'AUTO',
        'has_german_headers': False,
    }

    first_line = raw_content.split('\n')[0] if raw_content else ''

    # Delimiter detection: semicolon is SAP German locale standard
    if first_line.count(';') > first_line.count(','):
        hints['delimiter'] = ';'
        hints['decimal_sep'] = ','  # German locale: decimal comma
    elif first_line.count('\t') > first_line.count(','):
        hints['delimiter'] = '\t'

    # German header detection
    german_markers = ['Buchungsdatum', 'Menge', 'Werk', 'Kostenstelle',
                      'Materialnummer', 'Bewegungsart', 'Belegnummer']
    if any(marker.lower() in first_line.lower() for marker in german_markers):
        hints['has_german_headers'] = True

    return hints


def normalize_header(raw_header: str) -> str:
    """Map any known header alias to its canonical SAP field name."""
    return _ALIAS_TO_CANONICAL.get(raw_header.lower().strip(), raw_header.upper().strip())


def parse_sap_date(raw_date: str) -> date | None:
    """
    Parse SAP date in any of the known formats:
    - YYYYMMDD (internal storage format)
    - DD.MM.YYYY (German user profile)
    - MM/DD/YYYY (US user profile)
    - YYYY-MM-DD (ISO)
    Returns None if unparseable (triggers FLAGGED status).
    """
    s = raw_date.strip()
    if not s:
        return None
    formats = [
        ('%Y%m%d', r'^\d{8}$'),
        ('%d.%m.%Y', r'^\d{2}\.\d{2}\.\d{4}$'),
        ('%m/%d/%Y', r'^\d{2}/\d{2}/\d{4}$'),
        ('%Y-%m-%d', r'^\d{4}-\d{2}-\d{2}$'),
        ('%d-%m-%Y', r'^\d{2}-\d{2}-\d{4}$'),
    ]
    for fmt, pattern in formats:
        if re.match(pattern, s):
            try:
                return datetime.strptime(s, fmt).date()
            except ValueError:
                continue
    return None


def parse_german_decimal(raw: str, decimal_sep: str = '.') -> Decimal | None:
    """
    Parse numeric string handling both German (1.200,000) and English (1,200.000) formats.
    German format: periods as thousands separator, comma as decimal.
    """
    s = raw.strip().replace(' ', '')
    if not s:
        return None
    try:
        if decimal_sep == ',':
            # German: remove period thousands separators, replace comma decimal
            s = s.replace('.', '').replace(',', '.')
        else:
            # English: remove comma thousands separators
            s = s.replace(',', '')
        return Decimal(s)
    except InvalidOperation:
        return None


def strip_sap_leading_zeros(matnr: str) -> str:
    """Strip leading zeros from MATNR (18-char padded → actual code)."""
    stripped = matnr.strip().lstrip('0')
    return stripped if stripped else '0'


def classify_material(matnr: str, maktx: str) -> tuple[str, str, str]:
    """
    Classify material into (fuel_type, scope, category) using keyword matching
    on material description (MAKTX). MATNR codes are client-specific so we
    use description text as the primary signal.
    Returns ('UNKNOWN', '3', 'PURCHASED_GOODS') if unclassified.
    """
    search_text = f'{matnr} {maktx}'.lower()
    for keyword, classification in MATERIAL_FUEL_KEYWORDS.items():
        if keyword in search_text:
            return classification
    return ('UNKNOWN', '3', 'PURCHASED_GOODS')


def normalize_quantity_unit(menge: Decimal, meins: str) -> tuple[Decimal, str]:
    """Convert quantity to canonical unit. Returns (normalized_qty, canonical_unit)."""
    unit_upper = meins.strip().upper()
    if unit_upper in SAP_UNIT_CONVERSIONS:
        target_unit, multiplier = SAP_UNIT_CONVERSIONS[unit_upper]
        return menge * multiplier, target_unit
    canonical = SAP_UNIT_MAP.get(unit_upper, unit_upper)
    return menge, canonical


def compute_fuel_co2e(fuel_type: str, quantity: Decimal, unit: str) -> dict | None:
    """
    Compute kg CO2e for fuel combustion.
    Returns dict with co2e_kg, co2_kg, ch4_kg, n2o_kg, or None if unsupported.
    """
    factors = DEFRA_2025_FUEL.get(fuel_type)
    if not factors:
        return None

    expected_unit = factors.get('unit', 'L')
    if unit != expected_unit:
        return None  # unit mismatch — flag for analyst

    if fuel_type == 'NATGAS':
        co2e = quantity * factors['co2e_per_M3']
        co2  = quantity * factors['co2_per_M3']
        ch4  = quantity * factors['ch4_per_M3']
        n2o  = quantity * factors['n2o_per_M3']
    else:
        co2e = quantity * factors['co2e_per_L']
        co2  = quantity * factors['co2_per_L']
        ch4  = quantity * factors['ch4_per_L']
        n2o  = quantity * factors['n2o_per_L']

    return {'co2e_kg': co2e, 'co2_kg': co2, 'ch4_kg': ch4, 'n2o_kg': n2o}


def parse_sap_csv(file_content: bytes) -> tuple[list[dict], dict]:
    """
    Main entry point for SAP CSV parsing.

    Args:
        file_content: raw bytes of the uploaded CSV file

    Returns:
        (rows, metadata) where rows is a list of parsed record dicts
        and metadata contains format detection results and statistics.
    """
    # Encoding detection: try UTF-8 first, fall back to Windows-1252
    # (SAP exports in system codepage which is often CP1252 on Windows servers)
    for encoding in ('utf-8-sig', 'utf-8', 'cp1252', 'iso-8859-1'):
        try:
            raw_text = file_content.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raw_text = file_content.decode('utf-8', errors='replace')
        encoding = 'utf-8 (with replacement)'

    hints = detect_sap_format(raw_text)
    delimiter = hints['delimiter']
    decimal_sep = hints['decimal_sep']

    reader = csv.DictReader(io.StringIO(raw_text), delimiter=delimiter)
    if not reader.fieldnames:
        return [], {'error': 'No headers found in file'}

    # Normalize all headers
    canonical_fieldnames = [normalize_header(f) for f in reader.fieldnames]

    rows = []
    warnings_count = 0
    today = date.today()
    three_years_ago = date(today.year - 3, today.month, today.day)

    for row_num, raw_row in enumerate(reader, start=2):  # start=2 (row 1 is header)
        # Re-key with canonical names using zip (handles rows shorter than header)
        row = dict(zip(canonical_fieldnames, raw_row.values()))
        raw_json = dict(zip(reader.fieldnames, raw_row.values()))  # verbatim original

        result = {

            'row_number': row_num,
            'raw_json': raw_json,
            'parse_status': 'OK',
            'parse_warnings': [],
            'source_reference': row.get('MBLNR', '').strip(),
            'source_entity': row.get('WERKS', '').strip(),
            'source_description': row.get('MAKTX', '').strip(),
        }

        # Movement type filter
        bwart = row.get('BWART', '').strip()
        if bwart in RECEIPT_MOVEMENT_TYPES:
            result['parse_status'] = 'SKIPPED'
            result['skip_reason'] = f'Receipt movement type {bwart} excluded'
            rows.append(result)
            continue
        if bwart and bwart not in CONSUMPTION_MOVEMENT_TYPES and bwart not in REVERSAL_MAP:
            result['parse_warnings'].append(f'unrecognized_movement_type:{bwart}')

        is_reversal = bwart in REVERSAL_MAP

        # Parse posting date
        raw_date = row.get('BUDAT', '').strip()
        activity_date = parse_sap_date(raw_date)
        if not activity_date:
            result['parse_warnings'].append('unparseable_date')
            result['parse_status'] = 'FLAGGED'
        else:
            if activity_date > today:
                result['parse_warnings'].append('suspicious_date:future')
                result['parse_status'] = 'FLAGGED'
            elif activity_date < three_years_ago:
                result['parse_warnings'].append('suspicious_date:too_old')
                result['parse_status'] = 'FLAGGED'
        result['activity_date'] = activity_date
        result['period_start'] = activity_date
        result['period_end'] = activity_date

        # Parse quantity
        raw_menge = row.get('MENGE', '').strip()
        menge = parse_german_decimal(raw_menge, decimal_sep)
        if menge is None:
            result['parse_warnings'].append('unparseable_quantity')
            result['parse_status'] = 'FLAGGED'
            rows.append(result)
            continue

        # Reversal documents have negative quantities — preserve sign
        if is_reversal and menge > 0:
            menge = -menge

        raw_unit = row.get('MEINS', '').strip().upper()
        if not raw_unit:
            result['parse_warnings'].append('missing_unit')
            result['parse_status'] = 'FLAGGED'

        result['raw_quantity'] = menge
        result['raw_unit'] = raw_unit

        # Normalize quantity and unit
        if menge is not None and raw_unit:
            norm_qty, norm_unit = normalize_quantity_unit(menge, raw_unit)
            result['normalized_quantity'] = norm_qty
            result['normalized_unit'] = norm_unit
        else:
            norm_qty, norm_unit = menge, raw_unit
            result['normalized_quantity'] = norm_qty
            result['normalized_unit'] = norm_unit

        # Skip pieces (no emissions calculation possible)
        if norm_unit == 'ST':
            result['parse_status'] = 'SKIPPED'
            result['skip_reason'] = 'Piece unit (ST) — not applicable for emissions'
            rows.append(result)
            continue

        # Material classification
        matnr = strip_sap_leading_zeros(row.get('MATNR', ''))
        maktx = row.get('MAKTX', '')
        fuel_type, scope, category = classify_material(matnr, maktx)

        result['scope'] = scope
        result['category'] = category
        result['fuel_type'] = fuel_type

        if fuel_type == 'UNKNOWN':
            result['parse_warnings'].append('material_unclassified')
            if result['parse_status'] == 'OK':
                result['parse_status'] = 'FLAGGED'

        # Compute emissions for classified fuel materials
        if fuel_type not in ('UNKNOWN', '') and norm_qty is not None:
            emissions = compute_fuel_co2e(fuel_type, abs(norm_qty), norm_unit)
            if emissions:
                # Preserve sign for reversals
                sign = Decimal('-1') if norm_qty < 0 else Decimal('1')
                result['co2e_kg'] = emissions['co2e_kg'] * sign
                result['co2_kg'] = emissions['co2_kg'] * sign
                result['ch4_kg'] = emissions['ch4_kg'] * sign
                result['n2o_kg'] = emissions['n2o_kg'] * sign
            else:
                result['parse_warnings'].append(f'no_emission_factor:{fuel_type}:{norm_unit}')
                if result['parse_status'] == 'OK':
                    result['parse_status'] = 'FLAGGED'

        if result['parse_warnings']:
            warnings_count += 1

        rows.append(result)

    metadata = {
        'encoding': encoding,
        'delimiter': delimiter,
        'decimal_sep': decimal_sep,
        'has_german_headers': hints['has_german_headers'],
        'total_rows': len(rows),
        'warnings_count': warnings_count,
    }

    return rows, metadata
