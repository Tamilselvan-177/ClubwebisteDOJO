from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, permission_classes, action
from rest_framework.response import Response
from rest_framework.views import APIView
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.shortcuts import render, redirect
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils.decorators import method_decorator
from django.utils import timezone
from django.db import transaction
from django.db.models import Q, Count, Sum
from django.contrib.auth.decorators import login_required
from .decorators import email_verified_required
from events_ctf.models import Event
from .models import User, Team, TeamMembership, PlatformSettings
from .serializers import (
    UserRegistrationSerializer,
    UserSerializer,
    UserProfileSerializer,
    LoginSerializer,
    TeamSerializer,
    TeamCreateSerializer,
    TeamMembershipSerializer,
    VerifyEmailSerializer,
    ResendVerificationEmailSerializer,
    ForgotPasswordSerializer,
    ResetPasswordSerializer
)
from .permissions import IsTeamMember, IsTeamCaptain, IsNotBanned, IsTeamNotBanned, IsEmailVerified
from .email_service import send_verification_email, send_password_reset_email


@method_decorator(csrf_exempt, name='dispatch')
class UserRegistrationView(APIView):
    """User registration endpoint - CSRF exempt for API calls"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        # Check if registration is enabled
        settings = PlatformSettings.get_settings()
        if not settings.is_registration_enabled:
            return Response({
                'error': 'Registration is currently disabled',
                'message': 'New user registration has been temporarily disabled by administrators.'
            }, status=status.HTTP_403_FORBIDDEN)
        
        serializer = UserRegistrationSerializer(data=request.data, context={'require_email_verification': settings.require_email_verification})
        if serializer.is_valid():
            user = serializer.save()

            # If verification is required, send email and ask user to verify
            if settings.require_email_verification:
                verification_token = user.generate_email_verification_token()
                send_verification_email(user, verification_token, request)
                return Response({
                    'message': 'Registration successful! Please check your email to verify your account.',
                    'user': {
                        'id': user.id,
                        'username': user.username,
                        'email': user.email,
                        'is_email_verified': user.is_email_verified
                    }
                }, status=status.HTTP_201_CREATED)

            # If verification is NOT required, auto-login and return success
            login(request, user)
            return Response({
                'message': 'Registration successful! You are now logged in.',
                'user': {
                    'id': user.id,
                    'username': user.username,
                    'email': user.email,
                    'is_email_verified': user.is_email_verified
                }
            }, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class VerifyEmailView(APIView):
    """Email verification endpoint - CSRF exempt for API calls"""
    permission_classes = [permissions.AllowAny]

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        serializer = VerifyEmailSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            return Response({
                'message': 'Email verified successfully! You can now login.',
                'user': UserSerializer(user, context={'request': request}).data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResendVerificationEmailView(APIView):
    """Resend verification email endpoint"""
    permission_classes = [permissions.AllowAny]

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        serializer = ResendVerificationEmailSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            # Generate and send new verification email with dynamic host
            verification_token = user.generate_email_verification_token()
            send_verification_email(user, verification_token, request)
            
            return Response({
                'message': 'Verification email sent! Please check your email.'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ForgotPasswordView(APIView):
    """Forgot password endpoint - request password reset - CSRF exempt for API calls"""
    permission_classes = [permissions.AllowAny]

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        serializer = ForgotPasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.validated_data['user']
            # Generate and send password reset email with dynamic host
            reset_token = user.generate_password_reset_token()
            send_password_reset_email(user, reset_token, request)
            
            return Response({
                'message': 'If this email exists, you will receive a password reset link.'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class ResetPasswordView(APIView):
    """Reset password endpoint - CSRF exempt for API calls"""
    permission_classes = [permissions.AllowAny]

    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            return Response({
                'message': 'Password reset successfully! You can now login with your new password.'
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@method_decorator(csrf_exempt, name='dispatch')
class LoginView(APIView):
    """User login endpoint - CSRF exempt for API calls"""
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            login(request, user)
            # Update last login IP
            user.last_login_ip = self.get_client_ip(request)
            user.save(update_fields=['last_login_ip'])
            return Response({
                'message': 'Login successful',
                'user': UserSerializer(user, context={'request': request}).data
            }, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_401_UNAUTHORIZED)

    def get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class LogoutView(APIView):
    """User logout endpoint"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        logout(request)
        return Response({'message': 'Logout successful'}, status=status.HTTP_200_OK)


