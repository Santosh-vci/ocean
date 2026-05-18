from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from django.utils import timezone

from apps.audit.services import record_audit_event
from apps.scheduling.models import Assignment, PlanVersion, ScheduleEvent

from .models import (
    DeviceEndpoint,
    EdgeEventBatch,
    IntegrationFeed,
    OperationalEventCandidate,
    OperationalEventKind,
    OperationsAssetType,
)
from .services import ingest_device_health, ingest_operational_event

PHASE4_BATCH_SEQUENCES = (
    "PHASE4-EXECUTION-001",
    "PHASE4-HEALTH-001",
)


@dataclass(frozen=True)
class EdgeBatchCreationResult:
    batch: EdgeEventBatch
    created: bool


@dataclass(frozen=True)
class EdgeBatchReplayResult:
    batch: EdgeEventBatch
    idempotent: bool
    summary: dict


def create_edge_event_batch(*, payload: dict) -> EdgeBatchCreationResult:
    feed = _resolve_feed(payload)
    device = _resolve_device(payload, feed=feed)
    messages = payload.get("messages") or []
    checksum = payload.get("checksum_sha256") or _checksum(messages)
    batch_sequence = payload.get("batch_sequence", "")
    existing = None
    if batch_sequence and checksum:
        existing = EdgeEventBatch.objects.filter(
            feed=feed,
            device=device,
            batch_sequence=batch_sequence,
            checksum_sha256=checksum,
        ).first()
    if existing:
        return EdgeBatchCreationResult(batch=existing, created=False)

    batch = EdgeEventBatch.objects.create(
        feed=feed,
        device=device,
        batch_sequence=batch_sequence,
        captured_from=payload.get("captured_from"),
        captured_to=payload.get("captured_to"),
        received_at=payload.get("received_at") or timezone.now(),
        message_count=len(messages),
        checksum_sha256=checksum,
        metadata={
            **(payload.get("metadata") or {}),
            "messages": messages,
        },
    )
    return EdgeBatchCreationResult(batch=batch, created=True)


def replay_edge_batch(
    *,
    batch: EdgeEventBatch,
    actor=None,
    request=None,
) -> EdgeBatchReplayResult:
    existing_summary = batch.metadata.get("replaySummary")
    if batch.status == EdgeEventBatch.Status.PROCESSED and existing_summary:
        record_audit_event(
            actor=actor,
            organization=None,
            action="operations.edge_batch.replay_skipped",
            object_type="edge_event_batch",
            object_id=str(batch.pk),
            object_repr=batch.batch_id,
            metadata={
                "batch_id": batch.batch_id,
                "batch_sequence": batch.batch_sequence,
                "reason": "already_processed",
                "summary": existing_summary,
            },
            request=request,
        )
        return EdgeBatchReplayResult(
            batch=batch,
            idempotent=True,
            summary=existing_summary,
        )

    messages = batch.metadata.get("messages") or []
    results: list[dict] = []
    errors: list[dict] = []
    for index, message in enumerate(messages, start=1):
        try:
            results.append(
                _replay_message(
                    message=message,
                    index=index,
                    actor=actor,
                    request=request,
                )
            )
        except Exception as exc:
            errors.append(
                {
                    "index": index,
                    "type": message.get("type") or "event",
                    "error": str(exc),
                }
            )

    event_results = [row for row in results if row["type"] == "event"]
    health_results = [row for row in results if row["type"] == "health"]
    summary = {
        "batchId": batch.batch_id,
        "batchSequence": batch.batch_sequence,
        "messageCount": len(messages),
        "processedCount": len(results),
        "errorCount": len(errors),
        "eventCandidateCount": len(event_results),
        "createdCandidateCount": sum(1 for row in event_results if row["created"]),
        "duplicateCandidateCount": sum(1 for row in event_results if row["duplicate"]),
        "autoConfirmedCount": sum(1 for row in event_results if row["autoConfirmed"]),
        "pendingCandidateCount": sum(
            1
            for row in event_results
            if row["status"] == OperationalEventCandidate.Status.PENDING
        ),
        "healthSnapshotCount": len(health_results),
        "healthRiskCount": sum(1 for row in health_results if row["createdRisk"]),
        "candidateRefs": [
            row["candidateRef"] for row in event_results if row["candidateRef"] is not None
        ],
        "healthSnapshotRefs": [row["snapshotRef"] for row in health_results],
        "errors": errors,
    }
    if errors and results:
        status = EdgeEventBatch.Status.PARTIAL
    elif errors:
        status = EdgeEventBatch.Status.FAILED
    else:
        status = EdgeEventBatch.Status.PROCESSED

    batch.status = status
    batch.message_count = len(messages)
    batch.metadata = {
        **batch.metadata,
        "messageResults": results,
        "errors": errors,
        "replaySummary": summary,
        "processedAt": timezone.now().isoformat(),
    }
    batch.save(update_fields=["status", "message_count", "metadata", "updated_at"])
    record_audit_event(
        actor=actor,
        organization=None,
        action="operations.edge_batch.replayed",
        object_type="edge_event_batch",
        object_id=str(batch.pk),
        object_repr=batch.batch_id,
        metadata=summary,
        request=request,
    )
    return EdgeBatchReplayResult(batch=batch, idempotent=False, summary=summary)


