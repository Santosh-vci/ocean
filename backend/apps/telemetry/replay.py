from __future__ import annotations

from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.masters.models import Location
from apps.planning.models import OGVVoyage
from apps.scheduling.models import Assignment, PlanVersion, ScheduleEvent

from .models import (
    AssetIdentity,
    LatestAssetState,
    LiveEtaProjection,
    PositionPing,
    TelemetryReplayRun,
    TelemetrySource,
    TrackingAlert,
)
from .services import ingest_position_ping, refresh_signal_health

REPLAY_FAMILIES = [
    {
        "scenario_code": "TRACK-ON-TIME",
        "name": "On-time route proof",
        "description": "Tug leaves jetty and crosses bridge ahead of plan.",
        "speed_multiplier": Decimal("4.00"),
    },
    {
        "scenario_code": "TRACK-JETTY-DELAY",
        "name": "Jetty delay proof",
        "description": "Barge remains in the jetty after planned departure.",
        "speed_multiplier": Decimal("4.00"),
    },
    {
        "scenario_code": "TRACK-BRIDGE-WAIT",
        "name": "Bridge wait proof",
        "description": "Tug reaches bridge late and raises ETA risk.",
        "speed_multiplier": Decimal("4.00"),
    },
    {
        "scenario_code": "TRACK-STALE-SIGNAL",
        "name": "Stale signal proof",
        "description": "Barge signal stops mid-route and turns stale.",
        "speed_multiplier": Decimal("4.00"),
    },
    {
        "scenario_code": "TRACK-OGV-ETA-SHIFT",
        "name": "OGV ETA shift proof",
        "description": "AIS-style OGV pings show a later approach.",
        "speed_multiplier": Decimal("4.00"),
    },
    {
        "scenario_code": "TRACK-CTS-APPROACH",
        "name": "CTS approach proof",
        "description": "Loaded barge approaches and enters the CTS zone.",
        "speed_multiplier": Decimal("4.00"),
    },
]


def seed_phase3_replay_runs(*, reset_status: bool = True) -> list[TelemetryReplayRun]:
    seed_start_at = _active_seed_start()
    runs = []
    for family in REPLAY_FAMILIES:
        replay_id = f"RPL-{family['scenario_code']}"
        defaults = {
            "name": family["name"],
            "scenario_code": family["scenario_code"],
            "speed_multiplier": family["speed_multiplier"],
            "seed_start_at": seed_start_at,
            "metadata": {
                "seeded": True,
                "fixtureFamily": family["scenario_code"],
                "description": family["description"],
            },
        }
        if reset_status:
            defaults.update(
                {
                    "status": TelemetryReplayRun.Status.DRAFT,
                    "started_at": None,
                    "completed_at": None,
                }
            )
        run, _ = TelemetryReplayRun.objects.update_or_create(
            replay_id=replay_id,
            defaults=defaults,
        )
        runs.append(run)
    return runs


def start_synthetic_replay(
    *,
    replay_run: TelemetryReplayRun,
    speed_multiplier: Decimal | None = None,
) -> dict:
    if replay_run.scenario_code not in {item["scenario_code"] for item in REPLAY_FAMILIES}:
        raise ValueError(f"Unknown replay family: {replay_run.scenario_code}")

    with transaction.atomic():
        replay_run.status = TelemetryReplayRun.Status.RUNNING
        replay_run.started_at = timezone.now()
        replay_run.completed_at = None
        if speed_multiplier is not None:
            replay_run.speed_multiplier = Decimal(str(speed_multiplier))
        replay_run.save(
            update_fields=[
                "status",
                "started_at",
                "completed_at",
                "speed_multiplier",
                "updated_at",
            ]
        )

        payloads = build_replay_payloads(replay_run=replay_run)
        asset_codes = sorted({payload["asset_code"] for payload in payloads})
        _reset_replay_evidence(replay_run=replay_run, asset_codes=asset_codes)

        results = [ingest_position_ping(payload=payload) for payload in payloads]
        stale_alert_count = 0
        if replay_run.scenario_code == "TRACK-STALE-SIGNAL" and results:
            last_ping = results[-1]["ping"]
            refresh_signal_health(
                now=last_ping.device_timestamp
                + timedelta(seconds=last_ping.source.freshness_threshold_seconds * 2 + 60)
            )
            stale_alert_count = TrackingAlert.objects.filter(
                asset_code=last_ping.asset_code,
                alert_type=TrackingAlert.AlertType.STALE_SIGNAL,
                evidence__replayId=replay_run.replay_id,
            ).count()

        ping_ids = [result["ping"].ping_id for result in results]
        movement_event_count = sum(len(result["geofence_events"]) for result in results)
        alert_count = (
            TrackingAlert.objects.filter(evidence__replayId=replay_run.replay_id)
            .exclude(status=TrackingAlert.Status.RESOLVED)
            .count()
        )
        projection_count = LiveEtaProjection.objects.filter(
            metadata__replayId=replay_run.replay_id
        ).count()
        replay_run.status = TelemetryReplayRun.Status.COMPLETED
        replay_run.completed_at = timezone.now()
        replay_run.metadata = {
            **replay_run.metadata,
            "assetCodes": asset_codes,
            "pingCount": len(results),
            "movementEventCount": movement_event_count,
            "projectionCount": projection_count,
            "alertCount": alert_count,
            "staleAlertCount": stale_alert_count,
            "pingIds": ping_ids,
        }
        replay_run.save(
            update_fields=[
                "status",
                "completed_at",
                "metadata",
                "updated_at",
            ]
        )

    return {
        "run": replay_run,
        "ping_count": len(results),
        "movement_event_count": movement_event_count,
        "projection_count": projection_count,
        "alert_count": alert_count,
        "asset_codes": asset_codes,
    }


