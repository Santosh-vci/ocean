from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Q
from django.utils import timezone
from django.utils.dateparse import parse_datetime

from apps.masters.models import AssetCompatibilityRule, Barge, CTSAsset, Jetty, Tug
from apps.planning.models import AssetAvailabilityWindow, JettyAvailabilityWindow
from apps.telemetry.models import TrackingAlert

from .models import (
    Assignment,
    Conflict,
    OptimizerRun,
    OverrideRequest,
    RecoveryAction,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    RootCauseRepairAssessment,
)

ROOT_CAUSE_REPAIR_ASSESSMENT_VERSION = "phase6.3-root-cause-repair-assessment"

ASSET_CAUSE_TYPES = {
    "BARGE_UNAVAILABLE": "barge",
    "TUG_UNAVAILABLE": "tug",
    "CTS_UNAVAILABLE": "cts",
}

SUPPORTED_CAUSE_TYPES = {
    "BARGE_UNAVAILABLE",
    "TUG_UNAVAILABLE",
    "CTS_UNAVAILABLE",
    "JETTY_OVERLAP",
    "MOVEMENT_ASSIGNMENT_BLOCKED",
    "TIDE_WINDOW_MISSED",
    "BRIDGE_WINDOW_MISSED",
    "LAYER_SEQUENCE_VIOLATION",
    "TELEMETRY_ALERT_UNRESOLVED",
}

REASSIGN_ACTION_BY_ASSET = {
    "barge": RecoveryAction.ActionType.REASSIGN_BARGE,
    "tug": RecoveryAction.ActionType.REASSIGN_TUG,
    "cts": RecoveryAction.ActionType.REASSIGN_CTS,
}

TIMING_ACTIONS = {
    RecoveryAction.ActionType.DELAY_TRIP,
    RecoveryAction.ActionType.RESEQUENCE_TRIP,
    RecoveryAction.ActionType.SHIFT_WINDOW,
    RecoveryAction.ActionType.HOLD_AT_ANCHORAGE,
}

OVERRIDE_CAUSE_MAP = {
    OverrideRequest.ReasonCode.BARGE_UNAVAILABLE: "BARGE_UNAVAILABLE",
    OverrideRequest.ReasonCode.TUG_BREAKDOWN: "TUG_UNAVAILABLE",
    OverrideRequest.ReasonCode.JETTY_DELAY: "JETTY_OVERLAP",
    OverrideRequest.ReasonCode.GRADE_SEQUENCE_RECOVERY: "LAYER_SEQUENCE_VIOLATION",
}


@dataclass(slots=True)
class AssessmentEvidence:
    addressing: list[dict[str, Any]]
    mitigating: list[dict[str, Any]]
    unrelated: list[dict[str, Any]]
    unknown: list[dict[str, Any]]


def assess_recommendation_root_cause(
    recommendation: RecoveryRecommendation,
    *,
    actor=None,
) -> RootCauseRepairAssessment:
    recommendation = (
        RecoveryRecommendation.objects.select_related(
            "optimizer_run",
            "optimizer_run__input_snapshot",
            "optimizer_run__input_snapshot__source_conflict",
            "optimizer_run__input_snapshot__source_conflict__trip",
            "optimizer_run__input_snapshot__source_override",
            "optimizer_run__input_snapshot__source_tracking_alert",
            "optimizer_run__input_snapshot__source_operational_event",
            "optimizer_run__plan_version",
        )
        .prefetch_related("actions__target_assignment", "actions__target_trip", "evaluation")
        .get(pk=recommendation.pk)
    )
    payload = build_root_cause_assessment_payload(recommendation)
    assessment, _ = RootCauseRepairAssessment.objects.update_or_create(
        recommendation=recommendation,
        defaults={
            "source_kind": payload["source_kind"],
            "source_ref": payload["source_ref"],
            "source_cause_type": payload["source_cause_type"],
            "status": payload["status"],
            "required_resolution": payload["required_resolution"],
            "observed_resolution": payload["observed_resolution"],
            "residual_risk": payload["residual_risk"],
            "evidence": {
                **payload["evidence"],
                "assessedBy": getattr(actor, "email", "") if actor else "",
            },
            "assessed_at": timezone.now(),
            "assessed_by_algorithm_version": ROOT_CAUSE_REPAIR_ASSESSMENT_VERSION,
        },
    )
    return assessment


