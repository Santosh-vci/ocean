from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.audit.services import record_audit_event
from apps.rbac.permissions import RequiresAccessPermission
from apps.scheduling.serializers import SimulationScenarioSerializer

from .models import (
    AssetIdentity,
    GeofenceZone,
    LatestAssetState,
    LiveEtaProjection,
    MovementEvent,
    PositionPing,
    TelemetrySource,
    TelemetryReplayRun,
    TelemetryTrustAssessment,
    TelemetryTrustProfile,
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
    TelemetryReplayRunSerializer,
    TelemetrySourceSerializer,
    TelemetryTrustAssessSerializer,
    TelemetryTrustAssessmentSerializer,
    TelemetryTrustProfileSerializer,
    TrackingAlertSerializer,
)
from .replay import cancel_synthetic_replay, start_synthetic_replay
from .services import ingest_position_ping, refresh_signal_health
from .telemetry_trust_services import assess_telemetry_trust


def _bounded_list_limit(request, *, default: int = 120, maximum: int = 250) -> int:
    raw_limit = request.query_params.get("limit", default)
    try:
        limit = int(raw_limit)
    except (TypeError, ValueError):
        return default
    return max(1, min(limit, maximum))


class BoundedRecentListMixin:
    default_list_limit = 120
    max_list_limit = 250

    def get_queryset(self):
        queryset = super().get_queryset()
        if getattr(self, "action", None) != "list":
            return queryset
        return queryset[
            : _bounded_list_limit(
                self.request,
                default=self.default_list_limit,
                maximum=self.max_list_limit,
            )
        ]


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


class PositionPingViewSet(BoundedRecentListMixin, ReadOnlyModelViewSet):
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


class MovementEventViewSet(BoundedRecentListMixin, ReadOnlyModelViewSet):
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


class LiveEtaProjectionViewSet(BoundedRecentListMixin, ReadOnlyModelViewSet):
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


class TrackingAlertViewSet(BoundedRecentListMixin, ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "telemetry.view",
        "retrieve": "telemetry.view",
        "acknowledge": "telemetry.ingest",
        "convert_to_scenario": "schedule.edit",
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

    @action(detail=True, methods=["post"], url_path="convert-to-scenario")
    def convert_to_scenario(self, request, pk=None):
        alert = self.get_object()
        scenario = alert.convert_to_scenario(actor=request.user)
        record_audit_event(
            actor=request.user,
            organization=scenario.baseline_version.plan.organization,
            action="tracking_alert.convert_to_scenario",
            object_type="tracking_alert",
            object_id=str(alert.pk),
            object_repr=alert.alert_id,
            metadata={
                "tracking_alert_id": alert.pk,
                "tracking_alert_ref": alert.alert_id,
                "scenario_id": scenario.scenario_id,
                "trip": alert.trip.trip_id if alert.trip_id else None,
                "alert_type": alert.alert_type,
                "delay_minutes": alert.evidence.get("varianceMinutes"),
            },
            request=request,
        )
        return Response(
            SimulationScenarioSerializer(scenario).data,
            status=status.HTTP_201_CREATED,
        )


class TelemetryTrustProfileViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "telemetry.view",
        "retrieve": "telemetry.view",
    }
    queryset = TelemetryTrustProfile.objects.all()
    serializer_class = TelemetryTrustProfileSerializer
    lookup_field = "profile_key"


class TelemetryTrustAssessmentViewSet(BoundedRecentListMixin, ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "telemetry.view",
        "retrieve": "telemetry.view",
        "assess": "telemetry.view",
    }
    queryset = TelemetryTrustAssessment.objects.select_related(
        "profile",
        "source",
        "asset_identity",
        "latest_state",
    ).all()
    serializer_class = TelemetryTrustAssessmentSerializer

    @action(detail=False, methods=["post"], url_path="assess")
    def assess(self, request):
        serializer = TelemetryTrustAssessSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = assess_telemetry_trust(
            latest_state=serializer.validated_data.get("latest_state"),
            plan_version=serializer.validated_data.get("plan_version"),
            profile=serializer.validated_data.get("profile"),
            actor=request.user,
            persist=True,
        )
        if isinstance(result, list):
            return Response(
                TelemetryTrustAssessmentSerializer(result, many=True).data,
                status=status.HTTP_201_CREATED,
            )
        return Response(
            TelemetryTrustAssessmentSerializer(result).data,
            status=status.HTTP_201_CREATED,
        )


class TelemetryReplayRunViewSet(TelemetryViewSet):
    queryset = TelemetryReplayRun.objects.all()
    serializer_class = TelemetryReplayRunSerializer
    lookup_field = "replay_id"
    action_permission_map = {
        **TelemetryViewSet.action_permission_map,
        "start": "telemetry.ingest",
        "stop": "telemetry.ingest",
    }

    @action(detail=True, methods=["post"], url_path="start")
    def start(self, request, replay_id=None):
        replay_run = self.get_object()
        speed_multiplier = request.data.get("speed_multiplier")
        result = start_synthetic_replay(
            replay_run=replay_run,
            speed_multiplier=speed_multiplier,
        )
        return Response(TelemetryReplayRunSerializer(result["run"]).data)

    @action(detail=True, methods=["post"], url_path="stop")
    def stop(self, request, replay_id=None):
        replay_run = cancel_synthetic_replay(replay_run=self.get_object())
        return Response(TelemetryReplayRunSerializer(replay_run).data)
