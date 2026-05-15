from django.contrib import admin

from .models import (
    AccessPermission,
    DataScope,
    OrganizationMembership,
    Role,
    UserRoleAssignment,
)


@admin.register(AccessPermission)
class AccessPermissionAdmin(admin.ModelAdmin):
    list_display = ("code", "module", "action")
    search_fields = ("code", "module", "action")


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "organization", "is_system_role", "is_active")
    list_filter = ("is_system_role", "is_active")
    search_fields = ("name", "code")
    filter_horizontal = ("permissions",)


@admin.register(DataScope)
class DataScopeAdmin(admin.ModelAdmin):
    list_display = ("name", "code", "scope_type", "organization", "is_active")
    list_filter = ("scope_type", "is_active")
    search_fields = ("name", "code")


@admin.register(OrganizationMembership)
class OrganizationMembershipAdmin(admin.ModelAdmin):
    list_display = ("user", "organization", "title", "is_default", "is_active")
    list_filter = ("is_default", "is_active")


@admin.register(UserRoleAssignment)
class UserRoleAssignmentAdmin(admin.ModelAdmin):
    list_display = ("user", "role", "organization", "data_scope", "is_active")
    list_filter = ("role", "organization", "is_active")

