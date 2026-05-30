from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.flows.definitions import seed_canonical_flow_definitions
from apps.flows.services import evaluate_flow_run, start_flow
from apps.masters.models import Barge, CTSAsset, Jetty, Tug
from apps.organizations.models import Organization
from apps.planning.models import AssetAvailabilityWindow, OGVVoyage
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import (
    Assignment,
    Conflict,
    OptimizerRun,
    Plan,
    PlanVersion,
    RecoveryAction,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    RecommendationEvaluation,
    RootCauseRepairAssessment,
    Trip,
)
from apps.scheduling.recovery_services import build_recommendation_proof_pack
from apps.scheduling.root_cause_services import assess_recommendation_root_cause


@pytest.mark.django_db
def test_barge_unavailable_cts_reassignment_does_not_address_cause():
    recommendation = make_recommendation("BARGE_UNAVAILABLE")
    assignment = recommendation.optimizer_run.input_snapshot.source_conflict.trip.assignment
    RecoveryAction.objects.create(
        recommendation=recommendation,
        sequence=1,
        action_type=RecoveryAction.ActionType.REASSIGN_CTS,
        target_trip=assignment.trip,
        target_assignment=assignment,
        before_state={"cts": assignment.cts.code},
        after_state={"cts": "CTS-ALT"},
        constraints_checked=["cts_available"],
    )

    assessment = assess_recommendation_root_cause(recommendation=recommendation)

    assert assessment.status == RootCauseRepairAssessment.Status.DOES_NOT_ADDRESS_CAUSE
    assert assessment.source_cause_type == "BARGE_UNAVAILABLE"
    assert assessment.residual_risk["level"] == "high"


@pytest.mark.django_db
def test_barge_unavailable_barge_reassignment_addresses_cause_idempotently():
    recommendation = make_recommendation("BARGE_UNAVAILABLE")
    assignment = recommendation.optimizer_run.input_snapshot.source_conflict.trip.assignment
    Barge.objects.create(
        code="BG-ALT",
        name="Alt Barge",
        capacity_mt=9000,
        barge_class="standard",
        status=Barge.Status.AVAILABLE,
    )
    RecoveryAction.objects.create(
        recommendation=recommendation,
        sequence=1,
        action_type=RecoveryAction.ActionType.REASSIGN_BARGE,
        target_trip=assignment.trip,
        target_assignment=assignment,
        before_state={"barge": assignment.barge.code},
        after_state={"barge": "BG-ALT"},
        constraints_checked=["resource_availability", "tug_barge_compatibility"],
    )

    first = assess_recommendation_root_cause(recommendation=recommendation)
    second = assess_recommendation_root_cause(recommendation=recommendation)

    assert first.pk == second.pk
    assert RootCauseRepairAssessment.objects.count() == 1
    assert second.status == RootCauseRepairAssessment.Status.ADDRESSES_CAUSE


@pytest.mark.django_db
def test_unknown_source_returns_non_error_unknown_assessment():
    recommendation = make_recommendation("TUG_BARGE_INCOMPATIBLE")
    assignment = recommendation.optimizer_run.input_snapshot.source_conflict.trip.assignment
    RecoveryAction.objects.create(
        recommendation=recommendation,
        sequence=1,
        action_type=RecoveryAction.ActionType.REASSIGN_CTS,
        target_trip=assignment.trip,
        target_assignment=assignment,
        before_state={"cts": assignment.cts.code},
        after_state={"cts": "CTS-ALT"},
        constraints_checked=["cts_available"],
    )

    assessment = assess_recommendation_root_cause(recommendation=recommendation)

    assert assessment.status == RootCauseRepairAssessment.Status.UNKNOWN
    assert assessment.required_resolution["family"] == "unsupported"


