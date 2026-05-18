import hashlib
import json
from datetime import timedelta
from decimal import Decimal

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.masters.models import AssetCompatibilityRule, Barge, CTSAsset, Tug
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
    OptimizerRun,
    PlanVersion,
    RecommendationEvaluation,
    RecoveryAction,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    ScheduleEvent,
    SimulationScenario,
    Trip,
)

RECOVERY_INPUT_SNAPSHOT_ALGORITHM_VERSION = "phase5.1-input-snapshot-builder"
RECOVERY_REPAIR_ALGORITHM_VERSION = "phase5.2-deterministic-repair-engine"
DEFAULT_REPAIR_OBJECTIVE_WEIGHTS = {
    "delayMinutes": 0.4,
    "missedWindows": 0.25,
    "resourceConflicts": 0.2,
    "manualChanges": 0.1,
    "healthRisk": 0.05,
}


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


def generate_recovery_recommendations(
    *,
    snapshot: RecoveryInputSnapshot,
    objective_weights: dict | None = None,
    actor=None,
    run_id: str | None = None,
    replace_existing: bool = False,
    max_candidates: int = 5,
) -> OptimizerRun:
    weights = {
        **DEFAULT_REPAIR_OBJECTIVE_WEIGHTS,
        **(objective_weights or {}),
    }
    max_candidates = max(1, min(int(max_candidates or 5), 10))
    started_at = timezone.now()
    with transaction.atomic():
        if run_id and replace_existing:
            optimizer_run, _ = OptimizerRun.objects.update_or_create(
                run_id=run_id,
                defaults={
                    "input_snapshot": snapshot,
                    "plan_version": snapshot.plan_version,
                    "status": OptimizerRun.Status.RUNNING,
                    "algorithm_version": RECOVERY_REPAIR_ALGORITHM_VERSION,
                    "objective_weights": weights,
                    "summary": {},
                    "error_message": "",
                    "started_by": actor
                    if actor is not None and getattr(actor, "is_authenticated", True)
                    else None,
                    "started_at": started_at,
                    "completed_at": None,
                },
            )
            optimizer_run.recommendations.all().delete()
        else:
            create_defaults = {
                "input_snapshot": snapshot,
                "plan_version": snapshot.plan_version,
                "status": OptimizerRun.Status.RUNNING,
                "algorithm_version": RECOVERY_REPAIR_ALGORITHM_VERSION,
                "objective_weights": weights,
                "started_by": actor
                if actor is not None and getattr(actor, "is_authenticated", True)
                else None,
                "started_at": started_at,
            }
            if run_id:
                create_defaults["run_id"] = run_id
            optimizer_run = OptimizerRun.objects.create(**create_defaults)

        candidates = _deterministic_repair_candidates(
            snapshot=snapshot,
            objective_weights=weights,
        )
        candidates = sorted(
            candidates,
            key=lambda item: (-item["score"], item["strategy"]),
        )[:max_candidates]

        recommendations = []
        for rank, candidate in enumerate(candidates, start=1):
            recommendation = RecoveryRecommendation.objects.create(
                optimizer_run=optimizer_run,
                rank=rank,
                status=RecoveryRecommendation.Status.CANDIDATE,
                risk_level=candidate["risk_level"],
                score=_decimal_score(candidate["score"], places="0.001"),
                summary=candidate["summary"],
                explanation=candidate["explanation"],
                metadata={
                    "strategy": candidate["strategy"],
                    "algorithmVersion": RECOVERY_REPAIR_ALGORITHM_VERSION,
                    **candidate.get("metadata", {}),
                },
            )
            for sequence, action in enumerate(candidate["actions"], start=1):
                RecoveryAction.objects.create(
                    recommendation=recommendation,
                    sequence=sequence,
                    action_type=action["action_type"],
                    target_trip=action.get("target_trip"),
                    target_assignment=action.get("target_assignment"),
                    before_state=action.get("before_state", {}),
                    after_state=action.get("after_state", {}),
                    constraints_checked=action.get("constraints_checked", []),
                    metadata={
                        "strategy": candidate["strategy"],
                        **action.get("metadata", {}),
                    },
                )
            RecommendationEvaluation.objects.create(
                recommendation=recommendation,
                delay_minutes=candidate["delay_minutes"],
                missed_windows=candidate["missed_windows"],
                resource_conflicts=candidate["resource_conflicts"],
                utilization_delta_pct=_decimal_score(
                    candidate["utilization_delta_pct"],
                    places="0.01",
                ),
                confidence_score=_decimal_score(
                    candidate["confidence_score"],
                    places="0.01",
                ),
                hard_constraints_passed=candidate["hard_constraints_passed"],
                score_breakdown=candidate["score_breakdown"],
                metadata={
                    "strategy": candidate["strategy"],
                    "hardConstraintEvidence": candidate["hard_constraint_evidence"],
                },
            )
            recommendations.append(recommendation)

        optimizer_run.status = OptimizerRun.Status.SUCCEEDED
        optimizer_run.completed_at = timezone.now()
        optimizer_run.summary = _optimizer_summary(
            snapshot=snapshot,
            candidates=candidates,
            recommendations=recommendations,
        )
        optimizer_run.save(
            update_fields=[
                "status",
                "completed_at",
                "summary",
                "updated_at",
            ]
        )
        return optimizer_run


