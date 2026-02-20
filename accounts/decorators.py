"""
Custom decorators for accounts app
"""
from functools import wraps
from django.shortcuts import redirect, render
from django.contrib import messages
from django.urls import reverse


def email_verified_required(view_func):
    """
    Decorator to require email verification for template views.
    Must be used after @login_required.
    Shows a verification page if email is not verified.
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        # Staff users bypass verification
        if request.user.is_staff:
            return view_func(request, *args, **kwargs)
        
        # Check if email is verified
        if not request.user.is_email_verified:
            # Show the verify email page with error message
            context = {
                'email': request.user.email,
                'show_verification_required': True,
                'message': 'Please verify your email address to access this page.',
            }
            return render(request, 'accounts/verify_email_required.html', context)
        
        return view_func(request, *args, **kwargs)
    
    return wrapper
    
    return wrapper
