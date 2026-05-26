from rest_framework import serializers
from .models import RawIngestionLog, StagingRecord, CarbonLedger, EmissionFactor
from core.models import Tenant, Facility, AuditLog
from django.contrib.auth.models import User


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = ['id', 'facility_name', 'country_code', 'grid_region_code',
                  'sap_plant_codes', 'latitude', 'longitude']


class RawIngestionLogSerializer(serializers.ModelSerializer):
    uploaded_by_name = serializers.SerializerMethodField()
    source_type_display = serializers.CharField(source='get_source_type_display', read_only=True)
    facility_name = serializers.SerializerMethodField()

    class Meta:
        model = RawIngestionLog
        fields = [
            'id', 'source_type', 'source_type_display', 'original_filename',
            'file_size_bytes', 'uploaded_by_name', 'uploaded_at', 'status',
            'total_rows', 'parsed_rows', 'error_rows', 'flagged_rows',
            'is_locked', 'locked_at', 'detected_encoding', 'detected_delimiter',
            'processing_notes', 'facility_name',
        ]

    def get_uploaded_by_name(self, obj):
        if obj.uploaded_by:
            return obj.uploaded_by.get_full_name() or obj.uploaded_by.username
        return None

    def get_facility_name(self, obj):
        return obj.facility.facility_name if obj.facility else None


class StagingRecordSerializer(serializers.ModelSerializer):
    ingestion_log_filename = serializers.CharField(
        source='ingestion_log.original_filename', read_only=True)
    source_type = serializers.CharField(
        source='ingestion_log.source_type', read_only=True)
    reviewed_by_name = serializers.SerializerMethodField()
    facility_name = serializers.SerializerMethodField()
    scope_display = serializers.SerializerMethodField()
    co2e_kg_display = serializers.SerializerMethodField()

    class Meta:
        model = StagingRecord
        fields = [
            'id', 'ingestion_log', 'ingestion_log_filename', 'source_type',
            'row_number', 'raw_json', 'scope', 'scope_display', 'category',
            'activity_date', 'period_start', 'period_end',
            'raw_quantity', 'raw_unit', 'normalized_quantity', 'normalized_unit',
            'co2e_kg', 'co2e_kg_display', 'co2_kg', 'ch4_kg', 'n2o_kg',
            'source_entity', 'source_description', 'source_reference',
            'origin_iata', 'destination_iata', 'distance_km', 'cabin_class',
            'hotel_country_code', 'hotel_nights',
            'status', 'reviewed_by_name', 'reviewed_at', 'review_note',
            'parse_warnings', 'is_estimated', 'is_calendarized',
            'original_quantity', 'original_unit', 'edited_at', 'edit_note',
            'facility_name', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'ingestion_log', 'row_number', 'raw_json', 'scope', 'category',
            'activity_date', 'period_start', 'period_end',
            'raw_quantity', 'raw_unit', 'co2_kg', 'ch4_kg', 'n2o_kg',
            'source_entity', 'source_description', 'source_reference',
            'origin_iata', 'destination_iata', 'distance_km', 'cabin_class',
            'hotel_country_code', 'hotel_nights',
            'reviewed_by_name', 'reviewed_at', 'is_estimated', 'is_calendarized',
            'facility_name', 'created_at', 'updated_at', 'parse_warnings',
            'ingestion_log_filename', 'source_type', 'scope_display', 'co2e_kg_display',
        ]

    def get_reviewed_by_name(self, obj):
        if obj.reviewed_by:
            return obj.reviewed_by.get_full_name() or obj.reviewed_by.username
        return None

    def get_facility_name(self, obj):
        return obj.facility.facility_name if obj.facility else None

    def get_scope_display(self, obj):
        return {1: 'Scope 1', 2: 'Scope 2', 3: 'Scope 3'}.get(int(obj.scope or 3), f'Scope {obj.scope}')

    def get_co2e_kg_display(self, obj):
        if obj.co2e_kg is None:
            return None
        kg = float(obj.co2e_kg)
        if kg >= 1000:
            return f'{kg/1000:.3f} tCO2e'
        return f'{kg:.3f} kgCO2e'


class StagingRecordReviewSerializer(serializers.ModelSerializer):
    """Minimal serializer for review PATCH endpoint."""
    class Meta:
        model = StagingRecord
        fields = ['status', 'review_note', 'normalized_quantity', 'normalized_unit', 'edit_note']


class CarbonLedgerSerializer(serializers.ModelSerializer):
    facility_name = serializers.SerializerMethodField()
    approved_by_name = serializers.SerializerMethodField()

    class Meta:
        model = CarbonLedger
        fields = [
            'id', 'scope', 'category', 'scope3_category_number',
            'start_date', 'end_date',
            'raw_quantity', 'raw_unit', 'normalized_quantity', 'normalized_unit',
            'co2e_metric_tons', 'co2_metric_tons', 'ch4_metric_tons', 'n2o_metric_tons',
            'is_reversal', 'source_entity', 'source_description', 'source_reference',
            'approved_by_name', 'approved_at', 'facility_name',
            'emission_factor_snapshot',
        ]

    def get_facility_name(self, obj):
        return obj.facility.facility_name if obj.facility else None

    def get_approved_by_name(self, obj):
        if obj.approved_by:
            return obj.approved_by.get_full_name() or obj.approved_by.username
        return None


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.SerializerMethodField()
    action_display = serializers.CharField(source='get_action_display', read_only=True)

    class Meta:
        model = AuditLog
        fields = ['id', 'action', 'action_display', 'target_type', 'target_id',
                  'before_json', 'after_json', 'note', 'timestamp', 'user_name']

    def get_user_name(self, obj):
        if obj.user:
            return obj.user.get_full_name() or obj.user.username
        return 'System'
