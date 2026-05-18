import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.operations.models import (
    ConfirmedOperationalEvent,
    DeviceEndpoint,
    DeviceHealthSnapshot,
    IntegrationFeed,
    OperationalActualization,
    OperationalEventCandidate,
    OperationalEventKind,
    OperationsAssetType,
)
from apps.operations.services import operations_health_summary
from apps.organizations.models import Organization
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import ScheduleEvent


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


def organization():
    return Organization.objects.create(
        name="Coalflow Platform Operations",
        slug=f"coalflow-platform-ops-{timezone.now():%Y%m%d%H%M%S%f}",
        kind=Organization.Kind.PLATFORM,
    )


def feed():
    return IntegrationFeed.objects.create(
        feed_id="SYN-OPS-TEST",
        name="Synthetic operations test feed",
        feed_type=IntegrationFeed.FeedType.SYNTHETIC,
        trust_mode=IntegrationFeed.TrustMode.MANUAL_REVIEW,
    )


def trusted_feed():
    return IntegrationFeed.objects.create(
        feed_id="TRUSTED-OPS-TEST",
        name="Trusted operations test feed",
        feed_type=IntegrationFeed.FeedType.SYNTHETIC,
        trust_mode=IntegrationFeed.TrustMode.AUTO_CONFIRM_WITH_THRESHOLD,
        metadata={
            "confidenceThreshold": "90",
            "autoConfirmToleranceMinutes": 180,
        },
    )


def device(source_feed):
    return DeviceEndpoint.objects.create(
        device_id="DEV-JTY-SUARAN-TEST",
        feed=source_feed,
        device_type=DeviceEndpoint.DeviceType.JETTY_PLC,
        asset_type=OperationsAssetType.JETTY,
        asset_code="JTY-SUARAN",
    )


