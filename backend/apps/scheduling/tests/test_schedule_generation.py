from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.organizations.models import Organization
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import (
    ApprovalDecision,
    ApprovalRequest,
    Conflict,
    OverrideRequest,
    PlanVersion,
    PublishedPlanSnapshot,
    Trip,
)
from apps.scheduling.services import clone_plan_version, compute_plan_diff, generate_plan_version


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


@pytest.mark.django_db
def test_seeded_schedule_generation_is_deterministic_and_idempotent():
    call_command("seed_phase0")
    version = PlanVersion.objects.get(plan__code="PLAN-2026-10-24", version_no=1)

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
    version = PlanVersion.objects.get(plan__code="PLAN-2026-10-24", version_no=1)

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
    version = PlanVersion.objects.get(plan__code="PLAN-2026-10-24", version_no=1)

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
            "rows": [
                {
                    "voyage_id": "VOY-UI-SCHED-001",
                    "vessel_name": "MV Operator UI Import",
                    "customer_name": "Pilot Customer",
                    "laycan_start": "2026-11-05T00:00:00Z",
                    "laycan_end": "2026-11-08T00:00:00Z",
                    "eta": "2026-11-05T06:00:00Z",
                    "required_mt": 64000,
                }
            ],
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
            "horizon_start": "2026-11-05T00:00:00Z",
            "horizon_end": "2026-11-12T23:59:00Z",
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
    version = PlanVersion.objects.get(plan__code="PLAN-2026-10-24", version_no=1)
    assignment = version.trips.order_by("sequence").first().assignment

    client = APIClient()
    client.force_authenticate(user)
    missing_reason = client.post(
        f"/api/scheduling/assignments/{assignment.id}/apply-override/",
        {"description": "Manual correction", "changes": {"next_action": "Hold"}},
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
    assert valid.status_code == 201
    assert OverrideRequest.objects.filter(
        reason_code=OverrideRequest.ReasonCode.MANUAL_CORRECTION
    ).exists()
    assert AuditEvent.objects.filter(action="assignment.override").exists()


@pytest.mark.django_db
def test_publish_is_blocked_until_conflicts_are_resolved_even_after_approvals():
    call_command("seed_phase0")
    platform = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user(username="approval-manager", password="secret")
    assign(user, platform, ["schedule.view", "schedule.approve", "schedule.publish"])
    version = PlanVersion.objects.get(plan__code="PLAN-2026-10-24", version_no=1)
    approval_request = ApprovalRequest.objects.get(request_id="APR-PLAN-2026-10-24-V1")

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
def test_resolved_dual_party_approved_plan_can_publish_and_becomes_immutable():
    call_command("seed_phase0")
    platform = Organization.objects.get(slug="coalflow-platform")
    user = User.objects.create_user(username="publisher", password="secret")
    assign(
        user,
        platform,
        ["schedule.view", "schedule.edit", "schedule.approve", "schedule.publish"],
    )
    version = PlanVersion.objects.get(plan__code="PLAN-2026-10-24", version_no=1)
    Conflict.objects.filter(plan_version=version).update(resolved_at=timezone.now())
    version.validation_status = PlanVersion.ValidationStatus.FEASIBLE
    version.save(update_fields=["validation_status", "updated_at"])
    approval_request = ApprovalRequest.objects.get(request_id="APR-PLAN-2026-10-24-V1")
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
    version = PlanVersion.objects.get(plan__code="PLAN-2026-10-24", version_no=1)
    clone = clone_plan_version(source_version=version)
    trip = clone.trips.order_by("sequence").first()
    trip.planned_end = trip.planned_end + timedelta(hours=1)
    trip.save(update_fields=["planned_end", "updated_at"])

    diff = compute_plan_diff(source_version=version, target_version=clone)

    assert diff["summary"]["changedTripCount"] == 1
    assert diff["summary"]["delayDeltaMinutes"] == 60
