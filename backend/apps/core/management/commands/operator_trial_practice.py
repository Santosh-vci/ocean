import json
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
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
from apps.scheduling.services import generate_plan_version, next_version_no
from apps.telemetry.models import TrackingAlert


class Command(BaseCommand):
    help = "Run staged operator-practice setup steps without pre-populating demand."

    def add_arguments(self, parser):
        parser.add_argument(
            "step",
            choices=["reset", "import-demand", "enter-windows", "generate-plan", "status"],
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
            {"source": "operator-trial-practice-command"},
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
            "openConflicts": Conflict.objects.filter(resolved_at__isnull=True).count(),
            "openTrackingAlerts": TrackingAlert.objects.filter(
                status__in=[TrackingAlert.Status.OPEN, TrackingAlert.Status.ACKNOWLEDGED],
            ).count(),
            "pendingOperationalEvents": OperationalEventCandidate.objects.filter(
                status=OperationalEventCandidate.Status.PENDING,
            ).count(),
            "auditEvents": AuditEvent.objects.count(),
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
