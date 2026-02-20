from django.urls import path
from .views import EventGalleryView
from .views import EventListView

app_name = "Events"

urlpatterns = [
    path("", EventListView.as_view(), name="events"),
    path("<slug:slug>/", EventGalleryView.as_view(), name="gallery"),
]