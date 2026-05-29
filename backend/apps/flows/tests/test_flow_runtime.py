from datetime import timedelta
from decimal import Decimal

import pytest
from django.contrib.auth.models import User
from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.utils import timezone
from rest_framework.test import APIClient

from apps.flows.definitions import seed_canonical_flow_definitions
from apps.flows.models import FlowDefinition, FlowEvent, FlowRun, FlowStepRun
from apps.flows.services import record_cta_intent, start_flow
from apps.masters.models import Location
from apps.organizations.models import Organization
from apps.planning.models import BridgeWindow, ImportJob, OGVVoyage, TideWindow
from apps.rbac.models import AccessPermission, DataScope, Role, UserRoleAssignment
from apps.scheduling.models import (
    ApprovalDecision,
    ApprovalRequest,
    ExportJob,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
    Trip,
)
from apps.scheduling.publishability_services import assess_plan_publishability


def make_org(slug="flows-org"):
    return Organization.objects.create(name=slug, slug=slug, kind=Organization.Kind.BERAU)


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


def make_user(username, permissions=("schedule.view", "schedule.edit")):
    org = make_org(username)
    user = User.objects.create_user(username=username, password="secret")
    assign(user, org, permissions)
    return user, org


def client_for(user):
    client = APIClient()
    client.force_authenticate(user)
    return client


def create_location(code="LOC-FLOW"):
    return Location.objects.create(
        code=code,
        name=code,
        location_type=Location.LocationType.TIDE_GATE,
        latitude=Decimal("-1.900000"),
        longitude=Decimal("118.000000"),
    )


def create_demand(user, org):
    now = timezone.now()
    voyage = OGVVoyage.objects.create(
        voyage_id=f"VOY-{org.slug}",
        vessel_name="MV Flow Runtime",
        customer_name="Test Customer",
        eta=now,
        laycan_start=now,
        laycan_end=now + timedelta(days=3),
        required_mt=10000,
        organization=org,
    )
    ImportJob.objects.create(
        import_type=ImportJob.ImportType.OGV_DEMAND,
        filename="flow-demand.json",
        source="test",
        status=ImportJob.Status.IMPORTED,
        total_rows=1,
        valid_rows=1,
        created_by=user,
    )
    return voyage


def create_windows():
    now = timezone.now()
    tide_location = create_location("LOC-FLOW-TIDE")
    bridge_location = create_location("LOC-FLOW-BRIDGE")
    TideWindow.objects.create(
        code="TIDE-FLOW-01",
        location=tide_location,
        window_start=now,
        window_end=now + timedelta(hours=4),
        min_water_level_m=Decimal("2.10"),
        max_loaded_draft_m=Decimal("4.50"),
        is_active=True,
    )
    BridgeWindow.objects.create(
        code="BRDG-FLOW-01",
        location=bridge_location,
        window_start=now,
        window_end=now + timedelta(hours=4),
        clearance_m=Decimal("12.00"),
        status=BridgeWindow.Status.OPEN,
        is_active=True,
    )


