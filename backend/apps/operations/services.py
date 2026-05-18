from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework.exceptions import PermissionDenied, ValidationError

from apps.audit.services import record_audit_event
from apps.organizations.models import Organization
from apps.rbac.services import has_any_permission
from apps.scheduling.models import Assignment, PlanVersion, ScheduleEvent, Trip

from .models import (
    ConfirmedOperationalEvent,
    DeviceEndpoint,
    DeviceHealthSnapshot,
    IntegrationFeed,
    OperationalActualization,
    OperationalEventCandidate,
    OperationalEventKind,
    OperationsAssetType,
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
HIGH_IMPACT_EVENT_KINDS = GENERIC_EVENT_KINDS | {
    OperationalEventKind.CTS_RATE_UPDATED,
    OperationalEventKind.CTS_DISCHARGE_STOPPED,
}

EVENT_KIND_TO_SCHEDULE_EVENT_TYPE = {
    OperationalEventKind.JETTY_LOADING_STARTED: ScheduleEvent.EventType.LOAD_START,
    OperationalEventKind.JETTY_LOADING_COMPLETED: ScheduleEvent.EventType.LOAD_COMPLETE,
    OperationalEventKind.JETTY_DEPARTED: ScheduleEvent.EventType.DEPART_JETTY,
    OperationalEventKind.BRIDGE_CROSSED: ScheduleEvent.EventType.BRIDGE_CROSS,
    OperationalEventKind.TIDE_GATE_PASSED: ScheduleEvent.EventType.TIDE_GATE,
    OperationalEventKind.CTS_ARRIVED: ScheduleEvent.EventType.ARRIVE_CTS,
    OperationalEventKind.CTS_DISCHARGE_STARTED: ScheduleEvent.EventType.DISCHARGE_START,
    OperationalEventKind.CTS_DISCHARGE_COMPLETED: ScheduleEvent.EventType.DISCHARGE_COMPLETE,
}
EVENT_KIND_TO_TRIP_STATUS = {
    OperationalEventKind.JETTY_LOADING_STARTED: Trip.Status.LOADING,
    OperationalEventKind.JETTY_LOADING_COMPLETED: Trip.Status.LOADING,
    OperationalEventKind.JETTY_DEPARTED: Trip.Status.TRANSIT,
    OperationalEventKind.BRIDGE_CROSSED: Trip.Status.TRANSIT,
    OperationalEventKind.TIDE_GATE_PASSED: Trip.Status.TRANSIT,
    OperationalEventKind.CTS_ARRIVED: Trip.Status.DISCHARGING,
    OperationalEventKind.CTS_DISCHARGE_STARTED: Trip.Status.DISCHARGING,
    OperationalEventKind.CTS_DISCHARGE_COMPLETED: Trip.Status.COMPLETED,
}
EVENT_KIND_TO_ASSIGNMENT_STATUS = {
    OperationalEventKind.JETTY_LOADING_STARTED: Assignment.Status.LOADING,
    OperationalEventKind.JETTY_LOADING_COMPLETED: Assignment.Status.IN_TRANSIT,
    OperationalEventKind.JETTY_DEPARTED: Assignment.Status.IN_TRANSIT,
    OperationalEventKind.BRIDGE_CROSSED: Assignment.Status.IN_TRANSIT,
    OperationalEventKind.TIDE_GATE_PASSED: Assignment.Status.IN_TRANSIT,
    OperationalEventKind.CTS_ARRIVED: Assignment.Status.AT_CTS,
    OperationalEventKind.CTS_DISCHARGE_STARTED: Assignment.Status.AT_CTS,
    OperationalEventKind.CTS_DISCHARGE_COMPLETED: Assignment.Status.AT_CTS,
}

AUTO_CONFIRMATION_MODES = {
    ConfirmedOperationalEvent.ConfirmationMode.AUTO_TRUSTED_SOURCE,
    ConfirmedOperationalEvent.ConfirmationMode.AUTO_THRESHOLD,
    ConfirmedOperationalEvent.ConfirmationMode.REPLAY_PROOF,
}


@dataclass(frozen=True)
class ConfirmationResult:
    event: ConfirmedOperationalEvent
    created: bool
    actualization_summary: dict


@dataclass(frozen=True)
class IngestionResult:
    candidate: OperationalEventCandidate
    created: bool
    duplicate: bool
    auto_confirmed: bool
    confirmed_event: ConfirmedOperationalEvent | None
    trust_evaluation: dict


@dataclass(frozen=True)
class HealthIngestionResult:
    snapshot: DeviceHealthSnapshot
    device: DeviceEndpoint
    feed: IntegrationFeed
    candidate: OperationalEventCandidate | None
    created_risk: bool
    health_summary: dict


@dataclass(frozen=True)
class MatchResult:
    trip: Trip | None
    assignment: Assignment | None
    schedule_event: ScheduleEvent | None
    metadata: dict


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


def ingest_operational_event(
    *,
    payload: dict,
    actor=None,
    request=None,
) -> IngestionResult:
    feed = _resolve_feed(payload)
    device = _resolve_device(payload, feed=feed)
    event_kind = _required(payload, "event_kind")
    event_at = _coerce_datetime(_required(payload, "event_at"), field_name="event_at")
    received_at = _coerce_datetime(payload.get("received_at") or timezone.now())
    source_kind = payload.get("source_kind") or OperationalEventCandidate.SourceKind.SYNTHETIC
    confidence_score = _coerce_decimal(payload.get("confidence_score", Decimal("0")))
    payload_body = payload.get("payload") or {}
    asset_type = payload.get("asset_type") or (device.asset_type if device else "")
    asset_code = payload.get("asset_code") or (device.asset_code if device else "")

    match = match_operational_event(
        payload=payload,
        event_kind=event_kind,
        event_at=event_at,
        asset_code=asset_code,
        device=device,
    )
    dedupe_key = _dedupe_key(
        feed=feed,
        device=device,
        event_kind=event_kind,
        asset_code=asset_code,
        event_at=event_at,
        schedule_event=match.schedule_event,
        payload=payload,
    )
    duplicate_of = (
        OperationalEventCandidate.objects.filter(feed=feed, dedupe_key=dedupe_key)
        .exclude(status=OperationalEventCandidate.Status.DUPLICATE)
        .order_by("created_at", "id")
        .first()
        if dedupe_key
        else None
    )

    with transaction.atomic():
        candidate = OperationalEventCandidate.objects.create(
            feed=feed,
            device=device,
            source_kind=source_kind,
            event_kind=event_kind,
            asset_type=asset_type,
            asset_code=asset_code,
            trip=match.trip,
            assignment=match.assignment,
            schedule_event=match.schedule_event,
            event_at=event_at,
            received_at=received_at,
            confidence_score=confidence_score,
            dedupe_key=dedupe_key,
            status=(
                OperationalEventCandidate.Status.DUPLICATE
                if duplicate_of
                else OperationalEventCandidate.Status.PENDING
            ),
            payload=payload_body,
            raw_payload_ref=payload.get("raw_payload_ref", ""),
            metadata={
                **(payload.get("metadata") or {}),
                "match": match.metadata,
                "dedupe": {
                    "dedupeKey": dedupe_key,
                    "duplicateOf": duplicate_of.candidate_id if duplicate_of else None,
                },
            },
        )
        _mark_device_seen(device=device, event_at=event_at)

        if duplicate_of:
            confirmed_event = _confirmed_event_for_candidate(duplicate_of)
            _record_candidate_audit(
                candidate=candidate,
                actor=actor,
                action="operational_event.duplicate",
                request=request,
                metadata={
                    "duplicate_of": duplicate_of.candidate_id,
                    "dedupe_key": dedupe_key,
                    "existing_confirmed_event": (
                        confirmed_event.event_id if confirmed_event else None
                    ),
                },
            )
            return IngestionResult(
                candidate=candidate,
                created=False,
                duplicate=True,
                auto_confirmed=False,
                confirmed_event=confirmed_event,
                trust_evaluation={"decision": "duplicate", "reasons": ["duplicate_payload"]},
            )

        trust = evaluate_trust_policy(candidate)
        candidate.metadata = {
            **candidate.metadata,
            "trustEvaluation": trust,
        }
        candidate.save(update_fields=["metadata", "updated_at"])
        _record_candidate_audit(
            candidate=candidate,
            actor=actor,
            action="operational_event.ingested",
            request=request,
            metadata={"trust": trust},
        )

    confirmed_event = None
    if trust["shouldAutoConfirm"]:
        result = confirm_operational_event(
            candidate=candidate,
            actor=None,
            actual_at=candidate.event_at,
            confirmation_mode=trust["confirmationMode"],
            reason_code="trusted_feed_auto_confirm",
            metadata={"trustEvaluation": trust, "ingestedBy": getattr(actor, "username", None)},
            confirmed_quantity_mt=payload.get("confirmed_quantity_mt"),
            confirmed_rate_tph=payload.get("confirmed_rate_tph"),
            confirmed_grade_code=payload.get("confirmed_grade_code", ""),
            request=request,
            skip_authority_check=True,
        )
        confirmed_event = result.event

    candidate.refresh_from_db()
    return IngestionResult(
        candidate=candidate,
        created=True,
        duplicate=False,
        auto_confirmed=confirmed_event is not None,
        confirmed_event=confirmed_event,
        trust_evaluation=trust,
    )


def ingest_device_health(
    *,
    payload: dict,
    actor=None,
    request=None,
) -> HealthIngestionResult:
    device = _resolve_health_device(payload)
    feed = device.feed
    observed_at = _coerce_datetime(
        _required(payload, "observed_at"),
        field_name="observed_at",
    )
    received_at = _coerce_datetime(payload.get("received_at") or timezone.now())
    health_status = payload.get("health_status") or DeviceHealthSnapshot.HealthStatus.UNKNOWN

    with transaction.atomic():
        snapshot = DeviceHealthSnapshot.objects.create(
            device=device,
            observed_at=observed_at,
            received_at=received_at,
            health_status=health_status,
            battery_level=payload.get("battery_level"),
            power_status=payload.get("power_status", ""),
            network_status=payload.get("network_status", ""),
            latency_ms=payload.get("latency_ms"),
            gap_seconds=payload.get("gap_seconds"),
            metadata=payload.get("metadata") or {},
        )
        health_summary = _apply_device_health_snapshot(snapshot=snapshot, now=received_at)
        candidate = None
        created_risk = False
        if health_summary["riskSeverity"] == "critical":
            candidate, created_risk = _ensure_device_health_candidate(
                device=device,
                snapshot=snapshot,
                health_summary=health_summary,
                actor=actor,
                request=request,
            )
        _refresh_feed_health(feed)

        record_audit_event(
            actor=actor,
            organization=None,
            action="operations.device_health.ingested",
            object_type="device_health_snapshot",
            object_id=str(snapshot.pk),
            object_repr=snapshot.snapshot_id,
            metadata={
                "device_id": device.device_id,
                "feed_id": feed.feed_id,
                "health_status": snapshot.health_status,
                "device_status": health_summary["deviceStatus"],
                "risk_severity": health_summary["riskSeverity"],
                "risk_candidate": candidate.candidate_id if candidate else None,
            },
            request=request,
        )

    device.refresh_from_db()
    feed.refresh_from_db()
    return HealthIngestionResult(
        snapshot=snapshot,
        device=device,
        feed=feed,
        candidate=candidate,
        created_risk=created_risk,
        health_summary=health_summary,
    )


def refresh_operations_health(*, now=None) -> dict:
    now = _coerce_datetime(now or timezone.now())
    changed_devices = 0
    created_risks = 0
    for device in DeviceEndpoint.objects.select_related("feed").all():
        if device.status in {DeviceEndpoint.Status.PAUSED, DeviceEndpoint.Status.RETIRED}:
            continue
        latest = device.health_snapshots.order_by("-observed_at", "-id").first()
        health_summary = _device_health_evaluation(device=device, snapshot=latest, now=now)
        if health_summary["deviceStatus"] != device.status:
            device.status = health_summary["deviceStatus"]
            device.metadata = {
                **device.metadata,
                "health": health_summary,
            }
            device.save(update_fields=["status", "metadata", "updated_at"])
            changed_devices += 1
        if (
            health_summary["riskSeverity"] == "critical"
            and latest is None
            and health_summary["reason"] in {"freshness_offline", "stale_offline"}
        ):
            candidate, created = _ensure_device_health_candidate(
                device=device,
                snapshot=latest,
                health_summary=health_summary,
                actor=None,
                request=None,
            )
            if created:
                created_risks += 1

    for feed in IntegrationFeed.objects.all():
        _refresh_feed_health(feed)

    return {
        "changedDevices": changed_devices,
        "createdRisks": created_risks,
        "refreshedAt": now.isoformat(),
    }


def operations_health_summary(*, refresh: bool = True, now=None) -> dict:
    now = _coerce_datetime(now or timezone.now())
    refresh_result = refresh_operations_health(now=now) if refresh else None
    feed_counts = {
        status: IntegrationFeed.objects.filter(status=status).count()
        for status in IntegrationFeed.Status.values
    }
    device_counts = {
        status: DeviceEndpoint.objects.filter(status=status).count()
        for status in DeviceEndpoint.Status.values
    }
    health_counts = {
        status: DeviceHealthSnapshot.objects.filter(health_status=status).count()
        for status in DeviceHealthSnapshot.HealthStatus.values
    }
    pending_risks = OperationalEventCandidate.objects.select_related(
        "feed",
        "device",
    ).filter(
        event_kind=OperationalEventKind.DEVICE_OFFLINE,
        status=OperationalEventCandidate.Status.PENDING,
    )
    latest_snapshot = DeviceHealthSnapshot.objects.order_by("-observed_at", "-id").first()
    stale_devices = [
        _device_health_evaluation(
            device=device,
            snapshot=device.health_snapshots.order_by("-observed_at", "-id").first(),
            now=now,
        )
        for device in DeviceEndpoint.objects.select_related("feed").all()
    ]
    stale_count = sum(
        1
        for summary in stale_devices
        if summary["reason"] in {"freshness_degraded", "freshness_offline", "stale_offline"}
    )
    critical_count = pending_risks.count()
    return {
        "feeds": {
            "total": IntegrationFeed.objects.count(),
            "active": feed_counts.get(IntegrationFeed.Status.ACTIVE, 0),
            "degraded": feed_counts.get(IntegrationFeed.Status.DEGRADED, 0),
            "paused": feed_counts.get(IntegrationFeed.Status.PAUSED, 0),
            "retired": feed_counts.get(IntegrationFeed.Status.RETIRED, 0),
        },
        "devices": {
            "total": DeviceEndpoint.objects.count(),
            "active": device_counts.get(DeviceEndpoint.Status.ACTIVE, 0),
            "degraded": device_counts.get(DeviceEndpoint.Status.DEGRADED, 0),
            "offline": device_counts.get(DeviceEndpoint.Status.OFFLINE, 0),
            "paused": device_counts.get(DeviceEndpoint.Status.PAUSED, 0),
            "retired": device_counts.get(DeviceEndpoint.Status.RETIRED, 0),
            "stale": stale_count,
        },
        "snapshots": {
            "total": DeviceHealthSnapshot.objects.count(),
            "healthy": health_counts.get(DeviceHealthSnapshot.HealthStatus.HEALTHY, 0),
            "warning": health_counts.get(DeviceHealthSnapshot.HealthStatus.WARNING, 0),
            "critical": health_counts.get(DeviceHealthSnapshot.HealthStatus.CRITICAL, 0),
            "offline": health_counts.get(DeviceHealthSnapshot.HealthStatus.OFFLINE, 0),
            "unknown": health_counts.get(DeviceHealthSnapshot.HealthStatus.UNKNOWN, 0),
            "latestObservedAt": latest_snapshot.observed_at.isoformat()
            if latest_snapshot
            else None,
        },
        "risks": [_health_risk_candidate_summary(candidate) for candidate in pending_risks[:12]],
        "criticalRiskCount": critical_count,
        "status": (
            "critical"
            if device_counts.get(DeviceEndpoint.Status.OFFLINE, 0) or critical_count
            else "warning"
            if device_counts.get(DeviceEndpoint.Status.DEGRADED, 0)
            or feed_counts.get(IntegrationFeed.Status.DEGRADED, 0)
            else "ok"
        ),
        "refresh": refresh_result,
        "calculatedAt": now.isoformat(),
    }


def match_operational_event(
    *,
    payload: dict,
    event_kind: str,
    event_at,
    asset_code: str,
    device: DeviceEndpoint | None = None,
) -> MatchResult:
    schedule_event = _resolve_schedule_event(payload)
    trip = _resolve_trip(payload)
    assignment = _resolve_assignment(payload)
    match_path = "unmatched"
    candidate_count = 0

    if schedule_event is not None:
        trip = schedule_event.trip
        assignment = getattr(trip, "assignment", None)
        match_path = "direct_schedule_event"
        candidate_count = 1
    elif assignment is not None:
        trip = assignment.trip
        schedule_event = _schedule_event_for_trip(trip=trip, event_kind=event_kind)
        match_path = "direct_assignment"
        candidate_count = 1 if schedule_event else 0
    elif trip is not None:
        assignment = getattr(trip, "assignment", None)
        schedule_event = _schedule_event_for_trip(trip=trip, event_kind=event_kind)
        match_path = "direct_trip"
        candidate_count = 1 if schedule_event else 0
    else:
        schedule_event, candidate_count = _nearest_schedule_event(
            event_kind=event_kind,
            event_at=event_at,
            asset_code=asset_code,
            device=device,
            tolerance_minutes=int(payload.get("match_tolerance_minutes") or 720),
        )
        if schedule_event:
            trip = schedule_event.trip
            assignment = getattr(trip, "assignment", None)
            match_path = "nearest_active_plan_event"

    return MatchResult(
        trip=trip,
        assignment=assignment,
        schedule_event=schedule_event,
        metadata={
            "path": match_path,
            "matched": schedule_event is not None,
            "matchCount": candidate_count,
            "ambiguous": candidate_count > 1,
            "deviceId": device.device_id if device else None,
            "assetCode": asset_code,
            "scheduleEventId": schedule_event.id if schedule_event else None,
            "scheduleEventType": schedule_event.event_type if schedule_event else None,
            "tripId": trip.trip_id if trip else None,
            "assignmentId": assignment.id if assignment else None,
        },
    )


def evaluate_trust_policy(candidate: OperationalEventCandidate) -> dict:
    feed = candidate.feed
    device = candidate.device
    reasons = []
    threshold = _metadata_decimal(feed.metadata, "confidenceThreshold", Decimal("90"))
    tolerance_minutes = int(feed.metadata.get("autoConfirmToleranceMinutes", 180))
    confirmation_mode = (
        ConfirmedOperationalEvent.ConfirmationMode.REPLAY_PROOF
        if candidate.metadata.get("replayProof")
        else ConfirmedOperationalEvent.ConfirmationMode.AUTO_THRESHOLD
        if feed.trust_mode == IntegrationFeed.TrustMode.AUTO_CONFIRM_WITH_THRESHOLD
        else ConfirmedOperationalEvent.ConfirmationMode.AUTO_TRUSTED_SOURCE
    )

    if feed.status != IntegrationFeed.Status.ACTIVE:
        reasons.append("feed_not_active")
    if feed.trust_mode == IntegrationFeed.TrustMode.MANUAL_REVIEW:
        reasons.append("feed_requires_manual_review")
    if candidate.event_kind in HIGH_IMPACT_EVENT_KINDS:
        reasons.append("high_impact_event_requires_manual_review")
    if candidate.schedule_event_id is None:
        reasons.append("no_single_schedule_event_match")
    if candidate.metadata.get("match", {}).get("ambiguous"):
        reasons.append("ambiguous_match")
    if candidate.confidence_score < threshold:
        reasons.append("confidence_below_threshold")

    device_health = _device_health_summary(device)
    if not device_health["isHealthy"]:
        reasons.append(device_health["reason"])

    variance_minutes = None
    if candidate.schedule_event_id:
        variance_minutes = _variance_minutes(
            candidate.schedule_event.planned_at,
            candidate.event_at,
        )
        if abs(variance_minutes) > tolerance_minutes:
            reasons.append("outside_auto_confirm_tolerance")

    should_auto_confirm = len(reasons) == 0
    return {
        "decision": "auto_confirm" if should_auto_confirm else "manual_review",
        "shouldAutoConfirm": should_auto_confirm,
        "confirmationMode": confirmation_mode,
        "reasons": reasons,
        "confidenceScore": str(candidate.confidence_score),
        "confidenceThreshold": str(threshold),
        "varianceMinutes": variance_minutes,
        "toleranceMinutes": tolerance_minutes,
        "deviceHealth": device_health,
    }


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
    skip_authority_check: bool = False,
) -> ConfirmationResult:
    if not skip_authority_check:
        require_confirmation_authority(actor, candidate.event_kind)
    confirmed_quantity_mt = _coerce_optional_decimal(confirmed_quantity_mt)
    confirmed_rate_tph = _coerce_optional_decimal(confirmed_rate_tph)

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
            return ConfirmationResult(
                event=event,
                created=False,
                actualization_summary=_summarize_actualizations(event),
            )

        actual_at = _coerce_datetime(actual_at or locked.event_at, field_name="actual_at")
        schedule_event = schedule_event_for_candidate(locked)
        plan_version = plan_version_for_candidate(locked)
        trip = trip_for_candidate(locked)
        assignment = assignment_for_candidate(locked)
        before_state = _event_before_state(locked, schedule_event, trip, assignment)
        final_candidate_status = (
            OperationalEventCandidate.Status.AUTO_CONFIRMED
            if confirmation_mode in AUTO_CONFIRMATION_MODES
            else OperationalEventCandidate.Status.CONFIRMED
        )
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
            confirmed_by=None if skip_authority_check else actor,
            confirmed_at=timezone.now(),
            confirmation_mode=confirmation_mode,
            reason_code=reason_code,
            before_state=before_state,
            after_state={
                "candidate": {
                    "status": final_candidate_status,
                    "actual_at": actual_at.isoformat(),
                }
            },
            metadata=metadata or {},
        )
        locked.status = final_candidate_status
        locked.metadata = {
            **locked.metadata,
            "confirmedEventRef": event.event_id,
            "confirmedBy": getattr(actor, "username", None),
            "confirmedAt": event.confirmed_at.isoformat(),
            "confirmationMode": confirmation_mode,
        }
        locked.save(update_fields=["status", "metadata", "updated_at"])

        actualization_summary = apply_confirmed_event(event=event)
        event.after_state = {
            **event.after_state,
            "actualization": actualization_summary,
        }
        event.save(update_fields=["after_state"])

        record_audit_event(
            actor=actor if not skip_authority_check else None,
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
                "actualization": actualization_summary,
            },
            request=request,
        )

    return ConfirmationResult(
        event=event,
        created=True,
        actualization_summary=actualization_summary,
    )


