from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from django.utils import timezone

from apps.scheduling.models import OptimizerRun, PlanVersion, RecoveryRecommendation

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


@dataclass(slots=True)
class AssistantChecklistItem:
    key: str
    label: str
    status: str
    action_id: str | None = None
    route: str | None = None
    reason: str = ""


VALID_ASSISTANT_MODES = {"off", "assisted", "guided", "supervisor"}
RECOVERY_WORKFLOW_NEXT_ACTION_IDS = {
    "VALIDATE_ROOT_CAUSE_REPAIR",
    "MATERIALIZE_RECOVERY_RECOMMENDATION",
    "RUN_SIMULATION",
    "PROMOTE_SCENARIO",
    "REGENERATE_PLAN",
}


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
        and ctx.object_type is not None
        and item.target_object_type == ctx.object_type
        and item.target_object_id == ctx.object_id
    ]
    page_actions = [
        item
        for item in sorted_enabled
        if _action_affects_current_route(item, ctx.route)
        and item not in row_actions
    ][:limit]
    global_next_action = _select_global_next_action(sorted_enabled, ctx)

    return ShapedRecommendations(
        global_next_action=global_next_action,
        page_actions=page_actions,
        row_actions=row_actions[:limit],
        blocked_actions=sorted_blocked[:limit],
    )


def _select_global_next_action(
    sorted_enabled: list[ActionRecommendation],
    ctx,
) -> ActionRecommendation | None:
    if not sorted_enabled:
        return None

    flow_action = next(
        (item for item in sorted_enabled if item.source == "flow.current_step"),
        None,
    )
    if flow_action:
        higher_critical_blocker = next(
            (
                item
                for item in sorted_enabled
                if item.priority == "critical" and item.rank_score > flow_action.rank_score
            ),
            None,
        )
        if higher_critical_blocker:
            return higher_critical_blocker
        return flow_action

    route_workflow_actions = [
        item
        for item in sorted_enabled
        if item.action_id in RECOVERY_WORKFLOW_NEXT_ACTION_IDS
        and _action_affects_current_route(item, ctx.route)
    ]
    if route_workflow_actions:
        return route_workflow_actions[0]

    return sorted_enabled[0]


def build_checklist(ctx, shaped: ShapedRecommendations) -> list[dict[str, Any]]:
    if ctx.mode == "off":
        return []
    if ctx.flow_checklist:
        return ctx.flow_checklist

    blocked_by_action = {action.action_id: action for action in shaped.blocked_actions}
    stages = [
        _stage_demand_imported(ctx),
        _stage_cargo_sequence_reviewed(ctx),
        _stage_operating_windows_entered(ctx),
        _stage_plan_generated(ctx),
        _stage_exceptions_resolved(ctx),
        _stage_recovery_options_generated(ctx),
        _stage_recovery_recommendation_reviewed(ctx),
        _stage_recommendation_materialized(ctx),
        _stage_approval_submitted(ctx),
        _stage_approval_completed(ctx),
        _stage_plan_published(ctx),
        _stage_export_generated(ctx),
        _stage_proof_pack_review(ctx),
    ]

    return [
        _checklist_item_dict(_apply_blocked_stage(stage, blocked_by_action))
        for stage in stages
    ]


def get_next_actions(
    user,
    route: str | None = None,
    object_type: str | None = None,
    object_id: str | int | None = None,
    mode: str = "assisted",
    limit: int = 10,
) -> dict[str, Any]:
    from .rules import evaluate_rules
    from .selectors import build_assistant_context

    resolved_mode = mode if mode in VALID_ASSISTANT_MODES else "assisted"
    bounded_limit = max(1, min(limit, 50))
    ctx = build_assistant_context(
        user=user,
        route=route,
        object_type=object_type,
        object_id=object_id,
        mode=resolved_mode,
    )
    if resolved_mode == "off":
        return _response_payload(ctx, ShapedRecommendations(None, [], [], []))

    recommendations = evaluate_rules(ctx)
    shaped = shape_recommendations(ctx, recommendations, limit=bounded_limit)
    return _response_payload(ctx, shaped)


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


