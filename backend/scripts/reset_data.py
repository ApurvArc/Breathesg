import os
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breathesg.settings')
django.setup()

from review.models import StagingRecord
from emissions.models import LedgerEntry

def reset_data():
    print("Clearing ingested records...")
    deleted_staging, _ = StagingRecord.objects.all().delete()
    print(f"Deleted {deleted_staging} staging records.")

    print("Clearing audit ledger...")
    deleted_ledger, _ = LedgerEntry.objects.all().delete()
    print(f"Deleted {deleted_ledger} ledger entries.")

    print("\nData successfully cleared! You can now start fresh.")

if __name__ == '__main__':
    reset_data()
