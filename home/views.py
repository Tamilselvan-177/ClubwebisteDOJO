from django.shortcuts import render
from Events.models import Event
from Blogs.models import Blog

# Create your views here.
def home(request):
    events = Event.objects.only("title", "date", "slug", "cover_image").order_by("-date")
    blog = Blog.objects.only("title", "date", "desc", "cover_image", "slug").order_by("-date")
    return render(request, 'home.html', {"events":events, "blog": blog})

def aboutus(request):
    return render(request, 'aboutus.html', {})

def achievements(request):
    return render(request, 'achievements.html', {})

def team(request):
    return render(request, 'team.html', {})