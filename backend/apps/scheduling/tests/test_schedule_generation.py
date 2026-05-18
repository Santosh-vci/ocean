from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.masters.models import AssetCompatibilityRule, Location
from apps.organizations.models import Organization
from apps.planning.models import BridgeWindow, TideWindow
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import (
    ApprovalDecision,
    ApprovalRequest,
    Conflict,
    ImpactChainAssessment,
    OptimizerRun,
    OverrideRequest,
    PlanVersion,
    PublishedPlanSnapshot,
    RecommendationEvaluation,
    RecoveryAction,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    ScenarioAssumption,
    ScenarioConstraintEvaluation,
    ScenarioEventProjection,
    ScenarioOgvProjection,
    ScenarioResourceUtilization,
    ScenarioRun,
    ScenarioTripProjection,
    ScheduleEvent,
    SimulationScenario,
    Trip,
)
from apps.scheduling.services import (
    clone_plan_version,
    compute_plan_diff,
    create_scenario_assumption,
    create_scenario_from_conflict,
    generate_plan_version,
    promote_scenario_to_proposed,
    record_approval_decision,
    simulate_scenario,
    submit_approval_request,
)
from apps.scheduling.recovery_services import (
    RECOVERY_INPUT_SNAPSHOT_ALGORITHM_VERSION,
    RECOVERY_REPAIR_ALGORITHM_VERSION,
    RECOVERY_SCORING_ALGORITHM_VERSION,
    build_recovery_input_snapshot,
    generate_recovery_recommendations,
)


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


def seeded_plan_version() -> PlanVersion:
    return PlanVersion.objects.get(
        plan__name="Berau-ABL Feasible Schedule Horizon",
        version_no=1,
    )


def seeded_approval_request(version: PlanVersion) -> ApprovalRequest:
    return ApprovalRequest.objects.get(plan_version=version)


def operator_iso(days_from_today: int, hour: int, minute: int = 0) -> str:
    target_date = timezone.localdate() + timedelta(days=days_from_today)
    return timezone.make_aware(datetime.combine(target_date, time(hour, minute))).isoformat()


def operator_demand_row(voyage_id: str) -> dict:
    return {
        "voyage_id": voyage_id,
        "vessel_name": "MV Operator UI Import",
        "customer_name": "Pilot Customer",
        "laycan_start": operator_iso(1, 0),
        "laycan_end": operator_iso(4, 0),
        "eta": operator_iso(1, 6),
        "required_mt": 64000,
    }


def replace_gate_windows(*, assignment, bridge_start, bridge_end, tide_start, tide_end):
    BridgeWindow.objects.all().delete()
    TideWindow.objects.all().delete()
    bridge_location = Location.objects.filter(
        location_type=Location.LocationType.BRIDGE,
    ).first() or Location.objects.create(
        code="BRDG-TEST",
        name="Bridge Test Gate",
        location_type=Location.LocationType.BRIDGE,
        latitude=Decimal("0.000000"),
        longitude=Decimal("0.000000"),
    )
    tide_location = Location.objects.filter(
        location_type=Location.LocationType.TIDE_GATE,
    ).first() or Location.objects.create(
        code="TIDE-TEST",
        name="Tide Test Gate",
        location_type=Location.LocationType.TIDE_GATE,
        latitude=Decimal("0.000000"),
        longitude=Decimal("0.000000"),
    )
    BridgeWindow.objects.create(
        code="BRDG-IMPACT-TEST",
        location=bridge_location,
        window_start=bridge_start,
        window_end=bridge_end,
        clearance_m=Decimal("13.20"),
        allowed_asset_class="300ft/330ft barge convoy",
        status=BridgeWindow.Status.OPEN,
    )
    TideWindow.objects.create(
        code="TIDE-IMPACT-TEST",
        location=tide_location,
        window_start=tide_start,
        window_end=tide_end,
        min_water_level_m=Decimal("2.80"),
        max_loaded_draft_m=Decimal("4.80"),
        applicable_route_segment=assignment.route_segment,
        risk_level=TideWindow.RiskLevel.NORMAL,
        source="test",
    )


@pytest.mark.django_db
def test_seeded_schedule_generation_is_deterministic_and_idempotent():
    call_command("seed_phase0")
    version = seeded_plan_version()

    first_trips = list(
        Trip.objects.filter(plan_version=version).values_list(
            "trip_id",
            "sequence",
            "planned_start",
        )
    )
    first_conflicts = list(
        Conflict.objects.filter(plan_version=version).values_list(
            "code",
            "object_id",
            "is_blocking",
        )
    )

    result = generate_plan_version(version)
    second_trips = list(
        Trip.objects.filter(plan_version=version).values_list(
            "trip_id",
            "sequence",
            "planned_start",
        )
    )
    second_conflicts = list(
        Conflict.objects.filter(plan_version=version).values_list(
            "code",
            "object_id",
            "is_blocking",
        )
    )

    assert result.trip_count == 6
    assert first_trips == second_trips
    assert first_conflicts == second_conflicts
    assert version.summary["firstBlockingConstraint"] in {
        "TIDE_WINDOW_MISSED",
        "BRIDGE_WINDOW_MISSED",
        "LAYER_SEQUENCE_VIOLATION",
        "BARGE_UNAVAILABLE",
    }


@pytest.mark.django_db
def test_schedule_viewer_can_read_overview_but_cannot_generate():
    call_command("seed_phase0")
    platform = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user(username="schedule-reader", password="secret")
    assign(user, platform, ["schedule.view"])
    version = seeded_plan_version()

    client = APIClient()
    client.force_authenticate(user)
    overview_response = client.get("/api/scheduling/overview/")
    generate_response = client.post(f"/api/scheduling/plan-versions/{version.id}/generate/")

    assert overview_response.status_code == 200
    assert overview_response.data["validation"]["tripCount"] == 6
    assert generate_response.status_code == 403


@pytest.mark.django_db
def test_schedule_editor_can_generate_and_clone_with_audit():
    call_command("seed_phase0")
    platform = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user(username="schedule-editor", password="secret")
    assign(user, platform, ["schedule.view", "schedule.edit"])
    version = seeded_plan_version()

    client = APIClient()
    client.force_authenticate(user)
    generate_response = client.post(f"/api/scheduling/plan-versions/{version.id}/generate/")
    clone_response = client.post(f"/api/scheduling/plan-versions/{version.id}/clone/")

    assert generate_response.status_code == 200
    assert clone_response.status_code == 201
    assert AuditEvent.objects.filter(action="planversion.generate").exists()
    assert AuditEvent.objects.filter(action="planversion.clone").exists()


@pytest.mark.django_db
def test_operator_ui_can_create_initial_plan_and_generate_from_blank_operational_seed():
    call_command("seed_phase0", "--reset-operational-data", "--master-data-only")
    user = User.objects.get(username="berau.scheduler@coalflow.local")
    berau = Organization.objects.get(slug="berau-coal")

    client = APIClient()
    client.force_authenticate(user)
    client.post(
        "/api/planning/import-jobs/validate-ogv-demand/",
        {
            "commit": True,
            "filename": "operator-ui-demand.xlsx",
            "source": "operator-ui-action",
            "rows": [operator_demand_row("VOY-UI-SCHED-001")],
        },
        format="json",
    )
    client.post("/api/planning/overview/enter-operating-windows/")
    plan_response = client.post(
        "/api/scheduling/plans/",
        {
            "code": "PLAN-UI-TEST",
            "name": "Operator UI Planning Run",
            "organization_id": berau.id,
            "horizon_start": operator_iso(1, 0),
            "horizon_end": operator_iso(8, 23, 59),
            "status": "active",
        },
        format="json",
    )
    version_response = client.post(
        f"/api/scheduling/plans/{plan_response.data['id']}/create-version/"
    )
    generate_response = client.post(
        f"/api/scheduling/plan-versions/{version_response.data['id']}/generate/"
    )

    assert plan_response.status_code == 201
    assert version_response.status_code == 201
    assert generate_response.status_code == 200
    assert generate_response.data["plan_code"] == "PLAN-UI-TEST"
    assert Trip.objects.filter(plan_version_id=version_response.data["id"]).count() == 2