class UserProfileView(APIView):
    """User profile endpoint (get and update own profile)"""
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified, IsNotBanned]

    def get(self, request):
        serializer = UserProfileSerializer(request.user, context={'request': request})
        return Response(serializer.data)

    def patch(self, request):
        serializer = UserProfileSerializer(
            request.user,
            data=request.data,
            partial=True,
            context={'request': request}
        )
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class CurrentUserView(APIView):
    """Get current authenticated user"""
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]

    def get(self, request):
        serializer = UserSerializer(request.user, context={'request': request})
        return Response(serializer.data)


class UserVerificationStatsView(APIView):
    """Get user verification statistics and list of verified/unverified users"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        """Get verification statistics"""
        total_users = User.objects.filter(is_active=True).count()
        verified_users = User.objects.filter(is_active=True, is_email_verified=True).count()
        unverified_users = User.objects.filter(is_active=True, is_email_verified=False).count()
        
        return Response({
            'statistics': {
                'total_users': total_users,
                'verified_users': verified_users,
                'unverified_users': unverified_users,
                'verification_rate': round((verified_users / total_users * 100) if total_users > 0 else 0, 2)
            },
            'verified_list': UserSerializer(
                User.objects.filter(is_active=True, is_email_verified=True),
                many=True,
                context={'request': request}
            ).data,
            'unverified_list': UserSerializer(
                User.objects.filter(is_active=True, is_email_verified=False),
                many=True,
                context={'request': request}
            ).data
        }, status=status.HTTP_200_OK)


class UserViewSet(viewsets.ReadOnlyModelViewSet):
    """ViewSet for viewing users (read-only)"""
    queryset = User.objects.filter(is_active=True, is_banned=False)
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified]
    lookup_field = 'username'

    def get_queryset(self):
        queryset = super().get_queryset()
        # Allow filtering by username
        username = self.request.query_params.get('username', None)
        if username:
            queryset = queryset.filter(username__icontains=username)
        return queryset


class TeamViewSet(viewsets.ModelViewSet):
    """ViewSet for team management"""
    queryset = Team.objects.all()
    serializer_class = TeamSerializer
    permission_classes = [permissions.IsAuthenticated, IsEmailVerified, IsNotBanned]
    lookup_field = 'pk'

    def get_serializer_class(self):
        if self.action == 'create':
            return TeamCreateSerializer
        return TeamSerializer

    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter by name if provided
        name = self.request.query_params.get('name', None)
        if name:
            queryset = queryset.filter(name__icontains=name)
        return queryset

    def _get_team_size_limit(self):
        """Return (limit, event) using the active/visible event or default."""
        event = Event.objects.filter(
            Q(is_active=True) | Q(is_visible=True),
            start_time__lte=timezone.now()
        ).order_by('-start_time').first()
        limit = event.max_team_size if event else 5
        return limit, event

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsEmailVerified, IsNotBanned])
    def request_join(self, request, pk=None):
        """Request to join a team"""
        team = self.get_object()

        if team.is_banned:
            return Response(
                {'error': 'This team is banned'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Check if already a member (accepted) or has pending request
        existing = TeamMembership.objects.filter(team=team, user=request.user).first()
        if existing:
            if existing.status == 'accepted':
                return Response(
                    {'error': 'You are already a member of this team'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            elif existing.status == 'pending':
                return Response(
                    {'error': 'You already have a pending join request'},
                    status=status.HTTP_400_BAD_REQUEST
                )

        # Check team size limit based on current event configuration
        limit, _ = self._get_team_size_limit()
        current_members = TeamMembership.objects.filter(team=team, status='accepted').count()
        if current_members >= limit:
            return Response(
                {'error': f'Team is full (limit {limit})'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Create membership request
        message = request.data.get('message', '')
        membership = TeamMembership.objects.create(
            team=team,
            user=request.user,
            status='pending',
            request_message=message,
            is_active=False
        )

        return Response({
            'message': 'Join request sent to team captain',
            'membership': TeamMembershipSerializer(membership).data
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsEmailVerified, IsTeamCaptain])
    def accept_join_request(self, request, pk=None):
        """Accept a join request"""
        team = self.get_object()
        username = request.data.get('username')

        if not username:
            return Response(
                {'error': 'username is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        membership = TeamMembership.objects.filter(team=team, user=user).first()
        if not membership:
            return Response(
                {'error': 'No join request from this user'},
                status=status.HTTP_404_NOT_FOUND
            )

        if membership.status != 'pending':
            return Response(
                {'error': f'Request is already {membership.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Enforce team size limit before accepting
        limit, _ = self._get_team_size_limit()
        accepted_members = TeamMembership.objects.filter(team=team, status='accepted').count()
        if accepted_members >= limit:
            return Response(
                {'error': f'Team is full (limit {limit})'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Accept the request
        membership.accept(accepted_by=request.user)

        return Response({
            'message': 'Join request accepted',
            'membership': TeamMembershipSerializer(membership).data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsEmailVerified, IsTeamCaptain])
    def reject_join_request(self, request, pk=None):
        """Reject a join request"""
        team = self.get_object()
        username = request.data.get('username')

        if not username:
            return Response(
                {'error': 'username is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            user = User.objects.get(username=username)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        membership = TeamMembership.objects.filter(team=team, user=user).first()
        if not membership:
            return Response(
                {'error': 'No join request from this user'},
                status=status.HTTP_404_NOT_FOUND
            )

        if membership.status != 'pending':
            return Response(
                {'error': f'Request is already {membership.status}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Reject the request
        membership.reject()

        return Response({
            'message': 'Join request rejected',
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated, IsEmailVerified, IsTeamCaptain])
    def pending_requests(self, request, pk=None):
        """Get pending join requests for team captain"""
        team = self.get_object()

        pending = TeamMembership.objects.filter(
            team=team,
            status='pending'
        ).select_related('user')

        serializer = TeamMembershipSerializer(pending, many=True)
        return Response({
            'pending_requests': serializer.data,
            'count': pending.count()
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsEmailVerified, IsTeamCaptain])
    def transfer_captaincy(self, request, pk=None):
        """Transfer team captaincy to another member"""
        team = self.get_object()
        new_captain_username = request.data.get('new_captain_username')

        if not new_captain_username:
            return Response(
                {'error': 'new_captain_username is required'},
                status=status.HTTP_400_BAD_REQUEST
            )

        try:
            new_captain = User.objects.get(username=new_captain_username)
        except User.DoesNotExist:
            return Response(
                {'error': 'User not found'},
                status=status.HTTP_404_NOT_FOUND
            )

        if not team.is_member(new_captain):
            return Response(
                {'error': 'User is not a member of this team'},
                status=status.HTTP_400_BAD_REQUEST
            )

        team.captain = new_captain
        team.save()

        serializer = TeamSerializer(team, context={'request': request})
        return Response({
            'message': 'Captaincy transferred successfully',
            'team': serializer.data
        }, status=status.HTTP_200_OK)

    @action(detail=True, methods=['get'], permission_classes=[permissions.IsAuthenticated, IsEmailVerified, IsTeamMember])
    def members(self, request, pk=None):
        """Get team members"""
        team = self.get_object()
        memberships = TeamMembership.objects.filter(team=team, is_active=True)
        serializer = TeamMembershipSerializer(memberships, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsEmailVerified, IsTeamMember])
    def leave(self, request, pk=None):
        """Leave a team - automatically delete team if no members left or promote new captain if captain leaves"""
        team = self.get_object()
        user = request.user

        # Check if user is a member
        membership = TeamMembership.objects.filter(team=team, user=user).first()
        if not membership or not membership.is_active:
            return Response(
                {'error': 'You are not a member of this team'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Mark membership as inactive
        membership.is_active = False
        membership.save()

        # Check if team has any active members left
        active_members = TeamMembership.objects.filter(team=team, is_active=True).count()

        if active_members == 0:
            # No members left - delete the team
            team_name = team.name
            team.delete()
            return Response({
                'message': f'You left the team. Team "{team_name}" was deleted as it has no members left.'
            }, status=status.HTTP_200_OK)
        
        # If captain left, promote the oldest active member
        if team.captain == user:
            remaining_member = TeamMembership.objects.filter(
                team=team,
                is_active=True
            ).select_related('user').order_by('joined_at').first()

            if remaining_member:
                team.captain = remaining_member.user
                team.save()
                return Response({
                    'message': f'You left the team. Captaincy transferred to {remaining_member.user.username}.',
                    'new_captain': remaining_member.user.username
                }, status=status.HTTP_200_OK)
        
        return Response({
            'message': 'You left the team successfully.'
        }, status=status.HTTP_200_OK)

    def perform_create(self, serializer):
        """Create team with current user as captain"""
        # Cancel any pending join requests from this user
        pending_requests = TeamMembership.objects.filter(
            user=self.request.user,
            status='pending'
        )
        pending_requests.delete()
        
        # Create the new team
        team = serializer.save(captain=self.request.user)
        # Add creator as team member
        TeamMembership.objects.create(team=team, user=self.request.user, is_active=True)

    def destroy(self, request, *args, **kwargs):
        """Only captain or staff can delete team"""
        team = self.get_object()
        if team.captain != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Only team captain can delete the team'},
                status=status.HTTP_403_FORBIDDEN
            )
        return super().destroy(request, *args, **kwargs)


# Template views for frontend
class RegistrationForm:
    """Simple form class for template rendering"""
    def __init__(self, data=None):
        self.data = data or {}
        self.errors = {}
        self.full_name = self.data.get('full_name', '')
        self.email = self.data.get('email', '')
    
    def is_valid(self):
        """Basic validation"""
        if not self.full_name:
            self.errors['full_name'] = ['Full name is required']
        if not self.email:
            self.errors['email'] = ['Email is required']
        elif '@' not in self.email:
            self.errors['email'] = ['Invalid email format']
        if not self.data.get('password1'):
            self.errors['password1'] = ['Password is required']
        elif len(self.data.get('password1', '')) < 8:
            self.errors['password1'] = ['Password must be at least 8 characters']
        if self.data.get('password1') != self.data.get('password2'):
            self.errors['password2'] = ['Passwords do not match']
        return len(self.errors) == 0


@require_http_methods(["GET", "POST"])
def login_view(request):
    """Template view for login page"""
    if request.method == 'GET':
        # Check if already logged in
        if request.user.is_authenticated:
            return redirect('ctf_core:index')
        return render(request, 'accounts/login.html', {'form': {}})
    
    # POST - handle login
    email = request.POST.get('email')
    password = request.POST.get('password')
    
    if not email or not password:
        messages.error(request, 'Email and password are required')
        return render(request, 'accounts/login.html', {'form': {'email': email}})
    
    # Authenticate user by email (lookup username from email)
    try:
        user = User.objects.get(email=email)
        if user.is_banned:
            messages.error(request, 'Your account has been banned')
            return render(request, 'accounts/login.html', {'form': {'email': email}})
        
        user = authenticate(request, username=user.username, password=password)
        if user is not None:
            login(request, user)
            # Update last login IP
            user.last_login_ip = get_client_ip(request)
            user.save(update_fields=['last_login_ip'])
            messages.success(request, 'Login successful!')
            next_url = request.GET.get('next', '/')
            # SECURITY: Prevent open redirect vulnerability
            if not next_url or next_url == '/' or not next_url.startswith('/'):
                return redirect('ctf_core:index')
            return redirect(next_url)
        else:
            messages.error(request, 'Invalid email or password')
    except User.DoesNotExist:
        messages.error(request, 'Invalid email or password')
    
    return render(request, 'accounts/login.html', {'form': {'email': email}})


def get_client_ip(request):
    """Get client IP address"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip


