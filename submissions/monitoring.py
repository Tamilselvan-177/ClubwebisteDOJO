"""
Monitoring and anti-cheat detection utilities.
"""
import logging
from django.utils import timezone
from django.db.models import Count, Q, Avg, Max, Min, Sum
from datetime import timedelta
from .models import Submission, Violation, Score
from challenges.models import ChallengeInstance
from accounts.models import Team

logger = logging.getLogger(__name__)


class MonitoringService:
    """
    Service for monitoring submissions and detecting suspicious patterns.
    """
    
    def detect_suspicious_submission_patterns(self, team, event, time_window_minutes=5):
        """
        Detect suspicious submission patterns for a team.
        Returns list of detected patterns.
        """
        patterns = []
        time_threshold = timezone.now() - timedelta(minutes=time_window_minutes)
        
        # Get recent submissions
        recent_submissions = Submission.objects.filter(
            team=team,
            event=event,
            submitted_at__gte=time_threshold
        )
        
        # Pattern 1: Too many submissions in short time
        submission_count = recent_submissions.count()
        if submission_count > 20:  # More than 20 submissions in 5 minutes
            patterns.append({
                'type': 'high_frequency_submissions',
                'severity': 'medium',
                'count': submission_count,
                'time_window': time_window_minutes,
                'description': f'Team submitted {submission_count} flags in {time_window_minutes} minutes'
            })
        
        # Pattern 2: Many incorrect submissions for same challenge
        incorrect_by_challenge = recent_submissions.filter(
            status='incorrect'
        ).values('challenge').annotate(
            count=Count('id')
        ).filter(count__gt=10)
        
        for item in incorrect_by_challenge:
            patterns.append({
                'type': 'repeated_wrong_submissions',
                'severity': 'low',
                'challenge_id': item['challenge'],
                'count': item['count'],
                'description': f'Team submitted {item["count"]} wrong flags for same challenge'
            })
        
        # Pattern 3: Rapid correct submissions across challenges
        correct_submissions = recent_submissions.filter(status='correct')
        if correct_submissions.count() > 5:
            # Check time between correct submissions
            submissions = correct_submissions.order_by('submitted_at')
            for i in range(1, len(submissions)):
                time_diff = (submissions[i].submitted_at - submissions[i-1].submitted_at).total_seconds()
                if time_diff < 30:  # Less than 30 seconds between correct submissions
                    patterns.append({
                        'type': 'rapid_correct_submissions',
                        'severity': 'high',
                        'time_between': time_diff,
                        'description': f'Team solved challenges very quickly ({time_diff}s between solves)'
                    })
        
        return patterns
    
    def detect_instance_tampering(self, instance):
        """
        Detect potential instance tampering.
        Returns (is_tampered, evidence).
        """
        evidence = {}
        is_tampered = False
        
        # Check if instance was accessed from multiple IPs (if we track that)
        # This would require additional tracking
        
        # Check if instance flag was accessed before submission
        # This would require flag access logging
        
        return is_tampered, evidence
    
    def analyze_team_behavior(self, team, event):
        """
        Analyze team's submission behavior for anomalies.
        Returns analysis dictionary.
        """
        submissions = Submission.objects.filter(team=team, event=event)
        
        total_submissions = submissions.count()
        correct_submissions = submissions.filter(status='correct').count()
        incorrect_submissions = submissions.filter(status='incorrect').count()
        
        if total_submissions == 0:
            return {
                'total': 0,
                'correct_rate': 0,
                'anomalies': []
            }
        
        correct_rate = (correct_submissions / total_submissions) * 100
        
        # Calculate average time between submissions
        submissions_ordered = submissions.order_by('submitted_at')
        time_diffs = []
        for i in range(1, len(submissions_ordered)):
            diff = (submissions_ordered[i].submitted_at - submissions_ordered[i-1].submitted_at).total_seconds()
            time_diffs.append(diff)
        
        avg_time_between = sum(time_diffs) / len(time_diffs) if time_diffs else 0
        
        anomalies = []
        
        # Anomaly: Very high correct rate (might indicate cheating)
        if correct_rate > 90 and total_submissions > 10:
            anomalies.append({
                'type': 'suspiciously_high_correct_rate',
                'severity': 'medium',
                'correct_rate': correct_rate,
                'description': f'Team has {correct_rate:.1f}% correct submission rate'
            })
        
        # Anomaly: Very low average time between submissions (bot-like)
        if avg_time_between < 5 and total_submissions > 10:
            anomalies.append({
                'type': 'bot_like_behavior',
                'severity': 'high',
                'avg_time_between': avg_time_between,
                'description': f'Team submits flags very quickly (avg {avg_time_between:.1f}s between)'
            })
        
        return {
            'total': total_submissions,
            'correct': correct_submissions,
            'incorrect': incorrect_submissions,
            'correct_rate': correct_rate,
            'avg_time_between_submissions': avg_time_between,
            'anomalies': anomalies
        }
    
    def get_event_statistics(self, event):
        """
        Get comprehensive statistics for an event.
        """
        from challenges.models import Challenge
        
        stats = {
            'total_submissions': Submission.objects.filter(event=event).count(),
            'correct_submissions': Submission.objects.filter(event=event, status='correct').count(),
            'incorrect_submissions': Submission.objects.filter(event=event, status='incorrect').count(),
            'total_teams': Team.objects.filter(
                submissions__event=event
            ).distinct().count(),
            'active_teams': Team.objects.filter(
                submissions__event=event,
                submissions__submitted_at__gte=timezone.now() - timedelta(hours=1)
            ).distinct().count(),
            'total_violations': Violation.objects.filter(event=event).count(),
            'unresolved_violations': Violation.objects.filter(event=event, is_resolved=False).count(),
            'banned_teams': Team.objects.filter(
                submissions__event=event,
                is_banned=True
            ).distinct().count(),
            'total_instances': ChallengeInstance.objects.filter(event=event).count(),
            'active_instances': ChallengeInstance.objects.filter(
                event=event,
                status='running'
            ).count(),
        }
        
        return stats
    
    def get_challenge_statistics(self, challenge, event):
        """
        Get statistics for a specific challenge.
        """
        submissions = Submission.objects.filter(challenge=challenge, event=event)
        
        stats = {
            'total_submissions': submissions.count(),
            'correct_submissions': submissions.filter(status='correct').count(),
            'first_blood': submissions.filter(
                status='correct'
            ).order_by('submitted_at').first(),
            'solve_count': challenge.solve_count,
            'current_points': challenge.get_current_points(),
            'teams_solved': submissions.filter(status='correct').values('team').distinct().count(),
        }
        
        return stats
    
    def get_team_statistics(self, team, event):
        """
        Get statistics for a team in an event.
        """
        submissions = Submission.objects.filter(team=team, event=event)
        scores = Score.objects.filter(team=team, event=event, score_type='award')
        
        total_points = scores.aggregate(total=Sum('points'))['total'] or 0
        
        stats = {
            'total_submissions': submissions.count(),
            'correct_submissions': submissions.filter(status='correct').count(),
            'incorrect_submissions': submissions.filter(status='incorrect').count(),
            'total_points': total_points,
            'challenges_solved': submissions.filter(status='correct').values('challenge').distinct().count(),
            'violations': Violation.objects.filter(team=team, event=event).count(),
            'is_banned': team.is_banned,
        }
        
        return stats


# Singleton instance
monitoring_service = MonitoringService()

