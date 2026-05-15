from django.contrib import admin

from .models import Assignment, Conflict, Plan, PlanVersion, ScheduleEvent, Trip


@admin.register(Plan)
class PlanAdmin(admin.ModelAdmin):
    list_display = ("code", "name", "horizon_start", "horizon_end", "status")
    list_filter = ("status", "organization")
    search_fields = ("code", "name")


@admin.register(PlanVersion)
class PlanVersionAdmin(admin.ModelAdmin):
    list_display = ("plan", "version_no", "status", "validation_status", "generated_at")
    list_filter = ("status", "validation_status")
    search_fields = ("plan__code",)


@admin.register(Trip)
class TripAdmin(admin.ModelAdmin):
    list_display = ("trip_id", "plan_version", "sequence", "voyage", "status")
    list_filter = ("status", "plan_version")
    search_fields = ("trip_id", "voyage__voyage_id", "voyage__vessel_name")


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ("trip", "tug", "barge", "jetty", "cts", "status")
    list_filter = ("status", "jetty", "cts")
    search_fields = ("trip__trip_id", "tug__code", "barge__code")


@admin.register(ScheduleEvent)
class ScheduleEventAdmin(admin.ModelAdmin):
    list_display = ("trip", "sequence", "event_type", "planned_at", "status")
    list_filter = ("event_type", "status")
    search_fields = ("trip__trip_id", "resource_code")


@admin.register(Conflict)
class ConflictAdmin(admin.ModelAdmin):
    list_display = ("code", "severity", "plan_version", "trip", "is_blocking")
    list_filter = ("code", "severity", "is_blocking")
    search_fields = ("code", "message", "trip__trip_id")
