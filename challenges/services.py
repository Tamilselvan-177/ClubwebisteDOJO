"""
Services for challenge instance management.
Handles Docker container operations and instance lifecycle.
"""
import secrets
import logging
import socket
import os
import subprocess
import json
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
from .models import Challenge, ChallengeInstance

logger = logging.getLogger(__name__)


class InstanceService:
    """
    Service class for managing challenge instances.
    Handles Docker container creation, management, and cleanup.
    Uses Docker CLI via subprocess to avoid docker-py compatibility issues.
    """
    
    # Port range for dynamic allocation
    PORT_RANGE_START = 10000
    PORT_RANGE_END = 65000
    
    def __init__(self):
        """Initialize Docker CLI interface"""
        self.client = None  # Will track if docker CLI works
        self.use_docker_cli = False
        
        try:
            # Test if Docker CLI is available
            result = subprocess.run(
                ['docker', 'ps', '--format', 'json'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                self.use_docker_cli = True
                self.client = True  # Mark as available
                logger.info("Docker CLI available - using subprocess Docker API")
            else:
                logger.error(f"Docker CLI returned error: {result.stderr.decode()}")
                self.client = None
        except FileNotFoundError:
            logger.error("Docker CLI not found in PATH")
            self.client = None
        except Exception as e:
            logger.error(f"Failed to initialize Docker CLI: {e}")
            self.client = None
    
    def _find_free_port(self):
        """
        Find an available free port by testing random ports (like CTFd).
        Doesn't rely on DB state; actually attempts to bind to verify port is free.
        """
        # Try random ports until we find one that's free
        # This is more reliable than DB tracking during retries
        max_port_attempts = 50
        for _ in range(max_port_attempts):
            # Pick a random port in the range
            port = secrets.randbelow(self.PORT_RANGE_END - self.PORT_RANGE_START) + self.PORT_RANGE_START
            
            # Test if port is actually free by attempting to bind
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                sock.bind(('0.0.0.0', port))
                sock.close()
                logger.debug(f"Found free port: {port}")
                return port
            except OSError:
                # Port in use, try another
                continue
        
        raise RuntimeError(f"Could not find a free port after {max_port_attempts} attempts")
    
    def can_start_instance(self, challenge, team, event):
        """
        Check if team can start a new instance for this challenge.
        Returns (can_start, reason)
        """
        if challenge.challenge_type != 'instance':
            return False, "Challenge is not instance-based"
        
        if not challenge.is_active or not challenge.is_visible:
            return False, "Challenge is not available"
        
        # Check global max instances per team limit (across all challenges)
        global_active_instances = ChallengeInstance.objects.filter(
            challenge__event=event,
            team=team,
            status='running'
        ).count()
        
        if global_active_instances >= event.max_instances_per_team:
            return False, f"Maximum instances per team ({event.max_instances_per_team}) reached globally"
        
        # Check per-challenge max instances per team limit
        challenge_active_instances = ChallengeInstance.objects.filter(
            challenge=challenge,
            team=team,
            status='running'
        ).count()
        
        if challenge_active_instances >= challenge.max_instances_per_team:
            return False, f"Maximum instances per team ({challenge.max_instances_per_team}) reached for this challenge"
        
        return True, "OK"
    
    def start_instance(self, challenge, team, user, event):
        """
        Start a new instance for a team using Docker CLI.
        Returns (instance, error_message)
        
        Key feature: Automatically allocates free ports to each instance
        so multiple teams can run the same challenge simultaneously.
        """
        if not self.client:
            return None, "Docker service unavailable"
        
        # Check if can start
        can_start, reason = self.can_start_instance(challenge, team, event)
        if not can_start:
            return None, reason
        
        # Get instance configuration
        config = challenge.instance_config or {}
        image = config.get('image', 'ubuntu:latest')
        ports = config.get('ports', {})
        env_vars = dict(config.get('environment', {}))  # Use 'environment' key
        
        # Generate unique instance ID and flag (format: eventname{16bit_md5_hash})
        import hashlib
        instance_id = f"{challenge.id}-{team.id}-{secrets.token_urlsafe(8)}"
        
        # Generate 16-bit MD5 hash for unique flag
        random_seed = f"{challenge.id}-{team.id}-{instance_id}-{timezone.now()}"
        md5_hash = hashlib.md5(random_seed.encode()).hexdigest()[:16]  # 16 chars of MD5
        
        # Get event name or use default
        event_name = event.name if event else 'CTF'
        event_name = event_name.replace(' ', '_').replace('{', '').replace('}', '')  # Sanitize
        
        # Format: eventname{16bit_md5_hash}
        flag = f"{event_name}{{{md5_hash}}}"
        
        # SECURITY: Sanitize environment variable keys and values
        safe_env_vars = {}
        for key, value in env_vars.items():
            # Only allow alphanumeric keys and underscores
            if not key.replace('_', '').isalnum():
                logger.warning(f"Skipping invalid env var key: {key}")
                continue
            # Convert value to string and remove shell metacharacters
            safe_value = str(value).replace('$', '').replace('`', '').replace('\\', '')
            safe_env_vars[key] = safe_value
        
        # Add FLAG to environment variables
        safe_env_vars['FLAG'] = flag
        
        try:
            # Find free port for this instance
            access_port = self._find_free_port()
            
            # Create container using Docker CLI
            container_name = f"ctf-instance-{instance_id}"
            
            # Build docker run command
            # SECURITY: Validate container name to prevent injection
            safe_container_name = ''.join(c for c in container_name if c.isalnum() or c in '-_')
            docker_cmd = ['docker', 'run', '-d', '--name', safe_container_name]
            
            # Add environment variables (already sanitized above)
            for key, value in safe_env_vars.items():
                docker_cmd.extend(['-e', f'{key}={value}'])
            
            # Add network config
            if config.get('network_disabled', False):
                docker_cmd.append('--network=none')

            # Preserve a base command (without ports and image) to rebuild on retry
            base_docker_cmd = docker_cmd.copy()

            # Add port bindings if provided (map container port to dynamically allocated host port)
            if ports:
                for container_port in ports.keys():
                    # SECURITY: Validate port is numeric
                    try:
                        port_num = int(str(container_port))
                        if 1 <= port_num <= 65535:
                            base_docker_cmd.extend(['-p', f'{access_port}:{port_num}'])
                    except (ValueError, TypeError):
                        logger.warning(f"Invalid port: {container_port}")
                        continue

            # SECURITY: Validate image name to prevent injection
            safe_image = ''.join(c for c in image if c.isalnum() or c in '._-:/')
            docker_cmd = base_docker_cmd + [safe_image]
            
            # Run container with retry on port allocation conflict
            max_attempts = 5
            attempt = 0
            container_id = None
            while attempt < max_attempts and not container_id:
                result = subprocess.run(
                    docker_cmd,
                    capture_output=True,
                    timeout=30,
                    text=True
                )
                if result.returncode == 0:
                    container_id = result.stdout.strip()
                    break
                error_msg = (result.stderr or result.stdout or '').strip()
                # If port is already allocated, pick a new port and retry
                if 'port is already allocated' in error_msg.lower():
                    logger.warning(f"Port {access_port} allocated, retrying with next port (attempt {attempt+1}/{max_attempts})")
                    # Find next free port
                    access_port = self._find_free_port()
                    # Rebuild docker command from base with new port mapping and image
                    new_cmd = base_docker_cmd.copy()
                    if ports:
                        for container_port in ports.keys():
                            try:
                                port_num = int(str(container_port))
                                if 1 <= port_num <= 65535:
                                    new_cmd.extend(['-p', f'{access_port}:{port_num}'])
                            except (ValueError, TypeError):
                                logger.warning(f"Invalid port: {container_port}")
                                continue
                    docker_cmd = new_cmd + [safe_image]
                    attempt += 1
                    continue
                # If container name conflict, generate a new unique name and retry
                if ('name is already in use' in error_msg.lower()) or ('conflict' in error_msg.lower() and 'container name' in error_msg.lower()):
                    import secrets as _secrets
                    new_name = safe_container_name + '-' + _secrets.token_urlsafe(4)
                    new_name = ''.join(c for c in new_name if c.isalnum() or c in '-_')
                    # Replace --name value in base command
                    rebuilt = []
                    i = 0
                    while i < len(base_docker_cmd):
                        if base_docker_cmd[i] == '--name' and i + 1 < len(base_docker_cmd):
                            rebuilt.extend(['--name', new_name])
                            i += 2
                        else:
                            rebuilt.append(base_docker_cmd[i])
                            i += 1
                    # Re-add ports
                    if ports:
                        for container_port in ports.keys():
                            try:
                                port_num = int(str(container_port))
                                if 1 <= port_num <= 65535:
                                    rebuilt.extend(['-p', f'{access_port}:{port_num}'])
                            except (ValueError, TypeError):
                                logger.warning(f"Invalid port: {container_port}")
                                continue
                    docker_cmd = rebuilt + [safe_image]
                    attempt += 1
                    continue
                # Other errors: abort
                logger.error(f"Failed to create container: {error_msg}")
                return None, f"Failed to create instance: {error_msg[:100]}"
            
            if not container_id:
                return None, "Failed to create instance after multiple attempts due to port conflicts"
            
            # Get container IP address using docker inspect
            container_ip = None
            try:
                inspect_result = subprocess.run(
                    ['docker', 'inspect', '-f', '{{range .NetworkSettings.Networks}}{{.IPAddress}}{{end}}', container_id],
                    capture_output=True,
                    timeout=10,
                    text=True
                )
                if inspect_result.returncode == 0:
                    container_ip = inspect_result.stdout.strip()
                    logger.info(f"Retrieved container IP: {container_ip}")
            except Exception as e:
                logger.warning(f"Failed to retrieve container IP: {e}")
            
            # Determine access URL using container IP and port
            if container_ip:
                access_url = f"http://{container_ip}:{access_port}"
                if config.get('access_url_template'):
                    access_url = config['access_url_template'].replace('{ip}', container_ip).replace('{port}', str(access_port))
            else:
                # Fallback to localhost if IP retrieval fails
                access_url = f"http://localhost:{access_port}"
                if config.get('access_url_template'):
                    access_url = config['access_url_template'].replace('{port}', str(access_port))
            
            # Calculate expiration time limit
            time_limit_minutes = challenge.instance_time_limit_minutes or event.instance_time_limit_minutes
            expires_at = timezone.now() + timedelta(minutes=time_limit_minutes)
            
            # Create instance record
            instance = ChallengeInstance.objects.create(
                challenge=challenge,
                team=team,
                started_by=user,
                event=event,
                container_id=container_id,
                instance_id=instance_id,
                flag=flag,
                access_url=access_url,
                access_port=access_port,
                container_ip=container_ip,
                status='running',
                started_at=timezone.now(),
                expires_at=expires_at,
                config_snapshot=config
            )
            
            logger.info(f"Started instance {container_id} for team {team.id} on port {access_port}")
            return instance, None
            
        except subprocess.TimeoutExpired:
            return None, "Docker operation timed out"
        except Exception as e:
            logger.error(f"Error starting instance: {e}")
            return None, f"Error starting instance: {str(e)[:100]}"
    
    def stop_instance(self, instance, reduce_points=False, reason="Instance stopped"):
        """
        Stop and remove an instance using Docker CLI.
        Optionally reduce challenge points when instance is destroyed.
        Point reduction is controlled by admin settings on the challenge.
        Returns (success, error_message, points_reduced)
        
        Args:
            instance: ChallengeInstance to stop
            reduce_points: If True, check admin settings and potentially reduce points
            reason: Reason for stopping (used in point reduction)
        """
        from django.db import transaction
        from challenges.models import ChallengeInstance
        
        points_reduced = 0
        docker_error = None
        
        # ATOMIC RACE CONDITION PREVENTION
        # Use database-level atomic update to claim the instance for stopping
        # Only one request will succeed in changing status from 'running' to 'stopping'
        with transaction.atomic():
            # Re-fetch with lock to prevent concurrent modifications
            locked_instance = ChallengeInstance.objects.select_for_update().filter(
                id=instance.id,
                status='running'
            ).first()
            
            if not locked_instance:
                # Instance was already stopped by another request or doesn't exist
                logger.warning(f"Instance {instance.instance_id} is not running (status: {instance.status}), skipping stop - race condition prevented")
                return True, "Instance already stopped", 0
            
            # Mark as 'stopping' immediately to block other concurrent requests
            locked_instance.status = 'stopping'
            locked_instance.save(update_fields=['status'])
            instance.refresh_from_db()
        
        logger.info(f"Instance {instance.instance_id} status changed to 'stopping' - proceeding with Docker stop")
        
        # Try to stop Docker container if Docker is available
        if self.client and instance.container_id:
            try:
                # KILL container immediately (no grace period) for fast shutdown
                subprocess.run(
                    ['docker', 'kill', instance.container_id],
                    capture_output=True,
                    timeout=2,
                    text=True
                )
                
                # Remove container immediately (ignore if already removed)
                subprocess.run(
                    ['docker', 'rm', instance.container_id],
                    capture_output=True,
                    timeout=2
                )
                
                logger.info(f"Instance {instance.instance_id} killed and removed")
                
            except subprocess.TimeoutExpired:
                docker_error = "Docker operation timed out"
                logger.error(f"Docker operation timeout for instance {instance.instance_id}")
                instance.mark_error(docker_error)
            except Exception as e:
                docker_error = str(e)
                logger.error(f"Error stopping instance {instance.instance_id}: {e}")
                instance.mark_error(docker_error)
        else:
            logger.warning(f"Docker unavailable or no container for instance {instance.instance_id}, marking as stopped anyway")
        
        # ALWAYS mark instance as stopped and handle point reduction
        # This ensures instances are marked stopped even if Docker fails
        instance.stop()
        
        # Check if we should reduce points based on admin settings and reason
        should_reduce = False
        
        if reduce_points:
            challenge = instance.challenge
            
            # Check admin settings based on reason
            if "expired" in reason.lower():
                should_reduce = challenge.reduce_points_on_expiry
            elif "stopped by user" in reason.lower():
                should_reduce = challenge.reduce_points_on_stop
            elif "wrong flag" in reason.lower():
                should_reduce = challenge.reduce_points_on_wrong_flag
            else:
                # For other reasons (event stopped, new instance, etc.), use default
                should_reduce = True
        
        # Reduce points if admin settings allow (team-scoped penalty only)
        if should_reduce:
            from submissions.models import Score, Submission
            from submissions.services import SubmissionService

            event = instance.event
            team = instance.team
            challenge = instance.challenge

            # Skip penalties if the team already solved the challenge.
            if Submission.objects.filter(team=team, challenge=challenge, event=event, status='correct').exists():
                logger.info(f"Skipping point reduction for {team.name} - already solved {challenge.name}")
                return True, docker_error, 0

            submission_service = SubmissionService()
            current_team_score = submission_service.calculate_team_total_score(team, event)

            # Calculate penalty based on challenge configuration
            if challenge.penalty_type == 'fixed':
                # Fixed points penalty
                reduction_amount = challenge.penalty_fixed_points
            else:
                # Percentage penalty (default)
                reduction_amount = max(1, int(challenge.points * (challenge.penalty_percentage / 100.0)))
            
            points_reduced = reduction_amount

            # Get current team total score (penalties don't change this)
            current_team_score = submission_service.calculate_team_total_score(team, event)

            # Create penalty Score entry (affects challenge score only, NOT team total score)
            # total_score stays the same because penalties don't reduce earned points
            Score.objects.create(
                team=team,
                challenge=challenge,
                event=event,
                points=-points_reduced,
                score_type='reduction',
                total_score=current_team_score,  # UNCHANGED - penalties don't reduce team total
                reason=reason,
                notes=f"Penalty for this team only; earned score unchanged. Instance: {instance.instance_id}"
            )
            logger.info(f"Team-scoped penalty {points_reduced} for team {team.id} on challenge {challenge.id}: {reason}")
        
        # Return success even if Docker failed, as long as we marked it stopped and reduced points
        return True, docker_error, points_reduced

    
    def cleanup_expired_instances(self):
        """
        Cleanup expired instances.
        Reduces team's challenge points for each expired instance.
        Returns count of cleaned instances.
        """
        expired_instances = ChallengeInstance.objects.filter(
            status='running',
            expires_at__lt=timezone.now()
        )
        
        count = 0
        for instance in expired_instances:
            # Stop instance and reduce points due to expiration
            success, error, points_reduced = self.stop_instance(
                instance,
                reduce_points=True,
                reason=f"Instance expired (limit: {instance.challenge.instance_time_limit_minutes} minutes)"
            )
            if success:
                count += 1
                logger.info(f"Expired instance {instance.instance_id} cleaned up. Points reduced: {points_reduced}")
        
        return count
    
    def cleanup_stopped_instances(self, older_than_hours=24):
        """
        Cleanup instances that have been stopped for a while.
        Returns count of cleaned instances.
        """
        cutoff_time = timezone.now() - timedelta(hours=older_than_hours)
        old_stopped = ChallengeInstance.objects.filter(
            status__in=['stopped', 'error'],
            stopped_at__lt=cutoff_time
        )
        
        count = old_stopped.count()
        old_stopped.delete()
        
        return count
    
    def get_instance_status(self, instance):
        """
        Get current status of an instance from Docker using CLI.
        Returns status string or None if error.
        """
        if not self.client or not instance.container_id:
            return instance.status
        
        try:
            # Get container status using Docker CLI
            result = subprocess.run(
                ['docker', 'inspect', '-f', '{{.State.Status}}', instance.container_id],
                capture_output=True,
                timeout=5,
                text=True
            )
            
            if result.returncode == 0:
                status = result.stdout.strip()
                if status == 'running':
                    return 'running'
                elif status in ['exited', 'stopped']:
                    return 'stopped'
                else:
                    return status
            else:
                # Container not found
                return 'stopped'
        except Exception as e:
            logger.error(f"Error checking instance status: {e}")
            return instance.status


# Singleton instance
instance_service = InstanceService()