def cancel_synthetic_replay(*, replay_run: TelemetryReplayRun) -> TelemetryReplayRun:
    replay_run.status = TelemetryReplayRun.Status.CANCELED
    replay_run.completed_at = timezone.now()
    replay_run.save(update_fields=["status", "completed_at", "updated_at"])
    return replay_run


def build_replay_payloads(*, replay_run: TelemetryReplayRun) -> list[dict]:
    active_version = _active_schedule_version()
    if not active_version:
        raise RuntimeError("Replay requires an active schedule version.")

    assignments = list(
        Assignment.objects.select_related(
            "trip",
            "trip__voyage",
            "tug",
            "barge",
            "jetty",
            "cts",
        )
        .prefetch_related("trip__events")
        .filter(trip__plan_version=active_version)
        .order_by("trip__sequence")
    )
    if not assignments:
        raise RuntimeError("Replay requires at least one active assignment.")

    locations = {location.code: location for location in Location.objects.all()}
    first_assignment = assignments[0]
    tug_08 = _assignment_for(assignments, tug_code="BER-TUG-08") or first_assignment
    tug_09 = _assignment_for(assignments, tug_code="BER-TUG-09") or first_assignment
    barge_val = _assignment_for(assignments, barge_code="BRG-VAL-08") or first_assignment
    barge_nus = _assignment_for(assignments, barge_code="BRG-NUS-17") or first_assignment
    barge_kal = _assignment_for(assignments, barge_code="BRG-KAL-22") or first_assignment

    payloads_by_family = {
        "TRACK-ON-TIME": [
            _payload(
                replay_run=replay_run,
                source_id="SYN-GPS-PHASE3",
                source_type=TelemetrySource.SourceType.SYNTHETIC_GPS,
                external_id="GPS-768",
                asset_type=AssetIdentity.AssetType.TUG,
                asset_code="BER-TUG-08",
                location=locations[_jetty_location_code(tug_08)],
                timestamp=_event_at(tug_08, ScheduleEvent.EventType.DEPART_JETTY)
                - timedelta(minutes=10),
                speed_knots="0.20",
                heading_degrees="095.00",
            ),
            _payload(
                replay_run=replay_run,
                source_id="SYN-GPS-PHASE3",
                source_type=TelemetrySource.SourceType.SYNTHETIC_GPS,
                external_id="GPS-768",
                asset_type=AssetIdentity.AssetType.TUG,
                asset_code="BER-TUG-08",
                location=locations["LOC-BRIDGE-GATE-B"],
                timestamp=_event_at(tug_08, ScheduleEvent.EventType.BRIDGE_CROSS)
                - timedelta(minutes=5),
                speed_knots="5.40",
                heading_degrees="090.00",
            ),
        ],
        "TRACK-JETTY-DELAY": [
            _payload(
                replay_run=replay_run,
                source_id="SYN-GPS-PHASE3",
                source_type=TelemetrySource.SourceType.SYNTHETIC_GPS,
                external_id="SYN-BRG-VAL-08",
                asset_type=AssetIdentity.AssetType.BARGE,
                asset_code="BRG-VAL-08",
                location=locations[_jetty_location_code(barge_val)],
                timestamp=_event_at(barge_val, ScheduleEvent.EventType.DEPART_JETTY)
                - timedelta(minutes=5),
                speed_knots="0.20",
                heading_degrees="090.00",
            ),
            _payload(
                replay_run=replay_run,
                source_id="SYN-GPS-PHASE3",
                source_type=TelemetrySource.SourceType.SYNTHETIC_GPS,
                external_id="SYN-BRG-VAL-08",
                asset_type=AssetIdentity.AssetType.BARGE,
                asset_code="BRG-VAL-08",
                location=locations[_jetty_location_code(barge_val)],
                timestamp=_event_at(barge_val, ScheduleEvent.EventType.DEPART_JETTY)
                + timedelta(minutes=45),
                speed_knots="0.20",
                heading_degrees="090.00",
            ),
        ],
        "TRACK-BRIDGE-WAIT": [
            _payload(
                replay_run=replay_run,
                source_id="SYN-GPS-PHASE3",
                source_type=TelemetrySource.SourceType.SYNTHETIC_GPS,
                external_id="GPS-771",
                asset_type=AssetIdentity.AssetType.TUG,
                asset_code="BER-TUG-09",
                location=locations[_jetty_location_code(tug_09)],
                timestamp=_event_at(tug_09, ScheduleEvent.EventType.DEPART_JETTY)
                - timedelta(minutes=5),
                speed_knots="0.30",
                heading_degrees="090.00",
            ),
            _payload(
                replay_run=replay_run,
                source_id="SYN-GPS-PHASE3",
                source_type=TelemetrySource.SourceType.SYNTHETIC_GPS,
                external_id="GPS-771",
                asset_type=AssetIdentity.AssetType.TUG,
                asset_code="BER-TUG-09",
                location=locations["LOC-BRIDGE-GATE-B"],
                timestamp=_event_at(tug_09, ScheduleEvent.EventType.BRIDGE_CROSS)
                + timedelta(minutes=35),
                speed_knots="0.40",
                heading_degrees="090.00",
            ),
        ],
        "TRACK-STALE-SIGNAL": [
            _payload(
                replay_run=replay_run,
                source_id="SYN-GPS-PHASE3",
                source_type=TelemetrySource.SourceType.SYNTHETIC_GPS,
                external_id="SYN-BRG-NUS-17",
                asset_type=AssetIdentity.AssetType.BARGE,
                asset_code="BRG-NUS-17",
                location=locations["LOC-BRIDGE-GATE-B"],
                timestamp=_event_at(barge_nus, ScheduleEvent.EventType.BRIDGE_CROSS)
                - timedelta(minutes=3),
                speed_knots="4.20",
                heading_degrees="090.00",
            ),
        ],
        "TRACK-OGV-ETA-SHIFT": _ogv_eta_shift_payloads(
            replay_run=replay_run,
            locations=locations,
        ),
        "TRACK-CTS-APPROACH": [
            _payload(
                replay_run=replay_run,
                source_id="SYN-GPS-PHASE3",
                source_type=TelemetrySource.SourceType.SYNTHETIC_GPS,
                external_id="SYN-BRG-KAL-22",
                asset_type=AssetIdentity.AssetType.BARGE,
                asset_code="BRG-KAL-22",
                location=locations["LOC-RANTAU-DELTA"],
                timestamp=_event_at(barge_kal, ScheduleEvent.EventType.TIDE_GATE)
                - timedelta(minutes=4),
                speed_knots="5.10",
                heading_degrees="105.00",
            ),
            _payload(
                replay_run=replay_run,
                source_id="SYN-GPS-PHASE3",
                source_type=TelemetrySource.SourceType.SYNTHETIC_GPS,
                external_id="SYN-BRG-KAL-22",
                asset_type=AssetIdentity.AssetType.BARGE,
                asset_code="BRG-KAL-22",
                location=locations[_cts_location_code(barge_kal)],
                timestamp=_event_at(barge_kal, ScheduleEvent.EventType.ARRIVE_CTS)
                + timedelta(minutes=5),
                speed_knots="3.20",
                heading_degrees="110.00",
            ),
        ],
    }
    return payloads_by_family[replay_run.scenario_code]


