from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.db import transaction
from django.db.models import Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from apps.masters.models import AssetCompatibilityRule, Barge, CTSAsset, Jetty, RouteSegment, Tug
from apps.planning.models import (
    AssetAvailabilityWindow,
    BridgeWindow,
    CargoLayerStep,
    JettyAvailabilityWindow,
    NavigationConstraintCheck,
    TideWindow,
)

from .active_plan_selectors import WORKING_CANDIDATE, select_active_plan_version
from .models import (
    MovementAssignmentCandidate,
    MovementAssignmentCandidateRun,
    PlanVersion,
)


MOVEMENT_ASSIGNMENT_ALGORITHM_VERSION = "phase6.14-movement-assignment-candidates"


def latest_candidate_run(plan_version: PlanVersion | None = None) -> MovementAssignmentCandidateRun | None:
    queryset = MovementAssignmentCandidateRun.objects.select_related(
        "plan_version",
        "plan_version__plan",
        "generated_by",
    ).prefetch_related("candidates")
    if plan_version is not None:
        queryset = queryset.filter(plan_version=plan_version)
    return queryset.order_by("-created_at", "-id").first()


def fresh_candidate_run_for_generation(
    plan_version: PlanVersion | None,
    *,
    actor=None,
) -> MovementAssignmentCandidateRun:
    input_summary = build_movement_assignment_input_summary(plan_version)
    input_signature = _input_signature(input_summary)
    latest = latest_candidate_run(plan_version)
    if (
        latest
        and latest.status == MovementAssignmentCandidateRun.Status.SUCCEEDED
        and latest.input_signature == input_signature
    ):
        return latest
    return generate_movement_assignment_candidates(plan_version=plan_version, actor=actor)


def generate_movement_assignment_candidates(
    *,
    plan_version: PlanVersion | None = None,
    actor=None,
    persist: bool = True,
) -> MovementAssignmentCandidateRun:
    resolved_plan_version = plan_version or select_active_plan_version(WORKING_CANDIDATE)
    steps = _movement_steps(resolved_plan_version)
    input_summary = build_movement_assignment_input_summary(resolved_plan_version)
    input_signature = _input_signature(input_summary)
    candidate_specs = _candidate_specs(steps)
    run_summary = _run_summary(candidate_specs, movement_count=len(steps))

    if not persist:
        run = MovementAssignmentCandidateRun(
            status=MovementAssignmentCandidateRun.Status.SUCCEEDED,
            plan_version=resolved_plan_version,
            input_signature=input_signature,
            input_summary=input_summary,
            algorithm_version=MOVEMENT_ASSIGNMENT_ALGORITHM_VERSION,
            metadata=run_summary,
        )
        run.transient_candidates = candidate_specs
        return run

    with transaction.atomic():
        now = timezone.now()
        run = MovementAssignmentCandidateRun.objects.create(
            status=MovementAssignmentCandidateRun.Status.RUNNING,
            plan_version=resolved_plan_version,
            input_signature=input_signature,
            input_summary=input_summary,
            algorithm_version=MOVEMENT_ASSIGNMENT_ALGORITHM_VERSION,
            generated_by=actor if getattr(actor, "is_authenticated", False) else None,
            started_at=now,
            metadata=run_summary,
        )
        for spec in candidate_specs:
            MovementAssignmentCandidate.objects.create(run=run, **spec)
        _select_default_candidates(run)
        run.status = MovementAssignmentCandidateRun.Status.SUCCEEDED
        run.completed_at = timezone.now()
        run.metadata = {
            **run.metadata,
            "completedAt": run.completed_at.isoformat(),
        }
        run.save(update_fields=("status", "completed_at", "metadata", "updated_at"))
    return run


def select_movement_assignment_candidate(
    candidate: MovementAssignmentCandidate,
) -> MovementAssignmentCandidate:
    if candidate.status == MovementAssignmentCandidate.Status.BLOCKED:
        raise ValidationError({"candidate": "Blocked movement assignment candidates cannot be selected."})
    with transaction.atomic():
        MovementAssignmentCandidate.objects.filter(
            run=candidate.run,
            cargo_layer_step=candidate.cargo_layer_step,
        ).exclude(pk=candidate.pk).update(is_selected=False)
        candidate.is_selected = True
        reason = candidate.selection_reason if isinstance(candidate.selection_reason, dict) else {}
        candidate.selection_reason = {**reason, "selectedByOperator": True}
        candidate.save(update_fields=("is_selected", "selection_reason", "updated_at"))
    return candidate


