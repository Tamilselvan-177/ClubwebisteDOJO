"""
Template URLs for challenges (non-API views only)
"""
from django.urls import path
from .views import challenge_list_view, challenge_detail_view

app_name = 'challenges'

urlpatterns = [
    path('', challenge_list_view, name='challenge_list'),
    path('<int:challenge_id>/', challenge_detail_view, name='challenge_detail'),
]
