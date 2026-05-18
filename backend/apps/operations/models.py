import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.masters.models import Location
from apps.scheduling.models import Assignment, PlanVersion, ScheduleEvent, Trip
from apps.telemetry.models import GeofenceZone


def _reference(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def snapshot_reference() -> str:
    return _reference("DHS")


def candidate_reference() -> str:
    return _reference("OEC")


def confirmed_event_reference() -> str:
    return _reference("COE")


def actualization_reference() -> str:
    return _reference("OAC")


def batch_reference() -> str:
    return _reference("OEB")


class OperationsAssetType(models.TextChoices):
    TUG = "tug", "Tug"
    BARGE = "barge", "Barge"
    CTS = "cts", "CTS"
    OGV = "ogv", "OGV"
    JETTY = "jetty", "Jetty"
    BRIDGE = "bridge", "Bridge"
    TIDE_GATE = "tide_gate", "Tide gate"
    DEVICE = "device", "Device"
    OTHER = "other", "Other"


class OperationalEventKind(models.TextChoices):
    JETTY_ARRIVED = "jetty_arrived", "Jetty arrived"
    JETTY_LOADING_STARTED = "jetty_loading_started", "Jetty loading started"
    JETTY_LOADING_COMPLETED = "jetty_loading_completed", "Jetty loading completed"
    JETTY_DEPARTED = "jetty_departed", "Jetty departed"
    BRIDGE_OPENED = "bridge_opened", "Bridge opened"
    BRIDGE_CLOSED = "bridge_closed", "Bridge closed"
    BRIDGE_CROSSED = "bridge_crossed", "Bridge crossed"
    TIDE_LEVEL_OBSERVED = "tide_level_observed", "Tide level observed"
    TIDE_GATE_PASSED = "tide_gate_passed", "Tide gate passed"
    CTS_ARRIVED = "cts_arrived", "CTS arrived"
    CTS_DISCHARGE_STARTED = "cts_discharge_started", "CTS discharge started"
    CTS_RATE_UPDATED = "cts_rate_updated", "CTS rate updated"
    CTS_DISCHARGE_STOPPED = "cts_discharge_stopped", "CTS discharge stopped"
    CTS_DISCHARGE_COMPLETED = "cts_discharge_completed", "CTS discharge completed"
    EQUIPMENT_BREAKDOWN = "equipment_breakdown", "Equipment breakdown"
    DEVICE_OFFLINE = "device_offline", "Device offline"
    MANUAL_STATUS_UPDATE = "manual_status_update", "Manual status update"


class IntegrationFeed(models.Model):
    class FeedType(models.TextChoices):
        SYNTHETIC = "synthetic", "Synthetic"
        MQTT = "mqtt", "MQTT"
        HTTP = "http", "HTTP"
        PLC = "plc", "PLC"
        WEIGHBRIDGE = "weighbridge", "Weighbridge"
        TIDE_SENSOR = "tide_sensor", "Tide sensor"
        BRIDGE_OPERATOR = "bridge_operator", "Bridge operator"
        JETTY_OPERATOR = "jetty_operator", "Jetty operator"
        CTS_OPERATOR = "cts_operator", "CTS operator"
        MANUAL = "manual", "Manual"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DEGRADED = "degraded", "Degraded"
        PAUSED = "paused", "Paused"
        RETIRED = "retired", "Retired"

    class TrustMode(models.TextChoices):
        MANUAL_REVIEW = "manual_review", "Manual review"
        AUTO_CONFIRM = "auto_confirm", "Auto-confirm"
        AUTO_CONFIRM_WITH_THRESHOLD = (
            "auto_confirm_with_threshold",
            "Auto-confirm with threshold",
        )

    feed_id = models.CharField(max_length=96, unique=True)
    name = models.CharField(max_length=180)
    feed_type = models.CharField(max_length=40, choices=FeedType.choices)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    trust_mode = models.CharField(
        max_length=40,
        choices=TrustMode.choices,
        default=TrustMode.MANUAL_REVIEW,
    )
    freshness_threshold_seconds = models.PositiveIntegerField(default=900)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["feed_id"]
        indexes = [
            models.Index(fields=("feed_type", "status")),
            models.Index(fields=("trust_mode", "status")),
        ]

    def __str__(self) -> str:
        return self.feed_id


class DeviceEndpoint(models.Model):
    class DeviceType(models.TextChoices):
        EDGE_GATEWAY = "edge_gateway", "Edge gateway"
        JETTY_PLC = "jetty_plc", "Jetty PLC"
        WEIGHBRIDGE = "weighbridge", "Weighbridge"
        OPERATOR_TABLET = "operator_tablet", "Operator tablet"
        TIDE_SENSOR = "tide_sensor", "Tide sensor"
        BRIDGE_CONSOLE = "bridge_console", "Bridge console"
        CTS_PLC = "cts_plc", "CTS PLC"
        AIS_RECEIVER = "ais_receiver", "AIS receiver"
        GPS_TRACKER = "gps_tracker", "GPS tracker"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DEGRADED = "degraded", "Degraded"
        OFFLINE = "offline", "Offline"
        PAUSED = "paused", "Paused"
        RETIRED = "retired", "Retired"

    device_id = models.CharField(max_length=96, unique=True)
    feed = models.ForeignKey(
        IntegrationFeed,
        on_delete=models.PROTECT,
        related_name="devices",
    )
    device_type = models.CharField(max_length=40, choices=DeviceType.choices)
    asset_type = models.CharField(
        max_length=32,
        choices=OperationsAssetType.choices,
        blank=True,
    )
    asset_code = models.CharField(max_length=80, blank=True)
    location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operations_devices",
    )
    geofence = models.ForeignKey(
        GeofenceZone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operations_devices",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    firmware_version = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["device_type", "device_id"]
        indexes = [
            models.Index(fields=("status", "device_type")),
            models.Index(fields=("asset_type", "asset_code")),
            models.Index(fields=("last_seen_at",)),
        ]

    def __str__(self) -> str:
        return self.device_id


class DeviceHealthSnapshot(models.Model):
    class HealthStatus(models.TextChoices):
        HEALTHY = "healthy", "Healthy"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"
        OFFLINE = "offline", "Offline"
        UNKNOWN = "unknown", "Unknown"

    snapshot_id = models.CharField(
        max_length=96,
        unique=True,
        default=snapshot_reference,
    )
    device = models.ForeignKey(
        DeviceEndpoint,
        on_delete=models.PROTECT,
        related_name="health_snapshots",
    )
    observed_at = models.DateTimeField()
    received_at = models.DateTimeField(default=timezone.now)
    health_status = models.CharField(
        max_length=32,
        choices=HealthStatus.choices,
        default=HealthStatus.UNKNOWN,
    )
    battery_level = models.PositiveSmallIntegerField(null=True, blank=True)
    power_status = models.CharField(max_length=80, blank=True)
    network_status = models.CharField(max_length=80, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    gap_seconds = models.PositiveIntegerField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-observed_at", "-id"]
        indexes = [
            models.Index(fields=("device", "observed_at")),
            models.Index(fields=("health_status", "observed_at")),
        ]

    def __str__(self) -> str:
        return self.snapshot_id


class OperationalEventCandidate(models.Model):
    class SourceKind(models.TextChoices):
        SYNTHETIC = "synthetic", "Synthetic"
        DEVICE = "device", "Device"
        OPERATOR = "operator", "Operator"
        TELEMETRY_INFERRED = "telemetry_inferred", "Telemetry inferred"
        VENDOR = "vendor", "Vendor"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        AUTO_CONFIRMED = "auto_confirmed", "Auto-confirmed"
        CONFIRMED = "confirmed", "Confirmed"
        REJECTED = "rejected", "Rejected"
        SUPERSEDED = "superseded", "Superseded"
        DUPLICATE = "duplicate", "Duplicate"

    candidate_id = models.CharField(
        max_length=96,
        unique=True,
        default=candidate_reference,
    )
    feed = models.ForeignKey(
        IntegrationFeed,
        on_delete=models.PROTECT,
        related_name="event_candidates",
    )
    device = models.ForeignKey(
        DeviceEndpoint,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="event_candidates",
    )
    source_kind = models.CharField(max_length=32, choices=SourceKind.choices)
    event_kind = models.CharField(max_length=48, choices=OperationalEventKind.choices)
    asset_type = models.CharField(
        max_length=32,
        choices=OperationsAssetType.choices,
        blank=True,
    )
    asset_code = models.CharField(max_length=80, blank=True)
    trip = models.ForeignKey(
        Trip,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operational_event_candidates",
    )
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operational_event_candidates",
    )
    schedule_event = models.ForeignKey(
        ScheduleEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="operational_event_candidates",
    )
    event_at = models.DateTimeField()
    received_at = models.DateTimeField(default=timezone.now)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    dedupe_key = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    payload = models.JSONField(default=dict, blank=True)
    raw_payload_ref = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-event_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=("feed", "dedupe_key"),
                condition=~models.Q(dedupe_key=""),
                name="unique_operational_candidate_dedupe_key",
            )
        ]
        indexes = [
            models.Index(fields=("status", "event_kind", "event_at")),
            models.Index(fields=("asset_type", "asset_code", "event_at")),
            models.Index(fields=("trip", "event_kind")),
            models.Index(fields=("schedule_event", "event_kind")),
        ]

    def __str__(self) -> str:
        return self.candidate_id