@pytest.mark.django_db
def test_assignment_override_requires_reason_and_records_audit():
    call_command("seed_phase0")
    platform = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user(username="override-editor", password="secret")
    assign(user, platform, ["schedule.view", "schedule.edit"])
    version = seeded_plan_version()
    assignment = version.trips.order_by("sequence").first().assignment

    client = APIClient()
    client.force_authenticate(user)
    missing_reason = client.post(
        f"/api/scheduling/assignments/{assignment.id}/apply-override/",
        {"description": "Manual correction", "changes": {"next_action": "Hold"}},
        format="json",
    )
    jetty_missing_start = client.post(
        f"/api/scheduling/assignments/{assignment.id}/apply-override/",
        {
            "reason_code": OverrideRequest.ReasonCode.JETTY_DELAY,
            "description": "Force-started from jetty board.",
            "changes": {"status": "loading"},
        },
        format="json",
    )
    valid = client.post(
        f"/api/scheduling/assignments/{assignment.id}/apply-override/",
        {
            "reason_code": OverrideRequest.ReasonCode.MANUAL_CORRECTION,
            "description": "Manual correction from dispatch desk.",
            "changes": {"next_action": "Hold for approval workflow."},
        },
        format="json",
    )

    assert missing_reason.status_code == 400
    assert jetty_missing_start.status_code == 400
    assert valid.status_code == 201
    assert OverrideRequest.objects.filter(
        reason_code=OverrideRequest.ReasonCode.MANUAL_CORRECTION
    ).exists()
    assert AuditEvent.objects.filter(action="assignment.override").exists()


@pytest.mark.django_db
def test_jetty_override_with_actual_start_creates_calculated_impact_chain():
    call_command("seed_phase0")
    platform = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user(username="impact-editor", password="secret")
    assign(user, platform, ["schedule.view", "schedule.edit"])
    assignment = seeded_plan_version().trips.order_by("sequence").first().assignment
    load_start = assignment.trip.events.get(
        event_type=ScheduleEvent.EventType.LOAD_START,
    ).planned_at
    actual_start = load_start + timedelta(minutes=120)
    replace_gate_windows(
        assignment=assignment,
        bridge_start=load_start + timedelta(hours=5, minutes=30),
        bridge_end=load_start + timedelta(hours=6, minutes=30),
        tide_start=load_start + timedelta(hours=7, minutes=30),
        tide_end=load_start + timedelta(hours=8, minutes=30),
    )

    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        f"/api/scheduling/assignments/{assignment.id}/apply-override/",
        {
            "reason_code": OverrideRequest.ReasonCode.JETTY_DELAY,
            "description": "Force-started from operator cockpit.",
            "changes": {
                "status": "loading",
                "next_action": "Force-started from operator cockpit.",
            },
            "impact_context": {"actual_start_at": actual_start.isoformat()},
        },
        format="json",
    )

    assert response.status_code == 201
    assessment = ImpactChainAssessment.objects.get(override_request_id=response.data["id"])
    assert assessment.delay_minutes == 120
    assert assessment.status == ImpactChainAssessment.Status.WARNING
    assert response.data["impact_assessment"]["delay_minutes"] == 120
    assert {node["label"] for node in assessment.nodes} >= {
        "BARGE DELAY",
        "BRIDGE WINDOW OK",
        "TIDE WINDOW OK",
    }
    assert [node["id"] for node in assessment.nodes] == [
        "source",
        "logistics",
        "bridge",
        "tide",
        "target",
    ]
    assert {node["type"] for node in assessment.nodes} == {
        "source_event",
        "logistics_delay",
        "bridge_window",
        "tide_window",
        "final_risk_target",
    }
    for node in assessment.nodes:
        assert {"id", "type", "label", "value", "status", "detail"}.issubset(node)


@pytest.mark.django_db
def test_jetty_override_impact_chain_flags_missed_tide_window():
    call_command("seed_phase0")
    platform = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user(username="impact-risk-editor", password="secret")
    assign(user, platform, ["schedule.view", "schedule.edit"])
    assignment = seeded_plan_version().trips.order_by("sequence").first().assignment
    load_start = assignment.trip.events.get(
        event_type=ScheduleEvent.EventType.LOAD_START,
    ).planned_at
    actual_start = load_start + timedelta(minutes=120)
    replace_gate_windows(
        assignment=assignment,
        bridge_start=load_start + timedelta(hours=3, minutes=30),
        bridge_end=load_start + timedelta(hours=4, minutes=30),
        tide_start=load_start + timedelta(hours=5, minutes=30),
        tide_end=load_start + timedelta(hours=6, minutes=30),
    )

    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        f"/api/scheduling/assignments/{assignment.id}/apply-override/",
        {
            "reason_code": OverrideRequest.ReasonCode.JETTY_DELAY,
            "description": "Force-started from operator cockpit.",
            "changes": {"status": "loading"},
            "impact_context": {"actual_start_at": actual_start.isoformat()},
        },
        format="json",
    )

    assert response.status_code == 201
    assessment = ImpactChainAssessment.objects.get(override_request_id=response.data["id"])
    labels = {node["label"] for node in assessment.nodes}
    assert assessment.status == ImpactChainAssessment.Status.CRITICAL
    assert "TIDE WINDOW MISSED" in labels
    assert any(node.get("missMinutes", 0) > 0 for node in assessment.nodes)


@pytest.mark.django_db
def test_publish_is_blocked_until_conflicts_are_resolved_even_after_approvals():
    call_command("seed_phase0")
    platform = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user(username="approval-manager", password="secret")
    assign(user, platform, ["schedule.view", "schedule.approve", "schedule.publish"])
    version = seeded_plan_version()
    approval_request = seeded_approval_request(version)

    client = APIClient()
    client.force_authenticate(user)
    decision_response = client.post(
        f"/api/scheduling/approval-requests/{approval_request.id}/decide/",
        {
            "authority_role": ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
            "decision": ApprovalDecision.Decision.APPROVE,
            "comments": "Berau accepts the proposed recovery path.",
        },
        format="json",
    )
    publish_response = client.post(f"/api/scheduling/plan-versions/{version.id}/publish/")

    assert decision_response.status_code == 200
    assert publish_response.status_code == 400
    assert not PublishedPlanSnapshot.objects.exists()


