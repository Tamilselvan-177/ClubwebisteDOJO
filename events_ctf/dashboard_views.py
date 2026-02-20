"""
Custom admin dashboard views for event management.
"""
from django.shortcuts import render, get_object_or_404
from django.contrib.admin.views.decorators import staff_member_required
from django.db.models import Count, Q, Sum
from .models import Event, AdminAuditLog
from challenges.models import ChallengeInstance, Challenge
from submissions.models import Submission, Violation, Score
from accounts.models import Team
from datetime import timedelta
from django.utils import timezone
import json


@staff_member_required
def admin_dashboard(request):
    """Main admin dashboard"""
    # Get active events
    active_events = Event.objects.filter(is_active=True).order_by('-created_at')
    
    # Get recent audit logs
    recent_logs = AdminAuditLog.objects.select_related('event', 'performed_by').order_by('-timestamp')[:20]
    
    # System statistics
    stats = {
        'total_events': Event.objects.count(),
        'active_events': active_events.count(),
        'total_teams': Team.objects.count(),
        'active_instances': ChallengeInstance.objects.filter(status='running').count(),
        'total_submissions': Submission.objects.count(),
        'pending_violations': Violation.objects.filter(is_resolved=False).count(),
    }
    
    context = {
        'active_events': active_events,
        'recent_logs': recent_logs,
        'stats': stats,
    }
    
    return render(request, 'admin/dashboard.html', context)


@staff_member_required
def event_control_panel(request, event_id):
    """Event-specific control panel"""
    event = get_object_or_404(Event, id=event_id)
    
    # Event statistics
    # Get teams that have submissions for this event
    teams_with_submissions = Submission.objects.filter(event=event).values_list('team', flat=True).distinct()
    
    stats = {
        'total_teams': Team.objects.filter(id__in=teams_with_submissions).count(),
        'active_instances': ChallengeInstance.objects.filter(event=event, status='running').count(),
        'total_instances': ChallengeInstance.objects.filter(event=event).count(),
        'total_submissions': Submission.objects.filter(event=event).count(),
        'correct_submissions': Submission.objects.filter(event=event, status='correct').count(),
        'violations': Violation.objects.filter(event=event, is_resolved=False).count(),
        'banned_teams': Team.objects.filter(id__in=teams_with_submissions, is_banned=True).count(),
    }
    
    # Recent activity
    recent_audit_logs = AdminAuditLog.objects.filter(event=event).order_by('-timestamp')[:10]
    
    # Instance breakdown by challenge
    instance_stats = ChallengeInstance.objects.filter(event=event).values(
        'challenge__name'
    ).annotate(
        total=Count('id'),
        running=Count('id', filter=Q(status='running')),
        stopped=Count('id', filter=Q(status='stopped'))
    ).order_by('-total')[:10]
    
    # Top teams by score
    from submissions.models import Score
    from django.db.models import Sum
    top_teams = Score.objects.filter(event=event).values(
        'team__name'
    ).annotate(
        total_score=Sum('points')
    ).order_by('-total_score')[:10]
    
    context = {
        'event': event,
        'stats': stats,
        'recent_logs': recent_audit_logs,
        'instance_stats': instance_stats,
        'top_teams': top_teams,
    }
    
    return render(request, 'admin/event_control_panel.html', context)


