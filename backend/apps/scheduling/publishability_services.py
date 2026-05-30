from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db.models import Max, Q
from django.utils import timezone

from apps.planning.models import BridgeWindow, CargoLayerStep, TideWindow
from apps.telemetry.models import TrackingAlert
from apps.telemetry.telemetry_trust_services import (
    latest_trust_assessments_for_plan,
    trust_assessment_is_blocking,
)

from .models import (
    ApprovalDecision,
    ApprovalRequest,
    Conflict,
    PlanVersion,
    PublishabilityAssessment,
    RecoveryRecommendation,
    RootCauseRepairAssessment,
)
from .recovery_lineage import recommendation_for_plan_version, recovery_origin_from_summary

PUBLISHABILITY_ALGORITHM_VERSION = "phase6.4-publishability-gate"

_PASS = "clear"
_WARNING = "warning"
_BLOCKED = "blocked"
_NOT_APPLICABLE = "not_applicable"


@dataclass(frozen=True, slots=True)
class PublishabilityPayload:
    status: str
    blocking_reason_count: int
    warning_count: int
    approval_status: str
    conflict_status: str
    telemetry_status: str
    cargo_sequence_status: str
    operating_window_status: str
    recommendation_origin_status: str
    details: list[dict[str, Any]]


def latest_publishability_assessment(
    plan_version: PlanVersion | None,
) -> PublishabilityAssessment | None:
    if plan_version is None:
        return None
    return (
        PublishabilityAssessment.objects.filter(plan_version=plan_version)
        .select_related("plan_version", "checked_by")
        .order_by("-checked_at", "-id")
        .first()
    )


def is_publishability_assessment_stale(
    assessment: PublishabilityAssessment | None,
    plan_version: PlanVersion | None,
) -> bool:
    if assessment is None or plan_version is None:
        return True
    return assessment.checked_at < _latest_publishability_input_time(plan_version)


def top_publishability_blocker(
    assessment: PublishabilityAssessment | None,
) -> dict[str, Any] | None:
    if assessment is None:
        return None
    details = assessment.details if isinstance(assessment.details, list) else []
    for detail in details:
        if isinstance(detail, dict) and detail.get("status") == _BLOCKED:
            return detail
    return None


def resolver_action_for_publishability(
    assessment: PublishabilityAssessment | None,
) -> str:
    blocker = top_publishability_blocker(assessment)
    if not blocker:
        return "RUN_PUBLISHABILITY_CHECK"
    return _resolver_action_for_detail(blocker)


def assess_plan_publishability(
    plan_version: PlanVersion,
    actor=None,
    *,
    persist: bool = True,
) -> PublishabilityAssessment | PublishabilityPayload:
    details: list[dict[str, Any]] = []
    details.extend(_approval_details(plan_version))
    details.extend(_conflict_details(plan_version))
    details.extend(_cargo_sequence_details(plan_version))
    details.extend(_operating_window_details())
    details.extend(_stale_source_details(plan_version))
    details.extend(_recommendation_origin_details(plan_version))
    details.extend(_telemetry_details(plan_version))

    payload = _payload_from_details(details)
    if not persist:
        return payload

    return PublishabilityAssessment.objects.create(
        plan_version=plan_version,
        status=payload.status,
        blocking_reason_count=payload.blocking_reason_count,
        warning_count=payload.warning_count,
        approval_status=payload.approval_status,
        conflict_status=payload.conflict_status,
        telemetry_status=payload.telemetry_status,
        cargo_sequence_status=payload.cargo_sequence_status,
        operating_window_status=payload.operating_window_status,
        recommendation_origin_status=payload.recommendation_origin_status,
        checked_at=timezone.now(),
        checked_by=actor if actor is not None and getattr(actor, "is_authenticated", True) else None,
        algorithm_version=PUBLISHABILITY_ALGORITHM_VERSION,
        details=details,
    )


