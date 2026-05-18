from rest_framework.routers import DefaultRouter

from .views import (
    ConfirmedOperationalEventViewSet,
    DeviceEndpointViewSet,
    DeviceHealthSnapshotViewSet,
    EdgeEventBatchViewSet,
    IntegrationFeedViewSet,
    OperationalActualizationViewSet,
    OperationalEventCandidateViewSet,
    OperationsOverviewViewSet,
)

router = DefaultRouter()
router.register("operations/feeds", IntegrationFeedViewSet, basename="operations-feed")
router.register("operations/devices", DeviceEndpointViewSet, basename="operations-device")
router.register(
    "operations/device-health",
    DeviceHealthSnapshotViewSet,
    basename="operations-device-health",
)
router.register(
    "operations/event-candidates",
    OperationalEventCandidateViewSet,
    basename="operations-event-candidate",
)
router.register(
    "operations/confirmed-events",
    ConfirmedOperationalEventViewSet,
    basename="operations-confirmed-event",
)
router.register(
    "operations/actualizations",
    OperationalActualizationViewSet,
    basename="operations-actualization",
)
router.register("operations/edge-batches", EdgeEventBatchViewSet, basename="operations-edge-batch")
router.register("operations/overview", OperationsOverviewViewSet, basename="operations-overview")

urlpatterns = router.urls
