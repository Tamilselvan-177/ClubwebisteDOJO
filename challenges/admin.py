from django.contrib import admin
from django.utils.html import format_html
from django import forms
import subprocess
from .models import Category, Challenge, ChallengeFile, Hint, ChallengeInstance


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    """Admin interface for Category model"""
    list_display = ['name', 'icon', 'challenge_count', 'color_preview']
    search_fields = ['name', 'description']
    
    def challenge_count(self, obj):
        """Display number of challenges in category"""
        return obj.challenges.count()
    challenge_count.short_description = 'Challenges'
    
    def color_preview(self, obj):
        """Display color preview"""
        return format_html(
            '<div style="width: 30px; height: 20px; background-color: {}; border: 1px solid #ccc;"></div>',
            obj.color
        )
    color_preview.short_description = 'Color'


class HintInline(admin.TabularInline):
    """Inline admin for hints"""
    model = Hint
    extra = 1
    ordering = ['order']


def _list_docker_images():
    """Return list of docker images as strings 'repository:tag'."""
    images = []
    try:
        result = subprocess.run(
            ['docker', 'images', '--format', '{{.Repository}}:{{.Tag}}'],
            capture_output=True,
            timeout=10,
            text=True
        )
        if result.returncode == 0:
            for line in result.stdout.splitlines():
                line = line.strip()
                if line and line != '<none>:<none>':
                    images.append(line)
    except Exception:
        # If docker is not available, return empty list
        pass
    # Ensure some common images for convenience
    defaults = ['ubuntu:latest', 'python:3.11', 'nginx:latest']
    for img in defaults:
        if img not in images:
            images.append(img)
    return images


