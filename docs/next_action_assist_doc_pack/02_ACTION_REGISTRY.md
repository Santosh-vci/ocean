# Next Action Assist — Canonical Action Registry

## 1. Purpose

The action registry is the central contract between backend state rules and frontend UI guidance.

Every recommendation emitted by the assistant must map to an entry in this registry.

No page should invent recommendation labels or business actions independently. Page components may choose how to render a recommendation, but not redefine the meaning of the action.

---

## 2. Registry schema

Each action entry must define:

| Field | Required | Description |
|---|---:|---|
| `action_id` | yes | Stable uppercase identifier. |
| `label` | yes | Short human-readable name. |
| `description` | yes | What the action does. |
| `route` | yes | Default route for the action. |
| `cta_label` | yes | Button/link label. |
| `owner_roles` | yes | Roles likely to own the action. |
| `required_permission` | no | Permission code if required. |
| `audit_required` | yes | Whether action is governed/audited. |
| `eligible_when` | yes | Business state allowing recommendation. |
| `blocked_when` | yes | Business state that blocks the action. |
| `ui_placements` | yes | Shell, dashboard, page card, row hint, tooltip, checklist. |
| `mutating_endpoint` | no | Existing backend endpoint used when CTA performs mutation. |
| `read_only` | yes | Whether CTA is navigation only. |
| `fallback_message` | yes | Message when recommendation is blocked or cannot be shaped. |

---

## 3. Initial registry

### 3.1 Planning readiness actions

| Action ID | Label | Route | Permission | Audit | Eligibility | Blocked when | UI placement |
|---|---|---|---|---:|---|---|---|
| `IMPORT_OGV_DEMAND` | Import OGV demand | `/schedule/ogv-demand` | schedule edit / planning import authority | yes | No active demand or demand import needed | user lacks edit/import permission | Dashboard, OGV Demand page, checklist |
| `REVIEW_COAL_SEQUENCE` | Review coal grade sequence | `/schedule/coal-grade-sequence` | schedule view | no | Demand exists and cargo/layer sequence needs review | no demand exists | Dashboard, Coal Sequence page, checklist |
| `ENTER_OPERATING_WINDOWS` | Enter tide/bridge windows | `/constraints/tide-bridge` | schedule edit | yes | Demand exists and operating windows missing/incomplete | user lacks edit permission | Dashboard, Tide/Bridge page, checklist |
| `REVIEW_MASTER_DATA` | Review master data readiness | `/admin/master-data` | master data view | no | Master data dependency is missing/inactive | user lacks view permission | Dashboard, Master Data page, disabled reason |
| `REVIEW_RBAC` | Review RBAC coverage | `/admin/users-rbac` | admin view | no | Role, permission, and scope coverage needs governance review | user lacks admin visibility | Users & RBAC page |

### 3.2 Plan generation actions

| Action ID | Label | Route | Permission | Audit | Eligibility | Blocked when | UI placement |
|---|---|---|---|---:|---|---|---|
| `GENERATE_PLAN` | Generate plan | `/operations/tug-barge-assignment` | schedule edit | yes | Demand, cargo sequence, and windows ready; no generated editable plan exists | missing demand/windows/sequence or permission | Tug/Barge page, Dashboard, checklist |
| `REGENERATE_PLAN` | Regenerate plan | `/operations/tug-barge-assignment` | schedule edit | yes | Editable active plan exists and source constraints changed | active plan is published, submitted, approved, or user lacks edit | Tug/Barge page, Published Plan page |
| `CREATE_DRAFT` | Create successor draft | `/schedule/published-plan` | schedule edit | yes | Active plan is published/superseded and change is needed | no published/superseded plan or user lacks edit | Published Plan page, Dashboard |

### 3.3 Exception and recovery actions