def _stage(
    key: str,
    label: str,
    status: str,
    *,
    action_id: str | None = None,
    reason: str = "",
) -> AssistantChecklistItem:
    route = get_action_definition(action_id).route if action_id else None
    return AssistantChecklistItem(
        key=key,
        label=label,
        status=status,
        action_id=action_id,
        route=route,
        reason=reason,
    )


def _stage_demand_imported(ctx) -> AssistantChecklistItem:
    if ctx.demand_count > 0:
        return _stage(
            "demand_imported",
            "Demand imported",
            "complete",
            reason=f"{ctx.demand_count} active demand row(s) are available.",
        )
    return _stage(
        "demand_imported",
        "Demand imported",
        "current",
        action_id="IMPORT_OGV_DEMAND",
        reason="No active OGV demand is available for planning.",
    )


def _stage_cargo_sequence_reviewed(ctx) -> AssistantChecklistItem:
    if ctx.demand_count == 0:
        return _stage(
            "cargo_sequence_reviewed",
            "Cargo sequence reviewed",
            "pending",
            reason="Import demand before reviewing cargo sequence readiness.",
        )
    if ctx.cargo_layer_issue_count > 0:
        return _stage(
            "cargo_sequence_reviewed",
            "Cargo sequence reviewed",
            "current",
            action_id="REVIEW_COAL_SEQUENCE",
            reason=f"{ctx.cargo_layer_issue_count} cargo layer issue(s) need review.",
        )
    return _stage(
        "cargo_sequence_reviewed",
        "Cargo sequence reviewed",
        "complete",
        reason="No open cargo sequence issue is blocking planning.",
    )


def _stage_operating_windows_entered(ctx) -> AssistantChecklistItem:
    if ctx.demand_count == 0:
        return _stage(
            "operating_windows_entered",
            "Operating windows entered",
            "pending",
            reason="Demand intake must exist before operating windows can be checked.",
        )
    if ctx.tide_window_count > 0 and ctx.bridge_window_count > 0:
        return _stage(
            "operating_windows_entered",
            "Operating windows entered",
            "complete",
            reason="Active tide and bridge windows are available.",
        )
    return _stage(
        "operating_windows_entered",
        "Operating windows entered",
        "current",
        action_id="ENTER_OPERATING_WINDOWS",
        reason="Tide or bridge operating windows are missing.",
    )


def _stage_plan_generated(ctx) -> AssistantChecklistItem:
    if (
        ctx.active_plan_version_id
        and ctx.active_plan_trip_count > 0
        and ctx.active_plan_status != PlanVersion.Status.DRAFT
    ):
        return _stage(
            "plan_generated",
            "Plan generated",
            "complete",
            reason=f"Active plan version {ctx.active_plan_version_id} has generated trips.",
        )
    if ctx.demand_count > 0 and ctx.tide_window_count > 0 and ctx.bridge_window_count > 0:
        return _stage(
            "plan_generated",
            "Plan generated",
            "current",
            action_id="GENERATE_PLAN",
            reason="Demand and operating windows are ready for plan generation.",
        )
    return _stage(
        "plan_generated",
        "Plan generated",
        "pending",
        reason="Complete demand and operating-window readiness first.",
    )


def _stage_exceptions_resolved(ctx) -> AssistantChecklistItem:
    if not ctx.active_plan_version_id:
        return _stage(
            "exceptions_resolved",
            "Exceptions resolved",
            "pending",
            reason="Generate a plan before exception readiness can be evaluated.",
        )
    if ctx.blocking_conflict_count > 0:
        return _stage(
            "exceptions_resolved",
            "Exceptions resolved",
            "current",
            action_id="OPEN_EXCEPTION_CENTER",
            reason=f"{ctx.blocking_conflict_count} unresolved blocking conflict(s) remain.",
        )
    return _stage(
        "exceptions_resolved",
        "Exceptions resolved",
        "complete",
        reason="No unresolved blocking conflicts are open.",
    )


