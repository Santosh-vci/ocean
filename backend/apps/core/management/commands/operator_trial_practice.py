import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.flows.definitions import seed_canonical_flow_definitions
from apps.flows.models import FlowEvent, FlowRun
from apps.flows.services import FlowSubject, start_flow
from apps.operations.models import OperationalEventCandidate
from apps.planning.models import (
    BridgeWindow,
    CargoLayerStep,
    CargoRequirement,
    ImportJob,
    OGVVoyage,
    TideWindow,
)
from apps.planning.trial_pack import trial_dt, trial_start_date
from apps.scheduling.models import Conflict, Plan, PlanVersion, Trip
from apps.scheduling.models import (
    ApprovalRequest,
    ExportJob,
    MovementAssignmentCandidateRun,
    OptimizerRun,
    PublishabilityAssessment,
    PublishedPlanSnapshot,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    RootCauseRepairAssessment,
    SimulationScenario,
)
from apps.scheduling.services import generate_plan_version, next_version_no
from apps.telemetry.models import TrackingAlert


class Command(BaseCommand):
    help = "Run staged operator-practice setup steps without pre-populating demand."

    def add_arguments(self, parser):
        parser.add_argument(
            "step",
            choices=[
                "reset",
                "import-demand",
                "enter-windows",
                "generate-plan",
                "status",
                "prepare-db-truth",
            ],
        )
        parser.add_argument(
            "--flow",
            choices=["happy-path", "recovery"],
            default="happy-path",
            help="Flow truth to prepare when step is prepare-db-truth.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Emit machine-readable JSON only.",
        )

    def handle(self, *args, **options):
        runner = OperatorTrialPracticeRunner()
        step = options["step"]
        if step == "prepare-db-truth":
            evidence = runner.prepare_db_truth(flow=options["flow"])
        else:
            evidence = getattr(runner, step.replace("-", "_"))()
        if options["json_output"]:
            self.stdout.write(json.dumps(evidence, indent=2, sort_keys=True))
            return
        self.stdout.write(self.style.SUCCESS(f"Operator trial step complete: {step}"))
        self.stdout.write(json.dumps(evidence, indent=2, sort_keys=True))