@require_http_methods(["GET", "POST"])
def register_view(request):
    """Template view for registration page"""
    # Check if registration is enabled
    settings = PlatformSettings.get_settings()
    if not settings.is_registration_enabled:
        messages.error(request, 'Registration is currently disabled by administrators.')
        return redirect('ctf_core:index')
    
    if request.method == 'GET':
        # Check if already logged in
        if request.user.is_authenticated:
            return redirect('ctf_core:index')
        return render(request, 'accounts/register.html', {'form': {}})
    
    # POST - handle registration
    username = request.POST.get('username', '').strip()
    email = request.POST.get('email', '').strip()
    password = request.POST.get('password', '')
    password_confirm = request.POST.get('password_confirm', '')
    first_name = request.POST.get('first_name', '').strip()
    last_name = request.POST.get('last_name', '').strip()
    
    # Validation
    errors = {}
    form_data = {
        'username': username,
        'email': email,
        'first_name': first_name,
        'last_name': last_name,
    }
    
    if not username:
        errors['username'] = ['Username is required']
    elif len(username) < 3:
        errors['username'] = ['Username must be at least 3 characters']
    elif User.objects.filter(username=username).exists():
        errors['username'] = ['Username already exists']
    
    if not email:
        errors['email'] = ['Email is required']
    elif '@' not in email:
        errors['email'] = ['Invalid email format']
    elif User.objects.filter(email=email).exists():
        errors['email'] = ['Email already registered']
    
    if not password:
        errors['password'] = ['Password is required']
    
    # Check password mismatch - restore form data, only clear passwords
    if password and password_confirm and password != password_confirm:
        errors['password_confirm'] = ['Passwords do not match']
        form_data['password_error'] = True
    
    # Show errors if any
    if errors:
        form_data['errors'] = errors
        return render(request, 'accounts/register.html', {'form': form_data}, status=400)
    
    # Create user
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name
        )

        # If email verification is required, send email; otherwise auto-verify and log in
        if settings.require_email_verification:
            verification_token = user.generate_email_verification_token()
            send_verification_email(user, verification_token, request)
            messages.success(request, 'Registration successful! Please check your email to verify your account.')
            return redirect(f'/accounts/check-email/?email={email}')

        # Auto-verify and login when verification is disabled
        user.is_email_verified = True
        user.save(update_fields=['is_email_verified'])
        login(request, user)
        messages.success(request, 'Registration successful! You are now logged in.')
        return redirect('ctf_core:index')
    except Exception as e:
        messages.error(request, f'Registration failed: {str(e)}')
        form_data['errors'] = {'__all__': [str(e)]}
        return render(request, 'accounts/register.html', {'form': form_data}, status=400)