def _deterministic_repair_candidates(
    *,
    snapshot: RecoveryInputSnapshot,
    objective_weights: dict,
) -> list[dict]:
    assignment = _target_assignment_for_snapshot(snapshot)
    if assignment is None:
        return [_noop_candidate(snapshot=snapshot)]

    delay_minutes = _source_delay_minutes(snapshot=snapshot, assignment=assignment)
    candidates = [
        _delay_trip_candidate(
            snapshot=snapshot,
            assignment=assignment,
            delay_minutes=delay_minutes,
            objective_weights=objective_weights,
        ),
        _next_window_candidate(
            snapshot=snapshot,
            assignment=assignment,
            delay_minutes=delay_minutes,
            objective_weights=objective_weights,
        ),
    ]
    resequence = _resequence_candidate(
        snapshot=snapshot,
        assignment=assignment,
        delay_minutes=delay_minutes,
        objective_weights=objective_weights,
    )
    if resequence:
        candidates.append(resequence)
    tug_barge = _tug_barge_swap_candidate(
        snapshot=snapshot,
        assignment=assignment,
        delay_minutes=delay_minutes,
        objective_weights=objective_weights,
    )
    if tug_barge:
        candidates.append(tug_barge)
    cts = _cts_reassignment_candidate(
        snapshot=snapshot,
        assignment=assignment,
        delay_minutes=delay_minutes,
        objective_weights=objective_weights,
    )
    if cts:
        candidates.append(cts)
    return candidates


def _delay_trip_candidate(
    *,
    snapshot: RecoveryInputSnapshot,
    assignment: Assignment,
    delay_minutes: int,
    objective_weights: dict,
) -> dict:
    projected_departure = assignment.planned_departure + timedelta(minutes=delay_minutes)
    projected_arrival = assignment.planned_arrival + timedelta(minutes=delay_minutes)
    constraint_evidence = [
        "confirmed_actuals_frozen",
        "active_schedule_events_projected_only",
        "no_resource_reassignment",
    ]
    return _candidate(
        snapshot=snapshot,
        assignment=assignment,
        strategy="delay_trip",
        summary=(
            f"Delay {assignment.trip.trip_id} by {delay_minutes} minutes without changing "
            "assigned resources."
        ),
        delay_minutes=delay_minutes,
        missed_windows=_missed_windows_for_shift(
            assignment=assignment,
            shift_minutes=delay_minutes,
        ),
        resource_conflicts=0,
        manual_changes=1,
        hard_constraints_passed=True,
        hard_constraint_evidence=constraint_evidence,
        objective_weights=objective_weights,
        actions=[
            {
                "action_type": RecoveryAction.ActionType.DELAY_TRIP,
                "target_trip": assignment.trip,
                "target_assignment": assignment,
                "before_state": _assignment_schedule_state(assignment),
                "after_state": {
                    **_assignment_schedule_state(assignment),
                    "plannedDeparture": _iso(projected_departure),
                    "plannedArrival": _iso(projected_arrival),
                    "delayMinutes": delay_minutes,
                },
                "constraints_checked": constraint_evidence,
                "metadata": {
                    "sourceDelayMinutes": delay_minutes,
                    "mutatesActivePlan": False,
                },
            }
        ],
        explanation=[
            _explanation_node(
                kind="source",
                label="Source disruption",
                value=snapshot.source_ref,
            ),
            _explanation_node(
                kind="repair",
                label="Repair action",
                value=f"Project the disrupted trip {delay_minutes} minutes later.",
            ),
            _explanation_node(
                kind="governance",
                label="Plan safety",
                value="No schedule rows are changed; this is a recommendation only.",
            ),
        ],
    )


