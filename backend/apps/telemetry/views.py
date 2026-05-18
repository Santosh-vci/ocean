from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.rbac.permissions import RequiresAccessPermission

from .models import (
    AssetIdentity,
    GeofenceZone,
    LatestAssetState,
    LiveEtaProjection,
    MovementEvent,
    PositionPing,
    TelemetrySource,
    TrackingAlert,
)
from .serializers import (
    AssetIdentitySerializer,
    GeofenceZoneSerializer,
    LatestAssetStateSerializer,
    LiveEtaProjectionSerializer,
    MovementEventSerializer,
    PositionPingIngestResponseSerializer,
    PositionPingIngestSerializer,
    PositionPingSerializer,
    TelemetrySourceSerializer,
    TrackingAlertSerializer,
)
from .services import ingest_position_ping, refresh_signal_health


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


class LatestAssetStateViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "telemetry.view",
        "retrieve": "telemetry.view",
        "refresh_signal_health": "telemetry.ingest",
    }
    queryset = LatestAssetState.objects.select_related(
        "source",
        "asset_identity",
        "last_ping",
        "current_geofence",
        "last_movement_event",
    ).all()
    serializer_class = LatestAssetStateSerializer

    @action(detail=False, methods=["post"], url_path="refresh-signal-health")
    def refresh_signal_health(self, request):
        updated = refresh_signal_health()
        states = self.get_queryset()
        return Response(
            {
                "updated": updated,
                "states": LatestAssetStateSerializer(states, many=True).data,
            }
        )


class GeofenceZoneViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "telemetry.view",
        "retrieve": "telemetry.view",
    }
    queryset = GeofenceZone.objects.select_related("source_location").all()
    serializer_class = GeofenceZoneSerializer
    lookup_field = "zone_id"


class MovementEventViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "telemetry.view",
        "retrieve": "telemetry.view",
    }
    queryset = MovementEvent.objects.select_related(
        "source",
        "asset_identity",
        "position_ping",
        "geofence",
    ).all()
    serializer_class = MovementEventSerializer


class LiveEtaProjectionViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "telemetry.view",
        "retrieve": "telemetry.view",
    }
    queryset = LiveEtaProjection.objects.select_related(
        "source",
        "asset_identity",
        "trip",
        "trip__voyage",
        "schedule_event",
        "source_ping",
        "current_geofence",
    ).all()
    serializer_class = LiveEtaProjectionSerializer


class TrackingAlertViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "telemetry.view",
        "retrieve": "telemetry.view",
        "acknowledge": "telemetry.ingest",
    }
    queryset = TrackingAlert.objects.select_related(
        "source",
        "asset_identity",
        "source_ping",
        "trip",
        "trip__voyage",
        "schedule_event",
        "eta_projection",
        "created_scenario",
    ).all()
    serializer_class = TrackingAlertSerializer

    @action(detail=True, methods=["post"], url_path="acknowledge")
    def acknowledge(self, request, pk=None):
        alert = self.get_object()
        alert.status = TrackingAlert.Status.ACKNOWLEDGED
        alert.save(update_fields=["status", "updated_at"])
        return Response(TrackingAlertSerializer(alert).data)
