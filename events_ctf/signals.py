"""
Signals for events app.
"""
from django.db.models.signals import post_save
from django.dispatch import receiver
from .models import Event
import logging

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Event)
def auto_stop_event_on_save(sender, instance, created, **kwargs):
    """
    Signal handler to auto-stop event if end_time has passed.
    Triggered whenever an Event is saved.
    """
    if not created:  # Only on update, not on creation
        # Check if event should be auto-stopped
        if instance.auto_stop_if_expired():
            logger.info(f"[SIGNAL] Event '{instance.name}' auto-stopped on save")
