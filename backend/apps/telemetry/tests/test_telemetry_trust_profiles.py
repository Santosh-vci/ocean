from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizations.models import Organization
from apps.planning.models import BridgeWindow, OGVVoyage, TideWindow
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import (
    ApprovalDecision,
    ApprovalRequest,
    Plan,
    PlanVersion,
    PublishabilityAssessment,
    Trip,
)
from apps.scheduling.publishability_services import assess_plan_publishability
from apps.telemetry.models import (
    AssetIdentity,
    LatestAssetState,
    TelemetrySource,
    TelemetryTrustAssessment,
    TelemetryTrustProfile,
)
from apps.telemetry.telemetry_trust_services import (
    TELEMETRY_TRUST_ALGORITHM_VERSION,
    assess_telemetry_trust,
    seed_telemetry_trust_profiles,
)


@pytest.mark.django_db
def test_seed_phase0_master_data_only_creates_trust_profile_without_assessments():
    call_command("seed_phase0", "--master-data-only", verbosity=0)

    profile = TelemetryTrustProfile.objects.get(profile_key="telemetry_trust_default_v1")
    assert profile.status == TelemetryTrustProfile.Status.ACTIVE
    assert profile.source_hierarchy
    assert TelemetryTrustAssessment.objects.count() == 0


@pytest.mark.django_db
def test_trust_assessment_statuses_are_deterministic():
    profile = seed_telemetry_trust_profiles()[0]

    trusted = assess_telemetry_trust(
        latest_state=make_latest_state("TRUSTED", confidence_score=Decimal("96")),
        profile=profile,
    )
    degraded = assess_telemetry_trust(
        latest_state=make_latest_state(
            "DEGRADED",
            freshness_status=LatestAssetState.FreshnessStatus.AGING,
            confidence_score=Decimal("72"),
        ),
        profile=profile,
    )
    quarantined = assess_telemetry_trust(
        latest_state=make_latest_state("QUAR", confidence_score=Decimal("12")),
        profile=profile,
    )
    manual = assess_telemetry_trust(
        latest_state=make_latest_state(
            "MANUAL",
            freshness_status=LatestAssetState.FreshnessStatus.MISSING,
            confidence_score=Decimal("72"),
        ),
        profile=profile,
    )

    assert trusted.trust_status == TelemetryTrustAssessment.TrustStatus.TRUSTED
    assert degraded.trust_status == TelemetryTrustAssessment.TrustStatus.DEGRADED
    assert quarantined.trust_status == TelemetryTrustAssessment.TrustStatus.QUARANTINED
    assert manual.trust_status == (
        TelemetryTrustAssessment.TrustStatus.MANUAL_CONFIRMATION_REQUIRED
    )
    assert trusted.algorithm_version == TELEMETRY_TRUST_ALGORITHM_VERSION


@pytest.mark.django_db
def test_publishability_blocks_quarantined_trust_and_warns_for_degraded_trust():
    user, org = make_user("trust-publish")
    version = make_clean_approved_plan(user, org)
    trip = version.trips.get()
    state = make_latest_state(trip.voyage.voyage_id, confidence_score=Decimal("12"))
    assess_telemetry_trust(latest_state=state, plan_version=version, actor=user)

    blocked = assess_plan_publishability(plan_version=version, actor=user)

    assert blocked.status == PublishabilityAssessment.Status.BLOCKED
    assert any(
        detail["key"] == "telemetry_trust_clear"
        and detail["status"] == "blocked"
        and detail["actionId"] == "REVIEW_TELEMETRY_TRUST_STATE"
        for detail in blocked.details
    )

    TelemetryTrustAssessment.objects.all().delete()
    state.confidence_score = Decimal("72")
    state.freshness_status = LatestAssetState.FreshnessStatus.AGING
    state.save(update_fields=["confidence_score", "freshness_status", "updated_at"])
    assess_telemetry_trust(latest_state=state, plan_version=version, actor=user)

    warning = assess_plan_publishability(plan_version=version, actor=user)

    assert warning.status == PublishabilityAssessment.Status.WARNING
    assert any(
        detail["key"] == "telemetry_trust_clear" and detail["status"] == "warning"
        for detail in warning.details
    )


@pytest.mark.django_db
def test_trust_assessment_api_uses_telemetry_view_permission():
    profile = seed_telemetry_trust_profiles()[0]
    state = make_latest_state("API-TRUST")
    user, org = make_user("trust-api", permissions=("telemetry.view",))
    path = "/api/telemetry/trust-assessments/assess/"

    anonymous = APIClient(HTTP_HOST="localhost").post(
        path,
        {"latest_state": state.id, "profile": profile.id},
        format="json",
    )
    assert anonymous.status_code in {401, 403}

    no_access = User.objects.create_user(username="trust-no-access", password="pw")
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(user=no_access)
    denied = client.post(path, {"latest_state": state.id}, format="json")
    assert denied.status_code == 403

    allowed = APIClient(HTTP_HOST="localhost")
    allowed.force_authenticate(user=user)
    created = allowed.post(
        path,
        {"latest_state": state.id, "profile": profile.id},
        format="json",
    )
    listed = allowed.get("/api/telemetry/trust-assessments/")

    assert created.status_code == 201
    assert created.data["trust_status"] == TelemetryTrustAssessment.TrustStatus.TRUSTED
    assert listed.status_code == 200
    assert listed.data[0]["assessment_id"] == created.data["assessment_id"]
    assert org is not None


