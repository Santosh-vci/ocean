from __future__ import annotations

import hashlib
import json
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.db.models import Count, F, Q, Sum
from django.utils import timezone

from apps.masters.models import Barge, CTSAsset, Jetty, Tug
from apps.operations.models import ConfirmedOperationalEvent
from apps.planning.models import (
    AssetAvailabilityWindow,
    BridgeWindow,
    CargoLayerStep,
    JettyAvailabilityWindow,
    OGVVoyage,
    TideWindow,
)
from apps.telemetry.models import TrackingAlert

from .models import (
    Assignment,
    Conflict,
    GlobalObjectiveProfile,
    GlobalOptimizationCandidate,
    GlobalOptimizationRun,
    PlanVersion,
    Trip,
)

GLOBAL_OPTIMIZER_ALGORITHM_VERSION = "phase6.5-global-optimizer-scaffold"
DEFAULT_PROFILE_KEY = "global_optimizer_default_v1"
DEFAULT_OBJECTIVE_WEIGHTS = {
    "delay_minutes": 0.30,
    "laycan_risk": 0.25,
    "asset_balance": 0.20,
    "demurrage_exposure": 0.15,
    "residual_risk": 0.10,
}
DEFAULT_CONSTRAINTS = {
    "respect_approvals": True,
    "respect_operating_windows": True,
    "publish_candidate_only": True,
}


def seed_global_objective_profiles() -> list[GlobalObjectiveProfile]:
    profiles = getattr(settings, "GLOBAL_OPTIMIZER_OBJECTIVE_PROFILES", None)
    if not profiles:
        profiles = [
            {
                "profile_key": DEFAULT_PROFILE_KEY,
                "name": "Global optimizer default",
                "version": 1,
                "status": GlobalObjectiveProfile.Status.ACTIVE,
                "weights": DEFAULT_OBJECTIVE_WEIGHTS,
                "constraints": DEFAULT_CONSTRAINTS,
                "source": "settings/default",
            }
        ]

    seeded: list[GlobalObjectiveProfile] = []
    for profile in profiles:
        profile_key = str(profile.get("profile_key") or DEFAULT_PROFILE_KEY)
        weights = normalize_objective_weights(profile.get("weights") or DEFAULT_OBJECTIVE_WEIGHTS)
        obj, _created = GlobalObjectiveProfile.objects.update_or_create(
            profile_key=profile_key,
            defaults={
                "name": str(profile.get("name") or profile_key.replace("_", " ").title()),
                "version": int(profile.get("version") or 1),
                "status": str(profile.get("status") or GlobalObjectiveProfile.Status.ACTIVE),
                "weights": weights,
                "constraints": profile.get("constraints") or DEFAULT_CONSTRAINTS,
                "source": str(profile.get("source") or "settings"),
            },
        )
        seeded.append(obj)
    return seeded


def normalize_objective_weights(weights: dict[str, Any] | None) -> dict[str, float]:
    raw = weights if isinstance(weights, dict) and weights else DEFAULT_OBJECTIVE_WEIGHTS
    cleaned: dict[str, float] = {}
    for key, value in raw.items():
        try:
            resolved = float(value)
        except (TypeError, ValueError):
            continue
        if resolved > 0:
            cleaned[str(key)] = resolved
    if not cleaned:
        cleaned = dict(DEFAULT_OBJECTIVE_WEIGHTS)
    total = sum(cleaned.values())
    return {
        key: round(value / total, 4)
        for key, value in sorted(cleaned.items())
    }


def get_default_global_objective_profile() -> GlobalObjectiveProfile:
    profile = (
        GlobalObjectiveProfile.objects.filter(
            profile_key=DEFAULT_PROFILE_KEY,
            status=GlobalObjectiveProfile.Status.ACTIVE,
        )
        .order_by("-version", "-id")
        .first()
    )
    if profile:
        return profile
    return seed_global_objective_profiles()[0]


def latest_global_optimization_run(
    plan_version: PlanVersion | None = None,
) -> GlobalOptimizationRun | None:
    queryset = GlobalOptimizationRun.objects.select_related(
        "plan_version",
        "plan_version__plan",
        "objective_profile",
        "started_by",
    ).prefetch_related("candidates")
    if plan_version is not None:
        plan_version_ids = [plan_version.id]
        if plan_version.source_version_id:
            plan_version_ids.append(plan_version.source_version_id)
        queryset = queryset.filter(plan_version_id__in=plan_version_ids)
    return queryset.order_by("-created_at", "-id").first()


