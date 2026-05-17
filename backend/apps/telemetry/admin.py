from django.contrib import admin

from .models import AssetIdentity, LatestAssetState, PositionPing, TelemetrySource


@admin.register(TelemetrySource)
class TelemetrySourceAdmin(admin.ModelAdmin):
    list_display = ("source_id", "source_type", "status", "freshness_threshold_seconds")
    search_fields = ("source_id", "name")
    list_filter = ("source_type", "status")


@admin.register(AssetIdentity)
class AssetIdentityAdmin(admin.ModelAdmin):
    list_display = ("asset_code", "asset_type", "source", "external_id", "external_id_type")
    search_fields = ("asset_code", "external_id", "source__source_id")
    list_filter = ("asset_type", "external_id_type", "is_primary")


@admin.register(PositionPing)
class PositionPingAdmin(admin.ModelAdmin):
    list_display = (
        "ping_id",
        "asset_code",
        "asset_type",
        "source",
        "device_timestamp",
        "signal_quality",
        "is_synthetic",
    )
    search_fields = ("ping_id", "asset_code", "source__source_id")
    list_filter = ("asset_type", "signal_quality", "is_synthetic")
    readonly_fields = ("created_at",)


@admin.register(LatestAssetState)
class LatestAssetStateAdmin(admin.ModelAdmin):
    list_display = (
        "asset_code",
        "asset_type",
        "freshness_status",
        "derived_status",
        "source",
        "last_seen_at",
        "confidence_score",
    )
    search_fields = ("asset_code", "source__source_id", "asset_identity__external_id")
    list_filter = ("asset_type", "freshness_status", "derived_status")
