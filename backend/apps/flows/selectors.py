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
    ScenarioConstraintEvaluation,
    RootCauseRepairAssessment,
    ScenarioRun,
    SimulationScenario,
)
from apps.scheduling.active_plan_selectors import (
    PUBLISH_CANDIDATE,
    WORKING_CANDIDATE,
    select_active_plan_version,
)
from apps.scheduling.publishability_services import (
    is_publishability_assessment_stale,
    latest_publishability_assessment,
    top_publishability_blocker,
)
from apps.scheduling.services import REQUIRED_APPROVAL_AUTHORITIES
from apps.telemetry.models import TrackingAlert

PASSING_ROOT_CAUSE_STATUSES = {
    RootCauseRepairAssessment.Status.ADDRESSES_CAUSE,
    RootCauseRepairAssessment.Status.MITIGATES_CAUSE,
}


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
        "approval_blocked_or_missing": _approval_blocked_or_missing,
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
        "root_cause_assessment_blocking": _root_cause_assessment_blocking,
        "scenario_run_succeeded": _scenario_run_succeeded,
        "scenario_run_missing": _scenario_run_missing,
        "scenario_run_critical_constraints_present": _scenario_run_critical_constraints_present,
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


def _metadata(flow_run) -> dict[str, Any]:
    metadata = getattr(flow_run, "metadata", {}) if flow_run else {}
    return metadata if isinstance(metadata, dict) else {}


def _bound_refs(flow_run) -> dict[str, Any]:
    refs = _metadata(flow_run).get("bound_refs", {})
    return refs if isinstance(refs, dict) else {}


def _requires_bound_refs(flow_run) -> bool:
    metadata = _metadata(flow_run)
    return bool(
        getattr(flow_run, "subject_type", "")
        or metadata.get("trial_pack")
        or metadata.get("evidence_run_id")
    )


def _bound_ref(flow_run, key: str):
    value = _bound_refs(flow_run).get(key)
    return value if value not in {None, ""} else None


def _bound_int(flow_run, key: str) -> int | None:
    value = _bound_ref(flow_run, key)
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


def _bound_or_subject_plan_version(flow_run) -> PlanVersion | None:
    plan_version_id = _bound_int(flow_run, "plan_version_id")
    if plan_version_id:
        return PlanVersion.objects.filter(pk=plan_version_id).first()
    if getattr(flow_run, "subject_type", "") == "plan_version":
        try:
            return PlanVersion.objects.filter(pk=int(flow_run.subject_id)).first()
        except (TypeError, ValueError):
            return None
    return None


def _active_plan_version(flow_run=None, mode: str = WORKING_CANDIDATE) -> PlanVersion | None:
    bound = _bound_or_subject_plan_version(flow_run)
    if bound:
        if mode == PUBLISH_CANDIDATE and bound.status not in {
            PlanVersion.Status.APPROVED,
            PlanVersion.Status.PUBLISHED,
        }:
            return None
        return bound
    if _requires_bound_refs(flow_run):
        return None
    return select_active_plan_version(mode)


def _approval_request(flow_run) -> ApprovalRequest | None:
    approval_request_id = _bound_int(flow_run, "approval_request_id")
    if approval_request_id:
        return ApprovalRequest.objects.filter(pk=approval_request_id).first()
    if _requires_bound_refs(flow_run):
        return None
    version = _active_plan_version(flow_run)
    queryset = ApprovalRequest.objects.all()
    if version:
        queryset = queryset.filter(plan_version=version)
    return queryset.order_by("-created_at", "-id").first()


def _publishability_assessment(flow_run, version: PlanVersion | None) -> PublishabilityAssessment | None:
    assessment_id = _bound_int(flow_run, "publishability_assessment_id")
    if assessment_id:
        queryset = PublishabilityAssessment.objects.filter(pk=assessment_id)
        if version:
            queryset = queryset.filter(plan_version=version)
        return queryset.first()
    if _requires_bound_refs(flow_run):
        return None
    return latest_publishability_assessment(version)


