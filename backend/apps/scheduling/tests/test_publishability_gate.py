from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.flows.definitions import seed_canonical_flow_definitions
from apps.flows.models import FlowStepRun
from apps.flows.services import evaluate_flow_run, start_flow
from apps.masters.models import CoalGrade, Location
from apps.organizations.models import Organization
from apps.planning.models import BridgeWindow, CargoLayerStep, ImportJob, OGVVoyage, TideWindow
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import (
    ApprovalDecision,
    ApprovalRequest,
    Conflict,
    OptimizerRun,
    Plan,
    PlanVersion,
    PublishabilityAssessment,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    RootCauseRepairAssessment,
    SimulationScenario,
    Trip,
)
from apps.scheduling.publishability_services import assess_plan_publishability
from apps.scheduling.services import clone_plan_version, publish_plan_version
from apps.telemetry.models import AssetIdentity, TelemetrySource, TrackingAlert


@pytest.mark.django_db
def test_publishability_service_returns_publishable_for_clean_approved_plan():
    user, org = make_user("pub-clean")
    version = make_clean_approved_plan(user, org)

    assessment = assess_plan_publishability(plan_version=version, actor=user)

    assert assessment.status == PublishabilityAssessment.Status.PUBLISHABLE
    assert assessment.blocking_reason_count == 0
    assert assessment.warning_count == 0
    assert assessment.approval_status == "clear"
    assert assessment.conflict_status == "clear"
    assert assessment.operating_window_status == "clear"


@pytest.mark.django_db
def test_publishability_service_warns_for_mitigated_recovery_origin_risk():
    user, org = make_user("pub-warning")
    version = make_clean_approved_plan(user, org)
    recommendation = link_recovery_origin(version, user)
    RootCauseRepairAssessment.objects.create(
        recommendation=recommendation,
        source_kind="conflict",
        source_ref="CONFLICT-1",
        source_cause_type="BARGE_UNAVAILABLE",
        status=RootCauseRepairAssessment.Status.MITIGATES_CAUSE,
        required_resolution={"family": "barge"},
        observed_resolution={"mitigation": True},
        residual_risk={"count": 1, "items": ["Original outage still active."]},
        assessed_by_algorithm_version="test",
    )

    assessment = assess_plan_publishability(plan_version=version, actor=user)

    assert assessment.status == PublishabilityAssessment.Status.WARNING
    assert assessment.warning_count == 1
    assert assessment.recommendation_origin_status == "warning"


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("mutator", "expected_group"),
    [
        (lambda version, _user: version.approval_requests.all().delete(), "approval"),
        (
            lambda version, _user: Conflict.objects.create(
                plan_version=version,
                code="JETTY_OVERLAP",
                severity=Conflict.Severity.CRITICAL,
                message="Jetty overlap remains.",
                is_blocking=True,
            ),
            "conflict",
        ),
        (
            lambda version, _user: mark_first_cargo_step_blocked(version),
            "cargo_sequence",
        ),
        (
            lambda _version, _user: TideWindow.objects.all().delete(),
            "operating_window",
        ),
        (
            lambda version, _user: mark_source_inputs_changed(version),
            "conflict",
        ),
        (
            lambda version, user: make_tracking_alert(version, user),
            "telemetry",
        ),
        (
            lambda version, user: link_recovery_origin(version, user),
            "recommendation_origin",
        ),
    ],
)
def test_publishability_service_blocks_hard_gate_failures(mutator, expected_group):
    user, org = make_user(f"pub-block-{expected_group}")
    version = make_clean_approved_plan(user, org, with_cargo_step=True)
    mutator(version, user)

    assessment = assess_plan_publishability(plan_version=version, actor=user)

    assert assessment.status == PublishabilityAssessment.Status.BLOCKED
    assert assessment.blocking_reason_count >= 1
    assert any(
        detail["group"] == expected_group and detail["status"] == "blocked"
        for detail in assessment.details
    )


