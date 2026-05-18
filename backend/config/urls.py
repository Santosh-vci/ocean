from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("apps.core.urls")),
    path("api/", include("apps.organizations.urls")),
    path("api/", include("apps.rbac.urls")),
    path("api/", include("apps.audit.urls")),
    path("api/", include("apps.masters.urls")),
    path("api/", include("apps.planning.urls")),
    path("api/", include("apps.scheduling.urls")),
    path("api/", include("apps.telemetry.urls")),
    path("api/", include("apps.operations.urls")),
    path("api/", include("apps.assistant.urls")),
]
