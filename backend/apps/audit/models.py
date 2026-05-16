from django.conf import settings
from django.db import models

from apps.organizations.models import Organization


class AuditEvent(models.Model):
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="audit_events",
    )
    action = models.CharField(max_length=160)
    object_type = models.CharField(max_length=160)
    object_id = models.CharField(max_length=160)
    object_repr = models.CharField(max_length=255, blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    request_id = models.UUIDField(null=True, blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=("action", "created_at")),
            models.Index(fields=("object_type", "object_id")),
            models.Index(fields=("organization", "created_at")),
            models.Index(fields=("actor", "created_at")),
            models.Index(fields=("request_id",)),
        ]

    def __str__(self) -> str:
        return f"{self.action} {self.object_type}:{self.object_id}"
