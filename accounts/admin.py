from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from .models import User, Team, TeamMembership, PlatformSettings


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Admin interface for User model"""
    list_display = ['username', 'email', 'email_verified_badge', 'is_banned', 'is_staff', 'is_superuser', 'created_at']
    list_filter = ['is_email_verified', 'is_banned', 'is_staff', 'is_superuser', 'is_active', 'created_at']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ['created_at', 'updated_at', 'last_login', 'date_joined', 'email_verification_token_created_at']
    autocomplete_fields = []
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Email Verification', {
            'fields': ('is_email_verified', 'email_verification_token', 'email_verification_token_created_at')
        }),
        ('Ban Information', {
            'fields': ('is_banned', 'banned_at', 'banned_reason')
        }),
        ('Profile', {
            'fields': ('bio', 'avatar')
        }),
        ('Preferences', {
            'fields': ('email_notifications',)
        }),
        ('Metadata', {
            'fields': ('last_login_ip', 'created_at', 'updated_at')
        }),
    )
    
    actions = ['ban_users', 'unban_users', 'verify_emails', 'unverify_emails']
    
    def email_verified_badge(self, obj):
        """Display email verification status with colored badge"""
        if obj.is_email_verified:
            return format_html(
                '<span style="background-color: #28a745; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">✓ VERIFIED</span>'
            )
        else:
            return format_html(
                '<span style="background-color: #dc3545; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">✗ NOT VERIFIED</span>'
            )
    email_verified_badge.short_description = 'Email Status'
    
    def verify_emails(self, request, queryset):
        """Admin action to manually verify user emails"""
        count = queryset.update(is_email_verified=True)
        self.message_user(request, f'{count} user(s) email verified.')
    verify_emails.short_description = "✓ Verify selected users' emails"
    
    def unverify_emails(self, request, queryset):
        """Admin action to unverify user emails"""
        count = queryset.update(is_email_verified=False)
        self.message_user(request, f'{count} user(s) email unverified.')
    unverify_emails.short_description = "✗ Unverify selected users' emails"
    
    def ban_users(self, request, queryset):
        """Admin action to ban users"""
        for user in queryset:
            user.ban(reason="Banned by administrator")
        self.message_user(request, f'{queryset.count()} users banned.')
    ban_users.short_description = "Ban selected users"
    
    def unban_users(self, request, queryset):
        """Admin action to unban users"""
        count = queryset.update(is_banned=False)
        self.message_user(request, f'{count} users unbanned.')
    unban_users.short_description = "Unban selected users"


class TeamMembershipInline(admin.TabularInline):
    """Inline admin for team members"""
    model = TeamMembership
    extra = 1
    autocomplete_fields = ['user']


@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    """Admin interface for Team model"""
    list_display = ['name', 'captain', 'member_count', 'is_banned', 'created_at']
    list_filter = ['is_banned', 'created_at']
    search_fields = ['name', 'description']
    readonly_fields = ['created_at', 'updated_at', 'banned_at']
    autocomplete_fields = ['captain']
    inlines = [TeamMembershipInline]
    
    fieldsets = (
        ('Team Information', {
            'fields': ('name', 'description', 'captain', 'avatar', 'website')
        }),
        ('Ban Information', {
            'fields': ('is_banned', 'banned_at', 'banned_reason')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at')
        }),
    )
    
    actions = ['ban_teams', 'unban_teams']
    
    def member_count(self, obj):
        """Display member count"""
        return obj.get_member_count()
    member_count.short_description = 'Members'
    
    def ban_teams(self, request, queryset):
        """Admin action to ban teams"""
        count = queryset.update(is_banned=True)
        self.message_user(request, f'{count} teams banned.')
    ban_teams.short_description = "Ban selected teams"
    
    def unban_teams(self, request, queryset):
        """Admin action to unban teams"""
        count = queryset.update(is_banned=False)
        self.message_user(request, f'{count} teams unbanned.')
    unban_teams.short_description = "Unban selected teams"


@admin.register(TeamMembership)
class TeamMembershipAdmin(admin.ModelAdmin):
    """Admin interface for TeamMembership model"""
    list_display = ['user', 'team', 'joined_at', 'is_active']
    list_filter = ['is_active', 'joined_at', 'team']
    search_fields = ['user__username', 'team__name']
    autocomplete_fields = ['user', 'team']
    readonly_fields = ['joined_at']


@admin.register(PlatformSettings)
class PlatformSettingsAdmin(admin.ModelAdmin):
    """Admin interface for Platform Settings"""
    list_display = ['get_status', 'updated_at']
    readonly_fields = ['updated_at']
    
    fieldsets = (
        ('Registration Settings', {
            'fields': ('is_registration_enabled', 'require_email_verification'),
            'description': 'Control whether new users can register and if email verification is required for login.'
        }),
        ('Maintenance Settings', {
            'fields': ('maintenance_mode', 'maintenance_message'),
            'description': 'Put the platform in maintenance mode if needed.'
        }),
        ('Metadata', {
            'fields': ('updated_at',),
            'classes': ('collapse',)
        }),
    )
    
    def has_add_permission(self, request):
        """Only allow editing existing settings, not creating new ones"""
        return not PlatformSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of settings"""
        return False
    
    def get_status(self, obj):
        """Display registration status"""
        status = '✅ Enabled' if obj.is_registration_enabled else '❌ Disabled'
        return format_html('<strong>{}</strong>', status)
    get_status.short_description = 'Registration Status'


# Hide Celery Beat scheduling models from the admin UI
try:
    from django_celery_beat.models import (
        ClockedSchedule,
        CrontabSchedule,
        IntervalSchedule,
        PeriodicTask,
        SolarSchedule,
    )

    for model in (
        ClockedSchedule,
        CrontabSchedule,
        IntervalSchedule,
        PeriodicTask,
        SolarSchedule,
    ):
        try:
            admin.site.unregister(model)
        except admin.sites.NotRegistered:
            pass
except Exception:
    # If django_celery_beat is missing, skip unregistering
    pass
