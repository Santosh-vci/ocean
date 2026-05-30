from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from .models import FlowDefinition, FlowEvent, FlowRun, FlowStepRun
from .selectors import SelectorResult, evaluate_selector

HIGH_RISK_STEP_KEYS = {
    "generate_plan",
    "validate_root_cause",
    "promote_scenario",
    "submit_approval",
    "approve_plan",
    "run_publishability_check",
    "publish_plan",
    "generate_export",
}

BOUND_REF_ALIASES = {
    "importJobId": "import_job_id",
    "import_job_id": "import_job_id",
    "planVersionId": "plan_version_id",
    "plan_version_id": "plan_version_id",
    "approvalRequestId": "approval_request_id",
    "approval_request_id": "approval_request_id",
    "recommendationId": "recommendation_id",
    "recommendation_id": "recommendation_id",
    "scenarioId": "scenario_id",
    "scenario_id": "scenario_id",
    "scenarioRunId": "scenario_run_id",
    "scenario_run_id": "scenario_run_id",
    "snapshotId": "recovery_snapshot_id",
    "recoverySnapshotId": "recovery_snapshot_id",
    "recovery_snapshot_id": "recovery_snapshot_id",
    "optimizerRunId": "optimizer_run_id",
    "optimizer_run_id": "optimizer_run_id",
    "assignmentCandidateRunId": "assignment_candidate_run_id",
    "assignment_candidate_run_id": "assignment_candidate_run_id",
    "publishabilityAssessmentId": "publishability_assessment_id",
    "publishability_assessment_id": "publishability_assessment_id",
    "rootCauseAssessmentId": "root_cause_assessment_id",
    "root_cause_assessment_id": "root_cause_assessment_id",
    "publishedSnapshotId": "published_snapshot_id",
    "published_snapshot_id": "published_snapshot_id",
    "exportJobId": "export_job_id",
    "export_job_id": "export_job_id",
    "scenarioVersionId": "plan_version_id",
    "scenario_version": "plan_version_id",
}

ACTION_REF_ALIASES = {
    "VALIDATE_ROOT_CAUSE_REPAIR": {"assessmentId": "root_cause_assessment_id"},
    "RUN_PUBLISHABILITY_CHECK": {"assessmentId": "publishability_assessment_id"},
}

OBJECT_TYPE_REF_ALIASES = {
    "import_job": "import_job_id",
    "plan_version": "plan_version_id",
    "approval_request": "approval_request_id",
    "recovery_recommendation": "recommendation_id",
    "simulation_scenario": "scenario_id",
    "scenario_run": "scenario_run_id",
    "recovery_input_snapshot": "recovery_snapshot_id",
    "optimizer_run": "optimizer_run_id",
    "publishability_assessment": "publishability_assessment_id",
    "published_plan_snapshot": "published_snapshot_id",
    "export_job": "export_job_id",
}


@dataclass(frozen=True, slots=True)
class FlowSubject:
    subject_type: str = ""
    subject_id: str = ""


def get_active_flow_run(user, route: str | None = None, subject: FlowSubject | None = None):
    queryset = FlowRun.objects.select_related("flow_definition", "started_by").prefetch_related(
        "step_runs",
    )
    queryset = queryset.filter(status__in=[FlowRun.Status.ACTIVE, FlowRun.Status.BLOCKED])
    if user is not None and getattr(user, "is_authenticated", False) and not getattr(user, "is_superuser", False):
        organization_ids = list(
            user.organization_memberships.filter(is_active=True).values_list(
                "organization_id",
                flat=True,
            )
        )
        organization_ids.extend(
            user.role_assignments.filter(is_active=True).values_list("organization_id", flat=True)
        )
        organization_ids = list(dict.fromkeys(organization_ids))
        if organization_ids:
            queryset = queryset.filter(
                Q(started_by=user)
                | Q(started_by__organization_memberships__organization_id__in=organization_ids)
                | Q(started_by__role_assignments__organization_id__in=organization_ids),
            ).distinct()
        else:
            queryset = queryset.filter(started_by=user)
    if subject and subject.subject_type:
        queryset = queryset.filter(subject_type=subject.subject_type)
    if subject and subject.subject_id:
        queryset = queryset.filter(subject_id=subject.subject_id)
    if route:
        queryset = queryset.filter(
            step_runs__step_key=F("current_step_key"),
            step_runs__expected_route=route,
        ).distinct()
    return queryset.order_by("-created_at", "-id").first()