def _queryset_for_version_or_all(queryset, version: PlanVersion | None):
    return queryset.filter(plan_version=version) if version else queryset


def _demand_imported(flow_run, selector_name: str) -> SelectorResult:
    import_job_id = _bound_int(flow_run, "import_job_id")
    if import_job_id:
        import_job = ImportJob.objects.filter(
            pk=import_job_id,
            import_type=ImportJob.ImportType.OGV_DEMAND,
            status=ImportJob.Status.IMPORTED,
        ).first()
        demand_count = OGVVoyage.objects.exclude(status=OGVVoyage.Status.COMPLETED).count()
        completed = import_job is not None and demand_count > 0
        return SelectorResult(
            completed=completed,
            reason="" if completed else "Bound OGV demand import is no longer available.",
            evidence={"importJobId": import_job_id, "demandCount": demand_count},
        )
    if _requires_bound_refs(flow_run):
        return SelectorResult(reason="Bound OGV demand import evidence has not been recorded.")
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
    if _requires_bound_refs(flow_run) and _bound_or_subject_plan_version(flow_run) is None:
        return SelectorResult(reason="Bound plan version evidence has not been recorded.")
    version = _active_plan_version(flow_run)
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
    request = _approval_request(flow_run)
    version = request.plan_version if request else _active_plan_version(flow_run)
    blocking_count = _blocking_conflict_count(version)
    if blocking_count:
        return SelectorResult(
            reason=f"{blocking_count} blocking conflict(s) remain before approval submission.",
            evidence={
                "approvalRequestId": request.id if request else None,
                "blockingConflictCount": blocking_count,
            },
        )
    return SelectorResult(
        completed=request is not None,
        reason="" if request else "No approval request has been submitted.",
        evidence={
            "approvalRequestId": request.id if request else None,
            "blockingConflictCount": blocking_count,
        },
    )


def _approvals_complete(flow_run, selector_name: str) -> SelectorResult:
    request = _approval_request(flow_run)
    if request is None:
        return SelectorResult(reason="No approval request is available.")
    blocking_count = _blocking_conflict_count(request.plan_version)
    if blocking_count:
        return SelectorResult(
            reason=f"{blocking_count} blocking conflict(s) remain before approval.",
            evidence={
                "approvalRequestId": request.id,
                "blockingConflictCount": blocking_count,
            },
        )
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


def _approval_blocked_or_missing(flow_run, selector_name: str) -> SelectorResult:
    request = _approval_request(flow_run)
    version = request.plan_version if request else _active_plan_version(flow_run)
    blocking_count = _blocking_conflict_count(version)
    if blocking_count:
        return SelectorResult(
            blocked=True,
            reason=f"{blocking_count} blocking conflict(s) remain before approval.",
            evidence={
                "approvalRequestId": request.id if request else None,
                "blockingConflictCount": blocking_count,
            },
        )
    return _approval_missing(flow_run, selector_name)


def _plan_published(flow_run, selector_name: str) -> SelectorResult:
    snapshot_id = _bound_int(flow_run, "published_snapshot_id")
    if snapshot_id:
        snapshot = PublishedPlanSnapshot.objects.filter(
            pk=snapshot_id,
            status=PublishedPlanSnapshot.Status.ACTIVE,
        ).first()
        return SelectorResult(
            completed=snapshot is not None,
            reason="" if snapshot else "Bound published plan snapshot is no longer active.",
            evidence={"publishedSnapshotId": snapshot_id},
        )
    if _requires_bound_refs(flow_run):
        return SelectorResult(reason="Bound published snapshot evidence has not been recorded.")
    version = _active_plan_version(flow_run, PUBLISH_CANDIDATE)
    snapshot_queryset = PublishedPlanSnapshot.objects.filter(status=PublishedPlanSnapshot.Status.ACTIVE)
    if version:
        snapshot_queryset = snapshot_queryset.filter(plan_version=version)
    snapshot = (
        snapshot_queryset
        .order_by("-published_at", "-id")
        .first()
    )
    return SelectorResult(
        completed=snapshot is not None,
        reason="" if snapshot else "No active published plan snapshot exists.",
        evidence={"publishedSnapshotId": snapshot.id if snapshot else None},
    )


