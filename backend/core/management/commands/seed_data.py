"""
Management command: seed_data
Creates demo tenant, facilities, users, and ingests sample files.
Run: python manage.py seed_data
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import User
from django.core.files.base import ContentFile
from core.models import Tenant, Facility, TenantUser


SAMPLE_SAP_EN = """Material,Material Description,Document Number,Item,Posting Date,Document Date,Quantity,Unit of Measure,Plant,Storage Location,Movement Type,Cost Center,Amount in LC,Currency
DIESEL-001,Diesel Fuel B7,4900012345,1,2024-01-15,2024-01-15,500.000,L,DE01,TK01,201,DE01-MAINT,750.00,EUR
DIESEL-001,Diesel Fuel B7,4900012346,1,2024-01-22,2024-01-20,1200.000,L,DE01,TK01,261,DE01-PROD,1800.00,EUR
NATGAS-002,Natural Gas H-Type,4900012347,1,2024-01-31,2024-01-31,45.500,M3,UK03,GAS1,201,UK03-PROD,135.00,GBP
PETROL-001,Unleaded Petrol 95,4900012348,1,2024-02-05,2024-02-05,300.000,L,UK03,TK02,201,UK03-FLEET,420.00,GBP
ELEC-003,Grid Electricity 400V,4900012349,1,2024-02-10,2024-02-10,12500.000,KWH,DE01,UTIL,201,DE01-FAC,3562.50,EUR
OFFICE-SUP,Office Paper A4 80gsm,4900012350,1,2024-02-15,2024-02-15,50.000,KG,UK03,STORE,201,UK03-ADMIN,85.00,GBP
DIESEL-001,Diesel Fuel B7,4900012351,1,2024-03-01,2024-03-01,800.000,L,IN02,TK03,201,IN02-PROD,960.00,USD
LPG-001,LPG Industrial Grade,4900012352,1,2024-03-10,2024-03-10,200.000,L,DE01,GAS2,201,DE01-PROD,280.00,EUR
DIESEL-001,Diesel Fuel B7,4900012353,1,2024-03-22,2024-03-22,-300.000,L,DE01,TK01,202,DE01-MAINT,-450.00,EUR
DIESEL-001,Diesel Fuel B7,4900012354,1,2024-03-28,2024-03-28,650.000,L,UK03,TK02,261,UK03-FLEET,975.00,GBP
NATGAS-002,Natural Gas H-Type,4900012355,1,2024-04-05,2024-04-05,32.800,M3,IN02,GAS3,201,IN02-HEAT,98.40,USD
UNKNOWN-MAT,Custom Cleaning Chemical XR,4900012356,1,2024-04-10,2024-04-10,15.000,KG,DE01,CHEM,201,DE01-MAINT,225.00,EUR
DIESEL-001,Diesel Fuel B7,4900099999,1,2026-12-01,2026-12-01,100.000,L,DE01,TK01,201,DE01-MAINT,150.00,EUR
PETROL-001,Unleaded Petrol 95,4900012357,1,2024-04-20,2024-04-20,180.000,L,UK03,TK02,201,UK03-FLEET,252.00,GBP
HEATING-OIL,Heating Oil Red,4900012358,1,2024-04-25,2024-04-25,750.000,L,DE01,OIL1,201,DE01-HEAT,1050.00,EUR
"""

SAMPLE_SAP_DE = (
    "Material;Materialkurztext;Belegnummer;Position;Buchungsdatum;Menge;Mengeneinheit;Werk;Lagerort;Bewegungsart;Kostenstelle;Betrag in HW;Waehrung\n"
    "DIESEL-001;Dieselkraftstoff B7;4900009001;1;15.01.2024;500,000;L;1000;TK01;201;1000-WART;750,00;EUR\n"
    "DIESEL-001;Dieselkraftstoff B7;4900009002;1;22.01.2024;1.200,000;L;1000;TK01;261;;;1.800,00;EUR\n"
    "NATGAS-002;Erdgas H-Typ;4900009003;1;31.01.2024;45,500;M3;2000;GAS1;201;2000-PROD;135,00;EUR\n"
    "PETROL-001;Kraftstoff Benzin 95;4900009004;1;05.02.2024;300,000;L;3000;TK02;201;3000-FUHR;420,00;EUR\n"
)


SAMPLE_UTILITY_GB = """TYPE,DATE,START DATE,END DATE,USAGE,UNITS,COST,NOTES
Electric usage,2024-01-15,2023-12-18,2024-01-15,8420,kWh,£1563.11,
Electric usage,2024-02-14,2024-01-16,2024-02-14,7760,kWh,£1440.94,Estimated
Electric usage,2024-03-15,2024-02-15,2024-03-15,8100,kWh,£1503.60,
Electric usage,2024-04-16,2024-03-16,2024-04-16,6940,kWh,£1288.49,
Electric usage,2024-05-14,2024-04-17,2024-05-14,5820,kWh,£1080.26,
"""

SAMPLE_UTILITY_UK_HH = """Consumption (kWh),Start,End
0.213,2024-01-15T00:00:00+00:00,2024-01-15T00:30:00+00:00
0.198,2024-01-15T00:30:00+00:00,2024-01-15T01:00:00+00:00
0.205,2024-01-15T01:00:00+00:00,2024-01-15T01:30:00+00:00
0.312,2024-01-15T01:30:00+00:00,2024-01-15T02:00:00+00:00
0.287,2024-01-15T02:00:00+00:00,2024-01-15T02:30:00+00:00
"""

SAMPLE_TRAVEL = """Report_ID,Report_Name,Employee_Name,Employee_ID,Department,Cost_Center,Transaction_Date,Expense_Type_Code,Expense_Type,Vendor,Amount,Currency,Origin,Destination,Class_of_Service,Hotel_Nights,Distance,Distance_Unit,Country_Code,Country
RPT-2024-001,Q1 Business Travel,Priya Sharma,EMP-101,Engineering,CC-ENG,2024-01-20,AIRFR,Air Travel,British Airways,850.00,GBP,BOM,LHR,C,,,,,
RPT-2024-001,Q1 Business Travel,Priya Sharma,EMP-101,Engineering,CC-ENG,2024-01-21,HOTEL,Hotel,Hilton London Heathrow,,GBP,,,,,3,,GB,United Kingdom
RPT-2024-001,Q1 Business Travel,Priya Sharma,EMP-101,Engineering,CC-ENG,2024-01-24,AIRFR,Air Travel,British Airways,850.00,GBP,LHR,BOM,Y,,,,,
RPT-2024-002,NYC Client Visit,James Chen,EMP-205,Sales,CC-SALES,2024-02-05,AIRFR,Air Travel,United Airlines,1200.00,USD,LHR,JFK,C,,,,,
RPT-2024-002,NYC Client Visit,James Chen,EMP-205,Sales,CC-SALES,2024-02-05,HOTEL,Hotel,Marriott Times Square,,USD,,,,,4,,US,United States
RPT-2024-002,NYC Client Visit,James Chen,EMP-205,Sales,CC-SALES,2024-02-08,CARRT,Car Rental,Hertz,280.00,USD,,,,,,350,miles,,
RPT-2024-002,NYC Client Visit,James Chen,EMP-205,Sales,CC-SALES,2024-02-09,AIRFR,Air Travel,United Airlines,1200.00,USD,JFK,LHR,Y,,,,,
RPT-2024-003,Singapore Summit,Aisha Okonkwo,EMP-318,Operations,CC-OPS,2024-03-12,AIRFR,Air Travel,Singapore Airlines,2100.00,GBP,LHR,SIN,C,,,,,
RPT-2024-003,Singapore Summit,Aisha Okonkwo,EMP-318,Operations,CC-OPS,2024-03-13,HOTEL,Hotel,Marina Bay Sands,,SGD,,,,,3,,SG,Singapore
RPT-2024-003,Singapore Summit,Aisha Okonkwo,EMP-318,Operations,CC-OPS,2024-03-13,TAXCB,Taxi,GRAB,45.00,SGD,,,,,,,,SG,Singapore
RPT-2024-003,Singapore Summit,Aisha Okonkwo,EMP-318,Operations,CC-OPS,2024-03-15,AIRFR,Air Travel,Singapore Airlines,2100.00,GBP,SIN,LHR,Y,,,,,
RPT-2024-004,Berlin Conference,Tom Mueller,EMP-412,Finance,CC-FIN,2024-03-20,AIRFR,Air Travel,Lufthansa,420.00,EUR,LHR,FRA,Y,,,,,
RPT-2024-004,Berlin Conference,Tom Mueller,EMP-412,Finance,CC-FIN,2024-03-20,TRAIN,Train,Deutsche Bahn,89.00,EUR,,,,,,300,km,DE,Germany
RPT-2024-004,Berlin Conference,Tom Mueller,EMP-412,Finance,CC-FIN,2024-03-21,HOTEL,Hotel,Hilton Berlin,,EUR,,,,,2,,DE,Germany
RPT-2024-005,Unknown Route,Test User,EMP-999,Test,CC-TEST,2024-04-01,AIRFR,Air Travel,Test Airline,500.00,GBP,XYZ,ABC,Y,,,,,
RPT-2024-005,Unknown Route,Test User,EMP-999,Test,CC-TEST,2024-04-10,HOTEL,Hotel,Test Hotel,,GBP,,,,,1,,US,United States
RPT-2024-006,Melbourne Trip,Sarah Thompson,EMP-523,Marketing,CC-MKT,2024-04-15,AIRFR,Air Travel,Qantas,3200.00,GBP,LHR,MEL,C,,,,,
RPT-2024-006,Melbourne Trip,Sarah Thompson,EMP-523,Marketing,CC-MKT,2024-04-16,HOTEL,Hotel,Crown Towers Melbourne,,AUD,,,,,5,,AU,Australia
RPT-2024-006,Melbourne Trip,Sarah Thompson,EMP-523,Marketing,CC-MKT,2024-04-20,AIRFR,Air Travel,Qantas,3200.00,GBP,MEL,LHR,Y,,,,,
"""


class Command(BaseCommand):
    help = 'Seed database with demo tenant, users, facilities, and sample data'

    def handle(self, *args, **kwargs):
        self.stdout.write('Seeding database...')

        # Create tenant
        tenant, _ = Tenant.objects.get_or_create(
            slug='acme-corp',
            defaults={'name': 'ACME Corporation Global'}
        )

        # Create facilities
        facilities = [
            Facility.objects.get_or_create(
                tenant=tenant,
                facility_name='Munich Manufacturing Plant',
                defaults={
                    'country_code': 'DE',
                    'grid_region_code': 'DE',
                    'sap_plant_codes': 'DE01,1000,2000',
                    'latitude': 48.1351,
                    'longitude': 11.5820,
                }
            )[0],
            Facility.objects.get_or_create(
                tenant=tenant,
                facility_name='London Headquarters',
                defaults={
                    'country_code': 'GB',
                    'grid_region_code': 'GB',
                    'sap_plant_codes': 'UK03,3000',
                    'latitude': 51.5074,
                    'longitude': -0.1278,
                }
            )[0],
            Facility.objects.get_or_create(
                tenant=tenant,
                facility_name='Bangalore Technology Centre',
                defaults={
                    'country_code': 'IN',
                    'grid_region_code': 'IN',
                    'sap_plant_codes': 'IN02',
                    'latitude': 12.9716,
                    'longitude': 77.5946,
                }
            )[0],
        ]

        # Create admin user
        admin_user, created = User.objects.get_or_create(
            username='admin@esg.com',
            defaults={
                'email': 'admin@esg.com',
                'first_name': 'Alex',
                'last_name': 'Analyst',
                'is_staff': True,
            }
        )
        if created:
            admin_user.set_password('admin123')
            admin_user.save()

        TenantUser.objects.get_or_create(
            user=admin_user,
            defaults={'tenant': tenant, 'role': 'analyst'}
        )

        # Create viewer user
        viewer_user, created = User.objects.get_or_create(
            username='viewer',
            defaults={
                'email': 'viewer@acme-corp.com',
                'first_name': 'Vic',
                'last_name': 'Viewer',
            }
        )
        if created:
            viewer_user.set_password('breathesg2024')
            viewer_user.save()

        TenantUser.objects.get_or_create(
            user=viewer_user,
            defaults={'tenant': tenant, 'role': 'viewer'}
        )

        from ingestion.services import ingest_file
        from ingestion.models import RawIngestionLog

        samples = [
            ('sap_sample_en.csv', 'SAP', SAMPLE_SAP_EN.encode('utf-8'), facilities[0]),
            ('sap_sample_de.csv', 'SAP', SAMPLE_SAP_DE.encode('utf-8'), facilities[0]),
            ('utility_greenbutton.csv', 'UTILITY', SAMPLE_UTILITY_GB.encode('utf-8'), facilities[1]),
            ('utility_uk_hh.csv', 'UTILITY', SAMPLE_UTILITY_UK_HH.encode('utf-8'), facilities[1]),
            ('travel_concur.csv', 'TRAVEL', SAMPLE_TRAVEL.encode('utf-8'), None),
        ]

        for filename, source_type, content, facility in samples:
            # Skip if already ingested (idempotent by SHA-256)
            import hashlib
            file_hash = hashlib.sha256(content).hexdigest()
            if not RawIngestionLog.objects.filter(
                tenant=tenant, file_sha256=file_hash
            ).exists():

                try:
                    batch = ingest_file(
                        file_content=content,
                        original_filename=filename,
                        source_type=source_type,
                        tenant=tenant,
                        uploaded_by=admin_user,
                        facility=facility,
                        grid_region_code='GB',
                        facility_country='GB',
                    )
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'  Ingested {filename}: {batch.parsed_rows} parsed, '
                            f'{batch.flagged_rows} flagged'
                        )
                    )
                except Exception as e:
                    self.stdout.write(self.style.WARNING(f'  {filename}: {e}'))

        self.stdout.write(self.style.SUCCESS('\nSeed complete!'))
        self.stdout.write('Login credentials:')
        self.stdout.write('  Username: analyst  Password: breathesg2024')
        self.stdout.write('  Username: viewer   Password: breathesg2024')
