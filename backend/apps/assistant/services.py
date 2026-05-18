from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from .permissions import has_permission
from .registry import get_action_definition, get_route_action_ids


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


@dataclass(slots=True)
class ShapedRecommendations:
    global_next_action: ActionRecommendation | None
    page_actions: list[ActionRecommendation]
    row_actions: list[ActionRecommendation]
    blocked_actions: list[ActionRecommendation]


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


def dedupe_recommendations(
    items: list[ActionRecommendation],
) -> list[ActionRecommendation]:
    by_key: dict[tuple[str, str | None, str | None], ActionRecommendation] = {}
    for item in items:
        key = (item.action_id, item.target_object_type, item.target_object_id)
        current = by_key.get(key)
        if current is None or item.rank_score > current.rank_score:
            by_key[key] = item
    return list(by_key.values())


def sort_recommendations(
    items: list[ActionRecommendation],
    *,
    route: str | None = None,
    object_type: str | None = None,
    object_id: str | None = None,
) -> list[ActionRecommendation]:
    return sorted(
        items,
        key=lambda item: (
            item.rank_score,
            _priority_weight(item.priority),
            _route_match(item, route),
            _object_match(item, object_type, object_id),
        ),
        reverse=True,
    )


def shape_recommendations(
    ctx,
    recommendations: list[ActionRecommendation],
    *,
    limit: int = 10,
) -> ShapedRecommendations:
    enabled: list[ActionRecommendation] = []
    blocked: list[ActionRecommendation] = []

    for recommendation in recommendations:
        action_definition = get_action_definition(recommendation.action_id)
        if not recommendation.enabled:
            blocked.append(_blocked_copy(recommendation, action_definition.fallback_message))
            continue
        if has_permission(ctx.permissions, action_definition.required_permission):
            enabled.append(recommendation)
            continue
        if _action_affects_current_route(recommendation, ctx.route):
            blocked.append(
                _blocked_copy(
                    recommendation,
                    (
                        f"You do not have {action_definition.required_permission} permission. "
                        f"{action_definition.fallback_message}"
                    ),
                )
            )

    sorted_enabled = sort_recommendations(
        dedupe_recommendations(enabled),
        route=ctx.route,
        object_type=ctx.object_type,
        object_id=ctx.object_id,
    )
    sorted_blocked = sort_recommendations(
        dedupe_recommendations(blocked),
        route=ctx.route,
        object_type=ctx.object_type,
        object_id=ctx.object_id,
    )
    row_actions = [
        item
        for item in sorted_enabled
        if item.target_object_type
        and (
            ctx.object_type is None
            or (
                item.target_object_type == ctx.object_type
                and item.target_object_id == ctx.object_id
            )
        )
    ]
    page_actions = [
        item
        for item in sorted_enabled
        if _action_affects_current_route(item, ctx.route)
        and item not in row_actions
    ][:limit]
    global_next_action = sorted_enabled[0] if sorted_enabled else None

    return ShapedRecommendations(
        global_next_action=global_next_action,
        page_actions=page_actions,
        row_actions=row_actions[:limit],
        blocked_actions=sorted_blocked[:limit],
    )


def _blocked_copy(
    recommendation: ActionRecommendation,
    blocked_reason: str,
) -> ActionRecommendation:
    return ActionRecommendation(
        action_id=recommendation.action_id,
        label=recommendation.label,
        priority=recommendation.priority,
        rank_score=recommendation.rank_score,
        enabled=False,
        route=recommendation.route,
        cta_label=recommendation.cta_label,
        reason=recommendation.reason,
        hover_hint=recommendation.hover_hint,
        detail_text=recommendation.detail_text,
        impact_if_ignored=recommendation.impact_if_ignored,
        owner_role=recommendation.owner_role,
        required_permission=recommendation.required_permission,
        audit_required=recommendation.audit_required,
        target_object_type=recommendation.target_object_type,
        target_object_id=recommendation.target_object_id,
        blocked_reason=recommendation.blocked_reason or blocked_reason,
        source=recommendation.source,
        expires_at=recommendation.expires_at,
        metadata=recommendation.metadata,
    )


def _priority_weight(priority: str) -> int:
    return {
        "critical": 4,
        "warning": 3,
        "normal": 2,
        "info": 1,
    }.get(priority, 0)


def _route_match(item: ActionRecommendation, route: str | None) -> int:
    if not route:
        return 0
    return int(_action_affects_current_route(item, route))


def _object_match(
    item: ActionRecommendation,
    object_type: str | None,
    object_id: str | None,
) -> int:
    if not object_type or not object_id:
        return 0
    return int(item.target_object_type == object_type and item.target_object_id == object_id)


def _action_affects_current_route(
    item: ActionRecommendation,
    route: str | None,
) -> bool:
    if not route:
        return False
    if item.route == route:
        return True
    return item.action_id in get_route_action_ids(route)
