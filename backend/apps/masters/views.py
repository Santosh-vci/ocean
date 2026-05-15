from django.db import transaction
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.audit.mixins import AuditMutationMixin
from apps.audit.services import record_audit_event
from apps.rbac.permissions import RequiresAccessPermission

from .models import (
    AssetCompatibilityRule,
    Barge,
    CoalGrade,
    CTSAsset,
    Jetty,
    LoadingRateProfile,
    Location,
    Mine,
    Route,
    RouteSegment,
    Stockpile,
    Tug,
)
from .serializers import (
    AssetCompatibilityRuleSerializer,
    BargeSerializer,
    CoalGradeSerializer,
    CTSAssetSerializer,
    JettySerializer,
    LoadingRateProfileSerializer,
    LocationSerializer,
    MineSerializer,
    RouteSegmentSerializer,
    RouteSerializer,
    StockpileSerializer,
    TugSerializer,
)


class MasterDataViewSet(AuditMutationMixin, ModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "masterdata.view",
        "retrieve": "masterdata.view",
        "overview": "masterdata.view",
        "export": "masterdata.view",
        "import_records": "masterdata.manage",
        "create": "masterdata.manage",
        "update": "masterdata.manage",
        "partial_update": "masterdata.manage",
        "destroy": "masterdata.manage",
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

    @action(detail=False, methods=["post"], url_path="import")
    def import_records(self, request):
        records = request.data.get("records", request.data)
        if not isinstance(records, list):
            raise serializers.ValidationError({"records": "Expected a list of records."})

        created = 0
        updated = 0
        saved_instances = []
        with transaction.atomic():
            for index, row in enumerate(records):
                if not isinstance(row, dict):
                    raise serializers.ValidationError({str(index): "Expected an object record."})
                code = row.get("code")
                if not code:
                    raise serializers.ValidationError({str(index): "Missing required code."})
                instance = self.get_queryset().filter(code=code).first()
                serializer = self.get_serializer(
                    instance,
                    data=row,
                    partial=instance is not None,
                )
                serializer.is_valid(raise_exception=True)
                saved_instances.append(serializer.save())
                if instance is None:
                    created += 1
                else:
                    updated += 1

        model_name = self.queryset.model._meta.model_name
        record_audit_event(
            actor=request.user,
            organization=(
                getattr(saved_instances[0], "organization", None) if saved_instances else None
            ),
            action=f"{model_name}.import",
            object_type=model_name,
            object_id="bulk",
            object_repr=f"{created} created / {updated} updated",
            metadata={"created": created, "updated": updated, "count": len(records)},
            request=request,
        )
        return Response(
            {"created": created, "updated": updated, "count": len(records)},
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance):
        if not hasattr(instance, "is_active"):
            return super().perform_destroy(instance)

        instance.is_active = False
        instance.save(update_fields=["is_active", "updated_at"])
        record_audit_event(
            actor=self.request.user,
            organization=getattr(instance, "organization", None),
            action=f"{self._audit_object_type(instance)}.deactivate",
            object_type=self._audit_object_type(instance),
            object_id=str(instance.pk),
            object_repr=str(instance),
            metadata={"changes": {"is_active": False}},
            request=self.request,
        )


class LocationViewSet(MasterDataViewSet):
    queryset = Location.objects.select_related("organization").all()
    serializer_class = LocationSerializer


class CoalGradeViewSet(MasterDataViewSet):
    queryset = CoalGrade.objects.select_related("organization").all()
    serializer_class = CoalGradeSerializer


class MineViewSet(MasterDataViewSet):
    queryset = Mine.objects.select_related("organization").all()
    serializer_class = MineSerializer


class StockpileViewSet(MasterDataViewSet):
    queryset = Stockpile.objects.select_related("organization", "mine", "coal_grade").all()
    serializer_class = StockpileSerializer


class JettyViewSet(MasterDataViewSet):
    queryset = Jetty.objects.select_related("organization").all()
    serializer_class = JettySerializer


class TugViewSet(MasterDataViewSet):
    queryset = Tug.objects.select_related("organization").all()
    serializer_class = TugSerializer


class BargeViewSet(MasterDataViewSet):
    queryset = Barge.objects.select_related("organization").all()
    serializer_class = BargeSerializer


class CTSAssetViewSet(MasterDataViewSet):
    queryset = CTSAsset.objects.select_related("organization").all()
    serializer_class = CTSAssetSerializer


class RouteViewSet(MasterDataViewSet):
    queryset = Route.objects.select_related("organization").prefetch_related("segments").all()
    serializer_class = RouteSerializer


class RouteSegmentViewSet(MasterDataViewSet):
    queryset = RouteSegment.objects.select_related("route").all()
    serializer_class = RouteSegmentSerializer
    audit_object_type = "route_segment"
    action_permission_map = {
        "list": "masterdata.view",
        "retrieve": "masterdata.view",
        "create": "masterdata.manage",
        "update": "masterdata.manage",
        "partial_update": "masterdata.manage",
        "destroy": "masterdata.manage",
    }


class LoadingRateProfileViewSet(MasterDataViewSet):
    queryset = LoadingRateProfile.objects.select_related("organization", "coal_grade").all()
    serializer_class = LoadingRateProfileSerializer


class AssetCompatibilityRuleViewSet(MasterDataViewSet):
    queryset = AssetCompatibilityRule.objects.select_related("organization").all()
    serializer_class = AssetCompatibilityRuleSerializer


class MasterDataOverviewViewSet(MasterDataViewSet):
    queryset = CoalGrade.objects.none()
    serializer_class = CoalGradeSerializer

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):
        catalogs = {
            "locations": LocationSerializer(
                Location.objects.select_related("organization"),
                many=True,
            ).data,
            "coalGrades": CoalGradeSerializer(
                CoalGrade.objects.select_related("organization"),
                many=True,
            ).data,
            "mines": MineSerializer(Mine.objects.select_related("organization"), many=True).data,
            "stockpiles": StockpileSerializer(
                Stockpile.objects.select_related("organization", "mine", "coal_grade"),
                many=True,
            ).data,
            "jetties": JettySerializer(
                Jetty.objects.select_related("organization"),
                many=True,
            ).data,
            "tugs": TugSerializer(Tug.objects.select_related("organization"), many=True).data,
            "barges": BargeSerializer(Barge.objects.select_related("organization"), many=True).data,
            "ctsAssets": CTSAssetSerializer(
                CTSAsset.objects.select_related("organization"),
                many=True,
            ).data,
            "routes": RouteSerializer(
                Route.objects.select_related("organization").prefetch_related("segments"),
                many=True,
            ).data,
            "loadingRateProfiles": LoadingRateProfileSerializer(
                LoadingRateProfile.objects.select_related("organization", "coal_grade"),
                many=True,
            ).data,
            "compatibilityRules": AssetCompatibilityRuleSerializer(
                AssetCompatibilityRule.objects.select_related("organization"),
                many=True,
            ).data,
        }
        validation = {
            "inactiveRecords": sum(
                1
                for records in catalogs.values()
                for record in records
                if record.get("is_active") is False
            ),
            "blockingRules": AssetCompatibilityRule.objects.filter(is_compatible=False).count(),
            "missingGpsDevices": Tug.objects.filter(gps_device_id="").count(),
        }
        return Response({"catalogs": catalogs, "validation": validation})
