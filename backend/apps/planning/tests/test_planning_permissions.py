import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.masters.models import Location, Route, RouteSegment
from apps.organizations.models import Organization
from apps.planning.models import (
    BridgeWindow,
    ImportJob,
    NavigationConstraintCheck,
    OGVVoyage,
    TideWindow,
)
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment


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
        scope_type=DataScope.ScopeType.ORGANIZATION,
        organization=organization,
    )
    UserRoleAssignment.objects.create(
        user=user,
        role=role,
        organization=organization,
        data_scope=scope,
    )


def make_org():
    return Organization.objects.create(name="Berau", slug="berau-planning", kind="berau")


def make_location(org, code="LOC-MUARA"):
    return Location.objects.create(
        code=code,
        name="Muara",
        organization=org,
        location_type=Location.LocationType.TRANSSHIPMENT,
        latitude="-1.900000",
        longitude="118.000000",
        geofence_radius_m=1000,
    )


def voyage_payload(org, location):
    now = timezone.now()
    return {
        "voyage_id": "VOY-TEST-001",
        "vessel_name": "MV TEST",
        "customer_name": "Customer",
        "vessel_class": "Panamax",
        "eta": now.isoformat(),
        "etb": (now + timezone.timedelta(hours=4)).isoformat(),
        "etc_target": (now + timezone.timedelta(days=2)).isoformat(),
        "laycan_start": now.isoformat(),
        "laycan_end": (now + timezone.timedelta(days=3)).isoformat(),
        "required_mt": 120000,
        "organization_id": org.id,
        "anchorage_location_id": location.id,
    }


@pytest.mark.django_db
def test_schedule_viewer_can_list_but_cannot_create_voyage():
    org = make_org()
    location = make_location(org)
    user = User.objects.create_user(username="schedule-viewer", password="secret")
    assign(user, org, ["schedule.view"])
    OGVVoyage.objects.create(**voyage_payload(org, location))

    client = APIClient()
    client.force_authenticate(user)

    list_response = client.get("/api/planning/ogv-voyages/")
    create_response = client.post(
        "/api/planning/ogv-voyages/",
        {**voyage_payload(org, location), "voyage_id": "VOY-TEST-002"},
        format="json",
    )

    assert list_response.status_code == 200
    assert len(list_response.data) == 1
    assert create_response.status_code == 403


@pytest.mark.django_db
def test_schedule_editor_can_create_voyage_and_emit_audit():
    org = make_org()
    location = make_location(org)
    user = User.objects.create_user(username="schedule-editor", password="secret")
    assign(user, org, ["schedule.view", "schedule.edit"])

    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        "/api/planning/ogv-voyages/",
        voyage_payload(org, location),
        format="json",
    )

    assert response.status_code == 201
    assert AuditEvent.objects.filter(
        action="ogvvoyage.create",
        object_repr__contains="VOY-TEST-001",
    ).exists()


@pytest.mark.django_db
def test_ogv_demand_validation_reports_row_errors_and_persists_import_job():
    org = make_org()
    user = User.objects.create_user(username="schedule-importer", password="secret")
    assign(user, org, ["schedule.view", "schedule.edit"])

    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        "/api/planning/import-jobs/validate-ogv-demand/",
        {
            "filename": "bad-demand.xlsx",
            "rows": [
                {
                    "voyage_id": "VOY-BAD",
                    "vessel_name": "",
                    "customer_name": "Customer",
                    "laycan_start": "not-a-date",
                    "laycan_end": "2026-10-24T00:00:00Z",
                    "eta": "2026-10-24T05:00:00Z",
                    "required_mt": 0,
                }
            ],
        },
        format="json",
    )

    assert response.status_code == 400
    assert response.data["status"] == ImportJob.Status.FAILED
    assert response.data["error_rows"] == 1
    assert {error["field"] for error in response.data["errors"]} == {
        "vessel_name",
        "laycan_start",
        "required_mt",
    }


@pytest.mark.django_db
def test_planning_overview_exposes_tide_and_bridge_constraint_context():
    org = make_org()
    location = make_location(org)
    bridge = make_location(org, "LOC-BRIDGE")
    bridge.location_type = Location.LocationType.BRIDGE
    bridge.save(update_fields=["location_type"])
    route = Route.objects.create(
        code="RTE-TEST",
        name="Test Route",
        organization=org,
        origin="Jetty",
        destination="Muara",
        default_loaded_duration_minutes=480,
        default_empty_duration_minutes=390,
    )
    segment = RouteSegment.objects.create(
        route=route,
        sequence=1,
        from_location="Jetty",
        to_location="Bridge",
        distance_nm=10,
        loaded_duration_minutes=60,
        empty_duration_minutes=50,
        requires_tide_window=True,
        requires_bridge_window=True,
    )
    voyage = OGVVoyage.objects.create(**voyage_payload(org, location))
    now = timezone.now()
    TideWindow.objects.create(
        code="TIDE-TEST",
        location=location,
        window_start=now,
        window_end=now + timezone.timedelta(hours=4),
        min_water_level_m=2.4,
        max_loaded_draft_m=4.2,
        applicable_route_segment=segment,
    )
    BridgeWindow.objects.create(
        code="BRDG-TEST",
        location=bridge,
        window_start=now,
        window_end=now + timezone.timedelta(hours=2),
        clearance_m=12.4,
    )
    NavigationConstraintCheck.objects.create(
        voyage=voyage,
        asset_code="BRG-TEST",
        route_segment=segment,
        constraint_type=NavigationConstraintCheck.ConstraintType.TIDE,
        eta_gate=now + timezone.timedelta(hours=1),
        window_start=now,
        window_end=now + timezone.timedelta(hours=4),
        draft_m=4.1,
        margin_minutes=60,
        status=NavigationConstraintCheck.Status.CAN_CROSS,
    )
    user = User.objects.create_user(username="schedule-overview", password="secret")
    assign(user, org, ["schedule.view"])

    client = APIClient()
    client.force_authenticate(user)
    response = client.get("/api/planning/overview/")

    assert response.status_code == 200
    assert response.data["tideWindows"][0]["applicable_route_segment"]["sequence"] == 1
    assert response.data["bridgeWindows"][0]["location"]["code"] == "LOC-BRIDGE"
    assert response.data["constraintChecks"][0]["route_segment"]["requires_tide_window"] is True
