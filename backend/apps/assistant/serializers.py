from rest_framework import serializers


class ActionRecommendationSerializer(serializers.Serializer):
    action_id = serializers.CharField()
    label = serializers.CharField()
    priority = serializers.CharField()
    rank_score = serializers.IntegerField()
    enabled = serializers.BooleanField()
    route = serializers.CharField()
    cta_label = serializers.CharField()
    reason = serializers.CharField()
    hover_hint = serializers.CharField(allow_blank=True)
    detail_text = serializers.CharField(allow_blank=True)
    impact_if_ignored = serializers.CharField(allow_blank=True)
    owner_role = serializers.CharField(allow_blank=True)
    required_permission = serializers.CharField(allow_null=True)
    audit_required = serializers.BooleanField()
    target_object_type = serializers.CharField(allow_null=True)
    target_object_id = serializers.CharField(allow_null=True)
    blocked_reason = serializers.CharField(allow_blank=True)
    source = serializers.CharField()
    expires_at = serializers.DateTimeField(allow_null=True)
    metadata = serializers.DictField()


class NextActionsResponseSerializer(serializers.Serializer):
    generated_at = serializers.DateTimeField()
    mode = serializers.CharField()
    context = serializers.DictField()
    global_next_action = ActionRecommendationSerializer(allow_null=True)
    page_actions = ActionRecommendationSerializer(many=True)
    row_actions = ActionRecommendationSerializer(many=True)
    blocked_actions = ActionRecommendationSerializer(many=True)
    checklist = serializers.ListField(child=serializers.DictField())
