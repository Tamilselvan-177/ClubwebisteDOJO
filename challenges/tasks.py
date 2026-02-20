"""
Celery tasks for challenge instance management.
"""
from celery import shared_task
from django.utils import timezone
from .models import ChallengeInstance
from .services import instance_service
import logging

logger = logging.getLogger(__name__)


@shared_task
def cleanup_expired_instances():
    """
    Periodic task to cleanup expired instances.
    Should be run every hour.
    Reduces team points for each expired instance.
    """
    try:
        count = instance_service.cleanup_expired_instances()
        logger.info(f"Cleaned up {count} expired instances and reduced points accordingly")
        return count
    except Exception as e:
        logger.error(f"Error cleaning up expired instances: {e}")
        return 0


@shared_task
def cleanup_stopped_instances():
    """
    Periodic task to cleanup old stopped instances.
    Should be run daily.
    """
    try:
        count = instance_service.cleanup_stopped_instances(older_than_hours=24)
        logger.info(f"Cleaned up {count} old stopped instances")
        return count
    except Exception as e:
        logger.error(f"Error cleaning up stopped instances: {e}")
        return 0


@shared_task
def stop_instance(instance_id):
    """
    Task to stop an instance asynchronously.
    Does NOT reduce points (manual stop should be done via API endpoint).
    """
    try:
        instance = ChallengeInstance.objects.get(instance_id=instance_id)
        success, error, _ = instance_service.stop_instance(instance, reduce_points=False)
        if not success:
            logger.error(f"Failed to stop instance {instance_id}: {error}")
        return success
    except ChallengeInstance.DoesNotExist:
        logger.error(f"Instance {instance_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error stopping instance {instance_id}: {e}")
        return False


@shared_task
def sync_instance_statuses():
    """
    Periodic task to sync instance statuses with Docker.
    Updates database status based on actual Docker container status.
    """
    try:
        running_instances = ChallengeInstance.objects.filter(status='running')
        updated_count = 0
        
        for instance in running_instances:
            docker_status = instance_service.get_instance_status(instance)
            if docker_status != instance.status:
                if docker_status == 'stopped':
                    instance.stop()
                else:
                    instance.status = docker_status
                    instance.save(update_fields=['status'])
                updated_count += 1
        
        logger.info(f"Synced {updated_count} instance statuses")
        return updated_count
    except Exception as e:
        logger.error(f"Error syncing instance statuses: {e}")
        return 0

