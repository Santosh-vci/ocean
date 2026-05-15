from collections.abc import Iterable

from django.contrib.auth.models import AbstractBaseUser

from .models import UserRoleAssignment


def permission_codes_for_user(user: AbstractBaseUser) -> set[str]:
    if not user.is_authenticated:
        return set()

    if user.is_superuser:
        return {"*"}

    assignments = (
        UserRoleAssignment.objects.filter(user=user, is_active=True, role__is_active=True)
        .prefetch_related("role__permissions")
        .all()
    )

    codes: set[str] = set()
    for assignment in assignments:
        codes.update(assignment.role.permissions.values_list("code", flat=True))

    return codes


def user_has_permission_code(user: AbstractBaseUser, code: str) -> bool:
    codes = permission_codes_for_user(user)
    return "*" in codes or code in codes


def has_any_permission(user: AbstractBaseUser, codes: Iterable[str]) -> bool:
    current_codes = permission_codes_for_user(user)
    return "*" in current_codes or any(code in current_codes for code in codes)

