# Next Action Assist — Implementation Specification

## 1. Objective

Build a deterministic, governed **Next Action Assist** layer for the Ocean coal transshipment scheduling application.

The assistant must recommend the next business action based on the current state of:

- user role and permissions
- active plan/version status
- demand readiness
- cargo layer readiness
- tide/bridge/window readiness
- assignment readiness
- conflicts and blocking constraints
- overrides and impact chains
- telemetry/operational event candidates
- simulation scenario state
- approval status
- publish/export status
- audit sensitivity

It must integrate into existing frontend pages as a lightweight navigation and operation guide.

The assistant must support at least these modes:

```text
off       → no assistive UI except hard disabled reasons where required
assisted  → default; global next action, page hints, row hints, disabled reasons
guided    → step-by-step operational checklist and highlighted CTA
supervisor → cross-role control-tower view of pending actions and owners
```

The first build may implement `off` and `assisted`, with schema support for `guided` and `supervisor`.

---

## 2. Non-goals

The first implementation must not:

- use an LLM to decide operational actions
- bypass existing permissions
- bypass approval or publish governance
- mutate business state from the recommendation endpoint
- hide existing controls from expert users
- recommend actions that are not present in the action registry
- fabricate risks that are not present in current read models
- create a separate chatbot-first workflow

Optional later LLM usage is allowed only for explanation phrasing after deterministic action selection.

---

## 3. Existing application surfaces to integrate

| Route | Page/component | Assistant role |
|---|---|---|
| `/dashboard/situation` | `DashboardPage.tsx` | Global action inbox and top ranked system state. |
| `/admin/master-data` | `MasterDataPage.tsx` | Master data readiness, catalog-level blockers, validate/import/export guidance. |
| `/admin/users-rbac` | `RbacPage.tsx` | RBAC setup gaps and role-scope guidance. |
| `/schedule/ogv-demand` | `OgvDemandPage.tsx` | Demand import/readiness guidance. |
| `/schedule/coal-grade-sequence` | `CoalGradeSequencePage.tsx` | Cargo layer and hatch sequence readiness guidance. |
| `/constraints/tide-bridge` | `TideBridgePage.tsx` | Operating window readiness and feasibility guidance. |
| `/operations/tug-barge-assignment` | `LogisticsPages.tsx` | Generate/regenerate plan and assignment-level next action hints. |
| `/operations/jetty-loading` | `LogisticsPages.tsx` | Event confirmation, override caution, jetty actualization guidance. |
| `/operations/cts-floating-crane` | `LogisticsPages.tsx` | CTS event confirmation and discharge-risk guidance. |
| `/schedule/published-plan` | `RecoveryPages.tsx` | Draft/create/submit approval lifecycle guidance. |
| `/exceptions/center` | `RecoveryPages.tsx` | Exception triage, create scenario, simulate, promote. |
| `/simulation/workspace` | `RecoveryPages.tsx` | Scenario assumption/run/promote/submission guidance. |
| `/approvals/publishing` | `RecoveryPages.tsx` | Approve/reject/publish next action guidance. |
| `/map/live` | `MapPage.tsx` | Signal health, ETA risk, alert-to-exception guidance. |
| `/operations/event-confirmation` | `OperationsEventConsolePage.tsx` | Confirm/reject/manual-review candidate guidance. |
| `/admin/export-handoff` | `ExportHandoffPage.tsx` | Governed export timing and artifact readiness guidance. |
| `/admin/audit-logs` | `AuditPage.tsx` | Audit verification and traceability guidance. |

---

## 4. Core architecture

### 4.1 Add backend assistant module

Preferred new Django app:

```text
backend/apps/assistant/
  __init__.py
  apps.py
  urls.py
  views.py
  serializers.py
  services.py
  registry.py
  rules.py
  selectors.py
  permissions.py
  tests/
```

Alternative if the project wants fewer apps:

```text
backend/apps/scheduling/assistant/
```

However, a separate `assistant` app is recommended because it reads across `planning`, `scheduling`, `operations`, `telemetry`, `rbac`, `masters`, and `audit`.

### 4.2 Add API endpoint

```text
GET /api/assistant/next-actions/
```

Query parameters:

| Parameter | Optional | Purpose |
|---|---:|---|
| `route` | yes | Current frontend route for page-specific recommendations. |
| `object_type` | yes | Scope to row/object recommendation. |
| `object_id` | yes | Object identifier. |
| `mode` | yes | `off`, `assisted`, `guided`, `supervisor`. Default from user preference or `assisted`. |
| `limit` | yes | Max recommendations to return. Default 10. |

Example:

