from django.urls import path
from .views import writeupView, writeupsView

app_name="writeups"

urlpatterns = [
    path("", writeupsView.as_view(), name="writeups"),
    path("<int:pk>/", writeupView.as_view(), name="writeup"),
]