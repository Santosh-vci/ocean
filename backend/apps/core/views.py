from django.conf import settings
from django.contrib.auth.models import AnonymousUser
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_GET

from apps.core.object_storage import export_storage_health
from apps.rbac.services import user_has_permission_code


@require_GET
def health(request):
    return JsonResponse(
        {
            "status": "ok",
            "service": "coalflow-api",
        }
    )


@require_GET
def readiness(request):
    checks = {
        "database": _database_ready(),
        "cache": _cache_ready(),
        "exportStorage": _export_storage_ready(),
    }
    ready = all(item["ok"] for item in checks.values())
    return JsonResponse(
        {
            "status": "ready" if ready else "degraded",
            "service": "coalflow-api",
            "checks": checks,
        },
        status=200 if ready else 503,
    )


@require_GET
def metrics(request):
    user = getattr(request, "user", AnonymousUser())
    if not user.is_authenticated or not user_has_permission_code(user, "admin.view"):
        return JsonResponse({"detail": "Forbidden"}, status=403)

    from apps.audit.models import AuditEvent
    from apps.masters.models import Barge, CTSAsset, Jetty, Tug
    from apps.planning.models import ImportJob, OGVVoyage
    from apps.scheduling.models import Conflict, ExportJob, PlanVersion, PublishedPlanSnapshot

    return JsonResponse(
        {
            "service": "coalflow-api",
            "runtime": {
                "debug": settings.DEBUG,
                "timeZone": settings.TIME_ZONE,
            },
            "domain": {
                "voyages": OGVVoyage.objects.count(),
                "planVersions": PlanVersion.objects.count(),
                "activePublishedSnapshots": PublishedPlanSnapshot.objects.filter(
                    status=PublishedPlanSnapshot.Status.ACTIVE
                ).count(),
                "openBlockingConflicts": Conflict.objects.filter(
                    is_blocking=True,
                    resolved_at__isnull=True,
                ).count(),
                "imports": ImportJob.objects.count(),
                "exports": ExportJob.objects.count(),
                "auditEvents": AuditEvent.objects.count(),
            },
            "resources": {
                "tugs": Tug.objects.count(),
                "barges": Barge.objects.count(),
                "jetties": Jetty.objects.count(),
                "ctsAssets": CTSAsset.objects.count(),
            },
        }
    )


def _database_ready() -> dict:
    try:
        with connection.cursor() as cursor:
            cursor.execute("select 1")
            cursor.fetchone()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": exc.__class__.__name__}


def _cache_ready() -> dict:
    try:
        import redis

        client = redis.Redis.from_url(settings.CELERY_BROKER_URL, socket_connect_timeout=1)
        client.ping()
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": exc.__class__.__name__}


def _export_storage_ready() -> dict:
    try:
        status = export_storage_health()
        return {"ok": bool(status["writable"]), **status}
    except Exception as exc:
        return {"ok": False, "error": exc.__class__.__name__}