@pytest.mark.django_db
def test_resubmitting_completed_approval_request_preserves_approved_state():
    call_command("seed_phase0")
    platform = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user(username="resubmitter", password="secret")
    assign(user, platform, ["schedule.view", "schedule.edit", "schedule.approve"])
    version = seeded_plan_version()
    Conflict.objects.filter(plan_version=version).update(resolved_at=timezone.now())
    version.validation_status = PlanVersion.ValidationStatus.FEASIBLE
    version.save(update_fields=["validation_status", "updated_at"])
    approval_request = seeded_approval_request(version)

    record_approval_decision(
        approval_request=approval_request,
        actor=user,
        authority_role=ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
        decision=ApprovalDecision.Decision.APPROVE,
        comments="Berau approves the feasible plan.",
    )
    approval_request.refresh_from_db()
    version.refresh_from_db()

    assert approval_request.status == ApprovalRequest.Status.APPROVED
    assert version.status == PlanVersion.Status.APPROVED

    duplicate_request = submit_approval_request(
        plan_version=version,
        actor=user,
        reason="Duplicate submit from operator cockpit.",
    )
    duplicate_request.refresh_from_db()
    version.refresh_from_db()

    assert duplicate_request.pk == approval_request.pk
    assert duplicate_request.status == ApprovalRequest.Status.APPROVED
    assert version.status == PlanVersion.Status.APPROVED


@pytest.mark.django_db
def test_resolved_dual_party_approved_plan_can_publish_and_becomes_immutable():
    call_command("seed_phase0")
    platform = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user(username="publisher", password="secret")
    assign(
        user,
        platform,
        ["schedule.view", "schedule.edit", "schedule.approve", "schedule.publish"],
    )
    version = seeded_plan_version()
    Conflict.objects.filter(plan_version=version).update(resolved_at=timezone.now())
    version.validation_status = PlanVersion.ValidationStatus.FEASIBLE
    version.save(update_fields=["validation_status", "updated_at"])
    approval_request = seeded_approval_request(version)
    assignment = version.trips.order_by("sequence").first().assignment

    client = APIClient()
    client.force_authenticate(user)
    client.post(
        f"/api/scheduling/approval-requests/{approval_request.id}/decide/",
        {
            "authority_role": ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
            "decision": ApprovalDecision.Decision.APPROVE,
            "comments": "Berau final approval.",
        },
        format="json",
    )
    publish_response = client.post(f"/api/scheduling/plan-versions/{version.id}/publish/")
    override_response = client.post(
        f"/api/scheduling/assignments/{assignment.id}/apply-override/",
        {
            "reason_code": OverrideRequest.ReasonCode.MANUAL_CORRECTION,
            "description": "Attempt to mutate a published plan.",
            "changes": {"next_action": "Should fail"},
        },
        format="json",
    )

    assert publish_response.status_code == 201
    assert PublishedPlanSnapshot.objects.filter(status=PublishedPlanSnapshot.Status.ACTIVE).exists()
    assert override_response.status_code == 400


@pytest.mark.django_db
def test_plan_diff_reports_changed_trip_delta():
    call_command("seed_phase0")
    version = seeded_plan_version()
    clone = clone_plan_version(source_version=version)
    trip = clone.trips.order_by("sequence").first()
    trip.planned_end = trip.planned_end + timedelta(hours=1)
    trip.save(update_fields=["planned_end", "updated_at"])

    diff = compute_plan_diff(source_version=version, target_version=clone)

    assert diff["summary"]["changedTripCount"] == 1
    assert diff["summary"]["delayDeltaMinutes"] == 60


@pytest.mark.django_db
def test_scheduling_overview_prefers_successor_draft_over_published_live_version():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="berau-coal")
    user = User.objects.create_user("schedule-viewer")
    assign(user, organization, ["schedule.view"])
    published = seeded_plan_version()
    published.status = PlanVersion.Status.PUBLISHED
    published.generated_at = timezone.now() - timedelta(minutes=5)
    published.save(update_fields=["status", "generated_at", "updated_at"])
    draft = clone_plan_version(source_version=published)

    client = APIClient()
    client.force_authenticate(user)
    response = client.get("/api/scheduling/overview/")

    assert response.status_code == 200
    assert response.data["activePlanVersion"]["id"] == draft.id
    assert response.data["activePlanVersion"]["status"] == PlanVersion.Status.DRAFT
    assert response.data["validation"]["tripCount"] == draft.trips.count()


@pytest.mark.django_db
def test_scheduling_overview_keeps_approved_version_active_until_publish():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="berau-coal")
    user = User.objects.create_user("approval-viewer")
    assign(user, organization, ["schedule.view"])
    approved_version = clone_plan_version(source_version=seeded_plan_version())
    approved_version.status = PlanVersion.Status.APPROVED
    approved_version.validation_status = PlanVersion.ValidationStatus.FEASIBLE
    approved_version.save(update_fields=["status", "validation_status", "updated_at"])
    clone_plan_version(source_version=approved_version)

    client = APIClient()
    client.force_authenticate(user)
    response = client.get("/api/scheduling/overview/")

    assert response.status_code == 200
    assert response.data["activePlanVersion"]["id"] == approved_version.id
    assert response.data["activePlanVersion"]["status"] == PlanVersion.Status.APPROVED


@pytest.mark.django_db
def test_transition_scenario_contract_preserves_current_create_simulate_promote_flow():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-editor")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()

    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=baseline.conflicts.order_by("id").first(),
        actor=user,
    )
    assert scenario.status == SimulationScenario.Status.DRAFT
    assert scenario.name == "Recovery scenario"
    assert scenario.baseline_version_id == baseline.id
    assert scenario.scenario_version_id is None

    simulated = simulate_scenario(scenario=scenario)
    simulated.refresh_from_db()
    assert simulated.status == SimulationScenario.Status.SIMULATED
    assert simulated.impact_summary["sourceConflict"]
    assert {
        "delayDeltaMinutes",
        "demurrageDeltaUsd",
        "fleetUtilizationPct",
        "remainingViolations",
    }.issubset(simulated.delta_summary)

    promoted = promote_scenario_to_proposed(scenario=simulated, actor=user)
    promoted.refresh_from_db()
    assert promoted.status == SimulationScenario.Status.PROPOSED
    assert promoted.scenario_version_id is not None
    assert promoted.scenario_version.source_version_id == baseline.id
    assert promoted.scenario_version.plan_id == baseline.plan_id
    assert promoted.scenario_version.status == PlanVersion.Status.PROPOSED
    assert promoted.scenario_version.summary["scenarioLineage"]["selectedRunRef"]
    assert "scenarioDiff" in promoted.scenario_version.summary


@pytest.mark.django_db
def test_selected_run_promotion_materializes_candidate_and_preserves_baseline():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-run-promoter")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    baseline_trip = baseline.trips.order_by("sequence").first()
    baseline_start = baseline_trip.planned_start
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )
    create_scenario_assumption(
        scenario=scenario,
        actor=user,
        kind=ScenarioAssumption.Kind.TRIP_DELAY,
        scope_type=ScenarioAssumption.ScopeType.TRIP,
        scope_id=baseline_trip.id,
        payload={"delay_minutes": 90},
    )
    simulate_scenario(scenario=scenario, actor=user)
    selected_run = scenario.runs.order_by("-created_at", "-id").first()

    promoted = promote_scenario_to_proposed(
        scenario=scenario,
        actor=user,
        run=selected_run,
    )
    candidate_trip = promoted.scenario_version.trips.order_by("sequence").first()
    candidate_event = candidate_trip.events.get(event_type=ScheduleEvent.EventType.LOAD_START)

    baseline_trip.refresh_from_db()
    assert baseline_trip.planned_start == baseline_start
    assert candidate_trip.planned_start == baseline_start + timedelta(minutes=90)
    assert candidate_event.planned_at == baseline_start + timedelta(minutes=90)
    assert promoted.scenario_version.summary["scenarioLineage"] == {
        "baselineVersionId": baseline.id,
        "baselineVersionRef": str(baseline),
        "scenarioId": scenario.scenario_id,
        "scenarioPk": scenario.id,
        "selectedRunId": selected_run.id,
        "selectedRunRef": selected_run.run_id,
        "assumptionIds": list(scenario.assumptions.values_list("assumption_id", flat=True)),
        "algorithmVersion": selected_run.algorithm_version,
        "promotedAt": promoted.scenario_version.summary["scenarioLineage"]["promotedAt"],
        "promotedBy": user.username,
    }
    assert promoted.scenario_version.summary["scenarioDiff"]["summary"]["changedTripCount"] > 0