@pytest.mark.django_db
def test_publishability_blocks_horizon_wide_operator_recovery_windows():
    user, org = make_user("pub-recovery-window")
    version = make_clean_approved_plan(user, org)
    location = Location.objects.filter(location_type=Location.LocationType.TIDE_GATE).first()
    now = timezone.now()
    TideWindow.objects.create(
        code="TIDE-OPERATOR-RECOVERY-CLOSURE",
        location=location,
        window_start=now,
        window_end=now + timedelta(days=8),
        min_water_level_m=Decimal("2.90"),
        max_loaded_draft_m=Decimal("4.80"),
        source="operator-recovery-repair",
        is_active=True,
    )

    assessment = assess_plan_publishability(plan_version=version, actor=user)

    assert assessment.status == PublishabilityAssessment.Status.BLOCKED
    assert any(
        detail["key"] == "operator_recovery_windows_bounded"
        and detail["status"] == "blocked"
        for detail in assessment.details
    )


@pytest.mark.django_db
def test_publishability_ignores_synthetic_phase3_seed_alerts():
    user, org = make_user("pub-synthetic-alert")
    version = make_clean_approved_plan(user, org)
    alert = make_tracking_alert(version, user)
    alert.evidence = {"seed": "phase_3_sample_movement"}
    alert.save(update_fields=["evidence", "updated_at"])

    assessment = assess_plan_publishability(plan_version=version, actor=user)

    assert assessment.status == PublishabilityAssessment.Status.PUBLISHABLE
    telemetry_detail = next(
        detail for detail in assessment.details if detail["key"] == "telemetry_alerts_clear"
    )
    assert telemetry_detail["status"] == "clear"


@pytest.mark.django_db
def test_publishability_allows_bounded_same_day_operator_recovery_windows():
    user, org = make_user("pub-bounded-recovery-window")
    version = make_clean_approved_plan(user, org)
    location = Location.objects.filter(location_type=Location.LocationType.TIDE_GATE).first()
    now = timezone.now()
    TideWindow.objects.create(
        code="TIDE-OPERATOR-RECOVERY-01",
        location=location,
        window_start=now,
        window_end=now + timedelta(hours=13),
        min_water_level_m=Decimal("2.90"),
        max_loaded_draft_m=Decimal("4.80"),
        source="operator-recovery-repair",
        is_active=True,
    )

    assessment = assess_plan_publishability(plan_version=version, actor=user)

    assert assessment.status == PublishabilityAssessment.Status.PUBLISHABLE
    assert not any(
        detail["key"] == "operator_recovery_windows_bounded"
        for detail in assessment.details
    )


@pytest.mark.django_db
def test_publishability_api_uses_schedule_view_permission():
    user, org = make_user("pub-api", permissions=("schedule.view",))
    version = make_clean_approved_plan(user, org)
    path = f"/api/scheduling/plan-versions/{version.id}/publishability-assessment/"

    anonymous = APIClient(HTTP_HOST="localhost").post(path, {}, format="json")
    assert anonymous.status_code in {401, 403}

    no_access = User.objects.create_user(username="pub-no-access", password="pw")
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(user=no_access)
    denied = client.post(path, {}, format="json")
    assert denied.status_code == 403

    allowed = APIClient(HTTP_HOST="localhost")
    allowed.force_authenticate(user=user)
    created = allowed.post(path, {}, format="json")
    fetched = allowed.get(path)

    assert created.status_code == 200
    assert created.data["status"] == PublishabilityAssessment.Status.PUBLISHABLE
    assert fetched.status_code == 200
    assert fetched.data["assessment_id"] == created.data["assessment_id"]


