from django.urls import path, include
from .views import (
    challenge_list_view,
    challenge_detail_view
)

app_name = 'challenges'

# Template-based URLs (for /challenges/)
urlpatterns = [
    path('', challenge_list_view, name='challenge_list'),
    path('<int:challenge_id>/', challenge_detail_view, name='challenge_detail'),
]


