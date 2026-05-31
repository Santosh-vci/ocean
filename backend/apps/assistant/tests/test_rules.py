from apps.assistant.rules import evaluate_rules
from apps.assistant.selectors import AssistantContext
from apps.assistant.services import build_checklist, build_recommendation, shape_recommendations
from apps.scheduling.models import OptimizerRun, PlanVersion, RecoveryRecommendation


def context(**overrides):
    values = {
        "permissions": {"*"},
        "mode": "assisted",
        "route": "/dashboard/situation",
    }
    values.update(overrides)
    return AssistantContext(**values)


def action_ids(items):
    return [item.action_id for item in items]


def checklist_by_key(items):
    return {item["key"]: item for item in items}


def test_no_demand_recommends_import_demand():
    recommendations = evaluate_rules(context(demand_count=0))

    assert "IMPORT_OGV_DEMAND" in action_ids(recommendations)


def test_demand_without_windows_recommends_operating_windows():
    recommendations = evaluate_rules(
        context(demand_count=2, tide_window_count=0, bridge_window_count=1),
    )

    assert "ENTER_OPERATING_WINDOWS" in action_ids(recommendations)


def test_ready_planning_state_recommends_generate_plan():
    recommendations = evaluate_rules(
        context(
            demand_count=2,
            tide_window_count=1,
            bridge_window_count=1,
            active_plan_version_id=None,
        ),
    )

    assert "GENERATE_PLAN" in action_ids(recommendations)


def test_checklist_marks_completed_stages_correctly():
    ctx = context(
        demand_count=2,
        cargo_layer_issue_count=0,
        tide_window_count=1,
        bridge_window_count=1,
        active_plan_version_id=7,
        active_plan_trip_count=4,
        active_plan_status=PlanVersion.Status.GENERATED,
        blocking_conflict_count=0,
    )

    checklist = checklist_by_key(build_checklist(ctx, shape_recommendations(ctx, [])))

    assert checklist["demand_imported"]["status"] == "complete"
    assert checklist["cargo_sequence_reviewed"]["status"] == "complete"
    assert checklist["operating_windows_entered"]["status"] == "complete"
    assert checklist["plan_generated"]["status"] == "complete"
    assert checklist["exceptions_resolved"]["status"] == "complete"
    assert checklist["approval_submitted"]["status"] == "current"
    assert checklist["approval_submitted"]["action_id"] == "SUBMIT_APPROVAL"


def test_checklist_marks_blocked_current_stage_with_action_id():
    ctx = context(permissions={"schedule.view"}, route="/dashboard/situation", demand_count=0)
    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    checklist = checklist_by_key(build_checklist(ctx, shaped))

    assert checklist["demand_imported"]["status"] == "blocked"
    assert checklist["demand_imported"]["action_id"] == "IMPORT_OGV_DEMAND"
    assert "schedule.edit" in checklist["demand_imported"]["reason"]


def test_flow_checklist_replaces_lifecycle_checklist():
    ctx = context(
        flow_checklist=[
            {
                "key": "import_ogv_demand",
                "label": "Import OGV demand",
                "status": "current",
                "action_id": "IMPORT_OGV_DEMAND",
                "route": "/schedule/ogv-demand",
            }
        ],
    )

    assert build_checklist(ctx, shape_recommendations(ctx, [])) == ctx.flow_checklist


