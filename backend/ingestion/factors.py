"""
Emission Factor Engine — DEFRA 2025 + EPA eGRID 2025 factors.

Design note: factors are seeded to the EmissionFactor database via management
command (seed_factors). At calculation time, the engine queries the DB for the
correct factor. The FK is frozen in CarbonLedger at approval time so future
factor updates never silently alter historical inventories.
"""
from decimal import Decimal


# ─────────────────────────────────────────────────────────────────────────────
# DEFRA 2025 Aviation Factors (with Radiative Forcing)
# Source: UK DESNZ/DEFRA Greenhouse Gas Conversion Factors 2025
# RF included: accounts for contrails, NOx, water vapor at altitude
# Haul classification: short-haul < 3700 km, long-haul >= 3700 km
# ─────────────────────────────────────────────────────────────────────────────
DEFRA_2025_AVIATION = {
    # (haul_type, cabin_class): kg CO2e per passenger-km (with RF)
    ('SHORT', 'ECONOMY'):  Decimal('0.11604'),
    ('SHORT', 'BUSINESS'): Decimal('0.18727'),
    ('SHORT', 'AVERAGE'):  Decimal('0.15152'),
    ('LONG',  'ECONOMY'):  Decimal('0.12485'),
    ('LONG',  'BUSINESS'): Decimal('0.33652'),
    ('LONG',  'FIRST'):    Decimal('0.43663'),
    ('LONG',  'AVERAGE'):  Decimal('0.19500'),  # weighted average
}

SHORT_HAUL_MAX_KM = Decimal('3700')
ROUTING_UPLIFT = Decimal('1.08')  # 8% above great circle (DEFRA mandated)
EARTH_RADIUS_KM = 6371.0


# ─────────────────────────────────────────────────────────────────────────────
# DEFRA 2025 Hotel Factors
# Source: Cornell Hotel Sustainability Benchmarking Index + DEFRA 2025
# Unit: kg CO2e per room-night
# ─────────────────────────────────────────────────────────────────────────────
DEFRA_2025_HOTEL = {
    'GB': Decimal('10.4'),
    'US': Decimal('16.1'),
    'DE': Decimal('13.2'),
    'FR': Decimal('6.7'),
    'ES': Decimal('7.0'),
    'CA': Decimal('7.4'),
    'AU': Decimal('11.8'),
    'IN': Decimal('9.2'),
    'JP': Decimal('8.6'),
    'CN': Decimal('14.5'),
    'SG': Decimal('19.3'),
    'AE': Decimal('21.0'),
    'MV': Decimal('152.0'),  # Maldives — diesel generators
    'CR': Decimal('4.7'),    # Costa Rica — high renewables
    'DEFAULT': Decimal('12.0'),
}


# ─────────────────────────────────────────────────────────────────────────────
# DEFRA 2025 Ground Transport Factors
# Unit: kg CO2e per km
# ─────────────────────────────────────────────────────────────────────────────
DEFRA_2025_GROUND = {
    'CAR_PETROL':     Decimal('0.16272'),
    'CAR_DIESEL':     Decimal('0.17304'),
    'CAR_EV':         Decimal('0.04047'),
    'CAR_HYBRID':     Decimal('0.12825'),
    'CAR_UNKNOWN':    Decimal('0.16272'),  # default to petrol
    'TAXI':           Decimal('0.14910'),
    'RAIL_UK':        Decimal('0.03546'),
    'BUS':            Decimal('0.10385'),
}

# Average km per rental day (used when distance not provided by Concur)
AVG_KM_PER_RENTAL_DAY = Decimal('80')


# ─────────────────────────────────────────────────────────────────────────────
# DEFRA 2025 Fuel Combustion Factors (Scope 1)
# Unit: kg CO2e per litre (diesel, petrol, LPG) or per m3 (natural gas)
# ─────────────────────────────────────────────────────────────────────────────
DEFRA_2025_FUEL = {
    # (fuel_type): (kg_co2e_per_L, kg_co2_per_L, kg_ch4_per_L, kg_n2o_per_L)
    'DIESEL': {
        'co2e_per_L':  Decimal('2.62900'),
        'co2_per_L':   Decimal('2.60720'),
        'ch4_per_L':   Decimal('0.00017'),
        'n2o_per_L':   Decimal('0.00163'),
        'unit':        'L',
    },
    'PETROL': {
        'co2e_per_L':  Decimal('2.31200'),
        'co2_per_L':   Decimal('2.29400'),
        'ch4_per_L':   Decimal('0.00016'),
        'n2o_per_L':   Decimal('0.00140'),
        'unit':        'L',
    },
    'LPG': {
        'co2e_per_L':  Decimal('1.56000'),
        'co2_per_L':   Decimal('1.49500'),
        'ch4_per_L':   Decimal('0.00011'),
        'n2o_per_L':   Decimal('0.00089'),
        'unit':        'L',
    },
    'NATGAS': {
        'co2e_per_M3': Decimal('2.04400'),  # per cubic metre
        'co2_per_M3':  Decimal('2.02000'),
        'ch4_per_M3':  Decimal('0.00100'),
        'n2o_per_M3':  Decimal('0.00040'),
        'unit':        'M3',
    },
    'HEATING_OIL': {
        'co2e_per_L':  Decimal('2.51990'),
        'co2_per_L':   Decimal('2.51800'),
        'ch4_per_L':   Decimal('0.00012'),
        'n2o_per_L':   Decimal('0.00108'),
        'unit':        'L',
    },
}


