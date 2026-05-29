import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone

from apps.masters.models import Barge, CTSAsset, Jetty, Location, RouteSegment, Tug
from apps.organizations.models import Organization
from apps.planning.models import CargoLayerStep, CargoRequirement, OGVVoyage


def _reference(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def recovery_snapshot_reference() -> str:
    return _reference("RIS")


def optimizer_run_reference() -> str:
    return _reference("OPT")


def recovery_recommendation_reference() -> str:
    return _reference("REC")


def recovery_action_reference() -> str:
    return _reference("RAC")


def recommendation_evaluation_reference() -> str:
    return _reference("REV")


def root_cause_assessment_reference() -> str:
    return _reference("RCA")


def publishability_assessment_reference() -> str:
    return _reference("PUB")


def global_optimization_run_reference() -> str:
    return _reference("GOPT")


def global_optimization_candidate_reference() -> str:
    return _reference("GCAN")


def commercial_projection_run_reference() -> str:
    return _reference("CPR")


def customer_safe_commercial_projection_reference() -> str:
    return _reference("CSP")


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
        SUPERSEDED = "superseded", "Superseded"

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
        indexes = [
            models.Index(fields=("plan_version", "status", "planned_start")),
            models.Index(fields=("plan_version", "planned_start")),
            models.Index(fields=("voyage", "plan_version")),
        ]
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
        indexes = [
            models.Index(fields=("status", "planned_departure")),
            models.Index(fields=("owner_organization", "planned_departure")),
        ]

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
        indexes = [
            models.Index(fields=("planned_at", "status")),
            models.Index(fields=("resource_code", "planned_at")),
        ]
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


class OverrideRequest(models.Model):
    class ReasonCode(models.TextChoices):
        TUG_BREAKDOWN = "tug_breakdown", "Tug breakdown"
        BARGE_UNAVAILABLE = "barge_unavailable", "Barge unavailable"
        JETTY_DELAY = "jetty_delay", "Jetty delay"
        TIDE_BRIDGE_RECOVERY = "tide_bridge_recovery", "Tide / bridge recovery"
        GRADE_SEQUENCE_RECOVERY = "grade_sequence_recovery", "Grade sequence recovery"
        MANUAL_CORRECTION = "manual_correction", "Manual correction"

    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPLIED = "applied", "Applied"
        REJECTED = "rejected", "Rejected"
        SUPERSEDED = "superseded", "Superseded"

    plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        related_name="override_requests",
    )
    trip = models.ForeignKey(
        Trip,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="override_requests",
    )
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="override_requests",
    )
    reason_code = models.CharField(max_length=64, choices=ReasonCode.choices)
    description = models.CharField(max_length=255)
    requested_change = models.JSONField(default=dict, blank=True)
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_schedule_overrides",
    )
    applied_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="applied_schedule_overrides",
    )
    applied_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=("plan_version", "status", "reason_code"))]

    def __str__(self) -> str:
        return f"{self.reason_code} override on {self.plan_version}"


class ImpactChainAssessment(models.Model):
    class SourceKind(models.TextChoices):
        OVERRIDE = "override", "Override"
        CONFLICT = "conflict", "Conflict"
        PLANNING_FORECAST = "planning_forecast", "Planning forecast"
        SIMULATION = "simulation", "Simulation"

    class Status(models.TextChoices):
        OK = "ok", "OK"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    assessment_id = models.CharField(max_length=96, unique=True)
    plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        related_name="impact_chain_assessments",
    )
    trip = models.ForeignKey(
        Trip,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="impact_chain_assessments",
    )
    assignment = models.ForeignKey(
        Assignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="impact_chain_assessments",
    )
    override_request = models.OneToOneField(
        OverrideRequest,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="impact_assessment",
    )
    source_kind = models.CharField(
        max_length=40,
        choices=SourceKind.choices,
        default=SourceKind.OVERRIDE,
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.OK)
    delay_minutes = models.IntegerField(default=0)
    nodes = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=("plan_version", "source_kind", "status")),
            models.Index(fields=("trip", "source_kind", "status")),
        ]

    def __str__(self) -> str:
        return self.assessment_id


