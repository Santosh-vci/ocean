from django.conf import settings
from django.db import models

from apps.masters.models import Barge, CTSAsset, Jetty, Location, RouteSegment, Tug
from apps.organizations.models import Organization
from apps.planning.models import CargoLayerStep, CargoRequirement, OGVVoyage


class Plan(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        ACTIVE = "active", "Active"
        ARCHIVED = "archived", "Archived"

    code = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="plans",
    )
    horizon_start = models.DateTimeField()
    horizon_end = models.DateTimeField()
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-horizon_start", "code"]

    def __str__(self) -> str:
        return self.code


class PlanVersion(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        GENERATED = "generated", "Generated"
        VALIDATED = "validated", "Validated"
        PROPOSED = "proposed", "Proposed"
        APPROVED = "approved", "Approved"
        PUBLISHED = "published", "Published"

    class ValidationStatus(models.TextChoices):
        FEASIBLE = "feasible", "Feasible"
        WARNING = "warning", "Warning"
        BLOCKED = "blocked", "Blocked"

    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="versions")
    version_no = models.PositiveIntegerField()
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    validation_status = models.CharField(
        max_length=32,
        choices=ValidationStatus.choices,
        default=ValidationStatus.FEASIBLE,
    )
    source_version = models.ForeignKey(
        "self",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="successor_versions",
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_plan_versions",
    )
    summary = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plan__code", "-version_no"]
        constraints = [
            models.UniqueConstraint(
                fields=("plan", "version_no"),
                name="unique_plan_version_no",
            )
        ]

    def __str__(self) -> str:
        return f"{self.plan.code} V{self.version_no}"


class Trip(models.Model):
    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        LOADING = "loading", "Loading"
        TRANSIT = "transit", "Transit"
        DISCHARGING = "discharging", "Discharging"
        COMPLETED = "completed", "Completed"
        BLOCKED = "blocked", "Blocked"

    plan_version = models.ForeignKey(PlanVersion, on_delete=models.CASCADE, related_name="trips")
    trip_id = models.CharField(max_length=80)
    sequence = models.PositiveIntegerField()
    voyage = models.ForeignKey(OGVVoyage, on_delete=models.PROTECT, related_name="scheduled_trips")
    cargo_requirement = models.ForeignKey(
        CargoRequirement,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="scheduled_trips",
    )
    cargo_layer_step = models.ForeignKey(
        CargoLayerStep,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="scheduled_trips",
    )
    origin_jetty = models.ForeignKey(
        Jetty,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="origin_trips",
    )
    destination_location = models.ForeignKey(
        Location,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="destination_trips",
    )
    planned_start = models.DateTimeField()
    planned_end = models.DateTimeField()
    planned_quantity_mt = models.PositiveIntegerField()
    loaded_quantity_mt = models.PositiveIntegerField(default=0)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PLANNED)
    selection_reason = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["plan_version", "sequence", "trip_id"]
        constraints = [
            models.UniqueConstraint(
                fields=("plan_version", "trip_id"),
                name="unique_plan_version_trip_id",
            )
        ]

    def __str__(self) -> str:
        return self.trip_id


class Assignment(models.Model):
    class Status(models.TextChoices):
        ASSIGNED = "assigned", "Assigned"
        WAITING_TIDE = "waiting_tide", "Waiting tide"
        WAITING_BRIDGE = "waiting_bridge", "Waiting bridge"
        LOADING = "loading", "Loading"
        IN_TRANSIT = "in_transit", "In transit"
        AT_CTS = "at_cts", "At CTS"
        BLOCKED = "blocked", "Blocked"

    trip = models.OneToOneField(Trip, on_delete=models.CASCADE, related_name="assignment")
    tug = models.ForeignKey(
        Tug,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="schedule_assignments",
    )
    barge = models.ForeignKey(
        Barge,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="schedule_assignments",
    )
    jetty = models.ForeignKey(
        Jetty,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="schedule_assignments",
    )
    cts = models.ForeignKey(
        CTSAsset,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="schedule_assignments",
    )
    route_segment = models.ForeignKey(
        RouteSegment,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="schedule_assignments",
    )
    owner_organization = models.ForeignKey(
        Organization,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="schedule_assignments",
    )
    planned_departure = models.DateTimeField()
    planned_arrival = models.DateTimeField()
    tug_status = models.CharField(max_length=80, blank=True)
    barge_status = models.CharField(max_length=80, blank=True)
    next_constraint = models.CharField(max_length=180, blank=True)
    next_action = models.CharField(max_length=180, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ASSIGNED)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["planned_departure", "trip__trip_id"]

    def __str__(self) -> str:
        return f"{self.trip.trip_id} assignment"


class ScheduleEvent(models.Model):
    class EventType(models.TextChoices):
        LOAD_START = "load_start", "Load start"
        LOAD_COMPLETE = "load_complete", "Load complete"
        DEPART_JETTY = "depart_jetty", "Depart jetty"
        BRIDGE_CROSS = "bridge_cross", "Bridge cross"
        TIDE_GATE = "tide_gate", "Tide gate"
        ARRIVE_CTS = "arrive_cts", "Arrive CTS"
        DISCHARGE_START = "discharge_start", "Discharge start"
        DISCHARGE_COMPLETE = "discharge_complete", "Discharge complete"

    class Status(models.TextChoices):
        PLANNED = "planned", "Planned"
        ACTUAL = "actual", "Actual"
        DELAYED = "delayed", "Delayed"
        MISSED = "missed", "Missed"

    trip = models.ForeignKey(Trip, on_delete=models.CASCADE, related_name="events")
    sequence = models.PositiveIntegerField()
    event_type = models.CharField(max_length=40, choices=EventType.choices)
    planned_at = models.DateTimeField()
    actual_at = models.DateTimeField(null=True, blank=True)
    location_label = models.CharField(max_length=120, blank=True)
    resource_code = models.CharField(max_length=80, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PLANNED)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["trip", "sequence"]
        constraints = [
            models.UniqueConstraint(
                fields=("trip", "sequence"),
                name="unique_trip_event_sequence",
            )
        ]

    def __str__(self) -> str:
        return f"{self.trip.trip_id} {self.event_type}"


class Conflict(models.Model):
    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        related_name="conflicts",
    )
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="conflicts",
    )
    code = models.CharField(max_length=80)
    severity = models.CharField(max_length=32, choices=Severity.choices)
    object_type = models.CharField(max_length=80, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    message = models.CharField(max_length=255)
    is_blocking = models.BooleanField(default=True)
    resolved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-is_blocking", "severity", "code"]
        indexes = [models.Index(fields=("code", "severity", "is_blocking"))]

    def __str__(self) -> str:
        return f"{self.code}: {self.message}"
