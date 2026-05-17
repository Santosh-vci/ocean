from django.db.models import Count, F, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.audit.mixins import AuditMutationMixin
from apps.audit.services import record_audit_event
from apps.core.object_storage import read_export_object
from apps.rbac.permissions import RequiresAccessPermission

from .export_services import (
    create_governed_export,
    export_jobs_visible_to_user,
    export_overview_for_user,
)
from .models import (
    ApprovalDecision,
    ApprovalRequest,
    Assignment,
    Conflict,
    ExportJob,
    OverrideRequest,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
    ScheduleEvent,
    SimulationScenario,
    Trip,
)
from .read_models import build_dashboard_read_model
from .serializers import (
    ApprovalDecisionSerializer,
    ApprovalRequestSerializer,
    AssignmentSerializer,
    ConflictSerializer,
    ExportJobSerializer,
    OverrideRequestSerializer,
    PlanSerializer,
    PlanVersionSerializer,
    PublishedPlanSnapshotSerializer,
    ScheduleEventSerializer,
    SimulationScenarioSerializer,
    TripSerializer,
)
from .services import (
    apply_assignment_override,
    clone_plan_version,
    compute_plan_diff,
    create_plan_version,
    create_scenario_from_conflict,
    generate_plan_version,
    promote_scenario_to_proposed,
    publish_plan_version,
    record_approval_decision,
    simulate_scenario,
    submit_approval_request,
)


def _schedule_version_queryset():
    return PlanVersion.objects.select_related("plan", "created_by", "source_version").annotate(
        open_blockers=Count(
            "conflicts",
            filter=Q(conflicts__is_blocking=True, conflicts__resolved_at__isnull=True),
        )
    )


def _active_schedule_version():
    publish_candidate = (
        _schedule_version_queryset()
        .filter(status=PlanVersion.Status.APPROVED)
        .order_by("-created_at")
        .first()
    )
    if publish_candidate:
        return publish_candidate

    active_candidate = (
        _schedule_version_queryset()
        .filter(
            status__in=[
                PlanVersion.Status.DRAFT,
                PlanVersion.Status.VALIDATED,
                PlanVersion.Status.PROPOSED,
            ]
        )
        .order_by("-created_at")
        .first()
    )
    if active_candidate:
        return active_candidate

    return (
        _schedule_version_queryset()
        .order_by(F("generated_at").desc(nulls_last=True), "-created_at")
        .first()
    )


class DashboardSituationView(APIView):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {"get": "dashboard.view"}

    def get(self, request):
        return Response(build_dashboard_read_model(request.user))