def _ogv_eta_shift_payloads(*, replay_run: TelemetryReplayRun, locations: dict[str, Location]) -> list[dict]:
    voyage = OGVVoyage.objects.order_by("priority", "laycan_start").first()
    if not voyage:
        return []
    eta_shift = voyage.eta + timedelta(minutes=40)
    return [
        _payload(
            replay_run=replay_run,
            source_id="SYN-AIS-PHASE3",
            source_type=TelemetrySource.SourceType.SYNTHETIC_AIS,
            external_id=f"AIS-{voyage.voyage_id}",
            asset_type=AssetIdentity.AssetType.OGV,
            asset_code=voyage.voyage_id,
            location=voyage.anchorage_location or locations["LOC-MUARA-PANTAI"],
            timestamp=voyage.eta - timedelta(minutes=30),
            speed_knots="7.20",
            heading_degrees="080.00",
            extra_raw_payload={"observedEta": eta_shift.isoformat()},
        ),
        _payload(
            replay_run=replay_run,
            source_id="SYN-AIS-PHASE3",
            source_type=TelemetrySource.SourceType.SYNTHETIC_AIS,
            external_id=f"AIS-{voyage.voyage_id}",
            asset_type=AssetIdentity.AssetType.OGV,
            asset_code=voyage.voyage_id,
            location=locations["LOC-MUARA-PANTAI"],
            timestamp=voyage.eta + timedelta(minutes=5),
            speed_knots="6.70",
            heading_degrees="080.00",
            extra_raw_payload={"observedEta": eta_shift.isoformat()},
        ),
    ]