def _next_window_candidate(
    *,
    snapshot: RecoveryInputSnapshot,
    assignment: Assignment,
    delay_minutes: int,
    objective_weights: dict,
) -> dict:
    projection = _next_window_projection(assignment=assignment, delay_minutes=delay_minutes)
    shift_minutes = projection["shift_minutes"]
    projected_departure = assignment.planned_departure + timedelta(minutes=shift_minutes)
    projected_arrival = assignment.planned_arrival + timedelta(minutes=shift_minutes)
    hard_passed = projection["hard_constraints_passed"]
    constraint_evidence = [
        "confirmed_actuals_frozen",
        "tide_window_evaluated",
        "bridge_window_evaluated",
        *projection["evidence"],
    ]
    return _candidate(
        snapshot=snapshot,
        assignment=assignment,
        strategy="next_window_repair",
        summary=(
            f"Move {assignment.trip.trip_id} to the next feasible tide/bridge gate "
            "window."
        ),
        delay_minutes=shift_minutes,
        missed_windows=projection["missed_windows"],
        resource_conflicts=0,
        manual_changes=1,
        hard_constraints_passed=hard_passed,
        hard_constraint_evidence=constraint_evidence,
        objective_weights=objective_weights,
        actions=[
            {
                "action_type": RecoveryAction.ActionType.SHIFT_WINDOW,
                "target_trip": assignment.trip,
                "target_assignment": assignment,
                "before_state": {
                    **_assignment_schedule_state(assignment),
                    "bridgeGate": projection["bridge_before"],
                    "tideGate": projection["tide_before"],
                },
                "after_state": {
                    **_assignment_schedule_state(assignment),
                    "plannedDeparture": _iso(projected_departure),
                    "plannedArrival": _iso(projected_arrival),
                    "bridgeGate": projection["bridge_after"],
                    "tideGate": projection["tide_after"],
                    "shiftMinutes": shift_minutes,
                },
                "constraints_checked": constraint_evidence,
                "metadata": {
                    "windowCodes": projection["window_codes"],
                    "mutatesActivePlan": False,
                },
            }
        ],
        explanation=[
            _explanation_node(
                kind="constraint",
                label="Gate repair",
                value=(
                    "Projected bridge and tide gate times are aligned to the next "
                    "available governed windows."
                ),
            ),
            _explanation_node(
                kind="risk",
                label="Window misses",
                value=f"{projection['missed_windows']} miss risk(s) detected.",
            ),
        ],
    )


def _resequence_candidate(
    *,
    snapshot: RecoveryInputSnapshot,
    assignment: Assignment,
    delay_minutes: int,
    objective_weights: dict,
) -> dict | None:
    neighbor = (
        Assignment.objects.select_related("trip", "trip__voyage", "tug", "barge", "jetty", "cts")
        .filter(
            trip__plan_version=snapshot.plan_version,
            trip__sequence__gt=assignment.trip.sequence,
        )
        .order_by("trip__sequence")
        .first()
    )
    if neighbor is None:
        return None
    resequence_delay = max(30, int(delay_minutes * 0.5))
    constraint_evidence = [
        "confirmed_actuals_frozen",
        "ogv_laycan_guardrail",
        "resource_overlap_review_required",
    ]
    return _candidate(
        snapshot=snapshot,
        assignment=assignment,
        strategy="resequence_trip",
        summary=(
            f"Resequence {neighbor.trip.trip_id} around disrupted trip "
            f"{assignment.trip.trip_id}."
        ),
        delay_minutes=resequence_delay,
        missed_windows=_missed_windows_for_shift(
            assignment=neighbor,
            shift_minutes=resequence_delay,
        ),
        resource_conflicts=0,
        manual_changes=2,
        hard_constraints_passed=True,
        hard_constraint_evidence=constraint_evidence,
        objective_weights=objective_weights,
        actions=[
            {
                "action_type": RecoveryAction.ActionType.RESEQUENCE_TRIP,
                "target_trip": assignment.trip,
                "target_assignment": assignment,
                "before_state": {
                    "tripId": assignment.trip.trip_id,
                    "sequence": assignment.trip.sequence,
                },
                "after_state": {
                    "tripId": assignment.trip.trip_id,
                    "sequence": neighbor.trip.sequence,
                },
                "constraints_checked": constraint_evidence,
                "metadata": {"pairedTripId": neighbor.trip.trip_id},
            },
            {
                "action_type": RecoveryAction.ActionType.RESEQUENCE_TRIP,
                "target_trip": neighbor.trip,
                "target_assignment": neighbor,
                "before_state": {
                    "tripId": neighbor.trip.trip_id,
                    "sequence": neighbor.trip.sequence,
                },
                "after_state": {
                    "tripId": neighbor.trip.trip_id,
                    "sequence": assignment.trip.sequence,
                },
                "constraints_checked": constraint_evidence,
                "metadata": {"pairedTripId": assignment.trip.trip_id},
            },
        ],
        explanation=[
            _explanation_node(
                kind="repair",
                label="Sequence repair",
                value="Swap the disrupted trip with the next planned chain candidate.",
            ),
        ],
    )


