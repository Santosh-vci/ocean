from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from django.contrib.auth.models import AbstractBaseUser
from django.db.models import Count, F, Q

from apps.audit.models import AuditEvent
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
    ImpactChainAssessment,
    OptimizerRun,
    OverrideRequest,
    PlanVersion,
    PublishedPlanSnapshot,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    ScenarioRun,
    SimulationScenario,
)
from apps.scheduling.services import REQUIRED_APPROVAL_AUTHORITIES
from apps.telemetry.models import TrackingAlert


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
    recent_governed_mutation_count: int = 0


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
    queryset = PlanVersion.objects.select_related(
        "plan",
        "created_by",
        "source_version",
    ).annotate(
        open_blockers=Count(
            "conflicts",
            filter=Q(conflicts__is_blocking=True, conflicts__resolved_at__isnull=True),
        )
    )
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
        "simulated_scenario_count": scenarios.filter(
            status=SimulationScenario.Status.SIMULATED,
        ).count(),
        "promotable_scenario_count": scenarios.filter(
            status=SimulationScenario.Status.SIMULATED,
            runs__status=ScenarioRun.Status.SUCCEEDED,
        )
        .distinct()
        .count(),
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
        }

    recovery_plan_versions = [active_plan_version.id]
    if active_plan_version.source_version_id:
        recovery_plan_versions.append(active_plan_version.source_version_id)

    selected_id = _int_object_id(object_id)
    recommendations = RecoveryRecommendation.objects.filter(
        optimizer_run__plan_version_id__in=recovery_plan_versions,
    ).select_related("scenario", "optimizer_run", "optimizer_run__input_snapshot")

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
    }


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


def select_recent_audit_counts(user: AbstractBaseUser | None = None) -> dict[str, int]:
    governed_prefixes = (
        "approval.",
        "export.",
        "recovery.",
        "simulation.",
        "phase5.",
    )
    query = Q()
    for prefix in governed_prefixes:
        query |= Q(action__startswith=prefix)
    return {"recent_governed_mutation_count": AuditEvent.objects.filter(query).count()}


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
    audit_counts = select_recent_audit_counts(user)

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
        **audit_counts,
    )


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
