import hashlib

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.core.object_storage import read_export_object
from apps.scheduling.models import ExportJob, PlanVersion

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
