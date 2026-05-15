from django.db.models import Count, Q, Sum
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from apps.audit.mixins import AuditMutationMixin
from apps.audit.services import record_audit_event
from apps.rbac.permissions import RequiresAccessPermission

from .models import Assignment, Conflict, Plan, PlanVersion, ScheduleEvent, Trip
from .serializers import (
    AssignmentSerializer,
    ConflictSerializer,
    PlanSerializer,
    PlanVersionSerializer,
    ScheduleEventSerializer,
    TripSerializer,
)
from .services import clone_plan_version, create_plan_version, generate_plan_version


class SchedulingViewSet(AuditMutationMixin, ModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "schedule.view",
        "retrieve": "schedule.view",
        "overview": "schedule.view",
        "create_version": "schedule.edit",
        "generate": "schedule.edit",
        "clone": "schedule.edit",
        "create": "schedule.edit",
        "update": "schedule.edit",
        "partial_update": "schedule.edit",
        "destroy": "schedule.edit",
    }


class PlanViewSet(SchedulingViewSet):
    queryset = Plan.objects.select_related("organization").all()
    serializer_class = PlanSerializer

    @action(detail=True, methods=["post"], url_path="create-version")
    def create_version(self, request, pk=None):
        plan = self.get_object()
        version = create_plan_version(plan=plan, created_by=request.user)
        record_audit_event(
            actor=request.user,
            organization=plan.organization,
            action="planversion.create",
            object_type="plan_version",
            object_id=str(version.pk),
            object_repr=str(version),
            metadata={"plan": plan.code, "version_no": version.version_no},
            request=request,
        )
        return Response(PlanVersionSerializer(version).data, status=status.HTTP_201_CREATED)


class PlanVersionViewSet(SchedulingViewSet):
    queryset = PlanVersion.objects.select_related("plan", "created_by", "source_version").all()
    serializer_class = PlanVersionSerializer

    @action(detail=True, methods=["post"], url_path="generate")
    def generate(self, request, pk=None):
        version = self.get_object()
        result = generate_plan_version(version)
        record_audit_event(
            actor=request.user,
            organization=version.plan.organization,
            action="planversion.generate",
            object_type="plan_version",
            object_id=str(version.pk),
            object_repr=str(version),
            metadata={
                "tripCount": result.trip_count,
                "conflictCount": result.conflict_count,
                "blockingConflictCount": result.blocking_conflict_count,
            },
            request=request,
        )
        return Response(PlanVersionSerializer(result.plan_version).data)

    @action(detail=True, methods=["post"], url_path="clone")
    def clone(self, request, pk=None):
        source_version = self.get_object()
        clone = clone_plan_version(source_version=source_version, created_by=request.user)
        record_audit_event(
            actor=request.user,
            organization=source_version.plan.organization,
            action="planversion.clone",
            object_type="plan_version",
            object_id=str(clone.pk),
            object_repr=str(clone),
            metadata={
                "source_version_id": source_version.pk,
                "source_version_no": source_version.version_no,
            },
            request=request,
        )
        return Response(PlanVersionSerializer(clone).data, status=status.HTTP_201_CREATED)


class TripViewSet(SchedulingViewSet):
    queryset = (
        Trip.objects.select_related(
            "plan_version",
            "plan_version__plan",
            "voyage",
            "voyage__organization",
            "voyage__anchorage_location",
            "cargo_requirement",
            "cargo_requirement__coal_grade",
            "cargo_requirement__source_location",
            "cargo_requirement__preferred_jetty",
            "cargo_layer_step",
            "cargo_layer_step__coal_grade",
            "cargo_layer_step__planned_barge",
            "cargo_layer_step__planned_jetty",
            "cargo_layer_step__planned_cts",
            "origin_jetty",
            "destination_location",
        )
        .prefetch_related("events")
        .all()
    )
    serializer_class = TripSerializer


class AssignmentViewSet(SchedulingViewSet):
    queryset = Assignment.objects.select_related(
        "trip",
        "trip__voyage",
        "tug",
        "barge",
        "jetty",
        "cts",
        "route_segment",
        "owner_organization",
    ).all()
    serializer_class = AssignmentSerializer