class ConfirmedOperationalEvent(models.Model):
    class ConfirmationMode(models.TextChoices):
        MANUAL = "manual", "Manual"
        AUTO_TRUSTED_SOURCE = "auto_trusted_source", "Auto trusted source"
        AUTO_THRESHOLD = "auto_threshold", "Auto threshold"
        REPLAY_PROOF = "replay_proof", "Replay proof"

    event_id = models.CharField(
        max_length=96,
        unique=True,
        default=confirmed_event_reference,
    )
    candidate = models.OneToOneField(
        OperationalEventCandidate,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_event",
    )
    event_kind = models.CharField(max_length=48, choices=OperationalEventKind.choices)
    plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_operational_events",
    )
    trip = models.ForeignKey(
        Trip,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_operational_events",
    )
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_operational_events",
    )
    schedule_event = models.ForeignKey(
        ScheduleEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_operational_events",
    )
    actual_at = models.DateTimeField()
    confirmed_quantity_mt = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    confirmed_rate_tph = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        null=True,
        blank=True,
    )
    confirmed_grade_code = models.CharField(max_length=80, blank=True)
    confirmed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="confirmed_operational_events",
    )
    confirmed_at = models.DateTimeField(default=timezone.now)
    confirmation_mode = models.CharField(
        max_length=40,
        choices=ConfirmationMode.choices,
        default=ConfirmationMode.MANUAL,
    )
    reason_code = models.CharField(max_length=80, blank=True)
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-actual_at", "-id"]
        indexes = [
            models.Index(fields=("event_kind", "actual_at")),
            models.Index(fields=("plan_version", "event_kind", "actual_at")),
            models.Index(fields=("trip", "event_kind")),
            models.Index(fields=("schedule_event", "event_kind")),
        ]

    def __str__(self) -> str:
        return self.event_id


