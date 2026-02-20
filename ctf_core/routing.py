"""
WebSocket URL routing for Django Channels.
"""
from django.urls import re_path
from notifications import consumers

websocket_urlpatterns = [
    re_path(r'ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
    re_path(r'ws/first-blood/$', consumers.FirstBloodConsumer.as_asgi()),
]