def make_user(username: str, permissions=("schedule.view", "schedule.edit")):
    org = Organization.objects.create(
        name=username,
        slug=username,
        kind=Organization.Kind.BERAU,
    )
    user = User.objects.create_user(username=username, password="pw")
    assign(user, org, permissions)
    return user, org


def assign(user, organization, permission_codes):
    permissions = []
    for code in permission_codes:
        permission, _ = AccessPermission.objects.get_or_create(
            code=code,
            defaults={
                "module": code.split(".")[0],
                "action": code.split(".")[1],
                "description": code,
            },
        )
        permissions.append(permission)
    role = Role.objects.create(name=f"role-{user.username}", code=f"role-{user.username}")
    role.permissions.set(permissions)
    scope = DataScope.objects.create(
        name=f"scope-{user.username}",
        code=f"scope-{user.username}",
        scope_type=DataScope.ScopeType.ALL_NETWORK,
    )
    UserRoleAssignment.objects.create(
        user=user,
        role=role,
        organization=organization,
        data_scope=scope,
    )


def make_latest_state(
    asset_code: str,
    *,
    freshness_status=LatestAssetState.FreshnessStatus.FRESH,
    confidence_score=Decimal("96"),
    source_status=TelemetrySource.Status.ACTIVE,
):
    source = TelemetrySource.objects.create(
        source_id=f"SRC-{asset_code}",
        name=f"Source {asset_code}",
        source_type=TelemetrySource.SourceType.DEVICE_GATEWAY,
        status=source_status,
    )
    identity = AssetIdentity.objects.create(
        source=source,
        asset_type=AssetIdentity.AssetType.OGV,
        asset_code=asset_code,
        external_id=f"EXT-{asset_code}",
        external_id_type=AssetIdentity.ExternalIdType.TRACKER_ID,
        is_primary=True,
    )
    return LatestAssetState.objects.create(
        asset_type=AssetIdentity.AssetType.OGV,
        asset_code=asset_code,
        source=source,
        asset_identity=identity,
        freshness_status=freshness_status,
        confidence_score=confidence_score,
        last_seen_at=timezone.now(),
    )


def make_clean_approved_plan(user, org) -> PlanVersion:
    now = timezone.now()
    plan = Plan.objects.create(
        code=f"PLAN-{org.slug}",
        name="Trust publishability plan",
        organization=org,
        horizon_start=now,
        horizon_end=now + timedelta(days=3),
        status=Plan.Status.ACTIVE,
    )
    version = PlanVersion.objects.create(
        plan=plan,
        version_no=1,
        status=PlanVersion.Status.APPROVED,
        generated_at=now,
        created_by=user,
    )
    voyage = OGVVoyage.objects.create(
        voyage_id=f"VOY-{org.slug}",
        vessel_name="MV Trust",
        customer_name="Customer",
        eta=now,
        laycan_start=now,
        laycan_end=now + timedelta(days=2),
        required_mt=12000,
        organization=org,
    )
    Trip.objects.create(
        plan_version=version,
        trip_id=f"TRIP-{org.slug}",
        sequence=1,
        voyage=voyage,
        planned_start=now,
        planned_end=now + timedelta(hours=8),
        planned_quantity_mt=12000,
    )
    make_windows(now)
    make_approved_request(version, user)
    return version


def make_windows(now):
    location = apps_location("TRUST")
    TideWindow.objects.create(
        code=f"TIDE-TRUST-{TideWindow.objects.count()}",
        location=location,
        window_start=now,
        window_end=now + timedelta(hours=12),
        min_water_level_m=Decimal("2.10"),
        max_loaded_draft_m=Decimal("4.50"),
        is_active=True,
    )
    BridgeWindow.objects.create(
        code=f"BRIDGE-TRUST-{BridgeWindow.objects.count()}",
        location=location,
        window_start=now,
        window_end=now + timedelta(hours=12),
        clearance_m=Decimal("12.50"),
        status=BridgeWindow.Status.OPEN,
        is_active=True,
    )


def apps_location(prefix):
    from apps.masters.models import Location

    return Location.objects.create(
        code=f"{prefix}-{Location.objects.count()}",
        name=f"{prefix} Location",
        location_type=Location.LocationType.TIDE_GATE,
        latitude=Decimal("-1.100000"),
        longitude=Decimal("118.100000"),
    )


def make_approved_request(version, user):
    request = ApprovalRequest.objects.create(
        request_id=f"APR-{version.plan.code}-V{version.version_no}",
        plan_version=version,
        status=ApprovalRequest.Status.APPROVED,
        required_authorities=[
            ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
            ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
        ],
        reason="Trust publishability test approval.",
        requested_by=user,
        decided_at=timezone.now(),
    )
    for authority in request.required_authorities:
        ApprovalDecision.objects.create(
            approval_request=request,
            organization=version.plan.organization,
            authority_role=authority,
            actor=user,
            decision=ApprovalDecision.Decision.APPROVE,
        )
    return request
