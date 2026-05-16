from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    ApprovalDecisionViewSet,
    ApprovalRequestViewSet,
    AssignmentViewSet,
    ConflictViewSet,
    DashboardSituationView,
    ExportJobViewSet,
    OverrideRequestViewSet,
    PlanVersionViewSet,
    PlanViewSet,
    PublishedPlanSnapshotViewSet,
    ScheduleEventViewSet,
    SchedulingOverviewViewSet,
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

overview = SchedulingOverviewViewSet.as_view({"get": "overview"})

urlpatterns = [
    path("dashboard/situation/", DashboardSituationView.as_view(), name="dashboard-situation"),
    path("scheduling/overview/", overview, name="scheduling-overview"),
    *router.urls,
]
