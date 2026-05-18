import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.operations.models import (
    ConfirmedOperationalEvent,
    DeviceHealthSnapshot,
    EdgeEventBatch,
    OperationalActualization,
    OperationalEventCandidate,
    OperationalEventKind,
)
from apps.operations.replay import PHASE4_BATCH_SEQUENCES, replay_edge_batch, seed_phase4_event_pack


class Command(BaseCommand):
    help = "Run the repeatable Phase 4 synthetic operations replay proof flow."

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

        evidence = Phase4OperationsProofRunner().run()
        if options["json_output"]:
            self.stdout.write(json.dumps(evidence, indent=2, sort_keys=True))
            return

        self.stdout.write(self.style.SUCCESS("Phase 4 operations proof completed."))
        for stage in evidence["stages"]:
            self.stdout.write(
                f"{stage['stage']}. {stage['title']}: {stage['result']} "
                f"({stage['primaryEvidence']})"
            )


class Phase4OperationsProofRunner:
    def __init__(self):
        self.run_id = f"P4-OPERATIONS-{timezone.now():%Y%m%d%H%M%S}"
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.get(username="admin@coalflow.local")
        self.organization = self.admin.organization_memberships.first().organization
        self.stages: list[dict] = []

    def run(self) -> dict:
        batches = self._stage_seed_pack()
        replay_pack = self._stage_replay_batches(batches)
        operations_summary = self._stage_verify_operational_evidence()
        rerun = self._stage_verify_rerun(batches[0])
        audit = self._stage_verify_audit()
        return {
            "runId": self.run_id,
            "generatedAt": timezone.now().isoformat(),
            "definitionOfDone": {
                "overall": "PASS",
                "stagesPassed": len(self.stages),
                "expectedStages": 5,
            },
            "batchPack": replay_pack,
            "operationsSummary": operations_summary,
            "rerun": rerun,
            "audit": audit,
            "browserEvidenceTargets": [
                "/dashboard/situation",
                "/exceptions/center",
                "/admin/audit-logs",
            ],
            "stages": self.stages,
        }

    def _stage_seed_pack(self) -> list[EdgeEventBatch]:
        batches = seed_phase4_event_pack()
        found = tuple(batch.batch_sequence for batch in batches)
        if found != PHASE4_BATCH_SEQUENCES:
            raise RuntimeError(
                f"Phase 4 batch mismatch: expected {PHASE4_BATCH_SEQUENCES}, found {found}"
            )
        self._record_stage(
            action="phase4.proof.batch_pack_seeded",
            title="Synthetic batch pack seeded",
            primary=f"{len(batches)} edge batches",
            metadata={"batchSequences": list(found)},
        )
        return batches

    def _stage_replay_batches(self, batches: list[EdgeEventBatch]) -> list[dict]:
        rows = []
        for batch in batches:
            result = replay_edge_batch(batch=batch, actor=self.admin)
            rows.append(
                {
                    "batchId": batch.batch_id,
                    "batchSequence": batch.batch_sequence,
                    "status": result.batch.status,
                    "idempotent": result.idempotent,
                    **result.summary,
                }
            )
        self._record_stage(
            action="phase4.proof.replays_executed",
            title="Synthetic operations batches replayed",
            primary=f"{sum(row['processedCount'] for row in rows)} messages",
            metadata={"batches": rows},
        )
        return rows

    def _stage_verify_operational_evidence(self) -> dict:
        replay_candidates = OperationalEventCandidate.objects.filter(
            metadata__seed="phase4_replay"
        )
        replay_confirmed = ConfirmedOperationalEvent.objects.filter(
            candidate__metadata__seed="phase4_replay"
        )
        replay_actualizations = OperationalActualization.objects.filter(
            confirmed_event__candidate__metadata__seed="phase4_replay"
        )
        replay_health = DeviceHealthSnapshot.objects.filter(metadata__seed="phase4_replay")
        device_offline_candidates = OperationalEventCandidate.objects.filter(
            event_kind=OperationalEventKind.DEVICE_OFFLINE,
            metadata__healthRisk__snapshotRef__isnull=False,
        )
        duplicate_count = replay_candidates.filter(
            status=OperationalEventCandidate.Status.DUPLICATE
        ).count()
        pending_count = replay_candidates.filter(
            status=OperationalEventCandidate.Status.PENDING
        ).count()
        actualized_types = set(
            replay_actualizations.values_list("target_type", flat=True)
        )
        if duplicate_count < 1:
            raise RuntimeError("Replay did not produce a duplicate candidate.")
        if replay_confirmed.count() < 1 or replay_actualizations.count() < 1:
            raise RuntimeError("Replay did not produce confirmed actualized events.")
        if replay_health.count() < 1 or device_offline_candidates.count() < 1:
            raise RuntimeError("Replay did not produce health evidence and outage risk.")
        if pending_count < 1:
            raise RuntimeError("Replay did not preserve a manual-review candidate.")

        summary = {
            "candidateCount": replay_candidates.count(),
            "confirmedEventCount": replay_confirmed.count(),
            "actualizationCount": replay_actualizations.count(),
            "healthSnapshotCount": replay_health.count(),
            "duplicateCandidateCount": duplicate_count,
            "pendingCandidateCount": pending_count,
            "deviceOfflineRiskCount": device_offline_candidates.count(),
            "actualizedTargetTypes": sorted(actualized_types),
        }
        self._record_stage(
            action="phase4.proof.operational_evidence_verified",
            title="Operational evidence verified",
            primary=(
                f"{summary['confirmedEventCount']} confirmed / "
                f"{summary['healthSnapshotCount']} health"
            ),
            metadata=summary,
        )
        return summary

    def _stage_verify_rerun(self, batch: EdgeEventBatch) -> dict:
        counts_before = self._state_counts()
        result = replay_edge_batch(batch=batch, actor=self.admin)
        counts_after = self._state_counts()
        if not result.idempotent or counts_before != counts_after:
            raise RuntimeError("Edge batch rerun was not idempotent.")
        rerun = {
            "batchId": batch.batch_id,
            "batchSequence": batch.batch_sequence,
            "idempotent": result.idempotent,
            "counts": counts_after,
        }
        self._record_stage(
            action="phase4.proof.rerun_verified",
            title="Edge batch rerun idempotence",
            primary=batch.batch_sequence,
            metadata=rerun,
        )
        return rerun

    def _stage_verify_audit(self) -> dict:
        replay_audits = AuditEvent.objects.filter(
            action__in=[
                "operations.edge_batch.replayed",
                "operations.edge_batch.replay_skipped",
                "operations.device_health.ingested",
                "operational_event.ingested",
                "operational_event.duplicate",
                "operational_event.confirmed",
            ]
        )
        expected_actions = {
            "operations.edge_batch.replayed",
            "operations.edge_batch.replay_skipped",
            "operations.device_health.ingested",
            "operational_event.ingested",
            "operational_event.duplicate",
            "operational_event.confirmed",
        }
        observed_actions = set(replay_audits.values_list("action", flat=True))
        if not expected_actions.issubset(observed_actions):
            raise RuntimeError(
                f"Audit mismatch: expected {sorted(expected_actions)}, "
                f"found {sorted(observed_actions)}"
            )
        summary = {
            "auditEventCount": replay_audits.count(),
            "actions": sorted(observed_actions),
        }
        self._record_stage(
            action="phase4.proof.audit_verified",
            title="Replay audit verified",
            primary=f"{summary['auditEventCount']} audit events",
            metadata=summary,
        )
        return summary

    def _state_counts(self) -> dict:
        return {
            "candidates": OperationalEventCandidate.objects.count(),
            "confirmedEvents": ConfirmedOperationalEvent.objects.count(),
            "actualizations": OperationalActualization.objects.count(),
            "healthSnapshots": DeviceHealthSnapshot.objects.count(),
        }

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
            object_type="phase4_operations_proof",
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
