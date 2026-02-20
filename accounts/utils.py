"""
Utility functions for accounts app.
"""
from django.core.cache import cache
from django.utils import timezone


def get_user_teams(user):
    """
    Get all active teams for a user.
    """
    if not user.is_authenticated:
        return []
    return user.teams.filter(memberships__is_active=True)


def get_user_team_for_event(user, event):
    """
    Get user's team for a specific event.
    In future, teams can be event-specific.
    For now, return first active team.
    """
    teams = get_user_teams(user)
    if teams.exists():
        return teams.first()
    return None


def is_user_in_team(user, team):
    """
    Check if user is in a team.
    """
    if not user.is_authenticated or not team:
        return False
    return team.is_member(user)


def can_user_create_team(user):
    """
    Check if user can create a new team.
    Rules: User must not be banned, can create multiple teams (for now).
    """
    if not user.is_authenticated:
        return False
    if user.is_banned:
        return False
    return True


def get_user_permissions(user):
    """
    Get user permissions as a dictionary.
    """
    if not user.is_authenticated:
        return {
            'is_authenticated': False,
            'is_staff': False,
            'is_superuser': False,
            'is_banned': False,
        }

    return {
        'is_authenticated': True,
        'is_staff': user.is_staff,
        'is_superuser': user.is_superuser,
        'is_banned': user.is_banned,
        'username': user.username,
        'user_id': user.id,
    }

