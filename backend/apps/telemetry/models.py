import uuid

from django.db import models

from apps.masters.models import Location
from apps.scheduling.models import ScheduleEvent, SimulationScenario, Trip


def _reference(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def telemetry_trust_assessment_reference() -> str:
    return _reference("TTA")


class TelemetrySource(models.Model):
    class SourceType(models.TextChoices):
        SYNTHETIC_GPS = "synthetic_gps", "Synthetic GPS"
        SYNTHETIC_AIS = "synthetic_ais", "Synthetic AIS"
        VENDOR_API = "vendor_api", "Vendor API"
        MANUAL = "manual", "Manual"
        DEVICE_GATEWAY = "device_gateway", "Device gateway"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DEGRADED = "degraded", "Degraded"
        PAUSED = "paused", "Paused"
        RETIRED = "retired", "Retired"

    source_id = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    source_type = models.CharField(max_length=32, choices=SourceType.choices)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    freshness_threshold_seconds = models.PositiveIntegerField(default=900)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["source_id"]
        indexes = [
            models.Index(fields=("source_type", "status")),
        ]

    def __str__(self) -> str:
        return self.source_id


class AssetIdentity(models.Model):
    class AssetType(models.TextChoices):
        TUG = "tug", "Tug"
        BARGE = "barge", "Barge"
        CTS = "cts", "CTS"
        OGV = "ogv", "OGV"
        SERVICE_BOAT = "service_boat", "Service boat"

    class ExternalIdType(models.TextChoices):
        MMSI = "mmsi", "MMSI"
        IMO = "imo", "IMO"
        TRACKER_ID = "tracker_id", "Tracker ID"
        DEVICE_SERIAL = "device_serial", "Device serial"
        SYNTHETIC_ID = "synthetic_id", "Synthetic ID"

    source = models.ForeignKey(
        TelemetrySource,
        on_delete=models.CASCADE,
        related_name="asset_identities",
    )
    asset_type = models.CharField(max_length=32, choices=AssetType.choices)
    asset_object_id = models.PositiveBigIntegerField(null=True, blank=True)
    asset_code = models.CharField(max_length=80)
    external_id = models.CharField(max_length=120)
    external_id_type = models.CharField(max_length=32, choices=ExternalIdType.choices)
    is_primary = models.BooleanField(default=True)
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_to = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["asset_type", "asset_code", "source__source_id", "external_id"]
        constraints = [
            models.UniqueConstraint(
                fields=("source", "external_id"),
                name="unique_telemetry_source_external_id",
            )
        ]
        indexes = [
            models.Index(fields=("asset_type", "asset_code")),
            models.Index(fields=("external_id_type", "external_id")),
        ]

    def __str__(self) -> str:
        return f"{self.asset_code} via {self.source.source_id}"


class PositionPing(models.Model):
    class SignalQuality(models.TextChoices):
        GOOD = "good", "Good"
        WEAK = "weak", "Weak"
        STALE = "stale", "Stale"
        INVALID = "invalid", "Invalid"

    ping_id = models.CharField(max_length=96, unique=True)
    source = models.ForeignKey(
        TelemetrySource,
        on_delete=models.PROTECT,
        related_name="position_pings",
    )
    asset_identity = models.ForeignKey(
        AssetIdentity,
        on_delete=models.PROTECT,
        related_name="position_pings",
    )
    asset_type = models.CharField(max_length=32, choices=AssetIdentity.AssetType.choices)
    asset_code = models.CharField(max_length=80)
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    speed_knots = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    course_degrees = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    heading_degrees = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    device_timestamp = models.DateTimeField()
    received_timestamp = models.DateTimeField()
    signal_quality = models.CharField(
        max_length=32,
        choices=SignalQuality.choices,
        default=SignalQuality.GOOD,
    )
    accuracy_m = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)
    battery_level = models.PositiveSmallIntegerField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)
    raw_payload_ref = models.CharField(max_length=255, blank=True)
    is_synthetic = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-device_timestamp", "-id"]
        indexes = [
            models.Index(fields=("asset_code", "device_timestamp")),
            models.Index(fields=("source", "received_timestamp")),
            models.Index(fields=("asset_type", "asset_code", "device_timestamp")),
            models.Index(fields=("is_synthetic", "device_timestamp")),
        ]

    def __str__(self) -> str:
        return self.ping_id