def _export_generated(flow_run, selector_name: str) -> SelectorResult:
    export_job_id = _bound_int(flow_run, "export_job_id")
    if export_job_id:
        export = ExportJob.objects.filter(
            pk=export_job_id,
            status=ExportJob.Status.GENERATED,
        ).first()
        return SelectorResult(
            completed=export is not None,
            reason="" if export else "Bound governed export is no longer generated.",
            evidence={"exportJobId": export_job_id},
        )
    if _requires_bound_refs(flow_run):
        return SelectorResult(reason="Bound governed export evidence has not been recorded.")
    version = _active_plan_version(flow_run, PUBLISH_CANDIDATE)
    export_queryset = ExportJob.objects.filter(status=ExportJob.Status.GENERATED)
    if version:
        export_queryset = export_queryset.filter(plan_version=version)
    export = (
        export_queryset
        .order_by("-created_at", "-id")
        .first()
    )
    return SelectorResult(
        completed=export is not None,
        reason="" if export else "No governed export has been generated.",
        evidence={"exportJobId": export.id if export else None},
    )


def _active_disruption_exists(flow_run, selector_name: str) -> SelectorResult:
    version = _active_plan_version(flow_run)
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
    snapshot_id = _bound_int(flow_run, "recovery_snapshot_id")
    optimizer_run_id = _bound_int(flow_run, "optimizer_run_id")
    if snapshot_id:
        snapshot = RecoveryInputSnapshot.objects.filter(pk=snapshot_id).first()
    elif _requires_bound_refs(flow_run):
        snapshot = None
    else:
        version = _active_plan_version(flow_run)
        snapshots = RecoveryInputSnapshot.objects.all()
        if version:
            snapshots = snapshots.filter(plan_version=version)
        snapshot = snapshots.order_by("-generated_at", "-id").first()
    if optimizer_run_id:
        run = OptimizerRun.objects.filter(pk=optimizer_run_id).first()
    elif _requires_bound_refs(flow_run):
        run = None
    else:
        runs = OptimizerRun.objects.all()
        if snapshot:
            runs = runs.filter(input_snapshot=snapshot)
        run = runs.order_by("-created_at", "-id").first()
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
    recommendations = RecoveryRecommendation.objects.exclude(
        status=RecoveryRecommendation.Status.DISMISSED,
    )
    optimizer_run_id = _bound_int(flow_run, "optimizer_run_id")
    if optimizer_run_id:
        recommendations = recommendations.filter(optimizer_run_id=optimizer_run_id)
    elif _requires_bound_refs(flow_run):
        recommendations = recommendations.none()
    count = recommendations.count()
    return SelectorResult(
        completed=count > 0,
        reason="" if count else "No active recovery recommendations are available.",
        evidence={"recommendationCount": count},
    )


def _recommendations_missing(flow_run, selector_name: str) -> SelectorResult:
    exists = _recommendations_exist(flow_run, selector_name)
    return SelectorResult(blocked=not exists.completed, reason=exists.reason, evidence=exists.evidence)