@require_http_methods(["GET", "POST"])
def logout_view(request):
    """Template view for logout"""
    logout(request)
    messages.success(request, 'Logged out successfully')
    return redirect('ctf_core:index')


@require_http_methods(["GET", "POST"])
def forgot_password_view(request):
    """Template view for forgot password page"""
    if request.method == 'POST':
        email = request.POST.get('email')
        if email:
            try:
                user = User.objects.get(email=email)
                # Generate and send password reset email
                reset_token = user.generate_password_reset_token()
                send_password_reset_email(user, reset_token)
                messages.success(request, 'If an account with that email exists, we have sent password reset instructions.')
            except User.DoesNotExist:
                # Don't reveal if email exists for security
                messages.success(request, 'If an account with that email exists, we have sent password reset instructions.')
        else:
            messages.error(request, 'Email is required')
        return render(request, 'accounts/forgot_password.html')
    
    return render(request, 'accounts/forgot_password.html')


def check_email_view(request):
    """Template view to show 'check your email' message after registration"""
    email = request.GET.get('email', '')
    context = {
        'email': email,
    }
    return render(request, 'accounts/check_email.html', context)


@login_required
@require_http_methods(["GET"])
def verification_dashboard_view(request):
    """Template view for email verification dashboard"""
    # Only allow staff/superusers to view this
    if not request.user.is_staff and not request.user.is_superuser:
        messages.error(request, 'You do not have permission to access this page')
        return redirect('accounts:profile')
    
    return render(request, 'accounts/verification_dashboard.html')


