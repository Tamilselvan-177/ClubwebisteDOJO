from django.urls import path, include
from .views import (
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
    login_view,
    register_view,
    logout_view,
    forgot_password_view,
    verify_email_view,
    reset_password_view,
    check_email_view,
    resend_verification_view,
    verification_dashboard_view,
    profile_view,
    teams_list_view,
    team_create_view,
    team_detail_view
)

app_name = 'accounts'

urlpatterns = [
    # Template views (frontend)
    path('login/', login_view, name='login'),
    path('register/', register_view, name='register'),
    path('logout/', logout_view, name='logout'),
    path('forgot-password/', forgot_password_view, name='forgot_password'),
    path('check-email/', check_email_view, name='check_email'),
    path('resend-verification/', resend_verification_view, name='resend_verification'),
    path('verify-email/', verify_email_view, name='verify_email_page'),
    path('reset-password/', reset_password_view, name='reset_password_page'),
    path('verification-dashboard/', verification_dashboard_view, name='verification_dashboard'),
    path('profile/', profile_view, name='profile'),
    path('teams/', teams_list_view, name='teams_list'),
    path('teams/create/', team_create_view, name='team_create'),
    path('teams/<int:team_id>/', team_detail_view, name='team_detail'),
    
    # API Authentication endpoints
    path('auth/register/', UserRegistrationView.as_view(), name='user-register'),
    path('auth/login/', LoginView.as_view(), name='user-login'),
    path('auth/logout/', LogoutView.as_view(), name='user-logout'),
    path('auth/me/', CurrentUserView.as_view(), name='current-user'),
    path('auth/profile/', UserProfileView.as_view(), name='user-profile'),
    path('auth/verification-stats/', UserVerificationStatsView.as_view(), name='verification-stats'),
    
    # Email Verification & Password Reset
    path('auth/verify-email/', VerifyEmailView.as_view(), name='verify-email'),
    path('auth/resend-verification/', ResendVerificationEmailView.as_view(), name='resend-verification'),
    path('auth/forgot-password/', ForgotPasswordView.as_view(), name='forgot-password-api'),
    path('auth/reset-password/', ResetPasswordView.as_view(), name='reset-password'),
]

