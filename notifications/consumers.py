"""
WebSocket consumer for real-time notifications.
"""
import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from channels.db import database_sync_to_async
from django.contrib.auth import get_user_model

User = get_user_model()
logger = logging.getLogger(__name__)


class NotificationConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for real-time notifications.
    Users connect to receive notifications for themselves, their teams, and system-wide notifications.
    """
    
    async def connect(self):
        """
        Called when WebSocket connection is established.
        """
        self.user = self.scope["user"]
        
        # Reject connection if user is not authenticated
        if self.user.is_anonymous:
            await self.close()
            return
        
        # Group names for this user
        self.user_group = f"user_{self.user.id}"
        self.system_group = "notifications_system"
        
        # Add user to their personal notification group
        await self.channel_layer.group_add(
            self.user_group,
            self.channel_name
        )
        
        # Add user to system-wide notifications group
        await self.channel_layer.group_add(
            self.system_group,
            self.channel_name
        )
        
        # Add user to their team notification groups
        teams = await self.get_user_teams()
        self.team_groups = []
        for team in teams:
            team_group = f"team_{team.id}"
            await self.channel_layer.group_add(
                team_group,
                self.channel_name
            )
            self.team_groups.append(team_group)
        
        await self.accept()
        logger.info(f"WebSocket connected for user {self.user.username}")
    
    async def disconnect(self, close_code):
        """
        Called when WebSocket connection is closed.
        """
        # Remove from user group
        await self.channel_layer.group_discard(
            self.user_group,
            self.channel_name
        )
        
        # Remove from system group
        await self.channel_layer.group_discard(
            self.system_group,
            self.channel_name
        )
        
        # Remove from team groups
        for team_group in self.team_groups:
            await self.channel_layer.group_discard(
                team_group,
                self.channel_name
            )
        
        logger.info(f"WebSocket disconnected for user {self.user.username}")
    
    async def receive(self, text_data):
        """
        Called when a message is received from WebSocket.
        Currently, we only send notifications from server to client.
        Client can send ping/pong messages for keepalive.
        """
        try:
            data = json.loads(text_data)
            message_type = data.get('type', '')
            
            if message_type == 'ping':
                # Respond to ping with pong
                await self.send(text_data=json.dumps({
                    'type': 'pong'
                }))
        except json.JSONDecodeError:
            logger.warning(f"Invalid JSON received from WebSocket: {text_data}")
    
    async def notification_update(self, event):
        """
        Handler for 'notification_update' event from channel layer.
        Sends notification to WebSocket client.
        """
        notification = event.get('notification', {})
        
        await self.send(text_data=json.dumps({
            'type': 'notification',
            'notification': notification
        }))
    
    async def notification_created(self, event):
        """
        Handler for 'notification_created' event from channel layer.
        Sends new notification to WebSocket client.
        """
        notification = event.get('notification', {})
        
        await self.send(text_data=json.dumps({
            'type': 'notification_created',
            'notification': notification
        }))
    
    async def notification_count_update(self, event):
        """
        Handler for notification count updates.
        Sends unread count to WebSocket client.
        """
        unread_count = event.get('unread_count', 0)
        
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'unread_count': unread_count
        }))
    
    async def event_state_change(self, event):
        """
        Handler for event state change notifications.
        Sends event state update to WebSocket client.
        """
        await self.send(text_data=json.dumps({
            'type': 'event_state_change',
            'event_id': event.get('event_id'),
            'event_name': event.get('event_name'),
            'contest_state': event.get('contest_state'),
            'scoreboard_state': event.get('scoreboard_state'),
            'action': event.get('action'),
        }))
    
    @database_sync_to_async
    def get_user_teams(self):
        """
        Get all teams that the user is a member of.
        """
        return list(self.user.teams.all())


class FirstBloodConsumer(AsyncWebsocketConsumer):
    """
    WebSocket consumer for First Blood events.
    Broadcasts when someone solves a challenge first in an event.
    """
    
    async def connect(self):
        # Join first-blood events group
        await self.channel_layer.group_add(
            'first_blood_events',
            self.channel_name
        )
        await self.accept()
    
    async def disconnect(self, close_code):
        await self.channel_layer.group_discard(
            'first_blood_events',
            self.channel_name
        )
    
    async def receive(self, text_data):
        """Handle incoming WebSocket messages"""
        try:
            data = json.loads(text_data)
            
            if data.get('type') == 'subscribe':
                # User subscribed to event-specific first blood events
                event_id = data.get('event_id')
                if event_id:
                    group_name = f'first_blood_events_event_{event_id}'
                    await self.channel_layer.group_add(
                        group_name,
                        self.channel_name
                    )
        except json.JSONDecodeError:
            pass
    
    async def first_blood_event(self, event):
        """
        Receive first blood event and broadcast to WebSocket
        """
        await self.send(text_data=json.dumps({
            'type': 'first_blood',
            'player_name': event['player_name'],
            'challenge_name': event['challenge_name'],
            'team_name': event['team_name'],
            'points': event['points'],
            'team_color': event.get('team_color', '#ff0000'),
            'timestamp': event['timestamp'],
        }))

