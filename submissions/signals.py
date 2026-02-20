"""
Signals for submissions app.
Handles first blood broadcasts when challenges are solved and score recalculation on deletion.
"""
import logging
from django.db.models.signals import post_save, post_delete
from django.db.models import Sum
from django.dispatch import receiver
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Submission, Score

logger = logging.getLogger(__name__)


@receiver(post_save, sender=Submission)
def submission_created(sender, instance, created, **kwargs):
    """
    Signal handler triggered when a submission is created.
    NOTE: First blood is now detected server-side and returned in API response.
    The animation is triggered client-side on the challenge detail page for the
    player who submitted the flag, NOT broadcast globally.
    """
    # This handler kept for potential future use
    pass


@receiver(post_delete, sender=Submission)
def submission_deleted(sender, instance, **kwargs):
    """
    Signal handler triggered when a submission is deleted (e.g., via admin).
    Defers score recalculation until after the deletion transaction completes.
    """
    from django.db import transaction
    
    def recalculate_score():
        try:
            team = instance.team
            event = instance.event
            
            # Sum all remaining score entries (award + adjustment types only, exclude reductions)
            remaining_scores = Score.objects.filter(
                team=team,
                event=event,
                score_type__in=['award', 'adjustment']
            ).aggregate(total=Sum('points'))['total'] or 0
            
            new_total = max(0, remaining_scores)
            
            # Create an adjustment entry to record the recalculation
            Score.objects.create(
                team=team,
                event=event,
                challenge=None,  # Bulk recalculation, not tied to a specific challenge
                submission=None,
                points=0,
                score_type='adjustment',
                total_score=new_total,
                reason='Score recalculated after submission deletion',
                notes=f'Removed submission {instance.id} ({instance.challenge.name}). Team score updated from submission admin deletion.'
            )
            
            logger.info(f"Team {team.name} score recalculated to {new_total} after submission deletion")
            
        except Exception as e:
            logger.error(f"Error recalculating score after submission deletion: {e}")
    
    # Defer score recalculation until after the deletion transaction completes
    transaction.on_commit(recalculate_score)


def broadcast_first_blood(submission):
    """
    Broadcast first blood event to all connected WebSocket clients
    """
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return
        
        event_data = {
            'type': 'first_blood_event',
            'player_name': submission.user.get_full_name() or submission.user.username,
            'challenge_name': submission.challenge.name,
            'team_name': submission.team.name,
            'points': submission.points_awarded,
            'team_color': getattr(submission.team, 'color', '#ff0000'),
            'timestamp': submission.submitted_at.isoformat(),
        }
        
        # Broadcast to event-specific group
        group_name = f'first_blood_events_event_{submission.event.id}'
        async_to_sync(channel_layer.group_send)(
            group_name,
            event_data
        )
        
        # Broadcast to global group
        async_to_sync(channel_layer.group_send)(
            'first_blood_events',
            event_data
        )
        
    except Exception as e:
        logger.error(f"Error broadcasting first blood: {e}")
