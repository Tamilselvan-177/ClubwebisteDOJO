from django.shortcuts import render
from django.views.generic import ListView, DetailView
from .models import writeup

# Create your views here.
class writeupsView(ListView):
    model=writeup
    template_name = 'writeups.html'

class writeupView(DetailView):
    model=writeup
    template_name = 'writeup.html'