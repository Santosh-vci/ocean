from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Q

from apps.audit.models import AuditEvent
from apps.flows.models import FlowStepRun
from apps.flows.services import FlowSubject, get_active_flow_run
from apps.operations.models import OperationalEventCandidate
from apps.planning.models import (
    BridgeWindow,
    CargoLayerStep,
    NavigationConstraintCheck,
    OGVVoyage,
    TideWindow,
)
from apps.rbac.models import UserRoleAssignment
from apps.rbac.services import permission_codes_for_user
from apps.scheduling.models import (
    ApprovalDecision,
    ApprovalRequest,
    Conflict,
    ExportJob,
    GlobalOptimizationRun,
    ImpactChainAssessment,
    MovementAssignmentCandidateRun,
    OptimizerRun,
    OverrideRequest,
    PlanVersion,
    PublishedPlanSnapshot,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    RootCauseRepairAssessment,
    ScenarioConstraintEvaluation,
    ScenarioRun,
    SimulationScenario,
)
from apps.scheduling.active_plan_selectors import (
    WORKING_CANDIDATE,
    select_active_plan_version as select_scheduling_active_plan_version,
)
from apps.scheduling.commercial_projection_services import (
    is_commercial_projection_stale,
    latest_commercial_projection_run,
)
from apps.scheduling.movement_assignment_services import (
    build_movement_assignment_input_summary,
)
from apps.scheduling.publishability_services import (
    is_publishability_assessment_stale,
    latest_publishability_assessment,
    resolver_action_for_publishability,
    top_publishability_blocker,
)
from apps.scheduling.services import REQUIRED_APPROVAL_AUTHORITIES
from apps.telemetry.models import TrackingAlert
from apps.telemetry.telemetry_trust_services import (
    latest_trust_assessment_summary,
)


@dataclass(slots=True)
class AssistantContext:
    user: AbstractBaseUser | None = None
    permissions: set[str] = field(default_factory=set)
    role_codes: set[str] = field(default_factory=set)
    mode: str = "assisted"
    route: str | None = None
    object_type: str | None = None
    object_id: str | None = None
    active_plan_version: PlanVersion | None = None
    active_plan_version_id: int | None = None
    active_plan_status: str | None = None
    validation_status: str | None = None
    active_plan_trip_count: int = 0
    active_plan_is_editable: bool = False
    source_inputs_changed: bool = False
    demand_count: int = 0
    cargo_layer_issue_count: int = 0
    tide_window_count: int = 0
    bridge_window_count: int = 0
    constraint_blocker_count: int = 0
    blocking_conflict_count: int = 0
    critical_conflict_count: int = 0
    warning_conflict_count: int = 0
    pending_approval_count: int = 0
    current_user_pending_approval_count: int = 0
    all_required_approvals_complete: bool = False
    published_snapshot_exists: bool = False
    latest_export_for_published_plan_exists: bool = False
    pending_event_candidate_count: int = 0
    high_confidence_event_candidate_count: int = 0
    noisy_event_candidate_count: int = 0
    stale_signal_alert_count: int = 0
    open_tracking_alert_count: int = 0
    active_override_risk_count: int = 0
    open_scenario_count: int = 0
    scenario_ready_to_run_count: int = 0
    simulated_scenario_count: int = 0
    promotable_scenario_count: int = 0
    latest_recovery_input_snapshot_id: int | None = None
    latest_optimizer_run_id: int | None = None
    latest_optimizer_run_status: str | None = None
    latest_optimizer_run_candidate_count: int = 0
    top_recovery_recommendation_id: int | None = None
    top_recovery_recommendation_ref: str = ""
    top_recovery_recommendation_status: str | None = None
    top_recovery_recommendation_scenario_id: int | None = None
    materialized_recovery_recommendation_count: int = 0
    dismissed_recovery_recommendation_count: int = 0
    proof_pack_available: bool = False
    recommendation_origin_scenario_id: int | None = None
    recommendation_origin_scenario_status: str | None = None
    top_recovery_root_cause_assessment_id: int | None = None
    top_recovery_root_cause_assessment_ref: str = ""
    top_recovery_root_cause_status: str | None = None
    top_recovery_root_cause_source_type: str = ""
    top_recovery_root_cause_residual_risk_count: int = 0
    publishability_assessment_id: int | None = None
    publishability_assessment_ref: str = ""
    publishability_status: str | None = None
    publishability_blocking_reason_count: int = 0
    publishability_warning_count: int = 0
    publishability_top_blocker: str = ""
    publishability_top_blocker_key: str = ""
    publishability_top_blocker_group: str = ""
    publishability_expected_resolver_action_id: str = ""
    publishability_is_stale: bool = True
    latest_global_optimization_run_id: int | None = None
    latest_global_optimization_run_ref: str = ""
    latest_global_optimization_candidate_id: int | None = None
    latest_global_optimization_candidate_ref: str = ""
    latest_global_optimization_candidate_count: int = 0
    latest_global_optimization_candidate_summary: str = ""
    movement_assignment_candidate_run_id: int | None = None
    movement_assignment_candidate_run_ref: str = ""
    movement_assignment_candidate_movement_count: int = 0
    movement_assignment_candidate_covered_count: int = 0
    movement_assignment_candidate_blocked_count: int = 0
    movement_assignment_candidate_is_stale: bool = True
    telemetry_trust_blocking_count: int = 0
    telemetry_trust_degraded_count: int = 0
    telemetry_trust_latest_assessment_id: int | None = None
    telemetry_trust_latest_assessment_ref: str = ""
    telemetry_trust_latest_status: str = ""
    telemetry_trust_profile_key: str = ""
    commercial_projection_run_id: int | None = None
    commercial_projection_run_ref: str = ""
    commercial_projection_status: str | None = None
    commercial_projection_count: int = 0
    commercial_projection_at_risk_count: int = 0
    commercial_projection_is_stale: bool = True
    recent_governed_mutation_count: int = 0
    active_flow_run_id: str = ""
    active_flow_key: str = ""
    active_flow_name: str = ""
    active_flow_status: str = ""
    current_flow_step_key: str = ""
    current_flow_step_label: str = ""
    current_flow_step_status: str = ""
    expected_flow_route: str = ""
    expected_flow_action_id: str = ""
    flow_blocked_reason: str = ""
    flow_checklist: list[dict[str, Any]] = field(default_factory=list)
    flow_trial_pack: str = ""
    flow_evidence_run_id: str = ""
    flow_expected_action_ids: list[str] = field(default_factory=list)