@pytest.mark.django_db
def test_promoted_candidate_materializes_projected_constraints_for_governance():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-governance")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    scenario = SimulationScenario.objects.get(scenario_id__contains="TUG-OUTAGE")
    run = scenario.runs.order_by("-created_at", "-id").first()

    promoted = promote_scenario_to_proposed(scenario=scenario, actor=user, run=run)
    candidate = promoted.scenario_version

    assert candidate.validation_status == PlanVersion.ValidationStatus.BLOCKED
    assert candidate.conflicts.filter(code="ASSET_OUTAGE_OVERLAP", is_blocking=True).exists()
    approval = submit_approval_request(
        plan_version=candidate,
        actor=user,
        reason="Scenario candidate review.",
    )
    client = APIClient()
    client.force_authenticate(user)
    overview = client.get("/api/scheduling/overview/")

    assert approval.status == ApprovalRequest.Status.PENDING
    assert candidate.status == PlanVersion.Status.PROPOSED
    assert overview.status_code == 200
    assert (
        overview.data["approvalRequests"][0]["scenario_lineage"]["scenarioId"]
        == scenario.scenario_id
    )


@pytest.mark.django_db
def test_transition_scenario_api_contract_preserves_current_response_shape():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-api")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    conflict = baseline.conflicts.order_by("id").first()

    client = APIClient()
    client.force_authenticate(user)
    create_response = client.post(
        f"/api/scheduling/plan-versions/{baseline.id}/create-scenario/",
        {"conflict": conflict.id if conflict else None, "name": "Transition recovery scenario"},
        format="json",
    )
    simulate_response = client.post(
        f"/api/scheduling/scenarios/{create_response.data['id']}/simulate/"
    )
    selected_run_id = simulate_response.data["runs"][0]["id"]
    promote_response = client.post(
        f"/api/scheduling/scenarios/{create_response.data['id']}/promote/",
        {"run_id": selected_run_id},
        format="json",
    )

    assert create_response.status_code == 201
    assert create_response.data["baseline_version"] == baseline.id
    assert create_response.data["scenario_version"] is None
    assert create_response.data["status"] == SimulationScenario.Status.DRAFT
    assert {
        "baseline_version_ref",
        "scenario_version_ref",
        "source_conflict_code",
        "impact_summary",
        "delta_summary",
    }.issubset(create_response.data)
    assert simulate_response.status_code == 200
    assert simulate_response.data["status"] == SimulationScenario.Status.SIMULATED
    assert promote_response.status_code == 200
    assert promote_response.data["status"] == SimulationScenario.Status.PROPOSED
    assert promote_response.data["scenario_version"] is not None


@pytest.mark.django_db
def test_scenario_sources_assumptions_and_run_queue_are_persisted_and_audited():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-assumption-editor")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    conflict = baseline.conflicts.order_by("id").first()

    client = APIClient()
    client.force_authenticate(user)
    manual_response = client.post(
        f"/api/scheduling/plan-versions/{baseline.id}/create-scenario/",
        {"name": "Manual what-if"},
        format="json",
    )
    linked_response = client.post(
        f"/api/scheduling/plan-versions/{baseline.id}/create-scenario/",
        {"conflict": conflict.id if conflict else None, "name": "Conflict what-if"},
        format="json",
    )
    assignment = baseline.trips.order_by("sequence").first().assignment
    override_response = client.post(
        f"/api/scheduling/assignments/{assignment.id}/apply-override/",
        {
            "reason_code": OverrideRequest.ReasonCode.MANUAL_CORRECTION,
            "description": "Manual scenario source.",
            "changes": {"next_action": "Create scenario source."},
        },
        format="json",
    )
    override_scenario_response = client.post(
        f"/api/scheduling/plan-versions/{baseline.id}/create-scenario/",
        {"override": override_response.data["id"], "name": "Override what-if"},
        format="json",
    )
    assumption_response = client.post(
        f"/api/scheduling/scenarios/{manual_response.data['id']}/assumptions/",
        {
            "kind": ScenarioAssumption.Kind.TRIP_DELAY,
            "scope_type": ScenarioAssumption.ScopeType.TRIP,
            "scope_id": baseline.trips.order_by("sequence").first().id,
            "payload": {"delay_minutes": 90},
        },
        format="json",
    )
    run_response = client.post(
        f"/api/scheduling/scenarios/{manual_response.data['id']}/runs/",
        {},
        format="json",
    )

    assert manual_response.status_code == 201
    assert linked_response.status_code == 201
    assert override_response.status_code == 201
    assert override_scenario_response.status_code == 201
    assert manual_response.data["source_kind"] == SimulationScenario.SourceKind.MANUAL
    assert linked_response.data["source_kind"] == SimulationScenario.SourceKind.CONFLICT
    assert override_scenario_response.data["source_kind"] == SimulationScenario.SourceKind.OVERRIDE
    assert assumption_response.status_code == 201
    assert assumption_response.data["payload"]["delay_minutes"] == 90
    assert run_response.status_code == 201
    assert run_response.data["status"] == ScenarioRun.Status.QUEUED
    assert ScenarioAssumption.objects.filter(scenario_id=manual_response.data["id"]).count() == 1
    assert ScenarioRun.objects.filter(scenario_id=manual_response.data["id"]).count() == 1
    assert AuditEvent.objects.filter(action="simulation.assumption.create").exists()
    assert AuditEvent.objects.filter(action="simulation.run.create").exists()


@pytest.mark.django_db
def test_seeded_scenario_proves_a_real_baseline_bound_delta():
    call_command("seed_phase0")
    scenario = SimulationScenario.objects.get(scenario_id__contains="TUG-OUTAGE")
    run = scenario.runs.order_by("-created_at").first()

    assert scenario.scenario_version_id is None
    assert list(scenario.assumptions.values_list("kind", flat=True)) == [
        ScenarioAssumption.Kind.ASSET_OUTAGE
    ]
    assert run.summary["projectionSummary"]["changedTripCount"] > 0
    assert run.summary["deltaSummary"]["delayDeltaMinutes"] > 0
    assert run.summary["utilizationSummary"]["totalWaitingMinutes"] > 0
    assert ScenarioConstraintEvaluation.objects.filter(
        run=run,
        code="ASSET_OUTAGE_OVERLAP",
        severity=ScenarioConstraintEvaluation.Severity.CRITICAL,
    ).exists()