def _tug_barge_swap_candidate(
    *,
    snapshot: RecoveryInputSnapshot,
    assignment: Assignment,
    delay_minutes: int,
    objective_weights: dict,
) -> dict | None:
    replacement_tug = _replacement_tug(assignment=assignment, snapshot=snapshot)
    replacement_barge = _replacement_barge(assignment=assignment, snapshot=snapshot)
    if replacement_tug is None and replacement_barge is None:
        return None

    tug_code = replacement_tug.code if replacement_tug else assignment.tug.code if assignment.tug else ""
    barge_code = (
        replacement_barge.code
        if replacement_barge
        else assignment.barge.code
        if assignment.barge
        else ""
    )
    compatible = _tug_barge_compatible(tug_code=tug_code, barge_code=barge_code)
    resource_conflicts = _replacement_resource_conflicts(
        assignment=assignment,
        tug_code=tug_code if replacement_tug else "",
        barge_code=barge_code if replacement_barge else "",
    )
    hard_passed = compatible and resource_conflicts == 0
    constraint_evidence = [
        "confirmed_actuals_frozen",
        "tug_barge_compatibility",
        "resource_availability",
        "no_duplicate_assignment",
    ]
    actions = []
    if replacement_tug:
        actions.append(
            {
                "action_type": RecoveryAction.ActionType.REASSIGN_TUG,
                "target_trip": assignment.trip,
                "target_assignment": assignment,
                "before_state": {
                    "tripId": assignment.trip.trip_id,
                    "tug": assignment.tug.code if assignment.tug else "",
                },
                "after_state": {
                    "tripId": assignment.trip.trip_id,
                    "tug": replacement_tug.code,
                },
                "constraints_checked": constraint_evidence,
                "metadata": {"resourceConflictCount": resource_conflicts},
            }
        )
    if replacement_barge:
        actions.append(
            {
                "action_type": RecoveryAction.ActionType.REASSIGN_BARGE,
                "target_trip": assignment.trip,
                "target_assignment": assignment,
                "before_state": {
                    "tripId": assignment.trip.trip_id,
                    "barge": assignment.barge.code if assignment.barge else "",
                },
                "after_state": {
                    "tripId": assignment.trip.trip_id,
                    "barge": replacement_barge.code,
                },
                "constraints_checked": constraint_evidence,
                "metadata": {"resourceConflictCount": resource_conflicts},
            }
        )
    return _candidate(
        snapshot=snapshot,
        assignment=assignment,
        strategy="tug_barge_swap",
        summary=(
            f"Swap tug/barge resources for {assignment.trip.trip_id} to reduce the "
            "disruption exposure."
        ),
        delay_minutes=max(15, int(delay_minutes * 0.35)),
        missed_windows=_missed_windows_for_shift(
            assignment=assignment,
            shift_minutes=max(15, int(delay_minutes * 0.35)),
        ),
        resource_conflicts=resource_conflicts,
        manual_changes=len(actions),
        hard_constraints_passed=hard_passed,
        hard_constraint_evidence=constraint_evidence,
        objective_weights=objective_weights,
        actions=actions,
        explanation=[
            _explanation_node(
                kind="resource",
                label="Resource repair",
                value=(
                    f"Candidate tug {tug_code or 'unchanged'} with barge "
                    f"{barge_code or 'unchanged'}."
                ),
            ),
            _explanation_node(
                kind="constraint",
                label="Compatibility",
                value="Compatible" if compatible else "Compatibility review failed.",
            ),
        ],
    )


def _cts_reassignment_candidate(
    *,
    snapshot: RecoveryInputSnapshot,
    assignment: Assignment,
    delay_minutes: int,
    objective_weights: dict,
) -> dict | None:
    replacement_cts = _replacement_cts(assignment=assignment, snapshot=snapshot)
    if replacement_cts is None:
        return None

    resource_conflicts = _replacement_resource_conflicts(
        assignment=assignment,
        cts_code=replacement_cts.code,
    )
    constraint_evidence = [
        "confirmed_actuals_frozen",
        "cts_available",
        "cts_queue_overlap_review",
    ]
    cts_delay = max(20, int(delay_minutes * 0.45))
    return _candidate(
        snapshot=snapshot,
        assignment=assignment,
        strategy="cts_reassignment",
        summary=(
            f"Reassign {assignment.trip.trip_id} discharge handling to "
            f"{replacement_cts.code}."
        ),
        delay_minutes=cts_delay,
        missed_windows=0,
        resource_conflicts=resource_conflicts,
        manual_changes=1,
        hard_constraints_passed=resource_conflicts == 0,
        hard_constraint_evidence=constraint_evidence,
        objective_weights=objective_weights,
        actions=[
            {
                "action_type": RecoveryAction.ActionType.REASSIGN_CTS,
                "target_trip": assignment.trip,
                "target_assignment": assignment,
                "before_state": {
                    "tripId": assignment.trip.trip_id,
                    "cts": assignment.cts.code if assignment.cts else "",
                },
                "after_state": {
                    "tripId": assignment.trip.trip_id,
                    "cts": replacement_cts.code,
                },
                "constraints_checked": constraint_evidence,
                "metadata": {"resourceConflictCount": resource_conflicts},
            }
        ],
        explanation=[
            _explanation_node(
                kind="resource",
                label="CTS repair",
                value=f"Use {replacement_cts.code} as the discharge recovery resource.",
            ),
        ],
    )


