from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db.models import Max, Q
from django.utils import timezone

from apps.scheduling.models import Assignment, PlanVersion, Trip

from .models import (
    AssetIdentity,
    LatestAssetState,
    TelemetrySource,
    TelemetryTrustAssessment,
    TelemetryTrustProfile,
)

TELEMETRY_TRUST_ALGORITHM_VERSION = "phase6.6-telemetry-trust"
DEFAULT_PROFILE_KEY = "telemetry_trust_default_v1"
DEFAULT_SOURCE_HIERARCHY = [
    {"source_type": TelemetrySource.SourceType.MANUAL, "rank": 1, "label": "Manual confirmed"},
    {
        "source_type": TelemetrySource.SourceType.DEVICE_GATEWAY,
        "rank": 2,
        "label": "Owned GPS tracker",
    },
    {"source_type": TelemetrySource.SourceType.VENDOR_API, "rank": 3, "label": "Vendor GPS/AIS"},
    {
        "source_type": TelemetrySource.SourceType.SYNTHETIC_GPS,
        "rank": 4,
        "label": "Synthetic GPS",
    },
    {
        "source_type": TelemetrySource.SourceType.SYNTHETIC_AIS,
        "rank": 5,
        "label": "Synthetic AIS",
    },
]
DEFAULT_FRESHNESS_THRESHOLDS = {
    "trusted_statuses": ["fresh"],
    "degraded_statuses": ["aging", "stale"],
    "manual_confirmation_statuses": ["missing"],
}
DEFAULT_CONFIDENCE_THRESHOLDS = {
    "trusted_min": 80,
    "degraded_min": 50,
    "quarantine_below": 25,
}
DEFAULT_IDENTITY_RULES = {
    "require_primary_identity": False,
    "require_asset_object_id": False,
}
DEFAULT_QUARANTINE_RULES = {
    "quarantine_source_statuses": [
        TelemetrySource.Status.PAUSED,
        TelemetrySource.Status.RETIRED,
    ],
    "quarantine_signal_qualities": ["invalid"],
}


@dataclass(frozen=True, slots=True)
class TelemetryTrustSummary:
    profile_key: str
    latest_assessment_count: int
    trusted_count: int
    degraded_count: int
    blocking_count: int
    unknown_count: int
    latest_assessed_at: Any
    latest_assessments: list[TelemetryTrustAssessment]


def seed_telemetry_trust_profiles() -> list[TelemetryTrustProfile]:
    profiles = getattr(settings, "TELEMETRY_TRUST_PROFILES", None)
    if not profiles:
        profiles = [
            {
                "profile_key": DEFAULT_PROFILE_KEY,
                "name": "Telemetry trust default",
                "version": 1,
                "status": TelemetryTrustProfile.Status.ACTIVE,
                "source_hierarchy": DEFAULT_SOURCE_HIERARCHY,
                "freshness_thresholds": DEFAULT_FRESHNESS_THRESHOLDS,
                "confidence_thresholds": DEFAULT_CONFIDENCE_THRESHOLDS,
                "identity_rules": DEFAULT_IDENTITY_RULES,
                "quarantine_rules": DEFAULT_QUARANTINE_RULES,
                "metadata": {"source": "settings/default"},
            }
        ]

    seeded: list[TelemetryTrustProfile] = []
    for profile in profiles:
        profile_key = str(profile.get("profile_key") or DEFAULT_PROFILE_KEY)
        obj, _created = TelemetryTrustProfile.objects.update_or_create(
            profile_key=profile_key,
            defaults={
                "name": str(profile.get("name") or profile_key.replace("_", " ").title()),
                "version": int(profile.get("version") or 1),
                "status": str(profile.get("status") or TelemetryTrustProfile.Status.ACTIVE),
                "source_hierarchy": profile.get("source_hierarchy") or DEFAULT_SOURCE_HIERARCHY,
                "freshness_thresholds": (
                    profile.get("freshness_thresholds") or DEFAULT_FRESHNESS_THRESHOLDS
                ),
                "confidence_thresholds": (
                    profile.get("confidence_thresholds") or DEFAULT_CONFIDENCE_THRESHOLDS
                ),
                "identity_rules": profile.get("identity_rules") or DEFAULT_IDENTITY_RULES,
                "quarantine_rules": (
                    profile.get("quarantine_rules") or DEFAULT_QUARANTINE_RULES
                ),
                "metadata": profile.get("metadata") or {"source": "settings"},
            },
        )
        seeded.append(obj)
    return seeded


