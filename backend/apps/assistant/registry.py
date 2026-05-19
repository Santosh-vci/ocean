from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Final, Literal

Priority = Literal["critical", "warning", "normal", "info"]
AssistantMode = Literal["off", "assisted", "guided", "supervisor"]


@dataclass(frozen=True, slots=True)
class AssistantActionDefinition:
    action_id: str
    label: str
    description: str
    route: str
    cta_label: str
    owner_roles: tuple[str, ...]
    required_permission: str | None
    audit_required: bool
    read_only: bool
    ui_placements: tuple[str, ...]
    fallback_message: str


def _action(
    action_id: str,
    label: str,
    description: str,
    route: str,
    cta_label: str,
    owner_roles: tuple[str, ...],
    required_permission: str | None,
    audit_required: bool,
    read_only: bool,
    ui_placements: tuple[str, ...],
    fallback_message: str,
) -> AssistantActionDefinition:
    return AssistantActionDefinition(
        action_id=action_id,
        label=label,
        description=description,
        route=route,
        cta_label=cta_label,
        owner_roles=owner_roles,
        required_permission=required_permission,
        audit_required=audit_required,
        read_only=read_only,
        ui_placements=ui_placements,
        fallback_message=fallback_message,
    )


_ACTION_DEFINITIONS: Final[tuple[AssistantActionDefinition, ...]] = (
    _action(
        "IMPORT_OGV_DEMAND",
        "Import OGV demand",
        "Validate and commit OGV demand into the planning workspace.",
        "/schedule/ogv-demand",
        "Import demand",
        ("berau-scheduler",),
        "schedule.edit",
        True,
        False,
        ("dashboard", "page_card", "checklist"),
        "Import demand is available after schedule edit permission is granted.",
    ),
    _action(
        "REVIEW_COAL_SEQUENCE",
        "Review coal grade sequence",
        "Review cargo layer and hatch sequence readiness for imported demand.",
        "/schedule/coal-grade-sequence",
        "Review sequence",
        ("berau-scheduler",),
        "schedule.view",
        False,
        True,
        ("dashboard", "page_card", "checklist"),
        "Coal sequence review requires schedule visibility and imported demand.",
    ),
    _action(
        "ENTER_OPERATING_WINDOWS",
        "Enter tide/bridge windows",
        "Capture operating windows required before schedule generation.",
        "/constraints/tide-bridge",
        "Enter windows",
        ("berau-scheduler", "abl-dispatcher"),
        "schedule.edit",
        True,
        False,
        ("dashboard", "page_card", "checklist"),
        "Operating windows require schedule edit permission.",
    ),
    _action(
        "REVIEW_MASTER_DATA",
        "Review master data readiness",
        "Review missing or inactive catalog data that blocks planning.",
        "/admin/master-data",
        "Review master data",
        ("berau-scheduler", "admin"),
        "masterdata.view",
        False,
        True,
        ("dashboard", "page_card", "disabled_reason"),
        "Master data readiness requires master data view permission.",
    ),
    _action(
        "REVIEW_RBAC",
        "Review RBAC coverage",
        "Review role, permission, and data-scope coverage for governed workflows.",
        "/admin/users-rbac",
        "Review RBAC",
        ("admin",),
        "admin.view",
        False,
        True,
        ("page_card",),
        "RBAC coverage review requires admin visibility.",
    ),
    _action(
        "GENERATE_PLAN",
        "Generate plan",
        "Generate a deterministic draft plan from ready demand, cargo, and constraints.",
        "/operations/tug-barge-assignment",
        "Generate plan",
        ("berau-scheduler",),
        "schedule.edit",
        True,
        False,
        ("dashboard", "page_card", "checklist"),
        "Plan generation requires ready demand, operating windows, and schedule edit permission.",
    ),
    _action(
        "REGENERATE_PLAN",
        "Regenerate plan",
        "Regenerate an editable active plan after source inputs change.",
        "/operations/tug-barge-assignment",
        "Regenerate plan",
        ("berau-scheduler",),
        "schedule.edit",
        True,
        False,
        ("page_card", "disabled_reason"),
        "Regeneration is blocked for published, submitted, approved, or locked plans.",
    ),
    _action(
        "CREATE_DRAFT",
        "Create successor draft",
        "Create an editable successor when a published plan needs a governed change.",
        "/schedule/published-plan",
        "Create draft",
        ("berau-scheduler",),
        "schedule.edit",
        True,
        False,
        ("dashboard", "page_card"),
        "Create a successor draft before changing a published or superseded plan.",
    ),
    _action(
        "OPEN_EXCEPTION_CENTER",
        "Open Exception Center",
        "Open the exception triage surface for blocking conflicts and operational risk.",
        "/exceptions/center",
        "Open exceptions",
        ("berau-scheduler", "abl-dispatcher", "joint-control-tower-manager"),
        "schedule.view",
        False,
        True,
        ("shell", "dashboard", "page_card"),
        "Exception Center access requires schedule visibility.",
    ),
    _action(
        "CREATE_SCENARIO",
        "Create recovery scenario",
        "Create a governed recovery scenario from an exception, alert, override, or manual source.",
        "/exceptions/center",
        "Create scenario",
        ("berau-scheduler", "abl-dispatcher"),
        "schedule.edit",
        True,
        False,
        ("page_card", "row_hint", "checklist"),
        "Scenario creation requires an editable plan and schedule edit permission.",
    ),
    _action(
        "ADD_ASSUMPTION",
        "Add scenario assumption",
        "Add a scenario assumption before running a recovery simulation.",
        "/simulation/workspace",
        "Add assumption",
        ("berau-scheduler", "abl-dispatcher"),
        "schedule.edit",
        True,
        False,
        ("page_card", "checklist"),
        "Scenario assumptions require an editable scenario and schedule edit permission.",
    ),
    _action(
        "RUN_SIMULATION",
        "Run simulation",
        "Run deterministic scenario projection and constraint evaluation.",
        "/simulation/workspace",
        "Run simulation",
        ("berau-scheduler", "abl-dispatcher"),
        "schedule.edit",
        True,
        False,
        ("page_card", "checklist"),
        "Simulation requires scenario assumptions and schedule edit permission.",
    ),
    _action(
        "PROMOTE_SCENARIO",
        "Promote scenario",
        "Promote a successful scenario into a governed proposed plan version.",
        "/simulation/workspace",
        "Promote scenario",
        ("berau-scheduler",),
        "schedule.edit",
        True,
        False,
        ("page_card", "checklist"),
        "Scenario promotion requires a successful run and schedule edit permission.",
    ),
    _action(
        "SUBMIT_APPROVAL",
        "Submit approval",
        "Submit a feasible draft or proposed plan into approval governance.",
        "/schedule/published-plan",
        "Submit approval",
        ("berau-scheduler",),
        "schedule.edit",
        True,
        False,
        ("dashboard", "page_card", "disabled_reason", "checklist"),
        "Approval submission is blocked while critical conflicts remain.",
    ),
    _action(
        "APPROVE_PLAN",
        "Approve plan",
        "Record an approval decision for a pending plan approval request.",
        "/approvals/publishing",
        "Approve plan",
        ("berau-scheduler", "abl-dispatcher", "joint-control-tower-manager"),
        "schedule.approve",
        True,
        False,
        ("shell", "page_card", "disabled_reason"),
        "Plan approval requires pending authority and schedule approve permission.",
    ),
    _action(
        "REJECT_PLAN",
        "Reject plan",
        "Reject a pending plan approval request with reason capture.",
        "/approvals/publishing",
        "Reject plan",
        ("berau-scheduler", "abl-dispatcher", "joint-control-tower-manager"),
        "schedule.approve",
        True,
        False,
        ("page_card", "disabled_reason"),
        "Plan rejection requires pending authority and schedule approve permission.",
    ),
    _action(
        "PUBLISH_PLAN",
        "Publish plan",
        "Publish an approved plan as an immutable operational snapshot.",
        "/approvals/publishing",
        "Publish plan",
        ("joint-control-tower-manager",),
        "schedule.publish",
        True,
        False,
        ("dashboard", "page_card", "disabled_reason", "checklist"),
        "Publishing requires completed approvals, no blocking conflicts, and publish permission.",
    ),
    _action(
        "CONFIRM_EVENT",
        "Confirm operational event",
        "Confirm a trusted operational event candidate into actualized operational state.",
        "/operations/event-confirmation",
        "Confirm event",
        ("berau-scheduler", "abl-dispatcher", "joint-control-tower-manager"),
        "operations.view",
        True,
        False,
        ("page_card", "row_hint", "disabled_reason"),
        "Event confirmation requires the relevant operations confirm permission for the asset.",
    ),
    _action(
        "REJECT_EVENT",
        "Reject operational event",
        "Reject a duplicate, noisy, or conflicting operational event candidate.",
        "/operations/event-confirmation",
        "Reject event",
        ("berau-scheduler", "abl-dispatcher", "joint-control-tower-manager"),
        "operations.view",
        True,
        False,
        ("page_card", "row_hint", "disabled_reason"),
        "Event rejection requires the relevant operations confirm permission for the asset.",
    ),
    _action(
        "FORCE_START_JETTY",
        "Apply governed jetty override",
        "Apply a governed jetty start override with reason capture.",
        "/operations/jetty-loading",
        "Apply override",
        ("berau-scheduler", "joint-control-tower-manager"),
        "schedule.edit",
        True,
        False,
        ("page_card", "row_hint", "disabled_reason"),
        "Jetty override requires an editable plan, reason capture, and schedule edit permission.",
    ),
    _action(
        "REVIEW_SIGNAL_HEALTH",
        "Review signal health",
        "Review stale, low-confidence, or degraded live tracking signal health.",
        "/map/live",
        "Review signals",
        ("abl-dispatcher", "joint-control-tower-manager"),
        "telemetry.view",
        False,
        True,
        ("page_card", "row_hint"),
        "Signal health review requires telemetry visibility.",
    ),
    _action(
        "GENERATE_RECOVERY_OPTIONS",
        "Generate recovery options",
        "Build a Phase 5 input snapshot and deterministic optimizer run for a disruption.",
        "/exceptions/center",
        "Generate options",
        ("berau-scheduler", "abl-dispatcher"),
        "schedule.edit",
        True,
        False,
        ("dashboard", "page_card", "checklist"),
        "Recovery options require a selected governed source and schedule edit permission.",
    ),
    _action(
        "OPEN_RECOMMENDATION_CONSOLE",
        "Open Recommendation Console",
        "Open ranked Phase 5 recovery recommendations and explanation evidence.",
        "/recovery/recommendations",
        "Open recommendations",
        ("berau-scheduler", "abl-dispatcher", "joint-control-tower-manager"),
        "schedule.view",
        False,
        True,
        ("shell", "dashboard", "page_card"),
        "Recommendation Console requires schedule visibility and a recovery run.",
    ),
    _action(
        "MATERIALIZE_RECOVERY_RECOMMENDATION",
        "Create scenario from recommendation",
        "Materialize a selected Phase 5 recovery recommendation as a governed scenario.",
        "/recovery/recommendations",
        "Create scenario",
        ("berau-scheduler", "abl-dispatcher"),
        "schedule.edit",
        True,
        False,
        ("page_card", "row_hint", "disabled_reason", "checklist"),
        "Only actionable, non-dismissed recommendations can be materialized as scenarios.",
    ),
    _action(
        "DISMISS_RECOVERY_RECOMMENDATION",
        "Dismiss recovery recommendation",
        "Dismiss a Phase 5 recommendation that should not proceed to scenario handoff.",
        "/recovery/recommendations",
        "Dismiss recommendation",
        ("berau-scheduler", "abl-dispatcher"),
        "schedule.edit",
        True,
        False,
        ("page_card", "row_hint", "disabled_reason"),
        "Materialized recommendations cannot be dismissed.",
    ),
    _action(
        "REVIEW_RECOMMENDATION_PROOF_PACK",
        "Review recommendation proof pack",
        "Review Phase 5 input, recommendation, scenario, approval, and audit lineage.",
        "/recovery/recommendations",
        "Review proof pack",
        ("berau-scheduler", "abl-dispatcher", "joint-control-tower-manager"),
        "schedule.view",
        True,
        True,
        ("page_card", "row_hint", "checklist"),
        "Proof-pack review requires schedule visibility and persisted recommendation lineage.",
    ),
    _action(
        "GENERATE_EXPORT",
        "Generate governed export",
        "Generate governed schedule, conflict, scenario, or audit export artifacts.",
        "/admin/export-handoff",
        "Generate export",
        ("joint-control-tower-manager",),
        "export.generate",
        True,
        False,
        ("dashboard", "page_card", "disabled_reason", "checklist"),
        "Final export generation requires publish readiness and export permission.",
    ),
    _action(
        "REVIEW_AUDIT",
        "Review audit trail",
        "Review audit evidence for governed workflow changes.",
        "/admin/audit-logs",
        "Review audit",
        ("admin", "joint-control-tower-manager"),
        "audit.view",
        False,
        True,
        ("shell", "page_card"),
        "Audit review requires audit view permission.",
    ),
)