def _candidate(
    *,
    snapshot: RecoveryInputSnapshot,
    assignment: Assignment,
    strategy: str,
    summary: str,
    delay_minutes: int,
    missed_windows: int,
    resource_conflicts: int,
    manual_changes: int,
    hard_constraints_passed: bool,
    hard_constraint_evidence: list[str],
    objective_weights: dict,
    actions: list[dict],
    explanation: list[dict],
) -> dict:
    health_risk_count = len(snapshot.resource_state.get("healthRisks", []))
    score_breakdown = _score_breakdown(
        delay_minutes=delay_minutes,
        missed_windows=missed_windows,
        resource_conflicts=resource_conflicts,
        manual_changes=manual_changes,
        health_risk_count=health_risk_count,
        hard_constraints_passed=hard_constraints_passed,
        objective_weights=objective_weights,
    )
    score = score_breakdown["totalScore"]
    risk_level = _risk_level(
        delay_minutes=delay_minutes,
        missed_windows=missed_windows,
        resource_conflicts=resource_conflicts,
        hard_constraints_passed=hard_constraints_passed,
    )
    return {
        "strategy": strategy,
        "summary": summary,
        "delay_minutes": delay_minutes,
        "missed_windows": missed_windows,
        "resource_conflicts": resource_conflicts,
        "manual_changes": manual_changes,
        "hard_constraints_passed": hard_constraints_passed,
        "hard_constraint_evidence": hard_constraint_evidence,
        "score_breakdown": score_breakdown,
        "score": score,
        "risk_level": risk_level,
        "confidence_score": _confidence_score(
            hard_constraints_passed=hard_constraints_passed,
            health_risk_count=health_risk_count,
            resource_conflicts=resource_conflicts,
        ),
        "utilization_delta_pct": _utilization_delta_pct(
            delay_minutes=delay_minutes,
            manual_changes=manual_changes,
        ),
        "actions": actions,
        "explanation": [
            _explanation_node(
                kind="source",
                label="Input snapshot",
                value=f"{snapshot.snapshot_id} / {snapshot.source_ref}",
            ),
            *explanation,
            _explanation_node(
                kind="constraint",
                label="Hard constraints",
                value="Passed" if hard_constraints_passed else "Review required",
            ),
        ],
        "metadata": {
            "targetTripId": assignment.trip.trip_id,
            "targetAssignmentId": assignment.id,
            "manualChanges": manual_changes,
            "healthRiskCount": health_risk_count,
        },
    }


def _noop_candidate(*, snapshot: RecoveryInputSnapshot) -> dict:
    return {
        "strategy": "noop",
        "summary": "No disrupted assignment could be resolved from the input snapshot.",
        "delay_minutes": 0,
        "missed_windows": 0,
        "resource_conflicts": 0,
        "manual_changes": 0,
        "hard_constraints_passed": False,
        "hard_constraint_evidence": ["no_target_assignment"],
        "score_breakdown": {"totalScore": 0},
        "score": 0,
        "risk_level": RecoveryRecommendation.RiskLevel.CRITICAL,
        "confidence_score": 0,
        "utilization_delta_pct": 0,
        "actions": [
            {
                "action_type": RecoveryAction.ActionType.NOOP,
                "before_state": {},
                "after_state": {},
                "constraints_checked": ["no_target_assignment"],
            }
        ],
        "explanation": [
            _explanation_node(
                kind="risk",
                label="No target",
                value="Snapshot has no resolvable trip or assignment for repair.",
            )
        ],
        "metadata": {},
    }


