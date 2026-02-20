from rest_framework import serializers
from .models import Category, Challenge, ChallengeFile, Hint
from events_ctf.models import Event


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model"""
    challenge_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'description', 'icon', 'color', 'challenge_count'
        ]
    
    def get_challenge_count(self, obj):
        return obj.challenges.count()


class ChallengeFileSerializer(serializers.ModelSerializer):
    """Serializer for ChallengeFile model"""
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = ChallengeFile
        fields = [
            'id', 'name', 'file', 'file_url', 'description', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']
    
    def get_file_url(self, obj):
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class HintSerializer(serializers.ModelSerializer):
    """Serializer for Hint model"""
    class Meta:
        model = Hint
        fields = [
            'id', 'challenge', 'text', 'cost', 'is_visible', 'order', 'created_at'
        ]
        read_only_fields = ['id', 'created_at']


class ChallengeListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for challenge listing"""
    category_name = serializers.CharField(source='category.name', read_only=True)
    category_color = serializers.CharField(source='category.color', read_only=True)
    current_points = serializers.SerializerMethodField()
    
    class Meta:
        model = Challenge
        fields = [
            'id', 'name', 'category', 'category_name', 'category_color',
            'points', 'current_points', 'minimum_points', 'decay',
            'challenge_type', 'is_visible', 'is_active', 'solve_count',
            'release_time'
        ]
    
    def get_current_points(self, obj):
        return obj.get_current_points()


class ChallengeSerializer(serializers.ModelSerializer):
    """Full serializer for Challenge model"""
    category = CategorySerializer(read_only=True)
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=Category.objects.all(),
        source='category',
        write_only=True,
        required=False,
        allow_null=True
    )
    event_id = serializers.PrimaryKeyRelatedField(
    queryset=Event.objects.all(),
    source='event',
    write_only=True,
    required=True
)

    author_username = serializers.CharField(source='author.username', read_only=True)
    files = ChallengeFileSerializer(many=True, read_only=True)
    file_ids = serializers.PrimaryKeyRelatedField(
        queryset=ChallengeFile.objects.all(),
        many=True,
        source='files',
        write_only=True,
        required=False
    )
    hints = HintSerializer(many=True, read_only=True)
    current_points = serializers.SerializerMethodField()
    instance_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Challenge
        fields = [
            'id', 'name', 'description', 'category', 'category_id',
            'event', 'event_id', 'is_visible', 'is_active',
            'points', 'minimum_points', 'decay', 'current_points',
            'challenge_type', 'flag', 'flag_type',
            'instance_config', 'instance_flag_format', 'max_instances_per_team',
            'files', 'file_ids', 'hints',
            'release_time', 'author', 'author_username',
            'solve_count', 'instance_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'event', 'author', 'solve_count', 'created_at', 'updated_at'
        ]
    
    # def __init__(self, *args, **kwargs):
    #     super().__init__(*args, **kwargs)
    #     # Set event queryset dynamically to avoid circular import
    #     from events.models import Event
    #     self.fields['event_id'].queryset = Event.objects.all()
    
    def get_current_points(self, obj):
        return obj.get_current_points()
    
    def get_instance_count(self, obj):
        if obj.challenge_type == 'instance':
            return obj.instances.filter(status='running').count()
        return 0
    
    def validate_points(self, value):
        if value < 1:
            raise serializers.ValidationError("Points must be at least 1.")
        return value
    
    def validate_minimum_points(self, value):
        if value < 1:
            raise serializers.ValidationError("Minimum points must be at least 1.")
        return value
    
    def validate(self, attrs):
        # Validate points vs minimum_points
        points = attrs.get('points', self.instance.points if self.instance else None)
        minimum_points = attrs.get('minimum_points', self.instance.minimum_points if self.instance else None)
        
        if points and minimum_points and minimum_points > points:
            raise serializers.ValidationError({
                'minimum_points': 'Minimum points cannot be greater than initial points.'
            })
        
        # Validate flag for standard challenges
        challenge_type = attrs.get('challenge_type', self.instance.challenge_type if self.instance else None)
        flag = attrs.get('flag', None)
        
        if challenge_type == 'standard' and not flag and not self.instance:
            raise serializers.ValidationError({
                'flag': 'Flag is required for standard challenges.'
            })
        
        # Validate instance_config for instance-based challenges
        if challenge_type == 'instance':
            instance_config = attrs.get('instance_config', {})
            if not instance_config or not isinstance(instance_config, dict):
                raise serializers.ValidationError({
                    'instance_config': 'Instance configuration is required for instance-based challenges.'
                })
        
        return attrs
    
    def create(self, validated_data):
        validated_data['author'] = self.context['request'].user
        file_ids = validated_data.pop('files', [])
        challenge = super().create(validated_data)
        if file_ids:
            challenge.files.set(file_ids)
        return challenge
    
    def update(self, instance, validated_data):
        file_ids = validated_data.pop('files', None)
        challenge = super().update(instance, validated_data)
        if file_ids is not None:
            challenge.files.set(file_ids)
        return challenge


class ChallengeDetailSerializer(ChallengeSerializer):
    """Extended serializer for challenge detail view"""
    # Includes all fields from ChallengeSerializer
    # Can add additional computed fields if needed
    pass

