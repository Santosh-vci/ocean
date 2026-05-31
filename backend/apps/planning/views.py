from datetime import datetime, time, timedelta
from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Q, Sum
from django.utils import timezone
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.audit.mixins import AuditMutationMixin
from apps.audit.services import record_audit_event
from apps.masters.models import Barge, CoalGrade, CTSAsset, Jetty, Location, RouteSegment, Tug
from apps.organizations.models import Organization
from apps.rbac.permissions import RequiresAccessPermission
from apps.scheduling.models import (
    PlanVersion,
    ScenarioConstraintEvaluation,
    ScenarioRun,
    SimulationScenario,
)

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
from .trial_pack import (
    operator_happy_path_demand_rows,
    operator_trial_demand_rows,
    trial_dt,
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

    @action(detail=False, methods=["post"], url_path="import-trial-demand")
    def import_trial_demand(self, request):
        pack = request.data.get("pack") or "operator_trial_phase5"
        if pack == "operator_happy_path_v1":
            rows = operator_happy_path_demand_rows()
        elif pack == "operator_trial_phase5":
            rows = operator_trial_demand_rows()
        else:
            raise serializers.ValidationError(
                {
                    "pack": (
                        "Unsupported trial pack. Use operator_happy_path_v1 "
                        "or operator_trial_phase5."
                    )
                }
            )
        with transaction.atomic():
            committed_voyages = self._commit_ogv_demand_rows(rows=rows, actor=request.user)
            job = ImportJob.objects.create(
                import_type=ImportJob.ImportType.OGV_DEMAND,
                filename=request.data.get("filename", "operator_trial_ogv_demand.xlsx"),
                source=request.data.get("source", pack),
                status=ImportJob.Status.IMPORTED,
                total_rows=len(rows),
                valid_rows=len(rows),
                error_rows=0,
                errors=[],
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
                    "trial_pack": pack,
                },
                request=request,
            )
        return Response(ImportJobSerializer(job).data, status=status.HTTP_201_CREATED)

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
        requirements_by_grade = self._commit_cargo_requirements(voyage=voyage, row=row)
        layer_rows = row.get("cargo_layers")
        if isinstance(layer_rows, list) and not layer_rows:
            return
        if not isinstance(layer_rows, list):
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
            requirement = requirements_by_grade.get(grade.code)
            if requirement is None:
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
                requirements_by_grade[grade.code] = requirement
            CargoLayerStep.objects.update_or_create(
                voyage=voyage,
                required_sequence_no=int(layer.get("required_sequence_no", index) or index),
                defaults={
                    "cargo_requirement": requirement,
                    "hatch_no": int(layer.get("hatch_no", index) or index),
                    "layer_no": int(layer.get("layer_no", 1) or 1),
                    "coal_grade": grade,
                    "required_mt": quantity,
                    "remaining_mt": int(Decimal(str(layer.get("remaining_mt", quantity)))),
                    "planned_barge": barge,
                    "planned_jetty": jetty,
                    "planned_cts": cts,
                    "status": layer.get("status") or CargoLayerStep.Status.PLANNED,
                    "blocking_reason": layer.get("blocking_reason", ""),
                    "chain_status": layer.get("chain_status", "IMPORTED"),
                    "sequence_violation": _truthy(layer.get("sequence_violation", False)),
                    "planned_start": _parsed_datetime(layer.get("planned_start")),
                    "planned_end": _parsed_datetime(layer.get("planned_end")),
                },
            )

    def _commit_cargo_requirements(self, *, voyage: OGVVoyage, row: dict) -> dict[str, CargoRequirement]:
        requirement_rows = row.get("cargo_requirements")
        requirements_by_grade: dict[str, CargoRequirement] = {}
        if not isinstance(requirement_rows, list):
            return requirements_by_grade

        for requirement_row in requirement_rows:
            grade = _object_by_code(CoalGrade, requirement_row.get("coal_grade_code"))
            if grade is None:
                raise serializers.ValidationError(
                    "At least one coal grade is required before import."
                )
            source = _object_by_code(Location, requirement_row.get("source_location_code"))
            jetty = (
                _object_by_code(Jetty, requirement_row.get("preferred_jetty_code"))
                or Jetty.objects.first()
            )
            requirement, _ = CargoRequirement.objects.update_or_create(
                voyage=voyage,
                coal_grade=grade,
                defaults={
                    "source_location": source,
                    "preferred_jetty": jetty,
                    "required_mt": int(Decimal(str(requirement_row.get("required_mt", 0)))),
                    "loaded_mt": int(Decimal(str(requirement_row.get("loaded_mt", 0) or 0))),
                    "in_transit_mt": int(
                        Decimal(str(requirement_row.get("in_transit_mt", 0) or 0))
                    ),
                    "discharged_mt": int(
                        Decimal(str(requirement_row.get("discharged_mt", 0) or 0))
                    ),
                    "status": requirement_row.get("status") or CargoRequirement.Status.PLANNED,
                },
            )
            requirements_by_grade[grade.code] = requirement
        return requirements_by_grade


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


