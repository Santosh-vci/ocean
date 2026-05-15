from rest_framework import serializers

from apps.masters.serializers import (
    BargeSerializer,
    CTSAssetSerializer,
    JettySerializer,
    TugSerializer,
)
from apps.organizations.serializers import OrganizationSerializer
from apps.planning.serializers import (
    CargoLayerStepSerializer,
    CargoRequirementSerializer,
    OGVVoyageSerializer,
)

from .models import (
    ApprovalDecision,
    ApprovalRequest,
    Assignment,
    Conflict,
    OverrideRequest,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
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
            "created_at",
            "updated_at",
        )


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


class OverrideRequestSerializer(serializers.ModelSerializer):
    plan_version_ref = serializers.CharField(source="plan_version", read_only=True)
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)
    vessel_name = serializers.CharField(source="trip.voyage.vessel_name", read_only=True)
    requested_by_email = serializers.EmailField(source="requested_by.email", read_only=True)
    applied_by_email = serializers.EmailField(source="applied_by.email", read_only=True)

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
        )


class PublishedPlanSnapshotSerializer(serializers.ModelSerializer):
    plan_code = serializers.CharField(source="plan.code", read_only=True)
    plan_version_ref = serializers.CharField(source="plan_version", read_only=True)
    published_by_email = serializers.EmailField(source="published_by.email", read_only=True)

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
        )
        read_only_fields = fields


class SimulationScenarioSerializer(serializers.ModelSerializer):
    baseline_version_ref = serializers.CharField(source="baseline_version", read_only=True)
    scenario_version_ref = serializers.CharField(source="scenario_version", read_only=True)
    source_conflict_code = serializers.CharField(source="source_conflict.code", read_only=True)
    source_conflict_message = serializers.CharField(
        source="source_conflict.message",
        read_only=True,
    )
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

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
            "status",
            "recovery_actions",
            "impact_summary",
            "delta_summary",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "scenario_id",
            "scenario_version",
            "scenario_version_ref",
            "status",
            "recovery_actions",
            "impact_summary",
            "delta_summary",
            "created_by",
            "created_by_email",
            "created_at",
            "updated_at",
        )