def _target_assignment_for_snapshot(snapshot: RecoveryInputSnapshot) -> Assignment | None:
    if snapshot.source_override_id and snapshot.source_override.assignment_id:
        return _assignment_by_id(snapshot.source_override.assignment_id)
    if snapshot.source_override_id and snapshot.source_override.trip_id:
        return _assignment_for_trip(snapshot.source_override.trip)
    if snapshot.source_conflict_id and snapshot.source_conflict.trip_id:
        return _assignment_for_trip(snapshot.source_conflict.trip)
    if snapshot.source_tracking_alert_id and snapshot.source_tracking_alert.trip_id:
        return _assignment_for_trip(snapshot.source_tracking_alert.trip)
    if snapshot.source_operational_event_id:
        if snapshot.source_operational_event.assignment_id:
            return _assignment_by_id(snapshot.source_operational_event.assignment_id)
        if snapshot.source_operational_event.trip_id:
            return _assignment_for_trip(snapshot.source_operational_event.trip)
    assignment_id = snapshot.resource_state.get("assignments", [{}])[0].get("assignmentId")
    if assignment_id:
        assignment = _assignment_by_id(assignment_id)
        if assignment:
            return assignment
    return (
        Assignment.objects.select_related(
            "trip",
            "trip__voyage",
            "tug",
            "barge",
            "jetty",
            "cts",
            "route_segment",
            "route_segment__route",
        )
        .prefetch_related("trip__events")
        .filter(trip__plan_version=snapshot.plan_version)
        .order_by("trip__sequence")
        .first()
    )


def _assignment_by_id(assignment_id: int) -> Assignment | None:
    return (
        Assignment.objects.select_related(
            "trip",
            "trip__voyage",
            "tug",
            "barge",
            "jetty",
            "cts",
            "route_segment",
            "route_segment__route",
        )
        .prefetch_related("trip__events")
        .filter(pk=assignment_id)
        .first()
    )


def _assignment_for_trip(trip: Trip) -> Assignment | None:
    return _assignment_by_id(trip.assignment.id) if hasattr(trip, "assignment") else None


def _source_delay_minutes(*, snapshot: RecoveryInputSnapshot, assignment: Assignment) -> int:
    if snapshot.source_override_id and hasattr(snapshot.source_override, "impact_assessment"):
        delay_minutes = snapshot.source_override.impact_assessment.delay_minutes
        if delay_minutes:
            return max(0, delay_minutes)
    if (
        snapshot.source_tracking_alert_id
        and snapshot.source_tracking_alert.eta_projection_id
        and snapshot.source_tracking_alert.eta_projection.variance_minutes is not None
    ):
        return max(15, snapshot.source_tracking_alert.eta_projection.variance_minutes)
    if snapshot.source_operational_event_id and snapshot.source_operational_event.schedule_event_id:
        planned_at = snapshot.source_operational_event.schedule_event.planned_at
        actual_at = snapshot.source_operational_event.actual_at
        return max(0, _ceil_minutes(actual_at - planned_at))
    variance_minutes = [
        projection.get("varianceMinutes")
        for projection in snapshot.event_state.get("etaProjections", [])
        if projection.get("tripId") == assignment.trip.trip_id
        and projection.get("varianceMinutes") is not None
    ]
    if variance_minutes:
        return max(15, max(variance_minutes))
    if snapshot.source_override_id and snapshot.source_override.reason_code == OverrideRequest.ReasonCode.JETTY_DELAY:
        return 120
    if snapshot.source_kind in {
        RecoveryInputSnapshot.SourceKind.CONFLICT,
        RecoveryInputSnapshot.SourceKind.TRACKING_ALERT,
        RecoveryInputSnapshot.SourceKind.OPERATIONAL_EVENT,
    }:
        return 90
    return 60


def _next_window_projection(*, assignment: Assignment, delay_minutes: int) -> dict:
    events = _events_by_type(assignment.trip)
    bridge_event = events.get(ScheduleEvent.EventType.BRIDGE_CROSS)
    tide_event = events.get(ScheduleEvent.EventType.TIDE_GATE)
    bridge_windows = list(
        BridgeWindow.objects.filter(is_active=True)
        .exclude(status=BridgeWindow.Status.CLOSED)
        .order_by("window_start", "code")
    )
    tide_windows = TideWindow.objects.filter(is_active=True).exclude(
        risk_level=TideWindow.RiskLevel.CLOSED,
    )
    route_segment_ids = _route_segment_ids_for_assignment(assignment)
    if route_segment_ids:
        tide_windows = tide_windows.filter(
            Q(applicable_route_segment_id__in=route_segment_ids)
            | Q(applicable_route_segment__isnull=True)
        )
    tide_windows = list(tide_windows.order_by("window_start", "code"))

    bridge_plan = bridge_event.planned_at if bridge_event else assignment.planned_departure
    tide_plan = tide_event.planned_at if tide_event else assignment.planned_departure
    bridge_projected = bridge_plan + timedelta(minutes=delay_minutes)
    tide_projected = tide_plan + timedelta(minutes=delay_minutes)
    bridge_eval = _window_repair_eval(projected_at=bridge_projected, windows=bridge_windows)
    tide_eval = _window_repair_eval(projected_at=tide_projected, windows=tide_windows)
    added_shift = max(bridge_eval["additional_shift"], tide_eval["additional_shift"])
    shift_minutes = delay_minutes + added_shift
    return {
        "shift_minutes": shift_minutes,
        "missed_windows": int(bridge_eval["missed"]) + int(tide_eval["missed"]),
        "hard_constraints_passed": bridge_eval["window"] is not None and tide_eval["window"] is not None,
        "evidence": [
            bridge_eval["evidence"],
            tide_eval["evidence"],
        ],
        "window_codes": [
            item.code
            for item in [bridge_eval["window"], tide_eval["window"]]
            if item is not None
        ],
        "bridge_before": _iso(bridge_projected),
        "tide_before": _iso(tide_projected),
        "bridge_after": _iso(bridge_plan + timedelta(minutes=shift_minutes)),
        "tide_after": _iso(tide_plan + timedelta(minutes=shift_minutes)),
    }


