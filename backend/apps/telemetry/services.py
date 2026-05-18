from decimal import Decimal
from math import asin, cos, radians, sin, sqrt
from uuid import uuid4

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.scheduling.models import Assignment, PlanVersion, ScenarioAssumption, ScheduleEvent
from apps.scheduling.services import (
    create_scenario_assumption,
    create_scenario_from_tracking_alert,
)

from .models import (
    AssetIdentity,
    GeofenceZone,
    LatestAssetState,
    LiveEtaProjection,
    MovementEvent,
    PositionPing,
    TelemetrySource,
    TrackingAlert,
)

SYNTHETIC_SOURCE_TYPES = {
    TelemetrySource.SourceType.SYNTHETIC_GPS,
    TelemetrySource.SourceType.SYNTHETIC_AIS,
}


def ingest_position_ping(*, payload: dict) -> dict:
    normalized = _normalize_payload(payload)
    with transaction.atomic():
        source = _resolve_source(normalized)
        asset_identity = _resolve_asset_identity(source=source, payload=normalized)
        ping = PositionPing.objects.create(
            ping_id=_next_ping_id(source_id=source.source_id),
            source=source,
            asset_identity=asset_identity,
            asset_type=asset_identity.asset_type,
            asset_code=asset_identity.asset_code,
            latitude=normalized["latitude"],
            longitude=normalized["longitude"],
            speed_knots=normalized.get("speed_knots"),
            course_degrees=normalized.get("course_degrees"),
            heading_degrees=normalized.get("heading_degrees"),
            device_timestamp=normalized["device_timestamp"],
            received_timestamp=timezone.now(),
            signal_quality=normalized.get("signal_quality", PositionPing.SignalQuality.GOOD),
            accuracy_m=normalized.get("accuracy_m"),
            battery_level=normalized.get("battery_level"),
            raw_payload=normalized.get("raw_payload", {}),
            raw_payload_ref=normalized.get("raw_payload_ref", ""),
            is_synthetic=source.source_type in SYNTHETIC_SOURCE_TYPES,
        )
        latest_state_updated, movement_events, alerts = _update_latest_asset_state(ping=ping)
    return {
        "ping": ping,
        "latest_state_updated": latest_state_updated,
        "geofence_events": movement_events,
        "alerts": alerts,
    }


def ensure_missing_latest_state(*, asset_identity: AssetIdentity) -> LatestAssetState:
    state, _ = LatestAssetState.objects.get_or_create(
        asset_type=asset_identity.asset_type,
        asset_code=asset_identity.asset_code,
        defaults={
            "source": asset_identity.source,
            "asset_identity": asset_identity,
            "freshness_status": LatestAssetState.FreshnessStatus.MISSING,
            "derived_status": LatestAssetState.DerivedStatus.UNKNOWN,
            "confidence_score": Decimal("0"),
            "metadata": {"createdFromIdentitySeed": True},
        },
    )
    return state


def convert_tracking_alert_to_scenario(*, alert: TrackingAlert, actor):
    if alert.alert_type != TrackingAlert.AlertType.DELAY:
        raise ValidationError("Only delay tracking alerts can be converted to scenarios.")
    if alert.trip_id is None:
        raise ValidationError("Tracking alert must be linked to a trip before scenario conversion.")
    if alert.status not in {
        TrackingAlert.Status.OPEN,
        TrackingAlert.Status.ACKNOWLEDGED,
        TrackingAlert.Status.CONVERTED_TO_SCENARIO,
    }:
        raise ValidationError("Only active delay alerts can be converted to scenarios.")

    variance_minutes = alert.evidence.get("varianceMinutes")
    try:
        delay_minutes = max(0, int(variance_minutes or 0))
    except (TypeError, ValueError):
        delay_minutes = 0
    if delay_minutes <= 0:
        raise ValidationError("Delay alerts require positive ETA variance for scenario conversion.")

    with transaction.atomic():
        locked_alert = TrackingAlert.objects.select_for_update().get(pk=alert.pk)
        if locked_alert.created_scenario_id:
            return locked_alert.created_scenario

        scenario = create_scenario_from_tracking_alert(
            baseline_version=locked_alert.trip.plan_version,
            source_alert=locked_alert,
            actor=actor,
        )
        create_scenario_assumption(
            scenario=scenario,
            actor=actor,
            kind=ScenarioAssumption.Kind.TRIP_DELAY,
            scope_type=ScenarioAssumption.ScopeType.TRIP,
            scope_id=locked_alert.trip_id,
            payload={
                "delay_minutes": delay_minutes,
                "source_tracking_alert_id": locked_alert.pk,
                "source_tracking_alert_ref": locked_alert.alert_id,
            },
            effective_from=(
                locked_alert.schedule_event.planned_at
                if locked_alert.schedule_event_id
                else None
            ),
        )
        locked_alert.created_scenario = scenario
        locked_alert.status = TrackingAlert.Status.CONVERTED_TO_SCENARIO
        locked_alert.save(update_fields=["created_scenario", "status", "updated_at"])
        return scenario


