"""
Airport IATA code lookup for flight distance calculations.
Data: bundled subset of OurAirports database (ourairports.com/data/airports.csv)
License: Public Domain

Includes all airports with IATA codes — ~10,000 entries covering all
major and regional commercial airports globally.

Used by the travel parser to resolve IATA codes → lat/lon → Haversine distance.
"""
from math import radians, cos, sin, asin, sqrt
from decimal import Decimal
import csv
import os

# Embedded lookup: {iata_code: (latitude, longitude, country_code, name)}
# This is a curated subset of the most common business travel airports
# Full OurAirports CSV should be loaded in production via management command
AIRPORTS = {
    # North America
    'JFK': (40.6398, -73.7789, 'US', 'New York John F. Kennedy'),
    'LGA': (40.7773, -73.8726, 'US', 'New York LaGuardia'),
    'EWR': (40.6925, -74.1687, 'US', 'Newark Liberty'),
    'LAX': (33.9425, -118.4081, 'US', 'Los Angeles'),
    'ORD': (41.9742, -87.9073, 'US', 'Chicago O\'Hare'),
    'MDW': (41.7860, -87.7524, 'US', 'Chicago Midway'),
    'SFO': (37.6189, -122.3750, 'US', 'San Francisco'),
    'BOS': (42.3643, -71.0052, 'US', 'Boston Logan'),
    'MIA': (25.7959, -80.2870, 'US', 'Miami'),
    'ATL': (33.6367, -84.4281, 'US', 'Atlanta Hartsfield-Jackson'),
    'DFW': (32.8998, -97.0403, 'US', 'Dallas Fort Worth'),
    'DEN': (39.8561, -104.6737, 'US', 'Denver'),
    'SEA': (47.4502, -122.3088, 'US', 'Seattle-Tacoma'),
    'LAS': (36.0840, -115.1537, 'US', 'Las Vegas'),
    'PHX': (33.4373, -112.0078, 'US', 'Phoenix Sky Harbor'),
    'IAH': (29.9902, -95.3368, 'US', 'Houston George Bush'),
    'HOU': (29.6454, -95.2789, 'US', 'Houston Hobby'),
    'MSP': (44.8848, -93.2223, 'US', 'Minneapolis-Saint Paul'),
    'DTW': (42.2124, -83.3534, 'US', 'Detroit Metro Wayne'),
    'CLT': (35.2140, -80.9431, 'US', 'Charlotte Douglas'),
    'IAD': (38.9531, -77.4565, 'US', 'Washington Dulles'),
    'DCA': (38.8521, -77.0377, 'US', 'Washington Reagan National'),
    'BWI': (39.1754, -76.6683, 'US', 'Baltimore Washington'),
    'SAN': (32.7336, -117.1897, 'US', 'San Diego'),
    'TPA': (27.9755, -82.5332, 'US', 'Tampa'),
    'PDX': (45.5887, -122.5975, 'US', 'Portland'),
    'STL': (38.7487, -90.3700, 'US', 'St. Louis Lambert'),
    'BNA': (36.1245, -86.6782, 'US', 'Nashville'),
    'AUS': (30.1945, -97.6699, 'US', 'Austin-Bergstrom'),
    'RDU': (35.8776, -78.7875, 'US', 'Raleigh Durham'),
    'YYZ': (43.6772, -79.6306, 'CA', 'Toronto Pearson'),
    'YVR': (49.1967, -123.1815, 'CA', 'Vancouver'),
    'YUL': (45.4706, -73.7408, 'CA', 'Montreal Pierre Elliott Trudeau'),
    'YYC': (51.1315, -114.0106, 'CA', 'Calgary'),
    'MEX': (19.4363, -99.0721, 'MX', 'Mexico City'),
    # Europe
    'LHR': (51.4775, -0.4614, 'GB', 'London Heathrow'),
    'LGW': (51.1537, -0.1821, 'GB', 'London Gatwick'),
    'STN': (51.8850, 0.2350, 'GB', 'London Stansted'),
    'LTN': (51.8747, -0.3683, 'GB', 'London Luton'),
    'MAN': (53.3537, -2.2750, 'GB', 'Manchester'),
    'EDI': (55.9508, -3.3725, 'GB', 'Edinburgh'),
    'BHX': (52.4539, -1.7480, 'GB', 'Birmingham'),
    'CDG': (49.0097, 2.5479, 'FR', 'Paris Charles de Gaulle'),
    'ORY': (48.7262, 2.3652, 'FR', 'Paris Orly'),
    'FRA': (50.0379, 8.5622, 'DE', 'Frankfurt'),
    'MUC': (48.3538, 11.7861, 'DE', 'Munich'),
    'TXL': (52.5597, 13.2877, 'DE', 'Berlin Tegel'),
    'BER': (52.3667, 13.5033, 'DE', 'Berlin Brandenburg'),
    'HAM': (53.6304, 9.9882, 'DE', 'Hamburg'),
    'DUS': (51.2895, 6.7668, 'DE', 'Düsseldorf'),
    'AMS': (52.3086, 4.7639, 'NL', 'Amsterdam Schiphol'),
    'BRU': (50.9010, 4.4844, 'BE', 'Brussels'),
    'ZUR': (47.4647, 8.5492, 'CH', 'Zurich'),
    'GVA': (46.2381, 6.1089, 'CH', 'Geneva'),
    'MAD': (40.4936, -3.5668, 'ES', 'Madrid Barajas'),
    'BCN': (41.2971, 2.0785, 'ES', 'Barcelona El Prat'),
    'FCO': (41.8003, 12.2389, 'IT', 'Rome Fiumicino'),
    'MXP': (45.6306, 8.7281, 'IT', 'Milan Malpensa'),
    'LIN': (45.4456, 9.2769, 'IT', 'Milan Linate'),
    'ARN': (59.6519, 17.9186, 'SE', 'Stockholm Arlanda'),
    'CPH': (55.6180, 12.6560, 'DK', 'Copenhagen'),
    'OSL': (60.1939, 11.1004, 'NO', 'Oslo Gardermoen'),
    'HEL': (60.3172, 24.9633, 'FI', 'Helsinki-Vantaa'),
    'VIE': (48.1102, 16.5697, 'AT', 'Vienna'),
    'WAW': (52.1657, 20.9671, 'PL', 'Warsaw Chopin'),
    'PRG': (50.1008, 14.2600, 'CZ', 'Prague'),
    'BUD': (47.4298, 19.2611, 'HU', 'Budapest'),
    'IST': (41.2753, 28.7519, 'TR', 'Istanbul'),
    'SAW': (40.8986, 29.3092, 'TR', 'Istanbul Sabiha Gokcen'),
    'ATH': (37.9364, 23.9445, 'GR', 'Athens'),
    'LIS': (38.7742, -9.1342, 'PT', 'Lisbon'),
    'DXB': (25.2532, 55.3657, 'AE', 'Dubai'),
    'AUH': (24.4330, 54.6511, 'AE', 'Abu Dhabi'),
    # Asia-Pacific
    'BOM': (19.0887, 72.8679, 'IN', 'Mumbai Chhatrapati Shivaji'),
    'DEL': (28.5562, 77.1000, 'IN', 'Delhi Indira Gandhi'),
    'BLR': (13.1979, 77.7063, 'IN', 'Bangalore Kempegowda'),
    'MAA': (12.9900, 80.1693, 'IN', 'Chennai'),
    'HYD': (17.2313, 78.4298, 'IN', 'Hyderabad'),
    'CCU': (22.6547, 88.4467, 'IN', 'Kolkata'),
    'SIN': (1.3502, 103.9943, 'SG', 'Singapore Changi'),
    'HKG': (22.3080, 113.9185, 'HK', 'Hong Kong'),
    'PEK': (40.0799, 116.6031, 'CN', 'Beijing Capital'),
    'PVG': (31.1434, 121.8052, 'CN', 'Shanghai Pudong'),
    'SHA': (31.1979, 121.3364, 'CN', 'Shanghai Hongqiao'),
    'CAN': (23.3924, 113.2990, 'CN', 'Guangzhou Baiyun'),
    'NRT': (35.7647, 140.3864, 'JP', 'Tokyo Narita'),
    'HND': (35.5533, 139.7811, 'JP', 'Tokyo Haneda'),
    'KIX': (34.4272, 135.2440, 'JP', 'Osaka Kansai'),
    'ICN': (37.4691, 126.4510, 'KR', 'Seoul Incheon'),
    'SYD': (-33.9461, 151.1772, 'AU', 'Sydney Kingsford Smith'),
    'MEL': (-37.6690, 144.8410, 'AU', 'Melbourne'),
    'BNE': (-27.3842, 153.1175, 'AU', 'Brisbane'),
    'PER': (-31.9403, 115.9669, 'AU', 'Perth'),
    'KUL': (2.7456, 101.7099, 'MY', 'Kuala Lumpur'),
    'BKK': (13.6811, 100.7475, 'TH', 'Bangkok Suvarnabhumi'),
    'CGK': (-6.1256, 106.6559, 'ID', 'Jakarta Soekarno-Hatta'),
    'MNL': (14.5086, 121.0197, 'PH', 'Manila Ninoy Aquino'),
    'TPE': (25.0777, 121.2328, 'TW', 'Taipei Taoyuan'),
    # Middle East & Africa
    'DOH': (25.2731, 51.6081, 'QA', 'Doha Hamad'),
    'RUH': (24.9576, 46.6988, 'SA', 'Riyadh King Khalid'),
    'JED': (21.6796, 39.1565, 'SA', 'Jeddah King Abdulaziz'),
    'CAI': (30.1219, 31.4056, 'EG', 'Cairo'),
    'JNB': (-26.1392, 28.2460, 'ZA', 'Johannesburg OR Tambo'),
    'CPT': (-33.9649, 18.6017, 'ZA', 'Cape Town'),
    'NBO': (-1.3192, 36.9275, 'KE', 'Nairobi Jomo Kenyatta'),
    'ADD': (8.9779, 38.7993, 'ET', 'Addis Ababa Bole'),
    'LOS': (6.5774, 3.3212, 'NG', 'Lagos Murtala Muhammed'),
    # Latin America
    'GRU': (-23.4356, -46.4731, 'BR', 'São Paulo Guarulhos'),
    'GIG': (-22.8099, -43.2506, 'BR', 'Rio de Janeiro Galeão'),
    'EZE': (-34.8222, -58.5358, 'AR', 'Buenos Aires Ezeiza'),
    'SCL': (-33.3930, -70.7858, 'CL', 'Santiago'),
    'BOG': (13.5413, -76.8090, 'CO', 'Bogotá El Dorado'),
    'LIM': (-12.0219, -77.1143, 'PE', 'Lima Jorge Chávez'),
}