ROUTE_ACTIONS: Final[dict[str, tuple[str, ...]]] = {
    "/dashboard/situation": tuple(action.action_id for action in _ACTION_DEFINITIONS),
    "/schedule/ogv-demand": ("IMPORT_OGV_DEMAND", "REVIEW_COAL_SEQUENCE"),
    "/schedule/coal-grade-sequence": ("REVIEW_COAL_SEQUENCE", "ENTER_OPERATING_WINDOWS"),
    "/constraints/tide-bridge": (
        "ENTER_OPERATING_WINDOWS",
        "GENERATE_PLAN",
        "OPEN_EXCEPTION_CENTER",
    ),
    "/operations/tug-barge-assignment": (
        "GENERATE_PLAN",
        "REGENERATE_PLAN",
        "OPEN_EXCEPTION_CENTER",
    ),
    "/operations/jetty-loading": ("CONFIRM_EVENT", "FORCE_START_JETTY", "CREATE_SCENARIO"),
    "/operations/cts-floating-crane": ("CONFIRM_EVENT", "CREATE_SCENARIO"),
    "/schedule/published-plan": ("CREATE_DRAFT", "SUBMIT_APPROVAL", "GENERATE_EXPORT"),
    "/exceptions/center": (
        "OPEN_EXCEPTION_CENTER",
        "GENERATE_RECOVERY_OPTIONS",
        "CREATE_SCENARIO",
        "OPEN_RECOMMENDATION_CONSOLE",
    ),
    "/recovery/recommendations": (
        "OPEN_RECOMMENDATION_CONSOLE",
        "MATERIALIZE_RECOVERY_RECOMMENDATION",
        "DISMISS_RECOVERY_RECOMMENDATION",
        "REVIEW_RECOMMENDATION_PROOF_PACK",
    ),
    "/simulation/workspace": (
        "ADD_ASSUMPTION",
        "RUN_SIMULATION",
        "PROMOTE_SCENARIO",
        "SUBMIT_APPROVAL",
        "MATERIALIZE_RECOVERY_RECOMMENDATION",
    ),
    "/approvals/publishing": ("APPROVE_PLAN", "REJECT_PLAN", "PUBLISH_PLAN"),
    "/map/live": ("REVIEW_SIGNAL_HEALTH", "OPEN_EXCEPTION_CENTER", "CREATE_SCENARIO"),
    "/operations/event-confirmation": ("CONFIRM_EVENT", "REJECT_EVENT", "OPEN_EXCEPTION_CENTER"),
    "/admin/export-handoff": ("GENERATE_EXPORT", "REVIEW_AUDIT"),
    "/admin/master-data": ("REVIEW_MASTER_DATA",),
    "/admin/users-rbac": ("REVIEW_RBAC",),
    "/admin/audit-logs": ("REVIEW_AUDIT", "REVIEW_RECOMMENDATION_PROOF_PACK"),
}