@pytest.mark.django_db
def test_scenario_assumptions_reject_scope_outside_baseline():
    call_command("seed_phase0")
    baseline = seeded_plan_version()
    other_version = clone_plan_version(source_version=baseline)
    user = User.objects.create_user("scenario-scope-guard")
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )

    with pytest.raises(ValidationError):
        create_scenario_assumption(
            scenario=scenario,
            actor=user,
            kind=ScenarioAssumption.Kind.TRIP_DELAY,
            scope_type=ScenarioAssumption.ScopeType.TRIP,
            scope_id=other_version.trips.order_by("sequence").first().id,
            payload={"delay_minutes": 60},
        )


@pytest.mark.django_db
def test_new_assumption_resets_simulated_scenario_and_proposed_scenario_rejects_inputs():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-mutation-guard")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )
    simulate_scenario(scenario=scenario, actor=user)
    scenario.refresh_from_db()
    assert scenario.status == SimulationScenario.Status.SIMULATED

    client = APIClient()
    client.force_authenticate(user)
    reset_response = client.post(
        f"/api/scheduling/scenarios/{scenario.id}/assumptions/",
        {
            "kind": ScenarioAssumption.Kind.TRIP_DELAY,
            "scope_type": ScenarioAssumption.ScopeType.TRIP,
            "scope_id": baseline.trips.order_by("sequence").first().id,
            "payload": {"delay_minutes": 30},
        },
        format="json",
    )
    scenario.refresh_from_db()
    assert reset_response.status_code == 201
    assert scenario.status == SimulationScenario.Status.DRAFT
    assert scenario.impact_summary == {}
    assert scenario.delta_summary == {}

    simulate_scenario(scenario=scenario, actor=user)
    promote_scenario_to_proposed(scenario=scenario, actor=user)
    blocked_response = client.post(
        f"/api/scheduling/scenarios/{scenario.id}/assumptions/",
        {
            "kind": ScenarioAssumption.Kind.TRIP_DELAY,
            "scope_type": ScenarioAssumption.ScopeType.TRIP,
            "scope_id": baseline.trips.order_by("sequence").first().id,
            "payload": {"delay_minutes": 45},
        },
        format="json",
    )

    assert blocked_response.status_code == 400


@pytest.mark.django_db
def test_simulation_action_creates_succeeded_run_record():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-runner")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )

    client = APIClient()
    client.force_authenticate(user)
    response = client.post(f"/api/scheduling/scenarios/{scenario.id}/simulate/")

    assert response.status_code == 200
    run = ScenarioRun.objects.get(scenario=scenario)
    assert run.status == ScenarioRun.Status.SUCCEEDED
    assert run.summary["mode"] == "projection"
    assert run.trip_projections.count() == baseline.trips.count()
    assert response.data["runs"][0]["run_id"] == run.run_id


@pytest.mark.django_db
def test_trip_delay_scenario_persists_projection_chain_without_mutating_baseline():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-trip-delay")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    first_trip, second_trip = list(baseline.trips.order_by("sequence")[:2])
    first_baseline_start = first_trip.planned_start
    second_baseline_start = second_trip.planned_start
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )
    create_scenario_assumption(
        scenario=scenario,
        actor=user,
        kind=ScenarioAssumption.Kind.TRIP_DELAY,
        scope_type=ScenarioAssumption.ScopeType.TRIP,
        scope_id=first_trip.id,
        payload={"delay_minutes": 120},
    )

    simulate_scenario(scenario=scenario, actor=user)
    run = ScenarioRun.objects.get(scenario=scenario)
    first_projection = ScenarioTripProjection.objects.get(run=run, trip=first_trip)
    second_projection = ScenarioTripProjection.objects.get(run=run, trip=second_trip)
    first_load_start = ScenarioEventProjection.objects.get(
        run=run,
        trip=first_trip,
        event_type=ScheduleEvent.EventType.LOAD_START,
    )

    first_trip.refresh_from_db()
    second_trip.refresh_from_db()
    assert first_projection.delay_minutes == 120
    assert second_projection.delay_minutes == 120
    assert first_load_start.delay_minutes == 120
    assert first_trip.planned_start == first_baseline_start
    assert second_trip.planned_start == second_baseline_start
    assert second_projection.metadata["dependencySources"][0]["tripId"] == first_trip.trip_id


@pytest.mark.django_db
def test_asset_outage_and_rate_change_scenarios_persist_deterministic_projection_deltas():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-asset-rate")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    trip = baseline.trips.order_by("sequence").first()
    assignment = trip.assignment
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )
    create_scenario_assumption(
        scenario=scenario,
        actor=user,
        kind=ScenarioAssumption.Kind.ASSET_OUTAGE,
        scope_type=ScenarioAssumption.ScopeType.ASSET,
        scope_id=None,
        payload={"asset_code": assignment.tug.code},
        effective_from=trip.planned_start,
        effective_to=trip.planned_start + timedelta(hours=3),
    )
    create_scenario_assumption(
        scenario=scenario,
        actor=user,
        kind=ScenarioAssumption.Kind.RATE_CHANGE,
        scope_type=ScenarioAssumption.ScopeType.ASSET,
        scope_id=None,
        payload={"asset_code": assignment.jetty.code, "rate_tph": 1000},
    )

    simulate_scenario(scenario=scenario, actor=user)
    run = ScenarioRun.objects.get(scenario=scenario)
    projection = ScenarioTripProjection.objects.get(run=run, trip=trip)
    load_start = ScenarioEventProjection.objects.get(
        run=run,
        trip=trip,
        event_type=ScheduleEvent.EventType.LOAD_START,
    )
    load_complete = ScenarioEventProjection.objects.get(
        run=run,
        trip=trip,
        event_type=ScheduleEvent.EventType.LOAD_COMPLETE,
    )

    assert projection.delay_minutes > 180
    assert projection.metadata["loadDurationDeltaMinutes"] > 0
    assert load_start.delay_minutes == 180
    assert load_complete.delay_minutes > load_start.delay_minutes
    assert ScenarioConstraintEvaluation.objects.filter(
        run=run,
        code="ASSET_OUTAGE_OVERLAP",
        severity=ScenarioConstraintEvaluation.Severity.CRITICAL,
    ).exists()


@pytest.mark.django_db
def test_window_change_scenario_reuses_window_evaluation_for_simulation_assessment():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-window-change")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    trip = baseline.trips.order_by("sequence").first()
    assignment = trip.assignment
    tide_projection = trip.events.get(
        event_type=ScheduleEvent.EventType.TIDE_GATE,
    ).planned_at
    replace_gate_windows(
        assignment=assignment,
        bridge_start=tide_projection - timedelta(hours=3),
        bridge_end=tide_projection - timedelta(hours=2),
        tide_start=tide_projection - timedelta(hours=1),
        tide_end=tide_projection + timedelta(hours=1),
    )
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )
    create_scenario_assumption(
        scenario=scenario,
        actor=user,
        kind=ScenarioAssumption.Kind.WINDOW_CHANGE,
        scope_type=ScenarioAssumption.ScopeType.WINDOW,
        scope_id=None,
        payload={"window_code": "TIDE-IMPACT-TEST"},
        effective_from=tide_projection + timedelta(hours=2),
        effective_to=tide_projection + timedelta(hours=3),
    )

    simulate_scenario(scenario=scenario, actor=user)
    run = ScenarioRun.objects.get(scenario=scenario)
    assessment = ImpactChainAssessment.objects.get(
        assessment_id=f"ICA-{run.run_id}-T{trip.id:04d}",
    )

    assert assessment.status == ImpactChainAssessment.Status.WARNING
    assert assessment.metadata["scenarioRunId"] == run.run_id
    assert assessment.metadata["sourceAssumptionIds"]
    assert any(node["label"] == "TIDE WINDOW WAIT" for node in assessment.nodes)


