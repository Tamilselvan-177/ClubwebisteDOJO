from django.contrib import admin
from django.utils.html import format_html
from django.db.models import Sum
from .models import Submission, Score, Violation


@admin.register(Submission)
class SubmissionAdmin(admin.ModelAdmin):
    """Admin interface for Submission model"""
    list_display = ['team', 'challenge', 'status', 'points_awarded', 'submitted_at', 'user']
    list_filter = ['status', 'event', 'challenge', 'submitted_at']
    search_fields = ['team__name', 'challenge__name', 'flag', 'user__username']
    readonly_fields = ['submitted_at', 'points_awarded', 'points_at_submission']
    autocomplete_fields = ['team', 'challenge', 'event', 'user', 'instance']
    
    fieldsets = (
        ('Relationships', {
            'fields': ('event', 'challenge', 'team', 'user', 'instance')
        }),
        ('Submission Data', {
            'fields': ('flag', 'status')
        }),
        ('Scoring', {
            'fields': ('points_awarded', 'points_at_submission')
        }),
        ('Metadata', {
            'fields': ('ip_address', 'user_agent', 'submitted_at')
        }),
        ('Admin Notes', {
            'fields': ('admin_notes',),
            'classes': ('collapse',)
        }),
    )
    
    actions = [
        'mark_correct',
        'mark_incorrect',
        'delete_submissions_with_score_cleanup',
        'apply_wrong_flag_penalty',
        'remove_wrong_flag_penalty'
    ]
    
    def mark_correct(self, request, queryset):
        count = queryset.update(status='correct')
        self.message_user(request, f'{count} submissions marked as correct.')
    mark_correct.short_description = "Mark selected submissions as correct"
    
    def mark_incorrect(self, request, queryset):
        count = queryset.update(status='incorrect')
        self.message_user(request, f'{count} submissions marked as incorrect.')
    mark_incorrect.short_description = "Mark selected submissions as incorrect"
    
    def delete_submissions_with_score_cleanup(self, request, queryset):
        """
        Delete submissions and automatically clean up associated scores and solve counts.
        - Removes award/reduction scores tied to the submission
        - Decrements challenge.solve_count when a correct solve is removed
        - Recalculates team's total score after deletion
        """
        from django.db import transaction
        
        deleted_count = 0
        score_removed_count = 0
        solve_decrement = 0
        teams_to_recalc = set()
        
        with transaction.atomic():
            for submission in queryset:
                team = submission.team
                event = submission.event
                teams_to_recalc.add((team.id, event.id))
                
                # Delete any score rows linked to this submission (award/reduction/adjustment)
                score_entries = Score.objects.filter(
                    team=team,
                    challenge=submission.challenge,
                    event=event,
                    submission=submission
                )
                score_removed_count += score_entries.count()
                score_entries.delete()

                # If this was a correct solve, decrement solve_count (floor at 0)
                if submission.status == 'correct':
                    challenge = submission.challenge
                    if challenge.solve_count > 0:
                        challenge.solve_count -= 1
                        challenge.save(update_fields=['solve_count'])
                        solve_decrement += 1
                
                # Delete the submission itself
                submission.delete()
                deleted_count += 1
        
        # After transaction completes, recalculate scores for all affected teams
        for team_id, event_id in teams_to_recalc:
            try:
                from accounts.models import Team
                from events_ctf.models import Event
                team = Team.objects.get(id=team_id)
                event = Event.objects.get(id=event_id)
                
                # Sum remaining scores (award + adjustment types)
                remaining = Score.objects.filter(
                    team=team,
                    event=event,
                    score_type__in=['award', 'adjustment']
                ).aggregate(total=Sum('points'))['total'] or 0
                
                new_total = max(0, remaining)
                
                # Create adjustment entry with new total
                Score.objects.create(
                    team=team,
                    event=event,
                    challenge=None,
                    submission=None,
                    points=0,
                    score_type='adjustment',
                    total_score=new_total,
                    reason='Score recalculated after submission deletion',
                    notes=f'Admin deleted {deleted_count} submission(s). Score reset to {new_total}.'
                )
            except Exception as e:
                import logging
                logger = logging.getLogger(__name__)
                logger.error(f"Error recalculating score after deletion: {e}")
        
        self.message_user(
            request,
            f"✓ Deleted {deleted_count} submission(s). Removed {score_removed_count} score row(s). "
            f"Decremented {solve_decrement} challenge(s). Scores recalculated for {len(teams_to_recalc)} team(s)."
        )
    delete_submissions_with_score_cleanup.short_description = "🗑️ Delete selected + recalculate scores"

    def apply_wrong_flag_penalty(self, request, queryset):
        """Apply wrong-flag penalty entries for selected incorrect submissions (honors challenge toggle)."""
        from django.db import transaction
        from .services import submission_service
        applied = 0
        skipped = 0
        with transaction.atomic():
            for submission in queryset.select_related('challenge', 'team', 'event'):
                if submission.status != 'incorrect':
                    skipped += 1
                    continue
                challenge = submission.challenge
                if not getattr(challenge, 'reduce_points_on_wrong_flag', True):
                    skipped += 1
                    continue
                # Do not re-penalize if reduction already exists for this submission
                existing_reduction = Score.objects.filter(
                    submission=submission,
                    score_type='reduction'
                ).exists()
                if existing_reduction:
                    skipped += 1
                    continue
                submission_service.reduce_points_on_wrong_submission(
                    submission.team,
                    challenge,
                    submission.event,
                    submission
                )
                applied += 1
        self.message_user(request, f"Applied penalty to {applied} submission(s). Skipped {skipped}.")
    apply_wrong_flag_penalty.short_description = "Apply wrong-flag penalty to selected"

    def remove_wrong_flag_penalty(self, request, queryset):
        """Remove reduction entries associated with selected submissions."""
        from django.db import transaction
        removed = 0
        with transaction.atomic():
            for submission in queryset:
                removed += Score.objects.filter(
                    submission=submission,
                    score_type='reduction'
                ).delete()[0]
        self.message_user(request, f"Removed {removed} reduction score row(s).")
    remove_wrong_flag_penalty.short_description = "Remove wrong-flag penalty for selected"


