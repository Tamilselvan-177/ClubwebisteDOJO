from django.contrib import admin
from django.utils.html import format_html
from .models import Notification


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin interface for Notification model"""
    list_display = ['title', 'recipient_display', 'notification_type', 'priority', 'is_read', 'created_at']
    list_filter = ['notification_type', 'priority', 'is_read', 'is_system_wide', 'created_at']
    search_fields = ['title', 'message', 'user__username', 'team__name']
    readonly_fields = ['created_at', 'read_at']
    autocomplete_fields = ['user', 'team', 'event', 'challenge', 'submission', 'violation', 'created_by']
    
    fieldsets = (
        ('Recipients', {
            'fields': ('user', 'team', 'is_system_wide')
        }),
        ('Content', {
            'fields': ('title', 'message', 'notification_type', 'priority')
        }),
        ('Related Objects', {
            'fields': ('event', 'challenge', 'submission', 'violation'),
            'classes': ('collapse',)
        }),
        ('Action', {
            'fields': ('action_url', 'action_text'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_read', 'read_at', 'expires_at')
        }),
        ('Metadata', {
            'fields': ('created_by', 'created_at')
        }),
    )
    
    actions = ['mark_as_read', 'mark_as_unread', 'set_high_priority']
    
    def recipient_display(self, obj):
        """Display recipient information"""
        if obj.user:
            return f"User: {obj.user.username}"
        elif obj.team:
            return f"Team: {obj.team.name}"
        elif obj.is_system_wide:
            return format_html('<span style="color: #E50914; font-weight: bold;">System-wide</span>')
        return "-"
    recipient_display.short_description = 'Recipient'
    
    def mark_as_read(self, request, queryset):
        """Admin action to mark notifications as read"""
        count = 0
        for notification in queryset:
            notification.mark_as_read()
            count += 1
        self.message_user(request, f'{count} notifications marked as read.')
    mark_as_read.short_description = "Mark selected notifications as read"
    
    def mark_as_unread(self, request, queryset):
        """Admin action to mark notifications as unread"""
        count = 0
        for notification in queryset:
            notification.mark_as_unread()
            count += 1
        self.message_user(request, f'{count} notifications marked as unread.')
    mark_as_unread.short_description = "Mark selected notifications as unread"
    
    def set_high_priority(self, request, queryset):
        """Admin action to set high priority"""
        count = queryset.update(priority='high')
        self.message_user(request, f'{count} notifications set to high priority.')
    set_high_priority.short_description = "Set selected notifications to high priority"