def apply_confirmed_event(*, event: ConfirmedOperationalEvent) -> dict:
    with transaction.atomic():
        if event.actualizations.exists():
            return _summarize_actualizations(event)

        actualizations: list[OperationalActualization] = []
        if event.schedule_event_id:
            actualizations.append(_actualize_schedule_event(event))
        else:
            actualizations.append(
                OperationalActualization.objects.create(
                    confirmed_event=event,
                    target_type=OperationalActualization.TargetType.SCHEDULE_EVENT,
                    target_id="",
                    before_state={},
                    after_state={},
                    status=OperationalActualization.Status.SKIPPED,
                    metadata={"reason": "no_matched_schedule_event"},
                )
            )

        if event.assignment_id and event.event_kind in EVENT_KIND_TO_ASSIGNMENT_STATUS:
            actualizations.append(_actualize_assignment(event))
        if event.trip_id and event.event_kind in EVENT_KIND_TO_TRIP_STATUS:
            actualizations.append(_actualize_trip(event))

        return _summarize_actualizations(event, actualizations=actualizations)


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
        if locked.status in {
            OperationalEventCandidate.Status.CONFIRMED,
            OperationalEventCandidate.Status.AUTO_CONFIRMED,
        }:
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


def _actualize_schedule_event(event: ConfirmedOperationalEvent) -> OperationalActualization:
    schedule_event = ScheduleEvent.objects.select_for_update().get(pk=event.schedule_event_id)
    before_state = {
        "id": schedule_event.id,
        "event_type": schedule_event.event_type,
        "planned_at": schedule_event.planned_at.isoformat(),
        "actual_at": schedule_event.actual_at.isoformat() if schedule_event.actual_at else None,
        "status": schedule_event.status,
        "metadata": schedule_event.metadata,
    }
    variance_minutes = _variance_minutes(schedule_event.planned_at, event.actual_at)
    if schedule_event.actual_at:
        status = OperationalActualization.Status.SKIPPED
        reason = "schedule_event_actual_already_set"
    else:
        schedule_event.actual_at = event.actual_at
        schedule_event.status = (
            ScheduleEvent.Status.DELAYED if variance_minutes > 15 else ScheduleEvent.Status.ACTUAL
        )
        schedule_event.metadata = {
            **schedule_event.metadata,
            "operationsActual": {
                "confirmedEventRef": event.event_id,
                "candidateRef": event.candidate.candidate_id if event.candidate_id else None,
                "eventKind": event.event_kind,
                "varianceMinutes": variance_minutes,
                "actualizedAt": timezone.now().isoformat(),
            },
        }
        schedule_event.save(update_fields=["actual_at", "status", "metadata"])
        status = OperationalActualization.Status.APPLIED
        reason = "schedule_event_actual_applied"

    after_state = {
        "id": schedule_event.id,
        "actual_at": schedule_event.actual_at.isoformat() if schedule_event.actual_at else None,
        "status": schedule_event.status,
        "variance_minutes": variance_minutes,
    }
    return OperationalActualization.objects.create(
        confirmed_event=event,
        target_type=OperationalActualization.TargetType.SCHEDULE_EVENT,
        target_id=str(schedule_event.id),
        before_state=before_state,
        after_state=after_state,
        status=status,
        metadata={"reason": reason, "varianceMinutes": variance_minutes},
    )