@pytest.mark.django_db
def test_ogv_eta_change_shifts_voyage_completion_and_demurrage_projection():
    call_command("seed_phase0")
    baseline = seeded_plan_version()
    trip = baseline.trips.order_by("sequence").first()
    trip.voyage.demurrage_rate_usd_per_day = Decimal("24000.00")
    trip.voyage.save(update_fields=["demurrage_rate_usd_per_day", "updated_at"])
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=None,
    )
    create_scenario_assumption(
        scenario=scenario,
        actor=None,
        kind=ScenarioAssumption.Kind.OGV_ETA_CHANGE,
        scope_type=ScenarioAssumption.ScopeType.OGV,
        scope_id=trip.voyage_id,
        payload={"eta": (trip.voyage.eta + timedelta(days=3)).isoformat()},
    )

    simulate_scenario(scenario=scenario)
    run = ScenarioRun.objects.get(scenario=scenario)
    voyage_projection = ScenarioOgvProjection.objects.get(run=run, voyage=trip.voyage)

    assert voyage_projection.completion_delta_minutes >= 4320
    assert voyage_projection.demurrage_delta_usd > 0
    assert run.summary["projectionSummary"]["changedTripCount"] > 0


@pytest.mark.django_db
def test_manual_reassignment_persists_resource_delta_and_rechecks_compatibility():
    call_command("seed_phase0")
    baseline = seeded_plan_version()
    trip = baseline.trips.order_by("sequence").first()
    assignment = trip.assignment
    AssetCompatibilityRule.objects.create(
        code="CMP-TEST-TUG09-BRGKAL22",
        name="Test incompatible replacement pair",
        organization=trip.voyage.organization,
        rule_type="tug_barge",
        left_code="BER-TUG-09",
        right_code="BRG-KAL-22",
        is_compatible=False,
    )
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=None,
    )
    create_scenario_assumption(
        scenario=scenario,
        actor=None,
        kind=ScenarioAssumption.Kind.MANUAL_REASSIGNMENT,
        scope_type=ScenarioAssumption.ScopeType.ASSIGNMENT,
        scope_id=assignment.id,
        payload={
            "assignment_id": assignment.id,
            "tug_code": "BER-TUG-09",
            "barge_code": "BRG-KAL-22",
        },
    )

    simulate_scenario(scenario=scenario)
    run = ScenarioRun.objects.get(scenario=scenario)
    projection = ScenarioTripProjection.objects.get(run=run, trip=trip)

    assert projection.assignment_delta["resourceChanged"] is True
    assert projection.assignment_delta["projectedResources"]["tug"] == "BER-TUG-09"
    assert ScenarioConstraintEvaluation.objects.filter(
        run=run,
        code="TUG_BARGE_INCOMPATIBLE",
        severity=ScenarioConstraintEvaluation.Severity.CRITICAL,
    ).exists()
    assert run.summary["projectionSummary"]["changedTripCount"] > 0


@pytest.mark.django_db
def test_scenario_run_projection_endpoint_returns_trip_and_event_rows():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-projection-reader")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    trip = baseline.trips.order_by("sequence").first()
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )
    create_scenario_assumption(
        scenario=scenario,
        actor=user,
        kind=ScenarioAssumption.Kind.TRIP_DELAY,
        scope_type=ScenarioAssumption.ScopeType.TRIP,
        scope_id=trip.id,
        payload={"delay_minutes": 45},
    )
    simulate_scenario(scenario=scenario, actor=user)
    run = ScenarioRun.objects.get(scenario=scenario)

    client = APIClient()
    client.force_authenticate(user)
    response = client.get(f"/api/scheduling/scenario-runs/{run.id}/projections/")

    assert response.status_code == 200
    assert response.data["run"]["run_id"] == run.run_id
    assert response.data["run"]["impact_assessments"][0]["source_kind"] == (
        ImpactChainAssessment.SourceKind.SIMULATION
    )
    assert len(response.data["trip_projections"]) == baseline.trips.count()
    assert len(response.data["event_projections"]) == ScheduleEvent.objects.filter(
        trip__plan_version=baseline,
    ).count()


@pytest.mark.django_db
def test_scenario_run_materializes_constraint_ogv_demurrage_and_utilization_kpis():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-kpi-runner")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    trip = baseline.trips.order_by("sequence").first()
    trip.voyage.demurrage_rate_usd_per_day = Decimal("24000.00")
    trip.voyage.save(update_fields=["demurrage_rate_usd_per_day", "updated_at"])
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )
    create_scenario_assumption(
        scenario=scenario,
        actor=user,
        kind=ScenarioAssumption.Kind.TRIP_DELAY,
        scope_type=ScenarioAssumption.ScopeType.TRIP,
        scope_id=trip.id,
        payload={"delay_minutes": 4320},
    )

    simulate_scenario(scenario=scenario, actor=user)
    run = ScenarioRun.objects.get(scenario=scenario)
    scenario.refresh_from_db()
    first_voyage_projection = ScenarioOgvProjection.objects.get(
        run=run,
        voyage=trip.voyage,
    )

    assert ScenarioConstraintEvaluation.objects.filter(run=run).exists()
    assert ScenarioOgvProjection.objects.filter(run=run).count() == baseline.trips.values(
        "voyage",
    ).distinct().count()
    assert ScenarioResourceUtilization.objects.filter(run=run).exists()
    assert first_voyage_projection.completion_delta_minutes >= 4320
    assert first_voyage_projection.risk_status == ScenarioOgvProjection.RiskStatus.CRITICAL
    assert first_voyage_projection.demurrage_delta_usd > 0
    assert ScenarioConstraintEvaluation.objects.filter(
        run=run,
        code="LAYCAN_BREACH",
        severity=ScenarioConstraintEvaluation.Severity.CRITICAL,
    ).exists()
    critical_count = ScenarioConstraintEvaluation.objects.filter(
        run=run,
        severity=ScenarioConstraintEvaluation.Severity.CRITICAL,
    ).count()
    assert scenario.delta_summary["remainingViolations"] == critical_count
    assert scenario.delta_summary["demurrageDeltaUsd"] > 0
    assert (
        run.summary["ogvSummary"]["demurrageDeltaUsd"]
        == scenario.delta_summary["demurrageDeltaUsd"]
    )


@pytest.mark.django_db
def test_rate_change_scenario_calculates_resource_utilization_delta():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-utilization-runner")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    trip = baseline.trips.order_by("sequence").first()
    jetty_code = trip.assignment.jetty.code
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )
    create_scenario_assumption(
        scenario=scenario,
        actor=user,
        kind=ScenarioAssumption.Kind.RATE_CHANGE,
        scope_type=ScenarioAssumption.ScopeType.ASSET,
        scope_id=None,
        payload={"asset_code": jetty_code, "rate_tph": 1000},
    )

    simulate_scenario(scenario=scenario, actor=user)
    run = ScenarioRun.objects.get(scenario=scenario)
    utilization = ScenarioResourceUtilization.objects.get(
        run=run,
        resource_type=ScenarioResourceUtilization.ResourceType.JETTY,
        resource_code=jetty_code,
    )

    assert utilization.projected_occupied_minutes > utilization.baseline_occupied_minutes
    assert utilization.utilization_delta_pct > 0
    assert run.summary["utilizationSummary"]["averageUtilizationDeltaPct"] > 0