def refresh_signal_health(*, now=None) -> int:
    now = now or timezone.now()
    updated = 0
    for state in LatestAssetState.objects.select_related(
        "source",
        "asset_identity",
        "last_ping",
    ).all():
        freshness_status = _freshness_status(
            source=state.source,
            last_seen_at=state.last_seen_at,
            now=now,
            signal_quality=state.last_ping.signal_quality if state.last_ping else None,
        )
        confidence_score = _confidence_score(
            freshness_status=freshness_status,
            signal_quality=state.last_ping.signal_quality if state.last_ping else None,
        )
        if (
            state.freshness_status != freshness_status
            or state.confidence_score != confidence_score
        ):
            previous_status = state.freshness_status
            state.freshness_status = freshness_status
            state.confidence_score = confidence_score
            state.save(update_fields=["freshness_status", "confidence_score", "updated_at"])
            if freshness_status == LatestAssetState.FreshnessStatus.STALE:
                _sync_stale_signal_alert(state=state, now=now)
            elif previous_status == LatestAssetState.FreshnessStatus.STALE:
                _resolve_tracking_alerts(
                    asset_code=state.asset_code,
                    alert_type=TrackingAlert.AlertType.STALE_SIGNAL,
                    now=now,
                )
            updated += 1
    return updated