def _actualize_assignment(event: ConfirmedOperationalEvent) -> OperationalActualization:
    assignment = Assignment.objects.select_for_update().get(pk=event.assignment_id)
    target_status = EVENT_KIND_TO_ASSIGNMENT_STATUS[event.event_kind]
    before_state = {
        "id": assignment.id,
        "status": assignment.status,
        "next_action": assignment.next_action,
    }
    if assignment.status == target_status:
        status = OperationalActualization.Status.SKIPPED
        reason = "assignment_status_already_current"
    else:
        assignment.status = target_status
        assignment.next_action = _next_action_after_event(event.event_kind)
        assignment.save(update_fields=["status", "next_action", "updated_at"])
        status = OperationalActualization.Status.APPLIED
        reason = "assignment_status_updated"

    return OperationalActualization.objects.create(
        confirmed_event=event,
        target_type=OperationalActualization.TargetType.ASSIGNMENT,
        target_id=str(assignment.id),
        before_state=before_state,
        after_state={
            "id": assignment.id,
            "status": assignment.status,
            "next_action": assignment.next_action,
        },
        status=status,
        metadata={"reason": reason, "eventKind": event.event_kind},
    )


def _actualize_trip(event: ConfirmedOperationalEvent) -> OperationalActualization:
    trip = Trip.objects.select_for_update().get(pk=event.trip_id)
    target_status = EVENT_KIND_TO_TRIP_STATUS[event.event_kind]
    before_state = {
        "id": trip.id,
        "trip_id": trip.trip_id,
        "status": trip.status,
        "loaded_quantity_mt": trip.loaded_quantity_mt,
    }
    update_fields = ["status", "updated_at"]
    if event.event_kind == OperationalEventKind.JETTY_LOADING_COMPLETED:
        trip.loaded_quantity_mt = int(event.confirmed_quantity_mt or trip.planned_quantity_mt)
        update_fields.append("loaded_quantity_mt")

    if trip.status == target_status and "loaded_quantity_mt" not in update_fields:
        status = OperationalActualization.Status.SKIPPED
        reason = "trip_status_already_current"
    else:
        trip.status = target_status
        trip.save(update_fields=update_fields)
        status = OperationalActualization.Status.APPLIED
        reason = "trip_status_updated"

    return OperationalActualization.objects.create(
        confirmed_event=event,
        target_type=OperationalActualization.TargetType.TRIP,
        target_id=str(trip.id),
        before_state=before_state,
        after_state={
            "id": trip.id,
            "trip_id": trip.trip_id,
            "status": trip.status,
            "loaded_quantity_mt": trip.loaded_quantity_mt,
        },
        status=status,
        metadata={"reason": reason, "eventKind": event.event_kind},
    )