@pytest.mark.django_db
def test_scenario_run_kpi_endpoints_return_materialized_results():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-kpi-reader")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    trip = baseline.trips.order_by("sequence").first()
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )
    create_scenario_assumption(
        scenario=scenario,
        actor=user,
        kind=ScenarioAssumption.Kind.TRIP_DELAY,
        scope_type=ScenarioAssumption.ScopeType.TRIP,
        scope_id=trip.id,
        payload={"delay_minutes": 120},
    )
    simulate_scenario(scenario=scenario, actor=user)
    run = ScenarioRun.objects.get(scenario=scenario)

    client = APIClient()
    client.force_authenticate(user)
    constraints = client.get(f"/api/scheduling/scenario-runs/{run.id}/constraints/")
    utilization = client.get(f"/api/scheduling/scenario-runs/{run.id}/utilization/")
    ogv = client.get(f"/api/scheduling/scenario-runs/{run.id}/ogv-projections/")

    assert constraints.status_code == 200
    assert utilization.status_code == 200
    assert ogv.status_code == 200
    assert len(constraints.data) == ScenarioConstraintEvaluation.objects.filter(run=run).count()
    assert len(utilization.data) == ScenarioResourceUtilization.objects.filter(run=run).count()
    assert len(ogv.data) == ScenarioOgvProjection.objects.filter(run=run).count()


@pytest.mark.django_db
def test_transition_scenario_lifecycle_blocks_invalid_backward_moves():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-guard")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )

    with pytest.raises(ValidationError):
        promote_scenario_to_proposed(scenario=scenario, actor=user)

    simulate_scenario(scenario=scenario)
    promote_scenario_to_proposed(scenario=scenario, actor=user)
    scenario.refresh_from_db()

    with pytest.raises(ValidationError):
        simulate_scenario(scenario=scenario)


@pytest.mark.django_db
def test_transition_scenario_rejects_cross_baseline_lineage():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user("scenario-lineage")
    assign(user, organization, ["schedule.view", "schedule.edit"])
    baseline = seeded_plan_version()
    other_version = clone_plan_version(source_version=baseline)
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=user,
    )
    simulate_scenario(scenario=scenario)
    scenario.scenario_version = clone_plan_version(source_version=other_version)
    scenario.save(update_fields=["scenario_version", "updated_at"])

    with pytest.raises(ValidationError):
        promote_scenario_to_proposed(scenario=scenario, actor=user)


@pytest.mark.django_db
def test_scheduling_overview_includes_scenario_when_active_version_is_scenario_output():
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="berau-coal")
    user = User.objects.create_user("scenario-viewer")
    assign(user, organization, ["schedule.view"])
    baseline = seeded_plan_version()
    baseline.status = PlanVersion.Status.PUBLISHED
    baseline.generated_at = timezone.now() - timedelta(minutes=5)
    baseline.save(update_fields=["status", "generated_at", "updated_at"])
    scenario_version = clone_plan_version(source_version=baseline)
    scenario = SimulationScenario.objects.create(
        scenario_id="SIM-OVERVIEW-ACTIVE-DRAFT",
        name="Overview scenario visibility",
        scenario_type="conflict_recovery",
        baseline_version=baseline,
        scenario_version=scenario_version,
        status=SimulationScenario.Status.SIMULATED,
        impact_summary={"feasibilityPct": 89},
        delta_summary={"remainingViolations": 1},
    )

    client = APIClient()
    client.force_authenticate(user)
    response = client.get("/api/scheduling/overview/")

    assert response.status_code == 200
    assert response.data["activePlanVersion"]["id"] == scenario_version.id
    scenario_ids = {item["scenario_id"] for item in response.data["simulationScenarios"]}
    assert response.data["validation"]["scenarioCount"] == len(scenario_ids)
    assert scenario.scenario_id in scenario_ids
    assert "SIM-JETTY-DELAY" in scenario_ids


@pytest.mark.django_db
def test_phase5_seed_creates_recovery_model_foundation():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)

    snapshot = RecoveryInputSnapshot.objects.get(snapshot_id="RIS-PHASE5-SEED")
    optimizer_run = OptimizerRun.objects.get(run_id="OPT-PHASE5-SEED")
    recommendations = RecoveryRecommendation.objects.filter(optimizer_run=optimizer_run)

    assert snapshot.plan_version == seeded_plan_version()
    assert snapshot.input_hash
    assert snapshot.metadata["algorithmVersion"] == RECOVERY_INPUT_SNAPSHOT_ALGORITHM_VERSION
    assert snapshot.resource_state["tugs"]
    assert snapshot.resource_state["assignments"]
    assert snapshot.event_state["scheduleEvents"]
    assert snapshot.constraint_state["hardConstraints"]["confirmedActualsFrozen"] is True
    assert optimizer_run.input_snapshot == snapshot
    assert optimizer_run.status == OptimizerRun.Status.SUCCEEDED
    assert optimizer_run.algorithm_version == RECOVERY_REPAIR_ALGORITHM_VERSION
    assert recommendations.count() >= 4
    assert set(optimizer_run.summary["candidateStrategies"]) >= {
        "delay_trip",
        "next_window_repair",
        "resequence_trip",
    }
    assert optimizer_run.summary["scoringVersion"] == RECOVERY_SCORING_ALGORITHM_VERSION
    assert optimizer_run.summary["bestRiskLabel"]
    assert RecoveryAction.objects.filter(recommendation__optimizer_run=optimizer_run).count() >= 4
    assert RecommendationEvaluation.objects.filter(
        recommendation__optimizer_run=optimizer_run,
    ).count() == recommendations.count()
    assert recommendations.order_by("rank").first().evaluation.hard_constraints_passed is True


@pytest.mark.django_db
def test_phase5_input_snapshot_builder_normalizes_active_runtime_state():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)
    version = seeded_plan_version()
    user = User.objects.get(username="admin@coalflow.local")
    source_override = OverrideRequest.objects.filter(plan_version=version).first()
    assert source_override is not None

    snapshot = build_recovery_input_snapshot(
        plan_version=version,
        source_override=source_override,
        actor=user,
        metadata={"test": "phase5.1"},
    )

    assert snapshot.source_kind == RecoveryInputSnapshot.SourceKind.OVERRIDE
    assert snapshot.source_ref == f"{source_override.reason_code}:{source_override.pk}"
    assert snapshot.captured_by == user
    assert snapshot.input_hash
    assert snapshot.active_conflict_count == snapshot.constraint_state["openConflicts"]
    assert snapshot.confirmed_event_count == snapshot.event_state["summary"][
        "confirmedEventCount"
    ]
    assert snapshot.tracking_alert_count == snapshot.event_state["summary"][
        "trackingAlertCount"
    ]
    assert snapshot.resource_state["summary"]["assignmentCount"] > 0
    assert snapshot.resource_state["feedHealth"]
    assert "healthRisks" in snapshot.resource_state
    assert "trackingAlerts" in snapshot.event_state
    assert snapshot.constraint_state["tideWindows"]
    assert snapshot.constraint_state["bridgeWindows"]
    assert snapshot.constraint_state["hardConstraints"]["tideBridgeWindowsCaptured"] is True
    assert snapshot.metadata["algorithmVersion"] == RECOVERY_INPUT_SNAPSHOT_ALGORITHM_VERSION


