# Next Action Assist - Chunked Implementation Plan

## 1. Purpose

This plan turns the Next Action Assist documentation pack into an implementation sequence that can be built, reviewed, and verified in bounded chunks.

The target implementation is a deterministic, registry-backed assistant:

```text
Business state -> read-only selectors -> deterministic rules -> permission-shaped recommendations -> UI hints and CTAs
```

It must not become a chatbot workflow, must not bypass RBAC or approval governance, and must not mutate state from the recommendation endpoint.

## 2. Implementation Methodology

Use vertical, testable chunks. Each chunk should leave the repository in a working state and should include the smallest useful combination of backend, frontend, and tests.

Chunk rules:

- Keep each chunk reviewable. Prefer one clear capability per chunk.
- Add contract tests before broad page integration.
- Keep backend recommendation logic pure and read-only.
- Add frontend UI behind assistant mode behavior so it can fail closed.
- Preserve existing routes, handlers, permissions, audit behavior, and page workflows.
- Do not add action labels directly in pages if the action belongs in the registry.
- Do not ship a top-ranked disabled recommendation.
- Update tests and documentation whenever workflow behavior changes.

Recommended delivery order:

1. Foundation and contracts.
2. Backend registry, selectors, and rules.
3. API endpoint and response contract.
4. Frontend client, hook, and shell integration.
5. Page-level integrations.
6. Row hints, disabled reasons, and guided checklist scaffolding.
7. Governance checks and release hardening.

## 3. Cross-Cutting Contracts

### 3.1 Backend Contract

Add a backend assistant module:

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

Expose:

```http
GET /api/assistant/next-actions/
```

Supported query params:

```text
route
object_type
object_id
mode
limit
```

Response shape:

```text
generated_at
mode
context
global_next_action
page_actions
row_actions
blocked_actions
checklist
```

### 3.2 Frontend Contract

Add assistant types, API client, hook, and components:

```text
frontend/src/types/assistant.ts
frontend/src/hooks/useNextActions.ts
frontend/src/components/assistant/
  AssistantModeToggle.tsx
  NextActionPill.tsx
  ActionInboxPanel.tsx
  RecommendationCard.tsx
  DisabledReasonTooltip.tsx
  GuidedChecklist.tsx
  RowActionHint.tsx
  index.ts
```

The frontend should normalize backend snake_case into camelCase and hide assistive UI when mode is `off` or the API fails.

### 3.3 Initial Action Coverage

The first implementation must cover these action IDs:

```text
IMPORT_OGV_DEMAND
REVIEW_COAL_SEQUENCE
ENTER_OPERATING_WINDOWS
REVIEW_MASTER_DATA
GENERATE_PLAN
REGENERATE_PLAN
CREATE_DRAFT
OPEN_EXCEPTION_CENTER
CREATE_SCENARIO
ADD_ASSUMPTION
RUN_SIMULATION
PROMOTE_SCENARIO
SUBMIT_APPROVAL
APPROVE_PLAN
REJECT_PLAN
PUBLISH_PLAN
CONFIRM_EVENT
REJECT_EVENT
FORCE_START_JETTY
REVIEW_SIGNAL_HEALTH
GENERATE_EXPORT
REVIEW_AUDIT
```

## 4. Chunk 0 - Repository Alignment and Baseline

### Objective

Confirm current app structure, test commands, route ownership, auth patterns, and data model names before writing assistant code.

### Scope

- Read `agent.md` if present.
- Confirm backend framework setup, installed apps, root URL routing, auth classes, and test conventions.
- Confirm frontend routing ownership in `frontend/src/App.tsx`.
- Confirm current handlers listed in `02_ACTION_REGISTRY.md` still exist.
- Identify existing dashboard/overview services that can be reused by assistant selectors.
- Record exact backend and frontend test commands.

### Deliverables

- Short implementation notes in the PR or work log.
- No production behavior changes.

### Acceptance

- The implementation can name the correct settings file, URL include location, auth permission helpers, and test commands.
- Any mismatch between the documentation pack and current repo code is listed before Chunk 1 begins.

## 5. Chunk 1 - Backend Assistant App Skeleton and Registry

### Objective

Create the backend assistant app and canonical action registry without introducing business rule evaluation yet.

### Files

```text
backend/apps/assistant/apps.py
backend/apps/assistant/registry.py
backend/apps/assistant/services.py
backend/apps/assistant/tests/test_action_registry.py
backend/settings or project settings module
backend URL routing module
```