def _record_candidate_audit(
    *,
    candidate: OperationalEventCandidate,
    actor,
    action: str,
    request,
    metadata: dict | None = None,
) -> None:
    record_audit_event(
        actor=actor,
        organization=organization_for_candidate(candidate),
        action=action,
        object_type="operational_event_candidate",
        object_id=str(candidate.pk),
        object_repr=candidate.candidate_id,
        metadata={
            "candidate_ref": candidate.candidate_id,
            "event_kind": candidate.event_kind,
            "status": candidate.status,
            **(metadata or {}),
        },
        request=request,
    )


def _resolve_feed(payload: dict) -> IntegrationFeed:
    feed = payload.get("feed")
    if isinstance(feed, IntegrationFeed):
        return feed
    if feed:
        return IntegrationFeed.objects.get(pk=feed)
    feed_id = payload.get("feed_id")
    if feed_id:
        return IntegrationFeed.objects.get(feed_id=feed_id)
    raise ValidationError({"feed_id": "An integration feed is required."})


def _resolve_device(payload: dict, *, feed: IntegrationFeed) -> DeviceEndpoint | None:
    device = payload.get("device")
    if isinstance(device, DeviceEndpoint):
        return device
    if device:
        return DeviceEndpoint.objects.get(pk=device)
    device_id = payload.get("device_id")
    if device_id:
        return DeviceEndpoint.objects.get(device_id=device_id, feed=feed)
    return None


