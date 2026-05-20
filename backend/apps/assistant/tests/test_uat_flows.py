from apps.assistant.rules import evaluate_rules
from apps.assistant.selectors import AssistantContext
from apps.assistant.services import shape_recommendations
from apps.scheduling.models import OptimizerRun, PlanVersion, RecoveryRecommendation


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
        "blocking_conflict_count": 0,
        "pending_approval_count": 0,
    }
    values.update(overrides)
    return AssistantContext(**values)


def shaped_for(**overrides):
    ctx = context(**overrides)
    return shape_recommendations(ctx, evaluate_rules(ctx))


def action_ids(items):
    return [item.action_id for item in items]


def top_action_id(**overrides):
    shaped = shaped_for(**overrides)
    assert shaped.global_next_action
    return shaped.global_next_action.action_id


def assert_top_sequence(steps):
    for expected_action_id, overrides in steps:
        assert top_action_id(**overrides) == expected_action_id


def test_uat_happy_path_action_sequence():
    assert_top_sequence(
        [
            (
                "IMPORT_OGV_DEMAND",
                {
                    "demand_count": 0,
                    "active_plan_version_id": None,
                    "active_plan_trip_count": 0,
                    "active_plan_status": None,
                    "active_plan_is_editable": False,
                },
            ),
            ("REVIEW_COAL_SEQUENCE", {"cargo_layer_issue_count": 2}),
            ("ENTER_OPERATING_WINDOWS", {"tide_window_count": 0}),
            (
                "GENERATE_PLAN",
                {
                    "active_plan_version_id": None,
                    "active_plan_trip_count": 0,
                    "active_plan_status": None,
                    "active_plan_is_editable": False,
                },
            ),
            ("SUBMIT_APPROVAL", {}),
            (
                "APPROVE_PLAN",
                {
                    "active_plan_status": PlanVersion.Status.PROPOSED,
                    "pending_approval_count": 1,
                    "current_user_pending_approval_count": 1,
                },
            ),
            (
                "PUBLISH_PLAN",
                {
                    "active_plan_status": PlanVersion.Status.APPROVED,
                    "active_plan_is_editable": False,
                    "all_required_approvals_complete": True,
                },
            ),
            (
                "GENERATE_EXPORT",
                {
                    "active_plan_status": PlanVersion.Status.PUBLISHED,
                    "active_plan_is_editable": False,
                    "published_snapshot_exists": True,
                    "latest_export_for_published_plan_exists": False,
                    "source_inputs_changed": False,
                },
            ),
        ]
    )


def test_uat_blocking_conflict_recovery_path():
    assert top_action_id(blocking_conflict_count=1, open_scenario_count=0) == (
        "OPEN_EXCEPTION_CENTER"
    )

    exception_page = shaped_for(
        route="/exceptions/center",
        blocking_conflict_count=1,
        open_scenario_count=0,
        latest_optimizer_run_id=None,
    )
    exception_action_ids = action_ids(exception_page.page_actions)

    assert "GENERATE_RECOVERY_OPTIONS" in exception_action_ids
    assert "CREATE_SCENARIO" in exception_action_ids
    assert exception_action_ids.index("GENERATE_RECOVERY_OPTIONS") < (
        exception_action_ids.index("CREATE_SCENARIO")
    )
    assert top_action_id(route="/simulation/workspace", scenario_ready_to_run_count=1) == (
        "RUN_SIMULATION"
    )
    assert top_action_id(
        route="/simulation/workspace",
        blocking_conflict_count=1,
        open_scenario_count=1,
        scenario_ready_to_run_count=1,
    ) == "RUN_SIMULATION"
    assert top_action_id(route="/simulation/workspace", promotable_scenario_count=1) == (
        "PROMOTE_SCENARIO"
    )
    assert top_action_id(
        route="/simulation/workspace",
        blocking_conflict_count=1,
        open_scenario_count=1,
        promotable_scenario_count=1,
    ) == "PROMOTE_SCENARIO"
    assert top_action_id(route="/schedule/published-plan") == "SUBMIT_APPROVAL"


def test_uat_event_confirmation_path():
    assert (
        top_action_id(
            route="/operations/event-confirmation",
            high_confidence_event_candidate_count=1,
        )
        == "CONFIRM_EVENT"
    )
    assert top_action_id(
        route="/operations/event-confirmation",
        noisy_event_candidate_count=1,
        active_plan_status=PlanVersion.Status.PUBLISHED,
        active_plan_is_editable=False,
        published_snapshot_exists=True,
        latest_export_for_published_plan_exists=True,
    ) == "REJECT_EVENT"

    risk_page = shaped_for(
        route="/exceptions/center",
        active_override_risk_count=1,
        open_scenario_count=0,
        latest_optimizer_run_id=None,
        active_plan_status=PlanVersion.Status.PUBLISHED,
        active_plan_is_editable=False,
        published_snapshot_exists=True,
        latest_export_for_published_plan_exists=True,
    )
    risk_action_ids = action_ids(risk_page.page_actions)

    assert "GENERATE_RECOVERY_OPTIONS" in risk_action_ids
    assert "CREATE_SCENARIO" in risk_action_ids


