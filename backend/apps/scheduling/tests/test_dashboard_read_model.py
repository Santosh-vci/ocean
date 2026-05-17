import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.db import connection
from django.test.utils import CaptureQueriesContext
from rest_framework.test import APIClient

from apps.scheduling.models import Conflict, PlanVersion

User = get_user_model()


def _client_for(username: str):
    user = User.objects.get(username=username)
    client = APIClient()
    client.force_authenticate(user)
    return client


def _kpi(payload: dict, key: str) -> dict:
    return next(item for item in payload["kpis"] if item["key"] == key)


def seeded_plan_version() -> PlanVersion:
    return PlanVersion.objects.get(
        plan__name="Berau-ABL Feasible Schedule Horizon",
        version_no=1,
    )


@pytest.mark.django_db
def test_dashboard_read_model_reconciles_kpis_to_schedule_fixture():
    call_command("seed_phase0")
    version = seeded_plan_version()
    expected_blockers = Conflict.objects.filter(
        plan_version=version,
        is_blocking=True,
        resolved_at__isnull=True,
    ).count()
    expected_remaining = sum(
        max(trip.planned_quantity_mt - trip.loaded_quantity_mt, 0)
        for trip in version.trips.all()
    )

    response = _client_for("admin@coalflow.local").get("/api/dashboard/situation/")

    assert response.status_code == 200
    assert response.data["latestVersion"]["planCode"] == version.plan.code
    assert _kpi(response.data, "blockingConflicts")["value"] == expected_blockers
    assert _kpi(response.data, "cargoRemainingMt")["value"] == expected_remaining
    assert response.data["planRisk"]["highestRiskOgv"]["vesselName"]
    assert response.data["planRisk"]["mostConstrainedResource"]["label"]


@pytest.mark.django_db
def test_dashboard_response_is_shaped_by_operational_role():
    call_command("seed_phase0")

    berau_response = _client_for("berau.scheduler@coalflow.local").get(
        "/api/dashboard/situation/"
    )
    abl_response = _client_for("abl.dispatcher@coalflow.local").get(
        "/api/dashboard/situation/"
    )

    assert berau_response.status_code == 200
    assert abl_response.status_code == 200
    assert berau_response.data["roleShape"]["profile"] == "demand_control"
    assert berau_response.data["roleShape"]["sections"]["demandRisk"] is True
    assert berau_response.data["roleShape"]["sections"]["assetQueue"] is False
    assert "fleetMaintenanceDetail" in berau_response.data["roleShape"]["redactions"]
    assert abl_response.data["roleShape"]["profile"] == "dispatch_control"
    assert abl_response.data["roleShape"]["sections"]["assetQueue"] is True
    assert "customerCommercialExposure" in abl_response.data["roleShape"]["redactions"]


@pytest.mark.django_db
def test_dashboard_endpoint_has_query_baseline():
    call_command("seed_phase0")
    client = _client_for("admin@coalflow.local")

    with CaptureQueriesContext(connection) as captured:
        response = client.get("/api/dashboard/situation/")

    assert response.status_code == 200
    assert len(captured) <= 32