def candidate_payload(source_feed, source_device, **overrides):
    payload = {
        "feed": source_feed.id,
        "device": source_device.id,
        "source_kind": OperationalEventCandidate.SourceKind.SYNTHETIC,
        "event_kind": OperationalEventKind.JETTY_LOADING_STARTED,
        "asset_type": OperationsAssetType.JETTY,
        "asset_code": "JTY-SUARAN",
        "event_at": timezone.now().isoformat(),
        "confidence_score": "92.00",
        "dedupe_key": "ops-test-jetty-start-1",
        "payload": {"operator_note": "test"},
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_candidate_create_api_requires_operations_ingest_permission():
    org = organization()
    source_feed = feed()
    source_device = device(source_feed)
    viewer = User.objects.create_user(username="ops-viewer", password="secret")
    ingester = User.objects.create_user(username="ops-ingester", password="secret")
    assign(viewer, org, ["operations.view"])
    assign(ingester, org, ["operations.view", "operations.ingest"])

    client = APIClient()
    client.force_authenticate(viewer)
    denied = client.post(
        "/api/operations/event-candidates/",
        candidate_payload(source_feed, source_device),
        format="json",
    )

    client.force_authenticate(ingester)
    created = client.post(
        "/api/operations/event-candidates/",
        candidate_payload(source_feed, source_device),
        format="json",
    )

    assert denied.status_code == 403
    assert created.status_code == 201
    assert created.data["candidate_id"].startswith("OEC-")
    assert created.data["status"] == OperationalEventCandidate.Status.PENDING
    assert OperationalEventCandidate.objects.count() == 1


@pytest.mark.django_db
def test_confirm_candidate_requires_domain_authority_and_records_audit_event():
    org = organization()
    source_feed = feed()
    source_device = device(source_feed)
    candidate = OperationalEventCandidate.objects.create(
        **{
            key: value
            for key, value in candidate_payload(source_feed, source_device).items()
            if key not in {"feed", "device"}
        },
        feed=source_feed,
        device=source_device,
    )
    viewer = User.objects.create_user(username="ops-confirm-viewer", password="secret")
    jetty_controller = User.objects.create_user(username="ops-jetty-controller", password="secret")
    assign(viewer, org, ["operations.view"])
    assign(jetty_controller, org, ["operations.view", "operations.confirm_jetty"])

    client = APIClient()
    client.force_authenticate(viewer)
    denied = client.post(
        f"/api/operations/event-candidates/{candidate.id}/confirm/",
        {"reason_code": "operator_verified"},
        format="json",
    )

    client.force_authenticate(jetty_controller)
    confirmed = client.post(
        f"/api/operations/event-candidates/{candidate.id}/confirm/",
        {"reason_code": "operator_verified", "metadata": {"source": "unit-test"}},
        format="json",
    )

    candidate.refresh_from_db()
    event = ConfirmedOperationalEvent.objects.get(candidate=candidate)

    assert denied.status_code == 403
    assert confirmed.status_code == 201
    assert confirmed.data["event_id"] == event.event_id
    assert candidate.status == OperationalEventCandidate.Status.CONFIRMED
    assert event.confirmed_by == jetty_controller
    assert event.reason_code == "operator_verified"
    assert OperationalActualization.objects.filter(confirmed_event=event, status="skipped").exists()
    assert AuditEvent.objects.filter(
        action="operational_event.confirmed",
        object_id=str(event.pk),
    ).exists()


@pytest.mark.django_db
def test_bridge_candidate_requires_bridge_confirmation_permission():
    org = organization()
    source_feed = feed()
    source_device = device(source_feed)
    candidate = OperationalEventCandidate.objects.create(
        feed=source_feed,
        device=source_device,
        source_kind=OperationalEventCandidate.SourceKind.SYNTHETIC,
        event_kind=OperationalEventKind.BRIDGE_CROSSED,
        asset_type=OperationsAssetType.BRIDGE,
        asset_code="BRDG-UI-OPERATING-01",
        event_at=timezone.now(),
        confidence_score="90.00",
    )
    jetty_controller = User.objects.create_user(username="ops-jetty-only", password="secret")
    bridge_controller = User.objects.create_user(
        username="ops-bridge-controller",
        password="secret",
    )
    assign(jetty_controller, org, ["operations.view", "operations.confirm_jetty"])
    assign(bridge_controller, org, ["operations.view", "operations.confirm_bridge"])

    client = APIClient()
    client.force_authenticate(jetty_controller)
    denied = client.post(f"/api/operations/event-candidates/{candidate.id}/confirm/")

    client.force_authenticate(bridge_controller)
    confirmed = client.post(f"/api/operations/event-candidates/{candidate.id}/confirm/")

    assert denied.status_code == 403
    assert confirmed.status_code == 201
    assert ConfirmedOperationalEvent.objects.filter(candidate=candidate).exists()


@pytest.mark.django_db
def test_feed_and_candidate_model_constraints_are_enforced():
    source_feed = feed()
    source_device = device(source_feed)

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            IntegrationFeed.objects.create(
                feed_id=source_feed.feed_id,
                name="Duplicate feed",
                feed_type=IntegrationFeed.FeedType.SYNTHETIC,
            )

    first = OperationalEventCandidate.objects.create(
        feed=source_feed,
        device=source_device,
        source_kind=OperationalEventCandidate.SourceKind.SYNTHETIC,
        event_kind=OperationalEventKind.JETTY_LOADING_STARTED,
        asset_type=OperationsAssetType.JETTY,
        asset_code="JTY-SUARAN",
        event_at=timezone.now(),
        dedupe_key="same-source-event",
    )
    second = OperationalEventCandidate.objects.create(
        feed=source_feed,
        device=source_device,
        source_kind=OperationalEventCandidate.SourceKind.SYNTHETIC,
        event_kind=OperationalEventKind.JETTY_LOADING_STARTED,
        asset_type=OperationsAssetType.JETTY,
        asset_code="JTY-SUARAN",
        event_at=timezone.now(),
        dedupe_key="same-source-event",
    )

    assert first.dedupe_key == second.dedupe_key


@pytest.mark.django_db
def test_trusted_ingest_matches_schedule_event_auto_confirms_and_actualizes():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)
    source_feed = trusted_feed()
    load_start = ScheduleEvent.objects.select_related(
        "trip",
        "trip__assignment",
        "trip__assignment__jetty",
    ).filter(event_type=ScheduleEvent.EventType.LOAD_START).order_by("planned_at").first()
    source_device = DeviceEndpoint.objects.create(
        device_id="DEV-JTY-SUARAN-TRUSTED",
        feed=source_feed,
        device_type=DeviceEndpoint.DeviceType.JETTY_PLC,
        asset_type=OperationsAssetType.JETTY,
        asset_code=load_start.trip.assignment.jetty.code,
    )
    actual_at = load_start.planned_at + timezone.timedelta(minutes=12)
    user = User.objects.get(username="admin@coalflow.local")
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/operations/event-candidates/ingest/",
        {
            "feed_id": source_feed.feed_id,
            "device_id": source_device.device_id,
            "event_kind": OperationalEventKind.JETTY_LOADING_STARTED,
            "asset_type": OperationsAssetType.JETTY,
            "asset_code": source_device.asset_code,
            "schedule_event_id": load_start.id,
            "event_at": actual_at.isoformat(),
            "confidence_score": "96.00",
            "dedupe_key": "trusted-load-start-1",
            "payload": {"source_event_id": "PLC-LOAD-START-1"},
        },
        format="json",
    )

    load_start.refresh_from_db()
    load_start.trip.refresh_from_db()
    load_start.trip.assignment.refresh_from_db()
    candidate = OperationalEventCandidate.objects.get(dedupe_key="trusted-load-start-1")
    event = ConfirmedOperationalEvent.objects.get(candidate=candidate)

    assert response.status_code == 201
    assert response.data["auto_confirmed"] is True
    assert response.data["trust_evaluation"]["decision"] == "auto_confirm"
    assert candidate.status == OperationalEventCandidate.Status.AUTO_CONFIRMED
    assert event.confirmation_mode == ConfirmedOperationalEvent.ConfirmationMode.AUTO_THRESHOLD
    assert load_start.actual_at == actual_at
    assert load_start.status == ScheduleEvent.Status.ACTUAL
    assert load_start.trip.status == "loading"
    assert load_start.trip.assignment.status == "loading"
    assert OperationalActualization.objects.filter(
        confirmed_event=event,
        status=OperationalActualization.Status.APPLIED,
    ).count() == 3


