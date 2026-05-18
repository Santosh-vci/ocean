from rest_framework import serializers

from apps.masters.serializers import (
    BargeSerializer,
    CTSAssetSerializer,
    JettySerializer,
    TugSerializer,
)
from apps.operations.models import ConfirmedOperationalEvent
from apps.organizations.serializers import OrganizationSerializer
from apps.planning.serializers import (
    CargoLayerStepSerializer,
    CargoRequirementSerializer,
    OGVVoyageSerializer,
)
from apps.telemetry.models import TrackingAlert

from .models import (
    ApprovalDecision,
    ApprovalRequest,
    Assignment,
    Conflict,
    ExportJob,
    ImpactChainAssessment,
    OptimizerRun,
    OverrideRequest,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
    RecommendationEvaluation,
    RecoveryAction,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    ScenarioAssumption,
    ScenarioConstraintEvaluation,
    ScenarioEventProjection,
    ScenarioOgvProjection,
    ScenarioResourceUtilization,
    ScenarioRun,
    ScenarioTripProjection,
    ScheduleEvent,
    SimulationScenario,
    Trip,
)


class PlanSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = Plan
        fields = (
            "id",
            "code",
            "name",
            "organization",
            "organization_id",
            "horizon_start",
            "horizon_end",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class PlanVersionSerializer(serializers.ModelSerializer):
    plan_code = serializers.CharField(source="plan.code", read_only=True)
    plan_name = serializers.CharField(source="plan.name", read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    scenario_lineage = serializers.SerializerMethodField()
    scenario_diff_summary = serializers.SerializerMethodField()

    class Meta:
        model = PlanVersion
        fields = (
            "id",
            "plan",
            "plan_code",
            "plan_name",
            "version_no",
            "status",
            "validation_status",
            "source_version",
            "generated_at",
            "published_at",
            "created_by",
            "created_by_email",
            "summary",
            "scenario_lineage",
            "scenario_diff_summary",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "version_no",
            "generated_at",
            "published_at",
            "created_by",
            "created_by_email",
            "summary",
            "scenario_lineage",
            "scenario_diff_summary",
            "created_at",
            "updated_at",
        )

    def get_scenario_lineage(self, obj):
        return obj.summary.get("scenarioLineage")

    def get_scenario_diff_summary(self, obj):
        return obj.summary.get("scenarioDiff", {}).get("summary")


class ScheduleEventSerializer(serializers.ModelSerializer):
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)

    class Meta:
        model = ScheduleEvent
        fields = (
            "id",
            "trip",
            "trip_ref",
            "sequence",
            "event_type",
            "planned_at",
            "actual_at",
            "location_label",
            "resource_code",
            "status",
            "metadata",
        )
        read_only_fields = ("id",)


class AssignmentSerializer(serializers.ModelSerializer):
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)
    voyage_ref = serializers.CharField(source="trip.voyage.voyage_id", read_only=True)
    vessel_name = serializers.CharField(source="trip.voyage.vessel_name", read_only=True)
    planned_quantity_mt = serializers.IntegerField(
        source="trip.planned_quantity_mt",
        read_only=True,
    )
    tug = TugSerializer(read_only=True)
    barge = BargeSerializer(read_only=True)
    jetty = JettySerializer(read_only=True)
    cts = CTSAssetSerializer(read_only=True)
    owner_organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = Assignment
        fields = (
            "id",
            "trip",
            "trip_ref",
            "voyage_ref",
            "vessel_name",
            "planned_quantity_mt",
            "tug",
            "barge",
            "jetty",
            "cts",
            "route_segment",
            "owner_organization",
            "planned_departure",
            "planned_arrival",
            "tug_status",
            "barge_status",
            "next_constraint",
            "next_action",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class TripSerializer(serializers.ModelSerializer):
    plan_version_ref = serializers.CharField(source="plan_version", read_only=True)
    voyage = OGVVoyageSerializer(read_only=True)
    cargo_requirement = CargoRequirementSerializer(read_only=True)
    cargo_layer_step = CargoLayerStepSerializer(read_only=True)
    origin_jetty = JettySerializer(read_only=True)
    assignment = AssignmentSerializer(read_only=True)
    events = ScheduleEventSerializer(many=True, read_only=True)

    class Meta:
        model = Trip
        fields = (
            "id",
            "plan_version",
            "plan_version_ref",
            "trip_id",
            "sequence",
            "voyage",
            "cargo_requirement",
            "cargo_layer_step",
            "origin_jetty",
            "destination_location",
            "planned_start",
            "planned_end",
            "planned_quantity_mt",
            "loaded_quantity_mt",
            "status",
            "selection_reason",
            "assignment",
            "events",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ConflictSerializer(serializers.ModelSerializer):
    plan_version_ref = serializers.CharField(source="plan_version", read_only=True)
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)
    vessel_name = serializers.CharField(source="trip.voyage.vessel_name", read_only=True)

    class Meta:
        model = Conflict
        fields = (
            "id",
            "plan_version",
            "plan_version_ref",
            "trip",
            "trip_ref",
            "vessel_name",
            "code",
            "severity",
            "object_type",
            "object_id",
            "message",
            "is_blocking",
            "resolved_at",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class ImpactChainAssessmentSerializer(serializers.ModelSerializer):
    plan_version_ref = serializers.CharField(source="plan_version", read_only=True)
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)
    assignment_ref = serializers.CharField(source="assignment", read_only=True)
    override_request_ref = serializers.CharField(source="override_request", read_only=True)

    class Meta:
        model = ImpactChainAssessment
        fields = (
            "id",
            "assessment_id",
            "plan_version",
            "plan_version_ref",
            "trip",
            "trip_ref",
            "assignment",
            "assignment_ref",
            "override_request",
            "override_request_ref",
            "source_kind",
            "status",
            "delay_minutes",
            "nodes",
            "metadata",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class RecoveryInputSnapshotBuildSerializer(serializers.Serializer):
    plan_version = serializers.PrimaryKeyRelatedField(
        queryset=PlanVersion.objects.all(),
        required=False,
        allow_null=True,
    )
    source_kind = serializers.ChoiceField(
        choices=RecoveryInputSnapshot.SourceKind.choices,
        required=False,
    )
    source_ref = serializers.CharField(required=False, allow_blank=True)
    source_conflict = serializers.PrimaryKeyRelatedField(
        queryset=Conflict.objects.all(),
        required=False,
        allow_null=True,
    )
    source_override = serializers.PrimaryKeyRelatedField(
        queryset=OverrideRequest.objects.all(),
        required=False,
        allow_null=True,
    )
    source_tracking_alert = serializers.PrimaryKeyRelatedField(
        queryset=TrackingAlert.objects.all(),
        required=False,
        allow_null=True,
    )
    source_operational_event = serializers.PrimaryKeyRelatedField(
        queryset=ConfirmedOperationalEvent.objects.all(),
        required=False,
        allow_null=True,
    )
    source_scenario = serializers.PrimaryKeyRelatedField(
        queryset=SimulationScenario.objects.all(),
        required=False,
        allow_null=True,
    )
    metadata = serializers.JSONField(required=False, default=dict)


class RecoveryInputSnapshotSerializer(serializers.ModelSerializer):
    plan_version_ref = serializers.CharField(source="plan_version", read_only=True)
    source_conflict_code = serializers.CharField(source="source_conflict.code", read_only=True)
    source_override_reason_code = serializers.CharField(
        source="source_override.reason_code",
        read_only=True,
    )
    source_tracking_alert_ref = serializers.CharField(
        source="source_tracking_alert.alert_id",
        read_only=True,
    )
    source_operational_event_ref = serializers.CharField(
        source="source_operational_event.event_id",
        read_only=True,
    )
    source_scenario_ref = serializers.CharField(
        source="source_scenario.scenario_id",
        read_only=True,
    )
    captured_by_email = serializers.EmailField(source="captured_by.email", read_only=True)

    class Meta:
        model = RecoveryInputSnapshot
        fields = (
            "id",
            "snapshot_id",
            "plan_version",
            "plan_version_ref",
            "source_kind",
            "source_ref",
            "source_conflict",
            "source_conflict_code",
            "source_override",
            "source_override_reason_code",
            "source_tracking_alert",
            "source_tracking_alert_ref",
            "source_operational_event",
            "source_operational_event_ref",
            "source_scenario",
            "source_scenario_ref",
            "input_hash",
            "active_conflict_count",
            "confirmed_event_count",
            "tracking_alert_count",
            "resource_state",
            "event_state",
            "constraint_state",
            "metadata",
            "captured_by",
            "captured_by_email",
            "generated_at",
        )
        read_only_fields = fields


class RecoveryActionSerializer(serializers.ModelSerializer):
    recommendation_ref = serializers.CharField(
        source="recommendation.recommendation_id",
        read_only=True,
    )
    target_trip_ref = serializers.CharField(source="target_trip.trip_id", read_only=True)
    target_assignment_ref = serializers.CharField(source="target_assignment", read_only=True)

    class Meta:
        model = RecoveryAction
        fields = (
            "id",
            "action_id",
            "recommendation",
            "recommendation_ref",
            "sequence",
            "action_type",
            "target_trip",
            "target_trip_ref",
            "target_assignment",
            "target_assignment_ref",
            "before_state",
            "after_state",
            "constraints_checked",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class RecommendationEvaluationSerializer(serializers.ModelSerializer):
    recommendation_ref = serializers.CharField(
        source="recommendation.recommendation_id",
        read_only=True,
    )

    class Meta:
        model = RecommendationEvaluation
        fields = (
            "id",
            "evaluation_id",
            "recommendation",
            "recommendation_ref",
            "delay_minutes",
            "missed_windows",
            "resource_conflicts",
            "utilization_delta_pct",
            "confidence_score",
            "hard_constraints_passed",
            "score_breakdown",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class RecoveryRecommendationSerializer(serializers.ModelSerializer):
    optimizer_run_ref = serializers.CharField(source="optimizer_run.run_id", read_only=True)
    scenario_ref = serializers.CharField(source="scenario.scenario_id", read_only=True)
    actions = RecoveryActionSerializer(many=True, read_only=True)
    evaluation = RecommendationEvaluationSerializer(read_only=True)

    class Meta:
        model = RecoveryRecommendation
        fields = (
            "id",
            "recommendation_id",
            "optimizer_run",
            "optimizer_run_ref",
            "rank",
            "status",
            "risk_level",
            "score",
            "summary",
            "explanation",
            "scenario",
            "scenario_ref",
            "metadata",
            "actions",
            "evaluation",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class RecoveryRecommendationMaterializeSerializer(serializers.Serializer):
    name = serializers.CharField(required=False, allow_blank=True, max_length=160)
    run_simulation = serializers.BooleanField(required=False, default=True)


class OptimizerRunGenerateSerializer(serializers.Serializer):
    input_snapshot = serializers.PrimaryKeyRelatedField(
        queryset=RecoveryInputSnapshot.objects.all(),
    )
    objective_weights = serializers.JSONField(required=False, default=dict)
    max_candidates = serializers.IntegerField(required=False, min_value=1, max_value=10, default=5)


class OptimizerRunSerializer(serializers.ModelSerializer):
    input_snapshot_ref = serializers.CharField(source="input_snapshot.snapshot_id", read_only=True)
    plan_version_ref = serializers.CharField(source="plan_version", read_only=True)
    started_by_email = serializers.EmailField(source="started_by.email", read_only=True)
    recommendations = RecoveryRecommendationSerializer(many=True, read_only=True)

    class Meta:
        model = OptimizerRun
        fields = (
            "id",
            "run_id",
            "input_snapshot",
            "input_snapshot_ref",
            "plan_version",
            "plan_version_ref",
            "status",
            "algorithm_version",
            "objective_weights",
            "summary",
            "error_message",
            "started_by",
            "started_by_email",
            "started_at",
            "completed_at",
            "recommendations",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields


class OverrideRequestSerializer(serializers.ModelSerializer):
    plan_version_ref = serializers.CharField(source="plan_version", read_only=True)
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)
    vessel_name = serializers.CharField(source="trip.voyage.vessel_name", read_only=True)
    requested_by_email = serializers.EmailField(source="requested_by.email", read_only=True)
    applied_by_email = serializers.EmailField(source="applied_by.email", read_only=True)
    impact_assessment = ImpactChainAssessmentSerializer(read_only=True)

    class Meta:
        model = OverrideRequest
        fields = (
            "id",
            "plan_version",
            "plan_version_ref",
            "trip",
            "trip_ref",
            "vessel_name",
            "assignment",
            "reason_code",
            "description",
            "requested_change",
            "before_state",
            "after_state",
            "status",
            "requested_by",
            "requested_by_email",
            "applied_by",
            "applied_by_email",
            "applied_at",
            "impact_assessment",
            "created_at",
        )
        read_only_fields = (
            "id",
            "before_state",
            "after_state",
            "requested_by",
            "requested_by_email",
            "applied_by",
            "applied_by_email",
            "applied_at",
            "created_at",
        )


class ApprovalDecisionSerializer(serializers.ModelSerializer):
    actor_email = serializers.EmailField(source="actor.email", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)

    class Meta:
        model = ApprovalDecision
        fields = (
            "id",
            "approval_request",
            "authority_role",
            "decision",
            "comments",
            "actor",
            "actor_email",
            "organization",
            "organization_name",
            "created_at",
        )
        read_only_fields = (
            "id",
            "actor",
            "actor_email",
            "organization",
            "organization_name",
            "created_at",
        )


class ApprovalRequestSerializer(serializers.ModelSerializer):
    plan_version_ref = serializers.CharField(source="plan_version", read_only=True)
    requested_by_email = serializers.EmailField(source="requested_by.email", read_only=True)
    decisions = ApprovalDecisionSerializer(many=True, read_only=True)
    scenario_lineage = serializers.SerializerMethodField()
    scenario_diff_summary = serializers.SerializerMethodField()

    class Meta:
        model = ApprovalRequest
        fields = (
            "id",
            "request_id",
            "plan_version",
            "plan_version_ref",
            "status",
            "required_authorities",
            "reason",
            "requested_by",
            "requested_by_email",
            "decided_at",
            "created_at",
            "updated_at",
            "decisions",
            "scenario_lineage",
            "scenario_diff_summary",
        )
        read_only_fields = (
            "id",
            "request_id",
            "status",
            "required_authorities",
            "requested_by",
            "requested_by_email",
            "decided_at",
            "created_at",
            "updated_at",
            "decisions",
            "scenario_lineage",
            "scenario_diff_summary",
        )

    def get_scenario_lineage(self, obj):
        return obj.plan_version.summary.get("scenarioLineage")

    def get_scenario_diff_summary(self, obj):
        return obj.plan_version.summary.get("scenarioDiff", {}).get("summary")


class PublishedPlanSnapshotSerializer(serializers.ModelSerializer):
    plan_code = serializers.CharField(source="plan.code", read_only=True)
    plan_version_ref = serializers.CharField(source="plan_version", read_only=True)
    published_by_email = serializers.EmailField(source="published_by.email", read_only=True)
    scenario_lineage = serializers.SerializerMethodField()
    scenario_diff_summary = serializers.SerializerMethodField()

    class Meta:
        model = PublishedPlanSnapshot
        fields = (
            "id",
            "snapshot_id",
            "plan",
            "plan_code",
            "plan_version",
            "plan_version_ref",
            "approval_request",
            "status",
            "payload",
            "published_by",
            "published_by_email",
            "published_at",
            "scenario_lineage",
            "scenario_diff_summary",
        )
        read_only_fields = fields

    def get_scenario_lineage(self, obj):
        return obj.plan_version.summary.get("scenarioLineage")

    def get_scenario_diff_summary(self, obj):
        return obj.plan_version.summary.get("scenarioDiff", {}).get("summary")


class ExportJobSerializer(serializers.ModelSerializer):
    plan_version_ref = serializers.CharField(source="plan_version", read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    organization_name = serializers.CharField(source="organization.name", read_only=True)
    download_url = serializers.SerializerMethodField()
    storage_uri = serializers.SerializerMethodField()

    class Meta:
        model = ExportJob
        fields = (
            "id",
            "export_id",
            "export_type",
            "export_format",
            "status",
            "plan_version",
            "plan_version_ref",
            "organization",
            "organization_name",
            "storage_bucket",
            "storage_key",
            "storage_uri",
            "file_name",
            "content_type",
            "checksum_sha256",
            "size_bytes",
            "record_count",
            "scope",
            "payload",
            "failure_reason",
            "created_by",
            "created_by_email",
            "created_at",
            "download_url",
        )
        read_only_fields = fields

    def get_download_url(self, obj) -> str:
        return f"/api/exports/{obj.pk}/download/"

    def get_storage_uri(self, obj) -> str:
        return f"object://{obj.storage_bucket}/{obj.storage_key}"


class ScenarioAssumptionSerializer(serializers.ModelSerializer):
    scenario_ref = serializers.CharField(source="scenario.scenario_id", read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = ScenarioAssumption
        fields = (
            "id",
            "scenario",
            "scenario_ref",
            "assumption_id",
            "kind",
            "scope_type",
            "scope_id",
            "payload",
            "effective_from",
            "effective_to",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "scenario",
            "scenario_ref",
            "assumption_id",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        )


class ScenarioTripProjectionSerializer(serializers.ModelSerializer):
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)

    class Meta:
        model = ScenarioTripProjection
        fields = (
            "id",
            "run",
            "trip",
            "trip_ref",
            "baseline_start",
            "baseline_end",
            "projected_start",
            "projected_end",
            "projected_status",
            "delay_minutes",
            "assignment_delta",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class ScenarioEventProjectionSerializer(serializers.ModelSerializer):
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)
    event_ref = serializers.CharField(source="event", read_only=True)

    class Meta:
        model = ScenarioEventProjection
        fields = (
            "id",
            "run",
            "event",
            "event_ref",
            "trip",
            "trip_ref",
            "event_type",
            "baseline_at",
            "projected_at",
            "projected_status",
            "delay_minutes",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class ScenarioConstraintEvaluationSerializer(serializers.ModelSerializer):
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)

    class Meta:
        model = ScenarioConstraintEvaluation
        fields = (
            "id",
            "run",
            "evaluation_id",
            "trip",
            "trip_ref",
            "code",
            "severity",
            "affected_object_type",
            "affected_object_id",
            "baseline_value",
            "projected_value",
            "margin_minutes",
            "source_assumption_ids",
            "message",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class ScenarioOgvProjectionSerializer(serializers.ModelSerializer):
    voyage_ref = serializers.CharField(source="voyage.voyage_id", read_only=True)
    vessel_name = serializers.CharField(source="voyage.vessel_name", read_only=True)

    class Meta:
        model = ScenarioOgvProjection
        fields = (
            "id",
            "run",
            "voyage",
            "voyage_ref",
            "vessel_name",
            "baseline_completion_at",
            "projected_completion_at",
            "completion_delta_minutes",
            "laycan_end",
            "baseline_demurrage_minutes",
            "projected_demurrage_minutes",
            "demurrage_delta_usd",
            "risk_status",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class ScenarioResourceUtilizationSerializer(serializers.ModelSerializer):
    class Meta:
        model = ScenarioResourceUtilization
        fields = (
            "id",
            "run",
            "resource_type",
            "resource_code",
            "baseline_occupied_minutes",
            "projected_occupied_minutes",
            "baseline_idle_minutes",
            "projected_idle_minutes",
            "waiting_minutes",
            "utilization_delta_pct",
            "metadata",
            "created_at",
        )
        read_only_fields = fields


class ScenarioRunSerializer(serializers.ModelSerializer):
    scenario_ref = serializers.CharField(source="scenario.scenario_id", read_only=True)
    baseline_version_ref = serializers.CharField(source="baseline_version", read_only=True)
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    trip_projections = ScenarioTripProjectionSerializer(many=True, read_only=True)
    constraint_evaluations = ScenarioConstraintEvaluationSerializer(many=True, read_only=True)
    ogv_projections = ScenarioOgvProjectionSerializer(many=True, read_only=True)
    resource_utilizations = ScenarioResourceUtilizationSerializer(many=True, read_only=True)
    impact_assessments = serializers.SerializerMethodField()

    class Meta:
        model = ScenarioRun
        fields = (
            "id",
            "scenario",
            "scenario_ref",
            "run_id",
            "baseline_version",
            "baseline_version_ref",
            "status",
            "algorithm_version",
            "input_hash",
            "started_at",
            "completed_at",
            "summary",
            "created_by",
            "created_by_email",
            "trip_projections",
            "constraint_evaluations",
            "ogv_projections",
            "resource_utilizations",
            "impact_assessments",
            "created_at",
            "updated_at",
        )
        read_only_fields = fields

    def get_impact_assessments(self, obj):
        assessments = ImpactChainAssessment.objects.filter(
            assessment_id__startswith=f"ICA-{obj.run_id}-",
            source_kind=ImpactChainAssessment.SourceKind.SIMULATION,
        ).select_related("plan_version", "trip", "assignment", "override_request")
        return ImpactChainAssessmentSerializer(assessments, many=True).data


class SimulationScenarioSerializer(serializers.ModelSerializer):
    baseline_version_ref = serializers.CharField(source="baseline_version", read_only=True)
    scenario_version_ref = serializers.CharField(source="scenario_version", read_only=True)
    source_conflict_code = serializers.CharField(source="source_conflict.code", read_only=True)
    source_conflict_message = serializers.CharField(
        source="source_conflict.message",
        read_only=True,
    )
    source_override_reason_code = serializers.CharField(
        source="source_override.reason_code",
        read_only=True,
    )
    source_override_description = serializers.CharField(
        source="source_override.description",
        read_only=True,
    )
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)
    assumptions = ScenarioAssumptionSerializer(many=True, read_only=True)
    runs = ScenarioRunSerializer(many=True, read_only=True)

    class Meta:
        model = SimulationScenario
        fields = (
            "id",
            "scenario_id",
            "name",
            "scenario_type",
            "baseline_version",
            "baseline_version_ref",
            "scenario_version",
            "scenario_version_ref",
            "source_conflict",
            "source_conflict_code",
            "source_conflict_message",
            "source_override",
            "source_override_reason_code",
            "source_override_description",
            "source_kind",
            "status",
            "recovery_actions",
            "impact_summary",
            "delta_summary",
            "metadata",
            "created_by",
            "created_by_email",
            "assumptions",
            "runs",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "scenario_id",
            "scenario_version",
            "scenario_version_ref",
            "source_override",
            "source_override_reason_code",
            "source_override_description",
            "source_kind",
            "status",
            "recovery_actions",
            "impact_summary",
            "delta_summary",
            "metadata",
            "created_by",
            "created_by_email",
            "assumptions",
            "runs",
            "created_at",
            "updated_at",
        )