def selected_or_top_candidate_for_step(
    run: MovementAssignmentCandidateRun,
    cargo_layer_step: CargoLayerStep,
) -> MovementAssignmentCandidate | None:
    candidates = MovementAssignmentCandidate.objects.filter(
        run=run,
        cargo_layer_step=cargo_layer_step,
    ).select_related("tug", "barge", "jetty", "cts", "route_segment")
    selected = candidates.filter(
        is_selected=True,
        status__in=[
            MovementAssignmentCandidate.Status.FEASIBLE,
            MovementAssignmentCandidate.Status.WARNING,
        ],
    ).order_by("rank", "id").first()
    if selected:
        return selected
    top = candidates.filter(
        status__in=[
            MovementAssignmentCandidate.Status.FEASIBLE,
            MovementAssignmentCandidate.Status.WARNING,
        ],
    ).order_by("rank", "id").first()
    if top:
        return top
    return candidates.order_by("rank", "id").first()


def generate_plan_version_from_candidates(
    plan_version: PlanVersion,
    candidate_run: MovementAssignmentCandidateRun,
    actor=None,
):
    from .services import generate_plan_version

    return generate_plan_version(plan_version, candidate_run=candidate_run, actor=actor)


def build_movement_assignment_input_summary(plan_version: PlanVersion | None) -> dict[str, Any]:
    steps = _movement_steps(plan_version)
    return {
        "planVersionId": plan_version.id if plan_version else None,
        "movementCount": len(steps),
        "movementKeys": [_movement_key(step) for step in steps],
        "cargoLayerStepIds": [step.id for step in steps],
        "tugCount": Tug.objects.filter(is_active=True).count(),
        "bargeCount": Barge.objects.filter(is_active=True).count(),
        "jettyCount": Jetty.objects.filter(is_active=True).count(),
        "ctsCount": CTSAsset.objects.filter(is_active=True).count(),
        "assetWindowCount": AssetAvailabilityWindow.objects.count(),
        "jettyWindowCount": JettyAvailabilityWindow.objects.count(),
        "tideWindowCount": TideWindow.objects.filter(is_active=True).count(),
        "bridgeWindowCount": BridgeWindow.objects.filter(is_active=True).count(),
        "navigationCheckCount": NavigationConstraintCheck.objects.count(),
    }


def _movement_steps(plan_version: PlanVersion | None) -> list[CargoLayerStep]:
    queryset = CargoLayerStep.objects.select_related(
        "voyage",
        "cargo_requirement",
        "coal_grade",
        "planned_barge",
        "planned_jetty",
        "planned_cts",
    )
    if plan_version is not None:
        queryset = queryset.filter(voyage__laycan_start__lte=plan_version.plan.horizon_end)
        queryset = queryset.filter(voyage__laycan_end__gte=plan_version.plan.horizon_start)
    return list(
        queryset.order_by(
            "voyage__laycan_start",
            "voyage__priority",
            "voyage__voyage_id",
            "required_sequence_no",
        )
    )