@pytest.mark.django_db
def test_low_confidence_trusted_ingest_remains_pending_without_actualization():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)
    source_feed = trusted_feed()
    load_start = ScheduleEvent.objects.filter(
        event_type=ScheduleEvent.EventType.LOAD_START
    ).order_by("planned_at").first()
    source_device = DeviceEndpoint.objects.create(
        device_id="DEV-JTY-SUARAN-LOW-CONF",
        feed=source_feed,
        device_type=DeviceEndpoint.DeviceType.JETTY_PLC,
        asset_type=OperationsAssetType.JETTY,
        asset_code=load_start.resource_code,
    )
    user = User.objects.get(username="admin@coalflow.local")
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/operations/event-candidates/ingest/",
        {
            "feed_id": source_feed.feed_id,
            "device_id": source_device.device_id,
            "event_kind": OperationalEventKind.JETTY_LOADING_STARTED,
            "asset_type": OperationsAssetType.JETTY,
            "asset_code": source_device.asset_code,
            "schedule_event_id": load_start.id,
            "event_at": (load_start.planned_at + timezone.timedelta(minutes=10)).isoformat(),
            "confidence_score": "42.00",
            "dedupe_key": "low-confidence-load-start",
        },
        format="json",
    )

    load_start.refresh_from_db()
    candidate = OperationalEventCandidate.objects.get(dedupe_key="low-confidence-load-start")

    assert response.status_code == 201
    assert response.data["auto_confirmed"] is False
    assert "confidence_below_threshold" in response.data["trust_evaluation"]["reasons"]
    assert candidate.status == OperationalEventCandidate.Status.PENDING
    assert load_start.actual_at is None
    assert ConfirmedOperationalEvent.objects.filter(candidate=candidate).count() == 0