def build_root_cause_assessment_payload(recommendation: RecoveryRecommendation) -> dict[str, Any]:
    snapshot = recommendation.optimizer_run.input_snapshot
    source_cause_type = _source_cause_type(snapshot)
    actions = list(recommendation.actions.order_by("sequence", "id"))
    required_resolution = _required_resolution(source_cause_type)

    if source_cause_type not in SUPPORTED_CAUSE_TYPES:
        status = RootCauseRepairAssessment.Status.UNKNOWN
        observed_resolution = {
            "summary": "Source cause is not supported by Chunk 6.3 validation.",
            "actions": [_action_summary(action) for action in actions],
            "resolutionEvidence": [],
        }
        residual_risk = _residual_risk(
            status=status,
            message="Root-cause status cannot be determined for this source family.",
        )
    elif not actions:
        status = RootCauseRepairAssessment.Status.UNKNOWN
        observed_resolution = {
            "summary": "Recommendation has no repair actions to assess.",
            "actions": [],
            "resolutionEvidence": [],
        }
        residual_risk = _residual_risk(
            status=status,
            message="No recovery action evidence exists.",
        )
    else:
        evidence = _assess_supported_family(
            recommendation=recommendation,
            snapshot=snapshot,
            source_cause_type=source_cause_type,
            actions=actions,
        )
        status = _status_from_evidence(evidence)
        observed_resolution = {
            "summary": _observed_summary(status=status, source_cause_type=source_cause_type),
            "actions": [_action_summary(action) for action in actions],
            "resolutionEvidence": [
                *evidence.addressing,
                *evidence.mitigating,
                *evidence.unrelated,
                *evidence.unknown,
            ],
        }
        residual_risk = _residual_risk(
            status=status,
            message=_residual_message(status=status, source_cause_type=source_cause_type),
        )

    return {
        "source_kind": snapshot.source_kind,
        "source_ref": _source_ref(snapshot),
        "source_cause_type": source_cause_type,
        "status": status,
        "required_resolution": required_resolution,
        "observed_resolution": observed_resolution,
        "residual_risk": residual_risk,
        "evidence": {
            "algorithmVersion": ROOT_CAUSE_REPAIR_ASSESSMENT_VERSION,
            "recommendationId": recommendation.recommendation_id,
            "optimizerRunId": recommendation.optimizer_run.run_id,
            "snapshotId": snapshot.snapshot_id,
            "sourceConflictId": snapshot.source_conflict_id,
            "sourceTrackingAlertId": snapshot.source_tracking_alert_id,
            "actionCount": len(actions),
        },
    }


def root_cause_assessment_payload(
    assessment: RootCauseRepairAssessment | None,
) -> dict[str, Any] | None:
    if assessment is None:
        return None
    return {
        "id": assessment.pk,
        "assessmentId": assessment.assessment_id,
        "recommendationId": assessment.recommendation_id,
        "sourceKind": assessment.source_kind,
        "sourceRef": assessment.source_ref,
        "sourceCauseType": assessment.source_cause_type,
        "status": assessment.status,
        "requiredResolution": assessment.required_resolution,
        "observedResolution": assessment.observed_resolution,
        "residualRisk": assessment.residual_risk,
        "evidence": assessment.evidence,
        "assessedAt": _iso(assessment.assessed_at),
        "assessedByAlgorithmVersion": assessment.assessed_by_algorithm_version,
    }


def _assess_supported_family(
    *,
    recommendation: RecoveryRecommendation,
    snapshot: RecoveryInputSnapshot,
    source_cause_type: str,
    actions: list[RecoveryAction],
) -> AssessmentEvidence:
    if source_cause_type in ASSET_CAUSE_TYPES:
        return _assess_asset_family(
            recommendation=recommendation,
            snapshot=snapshot,
            source_cause_type=source_cause_type,
            actions=actions,
        )
    if source_cause_type == "JETTY_OVERLAP":
        return _assess_jetty_overlap(snapshot=snapshot, actions=actions)
    if source_cause_type == "MOVEMENT_ASSIGNMENT_BLOCKED":
        return _assess_movement_assignment_blocked(
            recommendation=recommendation,
            actions=actions,
        )
    if source_cause_type in {"TIDE_WINDOW_MISSED", "BRIDGE_WINDOW_MISSED"}:
        return _assess_navigation_window(
            recommendation=recommendation,
            source_cause_type=source_cause_type,
            actions=actions,
        )
    if source_cause_type == "LAYER_SEQUENCE_VIOLATION":
        return _assess_layer_sequence(actions=actions)
    if source_cause_type == "TELEMETRY_ALERT_UNRESOLVED":
        return _assess_telemetry_alert(snapshot=snapshot, actions=actions)
    return AssessmentEvidence([], [], [], [{"kind": "unsupported_source"}])


