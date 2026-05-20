from __future__ import annotations

from collections.abc import Callable

from apps.scheduling.models import (
    OptimizerRun,
    PlanVersion,
    RecoveryRecommendation,
    SimulationScenario,
)

from .selectors import AssistantContext
from .services import ActionRecommendation, build_recommendation

Rule = Callable[[AssistantContext], list[ActionRecommendation]]


def rule_import_demand(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.demand_count == 0:
        return [
            build_recommendation(
                "IMPORT_OGV_DEMAND",
                priority="warning",
                rank_score=760,
                enabled=True,
                reason="No active OGV demand is available for planning.",
                source="planning.no_demand",
                impact_if_ignored="The schedule cannot be generated until demand exists.",
            )
        ]
    return []


def rule_sequence_review_needed(ctx: AssistantContext) -> list[ActionRecommendation]:
    if (
        ctx.demand_count > 0
        and ctx.cargo_layer_issue_count > 0
        and ctx.validation_status != PlanVersion.ValidationStatus.FEASIBLE
        and ctx.active_plan_status
        not in {
            PlanVersion.Status.APPROVED,
            PlanVersion.Status.PUBLISHED,
            PlanVersion.Status.SUPERSEDED,
        }
    ):
        return [
            build_recommendation(
                "REVIEW_COAL_SEQUENCE",
                priority="warning",
                rank_score=730,
                enabled=True,
                reason=f"{ctx.cargo_layer_issue_count} cargo layer sequence issue(s) need review.",
                source="planning.sequence_review_needed",
                impact_if_ignored=(
                    "Sequence issues can create loading and grade compliance conflicts."
                ),
            )
        ]
    return []


def rule_missing_windows(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.demand_count > 0 and (ctx.tide_window_count == 0 or ctx.bridge_window_count == 0):
        return [
            build_recommendation(
                "ENTER_OPERATING_WINDOWS",
                priority="warning",
                rank_score=720,
                enabled=True,
                reason="Tide or bridge operating windows are missing for active demand.",
                source="planning.missing_windows",
                impact_if_ignored="The scheduler cannot validate feasible navigation windows.",
            )
        ]
    return []


def rule_ready_to_generate(ctx: AssistantContext) -> list[ActionRecommendation]:
    no_generated_plan = (
        ctx.active_plan_version_id is None
        or ctx.active_plan_trip_count == 0
        or ctx.active_plan_status == PlanVersion.Status.DRAFT
    )
    if (
        ctx.demand_count > 0
        and ctx.tide_window_count > 0
        and ctx.bridge_window_count > 0
        and no_generated_plan
    ):
        return [
            build_recommendation(
                "GENERATE_PLAN",
                priority="normal",
                rank_score=600,
                enabled=True,
                reason="Demand, cargo sequence, and operating windows are ready for planning.",
                source="planning.ready_to_generate",
                impact_if_ignored="Assignments remain unavailable until a plan is generated.",
            )
        ]
    return []


def rule_published_needs_draft(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.source_inputs_changed and ctx.active_plan_status in {
        PlanVersion.Status.PUBLISHED,
        PlanVersion.Status.SUPERSEDED,
    } and ctx.latest_export_for_published_plan_exists:
        return [
            build_recommendation(
                "CREATE_DRAFT",
                priority="normal",
                rank_score=590,
                enabled=True,
                reason="The active plan is published; changes need a successor draft.",
                source="plan.published_needs_draft",
                impact_if_ignored="Published snapshots must remain immutable.",
            )
        ]
    return []


def rule_editable_stale_regenerate(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.active_plan_is_editable and ctx.source_inputs_changed and ctx.active_plan_trip_count > 0:
        return [
            build_recommendation(
                "REGENERATE_PLAN",
                priority="warning",
                rank_score=740,
                enabled=True,
                reason="Source demand, constraints, or actuals changed after plan generation.",
                source="plan.editable_stale_regenerate",
                impact_if_ignored="Assignments may no longer reflect current planning inputs.",
            )
        ]
    return []


def rule_blocking_conflicts(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.blocking_conflict_count > 0:
        return [
            build_recommendation(
                "OPEN_EXCEPTION_CENTER",
                priority="critical",
                rank_score=980,
                enabled=True,
                reason=f"{ctx.blocking_conflict_count} unresolved blocking conflict(s) exist.",
                source="exceptions.blocking_conflicts",
                impact_if_ignored="Approval, publish, and export cannot safely proceed.",
            )
        ]
    return []


def rule_create_scenario(ctx: AssistantContext) -> list[ActionRecommendation]:
    risk_count = (
        ctx.blocking_conflict_count
        + ctx.critical_conflict_count
        + ctx.open_tracking_alert_count
        + ctx.active_override_risk_count
    )
    if risk_count > 0 and ctx.open_scenario_count == 0:
        return [
            build_recommendation(
                "CREATE_SCENARIO",
                priority="warning" if ctx.blocking_conflict_count == 0 else "critical",
                rank_score=850 if ctx.blocking_conflict_count else 700,
                enabled=True,
                reason="An active exception or operational risk needs recovery modeling.",
                source="exceptions.create_scenario",
                impact_if_ignored="The recovery path remains untested before approval.",
            )
        ]
    return []


def rule_scenario_ready_to_run(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.scenario_ready_to_run_count > 0:
        return [
            build_recommendation(
                "RUN_SIMULATION",
                priority="normal",
                rank_score=640,
                enabled=True,
                reason="A recovery scenario has assumptions and is ready to simulate.",
                source="scenario.ready_to_run",
                impact_if_ignored="Scenario impact remains unknown.",
            )
        ]
    return []


def rule_scenario_promotable(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.promotable_scenario_count > 0:
        return [
            build_recommendation(
                "PROMOTE_SCENARIO",
                priority="normal",
                rank_score=670,
                enabled=True,
                reason="A simulated recovery scenario is ready for governed promotion.",
                source="scenario.promotable",
                impact_if_ignored="The improved candidate will not enter approval governance.",
            )
        ]
    return []


def rule_approval_ready_to_submit(ctx: AssistantContext) -> list[ActionRecommendation]:
    if (
        ctx.active_plan_status
        in {
            PlanVersion.Status.DRAFT,
            PlanVersion.Status.GENERATED,
            PlanVersion.Status.VALIDATED,
            PlanVersion.Status.PROPOSED,
        }
        and ctx.active_plan_trip_count > 0
        and ctx.blocking_conflict_count == 0
        and ctx.pending_approval_count == 0
    ):
        return [
            build_recommendation(
                "SUBMIT_APPROVAL",
                priority="normal",
                rank_score=620,
                enabled=True,
                reason="The active plan has no blocking conflicts and is ready for approval.",
                source="approval.ready_to_submit",
                impact_if_ignored="The plan cannot publish until approval is requested.",
            )
        ]
    return []


def rule_approval_user_decision_pending(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.current_user_pending_approval_count <= 0:
        return []
    return [
        build_recommendation(
            "APPROVE_PLAN",
            priority="warning",
            rank_score=780,
            enabled=True,
            reason="A plan approval decision is waiting for your authority.",
            source="approval.user_decision_pending",
            impact_if_ignored="Publication remains blocked until required approvals complete.",
        ),
        build_recommendation(
            "REJECT_PLAN",
            priority="normal",
            rank_score=560,
            enabled=True,
            reason="Reject the pending request if the plan is not acceptable.",
            source="approval.user_decision_pending",
            impact_if_ignored="Unsafe changes should be rejected with a reason.",
        ),
    ]


def rule_publish_ready(ctx: AssistantContext) -> list[ActionRecommendation]:
    if (
        ctx.all_required_approvals_complete
        and ctx.active_plan_status != PlanVersion.Status.PUBLISHED
        and ctx.blocking_conflict_count == 0
    ):
        return [
            build_recommendation(
                "PUBLISH_PLAN",
                priority="warning",
                rank_score=760,
                enabled=True,
                reason="All required approvals are complete and no blocking conflicts remain.",
                source="publish.ready",
                impact_if_ignored="Operators will not receive an immutable live snapshot.",
            )
        ]
    return []


def rule_export_published_without_export(ctx: AssistantContext) -> list[ActionRecommendation]:
    if (
        ctx.active_plan_status == PlanVersion.Status.PUBLISHED
        and not ctx.latest_export_for_published_plan_exists
    ):
        return [
            build_recommendation(
                "GENERATE_EXPORT",
                priority="normal",
                rank_score=580,
                enabled=True,
                reason="The published plan does not yet have a governed export artifact.",
                source="export.published_without_export",
                impact_if_ignored="External handoff artifacts remain unavailable.",
            )
        ]
    return []


def rule_high_confidence_event(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.high_confidence_event_candidate_count > 0:
        return [
            build_recommendation(
                "CONFIRM_EVENT",
                priority="warning",
                rank_score=790,
                enabled=True,
                reason=(
                    f"{ctx.high_confidence_event_candidate_count} high-confidence "
                    "event candidate(s) need confirmation."
                ),
                source="operations.high_confidence_event",
                impact_if_ignored="Actualized operational state may lag trusted evidence.",
            )
        ]
    return []


def rule_noisy_event(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.noisy_event_candidate_count > 0:
        return [
            build_recommendation(
                "REJECT_EVENT",
                priority="normal",
                rank_score=540,
                enabled=True,
                reason="Duplicate or rejected operational event candidates need cleanup.",
                source="operations.noisy_event",
                impact_if_ignored="Noisy candidates can obscure trusted operations evidence.",
            )
        ]
    return []


def rule_override_risk(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.active_override_risk_count > 0:
        return [
            build_recommendation(
                "FORCE_START_JETTY",
                priority="warning",
                rank_score=710,
                enabled=True,
                reason="A governed operational variance needs review and possible override.",
                source="operations.override_risk",
                impact_if_ignored="Downstream recovery impact may remain unmodeled.",
            )
        ]
    return []


def rule_stale_signal(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.stale_signal_alert_count > 0:
        return [
            build_recommendation(
                "REVIEW_SIGNAL_HEALTH",
                priority="warning",
                rank_score=700,
                enabled=True,
                reason=f"{ctx.stale_signal_alert_count} stale tracking signal alert(s) are open.",
                source="telemetry.stale_signal",
                impact_if_ignored="Telemetry-derived ETA risk may be unreliable.",
            )
        ]
    return []


def rule_recovery_disruption_ready_for_options(
    ctx: AssistantContext,
) -> list[ActionRecommendation]:
    disruption_count = (
        ctx.blocking_conflict_count
        + ctx.critical_conflict_count
        + ctx.open_tracking_alert_count
        + ctx.pending_event_candidate_count
        + ctx.active_override_risk_count
    )
    if disruption_count > 0 and ctx.latest_optimizer_run_id is None:
        return [
            build_recommendation(
                "GENERATE_RECOVERY_OPTIONS",
                priority="warning",
                rank_score=860,
                enabled=True,
                reason="A governed disruption is ready for Phase 5 recovery options.",
                source="recovery.disruption_ready_for_options",
                impact_if_ignored="Operators will not see ranked recovery options.",
            )
        ]
    return []


def rule_recovery_optimizer_run_succeeded(ctx: AssistantContext) -> list[ActionRecommendation]:
    if (
        ctx.latest_optimizer_run_status == OptimizerRun.Status.SUCCEEDED
        and ctx.latest_optimizer_run_candidate_count > 0
        and ctx.materialized_recovery_recommendation_count == 0
    ):
        return [
            build_recommendation(
                "OPEN_RECOMMENDATION_CONSOLE",
                priority="warning",
                rank_score=830,
                enabled=True,
                reason="A successful recovery optimizer run has ranked candidate options.",
                source="recovery.optimizer_run_succeeded",
                target_object_type="optimizer_run",
                target_object_id=ctx.latest_optimizer_run_id,
                impact_if_ignored="Recovery options will not be reviewed or governed.",
            )
        ]
    return []


def rule_recovery_recommendation_ready_to_materialize(
    ctx: AssistantContext,
) -> list[ActionRecommendation]:
    if (
        ctx.top_recovery_recommendation_id
        and ctx.top_recovery_recommendation_scenario_id is None
        and ctx.top_recovery_recommendation_status
        not in {
            RecoveryRecommendation.Status.DISMISSED,
            RecoveryRecommendation.Status.MATERIALIZED,
        }
    ):
        return [
            build_recommendation(
                "MATERIALIZE_RECOVERY_RECOMMENDATION",
                priority="warning",
                rank_score=810,
                enabled=True,
                reason=(
                    "The top recovery recommendation is ready to be tested as a governed scenario."
                ),
                source="recovery.recommendation_ready_to_materialize",
                target_object_type="recovery_recommendation",
                target_object_id=ctx.top_recovery_recommendation_id,
                impact_if_ignored="The optimizer output remains advisory and cannot change the plan.",
                metadata={"recommendationRef": ctx.top_recovery_recommendation_ref},
            )
        ]
    return []


def rule_recovery_recommendation_dismiss_available(
    ctx: AssistantContext,
) -> list[ActionRecommendation]:
    if (
        ctx.route == "/recovery/recommendations"
        and ctx.top_recovery_recommendation_id
        and ctx.top_recovery_recommendation_scenario_id is None
        and ctx.top_recovery_recommendation_status != RecoveryRecommendation.Status.DISMISSED
    ):
        return [
            build_recommendation(
                "DISMISS_RECOVERY_RECOMMENDATION",
                priority="info",
                rank_score=360,
                enabled=True,
                reason="The selected recommendation can be dismissed if it should not proceed.",
                source="recovery.recommendation_dismiss_available",
                target_object_type="recovery_recommendation",
                target_object_id=ctx.top_recovery_recommendation_id,
            )
        ]
    return []


def rule_recovery_recommendation_blocked_state(
    ctx: AssistantContext,
) -> list[ActionRecommendation]:
    if ctx.route != "/recovery/recommendations" or not ctx.top_recovery_recommendation_id:
        return []

    blocked: list[ActionRecommendation] = []
    target = {
        "target_object_type": "recovery_recommendation",
        "target_object_id": ctx.top_recovery_recommendation_id,
    }
    if ctx.top_recovery_recommendation_status == RecoveryRecommendation.Status.DISMISSED:
        blocked.append(
            build_recommendation(
                "MATERIALIZE_RECOVERY_RECOMMENDATION",
                priority="info",
                rank_score=330,
                enabled=False,
                reason="The selected recovery recommendation was dismissed.",
                blocked_reason=(
                    "Dismissed recommendations cannot be tested as scenarios. Select an "
                    "actionable candidate or generate new recovery options."
                ),
                source="recovery.recommendation_dismissed",
                **target,
            )
        )
    if (
        ctx.top_recovery_recommendation_status == RecoveryRecommendation.Status.MATERIALIZED
        or ctx.top_recovery_recommendation_scenario_id
    ):
        blocked.append(
            build_recommendation(
                "MATERIALIZE_RECOVERY_RECOMMENDATION",
                priority="info",
                rank_score=330,
                enabled=False,
                reason="The selected recovery recommendation is already a governed scenario.",
                blocked_reason=(
                    "This recommendation is already a governed scenario. Continue in "
                    "Simulation Workspace."
                ),
                source="recovery.recommendation_materialized",
                **target,
            )
        )
        blocked.append(
            build_recommendation(
                "DISMISS_RECOVERY_RECOMMENDATION",
                priority="info",
                rank_score=320,
                enabled=False,
                reason="The selected recovery recommendation is already a governed scenario.",
                blocked_reason="Recommendations already created as scenarios cannot be dismissed.",
                source="recovery.recommendation_materialized",
                **target,
            )
        )
    return blocked


def rule_recovery_recommendation_already_materialized(
    ctx: AssistantContext,
) -> list[ActionRecommendation]:
    if (
        ctx.recommendation_origin_scenario_id
        and ctx.recommendation_origin_scenario_status == SimulationScenario.Status.DRAFT
    ):
        return [
            build_recommendation(
                "RUN_SIMULATION",
                priority="normal",
                rank_score=660,
                enabled=True,
                reason="The recovery recommendation is now a scenario ready for simulation.",
                source="recovery.recommendation_already_materialized",
                target_object_type="simulation_scenario",
                target_object_id=ctx.recommendation_origin_scenario_id,
                route="/simulation/workspace",
            )
        ]
    return []


def rule_recovery_proof_pack_available(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.proof_pack_available:
        return [
            build_recommendation(
                "REVIEW_RECOMMENDATION_PROOF_PACK",
                priority="info",
                rank_score=350,
                enabled=True,
                reason="A Phase 5 recommendation proof pack is available for review.",
                source="recovery.proof_pack_available",
                target_object_type="recovery_recommendation",
                target_object_id=ctx.top_recovery_recommendation_id,
                metadata={"recommendationRef": ctx.top_recovery_recommendation_ref},
            )
        ]
    return []


def rule_master_data_route_review(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.route == "/admin/master-data":
        return [
            build_recommendation(
                "REVIEW_MASTER_DATA",
                priority="info",
                rank_score=310,
                enabled=True,
                reason="Master data catalogs are ready for readiness and dependency review.",
                source="admin.master_data_route_review",
                impact_if_ignored="Planning blockers from catalog drift may go unnoticed.",
            )
        ]
    return []


def rule_rbac_route_review(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.route == "/admin/users-rbac":
        return [
            build_recommendation(
                "REVIEW_RBAC",
                priority="info",
                rank_score=300,
                enabled=True,
                reason="Role assignments and data scopes are ready for governance review.",
                source="admin.rbac_route_review",
                impact_if_ignored="Access governance drift may go unnoticed.",
            )
        ]
    return []


def rule_recovery_approved_candidate_publish_blocked(
    ctx: AssistantContext,
) -> list[ActionRecommendation]:
    if (
        ctx.all_required_approvals_complete
        and ctx.blocking_conflict_count > 0
        and ctx.recommendation_origin_scenario_id
    ):
        return [
            build_recommendation(
                "OPEN_EXCEPTION_CENTER",
                priority="critical",
                rank_score=990,
                enabled=True,
                reason=(
                    "The recommendation-origin candidate is approved but still has "
                    "blocking risk."
                ),
                source="recovery.approved_candidate_publish_blocked",
                impact_if_ignored="Publication remains governed-blocked until risk is resolved.",
            )
        ]
    return []


def rule_audit_after_governed_mutation(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.recent_governed_mutation_count > 0:
        return [
            build_recommendation(
                "REVIEW_AUDIT",
                priority="info",
                rank_score=320,
                enabled=True,
                reason="Recent governed workflow activity is available in the audit trail.",
                source="audit.after_governed_mutation",
                impact_if_ignored="Traceability evidence may go unreviewed.",
            )
        ]
    return []


RULES: tuple[Rule, ...] = (
    rule_import_demand,
    rule_sequence_review_needed,
    rule_missing_windows,
    rule_ready_to_generate,
    rule_published_needs_draft,
    rule_editable_stale_regenerate,
    rule_blocking_conflicts,
    rule_recovery_approved_candidate_publish_blocked,
    rule_create_scenario,
    rule_recovery_disruption_ready_for_options,
    rule_recovery_optimizer_run_succeeded,
    rule_recovery_recommendation_ready_to_materialize,
    rule_recovery_recommendation_dismiss_available,
    rule_recovery_recommendation_blocked_state,
    rule_recovery_recommendation_already_materialized,
    rule_scenario_ready_to_run,
    rule_scenario_promotable,
    rule_approval_ready_to_submit,
    rule_approval_user_decision_pending,
    rule_publish_ready,
    rule_export_published_without_export,
    rule_high_confidence_event,
    rule_noisy_event,
    rule_override_risk,
    rule_stale_signal,
    rule_recovery_proof_pack_available,
    rule_master_data_route_review,
    rule_rbac_route_review,
    rule_audit_after_governed_mutation,
)


def evaluate_rules(ctx: AssistantContext) -> list[ActionRecommendation]:
    recommendations: list[ActionRecommendation] = []
    for rule in RULES:
        recommendations.extend(rule(ctx))
    return recommendations