def _candidate_specs(steps: list[CargoLayerStep]) -> list[dict[str, Any]]:
    tugs = list(Tug.objects.filter(is_active=True).order_by("code"))
    barges = list(Barge.objects.filter(is_active=True).order_by("code"))
    jetties = list(Jetty.objects.filter(is_active=True).order_by("code"))
    cts_assets = list(CTSAsset.objects.filter(is_active=True).order_by("code"))
    route_segment = _first_route_segment()
    reserved_windows: dict[str, list[tuple]] = {}
    specs: list[dict[str, Any]] = []

    for sequence, step in enumerate(steps, start=1):
        start, end = _movement_window(step, sequence)
        movement_key = _movement_key(step)
        movement_specs = []
        for tug in tugs or [None]:
            for barge in _ordered_assets(barges, step.planned_barge):
                for jetty in _ordered_assets(jetties, step.planned_jetty):
                    for cts in _ordered_assets(cts_assets, step.planned_cts):
                        movement_specs.append(
                            _score_candidate(
                                step=step,
                                movement_key=movement_key,
                                start=start,
                                end=end,
                                tug=tug,
                                barge=barge,
                                jetty=jetty,
                                cts=cts,
                                route_segment=route_segment,
                                reserved_windows=reserved_windows,
                            )
                        )
        movement_specs.sort(
            key=lambda item: (
                _status_order(item["status"]),
                -float(item["score"]),
                item["selection_reason"].get("tugCode") or "",
                item["selection_reason"].get("bargeCode") or "",
                item["selection_reason"].get("jettyCode") or "",
                item["selection_reason"].get("ctsCode") or "",
            )
        )
        top_candidate = next(
            (
                spec
                for spec in movement_specs
                if spec["status"]
                in {
                    MovementAssignmentCandidate.Status.FEASIBLE,
                    MovementAssignmentCandidate.Status.WARNING,
                }
            ),
            None,
        )
        if top_candidate:
            _reserve_candidate_windows(top_candidate, reserved_windows, start, end)
        for rank, spec in enumerate(movement_specs, start=1):
            spec["rank"] = rank
            specs.append(spec)
    return specs


def _score_candidate(
    *,
    step: CargoLayerStep,
    movement_key: str,
    start,
    end,
    tug: Tug | None,
    barge: Barge | None,
    jetty: Jetty | None,
    cts: CTSAsset | None,
    route_segment: RouteSegment | None,
    reserved_windows: dict[str, list[tuple]],
) -> dict[str, Any]:
    checks = []
    blocking: list[str] = []
    warnings: list[str] = []
    score = Decimal("1000.000")

    def add_check(name: str, status: str, message: str, hard: bool = True):
        checks.append({"name": name, "status": status, "message": message})
        if status == "blocked" and hard:
            blocking.append(message)
        elif status in {"warning", "blocked"}:
            warnings.append(message)

    if step.sequence_violation:
        add_check("cargo_sequence", "blocked", step.blocking_reason or "Cargo sequence blocks movement.")
    elif step.status in {CargoLayerStep.Status.BLOCKED, CargoLayerStep.Status.QC_HOLD}:
        add_check("cargo_sequence", "blocked", step.blocking_reason or "Cargo layer is blocked.")
    else:
        add_check("cargo_sequence", "passed", "Cargo sequence allows movement.")

    _asset_check("tug", tug, start, end, add_check, reserved_windows)
    _asset_check("barge", barge, start, end, add_check, reserved_windows)
    _asset_check("cts", cts, start, end, add_check, reserved_windows)
    _jetty_check(jetty, start, end, add_check, reserved_windows)
    _compatibility_checks(tug, barge, jetty, cts, route_segment, add_check)
    _navigation_checks(step, barge, start, end, add_check)

    declared_match = {
        "barge": bool(barge and step.planned_barge_id == barge.id),
        "jetty": bool(jetty and step.planned_jetty_id == jetty.id),
        "cts": bool(cts and step.planned_cts_id == cts.id),
    }
    score += Decimal(100 * sum(1 for matched in declared_match.values() if matched))
    score -= Decimal(500 * len(blocking))
    score -= Decimal(75 * len(warnings))
    if tug and tug.status == Tug.Status.AVAILABLE:
        score += Decimal("20")

    status = MovementAssignmentCandidate.Status.FEASIBLE
    if blocking:
        status = MovementAssignmentCandidate.Status.BLOCKED
    elif warnings:
        status = MovementAssignmentCandidate.Status.WARNING

    return {
        "cargo_layer_step": step,
        "movement_key": movement_key,
        "status": status,
        "tug": tug,
        "barge": barge,
        "jetty": jetty,
        "cts": cts,
        "route_segment": route_segment,
        "score": score,
        "constraint_results": checks,
        "blocking_reasons": blocking,
        "warning_reasons": warnings,
        "selection_reason": {
            "algorithmVersion": MOVEMENT_ASSIGNMENT_ALGORITHM_VERSION,
            "declaredMatch": declared_match,
            "movementKey": movement_key,
            "tugCode": tug.code if tug else "",
            "bargeCode": barge.code if barge else "",
            "jettyCode": jetty.code if jetty else "",
            "ctsCode": cts.code if cts else "",
        },
    }