def get_default_trust_profile() -> TelemetryTrustProfile:
    profile = (
        TelemetryTrustProfile.objects.filter(
            profile_key=DEFAULT_PROFILE_KEY,
            status=TelemetryTrustProfile.Status.ACTIVE,
        )
        .order_by("-version", "-id")
        .first()
    )
    if profile:
        return profile
    return seed_telemetry_trust_profiles()[0]


def assess_telemetry_trust(
    *,
    latest_state: LatestAssetState | None = None,
    plan_version: PlanVersion | None = None,
    profile: TelemetryTrustProfile | None = None,
    actor=None,
    persist: bool = True,
) -> TelemetryTrustAssessment | list[TelemetryTrustAssessment] | list[dict[str, Any]]:
    resolved_profile = profile or get_default_trust_profile()
    states = _states_for_assessment(latest_state=latest_state, plan_version=plan_version)
    payloads = [
        _assessment_payload(
            state=state,
            profile=resolved_profile,
            plan_version=plan_version,
            actor=actor,
        )
        for state in states
    ]

    if not persist:
        return payloads[0] if latest_state is not None and payloads else payloads

    assessments = [
        TelemetryTrustAssessment.objects.create(**payload)
        for payload in payloads
    ]
    if latest_state is not None:
        return assessments[0] if assessments else []
    return assessments


def latest_trust_assessments_for_plan(
    plan_version: PlanVersion | None,
) -> list[TelemetryTrustAssessment]:
    if plan_version is None:
        return []
    states = _states_for_assessment(latest_state=None, plan_version=plan_version)
    if not states:
        return []
    latest: list[TelemetryTrustAssessment] = []
    for state in states:
        assessment = (
            TelemetryTrustAssessment.objects.filter(
                latest_state=state,
            )
            .select_related("profile", "source", "asset_identity", "latest_state")
            .order_by("-assessed_at", "-id")
            .first()
        )
        if assessment:
            latest.append(assessment)
    return latest


def latest_trust_assessment_summary(
    plan_version: PlanVersion | None,
) -> TelemetryTrustSummary:
    assessments = latest_trust_assessments_for_plan(plan_version)
    profile = assessments[0].profile if assessments else (
        TelemetryTrustProfile.objects.filter(
            profile_key=DEFAULT_PROFILE_KEY,
            status=TelemetryTrustProfile.Status.ACTIVE,
        )
        .order_by("-version", "-id")
        .first()
    )
    blocking_statuses = {
        TelemetryTrustAssessment.TrustStatus.QUARANTINED,
        TelemetryTrustAssessment.TrustStatus.MANUAL_CONFIRMATION_REQUIRED,
        TelemetryTrustAssessment.TrustStatus.UNKNOWN,
    }
    return TelemetryTrustSummary(
        profile_key=profile.profile_key if profile else DEFAULT_PROFILE_KEY,
        latest_assessment_count=len(assessments),
        trusted_count=sum(
            1
            for assessment in assessments
            if assessment.trust_status == TelemetryTrustAssessment.TrustStatus.TRUSTED
        ),
        degraded_count=sum(
            1
            for assessment in assessments
            if assessment.trust_status == TelemetryTrustAssessment.TrustStatus.DEGRADED
        ),
        blocking_count=sum(
            1 for assessment in assessments if assessment.trust_status in blocking_statuses
        ),
        unknown_count=sum(
            1
            for assessment in assessments
            if assessment.trust_status == TelemetryTrustAssessment.TrustStatus.UNKNOWN
        ),
        latest_assessed_at=max(
            (assessment.assessed_at for assessment in assessments),
            default=None,
        ),
        latest_assessments=assessments,
    )


def latest_trust_input_time(plan_version: PlanVersion | None):
    if plan_version is None:
        return None
    states = _states_for_assessment(latest_state=None, plan_version=plan_version)
    values = [
        value
        for value in [
            LatestAssetState.objects.filter(id__in=[state.id for state in states]).aggregate(
                value=Max("updated_at")
            )["value"],
            plan_version.updated_at,
        ]
        if value is not None
    ]
    return max(values) if values else None