@pytest.mark.django_db
def test_publish_plan_version_refuses_blocked_publishability():
    user, org = make_user("pub-guard")
    version = make_clean_approved_plan(user, org)
    Conflict.objects.create(
        plan_version=version,
        code="BARGE_UNAVAILABLE",
        severity=Conflict.Severity.CRITICAL,
        message="Unavailable barge remains.",
        is_blocking=False,
    )

    with pytest.raises(ValidationError, match="publishability gate"):
        publish_plan_version(plan_version=version, actor=user)

    assert PublishabilityAssessment.objects.filter(
        plan_version=version,
        status=PublishabilityAssessment.Status.BLOCKED,
    ).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "root_cause_status",
    [
        RootCauseRepairAssessment.Status.DOES_NOT_ADDRESS_CAUSE,
        RootCauseRepairAssessment.Status.UNKNOWN,
    ],
)
def test_recovery_origin_blocks_failed_root_cause_before_and_after_regeneration(
    root_cause_status,
):
    user, org = make_user(f"pub-root-{root_cause_status}")
    version = make_clean_approved_plan(user, org)
    recommendation = link_recovery_origin(version, user)
    RootCauseRepairAssessment.objects.create(
        recommendation=recommendation,
        source_kind="conflict",
        source_ref="CONFLICT-1",
        source_cause_type="BARGE_UNAVAILABLE",
        status=root_cause_status,
        required_resolution={"family": "barge"},
        observed_resolution={"action": "reassign_cts"},
        residual_risk={"level": "high"},
        assessed_by_algorithm_version="test",
    )

    before_regeneration = assess_plan_publishability(plan_version=version, actor=user)
    version.summary = {
        "tripCount": version.trips.count(),
        "conflictCount": 0,
        "blockingConflictCount": 0,
        **{
            key: value
            for key, value in version.summary.items()
            if key in {"recoveryOrigin", "scenarioLineage"}
        },
    }
    version.save(update_fields=["summary", "updated_at"])
    after_regeneration = assess_plan_publishability(plan_version=version, actor=user)

    for assessment in [before_regeneration, after_regeneration]:
        assert assessment.status == PublishabilityAssessment.Status.BLOCKED
        assert any(
            detail["key"] == "recommendation_origin_root_cause"
            and detail["status"] == "blocked"
            and detail["evidence"]["rootCauseStatus"] == root_cause_status
            for detail in assessment.details
        )


@pytest.mark.django_db
def test_publish_guard_refuses_recovery_origin_without_passing_root_cause():
    user, org = make_user("pub-root-guard")
    version = make_clean_approved_plan(user, org)
    recommendation = link_recovery_origin(version, user)
    RootCauseRepairAssessment.objects.create(
        recommendation=recommendation,
        source_kind="conflict",
        source_ref="CONFLICT-1",
        source_cause_type="BARGE_UNAVAILABLE",
        status=RootCauseRepairAssessment.Status.DOES_NOT_ADDRESS_CAUSE,
        required_resolution={"family": "barge"},
        observed_resolution={"action": "reassign_cts"},
        residual_risk={"level": "high"},
        assessed_by_algorithm_version="test",
    )

    with pytest.raises(ValidationError, match="publishability gate"):
        publish_plan_version(plan_version=version, actor=user)

    assert PublishabilityAssessment.objects.filter(
        plan_version=version,
        status=PublishabilityAssessment.Status.BLOCKED,
        recommendation_origin_status="blocked",
    ).exists()


@pytest.mark.django_db
def test_recovery_origin_provenance_survives_successor_plan_clone():
    user, org = make_user("pub-provenance-clone")
    version = make_clean_approved_plan(user, org)
    recommendation = link_recovery_origin(version, user)

    clone = clone_plan_version(source_version=version, created_by=user)

    assert clone.summary["recoveryOrigin"]["recommendationPk"] == recommendation.pk
    assert clone.summary["recoveryOrigin"]["recommendationRef"] == recommendation.recommendation_id
    assert clone.summary["scenarioLineage"]["scenarioPk"] == version.summary["scenarioLineage"]["scenarioPk"]


@pytest.mark.django_db
def test_flow_advances_from_publishability_step_after_clear_assessment():
    seed_canonical_flow_definitions()
    user, org = make_user("pub-flow")
    version = make_clean_approved_plan(user, org, with_import_job=True)
    flow_run = start_flow("operator_happy_path_v1", actor=user)

    flow_run.refresh_from_db()
    assert flow_run.current_step_key == "run_publishability_check"

    assess_plan_publishability(plan_version=version, actor=user)
    evaluate_flow_run(flow_run, actor=user)
    flow_run.refresh_from_db()
    step = flow_run.step_runs.get(step_key="run_publishability_check")

    assert step.status == FlowStepRun.Status.COMPLETED
    assert flow_run.current_step_key == "publish_plan"


@pytest.mark.django_db
def test_flow_blocks_publishability_step_after_blocked_assessment():
    seed_canonical_flow_definitions()
    user, org = make_user("pub-flow-blocked")
    version = make_clean_approved_plan(user, org, with_import_job=True)
    Conflict.objects.create(
        plan_version=version,
        code="BRIDGE_WINDOW_MISSED",
        severity=Conflict.Severity.CRITICAL,
        message="Bridge window miss remains.",
        is_blocking=False,
    )
    flow_run = start_flow("operator_happy_path_v1", actor=user)
    assess_plan_publishability(plan_version=version, actor=user)
    evaluate_flow_run(flow_run, actor=user)
    flow_run.refresh_from_db()
    step = flow_run.step_runs.get(step_key="run_publishability_check")

    assert step.status == FlowStepRun.Status.BLOCKED
    assert "conflict" in step.blocked_reason.lower()
    assert flow_run.current_step_key == "run_publishability_check"


