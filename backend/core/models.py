import uuid
from django.db import models
from django.contrib.auth.models import User


class Tenant(models.Model):
    """
    Root model for multi-tenancy. Every data record cascades from here.
    UUID primary key prevents enumeration attacks across tenants.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    slug = models.SlugField(unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class Facility(models.Model):
    """
    Physical location within a tenant. Geographical mapping is material
    to emissions calculation — eGRID factors are subregion-specific for US,
    DEFRA grid intensity applies to UK, etc.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='facilities')
    facility_name = models.CharField(max_length=255)
    # Spatial data for emission factor resolution
    latitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    longitude = models.DecimalField(max_digits=9, decimal_places=6, null=True, blank=True)
    country_code = models.CharField(max_length=2, help_text='ISO 3166-1 alpha-2')
    postal_code = models.CharField(max_length=20, blank=True)
    # eGRID subregion for US facilities (e.g. CAMX, ERCT, SRMW)
    grid_region_code = models.CharField(max_length=10, blank=True,
        help_text='EPA eGRID subregion or country grid code')
    # SAP plant code(s) that map to this facility (pipe-separated if multiple)
    sap_plant_codes = models.CharField(max_length=500, blank=True,
        help_text='SAP plant codes mapping to this facility, comma-separated')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.facility_name} ({self.tenant.slug})'

    class Meta:
        verbose_name_plural = 'Facilities'
        ordering = ['facility_name']


class TenantUser(models.Model):
    """Links Django users to tenants with roles."""
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('analyst', 'Analyst'),
        ('viewer', 'Viewer'),
    ]
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='tenant_profile')
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='members')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='analyst')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.user.username} @ {self.tenant.slug} ({self.role})'


class AuditLog(models.Model):
    """
    Append-only audit trail. Written via Django signals (pre_save/post_save)
    using thread-local user storage. Cannot be edited or deleted via ORM
    (enforced at the application level; DB-level protection via no UPDATE perms
    in production).
    """
    ACTION_CHOICES = [
        ('INGEST', 'Data Ingested'),
        ('PARSE_OK', 'Row Parsed Successfully'),
        ('PARSE_ERR', 'Row Parse Error'),
        ('REVIEW', 'Record Reviewed'),
        ('APPROVE', 'Record Approved'),
        ('REJECT', 'Record Rejected'),
        ('FLAG', 'Record Flagged'),
        ('EDIT', 'Record Edited'),
        ('LOCK', 'Batch Locked for Audit'),
        ('REVERSE', 'Reversal Entry Created'),
    ]
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='audit_logs')
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    target_type = models.CharField(max_length=100)  # model name
    target_id = models.CharField(max_length=100)    # pk as string
    # JSON diff: {"field": ["old_value", "new_value"]}
    before_json = models.JSONField(null=True, blank=True)
    after_json = models.JSONField(null=True, blank=True)
    note = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f'{self.action} on {self.target_type}:{self.target_id} at {self.timestamp}'

    class Meta:
        ordering = ['-timestamp']
        # Prevent accidental bulk deletes on this table
        default_permissions = ('add', 'view')