def test_uat_published_plan_change_path():
    assert top_action_id(
        active_plan_status=PlanVersion.Status.PUBLISHED,
        active_plan_is_editable=False,
        published_snapshot_exists=True,
        latest_export_for_published_plan_exists=True,
        source_inputs_changed=True,
    ) == "CREATE_DRAFT"
    assert top_action_id(
        active_plan_status=PlanVersion.Status.DRAFT,
        active_plan_is_editable=True,
        active_plan_trip_count=4,
        source_inputs_changed=True,
    ) == "REGENERATE_PLAN"

    assert_top_sequence(
        [
            ("SUBMIT_APPROVAL", {}),
            (
                "PUBLISH_PLAN",
                {
                    "active_plan_status": PlanVersion.Status.APPROVED,
                    "active_plan_is_editable": False,
                    "all_required_approvals_complete": True,
                },
            ),
            (
                "GENERATE_EXPORT",
                {
                    "active_plan_status": PlanVersion.Status.PUBLISHED,
                    "active_plan_is_editable": False,
                    "published_snapshot_exists": True,
                    "latest_export_for_published_plan_exists": False,
                    "source_inputs_changed": False,
                },
            ),
        ]
    )


def test_uat_phase5_recovery_recommendation_path():
    exception_page = shaped_for(
        route="/exceptions/center",
        blocking_conflict_count=1,
        open_scenario_count=0,
        latest_optimizer_run_id=None,
    )
    exception_action_ids = action_ids(exception_page.page_actions)
    assert "GENERATE_RECOVERY_OPTIONS" in exception_action_ids

    assert top_action_id(
        latest_optimizer_run_id=12,
        latest_optimizer_run_status=OptimizerRun.Status.SUCCEEDED,
        latest_optimizer_run_candidate_count=3,
    ) == "OPEN_RECOMMENDATION_CONSOLE"

    recommendation_page = shaped_for(
        route="/recovery/recommendations",
        object_type="recovery_recommendation",
        object_id="44",
        top_recovery_recommendation_id=44,
        top_recovery_recommendation_ref="REC-44",
        top_recovery_recommendation_status=RecoveryRecommendation.Status.CANDIDATE,
    )
    assert action_ids(recommendation_page.row_actions) == [
        "MATERIALIZE_RECOVERY_RECOMMENDATION",
        "DISMISS_RECOVERY_RECOMMENDATION",
    ]

    assert top_action_id(
        route="/simulation/workspace",
        object_type="simulation_scenario",
        object_id="91",
        top_recovery_recommendation_id=44,
        top_recovery_recommendation_status=RecoveryRecommendation.Status.MATERIALIZED,
        top_recovery_recommendation_scenario_id=91,
        recommendation_origin_scenario_id=91,
        recommendation_origin_scenario_status="draft",
    ) == "RUN_SIMULATION"
    assert top_action_id(route="/simulation/workspace", promotable_scenario_count=1) == (
        "PROMOTE_SCENARIO"
    )
    assert top_action_id() == "SUBMIT_APPROVAL"
    assert top_action_id(
        active_plan_status=PlanVersion.Status.VALIDATED,
        validation_status=PlanVersion.ValidationStatus.FEASIBLE,
        cargo_layer_issue_count=2,
        latest_optimizer_run_id=12,
        latest_optimizer_run_status=OptimizerRun.Status.SUCCEEDED,
        latest_optimizer_run_candidate_count=3,
        materialized_recovery_recommendation_count=1,
    ) == "SUBMIT_APPROVAL"
    assert top_action_id(
        active_plan_status=PlanVersion.Status.PROPOSED,
        validation_status=PlanVersion.ValidationStatus.FEASIBLE,
        cargo_layer_issue_count=2,
        pending_approval_count=1,
        current_user_pending_approval_count=1,
        latest_optimizer_run_id=12,
        latest_optimizer_run_status=OptimizerRun.Status.SUCCEEDED,
        latest_optimizer_run_candidate_count=3,
        materialized_recovery_recommendation_count=1,
    ) == "APPROVE_PLAN"
    assert top_action_id(
        active_plan_status=PlanVersion.Status.APPROVED,
        active_plan_is_editable=False,
        validation_status=PlanVersion.ValidationStatus.FEASIBLE,
        cargo_layer_issue_count=2,
        all_required_approvals_complete=True,
        latest_optimizer_run_id=12,
        latest_optimizer_run_status=OptimizerRun.Status.SUCCEEDED,
        latest_optimizer_run_candidate_count=3,
        materialized_recovery_recommendation_count=1,
    ) == "PUBLISH_PLAN"
    assert top_action_id(
        active_plan_status=PlanVersion.Status.PUBLISHED,
        active_plan_is_editable=False,
        validation_status=PlanVersion.ValidationStatus.FEASIBLE,
        cargo_layer_issue_count=2,
        published_snapshot_exists=True,
        latest_export_for_published_plan_exists=False,
        latest_optimizer_run_id=12,
        latest_optimizer_run_status=OptimizerRun.Status.SUCCEEDED,
        latest_optimizer_run_candidate_count=3,
        materialized_recovery_recommendation_count=1,
    ) == "GENERATE_EXPORT"

    blocked_publish = shaped_for(
        active_plan_status=PlanVersion.Status.APPROVED,
        active_plan_is_editable=False,
        all_required_approvals_complete=True,
        blocking_conflict_count=1,
        recommendation_origin_scenario_id=91,
    )
    assert blocked_publish.global_next_action
    assert blocked_publish.global_next_action.action_id == "OPEN_EXCEPTION_CENTER"

    proof_page = shaped_for(
        route="/recovery/recommendations",
        blocking_conflict_count=1,
        proof_pack_available=True,
        top_recovery_recommendation_id=44,
        top_recovery_recommendation_ref="REC-44",
    )
    proof_pack = next(
        action
        for action in proof_page.page_actions
        if action.action_id == "REVIEW_RECOMMENDATION_PROOF_PACK"
    )
    assert proof_pack.priority == "info"
    assert proof_pack.rank_score < proof_page.global_next_action.rank_score
