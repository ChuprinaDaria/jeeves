from rest_framework.permissions import BasePermission, SAFE_METHODS


class IsAdminOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        user = request.user
        return bool(user and user.is_authenticated and (user.is_superuser or getattr(user, 'is_staff_user', False)))


class IsClientOwner(BasePermission):
    def has_object_permission(self, request, view, obj):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        if user.is_superuser or getattr(user, 'is_staff_user', False):
            return True
        # Client can access own objects (support CharField username and User object)
        owner = getattr(obj, 'user', None)
        if owner is None and hasattr(obj, 'client'):
            owner = getattr(obj.client, 'user', None)
        if owner is None:
            return False
        # owner may be a User instance or a username string
        owner_username = getattr(owner, 'username', None) or owner
        return str(owner_username) == str(getattr(user, 'username', ''))