class ScheduleEventViewSet(SchedulingViewSet):
    queryset = ScheduleEvent.objects.select_related("trip").all()
    serializer_class = ScheduleEventSerializer


class ConflictViewSet(SchedulingViewSet):
    queryset = Conflict.objects.select_related(
        "plan_version",
        "plan_version__plan",
        "trip",
        "trip__voyage",
    ).all()
    serializer_class = ConflictSerializer


class SchedulingOverviewViewSet(SchedulingViewSet):
    queryset = PlanVersion.objects.none()
    serializer_class = PlanVersionSerializer

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):
        active_version = (
            PlanVersion.objects.select_related("plan", "created_by", "source_version")
            .annotate(
                open_blockers=Count(
                    "conflicts",
                    filter=Q(
                        conflicts__is_blocking=True,
                        conflicts__resolved_at__isnull=True,
                    ),
                )
            )
            .order_by("-generated_at", "-created_at")
            .first()
        )
        trips = Trip.objects.none()
        assignments = Assignment.objects.none()
        events = ScheduleEvent.objects.none()
        conflicts = Conflict.objects.none()

        if active_version:
            trips = (
                Trip.objects.filter(plan_version=active_version)
                .select_related(
                    "plan_version",
                    "plan_version__plan",
                    "voyage",
                    "voyage__organization",
                    "voyage__anchorage_location",
                    "cargo_requirement",
                    "cargo_requirement__coal_grade",
                    "cargo_requirement__source_location",
                    "cargo_requirement__preferred_jetty",
                    "cargo_layer_step",
                    "cargo_layer_step__coal_grade",
                    "cargo_layer_step__planned_barge",
                    "cargo_layer_step__planned_jetty",
                    "cargo_layer_step__planned_cts",
                    "origin_jetty",
                    "destination_location",
                )
                .prefetch_related("events")
            )
            assignments = Assignment.objects.filter(
                trip__plan_version=active_version
            ).select_related(
                "trip",
                "trip__voyage",
                "tug",
                "barge",
                "jetty",
                "cts",
                "route_segment",
                "owner_organization",
            )
            events = ScheduleEvent.objects.filter(
                trip__plan_version=active_version
            ).select_related("trip")
            conflicts = Conflict.objects.filter(plan_version=active_version).select_related(
                "plan_version",
                "plan_version__plan",
                "trip",
                "trip__voyage",
            )

        trip_totals = trips.aggregate(
            required=Sum("planned_quantity_mt"),
            loaded=Sum("loaded_quantity_mt"),
        )
        conflict_counts = conflicts.aggregate(
            total=Count("id"),
            blocking=Count("id", filter=Q(is_blocking=True, resolved_at__isnull=True)),
            critical=Count("id", filter=Q(severity=Conflict.Severity.CRITICAL)),
        )

        return Response(
            {
                "plans": PlanSerializer(
                    Plan.objects.select_related("organization"),
                    many=True,
                ).data,
                "planVersions": PlanVersionSerializer(
                    PlanVersion.objects.select_related("plan", "created_by", "source_version"),
                    many=True,
                ).data,
                "activePlanVersion": (
                    PlanVersionSerializer(active_version).data if active_version else None
                ),
                "trips": TripSerializer(trips, many=True).data,
                "assignments": AssignmentSerializer(assignments, many=True).data,
                "events": ScheduleEventSerializer(events, many=True).data,
                "conflicts": ConflictSerializer(conflicts, many=True).data,
                "validation": {
                    "tripCount": trips.count(),
                    "assignmentCount": assignments.count(),
                    "eventCount": events.count(),
                    "conflictCount": conflict_counts["total"] or 0,
                    "blockingConflictCount": conflict_counts["blocking"] or 0,
                    "criticalConflictCount": conflict_counts["critical"] or 0,
                    "plannedMt": trip_totals["required"] or 0,
                    "loadedMt": trip_totals["loaded"] or 0,
                },
            }
        )