def _normalize_payload(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValidationError("Telemetry payload must be an object.")

    required = [
        "source_id",
        "source_type",
        "external_id",
        "asset_type",
        "asset_code",
        "latitude",
        "longitude",
        "device_timestamp",
    ]
    missing = [field for field in required if payload.get(field) in {None, ""}]
    if missing:
        raise ValidationError({field: "This field is required." for field in missing})

    latitude = _decimal_in_range(payload["latitude"], "latitude", Decimal("-90"), Decimal("90"))
    longitude = _decimal_in_range(
        payload["longitude"],
        "longitude",
        Decimal("-180"),
        Decimal("180"),
    )
    speed_knots = _optional_decimal(payload.get("speed_knots"), "speed_knots")
    if speed_knots is not None and speed_knots < 0:
        raise ValidationError({"speed_knots": "Speed cannot be negative."})

    course_degrees = _optional_decimal(payload.get("course_degrees"), "course_degrees")
    heading_degrees = _optional_decimal(payload.get("heading_degrees"), "heading_degrees")
    for field, value in {
        "course_degrees": course_degrees,
        "heading_degrees": heading_degrees,
    }.items():
        if value is not None and (value < 0 or value >= 360):
            raise ValidationError({field: "Degrees must be >= 0 and < 360."})

    device_timestamp = payload["device_timestamp"]
    if timezone.is_naive(device_timestamp):
        device_timestamp = timezone.make_aware(device_timestamp)

    battery_level = payload.get("battery_level")
    if battery_level is not None and not 0 <= int(battery_level) <= 100:
        raise ValidationError({"battery_level": "Battery level must be between 0 and 100."})

    return {
        **payload,
        "source_id": str(payload["source_id"]).strip(),
        "source_type": str(payload["source_type"]).strip(),
        "external_id": str(payload["external_id"]).strip(),
        "asset_type": str(payload["asset_type"]).strip(),
        "asset_code": str(payload["asset_code"]).strip(),
        "external_id_type": str(
            payload.get("external_id_type") or AssetIdentity.ExternalIdType.SYNTHETIC_ID
        ).strip(),
        "latitude": latitude,
        "longitude": longitude,
        "speed_knots": speed_knots,
        "course_degrees": course_degrees,
        "heading_degrees": heading_degrees,
        "device_timestamp": device_timestamp,
        "battery_level": battery_level,
        "signal_quality": payload.get("signal_quality") or PositionPing.SignalQuality.GOOD,
        "raw_payload": payload.get("raw_payload") or {},
        "raw_payload_ref": str(payload.get("raw_payload_ref") or "").strip(),
    }


def _resolve_source(payload: dict) -> TelemetrySource:
    source_type = payload["source_type"]
    if source_type not in dict(TelemetrySource.SourceType.choices):
        raise ValidationError({"source_type": "Unsupported telemetry source type."})

    source, created = TelemetrySource.objects.get_or_create(
        source_id=payload["source_id"],
        defaults={
            "name": payload.get("source_name") or payload["source_id"],
            "source_type": source_type,
            "status": TelemetrySource.Status.ACTIVE,
            "metadata": {"createdFromIngest": True},
        },
    )
    if not created and source.source_type != source_type:
        raise ValidationError(
            {"source_type": f"{source.source_id} is registered as {source.source_type}."}
        )
    return source


def _resolve_asset_identity(*, source: TelemetrySource, payload: dict) -> AssetIdentity:
    if payload["asset_type"] not in dict(AssetIdentity.AssetType.choices):
        raise ValidationError({"asset_type": "Unsupported tracked asset type."})
    if payload["external_id_type"] not in dict(AssetIdentity.ExternalIdType.choices):
        raise ValidationError({"external_id_type": "Unsupported external ID type."})

    identity, created = AssetIdentity.objects.get_or_create(
        source=source,
        external_id=payload["external_id"],
        defaults={
            "asset_type": payload["asset_type"],
            "asset_code": payload["asset_code"],
            "asset_object_id": payload.get("asset_object_id"),
            "external_id_type": payload["external_id_type"],
            "is_primary": True,
            "metadata": {"createdFromIngest": True},
        },
    )
    if created:
        return identity

    changed_fields = []
    for field in ["asset_type", "asset_code", "external_id_type"]:
        incoming_value = payload[field]
        if getattr(identity, field) != incoming_value:
            setattr(identity, field, incoming_value)
            changed_fields.append(field)
    incoming_object_id = payload.get("asset_object_id")
    if incoming_object_id and identity.asset_object_id != incoming_object_id:
        identity.asset_object_id = incoming_object_id
        changed_fields.append("asset_object_id")
    if changed_fields:
        changed_fields.append("updated_at")
        identity.save(update_fields=changed_fields)
    return identity


def _update_latest_asset_state(
    *,
    ping: PositionPing,
) -> tuple[bool, list[MovementEvent], list[TrackingAlert]]:
    state = LatestAssetState.objects.filter(
        asset_type=ping.asset_type,
        asset_code=ping.asset_code,
    ).select_related("current_geofence").first()
    if state and state.last_seen_at and ping.device_timestamp < state.last_seen_at:
        return False, [], []

    freshness_status = _freshness_status(
        source=ping.source,
        last_seen_at=ping.device_timestamp,
        now=timezone.now(),
        signal_quality=ping.signal_quality,
    )
    derived_status = _derived_status(
        freshness_status=freshness_status,
        speed_knots=ping.speed_knots,
    )
    confidence_score = _confidence_score(
        freshness_status=freshness_status,
        signal_quality=ping.signal_quality,
    )
    previous_geofence = state.current_geofence if state else None
    current_geofence = _nearest_geofence_for_ping(ping=ping)
    movement_events = _derive_movement_events(
        ping=ping,
        previous_geofence=previous_geofence,
        current_geofence=current_geofence,
        confidence_score=confidence_score,
    )
    last_movement_event = movement_events[-1] if movement_events else (
        state.last_movement_event if state else None
    )
    latest_state, _ = LatestAssetState.objects.update_or_create(
        asset_type=ping.asset_type,
        asset_code=ping.asset_code,
        defaults={
            "source": ping.source,
            "asset_identity": ping.asset_identity,
            "last_ping": ping,
            "derived_status": derived_status,
            "latitude": ping.latitude,
            "longitude": ping.longitude,
            "speed_knots": ping.speed_knots,
            "heading_degrees": ping.heading_degrees,
            "last_seen_at": ping.device_timestamp,
            "current_geofence": current_geofence,
            "last_movement_event": last_movement_event,
            "freshness_status": freshness_status,
            "confidence_score": confidence_score,
            "metadata": {
                "lastPingId": ping.ping_id,
                "sourceType": ping.source.source_type,
                "signalQuality": ping.signal_quality,
                "isSynthetic": ping.is_synthetic,
                "currentGeofence": current_geofence.zone_id if current_geofence else None,
            },
        },
    )
    alerts = _evaluate_eta_projection_and_alerts(latest_state=latest_state, ping=ping)
    return True, movement_events, alerts


def _evaluate_eta_projection_and_alerts(
    *,
    latest_state: LatestAssetState,
    ping: PositionPing,
) -> list[TrackingAlert]:
    assignment = _assignment_for_asset(asset_code=ping.asset_code)
    if not assignment:
        return []

    schedule_event = _target_schedule_event(
        latest_state=latest_state,
        assignment=assignment,
        ping=ping,
    )
    if not schedule_event:
        return []

    observed_eta, method = _observed_eta_for_event(
        latest_state=latest_state,
        ping=ping,
        assignment=assignment,
        schedule_event=schedule_event,
    )
    variance_minutes = None
    if observed_eta:
        variance_minutes = round(
            (observed_eta - schedule_event.planned_at).total_seconds() / 60
        )
    status = _projection_status(
        variance_minutes=variance_minutes,
        schedule_event=schedule_event,
    )
    projection = _upsert_eta_projection(
        latest_state=latest_state,
        ping=ping,
        assignment=assignment,
        schedule_event=schedule_event,
        observed_eta=observed_eta,
        variance_minutes=variance_minutes,
        method=method,
        status=status,
    )
    alerts = _sync_projection_alerts(
        latest_state=latest_state,
        ping=ping,
        assignment=assignment,
        schedule_event=schedule_event,
        projection=projection,
    )
    alerts.extend(
        _sync_location_alerts(
            latest_state=latest_state,
            ping=ping,
            assignment=assignment,
            schedule_event=schedule_event,
            projection=projection,
        )
    )
    return alerts


def _active_schedule_version() -> PlanVersion | None:
    queryset = PlanVersion.objects.select_related("plan", "created_by", "source_version")
    publish_candidate = (
        queryset.filter(status=PlanVersion.Status.APPROVED).order_by("-created_at").first()
    )
    if publish_candidate:
        return publish_candidate

    active_candidate = (
        queryset.filter(
            status__in=[
                PlanVersion.Status.DRAFT,
                PlanVersion.Status.VALIDATED,
                PlanVersion.Status.PROPOSED,
            ]
        )
        .order_by("-created_at")
        .first()
    )
    if active_candidate:
        return active_candidate

    return queryset.order_by(F("generated_at").desc(nulls_last=True), "-created_at").first()


def _assignment_for_asset(*, asset_code: str) -> Assignment | None:
    active_version = _active_schedule_version()
    if not active_version:
        return None

    return (
        Assignment.objects.filter(trip__plan_version=active_version)
        .filter(
            Q(tug__code=asset_code)
            | Q(barge__code=asset_code)
            | Q(cts__code=asset_code)
        )
        .select_related(
            "trip",
            "trip__voyage",
            "tug",
            "barge",
            "jetty",
            "cts",
            "route_segment",
        )
        .order_by("trip__sequence")
        .first()
    )


def _target_schedule_event(
    *,
    latest_state: LatestAssetState,
    assignment: Assignment,
    ping: PositionPing,
) -> ScheduleEvent | None:
    zone_type = latest_state.current_geofence.zone_type if latest_state.current_geofence else ""
    event_type = None
    if zone_type == GeofenceZone.ZoneType.JETTY:
        event_type = ScheduleEvent.EventType.DEPART_JETTY
    elif zone_type == GeofenceZone.ZoneType.BRIDGE:
        event_type = ScheduleEvent.EventType.BRIDGE_CROSS
    elif zone_type == GeofenceZone.ZoneType.TIDE_GATE:
        event_type = ScheduleEvent.EventType.TIDE_GATE
    elif zone_type == GeofenceZone.ZoneType.CTS_ZONE:
        event_type = ScheduleEvent.EventType.ARRIVE_CTS

    events = ScheduleEvent.objects.filter(trip=assignment.trip).order_by("sequence")
    if event_type:
        target = events.filter(event_type=event_type).first()
        if target:
            return target

    return (
        events.filter(planned_at__gte=ping.device_timestamp)
        .order_by("planned_at", "sequence")
        .first()
        or events.order_by("-planned_at", "-sequence").first()
    )


def _observed_eta_for_event(
    *,
    latest_state: LatestAssetState,
    ping: PositionPing,
    assignment: Assignment,
    schedule_event: ScheduleEvent,
) -> tuple[object | None, str]:
    raw_eta = ping.raw_payload.get("observed_eta") or ping.raw_payload.get("observedEta")
    if raw_eta:
        parsed = parse_datetime(str(raw_eta))
        if parsed:
            if timezone.is_naive(parsed):
                parsed = timezone.make_aware(parsed)
            return parsed, LiveEtaProjection.CalculationMethod.SYNTHETIC_SCRIPT

    target_zone = _zone_for_schedule_event(assignment=assignment, schedule_event=schedule_event)
    if target_zone and latest_state.current_geofence_id == target_zone.id:
        return ping.device_timestamp, LiveEtaProjection.CalculationMethod.GEOFENCE_SEQUENCE

    speed_knots = Decimal(ping.speed_knots or 0)
    if not target_zone or speed_knots < Decimal("0.50"):
        return None, LiveEtaProjection.CalculationMethod.SIMPLE_SPEED

    distance_m = _distance_m(
        latitude_a=ping.latitude,
        longitude_a=ping.longitude,
        latitude_b=target_zone.latitude,
        longitude_b=target_zone.longitude,
    )
    meters_per_second = float(speed_knots) * 1852 / 3600
    if meters_per_second <= 0:
        return None, LiveEtaProjection.CalculationMethod.SIMPLE_SPEED
    travel_seconds = max(60, min(int(distance_m / meters_per_second), 72 * 3600))
    return (
        ping.device_timestamp + timezone.timedelta(seconds=travel_seconds),
        LiveEtaProjection.CalculationMethod.SIMPLE_SPEED,
    )


def _zone_for_schedule_event(
    *,
    assignment: Assignment,
    schedule_event: ScheduleEvent,
) -> GeofenceZone | None:
    if schedule_event.event_type in {
        ScheduleEvent.EventType.LOAD_START,
        ScheduleEvent.EventType.LOAD_COMPLETE,
        ScheduleEvent.EventType.DEPART_JETTY,
    }:
        return _zone_for_jetty(assignment.jetty.code if assignment.jetty else "")
    if schedule_event.event_type == ScheduleEvent.EventType.BRIDGE_CROSS:
        return GeofenceZone.objects.filter(
            status=GeofenceZone.Status.ACTIVE,
            zone_type=GeofenceZone.ZoneType.BRIDGE,
        ).order_by("zone_id").first()
    if schedule_event.event_type == ScheduleEvent.EventType.TIDE_GATE:
        return GeofenceZone.objects.filter(
            status=GeofenceZone.Status.ACTIVE,
            zone_type=GeofenceZone.ZoneType.TIDE_GATE,
        ).order_by("zone_id").first()
    if schedule_event.event_type in {
        ScheduleEvent.EventType.ARRIVE_CTS,
        ScheduleEvent.EventType.DISCHARGE_START,
        ScheduleEvent.EventType.DISCHARGE_COMPLETE,
    }:
        return _zone_for_cts(assignment.cts.code if assignment.cts else "")
    return None


def _zone_for_jetty(jetty_code: str) -> GeofenceZone | None:
    token_map = {
        "JTY-SUARAN": "LOC-SUARAN-PORT",
        "JTY-LATI": "LOC-LATI-PORT",
        "JTY-GMB": "LOC-GURIMBANG",
    }
    location_code = token_map.get(jetty_code)
    if location_code:
        zone = GeofenceZone.objects.filter(
            status=GeofenceZone.Status.ACTIVE,
            source_location__code=location_code,
        ).first()
        if zone:
            return zone
    token = jetty_code.replace("JTY-", "").lower()
    return GeofenceZone.objects.filter(
        status=GeofenceZone.Status.ACTIVE,
        zone_type=GeofenceZone.ZoneType.JETTY,
        source_location__code__icontains=token,
    ).first()


def _zone_for_cts(cts_code: str) -> GeofenceZone | None:
    token_map = {
        "CTS-BORNEO": "LOC-CTS-ALPHA",
        "CTS-JAVA": "LOC-CTS-BRAVO",
        "FC-CHLOE": "LOC-CTS-BRAVO",
    }
    location_code = token_map.get(cts_code)
    if location_code:
        zone = GeofenceZone.objects.filter(
            status=GeofenceZone.Status.ACTIVE,
            source_location__code=location_code,
        ).first()
        if zone:
            return zone
    return GeofenceZone.objects.filter(
        status=GeofenceZone.Status.ACTIVE,
        zone_type=GeofenceZone.ZoneType.CTS_ZONE,
    ).order_by("zone_id").first()


def _projection_status(
    *,
    variance_minutes: int | None,
    schedule_event: ScheduleEvent,
) -> str:
    if variance_minutes is None:
        return LiveEtaProjection.Status.UNKNOWN
    if variance_minutes <= 10:
        return LiveEtaProjection.Status.ON_TIME
    if schedule_event.event_type in {
        ScheduleEvent.EventType.BRIDGE_CROSS,
        ScheduleEvent.EventType.TIDE_GATE,
    }:
        return (
            LiveEtaProjection.Status.DELAYED
            if variance_minutes > 20
            else LiveEtaProjection.Status.WATCH
        )
    return (
        LiveEtaProjection.Status.DELAYED
        if variance_minutes > 30
        else LiveEtaProjection.Status.WATCH
    )


def _upsert_eta_projection(
    *,
    latest_state: LatestAssetState,
    ping: PositionPing,
    assignment: Assignment,
    schedule_event: ScheduleEvent,
    observed_eta,
    variance_minutes: int | None,
    method: str,
    status: str,
) -> LiveEtaProjection:
    now = timezone.now()
    projection, _ = LiveEtaProjection.objects.get_or_create(
        asset_code=ping.asset_code,
        trip=assignment.trip,
        schedule_event=schedule_event,
        defaults={
            "projection_id": _next_eta_projection_id(),
            "asset_type": ping.asset_type,
            "source": ping.source,
            "asset_identity": ping.asset_identity,
            "planned_at": schedule_event.planned_at,
            "observed_eta": observed_eta,
            "variance_minutes": variance_minutes,
            "calculation_method": method,
            "confidence_score": latest_state.confidence_score,
            "source_ping": ping,
            "current_geofence": latest_state.current_geofence,
            "status": status,
            "metadata": {},
            "calculated_at": now,
        },
    )
    projection.asset_type = ping.asset_type
    projection.source = ping.source
    projection.asset_identity = ping.asset_identity
    projection.planned_at = schedule_event.planned_at
    projection.observed_eta = observed_eta
    projection.variance_minutes = variance_minutes
    projection.calculation_method = method
    projection.confidence_score = latest_state.confidence_score
    projection.source_ping = ping
    projection.current_geofence = latest_state.current_geofence
    projection.status = status
    projection.metadata = {
        "sourcePingId": ping.ping_id,
        "currentGeofence": (
            latest_state.current_geofence.zone_id
            if latest_state.current_geofence
            else None
        ),
        "scheduleEventType": schedule_event.event_type,
        "seed": ping.raw_payload.get("seed"),
        "replayId": ping.raw_payload.get("replayId"),
    }
    projection.calculated_at = now
    projection.save(
        update_fields=[
            "asset_type",
            "source",
            "asset_identity",
            "planned_at",
            "observed_eta",
            "variance_minutes",
            "calculation_method",
            "confidence_score",
            "source_ping",
            "current_geofence",
            "status",
            "metadata",
            "calculated_at",
            "updated_at",
        ]
    )
    return projection


def _sync_projection_alerts(
    *,
    latest_state: LatestAssetState,
    ping: PositionPing,
    assignment: Assignment,
    schedule_event: ScheduleEvent,
    projection: LiveEtaProjection,
) -> list[TrackingAlert]:
    variance = projection.variance_minutes
    alerts = []
    is_departure_delay = (
        schedule_event.event_type == ScheduleEvent.EventType.DEPART_JETTY
        and variance is not None
        and variance > 15
    )
    is_eta_risk = (
        schedule_event.event_type in {
            ScheduleEvent.EventType.BRIDGE_CROSS,
            ScheduleEvent.EventType.TIDE_GATE,
            ScheduleEvent.EventType.ARRIVE_CTS,
        }
        and projection.status in {
            LiveEtaProjection.Status.WATCH,
            LiveEtaProjection.Status.DELAYED,
        }
    )

    if is_departure_delay:
        severity = (
            TrackingAlert.Severity.CRITICAL
            if variance is not None and variance >= 60
            else TrackingAlert.Severity.WARNING
        )
        alerts.append(
            _upsert_tracking_alert(
                alert_type=TrackingAlert.AlertType.DELAY,
                severity=severity,
                latest_state=latest_state,
                ping=ping,
                assignment=assignment,
                schedule_event=schedule_event,
                projection=projection,
                message=(
                    f"{ping.asset_code} is still at jetty with observed departure "
                    f"{variance} minutes after plan."
                ),
            )
        )
    else:
        _resolve_tracking_alerts(
            asset_code=ping.asset_code,
            alert_type=TrackingAlert.AlertType.DELAY,
            trip=assignment.trip,
            schedule_event=schedule_event,
        )

    if is_eta_risk:
        severity = (
            TrackingAlert.Severity.CRITICAL
            if variance is not None and variance >= 45
            else TrackingAlert.Severity.WARNING
        )
        alerts.append(
            _upsert_tracking_alert(
                alert_type=TrackingAlert.AlertType.ETA_RISK,
                severity=severity,
                latest_state=latest_state,
                ping=ping,
                assignment=assignment,
                schedule_event=schedule_event,
                projection=projection,
                message=(
                    f"{ping.asset_code} observed ETA is {variance} minutes off "
                    f"{schedule_event.event_type.replace('_', ' ')}."
                ),
            )
        )
    else:
        _resolve_tracking_alerts(
            asset_code=ping.asset_code,
            alert_type=TrackingAlert.AlertType.ETA_RISK,
            trip=assignment.trip,
            schedule_event=schedule_event,
        )

    return alerts


def _sync_location_alerts(
    *,
    latest_state: LatestAssetState,
    ping: PositionPing,
    assignment: Assignment,
    schedule_event: ScheduleEvent,
    projection: LiveEtaProjection,
) -> list[TrackingAlert]:
    alerts = []
    current_zone = latest_state.current_geofence
    if current_zone and current_zone.zone_type == GeofenceZone.ZoneType.MAINTENANCE:
        alerts.append(
            _upsert_tracking_alert(
                alert_type=TrackingAlert.AlertType.ROUTE_DEVIATION,
                severity=TrackingAlert.Severity.WARNING,
                latest_state=latest_state,
                ping=ping,
                assignment=assignment,
                schedule_event=schedule_event,
                projection=projection,
                message=f"{ping.asset_code} entered maintenance geofence while assigned.",
            )
        )
    else:
        _resolve_tracking_alerts(
            asset_code=ping.asset_code,
            alert_type=TrackingAlert.AlertType.ROUTE_DEVIATION,
            trip=assignment.trip,
        )

    dwell_minutes = _dwell_minutes(latest_state=latest_state, ping=ping)
    if current_zone and dwell_minutes is not None and dwell_minutes >= 30:
        alerts.append(
            _upsert_tracking_alert(
                alert_type=TrackingAlert.AlertType.GEOFENCE_DWELL,
                severity=TrackingAlert.Severity.WARNING,
                latest_state=latest_state,
                ping=ping,
                assignment=assignment,
                schedule_event=schedule_event,
                projection=projection,
                message=(
                    f"{ping.asset_code} has dwelled in {current_zone.name} "
                    f"for {dwell_minutes} minutes."
                ),
            )
        )
    else:
        _resolve_tracking_alerts(
            asset_code=ping.asset_code,
            alert_type=TrackingAlert.AlertType.GEOFENCE_DWELL,
            trip=assignment.trip,
        )
    return alerts


def _dwell_minutes(*, latest_state: LatestAssetState, ping: PositionPing) -> int | None:
    if not latest_state.current_geofence:
        return None
    if latest_state.current_geofence.zone_type == GeofenceZone.ZoneType.JETTY:
        assignment = _assignment_for_asset(asset_code=ping.asset_code)
        event = ScheduleEvent.objects.filter(
            trip=assignment.trip if assignment else None,
            event_type=ScheduleEvent.EventType.DEPART_JETTY,
        ).first()
        if event and ping.device_timestamp > event.planned_at:
            return round((ping.device_timestamp - event.planned_at).total_seconds() / 60)
    event_at = (
        latest_state.last_movement_event.event_at
        if latest_state.last_movement_event
        else None
    )
    if not event_at:
        return None
    return round((ping.device_timestamp - event_at).total_seconds() / 60)


def _sync_stale_signal_alert(*, state: LatestAssetState, now) -> TrackingAlert | None:
    assignment = _assignment_for_asset(asset_code=state.asset_code)
    if not assignment:
        return None
    schedule_event = (
        ScheduleEvent.objects.filter(
            trip=assignment.trip,
            planned_at__gte=state.last_seen_at or now,
        )
        .order_by("planned_at")
        .first()
        or ScheduleEvent.objects.filter(trip=assignment.trip).order_by("-planned_at").first()
    )
    if not schedule_event:
        return None
    return _upsert_tracking_alert(
        alert_type=TrackingAlert.AlertType.STALE_SIGNAL,
        severity=TrackingAlert.Severity.WARNING,
        latest_state=state,
        ping=state.last_ping,
        assignment=assignment,
        schedule_event=schedule_event,
        projection=None,
        message=f"{state.asset_code} telemetry signal is stale against the active trip.",
        now=now,
    )


def _upsert_tracking_alert(
    *,
    alert_type: str,
    severity: str,
    latest_state: LatestAssetState,
    ping: PositionPing | None,
    assignment: Assignment,
    schedule_event: ScheduleEvent,
    projection: LiveEtaProjection | None,
    message: str,
    now=None,
) -> TrackingAlert:
    now = now or timezone.now()
    evidence = {
        "sourcePingId": ping.ping_id if ping else None,
        "scheduleEventId": schedule_event.id,
        "scheduleEventType": schedule_event.event_type,
        "plannedAt": schedule_event.planned_at.isoformat(),
        "observedEta": (
            projection.observed_eta.isoformat()
            if projection and projection.observed_eta
            else None
        ),
        "varianceMinutes": projection.variance_minutes if projection else None,
        "currentGeofence": (
            latest_state.current_geofence.zone_id if latest_state.current_geofence else None
        ),
        "currentGeofenceName": (
            latest_state.current_geofence.name if latest_state.current_geofence else None
        ),
        "seed": ping.raw_payload.get("seed") if ping else None,
        "replayId": ping.raw_payload.get("replayId") if ping else None,
    }
    existing = TrackingAlert.objects.filter(
        asset_code=latest_state.asset_code,
        alert_type=alert_type,
        trip=assignment.trip,
        schedule_event=schedule_event,
        status__in=[TrackingAlert.Status.OPEN, TrackingAlert.Status.ACKNOWLEDGED],
    ).first()
    defaults = {
        "severity": severity,
        "asset_type": latest_state.asset_type,
        "source": latest_state.source,
        "asset_identity": latest_state.asset_identity,
        "source_ping": ping,
        "eta_projection": projection,
        "message": message,
        "evidence": evidence,
        "source_kind": _source_kind_for_ping(ping=ping),
        "opened_at": existing.opened_at if existing else now,
        "resolved_at": None,
    }
    if existing:
        for field, value in defaults.items():
            setattr(existing, field, value)
        existing.status = TrackingAlert.Status.OPEN
        existing.save(
            update_fields=[
                "severity",
                "asset_type",
                "source",
                "asset_identity",
                "source_ping",
                "eta_projection",
                "message",
                "evidence",
                "source_kind",
                "status",
                "opened_at",
                "resolved_at",
                "updated_at",
            ]
        )
        return existing

    return TrackingAlert.objects.create(
        alert_id=_next_tracking_alert_id(alert_type=alert_type),
        alert_type=alert_type,
        asset_code=latest_state.asset_code,
        trip=assignment.trip,
        schedule_event=schedule_event,
        status=TrackingAlert.Status.OPEN,
        **defaults,
    )


def _resolve_tracking_alerts(
    *,
    asset_code: str,
    alert_type: str,
    trip=None,
    schedule_event=None,
    now=None,
) -> int:
    now = now or timezone.now()
    queryset = TrackingAlert.objects.filter(
        asset_code=asset_code,
        alert_type=alert_type,
        status__in=[TrackingAlert.Status.OPEN, TrackingAlert.Status.ACKNOWLEDGED],
    )
    if trip:
        queryset = queryset.filter(trip=trip)
    if schedule_event:
        queryset = queryset.filter(schedule_event=schedule_event)
    return queryset.update(status=TrackingAlert.Status.RESOLVED, resolved_at=now)


def _source_kind_for_ping(*, ping: PositionPing | None) -> str:
    if not ping:
        return TrackingAlert.SourceKind.OBSERVED
    if ping.is_synthetic:
        return TrackingAlert.SourceKind.SYNTHETIC
    if ping.source.source_type == TelemetrySource.SourceType.VENDOR_API:
        return TrackingAlert.SourceKind.VENDOR
    return TrackingAlert.SourceKind.OBSERVED


def _nearest_geofence_for_ping(*, ping: PositionPing) -> GeofenceZone | None:
    if ping.signal_quality == PositionPing.SignalQuality.INVALID:
        return None

    closest = None
    closest_distance = None
    for zone in GeofenceZone.objects.filter(status=GeofenceZone.Status.ACTIVE):
        distance_m = _distance_m(
            latitude_a=ping.latitude,
            longitude_a=ping.longitude,
            latitude_b=zone.latitude,
            longitude_b=zone.longitude,
        )
        if distance_m <= zone.radius_m and (
            closest_distance is None or distance_m < closest_distance
        ):
            closest = zone
            closest_distance = distance_m
    return closest


def _derive_movement_events(
    *,
    ping: PositionPing,
    previous_geofence: GeofenceZone | None,
    current_geofence: GeofenceZone | None,
    confidence_score: Decimal,
) -> list[MovementEvent]:
    if previous_geofence == current_geofence:
        return []

    events = []
    if previous_geofence:
        events.append(
            _create_movement_event(
                ping=ping,
                event_type=MovementEvent.EventType.EXIT_GEOFENCE,
                geofence=previous_geofence,
                confidence_score=confidence_score,
                transition_to=current_geofence,
            )
        )
    if current_geofence:
        events.append(
            _create_movement_event(
                ping=ping,
                event_type=MovementEvent.EventType.ENTER_GEOFENCE,
                geofence=current_geofence,
                confidence_score=confidence_score,
                transition_from=previous_geofence,
            )
        )
    return events


def _create_movement_event(
    *,
    ping: PositionPing,
    event_type: str,
    geofence: GeofenceZone,
    confidence_score: Decimal,
    transition_from: GeofenceZone | None = None,
    transition_to: GeofenceZone | None = None,
) -> MovementEvent:
    distance_m = _distance_m(
        latitude_a=ping.latitude,
        longitude_a=ping.longitude,
        latitude_b=geofence.latitude,
        longitude_b=geofence.longitude,
    )
    event, _ = MovementEvent.objects.get_or_create(
        position_ping=ping,
        geofence=geofence,
        event_type=event_type,
        defaults={
            "event_id": _next_movement_event_id(event_type=event_type),
            "asset_type": ping.asset_type,
            "asset_code": ping.asset_code,
            "source": ping.source,
            "asset_identity": ping.asset_identity,
            "event_at": ping.device_timestamp,
            "latitude": ping.latitude,
            "longitude": ping.longitude,
            "speed_knots": ping.speed_knots,
            "confidence_score": confidence_score,
            "metadata": {
                "distanceM": round(distance_m, 1),
                "sourcePingId": ping.ping_id,
                "transitionFrom": transition_from.zone_id if transition_from else None,
                "transitionTo": transition_to.zone_id if transition_to else None,
                "zoneType": geofence.zone_type,
            },
        },
    )
    return event


def _distance_m(*, latitude_a, longitude_a, latitude_b, longitude_b) -> float:
    earth_radius_m = 6_371_000
    lat_a = radians(float(latitude_a))
    lat_b = radians(float(latitude_b))
    delta_lat = radians(float(latitude_b) - float(latitude_a))
    delta_lon = radians(float(longitude_b) - float(longitude_a))
    haversine = sin(delta_lat / 2) ** 2 + cos(lat_a) * cos(lat_b) * sin(delta_lon / 2) ** 2
    return 2 * earth_radius_m * asin(sqrt(haversine))


def _freshness_status(
    *,
    source: TelemetrySource,
    last_seen_at,
    now,
    signal_quality: str | None,
) -> str:
    if last_seen_at is None:
        return LatestAssetState.FreshnessStatus.MISSING
    if signal_quality in {PositionPing.SignalQuality.INVALID, PositionPing.SignalQuality.STALE}:
        return LatestAssetState.FreshnessStatus.STALE
    age_seconds = max(0, int((now - last_seen_at).total_seconds()))
    threshold = source.freshness_threshold_seconds
    if age_seconds <= threshold:
        return LatestAssetState.FreshnessStatus.FRESH
    if age_seconds <= threshold * 2:
        return LatestAssetState.FreshnessStatus.AGING
    return LatestAssetState.FreshnessStatus.STALE


def _derived_status(*, freshness_status: str, speed_knots) -> str:
    if freshness_status in {
        LatestAssetState.FreshnessStatus.MISSING,
        LatestAssetState.FreshnessStatus.STALE,
    }:
        return LatestAssetState.DerivedStatus.UNKNOWN
    if speed_knots is not None and Decimal(speed_knots) >= Decimal("1.00"):
        return LatestAssetState.DerivedStatus.UNDERWAY
    return LatestAssetState.DerivedStatus.STOPPED


def _confidence_score(*, freshness_status: str, signal_quality: str | None) -> Decimal:
    if freshness_status == LatestAssetState.FreshnessStatus.MISSING:
        return Decimal("0")
    if freshness_status == LatestAssetState.FreshnessStatus.STALE:
        return Decimal("25")
    if signal_quality == PositionPing.SignalQuality.WEAK:
        return Decimal("65")
    if freshness_status == LatestAssetState.FreshnessStatus.AGING:
        return Decimal("70")
    return Decimal("96")


def _decimal_in_range(value, field: str, minimum: Decimal, maximum: Decimal) -> Decimal:
    decimal_value = _optional_decimal(value, field)
    if decimal_value is None or decimal_value < minimum or decimal_value > maximum:
        raise ValidationError({field: f"{field} must be between {minimum} and {maximum}."})
    return decimal_value


def _optional_decimal(value, field: str) -> Decimal | None:
    if value in {None, ""}:
        return None
    try:
        return Decimal(str(value))
    except Exception as exc:
        raise ValidationError({field: "Must be a valid decimal value."}) from exc


def _next_ping_id(*, source_id: str) -> str:
    return f"PNG-{source_id}-{uuid4().hex[:12].upper()}"


def _next_movement_event_id(*, event_type: str) -> str:
    prefix = "ENTER" if event_type == MovementEvent.EventType.ENTER_GEOFENCE else "EXIT"
    return f"MEV-{prefix}-{uuid4().hex[:12].upper()}"


def _next_eta_projection_id() -> str:
    return f"ETA-{uuid4().hex[:12].upper()}"


def _next_tracking_alert_id(*, alert_type: str) -> str:
    prefix = alert_type.replace("_", "-").upper()
    return f"TRK-{prefix}-{uuid4().hex[:10].upper()}"