@transaction.atomic
def start_flow(
    flow_key: str,
    actor,
    subject: FlowSubject | None = None,
    metadata: dict | None = None,
) -> FlowRun:
    definition = FlowDefinition.objects.get(
        flow_key=flow_key,
        status=FlowDefinition.Status.ACTIVE,
    )
    now = timezone.now()
    flow_run = FlowRun.objects.create(
        flow_definition=definition,
        status=FlowRun.Status.ACTIVE,
        current_step_key=_first_step(definition)["step_key"],
        subject_type=subject.subject_type if subject else "",
        subject_id=str(subject.subject_id) if subject and subject.subject_id else "",
        started_by=actor if actor is not None and getattr(actor, "is_authenticated", True) else None,
        started_at=now,
        metadata=metadata or {},
    )
    for index, step in enumerate(definition.steps, start=1):
        FlowStepRun.objects.create(
            flow_run=flow_run,
            sequence=index,
            step_key=step["step_key"],
            status=FlowStepRun.Status.ACTIVE if index == 1 else FlowStepRun.Status.PENDING,
            expected_route=step["expected_route"],
            expected_action_id=step["expected_action_id"],
        )
    _record_event(
        flow_run=flow_run,
        step_run=flow_run.step_runs.order_by("sequence").first(),
        event_type=FlowEvent.EventType.STARTED,
        actor=actor,
        metadata={"flowKey": definition.flow_key},
    )
    return evaluate_flow_run(flow_run, actor=actor)


@transaction.atomic
def resume_flow(flow_run: FlowRun, actor=None) -> FlowRun:
    if flow_run.status == FlowRun.Status.CANCELED:
        raise ValidationError("Canceled flow runs cannot be resumed.")
    if flow_run.status == FlowRun.Status.COMPLETED:
        return flow_run
    flow_run.status = FlowRun.Status.ACTIVE
    flow_run.save(update_fields=["status", "updated_at"])
    _record_event(
        flow_run=flow_run,
        step_run=_current_step_run(flow_run),
        event_type=FlowEvent.EventType.RESUMED,
        actor=actor,
    )
    return evaluate_flow_run(flow_run, actor=actor)


@transaction.atomic
def evaluate_flow_run(flow_run: FlowRun, actor=None) -> FlowRun:
    flow_run = (
        FlowRun.objects.select_related("flow_definition")
        .prefetch_related("step_runs")
        .select_for_update()
        .get(pk=flow_run.pk)
    )
    if flow_run.status == FlowRun.Status.CANCELED:
        return flow_run

    ordered_steps = list(flow_run.step_runs.order_by("sequence"))
    definition_steps = {step["step_key"]: step for step in flow_run.flow_definition.steps}
    blocked_step = None
    active_step = None
    previous_flow_status = flow_run.status

    for step_run in ordered_steps:
        if step_run.status == FlowStepRun.Status.COMPLETED:
            if step_run.step_key in HIGH_RISK_STEP_KEYS:
                definition_step = definition_steps.get(step_run.step_key, {})
                completion = evaluate_selector(definition_step.get("completion_selector", ""), flow_run)
                if not completion.completed:
                    _block_step_run(
                        step_run,
                        SelectorResult(
                            blocked=True,
                            reason=completion.reason or "Completed step is no longer valid.",
                            evidence={
                                **completion.evidence,
                                "invalidationReason": "completed_step_invalidated",
                            },
                        ),
                        actor,
                    )
                    blocked_step = step_run
                    break
            continue
        definition_step = definition_steps.get(step_run.step_key, {})
        completion = evaluate_selector(definition_step.get("completion_selector", ""), flow_run)
        if completion.completed:
            _complete_step_run(step_run, completion, actor)
            continue

        block = evaluate_selector(definition_step.get("blocked_selector", ""), flow_run)
        if block.blocked:
            _block_step_run(step_run, block, actor)
            blocked_step = step_run
            break

        _activate_step_run(step_run)
        active_step = step_run
        break

    for later_step in ordered_steps:
        if active_step and later_step.sequence > active_step.sequence:
            _mark_pending_if_needed(later_step)
        if blocked_step and later_step.sequence > blocked_step.sequence:
            _mark_pending_if_needed(later_step, reset_completed=True)

    if blocked_step:
        flow_run.status = FlowRun.Status.BLOCKED
        flow_run.current_step_key = blocked_step.step_key
        flow_run.completed_at = None
    elif active_step:
        flow_run.status = FlowRun.Status.ACTIVE
        flow_run.current_step_key = active_step.step_key
        flow_run.completed_at = None
    else:
        flow_run.status = FlowRun.Status.COMPLETED
        flow_run.current_step_key = ""
        flow_run.completed_at = timezone.now()
        if previous_flow_status != FlowRun.Status.COMPLETED:
            _record_event(
                flow_run=flow_run,
                step_run=ordered_steps[-1] if ordered_steps else None,
                event_type=FlowEvent.EventType.COMPLETED,
                actor=actor,
            )
    flow_run.save(update_fields=["status", "current_step_key", "completed_at", "updated_at"])
    return flow_run