class OperatorTrialPracticeRunner:
    def __init__(self):
        self._admin = None

    def reset(self) -> dict:
        stdout = StringIO()
        call_command(
            "seed_phase0",
            reset_operational_data=True,
            master_data_only=True,
            stdout=stdout,
        )
        return {
            "step": "reset",
            "meaning": "Master data, users, telemetry identities, and operations feeds are seeded; demand and schedules are empty.",
            "counts": self._counts(),
        }

    def import_demand(self) -> dict:
        response = self._post(
            "/api/planning/import-jobs/import-trial-demand/",
            {
                "pack": "operator_trial_phase5",
                "source": "operator-trial-practice-command",
            },
        )
        return {
            "step": "import-demand",
            "meaning": "The operator trial OGV demand file has been imported into voyage, cargo requirement, and hatch/layer queues.",
            "importJob": response,
            "counts": self._counts(),
        }

    def enter_windows(self) -> dict:
        response = self._post("/api/planning/overview/enter-operating-windows/", {})
        return {
            "step": "enter-windows",
            "meaning": "Operating windows and availability checks have been entered for the imported OGV demand.",
            "windowEntry": response,
            "counts": self._counts(),
        }

    def generate_plan(self) -> dict:
        plan = self._active_or_new_plan()
        version = PlanVersion.objects.create(
            plan=plan,
            version_no=next_version_no(plan),
            created_by=self.admin,
        )
        result = generate_plan_version(version)
        return {
            "step": "generate-plan",
            "meaning": "The tug/barge/jetty/CTS assignment plan has been generated from imported demand and operating constraints.",
            "planVersion": {
                "id": result.plan_version.id,
                "reference": str(result.plan_version),
                "status": result.plan_version.status,
                "validationStatus": result.plan_version.validation_status,
                "tripCount": result.trip_count,
                "conflictCount": result.conflict_count,
                "blockingConflictCount": result.blocking_conflict_count,
            },
            "counts": self._counts(),
        }

    def status(self) -> dict:
        return {
            "step": "status",
            "meaning": "Current operator-practice runtime state.",
            "counts": self._counts(),
            "latestPlanVersion": self._latest_plan_version(),
        }

    def prepare_db_truth(self, *, flow: str) -> dict:
        if flow == "recovery":
            return self._prepare_recovery_truth()
        return self._prepare_happy_path_truth()

    def _prepare_happy_path_truth(self) -> dict:
        self._master_data_only_reset()
        flow_run = self._create_trial_flow_run(
            flow_key="operator_happy_path_v1",
            trial_pack="operator_happy_path_v1",
            evidence_run_id="operator-trial-happy-path",
            subject_id="happy-path",
        )
        return {
            "step": "prepare-db-truth",
            "flow": "happy-path",
            "meaning": (
                "DB truth is prepared for a UI-only happy path run. "
                "Demand, windows, plans, approvals, published snapshots, and exports are empty."
            ),
            **self._flow_payload(flow_run),
            "startingCounts": self._counts(),
            "finalStateAssertions": {
                "activePublishedSnapshotExists": True,
                "approvalsComplete": True,
                "generatedExportExists": True,
                "flowCompleted": True,
            },
        }

    def _prepare_recovery_truth(self) -> dict:
        self._master_data_only_reset()
        seed_stdout = StringIO()
        call_command(
            "seed_assistant_recovery_practice",
            skip_reset=True,
            json_output=True,
            stdout=seed_stdout,
        )
        seed_summary = json.loads(seed_stdout.getvalue())
        flow_run = self._create_trial_flow_run(
            flow_key="phase5_plus_recovery_v1",
            trial_pack="operator_trial_phase5",
            evidence_run_id="operator-trial-recovery",
            subject_type="plan_version",
            subject_id=str(seed_summary["planVersionId"]),
        )
        return {
            "step": "prepare-db-truth",
            "flow": "recovery",
            "meaning": (
                "DB truth is prepared for a UI-only recovery run. "
                "Disrupted demand and a blocked plan exist; recommendations and scenarios do not."
            ),
            **self._flow_payload(flow_run),
            "seedSummary": seed_summary,
            "startingCounts": self._counts(),
            "finalStateAssertions": {
                "recommendationsCreatedByUi": True,
                "scenarioMaterializedByUi": True,
                "activePublishedSnapshotExists": True,
                "flowCompleted": True,
            },
        }

    def _master_data_only_reset(self) -> None:
        stdout = StringIO()
        call_command(
            "seed_phase0",
            reset_operational_data=True,
            master_data_only=True,
            stdout=stdout,
        )
        FlowRun.objects.all().delete()
        seed_canonical_flow_definitions()

    def _create_trial_flow_run(
        self,
        *,
        flow_key: str,
        trial_pack: str,
        evidence_run_id: str,
        subject_id: str,
        subject_type: str = "operator_trial",
    ) -> FlowRun:
        FlowRun.objects.all().delete()
        definition = seed_canonical_flow_definitions()
        selected = next(item for item in definition if item.flow_key == flow_key)
        expected_action_ids = [
            step["expected_action_id"] for step in selected.steps if step.get("expected_action_id")
        ]
        expected_routes = [
            step["expected_route"] for step in selected.steps if step.get("expected_route")
        ]
        return start_flow(
            flow_key,
            actor=self.admin,
            subject=FlowSubject(subject_type, subject_id),
            metadata={
                "trial_pack": trial_pack,
                "evidence_run_id": evidence_run_id,
                "expected_action_ids": expected_action_ids,
                "expected_routes": expected_routes,
            },
        )

    def _flow_payload(self, flow_run: FlowRun) -> dict:
        flow_run.refresh_from_db()
        steps = list(flow_run.step_runs.order_by("sequence"))
        return {
            "flowRunId": flow_run.run_id,
            "flowKey": flow_run.flow_definition.flow_key,
            "flowName": flow_run.flow_definition.name,
            "flowStatus": flow_run.status,
            "currentStep": flow_run.current_step_key,
            "expectedActionIds": flow_run.metadata.get("expected_action_ids", []),
            "expectedRouteSequence": flow_run.metadata.get("expected_routes", []),
            "stepSequence": [
                {
                    "stepKey": step.step_key,
                    "status": step.status,
                    "expectedRoute": step.expected_route,
                    "expectedActionId": step.expected_action_id,
                }
                for step in steps
            ],
        }

    def _active_or_new_plan(self) -> Plan:
        plan_code = f"PLAN-{trial_start_date():%Y-%m-%d}"
        plan = Plan.objects.filter(code=plan_code).first()
        if plan:
            return plan
        organization = self.admin.organization_memberships.filter(
            is_default=True,
            is_active=True,
        ).select_related("organization").first()
        return Plan.objects.create(
            code=plan_code,
            name="Berau-ABL Operator Practice Schedule Horizon",
            organization=organization.organization if organization else None,
            horizon_start=trial_dt(0, 0),
            horizon_end=trial_dt(7, 23, 59),
            status=Plan.Status.ACTIVE,
        )

    def _post(self, path: str, payload: dict) -> dict:
        client = APIClient(HTTP_HOST="localhost")
        client.force_authenticate(user=self.admin)
        response = client.post(path, payload, format="json")
        if response.status_code >= 400:
            raise RuntimeError(f"{path} failed: {response.status_code} {response.data}")
        return response.data

    def _counts(self) -> dict:
        return {
            "voyages": OGVVoyage.objects.count(),
            "cargoRequirements": CargoRequirement.objects.count(),
            "cargoLayerSteps": CargoLayerStep.objects.count(),
            "importJobs": ImportJob.objects.count(),
            "tideWindows": TideWindow.objects.count(),
            "bridgeWindows": BridgeWindow.objects.count(),
            "plans": Plan.objects.count(),
            "planVersions": PlanVersion.objects.count(),
            "trips": Trip.objects.count(),
            "movementAssignmentCandidateRuns": MovementAssignmentCandidateRun.objects.count(),
            "approvalRequests": ApprovalRequest.objects.count(),
            "publishedSnapshots": PublishedPlanSnapshot.objects.count(),
            "exports": ExportJob.objects.count(),
            "recoverySnapshots": RecoveryInputSnapshot.objects.count(),
            "optimizerRuns": OptimizerRun.objects.count(),
            "recommendations": RecoveryRecommendation.objects.count(),
            "rootCauseAssessments": RootCauseRepairAssessment.objects.count(),
            "publishabilityAssessments": PublishabilityAssessment.objects.count(),
            "scenarios": SimulationScenario.objects.count(),
            "openConflicts": Conflict.objects.filter(resolved_at__isnull=True).count(),
            "openTrackingAlerts": TrackingAlert.objects.filter(
                status__in=[TrackingAlert.Status.OPEN, TrackingAlert.Status.ACKNOWLEDGED],
            ).count(),
            "pendingOperationalEvents": OperationalEventCandidate.objects.filter(
                status=OperationalEventCandidate.Status.PENDING,
            ).count(),
            "auditEvents": AuditEvent.objects.count(),
            "flowRuns": FlowRun.objects.count(),
            "flowEvents": FlowEvent.objects.count(),
        }

    def _latest_plan_version(self) -> dict | None:
        version = PlanVersion.objects.order_by("-created_at", "-id").first()
        if version is None:
            return None
        return {
            "id": version.id,
            "reference": str(version),
            "status": version.status,
            "validationStatus": version.validation_status,
            "summary": version.summary,
        }

    @property
    def admin(self):
        if self._admin is None:
            self._admin = get_user_model().objects.get(username="admin@coalflow.local")
        return self._admin
