import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.audit.models import AuditEvent
from apps.scheduling.models import Conflict, PlanVersion
from apps.telemetry.models import TrackingAlert


def command_json(*args):
    output = StringIO()
    call_command(*args, "--json", stdout=output)
    return json.loads(output.getvalue())


@pytest.mark.django_db
def test_operator_trial_practice_stages_start_empty_then_build_blocked_plan():
    reset = command_json("operator_trial_practice", "reset")
    assert reset["counts"]["voyages"] == 0
    assert reset["counts"]["cargoRequirements"] == 0
    assert reset["counts"]["planVersions"] == 0

    imported = command_json("operator_trial_practice", "import-demand")
    assert imported["counts"]["voyages"] == 5
    assert imported["counts"]["cargoRequirements"] == 8
    assert imported["counts"]["cargoLayerSteps"] == 6
    assert imported["counts"]["planVersions"] == 0

    windows = command_json("operator_trial_practice", "enter-windows")
    assert windows["counts"]["tideWindows"] == 3
    assert windows["counts"]["bridgeWindows"] == 3
    assert windows["windowEntry"]["constraintChecks"] == 5

    generated = command_json("operator_trial_practice", "generate-plan")
    assert generated["planVersion"]["tripCount"] == 6
    assert generated["planVersion"]["conflictCount"] == 4
    assert generated["planVersion"]["blockingConflictCount"] == 3
    assert generated["planVersion"]["validationStatus"] == "blocked"


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


@pytest.mark.django_db
def test_phase5_resolve_trial_pack_creates_clean_approved_closure_state():
    proof_output = StringIO()
    resolve_output = StringIO()

    call_command("phase5_recovery_proof", "--json", stdout=proof_output)
    call_command("phase5_resolve_trial_pack", "--json", stdout=resolve_output)

    evidence = json.loads(resolve_output.getvalue())
    closure_version = PlanVersion.objects.get(pk=evidence["closureVersion"]["id"])

    assert evidence["definitionOfDone"] == {
        "overall": "PASS",
        "allExceptionsHandled": True,
    }
    assert evidence["before"]["openConflictCount"] > 0
    assert evidence["resolvedPriorConflictCount"] > 0
    assert evidence["closureVersion"]["openConflictCount"] == 0
    assert evidence["closureVersion"]["blockingConflictCount"] == 0
    assert evidence["closureVersion"]["openTrackingAlertCount"] == 0
    assert closure_version.status == PlanVersion.Status.APPROVED
    assert closure_version.validation_status == PlanVersion.ValidationStatus.FEASIBLE
    assert not Conflict.objects.filter(
        plan_version=closure_version,
        resolved_at__isnull=True,
    ).exists()
    assert not TrackingAlert.objects.filter(
        status__in=[TrackingAlert.Status.OPEN, TrackingAlert.Status.ACKNOWLEDGED],
    ).exists()
    assert evidence["approval"]["status"] == "approved"
    assert evidence["approval"]["decisionCount"] == 2
    assert AuditEvent.objects.filter(
        action="phase5.trial.exceptions_resolved",
        object_repr=str(closure_version),
    ).exists()

    second_resolve_output = StringIO()
    call_command("phase5_resolve_trial_pack", "--json", stdout=second_resolve_output)
    second_evidence = json.loads(second_resolve_output.getvalue())

    assert second_evidence["closureVersion"]["id"] == closure_version.pk
    assert second_evidence["normalizedInputs"]["idempotent"] is True
    assert second_evidence["definitionOfDone"]["allExceptionsHandled"] is True
