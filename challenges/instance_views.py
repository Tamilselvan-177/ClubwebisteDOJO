"""
Views for challenge instance management.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from .models import Challenge, ChallengeInstance
from .serializers import ChallengeSerializer
from .instance_serializers import ChallengeInstanceSerializer, ChallengeInstanceListSerializer
from .services import instance_service
from accounts.permissions import IsNotBanned, IsTeamMember
from accounts.utils import get_user_team_for_event


class ChallengeInstanceViewSet(viewsets.ModelViewSet):
    """
    ViewSet for challenge instance management.
    Teams can start, stop, and view their instances.
    """
    queryset = ChallengeInstance.objects.all()
    serializer_class = ChallengeInstanceSerializer
    permission_classes = [permissions.IsAuthenticated, IsNotBanned]
    lookup_field = 'instance_id'
    
    def get_serializer_class(self):
        if self.action == 'list':
            return ChallengeInstanceListSerializer
        return ChallengeInstanceSerializer
    
    def get_queryset(self):
        """
        Users can only see instances for their teams.
        Admins can see all instances.
        """
        queryset = super().get_queryset()
        
        # Filter by team (user's teams)
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
        
        # Filter by team
        team_id = self.request.query_params.get('team', None)
        if team_id and self.request.user.is_staff:
            queryset = queryset.filter(team_id=team_id)
        
        return queryset.select_related('challenge', 'team', 'event', 'started_by').order_by('-started_at')
    
    def _reduce_challenge_points(self, challenge, event, team, reason="Instance destroyed"):
        """
        Reduce challenge points when an instance is destroyed.
        For dynamic scoring, we increment solve_count to simulate a solve,
        which naturally reduces points. For static scoring, we reduce points directly.
        Points cannot go below minimum_points.
        """
        from submissions.models import Score
        
        current_points = challenge.get_current_points()
        
        # For dynamic scoring (decay > 0), increment solve_count to reduce points
        # For static scoring (decay == 0), reduce points by a fixed percentage
        if challenge.decay > 0:
            # Dynamic scoring: increment solve_count to trigger point reduction
            challenge.solve_count += 1
            challenge.save(update_fields=['solve_count'])
            new_points = challenge.get_current_points()
            actual_reduction = current_points - new_points
        else:
            # Static scoring: reduce by 10% (minimum 1 point)
            reduction_amount = max(1, int(current_points * 0.10))
            new_points = max(challenge.minimum_points, current_points - reduction_amount)
            actual_reduction = current_points - new_points
            
            if actual_reduction > 0:
                # For static scoring, we need to track the reduction differently
                # We'll create a Score entry to log it, but don't modify challenge.points directly
                # as it would affect all teams. Instead, we'll note it in the score entry.
                pass
        
        if actual_reduction > 0:
            # Create score entry to log the reduction (team-specific for audit)
            # Note: This doesn't affect team's score, just logs the challenge point reduction
            Score.objects.create(
                team=team,  # Team that caused the reduction
                challenge=challenge,
                event=event,
                points=-actual_reduction,
                score_type='reduction',
                total_score=max(0, current_points - actual_reduction),
                reason=reason,
                notes=f"Challenge points reduced due to instance destruction. Previous: {current_points}, New: {new_points}"
            )
        
        return actual_reduction
    
    @action(detail=False, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsNotBanned])
    def start(self, request):
        """
        Start a new instance for a challenge.
        POST /api/instances/start/
        Body: { "challenge_id": 1, "event_id": 1 }
        
        If user already has an active instance, it is destroyed and challenge points are reduced.
        """
        challenge_id = request.data.get('challenge_id')
        event_id = request.data.get('event_id')
        
        if not challenge_id or not event_id:
            return Response(
                {'error': 'challenge_id and event_id are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            challenge = Challenge.objects.get(id=challenge_id)
            from events_ctf.models import Event
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
        
        # Check event state - instance creation only allowed in running/resumed/paused state
        if not event.can_create_instances():
            return Response(
                {'error': f'Instance creation is not allowed. Event state: {event.get_contest_state_display()}'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get user's team for this event
        team = get_user_team_for_event(request.user, event)
        if not team:
            return Response(
                {'error': 'You must be a member of a team to start instances'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if team is banned
        if team.is_banned:
            return Response(
                {'error': 'Your team is banned'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check instance limit
        can_start, reason = instance_service.can_start_instance(challenge, team)
        if not can_start:
            return Response(
                {'error': reason},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check if user already has an active instance for this challenge
        # (per requirement: "If a member who already has an active instance starts another,
        # their previous instance is destroyed and challenge points are reduced")
        user_instances = ChallengeInstance.objects.filter(
            challenge=challenge,
            team=team,
            started_by=request.user,
            status='running'
        )
        
        points_reduced = 0
        destroyed_instances = []
        
        if user_instances.exists():
            # Destroy previous instances and reduce points
            with transaction.atomic():
                for old_instance in user_instances:
                    success, error, reduction = instance_service.stop_instance(
                        old_instance,
                        reduce_points=True,
                        reason="Previous instance destroyed: User started new instance"
                    )
                    destroyed_instances.append(old_instance.instance_id)
                    points_reduced += reduction
        
        # Start new instance
        with transaction.atomic():
            instance, error = instance_service.start_instance(
                challenge, team, request.user, event
            )
            
            if error:
                return Response(
                    {'error': error},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        response_data = {
            'message': 'Instance started successfully',
            'instance': ChallengeInstanceSerializer(instance, context={'request': request}).data
        }
        
        if points_reduced > 0:
            response_data['warning'] = f'Previous instance(s) destroyed. Challenge points reduced by {points_reduced}.'
            response_data['destroyed_instances'] = destroyed_instances
            response_data['points_reduced'] = points_reduced
        elif user_instances.exists():
            # Check if any challenge has stop penalty enabled
            any_penalty_enabled = any(inst.challenge.reduce_points_on_stop for inst in user_instances)
            if not any_penalty_enabled:
                response_data['info'] = 'Previous instance(s) destroyed. No penalty applied (stop penalty disabled for this challenge).'
            else:
                response_data['info'] = 'Previous instance(s) destroyed. No penalty applied (challenge already solved or scoreboard frozen).'
        
        return Response(response_data, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsNotBanned, IsTeamMember])
    def stop(self, request, instance_id=None):
        """
        Stop an instance.
        Reduces team's challenge points when user manually stops instance.
        POST /api/instances/{instance_id}/stop/
        """
        instance = self.get_object()
        
        # Check if user is team member (IsTeamMember permission)
        if not instance.team.is_member(request.user) and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to stop this instance'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Stop instance and reduce points
        success, error, points_reduced = instance_service.stop_instance(
            instance,
            reduce_points=True,
            reason="Instance stopped by user"
        )
        
        if not success:
            return Response(
                {'error': error or 'Failed to stop instance'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        
        serializer = self.get_serializer(instance, context={'request': request})
        response_data = {
            'message': 'Instance stopped successfully',
            'instance': serializer.data
        }
        
        if points_reduced > 0:
            response_data['points_reduced'] = points_reduced
            response_data['warning'] = f'Challenge points reduced by {points_reduced} due to manual stop.'
        elif instance.challenge.reduce_points_on_stop:
            # Penalty setting is enabled but no penalty was applied (maybe already solved)
            response_data['info'] = 'Instance stopped. No penalty applied (challenge already solved or scoreboard frozen).'
        else:
            # Penalty setting is disabled
            response_data['info'] = 'Instance stopped. No penalty applied (stop penalty disabled for this challenge).'
        
        return Response(response_data)
    
    @action(detail=True, methods=['get'])
    def status(self, request, instance_id=None):
        """
        Get detailed status of an instance.
        GET /api/instances/{instance_id}/status/
        """
        instance = self.get_object()
        
        # Check permissions
        if not instance.team.is_member(request.user) and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to view this instance'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get current status from Docker
        docker_status = instance_service.get_instance_status(instance)
        
        # Check if can be renewed
        can_renew, renew_reason = instance.can_renew()
        
        serializer = self.get_serializer(instance, context={'request': request})
        return Response({
            'instance': serializer.data,
            'docker_status': docker_status,
            'is_running': docker_status == 'running',
            'can_renew': can_renew,
            'renew_reason': renew_reason,
            'renewal_count': instance.renewal_count,
            'renewal_limit': instance.challenge.instance_renewal_limit
        })
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated, IsNotBanned, IsTeamMember])
    def renew(self, request, instance_id=None):
        """
        Renew/extend instance expiration time.
        POST /api/instances/{instance_id}/renew/
        Body (optional): { "minutes": 30 }
        """
        instance = self.get_object()
        
        # Check if user is team member
        if not instance.team.is_member(request.user) and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to renew this instance'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Get minutes from request (optional)
        minutes = request.data.get('minutes')
        
        # Attempt renewal
        success, message, new_expiry = instance.renew(request.user, minutes)
        
        if not success:
            return Response(
                {'error': message},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(instance, context={'request': request})
        return Response({
            'message': message,
            'instance': serializer.data,
            'new_expiry': new_expiry,
            'renewal_count': instance.renewal_count
        }, status=status.HTTP_200_OK)
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete instance (stops it first).
        Only team members or admins can delete.
        Reduces team's challenge points when instance is destroyed.
        """
        instance = self.get_object()
        
        # Check permissions
        if not instance.team.is_member(request.user) and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to delete this instance'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Stop instance first and reduce points
        success, error, points_reduced = instance_service.stop_instance(
            instance,
            reduce_points=True,
            reason="Instance deleted by user/admin"
        )
        
        # Delete database record
        instance.delete()
        
        response_data = {
            'message': 'Instance deleted successfully',
        }
        
        if points_reduced > 0:
            response_data['points_reduced'] = points_reduced
            response_data['warning'] = f'Challenge points reduced by {points_reduced}.'
        
        return Response(response_data)
