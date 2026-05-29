from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from apps.planning.models import BridgeWindow, CargoLayerStep, ImportJob, OGVVoyage, TideWindow
from apps.scheduling.models import (
    ApprovalDecision,
    ApprovalRequest,
    Conflict,
    ExportJob,
    OptimizerRun,
    PlanVersion,
    PublishedPlanSnapshot,
    PublishabilityAssessment,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    RootCauseRepairAssessment,
    ScenarioRun,
    SimulationScenario,
)
from apps.scheduling.publishability_services import (
    latest_publishability_assessment,
    top_publishability_blocker,
)
from apps.scheduling.services import REQUIRED_APPROVAL_AUTHORITIES
from apps.telemetry.models import TrackingAlert


@dataclass(slots=True)
class SelectorResult:
    completed: bool = False
    blocked: bool = False
    reason: str = ""
    evidence: dict[str, Any] = field(default_factory=dict)


def evaluate_selector(selector_name: str, flow_run=None) -> SelectorResult:
    selectors = {
        "none": _none,
        "demand_imported": _demand_imported,
        "cargo_sequence_clear": _cargo_sequence_clear,
        "cargo_sequence_blocked": _cargo_sequence_blocked,
        "operating_windows_entered": _operating_windows_entered,
        "plan_generated": _plan_generated,
        "approval_submitted": _approval_submitted,
        "approvals_complete": _approvals_complete,
        "approval_missing": _approval_missing,
        "plan_published": _plan_published,
        "export_generated": _export_generated,
        "active_disruption_exists": _active_disruption_exists,
        "no_active_disruption": _no_active_disruption,
        "recovery_snapshot_and_run_exists": _recovery_snapshot_and_run_exists,
        "recovery_run_missing": _recovery_run_missing,
        "recommendations_exist": _recommendations_exist,
        "recommendations_missing": _recommendations_missing,
        "recommendation_materialized": _recommendation_materialized,
        "scenario_missing": _scenario_missing,
        "root_cause_assessment_exists": _root_cause_assessment_exists,
        "scenario_run_succeeded": _scenario_run_succeeded,
        "scenario_run_missing": _scenario_run_missing,
        "scenario_promoted": _scenario_promoted,
        "blocking_conflicts_clear": _blocking_conflicts_clear,
        "blocking_conflicts_present": _blocking_conflicts_present,
        "publishability_assessment_clear": _publishability_assessment_clear,
        "publishability_assessment_blocked": _publishability_assessment_blocked,
    }
    evaluator = selectors.get(selector_name, _unknown_selector)
    return evaluator(flow_run, selector_name)


def _none(flow_run, selector_name: str) -> SelectorResult:
    return SelectorResult()


def _unknown_selector(flow_run, selector_name: str) -> SelectorResult:
    return SelectorResult(reason=f"Selector '{selector_name}' is not registered.")


def _active_plan_version() -> PlanVersion | None:
    return (
        PlanVersion.objects.filter(status=PlanVersion.Status.APPROVED)
        .order_by("-created_at", "-id")
        .first()
        or PlanVersion.objects.filter(
            status__in=[
                PlanVersion.Status.DRAFT,
                PlanVersion.Status.GENERATED,
                PlanVersion.Status.VALIDATED,
                PlanVersion.Status.PROPOSED,
            ]
        )
        .order_by("-created_at", "-id")
        .first()
        or PlanVersion.objects.order_by("-generated_at", "-created_at", "-id").first()
    )


def _demand_imported(flow_run, selector_name: str) -> SelectorResult:
    demand_count = OGVVoyage.objects.exclude(status=OGVVoyage.Status.COMPLETED).count()
    import_job = (
        ImportJob.objects.filter(
            import_type=ImportJob.ImportType.OGV_DEMAND,
            status=ImportJob.Status.IMPORTED,
        )
        .order_by("-created_at", "-id")
        .first()
    )
    completed = demand_count > 0 and import_job is not None
    return SelectorResult(
        completed=completed,
        reason="" if completed else "Imported OGV demand is not available.",
        evidence={
            "demandCount": demand_count,
            "importJobId": import_job.id if import_job else None,
        },
    )


def _cargo_sequence_clear(flow_run, selector_name: str) -> SelectorResult:
    issue_count = _cargo_issue_count()
    return SelectorResult(
        completed=issue_count == 0,
        reason="" if issue_count == 0 else f"{issue_count} cargo layer issue(s) remain.",
        evidence={"cargoLayerIssueCount": issue_count},
    )


