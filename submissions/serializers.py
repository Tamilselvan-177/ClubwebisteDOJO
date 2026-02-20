from rest_framework import serializers
from .models import Submission, Score, Violation


class SubmissionSerializer(serializers.ModelSerializer):
    """Serializer for Submission model"""
    challenge_name = serializers.CharField(source='challenge.name', read_only=True)
    team_name = serializers.CharField(source='team.name', read_only=True)
    user_username = serializers.CharField(source='user.username', read_only=True)
    is_first_blood = serializers.SerializerMethodField()
    
    class Meta:
        model = Submission
        fields = [
            'id', 'challenge', 'challenge_name', 'event', 'team', 'team_name',
            'user', 'user_username', 'instance', 'flag', 'status',
            'points_awarded', 'points_at_submission', 'is_first_blood',
            'ip_address', 'submitted_at', 'admin_notes'
        ]
        read_only_fields = [
            'id', 'points_awarded', 'points_at_submission', 'submitted_at'
        ]
    
    def get_is_first_blood(self, obj):
        return obj.is_first_blood()


class SubmissionCreateSerializer(serializers.Serializer):
    """Serializer for creating a submission"""
    challenge_id = serializers.IntegerField(required=True)
    event_id = serializers.IntegerField(required=True)
    flag = serializers.CharField(max_length=500, required=True, trim_whitespace=True)
    instance_id = serializers.CharField(
        max_length=100,
        required=False,
        allow_null=True,
        help_text="Instance ID for instance-based challenges"
    )


class SubmissionListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for submission listing"""
    challenge_name = serializers.CharField(source='challenge.name', read_only=True)
    
    class Meta:
        model = Submission
        fields = [
            'id', 'challenge', 'challenge_name', 'status', 'points_awarded',
            'submitted_at'
        ]


class ScoreSerializer(serializers.ModelSerializer):
    """Serializer for Score model"""
    team_name = serializers.CharField(source='team.name', read_only=True)
    challenge_name = serializers.CharField(source='challenge.name', read_only=True)
    
    class Meta:
        model = Score
        fields = [
            'id', 'team', 'team_name', 'challenge', 'challenge_name',
            'event', 'points', 'score_type', 'total_score', 'reason',
            'notes', 'created_by', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ViolationSerializer(serializers.ModelSerializer):
    """Serializer for Violation model"""
    team_name = serializers.CharField(source='team.name', read_only=True)
    challenge_name = serializers.CharField(
        source='challenge.name',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        model = Violation
        fields = [
            'id', 'team', 'team_name', 'event', 'challenge', 'challenge_name',
            'violation_type', 'severity', 'description', 'evidence',
            'action_taken', 'is_resolved', 'resolved_at', 'resolved_by',
            'detected_by', 'created_at'
        ]
        read_only_fields = [
            'id', 'created_at', 'resolved_at'
        ]

