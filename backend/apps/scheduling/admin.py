from django.contrib import admin

from .models import (
    ApprovalDecision,
    ApprovalRequest,
    Assignment,
    Conflict,
    ExportJob,
    OverrideRequest,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
    ScheduleEvent,
    SimulationScenario,
    Trip,
)


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "horizon_start", "horizon_end", "status")
    list_filter = ("status", "organization")
    search_fields = ("code", "name")


@admin.register(PlanVersion)
class PlanVersionAdmin(admin.ModelAdmin):
    list_display = ("plan", "version_no", "status", "validation_status", "generated_at")
    list_filter = ("status", "validation_status")
    search_fields = ("plan__code",)


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("trip_id", "plan_version", "sequence", "voyage", "status")
    list_filter = ("status", "plan_version")
    search_fields = ("trip_id", "voyage__voyage_id", "voyage__vessel_name")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("trip", "tug", "barge", "jetty", "cts", "status")
    list_filter = ("status", "jetty", "cts")
    search_fields = ("trip__trip_id", "tug__code", "barge__code")


@admin.register(ScheduleEvent)
class ScheduleEventAdmin(admin.ModelAdmin):
    list_display = ("trip", "sequence", "event_type", "planned_at", "status")
    list_filter = ("event_type", "status")
    search_fields = ("trip__trip_id", "resource_code")


@admin.register(Conflict)
class ConflictAdmin(admin.ModelAdmin):
    list_display = ("code", "severity", "plan_version", "trip", "is_blocking")
    list_filter = ("code", "severity", "is_blocking")
    search_fields = ("code", "message", "trip__trip_id")


@admin.register(OverrideRequest)
class OverrideRequestAdmin(admin.ModelAdmin):
    list_display = ("reason_code", "plan_version", "trip", "status", "requested_by")
    list_filter = ("reason_code", "status")
    search_fields = ("description", "trip__trip_id")


@admin.register(ApprovalRequest)
class ApprovalRequestAdmin(admin.ModelAdmin):
    list_display = ("request_id", "plan_version", "status", "requested_by")
    list_filter = ("status",)
    search_fields = ("request_id", "plan_version__plan__code")


@admin.register(ApprovalDecision)
class ApprovalDecisionAdmin(admin.ModelAdmin):
    list_display = ("approval_request", "authority_role", "decision", "actor")
    list_filter = ("authority_role", "decision")
    search_fields = ("approval_request__request_id", "comments")


@admin.register(PublishedPlanSnapshot)
class PublishedPlanSnapshotAdmin(admin.ModelAdmin):
    list_display = ("snapshot_id", "plan", "plan_version", "status", "published_by")
    list_filter = ("status",)
    search_fields = ("snapshot_id", "plan__code")


@admin.register(ExportJob)
class ExportJobAdmin(admin.ModelAdmin):
    list_display = (
        "export_id",
        "export_type",
        "export_format",
        "status",
        "record_count",
        "created_by",
        "created_at",
    )
    list_filter = ("export_type", "export_format", "status", "organization")
    search_fields = ("export_id", "file_name", "storage_key")
    readonly_fields = (
        "export_id",
        "storage_bucket",
        "storage_key",
        "checksum_sha256",
        "size_bytes",
        "record_count",
        "payload",
        "created_at",
    )


@admin.register(SimulationScenario)
class SimulationScenarioAdmin(admin.ModelAdmin):
    list_display = ("scenario_id", "name", "baseline_version", "scenario_version", "status")
    list_filter = ("status", "scenario_type")
    search_fields = ("scenario_id", "name")