def _resolve_health_device(payload: dict) -> DeviceEndpoint:
    device = payload.get("device")
    if isinstance(device, DeviceEndpoint):
        return device
    queryset = DeviceEndpoint.objects.select_related("feed")
    if device:
        return queryset.get(pk=device)

    device_id = payload.get("device_id")
    if not device_id:
        raise ValidationError({"device_id": "A device endpoint is required."})
    feed = payload.get("feed")
    feed_id = payload.get("feed_id")
    if isinstance(feed, IntegrationFeed):
        queryset = queryset.filter(feed=feed)
    elif feed:
        queryset = queryset.filter(feed_id=feed)
    elif feed_id:
        queryset = queryset.filter(feed__feed_id=feed_id)
    return queryset.get(device_id=device_id)


def _resolve_schedule_event(payload: dict) -> ScheduleEvent | None:
    schedule_event = payload.get("schedule_event")
    if isinstance(schedule_event, ScheduleEvent):
        return schedule_event
    schedule_event_id = payload.get("schedule_event_id") or schedule_event
    if schedule_event_id:
        return ScheduleEvent.objects.select_related("trip", "trip__plan_version").get(
            pk=schedule_event_id
        )
    return None


def _resolve_assignment(payload: dict) -> Assignment | None:
    assignment = payload.get("assignment")
    if isinstance(assignment, Assignment):
        return assignment
    assignment_id = payload.get("assignment_id") or assignment
    if assignment_id:
        return Assignment.objects.select_related("trip", "trip__plan_version").get(pk=assignment_id)
    return None


