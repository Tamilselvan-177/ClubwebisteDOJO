from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import Event, Theme, AdminAuditLog, NotificationSound
from .services import event_control_service


@admin.register(NotificationSound)
class NotificationSoundAdmin(admin.ModelAdmin):
    """Admin interface for NotificationSound model"""
    list_display = ['name', 'sound_type', 'duration_display', 'is_default', 'audio_preview', 'created_at']
    list_filter = ['sound_type', 'is_default', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'audio_preview']
    
    fieldsets = (
        ('Sound Information', {
            'fields': ('name', 'description', 'sound_type', 'is_default')
        }),
        ('Audio File', {
            'fields': ('audio_file', 'audio_preview', 'duration_seconds')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def duration_display(self, obj):
        """Display duration in seconds"""
        if obj.duration_seconds:
            return f"{obj.duration_seconds}s"
        return "-"
    duration_display.short_description = 'Duration'
    
    def audio_preview(self, obj):
        """Display audio preview player"""
        if obj.audio_file:
            return format_html(
                '<audio controls style="width: 100%; max-width: 300px;"><source src="{}" type="audio/mpeg"></audio>',
                obj.audio_file.url
            )
        return "No audio file"
    audio_preview.short_description = 'Preview'


@admin.register(Theme)
class ThemeAdmin(admin.ModelAdmin):
    """Admin interface for Theme model"""
    list_display = ['name', 'is_default', 'color_preview', 'created_at']
    list_filter = ['is_default', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'color_preview']
    
    fieldsets = (
        ('Theme Information', {
            'fields': ('name', 'description', 'is_default')
        }),
        ('Colors', {
            'fields': ('primary_color', 'secondary_color', 'background_color', 'text_color', 'color_preview')
        }),
        ('Assets', {
            'fields': ('logo', 'favicon', 'custom_css')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    def color_preview(self, obj):
        """Display color preview"""
        if obj.primary_color:
            return format_html(
                '<div style="width: 50px; height: 20px; background-color: {}; border: 1px solid #ccc;"></div>',
                obj.primary_color
            )
        return "-"
    color_preview.short_description = 'Primary Color'


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    """Admin interface for Event model with contest control"""
    list_display = ['name', 'year', 'slug', 'contest_state_badge', 'scoreboard_state_badge', 'is_active', 'is_visible', 'state_changed_at', 'event_control_actions']
    list_filter = ['year', 'contest_state', 'scoreboard_state', 'is_active', 'is_visible', 'is_archived', 'scoring_type', 'registration_open', 'created_at']
    search_fields = ['name', 'slug', 'description']
    readonly_fields = ['created_by', 'created_at', 'updated_at', 'state_changed_at', 'state_changed_by', 'event_control_buttons']
    prepopulated_fields = {'slug': ('name', 'year')}
    
    fieldsets = (
        ('Event Information', {
            'fields': ('name', 'year', 'slug', 'description', 'banner')
        }),
        ('Contest State Control', {
            'fields': ('contest_state', 'scoreboard_state', 'state_changed_at', 'state_changed_by', 'event_control_buttons'),
            'description': 'Control the runtime state of the contest'
        }),
        ('Status', {
            'fields': ('is_active', 'is_visible', 'is_archived')
        }),
        ('Scheduling', {
            'fields': ('start_time', 'end_time')
        }),
        ('Configuration', {
            'fields': ('theme', 'scoring_type', 'max_team_size', 'registration_open')
        }),
        ('Instance Configuration', {
            'fields': (
                'max_instances_per_team',
                'instance_time_limit_minutes',
                'instance_extension_minutes',
                'instance_extension_penalty_points',
                'instance_max_extensions',
                'instance_low_time_threshold_minutes'
            )
        }),
        ('Notification Sounds - Toggle', {
            'fields': (
                'enable_notification_sounds',
                'sound_on_challenge_correct',
                'sound_on_instance_renewal',
                'sound_on_instance_expiry',
                'sound_on_flag_incorrect',
                'sound_on_hint_added',
                'sound_on_user_banned'
            ),
            'description': 'Control which events trigger notification sounds'
        }),
        ('Custom Notification Sounds', {
            'fields': (
                'custom_sound_challenge_correct',
                'custom_sound_instance_renewal',
                'custom_sound_instance_expiry',
                'custom_sound_flag_incorrect',
                'custom_sound_hint_added',
                'custom_sound_user_banned'
            ),
            'description': 'Assign custom audio files for each notification type (leave blank to use default sounds)',
            'classes': ('collapse',)
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['activate_events', 'deactivate_events', 'archive_events', 'start_events', 'pause_events', 'resume_events', 'stop_events']
    
    def save_model(self, request, obj, form, change):
        """Automatically set created_by when creating a new event"""
        if not change:  # Only when creating new event
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def contest_state_badge(self, obj):
        """Display contest state as colored badge"""
        colors = {
            'not_started': '#999',
            'running': '#00aa00',
            'paused': '#ffaa00',
            'resumed': '#00aaff',
            'stopped': '#aa0000',
        }
        color = colors.get(obj.contest_state, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_contest_state_display()
        )
    contest_state_badge.short_description = 'Contest State'
    
    def scoreboard_state_badge(self, obj):
        """Display scoreboard state as colored badge"""
        colors = {
            'hidden': '#999',
            'live': '#00aa00',
            'frozen': '#ffaa00',
            'finalized': '#aa0000',
        }
        color = colors.get(obj.scoreboard_state, '#999')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 8px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_scoreboard_state_display()
        )
    scoreboard_state_badge.short_description = 'Scoreboard State'
    
    def event_control_actions(self, obj):
        """Display inline action buttons for event control"""
        if not obj.id:
            return "-"
        
        buttons = []
        
        if obj.contest_state == 'not_started':
            start_url = reverse('admin:events_ctf_event_start', args=[obj.id])
            buttons.append(f'<a href="{start_url}" class="button" style="background-color:#417690;">▶️ Start</a>')
        elif obj.contest_state in ['running', 'resumed']:
            pause_url = reverse('admin:events_ctf_event_pause', args=[obj.id])
            stop_url = reverse('admin:events_ctf_event_stop', args=[obj.id])
            buttons.append(f'<a href="{pause_url}" class="button" style="background-color:#f8b737;">⏸️ Pause</a>')
            buttons.append(f'<a href="{stop_url}" class="button" style="background-color:#ba2121;">🛑 Stop</a>')
        elif obj.contest_state == 'paused':
            resume_url = reverse('admin:events_ctf_event_resume', args=[obj.id])
            stop_url = reverse('admin:events_ctf_event_stop', args=[obj.id])
            buttons.append(f'<a href="{resume_url}" class="button" style="background-color:#417690;">▶️ Resume</a>')
            buttons.append(f'<a href="{stop_url}" class="button" style="background-color:#ba2121;">🛑 Stop</a>')
        
        return mark_safe(' '.join(buttons)) if buttons else mark_safe('<span style="color: #999;">—</span>')
    event_control_actions.short_description = 'Actions'
    
    def event_control_buttons(self, obj):
        """Display event control buttons in change form"""
        if not obj.id:
            return "-"
        
        buttons = []
        
        # Scoreboard link (always visible)
        scoreboard_url = reverse('events_ctf:admin-scoreboard', args=[obj.id])
        buttons.append(f'<a href="{scoreboard_url}" class="button" style="background-color:#4a5568; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; display: inline-block; margin: 5px 0;">📊 View Scoreboard</a>')
        
        if obj.contest_state == 'not_started':
            start_url = reverse('admin:events_ctf_event_start', args=[obj.id])
            buttons.append(f'<a href="{start_url}" class="button" style="background-color:#417690;">▶️ Start Event</a>')
        elif obj.contest_state in ['running', 'resumed']:
            pause_url = reverse('admin:events_ctf_event_pause', args=[obj.id])
            stop_url = reverse('admin:events_ctf_event_stop', args=[obj.id])
            buttons.append(f'<a href="{pause_url}" class="button" style="background-color:#f8b737;">⏸️ Pause Event</a>')
            buttons.append(f'<a href="{stop_url}" class="button" style="background-color:#ba2121;">🛑 Stop Event</a>')
        elif obj.contest_state == 'paused':
            resume_url = reverse('admin:events_ctf_event_resume', args=[obj.id])
            stop_url = reverse('admin:events_ctf_event_stop', args=[obj.id])
            buttons.append(f'<a href="{resume_url}" class="button" style="background-color:#417690;">▶️ Resume Event</a>')
            buttons.append(f'<a href="{stop_url}" class="button" style="background-color:#ba2121;">🛑 Stop Event</a>')
        
        return mark_safe('<br>'.join(buttons)) if buttons else mark_safe('<span style="color: #999;">No actions available</span>')
    event_control_buttons.short_description = 'Contest Controls'
    
    def get_urls(self):
        """Add custom URLs for event control"""
        from django.urls import path
        urls = super().get_urls()
        custom_urls = [
            path('<int:event_id>/start/', self.admin_site.admin_view(self.start_event_view), name='events_ctf_event_start'),
            path('<int:event_id>/pause/', self.admin_site.admin_view(self.pause_event_view), name='events_ctf_event_pause'),
            path('<int:event_id>/resume/', self.admin_site.admin_view(self.resume_event_view), name='events_ctf_event_resume'),
            path('<int:event_id>/stop/', self.admin_site.admin_view(self.stop_event_view), name='events_ctf_event_stop'),
        ]
        return custom_urls + urls
    
    def start_event_view(self, request, event_id):
        """View to start event"""
        event = Event.objects.get(id=event_id)
        try:
            event_control_service.start_event(event, request.user, request)
            self.message_user(request, f'Event "{event.name}" started successfully.')
        except ValueError as e:
            self.message_user(request, f'Error: {str(e)}', level='ERROR')
        from django.shortcuts import redirect
        return redirect('admin:events_ctf_event_change', event_id)
    
    def pause_event_view(self, request, event_id):
        """View to pause event"""
        event = Event.objects.get(id=event_id)
        try:
            event_control_service.pause_event(event, request.user, request)
            self.message_user(request, f'Event "{event.name}" paused successfully.')
        except ValueError as e:
            self.message_user(request, f'Error: {str(e)}', level='ERROR')
        from django.shortcuts import redirect
        return redirect('admin:events_ctf_event_change', event_id)
    
    def resume_event_view(self, request, event_id):
        """View to resume event"""
        event = Event.objects.get(id=event_id)
        try:
            event_control_service.resume_event(event, request.user, request)
            self.message_user(request, f'Event "{event.name}" resumed successfully.')
        except ValueError as e:
            self.message_user(request, f'Error: {str(e)}', level='ERROR')
        from django.shortcuts import redirect
        return redirect('admin:events_ctf_event_change', event_id)
    
    def stop_event_view(self, request, event_id):
        """View to stop event"""
        event = Event.objects.get(id=event_id)
        try:
            event, destroyed_count = event_control_service.stop_event(event, request.user, request)
            self.message_user(request, f'Event "{event.name}" stopped successfully. {destroyed_count} instances destroyed.')
        except Exception as e:
            self.message_user(request, f'Error: {str(e)}', level='ERROR')
        from django.shortcuts import redirect
        return redirect('admin:events_ctf_event_change', event_id)
    
    def start_events(self, request, queryset):
        """Admin action to start events"""
        count = 0
        for event in queryset:
            try:
                event_control_service.start_event(event, request.user, request)
                count += 1
            except ValueError:
                pass
        self.message_user(request, f'{count} events started.')
    start_events.short_description = "Start selected events"
    
    def pause_events(self, request, queryset):
        """Admin action to pause events"""
        count = 0
        for event in queryset:
            try:
                event_control_service.pause_event(event, request.user, request)
                count += 1
            except ValueError:
                pass
        self.message_user(request, f'{count} events paused.')
    pause_events.short_description = "Pause selected events"
    
    def resume_events(self, request, queryset):
        """Admin action to resume events"""
        count = 0
        for event in queryset:
            try:
                event_control_service.resume_event(event, request.user, request)
                count += 1
            except ValueError:
                pass
        self.message_user(request, f'{count} events resumed.')
    resume_events.short_description = "Resume selected events"
    
    def stop_events(self, request, queryset):
        """Admin action to stop events"""
        count = 0
        total_destroyed = 0
        for event in queryset:
            try:
                _, destroyed_count = event_control_service.stop_event(event, request.user, request)
                count += 1
                total_destroyed += destroyed_count
            except Exception:
                pass
        self.message_user(request, f'{count} events stopped. {total_destroyed} instances destroyed.')
    stop_events.short_description = "Stop selected events (⚠️ DESTROYS ALL INSTANCES)"
    
    def activate_events(self, request, queryset):
        """Admin action to activate events"""
        count = queryset.update(is_active=True, is_visible=True)
        self.message_user(request, f'{count} events activated.')
    activate_events.short_description = "Activate selected events"
    
    def deactivate_events(self, request, queryset):
        """Admin action to deactivate events"""
        count = queryset.update(is_active=False)
        self.message_user(request, f'{count} events deactivated.')
    deactivate_events.short_description = "Deactivate selected events"
    
    def archive_events(self, request, queryset):
        """Admin action to archive events"""
        count = queryset.update(is_active=False, is_archived=True)
        self.message_user(request, f'{count} events archived.')
    archive_events.short_description = "Archive selected events"


@admin.register(AdminAuditLog)
class AdminAuditLogAdmin(admin.ModelAdmin):
    """Admin interface for audit logs"""
    list_display = ['timestamp', 'action_type', 'performed_by', 'event', 'description', 'ip_address']
    list_filter = ['action_type', 'timestamp', 'event']
    search_fields = ['description', 'performed_by__username', 'event__name']
    readonly_fields = ['timestamp', 'event', 'action_type', 'description', 'reason', 'performed_by', 
                      'content_type', 'object_id', 'ip_address', 'user_agent', 'metadata']
    date_hierarchy = 'timestamp'
    ordering = ['-timestamp']
    
    fieldsets = (
        ('Action Details', {
            'fields': ('action_type', 'description', 'reason', 'timestamp')
        }),
        ('Context', {
            'fields': ('event', 'performed_by', 'content_type', 'object_id')
        }),
        ('Request Information', {
            'fields': ('ip_address', 'user_agent')
        }),
        ('Additional Data', {
            'fields': ('metadata',)
        }),
    )
    
    def has_add_permission(self, request):
        """Audit logs are created automatically, no manual creation"""
        return False
    
    def has_change_permission(self, request, obj=None):
        """Audit logs are immutable"""
        return False
