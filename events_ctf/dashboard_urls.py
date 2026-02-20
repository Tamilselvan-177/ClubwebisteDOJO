"""
URLs for custom admin dashboard.
"""
from django.urls import path
from .dashboard_views import admin_dashboard, event_control_panel, admin_scoreboard, admin_live_scoreboard

app_name = 'events_ctf'

urlpatterns = [
    path('', admin_dashboard, name='admin-dashboard'),
    path('scoreboard/', admin_live_scoreboard, name='admin-live-scoreboard'),
    path('event/<int:event_id>/', event_control_panel, name='admin-event-control'),
    path('scoreboard/<int:event_id>/', admin_scoreboard, name='admin-scoreboard'),
]

