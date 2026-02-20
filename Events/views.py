from django.views.generic import DetailView
from .models import Event

from django.views.generic import ListView

class EventListView(ListView):
    model = Event
    template_name = "events_list.html"
    context_object_name = "events"

class EventGalleryView(DetailView):
    model = Event
    template_name = "event_gallery.html"
    slug_field = "slug"
    slug_url_kwarg = "slug"