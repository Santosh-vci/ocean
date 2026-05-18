# Backend Recommendation Engine Specification

## 1. Target backend app

Create:

```text
backend/apps/assistant/
  __init__.py
  apps.py
  urls.py
  serializers.py
  registry.py
  selectors.py
  rules.py
  services.py
  views.py
  tests/
```

Register the app in Django settings and include its urls under `/api/` with the rest of the app urls.

---

## 2. Registry implementation

### 2.1 `registry.py`

Implement immutable registry entries.

```python
from dataclasses import dataclass
from typing import Literal

Priority = Literal["critical", "warning", "normal", "info"]
AssistantMode = Literal["off", "assisted", "guided", "supervisor"]

@dataclass(frozen=True)
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
```

Expose:

```python
ACTION_REGISTRY: dict[str, AssistantActionDefinition]
get_action_definition(action_id: str) -> AssistantActionDefinition
```

Fail fast if duplicate IDs exist.

---

## 3. Recommendation shape

### 3.1 `services.py`

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class ActionRecommendation:
    action_id: str
    label: str
    priority: str
    rank_score: int
    enabled: bool
    route: str
    cta_label: str
    reason: str
    hover_hint: str = ""
    detail_text: str = ""
    impact_if_ignored: str = ""
    owner_role: str = ""
    required_permission: str | None = None
    audit_required: bool = False
    target_object_type: str | None = None
    target_object_id: str | None = None
    blocked_reason: str = ""
    source: str = ""
    expires_at: datetime | None = None
    metadata: dict = field(default_factory=dict)
```

### 3.2 Action factory

All rules should create recommendations through a factory so registry defaults remain consistent.

```python
def build_recommendation(
    action_id: str,
    *,
    priority: str,
    rank_score: int,
    enabled: bool,
    reason: str,
    source: str,
    target_object_type: str | None = None,
    target_object_id: str | None = None,
    blocked_reason: str = "",
    route: str | None = None,
    owner_role: str | None = None,
    impact_if_ignored: str = "",
    metadata: dict | None = None,
) -> ActionRecommendation:
    definition = get_action_definition(action_id)
    return ActionRecommendation(
        action_id=definition.action_id,
        label=definition.label,
        priority=priority,
        rank_score=rank_score,
        enabled=enabled,
        route=route or definition.route,
        cta_label=definition.cta_label,
        reason=reason,
        hover_hint=reason,
        detail_text=reason,
        impact_if_ignored=impact_if_ignored,
        owner_role=owner_role or (definition.owner_roles[0] if definition.owner_roles else ""),
        required_permission=definition.required_permission,
        audit_required=definition.audit_required,
        target_object_type=target_object_type,
        target_object_id=str(target_object_id) if target_object_id is not None else None,
        blocked_reason=blocked_reason,
        source=source,
        metadata=metadata or {},
    )
```

---

## 4. Context selectors

### 4.1 `selectors.py`

Implement read-only selectors. They should keep business queries out of rule code.

Recommended context dataclass:

```python
@dataclass
class AssistantContext:
    user: User
    permissions: set[str]
    mode: str
    route: str | None
    object_type: str | None
    object_id: str | None
    active_plan_version: object | None
    active_plan_status: str | None
    validation_status: str | None
    demand_count: int
    cargo_layer_issue_count: int
    tide_window_count: int
    bridge_window_count: int
    constraint_blocker_count: int
    blocking_conflict_count: int
    critical_conflict_count: int
    warning_conflict_count: int
    pending_approval_count: int
    current_user_pending_approval_count: int
    all_required_approvals_complete: bool
    published_snapshot_exists: bool
    latest_export_for_published_plan_exists: bool
    pending_event_candidate_count: int
    high_confidence_event_candidate_count: int
    stale_signal_alert_count: int
    open_tracking_alert_count: int
    open_scenario_count: int
    simulated_scenario_count: int
    promotable_scenario_count: int
```

Minimum selectors:

```python
select_user_permissions(user) -> set[str]
select_active_plan_version(user) -> PlanVersion | None
select_planning_counts(user) -> dict
select_conflict_counts(user, active_plan_version) -> dict
select_approval_status(user, active_plan_version) -> dict
select_export_status(user, active_plan_version) -> dict
select_event_candidate_counts(user) -> dict
select_tracking_alert_counts(user) -> dict
select_simulation_counts(user, active_plan_version) -> dict
build_assistant_context(user, route, object_type, object_id, mode) -> AssistantContext
```

### 4.2 Selector discipline

- Use existing models and serializers where possible.
- Avoid large queryset materialization.
- Use `.count()`, `.exists()`, `.values()` where enough.
- Do not mutate any model in selectors.
- Scope queries by organization/data scope using existing RBAC/data-scope patterns.
- If scope logic is unclear, reuse existing overview/dashboard service logic instead of inventing a new one.

---

## 5. Rule implementation

### 5.1 `rules.py`

Each rule function takes `AssistantContext` and returns a list of recommendations.

```python
def rule_import_demand(ctx: AssistantContext) -> list[ActionRecommendation]:
    if ctx.demand_count == 0:
        return [build_recommendation(...)]
    return []
