from __future__ import annotations

import hashlib
import json
from datetime import timedelta
from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db import transaction
from django.db.models import F, Max
from django.utils import timezone

from apps.planning.models import OGVVoyage
from apps.telemetry.models import LiveEtaProjection, TelemetryTrustAssessment
from apps.telemetry.telemetry_trust_services import (
    get_default_trust_profile,
    latest_trust_assessments_for_plan,
    trust_assessment_is_blocking,
)

from .models import (
    CommercialProjectionRun,
    CustomerSafeCommercialProjection,
    PlanVersion,
    ScheduleEvent,
    Trip,
)

COMMERCIAL_PROJECTION_ALGORITHM_VERSION = "phase6.6-commercial-projection"
PROJECTION_ONLY_DISCLAIMER = (
    "Projection only: not a customer commitment, invoice, laytime calculation, "
    "NOR/SOF determination, demurrage settlement, or despatch settlement."
)


def latest_commercial_projection_run(
    plan_version: PlanVersion | None = None,
) -> CommercialProjectionRun | None:
    queryset = CommercialProjectionRun.objects.select_related(
        "plan_version",
        "plan_version__plan",
        "telemetry_trust_profile",
        "generated_by",
    ).prefetch_related("projections", "projections__voyage", "projections__trip")
    if plan_version is not None:
        plan_version_ids = [plan_version.id]
        if plan_version.source_version_id:
            plan_version_ids.append(plan_version.source_version_id)
        queryset = queryset.filter(plan_version_id__in=plan_version_ids)
    return queryset.order_by("-created_at", "-id").first()


def is_commercial_projection_stale(
    run: CommercialProjectionRun | None,
    plan_version: PlanVersion | None,
) -> bool:
    if run is None or plan_version is None:
        return True
    latest_input = latest_commercial_projection_input_time(plan_version)
    return bool(latest_input and run.completed_at and run.completed_at < latest_input)


def latest_commercial_projection_input_time(plan_version: PlanVersion | None):
    if plan_version is None:
        return None
    values = [
        value
        for value in [
            plan_version.updated_at,
            Trip.objects.filter(plan_version=plan_version).aggregate(value=Max("updated_at"))[
                "value"
            ],
            LiveEtaProjection.objects.filter(trip__plan_version=plan_version).aggregate(
                value=Max("updated_at")
            )["value"],
            max(
                (
                    assessment.assessed_at
                    for assessment in latest_trust_assessments_for_plan(plan_version)
                ),
                default=None,
            ),
        ]
        if value is not None
    ]
    return max(values) if values else None


def generate_customer_safe_commercial_projections(
    *,
    plan_version: PlanVersion | None = None,
    actor=None,
) -> CommercialProjectionRun:
    resolved_plan_version = plan_version or _select_active_plan_version()
    trust_profile = get_default_trust_profile()
    input_summary = build_commercial_projection_input_summary(resolved_plan_version)
    input_signature = _input_signature(input_summary)
    projection_specs = _projection_specs(resolved_plan_version)

    with transaction.atomic():
        now = timezone.now()
        run = CommercialProjectionRun.objects.create(
            status=CommercialProjectionRun.Status.RUNNING,
            plan_version=resolved_plan_version,
            telemetry_trust_profile=trust_profile,
            input_signature=input_signature,
            input_summary=input_summary,
            algorithm_version=COMMERCIAL_PROJECTION_ALGORITHM_VERSION,
            audit_lineage={
                "eventAction": "commercial_projection.run.generate",
                "algorithmVersion": COMMERCIAL_PROJECTION_ALGORITHM_VERSION,
                "inputSignature": input_signature,
                "projectionOnly": True,
                "finalSettlement": False,
            },
            generated_by=actor if getattr(actor, "is_authenticated", False) else None,
            started_at=now,
        )
        for spec in projection_specs:
            CustomerSafeCommercialProjection.objects.create(run=run, **spec)
        summary = _run_summary(projection_specs)
        run.status = CommercialProjectionRun.Status.SUCCEEDED
        run.completed_at = timezone.now()
        run.summary = summary
        run.audit_lineage = {
            **run.audit_lineage,
            "projectionCount": len(projection_specs),
            "completedAt": run.completed_at.isoformat(),
        }
        run.save(
            update_fields=(
                "status",
                "completed_at",
                "summary",
                "audit_lineage",
                "updated_at",
            )
        )
    return run