class LatestAssetState(models.Model):
    class DerivedStatus(models.TextChoices):
        UNDERWAY = "underway", "Underway"
        STOPPED = "stopped", "Stopped"
        UNKNOWN = "unknown", "Unknown"

    class FreshnessStatus(models.TextChoices):
        FRESH = "fresh", "Fresh"
        AGING = "aging", "Aging"
        STALE = "stale", "Stale"
        MISSING = "missing", "Missing"

    asset_type = models.CharField(max_length=32, choices=AssetIdentity.AssetType.choices)
    asset_code = models.CharField(max_length=80)
    source = models.ForeignKey(
        TelemetrySource,
        on_delete=models.PROTECT,
        related_name="latest_asset_states",
    )
    asset_identity = models.ForeignKey(
        AssetIdentity,
        on_delete=models.PROTECT,
        related_name="latest_states",
    )
    last_ping = models.ForeignKey(
        PositionPing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="latest_state_refs",
    )
    derived_status = models.CharField(
        max_length=32,
        choices=DerivedStatus.choices,
        default=DerivedStatus.UNKNOWN,
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    longitude = models.DecimalField(max_digits=10, decimal_places=7, null=True, blank=True)
    speed_knots = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    heading_degrees = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    last_seen_at = models.DateTimeField(null=True, blank=True)
    current_geofence = models.ForeignKey(
        "GeofenceZone",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="current_asset_states",
    )
    last_movement_event = models.ForeignKey(
        "MovementEvent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="latest_state_refs",
    )
    freshness_status = models.CharField(
        max_length=32,
        choices=FreshnessStatus.choices,
        default=FreshnessStatus.MISSING,
    )
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    paired_asset_code = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["asset_type", "asset_code"]
        constraints = [
            models.UniqueConstraint(
                fields=("asset_type", "asset_code"),
                name="unique_latest_asset_state",
            )
        ]
        indexes = [
            models.Index(fields=("freshness_status", "last_seen_at")),
            models.Index(fields=("asset_type", "asset_code")),
        ]

    def __str__(self) -> str:
        return f"{self.asset_code} {self.freshness_status}"


class GeofenceZone(models.Model):
    class ZoneType(models.TextChoices):
        MINE = "mine", "Mine"
        CPP = "cpp", "CPP"
        JETTY = "jetty", "Jetty"
        CHECKPOINT = "checkpoint", "Checkpoint"
        BRIDGE = "bridge", "Bridge"
        TIDE_GATE = "tide_gate", "Tide gate"
        ANCHORAGE = "anchorage", "Anchorage"
        TRANSSHIPMENT = "transshipment", "Transshipment"
        CTS_ZONE = "cts_zone", "CTS zone"
        MAINTENANCE = "maintenance", "Maintenance"

    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        PAUSED = "paused", "Paused"
        RETIRED = "retired", "Retired"

    zone_id = models.CharField(max_length=96, unique=True)
    name = models.CharField(max_length=180)
    zone_type = models.CharField(max_length=40, choices=ZoneType.choices)
    source_location = models.ForeignKey(
        Location,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="telemetry_geofences",
    )
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    radius_m = models.PositiveIntegerField()
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["zone_type", "zone_id"]
        indexes = [
            models.Index(fields=("status", "zone_type")),
            models.Index(fields=("zone_id",)),
        ]

    def __str__(self) -> str:
        return self.zone_id


class MovementEvent(models.Model):
    class EventType(models.TextChoices):
        ENTER_GEOFENCE = "enter_geofence", "Enter geofence"
        EXIT_GEOFENCE = "exit_geofence", "Exit geofence"

    event_id = models.CharField(max_length=96, unique=True)
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    asset_type = models.CharField(max_length=32, choices=AssetIdentity.AssetType.choices)
    asset_code = models.CharField(max_length=80)
    source = models.ForeignKey(
        TelemetrySource,
        on_delete=models.PROTECT,
        related_name="movement_events",
    )
    asset_identity = models.ForeignKey(
        AssetIdentity,
        on_delete=models.PROTECT,
        related_name="movement_events",
    )
    position_ping = models.ForeignKey(
        PositionPing,
        on_delete=models.CASCADE,
        related_name="movement_events",
    )
    geofence = models.ForeignKey(
        GeofenceZone,
        on_delete=models.PROTECT,
        related_name="movement_events",
    )
    event_at = models.DateTimeField()
    latitude = models.DecimalField(max_digits=10, decimal_places=7)
    longitude = models.DecimalField(max_digits=10, decimal_places=7)
    speed_knots = models.DecimalField(max_digits=7, decimal_places=2, null=True, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-event_at", "-id"]
        constraints = [
            models.UniqueConstraint(
                fields=("position_ping", "geofence", "event_type"),
                name="unique_ping_geofence_movement_event",
            )
        ]
        indexes = [
            models.Index(fields=("asset_code", "event_at")),
            models.Index(fields=("event_type", "event_at")),
            models.Index(fields=("geofence", "event_at")),
        ]

    def __str__(self) -> str:
        return f"{self.asset_code} {self.event_type} {self.geofence.zone_id}"


class LiveEtaProjection(models.Model):
    class CalculationMethod(models.TextChoices):
        ROUTE_REMAINING = "route_remaining", "Route remaining"
        GEOFENCE_SEQUENCE = "geofence_sequence", "Geofence sequence"
        SIMPLE_SPEED = "simple_speed", "Simple speed"
        SYNTHETIC_SCRIPT = "synthetic_script", "Synthetic script"

    class Status(models.TextChoices):
        ON_TIME = "on_time", "On time"
        WATCH = "watch", "Watch"
        DELAYED = "delayed", "Delayed"
        UNKNOWN = "unknown", "Unknown"

    projection_id = models.CharField(max_length=96, unique=True)
    asset_type = models.CharField(max_length=32, choices=AssetIdentity.AssetType.choices)
    asset_code = models.CharField(max_length=80)
    source = models.ForeignKey(
        TelemetrySource,
        on_delete=models.PROTECT,
        related_name="eta_projections",
    )
    asset_identity = models.ForeignKey(
        AssetIdentity,
        on_delete=models.PROTECT,
        related_name="eta_projections",
    )
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="live_eta_projections",
    )
    schedule_event = models.ForeignKey(
        ScheduleEvent,
        on_delete=models.CASCADE,
        related_name="live_eta_projections",
    )
    planned_at = models.DateTimeField()
    observed_eta = models.DateTimeField(null=True, blank=True)
    variance_minutes = models.IntegerField(null=True, blank=True)
    calculation_method = models.CharField(
        max_length=40,
        choices=CalculationMethod.choices,
        default=CalculationMethod.SIMPLE_SPEED,
    )
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    source_ping = models.ForeignKey(
        PositionPing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eta_projections",
    )
    current_geofence = models.ForeignKey(
        GeofenceZone,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="eta_projections",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.UNKNOWN,
    )
    metadata = models.JSONField(default=dict, blank=True)
    calculated_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-calculated_at", "asset_code"]
        constraints = [
            models.UniqueConstraint(
                fields=("asset_code", "trip", "schedule_event"),
                name="unique_live_eta_asset_trip_event",
            )
        ]
        indexes = [
            models.Index(fields=("asset_code", "status")),
            models.Index(fields=("trip", "status")),
            models.Index(fields=("schedule_event", "status")),
        ]

    def __str__(self) -> str:
        return self.projection_id


class TrackingAlert(models.Model):
    class AlertType(models.TextChoices):
        DELAY = "delay", "Delay"
        STALE_SIGNAL = "stale_signal", "Stale signal"
        ROUTE_DEVIATION = "route_deviation", "Route deviation"
        GEOFENCE_DWELL = "geofence_dwell", "Geofence dwell"
        MISSING_ASSET = "missing_asset", "Missing asset"
        ETA_RISK = "eta_risk", "ETA risk"

    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        ACKNOWLEDGED = "acknowledged", "Acknowledged"
        CONVERTED_TO_SCENARIO = "converted_to_scenario", "Converted to scenario"
        DISMISSED = "dismissed", "Dismissed"
        RESOLVED = "resolved", "Resolved"

    class SourceKind(models.TextChoices):
        SYNTHETIC = "synthetic", "Synthetic"
        OBSERVED = "observed", "Observed"
        VENDOR = "vendor", "Vendor"

    alert_id = models.CharField(max_length=96, unique=True)
    alert_type = models.CharField(max_length=40, choices=AlertType.choices)
    severity = models.CharField(
        max_length=32,
        choices=Severity.choices,
        default=Severity.INFO,
    )
    asset_type = models.CharField(max_length=32, choices=AssetIdentity.AssetType.choices)
    asset_code = models.CharField(max_length=80)
    source = models.ForeignKey(
        TelemetrySource,
        on_delete=models.PROTECT,
        related_name="tracking_alerts",
    )
    asset_identity = models.ForeignKey(
        AssetIdentity,
        on_delete=models.PROTECT,
        related_name="tracking_alerts",
    )
    source_ping = models.ForeignKey(
        PositionPing,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tracking_alerts",
    )
    trip = models.ForeignKey(
        Trip,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tracking_alerts",
    )
    schedule_event = models.ForeignKey(
        ScheduleEvent,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tracking_alerts",
    )
    eta_projection = models.ForeignKey(
        LiveEtaProjection,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="tracking_alerts",
    )
    message = models.CharField(max_length=255)
    evidence = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=40, choices=Status.choices, default=Status.OPEN)
    source_kind = models.CharField(
        max_length=32,
        choices=SourceKind.choices,
        default=SourceKind.OBSERVED,
    )
    opened_at = models.DateTimeField()
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_scenario = models.ForeignKey(
        SimulationScenario,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_tracking_alerts",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-opened_at", "severity", "asset_code"]
        indexes = [
            models.Index(fields=("status", "severity", "opened_at")),
            models.Index(fields=("asset_code", "status", "alert_type")),
            models.Index(fields=("trip", "status", "alert_type")),
            models.Index(fields=("source_kind", "status")),
        ]

    def __str__(self) -> str:
        return self.alert_id

    def convert_to_scenario(self, *, actor):
        from .services import convert_tracking_alert_to_scenario

        return convert_tracking_alert_to_scenario(alert=self, actor=actor)


