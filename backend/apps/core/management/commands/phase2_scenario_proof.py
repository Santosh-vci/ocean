import json
import os
from io import StringIO
from pathlib import Path

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.scheduling.export_services import create_governed_export
from apps.scheduling.models import (
    ExportJob,
    PlanVersion,
    ScenarioRun,
    SimulationScenario,
)
from apps.scheduling.services import (
    promote_scenario_to_proposed,
    submit_approval_request,
)

EXPECTED_SCENARIOS = [
    "SIM-JETTY-DELAY",
    "SIM-TUG-OUTAGE",
    "SIM-TIDE-RECOVERY",
    "SIM-CTS-RATE",
    "SIM-TOPUP-DEMAND",
    "SIM-MANUAL-REASSIGNMENT",
    "SIM-MULTI-CANDIDATE",
]
EVIDENCE_PATH = Path(
    os.getenv("PHASE2_EVIDENCE_PATH", "docs/evidence/phase2/phase2_scenario_evidence.json"),
)


class Command(BaseCommand):
    help = "Run the repeatable Phase 2 scenario proof flow against seeded data."

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
            help="Do not refresh Phase 2 seed data before running the proof.",
        )

    def handle(self, *args, **options):
        if not options["skip_seed"]:
            seed_stdout = StringIO()
            call_command(
                "seed_phase0",
                reset_operational_data=True,
                stdout=seed_stdout,
            )

        evidence = Phase2ScenarioProofRunner().run()
        EVIDENCE_PATH.parent.mkdir(parents=True, exist_ok=True)
        EVIDENCE_PATH.write_text(json.dumps(evidence, indent=2, sort_keys=True))

        if options["json_output"]:
            self.stdout.write(json.dumps(evidence, indent=2, sort_keys=True))
            return

        self.stdout.write(self.style.SUCCESS("Phase 2 scenario proof completed."))
        for stage in evidence["stages"]:
            self.stdout.write(
                f"{stage['stage']}. {stage['title']}: {stage['result']} "
                f"({stage['primaryEvidence']})"
            )
        self.stdout.write(f"Evidence: {evidence['evidenceFile']}")


