"""
Instance extension model and logic.
"""
from django.db import models
from django.utils import timezone
from datetime import timedelta


class InstanceExtension(models.Model):
    """
    Tracks instance time extensions.
    """
    instance = models.ForeignKey(
        'challenges.ChallengeInstance',
        on_delete=models.CASCADE,
        related_name='extensions'
    )
    extension_minutes = models.PositiveIntegerField(help_text="Minutes added to instance")
    penalty_points = models.PositiveIntegerField(default=0, help_text="Points penalty applied")
    extended_at = models.DateTimeField(auto_now_add=True)
    extended_by = models.ForeignKey(
        'accounts.User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='instance_extensions'
    )
    
    class Meta:
        db_table = 'instance_extensions'
        verbose_name = 'Instance Extension'
        verbose_name_plural = 'Instance Extensions'
        ordering = ['-extended_at']
    
    def __str__(self):
        return f"Extension for {self.instance.instance_id}: +{self.extension_minutes}min"