class RecoveryInputSnapshot(models.Model):
    class SourceKind(models.TextChoices):
        MANUAL = "manual", "Manual"
        CONFLICT = "conflict", "Conflict"
        OVERRIDE = "override", "Override"
        TRACKING_ALERT = "tracking_alert", "Tracking alert"
        OPERATIONAL_EVENT = "operational_event", "Operational event"
        SCENARIO = "scenario", "Scenario"

    snapshot_id = models.CharField(
        max_length=96,
        unique=True,
        default=recovery_snapshot_reference,
    )
    plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        related_name="recovery_input_snapshots",
    )
    source_kind = models.CharField(
        max_length=40,
        choices=SourceKind.choices,
        default=SourceKind.MANUAL,
    )
    source_ref = models.CharField(max_length=120, blank=True)
    source_conflict = models.ForeignKey(
        Conflict,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_input_snapshots",
    )
    source_override = models.ForeignKey(
        OverrideRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_input_snapshots",
    )
    source_tracking_alert = models.ForeignKey(
        "telemetry.TrackingAlert",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_input_snapshots",
    )
    source_operational_event = models.ForeignKey(
        "operations.ConfirmedOperationalEvent",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_input_snapshots",
    )
    source_scenario = models.ForeignKey(
        "SimulationScenario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_input_snapshots",
    )
    input_hash = models.CharField(max_length=64, blank=True)
    active_conflict_count = models.PositiveIntegerField(default=0)
    confirmed_event_count = models.PositiveIntegerField(default=0)
    tracking_alert_count = models.PositiveIntegerField(default=0)
    resource_state = models.JSONField(default=dict, blank=True)
    event_state = models.JSONField(default=dict, blank=True)
    constraint_state = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    captured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="captured_recovery_input_snapshots",
    )
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-generated_at", "-id"]
        indexes = [
            models.Index(fields=("plan_version", "source_kind", "generated_at")),
            models.Index(fields=("source_kind", "source_ref")),
            models.Index(fields=("input_hash",)),
        ]

    @property
    def organization(self):
        return self.plan_version.plan.organization

    def __str__(self) -> str:
        return self.snapshot_id


class OptimizerRun(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    run_id = models.CharField(
        max_length=96,
        unique=True,
        default=optimizer_run_reference,
    )
    input_snapshot = models.ForeignKey(
        RecoveryInputSnapshot,
        on_delete=models.CASCADE,
        related_name="optimizer_runs",
    )
    plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        related_name="optimizer_runs",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    algorithm_version = models.CharField(max_length=80, default="phase5.0-foundation")
    objective_weights = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="started_optimizer_runs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=("plan_version", "status", "created_at")),
            models.Index(fields=("input_snapshot", "status")),
            models.Index(fields=("algorithm_version", "status")),
        ]

    @property
    def organization(self):
        return self.plan_version.plan.organization

    def __str__(self) -> str:
        return self.run_id


class RecoveryRecommendation(models.Model):
    class Status(models.TextChoices):
        CANDIDATE = "candidate", "Candidate"
        SHORTLISTED = "shortlisted", "Shortlisted"
        SELECTED = "selected", "Selected"
        DISMISSED = "dismissed", "Dismissed"
        MATERIALIZED = "materialized", "Materialized"

    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    recommendation_id = models.CharField(
        max_length=96,
        unique=True,
        default=recovery_recommendation_reference,
    )
    optimizer_run = models.ForeignKey(
        OptimizerRun,
        on_delete=models.CASCADE,
        related_name="recommendations",
    )
    rank = models.PositiveIntegerField()
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.CANDIDATE,
    )
    risk_level = models.CharField(
        max_length=32,
        choices=RiskLevel.choices,
        default=RiskLevel.MEDIUM,
    )
    score = models.DecimalField(max_digits=8, decimal_places=3, default=0)
    summary = models.CharField(max_length=255)
    explanation = models.JSONField(default=list, blank=True)
    scenario = models.ForeignKey(
        "SimulationScenario",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="source_recommendations",
    )
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["optimizer_run", "rank", "id"]
        indexes = [
            models.Index(fields=("optimizer_run", "status", "rank")),
            models.Index(fields=("risk_level", "score")),
            models.Index(fields=("status", "created_at")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("optimizer_run", "rank"),
                name="unique_optimizer_run_recommendation_rank",
            )
        ]

    @property
    def organization(self):
        return self.optimizer_run.organization

    def __str__(self) -> str:
        return self.recommendation_id


