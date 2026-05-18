# Next Action Assist Documentation Pack

## Purpose

This documentation pack converts the repo scan and user-flow assessment into an implementation-ready specification for building a deterministic **Next Action Assist** layer into the existing Ocean coal transshipment scheduling codebase.

The objective is to make every major UI surface capable of answering:

1. What is the current business state?
2. What is blocking progress?
3. What should the user do next?
4. Who owns that action?
5. Which UI surface/button should be used?
6. Why is the action safe, blocked, risky, or governed?

The assistant must stay aligned with the repo’s existing deterministic, governed, auditable design. It should not become an unconstrained chatbot. The first build should be a state-machine and rule-based recommendation engine, with optional language polish later.

## Repo surfaces scanned

The implementation spec is aligned to the current structure observed in the repo:

```text
backend/apps/audit
backend/apps/core
backend/apps/masters
backend/apps/operations
backend/apps/planning
backend/apps/rbac
backend/apps/scheduling
backend/apps/telemetry
frontend/src/App.tsx
frontend/src/components/Sidebar.tsx
frontend/src/components/Topbar.tsx
frontend/src/pages/DashboardPage.tsx
frontend/src/pages/MasterDataPage.tsx
frontend/src/pages/OgvDemandPage.tsx
frontend/src/pages/CoalGradeSequencePage.tsx
frontend/src/pages/TideBridgePage.tsx
frontend/src/pages/LogisticsPages.tsx
frontend/src/pages/RecoveryPages.tsx
frontend/src/pages/OperationsEventConsolePage.tsx
frontend/src/pages/MapPage.tsx
frontend/src/pages/ExportHandoffPage.tsx
frontend/src/pages/AuditPage.tsx
frontend/src/lib/api.ts
frontend/src/types.ts
```

## Documents in this pack

| Document | Purpose |
|---|---|
| `01_IMPLEMENTATION_SPEC.md` | Core implementation specification for backend, frontend, API, state model, and rollout phases. |
| `02_ACTION_REGISTRY.md` | Canonical action registry with IDs, routes, permissions, eligibility, blocked states, and UI placement. |
| `03_BACKEND_RECOMMENDATION_ENGINE_SPEC.md` | Detailed backend design for deterministic rule evaluation, serializers, endpoint, and tests. |
| `04_FRONTEND_INTEGRATION_SPEC.md` | Detailed React integration plan: assisted mode state, components, page embedding, and API usage. |
| `05_GOVERNANCE_AND_CHANGE_CONTROL.md` | Governance rules so future features keep assistant recommendations aligned. |
| `06_TESTING_AND_ACCEPTANCE_PLAN.md` | Unit, API, frontend, e2e, regression, and UAT acceptance criteria. |
| `07_CODEX_AGENT_BUILD_PROMPT.md` | Ready-to-use Codex implementation prompt for applying this pack to the repo. |

## Implementation principle

The assistant must be built as:

```text
Business state → deterministic rule evaluation → recommended next action → UI hint / CTA / disabled reason
```

Not as:

```text
User asks chatbot → assistant guesses next step
```

## Required first milestone

The first implementation should produce:

1. A backend `assistant` app or equivalent module.
2. A canonical action registry.
3. A `/api/assistant/next-actions/` endpoint.
4. A frontend `useNextActions` hook.
5. A global `NextActionPill` in the topbar or shell.
6. Page-level recommendation cards on Dashboard, Exception Center, Published Plan, Approvals, Tug/Barge, Tide/Bridge, Event Console, and Export Handoff.
7. Tests proving that blocked actions, role-sensitive actions, approval gates, publish gates, export gates, and event-confirmation gates are recommended correctly.