def _cargo_sequence_blocked(flow_run, selector_name: str) -> SelectorResult:
    issue_count = _cargo_issue_count()
    return SelectorResult(
        blocked=issue_count > 0,
        reason=f"{issue_count} cargo layer issue(s) block planning." if issue_count else "",
        evidence={"cargoLayerIssueCount": issue_count},
    )


def _cargo_issue_count() -> int:
    return CargoLayerStep.objects.filter(
        sequence_violation=True,
    ).count() + CargoLayerStep.objects.filter(
        status__in=[CargoLayerStep.Status.BLOCKED, CargoLayerStep.Status.QC_HOLD],
    ).count()


def _operating_windows_entered(flow_run, selector_name: str) -> SelectorResult:
    tide_count = TideWindow.objects.filter(is_active=True).count()
    bridge_count = BridgeWindow.objects.filter(is_active=True).count()
    completed = tide_count > 0 and bridge_count > 0
    return SelectorResult(
        completed=completed,
        reason="" if completed else "Active tide and bridge windows are required.",
        evidence={"tideWindowCount": tide_count, "bridgeWindowCount": bridge_count},
    )


def _plan_generated(flow_run, selector_name: str) -> SelectorResult:
    version = _active_plan_version()
    trip_count = version.trips.count() if version else 0
    completed = bool(version and trip_count > 0)
    return SelectorResult(
        completed=completed,
        reason="" if completed else "A generated plan with trips is not available.",
        evidence={
            "planVersionId": version.id if version else None,
            "tripCount": trip_count,
        },
    )


def _approval_submitted(flow_run, selector_name: str) -> SelectorResult:
    request = ApprovalRequest.objects.order_by("-created_at", "-id").first()
    return SelectorResult(
        completed=request is not None,
        reason="" if request else "No approval request has been submitted.",
        evidence={"approvalRequestId": request.id if request else None},
    )


def _approvals_complete(flow_run, selector_name: str) -> SelectorResult:
    request = ApprovalRequest.objects.order_by("-created_at", "-id").first()
    if request is None:
        return SelectorResult(reason="No approval request is available.")
    approved_roles = set(
        request.decisions.filter(decision=ApprovalDecision.Decision.APPROVE).values_list(
            "authority_role",
            flat=True,
        )
    )
    required_roles = set(request.required_authorities or REQUIRED_APPROVAL_AUTHORITIES)
    missing_roles = sorted(required_roles - approved_roles)
    return SelectorResult(
        completed=not missing_roles,
        reason="" if not missing_roles else "Required approval decisions are incomplete.",
        evidence={
            "approvalRequestId": request.id,
            "approvedRoles": sorted(approved_roles),
            "missingRoles": missing_roles,
        },
    )


def _approval_missing(flow_run, selector_name: str) -> SelectorResult:
    complete = _approvals_complete(flow_run, selector_name)
    return SelectorResult(
        blocked=not complete.completed,
        reason=complete.reason or "Required approvals are incomplete.",
        evidence=complete.evidence,
    )


def _plan_published(flow_run, selector_name: str) -> SelectorResult:
    snapshot = (
        PublishedPlanSnapshot.objects.filter(status=PublishedPlanSnapshot.Status.ACTIVE)
        .order_by("-published_at", "-id")
        .first()
    )
    return SelectorResult(
        completed=snapshot is not None,
        reason="" if snapshot else "No active published plan snapshot exists.",
        evidence={"publishedSnapshotId": snapshot.id if snapshot else None},
    )


def _export_generated(flow_run, selector_name: str) -> SelectorResult:
    export = (
        ExportJob.objects.filter(status=ExportJob.Status.GENERATED)
        .order_by("-created_at", "-id")
        .first()
    )
    return SelectorResult(
        completed=export is not None,
        reason="" if export else "No governed export has been generated.",
        evidence={"exportJobId": export.id if export else None},
    )


def _active_disruption_exists(flow_run, selector_name: str) -> SelectorResult:
    version = _active_plan_version()
    conflict_count = (
        Conflict.objects.filter(plan_version=version, resolved_at__isnull=True).count()
        if version
        else 0
    )
    alert_count = TrackingAlert.objects.filter(
        status__in=[TrackingAlert.Status.OPEN, TrackingAlert.Status.ACKNOWLEDGED],
    ).count()
    completed = conflict_count + alert_count > 0
    return SelectorResult(
        completed=completed,
        reason="" if completed else "No active disruption is available for recovery.",
        evidence={"openConflictCount": conflict_count, "openTrackingAlertCount": alert_count},
    )


