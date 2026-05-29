from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ApprovalDecisionViewSet,
    ApprovalRequestViewSet,
    AssignmentViewSet,
    ConflictViewSet,
    DashboardSituationView,
    ExportJobViewSet,
    GlobalOptimizationCandidateViewSet,
    GlobalOptimizationRunViewSet,
    OptimizerRunViewSet,
    OverrideRequestViewSet,
    PlanVersionViewSet,
    PlanViewSet,
    PublishedPlanSnapshotViewSet,
    RecommendationEvaluationViewSet,
    RecoveryActionViewSet,
    RecoveryInputSnapshotViewSet,
    RecoveryRecommendationViewSet,
    ScheduleEventViewSet,
    SchedulingOverviewViewSet,
    ScenarioRunViewSet,
    SimulationScenarioViewSet,
    TripViewSet,
)

router = DefaultRouter()
router.register("scheduling/plans", PlanViewSet, basename="plan")
router.register("scheduling/plan-versions", PlanVersionViewSet, basename="plan-version")
router.register("scheduling/trips", TripViewSet, basename="trip")
router.register("scheduling/assignments", AssignmentViewSet, basename="assignment")
router.register("scheduling/schedule-events", ScheduleEventViewSet, basename="schedule-event")
router.register("scheduling/conflicts", ConflictViewSet, basename="conflict")
router.register("scheduling/overrides", OverrideRequestViewSet, basename="override")
router.register("scheduling/approval-requests", ApprovalRequestViewSet, basename="approval-request")
router.register(
    "scheduling/approval-decisions",
    ApprovalDecisionViewSet,
    basename="approval-decision",
)
router.register(
    "scheduling/published-snapshots",
    PublishedPlanSnapshotViewSet,
    basename="published-snapshot",
)
router.register("exports", ExportJobViewSet, basename="export")
router.register("scheduling/scenarios", SimulationScenarioViewSet, basename="simulation-scenario")
router.register("scheduling/scenario-runs", ScenarioRunViewSet, basename="scenario-run")
router.register(
    "scheduling/recovery-input-snapshots",
    RecoveryInputSnapshotViewSet,
    basename="recovery-input-snapshot",
)
router.register("scheduling/optimizer-runs", OptimizerRunViewSet, basename="optimizer-run")
router.register("scheduling/recovery-runs", OptimizerRunViewSet, basename="recovery-run")
router.register(
    "scheduling/global-optimization-runs",
    GlobalOptimizationRunViewSet,
    basename="global-optimization-run",
)
router.register(
    "scheduling/global-optimization-candidates",
    GlobalOptimizationCandidateViewSet,
    basename="global-optimization-candidate",
)
router.register(
    "scheduling/recovery-recommendations",
    RecoveryRecommendationViewSet,
    basename="recovery-recommendation",
)
router.register(
    "scheduling/recommendations",
    RecoveryRecommendationViewSet,
    basename="recommendation",
)
router.register("scheduling/recovery-actions", RecoveryActionViewSet, basename="recovery-action")
router.register(
    "scheduling/recommendation-evaluations",
    RecommendationEvaluationViewSet,
    basename="recommendation-evaluation",
)

overview = SchedulingOverviewViewSet.as_view({"get": "overview"})

urlpatterns = [
    path("dashboard/situation/", DashboardSituationView.as_view(), name="dashboard-situation"),
    path("scheduling/overview/", overview, name="scheduling-overview"),
    *router.urls,
]
