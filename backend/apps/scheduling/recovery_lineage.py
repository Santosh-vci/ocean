from __future__ import annotations

from typing import Any

from .models import PlanVersion, RecoveryRecommendation, RootCauseRepairAssessment, ScenarioRun, SimulationScenario


RECOVERY_ORIGIN_KEY = "recoveryOrigin"
SCENARIO_LINEAGE_KEY = "scenarioLineage"


def build_recovery_origin(
    *,
    scenario: SimulationScenario,
    run: ScenarioRun | None = None,
) -> dict[str, Any]:
    recommendation = (
        RecoveryRecommendation.objects.filter(scenario=scenario)
        .select_related("root_cause_assessment")
        .order_by("-updated_at", "-id")
        .first()
    )
    if recommendation is None and scenario.scenario_type != "recovery_recommendation":
        return {}
    origin: dict[str, Any] = {
        "scenarioPk": scenario.pk,
        "scenarioId": scenario.scenario_id,
        "baselineVersionId": scenario.baseline_version_id,
        "selectedRunId": run.id if run else None,
        "selectedRunRef": run.run_id if run else "",
    }
    if recommendation:
        origin.update(
            {
                "recommendationPk": recommendation.pk,
                "recommendationRef": recommendation.recommendation_id,
                "optimizerRunPk": recommendation.optimizer_run_id,
                "optimizerRunRef": recommendation.optimizer_run.run_id,
            }
        )
        assessment = getattr(recommendation, "root_cause_assessment", None)
        if assessment:
            origin.update(root_cause_origin_fields(assessment))
    return origin


def root_cause_origin_fields(assessment: RootCauseRepairAssessment) -> dict[str, Any]:
    return {
        "rootCauseAssessmentPk": assessment.pk,
        "rootCauseAssessmentRef": assessment.assessment_id,
        "rootCauseStatus": assessment.status,
        "sourceCauseType": assessment.source_cause_type,
    }


def recovery_origin_from_summary(summary: dict | None) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    origin = summary.get(RECOVERY_ORIGIN_KEY)
    if isinstance(origin, dict) and origin:
        return dict(origin)
    lineage = summary.get(SCENARIO_LINEAGE_KEY)
    if isinstance(lineage, dict) and lineage.get("scenarioPk"):
        return {
            "scenarioPk": lineage.get("scenarioPk"),
            "scenarioId": lineage.get("scenarioId", ""),
            "baselineVersionId": lineage.get("baselineVersionId"),
            "selectedRunId": lineage.get("selectedRunId"),
            "selectedRunRef": lineage.get("selectedRunRef", ""),
        }
    return {}


def provenance_summary_fields(summary: dict | None) -> dict[str, Any]:
    if not isinstance(summary, dict):
        return {}
    fields: dict[str, Any] = {}
    for key in (RECOVERY_ORIGIN_KEY, SCENARIO_LINEAGE_KEY):
        value = summary.get(key)
        if isinstance(value, dict) and value:
            fields[key] = value
    return fields


def recommendation_for_plan_version(plan_version: PlanVersion) -> tuple[RecoveryRecommendation | None, dict[str, Any]]:
    origin = recovery_origin_from_summary(plan_version.summary)
    if not origin:
        return None, {}
    recommendation = _recommendation_from_origin(origin)
    if recommendation:
        return recommendation, origin
    scenario_pk = origin.get("scenarioPk")
    if scenario_pk:
        recommendation = (
            RecoveryRecommendation.objects.filter(scenario_id=scenario_pk)
            .select_related("root_cause_assessment")
            .order_by("-updated_at", "-id")
            .first()
        )
    return recommendation, origin


def _recommendation_from_origin(origin: dict[str, Any]) -> RecoveryRecommendation | None:
    recommendation_pk = origin.get("recommendationPk")
    if recommendation_pk:
        try:
            return RecoveryRecommendation.objects.select_related("root_cause_assessment").get(
                pk=int(recommendation_pk),
            )
        except (RecoveryRecommendation.DoesNotExist, TypeError, ValueError):
            return None
    recommendation_ref = origin.get("recommendationRef")
    if recommendation_ref:
        return (
            RecoveryRecommendation.objects.filter(recommendation_id=str(recommendation_ref))
            .select_related("root_cause_assessment")
            .first()
        )
    return None
