from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet, ViewSet

from apps.audit.services import record_audit_event
from apps.rbac.permissions import RequiresAccessPermission

from .models import (
    ConfirmedOperationalEvent,
    DeviceEndpoint,
    DeviceHealthSnapshot,
    EdgeEventBatch,
    IntegrationFeed,
    OperationalActualization,
    OperationalEventCandidate,
)
from .replay import create_edge_event_batch, replay_edge_batch
from .serializers import (
    ConfirmedOperationalEventSerializer,
    DeviceEndpointSerializer,
    DeviceHealthIngestSerializer,
    DeviceHealthSnapshotSerializer,
    EdgeEventBatchReplaySerializer,
    EdgeEventBatchSerializer,
    IntegrationFeedSerializer,
    OperationalActualizationSerializer,
    OperationalEventCandidateSerializer,
    OperationalEventIngestSerializer,
)
from .services import (
    apply_confirmed_event,
    confirm_operational_event,
    ingest_device_health,
    ingest_operational_event,
    operations_health_summary,
    reject_operational_event,
    require_confirmation_authority,
)


class OperationsViewSet(ModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "operations.view",
        "retrieve": "operations.view",
        "create": "operations.ingest",
        "update": "operations.ingest",
        "partial_update": "operations.ingest",
        "destroy": "operations.ingest",
    }


class IntegrationFeedViewSet(OperationsViewSet):
    queryset = IntegrationFeed.objects.all()
    serializer_class = IntegrationFeedSerializer
    lookup_field = "feed_id"
    action_permission_map = {
        **OperationsViewSet.action_permission_map,
        "create": "operations.manage_feeds",
        "update": "operations.manage_feeds",
        "partial_update": "operations.manage_feeds",
        "destroy": "operations.manage_feeds",
    }


class DeviceEndpointViewSet(OperationsViewSet):
    queryset = DeviceEndpoint.objects.select_related("feed", "location", "geofence").all()
    serializer_class = DeviceEndpointSerializer
    lookup_field = "device_id"
    action_permission_map = {
        **OperationsViewSet.action_permission_map,
        "create": "operations.manage_feeds",
        "update": "operations.manage_feeds",
        "partial_update": "operations.manage_feeds",
        "destroy": "operations.manage_feeds",
    }


class DeviceHealthSnapshotViewSet(OperationsViewSet):
    queryset = DeviceHealthSnapshot.objects.select_related("device", "device__feed").all()
    serializer_class = DeviceHealthSnapshotSerializer
    action_permission_map = {
        **OperationsViewSet.action_permission_map,
        "ingest": "operations.ingest",
    }

    def create(self, request, *args, **kwargs):
        serializer = DeviceHealthIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = ingest_device_health(
            payload=serializer.validated_data,
            actor=request.user,
            request=request,
        )
        return Response(_health_ingest_response(result), status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["post"], url_path="ingest")
    def ingest(self, request):
        serializer = DeviceHealthIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = ingest_device_health(
            payload=serializer.validated_data,
            actor=request.user,
            request=request,
        )
        return Response(_health_ingest_response(result), status=status.HTTP_201_CREATED)


class OperationalEventCandidateViewSet(OperationsViewSet):
    queryset = OperationalEventCandidate.objects.select_related(
        "feed",
        "device",
        "trip",
        "trip__plan_version",
        "assignment",
        "assignment__trip",
        "schedule_event",
    ).all()
    serializer_class = OperationalEventCandidateSerializer
    action_permission_map = {
        **OperationsViewSet.action_permission_map,
        "ingest": "operations.ingest",
        "confirm": "operations.view",
        "reject": "operations.view",
    }

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = ingest_operational_event(
            payload=serializer.validated_data,
            actor=request.user,
            request=request,
        )
        response_status = status.HTTP_200_OK if result.duplicate else status.HTTP_201_CREATED
        return Response(
            OperationalEventCandidateSerializer(result.candidate).data,
            status=response_status,
        )

    @action(detail=False, methods=["post"], url_path="ingest")
    def ingest(self, request):
        serializer = OperationalEventIngestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        result = ingest_operational_event(
            payload=serializer.validated_data,
            actor=request.user,
            request=request,
        )
        response_status = status.HTTP_200_OK if result.duplicate else status.HTTP_201_CREATED
        return Response(_ingest_response(result), status=response_status)

    @action(detail=True, methods=["post"], url_path="confirm")
    def confirm(self, request, pk=None):
        candidate = self.get_object()
        result = confirm_operational_event(
            candidate=candidate,
            actor=request.user,
            actual_at=request.data.get("actual_at") or None,
            confirmation_mode=request.data.get("confirmation_mode")
            or ConfirmedOperationalEvent.ConfirmationMode.MANUAL,
            reason_code=request.data.get("reason_code", ""),
            confirmed_quantity_mt=request.data.get("confirmed_quantity_mt"),
            confirmed_rate_tph=request.data.get("confirmed_rate_tph"),
            confirmed_grade_code=request.data.get("confirmed_grade_code", ""),
            metadata=request.data.get("metadata") or {},
            request=request,
        )
        response_status = status.HTTP_201_CREATED if result.created else status.HTTP_200_OK
        return Response(
            ConfirmedOperationalEventSerializer(result.event).data,
            status=response_status,
        )

    @action(detail=True, methods=["post"], url_path="reject")
    def reject(self, request, pk=None):
        candidate = self.get_object()
        candidate = reject_operational_event(
            candidate=candidate,
            actor=request.user,
            reason_code=request.data.get("reason_code", "manual_reject"),
            notes=request.data.get("notes", ""),
            request=request,
        )
        return Response(OperationalEventCandidateSerializer(candidate).data)