PHASE5_ACTION_IDS: Final[tuple[str, ...]] = (
    "GENERATE_RECOVERY_OPTIONS",
    "OPEN_RECOMMENDATION_CONSOLE",
    "MATERIALIZE_RECOVERY_RECOMMENDATION",
    "DISMISS_RECOVERY_RECOMMENDATION",
    "REVIEW_RECOMMENDATION_PROOF_PACK",
)

REQUIRED_FIRST_SPRINT_ACTION_IDS: Final[tuple[str, ...]] = tuple(
    action.action_id for action in _ACTION_DEFINITIONS
)


def _build_action_registry(
    definitions: Iterable[AssistantActionDefinition],
) -> dict[str, AssistantActionDefinition]:
    registry: dict[str, AssistantActionDefinition] = {}
    duplicates: set[str] = set()

    for definition in definitions:
        if definition.action_id in registry:
            duplicates.add(definition.action_id)
        registry[definition.action_id] = definition

    if duplicates:
        duplicate_list = ", ".join(sorted(duplicates))
        raise RuntimeError(f"Duplicate assistant action IDs: {duplicate_list}")

    return registry


ACTION_REGISTRY: Final[dict[str, AssistantActionDefinition]] = _build_action_registry(
    _ACTION_DEFINITIONS,
)


def get_action_definition(action_id: str) -> AssistantActionDefinition:
    try:
        return ACTION_REGISTRY[action_id]
    except KeyError as exc:
        raise KeyError(f"Unknown assistant action_id: {action_id}") from exc


def get_route_action_ids(route: str) -> tuple[str, ...]:
    return ROUTE_ACTIONS.get(route, ())


def iter_action_definitions() -> Iterable[AssistantActionDefinition]:
    return ACTION_REGISTRY.values()
