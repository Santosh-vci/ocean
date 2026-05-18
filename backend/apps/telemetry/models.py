from django.db import models

from apps.masters.models import Location


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
