from rest_framework import serializers

from .models import FlowDefinition, FlowEvent, FlowRun, FlowStepRun


class FlowDefinitionSummarySerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowDefinition
        fields = ["flow_key", "name", "description", "version", "status", "entry_route"]


class FlowStepRunSerializer(serializers.ModelSerializer):
    class Meta:
        model = FlowStepRun
        fields = [
            "id",
            "sequence",
            "step_key",
            "status",
            "expected_route",
            "expected_action_id",
            "blocked_reason",
            "completed_at",
            "evidence",
        ]


class FlowEventSerializer(serializers.ModelSerializer):
    actor_username = serializers.CharField(source="actor.username", read_only=True)

    class Meta:
        model = FlowEvent
        fields = [
            "id",
            "event_id",
            "step_key",
            "event_type",
            "actor",
            "actor_username",
            "route",
            "action_id",
            "object_type",
            "object_id",
            "metadata",
            "created_at",
        ]
        read_only_fields = fields


class FlowRunSerializer(serializers.ModelSerializer):
    flow_definition = FlowDefinitionSummarySerializer(read_only=True)
    step_runs = FlowStepRunSerializer(many=True, read_only=True)
    recent_events = serializers.SerializerMethodField()

    class Meta:
        model = FlowRun
        fields = [
            "id",
            "run_id",
            "flow_definition",
            "status",
            "current_step_key",
            "subject_type",
            "subject_id",
            "started_by",
            "started_at",
            "completed_at",
            "metadata",
            "created_at",
            "updated_at",
            "step_runs",
            "recent_events",
        ]
        read_only_fields = fields

    def get_recent_events(self, obj):
        events = obj.events.select_related("actor").order_by("-created_at", "-id")[:20]
        return FlowEventSerializer(events, many=True).data


class ActiveFlowResponseSerializer(serializers.Serializer):
    flow = FlowRunSerializer(allow_null=True)


class FlowEventCreateSerializer(serializers.Serializer):
    step_key = serializers.CharField(max_length=120)
    action_id = serializers.CharField(max_length=120)
    route = serializers.CharField(max_length=180)
    object_type = serializers.CharField(max_length=80, required=False, allow_blank=True)
    object_id = serializers.CharField(max_length=80, required=False, allow_blank=True)
    metadata = serializers.JSONField(required=False, default=dict)
