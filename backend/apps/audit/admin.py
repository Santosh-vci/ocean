from django.contrib import admin

from .models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = (
        "created_at",
        "actor",
        "organization",
        "action",
        "object_type",
        "object_id",
    )
    list_filter = ("action", "object_type", "created_at")
    search_fields = ("object_repr", "object_id", "actor__username")
    readonly_fields = tuple(field.name for field in AuditEvent._meta.fields)