def _next_operating_anchor():
    next_day = timezone.localdate() + timedelta(days=1)
    return timezone.make_aware(datetime.combine(next_day, time(6, 0)))


def _is_navigation_recovery_text(value: str | None) -> bool:
    text = (value or "").lower()
    return ("tide" in text or "bridge" in text) and (
        "miss" in text or "recovery" in text or "window" in text
    )


def _clear_resolved_navigation_recovery_state(voyages: list[OGVVoyage]) -> dict[str, int]:
    voyage_ids = [voyage.id for voyage in voyages]
    if not voyage_ids:
        return {"cargoLayers": 0, "voyages": 0}

    cleared_layers = 0
    layer_steps = CargoLayerStep.objects.filter(voyage_id__in=voyage_ids)
    for step in layer_steps:
        if step.sequence_violation:
            continue
        if not _is_navigation_recovery_text(f"{step.blocking_reason} {step.chain_status}"):
            continue
        if step.status != CargoLayerStep.Status.BLOCKED and not step.blocking_reason:
            continue
        step.status = CargoLayerStep.Status.PLANNED
        step.blocking_reason = ""
        step.chain_status = "PLANNED"
        step.save(update_fields=["status", "blocking_reason", "chain_status", "updated_at"])
        cleared_layers += 1

    cleared_voyages = 0
    refreshed_voyages = OGVVoyage.objects.filter(id__in=voyage_ids).prefetch_related(
        "layer_steps"
    )
    for voyage in refreshed_voyages:
        if not _is_navigation_recovery_text(voyage.next_blocking_constraint):
            continue
        has_layer_blocker = any(
            step.sequence_violation
            or step.status in {CargoLayerStep.Status.BLOCKED, CargoLayerStep.Status.QC_HOLD}
            or bool(step.blocking_reason)
            for step in voyage.layer_steps.all()
        )
        has_navigation_warning = NavigationConstraintCheck.objects.filter(
            voyage=voyage,
            status__in=[
                NavigationConstraintCheck.Status.MISSED,
                NavigationConstraintCheck.Status.MARGINAL,
            ],
        ).exists()
        if has_layer_blocker or has_navigation_warning:
            continue
        voyage.status = OGVVoyage.Status.PLANNED
        voyage.risk_status = OGVVoyage.RiskStatus.LOW
        voyage.next_blocking_constraint = ""
        voyage.save(
            update_fields=[
                "status",
                "risk_status",
                "next_blocking_constraint",
                "updated_at",
            ]
        )
        cleared_voyages += 1

    return {"cargoLayers": cleared_layers, "voyages": cleared_voyages}


def _mark_editable_plan_versions_stale(*, reason: str) -> int:
    stale_count = 0
    now = timezone.now().isoformat()
    for plan_version in PlanVersion.objects.filter(
        status__in=[
            PlanVersion.Status.DRAFT,
            PlanVersion.Status.GENERATED,
            PlanVersion.Status.VALIDATED,
            PlanVersion.Status.PROPOSED,
        ],
    ):
        summary = plan_version.summary if isinstance(plan_version.summary, dict) else {}
        plan_version.summary = {
            **summary,
            "sourceInputsChanged": True,
            "sourceInputChangeReason": reason,
            "sourceInputChangedAt": now,
        }
        plan_version.save(update_fields=["summary", "updated_at"])
        stale_count += 1
    return stale_count


def _latest_plan_version_has_recovery_origin() -> bool:
    latest_plan_version = PlanVersion.objects.order_by("-created_at").first()
    return bool(
        latest_plan_version
        and isinstance(latest_plan_version.summary, dict)
        and latest_plan_version.summary.get("recoveryOrigin")
    )


def _latest_blocked_recovery_plan_version() -> PlanVersion | None:
    latest_plan_version = PlanVersion.objects.order_by("-created_at", "-id").first()
    if latest_plan_version is None:
        return None
    if latest_plan_version.status not in {
        PlanVersion.Status.DRAFT,
        PlanVersion.Status.GENERATED,
        PlanVersion.Status.VALIDATED,
        PlanVersion.Status.PROPOSED,
    }:
        return None
    has_open_blocker = latest_plan_version.conflicts.filter(
        is_blocking=True,
        resolved_at__isnull=True,
    ).exists()
    if has_open_blocker:
        return latest_plan_version
    if isinstance(latest_plan_version.summary, dict) and latest_plan_version.summary.get(
        "recoveryOrigin",
    ):
        return latest_plan_version
    return None


def _restore_recovery_practice_assets() -> None:
    Barge.objects.filter(code="BRG-KAL-22").update(status=Barge.Status.AVAILABLE)
    Tug.objects.filter(code__in=["BER-TUG-04", "BER-TUG-08", "BER-TUG-09"]).update(
        status=Tug.Status.AVAILABLE,
    )
    CTSAsset.objects.filter(code__in=["CTS-BORNEO", "CTS-JAVA"]).update(is_available=True)