@pytest.mark.django_db
def test_movement_assignment_blocked_addresses_when_candidate_evaluation_clears_hard_constraints():
    recommendation = make_recommendation("MOVEMENT_ASSIGNMENT_BLOCKED")
    assignment = recommendation.optimizer_run.input_snapshot.source_conflict.trip.assignment
    RecoveryAction.objects.create(
        recommendation=recommendation,
        sequence=1,
        action_type=RecoveryAction.ActionType.REASSIGN_CTS,
        target_trip=assignment.trip,
        target_assignment=assignment,
        before_state={"cts": assignment.cts.code},
        after_state={"cts": "CTS-ALT"},
        constraints_checked=["cts_available", "cts_queue_overlap_review"],
    )
    RecommendationEvaluation.objects.create(
        recommendation=recommendation,
        missed_windows=0,
        resource_conflicts=0,
        hard_constraints_passed=True,
        confidence_score=Decimal("86.00"),
    )

    assessment = assess_recommendation_root_cause(recommendation=recommendation)

    assert assessment.status == RootCauseRepairAssessment.Status.ADDRESSES_CAUSE
    assert assessment.source_cause_type == "MOVEMENT_ASSIGNMENT_BLOCKED"
    assert assessment.required_resolution["family"] == "movement_assignment_candidate"
    assert assessment.residual_risk["level"] == "low"


@pytest.mark.django_db
def test_movement_assignment_blocked_warns_when_candidate_evaluation_has_residual_risk():
    recommendation = make_recommendation("MOVEMENT_ASSIGNMENT_BLOCKED")
    assignment = recommendation.optimizer_run.input_snapshot.source_conflict.trip.assignment
    RecoveryAction.objects.create(
        recommendation=recommendation,
        sequence=1,
        action_type=RecoveryAction.ActionType.RESEQUENCE_TRIP,
        target_trip=assignment.trip,
        target_assignment=assignment,
        before_state={"tripId": assignment.trip.trip_id},
        after_state={"tripId": assignment.trip.trip_id},
        constraints_checked=["tide_window_evaluated"],
    )
    RecommendationEvaluation.objects.create(
        recommendation=recommendation,
        missed_windows=1,
        resource_conflicts=0,
        hard_constraints_passed=False,
        confidence_score=Decimal("60.00"),
    )

    assessment = assess_recommendation_root_cause(recommendation=recommendation)

    assert assessment.status == RootCauseRepairAssessment.Status.MITIGATES_CAUSE
    assert assessment.residual_risk["level"] == "medium"


@pytest.mark.django_db
def test_root_cause_assessment_api_uses_schedule_view_and_records_audit_only():
    recommendation = make_recommendation("BARGE_UNAVAILABLE")
    assignment = recommendation.optimizer_run.input_snapshot.source_conflict.trip.assignment
    RecoveryAction.objects.create(
        recommendation=recommendation,
        sequence=1,
        action_type=RecoveryAction.ActionType.REASSIGN_CTS,
        target_trip=assignment.trip,
        target_assignment=assignment,
        before_state={"cts": assignment.cts.code},
        after_state={"cts": "CTS-ALT"},
        constraints_checked=["cts_available"],
    )
    user = User.objects.create_user(username="viewer", password="pw")
    assign(user, ["schedule.view"])
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(user=user)
    counts_before = business_counts()

    response = client.post(
        f"/api/scheduling/recovery-recommendations/{recommendation.id}/root-cause-assessment/",
        {},
        format="json",
    )

    assert response.status_code == 200
    assert response.data["status"] == RootCauseRepairAssessment.Status.DOES_NOT_ADDRESS_CAUSE
    assert business_counts() == counts_before
    assert RootCauseRepairAssessment.objects.count() == 1
    assert AuditEvent.objects.filter(action="recovery.recommendation.root_cause_assess").exists()


@pytest.mark.django_db
def test_root_cause_assessment_get_returns_null_until_recorded():
    recommendation = make_recommendation("BARGE_UNAVAILABLE")
    user = User.objects.create_user(username="viewer", password="pw")
    assign(user, ["schedule.view"])
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(user=user)

    response = client.get(
        f"/api/scheduling/recovery-recommendations/{recommendation.id}/root-cause-assessment/",
    )

    assert response.status_code == 200
    assert response.data is None


@pytest.mark.django_db
def test_root_cause_assessment_api_requires_authentication_and_schedule_view():
    recommendation = make_recommendation("BARGE_UNAVAILABLE")
    path = (
        f"/api/scheduling/recovery-recommendations/{recommendation.id}/"
        "root-cause-assessment/"
    )

    anonymous_response = APIClient(HTTP_HOST="localhost").post(path, {}, format="json")
    assert anonymous_response.status_code in {401, 403}

    user = User.objects.create_user(username="no-access", password="pw")
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(user=user)
    response = client.post(path, {}, format="json")

    assert response.status_code == 403
    assert RootCauseRepairAssessment.objects.count() == 0


