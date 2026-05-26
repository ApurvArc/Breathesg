"""
Django signal handlers for immutable audit trail.

Uses thread-local user storage (set by CurrentUserMiddleware) to capture
who triggered each model change at the ORM level — not the view level.
This ensures bulk DB operations, admin actions, and API calls all produce
identical audit records with no escape hatch.

Connected in core/apps.py ready() method.
"""
from django.db.models.signals import pre_save, post_save
from django.dispatch import receiver
from django.contrib.auth.models import User

from .middleware import get_current_user
from .models import AuditLog, Tenant


AUDITED_MODELS = set()  # populated by register_audit()


def register_audit(*models):
    """Register models for automatic audit trail generation."""
    for model in models:
        AUDITED_MODELS.add(model)
        pre_save.connect(_capture_pre_save, sender=model)
        post_save.connect(_write_audit_log, sender=model)


_pre_save_states = {}  # thread-local would be cleaner but dict keyed by (model, pk) works


def _capture_pre_save(sender, instance, **kwargs):
    """
    Intercept save BEFORE the DB write. Capture the current DB state
    so we can compute a changeset in post_save.
    """
    if not instance.pk:
        return  # New object — no previous state

    try:
        old = sender.objects.get(pk=instance.pk)
        # Serialize all field values to a comparable dict
        old_data = {}
        for field in sender._meta.get_fields():
            if hasattr(field, 'attname'):
                old_data[field.name] = str(getattr(old, field.attname, ''))
        _pre_save_states[(sender.__name__, str(instance.pk))] = old_data
    except sender.DoesNotExist:
        pass


def _write_audit_log(sender, instance, created, **kwargs):
    """
    Intercept save AFTER DB commit. Compute changeset and write AuditLog.
    Skips AuditLog itself to prevent infinite recursion.
    """
    if sender == AuditLog:
        return

    user = get_current_user()

    # Get tenant FK from instance
    tenant = None
    if hasattr(instance, 'tenant'):
        tenant = instance.tenant
    elif hasattr(instance, 'ingestion_log') and hasattr(instance.ingestion_log, 'tenant'):
        tenant = instance.ingestion_log.tenant

    if tenant is None:
        return  # Can't log without tenant context

    action = 'INGEST' if created else 'EDIT'
    before = None
    after = None

    if not created:
        key = (sender.__name__, str(instance.pk))
        old_data = _pre_save_states.pop(key, {})

        # Build after state
        new_data = {}
        for field in sender._meta.get_fields():
            if hasattr(field, 'attname'):
                new_data[field.name] = str(getattr(instance, field.attname, ''))

        # Only record fields that actually changed
        changed = {
            k: [old_data.get(k, ''), new_data.get(k, '')]
            for k in new_data
            if old_data.get(k) != new_data.get(k)
        }

        if not changed:
            return  # Nothing changed — no log entry needed

        before = {k: v[0] for k, v in changed.items()}
        after = {k: v[1] for k, v in changed.items()}

        # Determine action from status changes
        status_change = changed.get('status')
        if status_change:
            new_status = status_change[1]
            action = {
                'APPROVED': 'APPROVE',
                'REJECTED': 'REJECT',
                'FLAGGED': 'FLAG',
            }.get(new_status, 'EDIT')

    AuditLog.objects.create(
        tenant=tenant,
        user=user if isinstance(user, User) else None,
        action=action,
        target_type=sender.__name__,
        target_id=str(instance.pk),
        before_json=before,
        after_json=after,
    )
