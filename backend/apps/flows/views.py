from rest_framework.response import Response
from rest_framework.views import APIView

from apps.rbac.permissions import RequiresAccessPermission

from .models import FlowRun
from .serializers import ActiveFlowResponseSerializer, FlowEventCreateSerializer, FlowRunSerializer
from .services import FlowSubject, get_active_flow_run, record_cta_intent


class ActiveFlowView(APIView):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {"get": "schedule.view"}

    def get(self, request):
        subject = FlowSubject(
            subject_type=request.query_params.get("subject_type") or "",
            subject_id=request.query_params.get("subject_id") or "",
        )
        flow = get_active_flow_run(
            request.user,
            route=request.query_params.get("route"),
            subject=subject,
        )
        payload = {"flow": flow}
        return Response(ActiveFlowResponseSerializer(payload).data)


class FlowRunDetailView(APIView):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {"get": "schedule.view"}

    def get(self, request, run_id: str):
        flow = _flow_queryset().get(run_id=run_id)
        return Response(FlowRunSerializer(flow).data)


class FlowRunEventView(APIView):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {"post": "schedule.edit"}

    def post(self, request, run_id: str):
        flow = _flow_queryset().get(run_id=run_id)
        serializer = FlowEventCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        updated = record_cta_intent(
            flow,
            step_key=serializer.validated_data["step_key"],
            action_id=serializer.validated_data["action_id"],
            route=serializer.validated_data["route"],
            actor=request.user,
            object_type=serializer.validated_data.get("object_type") or "",
            object_id=serializer.validated_data.get("object_id") or "",
            metadata=serializer.validated_data.get("metadata") or {},
        )
        return Response(FlowRunSerializer(updated).data)


def _flow_queryset():
    return FlowRun.objects.select_related("flow_definition", "started_by").prefetch_related(
        "step_runs",
        "events",
        "events__actor",
    )
