from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from apps.masters.models import AssetCompatibilityRule, Jetty, Location, Tug
from apps.planning.models import (
    AssetAvailabilityWindow,
    CargoLayerStep,
    JettyAvailabilityWindow,
    NavigationConstraintCheck,
    OGVVoyage,
)

from .models import Assignment, Conflict, Plan, PlanVersion, ScheduleEvent, Trip


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
                    "source": "deterministic_chunk4_generator",
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
