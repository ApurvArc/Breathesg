from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.pagination import PageNumberPagination
from django.db.models import Sum, Count, Q
from django.db import transaction
from django.utils import timezone
from datetime import datetime, timedelta
import json

from .models import RawIngestionLog, StagingRecord, CarbonLedger
from .serializers import (
    RawIngestionLogSerializer, StagingRecordSerializer,
    StagingRecordReviewSerializer, CarbonLedgerSerializer,
)
from .services import ingest_file, approve_staging_record, lock_batch
from core.models import Facility, AuditLog
from core.serializers import AuditLogSerializer


def get_tenant(request):
    """Get tenant from authenticated user's profile."""
    return request.user.tenant_profile.tenant


# ---------------------------------------------------------------------------
# Batch endpoints
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def batch_list(request):
    tenant = get_tenant(request)
    batches = RawIngestionLog.objects.filter(tenant=tenant)

    # Filters
    source_type = request.query_params.get('source_type')
    if source_type:
        batches = batches.filter(source_type=source_type)

    search = request.query_params.get('search')
    if search:
        batches = batches.filter(original_filename__icontains=search)

    paginator = PageNumberPagination()
    paginator.page_size = 10
    page = paginator.paginate_queryset(batches, request)
    serializer = RawIngestionLogSerializer(page, many=True)
    return paginator.get_paginated_response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_upload(request):
    """Multipart file upload endpoint. Dispatches to correct parser."""
    tenant = get_tenant(request)

    if 'file' not in request.FILES:
        return Response({'success': False, 'message': 'No file provided'}, status=400)

    uploaded_file = request.FILES['file']
    source_type = request.data.get('source_type', '').upper()
    if source_type not in ('SAP', 'UTILITY', 'TRAVEL'):
        return Response(
            {'success': False, 'message': 'source_type must be SAP, UTILITY, or TRAVEL'},
            status=400
        )

    facility_id = request.data.get('facility_id')
    facility = None
    grid_region_code = request.data.get('grid_region_code', 'GB')
    facility_country = request.data.get('facility_country', 'GB')

    if facility_id:
        try:
            facility = Facility.objects.get(id=facility_id, tenant=tenant)
            grid_region_code = facility.grid_region_code or grid_region_code
            facility_country = facility.country_code or facility_country
        except Facility.DoesNotExist:
            return Response({'success': False, 'message': 'Facility not found'}, status=400)

    file_content = uploaded_file.read()

    try:
        batch = ingest_file(
            file_content=file_content,
            original_filename=uploaded_file.name,
            source_type=source_type,
            tenant=tenant,
            uploaded_by=request.user,
            facility=facility,
            grid_region_code=grid_region_code,
            facility_country=facility_country,
        )
    except ValueError as e:
        return Response({'success': False, 'message': str(e)}, status=409)
    except Exception as e:
        return Response({'success': False, 'message': f'Parse error: {str(e)}'}, status=400)

    return Response(
        {'success': True, 'data': RawIngestionLogSerializer(batch).data},
        status=201
    )


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def batch_detail(request, batch_id):
    tenant = get_tenant(request)
    try:
        batch = RawIngestionLog.objects.get(id=batch_id, tenant=tenant)
    except RawIngestionLog.DoesNotExist:
        return Response({'success': False, 'message': 'Not found'}, status=404)
    return Response({'success': True, 'data': RawIngestionLogSerializer(batch).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def batch_lock(request, batch_id):
    tenant = get_tenant(request)
    try:
        batch = RawIngestionLog.objects.get(id=batch_id, tenant=tenant)
    except RawIngestionLog.DoesNotExist:
        return Response({'success': False, 'message': 'Not found'}, status=404)

    try:
        lock_batch(batch, request.user)
    except ValueError as e:
        return Response({'success': False, 'message': str(e)}, status=400)

    return Response({'success': True, 'message': 'Batch locked for audit'})


# ---------------------------------------------------------------------------
# Staging record (review queue) endpoints
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def staging_record_list(request):
    tenant = get_tenant(request)
    base_qs = StagingRecord.objects.filter(tenant=tenant).select_related(
        'ingestion_log', 'facility', 'reviewed_by'
    )

    source_type = request.query_params.get('source_type')
    if source_type:
        base_qs = base_qs.filter(ingestion_log__source_type=source_type)

    scope_filter = request.query_params.get('scope')
    if scope_filter:
        base_qs = base_qs.filter(scope=scope_filter)

    batch_id = request.query_params.get('batch_id')
    if batch_id:
        base_qs = base_qs.filter(ingestion_log_id=batch_id)

    date_from = request.query_params.get('date_from')
    if date_from:
        base_qs = base_qs.filter(activity_date__gte=date_from)

    date_to = request.query_params.get('date_to')
    if date_to:
        base_qs = base_qs.filter(activity_date__lte=date_to)

    search = request.query_params.get('search')
    if search:
        base_qs = base_qs.filter(
            Q(source_description__icontains=search) |
            Q(source_entity__icontains=search) |
            Q(source_reference__icontains=search)
        )

    records = base_qs
    status_filter = request.query_params.get('status')
    if status_filter:
        records = records.filter(status=status_filter)
    else:
        records = records.exclude(status__in=['APPROVED', 'REJECTED'])

    paginator = PageNumberPagination()
    paginator.page_size = 10
    page = paginator.paginate_queryset(records, request)
    serializer = StagingRecordSerializer(page, many=True)
    
    response = paginator.get_paginated_response(serializer.data)
    response.data['query_total_rows'] = base_qs.count()
    response.data['query_resolved_rows'] = base_qs.filter(status__in=['APPROVED', 'REJECTED']).count()
    return response


@api_view(['GET', 'PATCH'])
@permission_classes([IsAuthenticated])
def staging_record_detail(request, record_id):
    tenant = get_tenant(request)
    try:
        record = StagingRecord.objects.get(id=record_id, tenant=tenant)
    except StagingRecord.DoesNotExist:
        return Response({'success': False, 'message': 'Not found'}, status=404)

    if request.method == 'GET':
        return Response({'success': True, 'data': StagingRecordSerializer(record).data})

    # PATCH: update review status or analyst corrections
    if request.method == 'PATCH':
        if record.ingestion_log.is_locked:
            return Response(
                {'success': False, 'message': 'Batch is locked — cannot modify records'},
                status=403
            )

        new_status = request.data.get('status')
        note = request.data.get('review_note', '')

        # Analyst quantity correction
        new_qty = request.data.get('normalized_quantity')
        new_unit = request.data.get('normalized_unit')
        edit_note = request.data.get('edit_note', '')

        if new_qty and new_qty != str(record.normalized_quantity):
            # Preserve original before edit
            if not record.original_quantity:
                record.original_quantity = record.normalized_quantity
                record.original_unit = record.normalized_unit
            record.normalized_quantity = new_qty
            if new_unit:
                record.normalized_unit = new_unit
            record.edited_by = request.user
            record.edited_at = timezone.now()
            record.edit_note = edit_note

        if new_status:
            valid_transitions = {
                'PENDING': ['APPROVED', 'FLAGGED', 'REJECTED'],
                'FLAGGED': ['APPROVED', 'REJECTED', 'PENDING'],
                'APPROVED': [],  # locked — use reversal workflow
                'REJECTED': ['PENDING'],
            }
            allowed = valid_transitions.get(record.status, [])
            if new_status not in allowed:
                return Response(
                    {'success': False,
                     'message': f'Cannot transition from {record.status} to {new_status}'},
                    status=400
                )

            if new_status == 'APPROVED':
                try:
                    approve_staging_record(record, request.user, note)
                except ValueError as e:
                    return Response({'success': False, 'message': str(e)}, status=400)
                return Response({'success': True, 'message': 'Record approved and committed to ledger'})
            else:
                record.status = new_status
                record.review_note = note
                record.reviewed_by = request.user
                record.reviewed_at = timezone.now()
                record.save()

        return Response({'success': True, 'data': StagingRecordSerializer(record).data})


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def bulk_approve(request):
    """Approve multiple staging records at once."""
    tenant = get_tenant(request)
    record_ids = request.data.get('record_ids', [])
    note = request.data.get('note', 'Bulk approved')

    if not record_ids:
        return Response({'success': False, 'message': 'No record IDs provided'}, status=400)

    approved = 0
    errors = []

    records = StagingRecord.objects.filter(
        id__in=record_ids, tenant=tenant, status__in=['PENDING', 'FLAGGED']
    )

    try:
        with transaction.atomic():
            for record in records:
                try:
                    approve_staging_record(record, request.user, note)
                    approved += 1
                except Exception as e:
                    errors.append({'id': str(record.id), 'error': str(e)})
            
            if errors:
                raise ValueError(f"Bulk approval aborted. {len(errors)} records failed validation.")
    except ValueError as e:
        return Response({
            'success': False,
            'approved': 0,
            'errors': errors,
            'message': str(e)
        }, status=400)

    return Response({
        'success': True,
        'approved': approved,
        'errors': [],
    })


# ---------------------------------------------------------------------------
# Carbon Ledger
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def carbon_ledger_list(request):
    tenant = get_tenant(request)
    entries = CarbonLedger.objects.filter(tenant=tenant).select_related(
        'facility', 'approved_by'
    ).order_by('-approved_at')

    scope_filter = request.query_params.get('scope')
    if scope_filter:
        entries = entries.filter(scope=scope_filter)

    category_filter = request.query_params.get('category')
    if category_filter:
        entries = entries.filter(category=category_filter)

    paginator = PageNumberPagination()
    paginator.page_size = 10
    page = paginator.paginate_queryset(entries, request)
    serializer = CarbonLedgerSerializer(page, many=True)
    
    response = paginator.get_paginated_response(serializer.data)
    total_co2e = entries.aggregate(Sum('co2e_metric_tons'))['co2e_metric_tons__sum'] or 0.0
    response.data['query_total_co2e'] = float(total_co2e)
    return response


# ---------------------------------------------------------------------------
# Dashboard / aggregation
# ---------------------------------------------------------------------------

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def dashboard_summary(request):
    tenant = get_tenant(request)
    period = request.query_params.get('period', 'All Time')
    import datetime
    import calendar
    today = timezone.now().date()

    ledger_qs = CarbonLedger.objects.filter(tenant=tenant, is_reversal=False)
    staging_qs = StagingRecord.objects.filter(tenant=tenant)
    recent_batches_qs = RawIngestionLog.objects.filter(tenant=tenant).order_by('-uploaded_at')

    if period == 'YTD':
        start_dt = today.replace(month=1, day=1)
        ledger_qs = ledger_qs.filter(start_date__gte=start_dt)
        staging_qs = staging_qs.filter(activity_date__gte=start_dt)
        recent_batches_qs = recent_batches_qs.filter(uploaded_at__date__gte=start_dt)
    elif period == 'This Quarter':
        current_q = (today.month - 1) // 3 + 1
        start_m = 3 * current_q - 2
        start_dt = today.replace(month=start_m, day=1)
        ledger_qs = ledger_qs.filter(start_date__gte=start_dt)
        staging_qs = staging_qs.filter(activity_date__gte=start_dt)
        recent_batches_qs = recent_batches_qs.filter(uploaded_at__date__gte=start_dt)
    elif period == 'Last Quarter':
        current_q = (today.month - 1) // 3 + 1
        last_q = current_q - 1 if current_q > 1 else 4
        last_q_year = today.year if current_q > 1 else today.year - 1
        start_m = 3 * last_q - 2
        end_m = start_m + 2
        end_d = calendar.monthrange(last_q_year, end_m)[1]
        start_dt = datetime.date(last_q_year, start_m, 1)
        end_dt = datetime.date(last_q_year, end_m, end_d)
        ledger_qs = ledger_qs.filter(start_date__gte=start_dt, start_date__lte=end_dt)
        staging_qs = staging_qs.filter(activity_date__gte=start_dt, activity_date__lte=end_dt)
        recent_batches_qs = recent_batches_qs.filter(uploaded_at__date__gte=start_dt, uploaded_at__date__lte=end_dt)

    # Ledger totals
    total_co2e = ledger_qs.aggregate(total=Sum('co2e_metric_tons'))['total'] or 0

    by_scope = list(ledger_qs.values('scope').annotate(
        total_co2e=Sum('co2e_metric_tons')
    ).order_by('scope'))

    by_category = list(ledger_qs.values('category').annotate(
        total_co2e=Sum('co2e_metric_tons')
    ).order_by('-total_co2e'))

    by_source = list(ledger_qs.values('ingestion_log__source_type').annotate(
        total_co2e=Sum('co2e_metric_tons')
    ).order_by('-total_co2e'))

    # Review queue stats
    pending_count = staging_qs.filter(status='PENDING').count()
    flagged_count = staging_qs.filter(status='FLAGGED').count()
    approved_count = staging_qs.filter(status='APPROVED').count()
    rejected_count = staging_qs.filter(status='REJECTED').count()

    total_staging = staging_qs.count()
    error_count = flagged_count + rejected_count
    error_rate = (error_count / total_staging * 100) if total_staging > 0 else 0.0

    # Batches
    total_batches = recent_batches_qs.count()
    failed_batches = RawIngestionLog.objects.filter(tenant=tenant, status='FAILED').count()
    recent_batches = recent_batches_qs[:5]

    # Monthly trend (last 12 months) using TruncMonth
    import datetime
    twelve_months_ago = (timezone.now().date() - datetime.timedelta(days=365)).replace(day=1)

    from django.db.models.functions import TruncMonth
    monthly_raw = list(
        ledger_qs
        .filter(start_date__gte=twelve_months_ago)
        .annotate(month=TruncMonth('start_date'))
        .values('month')
        .annotate(total_co2e=Sum('co2e_metric_tons'))
        .order_by('month')
    )
    monthly_trend = [
        {'month': str(r['month'])[:7] if r['month'] else None, 'total_co2e': float(r['total_co2e'] or 0)}
        for r in monthly_raw
    ]

    return Response({
        'success': True,
        'data': {
            'total_co2e_metric_tons': float(total_co2e),
            'by_scope': by_scope,
            'by_category': by_category,
            'by_source': [{
                'source_type': r['ingestion_log__source_type'],
                'total_co2e': r['total_co2e']
            } for r in by_source],
            'review_queue': {
                'pending': pending_count,
                'flagged': flagged_count,
                'approved': approved_count,
                'rejected': rejected_count,
            },
            'total_batches': total_batches,
            'failed_batches': failed_batches,
            'error_rate_percentage': error_rate,
            'recent_batches': RawIngestionLogSerializer(recent_batches, many=True).data,
            'monthly_trend': monthly_trend,
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def audit_log_list(request):
    tenant = get_tenant(request)
    logs = AuditLog.objects.filter(tenant=tenant)

    paginator = PageNumberPagination()
    paginator.page_size = 10
    page = paginator.paginate_queryset(logs, request)
    serializer = AuditLogSerializer(page, many=True)
    
    response = paginator.get_paginated_response(serializer.data)
    response.data['review_count'] = logs.filter(action__in=['APPROVE', 'REJECT', 'FLAG']).count()
    response.data['lock_count'] = logs.filter(action='LOCK').count()
    response.data['edit_count'] = logs.filter(action='EDIT').count()
    return response