def select_user_permissions(user: AbstractBaseUser) -> set[str]:
    return permission_codes_for_user(user)


def select_user_role_codes(user: AbstractBaseUser) -> set[str]:
    if not user or not user.is_authenticated:
        return set()
    return set(
        UserRoleAssignment.objects.filter(
            user=user,
            is_active=True,
            role__is_active=True,
        ).values_list("role__code", flat=True)
    )


def select_active_plan_version(user: AbstractBaseUser | None = None) -> PlanVersion | None:
    return select_scheduling_active_plan_version(WORKING_CANDIDATE)


def select_planning_counts(
    user: AbstractBaseUser | None = None,
    active_plan_version: PlanVersion | None = None,
) -> dict[str, int]:
    local_issue_layer_ids = set(
        CargoLayerStep.objects.filter(
            Q(sequence_violation=True)
            | Q(status__in=[CargoLayerStep.Status.BLOCKED, CargoLayerStep.Status.QC_HOLD])
        ).values_list("id", flat=True)
    )

    return {
        "demand_count": OGVVoyage.objects.exclude(
            status=OGVVoyage.Status.COMPLETED,
        ).count(),
        "cargo_layer_issue_count": len(local_issue_layer_ids),
        "tide_window_count": TideWindow.objects.filter(is_active=True).count(),
        "bridge_window_count": BridgeWindow.objects.filter(is_active=True).count(),
        "constraint_blocker_count": NavigationConstraintCheck.objects.filter(
            status__in=[
                NavigationConstraintCheck.Status.MISSED,
                NavigationConstraintCheck.Status.WAITING,
            ]
        ).count(),
    }


def select_conflict_counts(
    user: AbstractBaseUser | None,
    active_plan_version: PlanVersion | None,
) -> dict[str, int]:
    if active_plan_version is None:
        return {
            "blocking_conflict_count": 0,
            "critical_conflict_count": 0,
            "warning_conflict_count": 0,
        }
    unresolved = Conflict.objects.filter(
        plan_version=active_plan_version,
        resolved_at__isnull=True,
    )
    return {
        "blocking_conflict_count": unresolved.filter(is_blocking=True).count(),
        "critical_conflict_count": unresolved.filter(
            severity=Conflict.Severity.CRITICAL,
        ).count(),
        "warning_conflict_count": unresolved.filter(
            severity=Conflict.Severity.WARNING,
        ).count(),
    }


