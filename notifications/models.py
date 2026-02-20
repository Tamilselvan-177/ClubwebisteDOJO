from django.db import models
from django.utils import timezone


class Notification(models.Model):
    """
    Notification model for real-time system notifications.
    Supports user, team, and system-wide notifications.
    """
    NOTIFICATION_TYPE_CHOICES = [
        ('system', 'System'),
        ('event', 'Event'),
        ('challenge', 'Challenge'),
        ('challenge_release', 'Challenge Release'),
        ('submission', 'Submission'),
        ('violation', 'Violation'),
        ('team', 'Team'),
        ('admin', 'Admin'),
        ('user_banned', 'User Banned'),
        ('hint', 'Hint Release'),
    ]
    
    PRIORITY_CHOICES = [
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    # Recipient (can be user, team, or system-wide)
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text="Specific user recipient (null for system-wide)"
    )
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications',
        help_text="Team recipient (null for individual user)"
    )
    is_system_wide = models.BooleanField(
        default=False,
        help_text="Notification visible to all users"
    )
    
    # Notification content
    title = models.CharField(max_length=200)
    message = models.TextField()
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPE_CHOICES, default='system')
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Related objects (optional)
    event = models.ForeignKey(
        'events_ctf.Event',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    challenge = models.ForeignKey(
        'challenges.Challenge',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    submission = models.ForeignKey(
        'submissions.Submission',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    violation = models.ForeignKey(
        'submissions.Violation',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='notifications'
    )
    
    # Action link (optional)
    action_url = models.URLField(blank=True, help_text="URL to navigate to when notification is clicked")
    action_text = models.CharField(max_length=100, blank=True, help_text="Text for action button")
    
    # Status
    is_read = models.BooleanField(default=False, db_index=True)
    read_at = models.DateTimeField(null=True, blank=True)
    sound_played = models.BooleanField(
        default=False,
        db_index=True,
        help_text="Whether notification sound has been played (prevents replay on reload)"
    )
    
    # Dismiss tracking (for users to hide notifications they cleared)
    dismissed_by_users = models.ManyToManyField(
        'accounts.User',
        blank=True,
        related_name='dismissed_notifications',
        help_text="Users who have dismissed/cleared this notification"
    )
    
    # Metadata
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_notifications',
        help_text="User/system that created this notification"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Notification expiration time")
    
    # Extra data for rich notifications (challenge details, hint details, etc.)
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        help_text="Additional data for rich notifications (difficulty, points, category, cost, etc.)"
    )
    
    class Meta:
        db_table = 'notifications'
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
        indexes = [
            models.Index(fields=['user', 'is_read', 'created_at']),
            models.Index(fields=['team', 'is_read', 'created_at']),
            models.Index(fields=['is_system_wide', 'is_read', 'created_at']),
            models.Index(fields=['notification_type', 'priority']),
            models.Index(fields=['event', 'created_at']),
            models.Index(fields=['expires_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        recipient = self.user.username if self.user else (self.team.name if self.team else "System-wide")
        return f"{self.title} - {recipient}"
    
    def mark_as_read(self):
        """Mark notification as read"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save()
    
    def mark_as_unread(self):
        """Mark notification as unread"""
        if self.is_read:
            self.is_read = False
            self.read_at = None
            self.save()
    
    def is_expired(self):
        """Check if notification has expired"""
        if self.expires_at:
            return timezone.now() > self.expires_at
        return False
