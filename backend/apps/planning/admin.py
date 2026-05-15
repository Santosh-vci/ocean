from django.contrib import admin

from .models import (
    AssetAvailabilityWindow,
    BridgeWindow,
    CargoLayerStep,
    CargoRequirement,
    ImportJob,
    JettyAvailabilityWindow,
    NavigationConstraintCheck,
    OGVVoyage,
    TideWindow,
)


@admin.register(OGVVoyage)
class OGVVoyageAdmin(admin.ModelAdmin):
    list_display = ("voyage_id", "vessel_name", "customer_name", "status", "risk_status")
    list_filter = ("status", "risk_status", "organization")
    search_fields = ("voyage_id", "vessel_name", "customer_name")


@admin.register(CargoRequirement)
class CargoRequirementAdmin(admin.ModelAdmin):
    list_display = ("voyage", "coal_grade", "required_mt", "status")
    list_filter = ("status", "coal_grade")
    search_fields = ("voyage__voyage_id", "voyage__vessel_name", "coal_grade__code")


@admin.register(CargoLayerStep)
class CargoLayerStepAdmin(admin.ModelAdmin):
    list_display = ("voyage", "hatch_no", "layer_no", "coal_grade", "status", "sequence_violation")
    list_filter = ("status", "sequence_violation", "coal_grade")
    search_fields = ("voyage__voyage_id", "voyage__vessel_name", "blocking_reason")


admin.site.register(AssetAvailabilityWindow)
admin.site.register(JettyAvailabilityWindow)
admin.site.register(TideWindow)
admin.site.register(BridgeWindow)
admin.site.register(NavigationConstraintCheck)
admin.site.register(ImportJob)
