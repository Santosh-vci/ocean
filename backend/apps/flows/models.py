import uuid

from django.conf import settings
from django.db import models


def _reference(prefix: str) -> str:
    return f"{prefix}-{uuid.uuid4().hex[:12].upper()}"


def flow_run_reference() -> str:
    return _reference("FLOW")


def flow_event_reference() -> str:
    return _reference("FEV")


class FlowDefinition(models.Model):
    class Status(models.TextChoices):
        ACTIVE = "active", "Active"
        DEPRECATED = "deprecated", "Deprecated"

    flow_key = models.CharField(max_length=120, unique=True)
    name = models.CharField(max_length=180)
    description = models.CharField(max_length=255, blank=True)
    version = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.ACTIVE)
    entry_route = models.CharField(max_length=180)
    steps = models.JSONField(default=list, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["flow_key", "version"]
        indexes = [
            models.Index(fields=("flow_key", "status")),
            models.Index(fields=("status", "updated_at")),
        ]

    def __str__(self) -> str:
        return self.flow_key


class FlowRun(models.Model):
    class Status(models.TextChoices):
        NOT_STARTED = "not_started", "Not started"
        ACTIVE = "active", "Active"
        BLOCKED = "blocked", "Blocked"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"

    run_id = models.CharField(max_length=96, unique=True, default=flow_run_reference)
    flow_definition = models.ForeignKey(
        FlowDefinition,
        on_delete=models.PROTECT,
        related_name="runs",
    )
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.NOT_STARTED)
    current_step_key = models.CharField(max_length=120, blank=True)
    subject_type = models.CharField(max_length=80, blank=True)
    subject_id = models.CharField(max_length=80, blank=True)
    started_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="started_flow_runs",
    )
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=("status", "current_step_key")),
            models.Index(fields=("subject_type", "subject_id")),
            models.Index(fields=("flow_definition", "status", "created_at")),
        ]

    def __str__(self) -> str:
        return self.run_id


class FlowStepRun(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        ACTIVE = "active", "Active"
        BLOCKED = "blocked", "Blocked"
        COMPLETED = "completed", "Completed"
        SKIPPED = "skipped", "Skipped"

    flow_run = models.ForeignKey(FlowRun, on_delete=models.CASCADE, related_name="step_runs")
    sequence = models.PositiveIntegerField()
    step_key = models.CharField(max_length=120)
    status = models.CharField(max_length=32, choices=Status.choices, default=Status.PENDING)
    expected_route = models.CharField(max_length=180)
    expected_action_id = models.CharField(max_length=120)
    blocked_reason = models.CharField(max_length=255, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    evidence = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["flow_run", "sequence"]
        indexes = [
            models.Index(fields=("flow_run", "status", "sequence")),
            models.Index(fields=("status", "expected_action_id")),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=("flow_run", "step_key"),
                name="unique_flow_run_step_key",
            )
        ]

    def __str__(self) -> str:
        return f"{self.flow_run.run_id} {self.step_key}"


class FlowEvent(models.Model):
    class EventType(models.TextChoices):
        STARTED = "started", "Started"
        RESUMED = "resumed", "Resumed"
        CTA_INTENT = "cta_intent", "CTA intent"
        DOMAIN_COMPLETED = "domain_completed", "Domain completed"
        BLOCKED = "blocked", "Blocked"
        UNBLOCKED = "unblocked", "Unblocked"
        COMPLETED = "completed", "Completed"
        CANCELED = "canceled", "Canceled"

    event_id = models.CharField(max_length=96, unique=True, default=flow_event_reference)
    flow_run = models.ForeignKey(FlowRun, on_delete=models.CASCADE, related_name="events")
    step_run = models.ForeignKey(
        FlowStepRun,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="events",
    )
    step_key = models.CharField(max_length=120, blank=True)
    event_type = models.CharField(max_length=32, choices=EventType.choices)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="flow_events",
    )
    route = models.CharField(max_length=180, blank=True)
    action_id = models.CharField(max_length=120, blank=True)
    object_type = models.CharField(max_length=80, blank=True)
    object_id = models.CharField(max_length=80, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(fields=("flow_run", "created_at")),
            models.Index(fields=("event_type", "created_at")),
            models.Index(fields=("created_at",)),
        ]

    def __str__(self) -> str:
        return self.event_id