```

Rule functions should be pure.

### 5.2 Rule IDs

Every emitted recommendation must have a `source` rule ID.

Examples:

```text
planning.no_demand
planning.missing_windows
planning.ready_to_generate
plan.published_needs_draft
exceptions.blocking_conflicts
scenario.ready_to_run
approval.user_decision_pending
publish.ready
export.published_without_export
operations.high_confidence_event
telemetry.stale_signal
```

### 5.3 Required rules

#### `planning.no_demand`

```text
IF demand_count == 0
THEN recommend IMPORT_OGV_DEMAND
PRIORITY warning
```

#### `planning.sequence_review_needed`

```text
IF demand_count > 0 AND cargo_layer_issue_count > 0
THEN recommend REVIEW_COAL_SEQUENCE
PRIORITY warning
```

#### `planning.missing_windows`

```text
IF demand_count > 0 AND (tide_window_count == 0 OR bridge_window_count == 0)
THEN recommend ENTER_OPERATING_WINDOWS
PRIORITY warning
```

#### `planning.ready_to_generate`

```text
IF demand_count > 0
AND tide_window_count > 0
AND bridge_window_count > 0
AND no active generated/editable plan exists
THEN recommend GENERATE_PLAN
PRIORITY normal
```

#### `plan.published_needs_draft`

```text
IF active_plan_status IN published/superseded
AND source demand/constraints changed OR user is on published plan page
THEN recommend CREATE_DRAFT
PRIORITY normal
```

#### `plan.editable_stale_regenerate`

```text
IF active plan is editable
AND constraints/demand/actuals changed after generated_at
THEN recommend REGENERATE_PLAN
PRIORITY warning
```

#### `exceptions.blocking_conflicts`

```text
IF blocking_conflict_count > 0
THEN recommend OPEN_EXCEPTION_CENTER
PRIORITY critical
```

This must outrank submit/publish/export actions.

#### `exceptions.create_scenario`

```text
IF blocking or critical exception exists
AND no open scenario exists for source item
THEN recommend CREATE_SCENARIO
PRIORITY critical/warning based on severity
```

#### `scenario.ready_to_run`

```text
IF open_scenario_count > 0 AND scenario has assumptions AND no latest successful run
THEN recommend RUN_SIMULATION
```

#### `scenario.promotable`

```text
IF promotable_scenario_count > 0
THEN recommend PROMOTE_SCENARIO
```

#### `approval.ready_to_submit`

```text
IF active plan is editable/proposed/generated/validated
AND blocking_conflict_count == 0
AND no pending approval request
THEN recommend SUBMIT_APPROVAL
```

#### `approval.user_decision_pending`

```text
IF current_user_pending_approval_count > 0
THEN recommend APPROVE_PLAN and optionally REJECT_PLAN
```

Primary top action should be `APPROVE_PLAN`; `REJECT_PLAN` should normally be a secondary page action, unless blocking/critical issue exists.

#### `publish.ready`

```text
IF all_required_approvals_complete
AND active plan not published
AND user has publish permission
AND blocking_conflict_count == 0
THEN recommend PUBLISH_PLAN
```

#### `export.published_without_export`

```text
IF active plan is published
AND latest_export_for_published_plan_exists is false
THEN recommend GENERATE_EXPORT
```

#### `operations.high_confidence_event`

```text
IF high_confidence_event_candidate_count > 0
THEN recommend CONFIRM_EVENT
```

#### `operations.noisy_event`

```text
IF pending event candidate is duplicate/noisy/conflicting
THEN recommend REJECT_EVENT as page/row action
```

#### `operations.override_risk`

```text
IF jetty actual materially differs from plan
AND assignment is eligible for override
THEN recommend FORCE_START_JETTY as page/row action
```

#### `telemetry.stale_signal`

```text
IF stale_signal_alert_count > 0
THEN recommend REVIEW_SIGNAL_HEALTH or OPEN_EXCEPTION_CENTER depending severity
```

#### `audit.after_governed_mutation`

```text
IF recent governed mutation exists and user has audit permission
THEN recommend REVIEW_AUDIT as low-priority info
```

---

## 6. Permission shaping

Before returning recommendations:

1. If user has required permission, keep in `global_next_action`/`page_actions`.
2. If user lacks required permission but action affects current route, move to `blocked_actions` with blocked reason.
3. If user lacks view permission for the target route, omit entirely.
4. Read-only navigation actions still require route view permission.

Example blocked action:

```json
{
  "action_id": "PUBLISH_PLAN",
  "enabled": false,
  "blocked_reason": "You do not have schedule publish permission. Ask Joint Control to publish after approvals complete."
}
```

---

## 7. Dedupe and sorting

Implement:

```python
def dedupe_recommendations(items):
    by_key = {}
    for item in items:
        key = (item.action_id, item.target_object_type, item.target_object_id)
        if key not in by_key or item.rank_score > by_key[key].rank_score:
            by_key[key] = item
    return list(by_key.values())
