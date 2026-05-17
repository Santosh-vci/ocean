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
