from rest_framework.routers import DefaultRouter

from .views import (
    AssetIdentityViewSet,
    GeofenceZoneViewSet,
    LatestAssetStateViewSet,
    LiveEtaProjectionViewSet,
    MovementEventViewSet,
    PositionPingViewSet,
    TelemetryReplayRunViewSet,
    TelemetrySourceViewSet,
    TelemetryTrustAssessmentViewSet,
    TelemetryTrustProfileViewSet,
    TrackingAlertViewSet,
)

router = DefaultRouter()
router.register("telemetry/sources", TelemetrySourceViewSet, basename="telemetry-source")
router.register("telemetry/asset-identities", AssetIdentityViewSet, basename="asset-identity")
router.register("telemetry/position-pings", PositionPingViewSet, basename="position-ping")
router.register("telemetry/geofence-zones", GeofenceZoneViewSet, basename="geofence-zone")
router.register(
    "telemetry/latest-asset-states",
    LatestAssetStateViewSet,
    basename="latest-asset-state",
)
router.register("telemetry/movement-events", MovementEventViewSet, basename="movement-event")
router.register("telemetry/eta-projections", LiveEtaProjectionViewSet, basename="eta-projection")
router.register("telemetry/alerts", TrackingAlertViewSet, basename="tracking-alert")
router.register("telemetry/trust-profiles", TelemetryTrustProfileViewSet, basename="telemetry-trust-profile")
router.register(
    "telemetry/trust-assessments",
    TelemetryTrustAssessmentViewSet,
    basename="telemetry-trust-assessment",
)
router.register("telemetry/replay-runs", TelemetryReplayRunViewSet, basename="replay-run")

urlpatterns = router.urls