def _payload_from_details(details: list[dict[str, Any]]) -> PublishabilityPayload:
    blocking_count = sum(1 for detail in details if detail.get("status") == _BLOCKED)
    warning_count = sum(1 for detail in details if detail.get("status") == _WARNING)
    if blocking_count:
        status = PublishabilityAssessment.Status.BLOCKED
    elif warning_count:
        status = PublishabilityAssessment.Status.WARNING
    else:
        status = PublishabilityAssessment.Status.PUBLISHABLE

    return PublishabilityPayload(
        status=status,
        blocking_reason_count=blocking_count,
        warning_count=warning_count,
        approval_status=_group_status(details, "approval"),
        conflict_status=_group_status(details, "conflict"),
        telemetry_status=_group_status(details, "telemetry"),
        cargo_sequence_status=_group_status(details, "cargo_sequence"),
        operating_window_status=_group_status(details, "operating_window"),
        recommendation_origin_status=_group_status(details, "recommendation_origin"),
        details=details,
    )


def _group_status(details: list[dict[str, Any]], group: str) -> str:
    group_details = [detail for detail in details if detail.get("group") == group]
    if not group_details:
        return _NOT_APPLICABLE
    statuses = {str(detail.get("status") or "") for detail in group_details}
    if _BLOCKED in statuses:
        return _BLOCKED
    if _WARNING in statuses:
        return _WARNING
    if _PASS in statuses:
        return _PASS
    return _NOT_APPLICABLE


def _detail(
    key: str,
    group: str,
    status: str,
    message: str,
    *,
    action_id: str = "",
    evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "key": key,
        "group": group,
        "status": status,
        "severity": "critical" if status == _BLOCKED else status,
        "message": message,
        "actionId": action_id,
        "evidence": evidence or {},
    }


def _approval_details(plan_version: PlanVersion) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    if plan_version.status != PlanVersion.Status.APPROVED:
        details.append(
            _detail(
                "plan_version_approved",
                "approval",
                _BLOCKED,
                "Plan version must be approved before manual publish.",
                action_id="APPROVE_PLAN",
                evidence={"planVersionStatus": plan_version.status},
            )
        )
    else:
        details.append(
            _detail(
                "plan_version_approved",
                "approval",
                _PASS,
                "Plan version is approved.",
                evidence={"planVersionStatus": plan_version.status},
            )
        )

    approval_request = (
        plan_version.approval_requests.filter(
            status__in=[ApprovalRequest.Status.APPROVED, ApprovalRequest.Status.PUBLISHED],
        )
        .prefetch_related("decisions")
        .order_by("-created_at", "-id")
        .first()
    )
    if approval_request is None:
        pending = (
            plan_version.approval_requests.filter(status=ApprovalRequest.Status.PENDING)
            .order_by("-created_at", "-id")
            .first()
        )
        details.append(
            _detail(
                "required_approvals_complete",
                "approval",
                _BLOCKED,
                "Required Berau and ABL approval decisions are incomplete.",
                action_id="APPROVE_PLAN" if pending else "SUBMIT_APPROVAL",
                evidence={"approvalRequestId": pending.id if pending else None},
            )
        )
        return details

    approved_roles = set(
        approval_request.decisions.filter(decision=ApprovalDecision.Decision.APPROVE)
        .values_list("authority_role", flat=True)
    )
    required_roles = set(
        approval_request.required_authorities
        or [
            ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
            ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
        ]
    )
    missing_roles = sorted(required_roles - approved_roles)
    details.append(
        _detail(
            "required_approvals_complete",
            "approval",
            _BLOCKED if missing_roles else _PASS,
            (
                "Required Berau and ABL approval decisions are incomplete."
                if missing_roles
                else "Required approval decisions are complete."
            ),
            action_id="APPROVE_PLAN" if missing_roles else "",
            evidence={
                "approvalRequestId": approval_request.id,
                "requestStatus": approval_request.status,
                "approvedRoles": sorted(approved_roles),
                "missingRoles": missing_roles,
            },
        )
    )
    return details


