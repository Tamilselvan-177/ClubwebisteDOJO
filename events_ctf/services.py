"""
Services for event control and state management.
"""
import logging
from django.utils import timezone
from django.db import transaction
from django.db.models import Sum
from django.contrib.contenttypes.models import ContentType
from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from .models import Event, AdminAuditLog
from challenges.models import ChallengeInstance
from challenges.services import instance_service
from notifications.services import notification_service
from submissions.models import Score, Submission
from accounts.models import Team
from .models import ScoreboardSnapshot

logger = logging.getLogger(__name__)


class EventControlService:
    """
    Service for managing event runtime states and controls.
    """
    
    @staticmethod
    @transaction.atomic
    def start_event(event, performed_by, request=None, reason=''):
        """
        Start an event.
        
        State: not_started -> running
        Effects:
        - Instances: Allowed
        - Flag Submission: Allowed
        - Scoreboard: Live
        """
        if event.contest_state != 'not_started':
            raise ValueError(f"Cannot start event in state: {event.contest_state}")
        
        event.contest_state = 'running'
        event.scoreboard_state = 'live'
        event.state_changed_at = timezone.now()
        event.state_changed_by = performed_by
        event.is_active = True
        event.is_visible = True
        event.save()
        
        # Log action
        EventControlService._log_admin_action(
            action_type='event_start',
            description=f"Event '{event.name}' started",
            performed_by=performed_by,
            event=event,
            reason=reason,
            request=request
        )
        
        # Send notification
        notification_service.notify_event_announcement(
            event=event,
            title="Event Started!",
            message=f"The event '{event.name}' has started. Good luck!"
        )
        
        # Send WebSocket update
        EventControlService._send_websocket_update(event, 'started')
        
        logger.info(f"Event {event.id} started by {performed_by.username}")
        return event
    
    @staticmethod
    def _log_admin_action(
        action_type,
        description,
        performed_by,
        event=None,
        related_object=None,
        reason='',
        request=None,
        metadata=None
    ):
        """
        Helper function to log an admin action.
        """
        # Get IP and user agent from request if available
        ip_address = None
        user_agent = ''
        if request:
            x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
            if x_forwarded_for:
                ip_address = x_forwarded_for.split(',')[0]
            else:
                ip_address = request.META.get('REMOTE_ADDR')
            user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        # Get content type if related object is provided
        content_type = None
        object_id = None
        if related_object:
            content_type = ContentType.objects.get_for_model(related_object)
            object_id = related_object.pk
        
        log_entry = AdminAuditLog.objects.create(
            event=event,
            action_type=action_type,
            description=description,
            reason=reason,
            performed_by=performed_by,
            content_type=content_type,
            object_id=object_id,
            ip_address=ip_address,
            user_agent=user_agent,
            metadata=metadata or {}
        )
        
        return log_entry
    
    @staticmethod
    @transaction.atomic
    def pause_event(event, performed_by, request=None, reason=''):
        """
        Pause an event.
        
        State: running/resumed -> paused
        Effects:
        - Instances: Allowed (remain running)
        - Flag Submission: BLOCKED
        - Scoreboard: Frozen
        """
        if event.contest_state not in ['running', 'resumed']:
            raise ValueError(f"Cannot pause event in state: {event.contest_state}")
        
        event.contest_state = 'paused'
        event.scoreboard_state = 'frozen'
        event.state_changed_at = timezone.now()
        event.state_changed_by = performed_by
        event.save()
        
        # Log action
        EventControlService._log_admin_action(
            action_type='event_pause',
            description=f"Event '{event.name}' paused",
            performed_by=performed_by,
            event=event,
            reason=reason,
            request=request
        )
        
        # Send notification
        notification_service.notify_event_announcement(
            event=event,
            title="Event Paused",
            message=f"The event '{event.name}' has been paused. Flag submissions are temporarily disabled."
        )
        
        # Send WebSocket update
        EventControlService._send_websocket_update(event, 'paused')
        
        logger.info(f"Event {event.id} paused by {performed_by.username}")
        return event
    
    @staticmethod
    @transaction.atomic
    def resume_event(event, performed_by, request=None, reason=''):
        """
        Resume a paused event.
        
        State: paused -> resumed
        Effects:
        - Instances: Allowed
        - Flag Submission: Allowed
        - Scoreboard: Live
        """
        if event.contest_state != 'paused':
            raise ValueError(f"Cannot resume event in state: {event.contest_state}")
        
        event.contest_state = 'resumed'
        event.scoreboard_state = 'live'
        event.state_changed_at = timezone.now()
        event.state_changed_by = performed_by
        event.save()
        
        # Log action
        EventControlService._log_admin_action(
            action_type='event_resume',
            description=f"Event '{event.name}' resumed",
            performed_by=performed_by,
            event=event,
            reason=reason,
            request=request
        )
        
        # Send notification
        notification_service.notify_event_announcement(
            event=event,
            title="Event Resumed",
            message=f"The event '{event.name}' has been resumed. Flag submissions are now enabled again."
        )
        
        # Send WebSocket update
        EventControlService._send_websocket_update(event, 'resumed')
        
        logger.info(f"Event {event.id} resumed by {performed_by.username}")
        return event
    
    @staticmethod
    @transaction.atomic
    def stop_event(event, performed_by, request=None, reason=''):
        """
        Stop an event (final).
        
        State: any -> stopped
        Effects:
        - Instances: All destroyed immediately
        - Flag Submission: BLOCKED permanently
        - Scoreboard: Finalized (permanently locked)
        """
        event.contest_state = 'stopped'
        event.scoreboard_state = 'finalized'
        event.state_changed_at = timezone.now()
        event.state_changed_by = performed_by
        event.is_active = False  # Deactivate event
        event.save()
        
        # Destroy all running instances for this event
        running_instances = ChallengeInstance.objects.filter(
            event=event,
            status='running'
        )
        
        instance_count = running_instances.count()
        destroyed_count = 0
        points_reduced_total = 0
        
        for instance in running_instances:
            try:
                success, error, points_reduced = instance_service.stop_instance(
                    instance,
                    reduce_points=True,
                    reason="Event stopped by admin"
                )
                if success:
                    destroyed_count += 1
                    points_reduced_total += points_reduced
            except Exception as e:
                logger.error(f"Failed to destroy instance {instance.id}: {e}")
        
        # Log action with metadata
        EventControlService._log_admin_action(
            action_type='event_stop',
            description=f"Event '{event.name}' stopped. {destroyed_count} instances destroyed. Total points reduced: {points_reduced_total}.",
            performed_by=performed_by,
            event=event,
            reason=reason,
            request=request,
            metadata={
                'instances_destroyed': destroyed_count,
                'total_instances': instance_count
            }
        )
        
        # Send notification
        notification_service.notify_event_announcement(
            event=event,
            title="Event Stopped",
            message=f"The event '{event.name}' has been stopped. All instances have been destroyed and the scoreboard is now finalized."
        )
        
        # Send WebSocket update
        EventControlService._send_websocket_update(event, 'stopped')
        
        logger.info(f"Event {event.id} stopped by {performed_by.username}. Destroyed {destroyed_count} instances.")
        return event, destroyed_count

    @staticmethod
    @transaction.atomic
    def freeze_scoreboard(event, performed_by, request=None, reason=''):
        """
        Freeze the scoreboard at the current time without changing scoreboard_state.
        Effects:
        - Sets is_scoreboard_frozen=True and records scoreboard_frozen_at
        - Captures a snapshot of rankings and graph data up to freeze time
        - Blocks further score updates while frozen (enforced in submission services)
        """
        now = timezone.now()

        # Set freeze flags (do not alter scoreboard_state)
        event.is_scoreboard_frozen = True
        event.scoreboard_frozen_at = now
        event.save(update_fields=['is_scoreboard_frozen', 'scoreboard_frozen_at'])

        # Build frozen rankings (exclude banned teams)
        team_ids = set(Score.objects.filter(
            event=event,
            team__is_banned=False
        ).values_list('team_id', flat=True))

        teams = []
        for team_id in team_ids:
            try:
                team = Team.objects.get(id=team_id, is_banned=False)
            except Team.DoesNotExist:
                continue

            latest_score = Score.objects.filter(
                team_id=team_id,
                event=event,
                created_at__lte=now
            ).order_by('-created_at').first()
            total_score = latest_score.total_score if latest_score else 0

            solved_count = Submission.objects.filter(
                team_id=team_id,
                event=event,
                status='correct',
                submitted_at__lte=now
            ).values('challenge').distinct().count()

            penalty_sum = Score.objects.filter(
                team_id=team_id,
                event=event,
                score_type='reduction',
                created_at__lte=now
            ).aggregate(total=Sum('points'))['total'] or 0
            penalty_points = -penalty_sum if penalty_sum < 0 else 0

            last_submission = Submission.objects.filter(
                team_id=team_id,
                event=event,
                status='correct',
                submitted_at__lte=now
            ).order_by('-submitted_at').first()

            teams.append({
                'team_name': team.name,
                'team_id': team.id,
                'total_score': total_score,
                'solved_count': solved_count,
                'penalty_points': penalty_points,
                'score_without_penalty': total_score + penalty_points,
                'last_solve_time': last_submission.submitted_at.isoformat() if last_submission else None,
            })

        # Sort by score then last solve time
        teams.sort(key=lambda x: (-x['total_score'], x['last_solve_time'] or now))
        for idx, entry in enumerate(teams, 1):
            entry['rank'] = idx

        # Graph data up to freeze time (top 20 teams)
        graph_data = []
        for entry in teams[:20]:
            tid = entry['team_id']
            submissions = Submission.objects.filter(
                team_id=tid,
                event=event,
                status='correct',
                submitted_at__lte=now
            ).select_related('challenge').order_by('submitted_at')

            solves = [{
                'time': s.submitted_at.isoformat(),
                'points': s.points_awarded,
                'challenge': s.challenge.name
            } for s in submissions]

            graph_data.append({
                'name': entry['team_name'],
                'solves': solves,
                'color': None
            })

        snapshot_payload = {
            'freeze_time': now.isoformat(),
            'teams': teams[:50],
            'teams_graph_data': graph_data,
        }

        ScoreboardSnapshot.objects.create(
            event=event,
            freeze_time=now,
            snapshot=snapshot_payload
        )

        # Log action
        EventControlService._log_admin_action(
            action_type='scoreboard_freeze',
            description=f"Scoreboard for '{event.name}' frozen",
            performed_by=performed_by,
            event=event,
            reason=reason,
            request=request,
            metadata={'freeze_time': now.isoformat()}
        )

        # Optional notification
        notification_service.notify_event_announcement(
            event=event,
            title="Scoreboard Frozen",
            message=f"The scoreboard has been frozen at {now.strftime('%Y-%m-%d %H:%M:%S UTC')}"
        )

        # WebSocket update for clients to switch to frozen view
        EventControlService._send_websocket_update(event, 'scoreboard_frozen')

        logger.info(f"Scoreboard frozen for event {event.id} by {performed_by.username}")
        return event
    
    @staticmethod
    def _send_websocket_update(event, action):
        """Send WebSocket update for event state change"""
        try:
            channel_layer = get_channel_layer()
            if not channel_layer:
                logger.debug("Channel layer not available, skipping WebSocket update")
                return
            
            # Send to system-wide group
            async_to_sync(channel_layer.group_send)(
                "notifications_system",
                {
                    "type": "event_state_change",
                    "event_id": event.id,
                    "event_name": event.name,
                    "contest_state": event.contest_state,
                    "scoreboard_state": event.scoreboard_state,
                    "action": action,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to send WebSocket update for event state change: {e}")


# Singleton instance
event_control_service = EventControlService()