def _normalize_recovery_practice_inputs(*, voyages: list[OGVVoyage]) -> dict[str, int]:
    voyage_ids = [voyage.id for voyage in voyages]
    if not voyage_ids:
        return {
            "cargoLayerRows": 0,
            "assetAvailabilityRows": 0,
            "jettyWindowRows": 0,
            "tideWindowRows": 0,
            "bridgeWindowRows": 0,
        }
    cargo_layer_rows = CargoLayerStep.objects.filter(voyage_id__in=voyage_ids).update(
        status=CargoLayerStep.Status.PLANNED,
        sequence_violation=False,
        blocking_reason="",
        chain_status="RECOVERY CLEARED",
    )
    asset_rows = AssetAvailabilityWindow.objects.filter(
        reason__in=[
            "Planned maintenance at Dock 01",
            "Awaiting bridge pass",
            "Primary conveyor online",
            "Operator recovery repair: resource confirmed available.",
        ],
    ).exclude(
        status=AssetAvailabilityWindow.Status.AVAILABLE,
    ).update(
        status=AssetAvailabilityWindow.Status.AVAILABLE,
        reason="Operator recovery repair: resource confirmed available.",
    )
    jetty_rows = JettyAvailabilityWindow.objects.filter(
        Q(reason__in=[
            "Shift handover and conveyor inspection",
            "Silt clearance",
            "Operator recovery repair: jetty confirmed workable.",
        ])
        | Q(jetty__code__in=["JTY-SUARAN", "JTY-LATI", "JTY-GMB"])
    ).exclude(
        status=JettyAvailabilityWindow.Status.WORKING,
    ).update(
        status=JettyAvailabilityWindow.Status.WORKING,
        reason="Operator recovery repair: jetty confirmed workable.",
    )
    tide_rows = 0
    bridge_rows = 0
    for voyage in OGVVoyage.objects.filter(id__in=voyage_ids):
        voyage.status = OGVVoyage.Status.PLANNED
        voyage.risk_status = OGVVoyage.RiskStatus.LOW
        voyage.next_blocking_constraint = ""
        voyage.save(
            update_fields=[
                "status",
                "risk_status",
                "next_blocking_constraint",
                "updated_at",
            ],
        )
    return {
        "cargoLayerRows": cargo_layer_rows,
        "assetAvailabilityRows": asset_rows,
        "jettyWindowRows": jetty_rows,
        "tideWindowRows": tide_rows,
        "bridgeWindowRows": bridge_rows,
    }


def _ensure_recovery_closure_windows(
    *,
    plan_version: PlanVersion | None,
    locations: dict[str, Location],
) -> dict:
    bridge_location = (
        locations.get("LOC-BRIDGE-GATE-B")
        or Location.objects.filter(location_type=Location.LocationType.BRIDGE).first()
        or Location.objects.order_by("code").first()
    )
    tide_location = (
        locations.get("LOC-RANTAU-DELTA")
        or Location.objects.filter(location_type=Location.LocationType.TIDE_GATE).first()
        or bridge_location
    )
    if bridge_location is None or tide_location is None:
        return {}

    TideWindow.objects.filter(code__startswith="TIDE-OPERATOR-RECOVERY-").delete()
    BridgeWindow.objects.filter(code__startswith="BRDG-OPERATOR-RECOVERY-").delete()

    targets, source_run = _recovery_window_targets(plan_version)
    if not targets:
        return {
            "source": "scenario_critical_constraints",
            "sourceScenarioRun": source_run.run_id if source_run else "",
            "targetCount": 0,
            "tide": [],
            "bridge": [],
            "reason": "No scenario tide or bridge constraints are available.",
        }

    repair_windows = _merge_recovery_window_targets(targets)
    tide_codes = []
    bridge_codes = []
    for index, window in enumerate(repair_windows, start=1):
        if window["kind"] == "bridge":
            bridge, _ = BridgeWindow.objects.update_or_create(
                code=f"BRDG-OPERATOR-RECOVERY-{index:02d}",
                defaults={
                    "location": bridge_location,
                    "window_start": window["window_start"],
                    "window_end": window["window_end"],
                    "clearance_m": Decimal("12.50"),
                    "allowed_asset_class": "Recovered trial convoy",
                    "status": BridgeWindow.Status.OPEN,
                    "notes": (
                        "Operator recovery repair: targeted bridge slot for "
                        f"{window['target_count']} scenario constraint(s)."
                    ),
                    "is_active": True,
                },
            )
            bridge_codes.append(bridge.code)
            continue

        tide, _ = TideWindow.objects.update_or_create(
            code=f"TIDE-OPERATOR-RECOVERY-{index:02d}",
            defaults={
                "location": tide_location,
                "window_start": window["window_start"],
                "window_end": window["window_end"],
                "min_water_level_m": Decimal("2.90"),
                "max_loaded_draft_m": Decimal("4.80"),
                "applicable_route_segment": window.get("route_segment"),
                "risk_level": TideWindow.RiskLevel.NORMAL,
                "source": "operator-recovery-repair",
                "is_active": True,
            },
        )
        tide_codes.append(tide.code)

    return {
        "source": "scenario_critical_constraints",
        "sourceScenarioRun": source_run.run_id if source_run else "",
        "targetCount": len(targets),
        "repairWindowCount": len(repair_windows),
        "windowMinutes": 360,
        "tide": tide_codes,
        "bridge": bridge_codes,
    }


