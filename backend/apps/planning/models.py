from django.conf import settings
from django.db import models

from apps.masters.models import Barge, CoalGrade, CTSAsset, Jetty, Location, RouteSegment
from apps.organizations.models import Organization


class OGVVoyage(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTIVE = "active", "Active"
        AT_RISK = "at_risk", "At risk"
        COMPLETED = "completed", "Completed"
        HOLD = "hold", "Hold"

    class RiskStatus(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        DEMURRAGE = "demurrage", "Demurrage"

    voyage_id = models.CharField(max_length=80, unique=True)
    vessel_name = models.CharField(max_length=160)
    customer_name = models.CharField(max_length=160)
    vessel_class = models.CharField(max_length=80, blank=True)
    eta = models.DateTimeField()
    etb = models.DateTimeField(null=True, blank=True)
    etc_target = models.DateTimeField(null=True, blank=True)
    laycan_start = models.DateTimeField()
    laycan_end = models.DateTimeField()
    required_mt = models.PositiveIntegerField()
    loaded_mt = models.PositiveIntegerField(default=0)
    in_transit_mt = models.PositiveIntegerField(default=0)
    discharged_mt = models.PositiveIntegerField(default=0)
    priority = models.PositiveIntegerField(default=3)
    demurrage_rate_usd_per_day = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    anchorage_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ogv_voyages",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="ogv_voyages",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PLANNED)
    risk_status = models.CharField(
        max_length=32,
        choices=RiskStatus.choices,
        default=RiskStatus.LOW,
    )
    current_stage = models.CharField(max_length=80, blank=True)
    next_blocking_constraint = models.CharField(max_length=180, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["laycan_start", "priority", "vessel_name"]
        indexes = [
            models.Index(fields=("status", "risk_status")),
            models.Index(fields=("laycan_start", "laycan_end")),
        ]

    @property
    def remaining_mt(self) -> int:
        return max(self.required_mt - self.loaded_mt - self.in_transit_mt - self.discharged_mt, 0)

    def __str__(self) -> str:
        return f"{self.voyage_id} - {self.vessel_name}"


class CargoRequirement(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        LOADING = "loading", "Loading"
        PARTIAL = "partial", "Partial"
        COMPLETE = "complete", "Complete"
        HOLD = "hold", "Hold"

    voyage = models.ForeignKey(OGVVoyage, on_delete=models.CASCADE, related_name="requirements")
    coal_grade = models.ForeignKey(
        CoalGrade,
        on_delete=models.PROTECT,
        related_name="cargo_requirements",
    )
    source_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cargo_requirements",
    )
    preferred_jetty = models.ForeignKey(
        Jetty,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="cargo_requirements",
    )
    required_mt = models.PositiveIntegerField()
    loaded_mt = models.PositiveIntegerField(default=0)
    in_transit_mt = models.PositiveIntegerField(default=0)
    discharged_mt = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PLANNED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["voyage__laycan_start", "coal_grade__sequence_priority"]

    @property
    def remaining_mt(self) -> int:
        return max(self.required_mt - self.loaded_mt - self.in_transit_mt - self.discharged_mt, 0)

    def __str__(self) -> str:
        return f"{self.voyage.voyage_id} {self.coal_grade.code}"


class CargoLayerStep(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        QUEUED = "queued", "Queued"
        LOADING = "loading", "Loading"
        COMPLETED = "completed", "Completed"
        BLOCKED = "blocked", "Blocked"
        QC_HOLD = "qc_hold", "QC hold"

    voyage = models.ForeignKey(OGVVoyage, on_delete=models.CASCADE, related_name="layer_steps")
    cargo_requirement = models.ForeignKey(
        CargoRequirement,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="layer_steps",
    )
    hatch_no = models.PositiveIntegerField()
    layer_no = models.PositiveIntegerField()
    required_sequence_no = models.PositiveIntegerField()
    coal_grade = models.ForeignKey(
        CoalGrade,
        on_delete=models.PROTECT,
        related_name="cargo_layer_steps",
    )
    required_mt = models.PositiveIntegerField()
    remaining_mt = models.PositiveIntegerField(default=0)
    planned_barge = models.ForeignKey(
        Barge,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="planned_layer_steps",
    )
    planned_jetty = models.ForeignKey(
        Jetty,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="planned_layer_steps",
    )
    planned_cts = models.ForeignKey(
        CTSAsset,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="planned_layer_steps",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PLANNED)
    blocking_reason = models.CharField(max_length=255, blank=True)
    chain_status = models.CharField(max_length=80, blank=True)
    sequence_violation = models.BooleanField(default=False)
    planned_start = models.DateTimeField(null=True, blank=True)
    planned_end = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["voyage__laycan_start", "voyage__voyage_id", "required_sequence_no"]
        indexes = [
            models.Index(fields=("voyage", "status", "required_sequence_no")),
            models.Index(fields=("planned_start", "planned_end")),
            models.Index(fields=("sequence_violation", "status")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("voyage", "required_sequence_no"),
                name="unique_voyage_layer_sequence",
            )
        ]

    def __str__(self) -> str:
        return f"{self.voyage.voyage_id} H{self.hatch_no}/L{self.layer_no}"


class AssetAvailabilityWindow(models.Model):
    class AssetType(models.TextChoices):
        TUG = "tug", "Tug"
        BARGE = "barge", "Barge"
        CTS = "cts", "CTS"

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        UNAVAILABLE = "unavailable", "Unavailable"
        MAINTENANCE = "maintenance", "Maintenance"
        BREAKDOWN = "breakdown", "Breakdown"

    asset_type = models.CharField(max_length=20, choices=AssetType.choices)
    asset_code = models.CharField(max_length=80)
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    status = models.CharField(max_length=32, choices=Status.choices)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["window_start", "asset_type", "asset_code"]
        indexes = [
            models.Index(fields=("asset_type", "asset_code", "window_start", "window_end")),
            models.Index(fields=("status", "window_start")),
        ]

    def __str__(self) -> str:
        return f"{self.asset_code} {self.status}"


class JettyAvailabilityWindow(models.Model):
    class Status(models.TextChoices):
        WORKING = "working", "Working"
        BLOCKED = "blocked", "Blocked"
        REDUCED = "reduced", "Reduced"
        MAINTENANCE = "maintenance", "Maintenance"

    jetty = models.ForeignKey(Jetty, on_delete=models.CASCADE, related_name="availability_windows")
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    status = models.CharField(max_length=32, choices=Status.choices)
    loading_rate_override_tph = models.PositiveIntegerField(null=True, blank=True)
    reason = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["window_start", "jetty__code"]
        indexes = [
            models.Index(fields=("jetty", "window_start", "window_end")),
            models.Index(fields=("status", "window_start")),
        ]

    def __str__(self) -> str:
        return f"{self.jetty.code} {self.status}"


class TideWindow(models.Model):
    class RiskLevel(models.TextChoices):
        NORMAL = "normal", "Normal"
        TIGHT = "tight", "Tight"
        CLOSED = "closed", "Closed"

    code = models.CharField(max_length=80, unique=True)
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="tide_windows")
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    min_water_level_m = models.DecimalField(max_digits=5, decimal_places=2)
    max_loaded_draft_m = models.DecimalField(max_digits=5, decimal_places=2)
    applicable_route_segment = models.ForeignKey(
        RouteSegment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="tide_windows",
    )
    risk_level = models.CharField(
        max_length=32,
        choices=RiskLevel.choices,
        default=RiskLevel.NORMAL,
    )
    source = models.CharField(max_length=120, default="manual")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["window_start", "code"]
        indexes = [
            models.Index(fields=("location", "window_start", "window_end")),
            models.Index(fields=("is_active", "risk_level", "window_start")),
        ]

    def __str__(self) -> str:
        return self.code


class BridgeWindow(models.Model):
    class Status(models.TextChoices):
        OPEN = "open", "Open"
        RESTRICTED = "restricted", "Restricted"
        CLOSED = "closed", "Closed"

    code = models.CharField(max_length=80, unique=True)
    location = models.ForeignKey(Location, on_delete=models.PROTECT, related_name="bridge_windows")
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    clearance_m = models.DecimalField(max_digits=5, decimal_places=2)
    allowed_asset_class = models.CharField(max_length=120, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.OPEN)
    notes = models.CharField(max_length=255, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["window_start", "code"]
        indexes = [
            models.Index(fields=("location", "window_start", "window_end")),
            models.Index(fields=("is_active", "status", "window_start")),
        ]

    def __str__(self) -> str:
        return self.code


class NavigationConstraintCheck(models.Model):
    class ConstraintType(models.TextChoices):
        TIDE = "tide", "Tide"
        BRIDGE = "bridge", "Bridge"

    class Status(models.TextChoices):
        CAN_CROSS = "can_cross", "Can cross"
        WAITING = "waiting", "Waiting"
        MARGINAL = "marginal", "Marginal"
        MISSED = "missed", "Missed"

    voyage = models.ForeignKey(
        OGVVoyage,
        on_delete=models.CASCADE,
        related_name="constraint_checks",
    )
    asset_code = models.CharField(max_length=80)
    route_segment = models.ForeignKey(
        RouteSegment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="constraint_checks",
    )
    constraint_type = models.CharField(max_length=20, choices=ConstraintType.choices)
    eta_gate = models.DateTimeField()
    window_start = models.DateTimeField()
    window_end = models.DateTimeField()
    draft_m = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    margin_minutes = models.IntegerField()
    status = models.CharField(max_length=32, choices=Status.choices)
    recovery_hint = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["eta_gate", "voyage__voyage_id"]
        indexes = [
            models.Index(fields=("constraint_type", "status")),
            models.Index(fields=("voyage", "constraint_type", "status")),
            models.Index(fields=("asset_code", "eta_gate")),
        ]

    def __str__(self) -> str:
        return f"{self.voyage.voyage_id} {self.constraint_type} {self.status}"


class ImportJob(models.Model):
    class ImportType(models.TextChoices):
        OGV_DEMAND = "ogv_demand", "OGV demand"
        CALENDAR = "calendar", "Calendar"
        LAYER_SEQUENCE = "layer_sequence", "Layer sequence"

    class Status(models.TextChoices):
        VALIDATED = "validated", "Validated"
        FAILED = "failed", "Failed"
        IMPORTED = "imported", "Imported"

    import_type = models.CharField(max_length=40, choices=ImportType.choices)
    filename = models.CharField(max_length=180, blank=True)
    source = models.CharField(max_length=120, default="manual")
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.VALIDATED)
    total_rows = models.PositiveIntegerField(default=0)
    valid_rows = models.PositiveIntegerField(default=0)
    error_rows = models.PositiveIntegerField(default=0)
    errors = models.JSONField(default=list, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="planning_import_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=("import_type", "status", "created_at")),
            models.Index(fields=("created_by", "created_at")),
        ]

    def __str__(self) -> str:
        return f"{self.import_type} {self.status}"
