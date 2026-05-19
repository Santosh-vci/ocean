from __future__ import annotations

import json
from datetime import datetime, time, timedelta
from decimal import Decimal
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.masters.models import Barge, CTSAsset, CoalGrade, Jetty, Location, RouteSegment
from apps.organizations.models import Organization
from apps.planning.models import (
    BridgeWindow,
    CargoLayerStep,
    CargoRequirement,
    ImportJob,
    NavigationConstraintCheck,
    OGVVoyage,
    TideWindow,
)
from apps.scheduling.models import Conflict, Plan, PlanVersion
from apps.scheduling.services import generate_plan_version


class Command(BaseCommand):
    help = (
        "Create a clean multi-OGV recovery practice case for Assist Super mode evidence."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-reset",
            action="store_true",
            help="Do not run the master-data-only reseed first.",
        )
        parser.add_argument(
            "--json",
            action="store_true",
            dest="json_output",
            help="Emit machine-readable JSON only.",
        )

    def handle(self, *args, **options):
        if not options["skip_reset"]:
            seed_stdout = StringIO()
            call_command("seed_phase0", master_data_only=True, stdout=seed_stdout)

        summary = self._build_practice_case()

        if options["json_output"]:
            self.stdout.write(json.dumps(summary, indent=2, sort_keys=True))
            return

        self.stdout.write(self.style.SUCCESS("Assistant recovery practice case seeded."))
        self.stdout.write(
            f"Demand: {summary['voyageCount']} OGV(s), "
            f"{summary['cargoLayerCount']} cargo layer(s)"
        )
        self.stdout.write(
            f"Plan: {summary['planVersion']} "
            f"({summary['planStatus']}/{summary['validationStatus']})"
        )
        self.stdout.write(
            f"Conflicts: {summary['conflictCount']} total, "
            f"{summary['blockingConflictCount']} blocking"
        )

    def _build_practice_case(self) -> dict:
        admin = get_user_model().objects.get(username="admin@coalflow.local")
        org = (
            admin.organization_memberships.filter(is_default=True, is_active=True)
            .select_related("organization")
            .first()
        )
        organization = (
            org.organization
            if org
            else Organization.objects.filter(slug="berau-coal").first()
            or Organization.objects.first()
        )
        anchorage = self._by_code(Location, "LOC-ANCHORAGE-SOUTH")
        route_segment = (
            RouteSegment.objects.filter(requires_tide_window=True).first()
            or RouteSegment.objects.filter(requires_bridge_window=True).first()
            or RouteSegment.objects.first()
        )

        with transaction.atomic():
            voyages = self._create_demand(
                organization=organization,
                anchorage=anchorage,
            )
            self._create_windows_and_checks(
                voyages=voyages,
                route_segment=route_segment,
            )
            ImportJob.objects.create(
                import_type=ImportJob.ImportType.OGV_DEMAND,
                filename="assistant-recovery-practice-demand.json",
                source="assistant-recovery-practice",
                status=ImportJob.Status.IMPORTED,
                total_rows=len(voyages),
                valid_rows=len(voyages),
                error_rows=0,
                errors=[],
                created_by=admin,
            )
            plan = Plan.objects.create(
                code=f"PLAN-RECOVERY-PRACTICE-{timezone.localdate():%Y%m%d}",
                name="Assist Super Recovery Practice",
                organization=organization,
                horizon_start=self._at(1, 0),
                horizon_end=self._at(8, 23, 59),
                status=Plan.Status.ACTIVE,
            )
            version = PlanVersion.objects.create(
                plan=plan,
                version_no=1,
                created_by=admin,
            )
            generation = generate_plan_version(version)
            version.refresh_from_db()

        conflicts = Conflict.objects.filter(plan_version=version)
        return {
            "planVersionId": version.id,
            "planVersion": str(version),
            "planStatus": version.status,
            "validationStatus": version.validation_status,
            "voyageCount": len(voyages),
            "cargoLayerCount": CargoLayerStep.objects.count(),
            "navigationCheckCount": NavigationConstraintCheck.objects.count(),
            "missedCheckCount": NavigationConstraintCheck.objects.filter(
                status=NavigationConstraintCheck.Status.MISSED,
            ).count(),
            "tripCount": generation.trip_count,
            "conflictCount": conflicts.count(),
            "blockingConflictCount": conflicts.filter(
                is_blocking=True,
                resolved_at__isnull=True,
            ).count(),
            "conflicts": list(
                conflicts.order_by("code", "id").values(
                    "code",
                    "severity",
                    "object_type",
                    "object_id",
                    "message",
                    "is_blocking",
                )
            ),
        }

    def _create_demand(self, *, organization, anchorage) -> list[OGVVoyage]:
        specs = [
            {
                "voyage_id": "VOY-REC-001",
                "vessel_name": "MV Delta Recovery",
                "customer": "Berau Energy",
                "eta": self._at(1, 6),
                "required_mt": 92000,
                "priority": 1,
                "layers": [
                    ("EBONY", 46000, "LOC-SAMBARATA-PORT", "JTY-SUARAN", "BRG-VAL-08", "CTS-BORNEO", 1, self._at(1, 6), self._at(1, 16)),
                    ("AGATHIS", 46000, "LOC-LATI-PORT", "JTY-LATI", "BRG-NUS-17", "CTS-JAVA", 2, self._at(1, 17), self._at(2, 3)),
                ],
            },
            {
                "voyage_id": "VOY-REC-002",
                "vessel_name": "MV Kapuas Shift",
                "customer": "ABL Logistics",
                "eta": self._at(1, 9),
                "required_mt": 76000,
                "priority": 2,
                "layers": [
                    ("MAHONI", 38000, "LOC-SUARAN-PORT", "JTY-SUARAN", "BRG-KAL-22", "CTS-BORNEO", 1, self._at(1, 9), self._at(1, 19)),
                    ("EBONY", 38000, "LOC-SAMBARATA-PORT", "JTY-SUARAN", "BRG-VAL-08", "CTS-BORNEO", 2, self._at(2, 4), self._at(2, 14)),
                ],
            },
            {
                "voyage_id": "VOY-REC-003",
                "vessel_name": "MV Mahakam Light",
                "customer": "Pilot Customer",
                "eta": self._at(2, 5),
                "required_mt": 62000,
                "priority": 3,
                "layers": [
                    ("SUNGKAI", 31000, "LOC-LATI-PORT", "JTY-LATI", "BRG-NUS-17", "CTS-JAVA", 1, self._at(2, 5), self._at(2, 15)),
                    ("AGATHIS", 31000, "LOC-LATI-PORT", "JTY-LATI", "BRG-NUS-17", "CTS-JAVA", 2, self._at(2, 16), self._at(3, 2)),
                ],
            },
        ]
        voyages: list[OGVVoyage] = []
        for spec in specs:
            voyage = OGVVoyage.objects.create(
                voyage_id=spec["voyage_id"],
                vessel_name=spec["vessel_name"],
                customer_name=spec["customer"],
                vessel_class="Panamax",
                eta=spec["eta"],
                laycan_start=self._at(1, 0),
                laycan_end=self._at(5, 23),
                required_mt=spec["required_mt"],
                loaded_mt=0,
                in_transit_mt=0,
                discharged_mt=0,
                priority=spec["priority"],
                demurrage_rate_usd_per_day=Decimal("42000.00"),
                anchorage_location=anchorage,
                organization=organization,
                status=OGVVoyage.Status.AT_RISK,
                risk_status=OGVVoyage.RiskStatus.HIGH,
                current_stage="RECOVERY_PRACTICE",
                next_blocking_constraint="Tide/bridge miss requires recovery simulation",
            )
            for grade_code, qty, source_code, jetty_code, barge_code, cts_code, sequence, start, end in spec["layers"]:
                self._create_layer(
                    voyage=voyage,
                    grade_code=grade_code,
                    quantity=qty,
                    source_code=source_code,
                    jetty_code=jetty_code,
                    barge_code=barge_code,
                    cts_code=cts_code,
                    sequence=sequence,
                    planned_start=start,
                    planned_end=end,
                )
            voyages.append(voyage)
        return voyages

    def _create_layer(
        self,
        *,
        voyage,
        grade_code: str,
        quantity: int,
        source_code: str,
        jetty_code: str,
        barge_code: str,
        cts_code: str,
        sequence: int,
        planned_start,
        planned_end,
    ) -> None:
        grade = self._by_code(CoalGrade, grade_code)
        source = self._by_code(Location, source_code)
        jetty = self._by_code(Jetty, jetty_code)
        barge = self._by_code(Barge, barge_code)
        cts = self._by_code(CTSAsset, cts_code)
        requirement = CargoRequirement.objects.create(
            voyage=voyage,
            coal_grade=grade,
            source_location=source,
            preferred_jetty=jetty,
            required_mt=quantity,
            loaded_mt=0,
            in_transit_mt=0,
            discharged_mt=0,
            status=CargoRequirement.Status.PLANNED,
        )
        needs_recovery = sequence == 1 and voyage.voyage_id != "VOY-REC-003"
        CargoLayerStep.objects.create(
            voyage=voyage,
            cargo_requirement=requirement,
            hatch_no=sequence,
            layer_no=1,
            required_sequence_no=sequence,
            coal_grade=grade,
            required_mt=quantity,
            remaining_mt=quantity,
            planned_barge=barge,
            planned_jetty=jetty,
            planned_cts=cts,
            status=(
                CargoLayerStep.Status.BLOCKED
                if needs_recovery
                else CargoLayerStep.Status.PLANNED
            ),
            blocking_reason=(
                "Tide/bridge missed; recovery recommendation required"
                if needs_recovery
                else ""
            ),
            chain_status="WAITING RECOVERY" if needs_recovery else "PLANNED",
            planned_start=planned_start,
            planned_end=planned_end,
        )

    def _create_windows_and_checks(self, *, voyages, route_segment) -> None:
        tide_location = self._by_code(Location, "LOC-RANTAU-DELTA")
        bridge_location = self._by_code(Location, "LOC-BRIDGE-GATE-B")
        tide_window = TideWindow.objects.create(
            code="TIDE-REC-PRACTICE-01",
            location=tide_location,
            window_start=self._at(1, 5),
            window_end=self._at(1, 7),
            min_water_level_m=Decimal("2.45"),
            max_loaded_draft_m=Decimal("4.80"),
            applicable_route_segment=route_segment,
            risk_level=TideWindow.RiskLevel.TIGHT,
            source="assistant-recovery-practice",
            is_active=True,
        )
        tide_second = TideWindow.objects.create(
            code="TIDE-REC-PRACTICE-02",
            location=tide_location,
            window_start=self._at(2, 8),
            window_end=self._at(2, 11),
            min_water_level_m=Decimal("2.60"),
            max_loaded_draft_m=Decimal("4.80"),
            applicable_route_segment=route_segment,
            risk_level=TideWindow.RiskLevel.NORMAL,
            source="assistant-recovery-practice",
            is_active=True,
        )
        bridge_window = BridgeWindow.objects.create(
            code="BRDG-REC-PRACTICE-01",
            location=bridge_location,
            window_start=self._at(1, 7),
            window_end=self._at(1, 8),
            clearance_m=Decimal("13.00"),
            allowed_asset_class="300ft/330ft barge convoy",
            status=BridgeWindow.Status.RESTRICTED,
            notes="Recovery practice bridge slot.",
            is_active=True,
        )
        bridge_second = BridgeWindow.objects.create(
            code="BRDG-REC-PRACTICE-02",
            location=bridge_location,
            window_start=self._at(2, 9),
            window_end=self._at(2, 12),
            clearance_m=Decimal("13.20"),
            allowed_asset_class="300ft/330ft barge convoy",
            status=BridgeWindow.Status.OPEN,
            notes="Recovery practice open slot.",
            is_active=True,
        )

        checks = [
            (
                voyages[0],
                "BRG-VAL-08",
                NavigationConstraintCheck.ConstraintType.TIDE,
                self._at(1, 8),
                tide_window,
                -60,
                NavigationConstraintCheck.Status.MISSED,
                "Missed Rantau tide gate; generate recovery options before dispatch.",
            ),
            (
                voyages[1],
                "BRG-KAL-22",
                NavigationConstraintCheck.ConstraintType.BRIDGE,
                self._at(1, 9),
                bridge_window,
                -70,
                NavigationConstraintCheck.Status.MISSED,
                "Bridge gate missed; use recovery loop to resequence or shift window.",
            ),
            (
                voyages[2],
                "BRG-NUS-17",
                NavigationConstraintCheck.ConstraintType.TIDE,
                self._at(2, 10, 20),
                tide_second,
                40,
                NavigationConstraintCheck.Status.MARGINAL,
                "Marginal tide margin; monitor after recovery candidate is simulated.",
            ),
            (
                voyages[2],
                "BRG-NUS-17",
                NavigationConstraintCheck.ConstraintType.BRIDGE,
                self._at(2, 10),
                bridge_second,
                120,
                NavigationConstraintCheck.Status.CAN_CROSS,
                "Second-day bridge slot remains feasible.",
            ),
        ]
        for voyage, asset_code, constraint_type, eta, window, margin, status, hint in checks:
            NavigationConstraintCheck.objects.create(
                voyage=voyage,
                asset_code=asset_code,
                route_segment=route_segment,
                constraint_type=constraint_type,
                eta_gate=eta,
                window_start=window.window_start,
                window_end=window.window_end,
                draft_m=Decimal("4.20"),
                margin_minutes=margin,
                status=status,
                recovery_hint=hint,
            )

    def _by_code(self, model, code):
        obj = model.objects.filter(code=code).first()
        if obj is None:
            raise RuntimeError(f"Required master data not found: {model.__name__} {code}")
        return obj

    def _at(self, days_from_today: int, hour: int, minute: int = 0):
        target_date = timezone.localdate() + timedelta(days=days_from_today)
        return timezone.make_aware(datetime.combine(target_date, time(hour, minute)))