def _no_active_disruption(flow_run, selector_name: str) -> SelectorResult:
    active = _active_disruption_exists(flow_run, selector_name)
    return SelectorResult(
        blocked=not active.completed,
        reason=active.reason,
        evidence=active.evidence,
    )


def _recovery_snapshot_and_run_exists(flow_run, selector_name: str) -> SelectorResult:
    snapshot = RecoveryInputSnapshot.objects.order_by("-generated_at", "-id").first()
    run = OptimizerRun.objects.order_by("-created_at", "-id").first()
    completed = snapshot is not None and run is not None
    return SelectorResult(
        completed=completed,
        reason="" if completed else "Recovery input snapshot and optimizer run are required.",
        evidence={
            "snapshotId": snapshot.id if snapshot else None,
            "optimizerRunId": run.id if run else None,
        },
    )


def _recovery_run_missing(flow_run, selector_name: str) -> SelectorResult:
    exists = _recovery_snapshot_and_run_exists(flow_run, selector_name)
    return SelectorResult(blocked=not exists.completed, reason=exists.reason, evidence=exists.evidence)


def _recommendations_exist(flow_run, selector_name: str) -> SelectorResult:
    count = RecoveryRecommendation.objects.exclude(
        status=RecoveryRecommendation.Status.DISMISSED,
    ).count()
    return SelectorResult(
        completed=count > 0,
        reason="" if count else "No active recovery recommendations are available.",
        evidence={"recommendationCount": count},
    )


def _recommendations_missing(flow_run, selector_name: str) -> SelectorResult:
    exists = _recommendations_exist(flow_run, selector_name)
    return SelectorResult(blocked=not exists.completed, reason=exists.reason, evidence=exists.evidence)


def _recommendation_materialized(flow_run, selector_name: str) -> SelectorResult:
    recommendation = (
        RecoveryRecommendation.objects.filter(scenario__isnull=False)
        .order_by("-updated_at", "-id")
        .first()
    )
    return SelectorResult(
        completed=recommendation is not None,
        reason="" if recommendation else "No recovery recommendation has been materialized.",
        evidence={
            "recommendationId": recommendation.id if recommendation else None,
            "scenarioId": recommendation.scenario_id if recommendation else None,
        },
    )


def _root_cause_assessment_exists(flow_run, selector_name: str) -> SelectorResult:
    recommendation = _selected_recovery_recommendation(flow_run)
    if recommendation is None:
        return SelectorResult(reason="No active recovery recommendation is available.")
    assessment = RootCauseRepairAssessment.objects.filter(
        recommendation=recommendation,
    ).first()
    completed = assessment is not None
    return SelectorResult(
        completed=completed,
        reason="" if completed else "Root-cause repair assessment has not been recorded.",
        evidence={
            "recommendationId": recommendation.id,
            "recommendationRef": recommendation.recommendation_id,
            "rootCauseAssessmentId": assessment.id if assessment else None,
            "rootCauseAssessmentStatus": assessment.status if assessment else "",
            "sourceCauseType": assessment.source_cause_type if assessment else "",
        },
    )


def _selected_recovery_recommendation(flow_run) -> RecoveryRecommendation | None:
    subject_type = getattr(flow_run, "subject_type", "") if flow_run else ""
    subject_id = getattr(flow_run, "subject_id", "") if flow_run else ""
    if subject_type == "recovery_recommendation" and subject_id:
        try:
            return RecoveryRecommendation.objects.exclude(
                status=RecoveryRecommendation.Status.DISMISSED,
            ).get(pk=int(subject_id))
        except (RecoveryRecommendation.DoesNotExist, TypeError, ValueError):
            return None

    metadata = getattr(flow_run, "metadata", {}) if flow_run else {}
    selected_id = metadata.get("selected_recommendation_id") if isinstance(metadata, dict) else None
    if selected_id:
        try:
            return RecoveryRecommendation.objects.exclude(
                status=RecoveryRecommendation.Status.DISMISSED,
            ).get(pk=int(selected_id))
        except (RecoveryRecommendation.DoesNotExist, TypeError, ValueError):
            pass

    latest_run = OptimizerRun.objects.order_by("-created_at", "-id").first()
    if latest_run:
        recommendation = (
            RecoveryRecommendation.objects.filter(optimizer_run=latest_run)
            .exclude(status=RecoveryRecommendation.Status.DISMISSED)
            .order_by("rank", "id")
            .first()
        )
        if recommendation:
            return recommendation

    return (
        RecoveryRecommendation.objects.exclude(status=RecoveryRecommendation.Status.DISMISSED)
        .order_by("-optimizer_run__created_at", "rank", "id")
        .first()
    )


