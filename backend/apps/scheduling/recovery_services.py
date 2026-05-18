import hashlib
import json
from decimal import Decimal

from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.masters.models import AssetCompatibilityRule
from apps.operations.models import (
    ConfirmedOperationalEvent,
    DeviceEndpoint,
    DeviceHealthSnapshot,
    IntegrationFeed,
)
from apps.planning.models import (
    AssetAvailabilityWindow,
    BridgeWindow,
    JettyAvailabilityWindow,
    NavigationConstraintCheck,
    TideWindow,
)
from apps.telemetry.models import LatestAssetState, LiveEtaProjection, TrackingAlert

from .models import (
    Assignment,
    Conflict,
    OverrideRequest,
    PlanVersion,
    RecoveryInputSnapshot,
    ScheduleEvent,
    SimulationScenario,
    Trip,
)

RECOVERY_INPUT_SNAPSHOT_ALGORITHM_VERSION = "phase5.1-input-snapshot-builder"


def active_recovery_plan_version() -> PlanVersion | None:
    publish_candidate = (
        PlanVersion.objects.select_related("plan")
        .filter(status=PlanVersion.Status.APPROVED)
        .order_by("-created_at")
        .first()
    )
    if publish_candidate:
        return publish_candidate

    active_candidate = (
        PlanVersion.objects.select_related("plan")
        .filter(
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

    return (
        PlanVersion.objects.select_related("plan")
        .order_by(F("generated_at").desc(nulls_last=True), "-created_at")
        .first()
    )


def build_recovery_input_snapshot(
    *,
    plan_version: PlanVersion | None = None,
    source_kind: str | None = None,
    source_ref: str = "",
    source_conflict: Conflict | None = None,
    source_override: OverrideRequest | None = None,
    source_tracking_alert: TrackingAlert | None = None,
    source_operational_event: ConfirmedOperationalEvent | None = None,
    source_scenario: SimulationScenario | None = None,
    actor=None,
    metadata: dict | None = None,
    snapshot_id: str | None = None,
    replace_existing: bool = False,
) -> RecoveryInputSnapshot:
    plan_version = _resolve_plan_version(
        plan_version=plan_version,
        source_conflict=source_conflict,
        source_override=source_override,
        source_tracking_alert=source_tracking_alert,
        source_operational_event=source_operational_event,
        source_scenario=source_scenario,
    )
    if plan_version is None:
        raise ValidationError("No active plan version is available for recovery input capture.")

    _validate_source_scope(
        plan_version=plan_version,
        source_conflict=source_conflict,
        source_override=source_override,
        source_tracking_alert=source_tracking_alert,
        source_operational_event=source_operational_event,
        source_scenario=source_scenario,
    )

    source_kind = source_kind or _infer_source_kind(
        source_conflict=source_conflict,
        source_override=source_override,
        source_tracking_alert=source_tracking_alert,
        source_operational_event=source_operational_event,
        source_scenario=source_scenario,
    )
    if source_kind not in RecoveryInputSnapshot.SourceKind.values:
        raise ValidationError({"source_kind": "Unsupported recovery input source kind."})

    source_ref = source_ref or _infer_source_ref(
        plan_version=plan_version,
        source_conflict=source_conflict,
        source_override=source_override,
        source_tracking_alert=source_tracking_alert,
        source_operational_event=source_operational_event,
        source_scenario=source_scenario,
    )

    input_payload = _normalized_recovery_input_payload(
        plan_version=plan_version,
        source_kind=source_kind,
        source_ref=source_ref,
        source_conflict=source_conflict,
        source_override=source_override,
        source_tracking_alert=source_tracking_alert,
        source_operational_event=source_operational_event,
        source_scenario=source_scenario,
    )
    input_hash = hashlib.sha256(
        json.dumps(input_payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()

    metadata_payload = {
        "algorithmVersion": RECOVERY_INPUT_SNAPSHOT_ALGORITHM_VERSION,
        "capturedAt": timezone.now().isoformat(),
        "source": input_payload["source"],
        "includedCounts": input_payload["counts"],
        **(metadata or {}),
    }
    defaults = {
        "plan_version": plan_version,
        "source_kind": source_kind,
        "source_ref": source_ref,
        "source_conflict": source_conflict,
        "source_override": source_override,
        "source_tracking_alert": source_tracking_alert,
        "source_operational_event": source_operational_event,
        "source_scenario": source_scenario,
        "input_hash": input_hash,
        "active_conflict_count": input_payload["counts"]["activeConflicts"],
        "confirmed_event_count": input_payload["counts"]["confirmedEvents"],
        "tracking_alert_count": input_payload["counts"]["trackingAlerts"],
        "resource_state": input_payload["resourceState"],
        "event_state": input_payload["eventState"],
        "constraint_state": input_payload["constraintState"],
        "metadata": metadata_payload,
        "captured_by": actor
        if actor is not None and getattr(actor, "is_authenticated", True)
        else None,
    }

    if snapshot_id and replace_existing:
        snapshot, _ = RecoveryInputSnapshot.objects.update_or_create(
            snapshot_id=snapshot_id,
            defaults=defaults,
        )
        return snapshot

    if snapshot_id:
        defaults["snapshot_id"] = snapshot_id
    return RecoveryInputSnapshot.objects.create(**defaults)


def _resolve_plan_version(
    *,
    plan_version: PlanVersion | None,
    source_conflict: Conflict | None,
    source_override: OverrideRequest | None,
    source_tracking_alert: TrackingAlert | None,
    source_operational_event: ConfirmedOperationalEvent | None,
    source_scenario: SimulationScenario | None,
) -> PlanVersion | None:
    if plan_version:
        return plan_version
    if source_conflict:
        return source_conflict.plan_version
    if source_override:
        return source_override.plan_version
    if source_tracking_alert and source_tracking_alert.trip_id:
        return source_tracking_alert.trip.plan_version
    if source_operational_event:
        if source_operational_event.plan_version_id:
            return source_operational_event.plan_version
        if source_operational_event.trip_id:
            return source_operational_event.trip.plan_version
    if source_scenario:
        return source_scenario.scenario_version or source_scenario.baseline_version
    return active_recovery_plan_version()


def _validate_source_scope(
    *,
    plan_version: PlanVersion,
    source_conflict: Conflict | None,
    source_override: OverrideRequest | None,
    source_tracking_alert: TrackingAlert | None,
    source_operational_event: ConfirmedOperationalEvent | None,
    source_scenario: SimulationScenario | None,
) -> None:
    scope_errors = {}
    if source_conflict and source_conflict.plan_version_id != plan_version.id:
        scope_errors["source_conflict"] = "Conflict does not belong to the snapshot plan version."
    if source_override and source_override.plan_version_id != plan_version.id:
        scope_errors["source_override"] = "Override does not belong to the snapshot plan version."
    if (
        source_tracking_alert
        and source_tracking_alert.trip_id
        and source_tracking_alert.trip.plan_version_id != plan_version.id
    ):
        scope_errors["source_tracking_alert"] = (
            "Tracking alert does not belong to the snapshot plan version."
        )
    if source_operational_event:
        operational_plan_id = (
            source_operational_event.plan_version_id
            or (
                source_operational_event.trip.plan_version_id
                if source_operational_event.trip_id
                else None
            )
        )
        if operational_plan_id and operational_plan_id != plan_version.id:
            scope_errors["source_operational_event"] = (
                "Operational event does not belong to the snapshot plan version."
            )
    if source_scenario:
        scenario_version_ids = {
            source_scenario.baseline_version_id,
            source_scenario.scenario_version_id,
        }
        if plan_version.id not in scenario_version_ids:
            scope_errors["source_scenario"] = (
                "Scenario does not belong to the snapshot plan lineage."
            )
    if scope_errors:
        raise ValidationError(scope_errors)


def _infer_source_kind(
    *,
    source_conflict: Conflict | None,
    source_override: OverrideRequest | None,
    source_tracking_alert: TrackingAlert | None,
    source_operational_event: ConfirmedOperationalEvent | None,
    source_scenario: SimulationScenario | None,
) -> str:
    if source_conflict:
        return RecoveryInputSnapshot.SourceKind.CONFLICT
    if source_override:
        return RecoveryInputSnapshot.SourceKind.OVERRIDE
    if source_tracking_alert:
        return RecoveryInputSnapshot.SourceKind.TRACKING_ALERT
    if source_operational_event:
        return RecoveryInputSnapshot.SourceKind.OPERATIONAL_EVENT
    if source_scenario:
        return RecoveryInputSnapshot.SourceKind.SCENARIO
    return RecoveryInputSnapshot.SourceKind.MANUAL


def _infer_source_ref(
    *,
    plan_version: PlanVersion,
    source_conflict: Conflict | None,
    source_override: OverrideRequest | None,
    source_tracking_alert: TrackingAlert | None,
    source_operational_event: ConfirmedOperationalEvent | None,
    source_scenario: SimulationScenario | None,
) -> str:
    if source_conflict:
        return source_conflict.code
    if source_override:
        return f"{source_override.reason_code}:{source_override.pk}"
    if source_tracking_alert:
        return source_tracking_alert.alert_id
    if source_operational_event:
        return source_operational_event.event_id
    if source_scenario:
        return source_scenario.scenario_id
    return str(plan_version)


def _normalized_recovery_input_payload(
    *,
    plan_version: PlanVersion,
    source_kind: str,
    source_ref: str,
    source_conflict: Conflict | None,
    source_override: OverrideRequest | None,
    source_tracking_alert: TrackingAlert | None,
    source_operational_event: ConfirmedOperationalEvent | None,
    source_scenario: SimulationScenario | None,
) -> dict:
    assignments = list(
        Assignment.objects.select_related(
            "trip",
            "trip__voyage",
            "tug",
            "barge",
            "jetty",
            "cts",
            "route_segment",
            "route_segment__route",
            "owner_organization",
        )
        .filter(trip__plan_version=plan_version)
        .order_by("trip__sequence", "trip__trip_id")
    )
    trips = list(
        Trip.objects.select_related(
            "voyage",
            "cargo_requirement",
            "cargo_requirement__coal_grade",
            "cargo_requirement__preferred_jetty",
            "cargo_layer_step",
            "cargo_layer_step__coal_grade",
            "origin_jetty",
            "destination_location",
        )
        .prefetch_related("events")
        .filter(plan_version=plan_version)
        .order_by("sequence", "trip_id")
    )
    trip_ids = [trip.id for trip in trips]
    route_segment_ids = sorted(
        {assignment.route_segment_id for assignment in assignments if assignment.route_segment_id}
    )
    voyage_ids = sorted({trip.voyage_id for trip in trips if trip.voyage_id})
    asset_codes = _assigned_asset_codes(assignments)

    conflicts = list(
        Conflict.objects.select_related("trip")
        .filter(plan_version=plan_version, resolved_at__isnull=True)
        .order_by("-is_blocking", "severity", "code", "id")
    )
    confirmed_events = list(
        ConfirmedOperationalEvent.objects.select_related(
            "trip",
            "assignment",
            "schedule_event",
            "confirmed_by",
        )
        .filter(Q(plan_version=plan_version) | Q(trip__plan_version=plan_version))
        .distinct()
        .order_by("actual_at", "event_id")
    )
    tracking_alerts = list(
        TrackingAlert.objects.select_related(
            "trip",
            "schedule_event",
            "eta_projection",
            "source",
        )
        .filter(
            trip__plan_version=plan_version,
            status__in=[
                TrackingAlert.Status.OPEN,
                TrackingAlert.Status.ACKNOWLEDGED,
            ],
        )
        .order_by("-opened_at", "alert_id")
    )
    eta_projections = list(
        LiveEtaProjection.objects.select_related(
            "trip",
            "schedule_event",
            "source",
            "current_geofence",
        )
        .filter(trip__plan_version=plan_version)
        .order_by("trip__sequence", "schedule_event__sequence", "asset_code")
    )

    resource_state = _resource_state(
        assignments=assignments,
        plan_version=plan_version,
        asset_codes=asset_codes,
    )
    event_state = _event_state(
        trips=trips,
        confirmed_events=confirmed_events,
        tracking_alerts=tracking_alerts,
        eta_projections=eta_projections,
    )
    constraint_state = _constraint_state(
        plan_version=plan_version,
        assignments=assignments,
        conflicts=conflicts,
        route_segment_ids=route_segment_ids,
        voyage_ids=voyage_ids,
        asset_codes=asset_codes,
    )
    return {
        "algorithmVersion": RECOVERY_INPUT_SNAPSHOT_ALGORITHM_VERSION,
        "plan": _plan_state(plan_version),
        "source": {
            "kind": source_kind,
            "ref": source_ref,
            "conflictCode": source_conflict.code if source_conflict else "",
            "overrideReasonCode": source_override.reason_code if source_override else "",
            "trackingAlertId": (
                source_tracking_alert.alert_id if source_tracking_alert else ""
            ),
            "operationalEventId": (
                source_operational_event.event_id if source_operational_event else ""
            ),
            "scenarioId": source_scenario.scenario_id if source_scenario else "",
        },
        "counts": {
            "trips": len(trips),
            "assignments": len(assignments),
            "activeConflicts": len(conflicts),
            "blockingConflicts": len([item for item in conflicts if item.is_blocking]),
            "confirmedEvents": len(confirmed_events),
            "trackingAlerts": len(tracking_alerts),
            "etaProjections": len(eta_projections),
            "healthRisks": len(resource_state["healthRisks"]),
            "tideWindows": len(constraint_state["tideWindows"]),
            "bridgeWindows": len(constraint_state["bridgeWindows"]),
        },
        "resourceState": resource_state,
        "eventState": event_state,
        "constraintState": constraint_state,
    }


def _plan_state(plan_version: PlanVersion) -> dict:
    return {
        "planId": plan_version.plan_id,
        "planCode": plan_version.plan.code,
        "planName": plan_version.plan.name,
        "organization": (
            plan_version.plan.organization.slug if plan_version.plan.organization else ""
        ),
        "versionId": plan_version.id,
        "versionNo": plan_version.version_no,
        "status": plan_version.status,
        "validationStatus": plan_version.validation_status,
        "horizonStart": _iso(plan_version.plan.horizon_start),
        "horizonEnd": _iso(plan_version.plan.horizon_end),
        "generatedAt": _iso(plan_version.generated_at),
    }


def _resource_state(
    *,
    assignments: list[Assignment],
    plan_version: PlanVersion,
    asset_codes: set[str],
) -> dict:
    latest_states = list(
        LatestAssetState.objects.select_related("source", "current_geofence")
        .filter(asset_code__in=asset_codes)
        .order_by("asset_type", "asset_code")
    )
    device_endpoints = list(
        DeviceEndpoint.objects.select_related("feed")
        .filter(Q(asset_code__in=asset_codes) | ~Q(status=DeviceEndpoint.Status.ACTIVE))
        .order_by("device_type", "device_id")
    )
    health_snapshots = _latest_device_health_snapshots(asset_codes=asset_codes)
    feed_states = list(IntegrationFeed.objects.order_by("feed_id"))
    health_snapshot_risks = [
        _device_health_state(item)
        for item in health_snapshots
        if item.health_status
        in {
            DeviceHealthSnapshot.HealthStatus.WARNING,
            DeviceHealthSnapshot.HealthStatus.CRITICAL,
            DeviceHealthSnapshot.HealthStatus.OFFLINE,
            DeviceHealthSnapshot.HealthStatus.UNKNOWN,
        }
    ]
    device_status_risks = [
        _device_endpoint_state(item)
        for item in device_endpoints
        if item.status != DeviceEndpoint.Status.ACTIVE
    ]
    feed_status_risks = [
        _feed_state(item)
        for item in feed_states
        if item.status != IntegrationFeed.Status.ACTIVE
    ]
    health_risks = [
        *health_snapshot_risks,
        *device_status_risks,
        *feed_status_risks,
    ]

    return {
        "tugs": sorted({item.tug.code for item in assignments if item.tug}),
        "barges": sorted({item.barge.code for item in assignments if item.barge}),
        "jetties": sorted({item.jetty.code for item in assignments if item.jetty}),
        "cts": sorted({item.cts.code for item in assignments if item.cts}),
        "assignments": [_assignment_state(item) for item in assignments],
        "latestAssetStates": [_latest_asset_state(item) for item in latest_states],
        "devices": [_device_endpoint_state(item) for item in device_endpoints],
        "deviceHealth": [_device_health_state(item) for item in health_snapshots],
        "healthRisks": health_risks,
        "feedHealth": [_feed_state(item) for item in feed_states],
        "summary": {
            "assignmentCount": len(assignments),
            "tugCount": len({item.tug_id for item in assignments if item.tug_id}),
            "bargeCount": len({item.barge_id for item in assignments if item.barge_id}),
            "jettyCount": len({item.jetty_id for item in assignments if item.jetty_id}),
            "ctsCount": len({item.cts_id for item in assignments if item.cts_id}),
            "healthRiskCount": len(health_risks),
            "source": "active_plan_assignments_with_phase3_phase4_state",
        },
        "planVersion": str(plan_version),
    }


def _event_state(
    *,
    trips: list[Trip],
    confirmed_events: list[ConfirmedOperationalEvent],
    tracking_alerts: list[TrackingAlert],
    eta_projections: list[LiveEtaProjection],
) -> dict:
    return {
        "trips": [_trip_state(trip) for trip in trips],
        "scheduleEvents": [
            _schedule_event_state(event)
            for trip in trips
            for event in trip.events.all()
        ],
        "confirmedEvents": [_confirmed_event_state(item) for item in confirmed_events],
        "trackingAlerts": [_tracking_alert_state(item) for item in tracking_alerts],
        "etaProjections": [_eta_projection_state(item) for item in eta_projections],
        "summary": {
            "tripCount": len(trips),
            "confirmedEventCount": len(confirmed_events),
            "trackingAlertCount": len(tracking_alerts),
            "etaProjectionCount": len(eta_projections),
            "confirmedActualsFrozen": True,
        },
    }


def _constraint_state(
    *,
    plan_version: PlanVersion,
    assignments: list[Assignment],
    conflicts: list[Conflict],
    route_segment_ids: list[int],
    voyage_ids: list[int],
    asset_codes: set[str],
) -> dict:
    horizon_start = plan_version.plan.horizon_start
    horizon_end = plan_version.plan.horizon_end
    tide_windows = list(
        TideWindow.objects.select_related("location", "applicable_route_segment")
        .filter(
            is_active=True,
            window_start__lte=horizon_end,
            window_end__gte=horizon_start,
        )
        .order_by("window_start", "code")
    )
    bridge_windows = list(
        BridgeWindow.objects.select_related("location")
        .filter(
            is_active=True,
            window_start__lte=horizon_end,
            window_end__gte=horizon_start,
        )
        .order_by("window_start", "code")
    )
    navigation_checks = list(
        NavigationConstraintCheck.objects.select_related("voyage", "route_segment")
        .filter(voyage_id__in=voyage_ids)
        .order_by("eta_gate", "asset_code", "constraint_type")
    )
    asset_windows = list(
        AssetAvailabilityWindow.objects.filter(
            asset_code__in=asset_codes,
            window_start__lte=horizon_end,
            window_end__gte=horizon_start,
        ).order_by("window_start", "asset_type", "asset_code")
    )
    jetty_ids = [item.jetty_id for item in assignments if item.jetty_id]
    jetty_windows = list(
        JettyAvailabilityWindow.objects.select_related("jetty")
        .filter(
            jetty_id__in=jetty_ids,
            window_start__lte=horizon_end,
            window_end__gte=horizon_start,
        )
        .order_by("window_start", "jetty__code")
    )
    incompatible_rules = list(
        AssetCompatibilityRule.objects.filter(
            is_active=True,
            is_compatible=False,
        ).order_by("rule_type", "left_code", "right_code")
    )

    return {
        "openConflicts": len(conflicts),
        "blockingConflicts": len([item for item in conflicts if item.is_blocking]),
        "conflicts": [_conflict_state(item) for item in conflicts],
        "tideWindows": [_tide_window_state(item) for item in tide_windows],
        "bridgeWindows": [_bridge_window_state(item) for item in bridge_windows],
        "navigationChecks": [_navigation_check_state(item) for item in navigation_checks],
        "assetAvailability": [_asset_window_state(item) for item in asset_windows],
        "jettyAvailability": [_jetty_window_state(item) for item in jetty_windows],
        "incompatibleRules": [_compatibility_rule_state(item) for item in incompatible_rules],
        "routeSegments": [_route_segment_state(item) for item in assignments],
        "hardConstraints": {
            "confirmedActualsFrozen": True,
            "tideBridgeWindowsCaptured": True,
            "resourceAvailabilityCaptured": True,
            "compatibilityRulesCaptured": True,
            "duplicateAssignmentsRequireRepair": True,
        },
    }


def _assigned_asset_codes(assignments: list[Assignment]) -> set[str]:
    codes: set[str] = set()
    for assignment in assignments:
        for resource in (assignment.tug, assignment.barge, assignment.cts, assignment.jetty):
            if resource:
                codes.add(resource.code)
    return codes


def _latest_device_health_snapshots(*, asset_codes: set[str]) -> list[DeviceHealthSnapshot]:
    query = DeviceHealthSnapshot.objects.select_related("device", "device__feed")
    if asset_codes:
        query = query.filter(
            Q(device__asset_code__in=asset_codes)
            | Q(
                health_status__in=[
                    DeviceHealthSnapshot.HealthStatus.WARNING,
                    DeviceHealthSnapshot.HealthStatus.CRITICAL,
                    DeviceHealthSnapshot.HealthStatus.OFFLINE,
                    DeviceHealthSnapshot.HealthStatus.UNKNOWN,
                ]
            )
        )
    latest_by_device = {}
    for snapshot in query.order_by("device_id", "-observed_at", "-id"):
        latest_by_device.setdefault(snapshot.device_id, snapshot)
    return sorted(
        latest_by_device.values(),
        key=lambda item: (item.device.device_id, item.observed_at),
    )


def _assignment_state(assignment: Assignment) -> dict:
    return {
        "assignmentId": assignment.id,
        "tripId": assignment.trip.trip_id,
        "sequence": assignment.trip.sequence,
        "voyageId": assignment.trip.voyage.voyage_id if assignment.trip.voyage_id else "",
        "vesselName": assignment.trip.voyage.vessel_name if assignment.trip.voyage_id else "",
        "status": assignment.status,
        "plannedDeparture": _iso(assignment.planned_departure),
        "plannedArrival": _iso(assignment.planned_arrival),
        "tug": assignment.tug.code if assignment.tug else "",
        "barge": assignment.barge.code if assignment.barge else "",
        "jetty": assignment.jetty.code if assignment.jetty else "",
        "cts": assignment.cts.code if assignment.cts else "",
        "routeSegment": str(assignment.route_segment) if assignment.route_segment else "",
        "requiresTideWindow": (
            assignment.route_segment.requires_tide_window if assignment.route_segment else False
        ),
        "requiresBridgeWindow": (
            assignment.route_segment.requires_bridge_window if assignment.route_segment else False
        ),
        "nextConstraint": assignment.next_constraint,
        "nextAction": assignment.next_action,
        "owner": (
            assignment.owner_organization.slug if assignment.owner_organization else ""
        ),
    }


def _trip_state(trip: Trip) -> dict:
    return {
        "tripId": trip.trip_id,
        "sequence": trip.sequence,
        "status": trip.status,
        "voyageId": trip.voyage.voyage_id if trip.voyage_id else "",
        "vesselName": trip.voyage.vessel_name if trip.voyage_id else "",
        "plannedStart": _iso(trip.planned_start),
        "plannedEnd": _iso(trip.planned_end),
        "plannedQuantityMt": trip.planned_quantity_mt,
        "loadedQuantityMt": trip.loaded_quantity_mt,
        "originJetty": trip.origin_jetty.code if trip.origin_jetty else "",
        "destination": trip.destination_location.code if trip.destination_location else "",
        "coalGrade": (
            trip.cargo_layer_step.coal_grade.code
            if trip.cargo_layer_step and trip.cargo_layer_step.coal_grade
            else trip.cargo_requirement.coal_grade.code
            if trip.cargo_requirement and trip.cargo_requirement.coal_grade
            else ""
        ),
        "selectionReason": trip.selection_reason,
    }


def _schedule_event_state(event: ScheduleEvent) -> dict:
    return {
        "eventId": event.id,
        "tripId": event.trip.trip_id,
        "sequence": event.sequence,
        "eventType": event.event_type,
        "plannedAt": _iso(event.planned_at),
        "actualAt": _iso(event.actual_at),
        "locationLabel": event.location_label,
        "resourceCode": event.resource_code,
        "status": event.status,
        "metadata": event.metadata,
    }


def _conflict_state(conflict: Conflict) -> dict:
    return {
        "code": conflict.code,
        "severity": conflict.severity,
        "isBlocking": conflict.is_blocking,
        "objectType": conflict.object_type,
        "objectId": conflict.object_id,
        "message": conflict.message,
        "tripId": conflict.trip.trip_id if conflict.trip_id else "",
        "createdAt": _iso(conflict.created_at),
    }


def _confirmed_event_state(event: ConfirmedOperationalEvent) -> dict:
    return {
        "eventId": event.event_id,
        "eventKind": event.event_kind,
        "tripId": event.trip.trip_id if event.trip_id else "",
        "assignmentId": event.assignment_id,
        "scheduleEventType": (
            event.schedule_event.event_type if event.schedule_event_id else ""
        ),
        "actualAt": _iso(event.actual_at),
        "confirmationMode": event.confirmation_mode,
        "confirmedQuantityMt": _decimal(event.confirmed_quantity_mt),
        "confirmedRateTph": _decimal(event.confirmed_rate_tph),
        "reasonCode": event.reason_code,
        "confirmedBy": event.confirmed_by.email if event.confirmed_by_id else "",
    }


def _tracking_alert_state(alert: TrackingAlert) -> dict:
    return {
        "alertId": alert.alert_id,
        "alertType": alert.alert_type,
        "severity": alert.severity,
        "status": alert.status,
        "assetType": alert.asset_type,
        "assetCode": alert.asset_code,
        "tripId": alert.trip.trip_id if alert.trip_id else "",
        "scheduleEventType": (
            alert.schedule_event.event_type if alert.schedule_event_id else ""
        ),
        "message": alert.message,
        "openedAt": _iso(alert.opened_at),
        "sourceKind": alert.source_kind,
        "evidence": alert.evidence,
    }


def _eta_projection_state(projection: LiveEtaProjection) -> dict:
    return {
        "projectionId": projection.projection_id,
        "assetType": projection.asset_type,
        "assetCode": projection.asset_code,
        "tripId": projection.trip.trip_id,
        "scheduleEventType": projection.schedule_event.event_type,
        "plannedAt": _iso(projection.planned_at),
        "observedEta": _iso(projection.observed_eta),
        "varianceMinutes": projection.variance_minutes,
        "status": projection.status,
        "confidenceScore": _decimal(projection.confidence_score),
        "calculationMethod": projection.calculation_method,
        "currentGeofence": (
            projection.current_geofence.zone_id if projection.current_geofence_id else ""
        ),
        "calculatedAt": _iso(projection.calculated_at),
    }


def _latest_asset_state(state: LatestAssetState) -> dict:
    return {
        "assetType": state.asset_type,
        "assetCode": state.asset_code,
        "source": state.source.source_id,
        "derivedStatus": state.derived_status,
        "freshnessStatus": state.freshness_status,
        "lastSeenAt": _iso(state.last_seen_at),
        "currentGeofence": (
            state.current_geofence.zone_id if state.current_geofence_id else ""
        ),
        "speedKnots": _decimal(state.speed_knots),
        "confidenceScore": _decimal(state.confidence_score),
        "pairedAssetCode": state.paired_asset_code,
    }


def _device_health_state(snapshot: DeviceHealthSnapshot) -> dict:
    return {
        "kind": "device_health",
        "snapshotId": snapshot.snapshot_id,
        "deviceId": snapshot.device.device_id,
        "feedId": snapshot.device.feed.feed_id,
        "deviceType": snapshot.device.device_type,
        "assetType": snapshot.device.asset_type,
        "assetCode": snapshot.device.asset_code,
        "deviceStatus": snapshot.device.status,
        "healthStatus": snapshot.health_status,
        "observedAt": _iso(snapshot.observed_at),
        "batteryLevel": snapshot.battery_level,
        "powerStatus": snapshot.power_status,
        "networkStatus": snapshot.network_status,
        "latencyMs": snapshot.latency_ms,
        "gapSeconds": snapshot.gap_seconds,
    }


def _device_endpoint_state(device: DeviceEndpoint) -> dict:
    return {
        "kind": "device_endpoint",
        "deviceId": device.device_id,
        "feedId": device.feed.feed_id,
        "deviceType": device.device_type,
        "assetType": device.asset_type,
        "assetCode": device.asset_code,
        "status": device.status,
        "lastSeenAt": _iso(device.last_seen_at),
        "firmwareVersion": device.firmware_version,
    }


def _feed_state(feed: IntegrationFeed) -> dict:
    return {
        "kind": "integration_feed",
        "feedId": feed.feed_id,
        "feedType": feed.feed_type,
        "status": feed.status,
        "trustMode": feed.trust_mode,
        "freshnessThresholdSeconds": feed.freshness_threshold_seconds,
    }


def _tide_window_state(window: TideWindow) -> dict:
    return {
        "code": window.code,
        "location": window.location.code,
        "windowStart": _iso(window.window_start),
        "windowEnd": _iso(window.window_end),
        "riskLevel": window.risk_level,
        "minWaterLevelM": _decimal(window.min_water_level_m),
        "maxLoadedDraftM": _decimal(window.max_loaded_draft_m),
        "routeSegment": (
            str(window.applicable_route_segment)
            if window.applicable_route_segment_id
            else ""
        ),
        "source": window.source,
    }


def _bridge_window_state(window: BridgeWindow) -> dict:
    return {
        "code": window.code,
        "location": window.location.code,
        "windowStart": _iso(window.window_start),
        "windowEnd": _iso(window.window_end),
        "status": window.status,
        "clearanceM": _decimal(window.clearance_m),
        "allowedAssetClass": window.allowed_asset_class,
        "notes": window.notes,
    }


def _navigation_check_state(check: NavigationConstraintCheck) -> dict:
    return {
        "voyageId": check.voyage.voyage_id,
        "assetCode": check.asset_code,
        "routeSegment": str(check.route_segment) if check.route_segment_id else "",
        "constraintType": check.constraint_type,
        "etaGate": _iso(check.eta_gate),
        "windowStart": _iso(check.window_start),
        "windowEnd": _iso(check.window_end),
        "marginMinutes": check.margin_minutes,
        "status": check.status,
        "recoveryHint": check.recovery_hint,
    }


def _asset_window_state(window: AssetAvailabilityWindow) -> dict:
    return {
        "assetType": window.asset_type,
        "assetCode": window.asset_code,
        "windowStart": _iso(window.window_start),
        "windowEnd": _iso(window.window_end),
        "status": window.status,
        "reason": window.reason,
    }


def _jetty_window_state(window: JettyAvailabilityWindow) -> dict:
    return {
        "jetty": window.jetty.code,
        "windowStart": _iso(window.window_start),
        "windowEnd": _iso(window.window_end),
        "status": window.status,
        "loadingRateOverrideTph": window.loading_rate_override_tph,
        "reason": window.reason,
    }


def _compatibility_rule_state(rule: AssetCompatibilityRule) -> dict:
    return {
        "code": rule.code,
        "ruleType": rule.rule_type,
        "leftCode": rule.left_code,
        "rightCode": rule.right_code,
        "isCompatible": rule.is_compatible,
        "reason": rule.reason,
    }


def _route_segment_state(assignment: Assignment) -> dict:
    segment = assignment.route_segment
    if segment is None:
        return {
            "assignmentId": assignment.id,
            "tripId": assignment.trip.trip_id,
            "routeSegment": "",
        }
    return {
        "assignmentId": assignment.id,
        "tripId": assignment.trip.trip_id,
        "routeCode": segment.route.code,
        "sequence": segment.sequence,
        "routeSegment": str(segment),
        "fromLocation": segment.from_location,
        "toLocation": segment.to_location,
        "distanceNm": _decimal(segment.distance_nm),
        "loadedDurationMinutes": segment.loaded_duration_minutes,
        "emptyDurationMinutes": segment.empty_duration_minutes,
        "requiresTideWindow": segment.requires_tide_window,
        "requiresBridgeWindow": segment.requires_bridge_window,
    }


def _iso(value) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def _decimal(value) -> str | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return str(value)
    return str(value)
