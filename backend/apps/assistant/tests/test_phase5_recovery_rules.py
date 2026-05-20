from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.assistant.rules import evaluate_rules
from apps.assistant.selectors import AssistantContext, build_assistant_context
from apps.assistant.services import shape_recommendations
from apps.organizations.models import Organization
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import (
    Conflict,
    OptimizerRun,
    Plan,
    PlanVersion,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    SimulationScenario,
)

NEXT_ACTIONS_URL = "/api/assistant/next-actions/"


def context(**overrides):
    values = {
        "permissions": {"*"},
        "mode": "assisted",
        "route": "/recovery/recommendations",
        "demand_count": 1,
        "tide_window_count": 1,
        "bridge_window_count": 1,
    }
    values.update(overrides)
    return AssistantContext(**values)


def action_ids(items):
    return [item.action_id for item in items]


def assign(user, organization, permission_codes, *, role_code="berau-scheduler"):
    permissions = []
    for code in permission_codes:
        permission, _ = AccessPermission.objects.get_or_create(
            code=code,
            defaults={
                "module": code.split(".")[0],
                "action": code.split(".")[1],
                "description": code,
            },
        )
        permissions.append(permission)
    role = Role.objects.create(
        name=f"{role_code}-{user.username}",
        code=f"{role_code}-{user.username}",
    )
    role.permissions.set(permissions)
    scope = DataScope.objects.create(
        name=f"scope-{user.username}",
        code=f"scope-{user.username}",
        scope_type=DataScope.ScopeType.ALL_NETWORK,
    )
    UserRoleAssignment.objects.create(
        user=user,
        role=role,
        organization=organization,
        data_scope=scope,
    )


def make_org(slug):
    return Organization.objects.create(name=slug, slug=slug, kind=Organization.Kind.BERAU)


def make_user(slug, permissions=("schedule.view", "schedule.edit")):
    org = make_org(slug)
    user = User.objects.create_user(username=slug, password="secret")
    assign(user, org, permissions)
    return user, org


def make_plan_version(org, *, status=PlanVersion.Status.GENERATED):
    now = timezone.now()
    plan = Plan.objects.create(
        code=f"PLAN-{org.slug}",
        name="Assistant Phase 5 Plan",
        organization=org,
        horizon_start=now,
        horizon_end=now + timedelta(days=3),
    )
    return PlanVersion.objects.create(
        plan=plan,
        version_no=1,
        status=status,
        generated_at=now,
    )


def make_phase5_run(org, *, recommendation_status=RecoveryRecommendation.Status.CANDIDATE):
    version = make_plan_version(org)
    snapshot = RecoveryInputSnapshot.objects.create(
        plan_version=version,
        source_kind=RecoveryInputSnapshot.SourceKind.CONFLICT,
        source_ref="EX-P5-1",
    )
    run = OptimizerRun.objects.create(
        input_snapshot=snapshot,
        plan_version=version,
        status=OptimizerRun.Status.SUCCEEDED,
        algorithm_version="test-phase5",
    )
    recommendation = RecoveryRecommendation.objects.create(
        optimizer_run=run,
        rank=1,
        status=recommendation_status,
        risk_level=RecoveryRecommendation.RiskLevel.LOW,
        score="91.000",
        summary="Use a feasible recovery candidate.",
    )
    return version, snapshot, run, recommendation