def test_phase5_checklist_advances_from_run_to_scenario_handoff():
    base = {
        "demand_count": 2,
        "cargo_layer_issue_count": 0,
        "tide_window_count": 1,
        "bridge_window_count": 1,
        "active_plan_version_id": 7,
        "active_plan_trip_count": 4,
        "active_plan_status": PlanVersion.Status.GENERATED,
        "latest_optimizer_run_id": 12,
        "latest_optimizer_run_status": OptimizerRun.Status.SUCCEEDED,
        "latest_optimizer_run_candidate_count": 3,
    }
    optimizer_ctx = context(**base)
    optimizer_checklist = checklist_by_key(
        build_checklist(optimizer_ctx, shape_recommendations(optimizer_ctx, [])),
    )

    assert optimizer_checklist["recovery_options_generated"]["status"] == "complete"
    assert optimizer_checklist["recovery_recommendation_reviewed"]["status"] == "current"
    assert (
        optimizer_checklist["recovery_recommendation_reviewed"]["action_id"]
        == "OPEN_RECOMMENDATION_CONSOLE"
    )
    assert optimizer_checklist["recommendation_materialized"]["status"] == "pending"

    candidate_ctx = context(
        **base,
        top_recovery_recommendation_id=44,
        top_recovery_recommendation_status=RecoveryRecommendation.Status.CANDIDATE,
    )
    candidate_checklist = checklist_by_key(
        build_checklist(candidate_ctx, shape_recommendations(candidate_ctx, [])),
    )

    assert candidate_checklist["recommendation_materialized"]["status"] == "current"
    assert (
        candidate_checklist["recommendation_materialized"]["action_id"]
        == "MATERIALIZE_RECOVERY_RECOMMENDATION"
    )

    materialized_ctx = context(
        **base,
        top_recovery_recommendation_id=44,
        top_recovery_recommendation_status=RecoveryRecommendation.Status.MATERIALIZED,
        top_recovery_recommendation_scenario_id=91,
    )
    materialized_checklist = checklist_by_key(
        build_checklist(materialized_ctx, shape_recommendations(materialized_ctx, [])),
    )

    assert materialized_checklist["recovery_recommendation_reviewed"]["status"] == "complete"
    assert materialized_checklist["recommendation_materialized"]["status"] == "complete"


