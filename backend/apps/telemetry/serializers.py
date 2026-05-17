from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from .models import AssetIdentity, LatestAssetState, PositionPing, TelemetrySource


class TelemetrySourceSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetrySource
        fields = [
            "id",
            "source_id",
            "name",
            "source_type",
            "status",
            "freshness_threshold_seconds",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class AssetIdentitySerializer(serializers.ModelSerializer):
    source_id = serializers.CharField(source="source.source_id", read_only=True)

    class Meta:
        model = AssetIdentity
        fields = [
            "id",
            "source",
            "source_id",
            "asset_type",
            "asset_object_id",
            "asset_code",
            "external_id",
            "external_id_type",
            "is_primary",
            "valid_from",
            "valid_to",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "source_id", "created_at", "updated_at"]


class PositionPingSerializer(serializers.ModelSerializer):
    source_id = serializers.CharField(source="source.source_id", read_only=True)
    external_id = serializers.CharField(source="asset_identity.external_id", read_only=True)

    class Meta:
        model = PositionPing
        fields = [
            "id",
            "ping_id",
            "source",
            "source_id",
            "asset_identity",
            "external_id",
            "asset_type",
            "asset_code",
            "latitude",
            "longitude",
            "speed_knots",
            "course_degrees",
            "heading_degrees",
            "device_timestamp",
            "received_timestamp",
            "signal_quality",
            "accuracy_m",
            "battery_level",
            "raw_payload",
            "raw_payload_ref",
            "is_synthetic",
            "created_at",
        ]
        read_only_fields = fields


class LatestAssetStateSerializer(serializers.ModelSerializer):
    source_id = serializers.CharField(source="source.source_id", read_only=True)
    source_type = serializers.CharField(source="source.source_type", read_only=True)
    external_id = serializers.CharField(source="asset_identity.external_id", read_only=True)
    external_id_type = serializers.CharField(
        source="asset_identity.external_id_type",
        read_only=True,
    )
    last_ping_ref = serializers.CharField(source="last_ping.ping_id", read_only=True)
    age_seconds = serializers.SerializerMethodField()

    class Meta:
        model = LatestAssetState
        fields = [
            "id",
            "asset_type",
            "asset_code",
            "source",
            "source_id",
            "source_type",
            "asset_identity",
            "external_id",
            "external_id_type",
            "last_ping",
            "last_ping_ref",
            "derived_status",
            "latitude",
            "longitude",
            "speed_knots",
            "heading_degrees",
            "last_seen_at",
            "age_seconds",
            "freshness_status",
            "confidence_score",
            "paired_asset_code",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields

    def get_age_seconds(self, obj) -> int | None:
        if obj.last_seen_at is None:
            return None
        return max(0, int((timezone.now() - obj.last_seen_at).total_seconds()))


class PositionPingIngestSerializer(serializers.Serializer):
    source_id = serializers.CharField(max_length=80)
    source_type = serializers.ChoiceField(choices=TelemetrySource.SourceType.choices)
    source_name = serializers.CharField(max_length=160, required=False, allow_blank=True)
    external_id = serializers.CharField(max_length=120)
    external_id_type = serializers.ChoiceField(
        choices=AssetIdentity.ExternalIdType.choices,
        required=False,
        default=AssetIdentity.ExternalIdType.SYNTHETIC_ID,
    )
    asset_type = serializers.ChoiceField(choices=AssetIdentity.AssetType.choices)
    asset_object_id = serializers.IntegerField(required=False, allow_null=True, min_value=1)
    asset_code = serializers.CharField(max_length=80)
    latitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        min_value=Decimal("-90"),
        max_value=Decimal("90"),
    )
    longitude = serializers.DecimalField(
        max_digits=10,
        decimal_places=7,
        min_value=Decimal("-180"),
        max_value=Decimal("180"),
    )
    speed_knots = serializers.DecimalField(
        max_digits=7,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal("0"),
    )
    course_degrees = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal("0"),
        max_value=Decimal("359.99"),
    )
    heading_degrees = serializers.DecimalField(
        max_digits=6,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal("0"),
        max_value=Decimal("359.99"),
    )
    device_timestamp = serializers.DateTimeField()
    signal_quality = serializers.ChoiceField(
        choices=PositionPing.SignalQuality.choices,
        required=False,
        default=PositionPing.SignalQuality.GOOD,
    )
    accuracy_m = serializers.DecimalField(
        max_digits=8,
        decimal_places=2,
        required=False,
        allow_null=True,
        min_value=Decimal("0"),
    )
    battery_level = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
        max_value=100,
    )
    raw_payload = serializers.JSONField(required=False, default=dict)
    raw_payload_ref = serializers.CharField(max_length=255, required=False, allow_blank=True)


class PositionPingIngestResponseSerializer(serializers.Serializer):
    ping = PositionPingSerializer()
    latest_state_updated = serializers.BooleanField()
    geofence_events = serializers.ListField()
    alerts = serializers.ListField()