def _asset_check(asset_type: str, asset, start, end, add_check, reserved_windows) -> None:
    if asset is None:
        add_check(asset_type, "blocked", f"No {asset_type} is available for this movement.")
        return
    if asset_type == "cts" and not getattr(asset, "is_available", True):
        add_check(asset_type, "blocked", f"{asset.code} is not available.")
        return
    if getattr(asset, "status", "available") not in {"available", ""}:
        add_check(asset_type, "blocked", f"{asset.code} master status is {asset.status}.")
        return
    unavailable = AssetAvailabilityWindow.objects.filter(
        asset_type=asset_type,
        asset_code=asset.code,
        window_start__lt=end,
        window_end__gt=start,
    ).exclude(status=AssetAvailabilityWindow.Status.AVAILABLE).first()
    if unavailable:
        add_check(asset_type, "blocked", f"{asset.code} is {unavailable.status} inside the movement window.")
        return
    if _overlaps_reserved(f"{asset_type}:{asset.code}", start, end, reserved_windows):
        add_check(asset_type, "blocked", f"{asset.code} is already reserved by an earlier movement candidate.")
        return
    add_check(asset_type, "passed", f"{asset.code} is available.")


def _jetty_check(jetty: Jetty | None, start, end, add_check, reserved_windows) -> None:
    if jetty is None:
        add_check("jetty", "blocked", "No jetty is available for this movement.")
        return
    if jetty.status == Jetty.Status.BLOCKED:
        add_check("jetty", "blocked", f"{jetty.code} master status is blocked.")
        return
    window = JettyAvailabilityWindow.objects.filter(
        jetty=jetty,
        window_start__lt=end,
        window_end__gt=start,
    ).exclude(status=JettyAvailabilityWindow.Status.WORKING).first()
    if window and window.status == JettyAvailabilityWindow.Status.BLOCKED:
        add_check("jetty", "blocked", f"{jetty.code} is blocked inside the movement window.")
        return
    if window:
        add_check("jetty", "warning", f"{jetty.code} is {window.status} inside the movement window.", hard=False)
        return
    if _overlaps_reserved(f"jetty:{jetty.code}", start, end, reserved_windows):
        add_check("jetty", "warning", f"{jetty.code} is already used by an earlier movement candidate.", hard=False)
        return
    add_check("jetty", "passed", f"{jetty.code} is available.")


def _compatibility_checks(tug, barge, jetty, cts, route_segment, add_check) -> None:
    pairs = [
        ("tug_barge", tug.code if tug else "", barge.code if barge else ""),
        ("barge_jetty", barge.code if barge else "", jetty.code if jetty else ""),
        ("cts_route", cts.code if cts else "", str(route_segment.id) if route_segment else ""),
    ]
    for rule_type, left, right in pairs:
        if not left or not right:
            continue
        incompatible = AssetCompatibilityRule.objects.filter(
            rule_type=rule_type,
            left_code=left,
            right_code=right,
            is_compatible=False,
        ).first()
        if incompatible:
            add_check(rule_type, "blocked", incompatible.reason or f"{left} is incompatible with {right}.")
        else:
            add_check(rule_type, "passed", f"{left} is compatible with {right}.")


def _navigation_checks(step, barge, start, end, add_check) -> None:
    checks = NavigationConstraintCheck.objects.filter(voyage=step.voyage)
    if barge is not None:
        checks = checks.filter(Q(asset_code="") | Q(asset_code=barge.code))
    checks = list(checks)
    if not checks:
        add_check("navigation", "warning", "No movement-intent tide or bridge check exists.", hard=False)
        return
    relevant = [check for check in checks if start <= check.eta_gate <= end or check.asset_code == (barge.code if barge else "")]
    for check in relevant or checks:
        if check.status == NavigationConstraintCheck.Status.MISSED:
            add_check(check.constraint_type, "blocked", check.recovery_hint or f"{check.constraint_type} window is missed.")
        elif check.status == NavigationConstraintCheck.Status.MARGINAL:
            add_check(check.constraint_type, "warning", check.recovery_hint or f"{check.constraint_type} window is marginal.", hard=False)
        elif check.status == NavigationConstraintCheck.Status.WAITING:
            add_check(check.constraint_type, "warning", check.recovery_hint or f"{check.constraint_type} window is waiting.", hard=False)
        else:
            add_check(check.constraint_type, "passed", check.recovery_hint or f"{check.constraint_type} window allows crossing.")


