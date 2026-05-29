from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers

from apps.scheduling.models import PlanVersion

from .models import (
    AssetIdentity,
    GeofenceZone,
    LatestAssetState,
    LiveEtaProjection,
    MovementEvent,
    PositionPing,
    TelemetrySource,
    TelemetryReplayRun,
    TelemetryTrustAssessment,
    TelemetryTrustProfile,
    TrackingAlert,
)


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
    current_geofence_ref = serializers.CharField(source="current_geofence.zone_id", read_only=True)
    current_geofence_name = serializers.CharField(source="current_geofence.name", read_only=True)
    current_geofence_type = serializers.CharField(
        source="current_geofence.zone_type",
        read_only=True,
    )
    last_movement_event_ref = serializers.CharField(
        source="last_movement_event.event_id",
        read_only=True,
    )
    last_movement_event_type = serializers.CharField(
        source="last_movement_event.event_type",
        read_only=True,
    )
    last_movement_event_at = serializers.DateTimeField(
        source="last_movement_event.event_at",
        read_only=True,
    )
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
            "current_geofence",
            "current_geofence_ref",
            "current_geofence_name",
            "current_geofence_type",
            "last_movement_event",
            "last_movement_event_ref",
            "last_movement_event_type",
            "last_movement_event_at",
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