# ─────────────────────────────────────────────────────────────────────────────
# EPA eGRID 2025 Electricity Factors
# Source: EPA eGRID 2025 (2023 operational year data)
# Unit: lb CO2e per MWh → converted to kg CO2e per kWh in code
# ─────────────────────────────────────────────────────────────────────────────
EGRID_2025 = {
    # subregion_code: lb_co2e_per_MWh
    'CAMX': Decimal('429.983'),   # California
    'ERCT': Decimal('736.629'),   # Texas (ERCOT)
    'SRMW': Decimal('1248.582'),  # SERC Midwest
    'AZNM': Decimal('706.189'),   # Southwest
    'FRCC': Decimal('784.785'),   # Florida
    'NYCW': Decimal('369.100'),   # NYC (very low — lots of nuclear/hydro)
    'NYUP': Decimal('111.900'),   # Upstate NY (heavy hydro)
    'NEWE': Decimal('535.800'),   # New England
    'RFCE': Decimal('592.100'),   # RFC East (Mid-Atlantic)
    'RFCM': Decimal('1029.200'),  # RFC Michigan
    'RFCW': Decimal('856.600'),   # RFC West
    'SRSO': Decimal('798.900'),   # SERC South
    'SRVC': Decimal('467.900'),   # SERC Virginia/Carolina
    'NWPP': Decimal('479.600'),   # Northwest Power Pool
    'RMPA': Decimal('1000.200'),  # Rocky Mountain
    'SPNO': Decimal('858.000'),   # SPP North
    'SPSO': Decimal('944.800'),   # SPP South
    'HIOA': Decimal('1392.100'),  # Hawaii (Oahu)
    'HIMS': Decimal('1607.900'),  # Hawaii (Maui/Molokai/Lanai)
    'AKGD': Decimal('1148.600'),  # Alaska
    'DEFAULT': Decimal('800.000'),  # fallback US average
}

# UK Grid factor (DEFRA/DESNZ 2024, valid for 2024 reporting year)
UK_GRID_KG_CO2E_PER_KWH = Decimal('0.20705')   # Scope 2 (generation)
UK_GRID_TD_KG_CO2E_PER_KWH = Decimal('0.01830')  # Scope 3 (T&D losses)


def lb_per_mwh_to_kg_per_kwh(lb_per_mwh: Decimal) -> Decimal:
    """Convert EPA eGRID factor from lb/MWh to kg/kWh."""
    return lb_per_mwh * Decimal('0.453592') / Decimal('1000')


def get_egrid_factor_kg_per_kwh(subregion_code: str) -> Decimal:
    """Return kg CO2e per kWh for the given eGRID subregion."""
    lb_factor = EGRID_2025.get(subregion_code.upper(), EGRID_2025['DEFAULT'])
    return lb_per_mwh_to_kg_per_kwh(lb_factor)


def classify_flight_haul(distance_km: Decimal) -> str:
    """Classify flight as SHORT or LONG haul per DEFRA 2025 definition."""
    return 'SHORT' if distance_km < SHORT_HAUL_MAX_KM else 'LONG'


def normalize_cabin_class(raw_class: str) -> str:
    """Normalize varied cabin class strings to ECONOMY/BUSINESS/FIRST/AVERAGE."""
    raw = raw_class.upper().strip()
    if raw in ('Y', 'M', 'H', 'K', 'L', 'Q', 'T', 'V', 'W', 'ECONOMY',
               'COACH', 'STANDARD', 'ECONOMY CLASS'):
        return 'ECONOMY'
    if raw in ('C', 'J', 'D', 'I', 'Z', 'BUSINESS', 'BUSINESS CLASS',
               'PREMIUM BUSINESS', 'J CLASS'):
        return 'BUSINESS'
    if raw in ('F', 'A', 'FIRST', 'FIRST CLASS', 'PREMIUM FIRST'):
        return 'FIRST'
    if raw in ('W', 'PREMIUM ECONOMY', 'PREMIUM', 'PE'):
        # Treat premium economy as halfway between economy and business
        return 'ECONOMY'  # conservative — use economy factor
    return 'AVERAGE'