```http
GET /api/assistant/next-actions/?route=/exceptions/center&mode=assisted
```

### 4.3 Response schema

```json
{
  "generated_at": "2026-05-18T14:00:00Z",
  "mode": "assisted",
  "context": {
    "route": "/exceptions/center",
    "active_plan_version_id": 12,
    "active_plan_status": "generated",
    "validation_status": "warning",
    "role_profile": "berau_scheduler"
  },
  "global_next_action": {
    "action_id": "OPEN_EXCEPTION_CENTER",
    "label": "Resolve blocking conflicts",
    "priority": "critical",
    "rank_score": 950,
    "enabled": true,
    "route": "/exceptions/center",
    "cta_label": "Open exceptions",
    "reason": "The active plan has 2 blocking conflicts.",
    "impact_if_ignored": "The plan cannot be submitted or published until blockers are resolved.",
    "owner_role": "berau_scheduler",
    "audit_required": false,
    "target_object_type": "conflict",
    "target_object_id": null,
    "blocked_reason": ""
  },
  "page_actions": [],
  "row_actions": [],
  "blocked_actions": [],
  "checklist": []
}
```

### 4.4 Recommendation object schema

Canonical backend shape:

```python
@dataclass(frozen=True)
class ActionRecommendation:
    action_id: str
    label: str
    priority: str                 # critical | warning | normal | info
    rank_score: int
    enabled: bool
    route: str
    cta_label: str
    reason: str
    hover_hint: str
    detail_text: str
    impact_if_ignored: str
    owner_role: str
    required_permission: str | None
    audit_required: bool
    target_object_type: str | None
    target_object_id: str | None
    blocked_reason: str
    source: str                    # rule id that emitted it
    expires_at: datetime | None
    metadata: dict
```

Frontend TypeScript shape should mirror this, using camelCase.

---

## 5. Deterministic evaluation model

### 5.1 Inputs

The assistant should read from current repo read models rather than introduce a duplicate state store.

Minimum selectors:

```text
select_current_user_context(user)
select_active_plan_version(user)
select_dashboard_situation(user)
select_planning_readiness(user)
select_master_data_readiness(user)
select_conflict_summary(user)
select_approval_status(user)
select_export_status(user)
select_pending_event_candidates(user)
select_operational_actualization_risks(user)
select_simulation_status(user)
select_telemetry_alerts(user)
```

### 5.2 Rule execution order

Rules should execute in this order:

1. permission and scope shaping
2. planning readiness
3. constraint readiness
4. active plan lifecycle
5. operational blockers
6. event confirmation candidates
7. exceptions and simulation
8. approval and publish lifecycle
9. export lifecycle
10. audit/check evidence
11. route-specific hints
12. object-specific hints

### 5.3 Ranking

Suggested base ranking:

| Priority | Base score |
|---|---:|
| `critical` | 900 |
| `warning` | 700 |
| `normal` | 500 |
| `info` | 300 |

Modifiers:

| Condition | Score modifier |
|---|---:|
| action blocks publish | +80 |
| action is owned by current user | +70 |
| action has SLA breach | +60 |
| action affects current route | +40 |
| action affects selected object | +30 |
| action is already completed | exclude or return checklist complete |
| current user lacks permission | include only in `blocked_actions`, not `global_next_action` |

### 5.4 Dedupe

Recommendations must dedupe by:

```text
(action_id, target_object_type, target_object_id)
```

When duplicates exist, keep the highest `rank_score` and merge reason metadata where useful.

---

## 6. Required first-sprint action coverage

The first implementation must support these action IDs:

```text
IMPORT_OGV_DEMAND
REVIEW_COAL_SEQUENCE
ENTER_OPERATING_WINDOWS
GENERATE_PLAN
REGENERATE_PLAN
CREATE_DRAFT
OPEN_EXCEPTION_CENTER
CREATE_SCENARIO
RUN_SIMULATION
PROMOTE_SCENARIO
SUBMIT_APPROVAL
APPROVE_PLAN
REJECT_PLAN
PUBLISH_PLAN
CONFIRM_EVENT
REJECT_EVENT
FORCE_START_JETTY
GENERATE_EXPORT
REVIEW_AUDIT
REVIEW_MASTER_DATA
```

The registry document defines details.

---

## 7. Frontend experience

### 7.1 Add mode storage

For first implementation, local storage is sufficient:

```text
localStorage.assistantMode = off | assisted | guided | supervisor
```

Later migration: store in backend user profile.

### 7.2 Add API client

In `frontend/src/lib/api.ts`:

