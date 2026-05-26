from django.urls import path
from . import views

urlpatterns = [
    # Batches
    path('batches/', views.batch_list, name='batch-list'),
    path('batches/upload/', views.batch_upload, name='batch-upload'),
    path('batches/<uuid:batch_id>/', views.batch_detail, name='batch-detail'),
    path('batches/<uuid:batch_id>/lock/', views.batch_lock, name='batch-lock'),
    # Review queue
    path('records/', views.staging_record_list, name='staging-record-list'),
    path('records/<uuid:record_id>/', views.staging_record_detail, name='staging-record-detail'),
    path('records/bulk-approve/', views.bulk_approve, name='bulk-approve'),
    # Carbon Ledger
    path('ledger/', views.carbon_ledger_list, name='carbon-ledger-list'),
    # Dashboard
    path('dashboard/', views.dashboard_summary, name='dashboard-summary'),
    # Audit log
    path('audit-log/', views.audit_log_list, name='audit-log'),
]