### Implementation

1. Register the new Django app.
2. Add `AssistantActionDefinition`.
3. Add `ACTION_REGISTRY` with all first-sprint action IDs.
4. Add `get_action_definition(action_id)`.
5. Add `ActionRecommendation` and `build_recommendation`.
6. Validate duplicate IDs at import or test time.

### Tests

- Registry loads.
- All required first-sprint action IDs exist.
- Every action has label, route, CTA label, owner role, UI placement, and fallback message.
- Mutating/governed actions declare `audit_required=true`.
- `build_recommendation` fills registry defaults correctly.

### Acceptance

- Registry is the single backend source of action metadata.
- No assistant rule can emit an action ID that is absent from the registry.

## 6. Chunk 2 - Read-Only Context Selectors

### Objective

Build the assistant context from existing read models without duplicating business state or mutating the database.

### Files

```text
backend/apps/assistant/selectors.py
backend/apps/assistant/permissions.py
backend/apps/assistant/tests/test_selectors.py
```

### Implementation

1. Add `AssistantContext`.
2. Implement permission selector using existing RBAC/data-scope helpers.
3. Implement active plan selector.
4. Implement planning readiness counts.
5. Implement conflict counts.
6. Implement approval/publish/export status selectors.
7. Implement event candidate, telemetry alert, and simulation counts.
8. Add `build_assistant_context(user, route, object_type, object_id, mode)`.

### Selector Discipline

- Prefer existing overview/dashboard services where available.
- Use `.count()`, `.exists()`, and bounded queries.
- Scope by organization/site/role exactly as existing cockpit APIs do.
- Fail closed when a state source is unavailable.

### Tests

- Context builds for representative authenticated users.
- Unknown route does not crash.
- Unknown object ID does not crash.
- Selectors do not create or update records.
- Permission set matches existing RBAC behavior for representative roles.

### Acceptance

- Rule code can evaluate the full first-sprint workflow from `AssistantContext`.
- Context building is read-only and bounded.

## 7. Chunk 3 - Rule Engine, Ranking, Dedupe, and Permission Shaping

### Objective

Implement deterministic recommendations from assistant context and shape them by permissions.

### Files

```text
backend/apps/assistant/rules.py
backend/apps/assistant/services.py
backend/apps/assistant/tests/test_planning_rules.py
backend/apps/assistant/tests/test_exception_rules.py
backend/apps/assistant/tests/test_approval_publish_export_rules.py
backend/apps/assistant/tests/test_operations_event_rules.py
backend/apps/assistant/tests/test_permission_shaping.py
```

### Implementation

1. Add `RULES` list in explicit execution order.
2. Implement planning readiness rules:
   - `planning.no_demand`
   - `planning.sequence_review_needed`
   - `planning.missing_windows`
   - `planning.ready_to_generate`
3. Implement plan lifecycle rules:
   - `plan.published_needs_draft`
   - `plan.editable_stale_regenerate`
4. Implement exception and simulation rules:
   - `exceptions.blocking_conflicts`
   - `exceptions.create_scenario`
   - `scenario.ready_to_run`
   - `scenario.promotable`
5. Implement approval, publish, and export rules:
   - `approval.ready_to_submit`
   - `approval.user_decision_pending`
   - `publish.ready`
   - `export.published_without_export`
6. Implement operations and telemetry rules:
   - `operations.high_confidence_event`
   - `operations.noisy_event`
   - `operations.override_risk`
   - `telemetry.stale_signal`
7. Implement audit support rule:
   - `audit.after_governed_mutation`
8. Add dedupe by `(action_id, target_object_type, target_object_id)`.
9. Add sorting by rank score, priority, route match, and object match.
10. Add permission shaping:
    - Enabled recommendations only when user has required permission.
    - Current-route blocked actions returned with blocked reason.
    - No target-route visibility means omit.

### Ranking Requirements

- Blocking conflicts outrank approval, publish, and export.
- Approval decisions outrank publish until approvals are complete.
- Publish outranks export until published.
- High-confidence event confirmation outranks low-priority audit review.
- Published-plan changes recommend `CREATE_DRAFT` before regeneration.

### Tests