class SchedulingViewSet(AuditMutationMixin, ModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "schedule.view",
        "retrieve": "schedule.view",
        "overview": "schedule.view",
        "create_version": "schedule.edit",
        "generate": "schedule.edit",
        "clone": "schedule.edit",
        "apply_override": "schedule.edit",
        "request_approval": "schedule.edit",
        "decide": "schedule.approve",
        "publish": "schedule.publish",
        "diff": "schedule.view",
        "create_scenario": "schedule.edit",
        "simulate": "schedule.edit",
        "promote": "schedule.edit",
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

    @action(detail=True, methods=["post"], url_path="request-approval")
    def request_approval(self, request, pk=None):
        version = self.get_object()
        approval_request = submit_approval_request(
            plan_version=version,
            actor=request.user,
            reason=request.data.get("reason", ""),
        )
        record_audit_event(
            actor=request.user,
            organization=version.plan.organization,
            action="approval.request",
            object_type="approval_request",
            object_id=str(approval_request.pk),
            object_repr=approval_request.request_id,
            metadata={"plan_version": str(version), "status": approval_request.status},
            request=request,
        )
        return Response(
            ApprovalRequestSerializer(approval_request).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="publish")
    def publish(self, request, pk=None):
        version = self.get_object()
        snapshot = publish_plan_version(plan_version=version, actor=request.user)
        record_audit_event(
            actor=request.user,
            organization=version.plan.organization,
            action="planversion.publish",
            object_type="published_plan_snapshot",
            object_id=str(snapshot.pk),
            object_repr=snapshot.snapshot_id,
            metadata={"plan_version": str(version), "snapshot_id": snapshot.snapshot_id},
            request=request,
        )
        return Response(
            PublishedPlanSnapshotSerializer(snapshot).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get"], url_path="diff")
    def diff(self, request, pk=None):
        source_version = self.get_object()
        target_id = request.query_params.get("against")
        if not target_id:
            return Response(
                {"detail": "against query parameter is required."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        target_version = get_object_or_404(PlanVersion, pk=target_id)
        return Response(
            compute_plan_diff(source_version=source_version, target_version=target_version)
        )

    @action(detail=True, methods=["post"], url_path="create-scenario")
    def create_scenario(self, request, pk=None):
        version = self.get_object()
        conflict = None
        conflict_id = request.data.get("conflict")
        if conflict_id:
            conflict = get_object_or_404(Conflict, pk=conflict_id, plan_version=version)
        scenario = create_scenario_from_conflict(
            baseline_version=version,
            source_conflict=conflict,
            actor=request.user,
            name=request.data.get("name", ""),
        )
        record_audit_event(
            actor=request.user,
            organization=version.plan.organization,
            action="simulation.create",
            object_type="simulation_scenario",
            object_id=str(scenario.pk),
            object_repr=scenario.scenario_id,
            metadata={"plan_version": str(version), "source_conflict": conflict_id},
            request=request,
        )
        return Response(SimulationScenarioSerializer(scenario).data, status=status.HTTP_201_CREATED)


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

    @action(detail=True, methods=["post"], url_path="apply-override")
    def apply_override(self, request, pk=None):
        assignment = self.get_object()
        override = apply_assignment_override(
            assignment=assignment,
            actor=request.user,
            reason_code=request.data.get("reason_code", ""),
            description=request.data.get("description", ""),
            changes=request.data.get("changes", {}),
            impact_context=request.data.get("impact_context", {}),
        )
        record_audit_event(
            actor=request.user,
            organization=assignment.owner_organization,
            action="assignment.override",
            object_type="override_request",
            object_id=str(override.pk),
            object_repr=str(override),
            metadata={
                "trip": assignment.trip.trip_id,
                "reason_code": override.reason_code,
                "requested_change": override.requested_change,
                "impact_assessment": (
                    override.impact_assessment.assessment_id
                    if hasattr(override, "impact_assessment")
                    else None
                ),
            },
            request=request,
        )
        return Response(OverrideRequestSerializer(override).data, status=status.HTTP_201_CREATED)


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


class OverrideRequestViewSet(SchedulingViewSet):
    queryset = OverrideRequest.objects.select_related(
        "plan_version",
        "plan_version__plan",
        "trip",
        "trip__voyage",
        "assignment",
        "requested_by",
        "applied_by",
        "impact_assessment",
    ).all()
    serializer_class = OverrideRequestSerializer


class ApprovalRequestViewSet(SchedulingViewSet):
    queryset = (
        ApprovalRequest.objects.select_related(
            "plan_version",
            "plan_version__plan",
            "requested_by",
        )
        .prefetch_related("decisions")
        .all()
    )
    serializer_class = ApprovalRequestSerializer

    @action(detail=True, methods=["post"], url_path="decide")
    def decide(self, request, pk=None):
        approval_request = self.get_object()
        decision = record_approval_decision(
            approval_request=approval_request,
            actor=request.user,
            decision=request.data.get("decision", ApprovalDecision.Decision.APPROVE),
            authority_role=request.data.get("authority_role", ""),
            comments=request.data.get("comments", ""),
        )
        record_audit_event(
            actor=request.user,
            organization=decision.organization,
            action="approval.decision",
            object_type="approval_decision",
            object_id=str(decision.pk),
            object_repr=str(decision),
            metadata={
                "request_id": approval_request.request_id,
                "authority_role": decision.authority_role,
                "decision": decision.decision,
            },
            request=request,
        )
        approval_request.refresh_from_db()
        return Response(ApprovalRequestSerializer(approval_request).data)


class ApprovalDecisionViewSet(SchedulingViewSet):
    queryset = ApprovalDecision.objects.select_related(
        "approval_request",
        "actor",
        "organization",
    ).all()
    serializer_class = ApprovalDecisionSerializer


class PublishedPlanSnapshotViewSet(SchedulingViewSet):
    queryset = PublishedPlanSnapshot.objects.select_related(
        "plan",
        "plan_version",
        "approval_request",
        "published_by",
    ).all()
    serializer_class = PublishedPlanSnapshotSerializer


class ExportJobViewSet(ReadOnlyModelViewSet):
    serializer_class = ExportJobSerializer
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "export.view",
        "retrieve": "export.view",
        "overview": "export.view",
        "download": "export.view",
        "generate": "export.generate",
    }

    def get_queryset(self):
        return export_jobs_visible_to_user(self.request.user)

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):
        jobs = self.get_queryset()[:30]
        return Response(
            {
                **export_overview_for_user(request.user),
                "exports": ExportJobSerializer(jobs, many=True).data,
            }
        )

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        plan_version = None
        plan_version_id = request.data.get("plan_version")
        if plan_version_id:
            plan_version = get_object_or_404(PlanVersion, pk=plan_version_id)
        export_job = create_governed_export(
            actor=request.user,
            export_type=request.data.get("export_type", ExportJob.ExportType.PLAN),
            export_format=request.data.get("export_format", ExportJob.ExportFormat.JSON),
            plan_version=plan_version,
            request=request,
        )
        return Response(ExportJobSerializer(export_job).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=["get"], url_path="download")
    def download(self, request, pk=None):
        export_job = self.get_object()
        content = read_export_object(
            key=export_job.storage_key,
            bucket=export_job.storage_bucket,
        )
        response = HttpResponse(content, content_type=export_job.content_type)
        response["Content-Disposition"] = f'attachment; filename="{export_job.file_name}"'
        response["X-Content-SHA256"] = export_job.checksum_sha256
        return response


class SimulationScenarioViewSet(SchedulingViewSet):
    queryset = SimulationScenario.objects.select_related(
        "baseline_version",
        "baseline_version__plan",
        "scenario_version",
        "source_conflict",
        "source_conflict__trip",
        "source_conflict__trip__voyage",
        "created_by",
    ).all()
    serializer_class = SimulationScenarioSerializer

    @action(detail=True, methods=["post"], url_path="simulate")
    def simulate(self, request, pk=None):
        scenario = simulate_scenario(scenario=self.get_object())
        record_audit_event(
            actor=request.user,
            organization=scenario.baseline_version.plan.organization,
            action="simulation.run",
            object_type="simulation_scenario",
            object_id=str(scenario.pk),
            object_repr=scenario.scenario_id,
            metadata=scenario.delta_summary,
            request=request,
        )
        return Response(SimulationScenarioSerializer(scenario).data)

    @action(detail=True, methods=["post"], url_path="promote")
    def promote(self, request, pk=None):
        scenario = promote_scenario_to_proposed(scenario=self.get_object(), actor=request.user)
        record_audit_event(
            actor=request.user,
            organization=scenario.baseline_version.plan.organization,
            action="simulation.promote",
            object_type="simulation_scenario",
            object_id=str(scenario.pk),
            object_repr=scenario.scenario_id,
            metadata={"scenario_version": scenario.scenario_version_id},
            request=request,
        )
        return Response(SimulationScenarioSerializer(scenario).data)


class SchedulingOverviewViewSet(SchedulingViewSet):
    queryset = PlanVersion.objects.none()
    serializer_class = PlanVersionSerializer

    @action(detail=False, methods=["get"], url_path="overview")
    def overview(self, request):
        active_version = _active_schedule_version()
        trips = Trip.objects.none()
        assignments = Assignment.objects.none()
        events = ScheduleEvent.objects.none()
        conflicts = Conflict.objects.none()
        override_requests = OverrideRequest.objects.none()
        approval_requests = ApprovalRequest.objects.none()
        scenarios = SimulationScenario.objects.none()

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
            override_requests = OverrideRequest.objects.filter(
                plan_version=active_version
            ).select_related(
                "plan_version",
                "trip",
                "trip__voyage",
                "assignment",
                "requested_by",
                "applied_by",
                "impact_assessment",
            )
            approval_requests = (
                ApprovalRequest.objects.filter(plan_version=active_version)
                .select_related("plan_version", "requested_by")
                .prefetch_related("decisions")
            )
            scenarios = SimulationScenario.objects.filter(
                Q(baseline_version=active_version) | Q(scenario_version=active_version)
            ).select_related(
                "baseline_version",
                "scenario_version",
                "source_conflict",
                "source_conflict__trip",
                "source_conflict__trip__voyage",
                "created_by",
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
                "overrideRequests": OverrideRequestSerializer(
                    override_requests,
                    many=True,
                ).data,
                "approvalRequests": ApprovalRequestSerializer(
                    approval_requests,
                    many=True,
                ).data,
                "publishedSnapshots": PublishedPlanSnapshotSerializer(
                    PublishedPlanSnapshot.objects.select_related(
                        "plan",
                        "plan_version",
                        "approval_request",
                        "published_by",
                    ),
                    many=True,
                ).data,
                "simulationScenarios": SimulationScenarioSerializer(
                    scenarios,
                    many=True,
                ).data,
                "validation": {
                    "tripCount": trips.count(),
                    "assignmentCount": assignments.count(),
                    "eventCount": events.count(),
                    "conflictCount": conflict_counts["total"] or 0,
                    "blockingConflictCount": conflict_counts["blocking"] or 0,
                    "criticalConflictCount": conflict_counts["critical"] or 0,
                    "overrideCount": override_requests.count(),
                    "approvalPendingCount": approval_requests.filter(
                        status=ApprovalRequest.Status.PENDING
                    ).count(),
                    "scenarioCount": scenarios.count(),
                    "plannedMt": trip_totals["required"] or 0,
                    "loadedMt": trip_totals["loaded"] or 0,
                },
            }
        )
