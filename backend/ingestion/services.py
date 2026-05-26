"""
Ingestion Service — orchestrates the full pipeline:
1. Receive uploaded file
2. Hash for dedup (SHA-256)
3. Create RawIngestionLog
4. Dispatch to correct parser (SAP / Utility / Travel)
5. Create StagingRecord for each parsed row
6. Run anomaly detection heuristics
7. Update batch statistics
"""
import hashlib
import json
from decimal import Decimal
from datetime import date, timezone, datetime

from django.db import transaction

from core.models import Tenant, Facility, AuditLog
from ingestion.models import RawIngestionLog, StagingRecord, EmissionFactor, CarbonLedger
from ingestion.sap_parser import parse_sap_csv
from ingestion.utility_parser import parse_utility_csv
from ingestion.travel_parser import parse_travel_csv


def sha256_of_bytes(content: bytes) -> str:
    """Compute SHA-256 hex digest of raw file bytes."""
    return hashlib.sha256(content).hexdigest()


def get_or_none(model, **kwargs):
    try:
        return model.objects.get(**kwargs)
    except model.DoesNotExist:
        return None


def ingest_file(
    file_content: bytes,
    original_filename: str,
    source_type: str,  # SAP | UTILITY | TRAVEL
    tenant: Tenant,
    uploaded_by,
    facility: Facility | None = None,
    grid_region_code: str = 'GB',
    facility_country: str = 'GB',
) -> RawIngestionLog:
    """
    Main ingestion entry point. Parses the uploaded file and creates
    StagingRecords for analyst review. Returns the RawIngestionLog.

    Raises ValueError for duplicate files (same SHA-256 already exists for tenant).
    """
    file_hash = sha256_of_bytes(file_content)

    # Cryptographic deduplication — prevent double-counting
    existing = RawIngestionLog.objects.filter(
        tenant=tenant, file_sha256=file_hash
    ).exclude(status='FAILED').first()
    if existing:
        raise ValueError(
            f'Duplicate file detected: this file was already uploaded on '
            f'{existing.uploaded_at.strftime("%Y-%m-%d %H:%M")} UTC '
            f'(batch ID: {existing.id})'
        )

    with transaction.atomic():
        batch = RawIngestionLog.objects.create(
            tenant=tenant,
            facility=facility,
            source_type=source_type,
            original_filename=original_filename,
            file_sha256=file_hash,
            file_size_bytes=len(file_content),
            uploaded_by=uploaded_by,
            status='PROCESSING',
        )

        # Parse based on source type
        try:
            if source_type == 'SAP':
                rows, metadata = parse_sap_csv(file_content)
            elif source_type == 'UTILITY':
                rows, metadata = parse_utility_csv(
                    file_content,
                    grid_region_code=grid_region_code,
                    facility_country=facility_country,
                )
            elif source_type == 'TRAVEL':
                rows, metadata = parse_travel_csv(file_content)
            else:
                raise ValueError(f'Unknown source type: {source_type}')

            # Update format detection metadata
            batch.detected_encoding = metadata.get('encoding', '')
            batch.detected_delimiter = metadata.get('delimiter', '')
            batch.processing_notes = json.dumps(metadata, default=str)

        except Exception as e:
            batch.status = 'FAILED'
            batch.processing_notes = f'PARSE ERROR: {str(e)}'
            batch.save()
            raise

        # Create StagingRecords
        parsed = 0
        errors = 0
        flagged = 0

        for row_data in rows:
            if row_data.get('parse_status') == 'SKIPPED':
                continue

            # Run anomaly heuristics
            warnings = list(row_data.get('parse_warnings', []))
            status = row_data.get('parse_status', 'PENDING')

            # Heuristic: zero or negative quantity
            qty = row_data.get('normalized_quantity') or row_data.get('raw_quantity')
            if qty is not None and qty == 0:
                warnings.append('zero_quantity')
                status = 'FLAGGED'

            # Heuristic: stat deviation would be computed here if we have history
            # (simplified: flag very large single entries > 1,000,000 kWh or L)
            if qty is not None and abs(qty) > 1_000_000:
                warnings.append('anomalous_quantity:exceeds_1m_units')
                status = 'FLAGGED'

            if status == 'FLAGGED':
                flagged += 1
            elif row_data.get('parse_status') == 'OK':
                parsed += 1
            else:
                errors += 1

            # Map parse_status to review_status
            review_status = 'FLAGGED' if status == 'FLAGGED' else 'PENDING'

            StagingRecord.objects.create(
                ingestion_log=batch,
                tenant=tenant,
                facility=facility,
                row_number=row_data.get('row_number', 0),
                raw_json=row_data.get('raw_json', {}),
                scope=row_data.get('scope', '3'),
                category=row_data.get('category', 'PURCHASED_GOODS'),
                activity_date=row_data.get('activity_date'),
                period_start=row_data.get('period_start'),
                period_end=row_data.get('period_end'),
                raw_quantity=row_data.get('raw_quantity'),
                raw_unit=row_data.get('raw_unit', ''),
                normalized_quantity=row_data.get('normalized_quantity'),
                normalized_unit=row_data.get('normalized_unit', ''),
                co2e_kg=row_data.get('co2e_kg'),
                source_entity=row_data.get('source_entity', ''),
                source_description=row_data.get('source_description', ''),
                source_reference=row_data.get('source_reference', ''),
                origin_iata=row_data.get('origin_iata', ''),
                destination_iata=row_data.get('destination_iata', ''),
                distance_km=row_data.get('distance_km'),
                cabin_class=row_data.get('cabin_class', ''),
                hotel_country_code=row_data.get('hotel_country_code', ''),
                hotel_nights=row_data.get('hotel_nights'),
                status=review_status,
                parse_warnings=warnings,
                is_estimated=row_data.get('is_estimated', False),
                is_calendarized=row_data.get('is_calendarized', False),
            )

        batch.total_rows = len([r for r in rows if r.get('parse_status') != 'SKIPPED'])
        batch.parsed_rows = parsed
        batch.error_rows = errors
        batch.flagged_rows = flagged
        batch.status = 'DONE'
        batch.save()

        AuditLog.objects.create(
            tenant=tenant,
            user=uploaded_by,
            action='INGEST',
            target_type='RawIngestionLog',
            target_id=str(batch.id),
            after_json={
                'filename': original_filename,
                'source_type': source_type,
                'total_rows': batch.total_rows,
                'parsed_rows': parsed,
                'flagged_rows': flagged,
                'file_sha256': file_hash[:16] + '...',  # partial for log readability
            }
        )

    return batch


