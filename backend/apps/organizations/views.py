from rest_framework.viewsets import ModelViewSet

from apps.audit.mixins import AuditMutationMixin
from apps.rbac.permissions import RequiresAccessPermission

from .models import Organization
from .serializers import OrganizationSerializer


class OrganizationViewSet(AuditMutationMixin, ModelViewSet):
    queryset = Organization.objects.all()
    serializer_class = OrganizationSerializer
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "admin.view",
        "retrieve": "admin.view",
        "create": "admin.manage_users",
        "update": "admin.manage_users",
        "partial_update": "admin.manage_users",
        "destroy": "admin.manage_users",
    }
