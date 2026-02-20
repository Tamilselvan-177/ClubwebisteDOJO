"""
Views for notification management.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import models
from .models import Notification
from .serializers import (
    NotificationSerializer,
    NotificationCreateSerializer,
    NotificationListSerializer
)
from .services import notification_service

# Import channels for WebSocket
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

channel_layer = get_channel_layer()


class NotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for notification management.
    """
    queryset = Notification.objects.all()
    serializer_class = NotificationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return NotificationCreateSerializer
        elif self.action == 'list':
            return NotificationListSerializer
        return NotificationSerializer
    
    def get_queryset(self):
        """
        Users see their own notifications, team notifications, and system-wide notifications.
        Excludes notifications the user has dismissed.
        """
        user = self.request.user
        queryset = super().get_queryset()
        
        if user.is_staff and self.action == 'list':
            # Admins can see all notifications
            pass
        else:
            # Filter for user's notifications
            user_notifications = queryset.filter(user=user)
            team_notifications = queryset.filter(team__in=user.teams.all())
            system_wide = queryset.filter(is_system_wide=True)
            queryset = (user_notifications | team_notifications | system_wide).distinct()
        
        # Filter out expired notifications
        queryset = queryset.filter(
            models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=timezone.now())
        )
        
        # Exclude notifications dismissed by this user
        queryset = queryset.exclude(dismissed_by_users=user)
        
        # Filter by read status
        is_read = self.request.query_params.get('is_read', None)
        if is_read is not None:
            queryset = queryset.filter(is_read=is_read.lower() == 'true')
        
        # Filter by notification type
        notification_type = self.request.query_params.get('type', None)
        if notification_type:
            queryset = queryset.filter(notification_type=notification_type)
        
        # Filter by priority
        priority = self.request.query_params.get('priority', None)
        if priority:
            queryset = queryset.filter(priority=priority)
        
        # Filter by event
        event_id = self.request.query_params.get('event', None)
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        
        return queryset.order_by('-created_at')
    
    def get_permissions(self):
        """
        Admin can create, users can view/manage their own.
        """
        if self.action == 'create':
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Set created_by when creating notification"""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['post'])
    def mark_read(self, request, pk=None):
        """
        Mark notification as read AND dismiss it for the user.
        POST /api/notifications/{id}/mark_read/
        """
        notification = self.get_object()
        
        # Check permissions
        if not self._can_access_notification(request.user, notification):
            return Response(
                {'error': 'You do not have permission to access this notification'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Only mark as read if this notification is scoped to the current user
        if notification.user == request.user:
            notification_service.mark_as_read(notification)
            # Also add to dismissed so it won't reappear on next fetch
            notification.dismissed_by_users.add(request.user)
            # Send WebSocket notification
            self._send_websocket_update(request.user, notification)
        else:
            # For team/system notifications, just dismiss for this user (don't mark read globally)
            notification.dismissed_by_users.add(request.user)
        
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def mark_unread(self, request, pk=None):
        """
        Mark notification as unread.
        POST /api/notifications/{id}/mark_unread/
        """
        notification = self.get_object()
        
        if not self._can_access_notification(request.user, notification):
            return Response(
                {'error': 'You do not have permission to access this notification'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        notification_service.mark_as_unread(notification)
        serializer = self.get_serializer(notification)
        return Response(serializer.data)
    
    @action(detail=False, methods=['post'])
    def mark_all_read(self, request):
        """
        Mark all notifications as read for current user.
        POST /api/notifications/mark_all_read/
        """
        user = request.user
        now = timezone.now()
        # Only mark notifications that are scoped directly to this user
        qs = Notification.objects.filter(
            models.Q(user=user) &
            (models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now)) &
            models.Q(is_read=False)
        )
        count = qs.update(is_read=True, read_at=now)
        
        # Also mark these as dismissed so they don't reappear when fetching
        for notif in qs:
            notif.dismissed_by_users.add(user)
        
        return Response({'message': f'{count} notifications cleared', 'count': count})
    
    @action(detail=False, methods=['get'])
    def unread_count(self, request):
        """
        Get count of unread notifications.
        GET /api/notifications/unread_count/
        """
        count = notification_service.get_unread_count(request.user)
        return Response({'unread_count': count})
    
    @action(detail=False, methods=['get'])
    def popup_notifications(self, request):
        """
        Get unread popup notifications (challenge release, hint release, etc).
        These are one-time popups that should be shown on page load.
        GET /api/notifications/popup_notifications/
        Returns: list of unread notifications of type 'challenge_release' or 'hint'
        """
        user = request.user
        now = timezone.now()
        
        # Fetch unread release notifications for this user's teams
        user_teams = user.teams.filter(is_banned=False).values_list('id', flat=True)
        
        popup_types = ['challenge_release', 'hint']
        
        notifications = Notification.objects.filter(
            (models.Q(team_id__in=user_teams) | models.Q(is_system_wide=True)) &
            models.Q(notification_type__in=popup_types) &
            models.Q(is_read=False) &
            (models.Q(expires_at__isnull=True) | models.Q(expires_at__gt=now))
        ).exclude(
            dismissed_by_users=user
        ).select_related('challenge', 'team').order_by('-created_at')[:10]
        
        serializer = NotificationListSerializer(notifications, many=True)
        return Response({
            'count': len(notifications),
            'results': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def dismiss_popup(self, request, pk=None):
        """
        Mark a popup notification as dismissed and read.
        POST /api/notifications/{id}/dismiss_popup/
        """
        notification = self.get_object()
        
        if not self._can_access_notification(request.user, notification):
            return Response(
                {'error': 'You do not have permission to access this notification'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Mark as dismissed
        notification.dismissed_by_users.add(request.user)
        notification.is_read = True
        notification.read_at = timezone.now()
        notification.save(update_fields=['is_read', 'read_at'])
        
        return Response({'message': 'Notification dismissed'}, status=status.HTTP_200_OK)
    
    def _can_access_notification(self, user, notification):
        """Check if user can access this notification"""
        if user.is_staff:
            return True
        if notification.user == user:
            return True
        if notification.team and notification.team.is_member(user):
            return True
        if notification.is_system_wide:
            return True
        return False
    
    def _send_websocket_update(self, user, notification):
        """Send WebSocket update for notification"""
        if channel_layer:
            try:
                async_to_sync(channel_layer.group_send)(
                    f"user_{user.id}",
                    {
                        "type": "notification_update",
                        "notification": NotificationSerializer(notification).data
                    }
                )
            except Exception as e:
                # WebSocket not critical, log and continue
                import logging
                logger = logging.getLogger(__name__)
                logger.warning(f"Failed to send WebSocket notification: {e}")
