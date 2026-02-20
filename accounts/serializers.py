from rest_framework import serializers
from django.contrib.auth import authenticate
from .models import User, Team, TeamMembership


class UserRegistrationSerializer(serializers.ModelSerializer):
    """Serializer for user registration"""
    password = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )
    password_confirm = serializers.CharField(
        write_only=True,
        required=True,
        style={'input_type': 'password'}
    )

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'password', 'password_confirm',
            'first_name', 'last_name', 'bio'
        ]
        extra_kwargs = {
            'email': {'required': True},
            'username': {'required': True},
        }

    def validate(self, attrs):
        if attrs['password'] != attrs['password_confirm']:
            raise serializers.ValidationError({
                "password": "Password fields didn't match."
            })
        return attrs

    def validate_email(self, value):
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("A user with this email already exists.")
        return value

    def validate_username(self, value):
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("A user with this username already exists.")
        return value

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        password = validated_data.pop('password')
        require_email_verification = self.context.get('require_email_verification', True)

        # create_user() already hashes the password
        user = User.objects.create_user(password=password, **validated_data)

        # If verification is not required, mark as verified immediately
        if not require_email_verification:
            user.is_email_verified = True
            user.save(update_fields=['is_email_verified'])

        return user


class UserSerializer(serializers.ModelSerializer):
    """Serializer for user details"""
    team_count = serializers.SerializerMethodField()
    verification_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'bio', 'avatar', 'is_banned', 'is_email_verified', 'team_count',
            'verification_status', 'created_at', 'last_login'
        ]
        read_only_fields = ['id', 'is_banned', 'is_email_verified', 'created_at', 'last_login']

    def get_team_count(self, obj):
        return obj.teams.count()
    
    def get_verification_status(self, obj):
        """Return human-readable verification status"""
        if obj.is_email_verified:
            return {
                'status': 'verified',
                'message': '✓ Email Verified',
                'color': 'green',
                'icon': '✅'
            }
        else:
            return {
                'status': 'unverified',
                'message': '⚠ Email Not Verified',
                'color': 'red',
                'icon': '❌'
            }


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile (self-editable)"""
    teams = serializers.SerializerMethodField()
    verification_status = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name',
            'bio', 'avatar', 'email_notifications', 'is_email_verified',
            'teams', 'verification_status', 'created_at', 'last_login'
        ]
        read_only_fields = ['id', 'username', 'is_email_verified', 'created_at', 'last_login']

    def get_teams(self, obj):
        teams = obj.teams.all()
        return TeamSerializer(teams, many=True, context=self.context).data
    
    def get_verification_status(self, obj):
        """Return detailed verification status for profile"""
        if obj.is_email_verified:
            return {
                'status': 'verified',
                'message': '✓ Your email is verified',
                'color': 'green',
                'icon': '✅',
                'description': 'You have full access to all platform features'
            }
        else:
            return {
                'status': 'unverified',
                'message': '⚠ Email not verified',
                'color': 'red',
                'icon': '❌',
                'description': 'Please verify your email to access all features',
                'action': 'Check your inbox for verification link'
            }


class LoginSerializer(serializers.Serializer):
    """Serializer for user login"""
    username = serializers.CharField(required=True)
    password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        username = attrs.get('username')
        password = attrs.get('password')

        if username and password:
            # Allow login with email (case-insensitive) or username
            lookup_username = username
            if '@' in username:
                try:
                    from .models import User
                    user_obj = User.objects.filter(email__iexact=username).first()
                    if user_obj:
                        lookup_username = user_obj.username
                except Exception:
                    pass

            user = authenticate(
                request=self.context.get('request'),
                username=lookup_username,
                password=password
            )

            if not user:
                raise serializers.ValidationError(
                    'Invalid credentials. Please check your username and password.'
                )

            if not user.is_active:
                raise serializers.ValidationError('User account is disabled.')

            if user.is_banned:
                raise serializers.ValidationError('User account is banned.')

            # Check if email verification is required by platform settings
            from .models import PlatformSettings
            settings = PlatformSettings.get_settings()
            if settings.require_email_verification and not user.is_email_verified:
                raise serializers.ValidationError(
                    'Please verify your email address before logging in. Check your email for the verification link.'
                )

            attrs['user'] = user
            return attrs
        else:
            raise serializers.ValidationError('Must include "username" and "password".')


class TeamSerializer(serializers.ModelSerializer):
    """Serializer for team details"""
    member_count = serializers.SerializerMethodField()
    captain_username = serializers.CharField(source='captain.username', read_only=True)
    members = serializers.SerializerMethodField()
    is_member = serializers.SerializerMethodField()

    class Meta:
        model = Team
        fields = [
            'id', 'name', 'description', 'avatar', 'website',
            'captain', 'captain_username', 'member_count',
            'members', 'is_member', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']

    def get_member_count(self, obj):
        return obj.get_member_count()

    def get_members(self, obj):
        members = obj.members.all()
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            # Only show members if user is a member or admin
            if obj.is_member(request.user) or request.user.is_staff:
                return UserSerializer(members, many=True, context=self.context).data
        return []

    def get_is_member(self, obj):
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            return obj.is_member(request.user)
        return False


class TeamCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating a team"""
    class Meta:
        model = Team
        fields = ['name', 'description', 'avatar', 'website']

    def validate_name(self, value):
        # Case-insensitive check for existing team name
        if Team.objects.filter(name__iexact=value).exists():
            raise serializers.ValidationError("This team name is already taken. Please choose a different name.")
        return value

    def create(self, validated_data):
        from django.db import IntegrityError
        request = self.context.get('request')
        
        try:
            team = Team.objects.create(**validated_data)
            team.captain = request.user
            team.save()
            # Add creator as team member
            TeamMembership.objects.create(team=team, user=request.user)
        except IntegrityError:
            # Catch race condition where name was taken between validation and creation
            raise serializers.ValidationError({
                'name': 'This team name is already taken. Please choose a different name.'
            })
        return team


