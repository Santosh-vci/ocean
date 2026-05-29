from django.contrib import admin

from .models import (
    ApprovalDecision,
    ApprovalRequest,
    Assignment,
    Conflict,
    ExportJob,
    ImpactChainAssessment,
    OverrideRequest,
    OptimizerRun,
    Plan,
    PlanVersion,
    PublishabilityAssessment,
    PublishedPlanSnapshot,
    RecommendationEvaluation,
    RecoveryAction,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    RootCauseRepairAssessment,
    ScheduleEvent,
    ScenarioAssumption,
    ScenarioConstraintEvaluation,
    ScenarioEventProjection,
    ScenarioOgvProjection,
    ScenarioResourceUtilization,
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


@admin.register(RecoveryInputSnapshot)
class RecoveryInputSnapshotAdmin(admin.ModelAdmin):
    list_display = (
        "snapshot_id",
        "plan_version",
        "source_kind",
        "source_ref",
        "active_conflict_count",
        "confirmed_event_count",
    )
    list_filter = ("source_kind", "plan_version")
    search_fields = ("snapshot_id", "source_ref", "plan_version__plan__code")
    readonly_fields = (
        "snapshot_id",
        "input_hash",
        "resource_state",
        "event_state",
        "constraint_state",
        "metadata",
        "generated_at",
    )


@admin.register(OptimizerRun)
class OptimizerRunAdmin(admin.ModelAdmin):
    list_display = ("run_id", "plan_version", "status", "algorithm_version", "started_by")
    list_filter = ("status", "algorithm_version")
    search_fields = ("run_id", "input_snapshot__snapshot_id", "plan_version__plan__code")
    readonly_fields = ("run_id", "summary", "created_at", "updated_at")


@admin.register(RecoveryRecommendation)
class RecoveryRecommendationAdmin(admin.ModelAdmin):
    list_display = ("recommendation_id", "optimizer_run", "rank", "status", "risk_level", "score")
    list_filter = ("status", "risk_level")
    search_fields = ("recommendation_id", "optimizer_run__run_id", "summary")
    readonly_fields = ("recommendation_id", "explanation", "metadata", "created_at", "updated_at")


@admin.register(RecoveryAction)
class RecoveryActionAdmin(admin.ModelAdmin):
    list_display = ("action_id", "recommendation", "sequence", "action_type", "target_trip")
    list_filter = ("action_type",)
    search_fields = ("action_id", "recommendation__recommendation_id", "target_trip__trip_id")
    readonly_fields = ("action_id", "before_state", "after_state", "constraints_checked", "metadata")


@admin.register(RecommendationEvaluation)
class RecommendationEvaluationAdmin(admin.ModelAdmin):
    list_display = (
        "evaluation_id",
        "recommendation",
        "delay_minutes",
        "missed_windows",
        "resource_conflicts",
        "confidence_score",
        "hard_constraints_passed",
    )
    list_filter = ("hard_constraints_passed",)
    search_fields = ("evaluation_id", "recommendation__recommendation_id")
    readonly_fields = ("evaluation_id", "score_breakdown", "metadata", "created_at")


@admin.register(RootCauseRepairAssessment)
class RootCauseRepairAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "assessment_id",
        "recommendation",
        "source_cause_type",
        "status",
        "assessed_at",
    )
    list_filter = ("source_cause_type", "status", "assessed_by_algorithm_version")
    search_fields = (
        "assessment_id",
        "recommendation__recommendation_id",
        "source_ref",
        "source_cause_type",
    )
    readonly_fields = (
        "assessment_id",
        "required_resolution",
        "observed_resolution",
        "residual_risk",
        "evidence",
        "assessed_at",
        "created_at",
        "updated_at",
    )


@admin.register(PublishabilityAssessment)
class PublishabilityAssessmentAdmin(admin.ModelAdmin):
    list_display = (
        "assessment_id",
        "plan_version",
        "status",
        "blocking_reason_count",
        "warning_count",
        "checked_at",
    )
    list_filter = (
        "status",
        "approval_status",
        "conflict_status",
        "telemetry_status",
        "cargo_sequence_status",
        "operating_window_status",
        "recommendation_origin_status",
        "algorithm_version",
    )
    search_fields = ("assessment_id", "plan_version__plan__code")
    readonly_fields = (
        "assessment_id",
        "blocking_reason_count",
        "warning_count",
        "approval_status",
        "conflict_status",
        "telemetry_status",
        "cargo_sequence_status",
        "operating_window_status",
        "recommendation_origin_status",
        "details",
        "checked_at",
        "created_at",
        "updated_at",
    )


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


@admin.register(ScenarioConstraintEvaluation)
class ScenarioConstraintEvaluationAdmin(admin.ModelAdmin):
    list_display = ("evaluation_id", "run", "code", "severity", "affected_object_type")
    list_filter = ("severity", "code", "affected_object_type")
    search_fields = ("evaluation_id", "run__run_id", "trip__trip_id", "affected_object_id")
    readonly_fields = ("evaluation_id", "created_at")


@admin.register(ScenarioOgvProjection)
class ScenarioOgvProjectionAdmin(admin.ModelAdmin):
    list_display = ("run", "voyage", "risk_status", "completion_delta_minutes", "demurrage_delta_usd")
    list_filter = ("risk_status",)
    search_fields = ("run__run_id", "voyage__voyage_id", "voyage__vessel_name")
    readonly_fields = ("created_at",)


@admin.register(ScenarioResourceUtilization)
class ScenarioResourceUtilizationAdmin(admin.ModelAdmin):
    list_display = ("run", "resource_type", "resource_code", "utilization_delta_pct", "waiting_minutes")
    list_filter = ("resource_type",)
    search_fields = ("run__run_id", "resource_code")
    readonly_fields = ("created_at",)
