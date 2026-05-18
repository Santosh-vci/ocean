import hashlib
import json
import math
from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import ValidationError

from apps.masters.models import AssetCompatibilityRule, Barge, CTSAsset, Jetty, Location, Tug
from apps.planning.models import (
    AssetAvailabilityWindow,
    BridgeWindow,
    CargoLayerStep,
    JettyAvailabilityWindow,
    NavigationConstraintCheck,
    OGVVoyage,
    TideWindow,
)
from apps.rbac.models import UserRoleAssignment

from .models import (
    ApprovalDecision,
    ApprovalRequest,
    Assignment,
    Conflict,
    ImpactChainAssessment,
    OverrideRequest,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
    ScenarioAssumption,
    ScenarioConstraintEvaluation,
    ScenarioEventProjection,
    ScenarioOgvProjection,
    ScenarioResourceUtilization,
    ScenarioRun,
    ScenarioTripProjection,
    ScheduleEvent,
    SimulationScenario,
    Trip,
)

REQUIRED_APPROVAL_AUTHORITIES = [
    ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
    ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
]


@dataclass
class GenerationResult:
    plan_version: PlanVersion
    trip_count: int
    conflict_count: int
    blocking_conflict_count: int


def next_version_no(plan: Plan) -> int:
    latest = plan.versions.order_by("-version_no").first()
    return (latest.version_no if latest else 0) + 1


def create_plan_version(*, plan: Plan, created_by=None, source_version=None) -> PlanVersion:
    return PlanVersion.objects.create(
        plan=plan,
        version_no=next_version_no(plan),
        source_version=source_version,
        created_by=created_by,
    )


def clone_plan_version(*, source_version: PlanVersion, created_by=None) -> PlanVersion:
    """Create a successor draft preserving generated trip-chain evidence."""

    with transaction.atomic():
        clone = create_plan_version(
            plan=source_version.plan,
            created_by=created_by,
            source_version=source_version,
        )
        clone.validation_status = source_version.validation_status
        clone.summary = {
            **source_version.summary,
            "sourceVersion": source_version.version_no,
            "cloneMode": "generated_state_copy",
        }
        clone.save(update_fields=["validation_status", "summary", "updated_at"])

        trip_map = {}
        for trip in source_version.trips.select_related(
            "voyage",
            "cargo_requirement",
            "cargo_layer_step",
            "origin_jetty",
            "destination_location",
        ).order_by("sequence"):
            cloned_trip = Trip.objects.create(
                plan_version=clone,
                trip_id=trip.trip_id.replace(
                    f"{source_version.plan.code}-",
                    f"{source_version.plan.code}-CLONE{clone.version_no}-",
                    1,
                ),
                sequence=trip.sequence,
                voyage=trip.voyage,
                cargo_requirement=trip.cargo_requirement,
                cargo_layer_step=trip.cargo_layer_step,
                origin_jetty=trip.origin_jetty,
                destination_location=trip.destination_location,
                planned_start=trip.planned_start,
                planned_end=trip.planned_end,
                planned_quantity_mt=trip.planned_quantity_mt,
                loaded_quantity_mt=trip.loaded_quantity_mt,
                status=trip.status,
                selection_reason={
                    **trip.selection_reason,
                    "cloned_from": trip.trip_id,
                },
            )
            trip_map[trip.id] = cloned_trip
            if hasattr(trip, "assignment"):
                assignment = trip.assignment
                Assignment.objects.create(
                    trip=cloned_trip,
                    tug=assignment.tug,
                    barge=assignment.barge,
                    jetty=assignment.jetty,
                    cts=assignment.cts,
                    route_segment=assignment.route_segment,
                    owner_organization=assignment.owner_organization,
                    planned_departure=assignment.planned_departure,
                    planned_arrival=assignment.planned_arrival,
                    tug_status=assignment.tug_status,
                    barge_status=assignment.barge_status,
                    next_constraint=assignment.next_constraint,
                    next_action=assignment.next_action,
                    status=assignment.status,
                )
            for event in trip.events.order_by("sequence"):
                ScheduleEvent.objects.create(
                    trip=cloned_trip,
                    sequence=event.sequence,
                    event_type=event.event_type,
                    planned_at=event.planned_at,
                    actual_at=event.actual_at,
                    location_label=event.location_label,
                    resource_code=event.resource_code,
                    status=event.status,
                    metadata={**event.metadata, "cloned_from": trip.trip_id},
                )

        for conflict in source_version.conflicts.select_related("trip"):
            Conflict.objects.create(
                plan_version=clone,
                trip=trip_map.get(conflict.trip_id) if conflict.trip_id else None,
                code=conflict.code,
                severity=conflict.severity,
                object_type=conflict.object_type,
                object_id=conflict.object_id,
                message=conflict.message,
                is_blocking=conflict.is_blocking,
                resolved_at=conflict.resolved_at,
            )

    return clone


def apply_assignment_override(
    *,
    assignment: Assignment,
    actor,
    reason_code: str,
    description: str,
    changes: dict,
    impact_context: dict | None = None,
) -> OverrideRequest:
    if not reason_code:
        raise ValidationError({"reason_code": "A reason code is required for overrides."})
    if not description:
        raise ValidationError({"description": "A description is required for overrides."})
    if assignment.trip.plan_version.status in {
        PlanVersion.Status.PUBLISHED,
        PlanVersion.Status.SUPERSEDED,
    }:
        raise ValidationError("Published or superseded plan versions cannot be edited.")

    allowed_fields = {
        "status",
        "next_constraint",
        "next_action",
        "planned_departure",
        "planned_arrival",
    }
    requested_change = {key: value for key, value in changes.items() if key in allowed_fields}
    if not requested_change:
        raise ValidationError("At least one supported assignment field must change.")
    actual_start_at = _impact_actual_start_at(
        reason_code=reason_code,
        impact_context=impact_context,
    )

    with transaction.atomic():
        before_state = _assignment_state(assignment)
        for field, value in requested_change.items():
            setattr(assignment, field, value)
        assignment.save(update_fields=[*requested_change.keys(), "updated_at"])
        after_state = _assignment_state(assignment)

        override = OverrideRequest.objects.create(
            plan_version=assignment.trip.plan_version,
            trip=assignment.trip,
            assignment=assignment,
            reason_code=reason_code,
            description=description,
            requested_change=requested_change,
            before_state=before_state,
            after_state=after_state,
            status=OverrideRequest.Status.APPLIED,
            requested_by=actor,
            applied_by=actor,
            applied_at=timezone.now(),
        )
        if actual_start_at:
            calculate_override_impact_chain(
                override=override,
                actual_start_at=actual_start_at,
            )

    return override


