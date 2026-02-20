from django.db import models
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey


class Theme(models.Model):
    """
    Theme model for event theming.
    Stores UI theme configuration for events.
    """
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    
    # Color scheme (JSON field or individual fields)
    primary_color = models.CharField(max_length=7, default='#E50914', help_text="Hex color code")
    secondary_color = models.CharField(max_length=7, default='#00D4FF', help_text="Hex color code")
    background_color = models.CharField(max_length=7, default='#0A0A0A', help_text="Hex color code")
    text_color = models.CharField(max_length=7, default='#E0E0E0', help_text="Hex color code")
    
    # Additional theme settings
    logo = models.ImageField(upload_to='themes/logos/', null=True, blank=True)
    favicon = models.ImageField(upload_to='themes/favicons/', null=True, blank=True)
    custom_css = models.TextField(blank=True, help_text="Custom CSS for theme")
    
    # Metadata
    is_default = models.BooleanField(default=False, help_text="Default theme for new events")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'themes'
        verbose_name = 'Theme'
        verbose_name_plural = 'Themes'
        ordering = ['name']
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        # Ensure only one default theme
        if self.is_default:
            Theme.objects.filter(is_default=True).update(is_default=False)
        super().save(*args, **kwargs)


class NotificationSound(models.Model):
    """
    Notification Sound model for custom event notification sounds.
    Admins can upload and assign custom sounds to different notification types.
    """
    name = models.CharField(max_length=100, help_text="Sound name (e.g., 'Success Chime', 'Error Buzz')")
    description = models.TextField(blank=True, help_text="Description of the sound")
    
    # Audio file
    audio_file = models.FileField(
        upload_to='notification-sounds/',
        help_text="Upload MP3, WAV, or OGG audio file"
    )
    
    # Sound type
    SOUND_TYPE_CHOICES = [
        ('challenge_correct', 'Challenge Correct (First Blood)'),
        ('instance_renewal', 'Instance Renewal'),
        ('instance_expiry', 'Instance Expiry'),
        ('flag_incorrect', 'Flag Incorrect'),
        ('hint_added', 'Hint Added'),
        ('user_banned', 'User Banned'),
        ('custom', 'Custom'),
    ]
    sound_type = models.CharField(
        max_length=50,
        choices=SOUND_TYPE_CHOICES,
        default='custom',
        help_text="Type of notification this sound is for"
    )
    
    # Metadata
    duration_seconds = models.PositiveIntegerField(
        null=True,
        blank=True,
        help_text="Duration of the audio in seconds"
    )
    is_default = models.BooleanField(
        default=False,
        help_text="Use as default sound for this type"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'notification_sounds'
        verbose_name = 'Notification Sound'
        verbose_name_plural = 'Notification Sounds'
        ordering = ['sound_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.get_sound_type_display()})"


class Event(models.Model):
    """
    Event model representing year-wise CTF events.
    Each event preserves all historical data (leaderboards, submissions, etc.)
    """
    # Event identification
    name = models.CharField(max_length=200, db_index=True)
    year = models.IntegerField(
        validators=[MinValueValidator(2000), MaxValueValidator(3000)],
        db_index=True,
        help_text="Year of the event"
    )
    slug = models.SlugField(max_length=200, unique=True, db_index=True)
    
    # Event description
    description = models.TextField(blank=True)
    banner = models.ImageField(upload_to='events/banners/', null=True, blank=True)
    
    # Event status
    is_active = models.BooleanField(default=False, help_text="Event is currently active")
    is_visible = models.BooleanField(default=False, help_text="Event is visible to participants")
    is_archived = models.BooleanField(default=False, help_text="Event is archived (historical data preserved)")
    
    # Contest State (for runtime control)
    CONTEST_STATE_CHOICES = [
        ('not_started', 'Not Started'),
        ('running', 'Running'),
        ('paused', 'Paused'),
        ('resumed', 'Resumed'),
        ('stopped', 'Stopped'),
    ]
    contest_state = models.CharField(
        max_length=20,
        choices=CONTEST_STATE_CHOICES,
        default='not_started',
        db_index=True,
        help_text="Current runtime state of the contest"
    )
    scoreboard_state = models.CharField(
        max_length=20,
        choices=[
            ('hidden', 'Hidden'),
            ('live', 'Live'),
            ('frozen', 'Frozen'),
            ('finalized', 'Finalized'),
        ],
        default='hidden',
        db_index=True,
        help_text="Scoreboard display state"
    )
    # Freeze controls (independent of scoreboard_state)
    is_scoreboard_frozen = models.BooleanField(
        default=False,
        help_text="When true, show frozen snapshot and block score updates"
    )
    scoreboard_frozen_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Exact timestamp when scoreboard was frozen"
    )
    state_changed_at = models.DateTimeField(null=True, blank=True, help_text="When the contest state was last changed")
    state_changed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='state_changed_events',
        help_text="Admin who last changed the contest state"
    )
    
    # Scheduling
    start_time = models.DateTimeField(null=True, blank=True, help_text="Event start time")
    end_time = models.DateTimeField(null=True, blank=True, help_text="Event end time")
    
    # Theming
    theme = models.ForeignKey(
        Theme,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events',
        help_text="Theme for this event"
    )
    
    # Scoring configuration
    scoring_type = models.CharField(
        max_length=20,
        choices=[
            ('static', 'Static Scoring'),
            ('dynamic', 'Dynamic Scoring'),
        ],
        default='dynamic',
        help_text="Scoring system type"
    )
    
    # Configuration
    max_team_size = models.PositiveIntegerField(default=5, help_text="Maximum team size")
    registration_open = models.BooleanField(default=False, help_text="Registration is open")
    
    # Instance Configuration
    max_instances_per_team = models.PositiveIntegerField(
        default=2,
        help_text="Maximum number of instances a team can run simultaneously across all challenges (global limit)"
    )
    instance_time_limit_minutes = models.PositiveIntegerField(
        default=60,
        help_text="Default time limit for instances in minutes"
    )
    instance_extension_minutes = models.PositiveIntegerField(
        default=20,
        help_text="Time extension amount in minutes when teams extend their instance"
    )
    instance_extension_penalty_points = models.PositiveIntegerField(
        default=0,
        help_text="Points penalty for extending instance (0 = no penalty)"
    )
    instance_max_extensions = models.PositiveIntegerField(
        default=2,
        help_text="Maximum number of extensions allowed per instance"
    )
    instance_low_time_threshold_minutes = models.PositiveIntegerField(
        default=20,
        help_text="Time threshold in minutes below which extension button becomes available"
    )
    
    # Notification Sound Settings
    enable_notification_sounds = models.BooleanField(
        default=True,
        help_text="Enable notification sounds for the event"
    )
    sound_on_challenge_correct = models.BooleanField(
        default=True,
        help_text="Play sound when challenge solved correctly (first blood)"
    )
    sound_on_instance_renewal = models.BooleanField(
        default=True,
        help_text="Play sound when instance is renewed"
    )
    sound_on_instance_expiry = models.BooleanField(
        default=True,
        help_text="Play sound when instance expires"
    )
    sound_on_flag_incorrect = models.BooleanField(
        default=False,
        help_text="Play sound when flag is incorrect"
    )
    sound_on_hint_added = models.BooleanField(
        default=True,
        help_text="Play sound when a new hint is added"
    )
    sound_on_user_banned = models.BooleanField(
        default=True,
        help_text="Play sound when a user is banned"
    )
    
    # Custom Notification Sounds (can be null to use defaults)
    custom_sound_challenge_correct = models.ForeignKey(
        NotificationSound,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events_challenge_correct',
        help_text="Custom sound for challenge correct"
    )
    custom_sound_instance_renewal = models.ForeignKey(
        NotificationSound,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events_instance_renewal',
        help_text="Custom sound for instance renewal"
    )
    custom_sound_instance_expiry = models.ForeignKey(
        NotificationSound,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events_instance_expiry',
        help_text="Custom sound for instance expiry"
    )
    custom_sound_flag_incorrect = models.ForeignKey(
        NotificationSound,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events_flag_incorrect',
        help_text="Custom sound for flag incorrect"
    )
    custom_sound_hint_added = models.ForeignKey(
        NotificationSound,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events_hint_added',
        help_text="Custom sound for hint added"
    )
    custom_sound_user_banned = models.ForeignKey(
        NotificationSound,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='events_user_banned',
        help_text="Custom sound for user banned"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_events'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'events'
        verbose_name = 'Event'
        verbose_name_plural = 'Events'
        unique_together = ['name', 'year']  # Ensure unique name per year
        ordering = ['-year', '-created_at']
        indexes = [
            models.Index(fields=['year', 'is_active']),
            models.Index(fields=['slug']),
            models.Index(fields=['contest_state']),
            models.Index(fields=['scoreboard_state']),
        ]
    
    def __str__(self):
        return f"{self.name} ({self.year})"
    
    def is_running(self):
        """Check if event is currently running (considering contest state)"""
        if not self.is_active:
            return False
        if self.contest_state not in ['running', 'resumed']:
            return False
        now = timezone.now()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
        return True
    
    def can_submit_flags(self):
        """Check if flag submission is allowed"""
        # Must be active AND in running/resumed state
        return self.is_active and self.contest_state in ['running', 'resumed']
    
    def can_create_instances(self):
        """Check if instances can be created"""
        # Must be active AND in running/resumed/paused state
        return self.is_active and self.contest_state in ['running', 'resumed', 'paused']
    
    def should_destroy_instances(self):
        """Check if instances should be destroyed"""
        # Destroy if stopped OR if event is inactive
        return self.contest_state == 'stopped' or not self.is_active
    
    def get_scoreboard_state(self):
        """Get current scoreboard state based on contest state"""
        if self.scoreboard_state == 'finalized':
            return 'finalized'  # Once finalized, never change
        
        state_map = {
            'not_started': 'hidden',
            'running': 'live',
            'paused': 'frozen',
            'resumed': 'live',
            'stopped': 'finalized',
        }
        return state_map.get(self.contest_state, 'hidden')
    
    def get_duration(self):
        """Get event duration in hours"""
        if self.start_time and self.end_time:
            delta = self.end_time - self.start_time
            return delta.total_seconds() / 3600
        return None
    
    def activate(self):
        """Activate the event"""
        self.is_active = True
        self.is_visible = True
        self.save()
    
    def deactivate(self):
        """Deactivate the event"""
        self.is_active = False
        self.save()
    
    def auto_stop_if_expired(self):
        """
        Automatically stop the event if scheduled end time has passed.
        Sets is_active=False and contest_state='stopped'
        Does NOT change scoreboard_state - preserves current scoreboard state
        Returns True if event was stopped, False otherwise
        """
        now = timezone.now()
        
        # Check if event has an end time and it has passed
        if not self.end_time:
            return False
        
        if now > self.end_time and self.is_active and self.contest_state != 'stopped':
            # Auto-stop the event - DO NOT change scoreboard_state
            self.is_active = False
            self.contest_state = 'stopped'
            self.state_changed_at = now
            # scoreboard_state is NOT modified - keeps current state (live/frozen/hidden)
            self.save()
            
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"[AUTO-STOP] Event '{self.name}' automatically stopped (end_time passed). Scoreboard state preserved: {self.scoreboard_state}")
            
            return True
        
        return False
    
    def archive(self):
        """Archive the event (preserve all data)"""
        self.is_active = False
        self.is_archived = True
        self.save()


