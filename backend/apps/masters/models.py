from django.db import models

from apps.organizations.models import Organization


class TimestampedMasterModel(models.Model):
    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=180)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="%(class)s_records",
    )
    is_active = models.BooleanField(default=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True
        ordering = ["code"]

    def __str__(self) -> str:
        return f"{self.code} - {self.name}"


class Location(TimestampedMasterModel):
    class LocationType(models.TextChoices):
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

    location_type = models.CharField(max_length=40, choices=LocationType.choices)
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    geofence_radius_m = models.PositiveIntegerField(default=500)
    parent_area = models.CharField(max_length=120, blank=True)
    operational_notes = models.TextField(blank=True)


class CoalGrade(TimestampedMasterModel):
    brand_family = models.CharField(max_length=80)
    typical_cv_kcal = models.PositiveIntegerField(null=True, blank=True)
    sulfur_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    ash_pct = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    sequence_priority = models.PositiveIntegerField(default=1)


class Mine(TimestampedMasterModel):
    region = models.CharField(max_length=120, blank=True)
    default_haul_distance_km = models.DecimalField(
        max_digits=8,
        decimal_places=2,
        null=True,
        blank=True,
    )


class Stockpile(TimestampedMasterModel):
    mine = models.ForeignKey(Mine, on_delete=models.PROTECT, related_name="stockpiles")
    coal_grade = models.ForeignKey(CoalGrade, on_delete=models.PROTECT, related_name="stockpiles")
    available_quantity_mt = models.PositiveIntegerField(default=0)
    reserved_quantity_mt = models.PositiveIntegerField(default=0)


class Jetty(TimestampedMasterModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        DEGRADED = "degraded", "Degraded"
        BLOCKED = "blocked", "Blocked"

    location_name = models.CharField(max_length=160)
    loading_rate_tph = models.PositiveIntegerField(default=0)
    max_barge_draft_m = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True,
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.AVAILABLE)


class Tug(TimestampedMasterModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        ASSIGNED = "assigned", "Assigned"
        MAINTENANCE = "maintenance", "Maintenance"
        BREAKDOWN = "breakdown", "Breakdown"

    horsepower = models.PositiveIntegerField()
    bollard_pull_tonnes = models.DecimalField(max_digits=6, decimal_places=2)
    ais_mmsi = models.CharField(max_length=24, blank=True)
    gps_device_id = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.AVAILABLE)


class Barge(TimestampedMasterModel):
    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        ASSIGNED = "assigned", "Assigned"
        MAINTENANCE = "maintenance", "Maintenance"
        BREAKDOWN = "breakdown", "Breakdown"

    capacity_mt = models.PositiveIntegerField()
    barge_class = models.CharField(max_length=80)
    max_draft_m = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.AVAILABLE)


class CTSAsset(TimestampedMasterModel):
    class CtsType(models.TextChoices):
        CONVEYOR = "conveyor", "Conveyor CTS"
        CONVENTIONAL = "conventional", "Conventional CTS"
        FLOATING_CRANE = "floating_crane", "Floating Crane"
        FLOATING_STATION = "floating_station", "Floating Transfer Station"

    cts_type = models.CharField(max_length=40, choices=CtsType.choices)
    daily_capacity_mt = models.PositiveIntegerField()
    operating_area = models.CharField(max_length=160)
    is_available = models.BooleanField(default=True)


class Route(TimestampedMasterModel):
    origin = models.CharField(max_length=160)
    destination = models.CharField(max_length=160)
    default_loaded_duration_minutes = models.PositiveIntegerField()
    default_empty_duration_minutes = models.PositiveIntegerField()


class RouteSegment(models.Model):
    route = models.ForeignKey(Route, on_delete=models.CASCADE, related_name="segments")
    sequence = models.PositiveIntegerField()
    from_location = models.CharField(max_length=160)
    to_location = models.CharField(max_length=160)
    distance_nm = models.DecimalField(max_digits=8, decimal_places=2)
    loaded_duration_minutes = models.PositiveIntegerField()
    empty_duration_minutes = models.PositiveIntegerField()
    requires_tide_window = models.BooleanField(default=False)
    requires_bridge_window = models.BooleanField(default=False)

    class Meta:
        ordering = ["route__code", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=("route", "sequence"),
                name="unique_route_segment_sequence",
            )
        ]

    def __str__(self) -> str:
        return f"{self.route.code} #{self.sequence}"


class LoadingRateProfile(TimestampedMasterModel):
    class ResourceType(models.TextChoices):
        JETTY = "jetty", "Jetty"
        CTS = "cts", "CTS"

    resource_type = models.CharField(max_length=20, choices=ResourceType.choices)
    resource_code = models.CharField(max_length=80)
    coal_grade = models.ForeignKey(
        CoalGrade,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="loading_rate_profiles",
    )
    rate_tph = models.PositiveIntegerField()


class AssetCompatibilityRule(TimestampedMasterModel):
    class RuleType(models.TextChoices):
        TUG_BARGE = "tug_barge", "Tug-Barge"
        BARGE_JETTY = "barge_jetty", "Barge-Jetty"
        CTS_ROUTE = "cts_route", "CTS-Route"
        GRADE_JETTY = "grade_jetty", "Grade-Jetty"

    rule_type = models.CharField(max_length=32, choices=RuleType.choices)
    left_code = models.CharField(max_length=80)
    right_code = models.CharField(max_length=80)
    is_compatible = models.BooleanField(default=True)
    reason = models.CharField(max_length=255, blank=True)