def _resolve_trip(payload: dict) -> Trip | None:
    trip = payload.get("trip")
    if isinstance(trip, Trip):
        return trip
    trip_id = payload.get("trip_id") or trip
    if not trip_id:
        return None
    if isinstance(trip_id, int):
        return Trip.objects.select_related("plan_version").get(pk=trip_id)
    return Trip.objects.select_related("plan_version").get(trip_id=trip_id)


def _active_plan_versions():
    preferred_statuses = [
        PlanVersion.Status.PUBLISHED,
        PlanVersion.Status.APPROVED,
        PlanVersion.Status.PROPOSED,
        PlanVersion.Status.VALIDATED,
        PlanVersion.Status.GENERATED,
        PlanVersion.Status.DRAFT,
    ]
    for status in preferred_statuses:
        versions = list(
            PlanVersion.objects.filter(status=status)
            .select_related("plan")
            .order_by("-published_at", "-generated_at", "-created_at")[:3]
        )
        if versions:
            return versions
    return list(
        PlanVersion.objects.select_related("plan").order_by("-created_at", "-id")[:3]
    )


def _nearest_schedule_event(
    *,
    event_kind: str,
    event_at,
    asset_code: str,
    device: DeviceEndpoint | None,
    tolerance_minutes: int,
) -> tuple[ScheduleEvent | None, int]:
    event_type = EVENT_KIND_TO_SCHEDULE_EVENT_TYPE.get(event_kind)
    if event_type is None:
        return None, 0

    start = event_at - timezone.timedelta(minutes=tolerance_minutes)
    end = event_at + timezone.timedelta(minutes=tolerance_minutes)
    queryset = ScheduleEvent.objects.select_related(
        "trip",
        "trip__plan_version",
        "trip__assignment",
        "trip__assignment__jetty",
        "trip__assignment__tug",
        "trip__assignment__barge",
        "trip__assignment__cts",
    ).filter(
        trip__plan_version__in=_active_plan_versions(),
        event_type=event_type,
        planned_at__gte=start,
        planned_at__lte=end,
    )
    lookup_code = asset_code or (device.asset_code if device else "")
    if lookup_code:
        queryset = queryset.filter(
            Q(resource_code=lookup_code)
            | Q(location_label=lookup_code)
            | Q(trip__assignment__jetty__code=lookup_code)
            | Q(trip__assignment__tug__code=lookup_code)
            | Q(trip__assignment__barge__code=lookup_code)
            | Q(trip__assignment__cts__code=lookup_code)
        )

    candidates = list(queryset[:50])
    if not candidates:
        return None, 0
    candidates.sort(key=lambda item: abs((item.planned_at - event_at).total_seconds()))
    nearest = candidates[0]
    nearest_delta = abs((nearest.planned_at - event_at).total_seconds())
    same_nearest_count = sum(
        1
        for item in candidates
        if abs((item.planned_at - event_at).total_seconds()) == nearest_delta
    )
    return nearest, same_nearest_count


def _schedule_event_for_trip(*, trip: Trip, event_kind: str) -> ScheduleEvent | None:
    event_type = EVENT_KIND_TO_SCHEDULE_EVENT_TYPE.get(event_kind)
    if event_type is None:
        return None
    return trip.events.filter(event_type=event_type).order_by("sequence").first()


def _dedupe_key(
    *,
    feed: IntegrationFeed,
    device: DeviceEndpoint | None,
    event_kind: str,
    asset_code: str,
    event_at,
    schedule_event: ScheduleEvent | None,
    payload: dict,
) -> str:
    if payload.get("dedupe_key"):
        return payload["dedupe_key"]
    payload_body = payload.get("payload") or {}
    external_event_id = (
        payload.get("external_event_id")
        or payload.get("source_event_id")
        or payload_body.get("external_event_id")
        or payload_body.get("source_event_id")
        or payload_body.get("event_id")
    )
    bucket = event_at.replace(second=0, microsecond=0).isoformat()
    if external_event_id:
        return f"{feed.feed_id}|external|{external_event_id}"
    return "|".join(
        [
            feed.feed_id,
            device.device_id if device else "no-device",
            event_kind,
            asset_code or "no-asset",
            bucket,
            str(schedule_event.id if schedule_event else "no-schedule-event"),
        ]
    )


def _device_health_summary(device: DeviceEndpoint | None) -> dict:
    if device is None:
        return {"isHealthy": False, "reason": "missing_device"}
    if device.feed.status != IntegrationFeed.Status.ACTIVE:
        return {
            "isHealthy": False,
            "reason": "feed_not_active",
            "feedStatus": device.feed.status,
        }
    if device.status != DeviceEndpoint.Status.ACTIVE:
        return {"isHealthy": False, "reason": "device_not_active", "status": device.status}
    latest = device.health_snapshots.order_by("-observed_at", "-id").first()
    evaluation = _device_health_evaluation(device=device, snapshot=latest, now=timezone.now())
    if evaluation["deviceStatus"] != DeviceEndpoint.Status.ACTIVE:
        return {
            "isHealthy": False,
            "reason": evaluation["reason"],
            "status": evaluation["deviceStatus"],
            "healthStatus": evaluation["healthStatus"],
            "observedAt": evaluation["observedAt"],
            "freshnessSeconds": evaluation["freshnessSeconds"],
        }
    if latest and latest.health_status in {
        DeviceHealthSnapshot.HealthStatus.CRITICAL,
        DeviceHealthSnapshot.HealthStatus.OFFLINE,
        DeviceHealthSnapshot.HealthStatus.UNKNOWN,
    }:
        return {
            "isHealthy": False,
            "reason": "device_health_not_trusted",
            "healthStatus": latest.health_status,
            "observedAt": latest.observed_at.isoformat(),
        }
    return {
        "isHealthy": True,
        "reason": "active_device",
        "healthStatus": latest.health_status if latest else "not_reported",
        "observedAt": latest.observed_at.isoformat() if latest else None,
    }


