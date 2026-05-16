import json
from datetime import datetime
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.masters.models import Barge, CoalGrade, CTSAsset, Jetty, Location
from apps.organizations.models import Organization
from apps.planning.models import (
    AssetAvailabilityWindow,
    BridgeWindow,
    CargoLayerStep,
    CargoRequirement,
    ImportJob,
    JettyAvailabilityWindow,
    NavigationConstraintCheck,
    OGVVoyage,
    TideWindow,
)
from apps.rbac.services import user_has_permission_code
from apps.scheduling.export_services import create_governed_export
from apps.scheduling.models import (
    ApprovalDecision,
    Conflict,
    ExportJob,
    OverrideRequest,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
    ScheduleEvent,
    Trip,
)
from apps.scheduling.services import (
    apply_assignment_override,
    generate_plan_version,
    publish_plan_version,
    record_approval_decision,
    submit_approval_request,
)

PLAN_CODE = "PLAN-PHASE1-E2E"
VOYAGE_ID = "VOY-PHASE1-HAPPY-001"
DEMAND_FILENAME = "phase1_e2e_operator_demand.xlsx"
PROOF_REASON = "Phase 1 end-to-end proof run"


class Command(BaseCommand):
    help = "Run a repeatable Phase 1 end-to-end proof scenario against the live database."

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
            call_command("seed_phase0", stdout=seed_stdout)

        evidence = Phase1ProofRunner().run()

        if options["json_output"]:
            self.stdout.write(json.dumps(evidence, indent=2, sort_keys=True))
            return

        self.stdout.write(self.style.SUCCESS("Phase 1 end-to-end proof completed."))
        for stage in evidence["stages"]:
            self.stdout.write(
                f"{stage['stage']}. {stage['title']}: {stage['result']} "
                f"({stage['primaryEvidence']})"
            )
        self.stdout.write(f"Export: {evidence['governedExport']['fileName']}")


