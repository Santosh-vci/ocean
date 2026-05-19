from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.organizations.models import Organization
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import (
    OptimizerRun,
    Plan,
    PlanVersion,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
)

NEXT_ACTIONS_URL = "/api/assistant/next-actions/"


def assign(user, organization, permission_codes, *, role_code="berau-scheduler"):
    permissions = []
    for code in permission_codes:
        permission, _ = AccessPermission.objects.get_or_create(
            code=code,
            defaults={
                "module": code.split(".")[0],
                "action": code.split(".")[1],
                "description": code,
            },
        )
        permissions.append(permission)
    role = Role.objects.create(
        name=f"{role_code}-{user.username}",
        code=f"{role_code}-{user.username}",
    )
    role.permissions.set(permissions)
    scope = DataScope.objects.create(
        name=f"scope-{user.username}",
        code=f"scope-{user.username}",
        scope_type=DataScope.ScopeType.ALL_NETWORK,
    )
    UserRoleAssignment.objects.create(
        user=user,
        role=role,
        organization=organization,
        data_scope=scope,
    )


def make_org(slug):
    return Organization.objects.create(name=slug, slug=slug, kind=Organization.Kind.BERAU)


def make_user(slug, permissions=("schedule.view", "schedule.edit")):
    org = make_org(slug)
    user = User.objects.create_user(username=slug, password="secret")
    assign(user, org, permissions)
    return user, org


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def make_plan_version(org, *, status=PlanVersion.Status.GENERATED):
    now = timezone.now()
    plan = Plan.objects.create(
        code=f"PLAN-{org.slug}",
        name="Assistant API Plan",
        organization=org,
        horizon_start=now,
        horizon_end=now + timedelta(days=3),
    )
    return PlanVersion.objects.create(
        plan=plan,
        version_no=1,
        status=status,
        generated_at=now,
    )


def make_phase5_recommendation(org, *, status=RecoveryRecommendation.Status.CANDIDATE):
    version = make_plan_version(org)
    snapshot = RecoveryInputSnapshot.objects.create(
        plan_version=version,
        source_kind=RecoveryInputSnapshot.SourceKind.CONFLICT,
        source_ref="EX-API-1",
    )
    run = OptimizerRun.objects.create(
        input_snapshot=snapshot,
        plan_version=version,
        status=OptimizerRun.Status.SUCCEEDED,
        algorithm_version="test-api",
    )
    recommendation = RecoveryRecommendation.objects.create(
        optimizer_run=run,
        rank=1,
        status=status,
        risk_level=RecoveryRecommendation.RiskLevel.LOW,
        score="92.000",
        summary="Use the best feasible recovery option.",
    )
    return recommendation


@pytest.mark.django_db
def test_next_actions_requires_authentication():
    response = APIClient().get(NEXT_ACTIONS_URL)

    assert response.status_code in {401, 403}


