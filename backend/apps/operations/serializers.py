from rest_framework import serializers

from .models import (
    ConfirmedOperationalEvent,
    DeviceEndpoint,
    DeviceHealthSnapshot,
    EdgeEventBatch,
    IntegrationFeed,
    OperationalActualization,
    OperationalEventCandidate,
)


class IntegrationFeedSerializer(serializers.ModelSerializer):
    class Meta:
        model = IntegrationFeed
        fields = [
            "id",
            "feed_id",
            "name",
            "feed_type",
            "status",
            "trust_mode",
            "freshness_threshold_seconds",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class DeviceEndpointSerializer(serializers.ModelSerializer):
    feed_ref = serializers.CharField(source="feed.feed_id", read_only=True)
    location_code = serializers.CharField(source="location.code", read_only=True)
    geofence_ref = serializers.CharField(source="geofence.zone_id", read_only=True)

    class Meta:
        model = DeviceEndpoint
        fields = [
            "id",
            "device_id",
            "feed",
            "feed_ref",
            "device_type",
            "asset_type",
            "asset_code",
            "location",
            "location_code",
            "geofence",
            "geofence_ref",
            "status",
            "last_seen_at",
            "firmware_version",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "feed_ref",
            "location_code",
            "geofence_ref",
            "created_at",
            "updated_at",
        ]


class DeviceHealthSnapshotSerializer(serializers.ModelSerializer):
    device_ref = serializers.CharField(source="device.device_id", read_only=True)

    class Meta:
        model = DeviceHealthSnapshot
        fields = [
            "id",
            "snapshot_id",
            "device",
            "device_ref",
            "observed_at",
            "received_at",
            "health_status",
            "battery_level",
            "power_status",
            "network_status",
            "latency_ms",
            "gap_seconds",
            "metadata",
            "created_at",
        ]
        read_only_fields = ["id", "snapshot_id", "device_ref", "created_at"]


class OperationalEventCandidateSerializer(serializers.ModelSerializer):
    feed_ref = serializers.CharField(source="feed.feed_id", read_only=True)
    device_ref = serializers.CharField(source="device.device_id", read_only=True)
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)
    assignment_ref = serializers.CharField(source="assignment.trip.trip_id", read_only=True)
    schedule_event_type = serializers.CharField(source="schedule_event.event_type", read_only=True)
    confirmed_event_ref = serializers.SerializerMethodField()

    class Meta:
        model = OperationalEventCandidate
        fields = [
            "id",
            "candidate_id",
            "feed",
            "feed_ref",
            "device",
            "device_ref",
            "source_kind",
            "event_kind",
            "asset_type",
            "asset_code",
            "trip",
            "trip_ref",
            "assignment",
            "assignment_ref",
            "schedule_event",
            "schedule_event_type",
            "event_at",
            "received_at",
            "confidence_score",
            "dedupe_key",
            "status",
            "payload",
            "raw_payload_ref",
            "metadata",
            "confirmed_event_ref",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "candidate_id",
            "feed_ref",
            "device_ref",
            "trip_ref",
            "assignment_ref",
            "schedule_event_type",
            "status",
            "metadata",
            "confirmed_event_ref",
            "created_at",
            "updated_at",
        ]

    def get_confirmed_event_ref(self, obj) -> str | None:
        try:
            return obj.confirmed_event.event_id
        except Exception:
            return None


class ConfirmedOperationalEventSerializer(serializers.ModelSerializer):
    candidate_ref = serializers.CharField(source="candidate.candidate_id", read_only=True)
    plan_version_ref = serializers.CharField(source="plan_version", read_only=True)
    trip_ref = serializers.CharField(source="trip.trip_id", read_only=True)
    assignment_ref = serializers.CharField(source="assignment.trip.trip_id", read_only=True)
    schedule_event_type = serializers.CharField(source="schedule_event.event_type", read_only=True)
    confirmed_by_email = serializers.EmailField(source="confirmed_by.email", read_only=True)

    class Meta:
        model = ConfirmedOperationalEvent
        fields = [
            "id",
            "event_id",
            "candidate",
            "candidate_ref",
            "event_kind",
            "plan_version",
            "plan_version_ref",
            "trip",
            "trip_ref",
            "assignment",
            "assignment_ref",
            "schedule_event",
            "schedule_event_type",
            "actual_at",
            "confirmed_quantity_mt",
            "confirmed_rate_tph",
            "confirmed_grade_code",
            "confirmed_by",
            "confirmed_by_email",
            "confirmed_at",
            "confirmation_mode",
            "reason_code",
            "before_state",
            "after_state",
            "metadata",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "event_id",
            "candidate_ref",
            "plan_version_ref",
            "trip_ref",
            "assignment_ref",
            "schedule_event_type",
            "confirmed_by",
            "confirmed_by_email",
            "confirmed_at",
            "before_state",
            "after_state",
            "created_at",
        ]


class OperationalActualizationSerializer(serializers.ModelSerializer):
    confirmed_event_ref = serializers.CharField(source="confirmed_event.event_id", read_only=True)

    class Meta:
        model = OperationalActualization
        fields = [
            "id",
            "actualization_id",
            "confirmed_event",
            "confirmed_event_ref",
            "target_type",
            "target_id",
            "before_state",
            "after_state",
            "status",
            "error_message",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EdgeEventBatchSerializer(serializers.ModelSerializer):
    feed_ref = serializers.CharField(source="feed.feed_id", read_only=True)
    device_ref = serializers.CharField(source="device.device_id", read_only=True)

    class Meta:
        model = EdgeEventBatch
        fields = [
            "id",
            "batch_id",
            "feed",
            "feed_ref",
            "device",
            "device_ref",
            "batch_sequence",
            "captured_from",
            "captured_to",
            "received_at",
            "message_count",
            "status",
            "checksum_sha256",
            "metadata",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "batch_id", "feed_ref", "device_ref", "created_at", "updated_at"]