def resend_verification_view(request):
    """Template view for resending verification email"""
    email = request.GET.get('email', '')
    context = {
        'email': email,
    }
    return render(request, 'accounts/resend_verification.html', context)


def verify_email_view(request):
    """Template view for email verification page - auto-verifies from email link"""
    token = request.GET.get('token', '')
    email = request.GET.get('email', '')
    
    context = {
        'token': token,
        'email': email,
    }
    return render(request, 'accounts/verify_email_simple.html', context)


def reset_password_view(request):
    """Template view for password reset page"""
    token = request.GET.get('token', '')
    email = request.GET.get('email', '')
    
    context = {
        'token': token,
        'email': email,
    }
    return render(request, 'accounts/reset_password.html', context)


@login_required
@email_verified_required
@require_http_methods(["GET"])
def profile_view(request):
    """Template view for user profile"""
    from submissions.models import Submission, Score
    
    # Get user's teams
    user_teams = TeamMembership.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('team')
    
    # Get user statistics
    total_submissions = Submission.objects.filter(user=request.user).count()
    correct_submissions = Submission.objects.filter(user=request.user, status='correct').count()
    
    # Get total score from latest entries for each team
    total_score = 0
    for membership in user_teams:
        team = membership.team
        latest = Score.objects.filter(team=team).order_by('-created_at').first()
        if latest:
            total_score += latest.total_score
    
    # User solves list with earned points
    user_solves = (
        Submission.objects.filter(user=request.user, status='correct')
        .select_related('challenge', 'team')
        .order_by('-submitted_at')
    )
    # Sum of points awarded on correct submissions (personal earned)
    user_points = sum([getattr(s, 'points_awarded', 0) for s in user_solves])

    context = {
        'user_teams': user_teams,
        'user_stats': {
            'total_submissions': total_submissions,
            'correct_submissions': correct_submissions,
            'total_score': total_score,
            'personal_points': user_points,
        },
        'user_solves': user_solves,
    }
    
    return render(request, 'accounts/profile.html', context)


