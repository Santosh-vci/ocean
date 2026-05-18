import pytest
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizations.models import Organization
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.telemetry.models import (
    AssetIdentity,
    GeofenceZone,
    LatestAssetState,
    LiveEtaProjection,
    MovementEvent,
    PositionPing,
    TelemetryReplayRun,
    TelemetrySource,
    TrackingAlert,
)
from apps.telemetry.replay import seed_phase3_replay_runs, start_synthetic_replay
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


def geofence_zone(**overrides):
    payload = {
        "zone_id": "GEO-TEST-BRIDGE",
        "name": "Test Bridge Gate",
        "zone_type": GeofenceZone.ZoneType.BRIDGE,
        "latitude": "-1.2345670",
        "longitude": "117.2345670",
        "radius_m": 500,
        "status": GeofenceZone.Status.ACTIVE,
    }
    payload.update(overrides)
    return GeofenceZone.objects.create(**payload)


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
def test_ingest_derives_geofence_entry_and_exit_events():
    zone = geofence_zone()

    first = ingest_position_ping(payload=telemetry_payload())
    latest_state = LatestAssetState.objects.get(asset_code="BER-TUG-08")

    assert len(first["geofence_events"]) == 1
    assert first["geofence_events"][0].event_type == MovementEvent.EventType.ENTER_GEOFENCE
    assert first["geofence_events"][0].geofence == zone
    assert latest_state.current_geofence == zone

    second = ingest_position_ping(
        payload=telemetry_payload(
            latitude="-1.3000000",
            longitude="117.3000000",
            device_timestamp=timezone.now() + timezone.timedelta(minutes=5),
        )
    )
    latest_state.refresh_from_db()

    assert len(second["geofence_events"]) == 1
    assert second["geofence_events"][0].event_type == MovementEvent.EventType.EXIT_GEOFENCE
    assert latest_state.current_geofence is None
    assert latest_state.last_movement_event == second["geofence_events"][0]


@pytest.mark.django_db
def test_ingest_derives_cross_geofence_transition():
    first_zone = geofence_zone(zone_id="GEO-TEST-JETTY", zone_type=GeofenceZone.ZoneType.JETTY)
    second_zone = geofence_zone(
        zone_id="GEO-TEST-CTS",
        name="Test CTS",
        zone_type=GeofenceZone.ZoneType.CTS_ZONE,
        latitude="-1.2400000",
        longitude="117.2400000",
    )

    ingest_position_ping(payload=telemetry_payload())
    transition = ingest_position_ping(
        payload=telemetry_payload(
            latitude=second_zone.latitude,
            longitude=second_zone.longitude,
            device_timestamp=timezone.now() + timezone.timedelta(minutes=5),
        )
    )
    latest_state = LatestAssetState.objects.get(asset_code="BER-TUG-08")

    assert [event.event_type for event in transition["geofence_events"]] == [
        MovementEvent.EventType.EXIT_GEOFENCE,
        MovementEvent.EventType.ENTER_GEOFENCE,
    ]
    assert transition["geofence_events"][0].geofence == first_zone
    assert transition["geofence_events"][1].geofence == second_zone
    assert latest_state.current_geofence == second_zone


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
def test_geofence_and_movement_event_api_are_viewable_after_ingest():
    organization = Organization.objects.create(
        name="Coalflow Platform",
        slug="coalflow-platform-geofence-test",
        kind=Organization.Kind.PLATFORM,
    )
    viewer = User.objects.create_user(username="geofence-viewer", password="secret")
    assign(viewer, organization, ["telemetry.view", "telemetry.ingest"])
    geofence_zone()

    client = APIClient()
    client.force_authenticate(viewer)
    response = client.post(
        "/api/telemetry/position-pings/ingest/",
        telemetry_payload(device_timestamp=timezone.now().isoformat()),
        format="json",
    )
    geofence_response = client.get("/api/telemetry/geofence-zones/")
    event_response = client.get("/api/telemetry/movement-events/")

    assert response.status_code == 201
    assert response.data["geofence_events"][0]["event_type"] == "enter_geofence"
    assert response.data["geofence_events"][0]["geofence_ref"] == "GEO-TEST-BRIDGE"
    assert geofence_response.status_code == 200
    assert geofence_response.data[0]["zone_id"] == "GEO-TEST-BRIDGE"
    assert event_response.status_code == 200
    assert event_response.data[0]["event_type"] == "enter_geofence"


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
    assert GeofenceZone.objects.filter(zone_id="GEO-LOC-BRIDGE-GATE-B").exists()


@pytest.mark.django_db
def test_seed_phase0_sample_movement_events_are_idempotent():
    call_command("seed_phase0", verbosity=0)
    call_command("seed_phase0", verbosity=0)

    assert PositionPing.objects.filter(
        raw_payload__seed="phase_3_sample_movement"
    ).count() == 4
    assert MovementEvent.objects.count() == 5

    latest_state = LatestAssetState.objects.get(asset_code="BRG-VAL-08")
    assert latest_state.current_geofence.zone_id == "GEO-LOC-SUARAN-PORT"
    assert latest_state.freshness_status == LatestAssetState.FreshnessStatus.FRESH
    assert LiveEtaProjection.objects.filter(asset_code="BRG-VAL-08").exists()
    delay_alert = TrackingAlert.objects.get(
        asset_code="BRG-VAL-08",
        alert_type=TrackingAlert.AlertType.DELAY,
    )
    assert delay_alert.schedule_event.event_type == "depart_jetty"
    assert delay_alert.source_ping is not None
    assert delay_alert.evidence["varianceMinutes"] == 45


