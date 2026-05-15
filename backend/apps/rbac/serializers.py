from django.contrib.auth import get_user_model
from rest_framework import serializers

from apps.organizations.serializers import OrganizationSerializer

from .models import (
    AccessPermission,
    DataScope,
    OrganizationMembership,
    Role,
    UserRoleAssignment,
)
from .services import permission_codes_for_user

User = get_user_model()


class AccessPermissionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AccessPermission
        fields = ("id", "code", "module", "action", "description")


class DataScopeSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = DataScope
        fields = ("id", "name", "code", "scope_type", "organization", "rules", "is_active")


class RoleSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    permissions = AccessPermissionSerializer(read_only=True, many=True)

    class Meta:
        model = Role
        fields = (
            "id",
            "name",
            "code",
            "description",
            "organization",
            "permissions",
            "is_system_role",
            "is_active",
        )


class OrganizationMembershipSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = OrganizationMembership
        fields = ("organization", "title", "is_default", "is_active")


class UserRoleAssignmentSerializer(serializers.ModelSerializer):
    role = RoleSerializer(read_only=True)
    organization = OrganizationSerializer(read_only=True)
    data_scope = DataScopeSerializer(read_only=True)

    class Meta:
        model = UserRoleAssignment
        fields = ("role", "organization", "data_scope", "is_active")


class UserSummarySerializer(serializers.ModelSerializer):
    memberships = OrganizationMembershipSerializer(
        source="organization_memberships",
        many=True,
        read_only=True,
    )
    assignments = UserRoleAssignmentSerializer(
        source="role_assignments",
        many=True,
        read_only=True,
    )

    class Meta:
        model = User
        fields = ("id", "username", "email", "is_active", "memberships", "assignments")


class MeSerializer(UserSummarySerializer):
    permissions = serializers.SerializerMethodField()

    class Meta(UserSummarySerializer.Meta):
        fields = UserSummarySerializer.Meta.fields + ("permissions",)

    def get_permissions(self, obj) -> list[str]:
        return sorted(permission_codes_for_user(obj))

