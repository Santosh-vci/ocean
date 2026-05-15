from dataclasses import dataclass
from datetime import timedelta

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.masters.models import AssetCompatibilityRule, Jetty, Location, Tug
from apps.planning.models import (
    AssetAvailabilityWindow,
    CargoLayerStep,
    JettyAvailabilityWindow,
    NavigationConstraintCheck,
    OGVVoyage,
)
from apps.rbac.models import UserRoleAssignment

from .models import (
    ApprovalDecision,
    ApprovalRequest,
    Assignment,
    Conflict,
    OverrideRequest,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
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

    before_state = _assignment_state(assignment)
    for field, value in requested_change.items():
        setattr(assignment, field, value)
    assignment.save(update_fields=[*requested_change.keys(), "updated_at"])
    after_state = _assignment_state(assignment)

    return OverrideRequest.objects.create(
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
        approval_request, _ = ApprovalRequest.objects.update_or_create(
            request_id=request_id,
            defaults={
                "plan_version": plan_version,
                "status": ApprovalRequest.Status.PENDING,
                "required_authorities": REQUIRED_APPROVAL_AUTHORITIES,
                "reason": reason or "Plan lifecycle approval requested.",
                "requested_by": actor,
            },
        )
        if plan_version.status not in {
            PlanVersion.Status.PROPOSED,
            PlanVersion.Status.APPROVED,
        }:
            plan_version.status = PlanVersion.Status.PROPOSED
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
            source_tug = (
                source_assignment.tug.code
                if source_assignment and source_assignment.tug
                else ""
            )
            target_tug = (
                target_assignment.tug.code
                if target_assignment and target_assignment.tug
                else ""
            )
            state = (
                "changed"
                if row_delay or row_quantity or source_tug != target_tug
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
                    "sourceTug": source_tug,
                    "targetTug": target_tug,
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


def create_scenario_from_conflict(
    *,
    baseline_version: PlanVersion,
    source_conflict: Conflict | None,
    actor,
    name: str = "",
) -> SimulationScenario:
    scenario_id = f"SIM-{baseline_version.plan.code}-V{baseline_version.version_no}"
    scenario, _ = SimulationScenario.objects.get_or_create(
        scenario_id=scenario_id,
        defaults={
            "name": name or "Recovery scenario A",
            "scenario_type": "conflict_recovery",
            "baseline_version": baseline_version,
            "source_conflict": source_conflict,
            "status": SimulationScenario.Status.DRAFT,
            "created_by": actor,
        },
    )
    return scenario


def simulate_scenario(*, scenario: SimulationScenario) -> SimulationScenario:
    conflict = scenario.source_conflict
    actions = [
        "Reassign available tug against earliest feasible tide window.",
        "Hold barge queue at source jetty until route gate clears.",
        "Preserve OGV hatch/layer order before approval promotion.",
    ]
    scenario.recovery_actions = actions
    scenario.impact_summary = {
        "sourceConflict": conflict.code if conflict else "MANUAL_SCENARIO",
        "affectedVessel": conflict.trip.voyage.vessel_name if conflict and conflict.trip else "",
        "feasibilityPct": 89 if conflict else 96,
    }
    scenario.delta_summary = {
        "delayDeltaMinutes": -210 if conflict else 0,
        "demurrageDeltaUsd": -42000 if conflict else 0,
        "fleetUtilizationPct": 6,
        "remainingViolations": 1 if conflict else 0,
    }
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
    return scenario


def promote_scenario_to_proposed(*, scenario: SimulationScenario, actor) -> SimulationScenario:
    with transaction.atomic():
        if scenario.scenario_version is None:
            scenario.scenario_version = clone_plan_version(
                source_version=scenario.baseline_version,
                created_by=actor,
            )
        scenario.status = SimulationScenario.Status.PROPOSED
        scenario.scenario_version.status = PlanVersion.Status.PROPOSED
        scenario.scenario_version.save(update_fields=["status", "updated_at"])
        scenario.save(update_fields=["scenario_version", "status", "updated_at"])
    return scenario


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
