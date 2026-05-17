from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.rbac.permissions import RequiresAccessPermission

from .models import AssetIdentity, PositionPing, TelemetrySource
from .serializers import (
    AssetIdentitySerializer,
    PositionPingIngestResponseSerializer,
    PositionPingIngestSerializer,
    PositionPingSerializer,
    TelemetrySourceSerializer,
)
from .services import ingest_position_ping


class TelemetryViewSet(ModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "telemetry.view",
        "retrieve": "telemetry.view",
        "create": "telemetry.ingest",
        "update": "telemetry.ingest",
        "partial_update": "telemetry.ingest",
        "destroy": "telemetry.ingest",
    }


class TelemetrySourceViewSet(TelemetryViewSet):
    queryset = TelemetrySource.objects.all()
    serializer_class = TelemetrySourceSerializer
    lookup_field = "source_id"


class AssetIdentityViewSet(TelemetryViewSet):
    queryset = AssetIdentity.objects.select_related("source").all()
    serializer_class = AssetIdentitySerializer


class PositionPingViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "telemetry.view",
        "retrieve": "telemetry.view",
        "ingest": "telemetry.ingest",
    }
    queryset = PositionPing.objects.select_related("source", "asset_identity").all()
    serializer_class = PositionPingSerializer

    @action(detail=False, methods=["post"], url_path="ingest")
    def ingest(self, request):
        serializer = PositionPingIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = ingest_position_ping(payload=serializer.validated_data)
        response = PositionPingIngestResponseSerializer(result)
        return Response(response.data, status=status.HTTP_201_CREATED)