def _recovery_window_targets(
    plan_version: PlanVersion | None,
) -> tuple[list[dict], ScenarioRun | None]:
    run = _latest_recovery_scenario_run(plan_version)
    if run is None:
        return [], None

    targets = []
    evaluations = run.constraint_evaluations.filter(
        code__in=[
            "BRIDGE_WINDOW_MISSED",
            "BRIDGE_WINDOW_TIGHT",
            "BRIDGE_WINDOW_WAIT",
            "TIDE_WINDOW_MISSED",
            "TIDE_WINDOW_TIGHT",
            "TIDE_WINDOW_WAIT",
        ],
        severity__in=[
            ScenarioConstraintEvaluation.Severity.CRITICAL,
            ScenarioConstraintEvaluation.Severity.WARNING,
        ],
    ).select_related("trip", "trip__assignment", "trip__assignment__route_segment")
    for evaluation in evaluations:
        projected_at = _parsed_datetime(evaluation.projected_value.get("projectedAt"))
        if projected_at is None:
            continue
        trip = evaluation.trip
        assignment = getattr(trip, "assignment", None) if trip is not None else None
        route_segment = getattr(assignment, "route_segment", None)
        targets.append(
            {
                "kind": "tide" if evaluation.code.startswith("TIDE_") else "bridge",
                "projected_at": projected_at,
                "route_segment": route_segment if evaluation.code.startswith("TIDE_") else None,
                "evaluation_id": evaluation.evaluation_id,
            }
        )
    return targets, run


def _latest_recovery_scenario_run(plan_version: PlanVersion | None) -> ScenarioRun | None:
    if plan_version is None:
        return None
    scenario = (
        SimulationScenario.objects.filter(baseline_version=plan_version)
        .exclude(status=SimulationScenario.Status.CANCELED)
        .order_by("-updated_at", "-id")
        .first()
    )
    if scenario is None:
        return None
    return (
        scenario.runs.filter(status=ScenarioRun.Status.SUCCEEDED)
        .order_by("-completed_at", "-created_at", "-id")
        .first()
    )


def _merge_recovery_window_targets(targets: list[dict]) -> list[dict]:
    windows = []
    buffer_before = timedelta(minutes=90)
    buffer_after = timedelta(minutes=270)
    merge_gap = timedelta(minutes=30)
    ordered_targets = sorted(
        targets,
        key=lambda item: (
            item["kind"],
            getattr(item.get("route_segment"), "id", 0) or 0,
            item["projected_at"],
        ),
    )
    for target in ordered_targets:
        window_start = target["projected_at"] - buffer_before
        window_end = target["projected_at"] + buffer_after
        route_segment = target.get("route_segment")
        merge_key = (
            target["kind"],
            getattr(route_segment, "id", None),
        )
        if (
            windows
            and windows[-1]["merge_key"] == merge_key
            and window_start <= windows[-1]["window_end"] + merge_gap
        ):
            windows[-1]["window_end"] = max(windows[-1]["window_end"], window_end)
            windows[-1]["target_count"] += 1
            windows[-1]["evaluation_ids"].append(target["evaluation_id"])
            continue
        windows.append(
            {
                "kind": target["kind"],
                "route_segment": route_segment,
                "window_start": window_start,
                "window_end": window_end,
                "target_count": 1,
                "evaluation_ids": [target["evaluation_id"]],
                "merge_key": merge_key,
            }
        )
    return windows


