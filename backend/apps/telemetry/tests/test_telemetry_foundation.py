import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizations.models import Organization
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.telemetry.models import AssetIdentity, LatestAssetState, PositionPing, TelemetrySource
from apps.telemetry.services import ingest_position_ping, refresh_signal_health


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


def telemetry_payload(**overrides):
    payload = {
        "source_id": "SYN-GPS-PHASE3",
        "source_type": TelemetrySource.SourceType.SYNTHETIC_GPS,
        "external_id": "SYN-BER-TUG-08",
        "asset_type": AssetIdentity.AssetType.TUG,
        "asset_code": "BER-TUG-08",
        "latitude": "-1.2345670",
        "longitude": "117.2345670",
        "speed_knots": "5.40",
        "course_degrees": "91.00",
        "heading_degrees": "90.00",
        "device_timestamp": timezone.now(),
        "signal_quality": PositionPing.SignalQuality.GOOD,
        "raw_payload": {"sample": True},
    }
    payload.update(overrides)
    return payload


@pytest.mark.django_db
def test_ingest_synthetic_ping_creates_source_identity_and_position_ping():
    result = ingest_position_ping(payload=telemetry_payload())

    ping = result["ping"]
    assert ping.ping_id.startswith("PNG-SYN-GPS-PHASE3-")
    assert ping.source.source_id == "SYN-GPS-PHASE3"
    assert ping.source.source_type == TelemetrySource.SourceType.SYNTHETIC_GPS
    assert ping.asset_identity.external_id == "SYN-BER-TUG-08"
    assert ping.asset_type == AssetIdentity.AssetType.TUG
    assert ping.asset_code == "BER-TUG-08"
    assert ping.is_synthetic is True
    assert result["latest_state_updated"] is True
    latest_state = LatestAssetState.objects.get(asset_code="BER-TUG-08")
    assert latest_state.last_ping == ping
    assert latest_state.freshness_status == LatestAssetState.FreshnessStatus.FRESH
    assert latest_state.derived_status == LatestAssetState.DerivedStatus.UNDERWAY
    assert latest_state.confidence_score == 96
    assert result["geofence_events"] == []
    assert result["alerts"] == []


@pytest.mark.django_db
def test_older_ping_does_not_replace_latest_state():
    first_timestamp = timezone.now()
    first = ingest_position_ping(
        payload=telemetry_payload(device_timestamp=first_timestamp)
    )["ping"]
    older = ingest_position_ping(
        payload=telemetry_payload(
            device_timestamp=first_timestamp - timezone.timedelta(minutes=15),
            latitude="-1.0000000",
        )
    )

    latest_state = LatestAssetState.objects.get(asset_code="BER-TUG-08")
    assert older["latest_state_updated"] is False
    assert latest_state.last_ping == first
    assert latest_state.latitude == first.latitude


@pytest.mark.django_db
def test_refresh_signal_health_marks_old_state_stale():
    timestamp = timezone.now() - timezone.timedelta(minutes=10)
    ingest_position_ping(payload=telemetry_payload(device_timestamp=timestamp))

    updated = refresh_signal_health(now=timestamp + timezone.timedelta(minutes=40))

    latest_state = LatestAssetState.objects.get(asset_code="BER-TUG-08")
    assert updated == 1
    assert latest_state.freshness_status == LatestAssetState.FreshnessStatus.STALE
    assert latest_state.confidence_score == 25


@pytest.mark.django_db
def test_ingest_rejects_invalid_coordinates():
    with pytest.raises(ValidationError):
        ingest_position_ping(payload=telemetry_payload(latitude="99.9999999"))

    assert PositionPing.objects.count() == 0


@pytest.mark.django_db
def test_position_ping_ingest_api_enforces_permission_and_returns_normalized_ping():
    organization = Organization.objects.create(
        name="Coalflow Platform",
        slug="coalflow-platform-test",
        kind=Organization.Kind.PLATFORM,
    )
    viewer = User.objects.create_user(username="viewer", password="secret")
    dispatcher = User.objects.create_user(username="dispatcher", password="secret")
    assign(viewer, organization, ["telemetry.view"])
    assign(dispatcher, organization, ["telemetry.view", "telemetry.ingest"])

    request_payload = telemetry_payload(device_timestamp=timezone.now().isoformat())
    client = APIClient()
    client.force_authenticate(viewer)
    denied_response = client.post(
        "/api/telemetry/position-pings/ingest/",
        request_payload,
        format="json",
    )

    client.force_authenticate(dispatcher)
    response = client.post(
        "/api/telemetry/position-pings/ingest/",
        request_payload,
        format="json",
    )
    list_response = client.get("/api/telemetry/position-pings/")

    assert denied_response.status_code == 403
    assert response.status_code == 201
    assert response.data["ping"]["ping_id"].startswith("PNG-SYN-GPS-PHASE3-")
    assert response.data["ping"]["asset_code"] == "BER-TUG-08"
    assert response.data["ping"]["is_synthetic"] is True
    assert response.data["latest_state_updated"] is True
    assert list_response.status_code == 200
    assert len(list_response.data) == 1


@pytest.mark.django_db
def test_latest_state_api_lists_freshness_for_viewers_and_refreshes_for_ingesters():
    organization = Organization.objects.create(
        name="Coalflow Platform",
        slug="coalflow-platform-latest-test",
        kind=Organization.Kind.PLATFORM,
    )
    viewer = User.objects.create_user(username="latest-viewer", password="secret")
    dispatcher = User.objects.create_user(username="latest-dispatcher", password="secret")
    assign(viewer, organization, ["telemetry.view"])
    assign(dispatcher, organization, ["telemetry.view", "telemetry.ingest"])
    ingest_position_ping(payload=telemetry_payload(device_timestamp=timezone.now()))

    client = APIClient()
    client.force_authenticate(viewer)
    list_response = client.get("/api/telemetry/latest-asset-states/")
    denied_refresh = client.post("/api/telemetry/latest-asset-states/refresh-signal-health/")

    client.force_authenticate(dispatcher)
    refresh_response = client.post("/api/telemetry/latest-asset-states/refresh-signal-health/")

    assert list_response.status_code == 200
    assert list_response.data[0]["asset_code"] == "BER-TUG-08"
    assert list_response.data[0]["freshness_status"] == "fresh"
    assert denied_refresh.status_code == 403
    assert refresh_response.status_code == 200
    assert "updated" in refresh_response.data


@pytest.mark.django_db
def test_seed_phase0_creates_phase3_synthetic_sources_and_asset_identities():
    call_command("seed_phase0", master_data_only=True, verbosity=0)

    assert TelemetrySource.objects.filter(source_id="SYN-GPS-PHASE3").exists()
    assert TelemetrySource.objects.filter(source_id="SYN-AIS-PHASE3").exists()
    assert AssetIdentity.objects.filter(asset_code="BER-TUG-08", external_id="GPS-768").exists()
    assert AssetIdentity.objects.filter(asset_code="BRG-VAL-08").exists()
    assert AssetIdentity.objects.filter(asset_code="CTS-BORNEO").exists()
    assert LatestAssetState.objects.filter(
        asset_code="BER-TUG-08",
        freshness_status=LatestAssetState.FreshnessStatus.MISSING,
    ).exists()
