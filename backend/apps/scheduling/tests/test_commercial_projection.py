from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.flows.models import FlowRun
from apps.organizations.models import Organization
from apps.planning.models import OGVVoyage
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.commercial_projection_services import (
    COMMERCIAL_PROJECTION_ALGORITHM_VERSION,
    generate_customer_safe_commercial_projections,
)
from apps.scheduling.models import (
    CommercialProjectionRun,
    CustomerSafeCommercialProjection,
    Plan,
    PlanVersion,
    PublishabilityAssessment,
    ScheduleEvent,
    Trip,
)
from apps.telemetry.models import (
    AssetIdentity,
    LatestAssetState,
    LiveEtaProjection,
    TelemetrySource,
    TelemetryTrustAssessment,
)
from apps.telemetry.telemetry_trust_services import assess_telemetry_trust


@pytest.mark.django_db
def test_commercial_projection_generates_customer_safe_exposure_proxy_only():
    user, org = make_user("commercial-proxy")
    version, voyage, trip = make_plan_with_trip(
        user,
        org,
        laycan_end_offset_hours=8,
        planned_end_offset_hours=10,
        demurrage_rate=Decimal("14400.00"),
    )

    run = generate_customer_safe_commercial_projections(plan_version=version, actor=user)
    projection = run.projections.get()

    assert run.status == CommercialProjectionRun.Status.SUCCEEDED
    assert run.algorithm_version == COMMERCIAL_PROJECTION_ALGORITHM_VERSION
    assert run.audit_lineage["projectionOnly"] is True
    assert projection.voyage == voyage
    assert projection.trip == trip
    assert projection.status == CustomerSafeCommercialProjection.Status.AT_RISK
    assert projection.laycan_status == "breach"
    assert projection.projected_demurrage_exposure_minutes == 120
    assert projection.projected_demurrage_exposure_usd == Decimal("1200.00")
    assert projection.customer_safe_to_share is True
    assert "not a customer commitment" in projection.projection_only_disclaimer
    assert projection.details["finalDemurrageSettlement"] is False


@pytest.mark.django_db
def test_commercial_projection_uses_live_eta_and_degraded_trust_as_watch():
    user, org = make_user("commercial-eta")
    version, voyage, trip = make_plan_with_trip(
        user,
        org,
        laycan_end_offset_hours=20,
        planned_end_offset_hours=8,
    )
    event = ScheduleEvent.objects.create(
        trip=trip,
        sequence=1,
        event_type=ScheduleEvent.EventType.DISCHARGE_COMPLETE,
        planned_at=trip.planned_end,
        location_label="CTS",
        status=ScheduleEvent.Status.PLANNED,
    )
    source, identity = make_source_identity(voyage.voyage_id)
    LiveEtaProjection.objects.create(
        projection_id="ETA-COMMERCIAL-1",
        asset_type=AssetIdentity.AssetType.OGV,
        asset_code=voyage.voyage_id,
        source=source,
        asset_identity=identity,
        trip=trip,
        schedule_event=event,
        planned_at=trip.planned_end,
        observed_eta=trip.planned_end + timedelta(hours=2),
        variance_minutes=120,
        confidence_score=Decimal("72"),
        status=LiveEtaProjection.Status.WATCH,
        calculated_at=timezone.now(),
    )
    state = LatestAssetState.objects.create(
        asset_type=AssetIdentity.AssetType.OGV,
        asset_code=voyage.voyage_id,
        source=source,
        asset_identity=identity,
        freshness_status=LatestAssetState.FreshnessStatus.AGING,
        confidence_score=Decimal("72"),
        last_seen_at=timezone.now(),
    )
    assess_telemetry_trust(latest_state=state, plan_version=version, actor=user)

    run = generate_customer_safe_commercial_projections(plan_version=version, actor=user)
    projection = run.projections.get()

    assert projection.customer_safe_eta == trip.planned_end + timedelta(hours=2)
    assert projection.status == CustomerSafeCommercialProjection.Status.WATCH
    assert projection.telemetry_trust_status == TelemetryTrustAssessment.TrustStatus.DEGRADED
    assert projection.customer_safe_to_share is True
    assert projection.projected_demurrage_exposure_minutes == 0