def seed_phase4_event_pack(*, reset_status: bool = True) -> list[EdgeEventBatch]:
    feed = _trusted_synthetic_feed()
    devices = _phase4_devices(feed=feed)
    events = _active_trip_events()
    execution_messages = _execution_messages(devices=devices, events=events)
    health_messages = _health_messages(devices=devices, events=events)
    specs = [
        {
            "sequence": PHASE4_BATCH_SEQUENCES[0],
            "device": devices["jetty"],
            "messages": execution_messages,
            "metadata": {
                "seed": "phase4_replay",
                "fixtureFamily": "operations_execution",
                "description": "Trusted execution events plus pending manual-review candidates.",
            },
        },
        {
            "sequence": PHASE4_BATCH_SEQUENCES[1],
            "device": devices["tide"],
            "messages": health_messages,
            "metadata": {
                "seed": "phase4_replay",
                "fixtureFamily": "device_health",
                "description": "Healthy heartbeat followed by a synthetic offline outage.",
            },
        },
    ]
    batches = []
    for spec in specs:
        existing = EdgeEventBatch.objects.filter(
            feed=feed,
            batch_sequence=spec["sequence"],
        ).first()
        checksum = _checksum(spec["messages"])
        if existing:
            existing.device = spec["device"]
            existing.captured_from = _captured_from(spec["messages"])
            existing.captured_to = _captured_to(spec["messages"])
            existing.received_at = timezone.now()
            existing.message_count = len(spec["messages"])
            existing.checksum_sha256 = checksum
            existing.metadata = {
                **spec["metadata"],
                "messages": spec["messages"],
            }
            if reset_status:
                existing.status = EdgeEventBatch.Status.RECEIVED
            existing.save()
            batches.append(existing)
            continue

        batches.append(
            EdgeEventBatch.objects.create(
                feed=feed,
                device=spec["device"],
                batch_sequence=spec["sequence"],
                captured_from=_captured_from(spec["messages"]),
                captured_to=_captured_to(spec["messages"]),
                received_at=timezone.now(),
                message_count=len(spec["messages"]),
                checksum_sha256=checksum,
                metadata={
                    **spec["metadata"],
                    "messages": spec["messages"],
                },
            )
        )
    return batches


def _replay_message(*, message: dict, index: int, actor, request) -> dict:
    message_type = message.get("type") or "event"
    payload = message.get("payload") or {}
    if message_type == "event":
        result = ingest_operational_event(payload=payload, actor=actor, request=request)
        return {
            "index": index,
            "type": message_type,
            "candidateRef": result.candidate.candidate_id,
            "status": result.candidate.status,
            "created": result.created,
            "duplicate": result.duplicate,
            "autoConfirmed": result.auto_confirmed,
            "confirmedEventRef": (
                result.confirmed_event.event_id if result.confirmed_event else None
            ),
        }
    if message_type == "health":
        result = ingest_device_health(payload=payload, actor=actor, request=request)
        return {
            "index": index,
            "type": message_type,
            "snapshotRef": result.snapshot.snapshot_id,
            "healthStatus": result.snapshot.health_status,
            "deviceStatus": result.health_summary["deviceStatus"],
            "createdRisk": result.created_risk,
            "candidateRef": result.candidate.candidate_id if result.candidate else None,
        }
    raise ValueError(f"Unsupported edge message type: {message_type}")