@pytest.mark.django_db
def test_phase5_flow_advances_after_root_cause_assessment_exists():
    seed_canonical_flow_definitions()
    recommendation = make_recommendation("BARGE_UNAVAILABLE")
    assignment = recommendation.optimizer_run.input_snapshot.source_conflict.trip.assignment
    RecoveryAction.objects.create(
        recommendation=recommendation,
        sequence=1,
        action_type=RecoveryAction.ActionType.REASSIGN_CTS,
        target_trip=assignment.trip,
        target_assignment=assignment,
        before_state={"cts": assignment.cts.code},
        after_state={"cts": "CTS-ALT"},
        constraints_checked=["cts_available"],
    )
    user = User.objects.create_user(username="operator", password="pw")
    flow_run = start_flow("phase5_plus_recovery_v1", actor=user)

    flow_run.refresh_from_db()
    assert flow_run.current_step_key == "validate_root_cause"

    assessment = assess_recommendation_root_cause(recommendation=recommendation)
    evaluate_flow_run(flow_run, actor=user)
    flow_run.refresh_from_db()

    assert assessment.status == RootCauseRepairAssessment.Status.DOES_NOT_ADDRESS_CAUSE
    assert flow_run.current_step_key == "materialize_recommendation"


@pytest.mark.django_db
def test_proof_pack_includes_root_cause_assessment():
    recommendation = make_recommendation("BARGE_UNAVAILABLE")
    assignment = recommendation.optimizer_run.input_snapshot.source_conflict.trip.assignment
    RecoveryAction.objects.create(
        recommendation=recommendation,
        sequence=1,
        action_type=RecoveryAction.ActionType.REASSIGN_CTS,
        target_trip=assignment.trip,
        target_assignment=assignment,
        before_state={"cts": assignment.cts.code},
        after_state={"cts": "CTS-ALT"},
        constraints_checked=["cts_available"],
    )
    assessment = assess_recommendation_root_cause(recommendation=recommendation)

    proof_pack = build_recommendation_proof_pack(recommendation=recommendation)

    assert proof_pack["rootCauseAssessment"]["assessmentId"] == assessment.assessment_id
    assert proof_pack["rootCauseAssessment"]["status"] == assessment.status


