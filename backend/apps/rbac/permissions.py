from rest_framework.permissions import BasePermission

from .services import user_has_permission_code


class RequiresAccessPermission(BasePermission):
    message = "You do not have permission to perform this action."

    def has_permission(self, request, view) -> bool:
        if not request.user or not request.user.is_authenticated:
            return False

        action = getattr(view, "action", request.method.lower())
        action_permission_map = getattr(view, "action_permission_map", {})
        required_permission = action_permission_map.get(action)

        if required_permission is None:
            return request.user.is_superuser

        return user_has_permission_code(request.user, required_permission)