def _conflict_details(plan_version: PlanVersion) -> list[dict[str, Any]]:
    unresolved = Conflict.objects.filter(plan_version=plan_version, resolved_at__isnull=True)
    blocking_count = unresolved.filter(is_blocking=True).count()
    critical_count = unresolved.filter(severity=Conflict.Severity.CRITICAL).count()
    warning_count = unresolved.filter(severity=Conflict.Severity.WARNING).count()
    details = [
        _detail(
            "blocking_or_critical_conflicts_clear",
            "conflict",
            _BLOCKED if blocking_count or critical_count else _PASS,
            (
                "Unresolved blocking or critical conflicts remain."
                if blocking_count or critical_count
                else "No unresolved blocking or critical conflicts remain."
            ),
            action_id="OPEN_EXCEPTION_CENTER" if blocking_count or critical_count else "",
            evidence={
                "blockingConflictCount": blocking_count,
                "criticalConflictCount": critical_count,
            },
        )
    ]
    if warning_count:
        details.append(
            _detail(
                "warning_conflicts_reviewed",
                "conflict",
                _WARNING,
                "Unresolved warning conflicts remain visible for manual publish judgment.",
                action_id="OPEN_EXCEPTION_CENTER",
                evidence={"warningConflictCount": warning_count},
            )
        )
    return details


def _cargo_sequence_details(plan_version: PlanVersion) -> list[dict[str, Any]]:
    layer_ids = plan_version.trips.exclude(cargo_layer_step__isnull=True).values_list(
        "cargo_layer_step_id",
        flat=True,
    )
    issue_count = CargoLayerStep.objects.filter(
        Q(sequence_violation=True)
        | Q(status__in=[CargoLayerStep.Status.BLOCKED, CargoLayerStep.Status.QC_HOLD]),
        id__in=layer_ids,
    ).count()
    return [
        _detail(
            "cargo_sequence_clear",
            "cargo_sequence",
            _BLOCKED if issue_count else _PASS,
            (
                "Active plan trips include blocking cargo sequence issues."
                if issue_count
                else "Active plan trips have no blocking cargo sequence issues."
            ),
            action_id="REVIEW_COAL_SEQUENCE" if issue_count else "",
            evidence={"cargoLayerIssueCount": issue_count},
        )
    ]


def _operating_window_details() -> list[dict[str, Any]]:
    tide_count = TideWindow.objects.filter(is_active=True).exclude(
        risk_level=TideWindow.RiskLevel.CLOSED,
    ).count()
    bridge_count = BridgeWindow.objects.filter(is_active=True).exclude(
        status=BridgeWindow.Status.CLOSED,
    ).count()
    missing = []
    if tide_count == 0:
        missing.append("tide")
    if bridge_count == 0:
        missing.append("bridge")
    return [
        _detail(
            "active_operating_windows_exist",
            "operating_window",
            _BLOCKED if missing else _PASS,
            (
                "Active tide and bridge windows are required before publish."
                if missing
                else "Active tide and bridge windows are available."
            ),
            action_id="ENTER_OPERATING_WINDOWS" if missing else "",
            evidence={
                "tideWindowCount": tide_count,
                "bridgeWindowCount": bridge_count,
                "missing": missing,
            },
        )
    ]


def _stale_source_details(plan_version: PlanVersion) -> list[dict[str, Any]]:
    source_inputs_changed = bool(
        isinstance(plan_version.summary, dict)
        and plan_version.summary.get("sourceInputsChanged")
    )
    return [
        _detail(
            "source_inputs_current",
            "conflict",
            _BLOCKED if source_inputs_changed else _PASS,
            (
                "Source inputs changed after this plan version was generated."
                if source_inputs_changed
                else "No stale source-input marker is present."
            ),
            action_id="REGENERATE_PLAN" if source_inputs_changed else "",
            evidence={"sourceInputsChanged": source_inputs_changed},
        )
    ]