| Action ID | Label | Route | Permission | Audit | Eligibility | Blocked when | UI placement |
|---|---|---|---|---:|---|---|---|
| `OPEN_EXCEPTION_CENTER` | Open Exception Center | `/exceptions/center` | exception view / schedule view | no | Blocking/critical conflict, alert, or override risk exists | no exception visibility | Shell pill, Dashboard, page cards |
| `CREATE_SCENARIO` | Create recovery scenario | `/exceptions/center` | simulation run | yes | Conflict/override/alert exists and is not already converted | user lacks simulation permission | Exception Center, Map, Jetty, CTS |
| `ADD_ASSUMPTION` | Add scenario assumption | `/simulation/workspace` | simulation run | yes | Scenario exists and needs assumption before run | scenario is not editable | Simulation page |
| `RUN_SIMULATION` | Run simulation | `/simulation/workspace` | simulation run | yes | Scenario has sufficient assumptions and has not been run or is stale | missing assumptions or permission | Simulation page |
| `PROMOTE_SCENARIO` | Promote scenario | `/simulation/workspace` | schedule edit | yes | Scenario run exists and improves/solves risk | no successful run or unresolved critical conflict | Simulation page, Exception Center |

### 3.4 Approval and publish actions

| Action ID | Label | Route | Permission | Audit | Eligibility | Blocked when | UI placement |
|---|---|---|---|---:|---|---|---|
| `SUBMIT_APPROVAL` | Submit approval | `/schedule/published-plan` | schedule edit | yes | Editable/generated/validated/proposed plan is feasible enough for approval | blocking conflicts, already submitted, user lacks edit | Published Plan, Simulation, Dashboard |
| `APPROVE_PLAN` | Approve plan | `/approvals/publishing` | schedule approve | yes | Approval request pending and current user has undecided authority | user not an approver or already decided | Approvals page, Shell pill |
| `REJECT_PLAN` | Reject plan | `/approvals/publishing` | schedule approve | yes | Approval request pending and plan is unacceptable | user not an approver or already decided | Approvals page |
| `PUBLISH_PLAN` | Publish plan | `/approvals/publishing` | schedule publish | yes | All approvals complete and plan is publishable | missing approval, blocking conflict, no publish permission | Approvals page, Dashboard |

### 3.5 Operations and event actualization actions

| Action ID | Label | Route | Permission | Audit | Eligibility | Blocked when | UI placement |
|---|---|---|---|---:|---|---|---|
| `CONFIRM_EVENT` | Confirm operational event | `/operations/event-confirmation` | operations confirm | yes | Pending high-confidence event candidate exists | duplicate/low confidence/stale device/user lacks permission | Event Console, Jetty, CTS, Map |
| `REJECT_EVENT` | Reject operational event | `/operations/event-confirmation` | operations confirm | yes | Pending candidate is duplicate/noisy/conflicting | user lacks permission | Event Console |
| `FORCE_START_JETTY` | Apply governed jetty override | `/operations/jetty-loading` | schedule edit / operations override | yes | Jetty actual differs materially from plan and override is allowed | published/locked plan, no reason, no permission | Jetty page only |
| `REVIEW_SIGNAL_HEALTH` | Review signal health | `/map/live` | telemetry view | no | Active asset has stale signal/low confidence | user lacks telemetry visibility | Map, Exception Center |

### 3.6 Export and audit actions

| Action ID | Label | Route | Permission | Audit | Eligibility | Blocked when | UI placement |
|---|---|---|---|---:|---|---|---|
| `GENERATE_EXPORT` | Generate governed export | `/admin/export-handoff` | export generate | yes | Plan published/approved or internal review export allowed | plan not ready/final export before publish/no permission | Export page, Dashboard |
| `REVIEW_AUDIT` | Review audit trail | `/admin/audit-logs` | audit view | no | Governed mutation occurred or audit verification needed | user lacks audit permission | Audit page, shell support action |

---

## 4. Route-to-action ownership

