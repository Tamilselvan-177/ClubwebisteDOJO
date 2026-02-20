"""
Notification service for creating and sending notifications.
"""
import logging
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from .models import Notification
from .serializers import NotificationSerializer

logger = logging.getLogger(__name__)
channel_layer = get_channel_layer()


class NotificationService:
    """
    Service for creating and managing notifications.
    """
    
    def create_notification(self, title, message, notification_type='system', priority='normal',
                          user=None, team=None, is_system_wide=False, event=None, challenge=None,
                          submission=None, violation=None, action_url='', action_text='',
                          expires_at=None, created_by=None):
        """
        Create a notification and send WebSocket updates.
        Returns created Notification object.
        """
        notification = Notification.objects.create(
            user=user,
            team=team,
            is_system_wide=is_system_wide,
            title=title,
            message=message,
            notification_type=notification_type,
            priority=priority,
            event=event,
            challenge=challenge,
            submission=submission,
            violation=violation,
            action_url=action_url,
            action_text=action_text,
            expires_at=expires_at,
            created_by=created_by
        )
        
        logger.info(f"Notification created: {title} (type: {notification_type})")
        
        # Send WebSocket notification
        self._send_websocket_notification(notification, user, team, is_system_wide)
        
        return notification
    
    def mark_sound_played(self, notification):
        """
        Mark a notification's sound as played (prevents replay on reload).
        """
        if notification and not notification.sound_played:
            notification.sound_played = True
            notification.save(update_fields=['sound_played'])
            logger.info(f"Marked notification {notification.id} sound as played")
        return notification
    
    def _send_websocket_notification(self, notification, user, team, is_system_wide):
        """
        Send WebSocket notification to relevant users.
        """
        if not channel_layer:
            return
        
        try:
            notification_data = NotificationSerializer(notification).data
            
            # Send to specific user
            if user:
                async_to_sync(channel_layer.group_send)(
                    f"user_{user.id}",
                    {
                        "type": "notification_created",
                        "notification": notification_data
                    }
                )
            
            # Send to team members
            if team:
                async_to_sync(channel_layer.group_send)(
                    f"team_{team.id}",
                    {
                        "type": "notification_created",
                        "notification": notification_data
                    }
                )
            
            # Send to all users (system-wide)
            if is_system_wide:
                async_to_sync(channel_layer.group_send)(
                    "notifications_system",
                    {
                        "type": "notification_created",
                        "notification": notification_data
                    }
                )
        except Exception as e:
            logger.warning(f"Failed to send WebSocket notification: {e}")
    
    def notify_violation_detected(self, violation):
        """
        Create notification for violation detection.
        Notifies admins and the team.
        """
        # Notify team
        self.create_notification(
            title="Violation Detected",
            message=f"Your team has been flagged for a violation: {violation.violation_type}",
            notification_type='violation',
            priority='high',
            team=violation.team,
            event=violation.event,
            violation=violation,
            action_url=f"/violations/{violation.id}/"
        )
        
        # Notify admins (system-wide notification for admins)
        # In a real implementation, you'd filter for admin users
        self.create_notification(
            title=f"Violation: {violation.team.name}",
            message=f"Team {violation.team.name} detected for {violation.violation_type}",
            notification_type='violation',
            priority='urgent',
            is_system_wide=True,
            event=violation.event,
            violation=violation,
            action_url=f"/admin/violations/{violation.id}/"
        )
    
    def notify_team_banned(self, team, reason, event=None):
        """
        Create notification when team is banned.
        Uses user_banned notification type to trigger ban sound.
        If no event is provided, uses the current active event.
        """
        # Get active event if not provided
        if not event:
            from events_ctf.models import Event
            event = Event.objects.filter(is_active=True).first()
        
        self.create_notification(
            title="Team Banned",
            message=f"Your team has been banned. Reason: {reason}",
            notification_type='user_banned',  # Use user_banned type to trigger ban sound
            priority='urgent',
            team=team,
            event=event,
            action_url="/support/"
        )
    
    def notify_user_banned(self, user, reason, event=None):
        """
        Create notification when user is banned.
        If no event is provided, uses the current active event.
        """
        # Get active event if not provided
        if not event:
            from events_ctf.models import Event
            event = Event.objects.filter(is_active=True).first()
        
        self.create_notification(
            title="User Banned",
            message=f"Your account has been banned. Reason: {reason}",
            notification_type='user_banned',
            priority='urgent',
            user=user,
            event=event,
            action_url="/support/"
        )
    
    def notify_submission_result(self, submission, is_correct, points_awarded=0, is_first_blood=False):
        """
        Create notification for submission result.
        """
        if is_correct:
            title = "Correct Flag!"
            message = f"Congratulations! You solved {submission.challenge.name}"
            if is_first_blood:
                message += " (First Blood!)"
            if points_awarded > 0:
                message += f" Points awarded: {points_awarded}"
            priority = 'high'
        else:
            title = "Incorrect Flag"
            message = f"Sorry, that flag was incorrect for {submission.challenge.name}"
            priority = 'normal'
        
        self.create_notification(
            title=title,
            message=message,
            notification_type='submission',
            priority=priority,
            user=submission.user,
            team=submission.team,
            event=submission.event,
            challenge=submission.challenge,
            submission=submission,
            action_url=f"/challenges/{submission.challenge.id}/"
        )
    
    def notify_event_announcement(self, event, title, message):
        """
        Create system-wide event announcement.
        """
        self.create_notification(
            title=title,
            message=message,
            notification_type='event',
            priority='normal',
            is_system_wide=True,
            event=event,
            action_url=f"/events/{event.slug}/"
        )
    
    def notify_challenge_released(self, challenge):
        """
        Notify users when a challenge is released.
        """
        self.create_notification(
            title="New Challenge Available",
            message=f"A new challenge has been released: {challenge.name}",
            notification_type='challenge',
            priority='normal',
            is_system_wide=True,
            event=challenge.event,
            challenge=challenge,
            action_url=f"/challenges/{challenge.id}/"
        )
    
    def mark_as_read(self, notification):
        """Mark notification as read"""
        notification.mark_as_read()
        return notification
    
    def mark_as_unread(self, notification):
        """Mark notification as unread"""
        notification.mark_as_unread()
        return notification
    
    def get_unread_count(self, user):
        """
        Get count of unread notifications for a user.
        Includes system-wide, user-specific, and team notifications.
        """
        # System-wide unread
        system_wide = Notification.objects.filter(
            is_system_wide=True,
            is_read=False,
            expires_at__isnull=True
        ) | Notification.objects.filter(
            is_system_wide=True,
            is_read=False,
            expires_at__gt=timezone.now()
        )
        
        # User-specific unread
        user_notifications = Notification.objects.filter(
            user=user,
            is_read=False,
            expires_at__isnull=True
        ) | Notification.objects.filter(
            user=user,
            is_read=False,
            expires_at__gt=timezone.now()
        )
        
        # Team notifications
        user_teams = user.teams.all()
        team_notifications = Notification.objects.filter(
            team__in=user_teams,
            is_read=False,
            expires_at__isnull=True
        ) | Notification.objects.filter(
            team__in=user_teams,
            is_read=False,
            expires_at__gt=timezone.now()
        )
        
        # Combine and count unique notifications
        all_notifications = (system_wide | user_notifications | team_notifications).distinct()
        return all_notifications.count()
    
    def notify_challenge_release(self, challenge, teams=None):
        """
        Create notification for when a challenge is released.
        Sends to specified teams or all teams in the event.
        """
        if teams is None:
            # Get all teams participating in the event
            teams = challenge.event.teams.all()
        
        # Build extra data with challenge details
        extra_data = {
            'difficulty': challenge.get_difficulty_display() if hasattr(challenge, 'get_difficulty_display') else challenge.difficulty,
            'points': challenge.get_current_points(),
            'category': challenge.category.name if challenge.category else 'General',
        }
        
        # Create notification for each team
        for team in teams:
            notification = Notification.objects.create(
                team=team,
                title=f"🆕 New Challenge: {challenge.name}",
                message=f"A new challenge '{challenge.name}' has been released! Check it out now.",
                notification_type='challenge_release',
                priority='high',
                event=challenge.event,
                challenge=challenge,
                action_url=f"/dojo/challenges/{challenge.id}/",
                action_text="View Challenge",
                extra_data=extra_data
            )
            
            logger.info(f"Challenge release notification sent to team {team.name}: {challenge.name}")
            self._send_websocket_notification(notification, None, team, False)
        
        return True
    
    def notify_hint_release(self, hint, teams=None):
        """
        Create notification for when a hint is released.
        Sends to specified teams or all teams in the event.
        """
        challenge = hint.challenge
        
        if teams is None:
            # Get all teams participating in the event
            teams = challenge.event.teams.all()
        
        # Build extra data with hint details
        extra_data = {
            'challenge': challenge.name,
            'cost': hint.cost,
            'order': hint.order + 1,  # Display as 1-indexed
        }
        
        # Create notification for each team
        for team in teams:
            notification = Notification.objects.create(
                team=team,
                title=f"💡 New Hint: {challenge.name}",
                message=f"A new hint for '{challenge.name}' is available! {f'Cost: {hint.cost} points' if hint.cost > 0 else 'Free hint!'}",
                notification_type='hint',
                priority='normal',
                event=challenge.event,
                challenge=challenge,
                action_url=f"/dojo/challenges/{challenge.id}/",
                action_text="View Hint",
                extra_data=extra_data
            )
            
            logger.info(f"Hint release notification sent to team {team.name}: {challenge.name}")
            self._send_websocket_notification(notification, None, team, False)
        
        return True


# Singleton instance
notification_service = NotificationService()


