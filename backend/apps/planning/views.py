from datetime import timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.audit.mixins import AuditMutationMixin
from apps.audit.services import record_audit_event
from apps.masters.models import Barge, CoalGrade, CTSAsset, Jetty, Location, RouteSegment
from apps.organizations.models import Organization
from apps.rbac.permissions import RequiresAccessPermission

from .models import (
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
from .serializers import (
    AssetAvailabilityWindowSerializer,
    BridgeWindowSerializer,
    CargoLayerStepSerializer,
    CargoRequirementSerializer,
    ImportJobSerializer,
    JettyAvailabilityWindowSerializer,
    NavigationConstraintCheckSerializer,
    OGVVoyageSerializer,
    TideWindowSerializer,
)


class PlanningViewSet(AuditMutationMixin, ModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "schedule.view",
        "retrieve": "schedule.view",
        "overview": "schedule.view",
        "export": "schedule.view",
        "validate_ogv_demand": "schedule.edit",
        "enter_operating_windows": "schedule.edit",
        "create": "schedule.edit",
        "update": "schedule.edit",
        "partial_update": "schedule.edit",
        "destroy": "schedule.edit",
    }

    @action(detail=False, methods=["get"], url_path="export")
    def export(self, request):
        serializer = self.get_serializer(self.filter_queryset(self.get_queryset()), many=True)
        return Response(
            {
                "catalog": self.queryset.model._meta.model_name,
                "records": serializer.data,
                "recordCount": len(serializer.data),
            }
        )


class OGVVoyageViewSet(PlanningViewSet):
    queryset = OGVVoyage.objects.select_related("organization", "anchorage_location").all()
    serializer_class = OGVVoyageSerializer


class CargoRequirementViewSet(PlanningViewSet):
    queryset = CargoRequirement.objects.select_related(
        "voyage",
        "coal_grade",
        "source_location",
        "preferred_jetty",
    ).all()
    serializer_class = CargoRequirementSerializer


class CargoLayerStepViewSet(PlanningViewSet):
    queryset = CargoLayerStep.objects.select_related(
        "voyage",
        "cargo_requirement",
        "coal_grade",
        "planned_barge",
        "planned_jetty",
        "planned_cts",
    ).all()
    serializer_class = CargoLayerStepSerializer


class AssetAvailabilityWindowViewSet(PlanningViewSet):
    queryset = AssetAvailabilityWindow.objects.all()
    serializer_class = AssetAvailabilityWindowSerializer


class JettyAvailabilityWindowViewSet(PlanningViewSet):
    queryset = JettyAvailabilityWindow.objects.select_related("jetty", "jetty__organization").all()
    serializer_class = JettyAvailabilityWindowSerializer


class TideWindowViewSet(PlanningViewSet):
    queryset = TideWindow.objects.select_related(
        "location",
        "location__organization",
        "applicable_route_segment",
        "applicable_route_segment__route",
    ).all()
    serializer_class = TideWindowSerializer


class BridgeWindowViewSet(PlanningViewSet):
    queryset = BridgeWindow.objects.select_related("location", "location__organization").all()
    serializer_class = BridgeWindowSerializer


class NavigationConstraintCheckViewSet(PlanningViewSet):
    queryset = NavigationConstraintCheck.objects.select_related(
        "voyage",
        "route_segment",
        "route_segment__route",
    ).all()
    serializer_class = NavigationConstraintCheckSerializer


class ImportJobViewSet(PlanningViewSet):
    queryset = ImportJob.objects.select_related("created_by").all()
    serializer_class = ImportJobSerializer
    audit_object_type = "planning_import_job"

    @action(detail=False, methods=["post"], url_path="validate-ogv-demand")
    def validate_ogv_demand(self, request):
        rows = request.data.get("rows", [])
        if not isinstance(rows, list):
            raise serializers.ValidationError({"rows": "Expected a list of demand rows."})

        required_columns = [
            "voyage_id",
            "vessel_name",
            "customer_name",
            "laycan_start",
            "laycan_end",
            "eta",
            "required_mt",
        ]
        errors = []
        valid_rows = 0

        for index, row in enumerate(rows, start=1):
            if not isinstance(row, dict):
                errors.append({"row": index, "field": "row", "message": "Expected an object row."})
                continue

            row_errors = []
            for column in required_columns:
                if row.get(column) in (None, ""):
                    row_errors.append(
                        {
                            "row": index,
                            "field": column,
                            "message": "Required value missing.",
                        }
                    )

            for column in ("laycan_start", "laycan_end", "eta", "etb", "etc_target"):
                value = row.get(column)
                if value and parse_datetime(str(value)) is None:
                    row_errors.append(
                        {"row": index, "field": column, "message": "Invalid datetime."}
                    )

            quantity = row.get("required_mt")
            if quantity not in (None, ""):
                try:
                    if Decimal(str(quantity)) <= 0:
                        row_errors.append(
                            {
                                "row": index,
                                "field": "required_mt",
                                "message": "Required MT must be greater than zero.",
                            }
                        )
                except (InvalidOperation, ValueError):
                    row_errors.append(
                        {
                            "row": index,
                            "field": "required_mt",
                            "message": "Invalid number.",
                        }
                    )

            if row_errors:
                errors.extend(row_errors)
            else:
                valid_rows += 1

        with transaction.atomic():
            commit_rows = _truthy(request.data.get("commit", False)) and not errors
            committed_voyages = []
            if commit_rows:
                committed_voyages = self._commit_ogv_demand_rows(rows=rows, actor=request.user)
            job = ImportJob.objects.create(
                import_type=ImportJob.ImportType.OGV_DEMAND,
                filename=request.data.get("filename", "ogv-demand-upload.json"),
                source=request.data.get("source", "manual"),
                status=(
                    ImportJob.Status.FAILED
                    if errors
                    else ImportJob.Status.IMPORTED
                    if commit_rows
                    else ImportJob.Status.VALIDATED
                ),
                total_rows=len(rows),
                valid_rows=valid_rows,
                error_rows=len(rows) - valid_rows,
                errors=errors,
                created_by=request.user,
            )
            record_audit_event(
                actor=request.user,
                organization=None,
                action="planning_import_job.validate",
                object_type="planning_import_job",
                object_id=str(job.pk),
                object_repr=str(job),
                metadata={
                    "import_type": job.import_type,
                    "filename": job.filename,
                    "total_rows": job.total_rows,
                    "valid_rows": job.valid_rows,
                    "error_rows": job.error_rows,
                    "committed_voyages": committed_voyages,
                },
                request=request,
            )

        response_status = status.HTTP_400_BAD_REQUEST if errors else status.HTTP_201_CREATED
        return Response(ImportJobSerializer(job).data, status=response_status)

    def _commit_ogv_demand_rows(self, *, rows: list[dict], actor) -> list[str]:
        organization = (
            actor.organization_memberships.filter(is_default=True, is_active=True)
            .select_related("organization")
            .first()
        )
        owner = (
            organization.organization
            if organization
            else Organization.objects.filter(slug="berau-coal").first()
            or Organization.objects.first()
        )
        anchorage = _object_by_code(Location, "LOC-ANCHORAGE-SOUTH")
        committed_voyages = []

        for row in rows:
            required_mt = int(Decimal(str(row["required_mt"])))
            voyage, _ = OGVVoyage.objects.update_or_create(
                voyage_id=row["voyage_id"],
                defaults={
                    "vessel_name": row["vessel_name"],
                    "customer_name": row["customer_name"],
                    "vessel_class": row.get("vessel_class", "Panamax"),
                    "eta": _parsed_datetime(row["eta"]),
                    "etb": _parsed_datetime(row.get("etb")),
                    "etc_target": _parsed_datetime(row.get("etc_target")),
                    "laycan_start": _parsed_datetime(row["laycan_start"]),
                    "laycan_end": _parsed_datetime(row["laycan_end"]),
                    "required_mt": required_mt,
                    "loaded_mt": int(row.get("loaded_mt", 0) or 0),
                    "in_transit_mt": int(row.get("in_transit_mt", 0) or 0),
                    "discharged_mt": int(row.get("discharged_mt", 0) or 0),
                    "priority": int(row.get("priority", 2) or 2),
                    "demurrage_rate_usd_per_day": Decimal(
                        str(row.get("demurrage_rate_usd_per_day", "42000"))
                    ),
                    "anchorage_location": anchorage,
                    "organization": owner,
                    "status": OGVVoyage.Status.PLANNED,
                    "risk_status": OGVVoyage.RiskStatus.LOW,
                    "current_stage": row.get("current_stage", "IMPORTED"),
                    "next_blocking_constraint": row.get(
                        "next_blocking_constraint",
                        "Ready for scheduling",
                    ),
                },
            )
            committed_voyages.append(voyage.voyage_id)
            self._commit_cargo_layers(voyage=voyage, row=row, required_mt=required_mt)

        return committed_voyages

    def _commit_cargo_layers(self, *, voyage: OGVVoyage, row: dict, required_mt: int) -> None:
        layer_rows = row.get("cargo_layers")
        if not isinstance(layer_rows, list) or not layer_rows:
            first_quantity = required_mt // 2
            layer_rows = [
                {
                    "coal_grade_code": "EBONY",
                    "required_mt": first_quantity,
                    "hatch_no": 1,
                    "layer_no": 1,
                    "required_sequence_no": 1,
                    "source_location_code": "LOC-SAMBARATA-PORT",
                    "preferred_jetty_code": "JTY-SUARAN",
                    "planned_barge_code": "BRG-VAL-08",
                    "planned_cts_code": "CTS-BORNEO",
                },
                {
                    "coal_grade_code": "AGATHIS",
                    "required_mt": required_mt - first_quantity,
                    "hatch_no": 2,
                    "layer_no": 1,
                    "required_sequence_no": 2,
                    "source_location_code": "LOC-LATI-PORT",
                    "preferred_jetty_code": "JTY-LATI",
                    "planned_barge_code": "BRG-NUS-17",
                    "planned_cts_code": "CTS-JAVA",
                },
            ]

        for index, layer in enumerate(layer_rows, start=1):
            grade = (
                _object_by_code(CoalGrade, layer.get("coal_grade_code"))
                or CoalGrade.objects.first()
            )
            if grade is None:
                raise serializers.ValidationError(
                    "At least one coal grade is required before import."
                )
            source = _object_by_code(Location, layer.get("source_location_code"))
            jetty = (
                _object_by_code(Jetty, layer.get("preferred_jetty_code"))
                or Jetty.objects.first()
            )
            barge = _object_by_code(Barge, layer.get("planned_barge_code"))
            cts = _object_by_code(CTSAsset, layer.get("planned_cts_code"))
            quantity = int(Decimal(str(layer.get("required_mt", required_mt))))
            requirement, _ = CargoRequirement.objects.update_or_create(
                voyage=voyage,
                coal_grade=grade,
                defaults={
                    "source_location": source,
                    "preferred_jetty": jetty,
                    "required_mt": quantity,
                    "loaded_mt": 0,
                    "in_transit_mt": 0,
                    "discharged_mt": 0,
                    "status": CargoRequirement.Status.PLANNED,
                },
            )
            CargoLayerStep.objects.update_or_create(
                voyage=voyage,
                required_sequence_no=int(layer.get("required_sequence_no", index) or index),
                defaults={
                    "cargo_requirement": requirement,
                    "hatch_no": int(layer.get("hatch_no", index) or index),
                    "layer_no": int(layer.get("layer_no", 1) or 1),
                    "coal_grade": grade,
                    "required_mt": quantity,
                    "remaining_mt": quantity,
                    "planned_barge": barge,
                    "planned_jetty": jetty,
                    "planned_cts": cts,
                    "status": CargoLayerStep.Status.PLANNED,
                    "blocking_reason": "",
                    "chain_status": "IMPORTED",
                    "sequence_violation": False,
                    "planned_start": None,
                    "planned_end": None,
                },
            )


def _truthy(value) -> bool:
    return value in (True, "true", "True", "1", 1)


def _object_by_code(model, code):
    if not code:
        return None
    return model.objects.filter(code=code).first()


def _parsed_datetime(value):
    if not value:
        return None
    parsed = parse_datetime(str(value))
    if parsed is None:
        return None
    if timezone.is_naive(parsed):
        return timezone.make_aware(parsed)
    return parsed


class PlanningOverviewViewSet(PlanningViewSet):
    queryset = OGVVoyage.objects.none()
    serializer_class = OGVVoyageSerializer

    @action(detail=False, methods=["post"], url_path="enter-operating-windows")
    def enter_operating_windows(self, request):
        voyages = list(
            OGVVoyage.objects.prefetch_related("layer_steps", "layer_steps__planned_barge").all()
        )
        earliest_eta = min((voyage.eta for voyage in voyages), default=None)
        window_start = earliest_eta - timedelta(hours=6) if earliest_eta else _parsed_datetime(
            "2026-11-05T00:00:00Z"
        )
        window_end = window_start + timedelta(days=5)
        tide_location = _object_by_code(Location, "LOC-RANTAU-DELTA") or Location.objects.first()
        bridge_location = _object_by_code(Location, "LOC-BRIDGE-GATE-B") or tide_location
        route_segment = (
            RouteSegment.objects.filter(requires_tide_window=True).first()
            or RouteSegment.objects.filter(requires_bridge_window=True).first()
            or RouteSegment.objects.first()
        )
        if tide_location is None or bridge_location is None:
            raise serializers.ValidationError("Location master data is required.")

        asset_windows = 0
        for asset_type, asset_code in (
            (AssetAvailabilityWindow.AssetType.TUG, "BER-TUG-08"),
            (AssetAvailabilityWindow.AssetType.TUG, "BER-TUG-09"),
            (AssetAvailabilityWindow.AssetType.BARGE, "BRG-VAL-08"),
            (AssetAvailabilityWindow.AssetType.BARGE, "BRG-NUS-17"),
            (AssetAvailabilityWindow.AssetType.CTS, "CTS-BORNEO"),
            (AssetAvailabilityWindow.AssetType.CTS, "CTS-JAVA"),
        ):
            AssetAvailabilityWindow.objects.update_or_create(
                asset_type=asset_type,
                asset_code=asset_code,
                window_start=window_start,
                defaults={
                    "window_end": window_end,
                    "status": AssetAvailabilityWindow.Status.AVAILABLE,
                    "reason": "Entered from operator UI planning run.",
                },
            )
            asset_windows += 1

        jetty_windows = 0
        for jetty_code in ("JTY-SUARAN", "JTY-LATI"):
            jetty = _object_by_code(Jetty, jetty_code)
            if not jetty:
                continue
            JettyAvailabilityWindow.objects.update_or_create(
                jetty=jetty,
                window_start=window_start,
                defaults={
                    "window_end": window_end,
                    "status": JettyAvailabilityWindow.Status.WORKING,
                    "loading_rate_override_tph": jetty.loading_rate_tph,
                    "reason": "Entered from operator UI planning run.",
                },
            )
            jetty_windows += 1

        tide_window, _ = TideWindow.objects.update_or_create(
            code="TIDE-UI-OPERATING-01",
            defaults={
                "location": tide_location,
                "window_start": window_start,
                "window_end": window_end,
                "min_water_level_m": Decimal("2.40"),
                "max_loaded_draft_m": Decimal("4.80"),
                "applicable_route_segment": route_segment,
                "risk_level": TideWindow.RiskLevel.NORMAL,
                "source": "operator-ui",
                "is_active": True,
            },
        )
        bridge_window, _ = BridgeWindow.objects.update_or_create(
            code="BRDG-UI-OPERATING-01",
            defaults={
                "location": bridge_location,
                "window_start": window_start,
                "window_end": window_end,
                "clearance_m": Decimal("13.20"),
                "allowed_asset_class": "300ft/330ft barge convoy",
                "status": BridgeWindow.Status.OPEN,
                "notes": "Entered from operator UI planning run.",
                "is_active": True,
            },
        )

        checks_created = 0
        for voyage in voyages:
            layer_steps = sorted(
                voyage.layer_steps.all(),
                key=lambda step: step.required_sequence_no,
            )
            asset_codes = [
                step.planned_barge.code
                for step in layer_steps
                if step.planned_barge is not None
            ] or ["BRG-VAL-08"]
            for index, asset_code in enumerate(dict.fromkeys(asset_codes), start=1):
                eta_gate = voyage.eta + timedelta(hours=index * 2)
                NavigationConstraintCheck.objects.filter(
                    voyage=voyage,
                    asset_code=asset_code,
                    constraint_type__in=[
                        NavigationConstraintCheck.ConstraintType.TIDE,
                        NavigationConstraintCheck.ConstraintType.BRIDGE,
                    ],
                ).delete()
                NavigationConstraintCheck.objects.create(
                    voyage=voyage,
                    asset_code=asset_code,
                    route_segment=route_segment,
                    constraint_type=NavigationConstraintCheck.ConstraintType.TIDE,
                    eta_gate=eta_gate,
                    window_start=tide_window.window_start,
                    window_end=tide_window.window_end,
                    draft_m=Decimal("4.20"),
                    margin_minutes=180,
                    status=NavigationConstraintCheck.Status.CAN_CROSS,
                    recovery_hint="Open operator-entered tide window.",
                )
                NavigationConstraintCheck.objects.create(
                    voyage=voyage,
                    asset_code=asset_code,
                    route_segment=route_segment,
                    constraint_type=NavigationConstraintCheck.ConstraintType.BRIDGE,
                    eta_gate=eta_gate + timedelta(hours=1),
                    window_start=bridge_window.window_start,
                    window_end=bridge_window.window_end,
                    draft_m=Decimal("4.20"),
                    margin_minutes=210,
                    status=NavigationConstraintCheck.Status.CAN_CROSS,
                    recovery_hint="Open operator-entered bridge window.",
                )
                checks_created += 2

        record_audit_event(
            actor=request.user,
            organization=None,
            action="planning.operating_windows.entered",
            object_type="planning_windows",
            object_id="operator-ui",
            object_repr="Operator-entered Phase 1 operating windows",
            metadata={
                "asset_windows": asset_windows,
                "jetty_windows": jetty_windows,
                "tide_window": tide_window.code,
                "bridge_window": bridge_window.code,
                "constraint_checks": checks_created,
            },
            request=request,
        )
        return Response(
            {
                "assetWindows": asset_windows,
                "jettyWindows": jetty_windows,
                "tideWindow": tide_window.code,
                "bridgeWindow": bridge_window.code,
                "constraintChecks": checks_created,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):
        voyages = OGVVoyage.objects.select_related("organization", "anchorage_location").all()
        cargo_requirements = CargoRequirement.objects.select_related(
            "voyage",
            "coal_grade",
            "source_location",
            "preferred_jetty",
        ).all()
        layer_steps = CargoLayerStep.objects.select_related(
            "voyage",
            "cargo_requirement",
            "coal_grade",
            "planned_barge",
            "planned_jetty",
            "planned_cts",
        ).all()
        constraint_checks = NavigationConstraintCheck.objects.select_related(
            "voyage",
            "route_segment",
            "route_segment__route",
        ).all()
        aggregate = voyages.aggregate(required=Sum("required_mt"), remaining=Sum("required_mt"))
        loaded_mt = voyages.aggregate(loaded=Sum("loaded_mt"))["loaded"] or 0
        in_transit_mt = voyages.aggregate(in_transit=Sum("in_transit_mt"))["in_transit"] or 0
        discharged_mt = voyages.aggregate(discharged=Sum("discharged_mt"))["discharged"] or 0
        required_mt = aggregate["required"] or 0

        return Response(
            {
                "voyages": OGVVoyageSerializer(voyages, many=True).data,
                "cargoRequirements": CargoRequirementSerializer(cargo_requirements, many=True).data,
                "cargoLayerSteps": CargoLayerStepSerializer(layer_steps, many=True).data,
                "assetAvailability": AssetAvailabilityWindowSerializer(
                    AssetAvailabilityWindow.objects.all(),
                    many=True,
                ).data,
                "jettyAvailability": JettyAvailabilityWindowSerializer(
                    JettyAvailabilityWindow.objects.select_related("jetty", "jetty__organization"),
                    many=True,
                ).data,
                "tideWindows": TideWindowSerializer(
                    TideWindow.objects.select_related(
                        "location",
                        "location__organization",
                        "applicable_route_segment",
                        "applicable_route_segment__route",
                    ),
                    many=True,
                ).data,
                "bridgeWindows": BridgeWindowSerializer(
                    BridgeWindow.objects.select_related("location", "location__organization"),
                    many=True,
                ).data,
                "constraintChecks": NavigationConstraintCheckSerializer(
                    constraint_checks,
                    many=True,
                ).data,
                "importJobs": ImportJobSerializer(
                    ImportJob.objects.select_related("created_by")[:8],
                    many=True,
                ).data,
                "validation": {
                    "highRiskVoyages": voyages.filter(
                        risk_status__in=[
                            OGVVoyage.RiskStatus.HIGH,
                            OGVVoyage.RiskStatus.DEMURRAGE,
                        ],
                    ).count(),
                    "sequenceViolations": layer_steps.filter(sequence_violation=True).count(),
                    "missedWindows": constraint_checks.filter(
                        status=NavigationConstraintCheck.Status.MISSED,
                    ).count(),
                    "activeDemandMt": required_mt,
                    "remainingDemandMt": max(
                        required_mt - loaded_mt - in_transit_mt - discharged_mt,
                        0,
                    ),
                },
            }
        )
