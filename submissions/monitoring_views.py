"""
Views for monitoring and anti-cheat management.
"""
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Violation
from .serializers import ViolationSerializer
from .monitoring_serializers import ViolationDetailSerializer
from .monitoring import monitoring_service
from events_ctf.models import Event
from challenges.models import Challenge
from accounts.models import Team

# Import Sum for aggregation
from django.db.models import Sum


class MonitoringViewSet(viewsets.ViewSet):
    """
    ViewSet for monitoring endpoints (admin only).
    """
    permission_classes = [permissions.IsAdminUser]
    
    @action(detail=False, methods=['get'])
    def event_stats(self, request):
        """
        Get comprehensive statistics for an event.
        GET /api/monitoring/event_stats/?event_id=1
        """
        event_id = request.query_params.get('event_id')
        if not event_id:
            return Response(
                {'error': 'event_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response(
                {'error': 'Event not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        stats = monitoring_service.get_event_statistics(event)
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def challenge_stats(self, request):
        """
        Get statistics for a challenge.
        GET /api/monitoring/challenge_stats/?challenge_id=1&event_id=1
        """
        challenge_id = request.query_params.get('challenge_id')
        event_id = request.query_params.get('event_id')
        
        if not challenge_id or not event_id:
            return Response(
                {'error': 'challenge_id and event_id parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
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
        
        stats = monitoring_service.get_challenge_statistics(challenge, event)
        
        # Serialize first_blood if exists
        if stats['first_blood']:
            from .serializers import SubmissionListSerializer
            stats['first_blood'] = SubmissionListSerializer(stats['first_blood']).data
        
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def team_stats(self, request):
        """
        Get statistics for a team.
        GET /api/monitoring/team_stats/?team_id=1&event_id=1
        """
        team_id = request.query_params.get('team_id')
        event_id = request.query_params.get('event_id')
        
        if not team_id or not event_id:
            return Response(
                {'error': 'team_id and event_id parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            team = Team.objects.get(id=team_id)
            event = Event.objects.get(id=event_id)
        except Team.DoesNotExist:
            return Response(
                {'error': 'Team not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Event.DoesNotExist:
            return Response(
                {'error': 'Event not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        stats = monitoring_service.get_team_statistics(team, event)
        return Response(stats)
    
    @action(detail=False, methods=['get'])
    def team_behavior(self, request):
        """
        Analyze team behavior for anomalies.
        GET /api/monitoring/team_behavior/?team_id=1&event_id=1
        """
        team_id = request.query_params.get('team_id')
        event_id = request.query_params.get('event_id')
        
        if not team_id or not event_id:
            return Response(
                {'error': 'team_id and event_id parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            team = Team.objects.get(id=team_id)
            event = Event.objects.get(id=event_id)
        except Team.DoesNotExist:
            return Response(
                {'error': 'Team not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Event.DoesNotExist:
            return Response(
                {'error': 'Event not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        analysis = monitoring_service.analyze_team_behavior(team, event)
        
        # Also check for suspicious patterns
        patterns = monitoring_service.detect_suspicious_submission_patterns(team, event)
        
        return Response({
            'analysis': analysis,
            'suspicious_patterns': patterns
        })
    
    @action(detail=False, methods=['get'])
    def suspicious_teams(self, request):
        """
        Get list of teams with suspicious behavior.
        GET /api/monitoring/suspicious_teams/?event_id=1
        """
        event_id = request.query_params.get('event_id')
        if not event_id:
            return Response(
                {'error': 'event_id parameter is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            event = Event.objects.get(id=event_id)
        except Event.DoesNotExist:
            return Response(
                {'error': 'Event not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Get all teams with submissions in this event
        teams = Team.objects.filter(
            submissions__event=event
        ).distinct()
        
        suspicious_teams = []
        for team in teams:
            analysis = monitoring_service.analyze_team_behavior(team, event)
            patterns = monitoring_service.detect_suspicious_submission_patterns(team, event)
            
            if analysis['anomalies'] or patterns:
                suspicious_teams.append({
                    'team_id': team.id,
                    'team_name': team.name,
                    'analysis': analysis,
                    'suspicious_patterns': patterns
                })
        
        return Response({
            'count': len(suspicious_teams),
            'teams': suspicious_teams
        })


class ViolationManagementViewSet(viewsets.ModelViewSet):
    """
    ViewSet for violation management (admin only).
    """
    queryset = Violation.objects.all()
    serializer_class = ViolationSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_serializer_class(self):
        if self.action == 'retrieve':
            return ViolationDetailSerializer
        return ViolationSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by event
        event_id = self.request.query_params.get('event', None)
        if event_id:
            queryset = queryset.filter(event_id=event_id)
        
        # Filter by team
        team_id = self.request.query_params.get('team', None)
        if team_id:
            queryset = queryset.filter(team_id=team_id)
        
        # Filter by resolved status
        is_resolved = self.request.query_params.get('is_resolved', None)
        if is_resolved is not None:
            queryset = queryset.filter(is_resolved=is_resolved.lower() == 'true')
        
        # Filter by severity
        severity = self.request.query_params.get('severity', None)
        if severity:
            queryset = queryset.filter(severity=severity)
        
        return queryset.select_related('team', 'challenge', 'event').order_by('-created_at')
    
    @action(detail=True, methods=['post'])
    def resolve(self, request, pk=None):
        """
        Resolve a violation.
        POST /api/violations/{id}/resolve/
        Body: { "action_taken": "Team warned" }
        """
        violation = self.get_object()
        action_taken = request.data.get('action_taken', '')
        
        violation.resolve(resolved_by_user=request.user, action_taken=action_taken)
        
        serializer = self.get_serializer(violation)
        return Response({
            'message': 'Violation resolved',
            'violation': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def unban_team(self, request, pk=None):
        """
        Unban team associated with violation.
        POST /api/violations/{id}/unban_team/
        """
        violation = self.get_object()
        team = violation.team
        
        team.unban()
        
        violation.action_taken = f"{violation.action_taken or ''} Team unbanned by admin".strip()
        violation.save(update_fields=['action_taken'])
        
        return Response({
            'message': f'Team {team.name} has been unbanned',
            'team': team.name
        })

