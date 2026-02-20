from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from .models import Event, Theme
from .serializers import EventSerializer, EventListSerializer, ThemeSerializer
from accounts.permissions import IsNotBanned


class ThemeViewSet(viewsets.ModelViewSet):
    """ViewSet for Theme management (admin only)"""
    queryset = Theme.objects.all()
    serializer_class = ThemeSerializer
    permission_classes = [permissions.IsAdminUser]
    
    def get_queryset(self):
        queryset = super().get_queryset()
        # Filter by is_default if provided
        is_default = self.request.query_params.get('is_default', None)
        if is_default is not None:
            queryset = queryset.filter(is_default=is_default.lower() == 'true')
        return queryset


class EventViewSet(viewsets.ModelViewSet):
    """ViewSet for Event management"""
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    permission_classes = [permissions.IsAuthenticated, IsNotBanned]
    lookup_field = 'slug'
    
    def get_serializer_class(self):
        if self.action == 'list':
            return EventListSerializer
        return EventSerializer
    
    def get_queryset(self):
        queryset = super().get_queryset()
        
        # Filter by year
        year = self.request.query_params.get('year', None)
        if year:
            try:
                queryset = queryset.filter(year=int(year))
            except ValueError:
                pass
        
        # Filter by active status
        is_active = self.request.query_params.get('is_active', None)
        if is_active is not None:
            queryset = queryset.filter(is_active=is_active.lower() == 'true')
        
        # Filter by visible status
        is_visible = self.request.query_params.get('is_visible', None)
        if is_visible is not None:
            queryset = queryset.filter(is_visible=is_visible.lower() == 'true')
        
        # Filter by archived status
        is_archived = self.request.query_params.get('is_archived', None)
        if is_archived is not None:
            queryset = queryset.filter(is_archived=is_archived.lower() == 'true')
        
        # For non-staff users, only show visible events
        if not self.request.user.is_staff:
            queryset = queryset.filter(is_visible=True)
        
        return queryset.order_by('-year', '-created_at')
    
    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy', 'activate', 'deactivate', 'archive']:
            permission_classes = [permissions.IsAdminUser]
        else:
            permission_classes = [permissions.IsAuthenticated, IsNotBanned]
        return [permission() for permission in permission_classes]
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def activate(self, request, slug=None):
        """Activate an event"""
        event = self.get_object()
        event.activate()
        serializer = self.get_serializer(event)
        return Response({
            'message': 'Event activated successfully',
            'event': serializer.data
        })
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def deactivate(self, request, slug=None):
        """Deactivate an event"""
        event = self.get_object()
        event.deactivate()
        serializer = self.get_serializer(event)
        return Response({
            'message': 'Event deactivated successfully',
            'event': serializer.data
        })
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAdminUser])
    def archive(self, request, slug=None):
        """Archive an event"""
        event = self.get_object()
        event.archive()
        serializer = self.get_serializer(event)
        return Response({
            'message': 'Event archived successfully',
            'event': serializer.data
        })
    
    @action(detail=True, methods=['get'])
    def challenges(self, request, slug=None):
        """Get challenges for an event"""
        event = self.get_object()
        from challenges.models import Challenge
        from challenges.serializers import ChallengeListSerializer
        
        challenges = Challenge.objects.filter(event=event, is_visible=True)
        
        # Filter by category if provided
        category_id = request.query_params.get('category', None)
        if category_id:
            challenges = challenges.filter(category_id=category_id)
        
        # Filter by challenge_type if provided
        challenge_type = request.query_params.get('type', None)
        if challenge_type:
            challenges = challenges.filter(challenge_type=challenge_type)
        
        serializer = ChallengeListSerializer(challenges, many=True, context={'request': request})
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def statistics(self, request, slug=None):
        """Get event statistics"""
        event = self.get_object()
        from challenges.models import Challenge
        from submissions.models import Submission
        from accounts.models import Team
        
        stats = {
            'total_challenges': event.challenges.count(),
            'visible_challenges': event.challenges.filter(is_visible=True).count(),
            'total_teams': Team.objects.filter(
                submissions__event=event
            ).distinct().count(),
            'total_submissions': Submission.objects.filter(event=event).count(),
            'correct_submissions': Submission.objects.filter(
                event=event, status='correct'
            ).count(),
        }
        
        return Response(stats)
