"""
Admin views for event control and management.
"""
from rest_framework import status, permissions
from rest_framework.decorators import api_view, permission_classes
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from .models import Event, AdminAuditLog
from .services import event_control_service
from .serializers import EventSerializer


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def start_event(request, event_id):
    """Start an event"""
    event = get_object_or_404(Event, id=event_id)
    # Support both JSON and form data
    if hasattr(request, 'data'):
        reason = request.data.get('reason', '')
    else:
        reason = request.POST.get('reason', '')
    
    try:
        event_control_service.start_event(
            event=event,
            performed_by=request.user,
            request=request,
            reason=reason
        )
        # Refresh from DB to get updated state
        event.refresh_from_db()
        return Response({
            'message': 'Event started successfully',
            'event': EventSerializer(event, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def pause_event(request, event_id):
    """Pause an event"""
    event = get_object_or_404(Event, id=event_id)
    # Support both JSON and form data
    if hasattr(request, 'data'):
        reason = request.data.get('reason', '')
    else:
        reason = request.POST.get('reason', '')
    
    try:
        event_control_service.pause_event(
            event=event,
            performed_by=request.user,
            request=request,
            reason=reason
        )
        # Refresh from DB to get updated state
        event.refresh_from_db()
        return Response({
            'message': 'Event paused successfully',
            'event': EventSerializer(event, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def resume_event(request, event_id):
    """Resume a paused event"""
    event = get_object_or_404(Event, id=event_id)
    # Support both JSON and form data
    if hasattr(request, 'data'):
        reason = request.data.get('reason', '')
    else:
        reason = request.POST.get('reason', '')
    
    try:
        event_control_service.resume_event(
            event=event,
            performed_by=request.user,
            request=request,
            reason=reason
        )
        # Refresh from DB to get updated state
        event.refresh_from_db()
        return Response({
            'message': 'Event resumed successfully',
            'event': EventSerializer(event, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    except ValueError as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def stop_event(request, event_id):
    """Stop an event (final)"""
    event = get_object_or_404(Event, id=event_id)
    # Support both JSON and form data
    if hasattr(request, 'data'):
        reason = request.data.get('reason', '')
    else:
        reason = request.POST.get('reason', '')
    
    try:
        event, destroyed_count = event_control_service.stop_event(
            event=event,
            performed_by=request.user,
            request=request,
            reason=reason
        )
        # Refresh from DB to get updated state
        event.refresh_from_db()
        return Response({
            'message': 'Event stopped successfully',
            'instances_destroyed': destroyed_count,
            'event': EventSerializer(event, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response(
            {'error': str(e)},
            status=status.HTTP_400_BAD_REQUEST
        )


@api_view(['GET'])
@permission_classes([permissions.IsAdminUser])
def get_audit_logs(request, event_id=None):
    """Get admin audit logs"""
    queryset = AdminAuditLog.objects.all().select_related(
        'event', 'performed_by', 'content_type'
    ).order_by('-timestamp')
    
    if event_id:
        queryset = queryset.filter(event_id=event_id)
    
    # Pagination
    from rest_framework.pagination import PageNumberPagination
    paginator = PageNumberPagination()
    paginator.page_size = 50
    page = paginator.paginate_queryset(queryset, request)
    
    if page is not None:
        logs = [
            {
                'id': log.id,
                'action_type': log.get_action_type_display(),
                'description': log.description,
                'reason': log.reason,
                'performed_by': log.performed_by.username if log.performed_by else 'System',
                'event': log.event.name if log.event else None,
                'timestamp': log.timestamp,
                'ip_address': str(log.ip_address) if log.ip_address else None,
                'metadata': log.metadata,
            }
            for log in page
        ]
        return paginator.get_paginated_response(logs)
    
    logs = [
        {
            'id': log.id,
            'action_type': log.get_action_type_display(),
            'description': log.description,
            'reason': log.reason,
            'performed_by': log.performed_by.username if log.performed_by else 'System',
            'event': log.event.name if log.event else None,
            'timestamp': log.timestamp,
            'ip_address': str(log.ip_address) if log.ip_address else None,
            'metadata': log.metadata,
        }
        for log in queryset
    ]
    return Response({'results': logs}, status=status.HTTP_200_OK)


@api_view(['POST'])
@permission_classes([permissions.IsAdminUser])
def freeze_scoreboard(request, event_id):
    """Freeze the scoreboard at current time (no scoreboard_state change)."""
    event = get_object_or_404(Event, id=event_id)
    if hasattr(request, 'data'):
        reason = request.data.get('reason', '')
    else:
        reason = request.POST.get('reason', '')

    try:
        event_control_service.freeze_scoreboard(
            event=event,
            performed_by=request.user,
            request=request,
            reason=reason
        )
        event.refresh_from_db()
        return Response({
            'message': 'Scoreboard frozen successfully',
            'event': EventSerializer(event, context={'request': request}).data
        }, status=status.HTTP_200_OK)
    except Exception as e:
        return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)

