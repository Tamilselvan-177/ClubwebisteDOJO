"""
Celery tasks for event management.
"""
import logging
from celery import shared_task
from django.utils import timezone
from .models import Event

logger = logging.getLogger(__name__)


@shared_task
def auto_stop_expired_events():
    """
    Periodically check and auto-stop events that have passed their end time.
    
    Runs every minute via Celery Beat.
    For each active event, if end_time has passed:
    - Sets is_active = False
    - Sets contest_state = 'stopped'
    - PRESERVES scoreboard_state (does NOT change to 'finalized')
    
    This ensures NO ONE can submit flags after event ends,
    but scoreboard stays in its current state (live/frozen/hidden).
    """
    try:
        # Find all active events that should be stopped
        now = timezone.now()
        active_events = Event.objects.filter(
            is_active=True,
            end_time__lte=now
        ).exclude(contest_state='stopped')
        
        stopped_count = 0
        for event in active_events:
            if event.auto_stop_if_expired():
                stopped_count += 1
                logger.info(f"✓ Auto-stopped event: {event.name}")
        
        if stopped_count > 0:
            logger.info(f"[AUTO-STOP] Stopped {stopped_count} expired event(s)")
        
        return {
            'status': 'success',
            'stopped_count': stopped_count,
            'timestamp': now.isoformat()
        }
        
    except Exception as e:
        logger.error(f"[ERROR] auto_stop_expired_events task failed: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'timestamp': timezone.now().isoformat()
        }
