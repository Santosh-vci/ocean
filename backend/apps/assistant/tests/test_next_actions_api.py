from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.flows.definitions import seed_canonical_flow_definitions
from apps.flows.models import FlowEvent, FlowRun, FlowStepRun
from apps.flows.services import start_flow
from apps.organizations.models import Organization
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import (
    GlobalOptimizationRun,
    OptimizerRun,
    Plan,
    PlanVersion,
    RecoveryInputSnapshot,
    RecoveryRecommendation,
)
from apps.scheduling.global_optimizer_services import generate_global_optimization_candidates

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
        "flow",
    }
    assert payload["mode"] == "assisted"
    assert payload["context"]["route"] == "/dashboard/situation"
    assert payload["global_next_action"]["action_id"] == "IMPORT_OGV_DEMAND"
    assert payload["global_next_action"]["target_object_id"] is None
    assert isinstance(payload["page_actions"], list)
    assert isinstance(payload["row_actions"], list)
    assert isinstance(payload["blocked_actions"], list)
    assert isinstance(payload["checklist"], list)
    assert payload["flow"] is None
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
    assert payload["flow"] is None


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
def test_active_flow_returns_flow_metadata_and_flow_checklist():
    user, _org = make_user("assistant-api-flow-active")
    seed_canonical_flow_definitions()
    flow_run = start_flow("operator_happy_path_v1", actor=user)

    response = client_for(user).get(
        NEXT_ACTIONS_URL,
        {"route": "/dashboard/situation", "mode": "guided"},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["flow"] == {
        "active_flow": "operator_happy_path_v1",
        "flow_run_id": flow_run.run_id,
        "flow_name": "Operator happy path",
        "flow_status": "active",
        "current_step": "import_ogv_demand",
        "current_step_label": "Import OGV demand",
        "step_status": "active",
        "expected_route": "/schedule/ogv-demand",
        "expected_action_id": "IMPORT_OGV_DEMAND",
        "blocked_reason": "",
        "trial_pack": "",
        "evidence_run_id": "",
        "expected_action_ids": [],
    }
    assert payload["global_next_action"]["source"] == "flow.current_step"
    assert payload["global_next_action"]["action_id"] == "IMPORT_OGV_DEMAND"
    assert [item["key"] for item in payload["checklist"][:3]] == [
        "import_ogv_demand",
        "review_coal_sequence",
        "enter_operating_windows",
    ]


@pytest.mark.django_db
def test_next_actions_endpoint_does_not_mutate_flow_runtime_tables():
    user, _org = make_user("assistant-api-flow-readonly")
    seed_canonical_flow_definitions()
    flow_run = start_flow("operator_happy_path_v1", actor=user)
    before = _flow_counts(flow_run)

    response = client_for(user).get(
        NEXT_ACTIONS_URL,
        {"route": "/schedule/ogv-demand"},
    )

    assert response.status_code == 200
    assert _flow_counts(flow_run) == before


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
        "VALIDATE_ROOT_CAUSE_REPAIR",
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
def test_global_optimizer_candidate_review_action_is_available_read_only():
    user, org = make_user("assistant-api-global-review", permissions=("schedule.view",))
    version = make_plan_version(org)
    run = generate_global_optimization_candidates(plan_version=version, actor=user)
    candidate = run.candidates.order_by("rank").first()

    response = client_for(user).get(
        NEXT_ACTIONS_URL,
        {"route": "/optimization/global"},
    )

    assert response.status_code == 200
    payload = response.json()
    action_ids = [
        payload["global_next_action"]["action_id"],
        *[item["action_id"] for item in payload["page_actions"]],
    ]
    assert "REVIEW_GLOBAL_OPTIMIZATION_CANDIDATE" in action_ids
    review_action = next(
        item
        for item in [payload["global_next_action"], *payload["page_actions"]]
        if item["action_id"] == "REVIEW_GLOBAL_OPTIMIZATION_CANDIDATE"
    )
    assert review_action["route"] == "/optimization/global"
    assert review_action["required_permission"] == "schedule.view"
    assert review_action["audit_required"] is False
    assert review_action["target_object_type"] == "global_optimization_candidate"
    assert review_action["target_object_id"] == str(candidate.id)
    assert GlobalOptimizationRun.objects.count() == 1


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


def _flow_counts(flow_run):
    flow_run.refresh_from_db()
    return {
        "flow_runs": FlowRun.objects.count(),
        "step_runs": FlowStepRun.objects.count(),
        "events": FlowEvent.objects.count(),
        "status": flow_run.status,
        "current_step_key": flow_run.current_step_key,
    }
