import re
from pathlib import Path

from apps.assistant.registry import (
    ACTION_REGISTRY,
    PHASE5_ACTION_IDS,
    ROUTE_ACTIONS,
    get_action_definition,
    get_route_action_ids,
)
from apps.assistant.rules import evaluate_rules
from apps.assistant.selectors import AssistantContext
from apps.assistant.services import build_recommendation, shape_recommendations
from apps.scheduling.models import OptimizerRun, PlanVersion, RecoveryRecommendation

PUBLISH_OR_EXPORT_ACTIONS = {"PUBLISH_PLAN", "GENERATE_EXPORT"}
PHASE5_MUTATING_ACTIONS = {
    "GENERATE_RECOVERY_OPTIONS",
    "MATERIALIZE_RECOVERY_RECOMMENDATION",
    "DISMISS_RECOVERY_RECOMMENDATION",
}
FLOW_ACTION_IDS = {
    "VALIDATE_ROOT_CAUSE_REPAIR",
    "REPAIR_PLAN_CONFLICTS",
    "RUN_PUBLISHABILITY_CHECK",
}


def context(**overrides):
    values = {
        "permissions": {"*"},
        "mode": "assisted",
        "route": "/dashboard/situation",
        "demand_count": 2,
        "cargo_layer_issue_count": 0,
        "tide_window_count": 1,
        "bridge_window_count": 1,
        "active_plan_version_id": 7,
        "active_plan_trip_count": 4,
        "active_plan_status": PlanVersion.Status.GENERATED,
        "active_plan_is_editable": True,
    }
    values.update(overrides)
    return AssistantContext(**values)


def action_ids(items):
    return [item.action_id for item in items]


def shaped_for(**overrides):
    ctx = context(**overrides)
    return shape_recommendations(ctx, evaluate_rules(ctx))


def top_action_id(**overrides):
    shaped = shaped_for(**overrides)
    assert shaped.global_next_action
    return shaped.global_next_action.action_id


def representative_contexts():
    return [
        context(
            demand_count=0,
            active_plan_version_id=None,
            active_plan_trip_count=0,
            active_plan_status=None,
            active_plan_is_editable=False,
        ),
        context(cargo_layer_issue_count=1),
        context(tide_window_count=0),
        context(
            active_plan_version_id=None,
            active_plan_trip_count=0,
            active_plan_status=None,
            active_plan_is_editable=False,
        ),
        context(active_plan_status=PlanVersion.Status.PUBLISHED, source_inputs_changed=True),
        context(source_inputs_changed=True),
        context(blocking_conflict_count=1, open_scenario_count=0),
        context(scenario_ready_to_run_count=1),
        context(promotable_scenario_count=1),
        context(pending_approval_count=1, current_user_pending_approval_count=1),
        context(
            active_plan_status=PlanVersion.Status.APPROVED,
            active_plan_is_editable=False,
            all_required_approvals_complete=True,
        ),
        context(
            active_plan_status=PlanVersion.Status.PUBLISHED,
            active_plan_is_editable=False,
            latest_export_for_published_plan_exists=False,
        ),
        context(high_confidence_event_candidate_count=1),
        context(noisy_event_candidate_count=1),
        context(active_override_risk_count=1),
        context(stale_signal_alert_count=1),
        context(
            latest_optimizer_run_id=12,
            latest_optimizer_run_status=OptimizerRun.Status.SUCCEEDED,
            latest_optimizer_run_candidate_count=3,
        ),
        context(
            route="/recovery/recommendations",
            top_recovery_recommendation_id=44,
            top_recovery_recommendation_ref="REC-44",
            top_recovery_recommendation_status=RecoveryRecommendation.Status.CANDIDATE,
        ),
        context(
            route="/recovery/recommendations",
            top_recovery_recommendation_id=45,
            top_recovery_recommendation_status=RecoveryRecommendation.Status.DISMISSED,
        ),
        context(
            route="/recovery/recommendations",
            top_recovery_recommendation_id=46,
            top_recovery_recommendation_status=RecoveryRecommendation.Status.MATERIALIZED,
            top_recovery_recommendation_scenario_id=91,
        ),
        context(
            proof_pack_available=True,
            top_recovery_recommendation_id=47,
            top_recovery_recommendation_ref="REC-47",
        ),
        context(route="/admin/master-data"),
        context(route="/admin/users-rbac"),
        context(recent_governed_mutation_count=1),
        context(
            all_required_approvals_complete=True,
            blocking_conflict_count=1,
            recommendation_origin_scenario_id=91,
        ),
    ]


def test_every_registry_action_has_default_route_ownership():
    unowned = {
        action.action_id
        for action in ACTION_REGISTRY.values()
        if action.action_id not in get_route_action_ids(action.route)
    }

    assert not unowned