def _window_repair_eval(*, projected_at, windows: list) -> dict:
    if not windows:
        return {
            "additional_shift": 0,
            "missed": True,
            "window": None,
            "evidence": "no_active_window",
        }
    for window in windows:
        if window.window_start <= projected_at <= window.window_end:
            return {
                "additional_shift": 0,
                "missed": False,
                "window": window,
                "evidence": f"inside_{window.code}",
            }
    next_window = next((window for window in windows if window.window_start > projected_at), None)
    if next_window:
        return {
            "additional_shift": _ceil_minutes(next_window.window_start - projected_at),
            "missed": True,
            "window": next_window,
            "evidence": f"shift_to_{next_window.code}",
        }
    return {
        "additional_shift": 0,
        "missed": True,
        "window": None,
        "evidence": "no_future_window",
    }


def _missed_windows_for_shift(*, assignment: Assignment, shift_minutes: int) -> int:
    projection = _next_window_projection(assignment=assignment, delay_minutes=shift_minutes)
    return projection["missed_windows"]


def _replacement_tug(*, assignment: Assignment, snapshot: RecoveryInputSnapshot) -> Tug | None:
    current_code = assignment.tug.code if assignment.tug else ""
    candidates = list(Tug.objects.filter(is_active=True).exclude(code=current_code))
    candidates.sort(
        key=lambda item: (
            item.status != Tug.Status.AVAILABLE,
            _replacement_resource_conflicts(assignment=assignment, tug_code=item.code),
            item.code,
        )
    )
    for candidate in candidates:
        barge_code = assignment.barge.code if assignment.barge else ""
        if _tug_barge_compatible(tug_code=candidate.code, barge_code=barge_code):
            return candidate
    return candidates[0] if candidates else None


def _replacement_barge(*, assignment: Assignment, snapshot: RecoveryInputSnapshot) -> Barge | None:
    current_code = assignment.barge.code if assignment.barge else ""
    tug_code = assignment.tug.code if assignment.tug else ""
    candidates = list(Barge.objects.filter(is_active=True).exclude(code=current_code))
    candidates.sort(
        key=lambda item: (
            item.status != Barge.Status.AVAILABLE,
            _replacement_resource_conflicts(assignment=assignment, barge_code=item.code),
            item.code,
        )
    )
    for candidate in candidates:
        if _tug_barge_compatible(tug_code=tug_code, barge_code=candidate.code):
            return candidate
    return candidates[0] if candidates else None


def _replacement_cts(*, assignment: Assignment, snapshot: RecoveryInputSnapshot) -> CTSAsset | None:
    current_code = assignment.cts.code if assignment.cts else ""
    candidates = list(CTSAsset.objects.filter(is_active=True, is_available=True).exclude(
        code=current_code
    ))
    candidates.sort(
        key=lambda item: (
            _replacement_resource_conflicts(assignment=assignment, cts_code=item.code),
            item.code,
        )
    )
    return candidates[0] if candidates else None


def _replacement_resource_conflicts(
    *,
    assignment: Assignment,
    tug_code: str = "",
    barge_code: str = "",
    cts_code: str = "",
) -> int:
    query = Assignment.objects.select_related("trip", "tug", "barge", "cts").filter(
        trip__plan_version=assignment.trip.plan_version,
        planned_departure__lt=assignment.planned_arrival,
        planned_arrival__gt=assignment.planned_departure,
    ).exclude(pk=assignment.pk)
    conflicts = 0
    if tug_code:
        conflicts += query.filter(tug__code=tug_code).count()
    if barge_code:
        conflicts += query.filter(barge__code=barge_code).count()
    if cts_code:
        conflicts += query.filter(cts__code=cts_code).count()
    return conflicts


def _tug_barge_compatible(*, tug_code: str, barge_code: str) -> bool:
    if not tug_code or not barge_code:
        return True
    return not AssetCompatibilityRule.objects.filter(
        rule_type=AssetCompatibilityRule.RuleType.TUG_BARGE,
        left_code=tug_code,
        right_code=barge_code,
        is_active=True,
        is_compatible=False,
    ).exists()


