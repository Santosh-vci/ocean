import json
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.core.management import call_command
from rest_framework.test import APIClient

from apps.audit.models import AuditEvent
from apps.flows.models import FlowDefinition, FlowEvent, FlowRun
from apps.flows.services import record_cta_intent
from apps.planning.models import CargoLayerStep, ImportJob, OGVVoyage
from apps.planning.trial_pack import trial_dt
from apps.scheduling.models import (
    ApprovalDecision,
    ApprovalRequest,
    Conflict,
    ExportJob,
    PlanVersion,
    PublishedPlanSnapshot,
    RecoveryRecommendation,
)
from apps.telemetry.models import TrackingAlert


def command_json(*args):
    output = StringIO()
    call_command(*args, "--json", stdout=output)
    return json.loads(output.getvalue())


def admin_client():
    user = get_user_model().objects.get(username="admin@coalflow.local")
    client = APIClient()
    client.force_authenticate(user)
    return client, user


def _record_current_step(flow, action_id, route, user):
    flow.refresh_from_db()
    return record_cta_intent(
        flow,
        step_key=flow.current_step_key,
        action_id=action_id,
        route=route,
        actor=user,
        metadata={"test": "operator_trial_flow"},
    )


def _create_and_generate_plan(client, user):
    organization = (
        user.organization_memberships.filter(is_default=True, is_active=True)
        .select_related("organization")
        .first()
    )
    plan_response = client.post(
        "/api/scheduling/plans/",
        {
            "code": "PLAN-HAPPY-PATH-TRIAL",
            "name": "Operator Happy Path Trial",
            "organization_id": organization.organization_id if organization else None,
            "horizon_start": trial_dt(0, 0).isoformat(),
            "horizon_end": trial_dt(7, 23, 59).isoformat(),
            "status": "active",
        },
        format="json",
    )
    assert plan_response.status_code == 201
    version_response = client.post(
        f"/api/scheduling/plans/{plan_response.data['id']}/create-version/",
        {},
        format="json",
    )
    assert version_response.status_code == 201
    version_id = version_response.data["id"]
    generate_response = client.post(
        f"/api/scheduling/plan-versions/{version_id}/generate/",
        {},
        format="json",
    )
    assert generate_response.status_code == 200
    generated = PlanVersion.objects.get(pk=version_id)
    assert generated.trips.count() > 0
    assert generated.validation_status == PlanVersion.ValidationStatus.FEASIBLE
    return version_id


@pytest.mark.django_db
def test_operator_trial_practice_stages_start_empty_then_build_blocked_plan():
    reset = command_json("operator_trial_practice", "reset")
    assert reset["counts"]["voyages"] == 0
    assert reset["counts"]["cargoRequirements"] == 0
    assert reset["counts"]["planVersions"] == 0

    imported = command_json("operator_trial_practice", "import-demand")
    assert imported["counts"]["voyages"] == 5
    assert imported["counts"]["cargoRequirements"] == 8
    assert imported["counts"]["cargoLayerSteps"] == 6
    assert imported["counts"]["planVersions"] == 0

    windows = command_json("operator_trial_practice", "enter-windows")
    assert windows["counts"]["tideWindows"] == 3
    assert windows["counts"]["bridgeWindows"] == 3
    assert windows["windowEntry"]["constraintChecks"] == 5

    generated = command_json("operator_trial_practice", "generate-plan")
    assert generated["planVersion"]["tripCount"] == 6
    assert generated["planVersion"]["conflictCount"] == 4
    assert generated["planVersion"]["blockingConflictCount"] == 3
    assert generated["planVersion"]["validationStatus"] == "blocked"


@pytest.mark.django_db
def test_operator_trial_prepare_happy_path_db_truth_is_idempotent():
    evidence = command_json(
        "operator_trial_practice",
        "prepare-db-truth",
        "--flow",
        "happy-path",
    )

    assert evidence["flow"] == "happy-path"
    assert evidence["flowKey"] == "operator_happy_path_v1"
    assert evidence["currentStep"] == "import_ogv_demand"
    assert evidence["expectedActionIds"][:4] == [
        "IMPORT_OGV_DEMAND",
        "REVIEW_COAL_SEQUENCE",
        "ENTER_OPERATING_WINDOWS",
        "GENERATE_PLAN",
    ]
    assert evidence["startingCounts"]["voyages"] == 0
    assert evidence["startingCounts"]["planVersions"] == 0
    assert evidence["startingCounts"]["exports"] == 0
    assert FlowRun.objects.filter(status=FlowRun.Status.ACTIVE).count() == 1
    flow = FlowRun.objects.get(run_id=evidence["flowRunId"])
    assert flow.metadata["trial_pack"] == "operator_happy_path_v1"
    assert flow.metadata["evidence_run_id"] == "operator-trial-happy-path"

    rerun = command_json(
        "operator_trial_practice",
        "prepare-db-truth",
        "--flow",
        "happy-path",
    )

    assert FlowRun.objects.filter(
        flow_definition__flow_key="operator_happy_path_v1",
    ).count() == 1
    assert FlowEvent.objects.filter(flow_run__run_id=rerun["flowRunId"]).count() == 1


