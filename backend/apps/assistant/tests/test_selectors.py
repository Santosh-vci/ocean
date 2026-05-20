from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone

from apps.assistant.selectors import build_assistant_context
from apps.masters.models import CoalGrade, Location
from apps.organizations.models import Organization
from apps.planning.models import BridgeWindow, CargoLayerStep, OGVVoyage, TideWindow
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import (
    ApprovalDecision,
    ApprovalRequest,
    Conflict,
    OptimizerRun,
    Plan,
    PlanVersion,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    Trip,
)


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


def make_org(slug="assistant-org"):
    return Organization.objects.create(name=slug, slug=slug, kind=Organization.Kind.BERAU)


def make_location(org):
    return Location.objects.create(
        code=f"LOC-{org.slug}",
        name="Assistant Anchorage",
        organization=org,
        location_type=Location.LocationType.ANCHORAGE,
        latitude="-1.900000",
        longitude="118.000000",
    )


def make_plan_version(org, *, status=PlanVersion.Status.GENERATED):
    now = timezone.now()
    plan = Plan.objects.create(
        code=f"PLAN-{org.slug}",
        name="Assistant Plan",
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


@pytest.mark.django_db
def test_build_assistant_context_reads_permissions_and_planning_counts():
    org = make_org("assistant-context")
    location = make_location(org)
    user = User.objects.create_user(username="assistant-context", password="secret")
    assign(user, org, ["schedule.view", "schedule.edit"])
    version = make_plan_version(org)
    now = timezone.now()
    OGVVoyage.objects.create(
        voyage_id="VOY-ASSIST-001",
        vessel_name="MV Assist",
        customer_name="Customer",
        eta=now,
        laycan_start=now,
        laycan_end=now + timedelta(days=2),
        required_mt=50000,
        organization=org,
        anchorage_location=location,
    )
    TideWindow.objects.create(
        code="TIDE-ASSIST-001",
        location=location,
        window_start=now,
        window_end=now + timedelta(hours=4),
        min_water_level_m="2.00",
        max_loaded_draft_m="5.00",
    )
    BridgeWindow.objects.create(
        code="BRIDGE-ASSIST-001",
        location=location,
        window_start=now,
        window_end=now + timedelta(hours=4),
        clearance_m="12.00",
    )
    Conflict.objects.create(
        plan_version=version,
        code="ASSIST_BLOCKER",
        severity=Conflict.Severity.CRITICAL,
        message="Blocking test conflict",
        is_blocking=True,
    )

    ctx = build_assistant_context(user, route="/exceptions/center")

    assert ctx.active_plan_version_id == version.id
    assert ctx.active_plan_status == PlanVersion.Status.GENERATED
    assert ctx.demand_count == 1
    assert ctx.tide_window_count == 1
    assert ctx.bridge_window_count == 1
    assert ctx.blocking_conflict_count == 1
    assert "schedule.edit" in ctx.permissions
    assert ctx.route == "/exceptions/center"


@pytest.mark.django_db
def test_assistant_planning_counts_keep_conflicts_out_of_cargo_layer_status():
    org = make_org("assistant-layer-conflict")
    location = make_location(org)
    user = User.objects.create_user(username="assistant-layer-conflict", password="secret")
    assign(user, org, ["schedule.view", "schedule.edit"])
    version = make_plan_version(org)
    now = timezone.now()
    voyage = OGVVoyage.objects.create(
        voyage_id="VOY-ASSIST-LAYER",
        vessel_name="MV Assist Layer",
        customer_name="Customer",
        eta=now,
        laycan_start=now,
        laycan_end=now + timedelta(days=2),
        required_mt=46000,
        organization=org,
        anchorage_location=location,
    )
    grade = CoalGrade.objects.create(
        code="GRADE-ASSIST-LAYER",
        name="Assistant Layer Grade",
        brand_family="Thermal",
        sequence_priority=1,
    )
    layer = CargoLayerStep.objects.create(
        voyage=voyage,
        hatch_no=1,
        layer_no=1,
        required_sequence_no=1,
        coal_grade=grade,
        required_mt=46000,
        remaining_mt=46000,
        status=CargoLayerStep.Status.PLANNED,
        blocking_reason="",
        chain_status="PLANNED",
        sequence_violation=False,
    )
    trip = Trip.objects.create(
        plan_version=version,
        trip_id="PI-ASSIST-LAYER-001",
        sequence=1,
        voyage=voyage,
        cargo_layer_step=layer,
        planned_start=now,
        planned_end=now + timedelta(hours=8),
        planned_quantity_mt=46000,
        status=Trip.Status.PLANNED,
    )
    Conflict.objects.create(
        plan_version=version,
        trip=trip,
        code="BRIDGE_WINDOW_MISSED",
        severity=Conflict.Severity.CRITICAL,
        message="Bridge window missed.",
        is_blocking=True,
    )
    Conflict.objects.create(
        plan_version=version,
        trip=trip,
        code="OLD_TIDE_WINDOW_MISSED",
        severity=Conflict.Severity.CRITICAL,
        message="Resolved conflict should not count.",
        is_blocking=True,
        resolved_at=now,
    )

    ctx = build_assistant_context(user, route="/schedule/coal-grade-sequence")

    assert ctx.cargo_layer_issue_count == 0
    assert ctx.blocking_conflict_count == 1


@pytest.mark.django_db
def test_build_assistant_context_reads_phase5_state_without_mutation():
    org = make_org("assistant-phase5")
    user = User.objects.create_user(username="assistant-phase5", password="secret")
    assign(user, org, ["schedule.view", "schedule.edit"])
    version = make_plan_version(org)
    snapshot = RecoveryInputSnapshot.objects.create(
        plan_version=version,
        source_kind=RecoveryInputSnapshot.SourceKind.CONFLICT,
        source_ref="EX-1",
    )
    optimizer_run = OptimizerRun.objects.create(
        input_snapshot=snapshot,
        plan_version=version,
        status=OptimizerRun.Status.SUCCEEDED,
        algorithm_version="test-phase5",
    )
    recommendation = RecoveryRecommendation.objects.create(
        optimizer_run=optimizer_run,
        rank=1,
        risk_level=RecoveryRecommendation.RiskLevel.LOW,
        score="91.000",
        summary="Use a recovery candidate.",
    )
    counts_before = {
        "snapshots": RecoveryInputSnapshot.objects.count(),
        "runs": OptimizerRun.objects.count(),
        "recommendations": RecoveryRecommendation.objects.count(),
    }

    ctx = build_assistant_context(
        user,
        route="/recovery/recommendations",
        object_type="recovery_recommendation",
        object_id=recommendation.id,
    )

    assert ctx.latest_recovery_input_snapshot_id == snapshot.id
    assert ctx.latest_optimizer_run_id == optimizer_run.id
    assert ctx.latest_optimizer_run_status == OptimizerRun.Status.SUCCEEDED
    assert ctx.latest_optimizer_run_candidate_count == 1
    assert ctx.top_recovery_recommendation_id == recommendation.id
    assert ctx.top_recovery_recommendation_ref == recommendation.recommendation_id
    assert ctx.object_id == str(recommendation.id)
    assert counts_before == {
        "snapshots": RecoveryInputSnapshot.objects.count(),
        "runs": OptimizerRun.objects.count(),
        "recommendations": RecoveryRecommendation.objects.count(),
    }


@pytest.mark.django_db
def test_current_user_pending_approval_uses_role_authority():
    org = make_org("assistant-approval")
    user = User.objects.create_user(username="assistant-approval", password="secret")
    assign(user, org, ["schedule.view", "schedule.approve"], role_code="berau-scheduler")
    version = make_plan_version(org, status=PlanVersion.Status.PROPOSED)
    approval = ApprovalRequest.objects.create(
        request_id="APR-ASSIST-001",
        plan_version=version,
        status=ApprovalRequest.Status.PENDING,
        required_authorities=[
            ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
            ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
        ],
        reason="Need approval.",
        requested_by=user,
    )

    ctx = build_assistant_context(user, route="/approvals/publishing")

    assert approval.id
    assert ctx.pending_approval_count == 1
    assert ctx.current_user_pending_approval_count == 1
