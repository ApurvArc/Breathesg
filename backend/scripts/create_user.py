
import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'breathesg.settings')
django.setup()
from django.contrib.auth import get_user_model
User = get_user_model()
user, created = User.objects.get_or_create(username='admin@esg.com')
user.set_password('admin123')
user.email = 'admin@esg.com'
user.is_staff = True
user.is_superuser = True
user.save()
print('User admin@esg.com created/updated successfully.')

