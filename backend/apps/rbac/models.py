from django.conf import settings
from django.db import models

from apps.organizations.models import Organization


class AccessPermission(models.Model):
    code = models.CharField(max_length=120, unique=True)
    module = models.CharField(max_length=80)
    action = models.CharField(max_length=80)
    description = models.CharField(max_length=255)

    class Meta:
        ordering = ["module", "action", "code"]

    def __str__(self) -> str:
        return self.code


class Role(models.Model):
    name = models.CharField(max_length=180)
    code = models.SlugField(max_length=180, unique=True)
    description = models.TextField(blank=True)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="roles",
    )
    permissions = models.ManyToManyField(
        AccessPermission,
        blank=True,
        related_name="roles",
    )
    is_system_role = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class DataScope(models.Model):
    class ScopeType(models.TextChoices):
        ALL_NETWORK = "all_network", "All network"
        ORGANIZATION = "organization", "Organization"
        ASSIGNED_ONLY = "assigned_only", "Assigned only"
        CUSTOM = "custom", "Custom"

    name = models.CharField(max_length=180)
    code = models.SlugField(max_length=180, unique=True)
    scope_type = models.CharField(max_length=32, choices=ScopeType.choices)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="data_scopes",
    )
    rules = models.JSONField(default=dict, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class OrganizationMembership(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="organization_memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    title = models.CharField(max_length=180, blank=True)
    is_default = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "organization"),
                name="unique_user_organization_membership",
            )
        ]
        ordering = ["organization__name", "user__username"]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization}"


class UserRoleAssignment(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name="assignments")
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="role_assignments",
    )
    data_scope = models.ForeignKey(
        DataScope,
        on_delete=models.PROTECT,
        related_name="role_assignments",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=("user", "role", "organization", "data_scope"),
                name="unique_user_role_assignment",
            )
        ]
        ordering = ["organization__name", "role__name", "user__username"]

    def __str__(self) -> str:
        return f"{self.user} → {self.role} ({self.organization})"