def build_commercial_projection_input_summary(
    plan_version: PlanVersion | None,
) -> dict[str, Any]:
    trips = Trip.objects.filter(plan_version=plan_version) if plan_version else Trip.objects.none()
    voyages = OGVVoyage.objects.filter(scheduled_trips__in=trips).distinct()
    eta_projections = (
        LiveEtaProjection.objects.filter(trip__plan_version=plan_version)
        if plan_version
        else LiveEtaProjection.objects.none()
    )
    trust_assessments = latest_trust_assessments_for_plan(plan_version)
    blocking_trust = sum(1 for assessment in trust_assessments if trust_assessment_is_blocking(assessment))
    degraded_trust = sum(
        1
        for assessment in trust_assessments
        if assessment.trust_status == TelemetryTrustAssessment.TrustStatus.DEGRADED
    )
    return {
        "planVersion": _plan_version_summary(plan_version),
        "demand": {
            "voyageCount": voyages.count(),
            "remainingMt": sum(voyage.remaining_mt for voyage in voyages),
            "laycanAtRiskCount": voyages.filter(
                risk_status__in=[
                    OGVVoyage.RiskStatus.HIGH,
                    OGVVoyage.RiskStatus.DEMURRAGE,
                ]
            ).count(),
        },
        "schedule": {
            "tripCount": trips.count(),
            "lastPlannedEnd": _iso_or_none(trips.aggregate(value=Max("planned_end"))["value"]),
        },
        "telemetry": {
            "etaProjectionCount": eta_projections.count(),
            "trustAssessmentCount": len(trust_assessments),
            "blockingTrustCount": blocking_trust,
            "degradedTrustCount": degraded_trust,
        },
        "commercialContract": {
            "projectionOnly": True,
            "finalCommitment": False,
            "finalSettlement": False,
            "invoiceOutput": False,
        },
    }


def commercial_projection_summary_payload(
    run: CommercialProjectionRun | None,
) -> dict[str, Any] | None:
    if run is None:
        return None
    projections = list(run.projections.all())
    return {
        "runId": run.run_id,
        "status": run.status,
        "projectionCount": len(projections),
        "atRiskCount": sum(
            1
            for projection in projections
            if projection.status
            in {
                CustomerSafeCommercialProjection.Status.AT_RISK,
                CustomerSafeCommercialProjection.Status.BLOCKED,
            }
        ),
        "customerSafeToShareCount": sum(
            1 for projection in projections if projection.customer_safe_to_share
        ),
        "projectionOnly": True,
    }


def _projection_specs(plan_version: PlanVersion | None) -> list[dict[str, Any]]:
    if plan_version is None:
        return []
    trips = (
        Trip.objects.filter(plan_version=plan_version)
        .select_related("voyage")
        .order_by("voyage__laycan_start", "sequence")
    )
    trip_rows = list(trips)
    trips_by_voyage: dict[int, list[Trip]] = {}
    for trip in trip_rows:
        trips_by_voyage.setdefault(trip.voyage_id, []).append(trip)

    trust_by_asset = {
        assessment.asset_code: assessment
        for assessment in latest_trust_assessments_for_plan(plan_version)
    }
    specs = []
    for voyage_id, voyage_trips in trips_by_voyage.items():
        voyage = voyage_trips[0].voyage
        eta_projection = _latest_eta_projection(voyage_trips)
        completion_at = _projected_completion_at(voyage_trips, eta_projection)
        trust = _trust_for_voyage(voyage, voyage_trips, trust_by_asset)
        specs.append(
            _projection_spec(
                voyage=voyage,
                trip=voyage_trips[-1],
                eta_projection=eta_projection,
                completion_at=completion_at,
                trust=trust,
            )
        )
    return specs