def _states_for_assessment(
    *,
    latest_state: LatestAssetState | None,
    plan_version: PlanVersion | None,
) -> list[LatestAssetState]:
    queryset = LatestAssetState.objects.select_related(
        "source",
        "asset_identity",
        "last_ping",
    )
    if latest_state is not None:
        return [queryset.get(pk=latest_state.pk)]
    if plan_version is None:
        return list(queryset.order_by("asset_type", "asset_code"))

    asset_codes = _plan_asset_codes(plan_version)
    if not asset_codes:
        return []
    return list(
        queryset.filter(asset_code__in=asset_codes).order_by("asset_type", "asset_code")
    )


def _plan_asset_codes(plan_version: PlanVersion) -> set[str]:
    trips = Trip.objects.filter(plan_version=plan_version).select_related("voyage")
    asset_codes = {
        trip.voyage.voyage_id
        for trip in trips
        if trip.voyage_id and trip.voyage and trip.voyage.voyage_id
    }
    assignments = Assignment.objects.filter(trip__plan_version=plan_version).select_related(
        "tug",
        "barge",
        "cts",
    )
    for assignment in assignments:
        if assignment.tug_id and assignment.tug:
            asset_codes.add(assignment.tug.code)
        if assignment.barge_id and assignment.barge:
            asset_codes.add(assignment.barge.code)
        if assignment.cts_id and assignment.cts:
            asset_codes.add(assignment.cts.code)
    return asset_codes


def _assessment_payload(
    *,
    state: LatestAssetState,
    profile: TelemetryTrustProfile,
    plan_version: PlanVersion | None,
    actor,
) -> dict[str, Any]:
    reasons: list[str] = []
    identity_status = _identity_match_status(state, profile)
    source_rank = _source_rank(state.source, profile)
    confidence_score = _decimal_score(state.confidence_score)
    trust_status = _trust_status(
        state=state,
        profile=profile,
        confidence_score=confidence_score,
        identity_status=identity_status,
        reasons=reasons,
    )
    evidence = {
        "sourceId": state.source.source_id,
        "sourceType": state.source.source_type,
        "sourceStatus": state.source.status,
        "sourceRank": source_rank,
        "externalId": state.asset_identity.external_id,
        "externalIdType": state.asset_identity.external_id_type,
        "isPrimaryIdentity": state.asset_identity.is_primary,
        "assetObjectId": state.asset_identity.asset_object_id,
        "lastSeenAt": state.last_seen_at.isoformat() if state.last_seen_at else None,
        "lastPingRef": state.last_ping.ping_id if state.last_ping_id else "",
        "lastPingSignalQuality": state.last_ping.signal_quality if state.last_ping_id else "",
        "planVersionId": plan_version.id if plan_version else None,
        "assessedBy": getattr(actor, "email", "") if actor is not None else "",
        "customerSafeProductionTruth": False,
    }
    return {
        "profile": profile,
        "source": state.source,
        "asset_identity": state.asset_identity,
        "latest_state": state,
        "asset_type": state.asset_type,
        "asset_code": state.asset_code,
        "trust_status": trust_status,
        "freshness_status": state.freshness_status,
        "confidence_score": confidence_score,
        "identity_match_status": identity_status,
        "source_rank": source_rank,
        "reasons": reasons,
        "evidence": evidence,
        "assessed_at": timezone.now(),
        "algorithm_version": TELEMETRY_TRUST_ALGORITHM_VERSION,
    }


