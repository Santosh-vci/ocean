from config.celery import app

from .services import refresh_signal_health


@app.task(name="telemetry.refresh_signal_health")
def refresh_signal_health_task() -> dict:
    return {"updated": refresh_signal_health()}