def select_approval_status(
    user: AbstractBaseUser | None,
    active_plan_version: PlanVersion | None,
    role_codes: set[str] | None = None,
) -> dict[str, Any]:
    if active_plan_version is None:
        return {
            "pending_approval_count": 0,
            "current_user_pending_approval_count": 0,
            "all_required_approvals_complete": False,
        }
    pending_requests = ApprovalRequest.objects.filter(
        plan_version=active_plan_version,
        status=ApprovalRequest.Status.PENDING,
    ).prefetch_related("decisions")
    latest_request = (
        ApprovalRequest.objects.filter(plan_version=active_plan_version)
        .prefetch_related("decisions")
        .order_by("-created_at")
        .first()
    )
    pending_for_user = sum(
        _approval_request_pending_for_roles(request, role_codes or set())
        for request in pending_requests
    )
    return {
        "pending_approval_count": pending_requests.count(),
        "current_user_pending_approval_count": pending_for_user,
        "all_required_approvals_complete": (
            _required_approvals_complete(latest_request) if latest_request else False
        ),
    }


def select_export_status(
    user: AbstractBaseUser | None,
    active_plan_version: PlanVersion | None,
) -> dict[str, bool]:
    if active_plan_version is None:
        return {
            "published_snapshot_exists": False,
            "latest_export_for_published_plan_exists": False,
        }
    return {
        "published_snapshot_exists": PublishedPlanSnapshot.objects.filter(
            plan_version=active_plan_version,
            status=PublishedPlanSnapshot.Status.ACTIVE,
        ).exists(),
        "latest_export_for_published_plan_exists": ExportJob.objects.filter(
            plan_version=active_plan_version,
            export_type=ExportJob.ExportType.PLAN,
            status=ExportJob.Status.GENERATED,
        ).exists(),
    }


def select_event_candidate_counts(user: AbstractBaseUser | None = None) -> dict[str, int]:
    pending = OperationalEventCandidate.objects.filter(
        status=OperationalEventCandidate.Status.PENDING,
    )
    return {
        "pending_event_candidate_count": pending.count(),
        "high_confidence_event_candidate_count": pending.filter(
            confidence_score__gte=80,
        ).count(),
        "noisy_event_candidate_count": OperationalEventCandidate.objects.filter(
            status__in=[
                OperationalEventCandidate.Status.DUPLICATE,
                OperationalEventCandidate.Status.REJECTED,
            ],
        ).count(),
    }


def select_tracking_alert_counts(user: AbstractBaseUser | None = None) -> dict[str, int]:
    active_alerts = TrackingAlert.objects.filter(
        status__in=[
            TrackingAlert.Status.OPEN,
            TrackingAlert.Status.ACKNOWLEDGED,
        ],
    )
    return {
        "stale_signal_alert_count": active_alerts.filter(
            alert_type=TrackingAlert.AlertType.STALE_SIGNAL,
        ).count(),
        "open_tracking_alert_count": active_alerts.count(),
    }


def select_simulation_counts(
    user: AbstractBaseUser | None,
    active_plan_version: PlanVersion | None,
) -> dict[str, int]:
    if active_plan_version is None:
        return {
            "open_scenario_count": 0,
            "scenario_ready_to_run_count": 0,
            "simulated_scenario_count": 0,
            "promotable_scenario_count": 0,
        }
    scenario_versions = [active_plan_version.id]
    if active_plan_version.source_version_id:
        scenario_versions.append(active_plan_version.source_version_id)
    scenarios = SimulationScenario.objects.filter(
        Q(baseline_version_id__in=scenario_versions)
        | Q(scenario_version=active_plan_version)
    )
    simulated = scenarios.filter(status=SimulationScenario.Status.SIMULATED)
    promotable_count = 0
    for scenario in simulated:
        latest_run = (
            scenario.runs.filter(status=ScenarioRun.Status.SUCCEEDED)
            .order_by("-completed_at", "-created_at", "-id")
            .first()
        )
        if latest_run and not latest_run.constraint_evaluations.filter(
            severity=ScenarioConstraintEvaluation.Severity.CRITICAL,
        ).exists():
            promotable_count += 1

    return {
        "open_scenario_count": scenarios.exclude(
            status__in=[SimulationScenario.Status.PROPOSED, SimulationScenario.Status.CANCELED],
        ).count(),
        "scenario_ready_to_run_count": scenarios.filter(
            status=SimulationScenario.Status.DRAFT,
            assumptions__isnull=False,
        )
        .distinct()
        .count(),
        "simulated_scenario_count": simulated.count(),
        "promotable_scenario_count": promotable_count,
    }


def _int_object_id(object_id: str | int | None) -> int | None:
    if object_id is None:
        return None
    try:
        return int(object_id)
    except (TypeError, ValueError):
        return None