class RecoveryAction(models.Model):
    class ActionType(models.TextChoices):
        DELAY_TRIP = "delay_trip", "Delay trip"
        RESEQUENCE_TRIP = "resequence_trip", "Resequence trip"
        REASSIGN_TUG = "reassign_tug", "Reassign tug"
        REASSIGN_BARGE = "reassign_barge", "Reassign barge"
        REASSIGN_CTS = "reassign_cts", "Reassign CTS"
        SHIFT_WINDOW = "shift_window", "Shift window"
        HOLD_AT_ANCHORAGE = "hold_at_anchorage", "Hold at anchorage"
        NOOP = "noop", "No operation"

    action_id = models.CharField(
        max_length=96,
        unique=True,
        default=recovery_action_reference,
    )
    recommendation = models.ForeignKey(
        RecoveryRecommendation,
        on_delete=models.CASCADE,
        related_name="actions",
    )
    sequence = models.PositiveIntegerField()
    action_type = models.CharField(max_length=48, choices=ActionType.choices)
    target_trip = models.ForeignKey(
        Trip,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_actions",
    )
    target_assignment = models.ForeignKey(
        Assignment,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recovery_actions",
    )
    before_state = models.JSONField(default=dict, blank=True)
    after_state = models.JSONField(default=dict, blank=True)
    constraints_checked = models.JSONField(default=list, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recommendation", "sequence", "id"]
        indexes = [
            models.Index(fields=("recommendation", "sequence")),
            models.Index(fields=("action_type", "created_at")),
            models.Index(fields=("target_trip", "action_type")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("recommendation", "sequence"),
                name="unique_recommendation_action_sequence",
            )
        ]

    @property
    def organization(self):
        return self.recommendation.organization

    def __str__(self) -> str:
        return self.action_id


class RecommendationEvaluation(models.Model):
    evaluation_id = models.CharField(
        max_length=96,
        unique=True,
        default=recommendation_evaluation_reference,
    )
    recommendation = models.OneToOneField(
        RecoveryRecommendation,
        on_delete=models.CASCADE,
        related_name="evaluation",
    )
    delay_minutes = models.IntegerField(default=0)
    missed_windows = models.PositiveIntegerField(default=0)
    resource_conflicts = models.PositiveIntegerField(default=0)
    utilization_delta_pct = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    hard_constraints_passed = models.BooleanField(default=True)
    score_breakdown = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["recommendation__optimizer_run", "recommendation__rank"]
        indexes = [
            models.Index(fields=("hard_constraints_passed", "confidence_score")),
            models.Index(fields=("delay_minutes", "missed_windows")),
        ]

    @property
    def organization(self):
        return self.recommendation.organization

    def __str__(self) -> str:
        return self.evaluation_id


class RootCauseRepairAssessment(models.Model):
    class Status(models.TextChoices):
        ADDRESSES_CAUSE = "addresses_cause", "Addresses cause"
        MITIGATES_CAUSE = "mitigates_cause", "Mitigates cause"
        DOES_NOT_ADDRESS_CAUSE = "does_not_address_cause", "Does not address cause"
        UNKNOWN = "unknown", "Unknown"

    assessment_id = models.CharField(
        max_length=96,
        unique=True,
        default=root_cause_assessment_reference,
    )
    recommendation = models.OneToOneField(
        RecoveryRecommendation,
        on_delete=models.CASCADE,
        related_name="root_cause_assessment",
    )
    source_kind = models.CharField(max_length=40, blank=True)
    source_ref = models.CharField(max_length=120, blank=True)
    source_cause_type = models.CharField(max_length=80, blank=True)
    status = models.CharField(
        max_length=40,
        choices=Status.choices,
        default=Status.UNKNOWN,
    )
    required_resolution = models.JSONField(default=dict, blank=True)
    observed_resolution = models.JSONField(default=dict, blank=True)
    residual_risk = models.JSONField(default=dict, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    assessed_at = models.DateTimeField(default=timezone.now)
    assessed_by_algorithm_version = models.CharField(max_length=96)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-assessed_at", "-id"]
        indexes = [
            models.Index(fields=("source_cause_type", "status")),
            models.Index(fields=("status", "assessed_at")),
            models.Index(fields=("assessed_at",)),
        ]

    @property
    def organization(self):
        return self.recommendation.organization

    def __str__(self) -> str:
        return self.assessment_id


class PublishabilityAssessment(models.Model):
    class Status(models.TextChoices):
        PUBLISHABLE = "publishable", "Publishable"
        WARNING = "warning", "Warning"
        BLOCKED = "blocked", "Blocked"

    assessment_id = models.CharField(
        max_length=96,
        unique=True,
        default=publishability_assessment_reference,
    )
    plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        related_name="publishability_assessments",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.BLOCKED,
    )
    blocking_reason_count = models.PositiveIntegerField(default=0)
    warning_count = models.PositiveIntegerField(default=0)
    approval_status = models.CharField(max_length=40, blank=True)
    conflict_status = models.CharField(max_length=40, blank=True)
    telemetry_status = models.CharField(max_length=40, blank=True)
    cargo_sequence_status = models.CharField(max_length=40, blank=True)
    operating_window_status = models.CharField(max_length=40, blank=True)
    recommendation_origin_status = models.CharField(max_length=40, blank=True)
    checked_at = models.DateTimeField(default=timezone.now)
    checked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="checked_publishability_assessments",
    )
    algorithm_version = models.CharField(max_length=96)
    details = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-checked_at", "-id"]
        indexes = [
            models.Index(fields=("plan_version", "status", "checked_at")),
            models.Index(fields=("status", "checked_at")),
            models.Index(fields=("checked_at",)),
            models.Index(fields=("approval_status", "conflict_status")),
            models.Index(fields=("recommendation_origin_status", "telemetry_status")),
        ]

    @property
    def organization(self):
        return self.plan_version.plan.organization

    def __str__(self) -> str:
        return self.assessment_id