def _stage_recovery_options_generated(ctx) -> AssistantChecklistItem:
    if (
        ctx.latest_optimizer_run_id
        and ctx.latest_optimizer_run_status == OptimizerRun.Status.SUCCEEDED
    ):
        return _stage(
            "recovery_options_generated",
            "Recovery options generated",
            "complete",
            reason=f"Optimizer run {ctx.latest_optimizer_run_id} produced candidate options.",
        )
    if ctx.latest_optimizer_run_id:
        return _stage(
            "recovery_options_generated",
            "Recovery options generated",
            "pending",
            reason="A recovery optimizer run exists but has not produced successful options.",
        )
    if _disruption_count(ctx) > 0:
        return _stage(
            "recovery_options_generated",
            "Recovery options generated",
            "current",
            action_id="GENERATE_RECOVERY_OPTIONS",
            reason="A governed disruption is ready for Phase 5 recovery options.",
        )
    return _stage(
        "recovery_options_generated",
        "Recovery options generated",
        "pending",
        reason="No governed disruption is waiting for recovery options.",
    )


def _stage_recovery_recommendation_reviewed(ctx) -> AssistantChecklistItem:
    if (
        ctx.top_recovery_recommendation_scenario_id
        or ctx.materialized_recovery_recommendation_count
    ):
        return _stage(
            "recovery_recommendation_reviewed",
            "Recovery recommendation reviewed",
            "complete",
            reason="A recommendation has already moved into governed scenario handoff.",
        )
    if (
        ctx.latest_optimizer_run_status == OptimizerRun.Status.SUCCEEDED
        and ctx.latest_optimizer_run_candidate_count > 0
    ):
        return _stage(
            "recovery_recommendation_reviewed",
            "Recovery recommendation reviewed",
            "current",
            action_id="OPEN_RECOMMENDATION_CONSOLE",
            reason="Ranked recovery recommendations are ready for operator review.",
        )
    return _stage(
        "recovery_recommendation_reviewed",
        "Recovery recommendation reviewed",
        "pending",
        reason="Generate recovery options before recommendation review.",
    )


def _stage_recommendation_materialized(ctx) -> AssistantChecklistItem:
    if (
        ctx.top_recovery_recommendation_scenario_id
        or ctx.materialized_recovery_recommendation_count
    ):
        return _stage(
            "recommendation_materialized",
            "Recommendation tested as scenario",
            "complete",
            reason="The selected recommendation has a governed scenario handoff.",
        )
    if (
        ctx.top_recovery_recommendation_status == RecoveryRecommendation.Status.DISMISSED
        and ctx.top_recovery_recommendation_id
    ):
        return _stage(
            "recommendation_materialized",
            "Recommendation tested as scenario",
            "blocked",
            action_id="MATERIALIZE_RECOVERY_RECOMMENDATION",
            reason="The selected recommendation was dismissed.",
        )
    if (
        ctx.top_recovery_recommendation_id
        and ctx.top_recovery_recommendation_status != RecoveryRecommendation.Status.MATERIALIZED
    ):
        return _stage(
            "recommendation_materialized",
            "Recommendation tested as scenario",
            "current",
            action_id="MATERIALIZE_RECOVERY_RECOMMENDATION",
            reason="The top recovery recommendation is ready to be tested as a scenario.",
        )
    return _stage(
        "recommendation_materialized",
        "Recommendation tested as scenario",
        "pending",
        reason="Review a recovery recommendation before scenario testing.",
    )


