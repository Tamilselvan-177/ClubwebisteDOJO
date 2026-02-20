"""
Template views for frontend pages.
"""
from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required
from django.db.models import Q, Count, Sum, Case, When, IntegerField, Max
from django.utils import timezone
from django.core import serializers
import json
from events_ctf.models import Event
from challenges.models import Challenge, ChallengeInstance, HintUnlock
from submissions.models import Submission, Score
from accounts.models import Team, TeamMembership


def index(request):
    """Home page - redirect to dashboard"""
    if request.user.is_authenticated:
        return redirect('/dojo/dashboard/')
    return redirect('/dojo/accounts/login/')


@login_required
def dashboard(request):
    """User dashboard with stats and active challenges"""
    # Get current event (most recent active event)
    current_event = Event.objects.filter(
        Q(is_active=True) | Q(is_visible=True),
        start_time__lte=timezone.now()
    ).order_by('-start_time').first()
    
    if not current_event:
        return render(request, 'core/dashboard.html', {'current_event': None})
    
    # Check if user's team is banned
    is_team_banned = False
    ban_reason = ""
    banned_team = request.user.teams.filter(is_banned=True).first()
    if banned_team:
        is_team_banned = True
        ban_reason = banned_team.banned_reason or "Your team has been banned from this competition."
    
    # Get user's team for current event (only non-banned)
    user_teams = request.user.teams.filter(is_banned=False)
    team = user_teams.first()  # Get first active team
    
    # Initialize context
    context = {
        'current_event': current_event,
        'user_team': team,
        'is_team_banned': is_team_banned,
        'ban_reason': ban_reason,
    }
    
    if team:
        # Get team statistics - use latest total_score not sum
        latest_score = Score.objects.filter(
            team=team, 
            event=current_event
        ).order_by('-created_at').first()
        total_score = latest_score.total_score if latest_score else 0
        
        # Count solved challenges
        solved_challenges = Submission.objects.filter(
            team=team,
            event=current_event,
            status='correct'
        ).values('challenge').distinct().count()
        
        # Count active instances
        active_instances = ChallengeInstance.objects.filter(
            team=team,
            event=current_event,
            status__in=['running', 'starting']
        ).count()
        
        # Get team rank (position in scoreboard) - EXCLUDE BANNED TEAMS
        team_ids = set(Score.objects.filter(
            event=current_event,
            team__is_banned=False  # Exclude banned teams
        ).values_list('team_id', flat=True))
        
        team_scores = {}
        for tid in team_ids:
            latest = Score.objects.filter(
                team_id=tid,
                event=current_event
            ).order_by('-created_at').first()
            if latest:
                team_scores[tid] = latest.total_score
        
        # Sort teams by score (descending)
        sorted_teams = sorted(team_scores.items(), key=lambda x: x[1], reverse=True)
        team_rank = next((i+1 for i, (tid, _) in enumerate(sorted_teams) if tid == team.id), None)
        
        context.update({
            'total_score': total_score,
            'solved_count': solved_challenges,
            'active_instances': active_instances,
            'team_rank': team_rank,
        })
        
        # Get active challenges for user's team
        user_solved = Submission.objects.filter(
            team=team,
            event=current_event,
            status='correct'
        ).values_list('challenge_id', flat=True).distinct()
        
        active_challenges = Challenge.objects.filter(
            event=current_event,
            is_visible=True,
            is_active=True
        ).exclude(
            id__in=user_solved
        ).select_related('category').order_by('-points')[:10]
        
        context['active_challenges'] = active_challenges
        
        # Get active instances
        instances = ChallengeInstance.objects.filter(
            team=team,
            event=current_event
        ).select_related('challenge').order_by('-started_at')[:5]
        
        context['team_instances'] = instances
        
        # Get team submissions (recent)
        recent_submissions = Submission.objects.filter(
            team=team,
            event=current_event
        ).select_related('challenge', 'user').order_by('-submitted_at')[:10]
        
        context['recent_submissions'] = recent_submissions
        
        # Team Member Activity (solve/attempt/hint)
        activities = []
        # Submissions as activities
        subs = Submission.objects.filter(
            team=team,
            event=current_event
        ).select_related('challenge', 'user').order_by('-submitted_at')[:20]
        for s in subs:
            activities.append({
                'type': 'solve' if s.status == 'correct' else ('attempt' if s.status == 'incorrect' else 'attempt'),
                'member_name': getattr(s.user, 'username', 'Unknown'),
                'challenge_name': s.challenge.name,
                'timestamp': s.submitted_at,
            })
        
        # Hint unlocks as activities
        hints = HintUnlock.objects.filter(
            team=team,
            event=current_event
        ).select_related('hint__challenge').order_by('-unlocked_at')[:20]
        for h in hints:
            activities.append({
                'type': 'hint',
                'member_name': team.name,  # Team-level action
                'challenge_name': h.hint.challenge.name,
                'timestamp': h.unlocked_at,
            })
        
        # Sort combined activities by timestamp desc and trim
        activities.sort(key=lambda a: a['timestamp'] or timezone.now(), reverse=True)
        context['team_member_activity'] = activities[:20]
        
        # Get top teams (scoreboard) - EXCLUDE BANNED TEAMS
        top_teams = []
        for team_id, total_score in sorted_teams[:10]:
            try:
                t = Team.objects.get(id=team_id, is_banned=False)
                top_teams.append({'team': t, 'score': total_score})
            except Team.DoesNotExist:
                pass
        
        context['top_teams'] = top_teams
    
    # Get event stats - EXCLUDE BANNED TEAMS
    event_stats = {
        'total_challenges': Challenge.objects.filter(
            event=current_event,
            is_visible=True
        ).count(),
        'total_submissions': Submission.objects.filter(
            event=current_event,
            team__is_banned=False  # Exclude banned teams
        ).count(),
        'correct_submissions': Submission.objects.filter(
            event=current_event,
            status='correct',
            team__is_banned=False  # Exclude banned teams
        ).count(),
        'total_teams': Team.objects.filter(
            is_banned=False
        ).count(),
    }
    
    context['event_stats'] = event_stats
    
    return render(request, 'core/dashboard.html', context)


