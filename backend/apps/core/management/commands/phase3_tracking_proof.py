import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.telemetry.models import (
    AssetIdentity,
    LiveEtaProjection,
    MovementEvent,
    PositionPing,
    TelemetryReplayRun,
    TrackingAlert,
)
from apps.telemetry.replay import REPLAY_FAMILIES, seed_phase3_replay_runs, start_synthetic_replay


class Command(BaseCommand):
    help = "Run the repeatable Phase 3 synthetic tracking proof flow."

    def add_arguments(self, parser):
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Emit machine-readable JSON only.",
        )
        parser.add_argument(
            "--skip-seed",
            action="store_true",
            help="Do not refresh the baseline seed before running the proof.",
        )

    def handle(self, *args, **options):
        if not options["skip_seed"]:
            seed_stdout = StringIO()
            call_command(
                "seed_phase0",
                reset_operational_data=True,
                stdout=seed_stdout,
            )

        evidence = Phase3TrackingProofRunner().run()

        if options["json_output"]:
            self.stdout.write(json.dumps(evidence, indent=2, sort_keys=True))
            return

        self.stdout.write(self.style.SUCCESS("Phase 3 tracking proof completed."))
        for stage in evidence["stages"]:
            self.stdout.write(
                f"{stage['stage']}. {stage['title']}: {stage['result']} "
                f"({stage['primaryEvidence']})"
            )


class Phase3TrackingProofRunner:
    def __init__(self):
        self.run_id = f"P3-TRACKING-{timezone.now():%Y%m%d%H%M%S}"
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.get(username="admin@coalflow.local")
        self.organization = self.admin.organization_memberships.first().organization
        self.stages: list[dict] = []

    def run(self) -> dict:
        replay_runs = self._stage_seed_pack()
        replay_results = self._stage_execute_replays(replay_runs)
        telemetry_summary = self._stage_verify_observed_evidence()
        rerun = self._stage_verify_rerun(replay_runs[0])

        return {
            "runId": self.run_id,
            "generatedAt": timezone.now().isoformat(),
            "definitionOfDone": {
                "overall": "PASS",
                "stagesPassed": len(self.stages),
                "expectedStages": 4,
            },
            "replayPack": replay_results,
            "telemetrySummary": telemetry_summary,
            "rerun": rerun,
            "browserEvidenceTargets": [
                "/map/live",
                "/exceptions/center",
            ],
            "stages": self.stages,
        }

    def _stage_seed_pack(self) -> list[TelemetryReplayRun]:
        replay_runs = seed_phase3_replay_runs()
        expected = {family["scenario_code"] for family in REPLAY_FAMILIES}
        found = {run.scenario_code for run in replay_runs}
        if found != expected:
            raise RuntimeError(f"Replay seed mismatch: expected {sorted(expected)}, found {sorted(found)}")
        self._record_stage(
            action="phase3.proof.replay_pack_seeded",
            title="Replay pack seeded",
            primary=f"{len(replay_runs)} replay families",
            metadata={"scenarioCodes": sorted(found)},
        )
        return replay_runs

    def _stage_execute_replays(self, replay_runs: list[TelemetryReplayRun]) -> list[dict]:
        rows = []
        for replay_run in replay_runs:
            result = start_synthetic_replay(replay_run=replay_run)
            rows.append(
                {
                    "replayId": replay_run.replay_id,
                    "scenarioCode": replay_run.scenario_code,
                    "status": result["run"].status,
                    "pingCount": result["ping_count"],
                    "movementEventCount": result["movement_event_count"],
                    "projectionCount": result["projection_count"],
                    "alertCount": result["alert_count"],
                    "assetCodes": result["asset_codes"],
                }
            )
        self._record_stage(
            action="phase3.proof.replays_executed",
            title="Synthetic replays executed",
            primary=f"{sum(row['pingCount'] for row in rows)} pings",
            metadata={"runs": rows},
        )
        return rows

    def _stage_verify_observed_evidence(self) -> dict:
        replay_pings = PositionPing.objects.filter(raw_payload__seed="phase3_replay")
        replay_events = MovementEvent.objects.filter(
            position_ping__raw_payload__seed="phase3_replay"
        )
        projections = LiveEtaProjection.objects.filter(metadata__seed="phase3_replay")
        alerts = TrackingAlert.objects.filter(evidence__seed="phase3_replay")
        expected_alerts = {
            TrackingAlert.AlertType.DELAY,
            TrackingAlert.AlertType.ETA_RISK,
            TrackingAlert.AlertType.STALE_SIGNAL,
        }
        observed_alerts = set(alerts.values_list("alert_type", flat=True))
        if not expected_alerts.issubset(observed_alerts):
            raise RuntimeError(
                f"Replay alert mismatch: expected {sorted(expected_alerts)}, "
                f"found {sorted(observed_alerts)}"
            )
        on_time_has_false_delay = TrackingAlert.objects.filter(
            asset_code="BER-TUG-08",
            alert_type=TrackingAlert.AlertType.DELAY,
            evidence__replayId="RPL-TRACK-ON-TIME",
        ).exists()
        if on_time_has_false_delay:
            raise RuntimeError("On-time replay created a false delay alert.")

        summary = {
            "pingCount": replay_pings.count(),
            "movementEventCount": replay_events.count(),
            "projectionCount": projections.count(),
            "alertTypes": sorted(observed_alerts),
            "assetIdentityCount": AssetIdentity.objects.count(),
        }
        self._record_stage(
            action="phase3.proof.observed_evidence_verified",
            title="Observed evidence verified",
            primary=f"{summary['pingCount']} pings / {len(summary['alertTypes'])} alert types",
            metadata=summary,
        )
        return summary

    def _stage_verify_rerun(self, replay_run: TelemetryReplayRun) -> dict:
        identity_count_before = AssetIdentity.objects.count()
        first = start_synthetic_replay(replay_run=replay_run)
        identity_count_after_first = AssetIdentity.objects.count()
        second = start_synthetic_replay(replay_run=replay_run)
        identity_count_after_second = AssetIdentity.objects.count()
        if not (
            identity_count_before == identity_count_after_first == identity_count_after_second
        ):
            raise RuntimeError("Replay rerun created duplicate asset identities.")
        rerun = {
            "replayId": replay_run.replay_id,
            "identityCount": identity_count_after_second,
            "pingCountAfterRerun": second["ping_count"],
            "status": second["run"].status,
        }
        self._record_stage(
            action="phase3.proof.rerun_verified",
            title="Replay rerun idempotence",
            primary=replay_run.replay_id,
            metadata=rerun,
        )
        return rerun

    def _record_stage(
        self,
        *,
        action: str,
        title: str,
        primary: str,
        metadata: dict,
    ) -> None:
        stage_no = len(self.stages) + 1
        record_audit_event(
            actor=self.admin,
            organization=self.organization,
            action=action,
            object_type="phase3_tracking_proof",
            object_id=f"{self.run_id}-{stage_no:02d}",
            object_repr=title,
            metadata={"runId": self.run_id, **metadata},
        )
        self.stages.append(
            {
                "stage": stage_no,
                "title": title,
                "result": "PASS",
                "primaryEvidence": primary,
                "auditAction": action,
            }
        )

    def _proof_audit_events(self):
        return AuditEvent.objects.filter(
            action__startswith="phase3.proof.",
            metadata__runId=self.run_id,
        ).order_by("created_at")
