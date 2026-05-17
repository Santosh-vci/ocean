import hashlib

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.core.object_storage import read_export_object
from apps.organizations.models import Organization
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import ExportJob, PlanVersion, ScenarioAssumption
from apps.scheduling.services import (
    create_scenario_assumption,
    create_scenario_from_conflict,
    promote_scenario_to_proposed,
    simulate_scenario,
)

User = get_user_model()


def _client_for(username: str) -> APIClient:
    user = User.objects.get(username=username)
    client = APIClient()
    client.force_authenticate(user)
    return client


def seeded_plan_version() -> PlanVersion:
    return PlanVersion.objects.get(
        plan__name="Berau-ABL Feasible Schedule Horizon",
        version_no=1,
    )


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


@pytest.mark.django_db
def test_control_tower_can_generate_plan_export_with_file_and_audit(monkeypatch, tmp_path):
    monkeypatch.setenv("EXPORT_STORAGE_ROOT", str(tmp_path))
    call_command("seed_phase0")
    version = seeded_plan_version()
    client = _client_for("control.tower@coalflow.local")

    response = client.post(
        "/api/exports/generate/",
        {
            "export_type": ExportJob.ExportType.PLAN,
            "export_format": ExportJob.ExportFormat.CSV,
            "plan_version": version.id,
        },
        format="json",
    )

    assert response.status_code == 201
    export_job = ExportJob.objects.get(export_id=response.data["export_id"])
    content = read_export_object(
        key=export_job.storage_key,
        bucket=export_job.storage_bucket,
    )
    assert export_job.record_count == 6
    assert export_job.scope["scope_type"] == "all_network"
    assert export_job.checksum_sha256 == hashlib.sha256(content).hexdigest()
    assert b"tripId,sequence,vesselName" in content
    assert AuditEvent.objects.filter(
        action="export.generated",
        object_id=export_job.export_id,
    ).exists()


@pytest.mark.django_db
def test_read_only_viewer_cannot_generate_full_network_export(monkeypatch, tmp_path):
    monkeypatch.setenv("EXPORT_STORAGE_ROOT", str(tmp_path))
    call_command("seed_phase0")
    client = _client_for("viewer@coalflow.local")

    response = client.post(
        "/api/exports/generate/",
        {"export_type": ExportJob.ExportType.PLAN, "export_format": ExportJob.ExportFormat.JSON},
        format="json",
    )

    assert response.status_code == 403
    assert ExportJob.objects.count() == 0


@pytest.mark.django_db
def test_export_overview_has_access_aware_empty_state_for_scoped_users():
    call_command("seed_phase0")
    client = _client_for("berau.scheduler@coalflow.local")

    response = client.get("/api/exports/overview/")

    assert response.status_code == 200
    assert response.data["exports"] == []
    assert response.data["summary"]["total"] == 0
    assert response.data["scope"]["scope_type"] == "organization"
    assert response.data["canGenerate"] is False


@pytest.mark.django_db
def test_generated_export_can_be_downloaded(monkeypatch, tmp_path):
    monkeypatch.setenv("EXPORT_STORAGE_ROOT", str(tmp_path))
    call_command("seed_phase0")
    client = _client_for("control.tower@coalflow.local")

    generate_response = client.post(
        "/api/exports/generate/",
        {
            "export_type": ExportJob.ExportType.CONFLICT,
            "export_format": ExportJob.ExportFormat.JSON,
        },
        format="json",
    )
    download_response = client.get(generate_response.data["download_url"])

    assert generate_response.status_code == 201
    assert download_response.status_code == 200
    assert download_response["X-Content-SHA256"] == generate_response.data["checksum_sha256"]
    assert b'"exportType": "conflict"' in download_response.content


@pytest.mark.django_db
def test_promoted_scenario_diff_can_be_exported_with_lineage(monkeypatch, tmp_path):
    monkeypatch.setenv("EXPORT_STORAGE_ROOT", str(tmp_path))
    call_command("seed_phase0")
    organization = Organization.objects.get(slug="coalflow-platform")
    actor = User.objects.create_user("scenario-exporter")
    assign(actor, organization, ["schedule.view", "schedule.edit", "export.generate"])
    baseline = seeded_plan_version()
    trip = baseline.trips.order_by("sequence").first()
    scenario = create_scenario_from_conflict(
        baseline_version=baseline,
        source_conflict=None,
        actor=actor,
    )
    create_scenario_assumption(
        scenario=scenario,
        actor=actor,
        kind=ScenarioAssumption.Kind.TRIP_DELAY,
        scope_type=ScenarioAssumption.ScopeType.TRIP,
        scope_id=trip.id,
        payload={"delay_minutes": 45},
    )
    simulate_scenario(scenario=scenario, actor=actor)
    run = scenario.runs.order_by("-created_at", "-id").first()
    promoted = promote_scenario_to_proposed(scenario=scenario, actor=actor, run=run)

    client = APIClient()
    client.force_authenticate(actor)
    response = client.post(
        "/api/exports/generate/",
        {
            "export_type": ExportJob.ExportType.SCENARIO_DIFF,
            "export_format": ExportJob.ExportFormat.JSON,
            "plan_version": promoted.scenario_version_id,
        },
        format="json",
    )

    assert response.status_code == 201
    payload = response.data["payload"]
    assert payload["scenarioLineage"]["scenarioId"] == scenario.scenario_id
    assert payload["scenarioLineage"]["selectedRunRef"] == run.run_id
    assert payload["summary"]["changedTripCount"] > 0
