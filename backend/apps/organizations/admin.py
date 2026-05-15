from django.contrib import admin

from .models import Organization


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "kind", "is_active", "updated_at")
    list_filter = ("kind", "is_active")
    search_fields = ("name", "slug")