```ts
export async function fetchNextActions(params: NextActionParams): Promise<NextActionResponse> {
  const query = new URLSearchParams();
  if (params.route) query.set("route", params.route);
  if (params.objectType) query.set("object_type", params.objectType);
  if (params.objectId) query.set("object_id", String(params.objectId));
  if (params.mode) query.set("mode", params.mode);
  return apiFetch<NextActionResponse>(`/assistant/next-actions/?${query.toString()}`);
}
```

### 7.3 Add hook

```text
frontend/src/hooks/useNextActions.ts
```

Responsibilities:

- read assistant mode
- call API on route changes and workspace sync
- expose `globalNextAction`, `pageActions`, `rowActions`, `blockedActions`, `checklist`
- fail closed: hide assistant if API fails, but do not break cockpit

### 7.4 Add reusable components

```text
frontend/src/components/assistant/AssistantModeToggle.tsx
frontend/src/components/assistant/NextActionPill.tsx
frontend/src/components/assistant/ActionInboxPanel.tsx
frontend/src/components/assistant/RecommendationCard.tsx
frontend/src/components/assistant/DisabledReasonTooltip.tsx
frontend/src/components/assistant/GuidedChecklist.tsx
frontend/src/components/assistant/RowActionHint.tsx
```

### 7.5 Page integration priority

Integrate in this order:

1. `App.tsx` shell / topbar global next-action pill
2. `DashboardPage.tsx` action inbox
3. `RecoveryPages.tsx` Exception Center / Simulation / Approvals / Published Plan
4. `LogisticsPages.tsx` Tug/Barge, Jetty, CTS
5. `TideBridgePage.tsx`
6. `OperationsEventConsolePage.tsx`
7. `ExportHandoffPage.tsx`
8. `MasterDataPage.tsx`
9. `MapPage.tsx`
10. `AuditPage.tsx`

---

## 8. Backend acceptance criteria

The backend is acceptable when:

1. `GET /api/assistant/next-actions/` returns 200 for authenticated users.
2. Unauthenticated access is rejected consistently with existing auth.
3. Returned recommendations are permission-shaped.
4. No recommendation endpoint mutates business state.
5. The top recommendation is deterministic for the same seed data.
6. Blocking conflicts produce `OPEN_EXCEPTION_CENTER` above approval/publish recommendations.
7. Approval recommendations are shown only to users with appropriate authority.
8. Publish recommendation appears only after approval completion.
9. Export recommendation appears only after publish or valid internal export context.
10. Tests cover no-demand, demand-no-windows, windows-no-plan, plan-blocked, plan-ready, approval-pending, publish-ready, export-ready, event-candidate, and telemetry-risk cases.

---

## 9. Frontend acceptance criteria

The frontend is acceptable when:

1. The user can switch assistant mode off/assisted.
2. Assisted mode shows a global next action in the shell.
3. Dashboard shows action inbox.
4. Page-level recommendation card appears on key pages.
5. Disabled buttons show reason where blocked action is returned.
6. Clicking a recommendation navigates to the correct route.
7. If route matches the current page, the CTA scrolls/highlights the target area where feasible.
8. API failure does not break existing cockpit screens.
9. Expert mode/off mode suppresses nonessential nudges.
10. Existing tests continue to pass.

---

## 10. Rollout plan

### Sprint 1 — Backend core and shell UI

- Add backend assistant app.
- Add registry, selectors, rules, serializers, endpoint.
- Add first 20 action IDs.
- Add frontend API types/client/hook.
- Add topbar `NextActionPill`.
- Add dashboard action inbox.

### Sprint 2 — Operational pages

- Add recommendation cards to Exception Center, Published Plan, Approvals, Simulation.
- Add row hints to assignment, jetty, CTS, event candidate rows.
- Add disabled reason tooltips for publish/approve/submit/regenerate/export.

### Sprint 3 — Guided mode

- Add checklist schema and UI.
- Add step grouping.
- Add route-based walkthrough.
- Add UAT training seed scenario.

### Sprint 4 — Governance hardening

- Add assistant registry tests.
- Add CI check that new mutating routes have assistant metadata.
- Add docs update check.
- Add audit verification for governed recommendations.

---

## 11. Mandatory implementation constraints

- Read `agent.md` first before coding.
- Preserve existing auth, RBAC, and audit behavior.
- Do not rename existing routes without updating navigation and assistant registry.
- Do not introduce dynamic SQL or unbounded query logic.
- Do not call LLM from request path.
- Keep assistant endpoint fast; target less than 250 ms against seed data.
- Fail closed if an input state is missing.
- Prefer no recommendation over a wrong recommendation.
- Recommendations must be explainable by a `source` rule ID.