def test_route_ownership_covers_every_action_outside_dashboard_catchall():
    route_owned_actions = {
        action_id
        for route, action_ids_for_route in ROUTE_ACTIONS.items()
        if route != "/dashboard/situation"
        for action_id in action_ids_for_route
    }

    assert set(ACTION_REGISTRY) <= route_owned_actions


def test_recovery_recommendations_route_has_object_scoped_phase5_coverage():
    route_action_ids = set(get_route_action_ids("/recovery/recommendations"))

    assert {
        "OPEN_RECOMMENDATION_CONSOLE",
        "MATERIALIZE_RECOVERY_RECOMMENDATION",
        "DISMISS_RECOVERY_RECOMMENDATION",
        "REVIEW_RECOMMENDATION_PROOF_PACK",
    } <= route_action_ids


def test_all_rule_emitted_action_ids_exist_in_registry():
    emitted_action_ids = {
        recommendation.action_id
        for ctx in representative_contexts()
        for recommendation in evaluate_rules(ctx)
    }

    assert emitted_action_ids
    assert emitted_action_ids <= set(ACTION_REGISTRY)


def test_shaping_never_uses_disabled_recommendation_as_global_next_action():
    ctx = context(route="/approvals/publishing", permissions={"schedule.view"})
    disabled_publish = build_recommendation(
        "PUBLISH_PLAN",
        priority="critical",
        rank_score=999,
        enabled=False,
        reason="Synthetic disabled publish candidate.",
        source="test.disabled_publish",
    )
    enabled_exception = build_recommendation(
        "OPEN_EXCEPTION_CENTER",
        priority="normal",
        rank_score=100,
        enabled=True,
        reason="Synthetic enabled exception review.",
        source="test.enabled_exception",
    )

    shaped = shape_recommendations(ctx, [disabled_publish, enabled_exception])

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "OPEN_EXCEPTION_CENTER"
    assert shaped.global_next_action.enabled is True
    assert action_ids(shaped.blocked_actions) == ["PUBLISH_PLAN"]


def test_representative_rule_outputs_shape_only_enabled_global_actions():
    for ctx in representative_contexts():
        shaped = shape_recommendations(ctx, evaluate_rules(ctx))

        if shaped.global_next_action:
            assert shaped.global_next_action.enabled is True


def test_blocking_conflicts_prevent_publish_or_export_top_recommendation():
    shaped = shaped_for(
        active_plan_status=PlanVersion.Status.PUBLISHED,
        active_plan_is_editable=False,
        all_required_approvals_complete=True,
        blocking_conflict_count=1,
        open_scenario_count=1,
        published_snapshot_exists=True,
        latest_export_for_published_plan_exists=False,
    )

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "OPEN_EXCEPTION_CENTER"
    assert shaped.global_next_action.action_id not in PUBLISH_OR_EXPORT_ACTIONS


def test_recommendation_origin_blockers_prevent_publish_or_export_top_action():
    shaped = shaped_for(
        active_plan_status=PlanVersion.Status.PUBLISHED,
        active_plan_is_editable=False,
        all_required_approvals_complete=True,
        blocking_conflict_count=1,
        recommendation_origin_scenario_id=91,
        latest_export_for_published_plan_exists=False,
    )

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "OPEN_EXCEPTION_CENTER"
    assert shaped.global_next_action.source == "recovery.approved_candidate_publish_blocked"
    assert shaped.global_next_action.action_id not in PUBLISH_OR_EXPORT_ACTIONS


def test_phase5_recommendation_handoff_does_not_bypass_scenario_governance():
    candidate = shaped_for(
        route="/recovery/recommendations",
        object_type="recovery_recommendation",
        object_id="44",
        top_recovery_recommendation_id=44,
        top_recovery_recommendation_ref="REC-44",
        top_recovery_recommendation_status=RecoveryRecommendation.Status.CANDIDATE,
    )
    materialized = shaped_for(
        route="/simulation/workspace",
        object_type="simulation_scenario",
        object_id="91",
        top_recovery_recommendation_id=44,
        top_recovery_recommendation_status=RecoveryRecommendation.Status.MATERIALIZED,
        top_recovery_recommendation_scenario_id=91,
        recommendation_origin_scenario_id=91,
        recommendation_origin_scenario_status="draft",
    )

    assert "MATERIALIZE_RECOVERY_RECOMMENDATION" in action_ids(candidate.row_actions)
    assert not (set(action_ids(candidate.row_actions)) & PUBLISH_OR_EXPORT_ACTIONS)
    assert materialized.global_next_action
    assert materialized.global_next_action.action_id == "RUN_SIMULATION"
    assert materialized.global_next_action.action_id not in PUBLISH_OR_EXPORT_ACTIONS


