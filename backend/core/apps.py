from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """Register audit signal handlers on startup."""
        from .signals import register_audit
        from ingestion.models import StagingRecord, RawIngestionLog, CarbonLedger
        register_audit(StagingRecord, RawIngestionLog, CarbonLedger)
