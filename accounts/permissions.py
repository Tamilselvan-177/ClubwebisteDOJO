from rest_framework import permissions


class IsOwnerOrReadOnly(permissions.BasePermission):
    """
    Custom permission to only allow owners of an object to edit it.
    """

    def has_object_permission(self, request, view, obj):
        # Read permissions are allowed to any request
        if request.method in permissions.SAFE_METHODS:
            return True

        # Write permissions are only allowed to the owner
        return obj.user == request.user


class IsTeamMember(permissions.BasePermission):
    """
    Permission to check if user is a member of a team.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        # Staff can always access
        if request.user.is_staff:
            return True

        # Check if user is a member of the team
        if hasattr(obj, 'team'):
            return obj.team.is_member(request.user)
        elif hasattr(obj, 'is_member'):
            return obj.is_member(request.user)

        return False


class IsTeamCaptain(permissions.BasePermission):
    """
    Permission to check if user is the captain of a team.
    """

    def has_object_permission(self, request, view, obj):
        if not request.user.is_authenticated:
            return False

        # Staff can always access
        if request.user.is_staff:
            return True

        # Check if user is the captain
        if hasattr(obj, 'captain'):
            return obj.captain == request.user
        elif hasattr(obj, 'team') and hasattr(obj.team, 'captain'):
            return obj.team.captain == request.user

        return False


class IsNotBanned(permissions.BasePermission):
    """
    Permission to check if user is not banned.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Staff can always access
        if request.user.is_staff:
            return True

        # Check if user is banned
        return not request.user.is_banned


class IsTeamNotBanned(permissions.BasePermission):
    """
    Permission to check if user's team is not banned.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Staff can always access
        if request.user.is_staff:
            return True

        # Check if user's teams are banned
        user_teams = request.user.teams.all()
        if user_teams.exists():
            return not any(team.is_banned for team in user_teams)

        return True


class IsEmailVerified(permissions.BasePermission):
    """
    Permission to check if user has verified their email address.
    """

    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        # Staff can always access even without verification
        if request.user.is_staff:
            return True

        # Check if user's email is verified
        return request.user.is_email_verified