@pytest.mark.django_db
def test_duplicate_ingest_is_marked_duplicate_and_does_not_create_second_confirmed_event():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)
    source_feed = trusted_feed()
    load_start = ScheduleEvent.objects.filter(
        event_type=ScheduleEvent.EventType.LOAD_START
    ).order_by("planned_at").first()
    source_device = DeviceEndpoint.objects.create(
        device_id="DEV-JTY-SUARAN-DUPE",
        feed=source_feed,
        device_type=DeviceEndpoint.DeviceType.JETTY_PLC,
        asset_type=OperationsAssetType.JETTY,
        asset_code=load_start.resource_code,
    )
    user = User.objects.get(username="admin@coalflow.local")
    client = APIClient()
    client.force_authenticate(user)
    payload = {
        "feed_id": source_feed.feed_id,
        "device_id": source_device.device_id,
        "event_kind": OperationalEventKind.JETTY_LOADING_STARTED,
        "asset_type": OperationsAssetType.JETTY,
        "asset_code": source_device.asset_code,
        "schedule_event_id": load_start.id,
        "event_at": (load_start.planned_at + timezone.timedelta(minutes=8)).isoformat(),
        "confidence_score": "97.00",
        "dedupe_key": "duplicate-load-start",
    }

    first = client.post("/api/operations/event-candidates/ingest/", payload, format="json")
    duplicate = client.post("/api/operations/event-candidates/ingest/", payload, format="json")

    assert first.status_code == 201
    assert duplicate.status_code == 200
    assert duplicate.data["duplicate"] is True
    assert OperationalEventCandidate.objects.filter(dedupe_key="duplicate-load-start").count() == 2
    assert OperationalEventCandidate.objects.filter(
        dedupe_key="duplicate-load-start",
        status=OperationalEventCandidate.Status.DUPLICATE,
    ).exists()
    assert ConfirmedOperationalEvent.objects.filter(
        event_kind=OperationalEventKind.JETTY_LOADING_STARTED,
        schedule_event=load_start,
    ).count() == 1


@pytest.mark.django_db
def test_seed_phase0_creates_phase4_operation_permissions_and_seed_feed():
    call_command("seed_phase0", master_data_only=True, verbosity=0)

    for code in [
        "operations.view",
        "operations.ingest",
        "operations.confirm_jetty",
        "operations.confirm_cts",
        "operations.confirm_bridge",
        "operations.confirm_tide",
        "operations.manage_feeds",
        "operations.replay",
    ]:
        assert AccessPermission.objects.filter(code=code).exists()

    assert IntegrationFeed.objects.filter(feed_id="SYN-OPS-PHASE4").exists()
    assert DeviceEndpoint.objects.filter(device_id="JETTY-JTY-SUARAN-OPS").exists()


@pytest.mark.django_db
def test_device_health_ingest_marks_offline_feed_degraded_and_creates_risk():
    org = organization()
    source_feed = feed()
    source_feed.freshness_threshold_seconds = 120
    source_feed.save(update_fields=["freshness_threshold_seconds"])
    source_device = device(source_feed)
    ingester = User.objects.create_user(username="ops-health-ingester", password="secret")
    assign(ingester, org, ["operations.view", "operations.ingest"])

    client = APIClient()
    client.force_authenticate(ingester)
    response = client.post(
        "/api/operations/device-health/ingest/",
        {
            "feed_id": source_feed.feed_id,
            "device_id": source_device.device_id,
            "observed_at": timezone.now().isoformat(),
            "health_status": DeviceHealthSnapshot.HealthStatus.OFFLINE,
            "network_status": "broker_timeout",
            "gap_seconds": 360,
            "metadata": {"source": "unit-test"},
        },
        format="json",
    )

    source_device.refresh_from_db()
    source_feed.refresh_from_db()
    candidate = OperationalEventCandidate.objects.get(
        event_kind=OperationalEventKind.DEVICE_OFFLINE,
        device=source_device,
    )

    assert response.status_code == 201
    assert response.data["created_risk"] is True
    assert response.data["candidate"]["candidate_id"] == candidate.candidate_id
    assert source_device.status == DeviceEndpoint.Status.OFFLINE
    assert source_feed.status == IntegrationFeed.Status.DEGRADED
    assert candidate.status == OperationalEventCandidate.Status.PENDING
    assert candidate.metadata["healthRisk"]["riskSeverity"] == "critical"
    assert AuditEvent.objects.filter(
        action="operations.device_health.ingested",
        object_repr=response.data["snapshot"]["snapshot_id"],
    ).exists()

    overview = client.get("/api/operations/overview/")
    assert overview.status_code == 200
    assert overview.data["health"]["devices"]["offline"] == 1
    assert overview.data["health"]["criticalRiskCount"] == 1
    assert overview.data["health"]["risks"][0]["candidateId"] == candidate.candidate_id