@pytest.mark.django_db
def test_phase5_input_snapshot_build_api_creates_governed_snapshot():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)
    version = seeded_plan_version()
    source_override = OverrideRequest.objects.filter(plan_version=version).first()
    user = User.objects.get(username="admin@coalflow.local")
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/scheduling/recovery-input-snapshots/build/",
        {
            "plan_version": version.id,
            "source_override": source_override.id,
            "metadata": {"operatorFlow": "phase5.1"},
        },
        format="json",
    )
    overview = client.get("/api/scheduling/overview/")

    assert response.status_code == 201
    assert response.data["snapshot_id"].startswith("RIS-")
    assert response.data["source_kind"] == RecoveryInputSnapshot.SourceKind.OVERRIDE
    assert response.data["metadata"]["algorithmVersion"] == (
        RECOVERY_INPUT_SNAPSHOT_ALGORITHM_VERSION
    )
    assert response.data["resource_state"]["assignments"]
    assert response.data["event_state"]["scheduleEvents"]
    assert response.data["constraint_state"]["tideWindows"]
    assert overview.status_code == 200
    assert response.data["snapshot_id"] in {
        item["snapshot_id"] for item in overview.data["recoveryInputSnapshots"]
    }
    assert AuditEvent.objects.filter(
        action="recovery.input_snapshot.build",
        object_repr=response.data["snapshot_id"],
    ).exists()


@pytest.mark.django_db
def test_phase5_deterministic_repair_engine_persists_candidate_set():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)
    snapshot = RecoveryInputSnapshot.objects.get(snapshot_id="RIS-PHASE5-SEED")

    optimizer_run = generate_recovery_recommendations(
        snapshot=snapshot,
        run_id="OPT-PHASE5-TEST",
        replace_existing=True,
        max_candidates=5,
    )
    recommendations = list(optimizer_run.recommendations.prefetch_related("actions"))
    strategies = {item.metadata["strategy"] for item in recommendations}
    action_types = {
        action.action_type
        for recommendation in recommendations
        for action in recommendation.actions.all()
    }

    assert optimizer_run.status == OptimizerRun.Status.SUCCEEDED
    assert optimizer_run.algorithm_version == RECOVERY_REPAIR_ALGORITHM_VERSION
    assert strategies >= {
        "delay_trip",
        "next_window_repair",
        "resequence_trip",
        "tug_barge_swap",
    }
    assert RecoveryAction.ActionType.DELAY_TRIP in action_types
    assert RecoveryAction.ActionType.SHIFT_WINDOW in action_types
    assert RecoveryAction.ActionType.RESEQUENCE_TRIP in action_types
    assert {
        RecoveryAction.ActionType.REASSIGN_TUG,
        RecoveryAction.ActionType.REASSIGN_BARGE,
    } & action_types
    evaluations = RecommendationEvaluation.objects.filter(
        recommendation__optimizer_run=optimizer_run,
    )
    assert evaluations.count() == len(recommendations)
    assert all(item.score_breakdown["algorithmVersion"] == RECOVERY_SCORING_ALGORITHM_VERSION for item in evaluations)
    assert all("components" in item.score_breakdown for item in evaluations)
    assert all("risk" in item.score_breakdown for item in evaluations)
    assert optimizer_run.summary["mode"] == "deterministic_repair"
    assert optimizer_run.summary["bestScore"] == max(
        float(item.score) for item in recommendations
    )


@pytest.mark.django_db
def test_phase5_scoring_and_explanation_contract_is_operator_readable():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)
    optimizer_run = OptimizerRun.objects.get(run_id="OPT-PHASE5-SEED")
    recommendation = optimizer_run.recommendations.select_related("evaluation").order_by(
        "rank",
    ).first()
    explanation_kinds = {node["kind"] for node in recommendation.explanation}
    score_breakdown = recommendation.evaluation.score_breakdown

    assert recommendation.metadata["scoringVersion"] == RECOVERY_SCORING_ALGORITHM_VERSION
    assert recommendation.metadata["riskLabel"] == recommendation.evaluation.metadata["risk"][
        "label"
    ]
    assert score_breakdown["algorithmVersion"] == RECOVERY_SCORING_ALGORITHM_VERSION
    assert set(score_breakdown["weights"]) >= {
        "delayMinutes",
        "missedWindows",
        "resourceConflicts",
        "manualChanges",
        "healthRisk",
        "ogvCompletionRisk",
        "demurrageProxy",
    }
    assert score_breakdown["components"]
    assert all("weightedPenalty" in component for component in score_breakdown["components"])
    assert {"source", "score", "risk", "constraint", "next_step"} <= explanation_kinds
    assert all("title" in node and "detail" in node for node in recommendation.explanation)
    assert [node["sortOrder"] for node in recommendation.explanation] == list(
        range(1, len(recommendation.explanation) + 1)
    )


@pytest.mark.django_db
def test_phase5_recovery_run_api_generates_governed_optimizer_run():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)
    snapshot = RecoveryInputSnapshot.objects.get(snapshot_id="RIS-PHASE5-SEED")
    user = User.objects.get(username="admin@coalflow.local")
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/scheduling/recovery-runs/",
        {
            "input_snapshot": snapshot.id,
            "max_candidates": 5,
            "objective_weights": {"delayMinutes": 0.5},
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["algorithm_version"] == RECOVERY_REPAIR_ALGORITHM_VERSION
    assert response.data["status"] == OptimizerRun.Status.SUCCEEDED
    assert response.data["recommendations"]
    assert response.data["summary"]["candidateStrategies"]
    assert response.data["summary"]["scoringVersion"] == RECOVERY_SCORING_ALGORITHM_VERSION
    assert response.data["recommendations"][0]["metadata"]["riskLabel"]
    assert response.data["recommendations"][0]["evaluation"]["score_breakdown"]["components"]
    assert AuditEvent.objects.filter(
        action="recovery.optimizer.run",
        object_repr=response.data["run_id"],
    ).exists()


@pytest.mark.django_db
def test_phase5_recovery_foundation_read_apis_and_overview_contract():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)
    user = User.objects.get(username="admin@coalflow.local")
    client = APIClient()
    client.force_authenticate(user)

    snapshots = client.get("/api/scheduling/recovery-input-snapshots/")
    runs = client.get("/api/scheduling/optimizer-runs/")
    recommendations = client.get("/api/scheduling/recovery-recommendations/")
    actions = client.get("/api/scheduling/recovery-actions/")
    evaluations = client.get("/api/scheduling/recommendation-evaluations/")
    overview = client.get("/api/scheduling/overview/")

    assert snapshots.status_code == 200
    assert runs.status_code == 200
    assert recommendations.status_code == 200
    assert actions.status_code == 200
    assert evaluations.status_code == 200
    assert snapshots.data[0]["snapshot_id"] == "RIS-PHASE5-SEED"
    assert runs.data[0]["recommendations"][0]["actions"]
    assert recommendations.data[0]["evaluation"]["evaluation_id"].startswith("REV-")
    assert actions.data[0]["constraints_checked"]
    assert evaluations.data[0]["score_breakdown"]
    assert overview.status_code == 200
    assert overview.data["validation"]["optimizerRunCount"] == 1
    assert overview.data["validation"]["recoveryRecommendationCount"] == (
        OptimizerRun.objects.get(run_id="OPT-PHASE5-SEED").recommendations.count()
    )
    assert overview.data["optimizerRuns"][0]["run_id"] == "OPT-PHASE5-SEED"