def _recommendation_materialized(flow_run, selector_name: str) -> SelectorResult:
    recommendation = _selected_recovery_recommendation(flow_run)
    if recommendation is not None and recommendation.scenario_id is None:
        recommendation = None
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
    completed = assessment is not None and assessment.status in PASSING_ROOT_CAUSE_STATUSES
    reason = ""
    if assessment is None:
        reason = "Root-cause repair assessment has not been recorded."
    elif not completed:
        reason = f"Root-cause repair assessment is {assessment.status}."
    return SelectorResult(
        completed=completed,
        reason=reason,
        evidence={
            "recommendationId": recommendation.id,
            "recommendationRef": recommendation.recommendation_id,
            "rootCauseAssessmentId": assessment.id if assessment else None,
            "rootCauseAssessmentStatus": assessment.status if assessment else "",
            "sourceCauseType": assessment.source_cause_type if assessment else "",
        },
    )


def _root_cause_assessment_blocking(flow_run, selector_name: str) -> SelectorResult:
    assessment = _root_cause_assessment_exists(flow_run, selector_name)
    status = assessment.evidence.get("rootCauseAssessmentStatus", "")
    blocked = bool(status and status not in PASSING_ROOT_CAUSE_STATUSES)
    return SelectorResult(
        blocked=blocked,
        reason=assessment.reason if blocked else "",
        evidence=assessment.evidence,
    )


def _selected_recovery_recommendation(flow_run) -> RecoveryRecommendation | None:
    recommendation_id = _bound_int(flow_run, "recommendation_id")
    if recommendation_id:
        return (
            RecoveryRecommendation.objects.exclude(status=RecoveryRecommendation.Status.DISMISSED)
            .filter(pk=recommendation_id)
            .first()
        )
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

    optimizer_run_id = _bound_int(flow_run, "optimizer_run_id")
    latest_run = (
        OptimizerRun.objects.filter(pk=optimizer_run_id).first()
        if optimizer_run_id
        else None if _requires_bound_refs(flow_run) else OptimizerRun.objects.order_by("-created_at", "-id").first()
    )
    if latest_run:
        recommendation = (
            RecoveryRecommendation.objects.filter(optimizer_run=latest_run)
            .exclude(status=RecoveryRecommendation.Status.DISMISSED)
            .order_by("rank", "id")
            .first()
        )
        if recommendation:
            return recommendation
    if _requires_bound_refs(flow_run):
        return None

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
    run = _selected_successful_scenario_run(flow_run)
    return SelectorResult(
        completed=run is not None,
        reason="" if run else "No successful scenario run is available.",
        evidence={"scenarioRunId": run.id if run else None},
    )


def _selected_successful_scenario_run(flow_run) -> ScenarioRun | None:
    scenario_id = _bound_int(flow_run, "scenario_id")
    if _requires_bound_refs(flow_run) and not scenario_id:
        return None
    if scenario_id:
        return (
            ScenarioRun.objects.filter(
                scenario_id=scenario_id,
                status=ScenarioRun.Status.SUCCEEDED,
            )
            .order_by("-completed_at", "-created_at", "-id")
            .first()
        )
    scenario_run_id = _bound_int(flow_run, "scenario_run_id")
    if scenario_run_id:
        return ScenarioRun.objects.filter(
            pk=scenario_run_id,
            status=ScenarioRun.Status.SUCCEEDED,
        ).first()
    return (
        ScenarioRun.objects.filter(status=ScenarioRun.Status.SUCCEEDED)
        .order_by("-completed_at", "-created_at", "-id")
        .first()
    )


def _scenario_run_missing(flow_run, selector_name: str) -> SelectorResult:
    succeeded = _scenario_run_succeeded(flow_run, selector_name)
    return SelectorResult(
        blocked=not succeeded.completed,
        reason=succeeded.reason,
        evidence=succeeded.evidence,
    )


def _scenario_run_critical_constraints_present(flow_run, selector_name: str) -> SelectorResult:
    run = _selected_successful_scenario_run(flow_run)
    if run is None:
        return SelectorResult()
    critical_count = run.constraint_evaluations.filter(
        severity=ScenarioConstraintEvaluation.Severity.CRITICAL,
    ).count()
    return SelectorResult(
        blocked=critical_count > 0,
        reason=(
            f"{critical_count} critical simulated constraint(s) remain before promotion."
            if critical_count
            else ""
        ),
        evidence={"scenarioRunId": run.id, "criticalConstraintCount": critical_count},
    )