def select_phase5_recovery_status(
    user: AbstractBaseUser | None,
    active_plan_version: PlanVersion | None,
    object_type: str | None = None,
    object_id: str | int | None = None,
) -> dict[str, Any]:
    if active_plan_version is None:
        return {
            "latest_recovery_input_snapshot_id": None,
            "latest_optimizer_run_id": None,
            "latest_optimizer_run_status": None,
            "latest_optimizer_run_candidate_count": 0,
            "top_recovery_recommendation_id": None,
            "top_recovery_recommendation_ref": "",
            "top_recovery_recommendation_status": None,
            "top_recovery_recommendation_scenario_id": None,
            "materialized_recovery_recommendation_count": 0,
            "dismissed_recovery_recommendation_count": 0,
            "proof_pack_available": False,
            "recommendation_origin_scenario_id": None,
            "recommendation_origin_scenario_status": None,
            "top_recovery_root_cause_assessment_id": None,
            "top_recovery_root_cause_assessment_ref": "",
            "top_recovery_root_cause_status": None,
            "top_recovery_root_cause_source_type": "",
            "top_recovery_root_cause_residual_risk_count": 0,
        }

    recovery_plan_versions = [active_plan_version.id]
    if active_plan_version.source_version_id:
        recovery_plan_versions.append(active_plan_version.source_version_id)

    selected_id = _int_object_id(object_id)
    recommendations = RecoveryRecommendation.objects.filter(
        optimizer_run__plan_version_id__in=recovery_plan_versions,
    ).select_related(
        "scenario",
        "optimizer_run",
        "optimizer_run__input_snapshot",
        "root_cause_assessment",
    )

    selected_snapshot = None
    selected_run = None
    selected_recommendation = None
    selected_scenario = None

    if selected_id is not None and object_type == "recovery_input_snapshot":
        selected_snapshot = (
            RecoveryInputSnapshot.objects.filter(
                id=selected_id,
                plan_version_id__in=recovery_plan_versions,
            )
            .order_by("-generated_at", "-id")
            .first()
        )
    elif selected_id is not None and object_type == "optimizer_run":
        selected_run = (
            OptimizerRun.objects.filter(
                id=selected_id,
                plan_version_id__in=recovery_plan_versions,
            )
            .select_related("input_snapshot")
            .first()
        )
    elif selected_id is not None and object_type == "recovery_recommendation":
        selected_recommendation = recommendations.filter(id=selected_id).first()
    elif selected_id is not None and object_type == "simulation_scenario":
        selected_scenario = (
            SimulationScenario.objects.filter(
                Q(baseline_version_id__in=recovery_plan_versions)
                | Q(scenario_version_id__in=recovery_plan_versions),
                id=selected_id,
            )
            .order_by("-created_at", "-id")
            .first()
        )
        if selected_scenario:
            selected_recommendation = recommendations.filter(
                scenario=selected_scenario,
            ).first()

    if selected_recommendation:
        selected_run = selected_recommendation.optimizer_run
        selected_snapshot = selected_run.input_snapshot
    elif selected_run:
        selected_snapshot = selected_run.input_snapshot
    elif selected_snapshot:
        selected_run = (
            OptimizerRun.objects.filter(
                input_snapshot=selected_snapshot,
                plan_version_id__in=recovery_plan_versions,
            )
            .order_by("-created_at", "-id")
            .first()
        )

    latest_snapshot = selected_snapshot or (
        RecoveryInputSnapshot.objects.filter(plan_version_id__in=recovery_plan_versions)
        .order_by("-generated_at", "-id")
        .first()
    )
    latest_run = selected_run or (
        OptimizerRun.objects.filter(plan_version_id__in=recovery_plan_versions)
        .select_related("input_snapshot")
        .order_by("-created_at", "-id")
        .first()
    )

    if selected_recommendation:
        top_recommendation = selected_recommendation
    elif latest_run:
        top_recommendation = (
            recommendations.filter(optimizer_run=latest_run)
            .exclude(status=RecoveryRecommendation.Status.DISMISSED)
            .order_by("rank", "id")
            .first()
        )
    else:
        top_recommendation = (
            recommendations.exclude(status=RecoveryRecommendation.Status.DISMISSED)
            .order_by("-optimizer_run__created_at", "rank", "id")
            .first()
        )

    recommendation_scenario = selected_scenario if selected_recommendation else None
    if top_recommendation and top_recommendation.scenario_id:
        recommendation_scenario = top_recommendation.scenario
    root_cause_assessment = _root_cause_assessment(top_recommendation)

    return {
        "latest_recovery_input_snapshot_id": latest_snapshot.id if latest_snapshot else None,
        "latest_optimizer_run_id": latest_run.id if latest_run else None,
        "latest_optimizer_run_status": latest_run.status if latest_run else None,
        "latest_optimizer_run_candidate_count": (
            latest_run.recommendations.count() if latest_run else 0
        ),
        "top_recovery_recommendation_id": (
            top_recommendation.id if top_recommendation else None
        ),
        "top_recovery_recommendation_ref": (
            top_recommendation.recommendation_id if top_recommendation else ""
        ),
        "top_recovery_recommendation_status": (
            top_recommendation.status if top_recommendation else None
        ),
        "top_recovery_recommendation_scenario_id": (
            top_recommendation.scenario_id if top_recommendation else None
        ),
        "materialized_recovery_recommendation_count": recommendations.filter(
            status=RecoveryRecommendation.Status.MATERIALIZED,
        ).count(),
        "dismissed_recovery_recommendation_count": recommendations.filter(
            status=RecoveryRecommendation.Status.DISMISSED,
        ).count(),
        "proof_pack_available": bool(
            top_recommendation
            and top_recommendation.scenario_id
            and latest_run
            and latest_run.status == OptimizerRun.Status.SUCCEEDED
        ),
        "recommendation_origin_scenario_id": (
            recommendation_scenario.id if recommendation_scenario else None
        ),
        "recommendation_origin_scenario_status": (
            recommendation_scenario.status if recommendation_scenario else None
        ),
        "top_recovery_root_cause_assessment_id": (
            root_cause_assessment.id if root_cause_assessment else None
        ),
        "top_recovery_root_cause_assessment_ref": (
            root_cause_assessment.assessment_id if root_cause_assessment else ""
        ),
        "top_recovery_root_cause_status": (
            root_cause_assessment.status if root_cause_assessment else None
        ),
        "top_recovery_root_cause_source_type": (
            root_cause_assessment.source_cause_type if root_cause_assessment else ""
        ),
        "top_recovery_root_cause_residual_risk_count": (
            _residual_risk_count(root_cause_assessment.residual_risk)
            if root_cause_assessment
            else 0
        ),
    }