- No demand recommends `IMPORT_OGV_DEMAND`.
- Demand with missing windows recommends `ENTER_OPERATING_WINDOWS`.
- Ready planning state recommends `GENERATE_PLAN`.
- Blocking conflict top action is `OPEN_EXCEPTION_CENTER`.
- Blocking conflict prevents submit/publish/export from becoming top action.
- Current user pending approval recommends `APPROVE_PLAN`.
- Other user's pending approval does not recommend enabled `APPROVE_PLAN`.
- All approvals complete recommends `PUBLISH_PLAN` only to publish-authorized user.
- Published plan without export recommends `GENERATE_EXPORT`.
- High-confidence event candidate recommends `CONFIRM_EVENT`.
- User without permission gets blocked explanation or omission as defined.

### Acceptance

- Same seed state returns the same sorted recommendations.
- Every recommendation has a `source` rule ID and registry-backed metadata.
- Disabled recommendations cannot become `global_next_action`.

## 8. Chunk 4 - API Endpoint and Serialization

### Objective

Expose the assistant response contract through an authenticated, read-only API endpoint.

### Files

```text
backend/apps/assistant/serializers.py
backend/apps/assistant/views.py
backend/apps/assistant/urls.py
backend/apps/assistant/tests/test_next_actions_api.py
```

### Implementation

1. Add recommendation serializer.
2. Add next-actions response serializer.
3. Add `get_next_actions(user, route, object_type, object_id, mode, limit)`.
4. Add `NextActionsView`.
5. Include assistant URLs under `/api/assistant/`.
6. Support `mode=off` by returning no nonessential recommendations.
7. Apply `limit` after sorting and shaping.

### Tests

- Unauthenticated request is rejected consistently with project auth.
- Authenticated request returns 200 and contract shape.
- `mode=off` returns empty global/page/row recommendations.
- Unknown route returns global recommendations and no crash.
- Unknown object returns no row actions and no crash.
- Same seed state repeated returns the same top action.
- Endpoint does not mutate business tables.

### Acceptance

- `/api/assistant/next-actions/` is safe to call from any cockpit route.
- API failure behavior can be handled by frontend without affecting existing pages.

## 9. Chunk 5 - Frontend Types, API Client, Hook, and Mode Storage

### Objective

Add frontend data plumbing while keeping UI impact minimal.

### Files

```text
frontend/src/types/assistant.ts
frontend/src/lib/api.ts
frontend/src/hooks/useNextActions.ts
frontend/src/hooks/useAssistantMode.ts
frontend/src/components/assistant/index.ts
```

### Implementation

1. Add `AssistantMode`, `AssistantPriority`, `ActionRecommendation`, `AssistantChecklistItem`, and `NextActionResponse` types.
2. Add `normalizeNextActionResponse(raw)` for snake_case to camelCase mapping.
3. Add `fetchNextActions(params)`.
4. Add `useAssistantMode()` with `localStorage` key `ocean.assistantMode`.
5. Add `useNextActions(route, options)`.
6. Fail closed on API errors by preserving page functionality and hiding nonessential assistant UI.

### Tests

- Normalizer maps all fields.
- Missing optional arrays normalize to empty arrays if needed.
- Mode defaults to `assisted`.
- Mode can switch to `off`.
- Hook does not call API when mode is `off`.
- Hook handles API rejection without throwing into page render.

### Acceptance

- Frontend can consume assistant API from any route.
- Assisted/off mode state persists locally.

## 10. Chunk 6 - Shell UI and Dashboard Action Inbox

### Objective

Deliver the first visible vertical slice: global next action in the shell and action inbox on dashboard.

### Files

```text
frontend/src/components/assistant/AssistantModeToggle.tsx
frontend/src/components/assistant/NextActionPill.tsx
frontend/src/components/assistant/ActionInboxPanel.tsx
frontend/src/pages/DashboardPage.tsx
frontend/src/App.tsx
frontend/src/components/Topbar.tsx
frontend styles used by the app
```

### Implementation

1. Mount `useNextActions(activePath)` near route state in `App.tsx`.
2. Add `NextActionPill` to topbar or shell.
3. Add `AssistantModeToggle` near user/workspace controls.
4. Add dashboard `ActionInboxPanel`.
5. Click on enabled recommendation navigates to `action.route`.
6. Disabled recommendation shows blocked reason and does not navigate.
7. Keep UI compact and consistent with existing cockpit styling.

### Tests

- Pill hidden when action is null.
- Pill renders label and priority tone.
- Pill navigates when enabled.
- Pill does not navigate when disabled.
- Dashboard inbox renders top recommendations.
- Assisted mode shows assistant UI.
- Off mode hides assistant UI.

### Acceptance