class TeamMembershipSerializer(serializers.ModelSerializer):
    """Serializer for team membership"""
    user = UserSerializer(read_only=True)
    team = TeamSerializer(read_only=True)

    class Meta:
        model = TeamMembership
        fields = ['id', 'user', 'team', 'joined_at', 'is_active']
        read_only_fields = ['id', 'joined_at']


class VerifyEmailSerializer(serializers.Serializer):
    """Serializer for email verification"""
    email = serializers.EmailField(required=True)
    token = serializers.CharField(required=True, max_length=255)

    def validate(self, attrs):
        email = attrs.get('email')
        token = attrs.get('token')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid email or token.')

        if user.is_email_verified:
            raise serializers.ValidationError('Email is already verified.')

        if not user.verify_email_token(token, token_expiry_hours=24):
            raise serializers.ValidationError('Invalid or expired verification token.')

        attrs['user'] = user
        return attrs


class ResendVerificationEmailSerializer(serializers.Serializer):
    """Serializer for resending verification email"""
    email = serializers.EmailField(required=True)

    def validate(self, attrs):
        email = attrs.get('email')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError('User with this email does not exist.')

        if user.is_email_verified:
            raise serializers.ValidationError('Email is already verified.')

        attrs['user'] = user
        return attrs


class ForgotPasswordSerializer(serializers.Serializer):
    """Serializer for forgot password request"""
    email = serializers.EmailField(required=True)

    def validate(self, attrs):
        email = attrs.get('email')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            # For security, don't reveal if user exists
            raise serializers.ValidationError('If this email exists, you will receive a password reset link.')

        attrs['user'] = user
        return attrs


class ResetPasswordSerializer(serializers.Serializer):
    """Serializer for password reset"""
    email = serializers.EmailField(required=True)
    token = serializers.CharField(required=True, max_length=255)
    new_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )
    confirm_password = serializers.CharField(
        required=True,
        write_only=True,
        style={'input_type': 'password'}
    )

    def validate(self, attrs):
        email = attrs.get('email')
        token = attrs.get('token')
        new_password = attrs.get('new_password')
        confirm_password = attrs.get('confirm_password')

        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid email or token.')

        if not user.verify_password_reset_token(token, token_expiry_hours=1):
            raise serializers.ValidationError('Invalid or expired password reset token.')

        if new_password != confirm_password:
            raise serializers.ValidationError({
                'confirm_password': "Passwords don't match."
            })

        attrs['user'] = user
        return attrs

    def save(self):
        user = self.validated_data['user']
        user.set_password(self.validated_data['new_password'])
        user.password_reset_token = None
        user.password_reset_token_created_at = None
        user.save()
        return user