def _scenario_promoted(flow_run, selector_name: str) -> SelectorResult:
    scenario_id = _bound_int(flow_run, "scenario_id")
    if not scenario_id and _requires_bound_refs(flow_run):
        return SelectorResult(reason="Bound scenario evidence has not been recorded.")
    scenarios = SimulationScenario.objects.filter(
        status=SimulationScenario.Status.PROPOSED,
        scenario_version__isnull=False,
    )
    if scenario_id:
        scenarios = scenarios.filter(pk=scenario_id)
    scenario = scenarios.order_by("-updated_at", "-id").first()
    return SelectorResult(
        completed=scenario is not None,
        reason="" if scenario else "No promoted scenario version is available.",
        evidence={
            "scenarioId": scenario.id if scenario else None,
            "scenarioVersionId": scenario.scenario_version_id if scenario else None,
        },
    )


def _blocking_conflicts_clear(flow_run, selector_name: str) -> SelectorResult:
    if _requires_bound_refs(flow_run) and _bound_or_subject_plan_version(flow_run) is None:
        return SelectorResult(reason="Bound plan version evidence has not been recorded.")
    version = _active_plan_version(flow_run)
    count = _blocking_conflict_count(version)
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


def _blocking_conflict_count(version: PlanVersion | None) -> int:
    if version is None:
        return 0
    return Conflict.objects.filter(
        plan_version=version,
        is_blocking=True,
        resolved_at__isnull=True,
    ).count()


def _publishability_assessment_clear(flow_run, selector_name: str) -> SelectorResult:
    if _requires_bound_refs(flow_run) and _bound_or_subject_plan_version(flow_run) is None:
        return SelectorResult(reason="Bound plan version evidence has not been recorded.")
    version = _active_plan_version(flow_run, PUBLISH_CANDIDATE)
    assessment = _publishability_assessment(flow_run, version)
    if version is None:
        return SelectorResult(reason="No active plan version is available.")
    if assessment is None:
        return SelectorResult(
            reason="Publishability assessment has not been recorded.",
            evidence={"planVersionId": version.id, "publishabilityAssessmentId": None},
        )
    stale = is_publishability_assessment_stale(assessment, version)
    completed = not stale and assessment.status in {
        PublishabilityAssessment.Status.PUBLISHABLE,
        PublishabilityAssessment.Status.WARNING,
    }
    return SelectorResult(
        completed=completed,
        reason=(
            ""
            if completed
            else (
                "Publishability assessment is stale."
                if stale
                else _publishability_blocked_reason(assessment)
            )
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
    if _requires_bound_refs(flow_run) and _bound_or_subject_plan_version(flow_run) is None:
        return SelectorResult(
            reason="Bound plan version evidence has not been recorded.",
            evidence={"planVersionId": None},
        )
    version = _active_plan_version(flow_run, PUBLISH_CANDIDATE)
    assessment = _publishability_assessment(flow_run, version)
    if version is None or assessment is None:
        return SelectorResult(
            reason="Publishability assessment has not been recorded.",
            evidence={"planVersionId": version.id if version else None},
        )
    stale = is_publishability_assessment_stale(assessment, version)
    blocked = stale or assessment.status == PublishabilityAssessment.Status.BLOCKED
    return SelectorResult(
        blocked=blocked,
        reason=(
            "Publishability assessment is stale."
            if stale
            else _publishability_blocked_reason(assessment) if blocked else ""
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


def _publishability_blocked_reason(assessment: PublishabilityAssessment) -> str:
    blocker = top_publishability_blocker(assessment)
    if isinstance(blocker, dict) and blocker.get("message"):
        return str(blocker["message"])
    return "Publishability assessment is blocked."