def _assess_asset_family(
    *,
    recommendation: RecoveryRecommendation,
    snapshot: RecoveryInputSnapshot,
    source_cause_type: str,
    actions: list[RecoveryAction],
) -> AssessmentEvidence:
    asset_type = ASSET_CAUSE_TYPES[source_cause_type]
    expected_reassign = REASSIGN_ACTION_BY_ASSET[asset_type]
    source_code = _source_asset_code(snapshot=snapshot, asset_type=asset_type)
    addressing: list[dict[str, Any]] = []
    mitigating: list[dict[str, Any]] = []
    unrelated: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []

    for action in actions:
        if _operator_approved_mitigation(action):
            mitigating.append(_resolution(action, "operator_mitigation", "Operator mitigation accepted."))
            continue

        if action.action_type == expected_reassign:
            replacement_code = _resource_code_from_action(action, asset_type)
            if _replacement_resource_is_valid(
                action=action,
                asset_type=asset_type,
                source_code=source_code,
                replacement_code=replacement_code,
            ):
                addressing.append(
                    _resolution(
                        action,
                        f"{asset_type}_reassignment",
                        f"{replacement_code} is an available compatible replacement.",
                    )
                )
            else:
                unknown.append(
                    _resolution(
                        action,
                        f"{asset_type}_reassignment_unverified",
                        "Replacement availability or compatibility could not be proven.",
                    )
                )
            continue

        if action.action_type in TIMING_ACTIONS:
            if _action_interval_avoids_asset_outage(
                snapshot=snapshot,
                action=action,
                asset_type=asset_type,
                source_code=source_code,
            ):
                addressing.append(
                    _resolution(
                        action,
                        "timing_avoids_outage",
                        "Projected timing avoids the source outage window.",
                    )
                )
            else:
                mitigating.append(
                    _resolution(
                        action,
                        "timing_mitigation_unverified",
                        "Timing changed, but source outage removal is not fully proven.",
                    )
                )
            continue

        unrelated.append(
            _resolution(
                action,
                "unrelated_action_family",
                f"{action.action_type} does not repair {source_cause_type}.",
            )
        )

    if recommendation.metadata.get("explicitOperationalMitigation"):
        mitigating.append({
            "kind": "explicit_operational_mitigation",
            "detail": "Recommendation metadata records an explicit operational mitigation.",
            "metadata": recommendation.metadata.get("explicitOperationalMitigation"),
        })

    return AssessmentEvidence(addressing, mitigating, unrelated, unknown)


def _assess_jetty_overlap(
    *,
    snapshot: RecoveryInputSnapshot,
    actions: list[RecoveryAction],
) -> AssessmentEvidence:
    source_code = _source_jetty_code(snapshot)
    addressing: list[dict[str, Any]] = []
    mitigating: list[dict[str, Any]] = []
    unrelated: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for action in actions:
        if action.action_type in TIMING_ACTIONS:
            if _action_interval_avoids_jetty_overlap(action=action, jetty_code=source_code):
                addressing.append(
                    _resolution(
                        action,
                        "timing_avoids_jetty_overlap",
                        "Projected timing avoids the source jetty overlap.",
                    )
                )
            elif _action_interval(action) != (None, None):
                mitigating.append(
                    _resolution(
                        action,
                        "timing_mitigation_unverified",
                        "Timing changed, but the jetty overlap is not fully cleared.",
                    )
                )
            else:
                unknown.append(
                    _resolution(
                        action,
                        "timing_without_window_evidence",
                        "No projected timing evidence was available.",
                    )
                )
            continue
        unrelated.append(
            _resolution(
                action,
                "unrelated_action_family",
                f"{action.action_type} does not repair a jetty overlap.",
            )
        )
    return AssessmentEvidence(addressing, mitigating, unrelated, unknown)


