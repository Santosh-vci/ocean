from rest_framework import serializers

from apps.organizations.serializers import OrganizationSerializer

from .models import (
    AssetCompatibilityRule,
    Barge,
    CoalGrade,
    CTSAsset,
    Jetty,
    LoadingRateProfile,
    Location,
    Mine,
    Route,
    RouteSegment,
    Stockpile,
    Tug,
)


class MasterSerializer(serializers.ModelSerializer):
    organization = OrganizationSerializer(read_only=True)
    organization_id = serializers.IntegerField(required=False, allow_null=True, write_only=True)

    class Meta:
        fields = (
            "id",
            "code",
            "name",
            "organization",
            "organization_id",
            "is_active",
            "effective_from",
            "effective_to",
            "created_at",
            "updated_at",
        )
        read_only_fields = ("id", "created_at", "updated_at")


class LocationSerializer(MasterSerializer):
    class Meta(MasterSerializer.Meta):
        model = Location
        fields = MasterSerializer.Meta.fields + (
            "location_type",
            "latitude",
            "longitude",
            "geofence_radius_m",
            "parent_area",
            "operational_notes",
        )


class CoalGradeSerializer(MasterSerializer):
    class Meta(MasterSerializer.Meta):
        model = CoalGrade
        fields = MasterSerializer.Meta.fields + (
            "brand_family",
            "typical_cv_kcal",
            "sulfur_pct",
            "ash_pct",
            "sequence_priority",
        )


class MineSerializer(MasterSerializer):
    class Meta(MasterSerializer.Meta):
        model = Mine
        fields = MasterSerializer.Meta.fields + ("region", "default_haul_distance_km")


class StockpileSerializer(MasterSerializer):
    mine_code = serializers.CharField(source="mine.code", read_only=True)
    coal_grade_code = serializers.CharField(source="coal_grade.code", read_only=True)

    class Meta(MasterSerializer.Meta):
        model = Stockpile
        fields = MasterSerializer.Meta.fields + (
            "mine",
            "mine_code",
            "coal_grade",
            "coal_grade_code",
            "available_quantity_mt",
            "reserved_quantity_mt",
        )


class JettySerializer(MasterSerializer):
    class Meta(MasterSerializer.Meta):
        model = Jetty
        fields = MasterSerializer.Meta.fields + (
            "location_name",
            "loading_rate_tph",
            "max_barge_draft_m",
            "status",
        )


class TugSerializer(MasterSerializer):
    class Meta(MasterSerializer.Meta):
        model = Tug
        fields = MasterSerializer.Meta.fields + (
            "horsepower",
            "bollard_pull_tonnes",
            "ais_mmsi",
            "gps_device_id",
            "status",
        )


class BargeSerializer(MasterSerializer):
    class Meta(MasterSerializer.Meta):
        model = Barge
        fields = MasterSerializer.Meta.fields + (
            "capacity_mt",
            "barge_class",
            "max_draft_m",
            "status",
        )


class CTSAssetSerializer(MasterSerializer):
    class Meta(MasterSerializer.Meta):
        model = CTSAsset
        fields = MasterSerializer.Meta.fields + (
            "cts_type",
            "daily_capacity_mt",
            "operating_area",
            "is_available",
        )


class RouteSegmentSerializer(serializers.ModelSerializer):
    class Meta:
        model = RouteSegment
        fields = (
            "id",
            "route",
            "sequence",
            "from_location",
            "to_location",
            "distance_nm",
            "loaded_duration_minutes",
            "empty_duration_minutes",
            "requires_tide_window",
            "requires_bridge_window",
        )


class RouteSerializer(MasterSerializer):
    segments = RouteSegmentSerializer(many=True, read_only=True)

    class Meta(MasterSerializer.Meta):
        model = Route
        fields = MasterSerializer.Meta.fields + (
            "origin",
            "destination",
            "default_loaded_duration_minutes",
            "default_empty_duration_minutes",
            "segments",
        )


class LoadingRateProfileSerializer(MasterSerializer):
    coal_grade_code = serializers.CharField(source="coal_grade.code", read_only=True)

    class Meta(MasterSerializer.Meta):
        model = LoadingRateProfile
        fields = MasterSerializer.Meta.fields + (
            "resource_type",
            "resource_code",
            "coal_grade",
            "coal_grade_code",
            "rate_tph",
        )


class AssetCompatibilityRuleSerializer(MasterSerializer):
    class Meta(MasterSerializer.Meta):
        model = AssetCompatibilityRule
        fields = MasterSerializer.Meta.fields + (
            "rule_type",
            "left_code",
            "right_code",
            "is_compatible",
            "reason",
        )