def _recommendation_origin_details(plan_version: PlanVersion) -> list[dict[str, Any]]:
    recommendation, origin = recommendation_for_plan_version(plan_version)
    if not origin:
        return [
            _detail(
                "recommendation_origin_root_cause",
                "recommendation_origin",
                _PASS,
                "Plan version is not a promoted recovery-origin candidate.",
                evidence={"recoveryOrigin": False},
            )
        ]

    if recommendation is None:
        return [
            _detail(
                "recommendation_origin_root_cause",
                "recommendation_origin",
                _BLOCKED,
                "Recovery-origin plan has no linked recommendation for root-cause validation.",
                action_id="VALIDATE_ROOT_CAUSE_REPAIR",
                evidence={"recoveryOrigin": True, **origin},
            )
        ]

    try:
        assessment = recommendation.root_cause_assessment
    except RootCauseRepairAssessment.DoesNotExist:
        return [
            _detail(
                "recommendation_origin_root_cause",
                "recommendation_origin",
                _BLOCKED,
                "Recovery-origin recommendation requires root-cause validation before publish.",
                action_id="VALIDATE_ROOT_CAUSE_REPAIR",
                evidence={
                    "recoveryOrigin": True,
                    "recommendationId": recommendation.id,
                    "recommendationRef": recommendation.recommendation_id,
                },
            )
        ]

    if assessment.status == RootCauseRepairAssessment.Status.ADDRESSES_CAUSE:
        status = _PASS
        message = "Recovery-origin root cause is addressed."
    elif assessment.status == RootCauseRepairAssessment.Status.MITIGATES_CAUSE:
        status = _WARNING
        message = "Recovery-origin root cause is mitigated with residual risk."
    else:
        status = _BLOCKED
        message = "Recovery-origin root cause remains unresolved or unknown."

    return [
        _detail(
            "recommendation_origin_root_cause",
            "recommendation_origin",
            status,
            message,
            action_id=(
                "VALIDATE_ROOT_CAUSE_REPAIR"
                if status in {_BLOCKED, _WARNING}
                else ""
            ),
            evidence={
                "recoveryOrigin": True,
                **origin,
                "recommendationId": recommendation.id,
                "recommendationRef": recommendation.recommendation_id,
                "rootCauseAssessmentId": assessment.id,
                "rootCauseAssessmentRef": assessment.assessment_id,
                "rootCauseStatus": assessment.status,
                "sourceCauseType": assessment.source_cause_type,
                "residualRisk": assessment.residual_risk,
            },
        )
    ]


def _telemetry_details(plan_version: PlanVersion) -> list[dict[str, Any]]:
    trust_details = _telemetry_trust_details(plan_version)
    if any(detail.get("status") == _BLOCKED for detail in trust_details):
        return trust_details

    alerts = TrackingAlert.objects.filter(trip__plan_version=plan_version).exclude(
        status__in=[
            TrackingAlert.Status.RESOLVED,
            TrackingAlert.Status.DISMISSED,
            TrackingAlert.Status.CONVERTED_TO_SCENARIO,
        ],
    )
    blocking_alerts = []
    warning_alerts = []
    for alert in alerts:
        if _alert_is_acknowledged_non_blocking(alert):
            warning_alerts.append(alert)
            continue
        if alert.severity in {
            TrackingAlert.Severity.CRITICAL,
            TrackingAlert.Severity.WARNING,
        }:
            blocking_alerts.append(alert)
        else:
            warning_alerts.append(alert)

    if blocking_alerts:
        return trust_details + [
            _detail(
                "telemetry_alerts_clear",
                "telemetry",
                _BLOCKED,
                "Unresolved critical or warning telemetry alerts remain.",
                action_id="REVIEW_SIGNAL_HEALTH",
                evidence={
                    "blockingAlertCount": len(blocking_alerts),
                    "alertRefs": [alert.alert_id for alert in blocking_alerts[:5]],
                },
            )
        ]
    if warning_alerts:
        return trust_details + [
            _detail(
                "telemetry_alerts_clear",
                "telemetry",
                _WARNING,
                "Telemetry alerts are acknowledged as non-blocking or informational.",
                action_id="REVIEW_SIGNAL_HEALTH",
                evidence={
                    "warningAlertCount": len(warning_alerts),
                    "alertRefs": [alert.alert_id for alert in warning_alerts[:5]],
                },
            )
        ]
    return [
        *trust_details,
        _detail(
            "telemetry_alerts_clear",
            "telemetry",
            _PASS,
            "No unresolved telemetry alerts block publication.",
            evidence={"blockingAlertCount": 0},
        )
    ]