def _assess_navigation_window(
    *,
    recommendation: RecoveryRecommendation,
    source_cause_type: str,
    actions: list[RecoveryAction],
) -> AssessmentEvidence:
    required_check = (
        "tide_window_evaluated"
        if source_cause_type == "TIDE_WINDOW_MISSED"
        else "bridge_window_evaluated"
    )
    evaluation = getattr(recommendation, "evaluation", None)
    addressing: list[dict[str, Any]] = []
    mitigating: list[dict[str, Any]] = []
    unrelated: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for action in actions:
        if action.action_type in TIMING_ACTIONS and required_check in action.constraints_checked:
            if evaluation and evaluation.missed_windows == 0:
                addressing.append(
                    _resolution(
                        action,
                        "navigation_window_cleared",
                        "Projected timing satisfies the relevant operating window.",
                    )
                )
            else:
                mitigating.append(
                    _resolution(
                        action,
                        "navigation_window_reduced",
                        "The window was evaluated, but residual miss risk remains.",
                    )
                )
            continue
        if action.action_type in TIMING_ACTIONS:
            unknown.append(
                _resolution(
                    action,
                    "navigation_window_not_evaluated",
                    "Timing changed without relevant tide/bridge evidence.",
                )
            )
            continue
        unrelated.append(
            _resolution(
                action,
                "unrelated_action_family",
                f"{action.action_type} does not repair {source_cause_type}.",
            )
        )
    return AssessmentEvidence(addressing, mitigating, unrelated, unknown)


def _assess_movement_assignment_blocked(
    *,
    recommendation: RecoveryRecommendation,
    actions: list[RecoveryAction],
) -> AssessmentEvidence:
    evaluation = getattr(recommendation, "evaluation", None)
    addressing: list[dict[str, Any]] = []
    mitigating: list[dict[str, Any]] = []
    unrelated: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []

    for action in actions:
        if not _is_assignment_repair_action(action):
            unrelated.append(
                _resolution(
                    action,
                    "unrelated_action_family",
                    f"{action.action_type} does not repair movement assignment feasibility.",
                )
            )
            continue

        if evaluation is None:
            unknown.append(
                _resolution(
                    action,
                    "missing_recommendation_evaluation",
                    "No recommendation evaluation exists to prove movement assignment feasibility.",
                )
            )
            continue

        if (
            evaluation.hard_constraints_passed
            and evaluation.missed_windows == 0
            and evaluation.resource_conflicts == 0
        ):
            addressing.append(
                _resolution(
                    action,
                    "movement_assignment_feasible",
                    "Recommendation evaluation clears movement assignment hard constraints.",
                )
            )
            continue

        mitigating.append(
            _resolution(
                action,
                "movement_assignment_residual_risk",
                "Recommendation changes assignment feasibility but leaves residual hard-constraint risk.",
            )
        )

    return AssessmentEvidence(addressing, mitigating, unrelated, unknown)


def _assess_layer_sequence(*, actions: list[RecoveryAction]) -> AssessmentEvidence:
    addressing: list[dict[str, Any]] = []
    mitigating: list[dict[str, Any]] = []
    unrelated: list[dict[str, Any]] = []
    unknown: list[dict[str, Any]] = []
    for action in actions:
        metadata = action.metadata if isinstance(action.metadata, dict) else {}
        if metadata.get("cargoSequenceRepair") or metadata.get("sequenceViolationCleared"):
            addressing.append(
                _resolution(
                    action,
                    "cargo_sequence_repaired",
                    "Action metadata records cargo sequence repair evidence.",
                )
            )
        elif action.action_type == RecoveryAction.ActionType.RESEQUENCE_TRIP:
            mitigating.append(
                _resolution(
                    action,
                    "trip_resequence_only",
                    "Trip resequence may reduce impact but does not prove cargo sequence repair.",
                )
            )
        else:
            unrelated.append(
                _resolution(
                    action,
                    "unrelated_action_family",
                    f"{action.action_type} does not repair cargo sequence truth.",
                )
            )
    return AssessmentEvidence(addressing, mitigating, unrelated, unknown)