- A user can see and navigate from the top recommended action.
- Existing dashboard controls and route navigation still work.

## 11. Chunk 7 - Core Page Recommendation Cards

### Objective

Integrate page-level recommendations into the highest-value workflow pages.

### Files

```text
frontend/src/components/assistant/RecommendationCard.tsx
frontend/src/pages/RecoveryPages.tsx
frontend/src/pages/LogisticsPages.tsx
frontend/src/pages/TideBridgePage.tsx
frontend/src/pages/OperationsEventConsolePage.tsx
frontend/src/pages/ExportHandoffPage.tsx
```

### Pages

Integrate in this order:

1. Published Plan.
2. Approvals.
3. Exception Center.
4. Simulation Workspace.
5. Tug/Barge Assignment.
6. Tide/Bridge.
7. Event Confirmation.
8. Export Handoff.

### Implementation

- Pass `assistant.data?.pageActions`, `blockedActions`, `rowActions`, and `checklist` as optional props.
- Render one primary recommendation and compact secondary actions.
- Do not refactor page business handlers unless needed for action mapping.
- Use action routes and CTA labels from API response.
- Preserve existing buttons for expert users.

### Tests

- Each core page renders without assistant data.
- Each core page renders recommendation card with assistant data.
- CTA navigation uses recommendation route.
- Null action state is compact and non-disruptive.

### Acceptance

- Page-level guidance exists for the required first milestone pages.
- Existing page workflows remain available and unchanged.

## 12. Chunk 8 - Disabled Reasons and Row-Level Hints

### Objective

Connect blocked actions and object-specific recommendations to existing dense operational workflows.

### Files

```text
frontend/src/components/assistant/DisabledReasonTooltip.tsx
frontend/src/components/assistant/RowActionHint.tsx
frontend/src/pages/LogisticsPages.tsx
frontend/src/pages/OperationsEventConsolePage.tsx
frontend/src/pages/RecoveryPages.tsx
frontend/src/pages/ExportHandoffPage.tsx
```

### Implementation

1. Add `DisabledReasonTooltip` around publish, approval, regenerate, export, event confirm/reject, and governed override controls where blocked actions map cleanly.
2. Add `RowActionHint` for:
   - assignments
   - operational event candidates
   - conflicts
   - alerts
3. Match row hints by `targetObjectType` and `targetObjectId`.
4. Keep hints compact to avoid table clutter.

### Tests

- Tooltip finds matching blocked action by action ID.
- Tooltip shows blocked reason.
- Tooltip does not change child button handler.
- Row hint filters by object type and object ID.
- Row hint renders nothing when no matching action exists.

### Acceptance

- Users see why key governed actions are blocked.
- Dense operational rows can expose relevant next action without changing table layout.

## 13. Chunk 9 - Checklist and Guided Mode Scaffolding

### Objective

Add schema-compatible guided checklist support without making guided mode a dependency for first release.

### Files

```text
backend/apps/assistant/services.py
frontend/src/components/assistant/GuidedChecklist.tsx
frontend/src/pages/RecoveryPages.tsx
frontend/src/pages/DashboardPage.tsx
```

### Implementation

1. Add checklist builder for lifecycle stages:
   - Demand imported
   - Cargo sequence reviewed
   - Operating windows entered
   - Plan generated
   - Exceptions resolved
   - Approval submitted
   - Approval completed
   - Plan published
   - Export generated
2. Return checklist in assisted mode when useful.
3. Keep guided mode disabled or preview-labeled until fully supported.
4. Render read-only checklist on dashboard or simulation workspace where it helps.

### Tests

- Checklist marks completed stages correctly.
- Current blocked stage maps to the expected action ID.
- Guided mode request does not crash even if full guided UI is deferred.

### Acceptance

- Response contract supports guided rollout later.
- First release remains assisted/off focused.

## 14. Chunk 10 - Remaining Page Coverage

### Objective

Complete first-milestone and secondary surface coverage.

### Files

```text
frontend/src/pages/OgvDemandPage.tsx
frontend/src/pages/CoalGradeSequencePage.tsx
frontend/src/pages/MasterDataPage.tsx
frontend/src/pages/MapPage.tsx
frontend/src/pages/AuditPage.tsx
frontend/src/pages/RecoveryPages.tsx
frontend/src/pages/LogisticsPages.tsx
```

### Implementation

Add compact recommendation cards or hints for:

- OGV Demand.
- Coal Grade Sequence.
- Master Data.
- Map.
- Audit Logs.
- Jetty Loading.
- CTS / Floating Crane.