@transaction.atomic
def record_cta_intent(
    flow_run: FlowRun,
    step_key: str,
    action_id: str,
    route: str,
    actor,
    object_type: str | None = None,
    object_id: str | None = None,
    metadata: dict | None = None,
) -> FlowRun:
    flow_run = (
        FlowRun.objects.select_related("flow_definition")
        .prefetch_related("step_runs")
        .select_for_update()
        .get(pk=flow_run.pk)
    )
    if flow_run.status in {FlowRun.Status.COMPLETED, FlowRun.Status.CANCELED}:
        raise ValidationError({"flow_run": "Completed or canceled flow runs cannot record CTA evidence."})
    if step_key != flow_run.current_step_key:
        raise ValidationError({"step_key": "CTA evidence must target the current flow step."})
    step_run = flow_run.step_runs.filter(step_key=step_key).first()
    if step_run is None:
        raise ValidationError({"step_key": "Unknown step for this flow run."})
    if step_run.status not in {FlowStepRun.Status.ACTIVE, FlowStepRun.Status.BLOCKED}:
        raise ValidationError({"step_key": "CTA evidence can only be recorded for active or blocked steps."})
    if action_id != step_run.expected_action_id:
        raise ValidationError({"action_id": "CTA evidence action does not match the expected flow step action."})
    metadata = metadata or {}
    incoming_refs = _extract_bound_refs(
        metadata=metadata,
        action_id=action_id,
        object_type=object_type or "",
        object_id=str(object_id or ""),
    )
    _assert_bound_refs_compatible(flow_run, incoming_refs)
    _merge_bound_refs(flow_run, incoming_refs)
    _record_event(
        flow_run=flow_run,
        step_run=step_run,
        event_type=FlowEvent.EventType.CTA_INTENT,
        actor=actor,
        route=route,
        action_id=action_id,
        object_type=object_type or "",
        object_id=str(object_id or ""),
        metadata=metadata,
    )
    return evaluate_flow_run(flow_run, actor=actor)


@transaction.atomic
def complete_step_from_domain_state(
    flow_run: FlowRun,
    step_key: str,
    evidence: dict[str, Any],
) -> FlowStepRun:
    step_run = flow_run.step_runs.get(step_key=step_key)
    result = SelectorResult(completed=True, evidence=evidence)
    _complete_step_run(step_run, result, actor=None)
    return step_run


@transaction.atomic
def block_step_from_domain_state(flow_run: FlowRun, step_key: str, reason: str) -> FlowStepRun:
    step_run = flow_run.step_runs.get(step_key=step_key)
    result = SelectorResult(blocked=True, reason=reason)
    _block_step_run(step_run, result, actor=None)
    return step_run


def _first_step(definition: FlowDefinition) -> dict:
    if not definition.steps:
        raise ValidationError("Flow definition has no steps.")
    return definition.steps[0]


def _current_step_run(flow_run: FlowRun) -> FlowStepRun | None:
    if not flow_run.current_step_key:
        return None
    return flow_run.step_runs.filter(step_key=flow_run.current_step_key).first()


def _complete_step_run(step_run: FlowStepRun, result: SelectorResult, actor=None) -> None:
    if step_run.status == FlowStepRun.Status.COMPLETED and step_run.evidence == result.evidence:
        return
    previous_status = step_run.status
    step_run.status = FlowStepRun.Status.COMPLETED
    step_run.blocked_reason = ""
    step_run.evidence = result.evidence
    step_run.completed_at = step_run.completed_at or timezone.now()
    step_run.save(
        update_fields=[
            "status",
            "blocked_reason",
            "evidence",
            "completed_at",
            "updated_at",
        ]
    )
    _merge_bound_refs(step_run.flow_run, _extract_bound_refs(metadata=result.evidence))
    if previous_status != FlowStepRun.Status.COMPLETED:
        _record_event(
            flow_run=step_run.flow_run,
            step_run=step_run,
            event_type=FlowEvent.EventType.DOMAIN_COMPLETED,
            actor=actor,
            metadata={"evidence": result.evidence},
        )


