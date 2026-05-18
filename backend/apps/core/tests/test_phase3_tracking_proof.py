import json
from io import StringIO

import pytest
from django.core.management import call_command

from apps.audit.models import AuditEvent
from apps.telemetry.models import TelemetryReplayRun, TrackingAlert


@pytest.mark.django_db
def test_phase3_tracking_proof_command_creates_repeatable_replay_evidence():
    output = StringIO()

    call_command("phase3_tracking_proof", "--json", stdout=output)

    evidence = json.loads(output.getvalue())
    assert evidence["definitionOfDone"] == {
        "overall": "PASS",
        "stagesPassed": 4,
        "expectedStages": 4,
    }
    assert len(evidence["replayPack"]) == 6
    assert {row["scenarioCode"] for row in evidence["replayPack"]} == {
        "TRACK-ON-TIME",
        "TRACK-JETTY-DELAY",
        "TRACK-BRIDGE-WAIT",
        "TRACK-STALE-SIGNAL",
        "TRACK-OGV-ETA-SHIFT",
        "TRACK-CTS-APPROACH",
    }
    assert evidence["telemetrySummary"]["pingCount"] >= 1
    assert {
        "delay",
        "eta_risk",
        "stale_signal",
    }.issubset(set(evidence["telemetrySummary"]["alertTypes"]))
    assert evidence["rerun"]["status"] == TelemetryReplayRun.Status.COMPLETED
    assert TelemetryReplayRun.objects.count() == 6
    assert TrackingAlert.objects.filter(
        alert_type=TrackingAlert.AlertType.DELAY,
        evidence__replayId="RPL-TRACK-JETTY-DELAY",
    ).exists()
    assert AuditEvent.objects.filter(
        metadata__runId=evidence["runId"],
        action="phase3.proof.rerun_verified",
    ).exists()
