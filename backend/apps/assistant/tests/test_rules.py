from apps.assistant.rules import evaluate_rules
from apps.assistant.selectors import AssistantContext
from apps.assistant.services import build_recommendation, shape_recommendations
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
