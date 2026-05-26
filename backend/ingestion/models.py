import uuid
from django.db import models
from core.models import Tenant, Facility


class EmissionFactor(models.Model):
    """
    Versioned emission factor database. Storing the FK to this record
    in CarbonLedger ensures historical inventories don't silently change
    when factors are updated annually (DEFRA, EPA, IPCC).
    """
    SOURCE_CHOICES = [
        ('DEFRA', 'UK DEFRA/DESNZ'),
        ('EPA', 'US EPA'),
        ('IPCC', 'IPCC AR6'),
        ('EGRID', 'US EPA eGRID'),
        ('CUSTOM', 'Custom/Client'),
    ]
    CATEGORY_CHOICES = [
        ('FUEL_DIESEL', 'Diesel Fuel'),
        ('FUEL_PETROL', 'Motor Gasoline'),
        ('FUEL_LPG', 'LPG/Propane'),
        ('FUEL_NATGAS', 'Natural Gas'),
        ('FUEL_HEATING_OIL', 'Heating Oil'),
        ('ELECTRICITY_GRID', 'Grid Electricity'),
        ('FLIGHT_SHORT_ECONOMY', 'Short-haul Economy Flight'),
        ('FLIGHT_SHORT_BUSINESS', 'Short-haul Business Flight'),
        ('FLIGHT_LONG_ECONOMY', 'Long-haul Economy Flight'),
        ('FLIGHT_LONG_BUSINESS', 'Long-haul Business Flight'),
        ('FLIGHT_LONG_FIRST', 'Long-haul First Class Flight'),
        ('HOTEL_UK', 'Hotel Stay - UK'),
        ('HOTEL_USA', 'Hotel Stay - USA'),
        ('HOTEL_DE', 'Hotel Stay - Germany'),
        ('HOTEL_FR', 'Hotel Stay - France'),
        ('HOTEL_ES', 'Hotel Stay - Spain'),
        ('HOTEL_CA', 'Hotel Stay - Canada'),
        ('HOTEL_OTHER', 'Hotel Stay - Other'),
        ('CAR_PETROL', 'Petrol Car'),
        ('CAR_DIESEL', 'Diesel Car'),
        ('CAR_EV', 'Electric Vehicle'),
        ('CAR_HYBRID', 'Hybrid Car'),
        ('RAIL', 'Rail/Train'),
        ('PURCHASED_GOODS', 'Purchased Goods (spend-based)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    category = models.CharField(max_length=50, choices=CATEGORY_CHOICES)
    source = models.CharField(max_length=20, choices=SOURCE_CHOICES)
    publication_year = models.PositiveIntegerField()
    # Geographic scope (country/subregion code, or 'GLOBAL')
    geographic_scope = models.CharField(max_length=20, default='GLOBAL')
    # The factor value (kg CO2e per unit)
    co2e_per_unit = models.DecimalField(max_digits=12, decimal_places=8)
    # Constituent gases (for full GHG breakdown)
    co2_per_unit = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    ch4_per_unit = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    n2o_per_unit = models.DecimalField(max_digits=12, decimal_places=8, default=0)
    unit_denominator = models.CharField(max_length=20, help_text='e.g. L, KWH, passenger-km, room-night')
    includes_radiative_forcing = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.category} | {self.source} {self.publication_year} | {self.co2e_per_unit} kgCO2e/{self.unit_denominator}'

    class Meta:
        ordering = ['category', '-publication_year']
        unique_together = ['category', 'source', 'publication_year', 'geographic_scope']


class RawIngestionLog(models.Model):
    """
    Immutable record of every file upload. The SHA-256 hash of the file
    content acts as a cryptographic deduplication key — uploading the same
    utility bill twice is caught here before any rows are processed.
    """
    SOURCE_TYPE_CHOICES = [
        ('SAP', 'SAP ERP Export'),
        ('UTILITY', 'Utility Electricity Data'),
        ('TRAVEL', 'Corporate Travel (Concur/Navan)'),
    ]
    STATUS_CHOICES = [
        ('PROCESSING', 'Processing'),
        ('DONE', 'Done'),
        ('FAILED', 'Failed'),
        ('DUPLICATE', 'Duplicate (rejected)'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='ingestion_logs')
    facility = models.ForeignKey(Facility, null=True, blank=True, on_delete=models.SET_NULL)
    source_type = models.CharField(max_length=20, choices=SOURCE_TYPE_CHOICES)
    original_filename = models.CharField(max_length=500)
    file_sha256 = models.CharField(max_length=64, db_index=True,
        help_text='SHA-256 of file content for deduplication')
    file_size_bytes = models.PositiveIntegerField()
    uploaded_by = models.ForeignKey('auth.User', null=True, on_delete=models.SET_NULL)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='PROCESSING')
    total_rows = models.PositiveIntegerField(default=0)
    parsed_rows = models.PositiveIntegerField(default=0)
    error_rows = models.PositiveIntegerField(default=0)
    flagged_rows = models.PositiveIntegerField(default=0)
    # Detected file metadata
    detected_encoding = models.CharField(max_length=20, blank=True)
    detected_delimiter = models.CharField(max_length=5, blank=True)
    detected_date_format = models.CharField(max_length=20, blank=True)
    processing_notes = models.TextField(blank=True)
    # Set to True once analyst locks all approved rows for audit
    is_locked = models.BooleanField(default=False)
    locked_at = models.DateTimeField(null=True, blank=True)
    locked_by = models.ForeignKey('auth.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='locked_batches')

    def __str__(self):
        return f'{self.source_type} | {self.original_filename} | {self.uploaded_at.date()}'

    class Meta:
        ordering = ['-uploaded_at']


class StagingRecord(models.Model):
    """
    The 'purgatory' tier. Every parsed row lives here until an analyst
    approves or rejects it. Analysts interact exclusively with this table
    via the React dashboard. Status transitions are enforced as a strict
    state machine.

    The raw_json field stores the original CSV row verbatim — analysts
    can see the exact source data that produced each normalized record.
    """
    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('FLAGGED', 'Flagged — Needs Attention'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]
    SCOPE_CHOICES = [('1', 'Scope 1'), ('2', 'Scope 2'), ('3', 'Scope 3')]
    CATEGORY_CHOICES = [
        ('FUEL_COMBUSTION', 'Fuel Combustion (Stationary/Mobile)'),
        ('ELECTRICITY', 'Purchased Electricity'),
        ('BUSINESS_TRAVEL_AIR', 'Business Travel — Air'),
        ('BUSINESS_TRAVEL_HOTEL', 'Business Travel — Hotel'),
        ('BUSINESS_TRAVEL_GROUND', 'Business Travel — Ground Transport'),
        ('BUSINESS_TRAVEL_RAIL', 'Business Travel — Rail'),
        ('PURCHASED_GOODS', 'Purchased Goods & Services'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    ingestion_log = models.ForeignKey(RawIngestionLog, on_delete=models.CASCADE,
        related_name='staging_records')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE)
    facility = models.ForeignKey(Facility, null=True, blank=True, on_delete=models.SET_NULL)
    row_number = models.PositiveIntegerField()

    # Verbatim source data — never modified after ingestion
    raw_json = models.JSONField(help_text='Original row data as ingested, never modified')

    # Normalized activity data
    scope = models.CharField(max_length=1, choices=SCOPE_CHOICES)
    category = models.CharField(max_length=30, choices=CATEGORY_CHOICES)
    activity_date = models.DateField(null=True, blank=True)
    period_start = models.DateField(null=True, blank=True)
    period_end = models.DateField(null=True, blank=True)

    # Raw quantity/unit (exactly as in source)
    raw_quantity = models.DecimalField(max_digits=20, decimal_places=6, null=True)
    raw_unit = models.CharField(max_length=20)

    # Normalized quantity/unit (standardized for emission factor application)
    normalized_quantity = models.DecimalField(max_digits=20, decimal_places=6, null=True)
    normalized_unit = models.CharField(max_length=20)

    # Computed emissions (kg CO2e)
    co2e_kg = models.DecimalField(max_digits=20, decimal_places=6, null=True)
    co2_kg = models.DecimalField(max_digits=20, decimal_places=6, null=True)
    ch4_kg = models.DecimalField(max_digits=20, decimal_places=6, null=True)
    n2o_kg = models.DecimalField(max_digits=20, decimal_places=6, null=True)
    emission_factor = models.ForeignKey(EmissionFactor, null=True, blank=True,
        on_delete=models.SET_NULL)

    # Source metadata for analyst visibility
    source_entity = models.CharField(max_length=255, blank=True,
        help_text='Plant code / Meter ID / Employee ID')
    source_description = models.CharField(max_length=500, blank=True,
        help_text='Material description / Site address / Vendor name')
    source_reference = models.CharField(max_length=255, blank=True,
        help_text='SAP doc number / Invoice # / Report ID')

    # Travel-specific fields
    origin_iata = models.CharField(max_length=3, blank=True)
    destination_iata = models.CharField(max_length=3, blank=True)
    distance_km = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    cabin_class = models.CharField(max_length=20, blank=True)  # ECONOMY, BUSINESS, FIRST
    hotel_country_code = models.CharField(max_length=2, blank=True)
    hotel_nights = models.PositiveIntegerField(null=True, blank=True)

    # Review workflow — strict state machine
    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING', db_index=True)
    reviewed_by = models.ForeignKey('auth.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reviewed_records')
    reviewed_at = models.DateTimeField(null=True, blank=True)
    review_note = models.TextField(blank=True)

    # Parse quality flags
    parse_warnings = models.JSONField(default=list,
        help_text='List of warning codes from parser (e.g. suspicious_date, material_unclassified)')
    is_estimated = models.BooleanField(default=False,
        help_text='True if source marked this as an estimated/interpolated read')
    is_calendarized = models.BooleanField(default=False,
        help_text='True if utility bill was pro-rated across calendar months')

    # Edit tracking (analyst corrections)
    original_quantity = models.DecimalField(max_digits=20, decimal_places=6, null=True, blank=True,
        help_text='Preserved if analyst edits quantity')
    original_unit = models.CharField(max_length=20, blank=True)
    edited_by = models.ForeignKey('auth.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='edited_records')
    edited_at = models.DateTimeField(null=True, blank=True)
    edit_note = models.TextField(blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'Row {self.row_number} | {self.category} | {self.status}'

    class Meta:
        ordering = ['-updated_at']


class CarbonLedger(models.Model):
    """
    The immutable carbon ledger. Append-only. Once a StagingRecord is
    APPROVED and committed here, this record cannot be edited in-place.
    Corrections require a reversal entry (negative co2e_metric_tons)
    followed by a new corrected entry — mirroring financial double-entry
    accounting principles.

    This design satisfies the most rigorous external auditor requirements.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='carbon_ledger')
    facility = models.ForeignKey(Facility, null=True, on_delete=models.SET_NULL)
    # OneToOne link back to the approved staging record (full provenance chain)
    staging_record = models.OneToOneField(StagingRecord, null=True, on_delete=models.SET_NULL,
        related_name='ledger_entry')
    ingestion_log = models.ForeignKey(RawIngestionLog, on_delete=models.CASCADE)

    # GHG Protocol dimensions
    scope = models.CharField(max_length=1)
    category = models.CharField(max_length=30)
    # GHG Protocol Scope 3 category number (1-15), null for Scope 1/2
    scope3_category_number = models.PositiveSmallIntegerField(null=True, blank=True)

    # Activity period
    start_date = models.DateField()
    end_date = models.DateField()

    # Raw values preserved (chain of evidence)
    raw_quantity = models.DecimalField(max_digits=20, decimal_places=6)
    raw_unit = models.CharField(max_length=20)

    # Normalized values used for calculation
    normalized_quantity = models.DecimalField(max_digits=20, decimal_places=6)
    normalized_unit = models.CharField(max_length=20)

    # Emission factor FK — frozen at time of approval so future factor
    # updates don't silently change historical inventories
    emission_factor = models.ForeignKey(EmissionFactor, null=True, on_delete=models.SET_NULL)
    emission_factor_snapshot = models.JSONField(
        help_text='Snapshot of factor values at time of approval')

    # Final computed emissions
    co2e_metric_tons = models.DecimalField(max_digits=20, decimal_places=8)
    co2_metric_tons = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    ch4_metric_tons = models.DecimalField(max_digits=20, decimal_places=8, default=0)
    n2o_metric_tons = models.DecimalField(max_digits=20, decimal_places=8, default=0)

    # True for reversal entries (negative values that cancel a prior incorrect entry)
    is_reversal = models.BooleanField(default=False)
    reverses_entry = models.ForeignKey('self', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reversed_by')
    reversal_note = models.TextField(blank=True, help_text='Mandatory audit note when reversing an entry')

    # Source metadata
    source_entity = models.CharField(max_length=255, blank=True)
    source_description = models.CharField(max_length=500, blank=True)
    source_reference = models.CharField(max_length=255, blank=True)

    approved_by = models.ForeignKey('auth.User', null=True, on_delete=models.SET_NULL)
    approved_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.scope} | {self.category} | {self.co2e_metric_tons} tCO2e'

    class Meta:
        ordering = ['-approved_at']
        # Enforce no UPDATE permission at application level
        default_permissions = ('add', 'view')