def _projection_spec(
    *,
    voyage: OGVVoyage,
    trip: Trip,
    eta_projection: LiveEtaProjection | None,
    completion_at,
    trust: TelemetryTrustAssessment | None,
) -> dict[str, Any]:
    if completion_at is None:
        exposure_minutes = 0
        laycan_variance = 0
        laycan_status = "unknown"
    else:
        laycan_variance = _ceil_minutes(completion_at - voyage.laycan_end)
        exposure_minutes = max(laycan_variance, 0)
        laycan_status = "breach" if exposure_minutes else "clear"
        if not exposure_minutes and (voyage.laycan_end - completion_at).total_seconds() <= 12 * 3600:
            laycan_status = "watch"

    exposure_usd = _demurrage_exposure_usd(voyage=voyage, minutes=exposure_minutes)
    trust_status = trust.trust_status if trust else ""
    trust_blocks = bool(trust and trust_assessment_is_blocking(trust))
    confidence_score = trust.confidence_score if trust else (
        eta_projection.confidence_score if eta_projection else Decimal("0")
    )
    status = _projection_status(
        completion_at=completion_at,
        exposure_minutes=exposure_minutes,
        laycan_status=laycan_status,
        trust_status=trust_status,
    )
    customer_safe_to_share = bool(
        status not in {
            CustomerSafeCommercialProjection.Status.BLOCKED,
            CustomerSafeCommercialProjection.Status.UNKNOWN,
        }
        and not trust_blocks
    )
    return {
        "voyage": voyage,
        "trip": trip,
        "status": status,
        "customer_safe_eta": completion_at,
        "eta_band_start": (
            completion_at - timedelta(hours=2) if completion_at is not None else None
        ),
        "eta_band_end": (
            completion_at + timedelta(hours=2) if completion_at is not None else None
        ),
        "laycan_status": laycan_status,
        "laycan_variance_minutes": laycan_variance,
        "projected_demurrage_exposure_minutes": exposure_minutes,
        "projected_demurrage_exposure_usd": exposure_usd,
        "commitment_risk_level": _commitment_risk_level(status),
        "telemetry_trust_status": trust_status,
        "confidence_score": confidence_score,
        "customer_safe_to_share": customer_safe_to_share,
        "projection_only_disclaimer": PROJECTION_ONLY_DISCLAIMER,
        "details": {
            "voyageId": voyage.voyage_id,
            "vesselName": voyage.vessel_name,
            "customerName": voyage.customer_name,
            "laycanStart": voyage.laycan_start.isoformat(),
            "laycanEnd": voyage.laycan_end.isoformat(),
            "demurrageRateUsdPerDay": str(voyage.demurrage_rate_usd_per_day),
            "etaProjectionRef": eta_projection.projection_id if eta_projection else "",
            "etaProjectionStatus": eta_projection.status if eta_projection else "",
            "trustAssessmentRef": trust.assessment_id if trust else "",
            "projectionOnly": True,
            "finalCustomerCommitment": False,
            "finalDemurrageSettlement": False,
        },
    }


def _latest_eta_projection(trips: list[Trip]) -> LiveEtaProjection | None:
    trip_ids = [trip.id for trip in trips]
    discharge = (
        LiveEtaProjection.objects.filter(
            trip_id__in=trip_ids,
            schedule_event__event_type=ScheduleEvent.EventType.DISCHARGE_COMPLETE,
        )
        .select_related("schedule_event", "trip")
        .order_by("-calculated_at", "-id")
        .first()
    )
    if discharge:
        return discharge
    return (
        LiveEtaProjection.objects.filter(trip_id__in=trip_ids)
        .select_related("schedule_event", "trip")
        .order_by("-calculated_at", "-id")
        .first()
    )


def _projected_completion_at(
    trips: list[Trip],
    eta_projection: LiveEtaProjection | None,
):
    if eta_projection and eta_projection.observed_eta:
        return eta_projection.observed_eta
    if eta_projection:
        return eta_projection.planned_at
    return max((trip.planned_end for trip in trips), default=None)


def _trust_for_voyage(
    voyage: OGVVoyage,
    trips: list[Trip],
    trust_by_asset: dict[str, TelemetryTrustAssessment],
) -> TelemetryTrustAssessment | None:
    asset_codes = [voyage.voyage_id]
    for trip in trips:
        try:
            assignment = trip.assignment
        except Exception:
            assignment = None
        if not assignment:
            continue
        if assignment.tug_id and assignment.tug:
            asset_codes.append(assignment.tug.code)
        if assignment.barge_id and assignment.barge:
            asset_codes.append(assignment.barge.code)
        if assignment.cts_id and assignment.cts:
            asset_codes.append(assignment.cts.code)
    candidates = [trust_by_asset[code] for code in asset_codes if code in trust_by_asset]
    if not candidates:
        return None
    return sorted(candidates, key=_trust_sort_key)[0]


