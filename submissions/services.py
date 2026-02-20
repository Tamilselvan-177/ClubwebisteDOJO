"""
Services for submission and scoring logic.
"""
import re
import logging
import hashlib
from django.utils import timezone
from django.db.models import Q, Sum
from django.core.cache import cache
from .models import Submission, Score, Violation
from challenges.models import Challenge, ChallengeInstance

logger = logging.getLogger(__name__)


class SubmissionService:
    """
    Service class for handling flag submissions and scoring.
    Enhanced with security auditing and anomaly detection.
    """
    
    def validate_flag(self, submitted_flag, challenge, instance=None):
        """
        Validate a submitted flag.
        Returns (is_valid, is_correct, error_message)
        
        SECURITY:
        - Sanitizes flag input
        - Uses hash comparison for O(1) lookup on instance flags
        """
        # Sanitize input - remove null bytes and excessive whitespace
        try:
            submitted_flag = str(submitted_flag)[:1000]  # Prevent huge payloads
            if '\x00' in submitted_flag:
                return False, False, "Invalid flag format"
        except Exception as e:
            logger.error(f"Flag validation error: {e}")
            return False, False, "Flag validation error"
        
        # For instance-based challenges, use hash comparison for speed
        if challenge.challenge_type == 'instance':
            if not instance:
                return False, False, "Instance ID required for instance-based challenges"
            
            # O(1) hash comparison instead of O(n) string comparison
            submitted_hash = hashlib.sha256(submitted_flag.strip().encode()).hexdigest()
            if submitted_hash == instance.flag_hash:
                return True, True, None
            else:
                return True, False, "Incorrect flag"
        
        # For standard challenges, check challenge flag
        if challenge.flag_type == 'static':
            if submitted_flag.strip() == challenge.flag:
                return True, True, None
            else:
                return True, False, "Incorrect flag"
        
        elif challenge.flag_type == 'regex':
            try:
                pattern = challenge.flag
                if re.match(pattern, submitted_flag.strip()):
                    return True, True, None
                else:
                    return True, False, "Incorrect flag"
            except re.error as e:
                logger.error(f"Invalid regex pattern in challenge {challenge.id}: {e}")
                return False, False, "Flag validation error"
        
        return False, False, "Unknown flag type"
    
    def check_copied_flag(self, submitted_flag, team, event, challenge=None):
        """
        Check if submitted flag matches another team's instance flag using indexed hash lookup - O(1).
        Only flags as copying if:
        1. Flag hash matches another team's instance
        2. For the SAME challenge (prevents wrong challenge submission from triggering ban)
        
        Returns (is_copied, matching_instance, evidence)
        """
        if not challenge:
            return False, None, {}
        
        # O(1) hash lookup using indexed flag_hash column
        submitted_hash = hashlib.sha256(submitted_flag.strip().encode()).hexdigest()
        
        # Single indexed query - very fast due to flag_hash index + compound filters
        instance_match = ChallengeInstance.objects.filter(
            event=event,
            challenge=challenge,
            flag_hash=submitted_hash
        ).exclude(team=team).select_related('team', 'challenge').first()
        
        if instance_match:
            evidence = {
                'matched_instance_id': instance_match.instance_id,
                'matched_team': instance_match.team.name,
                'matched_challenge': instance_match.challenge.name,
                'submitted_flag': submitted_flag.strip(),
                'instance_status': instance_match.status
            }
            return True, instance_match, evidence
        
        return False, None, {}
    
    def check_duplicate_submission(self, team, challenge, event, submitted_flag):
        """
        Check if team has already submitted this flag correctly.
        Returns (is_duplicate, existing_submission)
        """
        existing = Submission.objects.filter(
            team=team,
            challenge=challenge,
            event=event,
            flag=submitted_flag.strip(),
            status='correct'
        ).first()
        
        if existing:
            return True, existing
        return False, None
    
    def _team_has_solved(self, team, challenge, event):
        """Check if the team already solved this challenge for the event."""
        return Submission.objects.filter(
            team=team,
            challenge=challenge,
            event=event,
            status='correct'
        ).exists()

    def get_team_penalty(self, team, challenge, event):
        """
        Return the cumulative point penalty (negative value) applied to a team for a challenge.
        Penalties are stored as score_type='reduction' but do not reduce total_score; they
        only affect the next award amount for this team.
        """
        return Score.objects.filter(
            team=team,
            challenge=challenge,
            event=event,
            score_type='reduction'
        ).aggregate(total=Sum('points'))['total'] or 0

    def calculate_points(self, challenge, event, team):
        """
        Calculate points to award for solving this challenge for a specific team.
        Uses global challenge points as baseline, then subtracts any per-team penalties.
        """
        base_points = challenge.get_current_points()
        penalty = self.get_team_penalty(team, challenge, event)  # negative or 0
        return max(challenge.minimum_points, base_points + penalty)
    
    def calculate_team_total_score(self, team, event):
        """
        Calculate team's total score for an event (leaderboard score).
        
        IMPORTANT: Only counts 'award' and 'adjustment' types.
        Penalties ('reduction' type) do NOT reduce team's total earned score.
        Penalties only affect challenge-specific scores (see get_team_penalty).
        
        Returns total score.
        """
        scores = Score.objects.filter(
            team=team,
            event=event,
            score_type__in=['award', 'adjustment']
        ).aggregate(
            total=Sum('points')
        )['total'] or 0

        # Reductions do NOT decrease earned points; they only affect challenge-specific scores.
        return max(0, scores)
    
    def award_points(self, team, challenge, event, submission, points):
        """
        Award points to team for solving challenge.
        Creates Score entry and updates challenge solve_count.
        Returns created Score object.
        """
        from django.db import transaction
        # Block score updates when scoreboard is frozen
        if getattr(event, 'is_scoreboard_frozen', False):
            logger.info(f"Scoreboard frozen; skipping award points for team {team.name} on {challenge.name}")
            return None
        
        with transaction.atomic():
            # Calculate team's new total score
            current_total = self.calculate_team_total_score(team, event)
            new_total = current_total + points
            
            # Create score entry
            score = Score.objects.create(
                team=team,
                challenge=challenge,
                event=event,
                submission=submission,
                points=points,
                score_type='award',
                total_score=new_total,
                reason='Correct flag submission'
            )
            
            # Increment solve count for dynamic scoring
            challenge.solve_count += 1
            challenge.save(update_fields=['solve_count'])
            
            logger.info(f"Awarded {points} points to team {team.name} for challenge {challenge.name}")
            return score
    
    def reduce_points_on_wrong_submission(self, team, challenge, event, submission):
        """Apply a per-team penalty for a wrong flag without removing earned points."""
        # Block penalties when scoreboard is frozen
        if getattr(event, 'is_scoreboard_frozen', False):
            logger.info(f"Scoreboard frozen; skipping penalty reduction for team {team.name} on {challenge.name}")
            return 0
        if self._team_has_solved(team, challenge, event):
            return 0

        # Get current team total score (penalties don't change this)
        current_team_score = self.calculate_team_total_score(team, event)

        # Fixed 10% penalty of base challenge points, minimum 1.
        reduction = max(1, int(challenge.points * 0.10))

        # Record penalty as reduction entry (affects challenge score only, NOT team total score)
        # total_score stays the same because penalties don't reduce earned points
        Score.objects.create(
            team=team,
            challenge=challenge,
            event=event,
            submission=submission,
            points=-reduction,
            score_type='reduction',
            total_score=current_team_score,  # UNCHANGED - penalties don't reduce team total
            reason='Wrong flag submission (team-scoped penalty)',
            notes="Penalty affects only this team's future award; earned score is unchanged"
        )

        return reduction
    
    def create_violation(self, team, event, challenge, submission, instance, violation_type, evidence):
        """
        Create a violation record for cheating.
        Returns created Violation object.
        """
        violation = Violation.objects.create(
            team=team,
            event=event,
            challenge=challenge,
            submission=submission,
            instance=instance,
            violation_type=violation_type,
            severity='critical',
            description=f"Team submitted flag from another team's instance",
            evidence=evidence,
            detected_by='system'
        )
        
        logger.warning(f"Violation created for team {team.name}: {violation_type}")
        
        # Send notification
        try:
            from notifications.services import notification_service
            notification_service.notify_violation_detected(violation)
        except Exception as e:
            logger.error(f"Failed to send violation notification: {e}")
        
        return violation
    
    def ban_team(self, team, reason="Cheating violation", event=None):
        """
        Ban a team for cheating.
        """
        team.ban(reason)
        logger.warning(f"Team {team.name} banned: {reason}")


# Singleton instance
submission_service = SubmissionService()

