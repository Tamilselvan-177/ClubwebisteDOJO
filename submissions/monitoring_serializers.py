from rest_framework import serializers
from .models import Violation
from accounts.serializers import TeamSerializer
from challenges.serializers import ChallengeListSerializer


class ViolationDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for violations"""
    team = TeamSerializer(read_only=True)
    challenge = ChallengeListSerializer(read_only=True)
    resolved_by_username = serializers.CharField(source='resolved_by.username', read_only=True, allow_null=True)
    
    class Meta:
        model = Violation
        fields = [
            'id', 'team', 'event', 'challenge', 'submission', 'instance',
            'violation_type', 'severity', 'description', 'evidence',
            'action_taken', 'is_resolved', 'resolved_at', 'resolved_by',
            'resolved_by_username', 'detected_by', 'created_at'
        ]
        read_only_fields = ['id', 'created_at', 'resolved_at']


