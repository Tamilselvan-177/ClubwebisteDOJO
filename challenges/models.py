from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import secrets


class Category(models.Model):
    """
    Challenge category model.
    Groups challenges by type (e.g., Web, Crypto, Forensics, etc.)
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, blank=True, help_text="Icon class or emoji")
    color = models.CharField(max_length=7, default='#E50914', help_text="Hex color code")
    
    class Meta:
        db_table = 'categories'
        verbose_name = 'Category'
        verbose_name_plural = 'Categories'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Challenge(models.Model):
    """
    Challenge model representing CTF challenges.
    Supports categories, scheduling, hints, files, and dynamic scoring.
    """
    # Basic information
    name = models.CharField(max_length=200, db_index=True)
    description = models.TextField()
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True, related_name='challenges')
    event = models.ForeignKey('events_ctf.Event', on_delete=models.CASCADE, related_name='challenges')
    difficulty = models.CharField(
        max_length=20,
        choices=[
            ('easy', 'Easy'),
            ('medium', 'Medium'),
            ('hard', 'Hard'),
            ('expert', 'Expert'),
        ],
        default='medium',
        help_text="Challenge difficulty level"
    )
    
    # Challenge status
    is_visible = models.BooleanField(default=False, help_text="Challenge is visible to participants")
    is_active = models.BooleanField(default=True, help_text="Challenge is active")
    
    # Scoring
    points = models.PositiveIntegerField(
        default=100,
        validators=[MinValueValidator(1)],
        help_text="Initial points for the challenge"
    )
    minimum_points = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1)],
        help_text="Minimum points (for dynamic scoring)"
    )
    decay = models.PositiveIntegerField(
        default=0,
        help_text="Points decay per solve (for dynamic scoring)"
    )
    
    # Challenge type
    challenge_type = models.CharField(
        max_length=20,
        choices=[
            ('standard', 'Standard'),
            ('instance', 'Instance-based'),
        ],
        default='standard',
        help_text="Challenge type"
    )
    
    # Flag configuration (for standard challenges)
    flag = models.CharField(max_length=500, blank=True, help_text="Flag for standard challenges")
    flag_type = models.CharField(
        max_length=20,
        choices=[
            ('static', 'Static Flag'),
            ('regex', 'Regex Pattern'),
        ],
        default='static',
        help_text="Flag matching type"
    )
    
    # Instance configuration (for instance-based challenges)
    instance_config = models.JSONField(
        default=dict,
        blank=True,
        help_text="Docker/instance configuration (image, ports, env vars, etc.)"
    )
    instance_flag_format = models.CharField(
        max_length=200,
        blank=True,
        default='CTF{random}',
        help_text="Flag format template for instances (use {random} for random string)"
    )
    instance_time_limit_minutes = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Time limit for instances in minutes (overrides event default if set)"
    )
    max_instances_per_team = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Maximum number of concurrent instances per team for this challenge"
    )
    
    # Instance URL display type
    INSTANCE_URL_TYPE_CHOICES = [
        ('web_url', 'Web URL (http://domain:port)'),
        ('netcat', 'Netcat (nc ip port)'),
    ]
    instance_url_type = models.CharField(
        max_length=20,
        choices=INSTANCE_URL_TYPE_CHOICES,
        default='web_url',
        help_text="How to display access URL for instance (web browser or netcat)"
    )
    
    # Admin-controlled instance settings
    allow_instance_renewal = models.BooleanField(
        default=False,
        help_text="Allow teams to renew/extend instances before expiration"
    )
    instance_renewal_limit = models.PositiveIntegerField(
        default=0,
        help_text="Maximum number of renewals per instance (0 = unlimited)"
    )
    instance_renewal_minutes = models.PositiveIntegerField(
        default=30,
        help_text="Additional minutes added per renewal"
    )
    instance_renewal_min_threshold = models.PositiveIntegerField(
        default=30,
        help_text="Show renew button only when instance has less than this many minutes remaining"
    )
    reduce_points_on_expiry = models.BooleanField(
        default=True,
        help_text="Reduce team points when instance expires"
    )
    reduce_points_on_stop = models.BooleanField(
        default=True,
        help_text="Reduce team points when user manually stops instance"
    )
    reduce_points_on_wrong_flag = models.BooleanField(
        default=True,
        help_text="Reduce team points when wrong flag submitted (additional to generic penalty)"
    )
    
    # Penalty Configuration
    PENALTY_TYPE_CHOICES = [
        ('percentage', 'Percentage of Challenge Points'),
        ('fixed', 'Fixed Points'),
    ]
    penalty_type = models.CharField(
        max_length=20,
        choices=PENALTY_TYPE_CHOICES,
        default='percentage',
        help_text="Type of penalty calculation"
    )
    penalty_percentage = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Percentage of challenge points to deduct (1-100%)"
    )
    penalty_fixed_points = models.PositiveIntegerField(
        default=10,
        validators=[MinValueValidator(1)],
        help_text="Fixed points to deduct per penalty"
    )
    
    # Challenge files and hints
    files = models.ManyToManyField('ChallengeFile', blank=True, related_name='challenges')
    
    # Scheduling
    release_time = models.DateTimeField(null=True, blank=True, help_text="When challenge becomes visible")
    
    # Metadata
    author = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='authored_challenges'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    solve_count = models.PositiveIntegerField(default=0, help_text="Number of successful solves")
    
    class Meta:
        db_table = 'challenges'
        verbose_name = 'Challenge'
        verbose_name_plural = 'Challenges'
        ordering = ['category', 'points', 'name']
        indexes = [
            models.Index(fields=['event', 'is_visible', 'is_active']),
            models.Index(fields=['category']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.event.name})"
    
    def is_released(self):
        """Check if challenge is released"""
        if not self.is_visible or not self.is_active:
            return False
        if self.release_time and timezone.now() < self.release_time:
            return False
        return True
    
    def get_current_points(self):
        """Calculate current points (for dynamic scoring)"""
        if self.decay == 0:
            return self.points
        # Dynamic scoring formula
        current_points = max(
            self.points - (self.solve_count * self.decay),
            self.minimum_points
        )
        return current_points


class ChallengeFile(models.Model):
    """
    Challenge file model.
    Stores files associated with challenges.
    """
    name = models.CharField(max_length=200)
    file = models.FileField(upload_to='challenges/files/')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'challenge_files'
        verbose_name = 'Challenge File'
        verbose_name_plural = 'Challenge Files'
        ordering = ['name']
    
    def __str__(self):
        return self.name


class Hint(models.Model):
    """
    Hint model for challenges.
    Hints can have point costs.
    """
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='hints')
    text = models.TextField()
    cost = models.PositiveIntegerField(default=0, help_text="Points cost to unlock hint")
    is_visible = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0, help_text="Display order")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'hints'
        verbose_name = 'Hint'
        verbose_name_plural = 'Hints'
        ordering = ['order', 'created_at']
    
    def __str__(self):
        return f"Hint for {self.challenge.name}"


class HintUnlock(models.Model):
    """
    Tracks which teams have unlocked which hints.
    """
    hint = models.ForeignKey(Hint, on_delete=models.CASCADE, related_name='unlocks')
    team = models.ForeignKey('accounts.Team', on_delete=models.CASCADE, related_name='unlocked_hints')
    event = models.ForeignKey('events_ctf.Event', on_delete=models.CASCADE, related_name='hint_unlocks')
    unlocked_at = models.DateTimeField(auto_now_add=True)
    cost_paid = models.PositiveIntegerField(help_text="Points deducted when unlocked")
    
    class Meta:
        db_table = 'hint_unlocks'
        verbose_name = 'Hint Unlock'
        verbose_name_plural = 'Hint Unlocks'
        unique_together = ['hint', 'team', 'event']
        ordering = ['-unlocked_at']
    
    def __str__(self):
        return f"{self.team.name} unlocked hint for {self.hint.challenge.name}"


class ChallengeInstance(models.Model):
    """
    ChallengeInstance model for per-team isolated instances.
    Each team gets their own instance with a unique flag.
    """
    STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('starting', 'Starting'),
        ('running', 'Running'),
        ('stopping', 'Stopping'),
        ('stopped', 'Stopped'),
        ('error', 'Error'),
    ]
    
    # Relationships
    challenge = models.ForeignKey(Challenge, on_delete=models.CASCADE, related_name='instances')
    team = models.ForeignKey('accounts.Team', on_delete=models.CASCADE, related_name='instances')
    started_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='started_instances'
    )
    event = models.ForeignKey('events_ctf.Event', on_delete=models.CASCADE, related_name='instances')
    
    # Instance identification
    container_id = models.CharField(max_length=200, blank=True, db_index=True, help_text="Docker container ID")
    instance_id = models.CharField(max_length=100, unique=True, db_index=True, help_text="Unique instance identifier")
    
    # Instance flag (unique per instance)
    flag = models.CharField(max_length=500, db_index=True, help_text="Unique flag for this instance")
    flag_hash = models.CharField(
        max_length=128,
        db_index=True,
        blank=True,
        help_text="SHA256 hash of the instance flag for fast copy detection"
    )
    
    # Access information
    access_url = models.URLField(blank=True, help_text="URL to access the instance")
    access_port = models.PositiveIntegerField(null=True, blank=True, help_text="Port to access the instance")
    container_ip = models.GenericIPAddressField(null=True, blank=True, help_text="Docker container IP address")
    
    # Status
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    error_message = models.TextField(blank=True, help_text="Error message if instance failed")
    
    # Timestamps
    started_at = models.DateTimeField(auto_now_add=True)
    stopped_at = models.DateTimeField(null=True, blank=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Instance expiration time")
    
    # Renewal tracking
    renewal_count = models.PositiveIntegerField(
        default=0,
        help_text="Number of times instance has been renewed"
    )
    last_renewed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When instance was last renewed"
    )
    renewed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='renewed_instances',
        help_text="User who last renewed instance"
    )
    
    # Metadata
    config_snapshot = models.JSONField(default=dict, blank=True, help_text="Snapshot of instance config")
    
    class Meta:
        db_table = 'challenge_instances'
        verbose_name = 'Challenge Instance'
        verbose_name_plural = 'Challenge Instances'
        unique_together = ['challenge', 'team', 'instance_id']
        indexes = [
            models.Index(fields=['team', 'challenge', 'status']),
            models.Index(fields=['container_id']),
            models.Index(fields=['instance_id']),
            models.Index(fields=['flag']),
            models.Index(fields=['flag_hash']),
            models.Index(fields=['status', 'expires_at']),
        ]
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.team.name} - {self.challenge.name} ({self.instance_id})"
    
    def generate_flag(self):
        """Generate a unique flag for this instance with event prefix and hash"""
        random_part = secrets.token_urlsafe(16)
        flag_format = self.challenge.instance_flag_format or 'CTF{random}'
        base_flag = flag_format.replace('{random}', random_part)
        event_prefix = self.event.slug if self.event and hasattr(self.event, 'slug') else 'event'
        full_flag = f"{event_prefix}_{base_flag}"
        return full_flag
    
    def save(self, *args, **kwargs):
        if not self.instance_id:
            # Generate unique instance ID
            self.instance_id = f"{self.challenge.id}-{self.team.id}-{secrets.token_urlsafe(8)}"
        if not self.flag and self.challenge.challenge_type == 'instance':
            # Generate flag for instance-based challenges
            self.flag = self.generate_flag()
        # Always ensure flag_hash is set for copy detection
        if self.flag and not self.flag_hash:
            import hashlib
            self.flag_hash = hashlib.sha256(self.flag.encode()).hexdigest()
        super().save(*args, **kwargs)
    
    def is_active(self):
        """Check if instance is currently active"""
        return self.status == 'running'
    
    def can_renew(self):
        """Check if instance can be renewed"""
        if not self.challenge.allow_instance_renewal:
            return False, "Renewal not allowed for this challenge"
        
        if self.status != 'running':
            return False, "Instance is not running"
        
        # SECURITY: Check if instance has expired
        from django.utils import timezone
        if self.expires_at and self.expires_at <= timezone.now():
            return False, "Instance has expired. Please start a new instance."
        
        renewal_limit = self.challenge.instance_renewal_limit
        if renewal_limit > 0 and self.renewal_count >= renewal_limit:
            return False, f"Maximum renewals ({renewal_limit}) reached"
        
        return True, "OK"
    
    def renew(self, user, minutes=None):
        """
        Renew/extend instance expiration time
        
        Args:
            user: User who is renewing
            minutes: Minutes to extend (uses challenge default if None)
        
        Returns:
            (success, message, new_expiry)
        """
        from django.utils import timezone
        from datetime import timedelta
        
        can_renew, reason = self.can_renew()
        if not can_renew:
            return False, reason, None
        
        # Get renewal minutes
        if minutes is None:
            minutes = self.challenge.instance_renewal_minutes
        
        # Extend expiration, but don't exceed the original instance time limit
        if self.expires_at:
            new_expiry = self.expires_at + timedelta(minutes=minutes)
        else:
            new_expiry = timezone.now() + timedelta(minutes=minutes)
        
        # Calculate max allowed expiry: started_at + instance_time_limit_minutes
        if self.started_at and self.challenge.instance_time_limit_minutes:
            max_allowed_expiry = self.started_at + timedelta(minutes=self.challenge.instance_time_limit_minutes)
            # If renewal would exceed limit, give fresh time limit from now
            if new_expiry > max_allowed_expiry:
                new_expiry = timezone.now() + timedelta(minutes=self.challenge.instance_time_limit_minutes)
        
        self.expires_at = new_expiry
        self.renewal_count += 1
        self.last_renewed_at = timezone.now()
        self.renewed_by = user
        self.save(update_fields=['expires_at', 'renewal_count', 'last_renewed_at', 'renewed_by'])
        
        return True, f"Instance renewed for {minutes} minutes", new_expiry
    
    def is_expired(self):
        """Check if instance has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
    
    def stop(self):
        """Mark instance as stopped"""
        self.status = 'stopped'
        self.stopped_at = timezone.now()
        self.save()
    
    def mark_error(self, error_msg):
        """Mark instance as error"""
        self.status = 'error'
        self.error_message = error_msg
        self.stopped_at = timezone.now()
        self.save()