def _metadata_decimal(metadata: dict, key: str, default: Decimal) -> Decimal:
    try:
        return Decimal(str(metadata.get(key, default)))
    except Exception:
        return default


def _confirmed_event_for_candidate(
    candidate: OperationalEventCandidate,
) -> ConfirmedOperationalEvent | None:
    try:
        return candidate.confirmed_event
    except ConfirmedOperationalEvent.DoesNotExist:
        return None


def _event_before_state(
    candidate: OperationalEventCandidate,
    schedule_event: ScheduleEvent | None,
    trip: Trip | None,
    assignment: Assignment | None,
) -> dict:
    state = {
        "candidate": {
            "status": candidate.status,
            "event_kind": candidate.event_kind,
            "event_at": candidate.event_at.isoformat(),
        }
    }
    if schedule_event:
        state["schedule_event"] = {
            "id": schedule_event.id,
            "event_type": schedule_event.event_type,
            "planned_at": schedule_event.planned_at.isoformat(),
            "actual_at": schedule_event.actual_at.isoformat() if schedule_event.actual_at else None,
            "status": schedule_event.status,
        }
    if assignment:
        state["assignment"] = {"id": assignment.id, "status": assignment.status}
    if trip:
        state["trip"] = {"id": trip.id, "trip_id": trip.trip_id, "status": trip.status}
    return state


def _summarize_actualizations(
    event: ConfirmedOperationalEvent,
    *,
    actualizations: list[OperationalActualization] | None = None,
) -> dict:
    rows = actualizations if actualizations is not None else list(event.actualizations.all())
    status_counts = {
        OperationalActualization.Status.APPLIED: 0,
        OperationalActualization.Status.SKIPPED: 0,
        OperationalActualization.Status.FAILED: 0,
    }
    for row in rows:
        status_counts[row.status] = status_counts.get(row.status, 0) + 1
    return {
        "actualizationIds": [row.actualization_id for row in rows],
        "applied": status_counts.get(OperationalActualization.Status.APPLIED, 0),
        "skipped": status_counts.get(OperationalActualization.Status.SKIPPED, 0),
        "failed": status_counts.get(OperationalActualization.Status.FAILED, 0),
    }


def _apply_device_health_snapshot(*, snapshot: DeviceHealthSnapshot, now) -> dict:
    device = DeviceEndpoint.objects.select_for_update().select_related("feed").get(
        pk=snapshot.device_id
    )
    health_summary = _device_health_evaluation(device=device, snapshot=snapshot, now=now)
    update_fields = ["status", "metadata", "updated_at"]
    device.status = health_summary["deviceStatus"]
    device.metadata = {
        **device.metadata,
        "health": health_summary,
    }
    if device.last_seen_at is None or snapshot.observed_at > device.last_seen_at:
        device.last_seen_at = snapshot.observed_at
        update_fields.append("last_seen_at")
    device.save(update_fields=update_fields)
    return health_summary


def _device_health_evaluation(
    *,
    device: DeviceEndpoint,
    snapshot: DeviceHealthSnapshot | None,
    now,
) -> dict:
    threshold = max(int(device.feed.freshness_threshold_seconds or 0), 60)
    observed_at = snapshot.observed_at if snapshot else device.last_seen_at
    health_status = snapshot.health_status if snapshot else "not_reported"
    age_seconds = (
        max(0, int((now - observed_at).total_seconds())) if observed_at is not None else None
    )
    observed_gap = snapshot.gap_seconds if snapshot and snapshot.gap_seconds is not None else None
    freshness_seconds = max(
        [value for value in [age_seconds, observed_gap] if value is not None],
        default=None,
    )
    device_status = DeviceEndpoint.Status.ACTIVE
    risk_severity = "ok"
    reason = "healthy"

    if snapshot is None:
        reason = "not_reported" if observed_at is None else "active_device_no_snapshot"
    elif health_status == DeviceHealthSnapshot.HealthStatus.OFFLINE:
        device_status = DeviceEndpoint.Status.OFFLINE
        risk_severity = "critical"
        reason = "health_offline"
    elif health_status == DeviceHealthSnapshot.HealthStatus.CRITICAL:
        device_status = DeviceEndpoint.Status.DEGRADED
        risk_severity = "critical"
        reason = "health_critical"
    elif health_status in {
        DeviceHealthSnapshot.HealthStatus.WARNING,
        DeviceHealthSnapshot.HealthStatus.UNKNOWN,
    }:
        device_status = DeviceEndpoint.Status.DEGRADED
        risk_severity = "warning"
        reason = f"health_{health_status}"

    if freshness_seconds is not None and freshness_seconds >= threshold * 2:
        device_status = DeviceEndpoint.Status.OFFLINE
        risk_severity = "critical"
        reason = "freshness_offline"
    elif freshness_seconds is not None and freshness_seconds > threshold:
        if device_status == DeviceEndpoint.Status.ACTIVE:
            device_status = DeviceEndpoint.Status.DEGRADED
        if risk_severity == "ok":
            risk_severity = "warning"
        if reason == "healthy":
            reason = "freshness_degraded"

    return {
        "deviceId": device.device_id,
        "feedId": device.feed.feed_id,
        "healthStatus": health_status,
        "deviceStatus": device_status,
        "riskSeverity": risk_severity,
        "reason": reason,
        "freshnessThresholdSeconds": threshold,
        "freshnessSeconds": freshness_seconds,
        "ageSeconds": age_seconds,
        "gapSeconds": observed_gap,
        "observedAt": observed_at.isoformat() if observed_at else None,
        "calculatedAt": now.isoformat(),
    }


