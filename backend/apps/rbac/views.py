from django.contrib.auth import authenticate, get_user_model, login, logout
from django.middleware.csrf import get_token
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.audit.models import AuditEvent
from apps.audit.services import record_audit_event
from apps.organizations.models import Organization
from apps.organizations.serializers import OrganizationSerializer

from .models import AccessPermission, DataScope, Role, UserRoleAssignment
from .permissions import RequiresAccessPermission
from .serializers import (
    AccessPermissionSerializer,
    DataScopeSerializer,
    MeSerializer,
    RoleSerializer,
    UserSummarySerializer,
)

User = get_user_model()


@api_view(["GET"])
@permission_classes([AllowAny])
def csrf(request):
    return Response({"csrfToken": get_token(request)})


@api_view(["POST"])
@permission_classes([AllowAny])
def login_view(request):
    username = request.data.get("username")
    password = request.data.get("password")

    user = authenticate(request, username=username, password=password)
    if user is None:
        return Response({"detail": "Invalid credentials."}, status=status.HTTP_400_BAD_REQUEST)

    login(request, user)
    record_audit_event(
        actor=user,
        organization=None,
        action="auth.login",
        object_type="user",
        object_id=str(user.pk),
        object_repr=user.get_username(),
        request=request,
    )
    return Response(MeSerializer(user).data)


@api_view(["POST"])
@permission_classes([IsAuthenticated])
def logout_view(request):
    user = request.user
    record_audit_event(
        actor=user,
        organization=None,
        action="auth.logout",
        object_type="user",
        object_id=str(user.pk),
        object_repr=user.get_username(),
        request=request,
    )
    logout(request)
    return Response(status=status.HTTP_204_NO_CONTENT)


@api_view(["GET"])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(MeSerializer(request.user).data)


class RoleViewSet(ReadOnlyModelViewSet):
    queryset = Role.objects.prefetch_related("permissions", "organization").all()
    serializer_class = RoleSerializer
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "admin.view",
        "retrieve": "admin.view",
    }


class AccessPermissionViewSet(ReadOnlyModelViewSet):
    queryset = AccessPermission.objects.all()
    serializer_class = AccessPermissionSerializer
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "admin.view",
        "retrieve": "admin.view",
    }


class DataScopeViewSet(ReadOnlyModelViewSet):
    queryset = DataScope.objects.select_related("organization").all()
    serializer_class = DataScopeSerializer
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "admin.view",
        "retrieve": "admin.view",
    }


class UserViewSet(ReadOnlyModelViewSet):
    queryset = User.objects.prefetch_related(
        "organization_memberships__organization",
        "role_assignments__role__permissions",
        "role_assignments__organization",
        "role_assignments__data_scope__organization",
    ).all()
    serializer_class = UserSummarySerializer
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {
        "list": "admin.view",
        "retrieve": "admin.view",
    }


class RbacOverviewView(APIView):
    permission_classes = [RequiresAccessPermission]
    action_permission_map = {"get": "admin.view"}

    def get(self, request):
        users = UserViewSet.queryset
        roles = RoleViewSet.queryset
        permissions = AccessPermission.objects.all()
        organizations = Organization.objects.all()
        scopes = DataScopeViewSet.queryset

        return Response(
            {
                "users": UserSummarySerializer(users, many=True).data,
                "roles": RoleSerializer(roles, many=True).data,
                "permissions": AccessPermissionSerializer(permissions, many=True).data,
                "organizations": OrganizationSerializer(organizations, many=True).data,
                "scopes": DataScopeSerializer(scopes, many=True).data,
                "assignmentCount": UserRoleAssignment.objects.filter(is_active=True).count(),
                "auditEventCount": AuditEvent.objects.count(),
            }
        )

