from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from .models import Facility
from .serializers import FacilitySerializer


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    user = request.user
    profile = getattr(user, 'tenant_profile', None)
    return Response({
        'success': True,
        'data': {
            'id': user.id,
            'username': user.username,
            'email': user.email,
            'full_name': user.get_full_name(),
            'tenant': {
                'id': str(profile.tenant.id) if profile else None,
                'name': profile.tenant.name if profile else None,
                'slug': profile.tenant.slug if profile else None,
            },
            'role': profile.role if profile else None,
        }
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def facility_list(request):
    tenant = request.user.tenant_profile.tenant
    facilities = Facility.objects.filter(tenant=tenant)
    return Response({
        'success': True,
        'data': FacilitySerializer(facilities, many=True).data
    })
