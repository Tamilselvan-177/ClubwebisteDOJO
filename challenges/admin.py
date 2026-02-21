from django.contrib import admin
from django.utils.html import format_html
from django import forms
import os
import subprocess
import logging
from .models import Category, Challenge, ChallengeFile, Hint, ChallengeInstance

logger = logging.getLogger(__name__)


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
    """
    Return list of docker images as 'repository:tag'. Runs 'docker images' on this server only (no Docker Hub / pull).
    The dropdown shows only what the web server process can see: same user must be in the 'docker' group and
    service restarted after that, or the command fails and you get no real images (you can still type image:tag manually).
    """
    images = []
    # Try full paths first so admin works when run under systemd (minimal PATH); then fall back to PATH
    for docker_cmd in ['/usr/bin/docker', '/usr/local/bin/docker', 'docker']:
        try:
            result = subprocess.run(
                [docker_cmd, 'images', '--format', '{{.Repository}}:{{.Tag}}'],
                capture_output=True,
                timeout=10,
                text=True,
                env={**os.environ, 'PATH': os.environ.get('PATH', '/usr/local/bin:/usr/bin:/bin')}
            )
            if result.returncode == 0:
                for line in result.stdout.splitlines():
                    line = line.strip()
                    if line and line != '<none>:<none>':
                        images.append(line)
                break
            else:
                logger.warning("docker images failed (%s): %s", docker_cmd, (result.stderr or result.stdout or "").strip())
        except FileNotFoundError:
            continue
        except Exception as e:
            logger.warning("Could not list Docker images (%s): %s", docker_cmd, e)
    else:
        logger.warning("Docker not found in PATH, /usr/bin/docker, or /usr/local/bin/docker. Use 'Or type image:tag manually' below.")
    # Ensure some common images for convenience when docker is available
    if images:
        for img in ['ubuntu:latest', 'python:3.11', 'nginx:latest']:
            if img not in images:
                images.append(img)
    return images


class ChallengeAdminForm(forms.ModelForm):
    """Admin form with Docker image dropdown and manual override for instance-based challenges."""

    docker_image = forms.ChoiceField(
        required=False,
        choices=[],
        label='Docker Image (from server)',
        help_text='Populated from "docker images" on this server. If empty, the web server user may not have Docker access (see instructions below).'
    )

    docker_image_manual = forms.CharField(
        required=False,
        max_length=255,
        label='Or type image:tag manually',
        help_text='e.g. hawkinslab-hawkins:latest — use this if the dropdown is empty (Docker not available to the server) or your image is not listed.'
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
        self.fields['docker_image'].choices = [('', '---------')] + [(img, img) for img in images]

        # Pre-select from existing instance_config
        try:
            config = self.instance.instance_config or {}
            current_image = config.get('image')
            if current_image:
                if current_image in images:
                    self.fields['docker_image'].initial = current_image
                else:
                    self.fields['docker_image_manual'].initial = current_image
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
            'fields': ('is_visible', 'is_active', 'release_time'),
            'description': 'Release time: Set when challenge becomes visible. Leave empty for immediate visibility. Use admin actions to reset or set to now.'
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
                'docker_image_manual',
                'container_port',
                'instance_url_type',
                'instance_flag_format', 
                'instance_time_limit_minutes',
                'max_instances_per_team'
            ),
            'classes': ('collapse',),
            'description': 'Select an image from the server or type image:tag manually (e.g. hawkinslab-hawkins:latest). If dropdown is empty, add the web server user to the docker group: sudo usermod -aG docker <user> and restart the app. Set the container port your app listens on; the backend will assign a random host port and inject FLAG at runtime.'
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
    
    actions = ['activate_challenges', 'deactivate_challenges', 'make_visible', 'make_hidden', 'reset_release_time', 'set_release_time_now']
    
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
    
    def reset_release_time(self, request, queryset):
        """Reset release_time to None (remove delay)"""
        count = queryset.update(release_time=None)
        self.message_user(request, f'{count} challenges release time reset (delay removed).')
    reset_release_time.short_description = "Reset release time (remove delay)"
    
    def set_release_time_now(self, request, queryset):
        """Set release_time to current time (make available immediately)"""
        from django.utils import timezone
        count = queryset.update(release_time=timezone.now())
        self.message_user(request, f'{count} challenges release time set to now (available immediately).')
    set_release_time_now.short_description = "Set release time to now (available immediately)"

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
        docker_image_manual = (form.cleaned_data.get('docker_image_manual') or '').strip()
        container_port = form.cleaned_data.get('container_port') or 5000  # default for typical web images

        config = {}
        # Prefer manually typed image (so you can use any image even when dropdown is empty)
        if docker_image_manual:
            config['image'] = docker_image_manual
        elif docker_image:
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