class GlobalObjectiveProfile(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DEPRECATED = "deprecated", "Deprecated"

    profile_key = models.CharField(max_length=96, unique=True)
    name = models.CharField(max_length=160)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    weights = models.JSONField(default=dict, blank=True)
    constraints = models.JSONField(default=dict, blank=True)
    source = models.CharField(max_length=80, default="settings")
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


class GlobalOptimizationRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    run_id = models.CharField(
        max_length=96,
        unique=True,
        default=global_optimization_run_reference,
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.QUEUED)
    plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="global_optimization_runs",
    )
    objective_profile = models.ForeignKey(
        GlobalObjectiveProfile,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="runs",
    )
    objective_weights = models.JSONField(default=dict, blank=True)
    input_signature = models.CharField(max_length=64, blank=True)
    input_summary = models.JSONField(default=dict, blank=True)
    algorithm_version = models.CharField(
        max_length=96,
        default="phase6.5-global-optimizer-scaffold",
    )
    audit_lineage = models.JSONField(default=dict, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="started_global_optimization_runs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=("status", "created_at")),
            models.Index(fields=("plan_version", "status", "created_at")),
            models.Index(fields=("objective_profile", "status")),
            models.Index(fields=("algorithm_version", "status")),
            models.Index(fields=("input_signature",)),
        ]

    @property
    def organization(self):
        return self.plan_version.plan.organization if self.plan_version else None

    def __str__(self) -> str:
        return self.run_id


class GlobalOptimizationCandidate(models.Model):
    class RiskLevel(models.TextChoices):
        LOW = "low", "Low"
        MEDIUM = "medium", "Medium"
        HIGH = "high", "High"
        CRITICAL = "critical", "Critical"

    candidate_id = models.CharField(
        max_length=96,
        unique=True,
        default=global_optimization_candidate_reference,
    )
    run = models.ForeignKey(
        GlobalOptimizationRun,
        on_delete=models.CASCADE,
        related_name="candidates",
    )
    rank = models.PositiveIntegerField()
    score = models.DecimalField(max_digits=9, decimal_places=3, default=0)
    risk_level = models.CharField(
        max_length=32,
        choices=RiskLevel.choices,
        default=RiskLevel.MEDIUM,
    )
    summary = models.CharField(max_length=255)
    objective_score_breakdown = models.JSONField(default=dict, blank=True)
    changed_assignments = models.JSONField(default=list, blank=True)
    trip_sequence_changes = models.JSONField(default=list, blank=True)
    projected_impacts = models.JSONField(default=dict, blank=True)
    unresolved_risks = models.JSONField(default=list, blank=True)
    approval_lineage = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["run", "rank", "id"]
        indexes = [
            models.Index(fields=("run", "rank")),
            models.Index(fields=("risk_level", "score")),
            models.Index(fields=("created_at",)),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("run", "rank"),
                name="unique_global_optimization_candidate_rank",
            )
        ]

    @property
    def organization(self):
        return self.run.organization

    def __str__(self) -> str:
        return self.candidate_id


class CommercialProjectionRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    run_id = models.CharField(
        max_length=96,
        unique=True,
        default=commercial_projection_run_reference,
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.QUEUED)
    plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="commercial_projection_runs",
    )
    telemetry_trust_profile = models.ForeignKey(
        "telemetry.TelemetryTrustProfile",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commercial_projection_runs",
    )
    input_signature = models.CharField(max_length=64, blank=True)
    input_summary = models.JSONField(default=dict, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    algorithm_version = models.CharField(
        max_length=96,
        default="phase6.6-commercial-projection",
    )
    audit_lineage = models.JSONField(default=dict, blank=True)
    generated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="generated_commercial_projection_runs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=("status", "created_at")),
            models.Index(fields=("plan_version", "status", "created_at")),
            models.Index(fields=("telemetry_trust_profile", "status")),
            models.Index(fields=("algorithm_version", "status")),
            models.Index(fields=("input_signature",)),
        ]

    @property
    def organization(self):
        return self.plan_version.plan.organization if self.plan_version else None

    def __str__(self) -> str:
        return self.run_id


class CustomerSafeCommercialProjection(models.Model):
    class Status(models.TextChoices):
        ON_TRACK = "on_track", "On track"
        WATCH = "watch", "Watch"
        AT_RISK = "at_risk", "At risk"
        BLOCKED = "blocked", "Blocked"
        UNKNOWN = "unknown", "Unknown"

    class CommitmentRiskLevel(models.TextChoices):
        LOW = "low", "Low"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"
        UNKNOWN = "unknown", "Unknown"

    projection_id = models.CharField(
        max_length=96,
        unique=True,
        default=customer_safe_commercial_projection_reference,
    )
    run = models.ForeignKey(
        CommercialProjectionRun,
        on_delete=models.CASCADE,
        related_name="projections",
    )
    voyage = models.ForeignKey(
        OGVVoyage,
        on_delete=models.CASCADE,
        related_name="commercial_projections",
    )
    trip = models.ForeignKey(
        Trip,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="commercial_projections",
    )
    status = models.CharField(
        max_length=32,
        choices=Status.choices,
        default=Status.UNKNOWN,
    )
    customer_safe_eta = models.DateTimeField(null=True, blank=True)
    eta_band_start = models.DateTimeField(null=True, blank=True)
    eta_band_end = models.DateTimeField(null=True, blank=True)
    laycan_status = models.CharField(max_length=32, blank=True)
    laycan_variance_minutes = models.IntegerField(default=0)
    projected_demurrage_exposure_minutes = models.PositiveIntegerField(default=0)
    projected_demurrage_exposure_usd = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=0,
    )
    commitment_risk_level = models.CharField(
        max_length=32,
        choices=CommitmentRiskLevel.choices,
        default=CommitmentRiskLevel.UNKNOWN,
    )
    telemetry_trust_status = models.CharField(max_length=48, blank=True)
    confidence_score = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    customer_safe_to_share = models.BooleanField(default=False)
    projection_only_disclaimer = models.CharField(max_length=255)
    details = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["voyage__laycan_start", "voyage__voyage_id", "id"]
        indexes = [
            models.Index(fields=("run", "status")),
            models.Index(fields=("voyage", "run")),
            models.Index(fields=("commitment_risk_level", "status")),
            models.Index(fields=("customer_safe_to_share", "status")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("run", "voyage"),
                name="unique_commercial_projection_run_voyage",
            )
        ]

    @property
    def organization(self):
        return self.run.organization

    def __str__(self) -> str:
        return self.projection_id


class ApprovalRequest(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PUBLISHED = "published", "Published"
        CANCELED = "canceled", "Canceled"

    request_id = models.CharField(max_length=80, unique=True)
    plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        related_name="approval_requests",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    required_authorities = models.JSONField(default=list, blank=True)
    reason = models.CharField(max_length=255)
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="requested_plan_approvals",
    )
    decided_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=("status", "created_at")),
            models.Index(fields=("plan_version", "status", "created_at")),
        ]

    def __str__(self) -> str:
        return self.request_id


