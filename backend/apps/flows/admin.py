from django.contrib import admin

from .models import FlowDefinition, FlowEvent, FlowRun, FlowStepRun


@admin.register(FlowDefinition)
class FlowDefinitionAdmin(admin.ModelAdmin):
    list_display = ("flow_key", "name", "version", "status", "entry_route", "updated_at")
    list_filter = ("status", "version")
    search_fields = ("flow_key", "name", "description")
    readonly_fields = ("created_at", "updated_at")


@admin.register(FlowRun)
class FlowRunAdmin(admin.ModelAdmin):
    list_display = ("run_id", "flow_definition", "status", "current_step_key", "started_by")
    list_filter = ("status", "flow_definition")
    search_fields = ("run_id", "flow_definition__flow_key", "subject_type", "subject_id")
    readonly_fields = ("run_id", "created_at", "updated_at")


@admin.register(FlowStepRun)
class FlowStepRunAdmin(admin.ModelAdmin):
    list_display = ("flow_run", "sequence", "step_key", "status", "expected_action_id")
    list_filter = ("status", "expected_action_id")
    search_fields = ("flow_run__run_id", "step_key", "expected_action_id")
    readonly_fields = ("evidence", "created_at", "updated_at")


@admin.register(FlowEvent)
class FlowEventAdmin(admin.ModelAdmin):
    list_display = ("event_id", "flow_run", "step_key", "event_type", "actor", "created_at")
    list_filter = ("event_type",)
    search_fields = ("event_id", "flow_run__run_id", "step_key", "action_id")
    readonly_fields = ("event_id", "metadata", "created_at")
