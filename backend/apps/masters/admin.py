from django.contrib import admin

from .models import (
    AssetCompatibilityRule,
    Barge,
    CoalGrade,
    CTSAsset,
    Jetty,
    LoadingRateProfile,
    Location,
    Mine,
    Route,
    RouteSegment,
    Stockpile,
    Tug,
)


class MasterAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "organization", "is_active", "updated_at")
    list_filter = ("is_active", "organization")
    search_fields = ("code", "name")


admin.site.register(Location, MasterAdmin)
admin.site.register(CoalGrade, MasterAdmin)
admin.site.register(Mine, MasterAdmin)
admin.site.register(Stockpile, MasterAdmin)
admin.site.register(Jetty, MasterAdmin)
admin.site.register(Tug, MasterAdmin)
admin.site.register(Barge, MasterAdmin)
admin.site.register(CTSAsset, MasterAdmin)
admin.site.register(Route, MasterAdmin)
admin.site.register(LoadingRateProfile, MasterAdmin)
admin.site.register(AssetCompatibilityRule, MasterAdmin)


@admin.register(RouteSegment)
class RouteSegmentAdmin(admin.ModelAdmin):
    list_display = ("route", "sequence", "from_location", "to_location")
    list_filter = ("requires_tide_window", "requires_bridge_window")
    search_fields = ("route__code", "from_location", "to_location")
