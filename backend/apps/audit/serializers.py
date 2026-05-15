from rest_framework import serializers

from apps.organizations.serializers import OrganizationSerializer

from .models import AuditEvent


class AuditEventSerializer(serializers.ModelSerializer):
    actor = serializers.SerializerMethodField()
    organization = OrganizationSerializer(read_only=True)

    class Meta:
        model = AuditEvent
        fields = (
            "id",
            "actor",
            "organization",
            "action",
            "object_type",
            "object_id",
            "object_repr",
            "metadata",
            "request_id",
            "ip_address",
            "created_at",
        )

    def get_actor(self, obj) -> dict | None:
        if obj.actor is None:
            return None

        return {
            "id": obj.actor_id,
            "username": obj.actor.get_username(),
            "email": obj.actor.email,
        }