def _stage_approval_submitted(ctx) -> AssistantChecklistItem:
    if (
        ctx.pending_approval_count > 0
        or ctx.all_required_approvals_complete
        or ctx.active_plan_status in {
            PlanVersion.Status.APPROVED,
            PlanVersion.Status.PUBLISHED,
        }
    ):
        return _stage(
            "approval_submitted",
            "Approval submitted",
            "complete",
            reason="The active plan has entered approval governance.",
        )
    if (
        ctx.active_plan_status
        in {
            PlanVersion.Status.DRAFT,
            PlanVersion.Status.GENERATED,
            PlanVersion.Status.VALIDATED,
            PlanVersion.Status.PROPOSED,
        }
        and ctx.active_plan_trip_count > 0
        and ctx.blocking_conflict_count == 0
    ):
        return _stage(
            "approval_submitted",
            "Approval submitted",
            "current",
            action_id="SUBMIT_APPROVAL",
            reason="The active plan is ready for approval submission.",
        )
    return _stage(
        "approval_submitted",
        "Approval submitted",
        "pending",
        reason="Resolve plan generation and blocking exceptions before approval.",
    )


def _stage_approval_completed(ctx) -> AssistantChecklistItem:
    if ctx.all_required_approvals_complete or ctx.active_plan_status in {
        PlanVersion.Status.APPROVED,
        PlanVersion.Status.PUBLISHED,
    }:
        return _stage(
            "approval_completed",
            "Approval completed",
            "complete",
            reason="Required approval authorities are complete.",
        )
    if ctx.current_user_pending_approval_count > 0:
        return _stage(
            "approval_completed",
            "Approval completed",
            "current",
            action_id="APPROVE_PLAN",
            reason="An approval decision is waiting for your authority.",
        )
    if ctx.pending_approval_count > 0:
        return _stage(
            "approval_completed",
            "Approval completed",
            "current",
            action_id="APPROVE_PLAN",
            reason="Approval decisions are still pending.",
        )
    return _stage(
        "approval_completed",
        "Approval completed",
        "pending",
        reason="Submit approval before completing authority decisions.",
    )


def _stage_plan_published(ctx) -> AssistantChecklistItem:
    if ctx.published_snapshot_exists or ctx.active_plan_status == PlanVersion.Status.PUBLISHED:
        return _stage(
            "plan_published",
            "Plan published",
            "complete",
            reason="An active published snapshot exists.",
        )
    publishability_clear = (
        ctx.publishability_status in {"publishable", "warning"}
        and ctx.publishability_assessment_id is not None
        and not ctx.publishability_is_stale
    )
    if ctx.all_required_approvals_complete and ctx.blocking_conflict_count == 0 and publishability_clear:
        return _stage(
            "plan_published",
            "Plan published",
            "current",
            action_id="PUBLISH_PLAN",
            reason="Approvals and publishability are complete and the plan is ready to publish.",
        )
    if ctx.all_required_approvals_complete and ctx.blocking_conflict_count == 0:
        return _stage(
            "plan_published",
            "Plan published",
            "blocked",
            action_id="RUN_PUBLISHABILITY_CHECK",
            reason="Run a clear publishability assessment before publishing.",
        )
    if ctx.all_required_approvals_complete and ctx.blocking_conflict_count > 0:
        return _stage(
            "plan_published",
            "Plan published",
            "blocked",
            action_id="OPEN_EXCEPTION_CENTER",
            reason="Publication is blocked until unresolved conflicts are cleared.",
        )
    return _stage(
        "plan_published",
        "Plan published",
        "pending",
        reason="Complete approval governance before publishing.",
    )


def _stage_export_generated(ctx) -> AssistantChecklistItem:
    if ctx.latest_export_for_published_plan_exists:
        return _stage(
            "export_generated",
            "Export generated",
            "complete",
            reason="The published plan has a governed export artifact.",
        )
    if ctx.active_plan_status == PlanVersion.Status.PUBLISHED or ctx.published_snapshot_exists:
        return _stage(
            "export_generated",
            "Export generated",
            "current",
            action_id="GENERATE_EXPORT",
            reason="Generate the governed export artifact for handoff.",
        )
    return _stage(
        "export_generated",
        "Export generated",
        "pending",
        reason="Publish a plan before generating final handoff exports.",
    )