class ConfirmedOperationalEventViewSet(OperationsViewSet):
    queryset = ConfirmedOperationalEvent.objects.select_related(
        "candidate",
        "plan_version",
        "trip",
        "assignment",
        "schedule_event",
        "confirmed_by",
    ).all()
    serializer_class = ConfirmedOperationalEventSerializer
    action_permission_map = {
        **OperationsViewSet.action_permission_map,
        "create": "operations.view",
        "update": "operations.manage_feeds",
        "partial_update": "operations.manage_feeds",
        "destroy": "operations.manage_feeds",
    }

    def perform_create(self, serializer):
        event_kind = serializer.validated_data["event_kind"]
        require_confirmation_authority(self.request.user, event_kind)
        event = serializer.save(confirmed_by=self.request.user)
        if event.candidate_id:
            event.candidate.status = OperationalEventCandidate.Status.CONFIRMED
            event.candidate.save(update_fields=["status", "updated_at"])
        actualization_summary = apply_confirmed_event(event=event)
        event.after_state = {
            **event.after_state,
            "actualization": actualization_summary,
        }
        event.save(update_fields=["after_state"])
        record_audit_event(
            actor=self.request.user,
            organization=event.plan_version.plan.organization if event.plan_version_id else None,
            action="operational_event.created",
            object_type="confirmed_operational_event",
            object_id=str(event.pk),
            object_repr=event.event_id,
            metadata={"event_kind": event.event_kind, "actual_at": event.actual_at.isoformat()},
            request=self.request,
        )


class OperationalActualizationViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "operations.view",
        "retrieve": "operations.view",
    }
    queryset = OperationalActualization.objects.select_related("confirmed_event").all()
    serializer_class = OperationalActualizationSerializer


class EdgeEventBatchViewSet(OperationsViewSet):
    queryset = EdgeEventBatch.objects.select_related("feed", "device").all()
    serializer_class = EdgeEventBatchSerializer
    action_permission_map = {
        **OperationsViewSet.action_permission_map,
        "create": "operations.replay",
        "replay": "operations.replay",
        "update": "operations.replay",
        "partial_update": "operations.replay",
        "destroy": "operations.replay",
    }

    @action(detail=False, methods=["post"], url_path="replay")
    def replay(self, request):
        serializer = EdgeEventBatchReplaySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        payload = serializer.validated_data
        if payload.get("batch_id"):
            batch = EdgeEventBatch.objects.get(batch_id=payload["batch_id"])
            created = False
        else:
            creation = create_edge_event_batch(payload=payload)
            batch = creation.batch
            created = creation.created
        result = replay_edge_batch(
            batch=batch,
            actor=request.user,
            request=request,
        )
        return Response(
            {
                "batch": EdgeEventBatchSerializer(result.batch).data,
                "created": created,
                "idempotent": result.idempotent,
                "summary": result.summary,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )


class OperationsOverviewViewSet(ViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {"list": "operations.view"}

    def list(self, request):
        health_summary = operations_health_summary()
        return Response(
            {
                "feeds": {
                    "total": IntegrationFeed.objects.count(),
                    "active": IntegrationFeed.objects.filter(
                        status=IntegrationFeed.Status.ACTIVE
                    ).count(),
                    "degraded": IntegrationFeed.objects.filter(
                        status=IntegrationFeed.Status.DEGRADED
                    ).count(),
                },
                "devices": {
                    "total": DeviceEndpoint.objects.count(),
                    "active": DeviceEndpoint.objects.filter(
                        status=DeviceEndpoint.Status.ACTIVE
                    ).count(),
                    "offline": DeviceEndpoint.objects.filter(
                        status=DeviceEndpoint.Status.OFFLINE
                    ).count(),
                },
                "candidates": {
                    "pending": OperationalEventCandidate.objects.filter(
                        status=OperationalEventCandidate.Status.PENDING
                    ).count(),
                    "confirmed": OperationalEventCandidate.objects.filter(
                        status__in=[
                            OperationalEventCandidate.Status.CONFIRMED,
                            OperationalEventCandidate.Status.AUTO_CONFIRMED,
                        ]
                    ).count(),
                    "rejected": OperationalEventCandidate.objects.filter(
                        status=OperationalEventCandidate.Status.REJECTED
                    ).count(),
                    "duplicates": OperationalEventCandidate.objects.filter(
                        status=OperationalEventCandidate.Status.DUPLICATE
                    ).count(),
                },
                "confirmedEvents": ConfirmedOperationalEvent.objects.count(),
                "actualizations": OperationalActualization.objects.count(),
                "edgeBatches": EdgeEventBatch.objects.count(),
                "health": health_summary,
            }
        )


def _ingest_response(result):
    return {
        "candidate": OperationalEventCandidateSerializer(result.candidate).data,
        "confirmed_event": (
            ConfirmedOperationalEventSerializer(result.confirmed_event).data
            if result.confirmed_event
            else None
        ),
        "created": result.created,
        "duplicate": result.duplicate,
        "auto_confirmed": result.auto_confirmed,
        "trust_evaluation": result.trust_evaluation,
    }


def _health_ingest_response(result):
    return {
        "snapshot": DeviceHealthSnapshotSerializer(result.snapshot).data,
        "device": DeviceEndpointSerializer(result.device).data,
        "feed": IntegrationFeedSerializer(result.feed).data,
        "candidate": (
            OperationalEventCandidateSerializer(result.candidate).data
            if result.candidate
            else None
        ),
        "created_risk": result.created_risk,
        "health_summary": result.health_summary,
    }