def create_plan_chain(user, org, voyage):
    now = timezone.now()
    plan = Plan.objects.create(
        code=f"PLAN-{org.slug}",
        name="Flow plan",
        organization=org,
        horizon_start=now,
        horizon_end=now + timedelta(days=3),
        status=Plan.Status.ACTIVE,
    )
    version = PlanVersion.objects.create(
        plan=plan,
        version_no=1,
        status=PlanVersion.Status.APPROVED,
        generated_at=now,
        created_by=user,
    )
    Trip.objects.create(
        plan_version=version,
        trip_id="TRIP-FLOW-01",
        sequence=1,
        voyage=voyage,
        planned_start=now,
        planned_end=now + timedelta(hours=8),
        planned_quantity_mt=10000,
    )
    approval = ApprovalRequest.objects.create(
        request_id="APR-FLOW-01",
        plan_version=version,
        status=ApprovalRequest.Status.APPROVED,
        required_authorities=[
            ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
            ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
        ],
        reason="Flow runtime test approval.",
        requested_by=user,
        decided_at=now,
    )
    ApprovalDecision.objects.create(
        approval_request=approval,
        authority_role=ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
        decision=ApprovalDecision.Decision.APPROVE,
        actor=user,
        organization=org,
    )
    ApprovalDecision.objects.create(
        approval_request=approval,
        authority_role=ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
        decision=ApprovalDecision.Decision.APPROVE,
        actor=user,
        organization=org,
    )
    PublishedPlanSnapshot.objects.create(
        snapshot_id="PPS-FLOW-01",
        plan=plan,
        plan_version=version,
        approval_request=approval,
        status=PublishedPlanSnapshot.Status.ACTIVE,
        payload={"test": "flow"},
        published_by=user,
    )
    ExportJob.objects.create(
        export_id="EXP-FLOW-01",
        export_type=ExportJob.ExportType.PLAN,
        export_format=ExportJob.ExportFormat.JSON,
        status=ExportJob.Status.GENERATED,
        plan_version=version,
        organization=org,
        storage_bucket="test",
        storage_key="flow/plan.json",
        file_name="plan.json",
        content_type="application/json",
        checksum_sha256="0" * 64,
        size_bytes=2,
        record_count=1,
        created_by=user,
    )
    assess_plan_publishability(plan_version=version, actor=user)
    return version


@pytest.mark.django_db
def test_flow_model_constraints_and_references():
    definition = seed_canonical_flow_definitions()[0]
    user, _org = make_user("flows-model")
    first = start_flow(definition.flow_key, user)
    second = start_flow(definition.flow_key, user)

    assert first.run_id.startswith("FLOW-")
    assert second.run_id.startswith("FLOW-")
    assert first.run_id != second.run_id
    assert first.events.first().event_id.startswith("FEV-")

    with transaction.atomic(), pytest.raises(IntegrityError):
        FlowStepRun.objects.create(
            flow_run=first,
            sequence=99,
            step_key="import_ogv_demand",
            expected_route="/schedule/ogv-demand",
            expected_action_id="IMPORT_OGV_DEMAND",
        )


@pytest.mark.django_db
def test_seed_phase0_master_data_only_creates_flow_definitions_without_runs():
    call_command("seed_phase0", master_data_only=True, verbosity=0)

    assert set(
        FlowDefinition.objects.filter(status=FlowDefinition.Status.ACTIVE).values_list(
            "flow_key",
            flat=True,
        )
    ) == {"operator_happy_path_v1", "phase5_plus_recovery_v1"}
    assert FlowRun.objects.count() == 0


@pytest.mark.django_db
def test_start_flow_creates_ordered_step_runs_and_started_event():
    seed_canonical_flow_definitions()
    user, _org = make_user("flows-start")

    flow = start_flow("operator_happy_path_v1", user)
    steps = list(flow.step_runs.order_by("sequence"))

    assert flow.status == FlowRun.Status.ACTIVE
    assert flow.current_step_key == "import_ogv_demand"
    assert [step.step_key for step in steps][:3] == [
        "import_ogv_demand",
        "review_coal_sequence",
        "enter_operating_windows",
    ]
    assert steps[0].status == FlowStepRun.Status.ACTIVE
    assert steps[1].status == FlowStepRun.Status.PENDING
    assert flow.events.filter(event_type=FlowEvent.EventType.STARTED).count() == 1


@pytest.mark.django_db
def test_evaluate_flow_run_advances_happy_path_from_domain_truth():
    seed_canonical_flow_definitions()
    user, org = make_user("flows-happy")
    flow = start_flow("operator_happy_path_v1", user)

    voyage = create_demand(user, org)
    create_windows()
    create_plan_chain(user, org, voyage)

    from apps.flows.services import evaluate_flow_run

    evaluated = evaluate_flow_run(flow, actor=user)
    step_statuses = dict(evaluated.step_runs.values_list("step_key", "status"))

    assert evaluated.status == FlowRun.Status.COMPLETED
    assert evaluated.current_step_key == ""
    assert all(status == FlowStepRun.Status.COMPLETED for status in step_statuses.values())
    assert evaluated.events.filter(event_type=FlowEvent.EventType.DOMAIN_COMPLETED).count() >= 8


