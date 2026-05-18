import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.scheduling.models import (
    ApprovalDecision,
    OptimizerRun,
    PlanVersion,
    RecoveryAction,
    RecoveryRecommendation,
    ScenarioRun,
)
from apps.scheduling.recovery_services import (
    RECOVERY_PROOF_PACK_VERSION,
    build_recommendation_proof_pack,
    build_recovery_input_snapshot,
    generate_recovery_recommendations,
    materialize_recommendation_as_scenario,
)
from apps.scheduling.services import (
    promote_scenario_to_proposed,
    record_approval_decision,
    submit_approval_request,
)

EVIDENCE_FILE = "docs/evidence/phase5/phase5_recovery_evidence.json"


class Command(BaseCommand):
    help = "Run the repeatable Phase 5 recommendation proof flow."

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

        evidence = Phase5RecoveryProofRunner().run()

        if options["json_output"]:
            self.stdout.write(json.dumps(evidence, indent=2, sort_keys=True))
            return

        self.stdout.write(self.style.SUCCESS("Phase 5 recovery proof completed."))
        for stage in evidence["stages"]:
            self.stdout.write(
                f"{stage['stage']}. {stage['title']}: {stage['result']} "
                f"({stage['primaryEvidence']})"
            )
        self.stdout.write(f"Evidence: {evidence['evidenceFile']}")


