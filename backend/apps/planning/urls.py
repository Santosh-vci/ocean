from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AssetAvailabilityWindowViewSet,
    BridgeWindowViewSet,
    CargoLayerStepViewSet,
    CargoRequirementViewSet,
    ImportJobViewSet,
    JettyAvailabilityWindowViewSet,
    NavigationConstraintCheckViewSet,
    OGVVoyageViewSet,
    PlanningOverviewViewSet,
    TideWindowViewSet,
)

router = DefaultRouter()
router.register("planning/ogv-voyages", OGVVoyageViewSet, basename="ogv-voyage")
router.register(
    "planning/cargo-requirements",
    CargoRequirementViewSet,
    basename="cargo-requirement",
)
router.register("planning/cargo-layer-steps", CargoLayerStepViewSet, basename="cargo-layer-step")
router.register(
    "planning/asset-availability",
    AssetAvailabilityWindowViewSet,
    basename="asset-availability",
)
router.register(
    "planning/jetty-availability",
    JettyAvailabilityWindowViewSet,
    basename="jetty-availability",
)
router.register("planning/tide-windows", TideWindowViewSet, basename="tide-window")
router.register("planning/bridge-windows", BridgeWindowViewSet, basename="bridge-window")
router.register(
    "planning/constraint-checks",
    NavigationConstraintCheckViewSet,
    basename="constraint-check",
)
router.register("planning/import-jobs", ImportJobViewSet, basename="planning-import-job")

overview = PlanningOverviewViewSet.as_view({"get": "overview"})

urlpatterns = [
    path("planning/overview/", overview, name="planning-overview"),
    *router.urls,
]