def _select_default_candidates(run: MovementAssignmentCandidateRun) -> None:
    step_ids = run.candidates.order_by("cargo_layer_step_id").values_list(
        "cargo_layer_step_id",
        flat=True,
    ).distinct()
    for step_id in step_ids:
        candidate = run.candidates.filter(
            cargo_layer_step_id=step_id,
            status__in=[
                MovementAssignmentCandidate.Status.FEASIBLE,
                MovementAssignmentCandidate.Status.WARNING,
            ],
        ).order_by("rank", "id").first()
        if candidate:
            candidate.is_selected = True
            candidate.save(update_fields=("is_selected", "updated_at"))


def _run_summary(candidate_specs: list[dict[str, Any]], *, movement_count: int) -> dict[str, Any]:
    feasible = sum(1 for spec in candidate_specs if spec["status"] == MovementAssignmentCandidate.Status.FEASIBLE)
    warning = sum(1 for spec in candidate_specs if spec["status"] == MovementAssignmentCandidate.Status.WARNING)
    blocked = sum(1 for spec in candidate_specs if spec["status"] == MovementAssignmentCandidate.Status.BLOCKED)
    covered_movements = len({spec["movement_key"] for spec in candidate_specs})
    return {
        "algorithmVersion": MOVEMENT_ASSIGNMENT_ALGORITHM_VERSION,
        "movementCount": movement_count,
        "coveredMovementCount": covered_movements,
        "candidateCount": len(candidate_specs),
        "feasibleCandidateCount": feasible,
        "warningCandidateCount": warning,
        "blockedCandidateCount": blocked,
    }


def candidate_run_summary(run: MovementAssignmentCandidateRun | None) -> dict[str, Any]:
    if run is None:
        return {
            "assignmentCandidateRunId": None,
            "movementCount": 0,
            "candidateFeasibleCount": 0,
            "candidateBlockedCount": 0,
            "generatedFromMovementCandidates": False,
        }
    metadata = run.metadata if isinstance(run.metadata, dict) else {}
    return {
        "assignmentCandidateRunId": run.id,
        "assignmentCandidateRunRef": run.run_id,
        "movementCount": int(metadata.get("movementCount") or 0),
        "candidateFeasibleCount": int(metadata.get("feasibleCandidateCount") or 0),
        "candidateBlockedCount": int(metadata.get("blockedCandidateCount") or 0),
        "generatedFromMovementCandidates": True,
    }


def _reserve_candidate_windows(spec: dict[str, Any], reserved_windows: dict[str, list[tuple]], start, end) -> None:
    for kind in ("tug", "barge", "cts", "jetty"):
        asset = spec.get(kind)
        if asset is not None:
            reserved_windows.setdefault(f"{kind}:{asset.code}", []).append((start, end))


def _overlaps_reserved(key: str, start, end, reserved_windows: dict[str, list[tuple]]) -> bool:
    return any(start < reserved_end and end > reserved_start for reserved_start, reserved_end in reserved_windows.get(key, []))


def _ordered_assets(assets: list, preferred):
    ordered = list(assets)
    if preferred in ordered:
        ordered.remove(preferred)
        ordered.insert(0, preferred)
    return ordered or [preferred]


def _movement_window(step: CargoLayerStep, sequence: int):
    start = step.planned_start or step.voyage.eta + timedelta(hours=sequence)
    end = step.planned_end or start + timedelta(hours=10)
    return start, end


def _movement_key(step: CargoLayerStep) -> str:
    return f"{step.voyage.voyage_id}:{step.required_sequence_no}:{step.id}"


def _first_route_segment() -> RouteSegment | None:
    return (
        RouteSegment.objects.filter(requires_tide_window=True).order_by("route__code", "sequence").first()
        or RouteSegment.objects.filter(requires_bridge_window=True).order_by("route__code", "sequence").first()
        or RouteSegment.objects.order_by("route__code", "sequence").first()
    )


def _status_order(status: str) -> int:
    if status == MovementAssignmentCandidate.Status.FEASIBLE:
        return 0
    if status == MovementAssignmentCandidate.Status.WARNING:
        return 1
    return 2


def _input_signature(payload: dict[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