def _root_cause_assessment(
    recommendation: RecoveryRecommendation | None,
) -> RootCauseRepairAssessment | None:
    if recommendation is None:
        return None
    try:
        return recommendation.root_cause_assessment
    except RootCauseRepairAssessment.DoesNotExist:
        return None


def _residual_risk_count(residual_risk: dict[str, Any] | None) -> int:
    if not isinstance(residual_risk, dict):
        return 0
    raw_count = residual_risk.get("count")
    if isinstance(raw_count, int):
        return raw_count
    items = residual_risk.get("items")
    return len(items) if isinstance(items, list) else 0


def select_operational_actualization_risks(
    user: AbstractBaseUser | None,
    active_plan_version: PlanVersion | None,
) -> dict[str, int]:
    if active_plan_version is None:
        return {"active_override_risk_count": 0}
    return {
        "active_override_risk_count": ImpactChainAssessment.objects.filter(
            plan_version=active_plan_version,
            status=ImpactChainAssessment.Status.CRITICAL,
        ).count()
        + OverrideRequest.objects.filter(
            plan_version=active_plan_version,
            status=OverrideRequest.Status.PENDING,
        ).count()
    }


def select_publishability_status(
    user: AbstractBaseUser | None,
    active_plan_version: PlanVersion | None,
) -> dict[str, Any]:
    assessment = latest_publishability_assessment(active_plan_version)
    blocker = top_publishability_blocker(assessment)
    return {
        "publishability_assessment_id": assessment.id if assessment else None,
        "publishability_assessment_ref": assessment.assessment_id if assessment else "",
        "publishability_status": assessment.status if assessment else None,
        "publishability_blocking_reason_count": (
            assessment.blocking_reason_count if assessment else 0
        ),
        "publishability_warning_count": assessment.warning_count if assessment else 0,
        "publishability_top_blocker": (
            str(blocker.get("message") or "") if isinstance(blocker, dict) else ""
        ),
        "publishability_top_blocker_key": (
            str(blocker.get("key") or "") if isinstance(blocker, dict) else ""
        ),
        "publishability_top_blocker_group": (
            str(blocker.get("group") or "") if isinstance(blocker, dict) else ""
        ),
        "publishability_expected_resolver_action_id": (
            resolver_action_for_publishability(assessment) if assessment else ""
        ),
        "publishability_is_stale": is_publishability_assessment_stale(
            assessment,
            active_plan_version,
        ),
    }


