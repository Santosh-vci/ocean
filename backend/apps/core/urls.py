from django.urls import path

from .views import health, metrics, readiness

urlpatterns = [
    path("health/", health, name="health"),
    path("ready/", readiness, name="readiness"),
    path("metrics/", metrics, name="metrics"),
]