### Tests

- Each page renders with and without assistant data.
- Route-specific action appears only where relevant.
- Map and audit hints stay low-priority unless operational severity requires otherwise.

### Acceptance

- All routes listed in the documentation pack have explicit assistant behavior or a documented exemption.

## 15. Chunk 11 - Governance and CI Checks

### Objective

Prevent the assistant from drifting away from the governed workflow after the initial build.

### Files

```text
backend/apps/assistant/tests/test_action_registry.py
backend/apps/assistant/tests/test_governance.py
frontend assistant/component tests
documentation in docs/next_action_assist_doc_pack/
optional CI scripts
```

### Implementation

1. Assert all emitted action IDs exist in registry.
2. Assert no top-ranked recommendation is disabled.
3. Assert blocking conflicts prevent publish/export top recommendations.
4. Assert every registry action has route ownership.
5. If frontend adds `data-action-id`, add a check that IDs map to registry.
6. Document any route or action exemptions.

### Tests

- Registry uniqueness.
- Route ownership completeness.
- Mutating action audit requirements.
- Endpoint non-mutation.
- Permission shaping.

### Acceptance

- New workflow actions require registry and rule/test updates.
- CI catches common assistant governance regressions.

## 16. Chunk 12 - End-to-End UAT and Release Hardening

### Objective

Validate the assistant against operator workflows and prepare for release.

### UAT Scripts

Run and record:

1. Happy path:
   - import demand
   - review sequence
   - enter windows
   - generate plan
   - submit approval
   - approve
   - publish
   - export
2. Blocking conflict path:
   - blocking conflict
   - Exception Center
   - create scenario
   - run simulation
   - promote
   - approval lifecycle
3. Event confirmation path:
   - high-confidence candidate
   - confirm event
   - actualization risk
   - exception/scenario guidance
4. Published-plan change path:
   - published plan
   - demand or constraint change
   - create draft
   - regenerate draft
   - approval/publish/export

### Performance Checks

- Assistant endpoint p95 below 250 ms against seed data.
- No unbounded query materialization.
- API failure does not break cockpit screens.

### Visual Checks

Capture dashboard, Exception Center, Approvals, Event Console, Export Handoff, and shell/topbar screenshots in assisted and off modes.

### Acceptance

- All existing tests pass.
- All new backend tests pass.
- All new frontend tests pass.
- UAT scripts produce the expected action sequence.
- Release notes list assistant scope, known limitations, and deferred guided/supervisor behavior.

## 17. Suggested Milestone Mapping

### Milestone 1 - First Working Vertical Slice

Chunks:

- 0 Repository alignment
- 1 Backend registry
- 2 Context selectors
- 3 Core rules
- 4 API endpoint
- 5 Frontend client/hook
- 6 Shell and dashboard UI

Result:

- `/api/assistant/next-actions/` works.
- Global next-action pill works.
- Dashboard action inbox works.
- Core workflow recommendations are deterministic and tested.

### Milestone 2 - Operational Workflow Coverage

Chunks:

- 7 Core page cards
- 8 Disabled reasons and row hints
- 10 Remaining page coverage

Result:

- Required first-milestone pages show page-level recommendations.
- Blocked governed actions explain why they are blocked.
- Event candidates, assignments, conflicts, and alerts can show row hints.

### Milestone 3 - Governance and Release

Chunks:

- 9 Checklist scaffolding
- 11 Governance and CI checks
- 12 UAT and release hardening

Result:

- Assistant behavior is protected against drift.
- Guided mode has compatible response scaffolding.
- UAT proves the happy path, exception path, event path, and published-plan change path.

## 18. Definition of Done

The implementation is complete when:

- Backend assistant app is registered and tested.
- Canonical action registry covers first-sprint action IDs.
- `/api/assistant/next-actions/` returns deterministic, permission-shaped recommendations.
- Recommendation endpoint is read-only.
- Frontend API client, hook, mode storage, and normalization are implemented.
- Shell global next-action pill works.
- Dashboard action inbox works.
- Recommendation cards exist on required first-milestone pages.
- Disabled reasons exist for approval, publish, regenerate, export, and event actions where applicable.
- Row hints work for object-scoped recommendations.
- Assisted/off modes work.
- Existing tests pass.
- New backend and frontend tests pass.
- Governance checks prevent action registry and route ownership drift.
- Documentation is updated for any behavior that differs from this plan.
