import pytest
from django.conf import settings

from apps.assistant.registry import (
    ACTION_REGISTRY,
    PHASE5_ACTION_IDS,
    REQUIRED_FIRST_SPRINT_ACTION_IDS,
    ROUTE_ACTIONS,
    get_action_definition,
    get_route_action_ids,
)
from apps.assistant.services import build_recommendation


def test_assistant_app_is_registered():
    assert "apps.assistant" in settings.INSTALLED_APPS


def test_action_ids_are_unique():
    assert len(ACTION_REGISTRY) == len(set(ACTION_REGISTRY))


def test_required_first_sprint_action_ids_exist():
    missing = set(REQUIRED_FIRST_SPRINT_ACTION_IDS) - set(ACTION_REGISTRY)
    assert not missing


def test_phase5_action_ids_exist_and_use_recommendation_console_route():
    missing = set(PHASE5_ACTION_IDS) - set(ACTION_REGISTRY)
    assert not missing
    assert get_action_definition("OPEN_RECOMMENDATION_CONSOLE").route == (
        "/recovery/recommendations"
    )
    assert get_action_definition("MATERIALIZE_RECOVERY_RECOMMENDATION").route == (
        "/recovery/recommendations"
    )


def test_action_definitions_have_required_contract_fields():
    for action in ACTION_REGISTRY.values():
        assert action.action_id
        assert action.label
        assert action.description
        assert action.route.startswith("/")
        assert action.cta_label
        assert action.owner_roles
        assert action.ui_placements
        assert action.fallback_message


def test_mutating_actions_are_marked_audited():
    not_audited = [
        action.action_id
        for action in ACTION_REGISTRY.values()
        if not action.read_only and not action.audit_required
    ]
    assert not not_audited


def test_route_ownership_points_to_registered_actions():
    unknown_actions = {
        action_id
        for route_actions in ROUTE_ACTIONS.values()
        for action_id in route_actions
        if action_id not in ACTION_REGISTRY
    }
    assert not unknown_actions
    assert "OPEN_RECOMMENDATION_CONSOLE" in get_route_action_ids(
        "/recovery/recommendations"
    )


def test_get_action_definition_rejects_unknown_action_id():
    with pytest.raises(KeyError, match="Unknown assistant action_id"):
        get_action_definition("UNKNOWN_ACTION")


def test_build_recommendation_uses_registry_defaults():
    recommendation = build_recommendation(
        "MATERIALIZE_RECOVERY_RECOMMENDATION",
        priority="warning",
        rank_score=740,
        enabled=True,
        reason="A ranked recovery recommendation is ready for scenario handoff.",
        source="recovery.recommendation_ready_to_materialize",
        target_object_type="recovery_recommendation",
        target_object_id=42,
        metadata={"recommendationId": "REC-42"},
    )

    assert recommendation.action_id == "MATERIALIZE_RECOVERY_RECOMMENDATION"
    assert recommendation.label == "Create scenario from recommendation"
    assert recommendation.route == "/recovery/recommendations"
    assert recommendation.cta_label == "Create scenario"
    assert recommendation.required_permission == "schedule.edit"
    assert recommendation.audit_required is True
    assert recommendation.target_object_id == "42"
    assert recommendation.hover_hint == recommendation.reason
    assert recommendation.metadata == {"recommendationId": "REC-42"}