def approve_staging_record(record: StagingRecord, user, note: str = '') -> CarbonLedger:
    """
    Transition StagingRecord to APPROVED and commit to CarbonLedger.
    Creates an immutable ledger entry with a snapshot of the emission factor used.
    """
    if record.status == 'APPROVED':
        raise ValueError('Record already approved')
    if record.ingestion_log.is_locked:
        raise ValueError('Batch is locked — cannot modify records')

    with transaction.atomic():
        record.status = 'APPROVED'
        record.reviewed_by = user
        record.reviewed_at = datetime.now(timezone.utc)
        record.review_note = note
        record.save()

        # Snapshot the emission factor at time of approval
        ef_snapshot = {}
        if record.emission_factor:
            ef = record.emission_factor
            ef_snapshot = {
                'id': str(ef.id),
                'category': ef.category,
                'source': ef.source,
                'publication_year': ef.publication_year,
                'co2e_per_unit': str(ef.co2e_per_unit),
                'unit_denominator': ef.unit_denominator,
                'snapshotted_at': datetime.now(timezone.utc).isoformat(),
            }

        co2e_kg = record.co2e_kg or Decimal('0')
        co2e_metric_tons = co2e_kg / Decimal('1000')

        start = record.period_start or record.activity_date
        end = record.period_end or record.activity_date

        if not start or not end:
            raise ValueError('Cannot approve record: missing activity or period dates. Please edit the record to provide a valid date.')

        ledger_entry = CarbonLedger.objects.create(
            tenant=record.tenant,
            facility=record.facility,
            staging_record=record,
            ingestion_log=record.ingestion_log,
            scope=record.scope,
            category=record.category,
            scope3_category_number=6 if record.category.startswith('BUSINESS_TRAVEL') else None,
            start_date=start,
            end_date=end,
            raw_quantity=record.raw_quantity or Decimal('0'),
            raw_unit=record.raw_unit,
            normalized_quantity=record.normalized_quantity or Decimal('0'),
            normalized_unit=record.normalized_unit,
            emission_factor=record.emission_factor,
            emission_factor_snapshot=ef_snapshot,
            co2e_metric_tons=co2e_metric_tons,
            co2_metric_tons=(record.co2_kg or Decimal('0')) / Decimal('1000'),
            ch4_metric_tons=(record.ch4_kg or Decimal('0')) / Decimal('1000'),
            n2o_metric_tons=(record.n2o_kg or Decimal('0')) / Decimal('1000'),
            source_entity=record.source_entity,
            source_description=record.source_description,
            source_reference=record.source_reference,
            approved_by=user,
            reversal_note='',
        )

        AuditLog.objects.create(
            tenant=record.tenant,
            user=user,
            action='APPROVE',
            target_type='StagingRecord',
            target_id=str(record.id),
            after_json={
                'ledger_id': str(ledger_entry.id),
                'co2e_metric_tons': str(co2e_metric_tons),
                'note': note,
            }
        )

    return ledger_entry


def lock_batch(batch: RawIngestionLog, user) -> None:
    """
    Lock a batch for audit. Once locked, no records can be approved/edited.
    All records must be reviewed (non-PENDING) before locking.
    """
    pending_count = StagingRecord.objects.filter(
        ingestion_log=batch, status='PENDING'
    ).count()

    if pending_count > 0:
        raise ValueError(
            f'Cannot lock batch: {pending_count} records still pending review'
        )

    batch.is_locked = True
    batch.locked_at = datetime.now(timezone.utc)
    batch.locked_by = user
    batch.save()

    AuditLog.objects.create(
        tenant=batch.tenant,
        user=user,
        action='LOCK',
        target_type='RawIngestionLog',
        target_id=str(batch.id),
        after_json={'locked_at': batch.locked_at.isoformat()}
    )