def _assess_telemetry_alert(
    *,
    snapshot: RecoveryInputSnapshot,
    actions: list[RecoveryAction],
) -> AssessmentEvidence:
    alert = snapshot.source_tracking_alert
    if alert is None:
        return AssessmentEvidence([], [], [], [{
            "kind": "missing_tracking_alert",
            "detail": "No source tracking alert is linked to the snapshot.",
        }])
    if alert.status in {
        TrackingAlert.Status.RESOLVED,
        TrackingAlert.Status.CONVERTED_TO_SCENARIO,
    }:
        return AssessmentEvidence([
            {
                "kind": "tracking_alert_resolved",
                "detail": "Source telemetry alert is resolved or governed as a scenario.",
                "alertId": alert.alert_id,
                "alertStatus": alert.status,
            }
        ], [], [], [])
    if actions:
        return AssessmentEvidence([], [
            {
                "kind": "telemetry_operational_mitigation",
                "detail": "Recommendation mitigates impact while telemetry remains unresolved.",
                "alertId": alert.alert_id,
                "alertStatus": alert.status,
            }
        ], [], [])
    return AssessmentEvidence([], [], [], [{
        "kind": "telemetry_unresolved",
        "detail": "Source telemetry alert remains unresolved.",
        "alertId": alert.alert_id,
        "alertStatus": alert.status,
    }])


def _source_cause_type(snapshot: RecoveryInputSnapshot) -> str:
    if snapshot.source_conflict_id and snapshot.source_conflict:
        return snapshot.source_conflict.code
    if snapshot.source_tracking_alert_id:
        return "TELEMETRY_ALERT_UNRESOLVED"
    if snapshot.source_override_id and snapshot.source_override:
        if snapshot.source_override.reason_code == OverrideRequest.ReasonCode.TIDE_BRIDGE_RECOVERY:
            return _tide_or_bridge_from_snapshot(snapshot) or "TIDE_WINDOW_MISSED"
        return OVERRIDE_CAUSE_MAP.get(snapshot.source_override.reason_code, "")
    conflicts = snapshot.constraint_state.get("conflicts", [])
    if isinstance(conflicts, list):
        for conflict in conflicts:
            code = conflict.get("code") if isinstance(conflict, dict) else ""
            if code:
                return str(code)
    return ""


def _source_ref(snapshot: RecoveryInputSnapshot) -> str:
    if snapshot.source_ref:
        return snapshot.source_ref
    if snapshot.source_conflict_id and snapshot.source_conflict:
        return f"{snapshot.source_conflict.code}:{snapshot.source_conflict.pk}"
    if snapshot.source_tracking_alert_id and snapshot.source_tracking_alert:
        return snapshot.source_tracking_alert.alert_id
    if snapshot.source_override_id and snapshot.source_override:
        return str(snapshot.source_override.pk)
    return snapshot.snapshot_id


def _required_resolution(source_cause_type: str) -> dict[str, Any]:
    common = {
        "sourceCauseType": source_cause_type,
        "acceptedStatuses": [
            RootCauseRepairAssessment.Status.ADDRESSES_CAUSE,
            RootCauseRepairAssessment.Status.MITIGATES_CAUSE,
        ],
    }
    if source_cause_type in ASSET_CAUSE_TYPES:
        asset_type = ASSET_CAUSE_TYPES[source_cause_type]
        return {
            **common,
            "family": "asset_unavailable",
            "requiredEvidence": [
                f"{asset_type} availability restored before trip window",
                f"assignment changed to an available compatible {asset_type}",
                "trip timing avoids the source outage window",
                "explicit operator mitigation records residual risk",
            ],
        }
    if source_cause_type == "JETTY_OVERLAP":
        return {
            **common,
            "family": "jetty_overlap",
            "requiredEvidence": ["trip timing avoids non-working jetty window"],
        }
    if source_cause_type == "MOVEMENT_ASSIGNMENT_BLOCKED":
        return {
            **common,
            "family": "movement_assignment_candidate",
            "requiredEvidence": [
                "recommendation action changes timing or tug/barge/jetty/CTS assignment",
                "recommendation evaluation passes hard constraints",
                "no residual missed tide/bridge windows or resource conflicts remain",
            ],
        }
    if source_cause_type in {"TIDE_WINDOW_MISSED", "BRIDGE_WINDOW_MISSED"}:
        return {
            **common,
            "family": "navigation_window",
            "requiredEvidence": ["projected timing satisfies the relevant operating window"],
        }
    if source_cause_type == "LAYER_SEQUENCE_VIOLATION":
        return {
            **common,
            "family": "cargo_sequence",
            "requiredEvidence": ["cargo sequence violation is explicitly cleared"],
        }
    if source_cause_type == "TELEMETRY_ALERT_UNRESOLVED":
        return {
            **common,
            "family": "telemetry_alert",
            "requiredEvidence": ["tracking alert is resolved or governed as a scenario"],
        }
    return {
        **common,
        "family": "unsupported",
        "requiredEvidence": ["supported source family is required"],
    }


