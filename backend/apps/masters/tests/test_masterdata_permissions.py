import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.masters.models import Location
from apps.organizations.models import Organization
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


@pytest.mark.django_db
def test_masterdata_viewer_cannot_create_coal_grade():
    org = Organization.objects.create(name="Berau", slug="berau-test", kind="berau")
    user = User.objects.create_user(username="viewer", password="secret")
    assign(user, org, ["masterdata.view"])

    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        "/api/master-data/coal-grades/",
        {"code": "EBY", "name": "Ebony", "brand_family": "Ebony"},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_masterdata_manager_can_create_coal_grade_and_emit_audit():
    org = Organization.objects.create(name="Berau", slug="berau-manage", kind="berau")
    user = User.objects.create_user(username="manager", password="secret")
    assign(user, org, ["masterdata.view", "masterdata.manage"])

    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        "/api/master-data/coal-grades/",
        {
            "code": "AGT",
            "name": "Agathis",
            "organization_id": org.id,
            "brand_family": "Agathis",
            "sequence_priority": 1,
        },
        format="json",
    )

    assert response.status_code == 201
    assert AuditEvent.objects.filter(
        action="coalgrade.create",
        object_repr__contains="AGT",
    ).exists()


@pytest.mark.django_db
def test_masterdata_viewer_can_export_locations_but_cannot_import():
    org = Organization.objects.create(name="Berau", slug="berau-location", kind="berau")
    user = User.objects.create_user(username="location-viewer", password="secret")
    assign(user, org, ["masterdata.view"])
    Location.objects.create(
        code="LOC-LATI-PORT",
        name="Lati Port",
        organization=org,
        location_type=Location.LocationType.JETTY,
        latitude="-2.147200",
        longitude="117.500900",
        geofence_radius_m=500,
        parent_area="Lati",
    )

    client = APIClient()
    client.force_authenticate(user)

    export_response = client.get("/api/master-data/locations/export/")
    import_response = client.post(
        "/api/master-data/locations/import/",
        {
            "records": [
                {
                    "code": "LOC-SUARAN-PORT",
                    "name": "Suaran Port",
                    "organization_id": org.id,
                    "location_type": Location.LocationType.JETTY,
                    "latitude": "-2.023100",
                    "longitude": "117.596700",
                }
            ]
        },
        format="json",
    )

    assert export_response.status_code == 200
    assert export_response.data["recordCount"] == 1
    assert import_response.status_code == 403