def _trust_sort_key(assessment: TelemetryTrustAssessment):
    order = {
        TelemetryTrustAssessment.TrustStatus.QUARANTINED: 0,
        TelemetryTrustAssessment.TrustStatus.MANUAL_CONFIRMATION_REQUIRED: 1,
        TelemetryTrustAssessment.TrustStatus.UNKNOWN: 2,
        TelemetryTrustAssessment.TrustStatus.DEGRADED: 3,
        TelemetryTrustAssessment.TrustStatus.TRUSTED: 4,
    }
    return (order.get(assessment.trust_status, 5), assessment.source_rank)


def _projection_status(
    *,
    completion_at,
    exposure_minutes: int,
    laycan_status: str,
    trust_status: str,
) -> str:
    if completion_at is None:
        return CustomerSafeCommercialProjection.Status.UNKNOWN
    if trust_status in {
        TelemetryTrustAssessment.TrustStatus.QUARANTINED,
        TelemetryTrustAssessment.TrustStatus.MANUAL_CONFIRMATION_REQUIRED,
        TelemetryTrustAssessment.TrustStatus.UNKNOWN,
    }:
        return CustomerSafeCommercialProjection.Status.BLOCKED
    if exposure_minutes > 0:
        return CustomerSafeCommercialProjection.Status.AT_RISK
    if laycan_status == "watch" or trust_status == TelemetryTrustAssessment.TrustStatus.DEGRADED:
        return CustomerSafeCommercialProjection.Status.WATCH
    return CustomerSafeCommercialProjection.Status.ON_TRACK


def _commitment_risk_level(status: str) -> str:
    if status == CustomerSafeCommercialProjection.Status.ON_TRACK:
        return CustomerSafeCommercialProjection.CommitmentRiskLevel.LOW
    if status == CustomerSafeCommercialProjection.Status.WATCH:
        return CustomerSafeCommercialProjection.CommitmentRiskLevel.WARNING
    if status in {
        CustomerSafeCommercialProjection.Status.AT_RISK,
        CustomerSafeCommercialProjection.Status.BLOCKED,
    }:
        return CustomerSafeCommercialProjection.CommitmentRiskLevel.CRITICAL
    return CustomerSafeCommercialProjection.CommitmentRiskLevel.UNKNOWN


def _run_summary(projection_specs: list[dict[str, Any]]) -> dict[str, Any]:
    exposure = sum(
        Decimal(str(spec["projected_demurrage_exposure_usd"]))
        for spec in projection_specs
    )
    return {
        "projectionCount": len(projection_specs),
        "atRiskCount": sum(
            1
            for spec in projection_specs
            if spec["status"]
            in {
                CustomerSafeCommercialProjection.Status.AT_RISK,
                CustomerSafeCommercialProjection.Status.BLOCKED,
            }
        ),
        "watchCount": sum(
            1
            for spec in projection_specs
            if spec["status"] == CustomerSafeCommercialProjection.Status.WATCH
        ),
        "customerSafeToShareCount": sum(
            1 for spec in projection_specs if spec["customer_safe_to_share"]
        ),
        "projectedDemurrageExposureUsd": str(exposure.quantize(Decimal("0.01"))),
        "projectionOnly": True,
        "finalSettlement": False,
    }


def _select_active_plan_version() -> PlanVersion | None:
    queryset = PlanVersion.objects.select_related("plan", "source_version")
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
    }


def _input_signature(input_summary: dict[str, Any]) -> str:
    payload = json.dumps(
        input_summary,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _iso_or_none(value) -> str | None:
    return value.isoformat() if value else None


def _ceil_minutes(delta) -> int:
    seconds = delta.total_seconds()
    if seconds <= 0:
        return int(seconds // 60)
    return int((seconds + 59) // 60)


def _demurrage_exposure_usd(*, voyage: OGVVoyage, minutes: int) -> Decimal:
    if minutes <= 0:
        return Decimal("0.00")
    amount = Decimal(minutes) * voyage.demurrage_rate_usd_per_day / Decimal("1440")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