def _events_by_type(trip: Trip) -> dict[str, ScheduleEvent]:
    return {event.event_type: event for event in trip.events.all()}


def _route_segment_ids_for_assignment(assignment: Assignment) -> list[int]:
    if not assignment.route_segment_id:
        return []
    route = assignment.route_segment.route
    route_segment_ids = set(
        route.segments.filter(requires_tide_window=True).values_list("id", flat=True)
    )
    route_segment_ids.add(assignment.route_segment_id)
    return list(route_segment_ids)


def _assignment_schedule_state(assignment: Assignment) -> dict:
    return {
        "tripId": assignment.trip.trip_id,
        "status": assignment.status,
        "plannedDeparture": _iso(assignment.planned_departure),
        "plannedArrival": _iso(assignment.planned_arrival),
        "tug": assignment.tug.code if assignment.tug else "",
        "barge": assignment.barge.code if assignment.barge else "",
        "jetty": assignment.jetty.code if assignment.jetty else "",
        "cts": assignment.cts.code if assignment.cts else "",
    }


def _score_breakdown(
    *,
    delay_minutes: int,
    missed_windows: int,
    resource_conflicts: int,
    manual_changes: int,
    health_risk_count: int,
    hard_constraints_passed: bool,
    objective_weights: dict,
) -> dict:
    delay_penalty = delay_minutes * 0.25 * float(objective_weights["delayMinutes"])
    window_penalty = missed_windows * 30 * float(objective_weights["missedWindows"])
    resource_penalty = resource_conflicts * 35 * float(objective_weights["resourceConflicts"])
    manual_penalty = manual_changes * 10 * float(objective_weights["manualChanges"])
    health_penalty = min(20, health_risk_count * 3) * float(objective_weights["healthRisk"])
    hard_penalty = 30 if not hard_constraints_passed else 0
    total = max(
        0,
        100
        - delay_penalty
        - window_penalty
        - resource_penalty
        - manual_penalty
        - health_penalty
        - hard_penalty,
    )
    return {
        "delayPenalty": round(delay_penalty, 3),
        "windowPenalty": round(window_penalty, 3),
        "resourcePenalty": round(resource_penalty, 3),
        "manualPenalty": round(manual_penalty, 3),
        "healthPenalty": round(health_penalty, 3),
        "hardConstraintPenalty": hard_penalty,
        "totalScore": round(total, 3),
    }


def _risk_level(
    *,
    delay_minutes: int,
    missed_windows: int,
    resource_conflicts: int,
    hard_constraints_passed: bool,
) -> str:
    if not hard_constraints_passed:
        return RecoveryRecommendation.RiskLevel.HIGH
    if resource_conflicts or missed_windows > 1 or delay_minutes >= 180:
        return RecoveryRecommendation.RiskLevel.HIGH
    if missed_windows or delay_minutes >= 90:
        return RecoveryRecommendation.RiskLevel.MEDIUM
    return RecoveryRecommendation.RiskLevel.LOW


def _confidence_score(
    *,
    hard_constraints_passed: bool,
    health_risk_count: int,
    resource_conflicts: int,
) -> float:
    score = 86
    if not hard_constraints_passed:
        score -= 24
    score -= min(18, health_risk_count * 4)
    score -= min(20, resource_conflicts * 10)
    return max(0, score)


def _utilization_delta_pct(*, delay_minutes: int, manual_changes: int) -> float:
    return round(min(12, (delay_minutes / 60) * 1.5 + manual_changes * 0.75), 2)


def _optimizer_summary(
    *,
    snapshot: RecoveryInputSnapshot,
    candidates: list[dict],
    recommendations: list[RecoveryRecommendation],
) -> dict:
    best = recommendations[0] if recommendations else None
    return {
        "sourceRef": snapshot.source_ref,
        "sourceKind": snapshot.source_kind,
        "recommendationCount": len(recommendations),
        "candidateStrategies": [candidate["strategy"] for candidate in candidates],
        "bestRecommendation": best.recommendation_id if best else "",
        "bestStrategy": candidates[0]["strategy"] if candidates else "",
        "hardConstraintPassCount": len(
            [candidate for candidate in candidates if candidate["hard_constraints_passed"]]
        ),
        "algorithmVersion": RECOVERY_REPAIR_ALGORITHM_VERSION,
        "mode": "deterministic_repair",
    }


def _explanation_node(*, kind: str, label: str, value: str) -> dict:
    return {"kind": kind, "label": label, "value": value}


def _decimal_score(value, *, places: str) -> Decimal:
    return Decimal(str(value)).quantize(Decimal(places))


def _ceil_minutes(delta) -> int:
    return max(0, int((delta.total_seconds() + 59) // 60))


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
