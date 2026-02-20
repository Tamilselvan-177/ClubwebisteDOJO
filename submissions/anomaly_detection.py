"""
Anomaly detection for CTF platform
Detects suspicious patterns in player behavior
"""

from django.core.cache import cache
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class AnomalyDetector:
    """
    Detect suspicious behavior patterns in CTF submissions
    """
    
    @staticmethod
    def track_submission_attempt(team, challenge, event, is_correct):
        """
        Track submission attempts and detect anomalies
        """
        cache_key = f"submission_attempts:{event.id}:{team.id}:{challenge.id}"
        attempt_data = cache.get(cache_key, {
            'attempts': 0,
            'correct': 0,
            'incorrect': 0,
            'last_attempt': None,
            'timestamps': []
        })
        
        now = timezone.now()
        
        # Update stats
        attempt_data['attempts'] += 1
        if is_correct:
            attempt_data['correct'] += 1
        else:
            attempt_data['incorrect'] += 1
        
        attempt_data['last_attempt'] = now.isoformat()
        attempt_data['timestamps'].append(now.isoformat())
        
        # Keep only last 100 timestamps
        attempt_data['timestamps'] = attempt_data['timestamps'][-100:]
        
        # Cache for 24 hours
        cache.set(cache_key, attempt_data, 86400)
        
        # Detect anomalies
        anomalies = []
        
        # Alert: Too many wrong attempts (brute force)
        if attempt_data['incorrect'] > 50:
            anomalies.append({
                'type': 'brute_force',
                'message': f"High number of wrong attempts: {attempt_data['incorrect']}",
                'severity': 'high'
            })
        
        # Alert: Rapid-fire submissions (likely automated)
        if len(attempt_data['timestamps']) > 1:
            recent = attempt_data['timestamps'][-10:]
            if len(recent) >= 10:
                from datetime import datetime, timedelta
                first = datetime.fromisoformat(recent[0])
                last = datetime.fromisoformat(recent[-1])
                time_span = (last - first).total_seconds()
                
                # 10 submissions in less than 5 seconds = suspicious
                if time_span < 5:
                    anomalies.append({
                        'type': 'rapid_fire',
                        'message': f"Rapid submissions detected: 10 in {time_span:.1f}s",
                        'severity': 'high'
                    })
        
        # Log anomalies
        for anomaly in anomalies:
            logger.warning(
                f"ANOMALY DETECTED: {anomaly['type']}",
                extra={
                    'team': team.name,
                    'challenge': challenge.name,
                    'severity': anomaly['severity'],
                    'details': anomaly['message']
                }
            )
        
        return anomalies
    
    @staticmethod
    def check_flag_sharing(submitted_flag, team, event):
        """
        Detect if flag was copied from another team's instance
        """
        # Get all active instances from other teams
        from challenges.models import ChallengeInstance
        
        suspicious_matches = []
        
        other_instances = ChallengeInstance.objects.filter(
            event=event,
            status='running'
        ).exclude(team=team)
        
        for instance in other_instances:
            # Use constant-time comparison to prevent timing attacks
            if _secure_compare(submitted_flag, instance.flag):
                suspicious_matches.append({
                    'type': 'flag_sharing',
                    'matched_team': instance.team.name,
                    'matched_challenge': instance.challenge.name,
                    'severity': 'critical'
                })
                
                logger.critical(
                    "POTENTIAL FLAG SHARING DETECTED",
                    extra={
                        'team': team.name,
                        'matched_team': instance.team.name,
                        'challenge': instance.challenge.name,
                    }
                )
        
        return suspicious_matches


def _secure_compare(a, b):
    """
    Constant-time string comparison to prevent timing attacks
    """
    import hmac
    return hmac.compare_digest(str(a), str(b))
