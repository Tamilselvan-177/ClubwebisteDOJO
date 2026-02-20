"""
Views for submission and scoring.
"""
import logging
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from django.core.cache import cache
from .models import Submission, Score, Violation
from .serializers import (
    SubmissionSerializer,
    SubmissionCreateSerializer,
    SubmissionListSerializer,
    ScoreSerializer,
    ViolationSerializer
)
from .services import submission_service
from challenges.models import Challenge, ChallengeInstance
from events_ctf.models import Event
from accounts.permissions import IsNotBanned, IsTeamNotBanned
from accounts.utils import get_user_team_for_event

# Rate limiting
SUBMISSION_RATE_LIMIT = 10  # submissions per minute per team
logger = logging.getLogger(__name__)


class SubmissionViewSet(viewsets.ModelViewSet):
    """
    ViewSet for flag submissions.
    """
    queryset = Submission.objects.all()
    serializer_class = SubmissionSerializer
    permission_classes = [permissions.IsAuthenticated, IsNotBanned, IsTeamNotBanned]
    
    def get_serializer_class(self):
        if self.action == 'create':
            return SubmissionCreateSerializer
        elif self.action == 'list':
            return SubmissionListSerializer
        return SubmissionSerializer
    
    def get_queryset(self):
        """
        Users can only see submissions for their teams.
        Admins can see all submissions.
        """
        queryset = super().get_queryset()
        
        if not self.request.user.is_staff:
            user_teams = self.request.user.teams.all()
            queryset = queryset.filter(team__in=user_teams)
        
        # Filter by challenge
        challenge_id = self.request.query_params.get('challenge', None)
        if challenge_id:
            queryset = queryset.filter(challenge_id=challenge_id)
        
        # Filter by event
        event_id = self.request.query_params.get('event', None)
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        
        # Filter by status
        status_filter = self.request.query_params.get('status', None)
        if status_filter:
            queryset = queryset.filter(status=status_filter)
        
        return queryset.select_related('challenge', 'team', 'event', 'user', 'instance').order_by('-submitted_at')
    
    def _check_rate_limit(self, team):
        """
        Check rate limit for submissions.
        Returns (allowed, error_message)
        """
        cache_key = f'submission_rate_limit_{team.id}'
        try:
            count = cache.get(cache_key, 0)
            if count >= SUBMISSION_RATE_LIMIT:
                return False, f"Rate limit exceeded. Maximum {SUBMISSION_RATE_LIMIT} submissions per minute."

            # Increment counter (expires in 60 seconds)
            cache.set(cache_key, count + 1, 60)
            return True, None
        except Exception as exc:  # Gracefully degrade if cache/redis is down
            logger.warning('Rate limit cache unavailable, allowing submission. Error: %s', exc)
            return True, None
    
    def create(self, request):
        """
        Submit a flag.
        POST /api/submissions/
        """
        serializer = SubmissionCreateSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        challenge_id = serializer.validated_data['challenge_id']
        event_id = serializer.validated_data['event_id']
        submitted_flag = serializer.validated_data['flag']
        instance_id = serializer.validated_data.get('instance_id')
        
        try:
            challenge = Challenge.objects.get(id=challenge_id)
            event = Event.objects.get(id=event_id)
        except Challenge.DoesNotExist:
            return Response(
                {'error': 'Challenge not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Event.DoesNotExist:
            return Response(
                {'error': 'Event not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # AUTO-STOP CHECK: If event has passed its end_time, auto-stop it
        event.auto_stop_if_expired()
        
        # Check event state - flag submission only allowed in running/resumed state
        if not event.can_submit_flags():
            return Response(
                {'error': f'Flag submission is not allowed. Event state: {event.get_contest_state_display()}'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get user's team
        team = get_user_team_for_event(request.user, event)
        if not team:
            return Response(
                {'error': 'You must be a member of a team to submit flags'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # REAL-TIME EXPIRY CHECK: Clean up any expired instances immediately before flag submission
        if challenge.challenge_type == 'instance':
            from django.utils import timezone
            from challenges.services import instance_service
            # Strict boundary check: treat 00m 00s as expired (lte instead of lt)
            expired_instances = ChallengeInstance.objects.filter(
                team=team,
                challenge=challenge,
                status='running',
                expires_at__lte=timezone.now()
            )
            for exp_instance in expired_instances:
                print(f"[SECURITY] Expired instance {exp_instance.instance_id} detected during submission. Cleaning up...")
                success, error, points_reduced = instance_service.stop_instance(
                    exp_instance,
                    reduce_points=True,
                    reason=f"Instance expired (limit: {challenge.instance_time_limit_minutes} minutes)"
                )
                if success:
                    print(f"[SECURITY] Instance cleaned up. Points reduced: {points_reduced}")
        
        # Check rate limit
        allowed, error_msg = self._check_rate_limit(team)
        if not allowed:
            return Response(
                {'error': error_msg},
                status=status.HTTP_429_TOO_MANY_REQUESTS
            )
        
        # Get instance if provided
        instance = None
        if instance_id:
            try:
                instance = ChallengeInstance.objects.get(
                    instance_id=instance_id,
                    team=team,
                    challenge=challenge,
                    status='running'
                )
            except ChallengeInstance.DoesNotExist:
                return Response(
                    {'error': 'Instance not found or not active'},
                    status=status.HTTP_404_NOT_FOUND
                )
            # Hard-stop if instance expired at boundary but status hasn't flipped yet
            from django.utils import timezone
            if instance.expires_at and instance.expires_at <= timezone.now():
                from challenges.services import instance_service
                success, error, points_reduced = instance_service.stop_instance(
                    instance,
                    reduce_points=True,
                    reason=f"Instance expired (limit: {challenge.instance_time_limit_minutes} minutes)"
                )
                return Response(
                    {'error': 'Instance expired. Please renew or start a new instance.'},
                    status=status.HTTP_403_FORBIDDEN
                )
        
        with transaction.atomic():
            # Require an active instance for instance-based challenges
            if challenge.challenge_type == 'instance' and instance is None:
                return Response(
                    {'error': 'Active instance required to submit flag. Please start or renew your instance.'},
                    status=status.HTTP_403_FORBIDDEN
                )

            # Check if challenge is already solved by this team (prevent re-submissions)
            already_solved = Submission.objects.filter(
                challenge=challenge,
                team=team,
                event=event,
                status='correct'
            ).exists()
            
            if already_solved:
                return Response({
                    'error': 'Challenge already solved! You cannot submit again.',
                    'message': 'You have already solved this challenge correctly.'
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Check for duplicate submission
            is_duplicate, existing = submission_service.check_duplicate_submission(
                team, challenge, event, submitted_flag
            )
            
            if is_duplicate:
                submission = Submission.objects.create(
                    challenge=challenge,
                    event=event,
                    team=team,
                    user=request.user,
                    instance=instance,
                    flag=submitted_flag,
                    flag_hash=hashlib.sha256(submitted_flag.strip().encode()).hexdigest(),
                    status='duplicate',
                    points_awarded=0,
                    points_at_submission=challenge.get_current_points(),
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
                
                serializer = SubmissionSerializer(submission, context={'request': request})
                return Response({
                    'message': 'Flag already submitted correctly',
                    'submission': serializer.data
                }, status=status.HTTP_200_OK)
            
            # Check for copied flag (anti-cheat)
            is_copied, matched_instance, evidence = submission_service.check_copied_flag(
                submitted_flag, team, event, challenge
            )
            
            if is_copied:
                # Create violation and ban team
                violation = submission_service.create_violation(
                    team, event, challenge, None, matched_instance,
                    'copied_flag', evidence
                )
                
                # Ban team with event context for ban sound notification
                submission_service.ban_team(
                    team, 
                    "Copied flag from another team's instance",
                    event=event
                )
                
                # Destroy the instance (no point reduction - team is banned)
                if instance:
                    from challenges.services import instance_service
                    instance_service.stop_instance(instance, reduce_points=False)
                
                submission = Submission.objects.create(
                    challenge=challenge,
                    event=event,
                    team=team,
                    user=request.user,
                    instance=instance,
                    flag=submitted_flag,
                    status='invalid',
                    points_awarded=0,
                    points_at_submission=challenge.get_current_points(),
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    admin_notes=f'Copied flag violation. Matched instance: {matched_instance.instance_id}'
                )
                
                return Response({
                    'error': 'Cheating detected. Team has been banned.',
                    'violation_id': violation.id
                }, status=status.HTTP_403_FORBIDDEN)
            
            # Validate flag
            is_valid, is_correct, error_msg = submission_service.validate_flag(
                submitted_flag, challenge, instance
            )
            
            if not is_valid:
                return Response(
                    {'error': error_msg},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            points_at_submission = challenge.get_current_points()
            submission_status = 'correct' if is_correct else 'incorrect'
            points_awarded = 0
            
            # Track submission for anomaly detection
            from .anomaly_detection import AnomalyDetector
            anomalies = AnomalyDetector.track_submission_attempt(
                team, challenge, event, is_correct
            )
            
            # Create submission record
            submission = Submission.objects.create(
                challenge=challenge,
                event=event,
                team=team,
                user=request.user,
                instance=instance,
                flag=submitted_flag,
                status=submission_status,
                points_awarded=points_awarded,
                points_at_submission=points_at_submission,
                ip_address=self._get_client_ip(request),
                user_agent=request.META.get('HTTP_USER_AGENT', '')
            )
            
            if is_correct:
                # If scoreboard is frozen, do not apply points
                if getattr(event, 'is_scoreboard_frozen', False):
                    submission.points_awarded = 0
                    submission.save(update_fields=['points_awarded'])
                    # Destroy instance if instance-based challenge (no penalty)
                    if instance:
                        from challenges.services import instance_service
                        instance_service.stop_instance(instance, reduce_points=False)
                    # Notify without points
                    try:
                        from notifications.services import notification_service
                        notification_service.notify_submission_result(
                            submission,
                            is_correct=True,
                            points_awarded=0,
                            is_first_blood=False
                        )
                    except Exception as e:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.error(f"Failed to send submission notification: {e}")
                    serializer = SubmissionSerializer(submission, context={'request': request})
                    return Response({
                        'message': 'Correct flag recorded, but scoreboard is frozen. No points applied.',
                        'submission': serializer.data,
                        'points_awarded': 0,
                        'is_first_blood': False,
                        'first_blood_sound_url': None,
                        'status': 'correct'
                    }, status=status.HTTP_201_CREATED)
                
                # Award points (normal)
                points = submission_service.calculate_points(challenge, event, team)
                submission.points_awarded = points
                submission.save(update_fields=['points_awarded'])
                
                score = submission_service.award_points(team, challenge, event, submission, points)
                
                # Send notification
                is_first_blood = submission.is_first_blood()
                try:
                    from notifications.services import notification_service
                    notification_service.notify_submission_result(
                        submission, 
                        is_correct=True, 
                        points_awarded=points, 
                        is_first_blood=is_first_blood
                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send submission notification: {e}")
                
                # Destroy instance if instance-based challenge (NO point reduction for correct flag)
                if instance:
                    from challenges.services import instance_service
                    instance_service.stop_instance(instance, reduce_points=False)
                
                # Get first blood sound URL if applicable
                first_blood_sound_url = None
                if is_first_blood and event.enable_notification_sounds and event.sound_on_challenge_correct:
                    if event.custom_sound_challenge_correct:
                        first_blood_sound_url = event.custom_sound_challenge_correct.audio_file.url
                
                serializer = SubmissionSerializer(submission, context={'request': request})
                return Response({
                    'message': 'Correct flag! Points awarded.',
                    'submission': serializer.data,
                    'points_awarded': points,
                    'is_first_blood': is_first_blood,
                    'first_blood_sound_url': first_blood_sound_url,
                    'status': 'correct'
                }, status=status.HTTP_201_CREATED)
            
            else:
                # Wrong flag - if frozen, no penalties; still destroy instance
                if getattr(event, 'is_scoreboard_frozen', False):
                    reduction = 0
                else:
                    reduction = submission_service.reduce_points_on_wrong_submission(
                        team, challenge, event, submission
                    )
                
                # Send notification
                try:
                    from notifications.services import notification_service
                    notification_service.notify_submission_result(
                        submission, 
                        is_correct=False
                    )
                except Exception as e:
                    import logging
                    logger = logging.getLogger(__name__)
                    logger.error(f"Failed to send submission notification: {e}")
                
                # Destroy instance if instance-based challenge AND reduce points
                if instance:
                    from challenges.services import instance_service
                    success, error, points_reduced = instance_service.stop_instance(
                        instance,
                        reduce_points=False,
                        reason="Instance destroyed due to wrong flag submission"
                    )
                
                serializer = SubmissionSerializer(submission, context={'request': request})
                return Response({
                    'message': 'Incorrect flag. Instance destroyed.' + (' Scoreboard is frozen; no penalties applied.' if getattr(event, 'is_scoreboard_frozen', False) else ' Team-only penalty applied.'),
                    'submission': serializer.data,
                    'points_reduced': reduction,
                    'status': 'incorrect'
                }, status=status.HTTP_200_OK)
    
    def _get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
    
    @action(detail=False, methods=['get'])
    def my_submissions(self, request):
        """
        Get current user's submissions.
        GET /api/submissions/my_submissions/
        """
        user_teams = request.user.teams.all()
        submissions = Submission.objects.filter(team__in=user_teams).order_by('-submitted_at')
        
        # Apply filters
        challenge_id = request.query_params.get('challenge', None)
        if challenge_id:
            submissions = submissions.filter(challenge_id=challenge_id)
        
        event_id = request.query_params.get('event', None)
        if event_id:
            submissions = submissions.filter(event_id=event_id)
        
        serializer = SubmissionListSerializer(submissions, many=True, context={'request': request})
        return Response(serializer.data)


class ScoreViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing scores (read-only).
    """
    queryset = Score.objects.all()
    serializer_class = ScoreSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        if not self.request.user.is_staff:
            user_teams = self.request.user.teams.all()
            queryset = queryset.filter(team__in=user_teams)
        
        # Filter by event
        event_id = self.request.query_params.get('event', None)
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        
        # Filter by team
        team_id = self.request.query_params.get('team', None)
        if team_id and self.request.user.is_staff:
            queryset = queryset.filter(team_id=team_id)
        
        return queryset.select_related('team', 'challenge', 'event').order_by('-created_at')


class ViolationViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing violations (read-only for non-staff).
    """
    queryset = Violation.objects.all()
    serializer_class = ViolationSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        if not self.request.user.is_staff:
            # Users can only see violations for their teams
            user_teams = self.request.user.teams.all()
            queryset = queryset.filter(team__in=user_teams)
        
        # Filter by event
        event_id = self.request.query_params.get('event', None)
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        
        # Filter by resolved status
        is_resolved = self.request.query_params.get('is_resolved', None)
        if is_resolved is not None:
            queryset = queryset.filter(is_resolved=is_resolved.lower() == 'true')
        
        return queryset.select_related('team', 'challenge', 'event').order_by('-created_at')