def _block_step_run(step_run: FlowStepRun, result: SelectorResult, actor=None) -> None:
    previous_status = step_run.status
    step_run.status = FlowStepRun.Status.BLOCKED
    step_run.blocked_reason = result.reason
    step_run.evidence = result.evidence
    step_run.completed_at = None
    step_run.save(
        update_fields=[
            "status",
            "blocked_reason",
            "evidence",
            "completed_at",
            "updated_at",
        ]
    )
    if previous_status != FlowStepRun.Status.BLOCKED:
        _record_event(
            flow_run=step_run.flow_run,
            step_run=step_run,
            event_type=FlowEvent.EventType.BLOCKED,
            actor=actor,
            metadata={"reason": result.reason, "evidence": result.evidence},
        )


def _activate_step_run(step_run: FlowStepRun) -> None:
    if step_run.status == FlowStepRun.Status.ACTIVE:
        return
    step_run.status = FlowStepRun.Status.ACTIVE
    step_run.blocked_reason = ""
    step_run.completed_at = None
    step_run.save(update_fields=["status", "blocked_reason", "completed_at", "updated_at"])


def _mark_pending_if_needed(step_run: FlowStepRun, *, reset_completed: bool = False) -> None:
    if step_run.status == FlowStepRun.Status.PENDING:
        return
    if step_run.status == FlowStepRun.Status.COMPLETED and not reset_completed:
        return
    step_run.status = FlowStepRun.Status.PENDING
    step_run.blocked_reason = ""
    step_run.completed_at = None
    step_run.save(update_fields=["status", "blocked_reason", "completed_at", "updated_at"])


def _record_event(
    *,
    flow_run: FlowRun,
    event_type: str,
    step_run: FlowStepRun | None = None,
    actor=None,
    route: str = "",
    action_id: str = "",
    object_type: str = "",
    object_id: str = "",
    metadata: dict | None = None,
) -> FlowEvent:
    return FlowEvent.objects.create(
        flow_run=flow_run,
        step_run=step_run,
        step_key=step_run.step_key if step_run else "",
        event_type=event_type,
        actor=actor if actor is not None and getattr(actor, "is_authenticated", True) else None,
        route=route,
        action_id=action_id,
        object_type=object_type,
        object_id=object_id,
        metadata=metadata or {},
    )


def _extract_bound_refs(
    *,
    metadata: dict | None = None,
    action_id: str = "",
    object_type: str = "",
    object_id: str = "",
) -> dict[str, str]:
    refs: dict[str, str] = {}
    payload = metadata if isinstance(metadata, dict) else {}
    aliases = {**BOUND_REF_ALIASES, **ACTION_REF_ALIASES.get(action_id, {})}
    for source_key, target_key in aliases.items():
        value = payload.get(source_key)
        if value not in {None, ""}:
            refs[target_key] = str(value)
    if object_type and object_id:
        target_key = OBJECT_TYPE_REF_ALIASES.get(object_type)
        if target_key:
            refs[target_key] = str(object_id)
    return refs


def _assert_bound_refs_compatible(flow_run: FlowRun, incoming_refs: dict[str, str]) -> None:
    if not incoming_refs:
        return
    bound_refs = _bound_refs(flow_run)
    conflicts = {
        key: {"existing": str(bound_refs[key]), "incoming": str(value)}
        for key, value in incoming_refs.items()
        if key in bound_refs and str(bound_refs[key]) != str(value)
    }
    if conflicts:
        raise ValidationError({"bound_refs": {"Conflicting flow domain references": conflicts}})


def _merge_bound_refs(flow_run: FlowRun, incoming_refs: dict[str, str]) -> None:
    if not incoming_refs:
        return
    metadata = flow_run.metadata if isinstance(flow_run.metadata, dict) else {}
    bound_refs = dict(metadata.get("bound_refs", {}) if isinstance(metadata.get("bound_refs"), dict) else {})
    changed = False
    for key, value in incoming_refs.items():
        if key not in bound_refs:
            bound_refs[key] = str(value)
            changed = True
    if not changed:
        return
    flow_run.metadata = {**metadata, "bound_refs": bound_refs}
    flow_run.save(update_fields=["metadata", "updated_at"])


def _bound_refs(flow_run: FlowRun) -> dict:
    metadata = flow_run.metadata if isinstance(flow_run.metadata, dict) else {}
    refs = metadata.get("bound_refs", {})
    return refs if isinstance(refs, dict) else {}
