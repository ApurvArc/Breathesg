from rest_framework import serializers
from .models import Facility, AuditLog


class FacilitySerializer(serializers.ModelSerializer):
    class Meta:
        model = Facility
        fields = ['id', 'facility_name', 'country_code', 'grid_region_code',
                  'sap_plant_codes', 'latitude', 'longitude']


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