def _stage_proof_pack_review(ctx) -> AssistantChecklistItem:
    if ctx.proof_pack_available:
        return _stage(
            "recommendation_proof_pack_reviewed",
            "Recommendation proof pack reviewed",
            "current",
            action_id="REVIEW_RECOMMENDATION_PROOF_PACK",
            reason="Phase 5 recommendation proof evidence is available for review.",
        )
    return _stage(
        "recommendation_proof_pack_reviewed",
        "Recommendation proof pack reviewed",
        "pending",
        reason="Proof evidence appears after recommendation scenario handoff.",
    )


def _disruption_count(ctx) -> int:
    return (
        ctx.blocking_conflict_count
        + ctx.critical_conflict_count
        + ctx.open_tracking_alert_count
        + ctx.pending_event_candidate_count
        + ctx.active_override_risk_count
    )


def _apply_blocked_stage(
    item: AssistantChecklistItem,
    blocked_by_action: dict[str, ActionRecommendation],
) -> AssistantChecklistItem:
    if item.status not in {"current", "blocked"} or not item.action_id:
        return item
    blocked_action = blocked_by_action.get(item.action_id)
    if not blocked_action:
        return item
    return AssistantChecklistItem(
        key=item.key,
        label=item.label,
        status="blocked",
        action_id=item.action_id,
        route=item.route,
        reason=blocked_action.blocked_reason or item.reason,
    )


def _checklist_item_dict(item: AssistantChecklistItem) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "key": item.key,
        "label": item.label,
        "status": item.status,
    }
    if item.action_id:
        payload["action_id"] = item.action_id
    if item.route:
        payload["route"] = item.route
    if item.reason:
        payload["reason"] = item.reason
    return payload


def _response_payload(ctx, shaped: ShapedRecommendations) -> dict[str, Any]:
    return {
        "generated_at": timezone.now(),
        "mode": ctx.mode,
        "context": {
            "route": ctx.route,
            "object_type": ctx.object_type,
            "object_id": ctx.object_id,
            "active_plan_version_id": ctx.active_plan_version_id,
            "active_plan_status": ctx.active_plan_status,
            "validation_status": ctx.validation_status,
            "role_codes": sorted(ctx.role_codes),
            "demand_count": ctx.demand_count,
            "blocking_conflict_count": ctx.blocking_conflict_count,
            "latest_optimizer_run_id": ctx.latest_optimizer_run_id,
            "top_recovery_recommendation_id": ctx.top_recovery_recommendation_id,
            "publishability_status": ctx.publishability_status,
            "publishability_assessment_id": ctx.publishability_assessment_id,
            "publishability_blocking_reason_count": (
                ctx.publishability_blocking_reason_count
            ),
            "publishability_warning_count": ctx.publishability_warning_count,
            "publishability_top_blocker": ctx.publishability_top_blocker,
            "latest_global_optimization_run_id": ctx.latest_global_optimization_run_id,
            "latest_global_optimization_candidate_id": (
                ctx.latest_global_optimization_candidate_id
            ),
            "latest_global_optimization_candidate_count": (
                ctx.latest_global_optimization_candidate_count
            ),
        },
        "global_next_action": shaped.global_next_action,
        "page_actions": shaped.page_actions,
        "row_actions": shaped.row_actions,
        "blocked_actions": shaped.blocked_actions,
        "checklist": build_checklist(ctx, shaped),
        "flow": _flow_payload(ctx),
    }


def _flow_payload(ctx) -> dict[str, Any] | None:
    if ctx.mode == "off" or not ctx.active_flow_run_id:
        return None
    return {
        "active_flow": ctx.active_flow_key,
        "flow_run_id": ctx.active_flow_run_id,
        "flow_name": ctx.active_flow_name,
        "flow_status": ctx.active_flow_status,
        "current_step": ctx.current_flow_step_key,
        "current_step_label": ctx.current_flow_step_label,
        "step_status": ctx.current_flow_step_status,
        "expected_route": ctx.expected_flow_route,
        "expected_action_id": ctx.expected_flow_action_id,
        "blocked_reason": ctx.flow_blocked_reason,
        "trial_pack": ctx.flow_trial_pack,
        "evidence_run_id": ctx.flow_evidence_run_id,
        "expected_action_ids": ctx.flow_expected_action_ids,
    }
