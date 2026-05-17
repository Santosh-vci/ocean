from django.contrib import admin

from .models import (
    ApprovalDecision,
    ApprovalRequest,
    Assignment,
    Conflict,
    ExportJob,
    ImpactChainAssessment,
    OverrideRequest,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
    ScheduleEvent,
    ScenarioAssumption,
    ScenarioEventProjection,
    ScenarioRun,
    ScenarioTripProjection,
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


@admin.register(ImpactChainAssessment)
class ImpactChainAssessmentAdmin(admin.ModelAdmin):
    list_display = ("assessment_id", "source_kind", "status", "delay_minutes", "trip")
    list_filter = ("source_kind", "status")
    search_fields = ("assessment_id", "trip__trip_id")
    readonly_fields = ("assessment_id", "nodes", "metadata", "created_at", "updated_at")


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
    list_display = (
        "scenario_id",
        "name",
        "baseline_version",
        "scenario_version",
        "source_kind",
        "status",
    )
    list_filter = ("status", "scenario_type", "source_kind")
    search_fields = ("scenario_id", "name")


@admin.register(ScenarioAssumption)
class ScenarioAssumptionAdmin(admin.ModelAdmin):
    list_display = ("assumption_id", "scenario", "kind", "scope_type", "scope_id", "created_by")
    list_filter = ("kind", "scope_type")
    search_fields = ("assumption_id", "scenario__scenario_id")
    readonly_fields = ("assumption_id", "created_at", "updated_at")


@admin.register(ScenarioRun)
class ScenarioRunAdmin(admin.ModelAdmin):
    list_display = ("run_id", "scenario", "status", "algorithm_version", "created_by")
    list_filter = ("status", "algorithm_version")
    search_fields = ("run_id", "scenario__scenario_id", "input_hash")
    readonly_fields = ("run_id", "input_hash", "created_at", "updated_at")


@admin.register(ScenarioTripProjection)
class ScenarioTripProjectionAdmin(admin.ModelAdmin):
    list_display = ("run", "trip", "projected_start", "projected_end", "delay_minutes")
    list_filter = ("projected_status",)
    search_fields = ("run__run_id", "trip__trip_id")
    readonly_fields = ("created_at",)


@admin.register(ScenarioEventProjection)
class ScenarioEventProjectionAdmin(admin.ModelAdmin):
    list_display = ("run", "trip", "event_type", "projected_at", "delay_minutes")
    list_filter = ("event_type", "projected_status")
    search_fields = ("run__run_id", "trip__trip_id", "event__resource_code")
    readonly_fields = ("created_at",)
