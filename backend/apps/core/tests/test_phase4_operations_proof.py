import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.audit.models import AuditEvent
from apps.operations.models import EdgeEventBatch, OperationalEventCandidate, OperationalEventKind


@pytest.mark.django_db
def test_phase4_operations_proof_command_creates_repeatable_batch_evidence():
    output = StringIO()

    call_command("phase4_operations_proof", "--json", stdout=output)

    evidence = json.loads(output.getvalue())
    assert evidence["definitionOfDone"] == {
        "overall": "PASS",
        "stagesPassed": 5,
        "expectedStages": 5,
    }
    assert [row["batchSequence"] for row in evidence["batchPack"]] == [
        "PHASE4-EXECUTION-001",
        "PHASE4-HEALTH-001",
    ]
    assert evidence["operationsSummary"]["confirmedEventCount"] >= 1
    assert evidence["operationsSummary"]["actualizationCount"] >= 1
    assert evidence["operationsSummary"]["healthSnapshotCount"] >= 1
    assert evidence["operationsSummary"]["duplicateCandidateCount"] >= 1
    assert evidence["operationsSummary"]["pendingCandidateCount"] >= 1
    assert evidence["operationsSummary"]["deviceOfflineRiskCount"] >= 1
    assert evidence["rerun"]["idempotent"] is True
    assert "/operations/event-confirmation" in evidence["browserEvidenceTargets"]
    assert EdgeEventBatch.objects.count() == 2
    assert OperationalEventCandidate.objects.filter(
        event_kind=OperationalEventKind.DEVICE_OFFLINE
    ).exists()
    assert AuditEvent.objects.filter(
        metadata__runId=evidence["runId"],
        action="phase4.proof.rerun_verified",
    ).exists()