@login_required
@email_verified_required
@require_http_methods(["GET"])
def teams_list_view(request):
    """Template view for listing all teams"""
    # Get search query
    search_query = request.GET.get('search', '').strip()
    
    # Base queryset
    teams = Team.objects.filter(is_banned=False).annotate(
        member_count=Count('memberships', filter=Q(memberships__is_active=True))
    )
    
    # Apply search filter
    if search_query:
        teams = teams.filter(
            Q(name__icontains=search_query) | 
            Q(description__icontains=search_query) |
            Q(captain__username__icontains=search_query)
        )
    
    # Order by
    teams = teams.order_by('-created_at')
    
    # Get user's current team
    user_team = None
    try:
        membership = TeamMembership.objects.filter(
            user=request.user,
            is_active=True
        ).select_related('team').first()
        if membership:
            user_team = membership.team
    except TeamMembership.DoesNotExist:
        pass
    
    context = {
        'teams': teams,
        'user_team': user_team,
        'search_query': search_query,
    }
    
    return render(request, 'accounts/teams.html', context)


@login_required
@email_verified_required
@require_http_methods(["GET", "POST"])
def team_create_view(request):
    """Template view for creating a team"""
    # Check if user already has a team
    existing_team = TeamMembership.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('team').first()
    
    if existing_team:
        messages.warning(request, 'You are already a member of a team')
        return redirect('accounts:teams_list')
    
    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        
        # Validation
        if not name:
            messages.error(request, 'Team name is required')
            return render(request, 'accounts/team_create.html')
        
        if len(name) < 3:
            messages.error(request, 'Team name must be at least 3 characters')
            return render(request, 'accounts/team_create.html')
        
        if Team.objects.filter(name=name).exists():
            messages.error(request, 'A team with this name already exists')
            return render(request, 'accounts/team_create.html')
        
        try:
            # Create team
            team = Team.objects.create(
                name=name,
                description=description,
                captain=request.user
            )
            
            # Add creator as team member (automatically accepted as captain)
            TeamMembership.objects.create(
                team=team,
                user=request.user,
                status='accepted',
                is_active=True
            )
            
            messages.success(request, f'Team "{name}" created successfully!')
            return redirect('accounts:team_detail', team_id=team.id)
            
        except Exception as e:
            messages.error(request, f'An error occurred while creating the team: {str(e)}')
            return render(request, 'accounts/team_create.html')
    
    return render(request, 'accounts/team_create.html')