class AdminAuditLog(models.Model):
    """
    Audit log for tracking all administrative actions.
    """
    ACTION_TYPE_CHOICES = [
        ('event_start', 'Event Started'),
        ('event_pause', 'Event Paused'),
        ('event_resume', 'Event Resumed'),
        ('event_stop', 'Event Stopped'),
        ('team_ban', 'Team Banned'),
        ('team_unban', 'Team Unbanned'),
        ('user_ban', 'User Banned'),
        ('user_unban', 'User Unbanned'),
        ('violation_resolve', 'Violation Resolved'),
        ('challenge_create', 'Challenge Created'),
        ('challenge_update', 'Challenge Updated'),
        ('challenge_delete', 'Challenge Deleted'),
        ('instance_manual_stop', 'Instance Manually Stopped'),
        ('scoreboard_freeze', 'Scoreboard Frozen'),
        ('scoreboard_finalize', 'Scoreboard Finalized'),
        ('other', 'Other'),
    ]
    
    # Event this action relates to
    event = models.ForeignKey(
        'events_ctf.Event',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='audit_logs',
        help_text="Event this action relates to"
    )
    
    # Action details
    action_type = models.CharField(max_length=50, choices=ACTION_TYPE_CHOICES)
    description = models.TextField(help_text="Description of the action")
    reason = models.TextField(blank=True, help_text="Reason for the action (optional)")
    
    # Admin who performed the action
    performed_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
        help_text="Admin who performed this action"
    )
    
    # Related object (generic foreign key for flexibility)
    content_type = models.ForeignKey(
        'contenttypes.ContentType',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        help_text="Type of related object"
    )
    object_id = models.PositiveIntegerField(null=True, blank=True, help_text="ID of related object")
    related_object = GenericForeignKey('content_type', 'object_id')
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP address of admin")
    user_agent = models.CharField(max_length=500, blank=True, help_text="User agent of admin")
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Additional data (JSON field for flexibility)
    metadata = models.JSONField(default=dict, blank=True, help_text="Additional action metadata")
    
    class Meta:
        db_table = 'admin_audit_logs'
        verbose_name = 'Admin Audit Log'
        verbose_name_plural = 'Admin Audit Logs'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['event', 'timestamp']),
            models.Index(fields=['action_type', 'timestamp']),
            models.Index(fields=['performed_by', 'timestamp']),
            models.Index(fields=['timestamp']),
        ]
    
    def __str__(self):
        event_name = self.event.name if self.event else "No Event"
        admin_name = self.performed_by.username if self.performed_by else "System"
        return f"{admin_name} - {self.get_action_type_display()} - {event_name} ({self.timestamp})"


class ScoreboardSnapshot(models.Model):
    """
    Snapshot of scoreboard at freeze time.
    Stores ranked teams and graph data for the event.
    """
    event = models.ForeignKey(
        Event,
        on_delete=models.CASCADE,
        related_name='scoreboard_snapshots'
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    freeze_time = models.DateTimeField(help_text="Timestamp when snapshot was captured")
    snapshot = models.JSONField(default=dict, help_text="Frozen scoreboard data (teams + graph)")

    class Meta:
        db_table = 'scoreboard_snapshots'
        verbose_name = 'Scoreboard Snapshot'
        verbose_name_plural = 'Scoreboard Snapshots'
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['event', 'created_at']),
        ]

    def __str__(self):
        return f"Snapshot for {self.event.name} at {self.freeze_time}"
