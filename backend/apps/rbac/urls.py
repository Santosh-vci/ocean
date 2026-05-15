from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    AccessPermissionViewSet,
    DataScopeViewSet,
    RbacOverviewView,
    RoleViewSet,
    UserViewSet,
    csrf,
    login_view,
    logout_view,
    me,
)

router = DefaultRouter()
router.register("roles", RoleViewSet, basename="role")
router.register("permissions", AccessPermissionViewSet, basename="permission")
router.register("data-scopes", DataScopeViewSet, basename="data-scope")
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("auth/csrf/", csrf, name="csrf"),
    path("auth/login/", login_view, name="login"),
    path("auth/logout/", logout_view, name="logout"),
    path("me/", me, name="me"),
    path("rbac/overview/", RbacOverviewView.as_view(), name="rbac-overview"),
    *router.urls,
]

