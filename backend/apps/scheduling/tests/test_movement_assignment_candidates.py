import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.exceptions import ValidationError
from rest_framework.test import APIClient

from apps.planning.models import CargoLayerStep, OGVVoyage
from apps.planning.trial_pack import trial_dt
from apps.scheduling.models import (
    ApprovalRequest,
    Assignment,
    Conflict,
    ExportJob,
    MovementAssignmentCandidate,
    MovementAssignmentCandidateRun,
    Plan,
    PlanVersion,
    PublishedPlanSnapshot,
    RecoveryRecommendation,
    Trip,
)
from apps.scheduling.movement_assignment_services import (
    generate_movement_assignment_candidates,
    select_movement_assignment_candidate,
)
from apps.scheduling.services import generate_plan_version


def command_json(*args):
    output = StringIO()
    call_command(*args, "--json", stdout=output)
    return json.loads(output.getvalue())


def prepare_operator_trial_plan() -> tuple[PlanVersion, object]:
    command_json("operator_trial_practice", "reset")
    command_json("operator_trial_practice", "import-demand")
    command_json("operator_trial_practice", "enter-windows")
    user = get_user_model().objects.get(username="admin@coalflow.local")
    plan = Plan.objects.create(
        code="PLAN-MAC-TRIAL",
        name="Movement assignment candidate trial",
        horizon_start=trial_dt(0, 0),
        horizon_end=trial_dt(8, 0),
        status=Plan.Status.ACTIVE,
    )
    version = PlanVersion.objects.create(plan=plan, version_no=1, created_by=user)
    return version, user


def prepare_happy_path_plan() -> tuple[PlanVersion, object]:
    call_command("seed_phase0", master_data_only=True, verbosity=0)
    user = get_user_model().objects.get(username="admin@coalflow.local")
    client = APIClient()
    client.force_authenticate(user)
    response = client.post(
        "/api/planning/import-jobs/import-trial-demand/",
        {"pack": "operator_happy_path_v1"},
        format="json",
    )
    assert response.status_code == 201
    command_json("operator_trial_practice", "enter-windows")
    plan = Plan.objects.create(
        code="PLAN-MAC-HAPPY",
        name="Movement assignment happy path trial",
        horizon_start=trial_dt(0, 0),
        horizon_end=trial_dt(8, 12),
        status=Plan.Status.ACTIVE,
    )
    version = PlanVersion.objects.create(plan=plan, version_no=1, created_by=user)
    return version, user


@pytest.mark.django_db
def test_candidate_generation_covers_each_operator_trial_movement_without_plan_mutation():
    version, user = prepare_operator_trial_plan()
    before_counts = {
        "trips": Trip.objects.count(),
        "assignments": Assignment.objects.count(),
        "approvals": ApprovalRequest.objects.count(),
        "exports": ExportJob.objects.count(),
        "recommendations": RecoveryRecommendation.objects.count(),
        "published": PublishedPlanSnapshot.objects.count(),
    }

    run = generate_movement_assignment_candidates(plan_version=version, actor=user)

    assert run.status == MovementAssignmentCandidateRun.Status.SUCCEEDED
    assert run.metadata["movementCount"] == 6
    assert run.candidates.values("cargo_layer_step").distinct().count() == 6
    assert run.candidates.filter(status=MovementAssignmentCandidate.Status.FEASIBLE).exists()
    assert run.candidates.filter(status=MovementAssignmentCandidate.Status.BLOCKED).exists()
    assert all(
        candidate.constraint_results
        for candidate in run.candidates.order_by("movement_key", "rank")[:6]
    )
    assert {
        "trips": Trip.objects.count(),
        "assignments": Assignment.objects.count(),
        "approvals": ApprovalRequest.objects.count(),
        "exports": ExportJob.objects.count(),
        "recommendations": RecoveryRecommendation.objects.count(),
        "published": PublishedPlanSnapshot.objects.count(),
    } == before_counts


@pytest.mark.django_db
def test_happy_path_pack_uses_realistic_vessel_names_and_rotates_tugs():
    version, user = prepare_happy_path_plan()

    run = generate_movement_assignment_candidates(plan_version=version, actor=user)

    assert OGVVoyage.objects.filter(vessel_name__icontains="HAPPY PATH").count() == 0
    assert set(OGVVoyage.objects.values_list("vessel_name", flat=True)) == {
        "MV DERAWAN STAR",
        "MV MARATUA TRADER",
        "MV SAMBARATA QUEEN",
        "MV LATI HORIZON",
        "MV BORNEO PROSPERITY",
    }
    selected_tugs = set(
        run.candidates.filter(is_selected=True, tug__isnull=False).values_list(
            "tug__code",
            flat=True,
        )
    )
    assert selected_tugs == {"BER-TUG-08", "BER-TUG-09"}


@pytest.mark.django_db
def test_plan_generation_creates_candidate_run_and_persists_trip_provenance():
    version, user = prepare_operator_trial_plan()

    result = generate_plan_version(version, actor=user)
    version.refresh_from_db()

    run_id = version.summary["assignmentCandidateRunId"]
    assert result.trip_count == 6
    assert version.summary["generatedFromMovementCandidates"] is True
    assert MovementAssignmentCandidateRun.objects.filter(pk=run_id).exists()
    assert Trip.objects.filter(
        plan_version=version,
        selection_reason__reason_code="MOVEMENT_ASSIGNMENT_CANDIDATE",
    ).count() == 6
    assert Trip.objects.filter(
        plan_version=version,
        selection_reason__assignmentCandidateRunId=run_id,
    ).count() == 6


