"""
Health check views for monitoring.
"""
from django.http import JsonResponse
from django.db import connection
from django.core.cache import cache
import redis
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync


def health_check(request):
    """
    Simple health check endpoint.
    Returns 200 if the service is up.
    """
    return JsonResponse({
        'status': 'healthy',
        'service': 'ctf-platform-backend'
    })


def detailed_health_check(request):
    """
    Detailed health check with database, cache, and redis status.
    """
    health_status = {
        'status': 'healthy',
        'checks': {}
    }
    
    # Check database
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
        health_status['checks']['database'] = 'healthy'
    except Exception as e:
        health_status['checks']['database'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'degraded'
    
    # Check cache/Redis
    try:
        cache.set('health_check', 'ok', 10)
        result = cache.get('health_check')
        if result == 'ok':
            health_status['checks']['cache'] = 'healthy'
        else:
            health_status['checks']['cache'] = 'unhealthy: cache test failed'
            health_status['status'] = 'degraded'
    except Exception as e:
        health_status['checks']['cache'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'degraded'
    
    # Check Redis directly
    try:
        from django.conf import settings
        redis_url = getattr(settings, 'REDIS_URL', 'redis://localhost:6379/0')
        r = redis.from_url(redis_url)
        r.ping()
        health_status['checks']['redis'] = 'healthy'
    except Exception as e:
        health_status['checks']['redis'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'degraded'
    
    # Check Channels layer
    try:
        channel_layer = get_channel_layer()
        if channel_layer:
            health_status['checks']['websockets'] = 'healthy'
        else:
            health_status['checks']['websockets'] = 'unhealthy: no channel layer'
            health_status['status'] = 'degraded'
    except Exception as e:
        health_status['checks']['websockets'] = f'unhealthy: {str(e)}'
        health_status['status'] = 'degraded'
    
    status_code = 200 if health_status['status'] == 'healthy' else 503
    return JsonResponse(health_status, status=status_code)
