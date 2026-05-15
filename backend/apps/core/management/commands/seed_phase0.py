import os

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

from apps.organizations.models import Organization
from apps.rbac.models import (
    AccessPermission,
    DataScope,
    OrganizationMembership,
    Role,
    UserRoleAssignment,
)


class Command(BaseCommand):
    help = "Seed the baseline local-development data required by the current build."

    def handle(self, *args, **options):
        email = os.getenv("SEED_ADMIN_EMAIL", "admin@coalflow.local")
        password = os.getenv("SEED_ADMIN_PASSWORD", "admin12345")
        user_model = get_user_model()
        default_user_password = os.getenv("SEED_USER_PASSWORD", "welcome12345")

        platform, _ = Organization.objects.get_or_create(
            slug="coalflow-platform",
            defaults={"name": "Coalflow Platform", "kind": Organization.Kind.PLATFORM},
        )
        berau, _ = Organization.objects.get_or_create(
            slug="berau-coal",
            defaults={"name": "Berau Coal", "kind": Organization.Kind.BERAU},
        )
        abl, _ = Organization.objects.get_or_create(
            slug="abl",
            defaults={"name": "ABL", "kind": Organization.Kind.ABL},
        )

        permission_rows = [
            ("dashboard.view", "dashboard", "view", "View the control-tower dashboard"),
            ("schedule.view", "schedule", "view", "View schedules"),
            ("schedule.edit", "schedule", "edit", "Edit draft schedules"),
            ("schedule.approve", "schedule", "approve", "Approve proposed schedules"),
            ("schedule.publish", "schedule", "publish", "Publish approved schedules"),
            ("fleet.view", "fleet", "view", "View fleet state"),
            ("fleet.assign", "fleet", "assign", "Assign fleet resources"),
            ("masterdata.view", "masterdata", "view", "View master data"),
            ("masterdata.manage", "masterdata", "manage", "Manage master data"),
            ("audit.view", "audit", "view", "View audit events"),
            ("admin.view", "admin", "view", "View admin consoles"),
            ("admin.manage_users", "admin", "manage_users", "Manage users and organizations"),
        ]
        permissions = {}
        for code, module, action, description in permission_rows:
            permission, _ = AccessPermission.objects.update_or_create(
                code=code,
                defaults={
                    "module": module,
                    "action": action,
                    "description": description,
                },
            )
            permissions[code] = permission

        all_network_scope, _ = DataScope.objects.update_or_create(
            code="all-network",
            defaults={
                "name": "All network",
                "scope_type": DataScope.ScopeType.ALL_NETWORK,
            },
        )
        berau_scope, _ = DataScope.objects.update_or_create(
            code="berau-only",
            defaults={
                "name": "Berau only",
                "scope_type": DataScope.ScopeType.ORGANIZATION,
                "organization": berau,
            },
        )
        abl_scope, _ = DataScope.objects.update_or_create(
            code="abl-only",
            defaults={
                "name": "ABL only",
                "scope_type": DataScope.ScopeType.ORGANIZATION,
                "organization": abl,
            },
        )

        role_rows = {
            "admin": {
                "name": "Admin",
                "description": "Platform administration and configuration.",
                "permissions": permissions.values(),
            },
            "berau-scheduler": {
                "name": "Berau Scheduler",
                "description": "Demand, grade sequence, and schedule review.",
                "permissions": [
                    permissions["dashboard.view"],
                    permissions["schedule.view"],
                    permissions["schedule.edit"],
                    permissions["schedule.approve"],
                    permissions["masterdata.view"],
                    permissions["audit.view"],
                ],
            },
            "abl-dispatcher": {
                "name": "ABL Dispatcher",
                "description": "Fleet dispatch and execution control.",
                "permissions": [
                    permissions["dashboard.view"],
                    permissions["schedule.view"],
                    permissions["schedule.edit"],
                    permissions["fleet.view"],
                    permissions["fleet.assign"],
                    permissions["audit.view"],
                ],
            },
            "joint-control-tower-manager": {
                "name": "Joint Control Tower Manager",
                "description": "Shared cross-party control and publication authority.",
                "permissions": [
                    permissions["dashboard.view"],
                    permissions["schedule.view"],
                    permissions["schedule.approve"],
                    permissions["schedule.publish"],
                    permissions["fleet.view"],
                    permissions["audit.view"],
                ],
            },
            "read-only-viewer": {
                "name": "Read-only Viewer",
                "description": "Safe observation without mutation rights.",
                "permissions": [
                    permissions["dashboard.view"],
                    permissions["schedule.view"],
                    permissions["fleet.view"],
                ],
            },
        }

        roles = {}
        for code, data in role_rows.items():
            role, _ = Role.objects.update_or_create(
                code=code,
                defaults={
                    "name": data["name"],
                    "description": data["description"],
                    "is_system_role": True,
                    "is_active": True,
                },
            )
            role.permissions.set(data["permissions"])
            roles[code] = role

        admin_user = self._upsert_user(
            user_model=user_model,
            username=email,
            email=email,
            password=password,
            is_staff=True,
            is_superuser=True,
        )
        self._assign(admin_user, platform, roles["admin"], all_network_scope, "Platform Admin")

        seeded_users = [
            (
                "berau.scheduler@coalflow.local",
                berau,
                roles["berau-scheduler"],
                berau_scope,
                "Berau Scheduler",
            ),
            (
                "abl.dispatcher@coalflow.local",
                abl,
                roles["abl-dispatcher"],
                abl_scope,
                "ABL Dispatcher",
            ),
            (
                "control.tower@coalflow.local",
                platform,
                roles["joint-control-tower-manager"],
                all_network_scope,
                "Joint Control Tower Manager",
            ),
            (
                "viewer@coalflow.local",
                platform,
                roles["read-only-viewer"],
                all_network_scope,
                "Read-only Viewer",
            ),
        ]

        for username, organization, role, scope, title in seeded_users:
            user = self._upsert_user(
                user_model=user_model,
                username=username,
                email=username,
                password=default_user_password,
            )
            self._assign(user, organization, role, scope, title)

        self.stdout.write(
            self.style.SUCCESS("Seeded baseline Chunk 1 organizations, roles, and users.")
        )

    def _upsert_user(
        self,
        *,
        user_model,
        username: str,
        email: str,
        password: str,
        is_staff: bool = False,
        is_superuser: bool = False,
    ):
        user, created = user_model.objects.get_or_create(
            username=username,
            defaults={
                "email": email,
                "is_staff": is_staff,
                "is_superuser": is_superuser,
            },
        )
        changed_fields = []
        if created:
            user.set_password(password)
            changed_fields.append("password")
        if user.email != email:
            user.email = email
            changed_fields.append("email")
        if user.is_staff != is_staff:
            user.is_staff = is_staff
            changed_fields.append("is_staff")
        if user.is_superuser != is_superuser:
            user.is_superuser = is_superuser
            changed_fields.append("is_superuser")
        if changed_fields:
            user.save(update_fields=changed_fields)
        return user

    def _assign(self, user, organization, role, scope, title):
        OrganizationMembership.objects.update_or_create(
            user=user,
            organization=organization,
            defaults={
                "title": title,
                "is_default": True,
                "is_active": True,
            },
        )
        UserRoleAssignment.objects.update_or_create(
            user=user,
            role=role,
            organization=organization,
            data_scope=scope,
            defaults={"is_active": True},
        )
