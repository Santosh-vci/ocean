from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AssetCompatibilityRuleViewSet,
    BargeViewSet,
    CoalGradeViewSet,
    CTSAssetViewSet,
    JettyViewSet,
    LoadingRateProfileViewSet,
    LocationViewSet,
    MasterDataOverviewViewSet,
    MineViewSet,
    RouteSegmentViewSet,
    RouteViewSet,
    StockpileViewSet,
    TugViewSet,
)

router = DefaultRouter()
router.register("master-data/locations", LocationViewSet, basename="location")
router.register("master-data/coal-grades", CoalGradeViewSet, basename="coal-grade")
router.register("master-data/mines", MineViewSet, basename="mine")
router.register("master-data/stockpiles", StockpileViewSet, basename="stockpile")
router.register("master-data/jetties", JettyViewSet, basename="jetty")
router.register("master-data/tugs", TugViewSet, basename="tug")
router.register("master-data/barges", BargeViewSet, basename="barge")
router.register("master-data/cts-assets", CTSAssetViewSet, basename="cts-asset")
router.register("master-data/routes", RouteViewSet, basename="route")
router.register("master-data/route-segments", RouteSegmentViewSet, basename="route-segment")
router.register(
    "master-data/loading-rate-profiles",
    LoadingRateProfileViewSet,
    basename="loading-rate-profile",
)
router.register(
    "master-data/compatibility-rules",
    AssetCompatibilityRuleViewSet,
    basename="compatibility-rule",
)

overview = MasterDataOverviewViewSet.as_view({"get": "overview"})

urlpatterns = [
    path("master-data/overview/", overview, name="master-data-overview"),
    *router.urls,
]