class TelemetryTrustProfile(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DEPRECATED = "deprecated", "Deprecated"

    profile_key = models.CharField(max_length=96, unique=True)
    name = models.CharField(max_length=160)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    source_hierarchy = models.JSONField(default=list, blank=True)
    freshness_thresholds = models.JSONField(default=dict, blank=True)
    confidence_thresholds = models.JSONField(default=dict, blank=True)
    identity_rules = models.JSONField(default=dict, blank=True)
    quarantine_rules = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["profile_key", "-version"]
        indexes = [
            models.Index(fields=("profile_key", "status")),
            models.Index(fields=("status", "version")),
        ]

    def __str__(self) -> str:
        return f"{self.profile_key} v{self.version}"


class TelemetryTrustAssessment(models.Model):
    class TrustStatus(models.TextChoices):
        TRUSTED = "trusted", "Trusted"
        DEGRADED = "degraded", "Degraded"
        QUARANTINED = "quarantined", "Quarantined"
        MANUAL_CONFIRMATION_REQUIRED = (
            "manual_confirmation_required",
            "Manual confirmation required",
        )
        UNKNOWN = "unknown", "Unknown"

    class IdentityMatchStatus(models.TextChoices):
        MATCHED = "matched", "Matched"
        AMBIGUOUS = "ambiguous", "Ambiguous"
        UNMAPPED = "unmapped", "Unmapped"
        UNKNOWN = "unknown", "Unknown"

    assessment_id = models.CharField(
        max_length=96,
        unique=True,
        default=telemetry_trust_assessment_reference,
    )
    profile = models.ForeignKey(
        TelemetryTrustProfile,
        on_delete=models.PROTECT,
        related_name="assessments",
    )
    source = models.ForeignKey(
        TelemetrySource,
        on_delete=models.PROTECT,
        related_name="trust_assessments",
    )
    asset_identity = models.ForeignKey(
        AssetIdentity,
        on_delete=models.PROTECT,
        related_name="trust_assessments",
    )
    latest_state = models.ForeignKey(
        LatestAssetState,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="trust_assessments",
    )
    asset_type = models.CharField(max_length=32, choices=AssetIdentity.AssetType.choices)
    asset_code = models.CharField(max_length=80)
    trust_status = models.CharField(
        max_length=48,
        choices=TrustStatus.choices,
        default=TrustStatus.UNKNOWN,
    )
    freshness_status = models.CharField(max_length=32, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    identity_match_status = models.CharField(
        max_length=32,
        choices=IdentityMatchStatus.choices,
        default=IdentityMatchStatus.UNKNOWN,
    )
    source_rank = models.PositiveIntegerField(default=999)
    reasons = models.JSONField(default=list, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    assessed_at = models.DateTimeField()
    algorithm_version = models.CharField(max_length=96)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-assessed_at", "-id"]
        indexes = [
            models.Index(fields=("trust_status", "assessed_at")),
            models.Index(fields=("asset_type", "asset_code", "assessed_at")),
            models.Index(fields=("source", "trust_status")),
            models.Index(fields=("profile", "trust_status")),
        ]

    def __str__(self) -> str:
        return self.assessment_id


class TelemetryReplayRun(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        RUNNING = "running", "Running"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    replay_id = models.CharField(max_length=96, unique=True)
    name = models.CharField(max_length=180)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    scenario_code = models.CharField(max_length=80)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    speed_multiplier = models.DecimalField(max_digits=6, decimal_places=2, default=1)
    seed_start_at = models.DateTimeField()
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["scenario_code", "replay_id"]
        indexes = [
            models.Index(fields=("status", "scenario_code")),
            models.Index(fields=("started_at", "completed_at")),
        ]

    def __str__(self) -> str:
        return self.replay_id