@admin.register(Score)
class ScoreAdmin(admin.ModelAdmin):
    """Admin interface for Score model"""
    list_display = ['team', 'challenge', 'points_display', 'score_type_badge', 'total_score', 'reason', 'created_at']
    list_filter = ['score_type', 'event', 'challenge', 'created_at']
    search_fields = ['team__name', 'challenge__name', 'reason', 'notes']
    readonly_fields = ['created_at', 'total_score']
    autocomplete_fields = ['team', 'challenge', 'event', 'submission', 'created_by']
    
    fieldsets = (
        ('Relationships', {
            'fields': ('event', 'team', 'challenge', 'submission', 'created_by')
        }),
        ('Score Information', {
            'fields': ('points', 'score_type', 'total_score')
        }),
        ('Details', {
            'fields': ('reason', 'notes')
        }),
        ('Timestamp', {
            'fields': ('created_at',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('team', 'challenge', 'event')
    
    def points_display(self, obj):
        """Display points with color coding"""
        from django.utils.html import format_html
        if obj.points < 0:
            return format_html('<span style="color: red; font-weight: bold;">{}</span>', obj.points)
        else:
            return format_html('<span style="color: green; font-weight: bold;">+{}</span>', obj.points)
    points_display.short_description = 'Points'
    
    def score_type_badge(self, obj):
        """Display score type with badge styling"""
        from django.utils.html import format_html
        colors = {
            'award': 'green',
            'reduction': 'red',
            'adjustment': 'blue'
        }
        color = colors.get(obj.score_type, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.score_type.upper()
        )
    score_type_badge.short_description = 'Type'


@admin.register(Violation)
class ViolationAdmin(admin.ModelAdmin):
    """Admin interface for Violation model"""
    list_display = ['team', 'violation_type', 'severity', 'is_resolved', 'created_at', 'detected_by']
    list_filter = ['violation_type', 'severity', 'is_resolved', 'event', 'created_at']
    search_fields = ['team__name', 'challenge__name', 'description', 'detected_by']
    readonly_fields = ['created_at', 'resolved_at']
    autocomplete_fields = ['team', 'event', 'challenge', 'submission', 'instance', 'resolved_by']
    
    fieldsets = (
        ('Relationships', {
            'fields': ('event', 'team', 'challenge', 'submission', 'instance')
        }),
        ('Violation Details', {
            'fields': ('violation_type', 'severity', 'description', 'evidence')
        }),
        ('Detection', {
            'fields': ('detected_by', 'created_at')
        }),
        ('Resolution', {
            'fields': ('is_resolved', 'action_taken', 'resolved_at', 'resolved_by')
        }),
    )
    
    actions = ['resolve_violations', 'mark_critical']
    
    def resolve_violations(self, request, queryset):
        """Admin action to resolve violations"""
        count = 0
        for violation in queryset:
            violation.resolve(resolved_by_user=request.user, action_taken="Resolved by admin")
            count += 1
        self.message_user(request, f'{count} violations resolved.')
    resolve_violations.short_description = "Resolve selected violations"
    
    def mark_critical(self, request, queryset):
        """Admin action to mark violations as critical"""
        count = queryset.update(severity='critical')
        self.message_user(request, f'{count} violations marked as critical.')
    mark_critical.short_description = "Mark selected violations as critical"
