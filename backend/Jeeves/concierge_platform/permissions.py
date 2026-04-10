from rest_framework.permissions import BasePermission

from Jeeves.accounts.models import Roles


class IsOwner(BasePermission):
    """Allow only authenticated users with role='owner'.

    Used to gate all /api/owner/* endpoints and the authenticated setup
    wizard steps. Single-admin per installation — the owner is the
    purchaser who runs the self-hosted copy of Jeeves.
    """

    message = "Owner role required."

    def has_permission(self, request, view):
        user = getattr(request, "user", None)
        return bool(
            user
            and user.is_authenticated
            and getattr(user, "role", None) == Roles.OWNER
        )
