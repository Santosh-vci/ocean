from collections.abc import Mapping

from django.contrib.auth import get_user_model

from apps.organizations.models import Organization

from .models import AuditEvent

User = get_user_model()


def record_audit_event(
    *,
    actor: User | None,
    organization: Organization | None,
    action: str,
    object_type: str,
    object_id: str,
    object_repr: str = "",
    metadata: Mapping | None = None,
    request=None,
) -> AuditEvent:
    request_id = getattr(request, "request_id", None)
    ip_address = None
    if request is not None:
        ip_address = request.META.get("REMOTE_ADDR")

    return AuditEvent.objects.create(
        actor=actor,
        organization=organization,
        action=action,
        object_type=object_type,
        object_id=object_id,
        object_repr=object_repr,
        metadata=dict(metadata or {}),
        request_id=request_id,
        ip_address=ip_address,
    )