def generate_global_optimization_candidates(
    *,
    plan_version: PlanVersion | None = None,
    objective_profile: GlobalObjectiveProfile | None = None,
    objective_weights: dict[str, Any] | None = None,
    max_candidates: int = 3,
    actor=None,
) -> GlobalOptimizationRun:
    resolved_plan_version = plan_version or select_active_global_plan_version()
    resolved_profile = objective_profile or get_default_global_objective_profile()
    normalized_weights = normalize_objective_weights(
        objective_weights if objective_weights else resolved_profile.weights,
    )
    input_summary = build_global_optimizer_input_summary(resolved_plan_version)
    input_signature = _input_signature(input_summary, normalized_weights)
    candidate_specs = _candidate_specs(
        input_summary=input_summary,
        objective_weights=normalized_weights,
        max_candidates=max_candidates,
    )

    with transaction.atomic():
        now = timezone.now()
        run = GlobalOptimizationRun.objects.create(
            status=GlobalOptimizationRun.Status.RUNNING,
            plan_version=resolved_plan_version,
            objective_profile=resolved_profile,
            objective_weights=normalized_weights,
            input_signature=input_signature,
            input_summary=input_summary,
            algorithm_version=GLOBAL_OPTIMIZER_ALGORITHM_VERSION,
            audit_lineage={
                "eventAction": "global_optimizer.run.generate",
                "algorithmVersion": GLOBAL_OPTIMIZER_ALGORITHM_VERSION,
                "objectiveProfileKey": resolved_profile.profile_key,
                "objectiveProfileVersion": resolved_profile.version,
                "inputSignature": input_signature,
            },
            started_by=actor if getattr(actor, "is_authenticated", False) else None,
            started_at=now,
        )
        for spec in candidate_specs:
            GlobalOptimizationCandidate.objects.create(run=run, **spec)
        run.status = GlobalOptimizationRun.Status.SUCCEEDED
        run.completed_at = timezone.now()
        run.audit_lineage = {
            **run.audit_lineage,
            "candidateCount": len(candidate_specs),
            "completedAt": run.completed_at.isoformat(),
        }
        run.save(update_fields=("status", "completed_at", "audit_lineage", "updated_at"))
    return run