class GeofenceZoneSerializer(serializers.ModelSerializer):
    source_location_code = serializers.CharField(source="source_location.code", read_only=True)
    source_location_name = serializers.CharField(source="source_location.name", read_only=True)

    class Meta:
        model = GeofenceZone
        fields = [
            "id",
            "zone_id",
            "name",
            "zone_type",
            "source_location",
            "source_location_code",
            "source_location_name",
            "latitude",
            "longitude",
            "radius_m",
            "status",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class MovementEventSerializer(serializers.ModelSerializer):
    source_id = serializers.CharField(source="source.source_id", read_only=True)
    external_id = serializers.CharField(source="asset_identity.external_id", read_only=True)
    geofence_ref = serializers.CharField(source="geofence.zone_id", read_only=True)
    geofence_name = serializers.CharField(source="geofence.name", read_only=True)
    geofence_type = serializers.CharField(source="geofence.zone_type", read_only=True)
    position_ping_ref = serializers.CharField(source="position_ping.ping_id", read_only=True)
    age_seconds = serializers.SerializerMethodField()

    class Meta:
        model = MovementEvent
        fields = [
            "id",
            "event_id",
            "event_type",
            "asset_type",
            "asset_code",
            "source",
            "source_id",
            "asset_identity",
            "external_id",
            "position_ping",
            "position_ping_ref",
            "geofence",
            "geofence_ref",
            "geofence_name",
            "geofence_type",
            "event_at",
            "age_seconds",
            "latitude",
            "longitude",
            "speed_knots",
            "confidence_score",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields

    def get_age_seconds(self, obj) -> int:
        return max(0, int((timezone.now() - obj.event_at).total_seconds()))


class LiveEtaProjectionSerializer(serializers.ModelSerializer):
    source_id = serializers.CharField(source="source.source_id", read_only=True)
    external_id = serializers.CharField(source="asset_identity.external_id", read_only=True)
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)
    vessel_name = serializers.CharField(source="trip.voyage.vessel_name", read_only=True)
    schedule_event_type = serializers.CharField(
        source="schedule_event.event_type",
        read_only=True,
    )
    schedule_event_label = serializers.CharField(
        source="schedule_event.location_label",
        read_only=True,
    )
    source_ping_ref = serializers.CharField(source="source_ping.ping_id", read_only=True)
    current_geofence_ref = serializers.CharField(
        source="current_geofence.zone_id",
        read_only=True,
    )
    current_geofence_name = serializers.CharField(
        source="current_geofence.name",
        read_only=True,
    )

    class Meta:
        model = LiveEtaProjection
        fields = [
            "id",
            "projection_id",
            "asset_type",
            "asset_code",
            "source",
            "source_id",
            "asset_identity",
            "external_id",
            "trip",
            "trip_ref",
            "vessel_name",
            "schedule_event",
            "schedule_event_type",
            "schedule_event_label",
            "planned_at",
            "observed_eta",
            "variance_minutes",
            "calculation_method",
            "confidence_score",
            "source_ping",
            "source_ping_ref",
            "current_geofence",
            "current_geofence_ref",
            "current_geofence_name",
            "status",
            "metadata",
            "calculated_at",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TrackingAlertSerializer(serializers.ModelSerializer):
    source_id = serializers.CharField(source="source.source_id", read_only=True)
    external_id = serializers.CharField(source="asset_identity.external_id", read_only=True)
    source_ping_ref = serializers.CharField(source="source_ping.ping_id", read_only=True)
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)
    vessel_name = serializers.CharField(source="trip.voyage.vessel_name", read_only=True)
    schedule_event_type = serializers.CharField(
        source="schedule_event.event_type",
        read_only=True,
    )
    schedule_event_planned_at = serializers.DateTimeField(
        source="schedule_event.planned_at",
        read_only=True,
    )
    eta_projection_ref = serializers.CharField(
        source="eta_projection.projection_id",
        read_only=True,
    )

    class Meta:
        model = TrackingAlert
        fields = [
            "id",
            "alert_id",
            "alert_type",
            "severity",
            "asset_type",
            "asset_code",
            "source",
            "source_id",
            "asset_identity",
            "external_id",
            "source_ping",
            "source_ping_ref",
            "trip",
            "trip_ref",
            "vessel_name",
            "schedule_event",
            "schedule_event_type",
            "schedule_event_planned_at",
            "eta_projection",
            "eta_projection_ref",
            "message",
            "evidence",
            "status",
            "source_kind",
            "opened_at",
            "resolved_at",
            "created_scenario",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TelemetryTrustProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetryTrustProfile
        fields = [
            "id",
            "profile_key",
            "name",
            "version",
            "status",
            "source_hierarchy",
            "freshness_thresholds",
            "confidence_thresholds",
            "identity_rules",
            "quarantine_rules",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class TelemetryTrustAssessmentSerializer(serializers.ModelSerializer):
    profile_ref = serializers.CharField(source="profile.profile_key", read_only=True)
    source_id = serializers.CharField(source="source.source_id", read_only=True)
    external_id = serializers.CharField(source="asset_identity.external_id", read_only=True)
    external_id_type = serializers.CharField(
        source="asset_identity.external_id_type",
        read_only=True,
    )
    latest_state_ref = serializers.CharField(source="latest_state.asset_code", read_only=True)

    class Meta:
        model = TelemetryTrustAssessment
        fields = [
            "id",
            "assessment_id",
            "profile",
            "profile_ref",
            "source",
            "source_id",
            "asset_identity",
            "external_id",
            "external_id_type",
            "latest_state",
            "latest_state_ref",
            "asset_type",
            "asset_code",
            "trust_status",
            "freshness_status",
            "confidence_score",
            "identity_match_status",
            "source_rank",
            "reasons",
            "evidence",
            "assessed_at",
            "algorithm_version",
            "created_at",
        ]
        read_only_fields = fields


class TelemetryTrustAssessSerializer(serializers.Serializer):
    latest_state = serializers.PrimaryKeyRelatedField(
        queryset=LatestAssetState.objects.all(),
        required=False,
        allow_null=True,
    )
    plan_version = serializers.PrimaryKeyRelatedField(
        queryset=PlanVersion.objects.all(),
        required=False,
        allow_null=True,
    )
    profile = serializers.PrimaryKeyRelatedField(
        queryset=TelemetryTrustProfile.objects.all(),
        required=False,
        allow_null=True,
    )


class TelemetryReplayRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = TelemetryReplayRun
        fields = [
            "id",
            "replay_id",
            "name",
            "status",
            "scenario_code",
            "started_at",
            "completed_at",
            "speed_multiplier",
            "seed_start_at",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "status",
            "started_at",
            "completed_at",
            "created_at",
            "updated_at",
        ]


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
    geofence_events = MovementEventSerializer(many=True)
    alerts = TrackingAlertSerializer(many=True)