@pytest.mark.django_db
def test_authenticated_next_actions_returns_contract_shape():
    user, _org = make_user("assistant-api-contract")

    response = client_for(user).get(
        NEXT_ACTIONS_URL,
        {"route": "/dashboard/situation", "limit": "3"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert set(payload) == {
        "generated_at",
        "mode",
        "context",
        "global_next_action",
        "page_actions",
        "row_actions",
        "blocked_actions",
        "checklist",
    }
    assert payload["mode"] == "assisted"
    assert payload["context"]["route"] == "/dashboard/situation"
    assert payload["global_next_action"]["action_id"] == "IMPORT_OGV_DEMAND"
    assert payload["global_next_action"]["target_object_id"] is None
    assert isinstance(payload["page_actions"], list)
    assert isinstance(payload["row_actions"], list)
    assert isinstance(payload["blocked_actions"], list)
    assert isinstance(payload["checklist"], list)
    assert payload["checklist"][0]["key"] == "demand_imported"
    assert payload["checklist"][0]["action_id"] == "IMPORT_OGV_DEMAND"


@pytest.mark.django_db
def test_mode_off_returns_empty_recommendations():
    user, _org = make_user("assistant-api-off")

    response = client_for(user).get(
        NEXT_ACTIONS_URL,
        {"route": "/dashboard/situation", "mode": "off"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "off"
    assert payload["global_next_action"] is None
    assert payload["page_actions"] == []
    assert payload["row_actions"] == []
    assert payload["blocked_actions"] == []
    assert payload["checklist"] == []


@pytest.mark.django_db
def test_guided_mode_returns_checklist_without_requiring_guided_ui():
    user, _org = make_user("assistant-api-guided")

    response = client_for(user).get(
        NEXT_ACTIONS_URL,
        {"route": "/dashboard/situation", "mode": "guided"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["mode"] == "guided"
    assert [item["key"] for item in payload["checklist"][:4]] == [
        "demand_imported",
        "cargo_sequence_reviewed",
        "operating_windows_entered",
        "plan_generated",
    ]


@pytest.mark.django_db
def test_unknown_route_returns_global_recommendations_without_crashing():
    user, _org = make_user("assistant-api-unknown-route")

    response = client_for(user).get(NEXT_ACTIONS_URL, {"route": "/unknown/route"})

    assert response.status_code == 200
    payload = response.json()
    assert payload["context"]["route"] == "/unknown/route"
    assert payload["global_next_action"]["action_id"] == "IMPORT_OGV_DEMAND"
    assert payload["page_actions"] == []
    assert payload["row_actions"] == []


@pytest.mark.django_db
def test_unknown_object_returns_no_row_actions_without_crashing():
    user, org = make_user("assistant-api-unknown-object")
    make_phase5_recommendation(org)

    response = client_for(user).get(
        NEXT_ACTIONS_URL,
        {
            "route": "/recovery/recommendations",
            "object_type": "recovery_recommendation",
            "object_id": "999999",
        },
    )

    assert response.status_code == 200
    assert response.json()["row_actions"] == []


@pytest.mark.django_db
def test_recovery_route_returns_phase5_page_actions():
    user, org = make_user("assistant-api-phase5-page")
    make_phase5_recommendation(org)

    response = client_for(user).get(
        NEXT_ACTIONS_URL,
        {"route": "/recovery/recommendations"},
    )

    assert response.status_code == 200
    action_ids = [item["action_id"] for item in response.json()["page_actions"]]
    assert "OPEN_RECOMMENDATION_CONSOLE" in action_ids
    assert "MATERIALIZE_RECOVERY_RECOMMENDATION" in action_ids
    assert "DISMISS_RECOVERY_RECOMMENDATION" in action_ids


@pytest.mark.django_db
def test_recovery_recommendation_object_returns_row_actions():
    user, org = make_user("assistant-api-phase5-row")
    recommendation = make_phase5_recommendation(org)

    response = client_for(user).get(
        NEXT_ACTIONS_URL,
        {
            "route": "/recovery/recommendations",
            "object_type": "recovery_recommendation",
            "object_id": recommendation.id,
        },
    )

    assert response.status_code == 200
    row_action_ids = [item["action_id"] for item in response.json()["row_actions"]]
    assert row_action_ids == [
        "MATERIALIZE_RECOVERY_RECOMMENDATION",
        "DISMISS_RECOVERY_RECOMMENDATION",
    ]


@pytest.mark.django_db
def test_repeated_next_actions_are_deterministic_for_same_state():
    user, org = make_user("assistant-api-deterministic")
    make_phase5_recommendation(org)
    client = client_for(user)

    first = client.get(NEXT_ACTIONS_URL, {"route": "/recovery/recommendations"}).json()
    second = client.get(NEXT_ACTIONS_URL, {"route": "/recovery/recommendations"}).json()

    assert first["global_next_action"]["action_id"] == second["global_next_action"]["action_id"]
    assert [item["action_id"] for item in first["page_actions"]] == [
        item["action_id"] for item in second["page_actions"]
    ]


@pytest.mark.django_db
def test_next_actions_endpoint_does_not_mutate_business_tables():
    user, org = make_user("assistant-api-readonly")
    make_phase5_recommendation(org)
    before = _business_counts()

    response = client_for(user).get(
        NEXT_ACTIONS_URL,
        {"route": "/recovery/recommendations"},
    )

    assert response.status_code == 200
    assert _business_counts() == before


@pytest.mark.django_db
def test_next_actions_endpoint_rejects_mutating_methods():
    user, _org = make_user("assistant-api-method-guard")

    response = client_for(user).post(
        NEXT_ACTIONS_URL,
        {"route": "/recovery/recommendations"},
        format="json",
    )

    assert response.status_code == 405


def _business_counts():
    return {
        "plan_versions": PlanVersion.objects.count(),
        "snapshots": RecoveryInputSnapshot.objects.count(),
        "optimizer_runs": OptimizerRun.objects.count(),
        "recommendations": RecoveryRecommendation.objects.count(),
    }