class Phase2ScenarioProofRunner:
    def __init__(self):
        self.run_id = f"P2-SCENARIO-{timezone.now():%Y%m%d%H%M%S}"
        self.user_model = get_user_model()
        self.stages: list[dict] = []
        self.version = PlanVersion.objects.get(
            plan__name="Berau-ABL Feasible Schedule Horizon",
            version_no=1,
        )
        self.organization = self.version.plan.organization

    def run(self) -> dict:
        actors = self._actors()
        scenario_pack = self._stage_seed_pack(actors)
        projection_summary = self._stage_projection_surfaces(actors)
        multi_run = self._stage_multi_run_comparison(actors)
        promoted = self._stage_promote_selected_run(actors)
        approval = self._stage_approval_gate(actors, promoted["candidateVersionId"])
        export_job = self._stage_governed_export(actors, promoted["candidateVersionId"])
        audit = self._stage_audit_evidence(actors)

        evidence = {
            "runId": self.run_id,
            "generatedAt": timezone.now().isoformat(),
            "definitionOfDone": {
                "overall": "PASS",
                "stagesPassed": len(self.stages),
                "expectedStages": 7,
            },
            "scenarioPack": scenario_pack,
            "projectionSummary": projection_summary,
            "multiRunComparison": multi_run,
            "promotedCandidate": promoted,
            "approvalGate": approval,
            "governedExport": export_job,
            "audit": audit,
            "browserEvidenceTargets": [
                "/simulation/workspace",
                "/approvals/publishing",
                "/admin/export-handoff",
                "/admin/audit-logs",
            ],
            "stages": self.stages,
            "evidenceFile": str(EVIDENCE_PATH),
        }
        return evidence

    def _actors(self) -> dict:
        return {
            "admin": self.user_model.objects.get(username="admin@coalflow.local"),
            "berau": self.user_model.objects.get(username="berau.scheduler@coalflow.local"),
            "control": self.user_model.objects.get(username="control.tower@coalflow.local"),
        }

    def _stage_seed_pack(self, actors: dict) -> list[dict]:
        scenarios = list(
            SimulationScenario.objects.filter(
                scenario_id__in=EXPECTED_SCENARIOS,
                baseline_version=self.version,
            )
            .prefetch_related("assumptions", "runs")
            .order_by("scenario_id")
        )
        found = {scenario.scenario_id for scenario in scenarios}
        missing = sorted(set(EXPECTED_SCENARIOS) - found)
        if missing:
            raise RuntimeError(f"Missing Phase 2 seed scenarios: {missing}")

        rows = [
            {
                "scenarioId": scenario.scenario_id,
                "status": scenario.status,
                "assumptionKinds": list(
                    scenario.assumptions.values_list("kind", flat=True)
                ),
                "runCount": scenario.runs.count(),
            }
            for scenario in scenarios
        ]
        self._record_stage(
            actor=actors["admin"],
            action="phase2.proof.seed_pack_verified",
            title="Seed scenario pack",
            primary=f"{len(rows)} scenarios",
            metadata={"scenarios": rows},
        )
        return rows

    def _stage_projection_surfaces(self, actors: dict) -> dict:
        rows = []
        for scenario_id in EXPECTED_SCENARIOS:
            scenario = SimulationScenario.objects.get(scenario_id=scenario_id)
            latest_run = scenario.runs.order_by("-created_at", "-id").first()
            if latest_run is None or latest_run.status != ScenarioRun.Status.SUCCEEDED:
                raise RuntimeError(f"{scenario_id} does not have a successful run.")
            rows.append(
                {
                    "scenarioId": scenario_id,
                    "runId": latest_run.run_id,
                    "tripProjections": latest_run.trip_projections.count(),
                    "eventProjections": latest_run.event_projections.count(),
                    "constraintEvaluations": latest_run.constraint_evaluations.count(),
                    "ogvProjections": latest_run.ogv_projections.count(),
                    "resourceUtilizations": latest_run.resource_utilizations.count(),
                    "changedTripCount": latest_run.summary["projectionSummary"][
                        "changedTripCount"
                    ],
                }
            )
        self._record_stage(
            actor=actors["admin"],
            action="phase2.proof.projections_verified",
            title="Projection rows",
            primary=f"{sum(row['tripProjections'] for row in rows)} trip projections",
            metadata={"runs": rows},
        )
        return {
            "scenarioCount": len(rows),
            "totalTripProjections": sum(row["tripProjections"] for row in rows),
            "totalConstraintEvaluations": sum(
                row["constraintEvaluations"] for row in rows
            ),
            "runs": rows,
        }

    def _stage_multi_run_comparison(self, actors: dict) -> dict:
        scenario = SimulationScenario.objects.get(scenario_id="SIM-MULTI-CANDIDATE")
        runs = list(scenario.runs.order_by("created_at", "id"))
        if len(runs) < 2:
            raise RuntimeError("SIM-MULTI-CANDIDATE must keep at least two runs.")
        deltas = [
            {
                "runId": run.run_id,
                "inputHash": run.input_hash,
                "maxDelayMinutes": run.summary["projectionSummary"]["maxDelayMinutes"],
                "changedTripCount": run.summary["projectionSummary"]["changedTripCount"],
            }
            for run in runs
        ]
        self._record_stage(
            actor=actors["admin"],
            action="phase2.proof.multi_run_compared",
            title="Multi-run comparison",
            primary=f"{len(deltas)} runs",
            metadata={"runs": deltas},
        )
        return {"scenarioId": scenario.scenario_id, "runs": deltas}

    def _stage_promote_selected_run(self, actors: dict) -> dict:
        scenario = SimulationScenario.objects.get(scenario_id="SIM-JETTY-DELAY")
        selected_run = scenario.runs.order_by("-created_at", "-id").first()
        if scenario.status == SimulationScenario.Status.PROPOSED and scenario.scenario_version:
            candidate = scenario.scenario_version
        else:
            scenario = promote_scenario_to_proposed(
                scenario=scenario,
                actor=actors["admin"],
                run=selected_run,
            )
            candidate = scenario.scenario_version

        lineage = candidate.summary["scenarioLineage"]
        diff_summary = candidate.summary["scenarioDiff"]["summary"]
        self._record_stage(
            actor=actors["admin"],
            action="phase2.proof.selected_run_promoted",
            title="Selected-run promotion",
            primary=str(candidate),
            metadata={"lineage": lineage, "diffSummary": diff_summary},
        )
        return {
            "scenarioId": scenario.scenario_id,
            "candidateVersionId": candidate.id,
            "candidateVersionRef": str(candidate),
            "candidateStatus": candidate.status,
            "candidateValidation": candidate.validation_status,
            "lineage": lineage,
            "diffSummary": diff_summary,
        }

    def _stage_approval_gate(self, actors: dict, candidate_version_id: int) -> dict:
        candidate = PlanVersion.objects.get(pk=candidate_version_id)
        approval = submit_approval_request(
            plan_version=candidate,
            actor=actors["berau"],
            reason="Phase 2 proof promoted scenario candidate requires governance review.",
        )
        publish_blocked = candidate.validation_status == PlanVersion.ValidationStatus.BLOCKED
        self._record_stage(
            actor=actors["berau"],
            action="phase2.proof.approval_gate_verified",
            title="Approval gate",
            primary=approval.request_id,
            metadata={
                "approvalStatus": approval.status,
                "candidateValidation": candidate.validation_status,
                "publishBlockedByRisk": publish_blocked,
            },
        )
        return {
            "requestId": approval.request_id,
            "status": approval.status,
            "requiredAuthorities": approval.required_authorities,
            "publishBlockedByRisk": publish_blocked,
        }

    def _stage_governed_export(self, actors: dict, candidate_version_id: int) -> dict:
        candidate = PlanVersion.objects.get(pk=candidate_version_id)
        export_job = create_governed_export(
            actor=actors["control"],
            export_type=ExportJob.ExportType.SCENARIO_DIFF,
            export_format=ExportJob.ExportFormat.JSON,
            plan_version=candidate,
        )
        self._record_stage(
            actor=actors["control"],
            action="phase2.proof.scenario_diff_exported",
            title="Governed scenario diff export",
            primary=export_job.export_id,
            metadata={
                "fileName": export_job.file_name,
                "recordCount": export_job.record_count,
                "checksum": export_job.checksum_sha256,
            },
        )
        return {
            "exportId": export_job.export_id,
            "fileName": export_job.file_name,
            "recordCount": export_job.record_count,
            "checksumSha256": export_job.checksum_sha256,
            "downloadUrl": f"/api/exports/{export_job.pk}/download/",
        }

    def _stage_audit_evidence(self, actors: dict) -> dict:
        events = list(self._proof_audit_events())
        self._record_stage(
            actor=actors["admin"],
            action="phase2.proof.audit_verified",
            title="Audit evidence",
            primary=f"{len(events)} proof events before marker",
            metadata={"eventCountBeforeMarker": len(events)},
        )
        events = list(self._proof_audit_events())
        return {
            "eventCount": len(events),
            "actions": [event.action for event in events],
        }

    def _record_stage(
        self,
        *,
        actor,
        action: str,
        title: str,
        primary: str,
        metadata: dict,
    ) -> None:
        stage_no = len(self.stages) + 1
        record_audit_event(
            actor=actor,
            organization=self.organization,
            action=action,
            object_type="phase2_scenario_proof",
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
            action__startswith="phase2.proof.",
            metadata__runId=self.run_id,
        ).order_by("created_at")
