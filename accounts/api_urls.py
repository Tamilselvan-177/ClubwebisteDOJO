"""
API URLs for accounts (REST framework API endpoints only)
"""
from rest_framework.routers import DefaultRouter
from .views import (
    UserViewSet, 
    TeamViewSet,
    UserRegistrationView,
    LoginView,
    LogoutView,
    UserProfileView,
    CurrentUserView,
    UserVerificationStatsView,
    VerifyEmailView,
    ResendVerificationEmailView,
    ForgotPasswordView,
    ResetPasswordView,
)
from django.urls import path

router = DefaultRouter()
router.register(r'users', UserViewSet, basename='user')
router.register(r'teams', TeamViewSet, basename='team')

# Authentication and verification endpoints
auth_urls = [
    path('auth/register/', UserRegistrationView.as_view(), name='user-register'),
    path('auth/login/', LoginView.as_view(), name='user-login'),
    path('auth/logout/', LogoutView.as_view(), name='user-logout'),
    path('auth/me/', CurrentUserView.as_view(), name='current-user'),
    path('auth/profile/', UserProfileView.as_view(), name='user-profile'),
    path('auth/verification-stats/', UserVerificationStatsView.as_view(), name='verification-stats'),
    path('auth/verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('auth/resend-verification/', ResendVerificationEmailView.as_view(), name='resend-verification'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot-password-api'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
]

urlpatterns = router.urls + auth_urls