@pytest.mark.django_db
def test_commercial_projection_generation_does_not_mutate_business_tables():
    user, org = make_user("commercial-readonly")
    version, _voyage, _trip = make_plan_with_trip(user, org)
    before = business_counts()

    generate_customer_safe_commercial_projections(plan_version=version, actor=user)

    after = business_counts()
    assert after == {
        **before,
        "commercial_runs": before["commercial_runs"] + 1,
        "commercial_projections": before["commercial_projections"] + 1,
    }


@pytest.mark.django_db
def test_commercial_projection_api_permissions_and_overview_payload():
    user, org = make_user("commercial-api", permissions=("schedule.view",))
    version, _voyage, _trip = make_plan_with_trip(user, org)
    path = "/api/scheduling/commercial-projection-runs/generate/"

    anonymous = APIClient(HTTP_HOST="localhost").post(
        path,
        {"plan_version": version.id},
        format="json",
    )
    assert anonymous.status_code in {401, 403}

    no_access = User.objects.create_user(username="commercial-no-access", password="pw")
    client = APIClient(HTTP_HOST="localhost")
    client.force_authenticate(user=no_access)
    denied = client.post(path, {"plan_version": version.id}, format="json")
    assert denied.status_code == 403

    allowed = APIClient(HTTP_HOST="localhost")
    allowed.force_authenticate(user=user)
    created = allowed.post(path, {"plan_version": version.id}, format="json")
    overview = allowed.get("/api/scheduling/overview/")

    assert created.status_code == 201
    assert created.data["summary"]["projectionOnly"] is True
    assert created.data["projections"][0]["projection_only_disclaimer"]
    assert AuditEvent.objects.filter(action="commercial_projection.run.generate").exists()
    assert overview.status_code == 200
    assert overview.data["commercialProjectionRun"]["run_id"] == created.data["run_id"]
    assert overview.data["commercialProjections"][0]["run_ref"] == created.data["run_id"]
    assert overview.data["commercialProjectionSummary"]["projectionOnly"] is True


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


def make_plan_with_trip(
    user,
    org,
    *,
    laycan_end_offset_hours=24,
    planned_end_offset_hours=8,
    demurrage_rate=Decimal("12000.00"),
):
    now = timezone.now().replace(microsecond=0)
    plan = Plan.objects.create(
        code=f"PLAN-{org.slug}",
        name="Commercial projection plan",
        organization=org,
        horizon_start=now,
        horizon_end=now + timedelta(days=3),
        status=Plan.Status.ACTIVE,
    )
    version = PlanVersion.objects.create(
        plan=plan,
        version_no=1,
        status=PlanVersion.Status.GENERATED,
        generated_at=now,
        created_by=user,
    )
    voyage = OGVVoyage.objects.create(
        voyage_id=f"VOY-{org.slug}",
        vessel_name="MV Commercial",
        customer_name="Customer",
        eta=now,
        laycan_start=now,
        laycan_end=now + timedelta(hours=laycan_end_offset_hours),
        required_mt=12000,
        demurrage_rate_usd_per_day=demurrage_rate,
        organization=org,
    )
    trip = Trip.objects.create(
        plan_version=version,
        trip_id=f"TRIP-{org.slug}",
        sequence=1,
        voyage=voyage,
        planned_start=now,
        planned_end=now + timedelta(hours=planned_end_offset_hours),
        planned_quantity_mt=12000,
    )
    return version, voyage, trip


def make_source_identity(asset_code: str):
    source = TelemetrySource.objects.create(
        source_id=f"SRC-{asset_code}",
        name=f"Source {asset_code}",
        source_type=TelemetrySource.SourceType.DEVICE_GATEWAY,
        status=TelemetrySource.Status.ACTIVE,
    )
    identity = AssetIdentity.objects.create(
        source=source,
        asset_type=AssetIdentity.AssetType.OGV,
        asset_code=asset_code,
        external_id=f"EXT-{asset_code}",
        external_id_type=AssetIdentity.ExternalIdType.TRACKER_ID,
        is_primary=True,
    )
    return source, identity


def business_counts():
    return {
        "plan_versions": PlanVersion.objects.count(),
        "trips": Trip.objects.count(),
        "publishability": PublishabilityAssessment.objects.count(),
        "flow_runs": FlowRun.objects.count(),
        "eta_projections": LiveEtaProjection.objects.count(),
        "commercial_runs": CommercialProjectionRun.objects.count(),
        "commercial_projections": CustomerSafeCommercialProjection.objects.count(),
    }
