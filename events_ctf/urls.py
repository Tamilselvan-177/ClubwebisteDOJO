from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import EventViewSet, ThemeViewSet
from .admin_views import start_event, pause_event, resume_event, stop_event, get_audit_logs, freeze_scoreboard

router = DefaultRouter()
router.register(r'events', EventViewSet, basename='event')
router.register(r'themes', ThemeViewSet, basename='theme')

urlpatterns = [
    # Event control endpoints (admin only)
    path('admin/events/<int:event_id>/start/', start_event, name='admin-event-start'),
    path('admin/events/<int:event_id>/pause/', pause_event, name='admin-event-pause'),
    path('admin/events/<int:event_id>/resume/', resume_event, name='admin-event-resume'),
    path('admin/events/<int:event_id>/stop/', stop_event, name='admin-event-stop'),
    path('admin/events/<int:event_id>/freeze-scoreboard/', freeze_scoreboard, name='admin-scoreboard-freeze'),
    path('admin/audit-logs/', get_audit_logs, name='admin-audit-logs'),
    path('admin/audit-logs/<int:event_id>/', get_audit_logs, name='admin-audit-logs-event'),
    
    # Router URLs
    path('', include(router.urls)),
]

