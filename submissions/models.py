from django.db import models
from django.core.validators import MinValueValidator
from django.utils import timezone


class Submission(models.Model):
    """
    Submission model for flag submissions.
    Tracks all submission attempts with timestamps and results.
    """
    SUBMISSION_STATUS = [
        ('correct', 'Correct'),
        ('incorrect', 'Incorrect'),
        ('duplicate', 'Duplicate'),
        ('invalid', 'Invalid'),
    ]
    
    # Relationships
    challenge = models.ForeignKey(
        'challenges.Challenge',
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    event = models.ForeignKey(
        'events_ctf.Event',
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    team = models.ForeignKey(
        'accounts.Team',
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    user = models.ForeignKey(
        'accounts.User',
        on_delete=models.CASCADE,
        related_name='submissions'
    )
    instance = models.ForeignKey(
        'challenges.ChallengeInstance',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='submissions',
        help_text="Instance this submission is for (if instance-based challenge)"
    )
    
    # Submission data
    flag = models.CharField(max_length=500, db_index=True, help_text="Submitted flag")
    flag_hash = models.CharField(
        max_length=128,
        db_index=True,
        blank=True,
        help_text="SHA256 hash of submitted flag for fast copy detection"
    )
    status = models.CharField(max_length=20, choices=SUBMISSION_STATUS, default='incorrect')
    
    # Scoring
    points_awarded = models.PositiveIntegerField(default=0, help_text="Points awarded for this submission")
    points_at_submission = models.PositiveIntegerField(default=0, help_text="Challenge points at time of submission")
    
    # Metadata
    ip_address = models.GenericIPAddressField(null=True, blank=True, help_text="IP address of submission")
    user_agent = models.CharField(max_length=500, blank=True, help_text="User agent of submission")
    submitted_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    # Notes
    admin_notes = models.TextField(blank=True, help_text="Admin notes about this submission")
    
    class Meta:
        db_table = 'submissions'
        verbose_name = 'Submission'
        verbose_name_plural = 'Submissions'
        indexes = [
            models.Index(fields=['team', 'challenge', 'status']),
            models.Index(fields=['event', 'submitted_at']),
            models.Index(fields=['flag']),
            models.Index(fields=['flag_hash']),
            models.Index(fields=['status', 'submitted_at']),
        ]
        ordering = ['-submitted_at']
    
    def __str__(self):
        return f"{self.team.name} - {self.challenge.name} ({self.status})"
    
    def is_correct(self):
        """Check if submission is correct"""
        return self.status == 'correct'
    
    def is_first_blood(self):
        """Check if this is the first correct submission for this challenge"""
        if not self.is_correct():
            return False
        first_correct = Submission.objects.filter(
            challenge=self.challenge,
            status='correct',
            submitted_at__lt=self.submitted_at
        ).first()
        return first_correct is None


class Score(models.Model):
    """
    Score model tracking team scores per challenge.
    Maintains full audit trail with point reductions.
    """
    SCORE_TYPE_CHOICES = [
        ('award', 'Points Awarded'),
        ('reduction', 'Points Reduced'),
        ('adjustment', 'Manual Adjustment'),
    ]
    
    # Relationships
    team = models.ForeignKey('accounts.Team', on_delete=models.CASCADE, related_name='scores')
    challenge = models.ForeignKey('challenges.Challenge', on_delete=models.CASCADE, related_name='scores')
    event = models.ForeignKey('events_ctf.Event', on_delete=models.CASCADE, related_name='scores')
    submission = models.ForeignKey(
        Submission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='score_entries',
        help_text="Submission that triggered this score entry"
    )
    
    # Score information
    points = models.IntegerField(help_text="Points change (positive for awards, negative for reductions)")
    score_type = models.CharField(max_length=20, choices=SCORE_TYPE_CHOICES, default='award')
    total_score = models.PositiveIntegerField(
        default=0,
        validators=[MinValueValidator(0)],
        help_text="Total score after this change (cannot be negative)"
    )
    
    # Metadata
    reason = models.CharField(max_length=200, blank=True, help_text="Reason for score change")
    notes = models.TextField(blank=True, help_text="Additional notes")
    created_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='score_entries',
        help_text="User who created this score entry (admin for manual adjustments)"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'scores'
        verbose_name = 'Score'
        verbose_name_plural = 'Scores'
        indexes = [
            models.Index(fields=['team', 'event']),
            models.Index(fields=['challenge', 'event']),
            models.Index(fields=['event', 'created_at']),
            models.Index(fields=['score_type']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.team.name} - {self.challenge.name}: {self.points:+d} ({self.score_type})"
    
    def save(self, *args, **kwargs):
        # Ensure total_score is never negative
        if self.total_score < 0:
            self.total_score = 0
        super().save(*args, **kwargs)


class Violation(models.Model):
    """
    Violation model for anti-cheat tracking.
    Records cheating attempts and violations.
    """
    VIOLATION_TYPE_CHOICES = [
        ('copied_flag', 'Copied Flag'),
        ('shared_flag', 'Shared Flag'),
        ('multiple_submissions', 'Multiple Submissions'),
        ('rate_limit', 'Rate Limit Exceeded'),
        ('instance_tampering', 'Instance Tampering'),
        ('other', 'Other'),
    ]
    
    SEVERITY_CHOICES = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    # Relationships
    team = models.ForeignKey('accounts.Team', on_delete=models.CASCADE, related_name='violations')
    event = models.ForeignKey('events_ctf.Event', on_delete=models.CASCADE, related_name='violations')
    challenge = models.ForeignKey(
        'challenges.Challenge',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='violations'
    )
    submission = models.ForeignKey(
        Submission,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='violations',
        help_text="Submission that triggered this violation"
    )
    instance = models.ForeignKey(
        'challenges.ChallengeInstance',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='violations',
        help_text="Instance involved in violation"
    )
    
    # Violation details
    violation_type = models.CharField(max_length=30, choices=VIOLATION_TYPE_CHOICES)
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='medium')
    description = models.TextField(help_text="Detailed description of the violation")
    evidence = models.JSONField(default=dict, blank=True, help_text="Evidence data (flags, IPs, etc.)")
    
    # Action taken
    action_taken = models.CharField(
        max_length=200,
        blank=True,
        help_text="Action taken (e.g., 'Team banned', 'Points reduced')"
    )
    is_resolved = models.BooleanField(default=False, help_text="Violation has been resolved")
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='resolved_violations'
    )
    
    # Metadata
    detected_by = models.CharField(
        max_length=50,
        default='system',
        help_text="Who detected the violation (system, admin username, etc.)"
    )
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        db_table = 'violations'
        verbose_name = 'Violation'
        verbose_name_plural = 'Violations'
        indexes = [
            models.Index(fields=['team', 'event']),
            models.Index(fields=['violation_type', 'severity']),
            models.Index(fields=['is_resolved', 'created_at']),
            models.Index(fields=['event', 'created_at']),
        ]
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.team.name} - {self.violation_type} ({self.severity})"
    
    def resolve(self, resolved_by_user=None, action_taken=""):
        """Mark violation as resolved"""
        self.is_resolved = True
        self.resolved_at = timezone.now()
        if resolved_by_user:
            self.resolved_by = resolved_by_user
        if action_taken:
            self.action_taken = action_taken
        self.save()