class Phase5RecoveryProofRunner:
    def __init__(self):
        self.run_id = f"P5-RECOVERY-{timezone.now():%Y%m%d%H%M%S}"
        self.user_model = get_user_model()
        self.admin = self.user_model.objects.get(username="admin@coalflow.local")
        self.berau = self.user_model.objects.get(username="berau.scheduler@coalflow.local")
        self.abl = self.user_model.objects.get(username="abl.dispatcher@coalflow.local")
        self.organization = self.admin.organization_memberships.first().organization
        self.stages: list[dict] = []

    def run(self) -> dict:
        seed_run = self._stage_seed_pack()
        optimizer_run = self._stage_governed_recovery_run(seed_run)
        recommendation = self._stage_ranked_recommendation(optimizer_run)
        scenario = self._stage_materialize_scenario(recommendation)
        approval = self._stage_approval_handoff(scenario)
        proof_pack = self._stage_proof_pack(recommendation)
        audit = self._stage_audit_evidence()
        return {
            "runId": self.run_id,
            "generatedAt": timezone.now().isoformat(),
            "definitionOfDone": {
                "overall": "PASS",
                "stagesPassed": len(self.stages),
                "expectedStages": 7,
            },
            "optimizerRun": {
                "runId": optimizer_run.run_id,
                "recommendationCount": optimizer_run.recommendations.count(),
                "bestRecommendation": optimizer_run.summary["bestRecommendation"],
                "bestStrategy": optimizer_run.summary["bestStrategy"],
            },
            "selectedRecommendation": {
                "recommendationId": recommendation.recommendation_id,
                "rank": recommendation.rank,
                "riskLevel": recommendation.risk_level,
                "score": float(recommendation.score),
            },
            "scenarioHandoff": {
                "scenarioId": scenario.scenario_id,
                "scenarioStatus": scenario.status,
                "scenarioRunId": scenario.runs.order_by("-created_at", "-id").first().run_id,
            },
            "approvalHandoff": approval,
            "proofPack": proof_pack,
            "audit": audit,
            "browserEvidenceTargets": [
                "/exceptions/center",
                "/recovery/recommendations",
                "/simulation/workspace",
                "/approvals/publishing",
                "/admin/audit-logs",
            ],
            "stages": self.stages,
            "evidenceFile": EVIDENCE_FILE,
        }

    def _stage_seed_pack(self) -> OptimizerRun:
        optimizer_run = OptimizerRun.objects.get(run_id="OPT-PHASE5-SEED")
        recommendations = optimizer_run.recommendations.order_by("rank")
        if optimizer_run.status != OptimizerRun.Status.SUCCEEDED:
            raise RuntimeError("Phase 5 seed optimizer run did not succeed.")
        if recommendations.count() < 4:
            raise RuntimeError("Phase 5 seed optimizer run did not create enough candidates.")
        self._record_stage(
            action="phase5.proof.seed_pack_verified",
            title="Recommendation seed pack",
            primary=f"{recommendations.count()} candidates",
            metadata={
                "runId": optimizer_run.run_id,
                "candidateStrategies": optimizer_run.summary["candidateStrategies"],
            },
        )
        return optimizer_run

    def _stage_governed_recovery_run(self, seed_run: OptimizerRun) -> OptimizerRun:
        seed_snapshot = seed_run.input_snapshot
        snapshot = build_recovery_input_snapshot(
            plan_version=seed_snapshot.plan_version,
            source_conflict=seed_snapshot.source_conflict,
            source_override=None if seed_snapshot.source_conflict_id else seed_snapshot.source_override,
            actor=self.admin,
            metadata={"proofRunId": self.run_id},
        )
        record_audit_event(
            actor=self.admin,
            organization=snapshot.organization,
            action="recovery.input_snapshot.build",
            object_type="recovery_input_snapshot",
            object_id=str(snapshot.pk),
            object_repr=snapshot.snapshot_id,
            metadata={
                "plan_version": str(snapshot.plan_version),
                "source_kind": snapshot.source_kind,
                "source_ref": snapshot.source_ref,
                "proofRunId": self.run_id,
            },
        )
        optimizer_run = generate_recovery_recommendations(
            snapshot=snapshot,
            actor=self.admin,
            run_id=f"OPT-{self.run_id}",
        )
        record_audit_event(
            actor=self.admin,
            organization=optimizer_run.organization,
            action="recovery.optimizer.run",
            object_type="optimizer_run",
            object_id=str(optimizer_run.pk),
            object_repr=optimizer_run.run_id,
            metadata={
                "input_snapshot": snapshot.snapshot_id,
                "recommendation_count": optimizer_run.recommendations.count(),
                "best_strategy": optimizer_run.summary.get("bestStrategy", ""),
                "proofRunId": self.run_id,
            },
        )
        self._record_stage(
            action="phase5.proof.governed_run_verified",
            title="Governed recovery run",
            primary=optimizer_run.run_id,
            metadata={
                "snapshotId": snapshot.snapshot_id,
                "recommendationCount": optimizer_run.recommendations.count(),
                "bestStrategy": optimizer_run.summary["bestStrategy"],
            },
        )
        return optimizer_run

    def _stage_ranked_recommendation(
        self,
        optimizer_run: OptimizerRun,
    ) -> RecoveryRecommendation:
        recommendation = (
            optimizer_run.recommendations.exclude(
                actions__action_type=RecoveryAction.ActionType.NOOP,
            )
            .select_related("evaluation")
            .order_by("rank")
            .first()
        )
        if recommendation is None:
            raise RuntimeError("No actionable recommendation is available for proof.")
        evaluation = recommendation.evaluation
        if not evaluation.hard_constraints_passed:
            raise RuntimeError("Top actionable recommendation failed hard constraints.")
        self._record_stage(
            action="phase5.proof.ranking_verified",
            title="Recommendation ranking",
            primary=recommendation.recommendation_id,
            metadata={
                "rank": recommendation.rank,
                "score": float(recommendation.score),
                "riskLevel": recommendation.risk_level,
                "strategy": recommendation.metadata["strategy"],
                "hardConstraintsPassed": evaluation.hard_constraints_passed,
            },
        )
        return recommendation

    def _stage_materialize_scenario(self, recommendation: RecoveryRecommendation):
        recommendation = materialize_recommendation_as_scenario(
            recommendation=recommendation,
            actor=self.admin,
            name="Phase 5 recovery proof recommendation",
            run_simulation=True,
        )
        scenario = recommendation.scenario
        latest_run = scenario.runs.order_by("-created_at", "-id").first()
        if latest_run is None or latest_run.status != ScenarioRun.Status.SUCCEEDED:
            raise RuntimeError("Recommendation did not materialize into a successful scenario run.")
        record_audit_event(
            actor=self.admin,
            organization=recommendation.organization,
            action="recovery.recommendation.materialize_scenario",
            object_type="recovery_recommendation",
            object_id=str(recommendation.pk),
            object_repr=recommendation.recommendation_id,
            metadata={
                "scenario_id": scenario.scenario_id,
                "scenario_pk": scenario.pk,
                "scenario_status": scenario.status,
                "optimizer_run": recommendation.optimizer_run.run_id,
                "strategy": recommendation.metadata.get("strategy", ""),
                "proofRunId": self.run_id,
            },
        )
        self._record_stage(
            action="phase5.proof.scenario_materialized",
            title="Recommendation scenario handoff",
            primary=f"{recommendation.recommendation_id} -> {scenario.scenario_id}",
            metadata={
                "scenarioId": scenario.scenario_id,
                "scenarioRunId": latest_run.run_id,
                "assumptionCount": scenario.assumptions.count(),
            },
        )
        return scenario

    def _stage_approval_handoff(self, scenario) -> dict:
        scenario = promote_scenario_to_proposed(
            scenario=scenario,
            actor=self.admin,
        )
        candidate = scenario.scenario_version
        approval = submit_approval_request(
            plan_version=candidate,
            actor=self.berau,
            reason="Phase 5 proof recommendation promoted for governed approval.",
        )
        record_audit_event(
            actor=self.berau,
            organization=self.organization,
            action="approval.request",
            object_type="approval_request",
            object_id=str(approval.pk),
            object_repr=approval.request_id,
            metadata={
                "plan_version": str(candidate),
                "status": approval.status,
                "proofRunId": self.run_id,
            },
        )
        berau_decision = record_approval_decision(
            approval_request=approval,
            actor=self.berau,
            decision=ApprovalDecision.Decision.APPROVE,
            authority_role=ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
            comments="Phase 5 proof review by Berau scheduler.",
        )
        record_audit_event(
            actor=self.berau,
            organization=berau_decision.organization,
            action="approval.decision",
            object_type="approval_decision",
            object_id=str(berau_decision.pk),
            object_repr=str(berau_decision),
            metadata={
                "request_id": approval.request_id,
                "authority_role": berau_decision.authority_role,
                "decision": berau_decision.decision,
                "proofRunId": self.run_id,
            },
        )
        abl_decision = record_approval_decision(
            approval_request=approval,
            actor=self.abl,
            decision=ApprovalDecision.Decision.APPROVE,
            authority_role=ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
            comments="Phase 5 proof review by ABL dispatcher.",
        )
        record_audit_event(
            actor=self.abl,
            organization=abl_decision.organization,
            action="approval.decision",
            object_type="approval_decision",
            object_id=str(abl_decision.pk),
            object_repr=str(abl_decision),
            metadata={
                "request_id": approval.request_id,
                "authority_role": abl_decision.authority_role,
                "decision": abl_decision.decision,
                "proofRunId": self.run_id,
            },
        )
        approval.refresh_from_db()
        candidate.refresh_from_db()
        publish_blocked_by_risk = candidate.status != PlanVersion.Status.APPROVED
        self._record_stage(
            action="phase5.proof.approval_handoff_verified",
            title="Promotion and approval handoff",
            primary=approval.request_id,
            metadata={
                "candidateVersion": str(candidate),
                "candidateStatus": candidate.status,
                "candidateValidation": candidate.validation_status,
                "approvalStatus": approval.status,
                "publishBlockedByRisk": publish_blocked_by_risk,
            },
        )
        return {
            "candidateVersionId": candidate.pk,
            "candidateVersionRef": str(candidate),
            "candidateStatus": candidate.status,
            "candidateValidation": candidate.validation_status,
            "requestId": approval.request_id,
            "approvalStatus": approval.status,
            "decisionCount": approval.decisions.count(),
            "publishBlockedByRisk": publish_blocked_by_risk,
        }

    def _stage_proof_pack(self, recommendation: RecoveryRecommendation) -> dict:
        recommendation.refresh_from_db()
        record_audit_event(
            actor=self.admin,
            organization=recommendation.organization,
            action="recovery.recommendation.proof_pack_viewed",
            object_type="recovery_recommendation",
            object_id=str(recommendation.pk),
            object_repr=recommendation.recommendation_id,
            metadata={
                "proof_pack_version": RECOVERY_PROOF_PACK_VERSION,
                "optimizer_run": recommendation.optimizer_run.run_id,
                "scenario_id": recommendation.scenario.scenario_id
                if recommendation.scenario
                else None,
                "proofRunId": self.run_id,
            },
        )
        payload = build_recommendation_proof_pack(recommendation=recommendation)
        if payload["proofPackVersion"] != RECOVERY_PROOF_PACK_VERSION:
            raise RuntimeError("Unexpected recommendation proof-pack version.")
        if payload["scenarioHandoff"] is None or not payload["approvalChain"]:
            raise RuntimeError("Proof pack did not include scenario and approval lineage.")
        self._record_stage(
            action="phase5.proof.proof_pack_verified",
            title="Recommendation proof pack",
            primary=payload["proofPackVersion"],
            metadata={
                "recommendationId": payload["recommendation"]["recommendationId"],
                "scenarioId": payload["scenarioHandoff"]["scenarioId"],
                "approvalCount": len(payload["approvalChain"]),
                "auditTrailCount": len(payload["auditTrail"]),
            },
        )
        return {
            "proofPackVersion": payload["proofPackVersion"],
            "recommendationId": payload["recommendation"]["recommendationId"],
            "scenarioId": payload["scenarioHandoff"]["scenarioId"],
            "approvalCount": len(payload["approvalChain"]),
            "auditTrailCount": len(payload["auditTrail"]),
        }

    def _stage_audit_evidence(self) -> dict:
        events = list(self._proof_audit_events())
        self._record_stage(
            action="phase5.proof.audit_verified",
            title="Proof audit evidence",
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
            object_type="phase5_recovery_proof",
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
            action__startswith="phase5.proof.",
            metadata__runId=self.run_id,
        ).order_by("created_at")