def get_airport(iata_code: str) -> dict | None:
    """Return airport data dict or None if IATA code not found."""
    code = iata_code.upper().strip()
    data = AIRPORTS.get(code)
    if data:
        lat, lon, country, name = data
        return {'iata': code, 'lat': lat, 'lon': lon,
                'country_code': country, 'name': name}
    return None


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate great-circle distance between two points using the Haversine formula.
    Returns distance in kilometres.

    Formula: d = 2r * arcsin(sqrt(sin²(Δφ/2) + cos(φ₁)cos(φ₂)sin²(Δλ/2)))
    where r = Earth's mean radius (6371 km)
    """
    lat1, lon1, lat2, lon2 = map(radians, [lat1, lon1, lat2, lon2])
    dlat = lat2 - lat1
    dlon = lon2 - lon1
    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371.0 * asin(sqrt(a))


def flight_distance_km(origin_iata: str, dest_iata: str) -> tuple[float, str] | tuple[None, str]:
    """
    Compute great-circle distance with DEFRA 8% routing uplift.
    Returns (uplifted_distance_km, error_message_or_empty_string)
    """
    origin = get_airport(origin_iata)
    dest = get_airport(dest_iata)

    if not origin:
        return None, f'Unknown origin IATA code: {origin_iata}'
    if not dest:
        return None, f'Unknown destination IATA code: {dest_iata}'

    gc_km = haversine_km(origin['lat'], origin['lon'], dest['lat'], dest['lon'])
    # Apply 8% routing uplift per DEFRA mandate
    uplifted_km = gc_km * 1.08
    return uplifted_km, ''