def select_global_optimizer_status(
    user: AbstractBaseUser | None,
    active_plan_version: PlanVersion | None,
) -> dict[str, Any]:
    if active_plan_version is None:
        return {
            "latest_global_optimization_run_id": None,
            "latest_global_optimization_run_ref": "",
            "latest_global_optimization_candidate_id": None,
            "latest_global_optimization_candidate_ref": "",
            "latest_global_optimization_candidate_count": 0,
            "latest_global_optimization_candidate_summary": "",
        }

    plan_version_ids = [active_plan_version.id]
    if active_plan_version.source_version_id:
        plan_version_ids.append(active_plan_version.source_version_id)
    run = (
        GlobalOptimizationRun.objects.filter(
            plan_version_id__in=plan_version_ids,
            status=GlobalOptimizationRun.Status.SUCCEEDED,
        )
        .prefetch_related("candidates")
        .order_by("-created_at", "-id")
        .first()
    )
    candidate = (
        run.candidates.order_by("rank", "id").first() if run else None
    )
    return {
        "latest_global_optimization_run_id": run.id if run else None,
        "latest_global_optimization_run_ref": run.run_id if run else "",
        "latest_global_optimization_candidate_id": candidate.id if candidate else None,
        "latest_global_optimization_candidate_ref": (
            candidate.candidate_id if candidate else ""
        ),
        "latest_global_optimization_candidate_count": (
            run.candidates.count() if run else 0
        ),
        "latest_global_optimization_candidate_summary": candidate.summary if candidate else "",
    }


def select_movement_assignment_candidate_status(
    user: AbstractBaseUser | None,
    active_plan_version: PlanVersion | None,
) -> dict[str, Any]:
    if active_plan_version is None:
        return {
            "movement_assignment_candidate_run_id": None,
            "movement_assignment_candidate_run_ref": "",
            "movement_assignment_candidate_movement_count": 0,
            "movement_assignment_candidate_covered_count": 0,
            "movement_assignment_candidate_blocked_count": 0,
            "movement_assignment_candidate_is_stale": True,
        }
    run = (
        MovementAssignmentCandidateRun.objects.filter(
            plan_version=active_plan_version,
            status=MovementAssignmentCandidateRun.Status.SUCCEEDED,
        )
        .prefetch_related("candidates")
        .order_by("-created_at", "-id")
        .first()
    )
    if run is None:
        return {
            "movement_assignment_candidate_run_id": None,
            "movement_assignment_candidate_run_ref": "",
            "movement_assignment_candidate_movement_count": 0,
            "movement_assignment_candidate_covered_count": 0,
            "movement_assignment_candidate_blocked_count": 0,
            "movement_assignment_candidate_is_stale": True,
        }
    expected_signature_payload = build_movement_assignment_input_summary(active_plan_version)
    metadata = run.metadata if isinstance(run.metadata, dict) else {}
    return {
        "movement_assignment_candidate_run_id": run.id,
        "movement_assignment_candidate_run_ref": run.run_id,
        "movement_assignment_candidate_movement_count": int(metadata.get("movementCount") or 0),
        "movement_assignment_candidate_covered_count": int(
            metadata.get("coveredMovementCount") or 0
        ),
        "movement_assignment_candidate_blocked_count": int(
            metadata.get("blockedCandidateCount") or 0
        ),
        "movement_assignment_candidate_is_stale": (
            sorted(expected_signature_payload.get("cargoLayerStepIds", []))
            != sorted(run.input_summary.get("cargoLayerStepIds", []))
            if isinstance(run.input_summary, dict)
            else True
        ),
    }


def select_telemetry_trust_status(
    user: AbstractBaseUser | None,
    active_plan_version: PlanVersion | None,
) -> dict[str, Any]:
    summary = latest_trust_assessment_summary(active_plan_version)
    latest = (
        sorted(summary.latest_assessments, key=lambda item: (item.assessed_at, item.id))[-1]
        if summary.latest_assessments
        else None
    )
    return {
        "telemetry_trust_blocking_count": summary.blocking_count,
        "telemetry_trust_degraded_count": summary.degraded_count,
        "telemetry_trust_latest_assessment_id": latest.id if latest else None,
        "telemetry_trust_latest_assessment_ref": latest.assessment_id if latest else "",
        "telemetry_trust_latest_status": latest.trust_status if latest else "",
        "telemetry_trust_profile_key": summary.profile_key,
    }


def select_commercial_projection_status(
    user: AbstractBaseUser | None,
    active_plan_version: PlanVersion | None,
) -> dict[str, Any]:
    run = latest_commercial_projection_run(active_plan_version)
    projections = list(run.projections.all()) if run else []
    at_risk = [
        projection
        for projection in projections
        if projection.status in {"at_risk", "blocked"}
    ]
    return {
        "commercial_projection_run_id": run.id if run else None,
        "commercial_projection_run_ref": run.run_id if run else "",
        "commercial_projection_status": run.status if run else None,
        "commercial_projection_count": len(projections),
        "commercial_projection_at_risk_count": len(at_risk),
        "commercial_projection_is_stale": is_commercial_projection_stale(
            run,
            active_plan_version,
        ),
    }