@pytest.mark.django_db
def test_seed_phase0_master_data_only_clears_flow_runs_but_keeps_definitions():
    command_json(
        "operator_trial_practice",
        "prepare-db-truth",
        "--flow",
        "happy-path",
    )

    call_command("seed_phase0", master_data_only=True, verbosity=0)

    assert FlowRun.objects.count() == 0
    assert FlowEvent.objects.count() == 0
    assert set(
        FlowDefinition.objects.filter(status=FlowDefinition.Status.ACTIVE).values_list(
            "flow_key",
            flat=True,
        )
    ) == {"operator_happy_path_v1", "phase5_plus_recovery_v1"}


@pytest.mark.django_db
def test_import_trial_demand_happy_path_pack_creates_clean_demand():
    call_command("seed_phase0", master_data_only=True, verbosity=0)
    client, _user = admin_client()

    response = client.post(
        "/api/planning/import-jobs/import-trial-demand/",
        {"pack": "operator_happy_path_v1"},
        format="json",
    )

    assert response.status_code == 201
    assert OGVVoyage.objects.count() == 2
    assert ImportJob.objects.get(pk=response.data["id"]).source == "operator_happy_path_v1"
    assert CargoLayerStep.objects.filter(sequence_violation=True).count() == 0
    assert CargoLayerStep.objects.filter(
        status__in=[CargoLayerStep.Status.BLOCKED, CargoLayerStep.Status.QC_HOLD],
    ).count() == 0


@pytest.mark.django_db
def test_happy_path_flow_advances_from_domain_truth_after_cta_events():
    evidence = command_json(
        "operator_trial_practice",
        "prepare-db-truth",
        "--flow",
        "happy-path",
    )
    client, user = admin_client()
    flow = FlowRun.objects.get(run_id=evidence["flowRunId"])

    import_response = client.post(
        "/api/planning/import-jobs/import-trial-demand/",
        {"pack": "operator_happy_path_v1"},
        format="json",
    )
    assert import_response.status_code == 201
    flow = _record_current_step(flow, "IMPORT_OGV_DEMAND", "/schedule/ogv-demand", user)
    assert flow.current_step_key == "enter_operating_windows"

    windows_response = client.post("/api/planning/overview/enter-operating-windows/", {})
    assert windows_response.status_code == 201
    flow = _record_current_step(
        flow,
        "ENTER_OPERATING_WINDOWS",
        "/constraints/tide-bridge",
        user,
    )
    assert flow.current_step_key == "generate_plan"

    version_id = _create_and_generate_plan(client, user)
    flow = _record_current_step(flow, "GENERATE_PLAN", "/operations/tug-barge-assignment", user)
    assert flow.current_step_key == "submit_approval"

    approval_response = client.post(
        f"/api/scheduling/plan-versions/{version_id}/request-approval/",
        {"reason": "Operator trial UI evidence."},
        format="json",
    )
    assert approval_response.status_code == 201
    flow = _record_current_step(flow, "SUBMIT_APPROVAL", "/schedule/published-plan", user)
    assert flow.current_step_key == "approve_plan"

    approval = ApprovalRequest.objects.get(pk=approval_response.data["id"])
    for authority in [
        ApprovalDecision.AuthorityRole.BERAU_SCHEDULER,
        ApprovalDecision.AuthorityRole.ABL_DISPATCHER,
    ]:
        decide_response = client.post(
            f"/api/scheduling/approval-requests/{approval.id}/decide/",
            {
                "authority_role": authority,
                "decision": ApprovalDecision.Decision.APPROVE,
                "comments": f"Approved as {authority}.",
            },
            format="json",
        )
        assert decide_response.status_code == 200
        flow = _record_current_step(flow, "APPROVE_PLAN", "/approvals/publishing", user)
    assert flow.current_step_key == "publish_plan"

    publish_response = client.post(f"/api/scheduling/plan-versions/{version_id}/publish/")
    assert publish_response.status_code == 201
    flow = _record_current_step(flow, "PUBLISH_PLAN", "/approvals/publishing", user)
    assert flow.current_step_key == "generate_export"
    assert PublishedPlanSnapshot.objects.filter(status=PublishedPlanSnapshot.Status.ACTIVE).exists()

    export_response = client.post(
        "/api/exports/generate/",
        {
            "export_type": ExportJob.ExportType.PLAN,
            "export_format": ExportJob.ExportFormat.PRINT,
            "plan_version": version_id,
        },
        format="json",
    )
    assert export_response.status_code == 201
    flow = _record_current_step(flow, "GENERATE_EXPORT", "/admin/export-handoff", user)

    assert flow.status == FlowRun.Status.COMPLETED
    assert flow.current_step_key == ""
    assert ExportJob.objects.filter(status=ExportJob.Status.GENERATED).exists()


