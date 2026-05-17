from datetime import datetime, time, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.masters.models import Location
from apps.organizations.models import Organization
from apps.planning.models import BridgeWindow, TideWindow
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import (
    ApprovalDecision,
    ApprovalRequest,
    Conflict,
    ImpactChainAssessment,
    OverrideRequest,
    PlanVersion,
    PublishedPlanSnapshot,
    ScheduleEvent,
    SimulationScenario,
    Trip,
)
from apps.scheduling.services import clone_plan_version, compute_plan_diff, generate_plan_version
from apps.scheduling.services import record_approval_decision, submit_approval_request


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
    assert response.data["validation"]["scenarioCount"] == 1
    assert response.data["simulationScenarios"][0]["id"] == scenario.id
