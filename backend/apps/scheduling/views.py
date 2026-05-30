from django.db.models import Count, Q, Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from apps.audit.mixins import AuditMutationMixin
from apps.audit.services import record_audit_event
from apps.core.object_storage import read_export_object
from apps.operations.services import operations_health_summary
from apps.rbac.permissions import RequiresAccessPermission
from apps.telemetry.models import LiveEtaProjection, TrackingAlert
from apps.telemetry.serializers import (
    LiveEtaProjectionSerializer,
    TelemetryTrustAssessmentSerializer,
    TrackingAlertSerializer,
)
from apps.telemetry.telemetry_trust_services import latest_trust_assessment_summary

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
    CommercialProjectionRun,
    CustomerSafeCommercialProjection,
    ExportJob,
    GlobalOptimizationCandidate,
    GlobalOptimizationRun,
    OptimizerRun,
    OverrideRequest,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
    RecommendationEvaluation,
    RecoveryAction,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
    RootCauseRepairAssessment,
    ScenarioRun,
    ScheduleEvent,
    SimulationScenario,
    Trip,
)
from .active_plan_selectors import WORKING_CANDIDATE, select_active_plan_version
from .read_models import build_dashboard_read_model
from .recovery_services import (
    build_recommendation_proof_pack,
    build_recovery_input_snapshot,
    generate_recovery_recommendations,
    materialize_recommendation_as_scenario,
)
from .root_cause_services import assess_recommendation_root_cause
from .publishability_services import assess_plan_publishability, latest_publishability_assessment
from .global_optimizer_services import (
    generate_global_optimization_candidates,
    latest_global_optimization_run,
)
from .commercial_projection_services import (
    commercial_projection_summary_payload,
    generate_customer_safe_commercial_projections,
    latest_commercial_projection_run,
)
from .serializers import (
    ApprovalDecisionSerializer,
    ApprovalRequestSerializer,
    AssignmentSerializer,
    CommercialProjectionRunGenerateSerializer,
    CommercialProjectionRunSerializer,
    ConflictSerializer,
    CustomerSafeCommercialProjectionSerializer,
    ExportJobSerializer,
    GlobalOptimizationCandidateSerializer,
    GlobalOptimizationRunGenerateSerializer,
    GlobalOptimizationRunSerializer,
    OptimizerRunGenerateSerializer,
    OptimizerRunSerializer,
    OverrideRequestSerializer,
    PlanSerializer,
    PlanVersionSerializer,
    PublishabilityAssessmentSerializer,
    PublishedPlanSnapshotSerializer,
    RecommendationEvaluationSerializer,
    RecoveryActionSerializer,
    RecoveryInputSnapshotBuildSerializer,
    RecoveryInputSnapshotSerializer,
    RecoveryRecommendationDismissSerializer,
    RecoveryRecommendationMaterializeSerializer,
    RecoveryRecommendationSerializer,
    RootCauseRepairAssessmentSerializer,
    ScenarioAssumptionSerializer,
    ScenarioConstraintEvaluationSerializer,
    ScenarioEventProjectionSerializer,
    ScenarioOgvProjectionSerializer,
    ScenarioResourceUtilizationSerializer,
    ScenarioRunSerializer,
    ScenarioTripProjectionSerializer,
    ScheduleEventSerializer,
    SimulationScenarioSerializer,
    TripSerializer,
)
from .services import (
    apply_assignment_override,
    clone_plan_version,
    compute_plan_diff,
    create_plan_version,
    create_scenario_assumption,
    create_scenario_from_conflict,
    create_scenario_run,
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
    version = select_active_plan_version(WORKING_CANDIDATE)
    if version is None:
        return None
    return _schedule_version_queryset().filter(pk=version.pk).first()


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
        "publishability_assessment": "schedule.view",
        "diff": "schedule.view",
        "create_scenario": "schedule.edit",
        "simulate": "schedule.edit",
        "promote": "schedule.edit",
        "assumptions": "schedule.edit",
        "runs": "schedule.edit",
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

    @action(
        detail=True,
        methods=["get", "post"],
        url_path="publishability-assessment",
    )
    def publishability_assessment(self, request, pk=None):
        version = self.get_object()
        if request.method.lower() == "get":
            assessment = latest_publishability_assessment(version)
            if assessment is None:
                return Response(None)
            return Response(PublishabilityAssessmentSerializer(assessment).data)

        assessment = assess_plan_publishability(
            plan_version=version,
            actor=request.user,
            persist=True,
        )
        return Response(PublishabilityAssessmentSerializer(assessment).data)

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
        override = None
        override_id = request.data.get("override")
        if override_id:
            override = get_object_or_404(OverrideRequest, pk=override_id, plan_version=version)
        scenario = create_scenario_from_conflict(
            baseline_version=version,
            source_conflict=conflict,
            source_override=override,
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
            metadata={
                "plan_version": str(version),
                "source_conflict": conflict_id,
                "source_override": override_id,
                "source_kind": scenario.source_kind,
            },
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


class RecoveryInputSnapshotViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "schedule.view",
        "retrieve": "schedule.view",
        "build": "schedule.edit",
    }
    queryset = RecoveryInputSnapshot.objects.select_related(
        "plan_version",
        "plan_version__plan",
        "source_conflict",
        "source_override",
        "source_tracking_alert",
        "source_operational_event",
        "source_scenario",
        "captured_by",
    ).all()
    serializer_class = RecoveryInputSnapshotSerializer

    @action(detail=False, methods=["post"], url_path="build")
    def build(self, request):
        build_serializer = RecoveryInputSnapshotBuildSerializer(data=request.data)
        build_serializer.is_valid(raise_exception=True)
        snapshot = build_recovery_input_snapshot(
            actor=request.user,
            **build_serializer.validated_data,
        )
        record_audit_event(
            actor=request.user,
            organization=snapshot.organization,
            action="recovery.input_snapshot.build",
            object_type="recovery_input_snapshot",
            object_id=str(snapshot.pk),
            object_repr=snapshot.snapshot_id,
            metadata={
                "plan_version": str(snapshot.plan_version),
                "source_kind": snapshot.source_kind,
                "source_ref": snapshot.source_ref,
                "input_hash": snapshot.input_hash,
                "active_conflict_count": snapshot.active_conflict_count,
                "confirmed_event_count": snapshot.confirmed_event_count,
                "tracking_alert_count": snapshot.tracking_alert_count,
            },
            request=request,
        )
        return Response(
            RecoveryInputSnapshotSerializer(snapshot).data,
            status=status.HTTP_201_CREATED,
        )


class OptimizerRunViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "schedule.view",
        "retrieve": "schedule.view",
        "create": "schedule.edit",
        "generate": "schedule.edit",
    }
    queryset = OptimizerRun.objects.select_related(
        "input_snapshot",
        "plan_version",
        "plan_version__plan",
        "started_by",
    ).prefetch_related(
        "recommendations",
        "recommendations__actions",
        "recommendations__evaluation",
    )
    serializer_class = OptimizerRunSerializer

    def create(self, request):
        return self._generate_recovery_run(request)

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        return self._generate_recovery_run(request)

    def _generate_recovery_run(self, request):
        generate_serializer = OptimizerRunGenerateSerializer(data=request.data)
        generate_serializer.is_valid(raise_exception=True)
        optimizer_run = generate_recovery_recommendations(
            snapshot=generate_serializer.validated_data["input_snapshot"],
            objective_weights=generate_serializer.validated_data.get("objective_weights", {}),
            max_candidates=generate_serializer.validated_data.get("max_candidates", 5),
            actor=request.user,
        )
        optimizer_run = self.get_queryset().get(pk=optimizer_run.pk)
        record_audit_event(
            actor=request.user,
            organization=optimizer_run.organization,
            action="recovery.optimizer.run",
            object_type="optimizer_run",
            object_id=str(optimizer_run.pk),
            object_repr=optimizer_run.run_id,
            metadata={
                "input_snapshot": optimizer_run.input_snapshot.snapshot_id,
                "plan_version": str(optimizer_run.plan_version),
                "algorithm_version": optimizer_run.algorithm_version,
                "recommendation_count": optimizer_run.recommendations.count(),
                "best_strategy": optimizer_run.summary.get("bestStrategy", ""),
            },
            request=request,
        )
        return Response(
            OptimizerRunSerializer(optimizer_run).data,
            status=status.HTTP_201_CREATED,
        )


class GlobalOptimizationRunViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "schedule.view",
        "retrieve": "schedule.view",
        "create": "schedule.edit",
        "generate": "schedule.edit",
    }
    queryset = GlobalOptimizationRun.objects.select_related(
        "plan_version",
        "plan_version__plan",
        "objective_profile",
        "started_by",
    ).prefetch_related("candidates")
    serializer_class = GlobalOptimizationRunSerializer

    def create(self, request):
        return self._generate_global_run(request)

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        return self._generate_global_run(request)

    def _generate_global_run(self, request):
        generate_serializer = GlobalOptimizationRunGenerateSerializer(data=request.data)
        generate_serializer.is_valid(raise_exception=True)
        run = generate_global_optimization_candidates(
            plan_version=generate_serializer.validated_data.get("plan_version"),
            objective_profile=generate_serializer.validated_data.get("objective_profile"),
            objective_weights=generate_serializer.validated_data.get("objective_weights", {}),
            max_candidates=generate_serializer.validated_data.get("max_candidates", 3),
            actor=request.user,
        )
        run = self.get_queryset().get(pk=run.pk)
        record_audit_event(
            actor=request.user,
            organization=run.organization,
            action="global_optimizer.run.generate",
            object_type="global_optimization_run",
            object_id=str(run.pk),
            object_repr=run.run_id,
            metadata={
                "run_id": run.run_id,
                "plan_version_id": run.plan_version_id,
                "objective_profile_key": (
                    run.objective_profile.profile_key if run.objective_profile else ""
                ),
                "objective_profile_version": (
                    run.objective_profile.version if run.objective_profile else None
                ),
                "input_signature": run.input_signature,
                "candidate_count": run.candidates.count(),
                "algorithm_version": run.algorithm_version,
            },
            request=request,
        )
        return Response(
            GlobalOptimizationRunSerializer(run).data,
            status=status.HTTP_201_CREATED,
        )


class GlobalOptimizationCandidateViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "schedule.view",
        "retrieve": "schedule.view",
    }
    queryset = GlobalOptimizationCandidate.objects.select_related(
        "run",
        "run__plan_version",
        "run__plan_version__plan",
    ).all()
    serializer_class = GlobalOptimizationCandidateSerializer


class CommercialProjectionRunViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "schedule.view",
        "retrieve": "schedule.view",
        "create": "schedule.view",
        "generate": "schedule.view",
    }
    queryset = CommercialProjectionRun.objects.select_related(
        "plan_version",
        "plan_version__plan",
        "telemetry_trust_profile",
        "generated_by",
    ).prefetch_related(
        "projections",
        "projections__voyage",
        "projections__trip",
    )
    serializer_class = CommercialProjectionRunSerializer

    def create(self, request):
        return self._generate_commercial_run(request)

    @action(detail=False, methods=["post"], url_path="generate")
    def generate(self, request):
        return self._generate_commercial_run(request)

    def _generate_commercial_run(self, request):
        generate_serializer = CommercialProjectionRunGenerateSerializer(data=request.data)
        generate_serializer.is_valid(raise_exception=True)
        run = generate_customer_safe_commercial_projections(
            plan_version=generate_serializer.validated_data.get("plan_version"),
            actor=request.user,
        )
        run = self.get_queryset().get(pk=run.pk)
        record_audit_event(
            actor=request.user,
            organization=run.organization,
            action="commercial_projection.run.generate",
            object_type="commercial_projection_run",
            object_id=str(run.pk),
            object_repr=run.run_id,
            metadata={
                "run_id": run.run_id,
                "plan_version_id": run.plan_version_id,
                "input_signature": run.input_signature,
                "projection_count": run.projections.count(),
                "algorithm_version": run.algorithm_version,
                "projection_only": True,
                "final_settlement": False,
            },
            request=request,
        )
        return Response(
            CommercialProjectionRunSerializer(run).data,
            status=status.HTTP_201_CREATED,
        )


class CustomerSafeCommercialProjectionViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "schedule.view",
        "retrieve": "schedule.view",
    }
    queryset = CustomerSafeCommercialProjection.objects.select_related(
        "run",
        "run__plan_version",
        "run__plan_version__plan",
        "voyage",
        "trip",
    ).all()
    serializer_class = CustomerSafeCommercialProjectionSerializer


class RecoveryRecommendationViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "schedule.view",
        "retrieve": "schedule.view",
        "proof_pack": "schedule.view",
        "root_cause_assessment": "schedule.view",
        "dismiss": "schedule.edit",
        "materialize_scenario": "schedule.edit",
    }
    queryset = RecoveryRecommendation.objects.select_related(
        "optimizer_run",
        "optimizer_run__input_snapshot",
        "optimizer_run__input_snapshot__source_conflict",
        "optimizer_run__input_snapshot__source_override",
        "optimizer_run__input_snapshot__source_tracking_alert",
        "optimizer_run__input_snapshot__source_operational_event",
        "optimizer_run__plan_version",
        "scenario",
        "root_cause_assessment",
    ).prefetch_related("actions", "evaluation")
    serializer_class = RecoveryRecommendationSerializer

    @action(detail=True, methods=["get", "post"], url_path="root-cause-assessment")
    def root_cause_assessment(self, request, pk=None):
        recommendation = self.get_object()
        if request.method.lower() == "get":
            assessment = RootCauseRepairAssessment.objects.filter(
                recommendation=recommendation,
            ).first()
            if assessment is None:
                return Response(None)
            return Response(RootCauseRepairAssessmentSerializer(assessment).data)

        assessment = assess_recommendation_root_cause(
            recommendation=recommendation,
            actor=request.user,
        )
        record_audit_event(
            actor=request.user,
            organization=recommendation.organization,
            action="recovery.recommendation.root_cause_assess",
            object_type="root_cause_repair_assessment",
            object_id=str(assessment.pk),
            object_repr=assessment.assessment_id,
            metadata={
                "recommendation": recommendation.recommendation_id,
                "source_cause_type": assessment.source_cause_type,
                "status": assessment.status,
                "assessment_algorithm": assessment.assessed_by_algorithm_version,
            },
            request=request,
        )
        return Response(RootCauseRepairAssessmentSerializer(assessment).data)

    @action(detail=True, methods=["get"], url_path="proof-pack")
    def proof_pack(self, request, pk=None):
        recommendation = self.get_object()
        payload = build_recommendation_proof_pack(recommendation=recommendation)
        record_audit_event(
            actor=request.user,
            organization=recommendation.organization,
            action="recovery.recommendation.proof_pack_viewed",
            object_type="recovery_recommendation",
            object_id=str(recommendation.pk),
            object_repr=recommendation.recommendation_id,
            metadata={
                "proof_pack_version": payload["proofPackVersion"],
                "optimizer_run": recommendation.optimizer_run.run_id,
                "scenario_id": recommendation.scenario.scenario_id
                if recommendation.scenario
                else None,
            },
            request=request,
        )
        return Response(payload)

    @action(detail=True, methods=["post"], url_path="dismiss")
    def dismiss(self, request, pk=None):
        dismiss_serializer = RecoveryRecommendationDismissSerializer(data=request.data)
        dismiss_serializer.is_valid(raise_exception=True)
        recommendation = self.get_object()
        if recommendation.scenario_id:
            return Response(
                {"detail": "Recommendations already created as scenarios cannot be dismissed."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        recommendation.status = RecoveryRecommendation.Status.DISMISSED
        recommendation.metadata = {
            **recommendation.metadata,
            "dismissal": {
                "reason": dismiss_serializer.validated_data["reason"],
                "dismissedAt": timezone.now().isoformat(),
                "dismissedBy": request.user.email,
            },
        }
        recommendation.save(update_fields=["status", "metadata", "updated_at"])
        record_audit_event(
            actor=request.user,
            organization=recommendation.organization,
            action="recovery.recommendation.dismiss",
            object_type="recovery_recommendation",
            object_id=str(recommendation.pk),
            object_repr=recommendation.recommendation_id,
            metadata={
                "reason": dismiss_serializer.validated_data["reason"],
                "optimizer_run": recommendation.optimizer_run.run_id,
            },
            request=request,
        )
        return Response(RecoveryRecommendationSerializer(recommendation).data)

    @action(detail=True, methods=["post"], url_path="materialize-scenario")
    def materialize_scenario(self, request, pk=None):
        materialize_serializer = RecoveryRecommendationMaterializeSerializer(
            data=request.data,
        )
        materialize_serializer.is_valid(raise_exception=True)
        recommendation = materialize_recommendation_as_scenario(
            recommendation=self.get_object(),
            actor=request.user,
            name=materialize_serializer.validated_data.get("name", ""),
            run_simulation=materialize_serializer.validated_data.get(
                "run_simulation",
                True,
            ),
        )
        recommendation = self.get_queryset().get(pk=recommendation.pk)
        record_audit_event(
            actor=request.user,
            organization=recommendation.organization,
            action="recovery.recommendation.materialize_scenario",
            object_type="recovery_recommendation",
            object_id=str(recommendation.pk),
            object_repr=recommendation.recommendation_id,
            metadata={
                "scenario_id": recommendation.scenario.scenario_id
                if recommendation.scenario
                else None,
                "scenario_pk": recommendation.scenario_id,
                "scenario_status": recommendation.scenario.status
                if recommendation.scenario
                else None,
                "optimizer_run": recommendation.optimizer_run.run_id,
                "strategy": recommendation.metadata.get("strategy", ""),
                "materialization": recommendation.metadata.get("materialization", {}),
            },
            request=request,
        )
        return Response(
            RecoveryRecommendationSerializer(recommendation).data,
            status=status.HTTP_201_CREATED,
        )


class RecoveryActionViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {"list": "schedule.view", "retrieve": "schedule.view"}
    queryset = RecoveryAction.objects.select_related(
        "recommendation",
        "recommendation__optimizer_run",
        "target_trip",
        "target_assignment",
    ).all()
    serializer_class = RecoveryActionSerializer


class RecommendationEvaluationViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {"list": "schedule.view", "retrieve": "schedule.view"}
    queryset = RecommendationEvaluation.objects.select_related(
        "recommendation",
        "recommendation__optimizer_run",
    ).all()
    serializer_class = RecommendationEvaluationSerializer


class SimulationScenarioViewSet(SchedulingViewSet):
    queryset = SimulationScenario.objects.select_related(
        "baseline_version",
        "baseline_version__plan",
        "scenario_version",
        "source_conflict",
        "source_conflict__trip",
        "source_conflict__trip__voyage",
        "source_override",
        "source_override__trip",
        "source_override__trip__voyage",
        "created_by",
    ).prefetch_related(
        "assumptions",
        "runs__trip_projections__trip",
        "runs__constraint_evaluations__trip",
        "runs__ogv_projections__voyage",
        "runs__resource_utilizations",
    ).all()
    serializer_class = SimulationScenarioSerializer

    @action(detail=True, methods=["post"], url_path="simulate")
    def simulate(self, request, pk=None):
        scenario = simulate_scenario(scenario=self.get_object(), actor=request.user)
        scenario = self.get_queryset().get(pk=scenario.pk)
        latest_run = scenario.runs.order_by("-created_at", "-id").first()
        record_audit_event(
            actor=request.user,
            organization=scenario.baseline_version.plan.organization,
            action="simulation.run",
            object_type="simulation_scenario",
            object_id=str(scenario.pk),
            object_repr=scenario.scenario_id,
            metadata={
                **scenario.delta_summary,
                "run_id": latest_run.run_id if latest_run else None,
            },
            request=request,
        )
        return Response(SimulationScenarioSerializer(scenario).data)

    @action(detail=True, methods=["post"], url_path="promote")
    def promote(self, request, pk=None):
        scenario = self.get_object()
        selected_run = None
        run_id = request.data.get("run_id")
        if run_id:
            selected_run = get_object_or_404(
                ScenarioRun,
                pk=run_id,
                scenario=scenario,
            )
        scenario = promote_scenario_to_proposed(
            scenario=scenario,
            actor=request.user,
            run=selected_run,
        )
        lineage = scenario.scenario_version.summary.get("scenarioLineage", {})
        record_audit_event(
            actor=request.user,
            organization=scenario.baseline_version.plan.organization,
            action="simulation.promote",
            object_type="simulation_scenario",
            object_id=str(scenario.pk),
            object_repr=scenario.scenario_id,
            metadata={
                "scenario_version": scenario.scenario_version_id,
                "selected_run_id": lineage.get("selectedRunId"),
                "selected_run_ref": lineage.get("selectedRunRef"),
            },
            request=request,
        )
        return Response(SimulationScenarioSerializer(scenario).data)

    @action(detail=True, methods=["get", "post"], url_path="assumptions")
    def assumptions(self, request, pk=None):
        scenario = self.get_object()
        if request.method.lower() == "get":
            assumptions = scenario.assumptions.select_related("scenario", "created_by")
            return Response(ScenarioAssumptionSerializer(assumptions, many=True).data)

        serializer = ScenarioAssumptionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        assumption = create_scenario_assumption(
            scenario=scenario,
            actor=request.user,
            kind=serializer.validated_data["kind"],
            scope_type=serializer.validated_data["scope_type"],
            scope_id=serializer.validated_data.get("scope_id"),
            payload=serializer.validated_data.get("payload", {}),
            effective_from=serializer.validated_data.get("effective_from"),
            effective_to=serializer.validated_data.get("effective_to"),
        )
        record_audit_event(
            actor=request.user,
            organization=scenario.baseline_version.plan.organization,
            action="simulation.assumption.create",
            object_type="scenario_assumption",
            object_id=str(assumption.pk),
            object_repr=assumption.assumption_id,
            metadata={
                "scenario_id": scenario.scenario_id,
                "kind": assumption.kind,
                "scope_type": assumption.scope_type,
                "scope_id": assumption.scope_id,
            },
            request=request,
        )
        return Response(
            ScenarioAssumptionSerializer(assumption).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["get", "post"], url_path="runs")
    def runs(self, request, pk=None):
        scenario = self.get_object()
        if request.method.lower() == "get":
            runs = scenario.runs.select_related("scenario", "baseline_version", "created_by")
            return Response(ScenarioRunSerializer(runs, many=True).data)

        run = create_scenario_run(
            scenario=scenario,
            actor=request.user,
            status=ScenarioRun.Status.QUEUED,
        )
        record_audit_event(
            actor=request.user,
            organization=scenario.baseline_version.plan.organization,
            action="simulation.run.create",
            object_type="scenario_run",
            object_id=str(run.pk),
            object_repr=run.run_id,
            metadata={
                "scenario_id": scenario.scenario_id,
                "status": run.status,
                "input_hash": run.input_hash,
            },
            request=request,
        )
        return Response(ScenarioRunSerializer(run).data, status=status.HTTP_201_CREATED)


class ScenarioRunViewSet(ReadOnlyModelViewSet):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "schedule.view",
        "retrieve": "schedule.view",
        "projections": "schedule.view",
        "constraints": "schedule.view",
        "utilization": "schedule.view",
        "ogv_projections": "schedule.view",
    }
    queryset = ScenarioRun.objects.select_related(
        "scenario",
        "baseline_version",
        "created_by",
    ).prefetch_related(
        "trip_projections__trip",
        "event_projections__trip",
        "event_projections__event",
        "constraint_evaluations__trip",
        "ogv_projections__voyage",
        "resource_utilizations",
    )
    serializer_class = ScenarioRunSerializer

    @action(detail=True, methods=["get"], url_path="projections")
    def projections(self, request, pk=None):
        run = self.get_object()
        return Response(
            {
                "run": ScenarioRunSerializer(run).data,
                "trip_projections": ScenarioTripProjectionSerializer(
                    run.trip_projections.select_related("trip"),
                    many=True,
                ).data,
                "event_projections": ScenarioEventProjectionSerializer(
                    run.event_projections.select_related("trip", "event"),
                    many=True,
                ).data,
            }
        )

    @action(detail=True, methods=["get"], url_path="constraints")
    def constraints(self, request, pk=None):
        run = self.get_object()
        return Response(
            ScenarioConstraintEvaluationSerializer(
                run.constraint_evaluations.select_related("trip"),
                many=True,
            ).data
        )

    @action(detail=True, methods=["get"], url_path="utilization")
    def utilization(self, request, pk=None):
        run = self.get_object()
        return Response(
            ScenarioResourceUtilizationSerializer(
                run.resource_utilizations.all(),
                many=True,
            ).data
        )

    @action(detail=True, methods=["get"], url_path="ogv-projections")
    def ogv_projections(self, request, pk=None):
        run = self.get_object()
        return Response(
            ScenarioOgvProjectionSerializer(
                run.ogv_projections.select_related("voyage"),
                many=True,
            ).data
        )


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
        recovery_input_snapshots = RecoveryInputSnapshot.objects.none()
        optimizer_runs = OptimizerRun.objects.none()
        recovery_recommendations = RecoveryRecommendation.objects.none()
        eta_projections = LiveEtaProjection.objects.none()
        tracking_alerts = TrackingAlert.objects.none()
        publishability_assessment = None
        global_optimization_runs = GlobalOptimizationRun.objects.none()
        global_optimization_candidates = GlobalOptimizationCandidate.objects.none()
        commercial_projection_run = None
        commercial_projections = CustomerSafeCommercialProjection.objects.none()
        telemetry_trust_summary = latest_trust_assessment_summary(None)

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
            scenario_baselines = [active_version.id]
            if active_version.source_version_id:
                scenario_baselines.append(active_version.source_version_id)
            scenarios = SimulationScenario.objects.filter(
                Q(baseline_version_id__in=scenario_baselines)
                | Q(scenario_version=active_version)
            ).select_related(
                "baseline_version",
                "scenario_version",
                "source_conflict",
                "source_conflict__trip",
                "source_conflict__trip__voyage",
                "source_override",
                "source_override__trip",
                "source_override__trip__voyage",
                "created_by",
            ).prefetch_related(
                "assumptions",
                "runs__trip_projections__trip",
                "runs__constraint_evaluations__trip",
                "runs__ogv_projections__voyage",
                "runs__resource_utilizations",
            )
            recovery_plan_versions = [active_version.id]
            if active_version.source_version_id:
                recovery_plan_versions.append(active_version.source_version_id)
            recovery_input_snapshots = RecoveryInputSnapshot.objects.filter(
                plan_version_id__in=recovery_plan_versions
            ).select_related(
                "plan_version",
                "plan_version__plan",
                "source_conflict",
                "source_override",
                "source_tracking_alert",
                "source_operational_event",
                "source_scenario",
                "captured_by",
            )
            optimizer_runs = OptimizerRun.objects.filter(
                plan_version_id__in=recovery_plan_versions
            ).select_related(
                "input_snapshot",
                "plan_version",
                "plan_version__plan",
                "started_by",
            ).prefetch_related(
                "recommendations",
                "recommendations__actions",
                "recommendations__evaluation",
            )
            recovery_recommendations = RecoveryRecommendation.objects.filter(
                optimizer_run__plan_version_id__in=recovery_plan_versions
            ).select_related(
                "optimizer_run",
                "optimizer_run__input_snapshot",
                "optimizer_run__plan_version",
                "scenario",
            ).prefetch_related("actions", "evaluation")
            eta_projections = LiveEtaProjection.objects.filter(
                trip__plan_version=active_version
            ).select_related(
                "source",
                "asset_identity",
                "trip",
                "trip__voyage",
                "schedule_event",
                "source_ping",
                "current_geofence",
            )
            tracking_alerts = TrackingAlert.objects.filter(
                trip__plan_version=active_version
            ).select_related(
                "source",
                "asset_identity",
                "source_ping",
                "trip",
                "trip__voyage",
                "schedule_event",
                "eta_projection",
                "created_scenario",
            )
            publishability_assessment = latest_publishability_assessment(active_version)
            global_run_plan_versions = [active_version.id]
            if active_version.source_version_id:
                global_run_plan_versions.append(active_version.source_version_id)
            global_optimization_runs = GlobalOptimizationRun.objects.filter(
                plan_version_id__in=global_run_plan_versions,
            ).select_related(
                "plan_version",
                "plan_version__plan",
                "objective_profile",
                "started_by",
            ).prefetch_related("candidates")
            latest_global_run = latest_global_optimization_run(active_version)
            if latest_global_run:
                global_optimization_candidates = latest_global_run.candidates.all()
            commercial_projection_run = latest_commercial_projection_run(active_version)
            if commercial_projection_run:
                commercial_projections = commercial_projection_run.projections.select_related(
                    "run",
                    "voyage",
                    "trip",
                )
            telemetry_trust_summary = latest_trust_assessment_summary(active_version)

        trip_totals = trips.aggregate(
            required=Sum("planned_quantity_mt"),
            loaded=Sum("loaded_quantity_mt"),
        )
        unresolved_conflicts = conflicts.filter(resolved_at__isnull=True)
        conflict_counts = unresolved_conflicts.aggregate(
            total=Count("id"),
            blocking=Count("id", filter=Q(is_blocking=True)),
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
                "recoveryInputSnapshots": RecoveryInputSnapshotSerializer(
                    recovery_input_snapshots,
                    many=True,
                ).data,
                "optimizerRuns": OptimizerRunSerializer(
                    optimizer_runs,
                    many=True,
                ).data,
                "recoveryRecommendations": RecoveryRecommendationSerializer(
                    recovery_recommendations,
                    many=True,
                ).data,
                "liveEtaProjections": LiveEtaProjectionSerializer(
                    eta_projections,
                    many=True,
                ).data,
                "trackingAlerts": TrackingAlertSerializer(
                    tracking_alerts,
                    many=True,
                ).data,
                "publishabilityAssessment": (
                    PublishabilityAssessmentSerializer(publishability_assessment).data
                    if publishability_assessment
                    else None
                ),
                "globalOptimizationRuns": GlobalOptimizationRunSerializer(
                    global_optimization_runs,
                    many=True,
                ).data,
                "globalOptimizationCandidates": GlobalOptimizationCandidateSerializer(
                    global_optimization_candidates,
                    many=True,
                ).data,
                "commercialProjectionRun": (
                    CommercialProjectionRunSerializer(commercial_projection_run).data
                    if commercial_projection_run
                    else None
                ),
                "commercialProjections": CustomerSafeCommercialProjectionSerializer(
                    commercial_projections,
                    many=True,
                ).data,
                "commercialProjectionSummary": commercial_projection_summary_payload(
                    commercial_projection_run,
                ),
                "telemetryTrustSummary": {
                    "profileKey": telemetry_trust_summary.profile_key,
                    "latestAssessmentCount": telemetry_trust_summary.latest_assessment_count,
                    "trustedCount": telemetry_trust_summary.trusted_count,
                    "degradedCount": telemetry_trust_summary.degraded_count,
                    "blockingCount": telemetry_trust_summary.blocking_count,
                    "unknownCount": telemetry_trust_summary.unknown_count,
                    "latestAssessedAt": (
                        telemetry_trust_summary.latest_assessed_at.isoformat()
                        if telemetry_trust_summary.latest_assessed_at
                        else None
                    ),
                    "latestAssessments": TelemetryTrustAssessmentSerializer(
                        telemetry_trust_summary.latest_assessments,
                        many=True,
                    ).data,
                },
                "trackingSummary": {
                    "projectionCount": eta_projections.count(),
                    "openAlertCount": tracking_alerts.filter(
                        status__in=[
                            TrackingAlert.Status.OPEN,
                            TrackingAlert.Status.ACKNOWLEDGED,
                        ],
                    ).count(),
                    "criticalAlertCount": tracking_alerts.filter(
                        status__in=[
                            TrackingAlert.Status.OPEN,
                            TrackingAlert.Status.ACKNOWLEDGED,
                        ],
                        severity=TrackingAlert.Severity.CRITICAL,
                    ).count(),
                    "highestVarianceMinutes": (
                        eta_projections.filter(variance_minutes__isnull=False)
                        .order_by("-variance_minutes")
                        .values_list("variance_minutes", flat=True)
                        .first()
                    )
                    or 0,
                },
                "operationsHealthSummary": operations_health_summary(),
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
                    "optimizerRunCount": optimizer_runs.count(),
                    "recoveryRecommendationCount": recovery_recommendations.count(),
                    "trackingAlertCount": tracking_alerts.count(),
                    "openTrackingAlertCount": tracking_alerts.filter(
                        status__in=[
                            TrackingAlert.Status.OPEN,
                            TrackingAlert.Status.ACKNOWLEDGED,
                        ],
                    ).count(),
                    "plannedMt": trip_totals["required"] or 0,
                    "loadedMt": trip_totals["loaded"] or 0,
                },
            }
        )