class ChallengeAdminForm(forms.ModelForm):
    """Admin form with Docker image dropdown helper for instance-based challenges."""

    docker_image = forms.ChoiceField(
        required=False,
        choices=[],
        label='Docker Image (from server)'
    )

    container_port = forms.IntegerField(
        required=False,
        label='Container port (inside image)',
        help_text='Backend will publish a random host port; this is the port your app listens on inside the container.'
    )

    class Meta:
        model = Challenge
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Populate docker image choices from server
        images = _list_docker_images()
        self.fields['docker_image'].choices = [(img, img) for img in images]

        # Pre-select from existing instance_config
        try:
            config = self.instance.instance_config or {}
            current_image = config.get('image')
            if current_image and current_image in images:
                self.fields['docker_image'].initial = current_image
            # Pull the first container port if present
            ports = config.get('ports') or {}
            if isinstance(ports, dict) and ports:
                first_port = next(iter(ports.keys()))
                try:
                    self.fields['container_port'].initial = int(first_port)
                except Exception:
                    pass
        except Exception:
            pass


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    """Admin interface for Challenge model"""
    form = ChallengeAdminForm
    list_display = ['name', 'event', 'category', 'difficulty', 'points', 'challenge_type', 'is_visible', 'is_active', 'solve_count', 'created_at']
    list_filter = ['challenge_type', 'is_visible', 'is_active', 'category', 'event', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'solve_count']
    autocomplete_fields = ['event', 'category', 'author']
    inlines = [HintInline]
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'description', 'event', 'category', 'author', 'difficulty')
        }),
        ('Status', {
            'fields': ('is_visible', 'is_active', 'release_time')
        }),
        ('Scoring', {
            'fields': ('points', 'minimum_points', 'decay')
        }),
        ('Challenge Type', {
            'fields': ('challenge_type',)
        }),
        ('Standard Flag', {
            'fields': ('flag', 'flag_type'),
            'classes': ('collapse',)
        }),
        ('Instance Configuration', {
            'fields': (
                'docker_image',
                'container_port',
                'instance_url_type',
                'instance_flag_format', 
                'instance_time_limit_minutes',
                'max_instances_per_team'
            ),
            'classes': ('collapse',),
            'description': 'Select an image from the server. Set the container port your app listens on; the backend will assign a random host port automatically and inject FLAG at runtime. Choose URL display type (Web URL or Netcat).'
        }),
        ('Instance Renewal Settings', {
            'fields': (
                'allow_instance_renewal',
                'instance_renewal_limit',
                'instance_renewal_minutes',
                'instance_renewal_min_threshold'
            ),
            'classes': ('collapse',),
            'description': 'Control if teams can renew instances before expiration. Threshold determines when renew button shows (if remaining time is less than threshold).'
        }),
        ('Point Reduction Settings', {
            'fields': (
                'reduce_points_on_expiry',
                'reduce_points_on_stop',
                'reduce_points_on_wrong_flag',
                'penalty_type',
                'penalty_percentage',
                'penalty_fixed_points'
            ),
            'classes': ('collapse',),
            'description': 'Control when and how much team points are reduced. Choose percentage (e.g., 10% of challenge points) or fixed amount (e.g., 50 points).'
        }),
        ('Files', {
            'fields': ('files',),
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('solve_count', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['activate_challenges', 'deactivate_challenges', 'make_visible', 'make_hidden']
    
    def activate_challenges(self, request, queryset):
        count = queryset.update(is_active=True)
        self.message_user(request, f'{count} challenges activated.')
    activate_challenges.short_description = "Activate selected challenges"
    
    def deactivate_challenges(self, request, queryset):
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} challenges deactivated.')
    deactivate_challenges.short_description = "Deactivate selected challenges"
    
    def make_visible(self, request, queryset):
        count = queryset.update(is_visible=True)
        self.message_user(request, f'{count} challenges made visible.')
    make_visible.short_description = "Make selected challenges visible"
    
    def make_hidden(self, request, queryset):
        count = queryset.update(is_visible=False)
        self.message_user(request, f'{count} challenges made hidden.')
    make_hidden.short_description = "Make selected challenges hidden"

    def save_model(self, request, obj, form, change):
        """Persist selected docker image and container port into instance_config; create config if missing."""
        # Start from a clean config but preserve existing environment if present
        try:
            existing = obj.instance_config or {}
            if not isinstance(existing, dict):
                existing = {}
        except Exception:
            existing = {}

        docker_image = form.cleaned_data.get('docker_image')
        container_port = form.cleaned_data.get('container_port') or 5000  # default for typical web images

        config = {}
        if docker_image:
            config['image'] = docker_image

        # Set the container port; backend will bind a random host port
        try:
            port_int = int(container_port)
            if 1 <= port_int <= 65535:
                config['ports'] = {str(port_int): port_int}
        except Exception:
            pass

        # Normalize environment key name used by services
        env = existing.get('environment') or existing.get('env') or {}
        if not isinstance(env, dict):
            env = {}
        config['environment'] = env

        obj.instance_config = config
        super().save_model(request, obj, form, change)


@admin.register(ChallengeFile)
class ChallengeFileAdmin(admin.ModelAdmin):
    """Admin interface for ChallengeFile model"""
    list_display = ['name', 'file', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at']


@admin.register(Hint)
class HintAdmin(admin.ModelAdmin):
    """Admin interface for Hint model"""
    list_display = ['challenge', 'order', 'cost', 'is_visible', 'created_at']
    list_filter = ['is_visible', 'cost', 'created_at']
    search_fields = ['challenge__name', 'text']
    autocomplete_fields = ['challenge']
    ordering = ['challenge', 'order']


@admin.register(ChallengeInstance)
class ChallengeInstanceAdmin(admin.ModelAdmin):
    """Admin interface for ChallengeInstance model"""
    list_display = ['instance_id', 'team', 'challenge', 'status', 'renewal_count', 'started_at', 'expires_at']
    list_filter = ['status', 'event', 'challenge', 'started_at']
    search_fields = ['instance_id', 'team__name', 'challenge__name', 'container_id', 'flag']
    readonly_fields = ['instance_id', 'flag', 'started_at', 'stopped_at', 'config_snapshot', 'renewal_count', 'last_renewed_at']
    autocomplete_fields = ['team', 'challenge', 'started_by', 'event', 'renewed_by']
    
    fieldsets = (
        ('Relationships', {
            'fields': ('challenge', 'team', 'event', 'started_by')
        }),
        ('Instance Information', {
            'fields': ('instance_id', 'container_id', 'flag')
        }),
        ('Access', {
            'fields': ('access_url', 'access_port')
        }),
        ('Status', {
            'fields': ('status', 'error_message')
        }),
        ('Timestamps', {
            'fields': ('started_at', 'stopped_at', 'expires_at')
        }),
        ('Renewal Tracking', {
            'fields': ('renewal_count', 'last_renewed_at', 'renewed_by'),
            'classes': ('collapse',)
        }),
        ('Configuration', {
            'fields': ('config_snapshot',),
            'classes': ('collapse',)
        }),
    )
    
    actions = ['stop_instances', 'mark_error']
    
    def stop_instances(self, request, queryset):
        """Admin action to stop instances"""
        count = 0
        for instance in queryset:
            instance.stop()
            count += 1
        self.message_user(request, f'{count} instances stopped.')
    stop_instances.short_description = "Stop selected instances"
    
    def mark_error(self, request, queryset):
        """Admin action to mark instances as error"""
        count = queryset.update(status='error')
        self.message_user(request, f'{count} instances marked as error.')
    mark_error.short_description = "Mark selected instances as error"
