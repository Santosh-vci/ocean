from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record_audit_event
from apps.organizations.models import Organization
from apps.rbac.services import has_any_permission
from apps.scheduling.models import Assignment, PlanVersion, ScheduleEvent, Trip

from .models import (
    ConfirmedOperationalEvent,
    OperationalActualization,
    OperationalEventCandidate,
    OperationalEventKind,
)

JETTY_EVENT_KINDS = {
    OperationalEventKind.JETTY_ARRIVED,
    OperationalEventKind.JETTY_LOADING_STARTED,
    OperationalEventKind.JETTY_LOADING_COMPLETED,
    OperationalEventKind.JETTY_DEPARTED,
}
BRIDGE_EVENT_KINDS = {
    OperationalEventKind.BRIDGE_OPENED,
    OperationalEventKind.BRIDGE_CLOSED,
    OperationalEventKind.BRIDGE_CROSSED,
}
TIDE_EVENT_KINDS = {
    OperationalEventKind.TIDE_LEVEL_OBSERVED,
    OperationalEventKind.TIDE_GATE_PASSED,
}
CTS_EVENT_KINDS = {
    OperationalEventKind.CTS_ARRIVED,
    OperationalEventKind.CTS_DISCHARGE_STARTED,
    OperationalEventKind.CTS_RATE_UPDATED,
    OperationalEventKind.CTS_DISCHARGE_STOPPED,
    OperationalEventKind.CTS_DISCHARGE_COMPLETED,
}
GENERIC_EVENT_KINDS = {
    OperationalEventKind.EQUIPMENT_BREAKDOWN,
    OperationalEventKind.DEVICE_OFFLINE,
    OperationalEventKind.MANUAL_STATUS_UPDATE,
}


@dataclass(frozen=True)
class ConfirmationResult:
    event: ConfirmedOperationalEvent
    created: bool


def confirmation_permission_codes(event_kind: str) -> tuple[str, ...]:
    if event_kind in JETTY_EVENT_KINDS:
        return ("operations.confirm_jetty",)
    if event_kind in CTS_EVENT_KINDS:
        return ("operations.confirm_cts",)
    if event_kind in BRIDGE_EVENT_KINDS:
        return ("operations.confirm_bridge",)
    if event_kind in TIDE_EVENT_KINDS:
        return ("operations.confirm_tide",)
    if event_kind in GENERIC_EVENT_KINDS:
        return (
            "operations.confirm_jetty",
            "operations.confirm_cts",
            "operations.confirm_bridge",
            "operations.confirm_tide",
        )
    return ("operations.manage_feeds",)


def require_confirmation_authority(user, event_kind: str) -> None:
    permission_codes = confirmation_permission_codes(event_kind)
    if not has_any_permission(user, permission_codes):
        joined = ", ".join(permission_codes)
        raise PermissionDenied(f"Confirmation requires one of: {joined}.")


def organization_for_candidate(candidate: OperationalEventCandidate) -> Organization | None:
    plan_version = plan_version_for_candidate(candidate)
    if plan_version and plan_version.plan_id:
        return plan_version.plan.organization
    return None


def plan_version_for_candidate(candidate: OperationalEventCandidate) -> PlanVersion | None:
    if candidate.trip_id:
        return candidate.trip.plan_version
    if candidate.schedule_event_id:
        return candidate.schedule_event.trip.plan_version
    if candidate.assignment_id:
        return candidate.assignment.trip.plan_version
    return None


def trip_for_candidate(candidate: OperationalEventCandidate) -> Trip | None:
    if candidate.trip_id:
        return candidate.trip
    if candidate.schedule_event_id:
        return candidate.schedule_event.trip
    if candidate.assignment_id:
        return candidate.assignment.trip
    return None


def assignment_for_candidate(candidate: OperationalEventCandidate) -> Assignment | None:
    if candidate.assignment_id:
        return candidate.assignment
    trip = trip_for_candidate(candidate)
    if not trip:
        return None
    return getattr(trip, "assignment", None)


def schedule_event_for_candidate(candidate: OperationalEventCandidate) -> ScheduleEvent | None:
    if candidate.schedule_event_id:
        return candidate.schedule_event
    return None