def select_active_global_plan_version() -> PlanVersion | None:
    queryset = PlanVersion.objects.select_related("plan", "source_version").annotate(
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


def build_global_optimizer_input_summary(
    plan_version: PlanVersion | None,
) -> dict[str, Any]:
    voyages = OGVVoyage.objects.exclude(status=OGVVoyage.Status.COMPLETED)
    cargo_steps = CargoLayerStep.objects.filter(voyage__in=voyages)
    active_trips = Trip.objects.filter(plan_version=plan_version) if plan_version else Trip.objects.none()
    assignments = Assignment.objects.filter(trip__in=active_trips).select_related(
        "trip",
        "tug",
        "barge",
        "jetty",
        "cts",
    )
    conflicts = Conflict.objects.filter(
        plan_version=plan_version,
        resolved_at__isnull=True,
    ) if plan_version else Conflict.objects.none()
    tracking_alerts = TrackingAlert.objects.filter(
        trip__plan_version=plan_version,
        status__in=[TrackingAlert.Status.OPEN, TrackingAlert.Status.ACKNOWLEDGED],
    ) if plan_version else TrackingAlert.objects.none()
    confirmed_events = ConfirmedOperationalEvent.objects.filter(
        plan_version=plan_version,
    ) if plan_version else ConfirmedOperationalEvent.objects.none()

    laycan_at_risk = [
        {
            "voyageId": voyage.voyage_id,
            "vesselName": voyage.vessel_name,
            "priority": voyage.priority,
            "riskStatus": voyage.risk_status,
            "laycanEnd": voyage.laycan_end.isoformat(),
            "remainingMt": voyage.remaining_mt,
            "demurrageRateUsdPerDay": str(voyage.demurrage_rate_usd_per_day),
        }
        for voyage in voyages.order_by("laycan_end", "priority", "voyage_id")[:20]
        if voyage.risk_status != OGVVoyage.RiskStatus.LOW or voyage.priority <= 2
    ]
    demand_totals = voyages.aggregate(
        required=Sum("required_mt"),
        loaded=Sum("loaded_mt"),
        in_transit=Sum("in_transit_mt"),
        discharged=Sum("discharged_mt"),
    )
    remaining_mt = max(
        (demand_totals["required"] or 0)
        - (demand_totals["loaded"] or 0)
        - (demand_totals["in_transit"] or 0)
        - (demand_totals["discharged"] or 0),
        0,
    )

    return {
        "planVersion": _plan_version_summary(plan_version),
        "demand": {
            "activeOgvCount": voyages.count(),
            "remainingMt": remaining_mt,
            "laycanRiskCount": len(laycan_at_risk),
            "manualPriorityCount": voyages.filter(priority__lte=2).count(),
            "laycanAtRisk": laycan_at_risk,
        },
        "cargo": {
            "requirementCount": cargo_steps.values("cargo_requirement_id").distinct().count(),
            "layerStepCount": cargo_steps.count(),
            "sequenceIssueCount": cargo_steps.filter(
                Q(sequence_violation=True)
                | Q(status__in=[CargoLayerStep.Status.BLOCKED, CargoLayerStep.Status.QC_HOLD])
            ).count(),
        },
        "schedule": {
            "tripCount": active_trips.count(),
            "assignmentCount": assignments.count(),
            "assignedTugs": _distinct_assignment_codes(assignments, "tug__code"),
            "assignedBarges": _distinct_assignment_codes(assignments, "barge__code"),
            "assignedCts": _distinct_assignment_codes(assignments, "cts__code"),
            "firstTrips": _first_trip_refs(active_trips),
        },
        "assets": {
            "tugAvailable": Tug.objects.filter(status=Tug.Status.AVAILABLE).count(),
            "tugUnavailable": Tug.objects.exclude(status=Tug.Status.AVAILABLE).count(),
            "bargeAvailable": Barge.objects.filter(status=Barge.Status.AVAILABLE).count(),
            "bargeUnavailable": Barge.objects.exclude(status=Barge.Status.AVAILABLE).count(),
            "ctsAvailable": CTSAsset.objects.filter(is_available=True).count(),
            "ctsUnavailable": CTSAsset.objects.filter(is_available=False).count(),
            "jettyAvailable": Jetty.objects.filter(status=Jetty.Status.AVAILABLE).count(),
            "jettyBlocked": Jetty.objects.filter(status=Jetty.Status.BLOCKED).count(),
            "assetWindowUnavailable": AssetAvailabilityWindow.objects.exclude(
                status=AssetAvailabilityWindow.Status.AVAILABLE,
            ).count(),
            "jettyWindowBlocked": JettyAvailabilityWindow.objects.exclude(
                status=JettyAvailabilityWindow.Status.WORKING,
            ).count(),
        },
        "constraints": {
            "activeTideWindows": TideWindow.objects.filter(is_active=True).count(),
            "activeBridgeWindows": BridgeWindow.objects.filter(is_active=True).count(),
            "unresolvedBlockingConflicts": conflicts.filter(is_blocking=True).count(),
            "unresolvedCriticalConflicts": conflicts.filter(
                severity=Conflict.Severity.CRITICAL,
            ).count(),
        },
        "telemetry": {
            "openAlertCount": tracking_alerts.count(),
            "criticalAlertCount": tracking_alerts.filter(
                severity=TrackingAlert.Severity.CRITICAL,
            ).count(),
            "warningAlertCount": tracking_alerts.filter(
                severity=TrackingAlert.Severity.WARNING,
            ).count(),
        },
        "operations": {
            "confirmedEventCount": confirmed_events.count(),
        },
    }


def _candidate_specs(
    *,
    input_summary: dict[str, Any],
    objective_weights: dict[str, float],
    max_candidates: int,
) -> list[dict[str, Any]]:
    candidates = [
        _baseline_candidate(input_summary, objective_weights),
        _laycan_priority_candidate(input_summary, objective_weights),
        _asset_balance_candidate(input_summary, objective_weights),
    ]
    ranked = sorted(candidates, key=lambda item: item["score"], reverse=True)
    limited = ranked[: max(1, min(max_candidates, 5))]
    return [
        {
            **candidate,
            "rank": index,
            "score": Decimal(str(round(float(candidate["score"]), 3))),
        }
        for index, candidate in enumerate(limited, start=1)
    ]


def _baseline_candidate(
    input_summary: dict[str, Any],
    objective_weights: dict[str, float],
) -> dict[str, Any]:
    risks = _unresolved_risks(input_summary)
    score = _score(
        objective_weights,
        delay_minutes=60,
        laycan_risk=input_summary["demand"]["laycanRiskCount"],
        asset_balance_gap=_asset_gap(input_summary),
        demurrage_exposure=2,
        residual_risk=len(risks),
    )
    return {
        "risk_level": _risk_level(risks),
        "score": score,
        "summary": "Status quo baseline across active OGV demand and current assignments.",
        "objective_score_breakdown": _breakdown(objective_weights, score),
        "changed_assignments": [],
        "trip_sequence_changes": [],
        "projected_impacts": {
            "delayMinutesDelta": 0,
            "laycanRiskDelta": 0,
            "demurrageExposureDeltaUsd": 0,
            "candidateKind": "status_quo_baseline",
        },
        "unresolved_risks": risks,
        "approval_lineage": _candidate_lineage("status_quo_baseline"),
        "metadata": {"candidateKind": "status_quo_baseline"},
    }


def _laycan_priority_candidate(
    input_summary: dict[str, Any],
    objective_weights: dict[str, float],
) -> dict[str, Any]:
    risks = _unresolved_risks(input_summary)
    top_laycan = input_summary["demand"]["laycanAtRisk"][:3]
    score = _score(
        objective_weights,
        delay_minutes=30,
        laycan_risk=max(input_summary["demand"]["laycanRiskCount"] - len(top_laycan), 0),
        asset_balance_gap=_asset_gap(input_summary) + 1,
        demurrage_exposure=1,
        residual_risk=len(risks),
    )
    return {
        "risk_level": _risk_level(risks),
        "score": score,
        "summary": "Prioritize earliest laycan and highest priority OGVs before lower-risk demand.",
        "objective_score_breakdown": _breakdown(objective_weights, score),
        "changed_assignments": [
            {
                "kind": "candidate_priority_shift",
                "voyageId": voyage["voyageId"],
                "reason": "Laycan or manual priority receives earlier network attention.",
            }
            for voyage in top_laycan
        ],
        "trip_sequence_changes": [
            {
                "kind": "candidate_sequence_priority",
                "voyageId": voyage["voyageId"],
                "target": "earlier_trip_sequence",
            }
            for voyage in top_laycan
        ],
        "projected_impacts": {
            "delayMinutesDelta": -30 if top_laycan else 0,
            "laycanRiskDelta": -len(top_laycan),
            "demurrageExposureDeltaUsd": -5000 * len(top_laycan),
            "candidateKind": "laycan_priority",
        },
        "unresolved_risks": risks,
        "approval_lineage": _candidate_lineage("laycan_priority"),
        "metadata": {"candidateKind": "laycan_priority", "priorityVoyageCount": len(top_laycan)},
    }


def _asset_balance_candidate(
    input_summary: dict[str, Any],
    objective_weights: dict[str, float],
) -> dict[str, Any]:
    risks = _unresolved_risks(input_summary)
    first_trips = input_summary["schedule"]["firstTrips"][:3]
    score = _score(
        objective_weights,
        delay_minutes=40,
        laycan_risk=input_summary["demand"]["laycanRiskCount"],
        asset_balance_gap=max(_asset_gap(input_summary) - 2, 0),
        demurrage_exposure=2,
        residual_risk=len(risks),
    )
    return {
        "risk_level": _risk_level(risks),
        "score": score,
        "summary": "Balance tug, barge, CTS, and jetty pressure without committing plan changes.",
        "objective_score_breakdown": _breakdown(objective_weights, score),
        "changed_assignments": [
            {
                "kind": "candidate_asset_balance",
                "tripId": trip["tripId"],
                "reason": "Review alternate compatible assets for network balance.",
            }
            for trip in first_trips
        ],
        "trip_sequence_changes": [],
        "projected_impacts": {
            "delayMinutesDelta": -20 if first_trips else 0,
            "laycanRiskDelta": 0,
            "demurrageExposureDeltaUsd": -2500 if first_trips else 0,
            "candidateKind": "asset_balance",
        },
        "unresolved_risks": risks,
        "approval_lineage": _candidate_lineage("asset_balance"),
        "metadata": {"candidateKind": "asset_balance", "reviewTripCount": len(first_trips)},
    }


def _score(
    weights: dict[str, float],
    *,
    delay_minutes: int,
    laycan_risk: int,
    asset_balance_gap: int,
    demurrage_exposure: int,
    residual_risk: int,
) -> float:
    penalties = {
        "delay_minutes": min(delay_minutes / 120, 1),
        "laycan_risk": min(laycan_risk / 10, 1),
        "asset_balance": min(asset_balance_gap / 10, 1),
        "demurrage_exposure": min(demurrage_exposure / 10, 1),
        "residual_risk": min(residual_risk / 10, 1),
    }
    penalty = sum(weights.get(key, 0) * penalties[key] for key in penalties)
    return max(0, 100 - (penalty * 100))


def _breakdown(weights: dict[str, float], score: float) -> dict[str, Any]:
    return {
        "score": round(score, 3),
        "weights": weights,
        "contract": "candidate_scaffold_projection",
        "finalCommercialPolicy": False,
    }


def _unresolved_risks(input_summary: dict[str, Any]) -> list[dict[str, Any]]:
    risks: list[dict[str, Any]] = []
    if input_summary["constraints"]["unresolvedBlockingConflicts"]:
        risks.append({
            "kind": "blocking_conflict",
            "severity": "critical",
            "count": input_summary["constraints"]["unresolvedBlockingConflicts"],
            "message": "Unresolved blocking conflicts remain in the active plan.",
        })
    if input_summary["telemetry"]["criticalAlertCount"]:
        risks.append({
            "kind": "telemetry_alert",
            "severity": "critical",
            "count": input_summary["telemetry"]["criticalAlertCount"],
            "message": "Critical telemetry alerts remain unresolved.",
        })
    if input_summary["cargo"]["sequenceIssueCount"]:
        risks.append({
            "kind": "cargo_sequence",
            "severity": "warning",
            "count": input_summary["cargo"]["sequenceIssueCount"],
            "message": "Cargo sequence issues require operator review.",
        })
    return risks


def _risk_level(risks: list[dict[str, Any]]) -> str:
    if any(risk.get("severity") == "critical" for risk in risks):
        return GlobalOptimizationCandidate.RiskLevel.CRITICAL
    if risks:
        return GlobalOptimizationCandidate.RiskLevel.MEDIUM
    return GlobalOptimizationCandidate.RiskLevel.LOW


def _asset_gap(input_summary: dict[str, Any]) -> int:
    assets = input_summary["assets"]
    return (
        int(assets["tugUnavailable"])
        + int(assets["bargeUnavailable"])
        + int(assets["ctsUnavailable"])
        + int(assets["jettyBlocked"])
        + int(assets["assetWindowUnavailable"])
        + int(assets["jettyWindowBlocked"])
    )


def _candidate_lineage(kind: str) -> dict[str, Any]:
    return {
        "candidateKind": kind,
        "approvalCreated": False,
        "requiresBerauAblReview": True,
        "manualPublishRequired": True,
    }


def _input_signature(input_summary: dict[str, Any], weights: dict[str, float]) -> str:
    payload = json.dumps(
        {"inputSummary": input_summary, "weights": weights},
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _plan_version_summary(plan_version: PlanVersion | None) -> dict[str, Any] | None:
    if plan_version is None:
        return None
    return {
        "id": plan_version.id,
        "ref": str(plan_version),
        "planCode": plan_version.plan.code,
        "versionNo": plan_version.version_no,
        "status": plan_version.status,
        "validationStatus": plan_version.validation_status,
        "sourceInputsChanged": bool(
            isinstance(plan_version.summary, dict)
            and plan_version.summary.get("sourceInputsChanged")
        ),
    }


def _distinct_assignment_codes(assignments, field_name: str) -> list[str]:
    return [
        code
        for code in assignments.order_by(field_name)
        .values_list(field_name, flat=True)
        .distinct()
        if code
    ]


def _first_trip_refs(trips) -> list[dict[str, Any]]:
    return [
        {
            "tripId": trip.trip_id,
            "sequence": trip.sequence,
            "voyageId": trip.voyage.voyage_id,
            "plannedStart": trip.planned_start.isoformat(),
            "plannedEnd": trip.planned_end.isoformat(),
        }
        for trip in trips.select_related("voyage").order_by("sequence", "planned_start")[:10]
    ]