class OperationalActualization(models.Model):
    class TargetType(models.TextChoices):
        SCHEDULE_EVENT = "schedule_event", "Schedule event"
        TRIP = "trip", "Trip"
        ASSIGNMENT = "assignment", "Assignment"
        CONSTRAINT_WINDOW = "constraint_window", "Constraint window"
        ASSET_HEALTH = "asset_health", "Asset health"

    class Status(models.TextChoices):
        APPLIED = "applied", "Applied"
        SKIPPED = "skipped", "Skipped"
        FAILED = "failed", "Failed"

    actualization_id = models.CharField(
        max_length=96,
        unique=True,
        default=actualization_reference,
    )
    confirmed_event = models.ForeignKey(
        ConfirmedOperationalEvent,
        on_delete=models.CASCADE,
        related_name="actualizations",
    )
    target_type = models.CharField(max_length=40, choices=TargetType.choices)
    target_id = models.CharField(max_length=120, blank=True)
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.SKIPPED)
    error_message = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=("confirmed_event", "status")),
            models.Index(fields=("target_type", "target_id")),
        ]

    def __str__(self) -> str:
        return self.actualization_id


class EdgeEventBatch(models.Model):
    class Status(models.TextChoices):
        RECEIVED = "received", "Received"
        PROCESSED = "processed", "Processed"
        PARTIAL = "partial", "Partial"
        FAILED = "failed", "Failed"

    batch_id = models.CharField(max_length=96, unique=True, default=batch_reference)
    feed = models.ForeignKey(
        IntegrationFeed,
        on_delete=models.PROTECT,
        related_name="edge_batches",
    )
    device = models.ForeignKey(
        DeviceEndpoint,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="edge_batches",
    )
    batch_sequence = models.CharField(max_length=120, blank=True)
    captured_from = models.DateTimeField(null=True, blank=True)
    captured_to = models.DateTimeField(null=True, blank=True)
    received_at = models.DateTimeField(default=timezone.now)
    message_count = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.RECEIVED)
    checksum_sha256 = models.CharField(max_length=64, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-received_at", "-id"]
        indexes = [
            models.Index(fields=("feed", "status", "received_at")),
            models.Index(fields=("device", "received_at")),
            models.Index(fields=("batch_sequence",)),
        ]

    def __str__(self) -> str:
        return self.batch_id
