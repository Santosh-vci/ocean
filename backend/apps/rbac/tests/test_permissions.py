import pytest
from django.contrib.auth.models import User
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.organizations.models import Organization
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment


@pytest.mark.django_db
def test_non_admin_cannot_create_organization():
    user = User.objects.create_user(username="viewer", password="secret")
    org = Organization.objects.create(name="Viewer Org", slug="viewer-org", kind="partner")
    scope = DataScope.objects.create(
        name="Viewer org only",
        code="viewer-org-only",
        scope_type=DataScope.ScopeType.ORGANIZATION,
        organization=org,
    )
    permission = AccessPermission.objects.create(
        code="dashboard.view",
        module="dashboard",
        action="view",
        description="View dashboard",
    )
    role = Role.objects.create(name="Viewer", code="viewer")
    role.permissions.add(permission)
    UserRoleAssignment.objects.create(user=user, role=role, organization=org, data_scope=scope)

    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        "/api/organizations/",
        {"name": "Blocked Org", "slug": "blocked-org", "kind": "partner"},
        format="json",
    )

    assert response.status_code == 403


@pytest.mark.django_db
def test_admin_can_create_organization_and_emit_audit():
    user = User.objects.create_user(username="admin", password="secret")
    permission = AccessPermission.objects.create(
        code="admin.manage_users",
        module="admin",
        action="manage_users",
        description="Manage admin objects",
    )
    role = Role.objects.create(name="Admin", code="admin")
    role.permissions.add(permission)
    platform = Organization.objects.create(name="Platform", slug="platform", kind="platform")
    scope = DataScope.objects.create(
        name="All network",
        code="all-network",
        scope_type=DataScope.ScopeType.ALL_NETWORK,
    )
    UserRoleAssignment.objects.create(
        user=user,
        role=role,
        organization=platform,
        data_scope=scope,
    )

    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        "/api/organizations/",
        {"name": "Created Org", "slug": "created-org", "kind": "partner"},
        format="json",
    )

    assert response.status_code == 201
    assert Organization.objects.filter(slug="created-org").exists()
    assert AuditEvent.objects.filter(action="organization.create").exists()

