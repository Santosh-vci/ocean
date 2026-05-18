from django.contrib import admin

from .models import (
    ConfirmedOperationalEvent,
    DeviceEndpoint,
    DeviceHealthSnapshot,
    EdgeEventBatch,
    IntegrationFeed,
    OperationalActualization,
    OperationalEventCandidate,
)


@admin.register(IntegrationFeed)
class IntegrationFeedAdmin(admin.ModelAdmin):
    list_display = ("feed_id", "feed_type", "status", "trust_mode", "freshness_threshold_seconds")
    search_fields = ("feed_id", "name")
    list_filter = ("feed_type", "status", "trust_mode")


@admin.register(DeviceEndpoint)
class DeviceEndpointAdmin(admin.ModelAdmin):
    list_display = ("device_id", "device_type", "asset_code", "feed", "status", "last_seen_at")
    search_fields = ("device_id", "asset_code", "feed__feed_id")
    list_filter = ("device_type", "status", "asset_type")


@admin.register(DeviceHealthSnapshot)
class DeviceHealthSnapshotAdmin(admin.ModelAdmin):
    list_display = ("snapshot_id", "device", "health_status", "observed_at", "received_at")
    search_fields = ("snapshot_id", "device__device_id")
    list_filter = ("health_status",)


@admin.register(OperationalEventCandidate)
class OperationalEventCandidateAdmin(admin.ModelAdmin):
    list_display = ("candidate_id", "event_kind", "asset_code", "status", "event_at", "feed")
    search_fields = ("candidate_id", "asset_code", "dedupe_key", "feed__feed_id")
    list_filter = ("event_kind", "source_kind", "status", "asset_type")


@admin.register(ConfirmedOperationalEvent)
class ConfirmedOperationalEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "event_kind", "actual_at", "confirmed_by", "confirmation_mode")
    search_fields = ("event_id", "candidate__candidate_id", "trip__trip_id")
    list_filter = ("event_kind", "confirmation_mode")


@admin.register(OperationalActualization)
class OperationalActualizationAdmin(admin.ModelAdmin):
    list_display = ("actualization_id", "confirmed_event", "target_type", "target_id", "status")
    search_fields = ("actualization_id", "confirmed_event__event_id", "target_id")
    list_filter = ("target_type", "status")


@admin.register(EdgeEventBatch)
class EdgeEventBatchAdmin(admin.ModelAdmin):
    list_display = ("batch_id", "feed", "device", "status", "message_count", "received_at")
    search_fields = ("batch_id", "batch_sequence", "feed__feed_id", "device__device_id")
    list_filter = ("status",)