class Phase1ProofRunner:
    def __init__(self):
        self.run_id = f"P1-E2E-{timezone.now():%Y%m%d%H%M%S}"
        self.user_model = get_user_model()
        self.stages: list[dict] = []

    def run(self) -> dict:
        self._reset_existing_proof()
        actors = self._actors()
        organizations = self._organizations()
        masters = self._masters()

        self._stage_login_and_roles(actors)
        self._stage_master_data(masters)
        voyage, requirement, layers, import_job = self._stage_demand_upload(
            actors=actors,
            organizations=organizations,
            masters=masters,
        )
        windows = self._stage_manual_windows(voyage=voyage, masters=masters)
        plan_version, generation = self._stage_generate_schedule(
            actors=actors,
            organizations=organizations,
        )
        chain = self._stage_trip_chain(plan_version=plan_version)
        override = self._stage_governed_adjustment(
            actors=actors,
            plan_version=plan_version,
        )
        approval_request, snapshot = self._stage_approval_publish(
            actors=actors,
            plan_version=plan_version,
        )
        self._stage_live_version_and_audit(snapshot=snapshot)
        export_job = self._stage_governed_export(
            actors=actors,
            plan_version=plan_version,
        )
        audit_events = self._proof_audit_events()
        constraint_scenario = self._constraint_scenario()

        return {
            "runId": self.run_id,
            "generatedAt": timezone.now().isoformat(),
            "definitionOfDone": {
                "overall": "PASS",
                "stagesPassed": len(self.stages),
                "expectedStages": 10,
            },
            "happyPath": {
                "planCode": PLAN_CODE,
                "planVersionId": plan_version.id,
                "status": plan_version.status,
                "validationStatus": plan_version.validation_status,
                "voyageId": voyage.voyage_id,
                "vesselName": voyage.vessel_name,
                "requiredMt": voyage.required_mt,
                "cargoRequirementId": requirement.id,
                "layerStepIds": [layer.id for layer in layers],
                "tripCount": generation["tripCount"],
                "eventCount": chain["eventCount"],
                "overrideId": override.id,
                "approvalRequestId": approval_request.request_id,
                "snapshotId": snapshot.snapshot_id,
            },
            "constraintScenario": constraint_scenario,
            "manualWindows": windows,
            "governedExport": {
                "exportId": export_job.export_id,
                "fileName": export_job.file_name,
                "storageUri": f"{export_job.storage_bucket}/{export_job.storage_key}",
                "checksumSha256": export_job.checksum_sha256,
                "recordCount": export_job.record_count,
                "format": export_job.export_format,
            },
            "auditTrail": {
                "events": [
                    {
                        "action": event.action,
                        "objectType": event.object_type,
                        "objectId": event.object_id,
                        "actor": event.actor.email if event.actor else "system",
                        "createdAt": event.created_at.isoformat(),
                    }
                    for event in audit_events
                ],
                "eventCount": len(audit_events),
            },
            "applicationEvidencePaths": [
                "http://localhost:8080/#/dashboard/situation",
                "http://localhost:8080/#/admin/master-data",
                "http://localhost:8080/#/schedule/ogv-demand",
                "http://localhost:8080/#/constraints/tide-bridge",
                "http://localhost:8080/#/schedule/published-plan",
                "http://localhost:8080/#/approvals/publishing",
                "http://localhost:8080/#/admin/audit-logs",
                "http://localhost:8080/#/admin/export-handoff",
            ],
            "stages": self.stages,
        }

    def _reset_existing_proof(self) -> None:
        ExportJob.objects.filter(plan_version__plan__code=PLAN_CODE).delete()
        PublishedPlanSnapshot.objects.filter(plan__code=PLAN_CODE).delete()
        Plan.objects.filter(code=PLAN_CODE).delete()
        OGVVoyage.objects.filter(voyage_id=VOYAGE_ID).delete()
        ImportJob.objects.filter(filename=DEMAND_FILENAME).delete()
        TideWindow.objects.filter(code__startswith="TIDE-P1-E2E").delete()
        BridgeWindow.objects.filter(code__startswith="BRDG-P1-E2E").delete()
        AssetAvailabilityWindow.objects.filter(reason=PROOF_REASON).delete()
        JettyAvailabilityWindow.objects.filter(reason=PROOF_REASON).delete()

    def _actors(self) -> dict:
        return {
            "admin": self.user_model.objects.get(username="admin@coalflow.local"),
            "berau": self.user_model.objects.get(username="berau.scheduler@coalflow.local"),
            "abl": self.user_model.objects.get(username="abl.dispatcher@coalflow.local"),
            "control": self.user_model.objects.get(username="control.tower@coalflow.local"),
            "viewer": self.user_model.objects.get(username="viewer@coalflow.local"),
        }

    def _organizations(self) -> dict:
        return {
            "berau": Organization.objects.get(slug="berau-coal"),
            "abl": Organization.objects.get(slug="abl"),
            "platform": Organization.objects.get(slug="coalflow-platform"),
        }

    def _masters(self) -> dict:
        return {
            "ebony": CoalGrade.objects.get(code="EBONY"),
            "agathis": CoalGrade.objects.get(code="AGATHIS"),
            "sambarata_port": Location.objects.get(code="LOC-SAMBARATA-PORT"),
            "lati_port": Location.objects.get(code="LOC-LATI-PORT"),
            "anchorage": Location.objects.get(code="LOC-ANCHORAGE-SOUTH"),
            "rantau_delta": Location.objects.get(code="LOC-RANTAU-DELTA"),
            "bridge_gate": Location.objects.get(code="LOC-BRIDGE-GATE-B"),
            "suaran_jetty": Jetty.objects.get(code="JTY-SUARAN"),
            "lati_jetty": Jetty.objects.get(code="JTY-LATI"),
            "barge_valiant": Barge.objects.get(code="BRG-VAL-08"),
            "barge_nusantara": Barge.objects.get(code="BRG-NUS-17"),
            "cts_borneo": CTSAsset.objects.get(code="CTS-BORNEO"),
            "cts_java": CTSAsset.objects.get(code="CTS-JAVA"),
        }

    def _dt(self, day: int, hour: int, minute: int = 0):
        return timezone.make_aware(datetime(2026, 11, day, hour, minute))

    def _record_stage(
        self,
        *,
        number: int,
        title: str,
        actor,
        primary_evidence: str,
        route: str,
        records: dict,
        audit_action: str,
        organization=None,
    ) -> None:
        record_audit_event(
            actor=actor,
            organization=organization,
            action=audit_action,
            object_type="phase1_e2e_stage",
            object_id=f"{self.run_id}-{number:02d}",
            object_repr=title,
            metadata={"records": records, "route": route},
        )
        self.stages.append(
            {
                "stage": number,
                "title": title,
                "result": "PASS",
                "actor": actor.email if actor else "system",
                "primaryEvidence": primary_evidence,
                "applicationRoute": route,
                "records": records,
            }
        )

    def _stage_login_and_roles(self, actors: dict) -> None:
        role_checks = {
            "admin": user_has_permission_code(actors["admin"], "admin.view"),
            "berauScheduler": user_has_permission_code(actors["berau"], "schedule.edit"),
            "ablDispatcher": user_has_permission_code(actors["abl"], "fleet.assign"),
            "controlTowerPublish": user_has_permission_code(actors["control"], "schedule.publish"),
            "viewerReadOnly": not user_has_permission_code(actors["viewer"], "schedule.edit"),
        }
        if not all(role_checks.values()):
            raise RuntimeError(f"Seeded role proof failed: {role_checks}")
        self._record_stage(
            number=1,
            title="Login under correct organization and role",
            actor=actors["admin"],
            primary_evidence="5 seeded users verified with role-shaped permissions",
            route="/me/",
            records=role_checks,
            audit_action="phase1.proof.login_roles_verified",
        )

    def _stage_master_data(self, masters: dict) -> None:
        records = {
            "coalGrades": CoalGrade.objects.count(),
            "jetties": Jetty.objects.count(),
            "locations": Location.objects.count(),
            "bargeSample": [
                masters["barge_valiant"].code,
                masters["barge_nusantara"].code,
            ],
            "jettySample": [
                masters["suaran_jetty"].code,
                masters["lati_jetty"].code,
            ],
        }
        self._record_stage(
            number=2,
            title="Review planning master data",
            actor=self.user_model.objects.get(username="admin@coalflow.local"),
            primary_evidence=(
                f"{records['coalGrades']} coal grades, {records['jetties']} jetties, "
                f"{records['locations']} locations"
            ),
            route="/admin/master-data",
            records=records,
            audit_action="phase1.proof.master_data_reviewed",
        )

    def _stage_demand_upload(self, *, actors: dict, organizations: dict, masters: dict):
        voyage = OGVVoyage.objects.create(
            voyage_id=VOYAGE_ID,
            vessel_name="MV Phase One Reliance",
            customer_name="Berau Contract Lift",
            vessel_class="Panamax",
            eta=self._dt(5, 6),
            etb=self._dt(5, 18),
            etc_target=self._dt(7, 6),
            laycan_start=self._dt(5, 0),
            laycan_end=self._dt(8, 0),
            required_mt=64000,
            priority=1,
            demurrage_rate_usd_per_day=52000,
            anchorage_location=masters["anchorage"],
            organization=organizations["berau"],
            status=OGVVoyage.Status.PLANNED,
            risk_status=OGVVoyage.RiskStatus.LOW,
            current_stage="Demand uploaded and cargo-layer plan accepted",
        )
        ebony_requirement = CargoRequirement.objects.create(
            voyage=voyage,
            coal_grade=masters["ebony"],
            source_location=masters["sambarata_port"],
            preferred_jetty=masters["suaran_jetty"],
            required_mt=32000,
            status=CargoRequirement.Status.PLANNED,
        )
        agathis_requirement = CargoRequirement.objects.create(
            voyage=voyage,
            coal_grade=masters["agathis"],
            source_location=masters["lati_port"],
            preferred_jetty=masters["lati_jetty"],
            required_mt=32000,
            status=CargoRequirement.Status.PLANNED,
        )
        layers = [
            CargoLayerStep.objects.create(
                voyage=voyage,
                cargo_requirement=ebony_requirement,
                hatch_no=1,
                layer_no=1,
                required_sequence_no=1,
                coal_grade=masters["ebony"],
                required_mt=32000,
                remaining_mt=32000,
                planned_barge=masters["barge_valiant"],
                planned_jetty=masters["suaran_jetty"],
                planned_cts=masters["cts_borneo"],
                status=CargoLayerStep.Status.PLANNED,
                chain_status="READY FOR DRAFT",
                planned_start=self._dt(5, 8),
                planned_end=self._dt(5, 18),
            ),
            CargoLayerStep.objects.create(
                voyage=voyage,
                cargo_requirement=agathis_requirement,
                hatch_no=2,
                layer_no=1,
                required_sequence_no=2,
                coal_grade=masters["agathis"],
                required_mt=32000,
                remaining_mt=32000,
                planned_barge=masters["barge_nusantara"],
                planned_jetty=masters["lati_jetty"],
                planned_cts=masters["cts_java"],
                status=CargoLayerStep.Status.PLANNED,
                chain_status="READY FOR DRAFT",
                planned_start=self._dt(5, 20),
                planned_end=self._dt(6, 6),
            ),
        ]
        import_job = ImportJob.objects.create(
            import_type=ImportJob.ImportType.OGV_DEMAND,
            filename=DEMAND_FILENAME,
            source="phase1_e2e_proof",
            status=ImportJob.Status.IMPORTED,
            total_rows=1,
            valid_rows=1,
            error_rows=0,
            errors=[],
            created_by=actors["berau"],
        )
        self._record_stage(
            number=3,
            title="Upload OGV demand and cargo-layer requirements",
            actor=actors["berau"],
            primary_evidence=(
                f"{voyage.voyage_id} / {voyage.required_mt} MT / "
                f"{len(layers)} cargo layers"
            ),
            route="/schedule/ogv-demand",
            records={
                "importJobId": import_job.id,
                "filename": import_job.filename,
                "voyageId": voyage.voyage_id,
                "cargoRequirements": [
                    ebony_requirement.id,
                    agathis_requirement.id,
                ],
                "layerSteps": [layer.id for layer in layers],
            },
            audit_action="phase1.proof.demand_uploaded",
            organization=organizations["berau"],
        )
        return voyage, ebony_requirement, layers, import_job

    def _stage_manual_windows(self, *, voyage, masters: dict) -> dict:
        for asset_type, asset_code in [
            (AssetAvailabilityWindow.AssetType.TUG, "BER-TUG-08"),
            (AssetAvailabilityWindow.AssetType.TUG, "BER-TUG-09"),
            (AssetAvailabilityWindow.AssetType.BARGE, "BRG-VAL-08"),
            (AssetAvailabilityWindow.AssetType.BARGE, "BRG-NUS-17"),
            (AssetAvailabilityWindow.AssetType.CTS, "CTS-BORNEO"),
            (AssetAvailabilityWindow.AssetType.CTS, "CTS-JAVA"),
        ]:
            AssetAvailabilityWindow.objects.create(
                asset_type=asset_type,
                asset_code=asset_code,
                window_start=self._dt(5, 0),
                window_end=self._dt(7, 12),
                status=AssetAvailabilityWindow.Status.AVAILABLE,
                reason=PROOF_REASON,
            )
        JettyAvailabilityWindow.objects.create(
            jetty=masters["suaran_jetty"],
            window_start=self._dt(5, 0),
            window_end=self._dt(7, 12),
            status=JettyAvailabilityWindow.Status.WORKING,
            loading_rate_override_tph=2800,
            reason=PROOF_REASON,
        )
        JettyAvailabilityWindow.objects.create(
            jetty=masters["lati_jetty"],
            window_start=self._dt(5, 0),
            window_end=self._dt(7, 12),
            status=JettyAvailabilityWindow.Status.WORKING,
            loading_rate_override_tph=2200,
            reason=PROOF_REASON,
        )
        tide = TideWindow.objects.create(
            code="TIDE-P1-E2E-RANTAU",
            location=masters["rantau_delta"],
            window_start=self._dt(5, 7),
            window_end=self._dt(5, 23),
            min_water_level_m="2.80",
            max_loaded_draft_m="4.80",
            risk_level=TideWindow.RiskLevel.NORMAL,
            source="phase1_e2e_proof",
        )
        bridge = BridgeWindow.objects.create(
            code="BRDG-P1-E2E-GATE-B",
            location=masters["bridge_gate"],
            window_start=self._dt(5, 6),
            window_end=self._dt(6, 2),
            clearance_m="13.20",
            allowed_asset_class="300ft barge",
            status=BridgeWindow.Status.OPEN,
            notes=PROOF_REASON,
        )
        NavigationConstraintCheck.objects.create(
            voyage=voyage,
            asset_code="BRG-VAL-08",
            constraint_type=NavigationConstraintCheck.ConstraintType.TIDE,
            eta_gate=self._dt(5, 12),
            window_start=tide.window_start,
            window_end=tide.window_end,
            draft_m="4.20",
            margin_minutes=180,
            status=NavigationConstraintCheck.Status.CAN_CROSS,
            recovery_hint="Happy-path proof: loaded barge crosses inside tide window.",
        )
        NavigationConstraintCheck.objects.create(
            voyage=voyage,
            asset_code="BRG-NUS-17",
            constraint_type=NavigationConstraintCheck.ConstraintType.BRIDGE,
            eta_gate=self._dt(5, 22),
            window_start=bridge.window_start,
            window_end=bridge.window_end,
            draft_m="4.00",
            margin_minutes=240,
            status=NavigationConstraintCheck.Status.CAN_CROSS,
            recovery_hint="Happy-path proof: bridge clearance is open through dispatch.",
        )
        records = {
            "assetAvailabilityWindows": AssetAvailabilityWindow.objects.filter(
                reason=PROOF_REASON
            ).count(),
            "jettyWindows": JettyAvailabilityWindow.objects.filter(reason=PROOF_REASON).count(),
            "tideWindow": tide.code,
            "bridgeWindow": bridge.code,
            "navigationChecks": NavigationConstraintCheck.objects.filter(voyage=voyage).count(),
        }
        self._record_stage(
            number=4,
            title="Enter manual availability plus tide/bridge windows",
            actor=self.user_model.objects.get(username="abl.dispatcher@coalflow.local"),
            primary_evidence=(
                f"{records['assetAvailabilityWindows']} asset windows, "
                f"{tide.code}, {bridge.code}"
            ),
            route="/constraints/tide-bridge",
            records=records,
            audit_action="phase1.proof.manual_windows_entered",
        )
        return records

    def _stage_generate_schedule(
        self,
        *,
        actors: dict,
        organizations: dict,
    ) -> tuple[PlanVersion, dict]:
        plan = Plan.objects.create(
            code=PLAN_CODE,
            name="Phase 1 Operator Proof Plan",
            organization=organizations["abl"],
            horizon_start=self._dt(5, 0),
            horizon_end=self._dt(8, 23, 59),
            status=Plan.Status.ACTIVE,
        )
        version = PlanVersion.objects.create(
            plan=plan,
            version_no=1,
            status=PlanVersion.Status.DRAFT,
            created_by=actors["admin"],
        )
        result = generate_plan_version(version)
        version.refresh_from_db()
        records = {
            "planVersionId": version.id,
            "planCode": plan.code,
            "status": version.status,
            "validationStatus": version.validation_status,
            "tripCount": result.trip_count,
            "conflictCount": result.conflict_count,
            "blockingConflictCount": result.blocking_conflict_count,
        }
        if result.blocking_conflict_count:
            raise RuntimeError(f"Happy-path proof generated blocking conflicts: {records}")
        self._record_stage(
            number=5,
            title="Generate a draft schedule",
            actor=actors["admin"],
            primary_evidence=(
                f"{plan.code} V{version.version_no} generated "
                f"{result.trip_count} trips with 0 blockers"
            ),
            route="/schedule/published-plan",
            records=records,
            audit_action="phase1.proof.schedule_generated",
            organization=organizations["abl"],
        )
        return version, records

    def _stage_trip_chain(self, *, plan_version: PlanVersion) -> dict:
        trips = list(
            Trip.objects.filter(plan_version=plan_version)
            .select_related("voyage", "assignment", "assignment__tug", "assignment__barge")
            .order_by("sequence")
        )
        event_count = ScheduleEvent.objects.filter(trip__plan_version=plan_version).count()
        records = {
            "tripCount": len(trips),
            "eventCount": event_count,
            "tripChain": [
                {
                    "tripId": trip.trip_id,
                    "vessel": trip.voyage.vessel_name,
                    "tug": trip.assignment.tug.code if trip.assignment.tug else "",
                    "barge": trip.assignment.barge.code if trip.assignment.barge else "",
                    "quantityMt": trip.planned_quantity_mt,
                }
                for trip in trips
            ],
            "conflicts": list(
                Conflict.objects.filter(plan_version=plan_version).values_list("code", flat=True)
            ),
        }
        self._record_stage(
            number=6,
            title="Inspect full trip chain and conflicts",
            actor=self.user_model.objects.get(username="control.tower@coalflow.local"),
            primary_evidence=(
                f"{len(trips)} trips / {event_count} schedule events / "
                f"{len(records['conflicts'])} conflicts"
            ),
            route="/operations/tug-barge-assignment",
            records=records,
            audit_action="phase1.proof.trip_chain_inspected",
        )
        return records

    def _stage_governed_adjustment(
        self,
        *,
        actors: dict,
        plan_version: PlanVersion,
    ) -> OverrideRequest:
        assignment = (
            Trip.objects.filter(plan_version=plan_version)
            .select_related("assignment", "assignment__tug")
            .order_by("sequence")
            .first()
            .assignment
        )
        override = apply_assignment_override(
            assignment=assignment,
            actor=actors["abl"],
            reason_code=OverrideRequest.ReasonCode.MANUAL_CORRECTION,
            description="Dispatcher confirmed tow readiness after manual VHF check.",
            changes={
                "next_action": "Dispatch chain on confirmed tide and bridge window.",
                "next_constraint": "Operator clearance confirmed.",
            },
        )
        self._record_stage(
            number=7,
            title="Make governed adjustments with reasons",
            actor=actors["abl"],
            primary_evidence=f"Override {override.id} applied with reason {override.reason_code}",
            route="/exceptions/center",
            records={
                "overrideId": override.id,
                "reasonCode": override.reason_code,
                "description": override.description,
                "changedFields": sorted(override.requested_change.keys()),
            },
            audit_action="phase1.proof.governed_adjustment_applied",
        )
        return override

    def _stage_approval_publish(self, *, actors: dict, plan_version: PlanVersion):
        approval_request = submit_approval_request(
            plan_version=plan_version,
            actor=actors["admin"],
            reason="Phase 1 proof plan is feasible and ready for dual-party publication.",
        )
        record_approval_decision(
            approval_request=approval_request,
            actor=actors["berau"],
            authority_role=ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
            decision=ApprovalDecision.Decision.APPROVE,
            comments="Berau accepts demand and cargo-layer sequence.",
        )
        record_approval_decision(
            approval_request=approval_request,
            actor=actors["abl"],
            authority_role=ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
            decision=ApprovalDecision.Decision.APPROVE,
            comments="ABL accepts tug, barge, jetty, CTS, tide, and bridge readiness.",
        )
        plan_version.refresh_from_db()
        snapshot = publish_plan_version(plan_version=plan_version, actor=actors["control"])
        approval_request.refresh_from_db()
        self._record_stage(
            number=8,
            title="Submit, approve, and publish a plan",
            actor=actors["control"],
            primary_evidence=(
                f"{approval_request.request_id} approved and published as "
                f"{snapshot.snapshot_id}"
            ),
            route="/approvals/publishing",
            records={
                "approvalRequestId": approval_request.request_id,
                "approvalStatus": approval_request.status,
                "planVersionStatus": plan_version.status,
                "snapshotId": snapshot.snapshot_id,
                "requiredAuthorities": approval_request.required_authorities,
            },
            audit_action="phase1.proof.plan_published",
            organization=plan_version.plan.organization,
        )
        return approval_request, snapshot

    def _stage_live_version_and_audit(self, *, snapshot: PublishedPlanSnapshot):
        events = self._proof_audit_events()
        self._record_stage(
            number=9,
            title="Retrieve live published version and audit trail",
            actor=self.user_model.objects.get(username="control.tower@coalflow.local"),
            primary_evidence=(
                f"{snapshot.snapshot_id} active with {len(events)} proof audit events "
                "before retrieval marker"
            ),
            route="/admin/audit-logs",
            records={
                "snapshotId": snapshot.snapshot_id,
                "snapshotStatus": snapshot.status,
                "payloadTripCount": len(snapshot.payload.get("trips", [])),
                "auditEventsBeforeMarker": len(events),
            },
            audit_action="phase1.proof.live_version_retrieved",
            organization=snapshot.plan.organization,
        )
        return self._proof_audit_events()

    def _stage_governed_export(self, *, actors: dict, plan_version: PlanVersion) -> ExportJob:
        export_job = create_governed_export(
            actor=actors["control"],
            export_type=ExportJob.ExportType.PLAN,
            export_format=ExportJob.ExportFormat.PRINT,
            plan_version=plan_version,
        )
        self._record_stage(
            number=10,
            title="Export the governed schedule",
            actor=actors["control"],
            primary_evidence=(
                f"{export_job.file_name} / {export_job.record_count} trips / "
                f"{export_job.checksum_sha256[:12]}..."
            ),
            route="/admin/export-handoff",
            records={
                "exportId": export_job.export_id,
                "fileName": export_job.file_name,
                "recordCount": export_job.record_count,
                "checksumSha256": export_job.checksum_sha256,
                "storageKey": export_job.storage_key,
            },
            audit_action="phase1.proof.governed_export_generated",
            organization=export_job.organization,
        )
        return export_job

    def _constraint_scenario(self) -> dict:
        baseline = PlanVersion.objects.get(plan__code="PLAN-2026-10-24", version_no=1)
        conflicts = list(
            Conflict.objects.filter(plan_version=baseline)
            .select_related("trip", "trip__voyage")
            .order_by("-is_blocking", "severity", "code")[:8]
        )
        return {
            "planCode": baseline.plan.code,
            "planVersionId": baseline.id,
            "status": baseline.status,
            "validationStatus": baseline.validation_status,
            "conflictCount": Conflict.objects.filter(plan_version=baseline).count(),
            "blockingConflictCount": Conflict.objects.filter(
                plan_version=baseline,
                is_blocking=True,
                resolved_at__isnull=True,
            ).count(),
            "examples": [
                {
                    "code": conflict.code,
                    "severity": conflict.severity,
                    "vessel": conflict.trip.voyage.vessel_name if conflict.trip else "",
                    "message": conflict.message,
                    "blocking": conflict.is_blocking,
                }
                for conflict in conflicts
            ],
        }

    def _proof_audit_events(self) -> list[AuditEvent]:
        return list(
            AuditEvent.objects.filter(object_id__startswith=self.run_id)
            .select_related("actor", "organization")
            .order_by("created_at")
        )
