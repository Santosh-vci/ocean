import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.audit.models import AuditEvent
from apps.scheduling.models import ExportJob, PublishedPlanSnapshot


@pytest.mark.django_db
def test_phase1_e2e_proof_command_creates_visible_runtime_evidence(monkeypatch, tmp_path):
    monkeypatch.setenv("EXPORT_STORAGE_ROOT", str(tmp_path))
    output = StringIO()

    call_command("phase1_e2e_proof", "--json", stdout=output)

    evidence = json.loads(output.getvalue())
    assert evidence["definitionOfDone"] == {
        "overall": "PASS",
        "stagesPassed": 10,
        "expectedStages": 10,
    }
    assert evidence["happyPath"]["planCode"] == "PLAN-PHASE1-E2E"
    assert evidence["happyPath"]["status"] == "published"
    assert evidence["happyPath"]["tripCount"] == 2
    assert evidence["happyPath"]["eventCount"] == 14
    assert evidence["constraintScenario"]["blockingConflictCount"] >= 1
    assert evidence["governedExport"]["recordCount"] == 2
    assert evidence["auditTrail"]["eventCount"] == 10

    assert PublishedPlanSnapshot.objects.filter(
        snapshot_id="LIVE-PLAN-PHASE1-E2E-V1",
        status=PublishedPlanSnapshot.Status.ACTIVE,
    ).exists()
    assert ExportJob.objects.filter(export_id=evidence["governedExport"]["exportId"]).exists()
    assert AuditEvent.objects.filter(
        object_id__startswith=evidence["runId"],
        action="phase1.proof.governed_export_generated",
    ).exists()