def test_simulation_workspace_shell_action_stays_on_scenario_workflow_with_open_blockers():
    ready_to_run = shaped_for(
        route="/simulation/workspace",
        blocking_conflict_count=2,
        open_scenario_count=1,
        scenario_ready_to_run_count=1,
    )
    promotable = shaped_for(
        route="/simulation/workspace",
        blocking_conflict_count=2,
        open_scenario_count=1,
        promotable_scenario_count=1,
    )
    exception_center = shaped_for(
        route="/exceptions/center",
        blocking_conflict_count=2,
        scenario_ready_to_run_count=1,
    )

    assert ready_to_run.global_next_action
    assert ready_to_run.global_next_action.action_id == "RUN_SIMULATION"
    assert "MATERIALIZE_RECOVERY_RECOMMENDATION" not in action_ids(
        ready_to_run.page_actions
    )
    assert promotable.global_next_action
    assert promotable.global_next_action.action_id == "PROMOTE_SCENARIO"
    assert "MATERIALIZE_RECOVERY_RECOMMENDATION" not in action_ids(
        promotable.page_actions
    )
    assert exception_center.global_next_action
    assert exception_center.global_next_action.action_id == "OPEN_EXCEPTION_CENTER"


def test_phase5_proof_pack_is_low_priority_and_does_not_override_blockers():
    ctx = context(
        route="/recovery/recommendations",
        blocking_conflict_count=1,
        proof_pack_available=True,
        top_recovery_recommendation_id=44,
        top_recovery_recommendation_ref="REC-44",
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))
    proof_pack = next(
        action
        for action in shaped.page_actions
        if action.action_id == "REVIEW_RECOMMENDATION_PROOF_PACK"
    )

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "OPEN_EXCEPTION_CENTER"
    assert proof_pack.priority == "info"
    assert proof_pack.rank_score < shaped.global_next_action.rank_score


def test_phase5_registry_actions_preserve_existing_mutation_governance():
    missing = set(PHASE5_ACTION_IDS) - set(ACTION_REGISTRY)
    assert not missing

    for action_id in PHASE5_MUTATING_ACTIONS:
        action = get_action_definition(action_id)

        assert action.audit_required is True
        assert action.read_only is False
        assert action.required_permission == "schedule.edit"
        assert not action.route.startswith("/api/assistant")

    proof_pack = get_action_definition("REVIEW_RECOMMENDATION_PROOF_PACK")
    assert proof_pack.audit_required is True
    assert proof_pack.read_only is True
    assert proof_pack.required_permission == "schedule.view"


def test_flow_action_registry_governance_and_route_ownership():
    assert FLOW_ACTION_IDS <= set(ACTION_REGISTRY)
    assert "VALIDATE_ROOT_CAUSE_REPAIR" in get_route_action_ids("/recovery/recommendations")
    assert "REPAIR_PLAN_CONFLICTS" in get_route_action_ids("/exceptions/center")
    assert "RUN_PUBLISHABILITY_CHECK" in get_route_action_ids("/approvals/publishing")

    root_cause = get_action_definition("VALIDATE_ROOT_CAUSE_REPAIR")
    publishability = get_action_definition("RUN_PUBLISHABILITY_CHECK")
    repair = get_action_definition("REPAIR_PLAN_CONFLICTS")

    assert root_cause.required_permission == "schedule.view"
    assert root_cause.read_only is True
    assert root_cause.audit_required is False
    assert publishability.required_permission == "schedule.view"
    assert publishability.read_only is True
    assert publishability.audit_required is False
    assert repair.required_permission == "schedule.edit"
    assert repair.read_only is False
    assert repair.audit_required is True


def test_frontend_data_action_ids_map_to_registry_if_present():
    repo_root = Path(__file__).resolve().parents[4]
    frontend_src = repo_root / "frontend" / "src"
    patterns = (
        re.compile(r"data-action-id\s*=\s*['\"]([A-Z0-9_]+)['\"]"),
        re.compile(r"dataActionId\s*[:=]\s*['\"]([A-Z0-9_]+)['\"]"),
    )
    discovered: dict[str, set[str]] = {}

    for source_file in frontend_src.rglob("*"):
        if source_file.suffix not in {".ts", ".tsx", ".js", ".jsx"}:
            continue
        text = source_file.read_text(encoding="utf-8")
        for pattern in patterns:
            for match in pattern.findall(text):
                discovered.setdefault(match, set()).add(str(source_file))

    unknown = sorted(set(discovered) - set(ACTION_REGISTRY))
    assert not unknown