def select_recent_audit_counts(user: AbstractBaseUser | None = None) -> dict[str, int]:
    governed_prefixes = (
        "approval.",
        "export.",
        "recovery.",
        "simulation.",
        "phase5.",
        "global_optimizer.",
    )
    query = Q()
    for prefix in governed_prefixes:
        query |= Q(action__startswith=prefix)
    return {"recent_governed_mutation_count": AuditEvent.objects.filter(query).count()}


def select_flow_status(
    user: AbstractBaseUser | None,
    object_type: str | None = None,
    object_id: str | int | None = None,
) -> dict[str, Any]:
    if not user or not user.is_authenticated:
        return _empty_flow_status()

    subject = (
        FlowSubject(subject_type=object_type, subject_id=str(object_id))
        if object_type and object_id is not None
        else None
    )
    flow_run = get_active_flow_run(user, subject=subject)
    if flow_run is None:
        return _empty_flow_status()

    ordered_steps = list(flow_run.step_runs.order_by("sequence"))
    definition_steps = {
        step.get("step_key"): step
        for step in flow_run.flow_definition.steps
        if isinstance(step, dict)
    }
    current_step = _current_flow_step(flow_run.current_step_key, ordered_steps)
    current_definition = (
        definition_steps.get(current_step.step_key, {}) if current_step else {}
    )
    metadata = flow_run.metadata if isinstance(flow_run.metadata, dict) else {}
    expected_action_ids = metadata.get("expected_action_ids")

    return {
        "active_flow_run_id": flow_run.run_id,
        "active_flow_key": flow_run.flow_definition.flow_key,
        "active_flow_name": flow_run.flow_definition.name,
        "active_flow_status": flow_run.status,
        "current_flow_step_key": current_step.step_key if current_step else "",
        "current_flow_step_label": str(current_definition.get("label", "")),
        "current_flow_step_status": current_step.status if current_step else "",
        "expected_flow_route": current_step.expected_route if current_step else "",
        "expected_flow_action_id": current_step.expected_action_id if current_step else "",
        "flow_blocked_reason": current_step.blocked_reason if current_step else "",
        "flow_checklist": [
            _flow_checklist_item(step_run, definition_steps.get(step_run.step_key, {}))
            for step_run in ordered_steps
        ],
        "flow_trial_pack": str(metadata.get("trial_pack") or ""),
        "flow_evidence_run_id": str(metadata.get("evidence_run_id") or ""),
        "flow_expected_action_ids": [
            str(action_id)
            for action_id in expected_action_ids
            if action_id
        ]
        if isinstance(expected_action_ids, list)
        else [],
    }


def build_assistant_context(
    user: AbstractBaseUser,
    route: str | None = None,
    object_type: str | None = None,
    object_id: str | int | None = None,
    mode: str = "assisted",
) -> AssistantContext:
    permissions = select_user_permissions(user)
    role_codes = select_user_role_codes(user)
    active_plan_version = select_active_plan_version(user)
    planning_counts = select_planning_counts(user, active_plan_version)
    conflict_counts = select_conflict_counts(user, active_plan_version)
    approval_status = select_approval_status(user, active_plan_version, role_codes)
    export_status = select_export_status(user, active_plan_version)
    event_counts = select_event_candidate_counts(user)
    tracking_counts = select_tracking_alert_counts(user)
    simulation_counts = select_simulation_counts(user, active_plan_version)
    phase5_status = select_phase5_recovery_status(
        user,
        active_plan_version,
        object_type=object_type,
        object_id=object_id,
    )
    operational_risks = select_operational_actualization_risks(user, active_plan_version)
    publishability_status = select_publishability_status(user, active_plan_version)
    global_optimizer_status = select_global_optimizer_status(user, active_plan_version)
    movement_assignment_candidate_status = select_movement_assignment_candidate_status(
        user,
        active_plan_version,
    )
    telemetry_trust_status = select_telemetry_trust_status(user, active_plan_version)
    commercial_projection_status = select_commercial_projection_status(user, active_plan_version)
    audit_counts = select_recent_audit_counts(user)
    flow_status = select_flow_status(
        user,
        object_type=object_type,
        object_id=object_id,
    )

    active_plan_trip_count = active_plan_version.trips.count() if active_plan_version else 0
    active_plan_status = active_plan_version.status if active_plan_version else None
    active_plan_is_editable = active_plan_status in {
        PlanVersion.Status.DRAFT,
        PlanVersion.Status.GENERATED,
        PlanVersion.Status.VALIDATED,
        PlanVersion.Status.PROPOSED,
    }
    source_inputs_changed = bool(
        active_plan_version
        and isinstance(active_plan_version.summary, dict)
        and active_plan_version.summary.get("sourceInputsChanged")
    )

    return AssistantContext(
        user=user,
        permissions=permissions,
        role_codes=role_codes,
        mode=mode or "assisted",
        route=route,
        object_type=object_type,
        object_id=str(object_id) if object_id is not None else None,
        active_plan_version=active_plan_version,
        active_plan_version_id=active_plan_version.id if active_plan_version else None,
        active_plan_status=active_plan_status,
        validation_status=(
            active_plan_version.validation_status if active_plan_version else None
        ),
        active_plan_trip_count=active_plan_trip_count,
        active_plan_is_editable=active_plan_is_editable,
        source_inputs_changed=source_inputs_changed,
        **planning_counts,
        **conflict_counts,
        **approval_status,
        **export_status,
        **event_counts,
        **tracking_counts,
        **simulation_counts,
        **phase5_status,
        **operational_risks,
        **publishability_status,
        **global_optimizer_status,
        **movement_assignment_candidate_status,
        **telemetry_trust_status,
        **commercial_projection_status,
        **audit_counts,
        **flow_status,
    )


