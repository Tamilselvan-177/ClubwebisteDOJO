from django.urls import path
from . import views

app_name = 'dojo'

urlpatterns = [
    path('', views.dojo_entry, name='dojo'),
]