def make_recommendation(conflict_code: str) -> RecoveryRecommendation:
    org = Organization.objects.create(
        name="Berau Test",
        slug=f"berau-test-{Organization.objects.count()}",
        kind=Organization.Kind.BERAU,
    )
    start = timezone.now() + timedelta(hours=1)
    end = start + timedelta(hours=4)
    plan = Plan.objects.create(
        code=f"PLAN-{Plan.objects.count()}",
        name="Test Plan",
        organization=org,
        horizon_start=start - timedelta(days=1),
        horizon_end=end + timedelta(days=1),
        status=Plan.Status.ACTIVE,
    )
    version = PlanVersion.objects.create(
        plan=plan,
        version_no=1,
        status=PlanVersion.Status.VALIDATED,
        validation_status=PlanVersion.ValidationStatus.BLOCKED,
    )
    tug = Tug.objects.create(
        code=f"TG-{Tug.objects.count()}",
        name="Test Tug",
        horsepower=2200,
        bollard_pull_tonnes=Decimal("45.00"),
        status=Tug.Status.AVAILABLE,
    )
    barge = Barge.objects.create(
        code=f"BG-{Barge.objects.count()}",
        name="Test Barge",
        capacity_mt=8000,
        barge_class="standard",
        status=Barge.Status.AVAILABLE,
    )
    cts = CTSAsset.objects.create(
        code=f"CTS-{CTSAsset.objects.count()}",
        name="Test CTS",
        cts_type=CTSAsset.CtsType.FLOATING_CRANE,
        daily_capacity_mt=30000,
        operating_area="Taboneo",
        is_available=True,
    )
    jetty = Jetty.objects.create(
        code=f"JTY-{Jetty.objects.count()}",
        name="Test Jetty",
        location_name="Sambarata",
        loading_rate_tph=1800,
        status=Jetty.Status.AVAILABLE,
    )
    voyage = OGVVoyage.objects.create(
        voyage_id=f"VOY-{OGVVoyage.objects.count()}",
        vessel_name="MV Test",
        customer_name="Customer",
        eta=start,
        laycan_start=start,
        laycan_end=end + timedelta(days=1),
        required_mt=50000,
        organization=org,
    )
    trip = Trip.objects.create(
        plan_version=version,
        trip_id=f"TRIP-{Trip.objects.count()}",
        sequence=1,
        voyage=voyage,
        planned_start=start,
        planned_end=end,
        planned_quantity_mt=8000,
        status=Trip.Status.BLOCKED,
    )
    Assignment.objects.create(
        trip=trip,
        tug=tug,
        barge=barge,
        jetty=jetty,
        cts=cts,
        owner_organization=org,
        planned_departure=start,
        planned_arrival=end,
        status=Assignment.Status.BLOCKED,
    )
    if conflict_code == "BARGE_UNAVAILABLE":
        object_type = "barge"
        object_id = barge.code
        AssetAvailabilityWindow.objects.create(
            asset_type=AssetAvailabilityWindow.AssetType.BARGE,
            asset_code=barge.code,
            window_start=start - timedelta(minutes=30),
            window_end=end + timedelta(minutes=30),
            status=AssetAvailabilityWindow.Status.UNAVAILABLE,
            reason="Trial outage",
        )
    else:
        object_type = "assignment"
        object_id = trip.trip_id
    conflict = Conflict.objects.create(
        plan_version=version,
        trip=trip,
        code=conflict_code,
        severity=Conflict.Severity.CRITICAL,
        object_type=object_type,
        object_id=object_id,
        message=f"{conflict_code} test conflict",
        is_blocking=True,
    )
    snapshot = RecoveryInputSnapshot.objects.create(
        plan_version=version,
        source_kind=RecoveryInputSnapshot.SourceKind.CONFLICT,
        source_ref=f"{conflict_code}:{conflict.id}",
        source_conflict=conflict,
        active_conflict_count=1,
        constraint_state={
            "conflicts": [
                {
                    "id": conflict.id,
                    "code": conflict.code,
                    "objectType": conflict.object_type,
                    "objectId": conflict.object_id,
                }
            ]
        },
    )
    optimizer_run = OptimizerRun.objects.create(
        input_snapshot=snapshot,
        plan_version=version,
        status=OptimizerRun.Status.SUCCEEDED,
        algorithm_version="test",
    )
    return RecoveryRecommendation.objects.create(
        optimizer_run=optimizer_run,
        rank=1,
        status=RecoveryRecommendation.Status.CANDIDATE,
        risk_level=RecoveryRecommendation.RiskLevel.MEDIUM,
        score=Decimal("75.000"),
        summary="Test recommendation",
    )


def assign(user: User, permission_codes: list[str]) -> None:
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
    role = Role.objects.create(name=f"role-{user.username}", code=f"role-{user.username}")
    role.permissions.set(permissions)
    scope = DataScope.objects.create(
        name=f"scope-{user.username}",
        code=f"scope-{user.username}",
        scope_type=DataScope.ScopeType.ALL_NETWORK,
    )
    org = Organization.objects.first() or Organization.objects.create(
        name="Berau Test",
        slug="berau-test-permission",
        kind=Organization.Kind.BERAU,
    )
    UserRoleAssignment.objects.create(
        user=user,
        role=role,
        organization=org,
        data_scope=scope,
    )


def business_counts() -> dict[str, int]:
    return {
        "plans": Plan.objects.count(),
        "versions": PlanVersion.objects.count(),
        "trips": Trip.objects.count(),
        "assignments": Assignment.objects.count(),
        "conflicts": Conflict.objects.count(),
        "snapshots": RecoveryInputSnapshot.objects.count(),
        "optimizerRuns": OptimizerRun.objects.count(),
        "recommendations": RecoveryRecommendation.objects.count(),
        "actions": RecoveryAction.objects.count(),
    }