def _status_from_evidence(evidence: AssessmentEvidence) -> str:
    if evidence.addressing:
        return RootCauseRepairAssessment.Status.ADDRESSES_CAUSE
    if evidence.mitigating:
        return RootCauseRepairAssessment.Status.MITIGATES_CAUSE
    if evidence.unrelated:
        return RootCauseRepairAssessment.Status.DOES_NOT_ADDRESS_CAUSE
    return RootCauseRepairAssessment.Status.UNKNOWN


def _observed_summary(*, status: str, source_cause_type: str) -> str:
    if status == RootCauseRepairAssessment.Status.ADDRESSES_CAUSE:
        return f"Recommendation includes evidence that addresses {source_cause_type}."
    if status == RootCauseRepairAssessment.Status.MITIGATES_CAUSE:
        return f"Recommendation mitigates {source_cause_type} but leaves residual risk."
    if status == RootCauseRepairAssessment.Status.DOES_NOT_ADDRESS_CAUSE:
        return f"Recommendation actions do not address {source_cause_type}."
    return f"Recommendation evidence is insufficient to assess {source_cause_type}."


def _residual_message(*, status: str, source_cause_type: str) -> str:
    if status == RootCauseRepairAssessment.Status.ADDRESSES_CAUSE:
        return "No root-cause residual risk identified by Chunk 6.3 validation."
    if status == RootCauseRepairAssessment.Status.MITIGATES_CAUSE:
        return f"{source_cause_type} is mitigated but not fully removed."
    if status == RootCauseRepairAssessment.Status.DOES_NOT_ADDRESS_CAUSE:
        return f"{source_cause_type} remains physically unresolved."
    return f"{source_cause_type} could not be validated from available evidence."


def _residual_risk(*, status: str, message: str) -> dict[str, Any]:
    if status == RootCauseRepairAssessment.Status.ADDRESSES_CAUSE:
        level = "low"
        items: list[dict[str, Any]] = []
    elif status == RootCauseRepairAssessment.Status.MITIGATES_CAUSE:
        level = "medium"
        items = [{"severity": "warning", "message": message}]
    elif status == RootCauseRepairAssessment.Status.DOES_NOT_ADDRESS_CAUSE:
        level = "high"
        items = [{"severity": "critical", "message": message}]
    else:
        level = "unknown"
        items = [{"severity": "warning", "message": message}]
    return {"level": level, "count": len(items), "items": items}


def _source_asset_code(*, snapshot: RecoveryInputSnapshot, asset_type: str) -> str:
    conflict = snapshot.source_conflict
    if conflict and conflict.object_type == asset_type and conflict.object_id:
        return conflict.object_id
    assignment = _source_assignment(snapshot)
    if assignment is None:
        return ""
    resource = getattr(assignment, asset_type, None)
    return resource.code if resource else ""


def _source_jetty_code(snapshot: RecoveryInputSnapshot) -> str:
    conflict = snapshot.source_conflict
    if conflict and conflict.object_type == "jetty" and conflict.object_id:
        return conflict.object_id
    assignment = _source_assignment(snapshot)
    return assignment.jetty.code if assignment and assignment.jetty_id else ""