@pytest.mark.django_db
def test_seed_phase0_on_time_track_does_not_create_false_delay_alert():
    call_command("seed_phase0", verbosity=0)

    assert LiveEtaProjection.objects.filter(
        asset_code="BER-TUG-08",
        status=LiveEtaProjection.Status.ON_TIME,
    ).exists()
    assert not TrackingAlert.objects.filter(
        asset_code="BER-TUG-08",
        alert_type=TrackingAlert.AlertType.DELAY,
        status=TrackingAlert.Status.OPEN,
    ).exists()


@pytest.mark.django_db
def test_refresh_signal_health_creates_stale_signal_alert_with_evidence():
    call_command("seed_phase0", verbosity=0)
    latest_state = LatestAssetState.objects.get(asset_code="BRG-VAL-08")

    refresh_signal_health(now=latest_state.last_seen_at + timezone.timedelta(minutes=40))

    stale_alert = TrackingAlert.objects.get(
        asset_code="BRG-VAL-08",
        alert_type=TrackingAlert.AlertType.STALE_SIGNAL,
    )
    assert stale_alert.status == TrackingAlert.Status.OPEN
    assert stale_alert.source_ping == latest_state.last_ping
    assert stale_alert.schedule_event is not None
    assert stale_alert.evidence["sourcePingId"] == latest_state.last_ping.ping_id


@pytest.mark.django_db
def test_eta_projection_and_tracking_alert_api_are_viewable():
    call_command("seed_phase0", verbosity=0)
    user = User.objects.get(username="admin@coalflow.local")
    client = APIClient()
    client.force_authenticate(user)

    projection_response = client.get("/api/telemetry/eta-projections/")
    alert_response = client.get("/api/telemetry/alerts/")
    overview_response = client.get("/api/scheduling/overview/")

    assert projection_response.status_code == 200
    assert alert_response.status_code == 200
    assert overview_response.status_code == 200
    assert projection_response.data[0]["schedule_event_type"]
    assert any(item["alert_type"] == "delay" for item in alert_response.data)
    assert overview_response.data["trackingSummary"]["openAlertCount"] >= 1


@pytest.mark.django_db
def test_seed_phase3_replay_creates_all_fixture_families_and_runs_are_rerunnable():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)

    replay_runs = seed_phase3_replay_runs()
    replay_run = TelemetryReplayRun.objects.get(scenario_code="TRACK-JETTY-DELAY")
    first = start_synthetic_replay(replay_run=replay_run)
    identity_count = AssetIdentity.objects.count()
    second = start_synthetic_replay(replay_run=replay_run)

    assert {run.scenario_code for run in replay_runs} == {
        "TRACK-ON-TIME",
        "TRACK-JETTY-DELAY",
        "TRACK-BRIDGE-WAIT",
        "TRACK-STALE-SIGNAL",
        "TRACK-OGV-ETA-SHIFT",
        "TRACK-CTS-APPROACH",
    }
    assert first["run"].status == TelemetryReplayRun.Status.COMPLETED
    assert first["ping_count"] == second["ping_count"] == 2
    assert AssetIdentity.objects.count() == identity_count
    assert TrackingAlert.objects.filter(
        alert_type=TrackingAlert.AlertType.DELAY,
        evidence__replayId=replay_run.replay_id,
    ).exists()


@pytest.mark.django_db
def test_replay_run_api_can_start_a_seeded_synthetic_flow():
    call_command("seed_phase0", reset_operational_data=True, verbosity=0)
    replay_run = seed_phase3_replay_runs()[0]
    organization = Organization.objects.create(
        name="Coalflow Platform Replay",
        slug="coalflow-platform-replay-test",
        kind=Organization.Kind.PLATFORM,
    )
    viewer = User.objects.create_user(username="replay-viewer", password="secret")
    dispatcher = User.objects.create_user(username="replay-dispatcher", password="secret")
    assign(viewer, organization, ["telemetry.view"])
    assign(dispatcher, organization, ["telemetry.view", "telemetry.ingest"])

    client = APIClient()
    client.force_authenticate(viewer)
    denied = client.post(f"/api/telemetry/replay-runs/{replay_run.replay_id}/start/")

    client.force_authenticate(dispatcher)
    response = client.post(f"/api/telemetry/replay-runs/{replay_run.replay_id}/start/")
    list_response = client.get("/api/telemetry/replay-runs/")

    assert denied.status_code == 403
    assert response.status_code == 200
    assert response.data["status"] == TelemetryReplayRun.Status.COMPLETED
    assert response.data["metadata"]["pingCount"] >= 1
    assert list_response.status_code == 200
    assert len(list_response.data) == 6
