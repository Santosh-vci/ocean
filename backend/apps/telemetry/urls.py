from rest_framework.routers import DefaultRouter

from .views import AssetIdentityViewSet, PositionPingViewSet, TelemetrySourceViewSet

router = DefaultRouter()
router.register("telemetry/sources", TelemetrySourceViewSet, basename="telemetry-source")
router.register("telemetry/asset-identities", AssetIdentityViewSet, basename="asset-identity")
router.register("telemetry/position-pings", PositionPingViewSet, basename="position-ping")

urlpatterns = router.urls