class ApprovalDecision(models.Model):
    class Decision(models.TextChoices):
        APPROVE = "approve", "Approve"
        REJECT = "reject", "Reject"
        RETURN = "return", "Return"
        ESCALATE = "escalate", "Escalate"

    class AuthorityRole(models.TextChoices):
        BERAU_SCHEDULER = "berau_scheduler", "Berau Scheduler"
        ABL_DISPATCHER = "abl_dispatcher", "ABL Dispatcher"
        JOINT_CONTROL = "joint_control", "Joint Control"

    approval_request = models.ForeignKey(
        ApprovalRequest,
        on_delete=models.CASCADE,
        related_name="decisions",
    )
    authority_role = models.CharField(max_length=64, choices=AuthorityRole.choices)
    decision = models.CharField(max_length=32, choices=Decision.choices)
    comments = models.CharField(max_length=255, blank=True)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plan_approval_decisions",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="plan_approval_decisions",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            models.UniqueConstraint(
                fields=("approval_request", "authority_role"),
                name="unique_approval_decision_authority",
            )
        ]

    def __str__(self) -> str:
        return f"{self.approval_request.request_id} {self.authority_role}"


class PublishedPlanSnapshot(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        SUPERSEDED = "superseded", "Superseded"

    snapshot_id = models.CharField(max_length=80, unique=True)
    plan = models.ForeignKey(Plan, on_delete=models.CASCADE, related_name="published_snapshots")
    plan_version = models.OneToOneField(
        PlanVersion,
        on_delete=models.PROTECT,
        related_name="published_snapshot",
    )
    approval_request = models.ForeignKey(
        ApprovalRequest,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="published_snapshots",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    payload = models.JSONField(default=dict)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="published_plan_snapshots",
    )
    published_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-published_at"]
        indexes = [
            models.Index(fields=("plan", "status")),
            models.Index(fields=("status", "published_at")),
        ]

    def __str__(self) -> str:
        return self.snapshot_id


class ExportJob(models.Model):
    class ExportType(models.TextChoices):
        PLAN = "plan", "Plan"
        CONFLICT = "conflict", "Conflict"
        SCENARIO_DIFF = "scenario_diff", "Scenario diff"
        AUDIT = "audit", "Audit"

    class ExportFormat(models.TextChoices):
        JSON = "json", "JSON"
        CSV = "csv", "CSV"
        PRINT = "print", "Printable text"

    class Status(models.TextChoices):
        GENERATED = "generated", "Generated"
        FAILED = "failed", "Failed"

    export_id = models.CharField(max_length=96, unique=True)
    export_type = models.CharField(max_length=32, choices=ExportType.choices)
    export_format = models.CharField(max_length=16, choices=ExportFormat.choices)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.GENERATED)
    plan_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="export_jobs",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="schedule_exports",
    )
    storage_bucket = models.CharField(max_length=120)
    storage_key = models.CharField(max_length=512)
    file_name = models.CharField(max_length=220)
    content_type = models.CharField(max_length=120)
    checksum_sha256 = models.CharField(max_length=64)
    size_bytes = models.PositiveIntegerField(default=0)
    record_count = models.PositiveIntegerField(default=0)
    scope = models.JSONField(default=dict, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    failure_reason = models.CharField(max_length=255, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_export_jobs",
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=("export_type", "status", "created_at")),
            models.Index(fields=("organization", "created_at")),
        ]

    def __str__(self) -> str:
        return self.export_id


class SimulationScenario(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        SIMULATED = "simulated", "Simulated"
        PROPOSED = "proposed", "Proposed"
        CANCELED = "canceled", "Canceled"

    class SourceKind(models.TextChoices):
        MANUAL = "manual", "Manual"
        CONFLICT = "conflict", "Conflict"
        OVERRIDE = "override", "Override"
        TRACKING_ALERT = "tracking_alert", "Tracking alert"

    scenario_id = models.CharField(max_length=80, unique=True)
    name = models.CharField(max_length=160)
    scenario_type = models.CharField(max_length=80)
    baseline_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        related_name="baseline_scenarios",
    )
    scenario_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="scenario_outputs",
    )
    source_conflict = models.ForeignKey(
        Conflict,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="simulation_scenarios",
    )
    source_override = models.ForeignKey(
        OverrideRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="simulation_scenarios",
    )
    source_kind = models.CharField(
        max_length=32,
        choices=SourceKind.choices,
        default=SourceKind.MANUAL,
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.DRAFT)
    recovery_actions = models.JSONField(default=list, blank=True)
    impact_summary = models.JSONField(default=dict, blank=True)
    delta_summary = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_simulation_scenarios",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=("status", "created_at"))]

    def __str__(self) -> str:
        return self.scenario_id