| Route | Primary actions |
|---|---|
| `/dashboard/situation` | all global actions, ranked |
| `/schedule/ogv-demand` | `IMPORT_OGV_DEMAND`, `REVIEW_COAL_SEQUENCE` |
| `/schedule/coal-grade-sequence` | `REVIEW_COAL_SEQUENCE`, `ENTER_OPERATING_WINDOWS` |
| `/constraints/tide-bridge` | `ENTER_OPERATING_WINDOWS`, `GENERATE_PLAN`, `OPEN_EXCEPTION_CENTER` |
| `/operations/tug-barge-assignment` | `GENERATE_PLAN`, `REGENERATE_PLAN`, `OPEN_EXCEPTION_CENTER` |
| `/operations/jetty-loading` | `CONFIRM_EVENT`, `FORCE_START_JETTY`, `CREATE_SCENARIO` |
| `/operations/cts-floating-crane` | `CONFIRM_EVENT`, `CREATE_SCENARIO` |
| `/schedule/published-plan` | `CREATE_DRAFT`, `SUBMIT_APPROVAL`, `GENERATE_EXPORT` |
| `/exceptions/center` | `CREATE_SCENARIO`, `RUN_SIMULATION`, `PROMOTE_SCENARIO` |
| `/simulation/workspace` | `ADD_ASSUMPTION`, `RUN_SIMULATION`, `PROMOTE_SCENARIO`, `SUBMIT_APPROVAL` |
| `/approvals/publishing` | `APPROVE_PLAN`, `REJECT_PLAN`, `PUBLISH_PLAN` |
| `/map/live` | `REVIEW_SIGNAL_HEALTH`, `OPEN_EXCEPTION_CENTER`, `CREATE_SCENARIO` |
| `/operations/event-confirmation` | `CONFIRM_EVENT`, `REJECT_EVENT`, `OPEN_EXCEPTION_CENTER` |
| `/admin/export-handoff` | `GENERATE_EXPORT`, `REVIEW_AUDIT` |
| `/admin/master-data` | `REVIEW_MASTER_DATA` |
| `/admin/users-rbac` | `REVIEW_RBAC` |
| `/admin/audit-logs` | `REVIEW_AUDIT` |

---

## 5. Button and endpoint mapping

The current `frontend/src/App.tsx` already contains most user actions as local handlers. The assistant registry must map to these existing handlers and backend endpoints.

| Current handler | Recommended action ID | Existing backend shape |
|---|---|---|
| `handleImportDemand` | `IMPORT_OGV_DEMAND` | `planning/import-jobs` validation/commit flow |
| `handleEnterOperatingWindows` | `ENTER_OPERATING_WINDOWS` | `planning/overview/enter-operating-windows/` |
| `handleRegeneratePlan` | `GENERATE_PLAN` / `REGENERATE_PLAN` | `scheduling/plan-versions/{id}/generate/` or equivalent action |
| `handleCreateDraft` | `CREATE_DRAFT` | plan version clone/create successor action |
| `handleForceStartJetty` | `FORCE_START_JETTY` | assignment override action |
| `handleConfirmOperationalEvent` | `CONFIRM_EVENT` | operations candidate confirm action |
| `handleRejectOperationalEvent` | `REJECT_EVENT` | operations candidate reject action |
| `handleCreateScenario` | `CREATE_SCENARIO` | scheduling scenario create action |
| `handleCreateAssumption` | `ADD_ASSUMPTION` | scenario assumption create action |
| `handleRunSimulation` | `RUN_SIMULATION` | scenario simulate action |
| `handlePromoteScenario` | `PROMOTE_SCENARIO` | scenario promote action |
| `handleSubmitApproval` | `SUBMIT_APPROVAL` | approval request action |
| `handleApprovePlan` | `APPROVE_PLAN` | approval decision action |
| `handleRejectPlan` | `REJECT_PLAN` | approval decision action |
| `handlePublishPlan` | `PUBLISH_PLAN` | plan publish action |
| `handleGenerateExport` | `GENERATE_EXPORT` | exports create action |

---

## 6. Registry governance rules

1. Every mutating user action exposed in the UI must have an action registry entry.
2. Every registry entry must define permission, route, eligibility, blocked states, and audit requirement.
3. New buttons must not be added without either:
   - mapping to an existing action ID, or
   - adding a new action ID with tests.
4. Disabled buttons must reference registry blocked reasons.
5. Page-level recommendations must be registry-backed.
6. Row-level hints must reference object type and object ID.
7. The assistant must never recommend a mutating action to a user who lacks permission.
8. The assistant may show blocked actions only as explanation, not as primary CTAs.
9. Governance-sensitive actions must include `audit_required=true`.
10. Each recommendation must include a source rule ID for traceability.