def _trust_status(
    *,
    state: LatestAssetState,
    profile: TelemetryTrustProfile,
    confidence_score: Decimal,
    identity_status: str,
    reasons: list[str],
) -> str:
    confidence = profile.confidence_thresholds or DEFAULT_CONFIDENCE_THRESHOLDS
    quarantine_rules = profile.quarantine_rules or DEFAULT_QUARANTINE_RULES
    freshness = profile.freshness_thresholds or DEFAULT_FRESHNESS_THRESHOLDS
    signal_quality = state.last_ping.signal_quality if state.last_ping_id else ""

    if state.source.status in quarantine_rules.get("quarantine_source_statuses", []):
        reasons.append("source_status_quarantined")
        return TelemetryTrustAssessment.TrustStatus.QUARANTINED
    if signal_quality in quarantine_rules.get("quarantine_signal_qualities", []):
        reasons.append("signal_quality_quarantined")
        return TelemetryTrustAssessment.TrustStatus.QUARANTINED
    if confidence_score < _decimal_score(confidence.get("quarantine_below", 25)):
        reasons.append("confidence_below_quarantine_threshold")
        return TelemetryTrustAssessment.TrustStatus.QUARANTINED
    if identity_status != TelemetryTrustAssessment.IdentityMatchStatus.MATCHED:
        reasons.append(f"identity_{identity_status}")
        return TelemetryTrustAssessment.TrustStatus.MANUAL_CONFIRMATION_REQUIRED
    if state.freshness_status in freshness.get("manual_confirmation_statuses", []):
        reasons.append("freshness_requires_manual_confirmation")
        return TelemetryTrustAssessment.TrustStatus.MANUAL_CONFIRMATION_REQUIRED
    if state.freshness_status in freshness.get("degraded_statuses", []):
        reasons.append("freshness_degraded")
        return TelemetryTrustAssessment.TrustStatus.DEGRADED
    if state.source.status == TelemetrySource.Status.DEGRADED:
        reasons.append("source_status_degraded")
        return TelemetryTrustAssessment.TrustStatus.DEGRADED
    if confidence_score < _decimal_score(confidence.get("degraded_min", 50)):
        reasons.append("confidence_below_degraded_threshold")
        return TelemetryTrustAssessment.TrustStatus.DEGRADED
    if confidence_score < _decimal_score(confidence.get("trusted_min", 80)):
        reasons.append("confidence_below_trusted_threshold")
        return TelemetryTrustAssessment.TrustStatus.DEGRADED
    if state.freshness_status not in freshness.get("trusted_statuses", ["fresh"]):
        reasons.append("freshness_unknown")
        return TelemetryTrustAssessment.TrustStatus.UNKNOWN

    reasons.append("trusted_by_profile")
    return TelemetryTrustAssessment.TrustStatus.TRUSTED


def _identity_match_status(state: LatestAssetState, profile: TelemetryTrustProfile) -> str:
    identity_rules = profile.identity_rules or DEFAULT_IDENTITY_RULES
    identity = state.asset_identity
    if not identity.external_id or not identity.asset_code:
        return TelemetryTrustAssessment.IdentityMatchStatus.UNMAPPED
    if identity.asset_code != state.asset_code:
        return TelemetryTrustAssessment.IdentityMatchStatus.AMBIGUOUS
    if identity_rules.get("require_asset_object_id") and not identity.asset_object_id:
        return TelemetryTrustAssessment.IdentityMatchStatus.UNMAPPED
    if identity_rules.get("require_primary_identity") and not identity.is_primary:
        return TelemetryTrustAssessment.IdentityMatchStatus.AMBIGUOUS
    duplicates = AssetIdentity.objects.filter(
        source=identity.source,
        external_id=identity.external_id,
    ).exclude(pk=identity.pk)
    if duplicates.exists():
        return TelemetryTrustAssessment.IdentityMatchStatus.AMBIGUOUS
    return TelemetryTrustAssessment.IdentityMatchStatus.MATCHED


def _source_rank(source: TelemetrySource, profile: TelemetryTrustProfile) -> int:
    hierarchy = profile.source_hierarchy or DEFAULT_SOURCE_HIERARCHY
    for index, item in enumerate(hierarchy, start=1):
        if isinstance(item, dict):
            if item.get("source_type") == source.source_type:
                try:
                    return int(item.get("rank") or index)
                except (TypeError, ValueError):
                    return index
        elif item == source.source_type:
            return index
    return 999


def _decimal_score(value) -> Decimal:
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def trust_assessment_is_blocking(assessment: TelemetryTrustAssessment) -> bool:
    return assessment.trust_status in {
        TelemetryTrustAssessment.TrustStatus.QUARANTINED,
        TelemetryTrustAssessment.TrustStatus.MANUAL_CONFIRMATION_REQUIRED,
        TelemetryTrustAssessment.TrustStatus.UNKNOWN,
    }


def telemetry_trust_filter_for_active_assessments() -> Q:
    return Q(
        trust_status__in=[
            TelemetryTrustAssessment.TrustStatus.TRUSTED,
            TelemetryTrustAssessment.TrustStatus.DEGRADED,
            TelemetryTrustAssessment.TrustStatus.QUARANTINED,
            TelemetryTrustAssessment.TrustStatus.MANUAL_CONFIRMATION_REQUIRED,
            TelemetryTrustAssessment.TrustStatus.UNKNOWN,
        ]
    )
