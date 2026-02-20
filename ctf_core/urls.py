"""
Base URL config for CTF. Mounted under /dojo/ in main urls.py
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import TemplateView, RedirectView
from .views import index, dashboard, scoreboard, about, rules
from .health import health_check, detailed_health_check
from accounts.views import reset_password_view, forgot_password_view

app_name = 'ctf_core'

urlpatterns = [
    path('health/', health_check, name='health'),
    path('api/health/', detailed_health_check, name='api-health'),
    path('admin/first-blood-test/', TemplateView.as_view(template_name='admin/first-blood-test.html'), name='first-blood-test'),
    path('admin/', admin.site.urls),
    # admin-dashboard is included in main urls.py at /dojo/admin-dashboard/ to ensure events_ctf namespace is registered at root level
    path('', index, name='index'),
    path('dashboard/', dashboard, name='dashboard'),
    path('scoreboard/', scoreboard, name='scoreboard'),
    path('about/', about, name='about'),
    path('rules/', rules, name='rules'),
    path('reset-password/', reset_password_view, name='reset_password'),
    path('forgot-password/', forgot_password_view, name='forgot_password'),
    # accounts and challenges are included in main urls.py at /dojo/accounts/ and /dojo/challenges/
    # to ensure namespaces are registered at root level
    path('teams/', RedirectView.as_view(url='/dojo/accounts/teams/', permanent=False)),
    path('teams/create/', RedirectView.as_view(url='/dojo/accounts/teams/create/', permanent=False)),
    path('teams/<int:team_id>/', RedirectView.as_view(url='/dojo/accounts/teams/%(team_id)d/', permanent=False)),
    path('profile/', RedirectView.as_view(url='/dojo/accounts/profile/', permanent=False)),
    path('api/', include('accounts.api_urls')),
    path('api/', include('events_ctf.urls')),
    path('api/', include('challenges.api_urls')),
    path('api/', include('submissions.urls')),
    path('api/', include('notifications.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