def _trusted_synthetic_feed() -> IntegrationFeed:
    feed = IntegrationFeed.objects.get(feed_id="SYN-OPS-PHASE4")
    feed.status = IntegrationFeed.Status.ACTIVE
    feed.trust_mode = IntegrationFeed.TrustMode.AUTO_CONFIRM_WITH_THRESHOLD
    feed.metadata = {
        **feed.metadata,
        "confidenceThreshold": "90",
        "autoConfirmToleranceMinutes": 180,
        "phase4ReplayTrusted": True,
    }
    feed.save(update_fields=["status", "trust_mode", "metadata", "updated_at"])
    return feed


def _phase4_devices(*, feed: IntegrationFeed) -> dict[str, DeviceEndpoint]:
    device_map = {
        "jetty": "JETTY-JTY-SUARAN-OPS",
        "bridge": "BRIDGE-GATE-B-OPS",
        "tide": "TIDE-RANTAU-OPS",
        "cts": "CTS-BORNEO-OPS",
    }
    devices = {}
    for key, device_id in device_map.items():
        device = DeviceEndpoint.objects.get(device_id=device_id)
        if device.feed_id != feed.id:
            device.feed = feed
        device.status = DeviceEndpoint.Status.ACTIVE
        device.save(update_fields=["feed", "status", "updated_at"])
        devices[key] = device
    return devices


def _active_trip_events() -> dict[str, object]:
    active_version = _active_schedule_version()
    assignment = (
        Assignment.objects.select_related(
            "trip",
            "trip__voyage",
            "jetty",
            "cts",
        )
        .filter(trip__plan_version=active_version)
        .order_by("trip__sequence")
        .first()
    )
    if assignment is None:
        raise RuntimeError("Phase 4 replay requires an active assignment.")
    events = {
        event.event_type: event
        for event in assignment.trip.events.order_by("sequence")
    }
    required = {
        ScheduleEvent.EventType.LOAD_START,
        ScheduleEvent.EventType.LOAD_COMPLETE,
        ScheduleEvent.EventType.DEPART_JETTY,
        ScheduleEvent.EventType.BRIDGE_CROSS,
        ScheduleEvent.EventType.TIDE_GATE,
        ScheduleEvent.EventType.ARRIVE_CTS,
        ScheduleEvent.EventType.DISCHARGE_COMPLETE,
    }
    missing = required.difference(events)
    if missing:
        raise RuntimeError(f"Phase 4 replay missing schedule events: {sorted(missing)}")
    return {
        "assignment": assignment,
        "trip": assignment.trip,
        **events,
    }


