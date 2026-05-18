from __future__ import annotations

from .registry import AssistantActionDefinition


def has_permission(permissions: set[str], required_permission: str | None) -> bool:
    if required_permission is None:
        return True
    return "*" in permissions or required_permission in permissions


def can_enable_action(
    permissions: set[str],
    definition: AssistantActionDefinition,
) -> bool:
    return has_permission(permissions, definition.required_permission)