def _telemetry_trust_details(plan_version: PlanVersion) -> list[dict[str, Any]]:
    assessments = latest_trust_assessments_for_plan(plan_version)
    if not assessments:
        return []

    blocking = [assessment for assessment in assessments if trust_assessment_is_blocking(assessment)]
    degraded = [
        assessment
        for assessment in assessments
        if assessment.trust_status == "degraded"
    ]
    if blocking:
        return [
            _detail(
                "telemetry_trust_clear",
                "telemetry",
                _BLOCKED,
                "Telemetry trust requires quarantine or manual confirmation review.",
                action_id="REVIEW_TELEMETRY_TRUST_STATE",
                evidence={
                    "blockingTrustCount": len(blocking),
                    "assessmentRefs": [
                        assessment.assessment_id for assessment in blocking[:5]
                    ],
                    "statuses": sorted({assessment.trust_status for assessment in blocking}),
                },
            )
        ]
    if degraded:
        return [
            _detail(
                "telemetry_trust_clear",
                "telemetry",
                _WARNING,
                "Telemetry trust is degraded and remains visible for manual publish judgment.",
                action_id="REVIEW_TELEMETRY_TRUST_STATE",
                evidence={
                    "degradedTrustCount": len(degraded),
                    "assessmentRefs": [
                        assessment.assessment_id for assessment in degraded[:5]
                    ],
                },
            )
        ]
    return [
        _detail(
            "telemetry_trust_clear",
            "telemetry",
            _PASS,
            "Latest telemetry trust assessments are clear.",
            evidence={"assessmentCount": len(assessments)},
        )
    ]


def _alert_is_acknowledged_non_blocking(alert: TrackingAlert) -> bool:
    if alert.status != TrackingAlert.Status.ACKNOWLEDGED:
        return False
    evidence = alert.evidence if isinstance(alert.evidence, dict) else {}
    return bool(
        evidence.get("non_blocking")
        or evidence.get("acknowledged_as_non_blocking")
        or evidence.get("publishability") == "non_blocking"
    )


def _resolver_action_for_detail(detail: dict[str, Any]) -> str:
    explicit = detail.get("actionId")
    if isinstance(explicit, str) and explicit:
        if explicit == "APPROVE_PLAN" and detail.get("key") == "required_approvals_complete":
            return "APPROVE_PLAN"
        return explicit
    group = detail.get("group")
    if group == "approval":
        return "APPROVE_PLAN"
    if group == "conflict":
        return "OPEN_EXCEPTION_CENTER"
    if group == "cargo_sequence":
        return "REVIEW_COAL_SEQUENCE"
    if group == "operating_window":
        return "ENTER_OPERATING_WINDOWS"
    if group == "recommendation_origin":
        return "VALIDATE_ROOT_CAUSE_REPAIR"
    if group == "telemetry":
        key = detail.get("key")
        if key == "telemetry_trust_clear":
            return "REVIEW_TELEMETRY_TRUST_STATE"
        return "REVIEW_SIGNAL_HEALTH"
    return "RUN_PUBLISHABILITY_CHECK"


def _latest_publishability_input_time(plan_version: PlanVersion):
    timestamps = [plan_version.generated_at or plan_version.created_at]
    if isinstance(plan_version.summary, dict) and plan_version.summary.get("sourceInputsChanged"):
        timestamps.append(plan_version.updated_at)
    origin = recovery_origin_from_summary(plan_version.summary)
    scenario_pk = origin.get("scenarioPk")
    recommendation_pk = origin.get("recommendationPk")
    timestamps.extend(
        value
        for value in [
            Conflict.objects.filter(plan_version=plan_version).aggregate(value=Max("created_at"))[
                "value"
            ],
            ApprovalRequest.objects.filter(plan_version=plan_version)
            .exclude(status=ApprovalRequest.Status.PUBLISHED)
            .aggregate(
                value=Max("updated_at")
            )["value"],
            plan_version.trips.aggregate(value=Max("updated_at"))["value"],
            TrackingAlert.objects.filter(trip__plan_version=plan_version).aggregate(
                value=Max("updated_at")
            )["value"],
            (
                max(
                    (
                        assessment.assessed_at
                        for assessment in latest_trust_assessments_for_plan(plan_version)
                    ),
                    default=None,
                )
            ),
            (
                RootCauseRepairAssessment.objects.filter(
                    Q(recommendation_id=recommendation_pk)
                    | Q(recommendation__scenario_id=scenario_pk),
                ).aggregate(value=Max("updated_at"))["value"]
                if scenario_pk or recommendation_pk
                else None
            ),
        ]
        if value is not None
    )
    return max(timestamps)