def test_blocking_conflict_outranks_submit_approval():
    ctx = context(
        active_plan_status=PlanVersion.Status.GENERATED,
        active_plan_trip_count=4,
        blocking_conflict_count=1,
        demand_count=2,
        tide_window_count=1,
        bridge_window_count=1,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "OPEN_EXCEPTION_CENTER"


def test_blocking_conflict_suppresses_pending_approval_action():
    ctx = context(
        route="/approvals/publishing",
        active_plan_status=PlanVersion.Status.PROPOSED,
        active_plan_trip_count=4,
        blocking_conflict_count=2,
        pending_approval_count=1,
        current_user_pending_approval_count=1,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "OPEN_EXCEPTION_CENTER"
    assert "APPROVE_PLAN" not in [item.action_id for item in shaped.page_actions]


def test_flow_current_step_becomes_global_next_action():
    ctx = context(
        active_flow_run_id="FLOW-TEST",
        active_flow_key="operator_happy_path_v1",
        active_flow_name="Operator happy path",
        active_flow_status="active",
        current_flow_step_key="generate_plan",
        current_flow_step_label="Generate plan",
        current_flow_step_status="active",
        expected_flow_route="/operations/tug-barge-assignment",
        expected_flow_action_id="GENERATE_PLAN",
        demand_count=2,
        tide_window_count=1,
        bridge_window_count=1,
        active_plan_version_id=7,
        active_plan_trip_count=4,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "GENERATE_PLAN"
    assert shaped.global_next_action.source == "flow.current_step"
    assert shaped.global_next_action.rank_score == 970
    assert shaped.global_next_action.metadata == {
        "flowRunId": "FLOW-TEST",
        "flowKey": "operator_happy_path_v1",
        "stepKey": "generate_plan",
        "stepStatus": "active",
    }


def test_critical_conflict_outranks_flow_current_step():
    ctx = context(
        active_flow_run_id="FLOW-BLOCKED",
        active_flow_key="operator_happy_path_v1",
        active_flow_name="Operator happy path",
        active_flow_status="active",
        current_flow_step_key="generate_plan",
        current_flow_step_label="Generate plan",
        current_flow_step_status="active",
        expected_flow_route="/operations/tug-barge-assignment",
        expected_flow_action_id="GENERATE_PLAN",
        blocking_conflict_count=1,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "OPEN_EXCEPTION_CENTER"


def test_blocked_flow_step_emits_approval_resolver():
    ctx = context(
        active_flow_run_id="FLOW-APPROVAL",
        active_flow_key="operator_happy_path_v1",
        active_flow_name="Operator happy path",
        active_flow_status="blocked",
        current_flow_step_key="publish_plan",
        current_flow_step_label="Publish plan",
        current_flow_step_status="blocked",
        expected_flow_route="/approvals/publishing",
        expected_flow_action_id="PUBLISH_PLAN",
        flow_blocked_reason="Required approval decisions are incomplete.",
        pending_approval_count=1,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "APPROVE_PLAN"
    assert shaped.global_next_action.source == "flow.current_step"


def test_blocked_publishability_flow_step_emits_resolver_action():
    ctx = context(
        active_flow_run_id="FLOW-PUB",
        active_flow_key="operator_happy_path_v1",
        active_flow_name="Operator happy path",
        active_flow_status="blocked",
        current_flow_step_key="run_publishability_check",
        current_flow_step_label="Run publishability check",
        current_flow_step_status="blocked",
        expected_flow_route="/approvals/publishing",
        expected_flow_action_id="RUN_PUBLISHABILITY_CHECK",
        flow_blocked_reason="Unresolved critical or warning telemetry alerts remain.",
        publishability_status="blocked",
        publishability_assessment_id=7,
        publishability_top_blocker_group="telemetry",
        publishability_expected_resolver_action_id="REVIEW_SIGNAL_HEALTH",
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "REVIEW_SIGNAL_HEALTH"


def test_blocked_promote_scenario_with_unrepaired_navigation_constraints_emits_window_repair():
    ctx = context(
        active_flow_run_id="FLOW-SCENARIO",
        active_flow_key="phase5_recovery_from_demand_v1",
        active_flow_name="Phase 5 recovery from demand",
        active_flow_status="blocked",
        current_flow_step_key="promote_scenario",
        current_flow_step_label="Promote scenario",
        current_flow_step_status="blocked",
        expected_flow_route="/simulation/workspace",
        expected_flow_action_id="PROMOTE_SCENARIO",
        flow_blocked_reason="8 critical simulated constraint(s) remain before promotion.",
        flow_promote_critical_constraint_count=8,
        flow_promote_critical_constraint_codes=[
            "BRIDGE_WINDOW_MISSED",
            "TIDE_WINDOW_MISSED",
        ],
        flow_promote_repair_after_latest_run=False,
        blocking_conflict_count=2,
        demand_count=5,
        tide_window_count=3,
        bridge_window_count=3,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "ENTER_OPERATING_WINDOWS"
    assert shaped.global_next_action.source == "flow.current_step"


def test_blocked_promote_scenario_after_window_repair_emits_rerun_simulation():
    ctx = context(
        active_flow_run_id="FLOW-SCENARIO",
        active_flow_key="phase5_recovery_from_demand_v1",
        active_flow_name="Phase 5 recovery from demand",
        active_flow_status="blocked",
        current_flow_step_key="promote_scenario",
        current_flow_step_label="Promote scenario",
        current_flow_step_status="blocked",
        expected_flow_route="/simulation/workspace",
        expected_flow_action_id="PROMOTE_SCENARIO",
        flow_blocked_reason="8 critical simulated constraint(s) remain before promotion.",
        flow_promote_critical_constraint_count=8,
        flow_promote_critical_constraint_codes=["BRIDGE_WINDOW_MISSED"],
        flow_promote_repair_after_latest_run=True,
        blocking_conflict_count=2,
        demand_count=5,
        tide_window_count=4,
        bridge_window_count=4,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "RUN_SIMULATION"
    assert shaped.global_next_action.source == "flow.current_step"


def test_blocked_promote_scenario_with_clear_latest_run_emits_promote():
    ctx = context(
        active_flow_run_id="FLOW-SCENARIO",
        active_flow_key="phase5_recovery_from_demand_v1",
        active_flow_name="Phase 5 recovery from demand",
        active_flow_status="blocked",
        current_flow_step_key="promote_scenario",
        current_flow_step_label="Promote scenario",
        current_flow_step_status="blocked",
        expected_flow_route="/simulation/workspace",
        expected_flow_action_id="PROMOTE_SCENARIO",
        flow_blocked_reason="8 critical simulated constraint(s) remain before promotion.",
        flow_promote_critical_constraint_count=0,
        flow_promote_critical_constraint_codes=[],
        blocking_conflict_count=2,
        demand_count=5,
        tide_window_count=4,
        bridge_window_count=4,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "PROMOTE_SCENARIO"
    assert shaped.global_next_action.source == "flow.current_step"


def test_publishability_check_needed_precedes_publish_ready():
    ctx = context(
        active_plan_status=PlanVersion.Status.APPROVED,
        active_plan_is_editable=False,
        all_required_approvals_complete=True,
        blocking_conflict_count=0,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "RUN_PUBLISHABILITY_CHECK"


def test_publish_ready_requires_clear_publishability_gate():
    ctx = context(
        active_plan_status=PlanVersion.Status.APPROVED,
        active_plan_is_editable=False,
        all_required_approvals_complete=True,
        blocking_conflict_count=0,
        publishability_status="warning",
        publishability_assessment_id=5,
        publishability_is_stale=False,
        demand_count=2,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "PUBLISH_PLAN"


def test_recovery_recommendation_route_prioritizes_testing_over_generic_exception():
    ctx = context(
        route="/recovery/recommendations",
        active_plan_status=PlanVersion.Status.GENERATED,
        active_plan_trip_count=4,
        blocking_conflict_count=2,
        demand_count=2,
        tide_window_count=1,
        bridge_window_count=1,
        latest_optimizer_run_id=12,
        latest_optimizer_run_status=OptimizerRun.Status.SUCCEEDED,
        latest_optimizer_run_candidate_count=3,
        top_recovery_recommendation_id=44,
        top_recovery_recommendation_ref="REC-44",
        top_recovery_recommendation_status=RecoveryRecommendation.Status.CANDIDATE,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "VALIDATE_ROOT_CAUSE_REPAIR"
    assert action_ids(shaped.page_actions)[0] == "VALIDATE_ROOT_CAUSE_REPAIR"


def test_corrected_constraints_prioritize_regeneration_over_stale_exceptions():
    ctx = context(
        route="/constraints/tide-bridge",
        active_plan_status=PlanVersion.Status.PROPOSED,
        active_plan_trip_count=6,
        active_plan_is_editable=True,
        source_inputs_changed=True,
        blocking_conflict_count=6,
        constraint_blocker_count=0,
        demand_count=3,
        tide_window_count=4,
        bridge_window_count=4,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "REGENERATE_PLAN"
    assert action_ids(shaped.page_actions)[0] == "REGENERATE_PLAN"


def test_scenario_rerun_handoff_suppresses_stale_regenerate_page_action():
    ctx = context(
        route="/constraints/tide-bridge",
        active_plan_status=PlanVersion.Status.GENERATED,
        active_plan_trip_count=6,
        active_plan_is_editable=True,
        source_inputs_changed=True,
        blocking_conflict_count=2,
        demand_count=5,
        tide_window_count=4,
        bridge_window_count=4,
        active_flow_run_id="FLOW-SCENARIO",
        active_flow_key="phase5_recovery_from_demand_v1",
        active_flow_name="Phase 5 recovery from demand",
        active_flow_status="blocked",
        current_flow_step_key="promote_scenario",
        current_flow_step_label="Promote scenario",
        current_flow_step_status="blocked",
        expected_flow_route="/simulation/workspace",
        expected_flow_action_id="PROMOTE_SCENARIO",
        flow_blocked_reason="8 critical simulated constraint(s) remain before promotion.",
        flow_promote_critical_constraint_count=8,
        flow_promote_critical_constraint_codes=["BRIDGE_WINDOW_MISSED"],
        flow_promote_repair_after_latest_run=True,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "RUN_SIMULATION"
    assert "REGENERATE_PLAN" not in action_ids(shaped.page_actions)


def test_promoted_but_blocked_plan_does_not_claim_approval_submitted():
    ctx = context(
        active_plan_status=PlanVersion.Status.PROPOSED,
        active_plan_trip_count=6,
        blocking_conflict_count=2,
        pending_approval_count=0,
        all_required_approvals_complete=False,
    )

    checklist = checklist_by_key(build_checklist(ctx, shape_recommendations(ctx, [])))

    assert checklist["approval_submitted"]["status"] == "pending"


def test_phase5_disruption_recommends_recovery_options_before_manual_scenario():
    ctx = context(
        route="/exceptions/center",
        blocking_conflict_count=1,
        latest_optimizer_run_id=None,
        open_scenario_count=0,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))
    ids = action_ids(shaped.page_actions)

    assert "GENERATE_RECOVERY_OPTIONS" in ids
    assert ids.index("GENERATE_RECOVERY_OPTIONS") < ids.index("CREATE_SCENARIO")


def test_successful_optimizer_run_recommends_recommendation_console():
    recommendations = evaluate_rules(
        context(
            latest_optimizer_run_id=12,
            latest_optimizer_run_status=OptimizerRun.Status.SUCCEEDED,
            latest_optimizer_run_candidate_count=3,
        ),
    )

    assert "OPEN_RECOMMENDATION_CONSOLE" in action_ids(recommendations)


def test_recovery_recommendation_ready_to_materialize_targets_object():
    recommendations = evaluate_rules(
        context(
            route="/recovery/recommendations",
            top_recovery_recommendation_id=44,
            top_recovery_recommendation_ref="REC-44",
            top_recovery_recommendation_status=RecoveryRecommendation.Status.CANDIDATE,
            top_recovery_recommendation_scenario_id=None,
        ),
    )

    recommendation = next(
        item
        for item in recommendations
        if item.action_id == "MATERIALIZE_RECOVERY_RECOMMENDATION"
    )
    assert recommendation.target_object_type == "recovery_recommendation"
    assert recommendation.target_object_id == "44"


def test_dismissed_recommendation_is_not_materializable():
    recommendations = evaluate_rules(
        context(
            top_recovery_recommendation_id=44,
            top_recovery_recommendation_status=RecoveryRecommendation.Status.DISMISSED,
            top_recovery_recommendation_scenario_id=None,
        ),
    )

    assert "MATERIALIZE_RECOVERY_RECOMMENDATION" not in action_ids(recommendations)


def test_phase5_approved_candidate_with_blocker_keeps_exception_top_action():
    ctx = context(
        all_required_approvals_complete=True,
        blocking_conflict_count=1,
        recommendation_origin_scenario_id=7,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "OPEN_EXCEPTION_CENTER"
    assert shaped.global_next_action.source == "recovery.approved_candidate_publish_blocked"


def test_permission_shaping_moves_current_route_action_to_blocked():
    ctx = context(permissions={"schedule.view"}, route="/approvals/publishing")
    recommendation = build_recommendation(
        "PUBLISH_PLAN",
        priority="warning",
        rank_score=760,
        enabled=True,
        reason="Ready to publish.",
        source="publish.ready",
    )

    shaped = shape_recommendations(ctx, [recommendation])

    assert shaped.global_next_action is None
    assert [item.action_id for item in shaped.blocked_actions] == ["PUBLISH_PLAN"]
    assert "schedule.publish" in shaped.blocked_actions[0].blocked_reason


def test_permission_shaping_omits_unrelated_action_without_permission():
    ctx = context(permissions={"schedule.view"}, route="/map/live")
    recommendation = build_recommendation(
        "PUBLISH_PLAN",
        priority="warning",
        rank_score=760,
        enabled=True,
        reason="Ready to publish.",
        source="publish.ready",
    )

    shaped = shape_recommendations(ctx, [recommendation])

    assert shaped.global_next_action is None
    assert shaped.blocked_actions == []


def test_master_data_route_has_explicit_read_only_guidance():
    ctx = context(route="/admin/master-data", permissions={"masterdata.view"})
    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert [item.action_id for item in shaped.page_actions] == ["REVIEW_MASTER_DATA"]
    assert shaped.page_actions[0].enabled is True


def test_rbac_route_has_explicit_read_only_guidance():
    ctx = context(route="/admin/users-rbac", permissions={"admin.view"})
    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert [item.action_id for item in shaped.page_actions] == ["REVIEW_RBAC"]
    assert shaped.page_actions[0].enabled is True


def test_dedupe_keeps_highest_ranked_recommendation():
    ctx = context(route="/exceptions/center")
    low = build_recommendation(
        "OPEN_EXCEPTION_CENTER",
        priority="warning",
        rank_score=700,
        enabled=True,
        reason="Lower.",
        source="test.low",
    )
    high = build_recommendation(
        "OPEN_EXCEPTION_CENTER",
        priority="critical",
        rank_score=950,
        enabled=True,
        reason="Higher.",
        source="test.high",
    )

    shaped = shape_recommendations(ctx, [low, high])

    assert shaped.global_next_action
    assert shaped.global_next_action.source == "test.high"