@staff_member_required
def admin_scoreboard(request, event_id):
    """Admin scoreboard view for specific event - shows all data including banned teams"""
    event = get_object_or_404(Event, id=event_id)
    
    context = {
        'current_event': event,
        'scoreboard_state': event.scoreboard_state,
        'is_scoreboard_frozen': getattr(event, 'is_scoreboard_frozen', False),
        'is_admin_view': True,
    }
    
    freeze_cutoff = event.scoreboard_frozen_at if getattr(event, 'is_scoreboard_frozen', False) else None
    scoreboard_state = event.scoreboard_state
    
    # If explicitly frozen, check for snapshot
    if getattr(event, 'is_scoreboard_frozen', False):
        from events_ctf.models import ScoreboardSnapshot
        snapshot = ScoreboardSnapshot.objects.filter(event=event).order_by('-created_at').first()
        if snapshot:
            context.update({
                'teams': snapshot.snapshot.get('teams', []),
                'teams_graph_data': json.dumps(snapshot.snapshot.get('teams_graph_data', [])),
                'recent_solves': Submission.objects.filter(
                    event=event,
                    status='correct',
                    submitted_at__lte=event.scoreboard_frozen_at,
                ).select_related('team', 'challenge', 'user').order_by('-submitted_at')[:20],
                'top_solvers': Submission.objects.filter(
                    event=event,
                    status='correct',
                    submitted_at__lte=event.scoreboard_frozen_at,
                ).values('user__username').annotate(
                    solve_count=Count('id')
                ).order_by('-solve_count')[:10],
                'total_challenges': Challenge.objects.filter(
                    event=event,
                    is_active=True,
                    is_visible=True
                ).count(),
                'freeze_time': event.scoreboard_frozen_at,
            })
            return render(request, 'admin/scoreboard.html', context)
    
    # Get all teams that have scores in this event - INCLUDE BANNED TEAMS (admin view)
    score_qs = Score.objects.filter(event=event)
    if freeze_cutoff:
        score_qs = score_qs.filter(created_at__lte=freeze_cutoff)
    team_ids = set(score_qs.values_list('team_id', flat=True))
    
    team_data = []
    for team_id in team_ids:
        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            continue
        
        # Get the LATEST total_score for this team in this event
        latest_score_qs = Score.objects.filter(
            team_id=team_id,
            event=event
        )
        if freeze_cutoff:
            latest_score_qs = latest_score_qs.filter(created_at__lte=freeze_cutoff)
        latest_score = latest_score_qs.order_by('-created_at').first()
        
        total_score = latest_score.total_score if latest_score else 0
        
        # Count correct submissions
        submissions_qs = Submission.objects.filter(
            team_id=team_id,
            event=event,
            status='correct'
        )
        if freeze_cutoff:
            submissions_qs = submissions_qs.filter(submitted_at__lte=freeze_cutoff)
        solved_count = submissions_qs.values('challenge').distinct().count()

        # Compute total penalty points (sum of reductions)
        penalty_qs = Score.objects.filter(
            team_id=team_id,
            event=event,
            score_type='reduction'
        )
        if freeze_cutoff:
            penalty_qs = penalty_qs.filter(created_at__lte=freeze_cutoff)
        penalty_sum = penalty_qs.aggregate(total=Sum('points'))['total'] or 0
        penalty_points = -penalty_sum if penalty_sum < 0 else 0

        # Compute total earned points from solved challenges (without penalties)
        solved_points_total = submissions_qs.aggregate(total=Sum('points_awarded'))['total'] or 0

        # Hypothetical score without penalties
        score_without_penalty = total_score + penalty_points
        
        # Get last solve time
        last_submission_qs = submissions_qs.order_by('-submitted_at')
        last_submission = last_submission_qs.first()
        
        team_data.append({
            'team': team,
            'total_score': total_score,
            'solved_count': solved_count,
            'penalty_points': penalty_points,
            'score_without_penalty': score_without_penalty,
            'solved_points_total': solved_points_total,
            'last_solve_time': last_submission.submitted_at if last_submission else None,
        })
    
    # Sort by score and time
    team_data.sort(key=lambda x: (-x['total_score'], x['last_solve_time'] or timezone.now()))
    
    # Add ranks
    for idx, entry in enumerate(team_data, 1):
        entry['rank'] = idx
    
    # Get recent solves (INCLUDE BANNED TEAMS for admin)
    recent_solves_qs = Submission.objects.filter(
        event=event,
        status='correct',
    ).select_related('team', 'challenge', 'user')
    
    if freeze_cutoff:
        recent_solves_qs = recent_solves_qs.filter(submitted_at__lte=freeze_cutoff)
    elif scoreboard_state == 'frozen' and event.state_changed_at:
        recent_solves_qs = recent_solves_qs.filter(submitted_at__lte=event.state_changed_at)
    
    recent_solves = recent_solves_qs.order_by('-submitted_at')[:20]
    
    # Get top solvers (INCLUDE BANNED TEAMS for admin)
    top_solvers_qs = Submission.objects.filter(
        event=event,
        status='correct',
    )
    if freeze_cutoff:
        top_solvers_qs = top_solvers_qs.filter(submitted_at__lte=freeze_cutoff)
    top_solvers = top_solvers_qs.values('user__username').annotate(
        solve_count=Count('id')
    ).order_by('-solve_count')[:10]
    
    # Total challenges
    total_challenges = Challenge.objects.filter(
        event=event,
        is_active=True,
        is_visible=True
    ).count()
    
    # Build team graph data with solve history
    teams_graph_data = []
    for entry in team_data[:20]:  # Top 20 teams for graph
        team = entry['team']
        
        # Get all correct submissions for this team in chronological order
        graph_submissions = Submission.objects.filter(
            team=team,
            event=event,
            status='correct'
        )
        if freeze_cutoff:
            graph_submissions = graph_submissions.filter(submitted_at__lte=freeze_cutoff)
        graph_submissions = graph_submissions.select_related('challenge').order_by('submitted_at')
        
        solves = []
        for submission in graph_submissions:
            solves.append({
                'time': submission.submitted_at.isoformat(),
                'points': submission.points_awarded,
                'challenge': submission.challenge.name
            })
        
        teams_graph_data.append({
            'name': team.name,
            'solves': solves,
            'color': None  # Use default colors
        })
    
    context.update({
        'teams': team_data[:50],  # Top 50 teams
        'teams_graph_data': json.dumps(teams_graph_data),
        'recent_solves': recent_solves,
        'top_solvers': top_solvers,
        'total_challenges': total_challenges,
        'freeze_time': freeze_cutoff or (event.state_changed_at if scoreboard_state == 'frozen' else None),
    })
    
    return render(request, 'admin/scoreboard.html', context)


