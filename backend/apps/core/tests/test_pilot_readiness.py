from datetime import datetime, time

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.masters.models import AssetCompatibilityRule, Jetty, Tug
from apps.planning.models import ImportJob, OGVVoyage
from apps.scheduling.models import (
    ApprovalDecision,
    ApprovalRequest,
    Conflict,
    ExportJob,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
)

User = get_user_model()


def _client_for(username: str) -> APIClient:
    user = User.objects.get(username=username)
    client = APIClient()
    client.force_authenticate(user)
    client.force_login(user)
    return client


def seeded_plan_version() -> PlanVersion:
    return PlanVersion.objects.get(
        plan__name="Berau-ABL Feasible Schedule Horizon",
        version_no=1,
    )


def seeded_approval_request(version: PlanVersion) -> ApprovalRequest:
    return ApprovalRequest.objects.get(plan_version=version)


def operator_iso(days_from_today: int, hour: int, minute: int = 0) -> str:
    target_date = timezone.localdate() + timezone.timedelta(days=days_from_today)
    return timezone.make_aware(datetime.combine(target_date, time(hour, minute))).isoformat()


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("username", "path", "expected_status"),
    [
        ("admin@coalflow.local", "/api/metrics/", 200),
        ("control.tower@coalflow.local", "/api/exports/overview/", 200),
        ("control.tower@coalflow.local", "/api/rbac/overview/", 403),
        ("berau.scheduler@coalflow.local", "/api/planning/overview/", 200),
        ("berau.scheduler@coalflow.local", "/api/exports/overview/", 200),
        ("berau.scheduler@coalflow.local", "/api/rbac/overview/", 403),
        ("abl.dispatcher@coalflow.local", "/api/dashboard/situation/", 200),
        ("abl.dispatcher@coalflow.local", "/api/master-data/overview/", 403),
        ("viewer@coalflow.local", "/api/audit-events/", 403),
        ("viewer@coalflow.local", "/api/exports/overview/", 403),
    ],
)
def test_seeded_role_regression_matrix(username, path, expected_status):
    call_command("seed_phase0")

    response = _client_for(username).get(path)

    assert response.status_code == expected_status


@pytest.mark.django_db
def test_full_seeded_workflow_reaches_published_plan_and_governed_export(monkeypatch, tmp_path):
    monkeypatch.setenv("EXPORT_STORAGE_ROOT", str(tmp_path))
    call_command("seed_phase0")
    client = _client_for("admin@coalflow.local")
    version = seeded_plan_version()
    approval_request = seeded_approval_request(version)

    demand_response = client.post(
        "/api/planning/import-jobs/validate-ogv-demand/",
        {
            "filename": "uat-demand.xlsx",
            "rows": [
                {
                    "voyage_id": "VOY-UAT-001",
                    "vessel_name": "MV UAT PILOT",
                    "customer_name": "Pilot Customer",
                    "laycan_start": operator_iso(1, 0),
                    "laycan_end": operator_iso(4, 0),
                    "eta": operator_iso(1, 6),
                    "required_mt": 64000,
                }
            ],
        },
        format="json",
    )
    generate_response = client.post(f"/api/scheduling/plan-versions/{version.id}/generate/")
    Conflict.objects.filter(plan_version=version).update(resolved_at=timezone.now())
    version.validation_status = PlanVersion.ValidationStatus.FEASIBLE
    version.save(update_fields=["validation_status", "updated_at"])
    berau_decision = client.post(
        f"/api/scheduling/approval-requests/{approval_request.id}/decide/",
        {
            "authority_role": ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
            "decision": ApprovalDecision.Decision.APPROVE,
            "comments": "Pilot Berau approval.",
        },
        format="json",
    )
    abl_decision = client.post(
        f"/api/scheduling/approval-requests/{approval_request.id}/decide/",
        {
            "authority_role": ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
            "decision": ApprovalDecision.Decision.APPROVE,
            "comments": "Pilot ABL approval.",
        },
        format="json",
    )
    publish_response = client.post(f"/api/scheduling/plan-versions/{version.id}/publish/")
    export_response = client.post(
        "/api/exports/generate/",
        {"export_type": ExportJob.ExportType.PLAN, "export_format": ExportJob.ExportFormat.PRINT},
        format="json",
    )

    assert demand_response.status_code == 201
    assert generate_response.status_code == 200
    assert berau_decision.status_code == 200
    assert abl_decision.status_code == 200
    assert publish_response.status_code == 201
    assert export_response.status_code == 201
    assert PublishedPlanSnapshot.objects.filter(status=PublishedPlanSnapshot.Status.ACTIVE).exists()
    assert AuditEvent.objects.filter(action="planning_import_job.validate").exists()
    assert AuditEvent.objects.filter(action="planversion.publish").exists()
    assert AuditEvent.objects.filter(action="export.generated").exists()


@pytest.mark.django_db
def test_master_data_only_seed_clears_operational_records():
    call_command("seed_phase0")
    assert OGVVoyage.objects.exists()
    assert PlanVersion.objects.exists()

    call_command("seed_phase0", "--reset-operational-data", "--master-data-only")

    assert User.objects.filter(username="admin@coalflow.local").exists()
    assert User.objects.filter(username="berau.scheduler@coalflow.local").exists()
    assert OGVVoyage.objects.count() == 0
    assert ImportJob.objects.count() == 0
    assert Plan.objects.count() == 0
    assert PlanVersion.objects.count() == 0
    assert Conflict.objects.count() == 0
    assert ExportJob.objects.count() == 0
    assert PublishedPlanSnapshot.objects.count() == 0
    assert AuditEvent.objects.count() == 0
    assert AssetCompatibilityRule.objects.filter(is_compatible=False).count() == 0
    assert Tug.objects.filter(gps_device_id="").count() == 0
    assert Jetty.objects.filter(
        code__in=["JTY-SUARAN", "JTY-LATI", "JTY-GMB"],
        status=Jetty.Status.AVAILABLE,
    ).count() == 3
