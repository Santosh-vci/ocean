import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.scheduling.models import (
    ApprovalRequest,
    ExportJob,
    PlanVersion,
    ScenarioRun,
    SimulationScenario,
)

EXPECTED_SCENARIOS = {
    "SIM-JETTY-DELAY",
    "SIM-TUG-OUTAGE",
    "SIM-TIDE-RECOVERY",
    "SIM-CTS-RATE",
    "SIM-TOPUP-DEMAND",
    "SIM-MANUAL-REASSIGNMENT",
    "SIM-MULTI-CANDIDATE",
}


@pytest.mark.django_db
def test_phase2_scenario_proof_command_creates_repeatable_evidence(
    monkeypatch,
    tmp_path,
):
    monkeypatch.setenv("EXPORT_STORAGE_ROOT", str(tmp_path / "exports"))
    evidence_path = tmp_path / "phase2_scenario_evidence.json"
    monkeypatch.setattr(
        "apps.core.management.commands.phase2_scenario_proof.EVIDENCE_PATH",
        evidence_path,
    )
    output = StringIO()

    call_command("phase2_scenario_proof", "--json", stdout=output)

    evidence = json.loads(output.getvalue())
    assert evidence["definitionOfDone"] == {
        "overall": "PASS",
        "stagesPassed": 7,
        "expectedStages": 7,
    }
    assert {row["scenarioId"] for row in evidence["scenarioPack"]} == EXPECTED_SCENARIOS
    assert evidence["projectionSummary"]["scenarioCount"] == len(EXPECTED_SCENARIOS)
    assert evidence["projectionSummary"]["totalTripProjections"] == 42
    assert evidence["projectionSummary"]["totalConstraintEvaluations"] == 105
    assert len(evidence["multiRunComparison"]["runs"]) == 2
    assert (
        evidence["multiRunComparison"]["runs"][0]["inputHash"]
        != evidence["multiRunComparison"]["runs"][1]["inputHash"]
    )

    promoted = evidence["promotedCandidate"]
    assert promoted["scenarioId"] == "SIM-JETTY-DELAY"
    assert promoted["candidateStatus"] == PlanVersion.Status.PROPOSED
    assert promoted["lineage"]["selectedRunRef"] == "RUN-SIM-JETTY-DELAY-01"
    assert promoted["diffSummary"]["changedTripCount"] == 6
    assert evidence["approvalGate"]["status"] == ApprovalRequest.Status.PENDING
    assert evidence["governedExport"]["recordCount"] >= 1
    assert evidence_path.exists()

    assert SimulationScenario.objects.filter(scenario_id__in=EXPECTED_SCENARIOS).count() == len(
        EXPECTED_SCENARIOS,
    )
    assert ScenarioRun.objects.filter(
        scenario__scenario_id="SIM-MULTI-CANDIDATE",
        status=ScenarioRun.Status.SUCCEEDED,
    ).count() == 2
    assert ExportJob.objects.filter(export_id=evidence["governedExport"]["exportId"]).exists()
    assert AuditEvent.objects.filter(
        metadata__runId=evidence["runId"],
        action="phase2.proof.selected_run_promoted",
    ).exists()

    client = APIClient()
    client.force_authenticate(get_user_model().objects.get(username="admin@coalflow.local"))
    overview = client.get("/api/scheduling/overview/")
    assert overview.status_code == 200
    assert {
        row["scenario_id"] for row in overview.data["simulationScenarios"]
    } == EXPECTED_SCENARIOS