class ScenarioAssumption(models.Model):
    class Kind(models.TextChoices):
        TRIP_DELAY = "trip_delay", "Trip delay"
        ASSET_OUTAGE = "asset_outage", "Asset outage"
        RATE_CHANGE = "rate_change", "Rate change"
        WINDOW_CHANGE = "window_change", "Window change"
        OGV_ETA_CHANGE = "ogv_eta_change", "OGV ETA change"
        MANUAL_REASSIGNMENT = "manual_reassignment", "Manual reassignment"

    class ScopeType(models.TextChoices):
        TRIP = "trip", "Trip"
        ASSIGNMENT = "assignment", "Assignment"
        ASSET = "asset", "Asset"
        WINDOW = "window", "Window"
        OGV = "ogv", "OGV"

    scenario = models.ForeignKey(
        SimulationScenario,
        on_delete=models.CASCADE,
        related_name="assumptions",
    )
    assumption_id = models.CharField(max_length=96, unique=True)
    kind = models.CharField(max_length=48, choices=Kind.choices)
    scope_type = models.CharField(max_length=32, choices=ScopeType.choices)
    scope_id = models.PositiveBigIntegerField(null=True, blank=True)
    payload = models.JSONField(default=dict, blank=True)
    effective_from = models.DateTimeField(null=True, blank=True)
    effective_to = models.DateTimeField(null=True, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_scenario_assumptions",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at", "id"]
        indexes = [
            models.Index(fields=("scenario", "kind", "created_at")),
            models.Index(fields=("scope_type", "scope_id")),
        ]

    @property
    def organization(self):
        return self.scenario.baseline_version.plan.organization

    def __str__(self) -> str:
        return self.assumption_id


class ScenarioRun(models.Model):
    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        RUNNING = "running", "Running"
        SUCCEEDED = "succeeded", "Succeeded"
        FAILED = "failed", "Failed"
        CANCELED = "canceled", "Canceled"

    scenario = models.ForeignKey(
        SimulationScenario,
        on_delete=models.CASCADE,
        related_name="runs",
    )
    run_id = models.CharField(max_length=96, unique=True)
    baseline_version = models.ForeignKey(
        PlanVersion,
        on_delete=models.CASCADE,
        related_name="scenario_runs",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.QUEUED)
    algorithm_version = models.CharField(max_length=80)
    input_hash = models.CharField(max_length=64)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    summary = models.JSONField(default=dict, blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="created_scenario_runs",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=("scenario", "status", "created_at")),
            models.Index(fields=("baseline_version", "created_at")),
            models.Index(fields=("input_hash",)),
        ]

    @property
    def organization(self):
        return self.scenario.baseline_version.plan.organization

    def __str__(self) -> str:
        return self.run_id