def _source_assignment(snapshot: RecoveryInputSnapshot) -> Assignment | None:
    if snapshot.source_conflict_id and snapshot.source_conflict.trip_id:
        return _assignment_for_trip_id(snapshot.source_conflict.trip_id)
    if snapshot.source_override_id and snapshot.source_override.assignment_id:
        return Assignment.objects.filter(pk=snapshot.source_override.assignment_id).first()
    if snapshot.source_override_id and snapshot.source_override.trip_id:
        return _assignment_for_trip_id(snapshot.source_override.trip_id)
    if snapshot.source_tracking_alert_id and snapshot.source_tracking_alert.trip_id:
        return _assignment_for_trip_id(snapshot.source_tracking_alert.trip_id)
    if snapshot.source_operational_event_id:
        if snapshot.source_operational_event.assignment_id:
            return Assignment.objects.filter(pk=snapshot.source_operational_event.assignment_id).first()
        if snapshot.source_operational_event.trip_id:
            return _assignment_for_trip_id(snapshot.source_operational_event.trip_id)
    return None


def _assignment_for_trip_id(trip_id: int | None) -> Assignment | None:
    if trip_id is None:
        return None
    return (
        Assignment.objects.select_related("trip", "tug", "barge", "jetty", "cts")
        .filter(trip_id=trip_id)
        .first()
    )


def _replacement_resource_is_valid(
    *,
    action: RecoveryAction,
    asset_type: str,
    source_code: str,
    replacement_code: str,
) -> bool:
    if not replacement_code or replacement_code == source_code:
        return False
    if not _resource_is_active_available(asset_type=asset_type, resource_code=replacement_code):
        return False
    start, end = _action_interval(action)
    if start and end and _asset_window_overlaps(asset_type, replacement_code, start, end):
        return False
    if asset_type in {"barge", "tug"} and not _replacement_tug_barge_compatible(
        action=action,
        asset_type=asset_type,
        replacement_code=replacement_code,
    ):
        return False
    return True


def _resource_is_active_available(*, asset_type: str, resource_code: str) -> bool:
    if asset_type == "barge":
        return Barge.objects.filter(
            code=resource_code,
            is_active=True,
            status=Barge.Status.AVAILABLE,
        ).exists()
    if asset_type == "tug":
        return Tug.objects.filter(
            code=resource_code,
            is_active=True,
            status=Tug.Status.AVAILABLE,
        ).exists()
    if asset_type == "cts":
        return CTSAsset.objects.filter(
            code=resource_code,
            is_active=True,
            is_available=True,
        ).exists()
    return False


def _replacement_tug_barge_compatible(
    *,
    action: RecoveryAction,
    asset_type: str,
    replacement_code: str,
) -> bool:
    assignment = action.target_assignment
    if assignment is None:
        return True
    tug_code = replacement_code if asset_type == "tug" else assignment.tug.code if assignment.tug else ""
    barge_code = (
        replacement_code if asset_type == "barge" else assignment.barge.code if assignment.barge else ""
    )
    if not tug_code or not barge_code:
        return True
    return not AssetCompatibilityRule.objects.filter(
        rule_type=AssetCompatibilityRule.RuleType.TUG_BARGE,
        left_code=tug_code,
        right_code=barge_code,
        is_active=True,
        is_compatible=False,
    ).exists()


def _action_interval_avoids_asset_outage(
    *,
    snapshot: RecoveryInputSnapshot,
    action: RecoveryAction,
    asset_type: str,
    source_code: str,
) -> bool:
    start, end = _action_interval(action)
    if not (source_code and start and end):
        return False
    if not _source_asset_window_exists(snapshot=snapshot, asset_type=asset_type, source_code=source_code):
        return False
    return not _asset_window_overlaps(asset_type, source_code, start, end)


def _source_asset_window_exists(
    *,
    snapshot: RecoveryInputSnapshot,
    asset_type: str,
    source_code: str,
) -> bool:
    if AssetAvailabilityWindow.objects.filter(
        asset_type=asset_type,
        asset_code=source_code,
    ).exclude(status=AssetAvailabilityWindow.Status.AVAILABLE).exists():
        return True
    availability = snapshot.constraint_state.get("assetAvailability", [])
    if isinstance(availability, list):
        return any(
            isinstance(item, dict)
            and item.get("assetType") == asset_type
            and item.get("assetCode") == source_code
            and item.get("status") != AssetAvailabilityWindow.Status.AVAILABLE
            for item in availability
        )
    return False


def _asset_window_overlaps(asset_type: str, asset_code: str, start, end) -> bool:
    return AssetAvailabilityWindow.objects.filter(
        asset_type=asset_type,
        asset_code=asset_code,
        window_start__lt=end,
        window_end__gt=start,
    ).exclude(status=AssetAvailabilityWindow.Status.AVAILABLE).exists()