@login_required
@email_verified_required
@require_http_methods(["GET"])
def team_detail_view(request, team_id):
    """Template view for team details"""
    from submissions.models import Score
    
    try:
        team = Team.objects.get(id=team_id)
    except Team.DoesNotExist:
        messages.error(request, 'Team not found')
        return redirect('accounts:teams_list')
    
    # SECURITY: Check if user is a member - prevent IDOR
    is_member = team.is_member(request.user)
    is_captain = team.captain == request.user
    
    # Only allow team members or staff to view team details
    if not is_member and not request.user.is_staff:
        messages.error(request, 'You do not have permission to view this team')
        return redirect('accounts:teams_list')
    
    # Get team members (accepted only)
    members = TeamMembership.objects.filter(
        team=team,
        status='accepted'
    ).select_related('user').order_by('-joined_at')
    
    # Get pending join requests (captain only)
    pending_requests = []
    if is_captain:
        pending_requests = TeamMembership.objects.filter(
            team=team,
            status='pending'
        ).select_related('user').order_by('joined_at')
    
    # Get team stats - use latest total_score entry
    latest_score = Score.objects.filter(team=team).order_by('-created_at').first()
    total_score = latest_score.total_score if latest_score else 0
    
    # Get team rank - get latest score for each team
    from django.db.models import OuterRef, Subquery
    from submissions.models import Score as ScoreModel
    
    # Get latest score id for each team
    latest_scores = ScoreModel.objects.filter(
        team_id=OuterRef('team')
    ).order_by('-created_at').values('id')[:1]
    
    teams_with_scores = ScoreModel.objects.filter(
        id__in=Subquery(latest_scores)
    ).values('team__id', 'total_score').order_by('-total_score')
    
    rank = None
    for idx, entry in enumerate(teams_with_scores, 1):
        if entry['team__id'] == team.id:
            rank = idx
            break

    # Team solves (who solved what and by whom)
    from submissions.models import Submission as SubmissionModel
    team_solves = (
        SubmissionModel.objects.filter(team=team, status='correct')
        .select_related('challenge', 'user')
        .order_by('-submitted_at')
    )

    context = {
        'team': team,
        'is_member': is_member,
        'is_captain': is_captain,
        'members': members,
        'pending_requests': pending_requests,
        'team_stats': {
            'member_count': members.count(),
            'total_score': total_score,
            'rank': rank,
        },
        'team_solves': team_solves,
    }
    
    return render(request, 'accounts/team_detail.html', context)