def _execution_messages(
    *,
    devices: dict[str, DeviceEndpoint],
    events: dict[str, object],
) -> list[dict]:
    assignment = events["assignment"]
    trip = events["trip"]
    jetty = devices["jetty"]
    bridge = devices["bridge"]
    tide = devices["tide"]
    cts = devices["cts"]
    load_start = events[ScheduleEvent.EventType.LOAD_START]
    load_complete = events[ScheduleEvent.EventType.LOAD_COMPLETE]
    depart_jetty = events[ScheduleEvent.EventType.DEPART_JETTY]
    bridge_cross = events[ScheduleEvent.EventType.BRIDGE_CROSS]
    tide_gate = events[ScheduleEvent.EventType.TIDE_GATE]
    arrive_cts = events[ScheduleEvent.EventType.ARRIVE_CTS]
    discharge_complete = events[ScheduleEvent.EventType.DISCHARGE_COMPLETE]

    messages = [
        _health_message(
            device=jetty,
            observed_at=load_start.planned_at - timezone.timedelta(minutes=15),
            status="healthy",
            network_status="online",
        ),
        _health_message(
            device=bridge,
            observed_at=bridge_cross.planned_at - timezone.timedelta(minutes=15),
            status="healthy",
            network_status="online",
        ),
        _health_message(
            device=tide,
            observed_at=tide_gate.planned_at - timezone.timedelta(minutes=15),
            status="healthy",
            network_status="online",
        ),
        _health_message(
            device=cts,
            observed_at=arrive_cts.planned_at - timezone.timedelta(minutes=15),
            status="healthy",
            network_status="online",
        ),
        _event_message(
            device=jetty,
            event_kind=OperationalEventKind.JETTY_LOADING_STARTED,
            event_at=load_start.planned_at + timezone.timedelta(minutes=10),
            schedule_event=load_start,
            asset_type=OperationsAssetType.JETTY,
            asset_code=assignment.jetty.code,
            dedupe_key="phase4-load-start",
            payload={"operator": "jetty.operator.synthetic"},
        ),
        _event_message(
            device=jetty,
            event_kind=OperationalEventKind.JETTY_LOADING_STARTED,
            event_at=load_start.planned_at + timezone.timedelta(minutes=10),
            schedule_event=load_start,
            asset_type=OperationsAssetType.JETTY,
            asset_code=assignment.jetty.code,
            dedupe_key="phase4-load-start",
            payload={"operator": "jetty.operator.synthetic", "duplicate": True},
        ),
        _event_message(
            device=jetty,
            event_kind=OperationalEventKind.JETTY_LOADING_COMPLETED,
            event_at=load_complete.planned_at + timezone.timedelta(minutes=35),
            schedule_event=load_complete,
            asset_type=OperationsAssetType.JETTY,
            asset_code=assignment.jetty.code,
            dedupe_key="phase4-load-complete",
            confirmed_quantity_mt=Decimal("12650.00"),
            payload={"operator": "jetty.operator.synthetic"},
        ),
        _event_message(
            device=jetty,
            event_kind=OperationalEventKind.JETTY_DEPARTED,
            event_at=depart_jetty.planned_at + timezone.timedelta(minutes=5),
            schedule_event=depart_jetty,
            asset_type=OperationsAssetType.JETTY,
            asset_code=assignment.jetty.code,
            dedupe_key="phase4-jetty-departed",
        ),
        _event_message(
            device=bridge,
            event_kind=OperationalEventKind.BRIDGE_OPENED,
            event_at=bridge_cross.planned_at - timezone.timedelta(minutes=5),
            schedule_event=None,
            asset_type=OperationsAssetType.BRIDGE,
            asset_code=bridge.asset_code,
            dedupe_key="phase4-bridge-opened",
            confidence_score=Decimal("82.00"),
        ),
        _event_message(
            device=bridge,
            event_kind=OperationalEventKind.BRIDGE_CROSSED,
            event_at=bridge_cross.planned_at + timezone.timedelta(minutes=8),
            schedule_event=bridge_cross,
            asset_type=OperationsAssetType.BRIDGE,
            asset_code=bridge.asset_code,
            dedupe_key="phase4-bridge-crossed",
        ),
        _event_message(
            device=tide,
            event_kind=OperationalEventKind.TIDE_LEVEL_OBSERVED,
            event_at=tide_gate.planned_at - timezone.timedelta(minutes=20),
            schedule_event=None,
            asset_type=OperationsAssetType.TIDE_GATE,
            asset_code=tide.asset_code,
            dedupe_key="phase4-tide-level",
            confidence_score=Decimal("88.00"),
            payload={"observed_level_m": "1.80", "threshold_m": "2.10"},
        ),
        _event_message(
            device=tide,
            event_kind=OperationalEventKind.TIDE_GATE_PASSED,
            event_at=tide_gate.planned_at + timezone.timedelta(minutes=12),
            schedule_event=tide_gate,
            asset_type=OperationsAssetType.TIDE_GATE,
            asset_code=tide.asset_code,
            dedupe_key="phase4-tide-gate-passed",
        ),
        _event_message(
            device=cts,
            event_kind=OperationalEventKind.CTS_ARRIVED,
            event_at=arrive_cts.planned_at + timezone.timedelta(minutes=15),
            schedule_event=arrive_cts,
            asset_type=OperationsAssetType.CTS,
            asset_code=assignment.cts.code,
            dedupe_key="phase4-cts-arrived",
        ),
        _event_message(
            device=cts,
            event_kind=OperationalEventKind.CTS_DISCHARGE_STARTED,
            event_at=arrive_cts.planned_at + timezone.timedelta(minutes=18),
            schedule_event=None,
            asset_type=OperationsAssetType.CTS,
            asset_code=assignment.cts.code,
            dedupe_key="phase4-discharge-started",
        ),
        _event_message(
            device=cts,
            event_kind=OperationalEventKind.CTS_RATE_UPDATED,
            event_at=arrive_cts.planned_at + timezone.timedelta(minutes=25),
            schedule_event=None,
            asset_type=OperationsAssetType.CTS,
            asset_code=assignment.cts.code,
            dedupe_key="phase4-cts-rate",
            confidence_score=Decimal("65.00"),
            confirmed_rate_tph=Decimal("1600.00"),
            payload={"planned_rate_tph": "2200.00"},
        ),
        _event_message(
            device=cts,
            event_kind=OperationalEventKind.CTS_DISCHARGE_COMPLETED,
            event_at=discharge_complete.planned_at + timezone.timedelta(minutes=20),
            schedule_event=discharge_complete,
            asset_type=OperationsAssetType.CTS,
            asset_code=assignment.cts.code,
            dedupe_key="phase4-discharge-complete",
        ),
    ]
    for message in messages:
        if message["type"] == "event":
            message["payload"]["trip_id"] = trip.trip_id
            message["payload"]["assignment_id"] = assignment.id
    return messages