class ScenarioTripProjection(models.Model):
    run = models.ForeignKey(
        ScenarioRun,
        on_delete=models.CASCADE,
        related_name="trip_projections",
    )
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="scenario_trip_projections",
    )
    baseline_start = models.DateTimeField()
    baseline_end = models.DateTimeField()
    projected_start = models.DateTimeField()
    projected_end = models.DateTimeField()
    projected_status = models.CharField(max_length=32)
    delay_minutes = models.IntegerField(default=0)
    assignment_delta = models.JSONField(default=dict, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["trip__sequence", "trip__trip_id"]
        indexes = [
            models.Index(fields=("run", "projected_start")),
            models.Index(fields=("trip", "delay_minutes")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("run", "trip"),
                name="unique_scenario_run_trip_projection",
            )
        ]

    @property
    def organization(self):
        return self.run.organization

    def __str__(self) -> str:
        return f"{self.run.run_id} {self.trip.trip_id}"


class ScenarioEventProjection(models.Model):
    run = models.ForeignKey(
        ScenarioRun,
        on_delete=models.CASCADE,
        related_name="event_projections",
    )
    event = models.ForeignKey(
        ScheduleEvent,
        on_delete=models.CASCADE,
        related_name="scenario_event_projections",
    )
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        related_name="scenario_event_projections",
    )
    event_type = models.CharField(max_length=40)
    baseline_at = models.DateTimeField()
    projected_at = models.DateTimeField()
    projected_status = models.CharField(max_length=32)
    delay_minutes = models.IntegerField(default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["trip__sequence", "event__sequence"]
        indexes = [
            models.Index(fields=("run", "projected_at")),
            models.Index(fields=("trip", "event_type")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("run", "event"),
                name="unique_scenario_run_event_projection",
            )
        ]

    @property
    def organization(self):
        return self.run.organization

    def __str__(self) -> str:
        return f"{self.run.run_id} {self.event}"


class ScenarioConstraintEvaluation(models.Model):
    class Severity(models.TextChoices):
        INFO = "info", "Info"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    run = models.ForeignKey(
        ScenarioRun,
        on_delete=models.CASCADE,
        related_name="constraint_evaluations",
    )
    evaluation_id = models.CharField(max_length=120, unique=True)
    trip = models.ForeignKey(
        Trip,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="scenario_constraint_evaluations",
    )
    code = models.CharField(max_length=80)
    severity = models.CharField(max_length=32, choices=Severity.choices)
    affected_object_type = models.CharField(max_length=48)
    affected_object_id = models.CharField(max_length=120, blank=True)
    baseline_value = models.JSONField(default=dict, blank=True)
    projected_value = models.JSONField(default=dict, blank=True)
    margin_minutes = models.IntegerField(null=True, blank=True)
    source_assumption_ids = models.JSONField(default=list, blank=True)
    message = models.CharField(max_length=255)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-severity", "code", "trip__sequence", "id"]
        indexes = [
            models.Index(fields=("run", "severity", "code")),
            models.Index(fields=("trip", "severity")),
        ]

    @property
    def organization(self):
        return self.run.organization

    def __str__(self) -> str:
        return self.evaluation_id


class ScenarioOgvProjection(models.Model):
    class RiskStatus(models.TextChoices):
        OK = "ok", "OK"
        WARNING = "warning", "Warning"
        CRITICAL = "critical", "Critical"

    run = models.ForeignKey(
        ScenarioRun,
        on_delete=models.CASCADE,
        related_name="ogv_projections",
    )
    voyage = models.ForeignKey(
        OGVVoyage,
        on_delete=models.CASCADE,
        related_name="scenario_ogv_projections",
    )
    baseline_completion_at = models.DateTimeField()
    projected_completion_at = models.DateTimeField()
    completion_delta_minutes = models.IntegerField(default=0)
    laycan_end = models.DateTimeField()
    baseline_demurrage_minutes = models.IntegerField(default=0)
    projected_demurrage_minutes = models.IntegerField(default=0)
    demurrage_delta_usd = models.DecimalField(max_digits=14, decimal_places=2, default=0)
    risk_status = models.CharField(max_length=32, choices=RiskStatus.choices, default=RiskStatus.OK)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["voyage__laycan_start", "voyage__voyage_id"]
        indexes = [
            models.Index(fields=("run", "risk_status")),
            models.Index(fields=("voyage", "run")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("run", "voyage"),
                name="unique_scenario_run_ogv_projection",
            )
        ]

    @property
    def organization(self):
        return self.run.organization

    def __str__(self) -> str:
        return f"{self.run.run_id} {self.voyage.voyage_id}"


class ScenarioResourceUtilization(models.Model):
    class ResourceType(models.TextChoices):
        TUG = "tug", "Tug"
        BARGE = "barge", "Barge"
        JETTY = "jetty", "Jetty"
        CTS = "cts", "CTS"

    run = models.ForeignKey(
        ScenarioRun,
        on_delete=models.CASCADE,
        related_name="resource_utilizations",
    )
    resource_type = models.CharField(max_length=32, choices=ResourceType.choices)
    resource_code = models.CharField(max_length=80)
    baseline_occupied_minutes = models.IntegerField(default=0)
    projected_occupied_minutes = models.IntegerField(default=0)
    baseline_idle_minutes = models.IntegerField(default=0)
    projected_idle_minutes = models.IntegerField(default=0)
    waiting_minutes = models.IntegerField(default=0)
    utilization_delta_pct = models.DecimalField(max_digits=7, decimal_places=2, default=0)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["resource_type", "resource_code"]
        indexes = [
            models.Index(fields=("run", "resource_type")),
            models.Index(fields=("resource_type", "resource_code")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("run", "resource_type", "resource_code"),
                name="unique_scenario_run_resource_utilization",
            )
        ]

    @property
    def organization(self):
        return self.run.organization

    def __str__(self) -> str:
        return f"{self.run.run_id} {self.resource_type}:{self.resource_code}"