def _scenario_missing(flow_run, selector_name: str) -> SelectorResult:
    materialized = _recommendation_materialized(flow_run, selector_name)
    return SelectorResult(
        blocked=not materialized.completed,
        reason=materialized.reason,
        evidence=materialized.evidence,
    )


def _scenario_run_succeeded(flow_run, selector_name: str) -> SelectorResult:
    run = (
        ScenarioRun.objects.filter(status=ScenarioRun.Status.SUCCEEDED)
        .order_by("-completed_at", "-created_at", "-id")
        .first()
    )
    return SelectorResult(
        completed=run is not None,
        reason="" if run else "No successful scenario run is available.",
        evidence={"scenarioRunId": run.id if run else None},
    )


def _scenario_run_missing(flow_run, selector_name: str) -> SelectorResult:
    succeeded = _scenario_run_succeeded(flow_run, selector_name)
    return SelectorResult(
        blocked=not succeeded.completed,
        reason=succeeded.reason,
        evidence=succeeded.evidence,
    )


def _scenario_promoted(flow_run, selector_name: str) -> SelectorResult:
    scenario = (
        SimulationScenario.objects.filter(
            status=SimulationScenario.Status.PROPOSED,
            scenario_version__isnull=False,
        )
        .order_by("-updated_at", "-id")
        .first()
    )
    return SelectorResult(
        completed=scenario is not None,
        reason="" if scenario else "No promoted scenario version is available.",
        evidence={
            "scenarioId": scenario.id if scenario else None,
            "scenarioVersionId": scenario.scenario_version_id if scenario else None,
        },
    )


def _blocking_conflicts_clear(flow_run, selector_name: str) -> SelectorResult:
    version = _active_plan_version()
    count = (
        Conflict.objects.filter(
            plan_version=version,
            is_blocking=True,
            resolved_at__isnull=True,
        ).count()
        if version
        else 0
    )
    return SelectorResult(
        completed=count == 0,
        reason="" if count == 0 else f"{count} blocking conflict(s) remain.",
        evidence={"blockingConflictCount": count},
    )


def _blocking_conflicts_present(flow_run, selector_name: str) -> SelectorResult:
    clear = _blocking_conflicts_clear(flow_run, selector_name)
    return SelectorResult(
        blocked=not clear.completed,
        reason=clear.reason,
        evidence=clear.evidence,
    )


def _publishability_assessment_clear(flow_run, selector_name: str) -> SelectorResult:
    version = _active_plan_version()
    assessment = latest_publishability_assessment(version)
    if version is None:
        return SelectorResult(reason="No active plan version is available.")
    if assessment is None:
        return SelectorResult(
            reason="Publishability assessment has not been recorded.",
            evidence={"planVersionId": version.id, "publishabilityAssessmentId": None},
        )
    completed = assessment.status in {
        PublishabilityAssessment.Status.PUBLISHABLE,
        PublishabilityAssessment.Status.WARNING,
    }
    return SelectorResult(
        completed=completed,
        reason=(
            ""
            if completed
            else _publishability_blocked_reason(assessment)
        ),
        evidence={
            "planVersionId": version.id,
            "publishabilityAssessmentId": assessment.id,
            "publishabilityAssessmentRef": assessment.assessment_id,
            "publishabilityStatus": assessment.status,
            "blockingReasonCount": assessment.blocking_reason_count,
            "warningCount": assessment.warning_count,
        },
    )


def _publishability_assessment_blocked(flow_run, selector_name: str) -> SelectorResult:
    version = _active_plan_version()
    assessment = latest_publishability_assessment(version)
    if version is None or assessment is None:
        return SelectorResult(
            reason="Publishability assessment has not been recorded.",
            evidence={"planVersionId": version.id if version else None},
        )
    blocked = assessment.status == PublishabilityAssessment.Status.BLOCKED
    return SelectorResult(
        blocked=blocked,
        reason=_publishability_blocked_reason(assessment) if blocked else "",
        evidence={
            "planVersionId": version.id,
            "publishabilityAssessmentId": assessment.id,
            "publishabilityAssessmentRef": assessment.assessment_id,
            "publishabilityStatus": assessment.status,
            "blockingReasonCount": assessment.blocking_reason_count,
            "warningCount": assessment.warning_count,
        },
    )


def _publishability_blocked_reason(assessment: PublishabilityAssessment) -> str:
    blocker = top_publishability_blocker(assessment)
    if isinstance(blocker, dict) and blocker.get("message"):
        return str(blocker["message"])
    return "Publishability assessment is blocked."
