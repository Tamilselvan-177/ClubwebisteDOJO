from rest_framework import serializers
from .models import Event, Theme


class ThemeSerializer(serializers.ModelSerializer):
    """Serializer for Theme model"""
    class Meta:
        model = Theme
        fields = [
            'id', 'name', 'description', 'primary_color', 'secondary_color',
            'background_color', 'text_color', 'logo', 'favicon', 'is_default',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']


class EventListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for event listing"""
    theme_name = serializers.CharField(source='theme.name', read_only=True)
    
    class Meta:
        model = Event
        fields = [
            'id', 'name', 'year', 'slug', 'is_active', 'is_visible',
            'is_archived', 'contest_state', 'scoreboard_state',
            'start_time', 'end_time', 'theme_name',
            'registration_open', 'created_at'
        ]


class EventSerializer(serializers.ModelSerializer):
    """Full serializer for Event model"""
    theme = ThemeSerializer(read_only=True)
    theme_id = serializers.PrimaryKeyRelatedField(
        queryset=Theme.objects.all(),
        source='theme',
        write_only=True,
        required=False,
        allow_null=True
    )
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    challenge_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Event
        fields = [
            'id', 'name', 'year', 'slug', 'description', 'banner',
            'is_active', 'is_visible', 'is_archived',
            'contest_state', 'scoreboard_state', 'state_changed_at', 'state_changed_by',
            'is_scoreboard_frozen', 'scoreboard_frozen_at',
            'start_time', 'end_time', 'theme', 'theme_id',
            'scoring_type', 'max_team_size', 'registration_open',
            'max_instances_per_team', 'instance_time_limit_minutes',
            'instance_extension_minutes', 'instance_extension_penalty_points',
            'instance_max_extensions', 'instance_low_time_threshold_minutes',
            'created_by', 'created_by_username', 'challenge_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'created_by', 'created_at', 'updated_at',
            'state_changed_at', 'state_changed_by'
        ]
    
    def get_challenge_count(self, obj):
        return obj.challenges.count()
    
    def validate(self, attrs):
        # Validate start_time and end_time
        start_time = attrs.get('start_time')
        end_time = attrs.get('end_time')
        
        if start_time and end_time and start_time >= end_time:
            raise serializers.ValidationError({
                'end_time': 'End time must be after start time.'
            })
        
        return attrs
    
    def create(self, validated_data):
        validated_data['created_by'] = self.context['request'].user
        return super().create(validated_data)