@pytest.mark.django_db
def test_phase5_plus_definition_seeds_future_steps_without_future_models():
    seed_canonical_flow_definitions()

    definition = FlowDefinition.objects.get(flow_key="phase5_plus_recovery_v1")
    step_keys = [step["step_key"] for step in definition.steps]

    assert "validate_root_cause" in step_keys
    assert "run_publishability_check" in step_keys
    assert "repair_remaining_conflicts" in step_keys


@pytest.mark.django_db
def test_record_cta_intent_only_writes_flow_runtime_records():
    seed_canonical_flow_definitions()
    user, _org = make_user("flows-cta")
    flow = start_flow("operator_happy_path_v1", user)
    planning_counts = {
        "voyages": OGVVoyage.objects.count(),
        "imports": ImportJob.objects.count(),
        "plans": Plan.objects.count(),
    }

    updated = record_cta_intent(
        flow,
        step_key="import_ogv_demand",
        action_id="IMPORT_OGV_DEMAND",
        route="/schedule/ogv-demand",
        actor=user,
        metadata={"test": True},
    )

    assert updated.events.filter(event_type=FlowEvent.EventType.CTA_INTENT).count() == 1
    assert OGVVoyage.objects.count() == planning_counts["voyages"]
    assert ImportJob.objects.count() == planning_counts["imports"]
    assert Plan.objects.count() == planning_counts["plans"]


@pytest.mark.django_db
def test_flow_api_auth_permissions_and_response_shape():
    seed_canonical_flow_definitions()
    viewer, org = make_user("flows-viewer", permissions=("schedule.view",))
    editor = User.objects.create_user(username="flows-editor", password="secret")
    assign(editor, org, ["schedule.view", "schedule.edit"])
    flow = start_flow("operator_happy_path_v1", editor)

    anonymous = APIClient().get("/api/flows/active/")
    assert anonymous.status_code in {401, 403}

    active = client_for(viewer).get("/api/flows/active/")
    route_miss = client_for(viewer).get(
        "/api/flows/active/",
        {"route": "/approvals/publishing"},
    )
    route_hit = client_for(viewer).get(
        "/api/flows/active/",
        {"route": "/schedule/ogv-demand"},
    )
    detail = client_for(viewer).get(f"/api/flows/{flow.run_id}/")
    denied_event = client_for(viewer).post(
        f"/api/flows/{flow.run_id}/events/",
        {
            "step_key": "import_ogv_demand",
            "action_id": "IMPORT_OGV_DEMAND",
            "route": "/schedule/ogv-demand",
        },
        format="json",
    )
    allowed_event = client_for(editor).post(
        f"/api/flows/{flow.run_id}/events/",
        {
            "step_key": "import_ogv_demand",
            "action_id": "IMPORT_OGV_DEMAND",
            "route": "/schedule/ogv-demand",
            "metadata": {"source": "test"},
        },
        format="json",
    )

    assert active.status_code == 200
    assert active.data["flow"]["run_id"] == flow.run_id
    assert active.data["flow"]["step_runs"][0]["step_key"] == "import_ogv_demand"
    assert route_miss.status_code == 200
    assert route_miss.data["flow"] is None
    assert route_hit.status_code == 200
    assert route_hit.data["flow"]["run_id"] == flow.run_id
    assert detail.status_code == 200
    assert detail.data["run_id"] == flow.run_id
    assert denied_event.status_code == 403
    assert allowed_event.status_code == 200
    assert allowed_event.data["recent_events"][0]["event_type"] in {
        FlowEvent.EventType.CTA_INTENT,
        FlowEvent.EventType.STARTED,
    }