def calculate_override_impact_chain(
    *,
    override: OverrideRequest,
    actual_start_at,
) -> ImpactChainAssessment:
    if override.trip is None or override.assignment is None:
        raise ValidationError(
            "Impact chain assessment requires an override with a trip assignment."
        )

    trip = override.trip
    assignment = override.assignment
    baseline_event = (
        trip.events.filter(event_type=ScheduleEvent.EventType.LOAD_START)
        .order_by("sequence")
        .first()
    )
    baseline_start = baseline_event.planned_at if baseline_event else trip.planned_start
    delay_minutes = max(0, int((actual_start_at - baseline_start).total_seconds() // 60))
    delay_delta = timedelta(minutes=delay_minutes)
    event_projections = _project_trip_events(trip=trip, delay_delta=delay_delta)
    bridge_projection = event_projections.get(ScheduleEvent.EventType.BRIDGE_CROSS)
    tide_projection = event_projections.get(ScheduleEvent.EventType.TIDE_GATE)
    bridge_eval = _evaluate_bridge_window(
        assignment=assignment,
        projected_at=bridge_projection["projected_at"] if bridge_projection else None,
    )
    tide_eval = _evaluate_tide_window(
        assignment=assignment,
        projected_at=tide_projection["projected_at"] if tide_projection else None,
    )
    nodes = _impact_nodes(
        override=override,
        baseline_start=baseline_start,
        actual_start_at=actual_start_at,
        delay_minutes=delay_minutes,
        bridge_eval=bridge_eval,
        tide_eval=tide_eval,
    )
    status = _worst_status(node["status"] for node in nodes)
    assessment_id = f"ICA-{override.plan_version.plan.code}-OR{override.id:04d}"

    assessment, _ = ImpactChainAssessment.objects.update_or_create(
        override_request=override,
        defaults={
            "assessment_id": assessment_id,
            "plan_version": override.plan_version,
            "trip": trip,
            "assignment": assignment,
            "source_kind": ImpactChainAssessment.SourceKind.OVERRIDE,
            "status": status,
            "delay_minutes": delay_minutes,
            "nodes": nodes,
            "metadata": {
                "algorithmVersion": "stage-7.1-current-trip-v1",
                "calculatedAt": timezone.now().isoformat(),
                "actualStartAt": actual_start_at.isoformat(),
                "baselineLoadStart": baseline_start.isoformat(),
                "baselineLoadStartEventId": baseline_event.id if baseline_event else None,
                "eventProjections": _serializable_event_projections(event_projections),
                "bridgeWindowId": bridge_eval.get("window_id"),
                "tideWindowId": tide_eval.get("window_id"),
            },
        },
    )
    return assessment


def _impact_actual_start_at(*, reason_code: str, impact_context: dict | None):
    raw_value = (impact_context or {}).get("actual_start_at")
    if not raw_value:
        if reason_code == OverrideRequest.ReasonCode.JETTY_DELAY:
            raise ValidationError(
                {"impact_context": {"actual_start_at": "Effective start time is required."}}
            )
        return None
    parsed = parse_datetime(raw_value) if isinstance(raw_value, str) else raw_value
    if parsed is None:
        raise ValidationError(
            {"impact_context": {"actual_start_at": "Enter a valid ISO datetime."}}
        )
    if timezone.is_naive(parsed):
        parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _project_trip_events(*, trip: Trip, delay_delta: timedelta) -> dict:
    tracked_events = {
        ScheduleEvent.EventType.LOAD_COMPLETE,
        ScheduleEvent.EventType.DEPART_JETTY,
        ScheduleEvent.EventType.BRIDGE_CROSS,
        ScheduleEvent.EventType.TIDE_GATE,
        ScheduleEvent.EventType.ARRIVE_CTS,
        ScheduleEvent.EventType.DISCHARGE_COMPLETE,
    }
    projections = {}
    for event in trip.events.filter(event_type__in=tracked_events).order_by("sequence"):
        projected_at = event.planned_at + delay_delta
        projections[event.event_type] = {
            "eventId": event.id,
            "plannedAt": event.planned_at.isoformat(),
            "projectedAt": projected_at.isoformat(),
            "projected_at": projected_at,
            "status": event.status,
        }
    return projections


def _serializable_event_projections(event_projections: dict) -> dict:
    return {
        event_type: {
            key: value
            for key, value in projection.items()
            if key != "projected_at"
        }
        for event_type, projection in event_projections.items()
    }


def _evaluate_bridge_window(*, assignment: Assignment, projected_at, window_overrides=None):
    if projected_at is None:
        return _missing_window_eval(kind="bridge", label="BRIDGE ETA UNKNOWN")
    windows = list(BridgeWindow.objects.filter(is_active=True).exclude(
        status=BridgeWindow.Status.CLOSED,
    ))
    return _evaluate_window_set(
        kind="bridge",
        projected_at=projected_at,
        windows=_apply_window_overrides(
            kind="bridge",
            windows=windows,
            window_overrides=window_overrides or {},
        ),
    )


def _evaluate_tide_window(*, assignment: Assignment, projected_at, window_overrides=None):
    if projected_at is None:
        return _missing_window_eval(kind="tide", label="TIDE ETA UNKNOWN")
    windows = TideWindow.objects.filter(is_active=True).exclude(
        risk_level=TideWindow.RiskLevel.CLOSED,
    )
    route_segment_ids = _route_segment_ids_for_tide(assignment)
    if route_segment_ids:
        windows = windows.filter(
            Q(applicable_route_segment_id__in=route_segment_ids)
            | Q(applicable_route_segment__isnull=True)
        )
    return _evaluate_window_set(
        kind="tide",
        projected_at=projected_at,
        windows=_apply_window_overrides(
            kind="tide",
            windows=list(windows),
            window_overrides=window_overrides or {},
        ),
    )


def _route_segment_ids_for_tide(assignment: Assignment) -> list[int]:
    if not assignment.route_segment_id:
        return []
    route = assignment.route_segment.route
    route_segment_ids = set(
        route.segments.filter(requires_tide_window=True).values_list("id", flat=True)
    )
    route_segment_ids.add(assignment.route_segment_id)
    return list(route_segment_ids)


def _missing_window_eval(*, kind: str, label: str) -> dict:
    return {
        "kind": kind,
        "label": label,
        "status": ImpactChainAssessment.Status.CRITICAL,
        "value": "no ETA",
        "detail": "No projected gate time is available for this trip.",
        "window_id": None,
        "window_start": None,
        "window_end": None,
        "projected_at": None,
        "margin_minutes": None,
        "miss_minutes": None,
    }


def _evaluate_window_set(*, kind: str, projected_at, windows) -> dict:
    window_rows = sorted(windows, key=lambda window: window.window_start)
    if not window_rows:
        return {
            "kind": kind,
            "label": f"{kind.upper()} WINDOW UNKNOWN",
            "status": ImpactChainAssessment.Status.CRITICAL,
            "value": "no active window",
            "detail": "No active governed window is available for this gate.",
            "window_id": None,
            "window_start": None,
            "window_end": None,
            "projected_at": projected_at,
            "margin_minutes": None,
            "miss_minutes": None,
        }

    for window in window_rows:
        if window.window_start <= projected_at <= window.window_end:
            margin_minutes = int((window.window_end - projected_at).total_seconds() // 60)
            restricted = getattr(window, "status", "") == BridgeWindow.Status.RESTRICTED
            tight = getattr(window, "risk_level", "") == TideWindow.RiskLevel.TIGHT
            status = (
                ImpactChainAssessment.Status.WARNING
                if margin_minutes < 30 or restricted or tight
                else ImpactChainAssessment.Status.OK
            )
            label = (
                f"{kind.upper()} WINDOW "
                f"{'TIGHT' if status == ImpactChainAssessment.Status.WARNING else 'OK'}"
            )
            return {
                "kind": kind,
                "label": label,
                "status": status,
                "value": f"{margin_minutes}m margin",
                "detail": f"Projected gate remains inside {window.code}.",
                "window_id": window.id,
                "window_code": window.code,
                "window_start": window.window_start.isoformat(),
                "window_end": window.window_end.isoformat(),
                "projected_at": projected_at,
                "margin_minutes": margin_minutes,
                "miss_minutes": None,
            }

    previous_windows = [window for window in window_rows if window.window_end < projected_at]
    next_windows = [window for window in window_rows if window.window_start > projected_at]
    previous_window = previous_windows[-1] if previous_windows else None
    next_window = next_windows[0] if next_windows else None

    if previous_window and (
        next_window is None
        or projected_at - previous_window.window_end <= next_window.window_start - projected_at
    ):
        miss_minutes = int((projected_at - previous_window.window_end).total_seconds() // 60)
        return {
            "kind": kind,
            "label": f"{kind.upper()} WINDOW MISSED",
            "status": ImpactChainAssessment.Status.CRITICAL,
            "value": f"by {miss_minutes}m",
            "detail": f"Projected gate misses {previous_window.code}.",
            "window_id": previous_window.id,
            "window_code": previous_window.code,
            "window_start": previous_window.window_start.isoformat(),
            "window_end": previous_window.window_end.isoformat(),
            "projected_at": projected_at,
            "margin_minutes": -miss_minutes,
            "miss_minutes": miss_minutes,
        }

    wait_minutes = int((next_window.window_start - projected_at).total_seconds() // 60)
    return {
        "kind": kind,
        "label": f"{kind.upper()} WINDOW WAIT",
        "status": ImpactChainAssessment.Status.WARNING,
        "value": f"{wait_minutes}m wait",
        "detail": f"Projected gate must wait for {next_window.code}.",
        "window_id": next_window.id,
        "window_code": next_window.code,
        "window_start": next_window.window_start.isoformat(),
        "window_end": next_window.window_end.isoformat(),
        "projected_at": projected_at,
        "margin_minutes": -wait_minutes,
        "miss_minutes": None,
    }


def _impact_nodes(
    *,
    override: OverrideRequest,
    baseline_start,
    actual_start_at,
    delay_minutes: int,
    bridge_eval: dict,
    tide_eval: dict,
) -> list[dict]:
    delay_status = (
        ImpactChainAssessment.Status.WARNING if delay_minutes else ImpactChainAssessment.Status.OK
    )
    navigation_status = _worst_status([bridge_eval["status"], tide_eval["status"]])
    return [
        {
            "id": "source",
            "type": "source_event",
            "label": override.reason_code.replace("_", " ").upper(),
            "value": actual_start_at.isoformat(),
            "status": delay_status,
            "detail": "Effective start against planned load start.",
            "plannedAt": baseline_start.isoformat(),
            "projectedAt": actual_start_at.isoformat(),
        },
        {
            "id": "logistics",
            "type": "logistics_delay",
            "label": "BARGE DELAY",
            "value": f"+{delay_minutes}m",
            "status": delay_status,
            "detail": "Current-trip event times shifted by operator-entered start.",
        },
        _window_node(node_id="bridge", evaluation=bridge_eval),
        _window_node(node_id="tide", evaluation=tide_eval),
        {
            "id": "target",
            "type": "final_risk_target",
            "label": "FINAL RISK TARGET",
            "value": override.trip.voyage.vessel_name if override.trip else "Network",
            "status": navigation_status,
            "detail": override.trip.trip_id if override.trip else "Network",
        },
    ]


def _window_node(*, node_id: str, evaluation: dict) -> dict:
    projected_at = evaluation.get("projected_at")
    return {
        "id": node_id,
        "type": f"{evaluation['kind']}_window",
        "label": evaluation["label"],
        "value": evaluation["value"],
        "status": evaluation["status"],
        "detail": evaluation["detail"],
        "projectedAt": projected_at.isoformat() if projected_at else None,
        "windowStart": evaluation.get("window_start"),
        "windowEnd": evaluation.get("window_end"),
        "marginMinutes": evaluation.get("margin_minutes"),
        "missMinutes": evaluation.get("miss_minutes"),
    }


def _worst_status(statuses) -> str:
    rank = {
        ImpactChainAssessment.Status.OK: 0,
        ImpactChainAssessment.Status.WARNING: 1,
        ImpactChainAssessment.Status.CRITICAL: 2,
    }
    status_list = list(statuses)
    if not status_list:
        return ImpactChainAssessment.Status.OK
    return max(status_list, key=lambda status: rank.get(status, 0))


def _display_time(value) -> str:
    return timezone.localtime(value).strftime("%b %d, %H:%M")


def submit_approval_request(
    *,
    plan_version: PlanVersion,
    actor,
    reason: str,
) -> ApprovalRequest:
    if plan_version.status in {PlanVersion.Status.PUBLISHED, PlanVersion.Status.SUPERSEDED}:
        raise ValidationError("Published or superseded plan versions cannot be submitted.")

    request_id = f"APR-{plan_version.plan.code}-V{plan_version.version_no}"
    with transaction.atomic():
        approval_request, created = ApprovalRequest.objects.get_or_create(
            request_id=request_id,
            defaults={
                "plan_version": plan_version,
                "status": ApprovalRequest.Status.PENDING,
                "required_authorities": REQUIRED_APPROVAL_AUTHORITIES,
                "reason": reason or "Plan lifecycle approval requested.",
                "requested_by": actor,
            },
        )
        if not created:
            approval_request.plan_version = plan_version
            approval_request.required_authorities = REQUIRED_APPROVAL_AUTHORITIES
            approval_request.reason = (
                reason
                or approval_request.reason
                or "Plan lifecycle approval requested."
            )
            approval_request.requested_by = actor

            if approval_request.status not in {
                ApprovalRequest.Status.PUBLISHED,
                ApprovalRequest.Status.CANCELED,
                ApprovalRequest.Status.REJECTED,
            }:
                if _required_approvals_complete(approval_request):
                    approval_request.status = ApprovalRequest.Status.APPROVED
                    approval_request.decided_at = approval_request.decided_at or timezone.now()
                    if not _open_blocking_conflicts(plan_version).exists():
                        plan_version.status = PlanVersion.Status.APPROVED
                else:
                    approval_request.status = ApprovalRequest.Status.PENDING

            approval_request.save(
                update_fields=[
                    "plan_version",
                    "required_authorities",
                    "reason",
                    "requested_by",
                    "status",
                    "decided_at",
                    "updated_at",
                ]
            )
        if plan_version.status not in {
            PlanVersion.Status.PROPOSED,
            PlanVersion.Status.APPROVED,
        }:
            plan_version.status = PlanVersion.Status.PROPOSED
            plan_version.save(update_fields=["status", "updated_at"])
        elif plan_version.status == PlanVersion.Status.APPROVED:
            plan_version.save(update_fields=["status", "updated_at"])

    return approval_request


def record_approval_decision(
    *,
    approval_request: ApprovalRequest,
    actor,
    decision: str,
    authority_role: str,
    comments: str = "",
) -> ApprovalDecision:
    if approval_request.status in {
        ApprovalRequest.Status.PUBLISHED,
        ApprovalRequest.Status.CANCELED,
    }:
        raise ValidationError("This approval request is closed.")
    if decision != ApprovalDecision.Decision.APPROVE and not comments:
        raise ValidationError({"comments": "Comments are required for non-approval decisions."})
    if decision not in dict(ApprovalDecision.Decision.choices):
        raise ValidationError({"decision": "Unsupported approval decision."})
    if authority_role not in dict(ApprovalDecision.AuthorityRole.choices):
        raise ValidationError({"authority_role": "Unsupported approval authority."})

    organization = _default_organization_for_actor(actor)
    with transaction.atomic():
        approval_decision, _ = ApprovalDecision.objects.update_or_create(
            approval_request=approval_request,
            authority_role=authority_role,
            defaults={
                "decision": decision,
                "comments": comments,
                "actor": actor,
                "organization": organization,
            },
        )
        if decision == ApprovalDecision.Decision.REJECT:
            approval_request.status = ApprovalRequest.Status.REJECTED
            approval_request.decided_at = timezone.now()
            approval_request.plan_version.status = PlanVersion.Status.PROPOSED
        elif _required_approvals_complete(approval_request):
            approval_request.status = ApprovalRequest.Status.APPROVED
            approval_request.decided_at = timezone.now()
            if not _open_blocking_conflicts(approval_request.plan_version).exists():
                approval_request.plan_version.status = PlanVersion.Status.APPROVED
        else:
            approval_request.status = ApprovalRequest.Status.PENDING

        approval_request.save(update_fields=["status", "decided_at", "updated_at"])
        approval_request.plan_version.save(update_fields=["status", "updated_at"])

    return approval_decision


def publish_plan_version(*, plan_version: PlanVersion, actor) -> PublishedPlanSnapshot:
    if plan_version.status == PlanVersion.Status.PUBLISHED:
        raise ValidationError("This plan version is already published.")
    approval_request = (
        plan_version.approval_requests.filter(status=ApprovalRequest.Status.APPROVED)
        .order_by("-created_at")
        .first()
    )
    if approval_request is None:
        raise ValidationError("A complete approval request is required before publishing.")
    if _open_blocking_conflicts(plan_version).exists():
        raise ValidationError("Publish is blocked while unresolved blocking conflicts remain.")
    if not _required_approvals_complete(approval_request):
        raise ValidationError("Dual-party Berau and ABL approvals are required.")

    with transaction.atomic():
        PlanVersion.objects.filter(
            plan=plan_version.plan,
            status=PlanVersion.Status.PUBLISHED,
        ).exclude(pk=plan_version.pk).update(status=PlanVersion.Status.SUPERSEDED)
        PublishedPlanSnapshot.objects.filter(
            plan=plan_version.plan,
            status=PublishedPlanSnapshot.Status.ACTIVE,
        ).update(status=PublishedPlanSnapshot.Status.SUPERSEDED)

        snapshot = PublishedPlanSnapshot.objects.create(
            snapshot_id=f"LIVE-{plan_version.plan.code}-V{plan_version.version_no}",
            plan=plan_version.plan,
            plan_version=plan_version,
            approval_request=approval_request,
            payload=_snapshot_payload(plan_version),
            published_by=actor,
        )
        plan_version.status = PlanVersion.Status.PUBLISHED
        plan_version.published_at = timezone.now()
        plan_version.save(update_fields=["status", "published_at", "updated_at"])
        approval_request.status = ApprovalRequest.Status.PUBLISHED
        approval_request.save(update_fields=["status", "updated_at"])

    return snapshot


def compute_plan_diff(*, source_version: PlanVersion, target_version: PlanVersion) -> dict:
    source_rows = {_trip_diff_key(trip): trip for trip in source_version.trips.all()}
    target_rows = {_trip_diff_key(trip): trip for trip in target_version.trips.all()}
    keys = sorted(set(source_rows) | set(target_rows))
    rows = []
    changed = 0
    delay_delta = 0
    quantity_delta = 0

    for key in keys:
        source_trip = source_rows.get(key)
        target_trip = target_rows.get(key)
        if source_trip and target_trip:
            row_delay = int(
                (target_trip.planned_end - source_trip.planned_end).total_seconds() / 60
            )
            row_quantity = target_trip.planned_quantity_mt - source_trip.planned_quantity_mt
            source_assignment = getattr(source_trip, "assignment", None)
            target_assignment = getattr(target_trip, "assignment", None)
            source_resources = _plan_diff_assignment_resources(source_assignment)
            target_resources = _plan_diff_assignment_resources(target_assignment)
            state = (
                "changed"
                if row_delay or row_quantity or source_resources != target_resources
                else "unchanged"
            )
            changed += 1 if state == "changed" else 0
            delay_delta += row_delay
            quantity_delta += row_quantity
            rows.append(
                {
                    "key": key,
                    "state": state,
                    "sourceTrip": source_trip.trip_id,
                    "targetTrip": target_trip.trip_id,
                    "sourceVessel": source_trip.voyage.vessel_name,
                    "targetVessel": target_trip.voyage.vessel_name,
                    "delayDeltaMinutes": row_delay,
                    "quantityDeltaMt": row_quantity,
                    "sourceResources": source_resources,
                    "targetResources": target_resources,
                }
            )
        elif target_trip:
            changed += 1
            quantity_delta += target_trip.planned_quantity_mt
            rows.append(
                {
                    "key": key,
                    "state": "added",
                    "targetTrip": target_trip.trip_id,
                    "targetVessel": target_trip.voyage.vessel_name,
                    "quantityDeltaMt": target_trip.planned_quantity_mt,
                }
            )
        elif source_trip:
            changed += 1
            quantity_delta -= source_trip.planned_quantity_mt
            rows.append(
                {
                    "key": key,
                    "state": "removed",
                    "sourceTrip": source_trip.trip_id,
                    "sourceVessel": source_trip.voyage.vessel_name,
                    "quantityDeltaMt": -source_trip.planned_quantity_mt,
                }
            )

    return {
        "sourceVersion": source_version.id,
        "targetVersion": target_version.id,
        "summary": {
            "changedTripCount": changed,
            "delayDeltaMinutes": delay_delta,
            "quantityDeltaMt": quantity_delta,
        },
        "rows": rows,
    }


def _plan_diff_assignment_resources(assignment: Assignment | None) -> dict[str, str]:
    return {
        "tug": assignment.tug.code if assignment and assignment.tug else "",
        "barge": assignment.barge.code if assignment and assignment.barge else "",
        "jetty": assignment.jetty.code if assignment and assignment.jetty else "",
        "cts": assignment.cts.code if assignment and assignment.cts else "",
    }


def create_scenario_from_conflict(
    *,
    baseline_version: PlanVersion,
    source_conflict: Conflict | None,
    source_override: OverrideRequest | None = None,
    actor,
    name: str = "",
) -> SimulationScenario:
    if source_conflict and source_conflict.plan_version_id != baseline_version.id:
        raise ValidationError("Scenario source conflict must belong to the baseline version.")
    if source_override and source_override.plan_version_id != baseline_version.id:
        raise ValidationError("Scenario source override must belong to the baseline version.")
    if source_conflict and source_override:
        raise ValidationError("A scenario can have either a conflict or override source, not both.")

    source_kind = (
        SimulationScenario.SourceKind.CONFLICT
        if source_conflict
        else SimulationScenario.SourceKind.OVERRIDE
        if source_override
        else SimulationScenario.SourceKind.MANUAL
    )
    sequence = baseline_version.baseline_scenarios.count() + 1
    scenario = SimulationScenario.objects.create(
        scenario_id=f"SIM-{baseline_version.plan.code}-V{baseline_version.version_no}-{sequence:02d}",
        name=name or "Recovery scenario",
        scenario_type="conflict_recovery",
        baseline_version=baseline_version,
        source_conflict=source_conflict,
        source_override=source_override,
        source_kind=source_kind,
        status=SimulationScenario.Status.DRAFT,
        created_by=actor,
    )
    return scenario


def create_scenario_from_tracking_alert(
    *,
    baseline_version: PlanVersion,
    source_alert,
    actor,
    name: str = "",
) -> SimulationScenario:
    if source_alert.trip_id is None:
        raise ValidationError("Scenario source tracking alert must be linked to a trip.")
    if source_alert.trip.plan_version_id != baseline_version.id:
        raise ValidationError("Scenario source tracking alert must belong to the baseline version.")

    sequence = baseline_version.baseline_scenarios.count() + 1
    return SimulationScenario.objects.create(
        scenario_id=f"SIM-{baseline_version.plan.code}-V{baseline_version.version_no}-{sequence:02d}",
        name=name or f"Observed delay {source_alert.trip.trip_id}",
        scenario_type="observed_delay_recovery",
        baseline_version=baseline_version,
        source_kind=SimulationScenario.SourceKind.TRACKING_ALERT,
        status=SimulationScenario.Status.DRAFT,
        metadata={
            "source": {
                "kind": SimulationScenario.SourceKind.TRACKING_ALERT,
                "trackingAlertId": source_alert.pk,
                "trackingAlertRef": source_alert.alert_id,
                "alertType": source_alert.alert_type,
                "severity": source_alert.severity,
                "assetCode": source_alert.asset_code,
                "tripId": source_alert.trip_id,
                "tripRef": source_alert.trip.trip_id,
                "scheduleEventId": source_alert.schedule_event_id,
                "scheduleEventType": (
                    source_alert.schedule_event.event_type
                    if source_alert.schedule_event_id
                    else None
                ),
                "sourceKind": source_alert.source_kind,
                "evidence": source_alert.evidence,
            }
        },
        created_by=actor,
    )


def create_scenario_assumption(
    *,
    scenario: SimulationScenario,
    actor,
    kind: str,
    scope_type: str,
    scope_id: int | None,
    payload: dict | None = None,
    effective_from=None,
    effective_to=None,
) -> ScenarioAssumption:
    _assert_scenario_inputs_mutable(scenario)
    normalized_payload = payload or {}
    _validate_scenario_assumption_payload(kind=kind, payload=normalized_payload)
    _validate_scenario_assumption_scope(
        scenario=scenario,
        kind=kind,
        scope_type=scope_type,
        scope_id=scope_id,
        payload=normalized_payload,
    )

    assumption_sequence = scenario.assumptions.count() + 1
    assumption = ScenarioAssumption.objects.create(
        scenario=scenario,
        assumption_id=f"ASM-{scenario.scenario_id}-{assumption_sequence:02d}",
        kind=kind,
        scope_type=scope_type,
        scope_id=scope_id,
        payload=normalized_payload,
        effective_from=effective_from,
        effective_to=effective_to,
        created_by=actor,
    )
    _mark_scenario_inputs_changed(scenario)
    return assumption


def create_scenario_run(
    *,
    scenario: SimulationScenario,
    actor,
    status: str = ScenarioRun.Status.QUEUED,
    algorithm_version: str = "phase2-projection-v1",
    summary: dict | None = None,
    started_at=None,
    completed_at=None,
) -> ScenarioRun:
    if scenario.status in {
        SimulationScenario.Status.PROPOSED,
        SimulationScenario.Status.CANCELED,
    }:
        raise ValidationError("Proposed or canceled scenarios cannot accept new runs.")
    run_sequence = scenario.runs.count() + 1
    return ScenarioRun.objects.create(
        scenario=scenario,
        run_id=f"RUN-{scenario.scenario_id}-{run_sequence:02d}",
        baseline_version=scenario.baseline_version,
        status=status,
        algorithm_version=algorithm_version,
        input_hash=_scenario_input_hash(scenario),
        summary=summary or {},
        started_at=started_at,
        completed_at=completed_at,
        created_by=actor,
    )


def simulate_scenario(*, scenario: SimulationScenario, actor=None) -> SimulationScenario:
    if scenario.status in {
        SimulationScenario.Status.PROPOSED,
        SimulationScenario.Status.CANCELED,
    }:
        raise ValidationError("Only draft or simulated scenarios can be simulated.")

    now = timezone.now()
    run = create_scenario_run(
        scenario=scenario,
        actor=actor,
        status=ScenarioRun.Status.RUNNING,
        started_at=now,
    )
    projection_summary = calculate_scenario_run_projections(run=run)
    scenario.recovery_actions = _scenario_recovery_actions(projection_summary)
    scenario.impact_summary = projection_summary["impactSummary"]
    scenario.delta_summary = projection_summary["deltaSummary"]
    scenario.status = SimulationScenario.Status.SIMULATED
    scenario.save(
        update_fields=[
            "recovery_actions",
            "impact_summary",
            "delta_summary",
            "status",
            "updated_at",
        ]
    )
    run.status = ScenarioRun.Status.SUCCEEDED
    run.summary = {
        "mode": "projection",
        **projection_summary,
    }
    run.completed_at = timezone.now()
    run.save(update_fields=["status", "summary", "completed_at", "updated_at"])
    return scenario


def calculate_scenario_run_projections(*, run: ScenarioRun) -> dict:
    states, edges = _build_baseline_schedule_graph(run.baseline_version)
    assumptions = list(
        run.scenario.assumptions.order_by("created_at", "id")
    )
    window_overrides = _apply_scenario_assumptions(
        states=states,
        assumptions=assumptions,
    )
    _rebuild_projected_resource_edges(states=states, edges=edges)
    _propagate_projection_graph(states=states, edges=edges)

    ScenarioTripProjection.objects.filter(run=run).delete()
    ScenarioEventProjection.objects.filter(run=run).delete()
    ScenarioConstraintEvaluation.objects.filter(run=run).delete()
    ScenarioOgvProjection.objects.filter(run=run).delete()
    ScenarioResourceUtilization.objects.filter(run=run).delete()
    ImpactChainAssessment.objects.filter(assessment_id__startswith=f"ICA-{run.run_id}-").delete()
    trip_projections = []
    event_projection_index = {}
    for state in states.values():
        trip_projection, event_projections = _persist_projection_state(
            run=run,
            state=state,
        )
        trip_projections.append(trip_projection)
        event_projection_index[state["trip"].id] = {
            event_projection.event_type: event_projection
            for event_projection in event_projections
        }

    assessments = _create_simulation_impact_assessments(
        run=run,
        states=states,
        event_projection_index=event_projection_index,
        window_overrides=window_overrides,
    )
    kpis = _materialize_scenario_kpis(
        run=run,
        trip_projections=trip_projections,
        event_projection_index=event_projection_index,
        assessments=assessments,
    )
    return _scenario_projection_summary(
        run=run,
        assumptions=assumptions,
        trip_projections=trip_projections,
        assessments=assessments,
        kpis=kpis,
    )


def promote_scenario_to_proposed(
    *,
    scenario: SimulationScenario,
    actor,
    run: ScenarioRun | None = None,
) -> SimulationScenario:
    if scenario.status != SimulationScenario.Status.SIMULATED:
        raise ValidationError("Only simulated scenarios can be promoted.")

    with transaction.atomic():
        selected_run = _selected_scenario_run(scenario=scenario, run=run)
        if scenario.scenario_version is None:
            scenario.scenario_version = clone_plan_version(
                source_version=scenario.baseline_version,
                created_by=actor,
            )
        elif scenario.scenario_version.plan_id != scenario.baseline_version.plan_id:
            raise ValidationError("Scenario output version must stay on the baseline plan.")
        elif scenario.scenario_version.source_version_id != scenario.baseline_version_id:
            raise ValidationError("Scenario output version must derive from the baseline version.")

        _materialize_scenario_run_to_version(
            run=selected_run,
            target_version=scenario.scenario_version,
        )
        scenario_diff = compute_plan_diff(
            source_version=scenario.baseline_version,
            target_version=scenario.scenario_version,
        )
        scenario.scenario_version.summary = {
            **scenario.scenario_version.summary,
            **_promoted_version_summary(
                scenario=scenario,
                run=selected_run,
                scenario_diff=scenario_diff,
                actor=actor,
            ),
        }
        scenario.status = SimulationScenario.Status.PROPOSED
        scenario.scenario_version.status = PlanVersion.Status.PROPOSED
        scenario.scenario_version.save(update_fields=["status", "summary", "updated_at"])
        scenario.save(update_fields=["scenario_version", "status", "updated_at"])
    return scenario


def _selected_scenario_run(
    *,
    scenario: SimulationScenario,
    run: ScenarioRun | None,
) -> ScenarioRun:
    selected_run = run or scenario.runs.filter(
        status=ScenarioRun.Status.SUCCEEDED,
    ).order_by("-created_at", "-id").first()
    if selected_run is None:
        raise ValidationError("A successful scenario run is required before promotion.")
    if selected_run.scenario_id != scenario.id:
        raise ValidationError("Selected run must belong to the scenario being promoted.")
    if selected_run.baseline_version_id != scenario.baseline_version_id:
        raise ValidationError("Selected run must use the scenario baseline version.")
    if selected_run.status != ScenarioRun.Status.SUCCEEDED:
        raise ValidationError("Only successful scenario runs can be promoted.")
    return selected_run


def _materialize_scenario_run_to_version(
    *,
    run: ScenarioRun,
    target_version: PlanVersion,
) -> None:
    baseline_trips = list(
        run.baseline_version.trips.select_related("assignment").order_by("sequence", "trip_id")
    )
    target_trips = list(
        target_version.trips.select_related("assignment").order_by("sequence", "trip_id")
    )
    if len(baseline_trips) != len(target_trips):
        raise ValidationError("Scenario output version no longer matches its baseline shape.")

    target_trip_by_source_id = {
        baseline_trip.id: target_trip
        for baseline_trip, target_trip in zip(baseline_trips, target_trips, strict=True)
    }
    projection_by_trip_id = {
        projection.trip_id: projection
        for projection in run.trip_projections.select_related("trip").all()
    }
    event_projection_index = {
        (projection.trip_id, projection.event_type): projection
        for projection in run.event_projections.select_related("trip", "event").all()
    }

    for baseline_trip in baseline_trips:
        target_trip = target_trip_by_source_id[baseline_trip.id]
        trip_projection = projection_by_trip_id.get(baseline_trip.id)
        if trip_projection is None:
            continue
        target_trip.planned_start = trip_projection.projected_start
        target_trip.planned_end = trip_projection.projected_end
        target_trip.status = trip_projection.projected_status
        target_trip.selection_reason = {
            **target_trip.selection_reason,
            "scenario_projection": {
                "runId": run.run_id,
                "sourceTrip": baseline_trip.trip_id,
                "delayMinutes": trip_projection.delay_minutes,
            },
        }
        target_trip.save(
            update_fields=[
                "planned_start",
                "planned_end",
                "status",
                "selection_reason",
                "updated_at",
            ]
        )
        _materialize_projected_assignment(
            target_trip=target_trip,
            trip_projection=trip_projection,
            event_projection_index=event_projection_index,
        )
        _materialize_projected_events(
            baseline_trip=baseline_trip,
            target_trip=target_trip,
            event_projection_index=event_projection_index,
        )

    _replace_version_conflicts_from_run(
        run=run,
        target_version=target_version,
        target_trip_by_source_id=target_trip_by_source_id,
    )


def _materialize_projected_assignment(
    *,
    target_trip: Trip,
    trip_projection: ScenarioTripProjection,
    event_projection_index: dict,
) -> None:
    assignment = getattr(target_trip, "assignment", None)
    if assignment is None:
        return

    projected_resources = trip_projection.assignment_delta.get("projectedResources", {})
    tug_code = projected_resources.get("tug")
    barge_code = projected_resources.get("barge")
    cts_code = projected_resources.get("cts")
    tug = Tug.objects.filter(code=tug_code).first() if tug_code else assignment.tug
    barge = Barge.objects.filter(code=barge_code).first() if barge_code else assignment.barge
    cts = CTSAsset.objects.filter(code=cts_code).first() if cts_code else assignment.cts
    depart_projection = event_projection_index.get(
        (trip_projection.trip_id, ScheduleEvent.EventType.DEPART_JETTY)
    )
    arrive_projection = event_projection_index.get(
        (trip_projection.trip_id, ScheduleEvent.EventType.ARRIVE_CTS)
    )
    assignment.tug = tug
    assignment.barge = barge
    assignment.cts = cts
    assignment.owner_organization = tug.organization if tug else assignment.owner_organization
    assignment.tug_status = _asset_status_label(tug)
    assignment.barge_status = _asset_status_label(barge)
    assignment.planned_departure = (
        depart_projection.projected_at if depart_projection else assignment.planned_departure
    )
    assignment.planned_arrival = (
        arrive_projection.projected_at if arrive_projection else assignment.planned_arrival
    )
    assignment.save(
        update_fields=[
            "tug",
            "barge",
            "cts",
            "owner_organization",
            "planned_departure",
            "planned_arrival",
            "tug_status",
            "barge_status",
            "updated_at",
        ]
    )


def _materialize_projected_events(
    *,
    baseline_trip: Trip,
    target_trip: Trip,
    event_projection_index: dict,
) -> None:
    assignment = getattr(target_trip, "assignment", None)
    baseline_events = {
        event.event_type: event
        for event in baseline_trip.events.order_by("sequence")
    }
    for target_event in target_trip.events.order_by("sequence"):
        baseline_event = baseline_events.get(target_event.event_type)
        projection = event_projection_index.get(
            (baseline_trip.id, target_event.event_type)
        )
        if baseline_event is None or projection is None:
            continue
        resource_code = _event_resource_code(
            event_type=target_event.event_type,
            trip=target_trip,
            assignment=assignment,
            fallback=target_event.resource_code,
        )
        target_event.planned_at = projection.projected_at
        target_event.status = projection.projected_status
        target_event.location_label = resource_code
        target_event.resource_code = resource_code
        target_event.metadata = {
            **target_event.metadata,
            "scenarioProjection": {
                "sourceEvent": baseline_event.id,
                "delayMinutes": projection.delay_minutes,
            },
        }
        target_event.save(
            update_fields=[
                "planned_at",
                "status",
                "location_label",
                "resource_code",
                "metadata",
            ]
        )


def _event_resource_code(
    *,
    event_type: str,
    trip: Trip,
    assignment: Assignment | None,
    fallback: str,
) -> str:
    if assignment is None:
        return fallback
    if event_type == ScheduleEvent.EventType.LOAD_START:
        return assignment.jetty.code if assignment.jetty else fallback
    if event_type == ScheduleEvent.EventType.LOAD_COMPLETE:
        return assignment.barge.code if assignment.barge else fallback
    if event_type == ScheduleEvent.EventType.DEPART_JETTY:
        return assignment.tug.code if assignment.tug else fallback
    if event_type == ScheduleEvent.EventType.ARRIVE_CTS:
        return assignment.cts.code if assignment.cts else fallback
    if event_type == ScheduleEvent.EventType.DISCHARGE_COMPLETE:
        return trip.voyage.vessel_name
    return fallback


def _replace_version_conflicts_from_run(
    *,
    run: ScenarioRun,
    target_version: PlanVersion,
    target_trip_by_source_id: dict[int, Trip],
) -> None:
    Conflict.objects.filter(plan_version=target_version).delete()
    for evaluation in run.constraint_evaluations.select_related("trip").all():
        if evaluation.severity == ScenarioConstraintEvaluation.Severity.INFO:
            continue
        Conflict.objects.create(
            plan_version=target_version,
            trip=target_trip_by_source_id.get(evaluation.trip_id),
            code=evaluation.code,
            severity=evaluation.severity,
            object_type=evaluation.affected_object_type,
            object_id=evaluation.affected_object_id,
            message=evaluation.message,
            is_blocking=evaluation.severity == ScenarioConstraintEvaluation.Severity.CRITICAL,
        )
    _refresh_plan_version_validation(target_version)


def _refresh_plan_version_validation(plan_version: PlanVersion) -> None:
    conflicts = plan_version.conflicts.all()
    blocking_count = conflicts.filter(is_blocking=True, resolved_at__isnull=True).count()
    warning_count = conflicts.filter(severity=Conflict.Severity.WARNING).count()
    if blocking_count:
        plan_version.validation_status = PlanVersion.ValidationStatus.BLOCKED
    elif warning_count:
        plan_version.validation_status = PlanVersion.ValidationStatus.WARNING
    else:
        plan_version.validation_status = PlanVersion.ValidationStatus.FEASIBLE
    plan_version.summary = {
        **plan_version.summary,
        "tripCount": plan_version.trips.count(),
        "conflictCount": conflicts.count(),
        "blockingConflictCount": blocking_count,
        "warningConflictCount": warning_count,
        "firstBlockingConstraint": (
            conflicts.filter(is_blocking=True)
            .order_by("created_at")
            .values_list("code", flat=True)
            .first()
        ),
    }
    plan_version.save(update_fields=["validation_status", "summary", "updated_at"])


def _promoted_version_summary(
    *,
    scenario: SimulationScenario,
    run: ScenarioRun,
    scenario_diff: dict,
    actor,
) -> dict:
    return {
        "scenarioLineage": {
            "baselineVersionId": scenario.baseline_version_id,
            "baselineVersionRef": str(scenario.baseline_version),
            "scenarioId": scenario.scenario_id,
            "scenarioPk": scenario.id,
            "selectedRunId": run.id,
            "selectedRunRef": run.run_id,
            "assumptionIds": list(
                scenario.assumptions.order_by("created_at", "id").values_list(
                    "assumption_id",
                    flat=True,
                )
            ),
            "algorithmVersion": run.algorithm_version,
            "promotedAt": timezone.now().isoformat(),
            "promotedBy": getattr(actor, "email", "") or getattr(actor, "username", ""),
        },
        "scenarioDiff": scenario_diff,
    }


def _assert_scenario_inputs_mutable(scenario: SimulationScenario) -> None:
    if scenario.status in {
        SimulationScenario.Status.PROPOSED,
        SimulationScenario.Status.CANCELED,
    }:
        raise ValidationError("Proposed or canceled scenarios cannot accept new assumptions.")


def _mark_scenario_inputs_changed(scenario: SimulationScenario) -> None:
    if scenario.status != SimulationScenario.Status.SIMULATED:
        return
    scenario.status = SimulationScenario.Status.DRAFT
    scenario.recovery_actions = []
    scenario.impact_summary = {}
    scenario.delta_summary = {}
    scenario.save(
        update_fields=[
            "status",
            "recovery_actions",
            "impact_summary",
            "delta_summary",
            "updated_at",
        ]
    )


def _validate_scenario_assumption_payload(*, kind: str, payload: dict) -> None:
    if not isinstance(payload, dict):
        raise ValidationError({"payload": "Assumption payload must be an object."})

    requirements = {
        ScenarioAssumption.Kind.TRIP_DELAY: ("delay_minutes",),
        ScenarioAssumption.Kind.ASSET_OUTAGE: ("asset_code",),
        ScenarioAssumption.Kind.RATE_CHANGE: ("rate_tph",),
        ScenarioAssumption.Kind.WINDOW_CHANGE: ("window_code",),
        ScenarioAssumption.Kind.OGV_ETA_CHANGE: ("eta",),
        ScenarioAssumption.Kind.MANUAL_REASSIGNMENT: ("assignment_id",),
    }
    required_keys = requirements.get(kind)
    if required_keys is None:
        raise ValidationError({"kind": "Unsupported assumption kind."})

    missing = [key for key in required_keys if payload.get(key) in {None, ""}]
    if missing:
        raise ValidationError({"payload": f"Missing required fields: {', '.join(missing)}."})

    if kind == ScenarioAssumption.Kind.TRIP_DELAY:
        delay_minutes = payload.get("delay_minutes")
        if not isinstance(delay_minutes, int) or delay_minutes < 0:
            raise ValidationError(
                {"payload": {"delay_minutes": "Delay minutes must be a non-negative integer."}}
            )
    if kind == ScenarioAssumption.Kind.RATE_CHANGE:
        rate_tph = payload.get("rate_tph")
        if not isinstance(rate_tph, int | float) or rate_tph <= 0:
            raise ValidationError(
                {"payload": {"rate_tph": "Rate TPH must be a positive number."}}
            )
    if kind == ScenarioAssumption.Kind.OGV_ETA_CHANGE:
        eta = payload.get("eta")
        if not isinstance(eta, str) or parse_datetime(eta) is None:
            raise ValidationError({"payload": {"eta": "ETA must be a valid datetime string."}})
    if kind == ScenarioAssumption.Kind.MANUAL_REASSIGNMENT:
        tug_code = str(payload.get("tug_code", "")).strip()
        barge_code = str(payload.get("barge_code", "")).strip()
        cts_code = str(payload.get("cts_code", "")).strip()
        if not tug_code and not barge_code and not cts_code:
            raise ValidationError(
                {"payload": "Manual reassignment requires a tug_code, barge_code, or cts_code."}
            )
        if tug_code and not Tug.objects.filter(code=tug_code).exists():
            raise ValidationError({"payload": {"tug_code": "Unknown tug code."}})
        if barge_code and not Barge.objects.filter(code=barge_code).exists():
            raise ValidationError({"payload": {"barge_code": "Unknown barge code."}})
        if cts_code and not CTSAsset.objects.filter(code=cts_code).exists():
            raise ValidationError({"payload": {"cts_code": "Unknown CTS code."}})


def _validate_scenario_assumption_scope(
    *,
    scenario: SimulationScenario,
    kind: str,
    scope_type: str,
    scope_id: int | None,
    payload: dict,
) -> None:
    baseline = scenario.baseline_version
    if kind == ScenarioAssumption.Kind.TRIP_DELAY:
        if (
            scope_type != ScenarioAssumption.ScopeType.TRIP
            or scope_id is None
            or not baseline.trips.filter(id=scope_id).exists()
        ):
            raise ValidationError({"scope_id": "Trip must belong to the scenario baseline."})
        return

    if kind == ScenarioAssumption.Kind.OGV_ETA_CHANGE:
        if (
            scope_type != ScenarioAssumption.ScopeType.OGV
            or scope_id is None
            or not baseline.trips.filter(voyage_id=scope_id).exists()
        ):
            raise ValidationError({"scope_id": "OGV must belong to the scenario baseline."})
        return

    if kind == ScenarioAssumption.Kind.MANUAL_REASSIGNMENT:
        assignment_id = payload.get("assignment_id")
        if (
            scope_type != ScenarioAssumption.ScopeType.ASSIGNMENT
            or scope_id != assignment_id
            or not Assignment.objects.filter(
                id=assignment_id,
                trip__plan_version=baseline,
            ).exists()
        ):
            raise ValidationError(
                {"scope_id": "Assignment must belong to the scenario baseline."}
            )


def _scenario_input_hash(scenario: SimulationScenario) -> str:
    assumptions = list(
        scenario.assumptions.order_by("created_at", "id").values(
            "assumption_id",
            "kind",
            "scope_type",
            "scope_id",
            "payload",
            "effective_from",
            "effective_to",
        )
    )
    payload = {
        "baselineVersion": scenario.baseline_version_id,
        "scenario": scenario.scenario_id,
        "assumptions": assumptions,
    }
    canonical = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _build_baseline_schedule_graph(plan_version: PlanVersion):
    trips = list(
        plan_version.trips.select_related(
            "voyage",
            "cargo_layer_step",
            "origin_jetty",
            "assignment__tug",
            "assignment__barge",
            "assignment__jetty",
            "assignment__cts",
        )
        .prefetch_related("events")
        .order_by("sequence", "trip_id")
    )
    states = {}
    edges = {trip.id: [] for trip in trips}
    last_resource_trip = {}
    last_voyage_trip = {}

    for trip in trips:
        assignment = getattr(trip, "assignment", None)
        states[trip.id] = {
            "trip": trip,
            "assignment": assignment,
            "baseline_resource_codes": _assignment_resource_code_map(assignment),
            "projected_resource_codes": _assignment_resource_code_map(assignment),
            "baseline_start": trip.planned_start,
            "baseline_end": trip.planned_end,
            "projected_start": trip.planned_start,
            "projected_end": trip.planned_end,
            "direct_shift_minutes": 0,
            "start_shift_minutes": 0,
            "load_duration_delta_minutes": 0,
            "discharge_duration_delta_minutes": 0,
            "direct_assumption_ids": [],
            "dependency_sources": [],
            "assumption_effects": [],
        }

        for resource_kind, resource_code in _assignment_resource_codes(assignment):
            predecessor_id = last_resource_trip.get((resource_kind, resource_code))
            if predecessor_id:
                edges[trip.id].append(
                    {
                        "from": predecessor_id,
                        "kind": resource_kind,
                    }
                )
            last_resource_trip[(resource_kind, resource_code)] = trip.id

        if trip.cargo_layer_step_id:
            predecessor_id = last_voyage_trip.get(trip.voyage_id)
            if predecessor_id:
                edges[trip.id].append(
                    {
                        "from": predecessor_id,
                        "kind": "cargo_layer",
                    }
                )
            last_voyage_trip[trip.voyage_id] = trip.id

    return states, edges


def _assignment_resource_codes(assignment: Assignment | None) -> list[tuple[str, str]]:
    if assignment is None:
        return []
    resources = [
        ("tug", assignment.tug.code if assignment.tug else ""),
        ("barge", assignment.barge.code if assignment.barge else ""),
        ("jetty", assignment.jetty.code if assignment.jetty else ""),
        ("cts", assignment.cts.code if assignment.cts else ""),
    ]
    return [(kind, code) for kind, code in resources if code]


def _assignment_resource_code_map(assignment: Assignment | None) -> dict[str, str]:
    return dict(_assignment_resource_codes(assignment))


def _resource_code_items(resource_codes: dict[str, str]) -> list[tuple[str, str]]:
    return [(kind, code) for kind, code in resource_codes.items() if code]


def _apply_scenario_assumptions(*, states: dict, assumptions: list[ScenarioAssumption]) -> dict:
    window_overrides = {}
    for assumption in assumptions:
        if assumption.kind == ScenarioAssumption.Kind.TRIP_DELAY:
            state = states.get(assumption.scope_id)
            if state is None:
                continue
            delay_minutes = int(assumption.payload["delay_minutes"])
            state["direct_shift_minutes"] += delay_minutes
            _record_assumption_effect(
                state=state,
                assumption=assumption,
                effect={"delayMinutes": delay_minutes},
            )
            continue

        if assumption.kind == ScenarioAssumption.Kind.ASSET_OUTAGE:
            _apply_asset_outage_assumption(
                states=states,
                assumption=assumption,
            )
            continue

        if assumption.kind == ScenarioAssumption.Kind.RATE_CHANGE:
            _apply_rate_change_assumption(
                states=states,
                assumption=assumption,
            )
            continue

        if assumption.kind == ScenarioAssumption.Kind.WINDOW_CHANGE:
            window_code = str(assumption.payload["window_code"]).strip()
            if not window_code:
                continue
            window_overrides[window_code] = {
                "window_start": assumption.effective_from,
                "window_end": assumption.effective_to,
                "assumption_id": assumption.assumption_id,
            }
            continue

        if assumption.kind == ScenarioAssumption.Kind.OGV_ETA_CHANGE:
            _apply_ogv_eta_change_assumption(
                states=states,
                assumption=assumption,
            )
            continue

        if assumption.kind == ScenarioAssumption.Kind.MANUAL_REASSIGNMENT:
            _apply_manual_reassignment_assumption(
                states=states,
                assumption=assumption,
            )
    return window_overrides


def _apply_ogv_eta_change_assumption(*, states: dict, assumption: ScenarioAssumption) -> None:
    projected_eta = parse_datetime(str(assumption.payload["eta"]))
    if projected_eta is None or assumption.scope_id is None:
        return
    if timezone.is_naive(projected_eta):
        projected_eta = timezone.make_aware(projected_eta)

    voyage_states = [
        state for state in states.values() if state["trip"].voyage_id == assumption.scope_id
    ]
    if not voyage_states:
        return

    first_state = min(
        voyage_states,
        key=lambda state: (state["trip"].sequence, state["trip"].trip_id),
    )
    eta_delay_minutes = max(
        0,
        _ceil_minutes(projected_eta - first_state["trip"].voyage.eta),
    )
    first_state["direct_shift_minutes"] = max(
        first_state["direct_shift_minutes"],
        eta_delay_minutes,
    )
    _record_assumption_effect(
        state=first_state,
        assumption=assumption,
        effect={
            "baselineEta": first_state["trip"].voyage.eta.isoformat(),
            "projectedEta": projected_eta.isoformat(),
            "delayMinutes": eta_delay_minutes,
        },
    )


def _apply_manual_reassignment_assumption(
    *,
    states: dict,
    assumption: ScenarioAssumption,
) -> None:
    assignment_id = assumption.payload["assignment_id"]
    state = next(
        (
            candidate
            for candidate in states.values()
            if candidate["assignment"] and candidate["assignment"].id == assignment_id
        ),
        None,
    )
    if state is None:
        return

    projected_resources = dict(state["projected_resource_codes"])
    replacement_resources = {}
    tug_code = str(assumption.payload.get("tug_code", "")).strip()
    barge_code = str(assumption.payload.get("barge_code", "")).strip()
    cts_code = str(assumption.payload.get("cts_code", "")).strip()
    if tug_code:
        projected_resources["tug"] = tug_code
        replacement_resources["tug"] = tug_code
    if barge_code:
        projected_resources["barge"] = barge_code
        replacement_resources["barge"] = barge_code
    if cts_code:
        projected_resources["cts"] = cts_code
        replacement_resources["cts"] = cts_code

    state["projected_resource_codes"] = projected_resources
    _record_assumption_effect(
        state=state,
        assumption=assumption,
        effect={
            "baselineResources": state["baseline_resource_codes"],
            "projectedResources": projected_resources,
            "replacementResources": replacement_resources,
        },
    )


def _rebuild_projected_resource_edges(*, states: dict, edges: dict) -> None:
    for trip_id, trip_edges in edges.items():
        edges[trip_id] = [
            edge for edge in trip_edges if edge["kind"] == "cargo_layer"
        ]

    last_resource_trip = {}
    ordered_states = sorted(
        states.values(),
        key=lambda state: (state["trip"].sequence, state["trip"].trip_id),
    )
    for state in ordered_states:
        for resource_kind, resource_code in _resource_code_items(
            state["projected_resource_codes"]
        ):
            predecessor_id = last_resource_trip.get((resource_kind, resource_code))
            if predecessor_id:
                edges[state["trip"].id].append(
                    {
                        "from": predecessor_id,
                        "kind": resource_kind,
                    }
                )
            last_resource_trip[(resource_kind, resource_code)] = state["trip"].id


def _apply_asset_outage_assumption(*, states: dict, assumption: ScenarioAssumption) -> None:
    asset_code = str(assumption.payload["asset_code"]).strip()
    if not asset_code or assumption.effective_from is None or assumption.effective_to is None:
        return

    for state in states.values():
        assignment = state["assignment"]
        resource_codes = {code for _, code in _assignment_resource_codes(assignment)}
        if asset_code not in resource_codes:
            continue
        if not _overlaps(
            start=state["baseline_start"],
            end=state["baseline_end"],
            window_start=assumption.effective_from,
            window_end=assumption.effective_to,
        ):
            continue
        delay_minutes = max(
            0,
            _ceil_minutes(assumption.effective_to - state["baseline_start"]),
        )
        state["direct_shift_minutes"] = max(state["direct_shift_minutes"], delay_minutes)
        _record_assumption_effect(
            state=state,
            assumption=assumption,
            effect={
                "assetCode": asset_code,
                "delayMinutes": delay_minutes,
                "effectiveFrom": assumption.effective_from.isoformat(),
                "effectiveTo": assumption.effective_to.isoformat(),
            },
        )


def _apply_rate_change_assumption(*, states: dict, assumption: ScenarioAssumption) -> None:
    asset_code = str(assumption.payload.get("asset_code", "")).strip()
    if not asset_code:
        return
    rate_tph = float(assumption.payload["rate_tph"])

    for state in states.values():
        assignment = state["assignment"]
        if assignment is None:
            continue
        if (
            assumption.effective_from
            and assumption.effective_to
            and not _overlaps(
                start=state["baseline_start"],
                end=state["baseline_end"],
                window_start=assumption.effective_from,
                window_end=assumption.effective_to,
            )
        ):
            continue
        events_by_type = _events_by_type(state["trip"])
        if assignment.jetty and assignment.jetty.code == asset_code:
            baseline_minutes = _event_span_minutes(
                events_by_type=events_by_type,
                start_type=ScheduleEvent.EventType.LOAD_START,
                end_type=ScheduleEvent.EventType.LOAD_COMPLETE,
            )
            projected_minutes = _duration_minutes_for_rate(
                quantity_mt=state["trip"].planned_quantity_mt,
                rate_tph=rate_tph,
            )
            delta_minutes = projected_minutes - baseline_minutes
            state["load_duration_delta_minutes"] += delta_minutes
            _record_assumption_effect(
                state=state,
                assumption=assumption,
                effect={
                    "assetCode": asset_code,
                    "rateTph": rate_tph,
                    "phase": "load",
                    "durationDeltaMinutes": delta_minutes,
                },
            )
        if assignment.cts and assignment.cts.code == asset_code:
            baseline_minutes = _event_span_minutes(
                events_by_type=events_by_type,
                start_type=ScheduleEvent.EventType.ARRIVE_CTS,
                end_type=ScheduleEvent.EventType.DISCHARGE_COMPLETE,
            )
            projected_minutes = _duration_minutes_for_rate(
                quantity_mt=state["trip"].planned_quantity_mt,
                rate_tph=rate_tph,
            )
            delta_minutes = projected_minutes - baseline_minutes
            state["discharge_duration_delta_minutes"] += delta_minutes
            _record_assumption_effect(
                state=state,
                assumption=assumption,
                effect={
                    "assetCode": asset_code,
                    "rateTph": rate_tph,
                    "phase": "discharge",
                    "durationDeltaMinutes": delta_minutes,
                },
            )


def _record_assumption_effect(
    *,
    state: dict,
    assumption: ScenarioAssumption,
    effect: dict,
) -> None:
    state["direct_assumption_ids"].append(assumption.assumption_id)
    state["assumption_effects"].append(
        {
            "assumptionId": assumption.assumption_id,
            "kind": assumption.kind,
            **effect,
        }
    )


def _state_source_assumption_ids(state: dict) -> list[str]:
    assumption_ids = list(state["direct_assumption_ids"])
    for dependency in state.get("dependency_sources", []):
        for assumption_id in dependency.get("sourceAssumptionIds", []):
            if assumption_id not in assumption_ids:
                assumption_ids.append(assumption_id)
    return assumption_ids


def _propagate_projection_graph(*, states: dict, edges: dict) -> None:
    ordered_states = sorted(
        states.values(),
        key=lambda state: (
            state["trip"].sequence,
            state["trip"].trip_id,
        ),
    )
    for state in ordered_states:
        dependency_shift_minutes = 0
        dependency_sources = []
        for edge in edges[state["trip"].id]:
            predecessor = states[edge["from"]]
            required_shift_minutes = max(
                0,
                _ceil_minutes(
                    predecessor["projected_end"] - predecessor["baseline_end"]
                ),
            )
            if required_shift_minutes > dependency_shift_minutes:
                dependency_shift_minutes = required_shift_minutes
            if required_shift_minutes:
                dependency_sources.append(
                    {
                        "tripId": predecessor["trip"].trip_id,
                        "kind": edge["kind"],
                        "delayMinutes": required_shift_minutes,
                        "sourceAssumptionIds": _state_source_assumption_ids(predecessor),
                    }
                )

        state["dependency_sources"] = dependency_sources
        state["start_shift_minutes"] = max(
            state["direct_shift_minutes"],
            dependency_shift_minutes,
        )
        state["projected_start"] = state["baseline_start"] + timedelta(
            minutes=state["start_shift_minutes"]
        )
        state["projected_end"] = state["baseline_end"] + timedelta(
            minutes=(
                state["start_shift_minutes"]
                + state["load_duration_delta_minutes"]
                + state["discharge_duration_delta_minutes"]
            )
        )


def _persist_projection_state(*, run: ScenarioRun, state: dict):
    trip = state["trip"]
    assignment = state["assignment"]
    source_assumption_ids = _state_source_assumption_ids(state)
    event_projections = []
    for event in trip.events.order_by("sequence"):
        event_delta_minutes = state["start_shift_minutes"]
        if event.sequence >= _event_sequence(trip, ScheduleEvent.EventType.LOAD_COMPLETE):
            event_delta_minutes += state["load_duration_delta_minutes"]
        if event.event_type == ScheduleEvent.EventType.DISCHARGE_COMPLETE:
            event_delta_minutes += state["discharge_duration_delta_minutes"]
        projected_at = event.planned_at + timedelta(minutes=event_delta_minutes)
        event_projections.append(
            ScenarioEventProjection.objects.create(
                run=run,
                event=event,
                trip=trip,
                event_type=event.event_type,
                baseline_at=event.planned_at,
                projected_at=projected_at,
                projected_status=(
                    ScheduleEvent.Status.DELAYED
                    if event_delta_minutes
                    else event.status
                ),
                delay_minutes=event_delta_minutes,
                metadata={
                    "sourceAssumptionIds": source_assumption_ids,
                    "dependencySources": state["dependency_sources"],
                },
            )
        )

    event_index = {
        projection.event_type: projection
        for projection in event_projections
    }
    assignment_delta = {}
    if assignment:
        departure = event_index.get(ScheduleEvent.EventType.DEPART_JETTY)
        arrival = event_index.get(ScheduleEvent.EventType.ARRIVE_CTS)
        assignment_delta = {
            "plannedDeparture": assignment.planned_departure.isoformat(),
            "projectedDeparture": (
                departure.projected_at.isoformat() if departure else None
            ),
            "plannedArrival": assignment.planned_arrival.isoformat(),
            "projectedArrival": (
                arrival.projected_at.isoformat() if arrival else None
            ),
            "baselineResources": state["baseline_resource_codes"],
            "projectedResources": state["projected_resource_codes"],
            "resourceChanged": (
                state["baseline_resource_codes"] != state["projected_resource_codes"]
            ),
        }

    trip_projection = ScenarioTripProjection.objects.create(
        run=run,
        trip=trip,
        baseline_start=state["baseline_start"],
        baseline_end=state["baseline_end"],
        projected_start=state["projected_start"],
        projected_end=state["projected_end"],
        projected_status=trip.status,
        delay_minutes=_ceil_minutes(state["projected_end"] - state["baseline_end"]),
        assignment_delta=assignment_delta,
        metadata={
            "sourceAssumptionIds": source_assumption_ids,
            "dependencySources": state["dependency_sources"],
            "assumptionEffects": state["assumption_effects"],
            "loadDurationDeltaMinutes": state["load_duration_delta_minutes"],
            "dischargeDurationDeltaMinutes": state["discharge_duration_delta_minutes"],
            "baselineResourceCodes": state["baseline_resource_codes"],
            "projectedResourceCodes": state["projected_resource_codes"],
        },
    )
    return trip_projection, event_projections


def _create_simulation_impact_assessments(
    *,
    run: ScenarioRun,
    states: dict,
    event_projection_index: dict,
    window_overrides: dict,
) -> list[ImpactChainAssessment]:
    assessments = []
    for state in states.values():
        trip = state["trip"]
        assignment = state["assignment"]
        if assignment is None:
            continue
        projections = event_projection_index.get(trip.id, {})
        bridge_projection = projections.get(ScheduleEvent.EventType.BRIDGE_CROSS)
        tide_projection = projections.get(ScheduleEvent.EventType.TIDE_GATE)
        bridge_eval = _evaluate_bridge_window(
            assignment=assignment,
            projected_at=bridge_projection.projected_at if bridge_projection else None,
            window_overrides=window_overrides,
        )
        tide_eval = _evaluate_tide_window(
            assignment=assignment,
            projected_at=tide_projection.projected_at if tide_projection else None,
            window_overrides=window_overrides,
        )
        window_assumption_ids = _window_assumption_ids(
            evaluations=[bridge_eval, tide_eval],
            window_overrides=window_overrides,
        )
        source_assumption_ids = [
            *_state_source_assumption_ids(state),
            *window_assumption_ids,
        ]
        delay_minutes = _ceil_minutes(state["projected_start"] - state["baseline_start"])
        if (
            not state["direct_assumption_ids"]
            and not window_assumption_ids
            and not state["dependency_sources"]
            and bridge_eval["status"] == ImpactChainAssessment.Status.OK
            and tide_eval["status"] == ImpactChainAssessment.Status.OK
        ):
            continue
        nodes = _simulation_impact_nodes(
            run=run,
            state=state,
            delay_minutes=delay_minutes,
            bridge_eval=bridge_eval,
            tide_eval=tide_eval,
            source_assumption_ids=source_assumption_ids,
        )
        assessment = ImpactChainAssessment.objects.create(
            assessment_id=f"ICA-{run.run_id}-T{trip.id:04d}",
            plan_version=run.baseline_version,
            trip=trip,
            assignment=assignment,
            source_kind=ImpactChainAssessment.SourceKind.SIMULATION,
            status=_worst_status(node["status"] for node in nodes),
            delay_minutes=delay_minutes,
            nodes=nodes,
            metadata={
                "algorithmVersion": run.algorithm_version,
                "calculatedAt": timezone.now().isoformat(),
                "scenarioId": run.scenario.scenario_id,
                "scenarioRunId": run.run_id,
                "sourceAssumptionIds": source_assumption_ids,
                "dependencySources": state["dependency_sources"],
                "bridgeWindowId": bridge_eval.get("window_id"),
                "tideWindowId": tide_eval.get("window_id"),
            },
        )
        assessments.append(assessment)
    return assessments


def _simulation_impact_nodes(
    *,
    run: ScenarioRun,
    state: dict,
    delay_minutes: int,
    bridge_eval: dict,
    tide_eval: dict,
    source_assumption_ids: list[str],
) -> list[dict]:
    trip = state["trip"]
    delay_status = (
        ImpactChainAssessment.Status.WARNING if delay_minutes else ImpactChainAssessment.Status.OK
    )
    navigation_status = _worst_status([bridge_eval["status"], tide_eval["status"]])
    source_label = (
        state["assumption_effects"][0]["kind"].replace("_", " ").upper()
        if state["assumption_effects"]
        else "WINDOW CHANGE"
        if source_assumption_ids
        else "DEPENDENCY PROPAGATION"
    )
    return [
        {
            "id": "source",
            "type": "source_event",
            "label": source_label,
            "value": run.run_id,
            "status": delay_status,
            "detail": ", ".join(source_assumption_ids) or "Inherited from prior trip.",
            "plannedAt": state["baseline_start"].isoformat(),
            "projectedAt": state["projected_start"].isoformat(),
        },
        {
            "id": "logistics",
            "type": "logistics_delay",
            "label": "TRIP DELAY",
            "value": f"+{delay_minutes}m",
            "status": delay_status,
            "detail": "Projected start after direct assumptions and dependency propagation.",
        },
        _window_node(node_id="bridge", evaluation=bridge_eval),
        _window_node(node_id="tide", evaluation=tide_eval),
        {
            "id": "target",
            "type": "final_risk_target",
            "label": "FINAL RISK TARGET",
            "value": trip.voyage.vessel_name,
            "status": navigation_status,
            "detail": trip.trip_id,
        },
    ]


def _materialize_scenario_kpis(
    *,
    run: ScenarioRun,
    trip_projections: list[ScenarioTripProjection],
    event_projection_index: dict,
    assessments: list[ImpactChainAssessment],
) -> dict:
    constraint_evaluations = _persist_window_constraint_evaluations(
        run=run,
        assessments=assessments,
    )
    ogv_projections = _persist_ogv_projections(
        run=run,
        trip_projections=trip_projections,
        event_projection_index=event_projection_index,
    )
    resource_utilizations = _persist_resource_utilizations(
        run=run,
        trip_projections=trip_projections,
    )
    constraint_evaluations.extend(
        _persist_ogv_constraint_evaluations(
            run=run,
            ogv_projections=ogv_projections,
        )
    )
    constraint_evaluations.extend(
        _persist_asset_outage_constraint_evaluations(
            run=run,
            trip_projections=trip_projections,
        )
    )
    constraint_evaluations.extend(
        _persist_resource_overlap_constraints(
            run=run,
            trip_projections=trip_projections,
        )
    )
    constraint_evaluations.extend(
        _persist_projected_assignment_constraint_evaluations(
            run=run,
            trip_projections=trip_projections,
        )
    )

    critical_count = sum(
        evaluation.severity == ScenarioConstraintEvaluation.Severity.CRITICAL
        for evaluation in constraint_evaluations
    )
    warning_count = sum(
        evaluation.severity == ScenarioConstraintEvaluation.Severity.WARNING
        for evaluation in constraint_evaluations
    )
    demurrage_delta = sum(
        (projection.demurrage_delta_usd for projection in ogv_projections),
        Decimal("0.00"),
    )
    avg_utilization_delta = (
        sum(
            (utilization.utilization_delta_pct for utilization in resource_utilizations),
            Decimal("0.00"),
        )
        / Decimal(len(resource_utilizations))
        if resource_utilizations
        else Decimal("0.00")
    )
    max_completion_delta = max(
        (projection.completion_delta_minutes for projection in ogv_projections),
        default=0,
    )
    return {
        "constraintEvaluations": constraint_evaluations,
        "ogvProjections": ogv_projections,
        "resourceUtilizations": resource_utilizations,
        "constraintSummary": {
            "total": len(constraint_evaluations),
            "critical": critical_count,
            "warning": warning_count,
        },
        "ogvSummary": {
            "count": len(ogv_projections),
            "completionRiskCount": sum(
                projection.risk_status != ScenarioOgvProjection.RiskStatus.OK
                for projection in ogv_projections
            ),
            "maxCompletionDeltaMinutes": max_completion_delta,
            "demurrageDeltaUsd": float(demurrage_delta),
        },
        "utilizationSummary": {
            "count": len(resource_utilizations),
            "averageUtilizationDeltaPct": float(
                avg_utilization_delta.quantize(Decimal("0.01"))
            ),
            "totalWaitingMinutes": sum(
                utilization.waiting_minutes for utilization in resource_utilizations
            ),
        },
    }


def _persist_window_constraint_evaluations(
    *,
    run: ScenarioRun,
    assessments: list[ImpactChainAssessment],
) -> list[ScenarioConstraintEvaluation]:
    evaluations = []
    for assessment in assessments:
        source_assumption_ids = assessment.metadata.get("sourceAssumptionIds", [])
        for node in assessment.nodes:
            if not str(node.get("type", "")).endswith("_window"):
                continue
            severity = _constraint_severity_from_status(node.get("status"))
            if severity == ScenarioConstraintEvaluation.Severity.INFO:
                continue
            evaluations.append(
                ScenarioConstraintEvaluation.objects.create(
                    run=run,
                    evaluation_id=(
                        f"SCE-{run.run_id}-{assessment.trip_id or 0:04d}-"
                        f"{node['id'].upper()}"
                    ),
                    trip=assessment.trip,
                    code=_constraint_code_from_node(node),
                    severity=severity,
                    affected_object_type=node["type"],
                    affected_object_id=str(node.get("windowStart") or node.get("label") or ""),
                    baseline_value={
                        "windowStart": node.get("windowStart"),
                        "windowEnd": node.get("windowEnd"),
                    },
                    projected_value={
                        "projectedAt": node.get("projectedAt"),
                        "value": node.get("value"),
                    },
                    margin_minutes=node.get("marginMinutes"),
                    source_assumption_ids=source_assumption_ids,
                    message=node.get("detail", ""),
                    metadata={
                        "impactAssessmentId": assessment.assessment_id,
                        "nodeId": node["id"],
                    },
                )
            )
    return evaluations


def _persist_ogv_projections(
    *,
    run: ScenarioRun,
    trip_projections: list[ScenarioTripProjection],
    event_projection_index: dict,
) -> list[ScenarioOgvProjection]:
    by_voyage: dict[int, list[ScenarioTripProjection]] = {}
    for projection in trip_projections:
        by_voyage.setdefault(projection.trip.voyage_id, []).append(projection)

    ogv_projections = []
    for voyage_id, projections in by_voyage.items():
        voyage = projections[0].trip.voyage
        source_assumption_ids = _projection_source_assumption_ids(projections)
        baseline_completion = max(
            (
                _completion_event_for_projection(
                    projection=projection,
                    event_projection_index=event_projection_index,
                )[0]
                for projection in projections
            ),
        )
        projected_completion = max(
            (
                _completion_event_for_projection(
                    projection=projection,
                    event_projection_index=event_projection_index,
                )[1]
                for projection in projections
            ),
        )
        completion_delta_minutes = _ceil_minutes(projected_completion - baseline_completion)
        baseline_demurrage_minutes = max(
            0,
            _ceil_minutes(baseline_completion - voyage.laycan_end),
        )
        projected_demurrage_minutes = max(
            0,
            _ceil_minutes(projected_completion - voyage.laycan_end),
        )
        demurrage_delta_usd = _demurrage_delta_usd(
            voyage=voyage,
            baseline_minutes=baseline_demurrage_minutes,
            projected_minutes=projected_demurrage_minutes,
        )
        risk_status = _ogv_risk_status(
            projected_completion=projected_completion,
            laycan_end=voyage.laycan_end,
            completion_delta_minutes=completion_delta_minutes,
        )
        ogv_projections.append(
            ScenarioOgvProjection.objects.create(
                run=run,
                voyage=voyage,
                baseline_completion_at=baseline_completion,
                projected_completion_at=projected_completion,
                completion_delta_minutes=completion_delta_minutes,
                laycan_end=voyage.laycan_end,
                baseline_demurrage_minutes=baseline_demurrage_minutes,
                projected_demurrage_minutes=projected_demurrage_minutes,
                demurrage_delta_usd=demurrage_delta_usd,
                risk_status=risk_status,
                metadata={
                    "tripProjectionIds": [projection.id for projection in projections],
                    "vesselName": voyage.vessel_name,
                    "demurrageRateUsdPerDay": str(voyage.demurrage_rate_usd_per_day),
                    "sourceAssumptionIds": source_assumption_ids,
                },
            )
        )
    return ogv_projections


def _persist_resource_utilizations(
    *,
    run: ScenarioRun,
    trip_projections: list[ScenarioTripProjection],
) -> list[ScenarioResourceUtilization]:
    horizon_minutes = max(
        1,
        _ceil_minutes(
            run.baseline_version.plan.horizon_end
            - run.baseline_version.plan.horizon_start
        ),
    )
    buckets: dict[tuple[str, str], dict] = {}
    for projection in trip_projections:
        baseline_resources = projection.metadata.get("baselineResourceCodes", {})
        projected_resources = projection.metadata.get("projectedResourceCodes", {})
        for resource_type, resource_code in _resource_code_items(baseline_resources):
            bucket = buckets.setdefault(
                (resource_type, resource_code),
                {
                    "baseline": 0,
                    "projected": 0,
                    "waiting": 0,
                    "trips": [],
                },
            )
            bucket["baseline"] += max(
                0,
                _ceil_minutes(projection.baseline_end - projection.baseline_start),
            )
            bucket["trips"].append(projection.trip.trip_id)

        for resource_type, resource_code in _resource_code_items(projected_resources):
            bucket = buckets.setdefault(
                (resource_type, resource_code),
                {
                    "baseline": 0,
                    "projected": 0,
                    "waiting": 0,
                    "trips": [],
                },
            )
            bucket["projected"] += max(
                0,
                _ceil_minutes(projection.projected_end - projection.projected_start),
            )
            bucket["waiting"] += max(0, projection.delay_minutes)
            if projection.trip.trip_id not in bucket["trips"]:
                bucket["trips"].append(projection.trip.trip_id)

    rows = []
    for (resource_type, resource_code), bucket in buckets.items():
        baseline_idle = max(0, horizon_minutes - bucket["baseline"])
        projected_idle = max(0, horizon_minutes - bucket["projected"])
        utilization_delta_pct = (
            (
                Decimal(bucket["projected"] - bucket["baseline"])
                / Decimal(horizon_minutes)
            )
            * Decimal("100")
        ).quantize(Decimal("0.01"))
        rows.append(
            ScenarioResourceUtilization.objects.create(
                run=run,
                resource_type=resource_type,
                resource_code=resource_code,
                baseline_occupied_minutes=bucket["baseline"],
                projected_occupied_minutes=bucket["projected"],
                baseline_idle_minutes=baseline_idle,
                projected_idle_minutes=projected_idle,
                waiting_minutes=bucket["waiting"],
                utilization_delta_pct=utilization_delta_pct,
                metadata={
                    "horizonMinutes": horizon_minutes,
                    "tripIds": bucket["trips"],
                },
            )
        )
    return rows


def _persist_ogv_constraint_evaluations(
    *,
    run: ScenarioRun,
    ogv_projections: list[ScenarioOgvProjection],
) -> list[ScenarioConstraintEvaluation]:
    evaluations = []
    for index, projection in enumerate(ogv_projections, start=1):
        if projection.projected_completion_at > projection.laycan_end:
            evaluations.append(
                ScenarioConstraintEvaluation.objects.create(
                    run=run,
                    evaluation_id=f"SCE-{run.run_id}-OGV-{index:02d}-LAYCAN",
                    trip=None,
                    code="LAYCAN_BREACH",
                    severity=ScenarioConstraintEvaluation.Severity.CRITICAL,
                    affected_object_type="ogv",
                    affected_object_id=projection.voyage.voyage_id,
                    baseline_value={
                        "completionAt": projection.baseline_completion_at.isoformat(),
                        "laycanEnd": projection.laycan_end.isoformat(),
                    },
                    projected_value={
                        "completionAt": projection.projected_completion_at.isoformat(),
                    },
                    margin_minutes=-projection.projected_demurrage_minutes,
                    source_assumption_ids=projection.metadata.get("sourceAssumptionIds", []),
                    message=(
                        f"{projection.voyage.vessel_name} projected completion breaches laycan."
                    ),
                    metadata={"ogvProjectionId": projection.id},
                )
            )
        if projection.demurrage_delta_usd > 0:
            evaluations.append(
                ScenarioConstraintEvaluation.objects.create(
                    run=run,
                    evaluation_id=f"SCE-{run.run_id}-OGV-{index:02d}-DEMURRAGE",
                    trip=None,
                    code="DEMURRAGE_RISK",
                    severity=ScenarioConstraintEvaluation.Severity.WARNING,
                    affected_object_type="ogv",
                    affected_object_id=projection.voyage.voyage_id,
                    baseline_value={
                        "demurrageMinutes": projection.baseline_demurrage_minutes,
                    },
                    projected_value={
                        "demurrageMinutes": projection.projected_demurrage_minutes,
                        "demurrageDeltaUsd": float(projection.demurrage_delta_usd),
                    },
                    margin_minutes=-projection.projected_demurrage_minutes,
                    source_assumption_ids=projection.metadata.get("sourceAssumptionIds", []),
                    message=(
                        f"{projection.voyage.vessel_name} has projected demurrage exposure."
                    ),
                    metadata={"ogvProjectionId": projection.id},
                )
            )
    return evaluations


def _persist_resource_overlap_constraints(
    *,
    run: ScenarioRun,
    trip_projections: list[ScenarioTripProjection],
) -> list[ScenarioConstraintEvaluation]:
    intervals: dict[tuple[str, str], list[tuple]] = {}
    for projection in trip_projections:
        for resource_type, resource_code in _resource_code_items(
            projection.metadata.get("projectedResourceCodes", {})
        ):
            intervals.setdefault((resource_type, resource_code), []).append(
                (projection.projected_start, projection.projected_end, projection)
            )

    evaluations = []
    overlap_index = 1
    for (resource_type, resource_code), resource_intervals in intervals.items():
        ordered = sorted(resource_intervals, key=lambda row: row[0])
        for previous, current in zip(ordered, ordered[1:]):
            if previous[1] <= current[0]:
                continue
            code = _resource_overlap_code(resource_type)
            severity = (
                ScenarioConstraintEvaluation.Severity.WARNING
                if resource_type in {"jetty", "cts"}
                else ScenarioConstraintEvaluation.Severity.CRITICAL
            )
            overlap_minutes = _ceil_minutes(previous[1] - current[0])
            evaluations.append(
                ScenarioConstraintEvaluation.objects.create(
                    run=run,
                    evaluation_id=f"SCE-{run.run_id}-RESOURCE-{overlap_index:03d}",
                    trip=current[2].trip,
                    code=code,
                    severity=severity,
                    affected_object_type=resource_type,
                    affected_object_id=resource_code,
                    baseline_value={
                        "previousTrip": previous[2].trip.trip_id,
                        "currentTrip": current[2].trip.trip_id,
                    },
                    projected_value={
                        "previousEnd": previous[1].isoformat(),
                        "currentStart": current[0].isoformat(),
                    },
                    margin_minutes=-overlap_minutes,
                    source_assumption_ids=current[2].metadata.get("sourceAssumptionIds", []),
                    message=(
                        f"{resource_code} is double-booked for {overlap_minutes} projected minutes."
                    ),
                    metadata={
                        "previousTripProjectionId": previous[2].id,
                        "currentTripProjectionId": current[2].id,
                    },
                )
            )
            overlap_index += 1
    return evaluations


def _persist_asset_outage_constraint_evaluations(
    *,
    run: ScenarioRun,
    trip_projections: list[ScenarioTripProjection],
) -> list[ScenarioConstraintEvaluation]:
    evaluations = []
    outage_index = 1
    for projection in trip_projections:
        for effect in projection.metadata.get("assumptionEffects", []):
            if effect.get("kind") != ScenarioAssumption.Kind.ASSET_OUTAGE:
                continue
            evaluations.append(
                ScenarioConstraintEvaluation.objects.create(
                    run=run,
                    evaluation_id=f"SCE-{run.run_id}-OUTAGE-{outage_index:03d}",
                    trip=projection.trip,
                    code="ASSET_OUTAGE_OVERLAP",
                    severity=ScenarioConstraintEvaluation.Severity.CRITICAL,
                    affected_object_type="asset",
                    affected_object_id=effect.get("assetCode", ""),
                    baseline_value={
                        "effectiveFrom": effect.get("effectiveFrom"),
                        "effectiveTo": effect.get("effectiveTo"),
                    },
                    projected_value={
                        "delayMinutes": effect.get("delayMinutes", 0),
                    },
                    margin_minutes=-effect.get("delayMinutes", 0),
                    source_assumption_ids=[effect.get("assumptionId", "")],
                    message=(
                        f"{effect.get('assetCode', 'Asset')} is unavailable inside "
                        f"{projection.trip.trip_id}."
                    ),
                    metadata={"tripProjectionId": projection.id},
                )
            )
            outage_index += 1
    return evaluations


def _persist_projected_assignment_constraint_evaluations(
    *,
    run: ScenarioRun,
    trip_projections: list[ScenarioTripProjection],
) -> list[ScenarioConstraintEvaluation]:
    evaluations = []
    for index, projection in enumerate(trip_projections, start=1):
        projected_resources = projection.metadata.get("projectedResourceCodes", {})
        tug_code = projected_resources.get("tug", "")
        barge_code = projected_resources.get("barge", "")
        if not tug_code or not barge_code:
            continue
        incompatible = AssetCompatibilityRule.objects.filter(
            rule_type="tug_barge",
            left_code=tug_code,
            right_code=barge_code,
            is_compatible=False,
        ).exists()
        if not incompatible:
            continue
        evaluations.append(
            ScenarioConstraintEvaluation.objects.create(
                run=run,
                evaluation_id=f"SCE-{run.run_id}-ASSIGNMENT-{index:03d}",
                trip=projection.trip,
                code="TUG_BARGE_INCOMPATIBLE",
                severity=ScenarioConstraintEvaluation.Severity.CRITICAL,
                affected_object_type="assignment",
                affected_object_id=projection.trip.trip_id,
                baseline_value=projection.metadata.get("baselineResourceCodes", {}),
                projected_value=projected_resources,
                margin_minutes=None,
                source_assumption_ids=projection.metadata.get("sourceAssumptionIds", []),
                message=f"{tug_code} is incompatible with {barge_code}.",
                metadata={"tripProjectionId": projection.id},
            )
        )
    return evaluations


def _scenario_projection_summary(
    *,
    run: ScenarioRun,
    assumptions: list[ScenarioAssumption],
    trip_projections: list[ScenarioTripProjection],
    assessments: list[ImpactChainAssessment],
    kpis: dict,
) -> dict:
    conflict = run.scenario.source_conflict
    override = run.scenario.source_override
    source_label = (
        conflict.code
        if conflict
        else override.reason_code.upper()
        if override
        else "MANUAL_SCENARIO"
    )
    affected_vessel = (
        conflict.trip.voyage.vessel_name
        if conflict and conflict.trip
        else override.trip.voyage.vessel_name
        if override and override.trip
        else ""
    )
    changed_trips = [
        projection
        for projection in trip_projections
        if projection.delay_minutes or projection.assignment_delta.get("resourceChanged")
    ]
    critical_count = kpis["constraintSummary"]["critical"]
    warning_count = kpis["constraintSummary"]["warning"]
    max_delay = max((projection.delay_minutes for projection in trip_projections), default=0)
    feasibility_pct = max(0, 100 - (critical_count * 20) - (warning_count * 5))
    return {
        "impactSummary": {
            "sourceConflict": source_label,
            "affectedVessel": affected_vessel,
            "feasibilityPct": feasibility_pct,
            "assumptionCount": len(assumptions),
            "projectedTripCount": len(trip_projections),
            "changedTripCount": len(changed_trips),
        },
        "deltaSummary": {
            "delayDeltaMinutes": max_delay,
            "demurrageDeltaUsd": kpis["ogvSummary"]["demurrageDeltaUsd"],
            "fleetUtilizationPct": kpis["utilizationSummary"]["averageUtilizationDeltaPct"],
            "remainingViolations": critical_count,
            "warningWindowCount": warning_count,
            "completionRiskCount": kpis["ogvSummary"]["completionRiskCount"],
            "resourceWaitingMinutes": kpis["utilizationSummary"]["totalWaitingMinutes"],
        },
        "projectionSummary": {
            "tripProjectionCount": len(trip_projections),
            "changedTripCount": len(changed_trips),
            "impactAssessmentCount": len(assessments),
            "constraintEvaluationCount": kpis["constraintSummary"]["total"],
            "ogvProjectionCount": kpis["ogvSummary"]["count"],
            "resourceUtilizationCount": kpis["utilizationSummary"]["count"],
            "maxDelayMinutes": max_delay,
        },
        "constraintSummary": kpis["constraintSummary"],
        "ogvSummary": kpis["ogvSummary"],
        "utilizationSummary": kpis["utilizationSummary"],
    }


def _scenario_recovery_actions(summary: dict) -> list[str]:
    projection_summary = summary["projectionSummary"]
    actions = [
        (
            f"Review {projection_summary['changedTripCount']} changed trip projection"
            f"{'' if projection_summary['changedTripCount'] == 1 else 's'}."
        )
    ]
    if summary["deltaSummary"]["remainingViolations"]:
        actions.append("Review projected critical window misses before promotion.")
    elif summary["deltaSummary"]["warningWindowCount"]:
        actions.append("Review projected tight-window margins before promotion.")
    else:
        actions.append("Projected bridge and tide gates remain feasible.")
    return actions


def _apply_window_overrides(*, kind: str, windows: list, window_overrides: dict) -> list:
    adjusted_windows = []
    for window in windows:
        override = window_overrides.get(window.code)
        if override and override["window_start"] and override["window_end"]:
            window.window_start = override["window_start"]
            window.window_end = override["window_end"]
        adjusted_windows.append(window)
    return adjusted_windows


def _window_assumption_ids(*, evaluations: list[dict], window_overrides: dict) -> list[str]:
    assumption_ids = []
    for evaluation in evaluations:
        override = window_overrides.get(evaluation.get("window_code"))
        if override and override["assumption_id"] not in assumption_ids:
            assumption_ids.append(override["assumption_id"])
    return assumption_ids


def _constraint_severity_from_status(status: str) -> str:
    if status == ImpactChainAssessment.Status.CRITICAL:
        return ScenarioConstraintEvaluation.Severity.CRITICAL
    if status == ImpactChainAssessment.Status.WARNING:
        return ScenarioConstraintEvaluation.Severity.WARNING
    return ScenarioConstraintEvaluation.Severity.INFO


def _constraint_code_from_node(node: dict) -> str:
    label = str(node.get("label") or node.get("type") or "PROJECTED_CONSTRAINT")
    return label.upper().replace(" ", "_").replace("/", "_")


def _completion_event_for_projection(
    *,
    projection: ScenarioTripProjection,
    event_projection_index: dict,
) -> tuple:
    discharge_projection = event_projection_index.get(projection.trip_id, {}).get(
        ScheduleEvent.EventType.DISCHARGE_COMPLETE,
    )
    if discharge_projection is None:
        return projection.baseline_end, projection.projected_end
    return discharge_projection.baseline_at, discharge_projection.projected_at


def _projection_source_assumption_ids(projections: list[ScenarioTripProjection]) -> list[str]:
    assumption_ids = []
    for projection in projections:
        for assumption_id in projection.metadata.get("sourceAssumptionIds", []):
            if assumption_id not in assumption_ids:
                assumption_ids.append(assumption_id)
    return assumption_ids


def _demurrage_delta_usd(*, voyage: OGVVoyage, baseline_minutes: int, projected_minutes: int):
    minute_delta = projected_minutes - baseline_minutes
    if minute_delta == 0:
        return Decimal("0.00")
    return (
        Decimal(minute_delta)
        / Decimal(1440)
        * voyage.demurrage_rate_usd_per_day
    ).quantize(Decimal("0.01"))


def _ogv_risk_status(*, projected_completion, laycan_end, completion_delta_minutes: int) -> str:
    if projected_completion > laycan_end:
        return ScenarioOgvProjection.RiskStatus.CRITICAL
    if completion_delta_minutes > 0:
        return ScenarioOgvProjection.RiskStatus.WARNING
    return ScenarioOgvProjection.RiskStatus.OK


def _resource_overlap_code(resource_type: str) -> str:
    if resource_type == "jetty":
        return "JETTY_OVERLAP"
    if resource_type == "cts":
        return "CTS_CAPACITY_CONFLICT"
    return "ASSET_DOUBLE_BOOKED"


def _events_by_type(trip: Trip) -> dict[str, ScheduleEvent]:
    return {event.event_type: event for event in trip.events.all()}


def _event_span_minutes(*, events_by_type: dict, start_type: str, end_type: str) -> int:
    start_event = events_by_type[start_type]
    end_event = events_by_type[end_type]
    return _ceil_minutes(end_event.planned_at - start_event.planned_at)


def _event_sequence(trip: Trip, event_type: str) -> int:
    event = next(event for event in trip.events.all() if event.event_type == event_type)
    return event.sequence


def _duration_minutes_for_rate(*, quantity_mt: int, rate_tph: float) -> int:
    return math.ceil((quantity_mt / rate_tph) * 60)


def _overlaps(*, start, end, window_start, window_end) -> bool:
    return start < window_end and end > window_start


def _ceil_minutes(delta: timedelta) -> int:
    return math.ceil(delta.total_seconds() / 60)


def generate_plan_version(plan_version: PlanVersion) -> GenerationResult:
    """Regenerate a deterministic trip chain from current demand, master, and constraint data."""

    with transaction.atomic():
        _clear_generated_state(plan_version)

        steps = (
            CargoLayerStep.objects.select_related(
                "voyage",
                "cargo_requirement",
                "coal_grade",
                "planned_barge",
                "planned_jetty",
                "planned_cts",
            )
            .filter(voyage__laycan_start__lte=plan_version.plan.horizon_end)
            .filter(voyage__laycan_end__gte=plan_version.plan.horizon_start)
            .order_by(
                "voyage__laycan_start",
                "voyage__priority",
                "voyage__voyage_id",
                "required_sequence_no",
            )
        )
        tugs = list(Tug.objects.select_related("organization").order_by("code"))
        route_segment = _first_route_segment()
        default_destination = Location.objects.filter(
            location_type=Location.LocationType.TRANSSHIPMENT
        ).first()

        assigned_windows: dict[str, list[tuple]] = {}
        for sequence, step in enumerate(steps, start=1):
            planned_start = step.planned_start or step.voyage.eta + timedelta(hours=sequence)
            planned_end = step.planned_end or planned_start + timedelta(hours=10)
            trip = Trip.objects.create(
                plan_version=plan_version,
                trip_id=f"PI-{plan_version.plan.code}-{sequence:04d}",
                sequence=sequence,
                voyage=step.voyage,
                cargo_requirement=step.cargo_requirement,
                cargo_layer_step=step,
                origin_jetty=step.planned_jetty,
                destination_location=default_destination or step.voyage.anchorage_location,
                planned_start=planned_start,
                planned_end=planned_end,
                planned_quantity_mt=step.required_mt,
                loaded_quantity_mt=max(step.required_mt - step.remaining_mt, 0),
                status=_trip_status(step),
                selection_reason={
                    "source": "deterministic_schedule_generator",
                    "layer_step": step.id,
                    "voyage_priority": step.voyage.priority,
                    "reason_code": "EARLIEST_LAYER_WITH_DECLARED_CHAIN",
                },
            )
            tug = _choose_tug(
                tugs=tugs,
                start=planned_start,
                end=planned_end,
                assigned_windows=assigned_windows,
            )
            if tug:
                assigned_windows.setdefault(tug.code, []).append((planned_start, planned_end))

            assignment = Assignment.objects.create(
                trip=trip,
                tug=tug,
                barge=step.planned_barge,
                jetty=step.planned_jetty,
                cts=step.planned_cts,
                route_segment=route_segment,
                owner_organization=tug.organization if tug else None,
                planned_departure=planned_start + timedelta(hours=2),
                planned_arrival=planned_end - timedelta(hours=2),
                tug_status=_asset_status_label(tug),
                barge_status=_asset_status_label(step.planned_barge),
                next_constraint=step.blocking_reason or step.voyage.next_blocking_constraint,
                next_action=_next_action(step),
                status=_assignment_status(step),
            )
            _create_events(trip=trip, assignment=assignment)
            _validate_trip(plan_version=plan_version, trip=trip, assignment=assignment)

        conflicts = Conflict.objects.filter(plan_version=plan_version)
        blocking_count = conflicts.filter(is_blocking=True, resolved_at__isnull=True).count()
        warning_count = conflicts.filter(severity=Conflict.Severity.WARNING).count()
        plan_version.generated_at = timezone.now()
        plan_version.status = (
            PlanVersion.Status.GENERATED if blocking_count else PlanVersion.Status.VALIDATED
        )
        if blocking_count:
            plan_version.validation_status = PlanVersion.ValidationStatus.BLOCKED
        elif warning_count:
            plan_version.validation_status = PlanVersion.ValidationStatus.WARNING
        else:
            plan_version.validation_status = PlanVersion.ValidationStatus.FEASIBLE
        plan_version.summary = {
            "tripCount": Trip.objects.filter(plan_version=plan_version).count(),
            "conflictCount": conflicts.count(),
            "blockingConflictCount": blocking_count,
            "warningConflictCount": warning_count,
            "firstBlockingConstraint": (
                conflicts.filter(is_blocking=True)
                .order_by("created_at")
                .values_list("code", flat=True)
                .first()
            ),
        }
        plan_version.save(
            update_fields=[
                "generated_at",
                "status",
                "validation_status",
                "summary",
                "updated_at",
            ]
        )

    return GenerationResult(
        plan_version=plan_version,
        trip_count=plan_version.summary["tripCount"],
        conflict_count=plan_version.summary["conflictCount"],
        blocking_conflict_count=plan_version.summary["blockingConflictCount"],
    )


def _clear_generated_state(plan_version: PlanVersion) -> None:
    Conflict.objects.filter(plan_version=plan_version).delete()
    Trip.objects.filter(plan_version=plan_version).delete()


def _trip_status(step: CargoLayerStep) -> str:
    if step.status == CargoLayerStep.Status.COMPLETED:
        return Trip.Status.COMPLETED
    if step.status == CargoLayerStep.Status.LOADING:
        return Trip.Status.LOADING
    if step.status == CargoLayerStep.Status.BLOCKED or step.sequence_violation:
        return Trip.Status.BLOCKED
    return Trip.Status.PLANNED


def _assignment_status(step: CargoLayerStep) -> str:
    blocker = f"{step.blocking_reason} {step.chain_status}".lower()
    if step.sequence_violation:
        return Assignment.Status.BLOCKED
    if "tide" in blocker:
        return Assignment.Status.WAITING_TIDE
    if "bridge" in blocker:
        return Assignment.Status.WAITING_BRIDGE
    if step.status == CargoLayerStep.Status.LOADING:
        return Assignment.Status.LOADING
    if step.status == CargoLayerStep.Status.COMPLETED:
        return Assignment.Status.AT_CTS
    return Assignment.Status.ASSIGNED


def _next_action(step: CargoLayerStep) -> str:
    if step.sequence_violation:
        return "Resolve hatch/layer sequence before publication."
    if step.blocking_reason:
        return "Review blocker and generate replan candidate."
    if step.status == CargoLayerStep.Status.COMPLETED:
        return "Monitor discharge completion at CTS."
    return "Dispatch chain on planned window."


def _asset_status_label(asset) -> str:
    if asset is None:
        return "UNASSIGNED"
    status = getattr(asset, "status", "")
    return str(status).replace("_", " ").upper() if status else "READY"


def _first_route_segment():
    from apps.masters.models import RouteSegment

    return RouteSegment.objects.select_related("route").order_by("route__code", "sequence").first()


def _choose_tug(*, tugs: list[Tug], start, end, assigned_windows: dict[str, list[tuple]]):
    for tug in tugs:
        if tug.status != Tug.Status.AVAILABLE:
            continue
        if _asset_unavailable("tug", tug.code, start, end):
            continue
        if any(
            existing_start < end and existing_end > start
            for existing_start, existing_end in assigned_windows.get(tug.code, [])
        ):
            continue
        return tug
    for tug in tugs:
        if tug.status == Tug.Status.AVAILABLE:
            return tug
    return None


def _asset_unavailable(asset_type: str, asset_code: str, start, end) -> bool:
    return AssetAvailabilityWindow.objects.filter(
        asset_type=asset_type,
        asset_code=asset_code,
        window_start__lt=end,
        window_end__gt=start,
    ).exclude(status=AssetAvailabilityWindow.Status.AVAILABLE).exists()


def _jetty_blocked(jetty: Jetty | None, start, end) -> JettyAvailabilityWindow | None:
    if jetty is None:
        return None
    return (
        JettyAvailabilityWindow.objects.filter(
            jetty=jetty,
            window_start__lt=end,
            window_end__gt=start,
        )
        .exclude(status=JettyAvailabilityWindow.Status.WORKING)
        .order_by("window_start")
        .first()
    )


def _navigation_checks(voyage: OGVVoyage):
    return NavigationConstraintCheck.objects.filter(voyage=voyage).filter(
        Q(status=NavigationConstraintCheck.Status.MISSED)
        | Q(status=NavigationConstraintCheck.Status.MARGINAL)
    )


def _create_events(*, trip: Trip, assignment: Assignment) -> None:
    start = trip.planned_start
    event_rows = [
        (
            1,
            ScheduleEvent.EventType.LOAD_START,
            start,
            assignment.jetty.code if assignment.jetty else "",
        ),
        (
            2,
            ScheduleEvent.EventType.LOAD_COMPLETE,
            start + timedelta(hours=2),
            assignment.barge.code if assignment.barge else "",
        ),
        (
            3,
            ScheduleEvent.EventType.DEPART_JETTY,
            assignment.planned_departure,
            assignment.tug.code if assignment.tug else "",
        ),
        (
            4,
            ScheduleEvent.EventType.BRIDGE_CROSS,
            assignment.planned_departure + timedelta(hours=2),
            assignment.route_segment.to_location if assignment.route_segment else "",
        ),
        (
            5,
            ScheduleEvent.EventType.TIDE_GATE,
            assignment.planned_departure + timedelta(hours=4),
            assignment.route_segment.to_location if assignment.route_segment else "",
        ),
        (
            6,
            ScheduleEvent.EventType.ARRIVE_CTS,
            assignment.planned_arrival,
            assignment.cts.code if assignment.cts else "",
        ),
        (
            7,
            ScheduleEvent.EventType.DISCHARGE_COMPLETE,
            trip.planned_end,
            trip.voyage.vessel_name,
        ),
    ]
    for sequence, event_type, planned_at, resource_code in event_rows:
        ScheduleEvent.objects.create(
            trip=trip,
            sequence=sequence,
            event_type=event_type,
            planned_at=planned_at,
            location_label=resource_code,
            resource_code=resource_code,
            status=ScheduleEvent.Status.PLANNED,
        )


def _validate_trip(*, plan_version: PlanVersion, trip: Trip, assignment: Assignment) -> None:
    if trip.cargo_layer_step and trip.cargo_layer_step.sequence_violation:
        _conflict(
            plan_version=plan_version,
            trip=trip,
            code="LAYER_SEQUENCE_VIOLATION",
            severity=Conflict.Severity.CRITICAL,
            message=trip.cargo_layer_step.blocking_reason or "Layer sequence violates cargo plan.",
        )
    if assignment.tug is None:
        _conflict(
            plan_version=plan_version,
            trip=trip,
            code="TUG_UNAVAILABLE",
            severity=Conflict.Severity.CRITICAL,
            message="No available tug could be selected for this trip window.",
        )
    elif _asset_unavailable("tug", assignment.tug.code, trip.planned_start, trip.planned_end):
        _conflict(
            plan_version=plan_version,
            trip=trip,
            code="TUG_UNAVAILABLE",
            severity=Conflict.Severity.CRITICAL,
            object_type="tug",
            object_id=assignment.tug.code,
            message=f"{assignment.tug.code} is unavailable inside the trip window.",
        )
    if assignment.barge is None:
        _conflict(
            plan_version=plan_version,
            trip=trip,
            code="BARGE_UNAVAILABLE",
            severity=Conflict.Severity.CRITICAL,
            message="No barge assigned to the cargo layer step.",
        )
    elif _asset_unavailable("barge", assignment.barge.code, trip.planned_start, trip.planned_end):
        _conflict(
            plan_version=plan_version,
            trip=trip,
            code="BARGE_UNAVAILABLE",
            severity=Conflict.Severity.CRITICAL,
            object_type="barge",
            object_id=assignment.barge.code,
            message=f"{assignment.barge.code} is unavailable inside the trip window.",
        )
    if assignment.cts is None or not assignment.cts.is_available:
        _conflict(
            plan_version=plan_version,
            trip=trip,
            code="CTS_UNAVAILABLE",
            severity=Conflict.Severity.CRITICAL,
            object_type="cts",
            object_id=assignment.cts.code if assignment.cts else "",
            message="CTS asset is unavailable or not assigned.",
        )
    elif _asset_unavailable("cts", assignment.cts.code, trip.planned_start, trip.planned_end):
        _conflict(
            plan_version=plan_version,
            trip=trip,
            code="CTS_CAPACITY_CONFLICT",
            severity=Conflict.Severity.WARNING,
            object_type="cts",
            object_id=assignment.cts.code,
            message=f"{assignment.cts.code} has an availability warning inside the trip window.",
            is_blocking=False,
        )
    jetty_window = _jetty_blocked(assignment.jetty, trip.planned_start, trip.planned_end)
    if jetty_window:
        _conflict(
            plan_version=plan_version,
            trip=trip,
            code="JETTY_OVERLAP",
            severity=Conflict.Severity.WARNING,
            object_type="jetty",
            object_id=assignment.jetty.code if assignment.jetty else "",
            message=f"{assignment.jetty.code} is {jetty_window.status} during this loading window.",
            is_blocking=jetty_window.status == JettyAvailabilityWindow.Status.BLOCKED,
        )
    if assignment.tug and assignment.barge:
        incompatible = AssetCompatibilityRule.objects.filter(
            rule_type="tug_barge",
            left_code=assignment.tug.code,
            right_code=assignment.barge.code,
            is_compatible=False,
        ).exists()
        if incompatible:
            _conflict(
                plan_version=plan_version,
                trip=trip,
                code="TUG_BARGE_INCOMPATIBLE",
                severity=Conflict.Severity.CRITICAL,
                object_type="assignment",
                object_id=assignment.trip.trip_id,
                message=f"{assignment.tug.code} is incompatible with {assignment.barge.code}.",
            )
    for check in _navigation_checks(trip.voyage):
        if check.constraint_type == NavigationConstraintCheck.ConstraintType.TIDE:
            code = "TIDE_WINDOW_MISSED"
        else:
            code = "BRIDGE_WINDOW_MISSED"
        _conflict(
            plan_version=plan_version,
            trip=trip,
            code=code,
            severity=(
                Conflict.Severity.CRITICAL
                if check.status == NavigationConstraintCheck.Status.MISSED
                else Conflict.Severity.WARNING
            ),
            object_type=check.constraint_type,
            object_id=str(check.id),
            message=check.recovery_hint or f"{check.constraint_type} check is {check.status}.",
            is_blocking=check.status == NavigationConstraintCheck.Status.MISSED,
        )


def _conflict(
    *,
    plan_version: PlanVersion,
    trip: Trip | None,
    code: str,
    severity: str,
    message: str,
    object_type: str = "",
    object_id: str = "",
    is_blocking: bool = True,
) -> Conflict:
    return Conflict.objects.create(
        plan_version=plan_version,
        trip=trip,
        code=code,
        severity=severity,
        object_type=object_type,
        object_id=object_id,
        message=message,
        is_blocking=is_blocking,
    )


def _assignment_state(assignment: Assignment) -> dict:
    return {
        "status": assignment.status,
        "tug": assignment.tug.code if assignment.tug else "",
        "barge": assignment.barge.code if assignment.barge else "",
        "jetty": assignment.jetty.code if assignment.jetty else "",
        "cts": assignment.cts.code if assignment.cts else "",
        "plannedDeparture": assignment.planned_departure.isoformat(),
        "plannedArrival": assignment.planned_arrival.isoformat(),
        "nextConstraint": assignment.next_constraint,
        "nextAction": assignment.next_action,
    }


def _open_blocking_conflicts(plan_version: PlanVersion):
    return plan_version.conflicts.filter(is_blocking=True, resolved_at__isnull=True)


def _required_approvals_complete(approval_request: ApprovalRequest) -> bool:
    approved_roles = set(
        approval_request.decisions.filter(
            decision=ApprovalDecision.Decision.APPROVE
        ).values_list("authority_role", flat=True)
    )
    return set(approval_request.required_authorities or REQUIRED_APPROVAL_AUTHORITIES).issubset(
        approved_roles
    )


def _default_organization_for_actor(actor):
    if not actor or not getattr(actor, "is_authenticated", False):
        return None
    assignment = (
        UserRoleAssignment.objects.select_related("organization")
        .filter(user=actor, is_active=True)
        .order_by("id")
        .first()
    )
    return assignment.organization if assignment else None


def _trip_diff_key(trip: Trip) -> str:
    if trip.cargo_layer_step_id:
        return f"layer-{trip.cargo_layer_step_id}"
    return f"seq-{trip.sequence}"


def _snapshot_payload(plan_version: PlanVersion) -> dict:
    trips = []
    for trip in plan_version.trips.select_related(
        "voyage",
        "cargo_layer_step",
        "origin_jetty",
    ).prefetch_related("events"):
        assignment = getattr(trip, "assignment", None)
        trips.append(
            {
                "tripId": trip.trip_id,
                "sequence": trip.sequence,
                "vessel": trip.voyage.vessel_name,
                "status": trip.status,
                "plannedStart": trip.planned_start.isoformat(),
                "plannedEnd": trip.planned_end.isoformat(),
                "plannedQuantityMt": trip.planned_quantity_mt,
                "jetty": trip.origin_jetty.code if trip.origin_jetty else "",
                "tug": assignment.tug.code if assignment and assignment.tug else "",
                "barge": assignment.barge.code if assignment and assignment.barge else "",
                "cts": assignment.cts.code if assignment and assignment.cts else "",
                "events": [
                    {
                        "type": event.event_type,
                        "plannedAt": event.planned_at.isoformat(),
                        "status": event.status,
                    }
                    for event in trip.events.all()
                ],
            }
        )
    approvals = [
        {
            "authorityRole": decision.authority_role,
            "decision": decision.decision,
            "actor": decision.actor.email if decision.actor else "",
            "createdAt": decision.created_at.isoformat(),
        }
        for decision in ApprovalDecision.objects.filter(
            approval_request__plan_version=plan_version
        ).select_related("actor")
    ]
    return {
        "plan": plan_version.plan.code,
        "version": plan_version.version_no,
        "publishedSourceStatus": plan_version.status,
        "summary": plan_version.summary,
        "trips": trips,
        "approvals": approvals,
    }