@login_required
def scoreboard(request):
    """Scoreboard page with team rankings"""
    # Get current event
    current_event = Event.objects.filter(
        Q(is_active=True) | Q(is_visible=True),
        start_time__lte=timezone.now()
    ).order_by('-start_time').first()
    
    context = {
        'current_event': current_event,
        'scoreboard_state': current_event.scoreboard_state if current_event else 'hidden',
        'is_scoreboard_frozen': getattr(current_event, 'is_scoreboard_frozen', False) if current_event else False,
    }
    
    if current_event:
        freeze_cutoff = current_event.scoreboard_frozen_at if getattr(current_event, 'is_scoreboard_frozen', False) else None
        scoreboard_state = current_event.scoreboard_state
        # If explicitly frozen, prefer frozen snapshot view regardless of scoreboard_state
        if getattr(current_event, 'is_scoreboard_frozen', False):
            from events_ctf.models import ScoreboardSnapshot
            snapshot = ScoreboardSnapshot.objects.filter(event=current_event).order_by('-created_at').first()
            if snapshot:
                context.update({
                    'teams': snapshot.snapshot.get('teams', []),
                    'teams_graph_data': json.dumps(snapshot.snapshot.get('teams_graph_data', [])),
                    'user_team': None,
                    'user_rank': None,
                    'user_team_score': 0,
                    'user_solved_count': 0,
                    'recent_solves': Submission.objects.filter(
                        event=current_event,
                        status='correct',
                        submitted_at__lte=current_event.scoreboard_frozen_at,
                        team__is_banned=False
                    ).select_related('team', 'challenge', 'user').order_by('-submitted_at')[:20],
                    'top_solvers': Submission.objects.filter(
                        event=current_event,
                        status='correct',
                        submitted_at__lte=current_event.scoreboard_frozen_at,
                        team__is_banned=False
                    ).values('user__username').annotate(
                        solve_count=Count('id')
                    ).order_by('-solve_count')[:10],
                    'total_challenges': Challenge.objects.filter(
                        event=current_event,
                        is_active=True,
                        is_visible=True
                    ).count(),
                    'is_team_banned': False,
                    'ban_reason': '',
                    'freeze_time': current_event.scoreboard_frozen_at,
                })
                return render(request, 'core/scoreboard.html', context)
        if scoreboard_state == 'hidden':
            context.update({
                'is_team_banned': False,
                'ban_reason': '',
            })
            return render(request, 'core/scoreboard.html', context)
        # Get user's team
        user_team = None
        is_team_banned = False
        ban_reason = ""
        
        membership = request.user.teams.filter(is_banned=False).first()
        if membership:
            user_team = membership
        else:
            # Check if user's team is banned
            banned_team = request.user.teams.filter(is_banned=True).first()
            if banned_team:
                is_team_banned = True
                ban_reason = banned_team.banned_reason or "Your team has been banned from this competition."
        
        # Get all teams that have scores in this event - EXCLUDE BANNED TEAMS
        score_qs = Score.objects.filter(
            event=current_event,
            team__is_banned=False  # Exclude banned teams
        )
        if freeze_cutoff:
            score_qs = score_qs.filter(created_at__lte=freeze_cutoff)
        team_ids = set(score_qs.values_list('team_id', flat=True))
        
        team_data = []
        for team_id in team_ids:
            team = Team.objects.get(id=team_id)
            
            # Get the LATEST total_score for this team in this event
            latest_score_qs = Score.objects.filter(
                team_id=team_id,
                event=current_event
            )
            if freeze_cutoff:
                latest_score_qs = latest_score_qs.filter(created_at__lte=freeze_cutoff)
            latest_score = latest_score_qs.order_by('-created_at').first()
            
            total_score = latest_score.total_score if latest_score else 0
            
            # Count correct submissions
            submissions_qs = Submission.objects.filter(
                team_id=team_id,
                event=current_event,
                status='correct'
            )
            if freeze_cutoff:
                submissions_qs = submissions_qs.filter(submitted_at__lte=freeze_cutoff)
            solved_count = submissions_qs.values('challenge').distinct().count()

            # Compute total penalty points (sum of reductions)
            penalty_qs = Score.objects.filter(
                team_id=team_id,
                event=current_event,
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
        
        # Get user team stats
        user_rank = None
        user_team_score = 0
        user_solved_count = 0
        if user_team:
            for entry in team_data:
                if entry['team'].id == user_team.id:
                    user_rank = entry['rank']
                    user_team_score = entry['total_score']
                    user_solved_count = entry['solved_count']
                    break
        
        # Get recent solves (EXCLUDE BANNED TEAMS)
        # If frozen, only show solves before freeze time
        recent_solves_qs = Submission.objects.filter(
            event=current_event,
            status='correct',
            team__is_banned=False  # Exclude banned teams
        ).select_related('team', 'challenge', 'user')
        
        if freeze_cutoff:
            recent_solves_qs = recent_solves_qs.filter(submitted_at__lte=freeze_cutoff)
        elif scoreboard_state == 'frozen' and current_event.state_changed_at:
            recent_solves_qs = recent_solves_qs.filter(submitted_at__lte=current_event.state_changed_at)
        
        recent_solves = recent_solves_qs.order_by('-submitted_at')[:20]
        
        # Get top solvers (EXCLUDE BANNED TEAMS)
        top_solvers_qs = Submission.objects.filter(
            event=current_event,
            status='correct',
            team__is_banned=False  # Exclude banned teams
        )
        if freeze_cutoff:
            top_solvers_qs = top_solvers_qs.filter(submitted_at__lte=freeze_cutoff)
        top_solvers = top_solvers_qs.values('user__username').annotate(
            solve_count=Count('id')
        ).order_by('-solve_count')[:10]
        
        # Total challenges
        total_challenges = Challenge.objects.filter(
            event=current_event,
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
                event=current_event,
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
            'teams_graph_data': json.dumps(teams_graph_data),  # Convert to JSON string
            'user_team': user_team,
            'user_rank': user_rank,
            'user_team_score': user_team_score,
            'user_solved_count': user_solved_count,
            'recent_solves': recent_solves,
            'top_solvers': top_solvers,
            'total_challenges': total_challenges,
            'is_team_banned': is_team_banned,
            'ban_reason': ban_reason,
            'freeze_time': freeze_cutoff or (current_event.state_changed_at if scoreboard_state == 'frozen' else None),
        })
    
    return render(request, 'core/scoreboard.html', context)


def about(request):
    """About page view - redirect to dashboard"""
    return redirect('/dojo/dashboard/')


def rules(request):
    """Rules page view"""
    return render(request, 'core/rules.html')
