"""
Serializers for challenge instances.
"""
from rest_framework import serializers
from .models import ChallengeInstance


class ChallengeInstanceSerializer(serializers.ModelSerializer):
    """Serializer for ChallengeInstance model"""
    challenge_name = serializers.CharField(source='challenge.name', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    started_by_username = serializers.CharField(source='started_by.username', read_only=True)
    is_expired = serializers.SerializerMethodField()
    is_active_status = serializers.SerializerMethodField()
    formatted_access_url = serializers.SerializerMethodField()
    instance_url_type = serializers.CharField(source='challenge.instance_url_type', read_only=True)
    
    class Meta:
        model = ChallengeInstance
        fields = [
            'id', 'instance_id', 'challenge', 'challenge_name',
            'team', 'team_name', 'event', 'started_by', 'started_by_username',
            'container_id', 'container_ip', 'flag', 'access_url', 'access_port',
            'status', 'error_message', 'started_at', 'stopped_at',
            'expires_at', 'is_expired', 'is_active_status', 'config_snapshot',
            'formatted_access_url', 'instance_url_type'
        ]
        read_only_fields = [
            'id', 'instance_id', 'container_id', 'container_ip', 'flag',
            'started_at', 'stopped_at', 'expires_at', 'config_snapshot'
        ]
    
    def get_is_expired(self, obj):
        return obj.is_expired()
    
    def get_is_active_status(self, obj):
        return obj.is_active()
    
    def get_formatted_access_url(self, obj):
        """Format access URL based on challenge's instance_url_type"""
        if not obj.access_url or not obj.container_ip or not obj.access_port:
            return None
        
        url_type = obj.challenge.instance_url_type
        
        if url_type == 'netcat':
            return f"nc {obj.container_ip} {obj.access_port}"
        else:  # web_url (default)
            return f"http://{obj.container_ip}:{obj.access_port}"


class ChallengeInstanceListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for instance listing"""
    challenge_name = serializers.CharField(source='challenge.name', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    formatted_access_url = serializers.SerializerMethodField()
    instance_url_type = serializers.CharField(source='challenge.instance_url_type', read_only=True)
    
    class Meta:
        model = ChallengeInstance
        fields = [
            'id', 'instance_id', 'challenge', 'challenge_name',
            'team', 'team_name', 'status', 'access_url', 'access_port', 'container_ip',
            'started_at', 'expires_at', 'formatted_access_url', 'instance_url_type'
        ]
    
    def get_formatted_access_url(self, obj):
        """Format access URL based on challenge's instance_url_type"""
        if not obj.access_url or not obj.container_ip or not obj.access_port:
            return None
        
        url_type = obj.challenge.instance_url_type
        
        if url_type == 'netcat':
            return f"nc {obj.container_ip} {obj.access_port}"
        else:  # web_url (default)
            return f"http://{obj.container_ip}:{obj.access_port}"

