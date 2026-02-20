from django.templatetags.static import static
from rest_framework import serializers

from events_ctf.models import NotificationSound

from .models import Notification


DEFAULT_BELL_SOUND_STATIC_PATH = 'notification-sounds/bell.mp3'


class NotificationSoundMixin:
    """Shared helpers for resolving notification sounds with sensible fallbacks."""

    # Maps notification_type -> Event.custom_sound_* field name
    sound_field_map = {
        'challenge': 'custom_sound_challenge_correct',
        'hint': 'custom_sound_hint_added',
        'renewal': 'custom_sound_instance_renewal',
        'expiry': 'custom_sound_instance_expiry',
        'flag_incorrect': 'custom_sound_flag_incorrect',
        'user_banned': 'custom_sound_user_banned',
    }

    # Maps notification_type -> NotificationSound.sound_type for default lookup
    sound_type_map = {
        'challenge': 'challenge_correct',
        'hint': 'hint_added',
        'renewal': 'instance_renewal',
        'expiry': 'instance_expiry',
        'flag_incorrect': 'flag_incorrect',
        'user_banned': 'user_banned',
    }

    def _default_bell(self):
        """Return default bell URL and no duration."""
        return static(DEFAULT_BELL_SOUND_STATIC_PATH), None

    def _default_sound_for_type(self, notification_type):
        """Return default sound configured for a type, else bell."""
        sound_type = self.sound_type_map.get(notification_type)
        if sound_type:
            default_sound = NotificationSound.objects.filter(
                sound_type=sound_type,
                is_default=True,
            ).first()
            if default_sound and getattr(default_sound, 'audio_file', None):
                return default_sound.audio_file.url, getattr(default_sound, 'duration_seconds', None)
        return self._default_bell()

    def _resolve_sound(self, obj):
        """Resolve sound URL/duration with fallbacks to default type or bell."""
        if not obj.event:
            return self._default_bell()

        field_name = self.sound_field_map.get(obj.notification_type)
        if field_name:
            try:
                sound = getattr(obj.event, field_name, None)
                if sound and getattr(sound, 'audio_file', None):
                    return sound.audio_file.url, getattr(sound, 'duration_seconds', None)
            except Exception:
                # Fall through to defaults if anything goes wrong
                pass

        return self._default_sound_for_type(obj.notification_type)


class NotificationSerializer(NotificationSoundMixin, serializers.ModelSerializer):
    """Serializer for Notification model"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True, allow_null=True)
    sound_url = serializers.SerializerMethodField()
    sound_duration = serializers.SerializerMethodField()
    
    def get_sound_url(self, obj):
        """Resolve sound URL with defaults when custom audio is missing."""
        url, _ = self._resolve_sound(obj)
        return url
    
    def get_sound_duration(self, obj):
        """Return duration if available, else None."""
        _, duration = self._resolve_sound(obj)
        return duration
    
    class Meta:
        model = Notification
        fields = [
            'id', 'user', 'team', 'is_system_wide', 'title', 'message',
            'notification_type', 'priority', 'event', 'challenge', 'submission',
            'violation', 'action_url', 'action_text', 'is_read', 'read_at',
            'sound_played', 'created_by', 'created_by_username', 'created_at', 'expires_at',
            'sound_url', 'sound_duration', 'extra_data'
        ]
        read_only_fields = ['id', 'read_at', 'created_at', 'sound_url', 'sound_duration', 'sound_played']


class NotificationCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating notifications (admin/system only)"""
    class Meta:
        model = Notification
        fields = [
            'user', 'team', 'is_system_wide', 'title', 'message',
            'notification_type', 'priority', 'event', 'challenge', 'submission',
            'violation', 'action_url', 'action_text', 'expires_at'
        ]


class NotificationListSerializer(NotificationSoundMixin, serializers.ModelSerializer):
    """Lightweight serializer for notification listing"""
    sound_url = serializers.SerializerMethodField()
    sound_duration = serializers.SerializerMethodField()
    
    def get_sound_url(self, obj):
        url, _ = self._resolve_sound(obj)
        return url
    
    def get_sound_duration(self, obj):
        _, duration = self._resolve_sound(obj)
        return duration
    
    class Meta:
        model = Notification
        fields = [
            'id', 'title', 'notification_type', 'priority', 'is_read',
            'created_at', 'expires_at', 'sound_url', 'sound_duration'
        ]