@staff_member_required
def admin_live_scoreboard(request):
    """Admin live scoreboard - always shows real-time data from all active events regardless of freeze/pause/stop"""
    
    # Get all active events (or most recent if none active)
    active_events = Event.objects.filter(is_active=True).order_by('-start_time')
    if not active_events.exists():
        active_events = Event.objects.all().order_by('-start_time')[:5]
    
    # Get selected event from query param or use first active
    event_id = request.GET.get('event')
    if event_id:
        try:
            current_event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            current_event = active_events.first() if active_events.exists() else None
    else:
        current_event = active_events.first() if active_events.exists() else None
    
    if not current_event:
        return render(request, 'admin/live_scoreboard.html', {
            'current_event': None,
            'events_list': [],
            'teams': [],
        })
    
    context = {
        'current_event': current_event,
        'events_list': active_events,
        'is_admin_view': True,
        'is_live_view': True,
    }
    
    # ALWAYS show live data - ignore freeze/pause/stop states
    # Get all teams that have scores in this event - INCLUDE BANNED TEAMS (admin view)
    score_qs = Score.objects.filter(event=current_event)
    team_ids = set(score_qs.values_list('team_id', flat=True))
    
    team_data = []
    for team_id in team_ids:
        try:
            team = Team.objects.get(id=team_id)
        except Team.DoesNotExist:
            continue
        
        # Get the LATEST total_score for this team - NO freeze cutoff
        latest_score = Score.objects.filter(
            team_id=team_id,
            event=current_event
        ).order_by('-created_at').first()
        
        total_score = latest_score.total_score if latest_score else 0
        
        # Count correct submissions - NO freeze cutoff
        submissions_qs = Submission.objects.filter(
            team_id=team_id,
            event=current_event,
            status='correct'
        )
        solved_count = submissions_qs.values('challenge').distinct().count()

        # Compute total penalty points
        penalty_sum = Score.objects.filter(
            team_id=team_id,
            event=current_event,
            score_type='reduction'
        ).aggregate(total=Sum('points'))['total'] or 0
        penalty_points = -penalty_sum if penalty_sum < 0 else 0

        # Compute total earned points
        solved_points_total = submissions_qs.aggregate(total=Sum('points_awarded'))['total'] or 0

        # Hypothetical score without penalties
        score_without_penalty = total_score + penalty_points
        
        # Get last solve time
        last_submission = submissions_qs.order_by('-submitted_at').first()
        
        team_data.append({
            'team': team,
            'total_score': total_score,
            'solved_count': solved_count,
            'penalty_points': penalty_points,
            'score_without_penalty': score_without_penalty,
            'solved_points_total': solved_points_total,
            'last_solve_time': last_submission.submitted_at if last_submission else None,
        })
    
    # Sort by score and time
    team_data.sort(key=lambda x: (-x['total_score'], x['last_solve_time'] or timezone.now()))
    
    # Add ranks
    for idx, entry in enumerate(team_data, 1):
        entry['rank'] = idx
    
    # Get recent solves - INCLUDE BANNED TEAMS, NO freeze cutoff
    recent_solves = Submission.objects.filter(
        event=current_event,
        status='correct',
    ).select_related('team', 'challenge', 'user').order_by('-submitted_at')[:20]
    
    # Get top solvers - NO freeze cutoff
    top_solvers = Submission.objects.filter(
        event=current_event,
        status='correct',
    ).values('user__username').annotate(
        solve_count=Count('id')
    ).order_by('-solve_count')[:10]
    
    # Total challenges
    total_challenges = Challenge.objects.filter(
        event=current_event,
        is_active=True,
        is_visible=True
    ).count()
    
    # Build team graph data with solve history - NO freeze cutoff
    teams_graph_data = []
    for entry in team_data[:20]:
        team = entry['team']
        
        graph_submissions = Submission.objects.filter(
            team=team,
            event=current_event,
            status='correct'
        ).select_related('challenge').order_by('submitted_at')
        
        solves = []
        for submission in graph_submissions:
            solves.append({
                'time': submission.submitted_at.isoformat(),
                'points': submission.points_awarded,
                'challenge': submission.challenge.name
            })
        
        teams_graph_data.append({
            'name': team.name,
            'solves': solves,
            'color': None
        })
    
    context.update({
        'teams': team_data[:50],
        'teams_graph_data': json.dumps(teams_graph_data),
        'recent_solves': recent_solves,
        'top_solvers': top_solvers,
        'total_challenges': total_challenges,
    })
    
    return render(request, 'admin/live_scoreboard.html', context)

