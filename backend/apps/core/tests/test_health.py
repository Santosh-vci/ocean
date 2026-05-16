import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.urls import reverse
from rest_framework.test import APIClient

User = get_user_model()


def test_health_endpoint(client):
    response = client.get(reverse("health"))

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "coalflow-api"}


@pytest.mark.django_db
def test_metrics_are_admin_only():
    call_command("seed_phase0")
    client = APIClient()

    forbidden = client.get("/api/metrics/")
    client.force_login(User.objects.get(username="admin@coalflow.local"))
    allowed = client.get("/api/metrics/")

    assert forbidden.status_code == 403
    assert allowed.status_code == 200
    assert allowed.json()["domain"]["planVersions"] >= 1


def test_sensitive_log_redaction_masks_credentials():
    from apps.core.logging import redact_sensitive

    redacted = redact_sensitive(
        "authorization=Bearer abc123 password: admin12345 token secret-value"
    )

    assert "abc123" not in redacted
    assert "admin12345" not in redacted
    assert "secret-value" not in redacted
    assert redacted.count("[REDACTED]") == 3
