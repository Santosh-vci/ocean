import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.audit.models import AuditEvent


@pytest.mark.django_db
def test_phase5_recovery_proof_command_creates_repeatable_recommendation_evidence():
    output = StringIO()

    call_command("phase5_recovery_proof", "--json", stdout=output)

    evidence = json.loads(output.getvalue())
    assert evidence["definitionOfDone"] == {
        "overall": "PASS",
        "stagesPassed": 7,
        "expectedStages": 7,
    }
    assert evidence["optimizerRun"]["runId"].startswith("OPT-P5-RECOVERY-")
    assert evidence["optimizerRun"]["recommendationCount"] >= 4
    assert evidence["selectedRecommendation"]["rank"] >= 1
    assert evidence["scenarioHandoff"]["scenarioStatus"] == "proposed"
    assert evidence["approvalHandoff"]["decisionCount"] == 2
    assert evidence["proofPack"]["proofPackVersion"] == "phase5.6-recommendation-proof-pack"
    assert evidence["proofPack"]["approvalCount"] == 1
    assert evidence["proofPack"]["auditTrailCount"] >= 6
    assert "/recovery/recommendations" in evidence["browserEvidenceTargets"]
    assert AuditEvent.objects.filter(
        metadata__runId=evidence["runId"],
        action="phase5.proof.proof_pack_verified",
    ).exists()

    rerun_output = StringIO()
    call_command("phase5_recovery_proof", "--json", stdout=rerun_output)
    rerun = json.loads(rerun_output.getvalue())
    assert rerun["definitionOfDone"]["overall"] == "PASS"
    assert rerun["runId"] != evidence["runId"]