@pytest.mark.django_db
def test_stale_device_refresh_creates_visible_health_risk():
    source_feed = feed()
    source_feed.freshness_threshold_seconds = 60
    source_feed.save(update_fields=["freshness_threshold_seconds"])
    source_device = device(source_feed)
    now = timezone.now()
    source_device.last_seen_at = now - timezone.timedelta(minutes=3)
    source_device.save(update_fields=["last_seen_at"])

    summary = operations_health_summary(now=now)
    source_device.refresh_from_db()
    source_feed.refresh_from_db()

    assert source_device.status == DeviceEndpoint.Status.OFFLINE
    assert source_feed.status == IntegrationFeed.Status.DEGRADED
    assert summary["devices"]["offline"] == 1
    assert summary["criticalRiskCount"] == 1
    assert OperationalEventCandidate.objects.filter(
        event_kind=OperationalEventKind.DEVICE_OFFLINE,
        status=OperationalEventCandidate.Status.PENDING,
        device=source_device,
    ).exists()


@pytest.mark.django_db
def test_healthy_device_health_supports_trusted_auto_confirm_policy():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)
    source_feed = trusted_feed()
    load_start = ScheduleEvent.objects.select_related(
        "trip",
        "trip__assignment",
        "trip__assignment__jetty",
    ).filter(event_type=ScheduleEvent.EventType.LOAD_START).order_by("planned_at").first()
    source_device = DeviceEndpoint.objects.create(
        device_id="DEV-JTY-SUARAN-HEALTHY",
        feed=source_feed,
        device_type=DeviceEndpoint.DeviceType.JETTY_PLC,
        asset_type=OperationsAssetType.JETTY,
        asset_code=load_start.trip.assignment.jetty.code,
    )
    DeviceHealthSnapshot.objects.create(
        device=source_device,
        observed_at=timezone.now(),
        health_status=DeviceHealthSnapshot.HealthStatus.HEALTHY,
        network_status="online",
        gap_seconds=0,
    )
    user = User.objects.get(username="admin@coalflow.local")
    client = APIClient()
    client.force_authenticate(user)

    response = client.post(
        "/api/operations/event-candidates/ingest/",
        {
            "feed_id": source_feed.feed_id,
            "device_id": source_device.device_id,
            "event_kind": OperationalEventKind.JETTY_LOADING_STARTED,
            "asset_type": OperationsAssetType.JETTY,
            "asset_code": source_device.asset_code,
            "schedule_event_id": load_start.id,
            "event_at": (load_start.planned_at + timezone.timedelta(minutes=6)).isoformat(),
            "confidence_score": "98.00",
            "dedupe_key": "healthy-device-auto-confirm",
        },
        format="json",
    )

    assert response.status_code == 201
    assert response.data["auto_confirmed"] is True
    assert response.data["trust_evaluation"]["deviceHealth"]["healthStatus"] == "healthy"


@pytest.mark.django_db
def test_scheduling_overview_exposes_operations_health_summary():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)
    user = User.objects.get(username="admin@coalflow.local")
    client = APIClient()
    client.force_authenticate(user)

    response = client.get("/api/scheduling/overview/")

    assert response.status_code == 200
    assert "operationsHealthSummary" in response.data
    assert "feeds" in response.data["operationsHealthSummary"]
    assert "devices" in response.data["operationsHealthSummary"]