def confirm_operational_event(
    *,
    candidate: OperationalEventCandidate,
    actor,
    actual_at=None,
    confirmation_mode: str = ConfirmedOperationalEvent.ConfirmationMode.MANUAL,
    reason_code: str = "",
    metadata: dict | None = None,
    confirmed_quantity_mt=None,
    confirmed_rate_tph=None,
    confirmed_grade_code: str = "",
    request=None,
) -> ConfirmationResult:
    require_confirmation_authority(actor, candidate.event_kind)

    with transaction.atomic():
        locked = OperationalEventCandidate.objects.select_for_update().get(pk=candidate.pk)
        if locked.status in {
            OperationalEventCandidate.Status.REJECTED,
            OperationalEventCandidate.Status.SUPERSEDED,
            OperationalEventCandidate.Status.DUPLICATE,
        }:
            raise ValidationError(
                f"Candidate {locked.candidate_id} cannot be confirmed from {locked.status}."
            )

        try:
            event = locked.confirmed_event
        except ConfirmedOperationalEvent.DoesNotExist:
            event = None

        if event is not None:
            return ConfirmationResult(event=event, created=False)

        before_state = {
            "candidate": {
                "status": locked.status,
                "event_kind": locked.event_kind,
                "event_at": locked.event_at.isoformat(),
            }
        }
        schedule_event = schedule_event_for_candidate(locked)
        if schedule_event:
            before_state["schedule_event"] = {
                "id": schedule_event.id,
                "event_type": schedule_event.event_type,
                "planned_at": schedule_event.planned_at.isoformat(),
                "actual_at": schedule_event.actual_at.isoformat()
                if schedule_event.actual_at
                else None,
                "status": schedule_event.status,
            }

        actual_at = actual_at or locked.event_at
        plan_version = plan_version_for_candidate(locked)
        trip = trip_for_candidate(locked)
        assignment = assignment_for_candidate(locked)
        event = ConfirmedOperationalEvent.objects.create(
            candidate=locked,
            event_kind=locked.event_kind,
            plan_version=plan_version,
            trip=trip,
            assignment=assignment,
            schedule_event=schedule_event,
            actual_at=actual_at,
            confirmed_quantity_mt=confirmed_quantity_mt,
            confirmed_rate_tph=confirmed_rate_tph,
            confirmed_grade_code=confirmed_grade_code,
            confirmed_by=actor,
            confirmed_at=timezone.now(),
            confirmation_mode=confirmation_mode,
            reason_code=reason_code,
            before_state=before_state,
            after_state={
                "candidate": {
                    "status": OperationalEventCandidate.Status.CONFIRMED,
                    "actual_at": actual_at.isoformat(),
                },
                "actualization": "deferred_to_chunk_4_1",
            },
            metadata=metadata or {},
        )
        locked.status = OperationalEventCandidate.Status.CONFIRMED
        locked.metadata = {
            **locked.metadata,
            "confirmedEventRef": event.event_id,
            "confirmedBy": getattr(actor, "username", ""),
            "confirmedAt": event.confirmed_at.isoformat(),
        }
        locked.save(update_fields=["status", "metadata", "updated_at"])

        OperationalActualization.objects.create(
            confirmed_event=event,
            target_type=(
                OperationalActualization.TargetType.SCHEDULE_EVENT
                if schedule_event
                else OperationalActualization.TargetType.TRIP
            ),
            target_id=str(schedule_event.id if schedule_event else (trip.id if trip else "")),
            before_state=before_state,
            after_state=event.after_state,
            status=OperationalActualization.Status.SKIPPED,
            metadata={
                "reason": "Chunk 4.0 persists confirmed truth; schedule mutation is Chunk 4.1.",
            },
        )

        record_audit_event(
            actor=actor,
            organization=organization_for_candidate(locked),
            action="operational_event.confirmed",
            object_type="confirmed_operational_event",
            object_id=str(event.pk),
            object_repr=event.event_id,
            metadata={
                "candidate_id": locked.pk,
                "candidate_ref": locked.candidate_id,
                "event_kind": locked.event_kind,
                "actual_at": actual_at.isoformat(),
                "confirmation_mode": confirmation_mode,
                "reason_code": reason_code,
                "required_permissions": list(confirmation_permission_codes(locked.event_kind)),
            },
            request=request,
        )

    return ConfirmationResult(event=event, created=True)


def reject_operational_event(
    *,
    candidate: OperationalEventCandidate,
    actor,
    reason_code: str,
    notes: str = "",
    request=None,
) -> OperationalEventCandidate:
    require_confirmation_authority(actor, candidate.event_kind)

    with transaction.atomic():
        locked = OperationalEventCandidate.objects.select_for_update().get(pk=candidate.pk)
        if locked.status == OperationalEventCandidate.Status.CONFIRMED:
            raise ValidationError(f"Confirmed candidate {locked.candidate_id} cannot be rejected.")
        locked.status = OperationalEventCandidate.Status.REJECTED
        locked.metadata = {
            **locked.metadata,
            "rejection": {
                "reasonCode": reason_code,
                "notes": notes,
                "actor": getattr(actor, "username", ""),
                "rejectedAt": timezone.now().isoformat(),
            },
        }
        locked.save(update_fields=["status", "metadata", "updated_at"])

        record_audit_event(
            actor=actor,
            organization=organization_for_candidate(locked),
            action="operational_event.rejected",
            object_type="operational_event_candidate",
            object_id=str(locked.pk),
            object_repr=locked.candidate_id,
            metadata={
                "candidate_ref": locked.candidate_id,
                "event_kind": locked.event_kind,
                "reason_code": reason_code,
                "notes": notes,
            },
            request=request,
        )

    return locked