def _refresh_feed_health(feed: IntegrationFeed) -> None:
    if feed.status in {IntegrationFeed.Status.PAUSED, IntegrationFeed.Status.RETIRED}:
        return
    device_counts = {
        status: feed.devices.filter(status=status).count()
        for status in DeviceEndpoint.Status.values
    }
    target_status = (
        IntegrationFeed.Status.DEGRADED
        if device_counts.get(DeviceEndpoint.Status.DEGRADED, 0)
        or device_counts.get(DeviceEndpoint.Status.OFFLINE, 0)
        else IntegrationFeed.Status.ACTIVE
    )
    feed.metadata = {
        **feed.metadata,
        "health": {
            "devices": device_counts,
            "status": target_status,
            "calculatedAt": timezone.now().isoformat(),
        },
    }
    feed.status = target_status
    feed.save(update_fields=["status", "metadata", "updated_at"])


def _ensure_device_health_candidate(
    *,
    device: DeviceEndpoint,
    snapshot: DeviceHealthSnapshot | None,
    health_summary: dict,
    actor,
    request,
) -> tuple[OperationalEventCandidate, bool]:
    event_at = snapshot.observed_at if snapshot else timezone.now()
    bucket = event_at.replace(minute=0, second=0, microsecond=0).isoformat()
    dedupe_key = "|".join(
        [
            device.feed.feed_id,
            device.device_id,
            "device_health",
            health_summary["reason"],
            bucket,
        ]
    )
    existing = (
        OperationalEventCandidate.objects.filter(feed=device.feed, dedupe_key=dedupe_key)
        .exclude(status=OperationalEventCandidate.Status.DUPLICATE)
        .order_by("created_at", "id")
        .first()
    )
    if existing:
        return existing, False

    candidate = OperationalEventCandidate.objects.create(
        feed=device.feed,
        device=device,
        source_kind=OperationalEventCandidate.SourceKind.DEVICE,
        event_kind=OperationalEventKind.DEVICE_OFFLINE,
        asset_type=device.asset_type or OperationsAssetType.DEVICE,
        asset_code=device.asset_code or device.device_id,
        event_at=event_at,
        received_at=timezone.now(),
        confidence_score=Decimal("100.00"),
        dedupe_key=dedupe_key,
        status=OperationalEventCandidate.Status.PENDING,
        payload={
            "source": "device_health",
            "snapshot_id": snapshot.snapshot_id if snapshot else None,
            "device_id": device.device_id,
            "feed_id": device.feed.feed_id,
            "health": health_summary,
        },
        metadata={
            "healthRisk": {
                **health_summary,
                "snapshotRef": snapshot.snapshot_id if snapshot else None,
                "message": _health_risk_message(device=device, health_summary=health_summary),
            }
        },
    )
    _record_candidate_audit(
        candidate=candidate,
        actor=actor,
        action="operations.device_health.risk_created",
        request=request,
        metadata={"healthRisk": candidate.metadata["healthRisk"]},
    )
    return candidate, True


def _health_risk_message(*, device: DeviceEndpoint, health_summary: dict) -> str:
    status = str(health_summary.get("healthStatus", "unknown")).replace("_", " ")
    reason = str(health_summary.get("reason", "health risk")).replace("_", " ")
    return (
        f"{device.device_id} reports {status}; feed {device.feed.feed_id} is "
        f"not trusted for auto-confirm until {reason} is reviewed."
    )


def _health_risk_candidate_summary(candidate: OperationalEventCandidate) -> dict:
    risk = candidate.metadata.get("healthRisk") or {}
    return {
        "id": candidate.id,
        "candidateId": candidate.candidate_id,
        "feedId": candidate.feed.feed_id,
        "deviceId": candidate.device.device_id if candidate.device_id else None,
        "eventKind": candidate.event_kind,
        "assetType": candidate.asset_type,
        "assetCode": candidate.asset_code,
        "status": candidate.status,
        "severity": risk.get("riskSeverity", "critical"),
        "healthStatus": risk.get("healthStatus"),
        "deviceStatus": risk.get("deviceStatus"),
        "reason": risk.get("reason"),
        "message": risk.get("message", "Device or feed health requires review."),
        "observedAt": risk.get("observedAt") or candidate.event_at.isoformat(),
        "createdAt": candidate.created_at.isoformat(),
    }


def _mark_device_seen(*, device: DeviceEndpoint | None, event_at) -> None:
    if device is None:
        return
    if device.last_seen_at is None or event_at > device.last_seen_at:
        device.last_seen_at = event_at
        device.save(update_fields=["last_seen_at", "updated_at"])


def _next_action_after_event(event_kind: str) -> str:
    return {
        OperationalEventKind.JETTY_LOADING_STARTED: (
            "Monitor loading progress and confirm completion."
        ),
        OperationalEventKind.JETTY_LOADING_COMPLETED: "Dispatch tug/barge chain from jetty.",
        OperationalEventKind.JETTY_DEPARTED: "Monitor bridge and tide gate transit.",
        OperationalEventKind.BRIDGE_CROSSED: "Monitor tide gate transit.",
        OperationalEventKind.TIDE_GATE_PASSED: "Monitor CTS arrival.",
        OperationalEventKind.CTS_ARRIVED: "Confirm discharge start and CTS rate.",
        OperationalEventKind.CTS_DISCHARGE_STARTED: "Monitor CTS discharge completion.",
        OperationalEventKind.CTS_DISCHARGE_COMPLETED: (
            "Close execution milestone and monitor OGV progress."
        ),
    }.get(event_kind, "Review confirmed operational event.")


def _variance_minutes(planned_at, actual_at) -> int:
    return int(round((actual_at - planned_at).total_seconds() / 60))


def _required(payload: dict, field_name: str):
    value = payload.get(field_name)
    if value in (None, ""):
        raise ValidationError({field_name: "This field is required."})
    return value


def _coerce_datetime(value, *, field_name: str = "timestamp"):
    if hasattr(value, "isoformat"):
        result = value
    else:
        result = parse_datetime(str(value))
    if result is None:
        raise ValidationError({field_name: "Enter a valid ISO-8601 datetime."})
    if timezone.is_naive(result):
        result = timezone.make_aware(result, timezone.get_current_timezone())
    return result


def _coerce_decimal(value) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValidationError({"confidence_score": "Enter a valid decimal."}) from exc


def _coerce_optional_decimal(value):
    if value in (None, ""):
        return None
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValidationError({"value": "Enter a valid decimal."}) from exc
