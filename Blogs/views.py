from django.shortcuts import render
from django.views.generic import ListView, DetailView
from .models import Blog

# Create your views here.
class blogsView(ListView):
    model=Blog
    template_name = 'blogs.html'

class blogView(DetailView):
    model=Blog
    template_name = 'blog.html'