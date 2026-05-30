from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.db.models import Q
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
        flow = get_object_or_404(_flow_queryset(request.user), run_id=run_id)
        return Response(FlowRunSerializer(flow).data)


class FlowRunEventView(APIView):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {"post": "schedule.edit"}

    def post(self, request, run_id: str):
        flow = get_object_or_404(_flow_queryset(request.user), run_id=run_id)
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


def _flow_queryset(user=None):
    queryset = FlowRun.objects.select_related("flow_definition", "started_by").prefetch_related(
        "step_runs",
        "events",
        "events__actor",
    )
    if user is None or getattr(user, "is_superuser", False):
        return queryset
    organization_ids = list(
        user.organization_memberships.filter(is_active=True).values_list(
            "organization_id",
            flat=True,
        )
    )
    organization_ids.extend(
        user.role_assignments.filter(is_active=True).values_list("organization_id", flat=True)
    )
    organization_ids = list(dict.fromkeys(organization_ids))
    if not organization_ids:
        return queryset.filter(started_by=user)
    return queryset.filter(
        Q(started_by=user)
        | Q(started_by__organization_memberships__organization_id__in=organization_ids)
        | Q(started_by__role_assignments__organization_id__in=organization_ids),
    ).distinct()