def _empty_flow_status() -> dict[str, Any]:
    return {
        "active_flow_run_id": "",
        "active_flow_key": "",
        "active_flow_name": "",
        "active_flow_status": "",
        "current_flow_step_key": "",
        "current_flow_step_label": "",
        "current_flow_step_status": "",
        "expected_flow_route": "",
        "expected_flow_action_id": "",
        "flow_blocked_reason": "",
        "flow_checklist": [],
        "flow_trial_pack": "",
        "flow_evidence_run_id": "",
        "flow_expected_action_ids": [],
    }


def _current_flow_step(
    current_step_key: str,
    ordered_steps: list[FlowStepRun],
) -> FlowStepRun | None:
    if current_step_key:
        for step_run in ordered_steps:
            if step_run.step_key == current_step_key:
                return step_run
    for step_run in ordered_steps:
        if step_run.status in {FlowStepRun.Status.ACTIVE, FlowStepRun.Status.BLOCKED}:
            return step_run
    return None


def _flow_checklist_item(
    step_run: FlowStepRun,
    definition_step: dict[str, Any],
) -> dict[str, Any]:
    payload = {
        "key": step_run.step_key,
        "label": str(definition_step.get("label") or step_run.step_key.replace("_", " ").title()),
        "status": _flow_checklist_status(step_run.status),
        "action_id": step_run.expected_action_id,
        "route": step_run.expected_route,
    }
    if step_run.blocked_reason:
        payload["reason"] = step_run.blocked_reason
    return payload


def _flow_checklist_status(status: str) -> str:
    if status == FlowStepRun.Status.COMPLETED:
        return "complete"
    if status == FlowStepRun.Status.BLOCKED:
        return "blocked"
    if status == FlowStepRun.Status.ACTIVE:
        return "current"
    return "pending"


def _approval_request_pending_for_roles(
    approval_request: ApprovalRequest,
    role_codes: set[str],
) -> bool:
    authority = _preferred_authority_for_roles(role_codes)
    decided_authorities = set(
        approval_request.decisions.values_list("authority_role", flat=True)
    )
    required_authorities = set(
        approval_request.required_authorities or REQUIRED_APPROVAL_AUTHORITIES,
    )
    if authority:
        return authority in required_authorities and authority not in decided_authorities
    return bool(required_authorities - decided_authorities)


def _preferred_authority_for_roles(role_codes: set[str]) -> str | None:
    if "berau-scheduler" in role_codes:
        return ApprovalDecision.AuthorityRole.BERAU_SCHEDULER
    if "abl-dispatcher" in role_codes:
        return ApprovalDecision.AuthorityRole.ABL_DISPATCHER
    if "joint-control-tower-manager" in role_codes:
        return ApprovalDecision.AuthorityRole.JOINT_CONTROL
    return None


def _required_approvals_complete(approval_request: ApprovalRequest) -> bool:
    approved_roles = set(
        approval_request.decisions.filter(
            decision=ApprovalDecision.Decision.APPROVE,
        ).values_list("authority_role", flat=True)
    )
    return set(approval_request.required_authorities or REQUIRED_APPROVAL_AUTHORITIES).issubset(
        approved_roles
    )
