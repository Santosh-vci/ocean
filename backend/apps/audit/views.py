from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.rbac.permissions import RequiresAccessPermission

from .models import AuditEvent
from .serializers import AuditEventSerializer


class AuditEventViewSet(ReadOnlyModelViewSet):
    queryset = AuditEvent.objects.select_related("actor", "organization").all()
    serializer_class = AuditEventSerializer
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "audit.view",
        "retrieve": "audit.view",
    }