def make_user(username: str, permissions=("schedule.view", "schedule.edit", "schedule.publish")):
    org = Organization.objects.create(
        name=username,
        slug=username,
        kind=Organization.Kind.BERAU,
    )
    user = User.objects.create_user(username=username, password="pw")
    assign(user, org, permissions)
    return user, org


def assign(user, organization, permission_codes):
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
    UserRoleAssignment.objects.create(
        user=user,
        role=role,
        organization=organization,
        data_scope=scope,
    )


def make_clean_approved_plan(
    user,
    org,
    *,
    with_cargo_step=False,
    with_import_job=False,
) -> PlanVersion:
    now = timezone.now()
    plan = Plan.objects.create(
        code=f"PLAN-{org.slug}",
        name="Publishability plan",
        organization=org,
        horizon_start=now,
        horizon_end=now + timedelta(days=3),
        status=Plan.Status.ACTIVE,
    )
    version = PlanVersion.objects.create(
        plan=plan,
        version_no=1,
        status=PlanVersion.Status.APPROVED,
        generated_at=now,
        created_by=user,
    )
    voyage = OGVVoyage.objects.create(
        voyage_id=f"VOY-{org.slug}",
        vessel_name="MV Publishability",
        customer_name="Customer",
        eta=now,
        laycan_start=now,
        laycan_end=now + timedelta(days=2),
        required_mt=12000,
        organization=org,
    )
    cargo_step = make_cargo_step(voyage) if with_cargo_step else None
    Trip.objects.create(
        plan_version=version,
        trip_id=f"TRIP-{org.slug}",
        sequence=1,
        voyage=voyage,
        cargo_layer_step=cargo_step,
        planned_start=now,
        planned_end=now + timedelta(hours=8),
        planned_quantity_mt=12000,
    )
    if with_import_job:
        ImportJob.objects.create(
            import_type=ImportJob.ImportType.OGV_DEMAND,
            filename="publishability-demand.json",
            source="test",
            status=ImportJob.Status.IMPORTED,
            total_rows=1,
            valid_rows=1,
            created_by=user,
        )
    make_windows(now)
    make_approved_request(version, user, org)
    return version


def make_windows(now):
    tide_location = Location.objects.create(
        code=f"TIDE-{Location.objects.count()}",
        name="Tide Gate",
        location_type=Location.LocationType.TIDE_GATE,
        latitude=Decimal("-1.100000"),
        longitude=Decimal("118.100000"),
    )
    bridge_location = Location.objects.create(
        code=f"BRIDGE-{Location.objects.count()}",
        name="Bridge",
        location_type=Location.LocationType.BRIDGE,
        latitude=Decimal("-1.200000"),
        longitude=Decimal("118.200000"),
    )
    TideWindow.objects.create(
        code=f"TIDE-PUB-{TideWindow.objects.count()}",
        location=tide_location,
        window_start=now,
        window_end=now + timedelta(hours=12),
        min_water_level_m=Decimal("2.10"),
        max_loaded_draft_m=Decimal("4.50"),
        is_active=True,
    )
    BridgeWindow.objects.create(
        code=f"BRIDGE-PUB-{BridgeWindow.objects.count()}",
        location=bridge_location,
        window_start=now,
        window_end=now + timedelta(hours=12),
        clearance_m=Decimal("12.50"),
        status=BridgeWindow.Status.OPEN,
        is_active=True,
    )


def make_approved_request(version, user, org):
    request = ApprovalRequest.objects.create(
        request_id=f"APR-{version.plan.code}-V{version.version_no}",
        plan_version=version,
        status=ApprovalRequest.Status.APPROVED,
        required_authorities=[
            ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
            ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
        ],
        reason="Publishability test approval.",
        requested_by=user,
        decided_at=timezone.now(),
    )
    for role in request.required_authorities:
        ApprovalDecision.objects.create(
            approval_request=request,
            authority_role=role,
            decision=ApprovalDecision.Decision.APPROVE,
            actor=user,
            organization=org,
        )
    return request


