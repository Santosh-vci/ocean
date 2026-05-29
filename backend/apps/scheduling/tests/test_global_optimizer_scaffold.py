from datetime import timedelta

import pytest
from django.contrib.auth.models import User
from django.utils import timezone
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.organizations.models import Organization
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.global_optimizer_services import (
    GLOBAL_OPTIMIZER_ALGORITHM_VERSION,
    generate_global_optimization_candidates,
    seed_global_objective_profiles,
)
from apps.scheduling.models import (
    ApprovalRequest,
    Assignment,
    Conflict,
    ExportJob,
    GlobalObjectiveProfile,
    GlobalOptimizationCandidate,
    GlobalOptimizationRun,
    OptimizerRun,
    Plan,
    PlanVersion,
    RecoveryRecommendation,
    Trip,
)


@pytest.mark.django_db
def test_default_global_objective_profile_seeds_deterministically():
    first = seed_global_objective_profiles()
    second = seed_global_objective_profiles()

    assert len(first) == 1
    assert len(second) == 1
    assert GlobalObjectiveProfile.objects.count() == 1
    profile = GlobalObjectiveProfile.objects.get(profile_key="global_optimizer_default_v1")
    assert profile.status == GlobalObjectiveProfile.Status.ACTIVE
    assert round(sum(profile.weights.values()), 4) == 1
    assert profile.constraints["publish_candidate_only"] is True


@pytest.mark.django_db
def test_global_optimizer_generation_creates_ranked_candidate_contracts_only():
    user, org = make_user("global-service")
    version = make_plan_version(org)
    before = business_counts()

    run = generate_global_optimization_candidates(plan_version=version, actor=user)

    assert run.status == GlobalOptimizationRun.Status.SUCCEEDED
    assert run.algorithm_version == GLOBAL_OPTIMIZER_ALGORITHM_VERSION
    assert run.objective_profile.profile_key == "global_optimizer_default_v1"
    assert run.input_signature
    assert run.audit_lineage["candidateCount"] == 3
    assert list(run.candidates.values_list("rank", flat=True)) == [1, 2, 3]
    assert run.candidates.first().approval_lineage["approvalCreated"] is False
    assert business_counts() == before


@pytest.mark.django_db
def test_global_optimizer_generation_persists_frozen_objective_weights():
    user, org = make_user("global-weights")
    version = make_plan_version(org)

    run = generate_global_optimization_candidates(
        plan_version=version,
        objective_weights={"laycan_risk": 5, "delay_minutes": 5, "ignored": -1},
        max_candidates=2,
        actor=user,
    )

    assert run.objective_weights == {"delay_minutes": 0.5, "laycan_risk": 0.5}
    assert run.candidates.count() == 2


@pytest.mark.django_db
def test_global_optimizer_api_permissions_and_audit_lineage():
    viewer, org = make_user("global-viewer", permissions=("schedule.view",))
    editor, _ = make_user("global-editor", permissions=("schedule.view", "schedule.edit"))
    version = make_plan_version(org)
    client = APIClient()

    assert client.get("/api/scheduling/global-optimization-runs/").status_code in {401, 403}

    client.force_authenticate(viewer)
    assert client.get("/api/scheduling/global-optimization-runs/").status_code == 200
    blocked = client.post(
        "/api/scheduling/global-optimization-runs/generate/",
        {"plan_version": version.id},
        format="json",
    )
    assert blocked.status_code == 403

    client.force_authenticate(editor)
    response = client.post(
        "/api/scheduling/global-optimization-runs/generate/",
        {"plan_version": version.id},
        format="json",
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "succeeded"
    assert payload["objective_profile_ref"] == "global_optimizer_default_v1"
    assert len(payload["candidates"]) == 3
    assert AuditEvent.objects.filter(
        action="global_optimizer.run.generate",
        object_type="global_optimization_run",
        object_id=str(payload["id"]),
    ).exists()


@pytest.mark.django_db
def test_global_optimizer_api_detail_candidate_and_overview_shape():
    user, org = make_user("global-overview", permissions=("schedule.view", "schedule.edit"))
    version = make_plan_version(org)
    run = generate_global_optimization_candidates(plan_version=version, actor=user)
    candidate = run.candidates.order_by("rank").first()
    client = client_for(user)

    detail = client.get(f"/api/scheduling/global-optimization-runs/{run.id}/")
    candidate_detail = client.get(
        f"/api/scheduling/global-optimization-candidates/{candidate.id}/",
    )
    overview = client.get("/api/scheduling/overview/")

    assert detail.status_code == 200
    assert detail.json()["run_id"] == run.run_id
    assert candidate_detail.status_code == 200
    assert candidate_detail.json()["candidate_id"] == candidate.candidate_id
    assert overview.status_code == 200
    assert overview.json()["globalOptimizationRuns"][0]["run_id"] == run.run_id
    assert overview.json()["globalOptimizationCandidates"][0]["candidate_id"] == (
        candidate.candidate_id
    )


@pytest.mark.django_db
def test_model_constraints_enforce_unique_candidate_rank_per_run():
    user, org = make_user("global-constraints")
    version = make_plan_version(org)
    run = generate_global_optimization_candidates(plan_version=version, actor=user)

    with pytest.raises(Exception):
        GlobalOptimizationCandidate.objects.create(
            run=run,
            rank=1,
            score="1.000",
            risk_level=GlobalOptimizationCandidate.RiskLevel.LOW,
            summary="Duplicate rank",
        )


def make_user(username: str, permissions=("schedule.view", "schedule.edit")):
    org = Organization.objects.create(
        name=f"{username} Org",
        slug=f"{username}-org",
        kind=Organization.Kind.BERAU,
    )
    user = User.objects.create_user(username=username, password="secret")
    assign(user, org, permissions)
    return user, org


def assign(user, organization, permission_codes):
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
    role = Role.objects.create(name=f"role-{user.username}", code=f"role-{user.username}")
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


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def make_plan_version(org):
    now = timezone.now()
    plan = Plan.objects.create(
        code=f"PLAN-{org.slug}",
        name="Global optimizer plan",
        organization=org,
        horizon_start=now,
        horizon_end=now + timedelta(days=7),
    )
    return PlanVersion.objects.create(
        plan=plan,
        version_no=1,
        status=PlanVersion.Status.GENERATED,
        generated_at=now,
    )


def business_counts():
    return {
        "plan_versions": PlanVersion.objects.count(),
        "trips": Trip.objects.count(),
        "assignments": Assignment.objects.count(),
        "conflicts": Conflict.objects.count(),
        "approval_requests": ApprovalRequest.objects.count(),
        "exports": ExportJob.objects.count(),
        "recovery_optimizer_runs": OptimizerRun.objects.count(),
        "recovery_recommendations": RecoveryRecommendation.objects.count(),
    }
