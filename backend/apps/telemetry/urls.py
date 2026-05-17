from rest_framework.routers import DefaultRouter

from .views import (
    AssetIdentityViewSet,
    LatestAssetStateViewSet,
    PositionPingViewSet,
    TelemetrySourceViewSet,
)

router = DefaultRouter()
router.register("telemetry/sources", TelemetrySourceViewSet, basename="telemetry-source")
router.register("telemetry/asset-identities", AssetIdentityViewSet, basename="asset-identity")
router.register("telemetry/position-pings", PositionPingViewSet, basename="position-ping")
router.register(
    "telemetry/latest-asset-states",
    LatestAssetStateViewSet,
    basename="latest-asset-state",
)

urlpatterns = router.urls