def make_cargo_step(voyage):
    grade = CoalGrade.objects.create(
        code=f"CG-{CoalGrade.objects.count()}",
        name="Test Coal",
        sequence_priority=1,
    )
    return CargoLayerStep.objects.create(
        voyage=voyage,
        hatch_no=1,
        layer_no=1,
        required_sequence_no=1,
        coal_grade=grade,
        required_mt=12000,
        remaining_mt=12000,
        status=CargoLayerStep.Status.PLANNED,
    )


def mark_first_cargo_step_blocked(version):
    step = version.trips.exclude(cargo_layer_step__isnull=True).first().cargo_layer_step
    step.status = CargoLayerStep.Status.BLOCKED
    step.blocking_reason = "Sequence blocked for test."
    step.save(update_fields=["status", "blocking_reason", "updated_at"])


def mark_source_inputs_changed(version):
    version.summary = {**version.summary, "sourceInputsChanged": True}
    version.save(update_fields=["summary", "updated_at"])


def make_tracking_alert(version, user):
    trip = version.trips.first()
    source = TelemetrySource.objects.create(
        source_id=f"TEL-{version.plan.code}",
        name="Telemetry",
        source_type=TelemetrySource.SourceType.MANUAL,
    )
    identity = AssetIdentity.objects.create(
        source=source,
        asset_type=AssetIdentity.AssetType.BARGE,
        asset_code="BG-PUB",
        external_id=f"BG-PUB-{version.id}",
        external_id_type=AssetIdentity.ExternalIdType.SYNTHETIC_ID,
    )
    return TrackingAlert.objects.create(
        alert_id=f"ALERT-{version.id}",
        alert_type=TrackingAlert.AlertType.ETA_RISK,
        severity=TrackingAlert.Severity.WARNING,
        asset_type=AssetIdentity.AssetType.BARGE,
        asset_code="BG-PUB",
        source=source,
        asset_identity=identity,
        trip=trip,
        message="ETA risk remains.",
        status=TrackingAlert.Status.OPEN,
        source_kind=TrackingAlert.SourceKind.OBSERVED,
        opened_at=timezone.now(),
    )


def link_recovery_origin(version, user):
    baseline = PlanVersion.objects.create(
        plan=version.plan,
        version_no=2,
        status=PlanVersion.Status.VALIDATED,
        generated_at=timezone.now(),
        created_by=user,
    )
    scenario = SimulationScenario.objects.create(
        scenario_id=f"SCN-{version.id}",
        name="Recovery scenario",
        scenario_type="recovery",
        baseline_version=baseline,
        scenario_version=version,
        status=SimulationScenario.Status.PROPOSED,
        created_by=user,
    )
    version.summary = {
        **version.summary,
        "scenarioLineage": {
            "baselineVersionId": baseline.id,
            "baselineVersionRef": str(baseline),
            "scenarioId": scenario.scenario_id,
            "scenarioPk": scenario.id,
            "selectedRunId": 1,
            "selectedRunRef": "RUN-1",
            "assumptionIds": [],
            "algorithmVersion": "test",
            "promotedAt": timezone.now().isoformat(),
            "promotedBy": user.username,
        },
    }
    version.save(update_fields=["summary", "updated_at"])
    snapshot = RecoveryInputSnapshot.objects.create(
        plan_version=baseline,
        source_kind=RecoveryInputSnapshot.SourceKind.CONFLICT,
        source_ref="CONFLICT-1",
    )
    run = OptimizerRun.objects.create(
        input_snapshot=snapshot,
        plan_version=baseline,
        status=OptimizerRun.Status.SUCCEEDED,
        algorithm_version="test",
    )
    recommendation = RecoveryRecommendation.objects.create(
        optimizer_run=run,
        rank=1,
        status=RecoveryRecommendation.Status.MATERIALIZED,
        risk_level=RecoveryRecommendation.RiskLevel.MEDIUM,
        score=Decimal("80.000"),
        summary="Recovery option",
        scenario=scenario,
    )
    version.summary = {
        **version.summary,
        "recoveryOrigin": {
            "recommendationPk": recommendation.pk,
            "recommendationRef": recommendation.recommendation_id,
            "scenarioPk": scenario.pk,
            "scenarioId": scenario.scenario_id,
            "baselineVersionId": baseline.pk,
            "selectedRunRef": "RUN-1",
        },
    }
    version.save(update_fields=["summary", "updated_at"])
    return recommendation