```

Sort by:

```text
rank_score DESC
priority weight DESC
current route match DESC
created/updated recency if relevant
```

---

## 8. Serializer

`serializers.py` should expose:

```python
class ActionRecommendationSerializer(serializers.Serializer):
    action_id = serializers.CharField()
    label = serializers.CharField()
    priority = serializers.CharField()
    rank_score = serializers.IntegerField()
    enabled = serializers.BooleanField()
    route = serializers.CharField()
    cta_label = serializers.CharField()
    reason = serializers.CharField()
    hover_hint = serializers.CharField(allow_blank=True)
    detail_text = serializers.CharField(allow_blank=True)
    impact_if_ignored = serializers.CharField(allow_blank=True)
    owner_role = serializers.CharField(allow_blank=True)
    required_permission = serializers.CharField(allow_null=True)
    audit_required = serializers.BooleanField()
    target_object_type = serializers.CharField(allow_null=True)
    target_object_id = serializers.CharField(allow_null=True)
    blocked_reason = serializers.CharField(allow_blank=True)
    source = serializers.CharField()
    expires_at = serializers.DateTimeField(allow_null=True)
    metadata = serializers.DictField()
```

Response serializer:

```python
class NextActionsResponseSerializer(serializers.Serializer):
    generated_at = serializers.DateTimeField()
    mode = serializers.CharField()
    context = serializers.DictField()
    global_next_action = ActionRecommendationSerializer(allow_null=True)
    page_actions = ActionRecommendationSerializer(many=True)
    row_actions = ActionRecommendationSerializer(many=True)
    blocked_actions = ActionRecommendationSerializer(many=True)
    checklist = serializers.ListField(child=serializers.DictField())
```

---

## 9. View

```python
class NextActionsView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        route = request.query_params.get("route")
        object_type = request.query_params.get("object_type")
        object_id = request.query_params.get("object_id")
        mode = request.query_params.get("mode") or "assisted"
        response = get_next_actions(
            user=request.user,
            route=route,
            object_type=object_type,
            object_id=object_id,
            mode=mode,
        )
        return Response(response)
```

---

## 10. Service API

```python
def get_next_actions(user, route=None, object_type=None, object_id=None, mode="assisted") -> dict:
    ctx = build_assistant_context(user, route, object_type, object_id, mode)
    if mode == "off":
        return empty_response(ctx)

    recommendations = []
    for rule in RULES:
        recommendations.extend(rule(ctx))

    shaped = shape_recommendations(ctx, recommendations)
    return serialize_response(ctx, shaped)
```

---

## 11. Tests

Create:

```text
backend/apps/assistant/tests/test_action_registry.py
backend/apps/assistant/tests/test_next_actions_api.py
backend/apps/assistant/tests/test_planning_rules.py
backend/apps/assistant/tests/test_exception_rules.py
backend/apps/assistant/tests/test_approval_publish_export_rules.py
backend/apps/assistant/tests/test_operations_event_rules.py
backend/apps/assistant/tests/test_permission_shaping.py
```

Minimum tests:

1. Registry has no duplicate action IDs.
2. All emitted action IDs exist in registry.
3. No demand recommends `IMPORT_OGV_DEMAND`.
4. Demand but no windows recommends `ENTER_OPERATING_WINDOWS`.
5. Ready planning state recommends `GENERATE_PLAN`.
6. Blocking conflicts outrank submit approval.
7. Published plan with no export recommends `GENERATE_EXPORT`.
8. Approval pending for user recommends `APPROVE_PLAN`.
9. Approval pending for other user does not recommend `APPROVE_PLAN` to current user.
10. User lacking publish permission gets blocked `PUBLISH_PLAN`, not enabled CTA.
11. Pending high-confidence candidate recommends `CONFIRM_EVENT`.
12. Assistant mode `off` returns no nonessential recommendations.

---

## 12. Performance requirements

- The endpoint should use bounded queries.
- Against seed data, p95 should be below 250 ms.
- Do not load full trips/events unless row-specific request requires it.
- Cache only if required; correctness is more important than cache in first build.
- If using cache later, invalidate on plan generation, conflict creation, event confirmation, approval decision, publish, export creation, and master-data update.
