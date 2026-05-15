from rest_framework import serializers

from apps.masters.serializers import (
    BargeSerializer,
    CoalGradeSerializer,
    CTSAssetSerializer,
    JettySerializer,
    LocationSerializer,
    RouteSegmentSerializer,
)
from apps.organizations.serializers import OrganizationSerializer

from .models import (
    AssetAvailabilityWindow,
    BridgeWindow,
    CargoLayerStep,
    CargoRequirement,
    ImportJob,
    JettyAvailabilityWindow,
    NavigationConstraintCheck,
    OGVVoyage,
    TideWindow,
)


class OGVVoyageSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    anchorage_location = LocationSerializer(read_only=True)
    anchorage_location_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        write_only=True,
    )
    remaining_mt = serializers.IntegerField(read_only=True)

    class Meta:
        model = OGVVoyage
        fields = (
            "id",
            "voyage_id",
            "vessel_name",
            "customer_name",
            "vessel_class",
            "eta",
            "etb",
            "etc_target",
            "laycan_start",
            "laycan_end",
            "required_mt",
            "loaded_mt",
            "in_transit_mt",
            "discharged_mt",
            "remaining_mt",
            "priority",
            "demurrage_rate_usd_per_day",
            "anchorage_location",
            "anchorage_location_id",
            "organization",
            "organization_id",
            "status",
            "risk_status",
            "current_stage",
            "next_blocking_constraint",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "remaining_mt")


class CargoRequirementSerializer(serializers.ModelSerializer):
    voyage_ref = serializers.CharField(source="voyage.voyage_id", read_only=True)
    vessel_name = serializers.CharField(source="voyage.vessel_name", read_only=True)
    coal_grade = CoalGradeSerializer(read_only=True)
    coal_grade_id = serializers.IntegerField(write_only=True)
    source_location = LocationSerializer(read_only=True)
    source_location_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    preferred_jetty = JettySerializer(read_only=True)
    preferred_jetty_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    remaining_mt = serializers.IntegerField(read_only=True)

    class Meta:
        model = CargoRequirement
        fields = (
            "id",
            "voyage",
            "voyage_ref",
            "vessel_name",
            "coal_grade",
            "coal_grade_id",
            "source_location",
            "source_location_id",
            "preferred_jetty",
            "preferred_jetty_id",
            "required_mt",
            "loaded_mt",
            "in_transit_mt",
            "discharged_mt",
            "remaining_mt",
            "status",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at", "remaining_mt")


class CargoLayerStepSerializer(serializers.ModelSerializer):
    voyage_ref = serializers.CharField(source="voyage.voyage_id", read_only=True)
    vessel_name = serializers.CharField(source="voyage.vessel_name", read_only=True)
    coal_grade = CoalGradeSerializer(read_only=True)
    coal_grade_id = serializers.IntegerField(write_only=True)
    planned_barge = BargeSerializer(read_only=True)
    planned_barge_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    planned_jetty = JettySerializer(read_only=True)
    planned_jetty_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)
    planned_cts = CTSAssetSerializer(read_only=True)
    planned_cts_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = CargoLayerStep
        fields = (
            "id",
            "voyage",
            "voyage_ref",
            "vessel_name",
            "cargo_requirement",
            "hatch_no",
            "layer_no",
            "required_sequence_no",
            "coal_grade",
            "coal_grade_id",
            "required_mt",
            "remaining_mt",
            "planned_barge",
            "planned_barge_id",
            "planned_jetty",
            "planned_jetty_id",
            "planned_cts",
            "planned_cts_id",
            "status",
            "blocking_reason",
            "chain_status",
            "sequence_violation",
            "planned_start",
            "planned_end",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class AssetAvailabilityWindowSerializer(serializers.ModelSerializer):
    class Meta:
        model = AssetAvailabilityWindow
        fields = "__all__"
        read_only_fields = ("id", "created_at", "updated_at")


class JettyAvailabilityWindowSerializer(serializers.ModelSerializer):
    jetty = JettySerializer(read_only=True)
    jetty_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = JettyAvailabilityWindow
        fields = (
            "id",
            "jetty",
            "jetty_id",
            "window_start",
            "window_end",
            "status",
            "loading_rate_override_tph",
            "reason",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class TideWindowSerializer(serializers.ModelSerializer):
    location = LocationSerializer(read_only=True)
    location_id = serializers.IntegerField(write_only=True)
    applicable_route_segment = RouteSegmentSerializer(read_only=True)
    applicable_route_segment_id = serializers.IntegerField(
        required=False,
        allow_null=True,
        write_only=True,
    )

    class Meta:
        model = TideWindow
        fields = (
            "id",
            "code",
            "location",
            "location_id",
            "window_start",
            "window_end",
            "min_water_level_m",
            "max_loaded_draft_m",
            "applicable_route_segment",
            "applicable_route_segment_id",
            "risk_level",
            "source",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class BridgeWindowSerializer(serializers.ModelSerializer):
    location = LocationSerializer(read_only=True)
    location_id = serializers.IntegerField(write_only=True)

    class Meta:
        model = BridgeWindow
        fields = (
            "id",
            "code",
            "location",
            "location_id",
            "window_start",
            "window_end",
            "clearance_m",
            "allowed_asset_class",
            "status",
            "notes",
            "is_active",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class NavigationConstraintCheckSerializer(serializers.ModelSerializer):
    voyage_ref = serializers.CharField(source="voyage.voyage_id", read_only=True)
    vessel_name = serializers.CharField(source="voyage.vessel_name", read_only=True)
    route_segment = RouteSegmentSerializer(read_only=True)
    route_segment_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        model = NavigationConstraintCheck
        fields = (
            "id",
            "voyage",
            "voyage_ref",
            "vessel_name",
            "asset_code",
            "route_segment",
            "route_segment_id",
            "constraint_type",
            "eta_gate",
            "window_start",
            "window_end",
            "draft_m",
            "margin_minutes",
            "status",
            "recovery_hint",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class ImportJobSerializer(serializers.ModelSerializer):
    created_by_email = serializers.EmailField(source="created_by.email", read_only=True)

    class Meta:
        model = ImportJob
        fields = (
            "id",
            "import_type",
            "filename",
            "source",
            "status",
            "total_rows",
            "valid_rows",
            "error_rows",
            "errors",
            "created_by",
            "created_by_email",
            "created_at",
        )
        read_only_fields = ("id", "created_by", "created_by_email", "created_at")