def _payload(
    *,
    replay_run: TelemetryReplayRun,
    source_id: str,
    source_type: str,
    external_id: str,
    asset_type: str,
    asset_code: str,
    location: Location,
    timestamp,
    speed_knots: str,
    heading_degrees: str,
    extra_raw_payload: dict | None = None,
) -> dict:
    return {
        "source_id": source_id,
        "source_type": source_type,
        "external_id": external_id,
        "asset_type": asset_type,
        "asset_code": asset_code,
        "latitude": location.latitude,
        "longitude": location.longitude,
        "speed_knots": speed_knots,
        "course_degrees": heading_degrees,
        "heading_degrees": heading_degrees,
        "device_timestamp": timestamp,
        "signal_quality": PositionPing.SignalQuality.GOOD,
        "raw_payload": {
            "seed": "phase3_replay",
            "fixtureFamily": replay_run.scenario_code,
            "replayId": replay_run.replay_id,
            "locationCode": location.code,
            **(extra_raw_payload or {}),
        },
    }


def _reset_replay_evidence(*, replay_run: TelemetryReplayRun, asset_codes: list[str]) -> None:
    TrackingAlert.objects.filter(evidence__replayId=replay_run.replay_id).delete()
    LiveEtaProjection.objects.filter(metadata__replayId=replay_run.replay_id).delete()
    PositionPing.objects.filter(raw_payload__replayId=replay_run.replay_id).delete()
    LatestAssetState.objects.filter(asset_code__in=asset_codes).update(
        last_ping=None,
        current_geofence=None,
        last_movement_event=None,
        derived_status=LatestAssetState.DerivedStatus.UNKNOWN,
        latitude=None,
        longitude=None,
        speed_knots=None,
        heading_degrees=None,
        last_seen_at=None,
        freshness_status=LatestAssetState.FreshnessStatus.MISSING,
        confidence_score=0,
    )


def _active_schedule_version() -> PlanVersion | None:
    queryset = PlanVersion.objects.select_related("plan")
    return (
        queryset.filter(status=PlanVersion.Status.APPROVED).order_by("-created_at").first()
        or queryset.filter(
            status__in=[
                PlanVersion.Status.DRAFT,
                PlanVersion.Status.VALIDATED,
                PlanVersion.Status.PROPOSED,
            ]
        )
        .order_by("-created_at")
        .first()
        or queryset.order_by("-created_at").first()
    )


def _active_seed_start():
    version = _active_schedule_version()
    if version:
        return version.plan.horizon_start
    return timezone.now()


def _assignment_for(assignments: list[Assignment], **filters) -> Assignment | None:
    for assignment in assignments:
        if all(
            getattr(assignment, field.removesuffix("_code")) is not None
            and getattr(assignment, field.removesuffix("_code")).code == value
            for field, value in filters.items()
        ):
            return assignment
    return None


def _event_at(assignment: Assignment, event_type: str):
    event = next(
        (item for item in assignment.trip.events.all() if item.event_type == event_type),
        None,
    )
    if not event:
        raise RuntimeError(f"{assignment.trip.trip_id} is missing {event_type}.")
    return event.planned_at


def _jetty_location_code(assignment: Assignment) -> str:
    if not assignment.jetty:
        return "LOC-SUARAN-PORT"
    return {
        "JTY-SUARAN": "LOC-SUARAN-PORT",
        "JTY-LATI": "LOC-LATI-PORT",
        "JTY-GMB": "LOC-GURIMBANG",
    }.get(assignment.jetty.code, "LOC-SUARAN-PORT")


def _cts_location_code(assignment: Assignment) -> str:
    if not assignment.cts:
        return "LOC-CTS-ALPHA"
    return {
        "CTS-BORNEO": "LOC-CTS-ALPHA",
        "CTS-JAVA": "LOC-CTS-BRAVO",
        "FC-CHLOE": "LOC-CTS-BRAVO",
    }.get(assignment.cts.code, "LOC-CTS-ALPHA")
