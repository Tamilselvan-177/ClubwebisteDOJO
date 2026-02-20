"""
Dojo views: Simple redirect to CTF platform (now merged into same app).
This view is kept for backward compatibility with navbar links.
"""
from django.shortcuts import redirect


def dojo_entry(request):
    """
    GET /dojo/: Redirect to CTF index page.
    Since everything is merged, this redirects to the CTF index.
    """
    return redirect('/dojo/')
