import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.organizations.models import Organization
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import Conflict, PlanVersion, Trip
from apps.scheduling.services import generate_plan_version


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