class PlanningOverviewViewSet(PlanningViewSet):
    queryset = OGVVoyage.objects.none()
    serializer_class = OGVVoyageSerializer

    @action(detail=False, methods=["post"], url_path="enter-operating-windows")
    def enter_operating_windows(self, request):
        voyages = list(
            OGVVoyage.objects.prefetch_related("layer_steps", "layer_steps__planned_barge").all()
        )
        operator_voyages = [
            voyage
            for voyage in voyages
            if voyage.voyage_id.startswith("VOY-UI-")
            or voyage.vessel_name == "MV Operator UI Import"
        ]
        trial_voyages = [
            voyage for voyage in voyages if voyage.voyage_id.startswith("VOY-")
        ]
        trial_ids = {voyage.voyage_id for voyage in trial_voyages}
        if not operator_voyages and {
            "VOY-PACIFIC-PRIDE",
            "VOY-NORTH-STAR",
            "VOY-TRITON-STAR",
        }.issubset(trial_ids):
            return self._enter_trial_operating_windows(request=request, voyages=trial_voyages)

        target_voyages = operator_voyages or voyages
        earliest_eta = min((voyage.eta for voyage in target_voyages), default=None)
        operating_anchor = earliest_eta or _next_operating_anchor()
        tide_location = _object_by_code(Location, "LOC-RANTAU-DELTA") or Location.objects.first()
        bridge_location = _object_by_code(Location, "LOC-BRIDGE-GATE-B") or tide_location
        tide_route_segment = (
            RouteSegment.objects.filter(requires_tide_window=True).first()
            or RouteSegment.objects.filter(requires_bridge_window=True).first()
            or RouteSegment.objects.first()
        )
        bridge_route_segment = (
            RouteSegment.objects.filter(requires_bridge_window=True).first()
            or tide_route_segment
        )
        route_segment = (
            tide_route_segment
            or RouteSegment.objects.filter(requires_bridge_window=True).first()
            or RouteSegment.objects.first()
        )
        if tide_location is None or bridge_location is None:
            raise serializers.ValidationError("Location master data is required.")

        tide_specs = [
            (
                "TIDE-UI-OPERATING-01",
                operating_anchor - timedelta(hours=2),
                operating_anchor + timedelta(hours=1),
                Decimal("2.40"),
            ),
            (
                "TIDE-UI-OPERATING-02",
                operating_anchor + timedelta(hours=8),
                operating_anchor + timedelta(hours=11),
                Decimal("2.55"),
            ),
        ]
        bridge_specs = [
            (
                "BRDG-UI-OPERATING-01",
                operating_anchor - timedelta(hours=1),
                operating_anchor + timedelta(hours=2),
                Decimal("13.20"),
            ),
            (
                "BRDG-UI-OPERATING-02",
                operating_anchor + timedelta(hours=7),
                operating_anchor + timedelta(hours=10),
                Decimal("13.00"),
            ),
        ]
        operating_start = min(start for _, start, _, _ in [*tide_specs, *bridge_specs])
        operating_end = max(end for _, _, end, _ in [*tide_specs, *bridge_specs])

        AssetAvailabilityWindow.objects.filter(
            reason="Entered from operator UI planning run.",
        ).delete()
        JettyAvailabilityWindow.objects.filter(
            reason="Entered from operator UI planning run.",
        ).delete()
        TideWindow.objects.filter(source="operator-ui").exclude(
            code__in=[code for code, _, _, _ in tide_specs],
        ).delete()
        BridgeWindow.objects.filter(code__startswith="BRDG-UI-OPERATING-").exclude(
            code__in=[code for code, _, _, _ in bridge_specs],
        ).delete()

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
                window_start=operating_start,
                defaults={
                    "window_end": operating_end,
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
                window_start=operating_start,
                defaults={
                    "window_end": operating_end,
                    "status": JettyAvailabilityWindow.Status.WORKING,
                    "loading_rate_override_tph": jetty.loading_rate_tph,
                    "reason": "Entered from operator UI planning run.",
                },
            )
            jetty_windows += 1

        tide_windows = []
        for code, start, end, min_water_level in tide_specs:
            tide_window, _ = TideWindow.objects.update_or_create(
                code=code,
                defaults={
                    "location": tide_location,
                    "window_start": start,
                    "window_end": end,
                    "min_water_level_m": min_water_level,
                    "max_loaded_draft_m": Decimal("4.80"),
                    "applicable_route_segment": tide_route_segment,
                    "risk_level": TideWindow.RiskLevel.NORMAL,
                    "source": "operator-ui",
                    "is_active": True,
                },
            )
            tide_windows.append(tide_window)

        bridge_windows = []
        for code, start, end, clearance in bridge_specs:
            bridge_window, _ = BridgeWindow.objects.update_or_create(
                code=code,
                defaults={
                    "location": bridge_location,
                    "window_start": start,
                    "window_end": end,
                    "clearance_m": clearance,
                    "allowed_asset_class": "300ft/330ft barge convoy",
                    "status": BridgeWindow.Status.OPEN,
                    "notes": "Entered from operator UI planning run.",
                    "is_active": True,
                },
            )
            bridge_windows.append(bridge_window)

        recovery_plan_version = _latest_blocked_recovery_plan_version()
        is_recovery_window_repair = recovery_plan_version is not None
        if is_recovery_window_repair:
            _restore_recovery_practice_assets()
            NavigationConstraintCheck.objects.filter(voyage__in=target_voyages).delete()
        else:
            NavigationConstraintCheck.objects.filter(
                recovery_hint__in=[
                    "Open operator-entered tide window.",
                    "Open operator-entered bridge window.",
                ],
            ).delete()

        checks_created = 0
        movement_index = 0
        for voyage in target_voyages:
            layer_steps = sorted(
                voyage.layer_steps.all(),
                key=lambda step: step.required_sequence_no,
            )
            movement_steps = layer_steps or [None]
            for step in movement_steps:
                movement_index += 1
                asset_code = (
                    step.planned_barge.code
                    if step is not None and step.planned_barge is not None
                    else "BRG-VAL-08"
                )
                planned_start = (
                    step.planned_start
                    if step is not None and step.planned_start is not None
                    else voyage.eta
                )
                if movement_index % 2:
                    window = tide_windows[(movement_index - 1) % len(tide_windows)]
                    constraint_type = NavigationConstraintCheck.ConstraintType.TIDE
                    route_for_check = tide_route_segment
                    margin_minutes = 180
                    recovery_hint = "Open operator-entered tide window."
                else:
                    window = bridge_windows[(movement_index - 1) % len(bridge_windows)]
                    constraint_type = NavigationConstraintCheck.ConstraintType.BRIDGE
                    route_for_check = bridge_route_segment
                    margin_minutes = 210
                    recovery_hint = "Open operator-entered bridge window."
                NavigationConstraintCheck.objects.create(
                    voyage=voyage,
                    asset_code=asset_code,
                    route_segment=route_for_check,
                    constraint_type=constraint_type,
                    eta_gate=(planned_start or window.window_start) + timedelta(hours=1),
                    window_start=window.window_start,
                    window_end=window.window_end,
                    draft_m=Decimal("4.20"),
                    margin_minutes=margin_minutes,
                    status=NavigationConstraintCheck.Status.CAN_CROSS,
                    recovery_hint=recovery_hint,
                )
                checks_created += 1

        recovery_normalization = {}
        recovery_closure_windows = {}
        if is_recovery_window_repair:
            recovery_normalization = _normalize_recovery_practice_inputs(voyages=target_voyages)
            recovery_closure_windows = _ensure_recovery_closure_windows(
                plan_version=recovery_plan_version,
                locations={
                    getattr(tide_location, "code", ""): tide_location,
                    getattr(bridge_location, "code", ""): bridge_location,
                },
            )

        cleared_recovery_state = _clear_resolved_navigation_recovery_state(target_voyages)
        stale_plan_versions = _mark_editable_plan_versions_stale(
            reason="operating_windows_entered",
        )

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
                "tide_windows": [window.code for window in tide_windows],
                "bridge_windows": [window.code for window in bridge_windows],
                "constraint_checks": checks_created,
                "cleared_layer_blockers": cleared_recovery_state["cargoLayers"],
                "cleared_voyage_blockers": cleared_recovery_state["voyages"],
                "stale_plan_versions": stale_plan_versions,
                "recovery_repair": is_recovery_window_repair,
                "recovery_normalization": recovery_normalization,
                "recovery_closure_windows": recovery_closure_windows,
            },
            request=request,
        )
        return Response(
            {
                "assetWindows": asset_windows,
                "jettyWindows": jetty_windows,
                "tideWindow": tide_windows[0].code,
                "bridgeWindow": bridge_windows[0].code,
                "tideWindows": [window.code for window in tide_windows],
                "bridgeWindows": [window.code for window in bridge_windows],
                "constraintChecks": checks_created,
                "clearedLayerBlockers": cleared_recovery_state["cargoLayers"],
                "clearedVoyageBlockers": cleared_recovery_state["voyages"],
                "stalePlanVersions": stale_plan_versions,
                "recoveryRepair": is_recovery_window_repair,
                "recoveryNormalization": recovery_normalization,
                "recoveryClosureWindows": recovery_closure_windows,
            },
            status=status.HTTP_201_CREATED,
        )

    def _enter_trial_operating_windows(self, *, request, voyages):
        locations = {record.code: record for record in Location.objects.all()}
        jetties = {record.code: record for record in Jetty.objects.all()}
        segments = {
            record.sequence: record for record in RouteSegment.objects.select_related("route")
        }
        voyages_by_id = {voyage.voyage_id: voyage for voyage in voyages}

        AssetAvailabilityWindow.objects.filter(
            reason__in=[
                "Planned maintenance at Dock 01",
                "Awaiting bridge pass",
                "Primary conveyor online",
            ],
        ).delete()
        JettyAvailabilityWindow.objects.filter(
            reason__in=[
                "",
                "Shift handover and conveyor inspection",
                "Silt clearance",
            ],
        ).delete()
        TideWindow.objects.filter(source="operator-trial-practice").delete()
        BridgeWindow.objects.filter(code__startswith="BRDG-TRIAL-").delete()
        NavigationConstraintCheck.objects.filter(voyage__in=voyages).delete()

        asset_windows = 0
        for asset_type, asset_code, start, end, window_status, reason in [
            (
                AssetAvailabilityWindow.AssetType.TUG,
                "BER-TUG-04",
                trial_dt(0, 0),
                trial_dt(2, 8),
                AssetAvailabilityWindow.Status.MAINTENANCE,
                "Planned maintenance at Dock 01",
            ),
            (
                AssetAvailabilityWindow.AssetType.BARGE,
                "BRG-KAL-22",
                trial_dt(1, 0),
                trial_dt(1, 10),
                AssetAvailabilityWindow.Status.UNAVAILABLE,
                "Awaiting bridge pass",
            ),
            (
                AssetAvailabilityWindow.AssetType.CTS,
                "CTS-JAVA",
                trial_dt(0, 0),
                trial_dt(5, 0),
                AssetAvailabilityWindow.Status.AVAILABLE,
                "Primary conveyor online",
            ),
        ]:
            AssetAvailabilityWindow.objects.update_or_create(
                asset_type=asset_type,
                asset_code=asset_code,
                reason=reason,
                defaults={
                    "window_start": start,
                    "window_end": end,
                    "status": window_status,
                },
            )
            asset_windows += 1

        jetty_windows = 0
        for jetty_code, start, end, window_status, rate, reason in [
            ("JTY-SUARAN", trial_dt(0, 0), trial_dt(2, 0), JettyAvailabilityWindow.Status.WORKING, 2800, ""),
            (
                "JTY-LATI",
                trial_dt(0, 16),
                trial_dt(1, 7),
                JettyAvailabilityWindow.Status.REDUCED,
                1500,
                "Shift handover and conveyor inspection",
            ),
            (
                "JTY-GMB",
                trial_dt(1, 6),
                trial_dt(2, 6),
                JettyAvailabilityWindow.Status.BLOCKED,
                None,
                "Silt clearance",
            ),
        ]:
            jetty = jetties.get(jetty_code)
            if not jetty:
                continue
            JettyAvailabilityWindow.objects.update_or_create(
                jetty=jetty,
                reason=reason,
                defaults={
                    "window_start": start,
                    "window_end": end,
                    "status": window_status,
                    "loading_rate_override_tph": rate,
                },
            )
            jetty_windows += 1

        tide_windows = []
        for code, location, start, end, water_level, draft, segment, risk in [
            ("TIDE-TRIAL-RANTAU-01", "LOC-RANTAU-DELTA", trial_dt(0, 7), trial_dt(0, 12), "2.40", "4.40", 2, TideWindow.RiskLevel.NORMAL),
            ("TIDE-TRIAL-RANTAU-02", "LOC-RANTAU-DELTA", trial_dt(1, 8), trial_dt(1, 10), "2.10", "4.20", 2, TideWindow.RiskLevel.TIGHT),
            ("TIDE-TRIAL-DEEP-01", "LOC-MUARA-PANTAI", trial_dt(1, 18), trial_dt(1, 23), "2.90", "4.80", 3, TideWindow.RiskLevel.NORMAL),
        ]:
            tide_window, _ = TideWindow.objects.update_or_create(
                code=code,
                defaults={
                    "location": locations[location],
                    "window_start": start,
                    "window_end": end,
                    "min_water_level_m": Decimal(water_level),
                    "max_loaded_draft_m": Decimal(draft),
                    "applicable_route_segment": segments[segment],
                    "risk_level": risk,
                    "source": "operator-trial-practice",
                    "is_active": True,
                },
            )
            tide_windows.append(tide_window)

        bridge_windows = []
        for code, start, end, clearance, allowed_class, window_status, notes in [
            ("BRDG-TRIAL-GATE-B-01", trial_dt(0, 6), trial_dt(0, 9), "12.50", "300ft barge", BridgeWindow.Status.OPEN, "Normal lift slot"),
            ("BRDG-TRIAL-GATE-B-02", trial_dt(1, 4), trial_dt(1, 5), "10.80", "300ft barge", BridgeWindow.Status.RESTRICTED, "Pilot approval required"),
            ("BRDG-TRIAL-GATE-B-03", trial_dt(1, 9), trial_dt(1, 13), "0.00", "", BridgeWindow.Status.CLOSED, "Maintenance hold"),
        ]:
            bridge_window, _ = BridgeWindow.objects.update_or_create(
                code=code,
                defaults={
                    "location": locations["LOC-BRIDGE-GATE-B"],
                    "window_start": start,
                    "window_end": end,
                    "clearance_m": Decimal(clearance),
                    "allowed_asset_class": allowed_class,
                    "status": window_status,
                    "notes": notes,
                    "is_active": True,
                },
            )
            bridge_windows.append(bridge_window)

        recovery_plan_version = _latest_blocked_recovery_plan_version()
        is_recovery_window_repair = recovery_plan_version is not None
        if is_recovery_window_repair:
            _restore_recovery_practice_assets()

        checks_created = 0
        movement_checks = [
            ("VOY-PACIFIC-PRIDE", "BRG-VAL-08", 2, NavigationConstraintCheck.ConstraintType.TIDE, trial_dt(0, 8, 30), trial_dt(0, 7), trial_dt(0, 12), "4.10", 90, NavigationConstraintCheck.Status.CAN_CROSS, "Movement 01 EBONY can cross Rantau Delta on the current tide slot."),
            ("VOY-PACIFIC-PRIDE", "BRG-NUS-17", 1, NavigationConstraintCheck.ConstraintType.BRIDGE, trial_dt(1, 4, 20), trial_dt(1, 4), trial_dt(1, 5), "4.20", 40, NavigationConstraintCheck.Status.CAN_CROSS, "Movement 02 AGATHIS can use the restricted bridge slot with pilot clearance."),
            ("VOY-PACIFIC-PRIDE", "BRG-KAL-22", 2, NavigationConstraintCheck.ConstraintType.TIDE, trial_dt(1, 9, 30), trial_dt(1, 8), trial_dt(1, 10), "4.35", 30, NavigationConstraintCheck.Status.WAITING, "Movement 03 EBONY is waiting on the tight Rantau Delta tide slot."),
            ("VOY-NORTH-STAR", "BRG-NUS-17", 1, NavigationConstraintCheck.ConstraintType.BRIDGE, trial_dt(1, 9, 45), trial_dt(1, 4), trial_dt(1, 5), "4.00", -285, NavigationConstraintCheck.Status.MISSED, "Movement 04 SUNGKAI misses the bridge lift and needs governed recovery."),
            ("VOY-GOLDEN-ORIOLE", "BRG-KAL-22", 1, NavigationConstraintCheck.ConstraintType.BRIDGE, trial_dt(4, 6, 25), trial_dt(1, 4), trial_dt(1, 5), "4.40", 0, NavigationConstraintCheck.Status.WAITING, "Movement 05 MAHONI is awaiting a future bridge slot before dispatch."),
            ("VOY-TRITON-STAR", "BRG-VAL-08", 2, NavigationConstraintCheck.ConstraintType.TIDE, trial_dt(1, 8, 20), trial_dt(1, 8), trial_dt(1, 10), "4.30", 100, NavigationConstraintCheck.Status.CAN_CROSS, "Movement 06 EBONY can cross on the tight Rantau Delta tide slot."),
        ]
        for voyage_id, asset, segment, kind, eta, window_start, window_end, draft, margin, check_status, hint in movement_checks:
            voyage = voyages_by_id.get(voyage_id)
            if not voyage:
                continue
            if is_recovery_window_repair:
                check_status = NavigationConstraintCheck.Status.CAN_CROSS
                margin = max(abs(margin), 60)
                eta = window_start + ((window_end - window_start) / 2)
                hint = f"{hint} Cleared by operator-entered recovery window repair."
            NavigationConstraintCheck.objects.create(
                voyage=voyage,
                asset_code=asset,
                route_segment=segments[segment],
                constraint_type=kind,
                eta_gate=eta,
                window_start=window_start,
                window_end=window_end,
                draft_m=Decimal(draft),
                margin_minutes=margin,
                status=check_status,
                recovery_hint=hint,
            )
            checks_created += 1

        recovery_normalization = {}
        recovery_closure_windows = {}
        if is_recovery_window_repair:
            recovery_normalization = _normalize_recovery_practice_inputs(voyages=voyages)
            recovery_closure_windows = _ensure_recovery_closure_windows(
                plan_version=recovery_plan_version,
                locations=locations,
            )

        stale_plan_versions = _mark_editable_plan_versions_stale(
            reason="operator_trial_operating_windows_entered",
        )
        record_audit_event(
            actor=request.user,
            organization=None,
            action="planning.operating_windows.entered",
            object_type="planning_windows",
            object_id="operator-trial-practice",
            object_repr="Operator trial tide, bridge, and availability windows",
            metadata={
                "asset_windows": asset_windows,
                "jetty_windows": jetty_windows,
                "tide_windows": [window.code for window in tide_windows],
                "bridge_windows": [window.code for window in bridge_windows],
                "constraint_checks": checks_created,
                "stale_plan_versions": stale_plan_versions,
                "trial_pack": "operator_trial_phase5",
                "recovery_repair": is_recovery_window_repair,
                "recovery_normalization": recovery_normalization,
                "recovery_closure_windows": recovery_closure_windows,
            },
            request=request,
        )
        return Response(
            {
                "assetWindows": asset_windows,
                "jettyWindows": jetty_windows,
                "tideWindow": tide_windows[0].code,
                "bridgeWindow": bridge_windows[0].code,
                "tideWindows": [window.code for window in tide_windows],
                "bridgeWindows": [window.code for window in bridge_windows],
                "constraintChecks": checks_created,
                "clearedLayerBlockers": 0,
                "clearedVoyageBlockers": 0,
                "stalePlanVersions": stale_plan_versions,
                "recoveryRepair": is_recovery_window_repair,
                "recoveryNormalization": recovery_normalization,
                "recoveryClosureWindows": recovery_closure_windows,
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
