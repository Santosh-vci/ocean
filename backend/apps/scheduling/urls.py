from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AssignmentViewSet,
    ConflictViewSet,
    PlanVersionViewSet,
    PlanViewSet,
    ScheduleEventViewSet,
    SchedulingOverviewViewSet,
    TripViewSet,
)

router = DefaultRouter()
router.register("scheduling/plans", PlanViewSet, basename="plan")
router.register("scheduling/plan-versions", PlanVersionViewSet, basename="plan-version")
router.register("scheduling/trips", TripViewSet, basename="trip")
router.register("scheduling/assignments", AssignmentViewSet, basename="assignment")
router.register("scheduling/schedule-events", ScheduleEventViewSet, basename="schedule-event")
router.register("scheduling/conflicts", ConflictViewSet, basename="conflict")

overview = SchedulingOverviewViewSet.as_view({"get": "overview"})

urlpatterns = [
    path("scheduling/overview/", overview, name="scheduling-overview"),
    *router.urls,
]
