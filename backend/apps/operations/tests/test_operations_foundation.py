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
    IntegrationFeed,
    OperationalActualization,
    OperationalEventCandidate,
    OperationalEventKind,
    OperationsAssetType,
)
from apps.organizations.models import Organization
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment


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

    OperationalEventCandidate.objects.create(
        feed=source_feed,
        device=source_device,
        source_kind=OperationalEventCandidate.SourceKind.SYNTHETIC,
        event_kind=OperationalEventKind.JETTY_LOADING_STARTED,
        asset_type=OperationsAssetType.JETTY,
        asset_code="JTY-SUARAN",
        event_at=timezone.now(),
        dedupe_key="same-source-event",
    )
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            OperationalEventCandidate.objects.create(
                feed=source_feed,
                device=source_device,
                source_kind=OperationalEventCandidate.SourceKind.SYNTHETIC,
                event_kind=OperationalEventKind.JETTY_LOADING_STARTED,
                asset_type=OperationsAssetType.JETTY,
                asset_code="JTY-SUARAN",
                event_at=timezone.now(),
                dedupe_key="same-source-event",
            )


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
