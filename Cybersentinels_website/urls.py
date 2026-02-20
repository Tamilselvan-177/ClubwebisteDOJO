"""
URL configuration for Cybersentinels_website project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # CTF platform routes under /dojo/ - include namespaced apps at root level
    path('dojo/accounts/', include(('accounts.urls', 'accounts'))),
    path('dojo/challenges/', include(('challenges.urls', 'challenges'))),
    path('dojo/admin-dashboard/', include(('events_ctf.dashboard_urls', 'events_ctf'))),  # Dashboard URLs with events_ctf namespace
    path('dojo/', include('ctf_core.urls')),  # CTF platform core routes under /dojo/
    path('', include('home.urls')),
    path("blogs/", include('Blogs.urls')),
    path("events/", include('Events.urls')),
    path("writeups/", include("writeups.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)