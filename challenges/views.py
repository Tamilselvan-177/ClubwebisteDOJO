from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import models, transaction
from .models import Category, Challenge, ChallengeFile, Hint, HintUnlock
from .serializers import (
    CategorySerializer,
    ChallengeSerializer,
    ChallengeListSerializer,
    ChallengeDetailSerializer,
    ChallengeFileSerializer,
    HintSerializer
)
from accounts.permissions import IsNotBanned
from accounts.utils import get_user_team_for_event
import logging

logger = logging.getLogger(__name__)


class CategoryViewSet(viewsets.ModelViewSet):
    """ViewSet for Category management"""
    queryset = Category.objects.all()
    serializer_class = CategorySerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_permissions(self):
        """
        Admin can create/update/delete, others can only view
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated]
        return [permission() for permission in permission_classes]


class ChallengeFileViewSet(viewsets.ModelViewSet):
    """ViewSet for ChallengeFile management"""
    queryset = ChallengeFile.objects.all()
    serializer_class = ChallengeFileSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter by name if provided
        name = self.request.query_params.get('name', None)
        if name:
            queryset = queryset.filter(name__icontains=name)
        return queryset


class HintViewSet(viewsets.ModelViewSet):
    """ViewSet for Hint management"""
    queryset = Hint.objects.all()
    serializer_class = HintSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter by challenge if provided
        challenge_id = self.request.query_params.get('challenge', None)
        if challenge_id:
            queryset = queryset.filter(challenge_id=challenge_id)
        return queryset.order_by('order', 'created_at')
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsNotBanned])
    def unlock(self, request, pk=None):
        """Unlock a hint by spending points from THIS CHALLENGE ONLY"""
        from submissions.models import Score, Submission
        from django.db.models import Sum
        from django.db import transaction
        
        hint = self.get_object()
        
        # Get team and event
        team = get_user_team_for_event(request.user, hint.challenge.event)
        if not team:
            return Response(
                {'error': 'You must be a member of a team to unlock hints'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if already unlocked
        if HintUnlock.objects.filter(hint=hint, team=team, event=hint.challenge.event).exists():
            return Response(
                {'error': 'Hint already unlocked'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from submissions.services import SubmissionService
        submission_service = SubmissionService()

        # Calculate current challenge-specific balance (awards + reductions)
        # and the effective spendable balance (base points minus penalties).
        challenge_score_query = Score.objects.filter(
            team=team,
            challenge=hint.challenge,
            event=hint.challenge.event
        ).aggregate(total=Sum('points'))

        raw_challenge_score = challenge_score_query['total'] or 0
        penalty_total = submission_service.get_team_penalty(team, hint.challenge, hint.challenge.event)  # negative or 0
        base_points = hint.challenge.get_current_points()
        available_balance = max(hint.challenge.minimum_points, base_points + penalty_total)

        # Spendable balance: either existing challenge score (if already earned)
        # or the available balance (base minus penalties) if not yet earned.
        spendable = max(0, raw_challenge_score, available_balance)

        logger.info(
            f"Team {team.name} checking hint on {hint.challenge.name}: raw_score={raw_challenge_score}, "
            f"available={available_balance}, spendable={spendable}, cost={hint.cost}"
        )

        # Check if team has enough points for THIS CHALLENGE
        if spendable < hint.cost:
            return Response(
                {'error': f'Not enough points for this challenge. You have {spendable}, need {hint.cost}'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Unlock hint and deduct points from THIS CHALLENGE ONLY
        with transaction.atomic():
            # Get current team total score (penalties don't change this)
            current_team_score = submission_service.calculate_team_total_score(team, hint.challenge.event)
            
            # Create unlock record
            HintUnlock.objects.create(
                hint=hint,
                team=team,
                event=hint.challenge.event,
                cost_paid=hint.cost
            )
            
            # Deduct points from challenge score (NOT from team's total earned score)
            new_raw_challenge_score = raw_challenge_score - hint.cost
            new_challenge_score = max(0, new_raw_challenge_score)
            Score.objects.create(
                team=team,
                challenge=hint.challenge,
                event=hint.challenge.event,
                points=-hint.cost,
                score_type='reduction',
                total_score=current_team_score,  # UNCHANGED - penalties don't reduce team total
                reason="Hint penalty",
                notes=f"Penalty for unlocking hint: {hint.text[:50]}"
            )
            
            logger.info(
                f"✓ Hint penalty applied: Team {team.name} spent {hint.cost} points on {hint.challenge.name} "
                f"(raw before: {raw_challenge_score}, spendable before: {spendable}, raw after: {new_raw_challenge_score}, "
                f"clamped after: {new_challenge_score})"
            )
        
        return Response({
            'message': 'Hint unlocked successfully',
            'hint_text': hint.text,
            'cost': hint.cost,
            'challenge_score_before': spendable,
            'challenge_score_after': max(0, spendable - hint.cost)
        })


class ChallengeViewSet(viewsets.ModelViewSet):
    """ViewSet for Challenge management"""
    queryset = Challenge.objects.all()
    serializer_class = ChallengeSerializer
    permission_classes = [permissions.IsAuthenticated, IsNotBanned]
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ChallengeListSerializer
        elif self.action == 'retrieve':
            return ChallengeDetailSerializer
        return ChallengeSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by event
        event_id = self.request.query_params.get('event', None)
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        
        # Filter by category
        category_id = self.request.query_params.get('category', None)
        if category_id:
            queryset = queryset.filter(category_id=category_id)
        
        # Filter by challenge_type
        challenge_type = self.request.query_params.get('type', None)
        if challenge_type:
            queryset = queryset.filter(challenge_type=challenge_type)
        
        # Filter by visibility
        is_visible = self.request.query_params.get('is_visible', None)
        if is_visible is not None:
            queryset = queryset.filter(is_visible=is_visible.lower() == 'true')
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # For non-staff users, only show visible and active challenges
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_visible=True, is_active=True)
            # Also check release_time
            queryset = queryset.filter(
                models.Q(release_time__isnull=True) | models.Q(release_time__lte=timezone.now())
            )
        
        return queryset.select_related('category', 'event', 'author').prefetch_related('files', 'hints')
    
    def get_permissions(self):
        """
        Admin can create/update/delete, authenticated users can view
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated, IsNotBanned]
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['get'])
    def hints(self, request, pk=None):
        """Get hints for a challenge"""
        challenge = self.get_object()
        hints = challenge.hints.filter(is_visible=True).order_by('order')
        serializer = HintSerializer(hints, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def files(self, request, pk=None):
        """Get files for a challenge"""
        challenge = self.get_object()
        files = challenge.files.all()
        serializer = ChallengeFileSerializer(files, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def solvers(self, request, pk=None):
        """List first correct solve per team for this challenge, ordered by time."""
        challenge = self.get_object()
        # All correct submissions ordered by time ascending
        qs = Submission.objects.filter(
            challenge=challenge,
            status='correct'
        ).select_related('team', 'user').order_by('submitted_at')

        seen_team_ids = set()
        entries = []
        for sub in qs:
            if sub.team_id in seen_team_ids:
                continue
            seen_team_ids.add(sub.team_id)
            entries.append({
                'team_id': sub.team_id,
                'team_name': sub.team.name,
                'user_id': sub.user_id,
                'username': sub.user.username,
                'submitted_at': sub.submitted_at,
                'points': getattr(sub, 'points_awarded', 0),
            })

        # Add rank
        for idx, e in enumerate(entries, start=1):
            e['rank'] = idx

        return Response({
            'count': len(entries),
            'results': entries,
        })
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def make_visible(self, request, pk=None):
        """Make challenge visible"""
        challenge = self.get_object()
        challenge.is_visible = True
        challenge.save()
        serializer = self.get_serializer(challenge)
        return Response({
            'message': 'Challenge made visible',
            'challenge': serializer.data
        })
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def make_hidden(self, request, pk=None):
        """Make challenge hidden"""
        challenge = self.get_object()
        challenge.is_visible = False
        challenge.save()
        serializer = self.get_serializer(challenge)
        return Response({
            'message': 'Challenge made hidden',
            'challenge': serializer.data
        })
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def activate(self, request, pk=None):
        """Activate challenge"""
        challenge = self.get_object()
        challenge.is_active = True
        challenge.save()
        serializer = self.get_serializer(challenge)
        return Response({
            'message': 'Challenge activated',
            'challenge': serializer.data
        })
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def deactivate(self, request, pk=None):
        """Deactivate challenge"""
        challenge = self.get_object()
        challenge.is_active = False
        challenge.save()
        serializer = self.get_serializer(challenge)
        return Response({
            'message': 'Challenge deactivated',
            'challenge': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def start_instance(self, request, pk=None):
        """Start a new instance for the user's team"""
        from accounts.utils import get_user_team_for_event
        from events_ctf.models import Event
        from challenges.services import instance_service
        
        # Check authentication
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        # Check if Docker is available
        if instance_service.client is None:
            return Response(
                {'error': 'Docker service unavailable. Contact administrator.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        challenge = self.get_object()
        
        # Only for instance-based challenges
        if challenge.challenge_type != 'instance':
            return Response(
                {'error': 'This is not an instance-based challenge'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get user's team
        try:
            event = Event.objects.get(is_active=True)
        except Event.DoesNotExist:
            return Response(
                {'error': 'No active event'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        team = get_user_team_for_event(request.user, event)
        if not team:
            return Response(
                {'error': 'You are not in a team for this event'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if event is paused or stopped
        if event.contest_state in ['paused', 'stopped']:
            return Response(
                {'error': f'Event is {event.contest_state}. Instances cannot be started.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Start instance
        instance, error = instance_service.start_instance(challenge, team, request.user, event)
        
        if error:
            return Response(
                {'error': error},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Return instance details
        from .instance_serializers import ChallengeInstanceSerializer
        serializer = ChallengeInstanceSerializer(instance, context={'request': request})
        return Response({
            'message': 'Instance started successfully',
            'instance': serializer.data,
            'access_url': instance.access_url,
            'access_port': instance.access_port,
            'flag': instance.flag
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'])
    def stop_instance(self, request, pk=None):
        """Stop an instance for the user's team"""
        from accounts.utils import get_user_team_for_event
        from events_ctf.models import Event
        from challenges.services import instance_service
        from challenges.models import ChallengeInstance
        
        # Check authentication
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        challenge = self.get_object()
        
        # Get user's team
        try:
            event = Event.objects.get(is_active=True)
        except Event.DoesNotExist:
            return Response(
                {'error': 'No active event'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        team = get_user_team_for_event(request.user, event)
        if not team:
            return Response(
                {'error': 'You are not in a team for this event'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the instance
        instance_id = request.data.get('instance_id')
        if instance_id:
            # Specific instance ID provided
            try:
                instance = ChallengeInstance.objects.get(
                    id=instance_id,
                    team=team,
                    challenge=challenge,
                    status='running'
                )
            except ChallengeInstance.DoesNotExist:
                return Response(
                    {'error': 'Instance not found or not active'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Find any running instance for this team+challenge
            instance = ChallengeInstance.objects.filter(
                team=team,
                challenge=challenge,
                status='running'
            ).first()
            
            if not instance:
                return Response(
                    {'error': 'No active instance found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Stop the instance and reduce points
        success, error, points_reduced = instance_service.stop_instance(
            instance,
            reduce_points=True,
            reason="Instance stopped by user"
        )
        
        if not success:
            return Response(
                {'error': error or 'Failed to stop instance'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        response_data = {
            'message': 'Instance stopped successfully'
        }
        
        if points_reduced > 0:
            response_data['points_reduced'] = points_reduced
            response_data['warning'] = f'Challenge points reduced by {points_reduced}.'
        
        return Response(response_data, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def renew_instance(self, request, pk=None):
        """Renew/extend an instance for the user's team"""
        from accounts.utils import get_user_team_for_event
        from events_ctf.models import Event
        from challenges.models import ChallengeInstance
        
        # Check authentication
        if not request.user.is_authenticated:
            return Response(
                {'error': 'Authentication required'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        challenge = self.get_object()
        
        # Get user's team
        try:
            event = Event.objects.get(is_active=True)
        except Event.DoesNotExist:
            return Response(
                {'error': 'No active event'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        team = get_user_team_for_event(request.user, event)
        if not team:
            return Response(
                {'error': 'You are not in a team for this event'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get the instance
        instance_id = request.data.get('instance_id')
        if instance_id:
            # Specific instance ID provided
            try:
                instance = ChallengeInstance.objects.get(
                    id=instance_id,
                    team=team,
                    challenge=challenge,
                    status='running'
                )
            except ChallengeInstance.DoesNotExist:
                return Response(
                    {'error': 'Instance not found or not active'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Find any running instance for this team+challenge
            instance = ChallengeInstance.objects.filter(
                team=team,
                challenge=challenge,
                status='running'
            ).first()
            
            if not instance:
                return Response(
                    {'error': 'No active instance found'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # SECURITY: Check if instance has expired before allowing renewal
        from django.utils import timezone
        if instance.expires_at and instance.expires_at <= timezone.now():
            from challenges.services import instance_service
            # Stop expired instance immediately
            success, error, points_reduced = instance_service.stop_instance(
                instance,
                reduce_points=True,
                reason=f"Instance expired (limit: {challenge.instance_time_limit_minutes} minutes)"
            )
            return Response(
                {'error': 'Instance has expired and has been terminated. Please start a new instance.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Renew the instance
        success, message, new_expiry = instance.renew(request.user)
        
        if not success:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        from django.utils import timezone
        time_remaining = new_expiry - timezone.now()
        minutes = int(time_remaining.total_seconds() / 60)
        
        # Check if event has sound enabled for renewal and get custom sound URL
        play_sound = challenge.event.enable_notification_sounds and challenge.event.sound_on_instance_renewal
        sound_url = None
        
        if play_sound and challenge.event.custom_sound_instance_renewal:
            sound_url = challenge.event.custom_sound_instance_renewal.audio_file.url
        
        return Response({
            'message': message,
            'new_expiry': new_expiry.isoformat(),
            'time_remaining': f'{minutes}m',
            'renewal_count': instance.renewal_count,
            'play_sound': play_sound,
            'sound_url': sound_url
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Submit a flag for a challenge"""
        from submissions.views import SubmissionViewSet
        
        challenge = self.get_object()
        flag = request.data.get('flag', '').strip()
        
        if not flag:
            return Response(
                {'error': 'Flag is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get active event
        from events_ctf.models import Event
        try:
            event = Event.objects.get(is_active=True)
        except Event.DoesNotExist:
            return Response(
                {'error': 'No active event'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Prepare submission data
        submission_data = {
            'challenge_id': challenge.id,
            'event_id': event.id,
            'flag': flag,
            'instance_id': request.data.get('instance_id')
        }
        
        # Use SubmissionViewSet to handle submission
        submission_viewset = SubmissionViewSet()
        submission_viewset.request = request
        submission_viewset.format_kwarg = None
        
        # Create a new request with the submission data
        from rest_framework.request import Request
        from django.http import QueryDict
        
        # Clone the request and update data
        request._full_data = submission_data
        
        return submission_viewset.create(request)


# Template views for frontend
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_http_methods
from django.contrib import messages
from django.db.models import Count, Q, Sum
from events_ctf.models import Event
from accounts.models import TeamMembership
from submissions.models import Submission, Score


@login_required
@require_http_methods(["GET"])
def challenge_list_view(request):
    """Template view for challenges list"""
    # Get current event
    current_event = Event.objects.filter(
        Q(is_active=True) | Q(is_visible=True),
        start_time__lte=timezone.now()
    ).order_by('-start_time').first()
    
    # Get user's team
    user_team = None
    membership = TeamMembership.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('team').first()
    if membership:
        user_team = membership.team
    
    # CHECK IF TEAM IS BANNED - REDIRECT IF BANNED
    if user_team and user_team.is_banned:
        messages.error(request, f'Your team has been banned: {user_team.banned_reason or "No reason provided"}')
        return redirect('dashboard')
    
    context = {
        'current_event': current_event,
        'user_team': user_team,
    }
    
    if current_event and user_team:
        # Get challenges for the event
        challenges = Challenge.objects.filter(
            event=current_event,
            is_active=True,
            is_visible=True
        ).select_related('category').annotate(
            solves=Count('submissions', filter=Q(submissions__status='correct'))
        )
        
        # Get categories with challenge count
        categories = Category.objects.annotate(
            challenge_count=Count('challenges', filter=Q(
                challenges__event=current_event,
                challenges__is_active=True,
                challenges__is_visible=True
            ))
        ).filter(challenge_count__gt=0)
        
        # Mark solved challenges
        solved_challenge_ids = Submission.objects.filter(
            team=user_team,
            event=current_event,
            status='correct'
        ).values_list('challenge_id', flat=True)
        
        from submissions.services import SubmissionService
        submission_service = SubmissionService()
        for challenge in challenges:
            challenge.is_solved = challenge.id in solved_challenge_ids
            # Compute team penalty and effective points for this challenge
            team_penalty = submission_service.get_team_penalty(user_team, challenge, current_event)
            effective_points = challenge.get_current_points() + team_penalty
            effective_points = max(challenge.minimum_points, effective_points)
            challenge.effective_points = effective_points
        
        # Get team stats - use latest total_score
        latest_score = Score.objects.filter(
            team=user_team,
            event=current_event
        ).order_by('-created_at').first()
        team_score = latest_score.total_score if latest_score else 0
        
        solved_count = Submission.objects.filter(
            team=user_team,
            event=current_event,
            status='correct'
        ).values('challenge').distinct().count()
        
        # Get team rank - use latest scores per team
        from django.db.models import OuterRef, Subquery
        latest_scores = Score.objects.filter(
            team_id=OuterRef('team'),
            event=current_event
        ).order_by('-created_at').values('id')[:1]
        
        teams_scores = Score.objects.filter(
            event=current_event,
            id__in=Subquery(latest_scores)
        ).values('team').annotate(
            total=Sum('total_score')
        ).order_by('-total')
        
        team_rank = None
        for idx, entry in enumerate(teams_scores, 1):
            if entry['team'] == user_team.id:
                team_rank = idx
                break
        
        # Get active instances count
        from challenges.models import ChallengeInstance
        active_instances = ChallengeInstance.objects.filter(
            team=user_team,
            status='running'
        ).count()
        
        context.update({
            'challenges': challenges,
            'categories': categories,
            'total_challenges': challenges.count(),
            'solved_count': solved_count,
            'team_score': team_score,
            'team_rank': team_rank,
            'active_instances': active_instances,
        })
    
    return render(request, 'challenges/challenge_list.html', context)


@login_required
@require_http_methods(["GET"])
def challenge_detail_view(request, challenge_id):
    """Template view for challenge detail"""
    challenge = get_object_or_404(
        Challenge.objects.select_related('category', 'event'),
        id=challenge_id,
        is_active=True,
        is_visible=True
    )
    
    # Get user's team
    membership = TeamMembership.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('team').first()
    
    if not membership:
        messages.error(request, 'You need to be in a team to view challenges')
        return redirect('challenges:challenge_list')
    
    user_team = membership.team
    
    # CHECK IF TEAM IS BANNED
    if user_team.is_banned:
        messages.error(request, f'Your team has been banned: {user_team.banned_reason or "No reason provided"}')
        return redirect('dashboard')
    
    # Check if solved
    is_solved = Submission.objects.filter(
        team=user_team,
        challenge=challenge,
        status='correct'
    ).exists()
    
    # Get active instance ONLY if challenge is instance-based
    from challenges.models import ChallengeInstance
    active_instance = None
    time_remaining = None
    minutes_remaining = None
    total_seconds = None
    initial_total_seconds = None
    if challenge.challenge_type == 'instance':
        active_instance = ChallengeInstance.objects.filter(
            team=user_team,
            challenge=challenge,
            status='running'
        ).first()
        
        # REAL-TIME EXPIRY CHECK: Clean up expired instances immediately (don't wait for hourly task)
        if active_instance:
            from django.utils import timezone
            if active_instance.expires_at and active_instance.expires_at <= timezone.now():
                print(f"[SECURITY] Instance {active_instance.instance_id} expired! Cleaning up immediately...")
                from challenges.services import instance_service
                success, error, points_reduced = instance_service.stop_instance(
                    active_instance,
                    reduce_points=True,
                    reason=f"Instance expired (limit: {challenge.instance_time_limit_minutes} minutes)"
                )
                if success:
                    print(f"[SECURITY] Instance cleaned up. Points reduced: {points_reduced}")
                    messages.warning(request, f'⏱️ Your instance time expired. Team penalty applied: -{points_reduced} pts')
                    active_instance = None  # Clear from context
                else:
                    print(f"[ERROR] Failed to clean up expired instance: {error}")
        
        if active_instance and active_instance.expires_at:
            from django.utils import timezone
            # Calculate initial total time when instance was created
            if active_instance.started_at and active_instance.expires_at:
                initial_total_seconds = int((active_instance.expires_at - active_instance.started_at).total_seconds())
            
            time_diff = active_instance.expires_at - timezone.now()
            if time_diff.total_seconds() > 0:
                total_seconds = int(time_diff.total_seconds())
                hours = int(time_diff.total_seconds() // 3600)
                minutes = int((time_diff.total_seconds() % 3600) // 60)
                # Floor minutes for textual display above, but compute a rounded-up minute for buttons
                minutes_remaining = minutes + (hours * 60)  # floored total minutes
                if hours > 0:
                    time_remaining = f"{hours}h {minutes}m"
                else:
                    time_remaining = f"{minutes}m"
            else:
                time_remaining = "Expired"
                minutes_remaining = 0
                total_seconds = 0
    
    # Get renewal information for instance-based challenges
    renewals_available = None
    renewals_used = None
    renewal_limit = None
    if challenge.challenge_type == 'instance' and active_instance:
        renewals_used = active_instance.renewal_count
        renewal_limit = getattr(challenge, 'instance_renewal_limit', 0)
        renewals_available = max(0, renewal_limit - renewals_used)
    
    # Get user submissions
    user_submissions = Submission.objects.filter(
        user=request.user,
        challenge=challenge
    ).order_by('-submitted_at')[:10]
    
    # Get challenge stats
    total_attempts = Submission.objects.filter(challenge=challenge).count()
    correct_attempts = Submission.objects.filter(challenge=challenge, status='correct').count()
    success_rate = (correct_attempts / total_attempts * 100) if total_attempts > 0 else 0
    
    # Get first blood
    first_blood = Submission.objects.filter(
        challenge=challenge,
        status='correct'
    ).select_related('user', 'team').order_by('submitted_at').first()
    
    # Get unlocked hints for this team
    from challenges.models import HintUnlock
    unlocked_hint_ids = HintUnlock.objects.filter(
        team=user_team,
        event=challenge.event,
        hint__challenge=challenge
    ).values_list('hint_id', flat=True)
    
    # Get team's penalty for this challenge
    from submissions.services import SubmissionService
    submission_service = SubmissionService()
    team_penalty = submission_service.get_team_penalty(user_team, challenge, challenge.event)
    effective_points = challenge.get_current_points() + team_penalty  # penalty is negative
    effective_points = max(challenge.minimum_points, effective_points)  # floor at minimum
    
    # Compute display minutes rounded up to avoid showing "healthy (0 min)" when seconds remain
    display_minutes_remaining = None
    if total_seconds is not None:
        from math import ceil
        display_minutes_remaining = max(0, ceil(total_seconds / 60))

    # Precompute renewal threshold in seconds to simplify template logic
    renewal_threshold_seconds = None
    if challenge.challenge_type == 'instance' and getattr(challenge, 'instance_renewal_min_threshold', None) is not None:
        try:
            renewal_threshold_seconds = int(challenge.instance_renewal_min_threshold) * 60
        except Exception:
            renewal_threshold_seconds = None

    context = {
        'challenge': challenge,
        'is_solved': is_solved,
        'active_instance': active_instance,
        'time_remaining': time_remaining,
        'minutes_remaining': minutes_remaining,
        'total_seconds': total_seconds,
        'initial_total_seconds': initial_total_seconds,
        'display_minutes_remaining': display_minutes_remaining,
        'renewal_threshold_seconds': renewal_threshold_seconds,
        'user_submissions': user_submissions,
        'total_attempts': total_attempts,
        'success_rate': round(success_rate, 1),
        'first_blood': first_blood,
        'team': user_team,
        'unlocked_hint_ids': list(unlocked_hint_ids),
        'team_penalty': team_penalty,
        'effective_points': effective_points,
        'renewals_available': renewals_available,
        'renewals_used': renewals_used,
        'renewal_limit': renewal_limit,
    }
    
    return render(request, 'challenges/challenge_detail.html', context)
