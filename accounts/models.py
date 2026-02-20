from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class User(AbstractUser):
    """
    Custom User model extending Django's AbstractUser.
    Stores user profile information and team membership.
    """
    email = models.EmailField(unique=True, blank=False)
    is_banned = models.BooleanField(default=False, help_text="User is banned from the platform")
    banned_at = models.DateTimeField(null=True, blank=True, help_text="When the user was banned")
    banned_reason = models.TextField(blank=True, help_text="Reason for banning")
    
    # Profile fields
    bio = models.TextField(blank=True, max_length=500)
    avatar = models.ImageField(upload_to='avatars/', null=True, blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)
    
    # Preferences
    email_notifications = models.BooleanField(default=True)
    
    # Email Verification
    is_email_verified = models.BooleanField(default=False, help_text="User has verified their email")
    email_verification_token = models.CharField(max_length=255, blank=True, unique=True, null=True, db_index=True)
    email_verification_token_created_at = models.DateTimeField(null=True, blank=True)
    
    # Password Reset
    password_reset_token = models.CharField(max_length=255, blank=True, unique=True, null=True, db_index=True)
    password_reset_token_created_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        db_table = 'users'
        verbose_name = 'User'
        verbose_name_plural = 'Users'
        ordering = ['-created_at']
    
    def __str__(self):
        return self.username
    
    def ban(self, reason=""):
        """Ban the user"""
        self.is_banned = True
        self.banned_at = timezone.now()
        self.banned_reason = reason
        self.save()
    
    def unban(self):
        """Unban the user"""
        self.is_banned = False
        self.banned_at = None
        self.banned_reason = ""
        self.save()
    
    def generate_email_verification_token(self):
        """Generate email verification token"""
        import secrets
        self.email_verification_token = secrets.token_urlsafe(32)
        self.email_verification_token_created_at = timezone.now()
        self.save()
        return self.email_verification_token
    
    def generate_password_reset_token(self):
        """Generate password reset token"""
        import secrets
        self.password_reset_token = secrets.token_urlsafe(32)
        self.password_reset_token_created_at = timezone.now()
        self.save()
        return self.password_reset_token
    
    def verify_email_token(self, token, token_expiry_hours=24):
        """Verify email verification token"""
        if self.email_verification_token != token:
            return False
        if not self.email_verification_token_created_at:
            return False
        
        # Check if token has expired
        expiry_time = self.email_verification_token_created_at + timezone.timedelta(hours=token_expiry_hours)
        if timezone.now() > expiry_time:
            return False
        
        # Mark email as verified
        self.is_email_verified = True
        self.email_verification_token = None
        self.email_verification_token_created_at = None
        self.save()
        return True
    
    def verify_password_reset_token(self, token, token_expiry_hours=1):
        """Verify password reset token"""
        if self.password_reset_token != token:
            return False
        if not self.password_reset_token_created_at:
            return False
        
        # Check if token has expired
        expiry_time = self.password_reset_token_created_at + timezone.timedelta(hours=token_expiry_hours)
        if timezone.now() > expiry_time:
            return False
        
        return True


class Team(models.Model):
    """
    Team model representing a group of users.
    Teams can have multiple members and participate in events.
    """
    name = models.CharField(max_length=100, unique=True, db_index=True)
    description = models.TextField(blank=True, max_length=500)
    
    # Team members (many-to-many with User)
    members = models.ManyToManyField(User, related_name='teams', through='TeamMembership', through_fields=('team', 'user'))
    captain = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='captained_teams')
    
    # Team status
    is_banned = models.BooleanField(default=False, help_text="Team is banned from competitions")
    banned_at = models.DateTimeField(null=True, blank=True)
    banned_reason = models.TextField(blank=True)
    
    # Team metadata
    avatar = models.ImageField(upload_to='team_avatars/', null=True, blank=True)
    website = models.URLField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'teams'
        verbose_name = 'Team'
        verbose_name_plural = 'Teams'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def get_member_count(self):
        """Get the number of accepted team members"""
        return self.memberships.filter(status='accepted').count()
    
    def is_member(self, user):
        """Check if a user is an accepted member of this team"""
        return self.memberships.filter(user=user, status='accepted').exists()
    
    def ban(self, reason=""):
        """Ban the team"""
        self.is_banned = True
        self.banned_at = timezone.now()
        self.banned_reason = reason
        self.save()
    
    def unban(self):
        """Unban the team"""
        self.is_banned = False
        self.banned_at = None
        self.banned_reason = ""
        self.save()


class TeamMembership(models.Model):
    """
    Through model for Team-User many-to-many relationship.
    Tracks when a user joined a team.
    Supports join requests: status can be 'pending', 'accepted', or 'rejected'.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending Request'),
        ('accepted', 'Accepted Member'),
        ('rejected', 'Rejected'),
    ]
    
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='memberships')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='team_memberships')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    # Join request tracking
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    request_message = models.TextField(blank=True, help_text="Message when requesting to join")
    accepted_at = models.DateTimeField(null=True, blank=True)
    accepted_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='accepted_membership_requests')
    
    class Meta:
        db_table = 'team_memberships'
        unique_together = ['team', 'user']
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.user.username} in {self.team.name} ({self.status})"
    
    def accept(self, accepted_by):
        """Accept a join request"""
        from django.utils import timezone
        self.status = 'accepted'
        self.is_active = True
        self.accepted_at = timezone.now()
        self.accepted_by = accepted_by
        self.save()
    
    def reject(self):
        """Reject a join request"""
        self.status = 'rejected'
        self.is_active = False
        self.save()


class PlatformSettings(models.Model):
    """
    Singleton model for platform-wide settings.
    Only one instance should exist in the database.
    """
    is_registration_enabled = models.BooleanField(
        default=True,
        help_text="Allow new user registration on the platform"
    )
    
    require_email_verification = models.BooleanField(
        default=True,
        help_text="Require users to verify their email before logging in"
    )
    
    # Add more settings as needed
    maintenance_mode = models.BooleanField(
        default=False,
        help_text="Enable maintenance mode"
    )
    maintenance_message = models.TextField(
        blank=True,
        help_text="Message to display when in maintenance mode"
    )
    
    # Timestamps
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'platform_settings'
        verbose_name = 'Platform Settings'
        verbose_name_plural = 'Platform Settings'
    
    def __str__(self):
        return "Platform Settings"
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists"""
        if not self.pk and PlatformSettings.objects.exists():
            # Update existing instance instead
            obj = PlatformSettings.objects.first()
            obj.is_registration_enabled = self.is_registration_enabled
            obj.require_email_verification = self.require_email_verification
            obj.maintenance_mode = self.maintenance_mode
            obj.maintenance_message = self.maintenance_message
            obj.save()
            return
        super().save(*args, **kwargs)
    
    @classmethod
    def get_settings(cls):
        """Get or create the platform settings instance"""
        settings, created = cls.objects.get_or_create(pk=1)
        return settings
