"""
Email service for user authentication (verification, password reset)
"""
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.utils.html import strip_tags, escape
from django.conf import settings
import re
import logging

logger = logging.getLogger(__name__)


def sanitize_user_input(value):
    """
    Sanitize user input to prevent XSS and injection attacks
    
    Args:
        value: User input string to sanitize
        
    Returns:
        Sanitized string safe for use in emails
    """
    if not isinstance(value, str):
        return value
    
    # Remove potentially dangerous characters and patterns
    # Remove any HTML tags
    value = re.sub(r'<[^>]*>', '', value)
    
    # Remove javascript: protocol
    value = re.sub(r'javascript:', '', value, flags=re.IGNORECASE)
    
    # Remove data: protocol
    value = re.sub(r'data:', '', value, flags=re.IGNORECASE)
    
    # Remove on* event handlers
    value = re.sub(r'on\w+\s*=', '', value, flags=re.IGNORECASE)
    
    # HTML escape the value to prevent XSS
    value = escape(value)
    
    return value


def get_host_from_request(request):
    """
    Get the dynamic host from the request object
    Handles both HTTP and HTTPS, and includes port if non-standard
    
    Args:
        request: Django request object
        
    Returns:
        Host URL (e.g., 'http://localhost:3000' or 'https://example.com')
    """
    protocol = 'https' if request.is_secure() else 'http'
    host = request.get_host()
    return f"{protocol}://{host}"


def send_verification_email(user, verification_token, request=None):
    """
    Send email verification link to user after registration
    
    Args:
        user: User instance
        verification_token: Token for email verification
        request: Optional Django request object for dynamic host URL
    """
    try:
        # Validate token format (should be alphanumeric and URL-safe characters only)
        if not re.match(r'^[A-Za-z0-9_-]+$', verification_token):
            logger.error(f"Invalid token format for user {user.id}")
            return False
        
        # Sanitize user input to prevent injection attacks
        username = sanitize_user_input(user.username)
        email = user.email  # Email is already validated by Django
        
        # Validate email format
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            logger.error(f"Invalid email format: {email}")
            return False

        # Hardcode verification link domain
        verify_url = f"https://0xti.online/accounts/verify-email/?token={verification_token}&email={email}"
        
        context = {
            'user_username': username,  # Use sanitized username
            'verify_url': verify_url,
        }
        
        # Render HTML email template (Django templates auto-escape by default)
        html_message = render_to_string('emails/verify_email.html', context)
        plain_message = f"""
    Welcome to 0xTi, {username}!
    
    Please verify your email by clicking the link below:
    {verify_url}
    
    This link will expire in 24 hours.
    
    If you didn't create this account, please ignore this email.
    
    Best regards,
    0xTi Team
    """
        
        result = send_mail(
            subject='Verify Your Email - 0xTi',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Verification email sent to {email} - Result: {result}")
        return True
    except Exception as e:
        logger.error(f"Error sending verification email to {user.email}: {str(e)}", exc_info=True)
        return False


def send_password_reset_email(user, reset_token, request=None):
    """
    Send password reset link to user
    
    Args:
        user: User instance
        reset_token: Token for password reset
        request: Optional Django request object for dynamic host URL
    """
    try:
        # Validate token format (should be alphanumeric and URL-safe characters only)
        if not re.match(r'^[A-Za-z0-9_-]+$', reset_token):
            logger.error(f"Invalid token format for user {user.id}")
            return False
        
        # Sanitize user input to prevent injection attacks
        username = sanitize_user_input(user.username)
        email = user.email
        
        # Validate email format
        if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
            logger.error(f"Invalid email format: {email}")
            return False
        
        # Generate dynamic host-based URL
        if request:
            base_url = get_host_from_request(request)
        else:
            base_url = settings.FRONTEND_URL
        
        reset_url = f"{base_url}/reset-password?token={reset_token}&email={email}"
        
        context = {
            'user_username': username,  # Use sanitized username
            'reset_url': reset_url,
        }
        
        # Render HTML email template (Django templates auto-escape by default)
        html_message = render_to_string('emails/reset_password.html', context)
        plain_message = f"""
    Password Reset Request - 0xTi
    
    Click the link below to reset your password:
    {reset_url}
    
    This link will expire in 1 hour.
    
    If you didn't request a password reset, please ignore this email or contact support.
    
    Best regards,
    0xTi Team
    """
        
        result = send_mail(
            subject='Reset Your Password - 0xTi',
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Password reset email sent to {email} - Result: {result}")
        return True
    except Exception as e:
        logger.error(f"Error sending password reset email to {user.email}: {str(e)}", exc_info=True)
        return False


def send_resend_verification_email(user):
    """
    Resend email verification link to user
    
    Args:
        user: User instance
    """
    # Generate new token
    token = user.generate_email_verification_token()
    return send_verification_email(user, token)
