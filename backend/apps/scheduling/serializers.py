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

from .models import Assignment, Conflict, Plan, PlanVersion, ScheduleEvent, Trip


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