@pytest.mark.django_db
def test_operator_trial_prepare_recovery_db_truth_starts_before_recommendations():
    evidence = command_json(
        "operator_trial_practice",
        "prepare-db-truth",
        "--flow",
        "recovery",
    )

    assert evidence["flow"] == "recovery"
    assert evidence["flowKey"] == "phase5_plus_recovery_v1"
    assert evidence["currentStep"] == "generate_recovery_options"
    assert evidence["startingCounts"]["voyages"] == 3
    assert evidence["startingCounts"]["openConflicts"] > 0
    assert evidence["startingCounts"]["recommendations"] == 0
    assert evidence["startingCounts"]["scenarios"] == 0
    assert RecoveryRecommendation.objects.count() == 0


@pytest.mark.django_db
def test_phase5_recovery_proof_command_creates_repeatable_recommendation_evidence():
    output = StringIO()

    call_command("phase5_recovery_proof", "--json", stdout=output)

    evidence = json.loads(output.getvalue())
    assert evidence["definitionOfDone"] == {
        "overall": "PASS",
        "stagesPassed": 7,
        "expectedStages": 7,
    }
    assert evidence["optimizerRun"]["runId"].startswith("OPT-P5-RECOVERY-")
    assert evidence["optimizerRun"]["recommendationCount"] >= 4
    assert evidence["selectedRecommendation"]["rank"] >= 1
    assert evidence["scenarioHandoff"]["scenarioStatus"] == "proposed"
    assert evidence["approvalHandoff"]["decisionCount"] == 2
    assert evidence["proofPack"]["proofPackVersion"] == "phase5.6-recommendation-proof-pack"
    assert evidence["proofPack"]["approvalCount"] == 1
    assert evidence["proofPack"]["auditTrailCount"] >= 6
    assert "/recovery/recommendations" in evidence["browserEvidenceTargets"]
    assert AuditEvent.objects.filter(
        metadata__runId=evidence["runId"],
        action="phase5.proof.proof_pack_verified",
    ).exists()

    rerun_output = StringIO()
    call_command("phase5_recovery_proof", "--json", stdout=rerun_output)
    rerun = json.loads(rerun_output.getvalue())
    assert rerun["definitionOfDone"]["overall"] == "PASS"
    assert rerun["runId"] != evidence["runId"]


@pytest.mark.django_db
def test_phase5_resolve_trial_pack_creates_clean_approved_closure_state():
    proof_output = StringIO()
    resolve_output = StringIO()

    call_command("phase5_recovery_proof", "--json", stdout=proof_output)
    call_command("phase5_resolve_trial_pack", "--json", stdout=resolve_output)

    evidence = json.loads(resolve_output.getvalue())
    closure_version = PlanVersion.objects.get(pk=evidence["closureVersion"]["id"])

    assert evidence["definitionOfDone"] == {
        "overall": "PASS",
        "allExceptionsHandled": True,
    }
    assert evidence["before"]["openConflictCount"] > 0
    assert evidence["resolvedPriorConflictCount"] > 0
    assert evidence["closureVersion"]["openConflictCount"] == 0
    assert evidence["closureVersion"]["blockingConflictCount"] == 0
    assert evidence["closureVersion"]["openTrackingAlertCount"] == 0
    assert closure_version.status == PlanVersion.Status.APPROVED
    assert closure_version.validation_status == PlanVersion.ValidationStatus.FEASIBLE
    assert not Conflict.objects.filter(
        plan_version=closure_version,
        resolved_at__isnull=True,
    ).exists()
    assert not TrackingAlert.objects.filter(
        status__in=[TrackingAlert.Status.OPEN, TrackingAlert.Status.ACKNOWLEDGED],
    ).exists()
    assert evidence["approval"]["status"] == "approved"
    assert evidence["approval"]["decisionCount"] == 2
    assert AuditEvent.objects.filter(
        action="phase5.trial.exceptions_resolved",
        object_repr=str(closure_version),
    ).exists()

    second_resolve_output = StringIO()
    call_command("phase5_resolve_trial_pack", "--json", stdout=second_resolve_output)
    second_evidence = json.loads(second_resolve_output.getvalue())

    assert second_evidence["closureVersion"]["id"] == closure_version.pk
    assert second_evidence["normalizedInputs"]["idempotent"] is True
    assert second_evidence["definitionOfDone"]["allExceptionsHandled"] is True