def _action_interval_avoids_jetty_overlap(
    *,
    action: RecoveryAction,
    jetty_code: str,
) -> bool:
    start, end = _action_interval(action)
    if not (jetty_code and start and end):
        return False
    jetty = Jetty.objects.filter(code=jetty_code).first()
    if jetty is None:
        return False
    has_source_window = JettyAvailabilityWindow.objects.filter(
        jetty=jetty,
    ).exclude(status=JettyAvailabilityWindow.Status.WORKING).exists()
    if not has_source_window:
        return False
    return not JettyAvailabilityWindow.objects.filter(
        jetty=jetty,
        window_start__lt=end,
        window_end__gt=start,
    ).exclude(status=JettyAvailabilityWindow.Status.WORKING).exists()


def _action_interval(action: RecoveryAction):
    start = _parse_state_dt(action.after_state.get("plannedDeparture"))
    end = _parse_state_dt(action.after_state.get("plannedArrival"))
    if start and end:
        return start, end
    if action.target_assignment_id:
        return action.target_assignment.planned_departure, action.target_assignment.planned_arrival
    return None, None


def _resource_code_from_action(action: RecoveryAction, asset_type: str) -> str:
    snake_key = f"{asset_type}_code"
    return str(
        action.after_state.get(asset_type)
        or action.after_state.get(snake_key)
        or action.metadata.get(asset_type)
        or action.metadata.get(snake_key)
        or ""
    )


def _operator_approved_mitigation(action: RecoveryAction) -> bool:
    metadata = action.metadata if isinstance(action.metadata, dict) else {}
    return bool(
        metadata.get("operatorApprovedMitigation")
        or metadata.get("explicitOperationalMitigation")
    )


def _is_assignment_repair_action(action: RecoveryAction) -> bool:
    if action.action_type in {
        *TIMING_ACTIONS,
        RecoveryAction.ActionType.REASSIGN_BARGE,
        RecoveryAction.ActionType.REASSIGN_TUG,
        RecoveryAction.ActionType.REASSIGN_CTS,
    }:
        return True
    checked = {
        str(value).lower()
        for value in (action.constraints_checked if isinstance(action.constraints_checked, list) else [])
    }
    return bool(checked.intersection({
        "asset_availability",
        "bridge_window_evaluated",
        "candidate_feasible",
        "cts_available",
        "cts_queue_overlap_review",
        "jetty_availability",
        "resource_availability",
        "tide_window_evaluated",
        "tug_barge_compatibility",
    }))


def _action_summary(action: RecoveryAction) -> dict[str, Any]:
    return {
        "actionId": action.action_id,
        "sequence": action.sequence,
        "actionType": action.action_type,
        "targetTrip": action.target_trip.trip_id if action.target_trip_id else "",
        "targetAssignment": action.target_assignment_id,
        "constraintsChecked": action.constraints_checked,
    }


def _resolution(action: RecoveryAction, kind: str, detail: str) -> dict[str, Any]:
    return {
        "kind": kind,
        "detail": detail,
        "actionId": action.action_id,
        "actionType": action.action_type,
        "targetTrip": action.target_trip.trip_id if action.target_trip_id else "",
        "targetAssignment": action.target_assignment_id,
    }


def _parse_state_dt(value: Any):
    if not value:
        return None
    if hasattr(value, "isoformat"):
        return value
    parsed = parse_datetime(str(value))
    if parsed and timezone.is_naive(parsed):
        return timezone.make_aware(parsed, timezone.get_current_timezone())
    return parsed


def _tide_or_bridge_from_snapshot(snapshot: RecoveryInputSnapshot) -> str:
    conflicts = snapshot.constraint_state.get("conflicts", [])
    if isinstance(conflicts, list):
        codes = [
            item.get("code")
            for item in conflicts
            if isinstance(item, dict) and item.get("code")
        ]
        if "BRIDGE_WINDOW_MISSED" in codes:
            return "BRIDGE_WINDOW_MISSED"
        if "TIDE_WINDOW_MISSED" in codes:
            return "TIDE_WINDOW_MISSED"
    return ""


def _iso(value) -> str:
    return value.isoformat() if value else ""
