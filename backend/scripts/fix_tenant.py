
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breathesg.settings')
django.setup()
from django.contrib.auth import get_user_model
from core.models import Tenant, TenantUser
User = get_user_model()
user = User.objects.get(username='admin@esg.com')
tenant, _ = Tenant.objects.get_or_create(name='Global Workspace', defaults={'slug': 'global'})
TenantUser.objects.get_or_create(user=user, tenant=tenant, role='admin')
print('Tenant profile fixed.')

