from config.celery import app

from .models import PlanVersion
from .services import generate_plan_version


@app.task(name="scheduling.generate_plan_version")
def generate_plan_version_task(plan_version_id: int):
    plan_version = PlanVersion.objects.get(pk=plan_version_id)
    result = generate_plan_version(plan_version)
    return {
        "planVersionId": plan_version_id,
        "tripCount": result.trip_count,
        "conflictCount": result.conflict_count,
        "blockingConflictCount": result.blocking_conflict_count,
    }
