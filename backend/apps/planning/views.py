from decimal import Decimal, InvalidOperation

from django.db import transaction
from django.db.models import Sum
from django.utils.dateparse import parse_datetime
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.audit.mixins import AuditMutationMixin
from apps.audit.services import record_audit_event
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
            job = ImportJob.objects.create(
                import_type=ImportJob.ImportType.OGV_DEMAND,
                filename=request.data.get("filename", "ogv-demand-upload.json"),
                source=request.data.get("source", "manual"),
                status=ImportJob.Status.FAILED if errors else ImportJob.Status.VALIDATED,
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
                },
                request=request,
            )

        response_status = status.HTTP_400_BAD_REQUEST if errors else status.HTTP_201_CREATED
        return Response(ImportJobSerializer(job).data, status=response_status)


class PlanningOverviewViewSet(PlanningViewSet):
    queryset = OGVVoyage.objects.none()
    serializer_class = OGVVoyageSerializer

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