def _health_messages(
    *,
    devices: dict[str, DeviceEndpoint],
    events: dict[str, object],
) -> list[dict]:
    tide = devices["tide"]
    tide_gate = events[ScheduleEvent.EventType.TIDE_GATE]
    return [
        _health_message(
            device=tide,
            observed_at=tide_gate.planned_at + timezone.timedelta(minutes=5),
            status="healthy",
            network_status="online",
        ),
        _health_message(
            device=tide,
            observed_at=tide_gate.planned_at + timezone.timedelta(minutes=35),
            status="offline",
            network_status="broker_timeout",
            gap_seconds=tide.feed.freshness_threshold_seconds * 2 + 60,
        ),
    ]


def _event_message(
    *,
    device: DeviceEndpoint,
    event_kind: str,
    event_at,
    schedule_event: ScheduleEvent | None,
    asset_type: str,
    asset_code: str,
    dedupe_key: str,
    confidence_score: Decimal = Decimal("96.00"),
    payload: dict | None = None,
    confirmed_quantity_mt: Decimal | None = None,
    confirmed_rate_tph: Decimal | None = None,
) -> dict:
    message_payload = {
        "feed_id": device.feed.feed_id,
        "device_id": device.device_id,
        "source_kind": OperationalEventCandidate.SourceKind.SYNTHETIC,
        "event_kind": event_kind,
        "asset_type": asset_type,
        "asset_code": asset_code,
        "schedule_event_id": schedule_event.id if schedule_event else None,
        "event_at": event_at.isoformat(),
        "confidence_score": str(confidence_score),
        "dedupe_key": dedupe_key,
        "payload": payload or {},
        "metadata": {
            "seed": "phase4_replay",
            "replayProof": True,
        },
    }
    if confirmed_quantity_mt is not None:
        message_payload["confirmed_quantity_mt"] = str(confirmed_quantity_mt)
    if confirmed_rate_tph is not None:
        message_payload["confirmed_rate_tph"] = str(confirmed_rate_tph)
    return {
        "type": "event",
        "payload": message_payload,
    }


def _health_message(
    *,
    device: DeviceEndpoint,
    observed_at,
    status: str,
    network_status: str,
    gap_seconds: int = 0,
) -> dict:
    return {
        "type": "health",
        "payload": {
            "feed_id": device.feed.feed_id,
            "device_id": device.device_id,
            "observed_at": observed_at.isoformat(),
            "health_status": status,
            "network_status": network_status,
            "gap_seconds": gap_seconds,
            "metadata": {
                "seed": "phase4_replay",
                "replayProof": True,
            },
        },
    }


def _active_schedule_version() -> PlanVersion:
    statuses = [
        PlanVersion.Status.PUBLISHED,
        PlanVersion.Status.APPROVED,
        PlanVersion.Status.PROPOSED,
        PlanVersion.Status.VALIDATED,
        PlanVersion.Status.GENERATED,
        PlanVersion.Status.DRAFT,
    ]
    for status in statuses:
        version = (
            PlanVersion.objects.filter(status=status)
            .order_by("-published_at", "-generated_at", "-created_at", "-id")
            .first()
        )
        if version:
            return version
    raise RuntimeError("Phase 4 replay requires an active schedule version.")


def _captured_from(messages: list[dict]):
    timestamps = [_message_timestamp(message) for message in messages]
    return min(timestamps) if timestamps else None


def _captured_to(messages: list[dict]):
    timestamps = [_message_timestamp(message) for message in messages]
    return max(timestamps) if timestamps else None


def _message_timestamp(message: dict):
    payload = message.get("payload") or {}
    value = payload.get("event_at") or payload.get("observed_at")
    return datetime.fromisoformat(value)


def _checksum(messages: list[dict]) -> str:
    canonical = json.dumps(messages, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _resolve_feed(payload: dict) -> IntegrationFeed:
    feed = payload.get("feed")
    if isinstance(feed, IntegrationFeed):
        return feed
    if feed:
        return IntegrationFeed.objects.get(pk=feed)
    feed_id = payload.get("feed_id")
    if feed_id:
        return IntegrationFeed.objects.get(feed_id=feed_id)
    raise ValueError("Edge batch requires a feed.")


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