def test_selected_exception_without_optimizer_run_recommends_recovery_options():
    ctx = context(
        route="/exceptions/center",
        blocking_conflict_count=1,
        latest_optimizer_run_id=None,
        open_scenario_count=0,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert "GENERATE_RECOVERY_OPTIONS" in action_ids(shaped.page_actions)


def test_successful_optimizer_run_recommends_recommendation_console():
    recommendations = evaluate_rules(
        context(
            latest_optimizer_run_id=12,
            latest_optimizer_run_status=OptimizerRun.Status.SUCCEEDED,
            latest_optimizer_run_candidate_count=3,
        ),
    )

    assert "OPEN_RECOMMENDATION_CONSOLE" in action_ids(recommendations)


def test_candidate_without_scenario_recommends_materialization():
    ctx = context(
        object_type="recovery_recommendation",
        object_id="44",
        top_recovery_recommendation_id=44,
        top_recovery_recommendation_ref="REC-44",
        top_recovery_recommendation_status=RecoveryRecommendation.Status.CANDIDATE,
        top_recovery_recommendation_scenario_id=None,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert "MATERIALIZE_RECOVERY_RECOMMENDATION" in action_ids(shaped.row_actions)


def test_dismissed_candidate_is_not_materializable_and_explains_block():
    ctx = context(
        object_type="recovery_recommendation",
        object_id="44",
        top_recovery_recommendation_id=44,
        top_recovery_recommendation_status=RecoveryRecommendation.Status.DISMISSED,
        top_recovery_recommendation_scenario_id=None,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert "MATERIALIZE_RECOVERY_RECOMMENDATION" not in action_ids(shaped.row_actions)
    blocked = [
        item for item in shaped.blocked_actions
        if item.action_id == "MATERIALIZE_RECOVERY_RECOMMENDATION"
    ]
    assert blocked
    assert "Dismissed recommendations cannot be tested as scenarios" in blocked[0].blocked_reason


def test_materialized_candidate_moves_to_simulation_and_blocks_dismiss():
    ctx = context(
        object_type="recovery_recommendation",
        object_id="44",
        top_recovery_recommendation_id=44,
        top_recovery_recommendation_status=RecoveryRecommendation.Status.MATERIALIZED,
        top_recovery_recommendation_scenario_id=12,
        recommendation_origin_scenario_id=12,
        recommendation_origin_scenario_status=SimulationScenario.Status.DRAFT,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))
    blocked_by_id = {item.action_id: item for item in shaped.blocked_actions}

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "RUN_SIMULATION"
    assert "already a governed scenario" in (
        blocked_by_id["MATERIALIZE_RECOVERY_RECOMMENDATION"].blocked_reason
    )
    assert (
        blocked_by_id["DISMISS_RECOVERY_RECOMMENDATION"].blocked_reason
        == "Recommendations already created as scenarios cannot be dismissed."
    )


def test_recommendation_proof_pack_is_low_priority_evidence_guidance():
    recommendations = evaluate_rules(
        context(
            proof_pack_available=True,
            top_recovery_recommendation_id=44,
            top_recovery_recommendation_ref="REC-44",
        ),
    )

    proof_pack = next(
        item for item in recommendations
        if item.action_id == "REVIEW_RECOMMENDATION_PROOF_PACK"
    )
    assert proof_pack.priority == "info"
    assert proof_pack.target_object_type == "recovery_recommendation"
    assert proof_pack.target_object_id == "44"


def test_dual_approved_phase5_candidate_with_blocking_risk_recommends_blocker_resolution():
    ctx = context(
        route="/approvals/publishing",
        all_required_approvals_complete=True,
        blocking_conflict_count=1,
        recommendation_origin_scenario_id=7,
    )

    shaped = shape_recommendations(ctx, evaluate_rules(ctx))

    assert shaped.global_next_action
    assert shaped.global_next_action.action_id == "OPEN_EXCEPTION_CENTER"
    assert shaped.global_next_action.source == "recovery.approved_candidate_publish_blocked"


@pytest.mark.django_db
def test_object_scoped_recovery_recommendation_can_select_dismissed_candidate():
    user, org = make_user("assistant-phase5-scoped-dismissed")
    _version, _snapshot, run, candidate = make_phase5_run(org)
    dismissed = RecoveryRecommendation.objects.create(
        optimizer_run=run,
        rank=2,
        status=RecoveryRecommendation.Status.DISMISSED,
        risk_level=RecoveryRecommendation.RiskLevel.MEDIUM,
        score="72.000",
        summary="Dismissed alternate recovery option.",
    )

    ctx = build_assistant_context(
        user,
        route="/recovery/recommendations",
        object_type="recovery_recommendation",
        object_id=dismissed.id,
    )

    assert candidate.id != dismissed.id
    assert ctx.top_recovery_recommendation_id == dismissed.id
    assert ctx.top_recovery_recommendation_status == RecoveryRecommendation.Status.DISMISSED


@pytest.mark.django_db
def test_object_scoped_snapshot_and_optimizer_run_override_latest_phase5_state():
    user, org = make_user("assistant-phase5-scoped-run")
    version, snapshot, run, _recommendation = make_phase5_run(org)
    newer_snapshot = RecoveryInputSnapshot.objects.create(
        plan_version=version,
        source_kind=RecoveryInputSnapshot.SourceKind.TRACKING_ALERT,
        source_ref="TA-P5-2",
    )
    newer_run = OptimizerRun.objects.create(
        input_snapshot=newer_snapshot,
        plan_version=version,
        status=OptimizerRun.Status.SUCCEEDED,
        algorithm_version="test-phase5-newer",
    )
    RecoveryRecommendation.objects.create(
        optimizer_run=newer_run,
        rank=1,
        risk_level=RecoveryRecommendation.RiskLevel.MEDIUM,
        score="75.000",
        summary="Newer option.",
    )

    snapshot_ctx = build_assistant_context(
        user,
        route="/recovery/recommendations",
        object_type="recovery_input_snapshot",
        object_id=snapshot.id,
    )
    run_ctx = build_assistant_context(
        user,
        route="/recovery/recommendations",
        object_type="optimizer_run",
        object_id=run.id,
    )

    assert snapshot_ctx.latest_recovery_input_snapshot_id == snapshot.id
    assert snapshot_ctx.latest_optimizer_run_id == run.id
    assert run_ctx.latest_recovery_input_snapshot_id == snapshot.id
    assert run_ctx.latest_optimizer_run_id == run.id


@pytest.mark.django_db
def test_object_scoped_simulation_scenario_finds_recovery_origin():
    user, org = make_user("assistant-phase5-scoped-scenario")
    version, _snapshot, _run, recommendation = make_phase5_run(
        org,
        recommendation_status=RecoveryRecommendation.Status.MATERIALIZED,
    )
    scenario = SimulationScenario.objects.create(
        scenario_id="SCN-P5-001",
        name="Recommendation scenario",
        scenario_type="recovery_recommendation",
        baseline_version=version,
        source_kind=SimulationScenario.SourceKind.MANUAL,
        status=SimulationScenario.Status.DRAFT,
        metadata={"source": {"kind": "recovery_recommendation"}},
    )
    recommendation.scenario = scenario
    recommendation.save(update_fields=["scenario", "updated_at"])

    ctx = build_assistant_context(
        user,
        route="/simulation/workspace",
        object_type="simulation_scenario",
        object_id=scenario.id,
    )

    assert ctx.top_recovery_recommendation_id == recommendation.id
    assert ctx.recommendation_origin_scenario_id == scenario.id
    assert ctx.recommendation_origin_scenario_status == SimulationScenario.Status.DRAFT


@pytest.mark.django_db
def test_object_scoped_manual_simulation_scenario_does_not_claim_recovery_origin():
    user, org = make_user("assistant-phase5-manual-scenario")
    version, _snapshot, _run, _recommendation = make_phase5_run(org)
    scenario = SimulationScenario.objects.create(
        scenario_id="SCN-MANUAL-001",
        name="Manual scenario",
        scenario_type="manual",
        baseline_version=version,
        source_kind=SimulationScenario.SourceKind.MANUAL,
        status=SimulationScenario.Status.DRAFT,
    )

    ctx = build_assistant_context(
        user,
        route="/simulation/workspace",
        object_type="simulation_scenario",
        object_id=scenario.id,
    )

    assert ctx.recommendation_origin_scenario_id is None
    assert ctx.recommendation_origin_scenario_status is None


@pytest.mark.django_db
def test_assistant_endpoint_is_read_only_with_phase5_objects():
    user, org = make_user("assistant-phase5-api-readonly")
    _version, _snapshot, _run, recommendation = make_phase5_run(org)
    before = {
        "snapshots": RecoveryInputSnapshot.objects.count(),
        "runs": OptimizerRun.objects.count(),
        "recommendations": RecoveryRecommendation.objects.count(),
        "scenarios": SimulationScenario.objects.count(),
        "conflicts": Conflict.objects.count(),
    }
    client = APIClient()
    client.force_authenticate(user)

    response = client.get(
        NEXT_ACTIONS_URL,
        {
            "route": "/recovery/recommendations",
            "object_type": "recovery_recommendation",
            "object_id": recommendation.id,
        },
    )

    assert response.status_code == 200
    assert before == {
        "snapshots": RecoveryInputSnapshot.objects.count(),
        "runs": OptimizerRun.objects.count(),
        "recommendations": RecoveryRecommendation.objects.count(),
        "scenarios": SimulationScenario.objects.count(),
        "conflicts": Conflict.objects.count(),
    }