@pytest.mark.django_db
def test_plan_generation_uses_operator_selected_candidate():
    version, user = prepare_operator_trial_plan()
    run = generate_movement_assignment_candidates(plan_version=version, actor=user)
    step = CargoLayerStep.objects.order_by(
        "voyage__laycan_start",
        "voyage__priority",
        "voyage__voyage_id",
        "required_sequence_no",
    ).first()
    options = list(
        run.candidates.filter(
            cargo_layer_step=step,
            status__in=[
                MovementAssignmentCandidate.Status.FEASIBLE,
                MovementAssignmentCandidate.Status.WARNING,
            ],
        ).order_by("rank", "id")[:3]
    )
    assert len(options) >= 2
    selected = select_movement_assignment_candidate(options[1])

    generate_plan_version(version, candidate_run=run, actor=user)
    trip = Trip.objects.get(plan_version=version, cargo_layer_step=step)

    assert trip.selection_reason["assignmentCandidateId"] == selected.id
    assert trip.assignment.tug_id == selected.tug_id
    assert trip.assignment.barge_id == selected.barge_id


@pytest.mark.django_db
def test_blocked_only_movement_generates_explicit_blocking_conflict():
    version, user = prepare_operator_trial_plan()
    run = generate_movement_assignment_candidates(plan_version=version, actor=user)
    step = CargoLayerStep.objects.order_by("id").first()
    run.candidates.filter(cargo_layer_step=step).update(
        status=MovementAssignmentCandidate.Status.BLOCKED,
        blocking_reasons=["No feasible tug-barge-jetty-CTS combination exists."],
        is_selected=False,
    )

    generate_plan_version(version, candidate_run=run, actor=user)

    conflict = Conflict.objects.get(
        plan_version=version,
        trip__cargo_layer_step=step,
        code="MOVEMENT_ASSIGNMENT_BLOCKED",
    )
    assignment = Trip.objects.get(plan_version=version, cargo_layer_step=step).assignment
    assert conflict.is_blocking is True
    assert "No feasible" in conflict.message
    assert assignment.status == Assignment.Status.BLOCKED
    assert assignment.tug_id is None
    assert assignment.barge_id is None
    assert assignment.cts_id is None


@pytest.mark.django_db
def test_operator_candidate_selection_rejects_overlapping_hard_resource_reuse():
    version, user = prepare_operator_trial_plan()
    run = generate_movement_assignment_candidates(plan_version=version, actor=user)
    selected = list(
        run.candidates.filter(is_selected=True)
        .select_related("cargo_layer_step", "tug", "barge", "cts")
        .order_by("cargo_layer_step__planned_start", "id")
    )
    overlap_pair = None
    for left in selected:
        left_start = left.cargo_layer_step.planned_start
        left_end = left.cargo_layer_step.planned_end
        if not left_start or not left_end:
            continue
        for right in selected:
            if left.pk == right.pk:
                continue
            right_start = right.cargo_layer_step.planned_start
            right_end = right.cargo_layer_step.planned_end
            if right_start and right_end and left_start < right_end and left_end > right_start:
                overlap_pair = (left, right)
                break
        if overlap_pair:
            break
    assert overlap_pair is not None
    source, conflicting = overlap_pair
    candidate = (
        run.candidates.filter(cargo_layer_step=source.cargo_layer_step)
        .exclude(pk=source.pk)
        .select_related("cargo_layer_step")
        .first()
    )
    candidate.tug = conflicting.tug
    candidate.barge = conflicting.barge
    candidate.cts = conflicting.cts
    candidate.status = MovementAssignmentCandidate.Status.FEASIBLE
    candidate.blocking_reasons = []
    candidate.warning_reasons = []
    candidate.is_selected = False
    candidate.save(
        update_fields=(
            "tug",
            "barge",
            "cts",
            "status",
            "blocking_reasons",
            "warning_reasons",
            "is_selected",
            "updated_at",
        )
    )

    with pytest.raises(ValidationError, match="already selected for overlapping movement"):
        select_movement_assignment_candidate(candidate)


@pytest.mark.django_db
def test_candidate_api_generate_and_select():
    version, user = prepare_operator_trial_plan()
    client = APIClient()
    client.force_authenticate(user)

    generated = client.post(
        "/api/scheduling/movement-assignment-candidate-runs/generate/",
        {"plan_version": version.id},
        format="json",
    )
    assert generated.status_code == 201
    assert generated.data["metadata"]["movementCount"] == 6
    candidate = MovementAssignmentCandidate.objects.filter(
        run_id=generated.data["id"],
        status=MovementAssignmentCandidate.Status.FEASIBLE,
    ).order_by("movement_key", "rank").first()

    selected = client.post(
        f"/api/scheduling/movement-assignment-candidates/{candidate.id}/select/",
        {},
        format="json",
    )

    assert selected.status_code == 200
    assert selected.data["is_selected"] is True


@pytest.mark.django_db
def test_operations_scope_overview_returns_lightweight_candidate_summaries():
    version, user = prepare_operator_trial_plan()
    run = generate_movement_assignment_candidates(plan_version=version, actor=user)
    movement_count = run.candidates.values("movement_key").distinct().count()
    client = APIClient()
    client.force_authenticate(user)

    response = client.get("/api/scheduling/overview/?scope=operations")

    assert response.status_code == 200
    assert response.data["plans"] == []
    assert response.data["simulationScenarios"] == []
    assert response.data["optimizerRuns"] == []
    assert response.data["globalOptimizationRuns"] == []
    assert response.data["commercialProjections"] == []
    assert response.data["movementAssignmentCandidateRun"]["candidates"] == []
    assert len(response.data["movementAssignmentCandidates"]) == movement_count
    assert all(
        candidate["rank"] == 1 or candidate["is_selected"]
        for candidate in response.data["movementAssignmentCandidates"]
    )
    assert all(
        candidate["constraint_results"] == []
        for candidate in response.data["movementAssignmentCandidates"]
    )
