from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .registry import get_action_definition


@dataclass(slots=True)
class ActionRecommendation:
    action_id: str
    label: str
    priority: str
    rank_score: int
    enabled: bool
    route: str
    cta_label: str
    reason: str
    hover_hint: str = ""
    detail_text: str = ""
    impact_if_ignored: str = ""
    owner_role: str = ""
    required_permission: str | None = None
    audit_required: bool = False
    target_object_type: str | None = None
    target_object_id: str | None = None
    blocked_reason: str = ""
    source: str = ""
    expires_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def build_recommendation(
    action_id: str,
    *,
    priority: str,
    rank_score: int,
    enabled: bool,
    reason: str,
    source: str,
    target_object_type: str | None = None,
    target_object_id: str | int | None = None,
    blocked_reason: str = "",
    route: str | None = None,
    owner_role: str | None = None,
    impact_if_ignored: str = "",
    metadata: dict[str, Any] | None = None,
) -> ActionRecommendation:
    definition = get_action_definition(action_id)
    resolved_owner_role = owner_role or (
        definition.owner_roles[0] if definition.owner_roles else ""
    )
    resolved_target_object_id = (
        str(target_object_id) if target_object_id is not None else None
    )

    return ActionRecommendation(
        action_id=definition.action_id,
        label=definition.label,
        priority=priority,
        rank_score=rank_score,
        enabled=enabled,
        route=route or definition.route,
        cta_label=definition.cta_label,
        reason=reason,
        hover_hint=reason,
        detail_text=reason,
        impact_if_ignored=impact_if_ignored,
        owner_role=resolved_owner_role,
        required_permission=definition.required_permission,
        audit_required=definition.audit_required,
        target_object_type=target_object_type,
        target_object_id=resolved_target_object_id,
        blocked_reason=blocked_reason,
        source=source,
        metadata=metadata or {},
    )
