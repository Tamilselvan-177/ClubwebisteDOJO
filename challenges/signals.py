"""
Signals for challenge models.
"""
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from .models import Challenge, Hint
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)

# Track old visibility/release values before challenge is saved
_challenge_old_state = {}

@receiver(pre_save, sender=Challenge)
def track_challenge_visibility_change(sender, instance, **kwargs):
    """
    Track the old is_visible and release_time values before they change.
    """
    if instance.pk:
        try:
            old_challenge = Challenge.objects.get(pk=instance.pk)
            _challenge_old_state[instance.pk] = {
                'is_visible': old_challenge.is_visible,
                'release_time': old_challenge.release_time,
            }
        except Challenge.DoesNotExist:
            _challenge_old_state[instance.pk] = None
    else:
        _challenge_old_state[instance.pk] = None


@receiver(post_save, sender=Challenge)
def validate_instance_config(sender, instance, **kwargs):
    """
    Validate instance configuration when challenge is saved.
    Also send notification when challenge becomes visible or gets scheduled.
    """
    from accounts.models import Team
    from notifications.models import Notification
    
    if instance.challenge_type == 'instance':
        config = instance.instance_config or {}
        if not config.get('image'):
            # Set default image if not provided
            instance.instance_config = {**config, 'image': 'ubuntu:latest'}
            instance.save(update_fields=['instance_config'])
    
    # Check if challenge visibility or release time changed
    old_state = _challenge_old_state.get(instance.pk)
    should_notify = False
    notification_title = ""
    notification_message = ""
    
    if old_state is None:
        # New challenge - check if created as visible
        if instance.is_visible:
            should_notify = True
            notification_title = f"🆕 Challenge Released: {instance.name}"
            notification_message = f"A new challenge '{instance.name}' ({instance.category.name}) has been released!"
    else:
        old_visible = old_state.get('is_visible', False)
        old_release_time = old_state.get('release_time')
        
        # Challenge became visible
        if not old_visible and instance.is_visible:
            should_notify = True
            notification_title = f"📢 Challenge Released: {instance.name}"
            notification_message = f"The challenge '{instance.name}' ({instance.category.name}) is now available!"
        
        # Release time was set (scheduled release)
        elif instance.release_time and (old_release_time is None or old_release_time != instance.release_time):
            should_notify = True
            notification_title = f"⏰ Challenge Scheduled: {instance.name}"
            notification_message = f"Challenge '{instance.name}' will be released at {instance.release_time.strftime('%Y-%m-%d %H:%M:%S')}"
        
        # Clean up old tracking
        if instance.pk in _challenge_old_state:
            del _challenge_old_state[instance.pk]
    
    if not should_notify:
        return
    
    # Send notification to all active teams
    teams = Team.objects.filter(is_banned=False)
    for team in teams:
        try:
            notification = Notification.objects.create(
                team=team,
                challenge=instance,
                event=instance.event,
                title=notification_title,
                message=notification_message,
                notification_type='challenge_release',
                priority='high',
                action_url=f'/challenges/{instance.id}/',
                action_text='View Challenge',
            )
            logger.info(f"Challenge release notification created for team {team.name}: {instance.name}")
        except Exception as e:
            logger.error(f"Error creating challenge notification for team {team.id}: {e}")


# Track old visibility value before hint is saved
_hint_old_visible = {}

@receiver(pre_save, sender=Hint)
def track_hint_visibility_change(sender, instance, **kwargs):
    """
    Track the old is_visible value before it's changed.
    """
    if instance.pk:
        try:
            old_hint = Hint.objects.get(pk=instance.pk)
            _hint_old_visible[instance.pk] = old_hint.is_visible
        except Hint.DoesNotExist:
            _hint_old_visible[instance.pk] = None
    else:
        _hint_old_visible[instance.pk] = False


@receiver(post_save, sender=Hint)
def notify_hint_added(sender, instance, created, **kwargs):
    """
    Send notification to all teams when a new hint is added or made visible.
    Triggers on:
    - Creation of a new visible hint
    - Changing is_visible from False to True (via admin or ORM)
    """
    from accounts.models import Team
    from notifications.models import Notification
    import logging
    
    logger = logging.getLogger(__name__)
    challenge = instance.challenge
    teams = Team.objects.filter(is_banned=False)
    
    # Check if we should send notification
    should_notify = False
    action = "New Hint Added"
    message = f"A new hint has been added to the challenge '{challenge.name}'"
    
    if created and instance.is_visible:
        # Case 1: NEW hint created as visible
        should_notify = True
        action = "New Hint Added"
        message = f"A new hint has been added to the challenge '{challenge.name}'"
        
    elif not created and instance.is_visible:
        # Case 2: Existing hint is now visible
        # Check if visibility was changed from False to True
        old_visible = _hint_old_visible.get(instance.pk, False)
        
        if not old_visible:  # Was invisible, now visible
            should_notify = True
            action = "Hint Now Visible"
            message = f"A hint is now visible for the challenge '{challenge.name}'"
        
        # Clean up old tracking
        if instance.pk in _hint_old_visible:
            del _hint_old_visible[instance.pk]
    
    if not should_notify:
        return
    
    # Create notification for each active team
    for team in teams:
        try:
            notification = Notification.objects.create(
                team=team,
                challenge=challenge,
                event=challenge.event,  # Include event for sound lookup
                title=f"{action}: {challenge.name}",
                message=message,
                notification_type='hint',  # Use 'hint' type for hint notifications
                priority='normal',
            )
            logger.info(f"Hint notification ({action}) created for team {team.name}: {challenge.name}")
            
        except Exception as e:
            logger.error(f"Error creating hint notification for team {team.id}: {e}")




