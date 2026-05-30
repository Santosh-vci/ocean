# 26 - Phase 6 / Phase 5+ Implementation Spec

**Status:** implemented and closed by Chunk 6.7 evidence

**Purpose:** define the next governed decision-support layer after Phase 5. This spec turns the known Phase 5 gaps into buildable work while keeping the operator experience UI-driven, approval-governed, and aligned with Next Action Assist.

## Goal

Phase 6 / Phase 5+ should help an operator move from disruption to a publishable, approved recovery plan with less manual interpretation.

The product must:

- run the operating flow through persistent backend flow state;
- use Next Action Assist as the visible guide for the operator;
- repair and validate more recovery cases without silently mutating the active plan;
- prove whether a selected recovery option actually addresses the original physical cause;
- expose publishability as an explicit read-only assessment before manual publication;
- prepare deterministic DB-truth operator-trial data for UI CTA-based testing;
- scaffold global optimization, live telemetry trust, and commercial projection without making unsupported business promises.

Automatic publishing, replacement of Berau or ABL approval, and final demurrage settlement remain out of scope.

## Product Boundaries

### In Scope

- Persistent flow runtime for clean planning and Phase 5+ recovery practice.
- Flow-aware Next Action guidance.
- Recovery repair orchestration across known conflict families.
- Root-cause validation for recovery recommendations.
- Read-only publishability assessment.
- DB-truth seed preparation for operator trial.
- UI CTA-driven evidence flow using Next Action.
- Global optimizer architecture scaffolding.
- Live GPS/AIS source-trust architecture.
- Customer-safe ETA, laycan, and demurrage exposure projections.

### Out Of Scope

- Autonomous plan publishing.
- Any workflow that bypasses approval.
- Replacement of Berau scheduler, ABL dispatcher, or joint-control approval authority.
- Final customer commitment calculation.
- Final demurrage, despatch, invoice, or settlement calculation.
- Treating raw third-party GPS/AIS as direct production truth without confidence and confirmation gates.

## Core Principles

1. **Flow state guides; domain state decides.** Flow runtime records where the operator is in a governed process. Completion and blocking status must be derived from persisted domain records, not from clicking a checklist.
2. **Next Action recommends; pages execute.** The assistant may point to the next route and CTA, but mutating operations stay on their existing page-owned endpoints.
3. **Recommendations remain advisory.** Optimizer output still becomes a scenario, then a promoted plan version, then approval, then manual publish.
4. **Publishability is explicit.** Manual publish is allowed only when a read-only assessment proves approvals and hard operational gates are clear.
5. **Trial evidence is UI-first.** Management commands may prepare deterministic DB truth, but the tested operator run must execute visible UI CTAs assisted by Next Action.

## Persistent Flow Runtime

Add a new backend flow runtime app or module. If a new Django app is used, name it `flows`. If the team keeps it inside an existing app, keep the model and API names below unchanged.

### Data Model

`FlowDefinition`

- `flow_key`: stable key, unique. Examples: `operator_happy_path_v1`, `phase5_plus_recovery_v1`.
- `name`: operator-readable flow name.
- `description`: short purpose.
- `version`: integer definition version.
- `status`: `active`, `deprecated`.
- `entry_route`: first route for the flow.
- `steps`: JSON ordered step definitions.
- `created_at`, `updated_at`.

Each `steps` entry must contain:

- `step_key`: stable key inside the flow.
- `label`: operator-readable label.
- `expected_route`: route where the operator should act.
- `expected_action_id`: Next Action registry ID.
- `completion_selector`: named backend selector used to derive completion.
- `blocked_selector`: named backend selector used to derive blocking reason.
- `required_permission`: permission needed to execute the CTA.
- `terminal`: boolean.

`FlowRun`

- `run_id`: stable public reference.
- `flow_definition`: FK.
- `status`: `not_started`, `active`, `blocked`, `completed`, `canceled`.
- `current_step_key`: current expected step.
- `subject_type`: optional domain subject, such as `plan_version` or `recovery_recommendation`.
- `subject_id`: optional subject id.
- `started_by`, `started_at`, `completed_at`.
- `metadata`: JSON for seed labels, evidence run IDs, and trial-pack identifiers.

`FlowStepRun`

- `flow_run`: FK.
- `step_key`.
- `status`: `pending`, `active`, `blocked`, `completed`, `skipped`.
- `expected_route`.
- `expected_action_id`.
- `blocked_reason`.
- `completed_at`.
- `evidence`: JSON containing domain object references that satisfied completion.

`FlowEvent`

- `flow_run`: FK.
- `step_key`: optional.
- `event_type`: `started`, `resumed`, `cta_intent`, `domain_completed`, `blocked`, `unblocked`, `completed`, `canceled`.
- `actor`: FK user, nullable for system events.
- `route`: route visible when the event was recorded.
- `action_id`: assistant action or page CTA action.
- `object_type`, `object_id`: optional domain reference.
- `metadata`: JSON.
- `created_at`.

### Runtime Services

Implement services with deterministic behavior:

- `get_active_flow_run(user, route=None, subject=None)`
- `start_flow(flow_key, actor, subject=None, metadata=None)`
- `resume_flow(flow_run, actor)`
- `evaluate_flow_run(flow_run, actor=None)`
- `record_cta_intent(flow_run, step_key, action_id, route, actor)`
- `complete_step_from_domain_state(flow_run, step_key, evidence)`
- `block_step_from_domain_state(flow_run, step_key, reason)`

`evaluate_flow_run` must never mutate scheduling, planning, approval, export, telemetry, or recovery records. It may only update flow-runtime state and flow events.

### Canonical Flow Definitions

`operator_happy_path_v1`

| Step key | Expected action | Expected route | Completion source |
|---|---|---|---|
| `import_ogv_demand` | `IMPORT_OGV_DEMAND` | `/schedule/ogv-demand` | active OGV demand exists with imported job |
| `review_coal_sequence` | `REVIEW_COAL_SEQUENCE` | `/schedule/coal-grade-sequence` | no blocking cargo-layer issue for planning |
| `enter_operating_windows` | `ENTER_OPERATING_WINDOWS` | `/constraints/tide-bridge` | active tide and bridge windows exist |
| `generate_plan` | `GENERATE_PLAN` | `/operations/tug-barge-assignment` | active plan version has generated trips |
| `submit_approval` | `SUBMIT_APPROVAL` | `/schedule/published-plan` | approval request exists |
| `approve_plan` | `APPROVE_PLAN` | `/approvals/publishing` | all required approvals complete |
| `run_publishability_check` | `RUN_PUBLISHABILITY_CHECK` | `/approvals/publishing` | latest publishability assessment is publishable or warning |
| `publish_plan` | `PUBLISH_PLAN` | `/approvals/publishing` | active published snapshot exists |
| `generate_export` | `GENERATE_EXPORT` | `/admin/export-handoff` | governed export exists; optional terminal step |

`phase5_plus_recovery_v1`

| Step key | Expected action | Expected route | Completion source |
|---|---|---|---|
| `open_exception_center` | `OPEN_EXCEPTION_CENTER` | `/exceptions/center` | selected active disruption exists |
| `generate_recovery_options` | `GENERATE_RECOVERY_OPTIONS` | `/exceptions/center` | recovery input snapshot and optimizer run exist |
| `review_recommendations` | `OPEN_RECOMMENDATION_CONSOLE` | `/recovery/recommendations` | operator reviewed ranked candidates |
| `validate_root_cause` | `VALIDATE_ROOT_CAUSE_REPAIR` | `/recovery/recommendations` | root-cause assessment exists |
| `materialize_recommendation` | `MATERIALIZE_RECOVERY_RECOMMENDATION` | `/recovery/recommendations` | scenario exists for selected recommendation |
| `run_simulation` | `RUN_SIMULATION` | `/simulation/workspace` | scenario run succeeded |
| `promote_scenario` | `PROMOTE_SCENARIO` | `/simulation/workspace` | proposed plan version exists |
| `repair_remaining_conflicts` | `REPAIR_PLAN_CONFLICTS` | `/exceptions/center` | no unresolved blocking conflict remains |
| `submit_approval` | `SUBMIT_APPROVAL` | `/schedule/published-plan` | approval request exists |
| `approve_plan` | `APPROVE_PLAN` | `/approvals/publishing` | all required approvals complete |
| `run_publishability_check` | `RUN_PUBLISHABILITY_CHECK` | `/approvals/publishing` | latest assessment is publishable or warning |
| `publish_plan` | `PUBLISH_PLAN` | `/approvals/publishing` | manual published snapshot exists |

## Flow-Aware Next Action Assist

Extend the assistant context with flow metadata:

- `active_flow_run_id`
- `active_flow_key`
- `active_flow_status`
- `current_flow_step_key`
- `current_flow_step_status`
- `expected_route`
- `expected_action_id`
- `flow_blocked_reason`

Extend the assistant response with optional snake_case fields:

```json
{
  "flow": {
    "active_flow": "phase5_plus_recovery_v1",
    "flow_run_id": "FLOW-P5P-20260529-001",
    "current_step": "validate_root_cause",
    "expected_route": "/recovery/recommendations",
    "expected_action_id": "VALIDATE_ROOT_CAUSE_REPAIR",
    "step_status": "active",
    "blocked_reason": ""
  }
}
```

Frontend normalization should expose the same payload as camelCase under `data.flow`.

The assistant ranking rule is:

1. If assisted mode is `off`, no flow UI is rendered.
2. If an active flow has an enabled expected action, that action becomes the top action unless a higher-severity governance blocker exists.
3. If the expected action is blocked, the top action becomes the blocker-resolution action with the flow blocked reason.
4. Disabled actions must never become `global_next_action`.
5. The assistant endpoint remains read-only.

Add action registry entries only where needed:

- `REPAIR_PLAN_CONFLICTS`
- `VALIDATE_ROOT_CAUSE_REPAIR`
- `RUN_PUBLISHABILITY_CHECK`
- `REVIEW_GLOBAL_OPTIMIZATION_CANDIDATE`
- `REVIEW_TELEMETRY_TRUST_STATE`
- `REVIEW_COMMERCIAL_PROJECTION`

## Recovery Repair Orchestration

Add a recovery repair orchestrator behind the existing Phase 5 recommendation model. It should not replace the current deterministic engine; it should coordinate repeated repair, validation, and scoring passes.

### Inputs

- selected `RecoveryRecommendation`;
- source disruption from `RecoveryInputSnapshot`;
- active/proposed `PlanVersion`;
- unresolved `Conflict` records;
- active `TrackingAlert` records;
- availability windows for tug, barge, CTS, jetty, tide, and bridge;
- cargo layer and hatch sequence state;
- existing scenario and promotion lineage.

### Conflict Taxonomy

Support these conflict families in the first implementation pass:

- `BARGE_UNAVAILABLE`
- `TUG_UNAVAILABLE`
- `CTS_UNAVAILABLE`
- `JETTY_OVERLAP`
- `TIDE_WINDOW_MISSED`
- `BRIDGE_WINDOW_MISSED`
- `LAYER_SEQUENCE_VIOLATION`
- `TELEMETRY_ALERT_UNRESOLVED`

### Repair Strategy Contract

Each strategy returns:

- `strategy_key`;
- `source_conflict_code`;
- `actions`: candidate `RecoveryAction` list;
- `expected_resolved_conflicts`;
- `new_risks`;
- `constraint_check_results`;
- `root_cause_result`;
- `publishability_preview`;
- `operator_explanation`.

### Root-Cause Validation

Add `RootCauseRepairAssessment` as a read model or persisted model associated to `RecoveryRecommendation`.

Minimum fields:

- `recommendation`;
- `source_kind`;
- `source_ref`;
- `source_cause_type`;
- `status`: `addresses_cause`, `mitigates_cause`, `does_not_address_cause`, `unknown`;
- `required_resolution`;
- `observed_resolution`;
- `residual_risk`;
- `evidence`: JSON;
- `assessed_at`;
- `assessed_by_algorithm_version`.

For `BARGE_UNAVAILABLE`, valid cause-handling evidence is one of:

- original barge availability restored before the trip window;
- assignment changed to an available compatible barge;
- trip resequenced outside the unavailable window;
- explicit operator-approved mitigation recorded with reason and residual risk.

A CTS reassignment alone must not be marked `addresses_cause` for a `BARGE_UNAVAILABLE` source unless one of the valid barge conditions is also true.

## Publishability Assessment

Add a read-only publishability service and optional persisted assessment.

`PublishabilityAssessment`

- `assessment_id`;
- `plan_version`;
- `status`: `publishable`, `blocked`, `warning`;
- `blocking_reason_count`;
- `warning_count`;
- `approval_status`;
- `conflict_status`;
- `telemetry_status`;
- `cargo_sequence_status`;
- `operating_window_status`;
- `recommendation_origin_status`;
- `checked_at`;
- `checked_by`;
- `algorithm_version`;
- `details`: JSON list of checks.

The assessment must evaluate:

- plan status is approved or otherwise eligible for manual publish;
- all required approvals are complete;
- no unresolved blocking conflict exists;
- no unresolved critical conflict exists;
- no blocking cargo layer sequence issue remains;
- active tide and bridge windows exist for required movements;
- recommendation-origin candidates have no unresolved residual critical risk;
- active telemetry alerts are either resolved, acknowledged as non-blocking, or converted into governed exception handling;
- there is no stale source-input marker requiring a successor draft.

Approvals/Publishing should surface the latest assessment before showing or enabling publish. Next Action should recommend `RUN_PUBLISHABILITY_CHECK` or blocker resolution when assessment state is absent or blocked.

## DB-Truth Operator Trial Seed Behavior

Extend seed behavior so the operator trial has deterministic DB truth for UI-only validation.

### Seed Preparation

Add a preparation mode to the existing operator trial tooling. The command may reset and prepare:

- master data;
- users and permissions;
- canonical `FlowDefinition` records;
- an empty or initialized `FlowRun`;
- expected CTA sequence;
- trial-pack demand rows;
- expected operating-window fixtures;
- expected recovery disruption fixtures;
- expected final-state assertions.

The preparation command must not perform the tested operator actions. It may create DB truth fixtures and expected records only.

### UI CTA Evidence Rule

The accepted development proof must drive visible browser CTAs:

1. Next Action points to the route.
2. The operator/browser clicks the page CTA.
3. The domain endpoint mutates state.
4. Flow runtime observes completion from DB state.
5. Next Action advances to the next step.

Management commands that directly import demand, enter windows, generate plans, resolve exceptions, approve, publish, or export are regression helpers only. They are not valid proof of the UI operator run.

## Global Optimizer Scaffold

Add architecture now, but defer final commercial optimization policy until business weights are approved.

Inputs:

- all active OGV demand;
- cargo requirements and layer sequence;
- current trip and assignment state;
- tug, barge, CTS, jetty, tide, bridge availability;
- confirmed operational events;
- telemetry-derived risk state;
- demurrage proxy and laycan risk;
- manual priority and customer class.

Output:

- ranked global candidate plans;
- objective weight set used;
- changed assignments and trip sequence;
- projected delay and laycan impact;
- projected demurrage exposure delta;
- unresolved risk list;
- approval and audit lineage.

Default objective weights should be configuration, not hard-coded business truth. Until weights are signed off, label outputs as optimization candidates, not commercially final decisions.

## Live GPS/AIS Trust Architecture

Raw live feeds are evidence. They are not automatic production truth.

Implement source-trust handling with:

- `TelemetrySourceTrustProfile`;
- source freshness threshold;
- source confidence threshold;
- asset identity mapping;
- duplicate and conflict detection;
- quarantine state for unknown or low-confidence records;
- manual confirmation or event-candidate conversion before planning mutation.

Source priority defaults:

1. confirmed operational event;
2. approved manual correction;
3. high-confidence owned GPS tracker;
4. high-confidence AIS/vendor feed;
5. synthetic replay or low-confidence feed.

Any third-party GPS/AIS integration must preserve current Phase 3/4 behavior: observed state may create alerts, scenarios, or recommendations, but must not overwrite baseline plan records without governed action.

## Commercial Projection

Commercial output in this phase is projection-only.

Expose:

- projected OGV completion time;
- laycan risk state;
- projected demurrage exposure minutes;
- projected demurrage exposure amount using configured voyage rate;
- confidence band;
- reasons contributing to exposure;
- whether the projection is customer-safe to share.

Do not expose:

- final customer commitment;
- final demurrage settlement;
- despatch calculation;
- invoice-ready values;
- contract exception judgment.

Final settlement requires contract terms, NOR/SOF rules, laytime definitions, exception clauses, customer approval workflow, and commercial ownership decisions outside this spec.

## API Surface

Add flow endpoints:

- `GET /api/flows/active/`
- `GET /api/flows/{id}/`
- `POST /api/flows/{id}/events/`

Add read-only recovery/approval endpoints or fields:

- recommendation root-cause assessment on recommendation detail and proof pack;
- latest publishability assessment on scheduling overview and approvals/publishing payload;
- commercial projection payload on scenario/recommendation/global optimizer views.

No new endpoint may publish a plan automatically.

## Testing And Acceptance

### Backend

- Flow runtime creates deterministic flow runs from seeded definitions.
- Flow step completion is derived from DB truth, not local UI state.
- Assistant top action follows active flow step order.
- Assistant endpoint remains read-only.
- Disabled or blocked actions cannot become global next action.
- Root-cause assessment rejects CTS-only repair for `BARGE_UNAVAILABLE`.
- Root-cause assessment accepts valid barge reassignment, restored availability, or resequence outside outage.
- Publishability blocks manual publish until conflicts, approvals, cargo sequence, telemetry blockers, and stale inputs are clear.
- Global optimizer candidates persist objective weights and audit lineage.
- Commercial projection is clearly non-settlement output.

### Frontend And Browser Evidence

- Happy path starts at imported OGV demand and proceeds through sequence, windows, plan generation, approval, manual publish, and optional export.
- Phase 5+ recovery path follows Next Action CTAs from exception triage through recommendation, root-cause assessment, scenario, simulation, conflict repair, publishability check, approval, and manual publish.
- Assisted mode shows flow-aware CTA guidance.
- Off mode hides assistive UI without breaking page workflows.
- Browser evidence validates actual UI CTA execution against DB-truth flow and trial-pack records.

### Regression Commands

Keep these as supporting regression evidence, not operator-flow proof:

```powershell
docker compose exec -T api pytest apps/assistant/tests -q
docker compose exec -T api python manage.py check
docker compose exec -T api python manage.py phase5_recovery_proof --json
docker compose exec -T api pytest apps/core/tests/test_phase5_recovery_proof.py -q
```

## Delivery Chunks

### Chunk 6.0 - Flow Runtime Foundation

Add flow models, serializers, services, admin/read APIs, seed definitions, and backend tests.

Status: complete.

### Chunk 6.1 - Flow-Aware Next Action

Extend assistant selectors, rules, response contract, frontend normalization, and assistant components.

Status: complete.

### Chunk 6.2 - Operator Trial DB Truth

Add deterministic DB-truth preparation for operator trial and UI CTA evidence assertions.

Status: complete.

### Chunk 6.3 - Root-Cause Repair Validation

Add recovery repair orchestration and root-cause assessment for core conflict families.

Status: complete.

### Chunk 6.4 - Publishability Gate

Add publishability service, Approvals/Publishing surface, and assistant guidance.

Status: complete.

### Chunk 6.5 - Global Optimizer Scaffold

Add global candidate contracts, objective weight configuration, audit lineage, and read-only review UI.

Status: complete.

### Chunk 6.6 - Telemetry Trust And Commercial Projection

Add telemetry trust profiles and projection-only customer-safe commercial outputs.

Status: complete.

### Chunk 6.7 - Evidence And Runbook Closure

Add UI CTA browser evidence, update operator runbooks, and document known remaining business decisions.

Status: complete. Closure evidence is recorded in `27_Phase_6_Completion_Evidence.md`.

### Chunk H6.8 - Recovery Lineage And Publishability Integrity

Preserve recovery-origin provenance through promotion, repair, regeneration, publishability, and publish guards.

Status: complete.

### Chunk H6.9 - Flow Subject Binding And Domain Ref Selectors

Bind flow progress to stored domain refs and use global fallback only for legacy non-trial flows.

Status: complete.

### Chunk H6.10 - Canonical Active Plan Selection

Centralize active plan selection modes for working, approval, publish, and published-snapshot candidates.

Status: complete.

### Chunk H6.11 - Server-Enforced Flow CTA Evidence

Reject forged flow evidence when step, action, state, visibility, or object refs do not match the active flow.

Status: complete.

### Chunk H6.12 - Completed-Step Invalidation Semantics

Revalidate high-risk completed flow steps and block/reset downstream steps when bound DB truth is invalidated.

Status: complete.

### Chunk H6.13 - Evidence Assertion And Runbook Closure

Tighten recovery evidence and docs so failed root-cause repair blocks publishability and backend publish.

Status: complete.

## Closure Evidence

Chunk 6.7 closes this specification with repeatable browser evidence and documentation updates:

- clean operator happy path UI CTA evidence: `docs/evidence/operator_trial_flow/operator_trial_flow_capture.json`;
- Phase 5+ recovery UI CTA evidence: `docs/evidence/phase6_recovery_flow/phase6_recovery_flow_capture.json`;
- read-only global optimizer, telemetry trust, and commercial projection surface evidence: `docs/evidence/phase6_review_surfaces/phase6_review_surface_capture.json`;
- completion runbook and remaining business decisions: `27_Phase_6_Completion_Evidence.md`.

Production hardening H6.8-H6.13 adds the final integrity layer:

- recovery-origin plans carry durable `summary.recoveryOrigin` refs;
- publishability blocks `does_not_address_cause`, `unknown`, and missing root-cause assessments even after regeneration;
- flow progress is bound to explicit domain refs instead of trainer-seed global state;
- flow CTA evidence is validated server-side against the current step and expected action;
- high-risk completed steps invalidate when approvals, publishability, publish snapshots, exports, or provenance no longer match DB truth;
- recovery browser/API evidence includes a negative gate where failed root-cause repair blocks publishability and manual publish.

## Exit Criteria

Phase 6 / Phase 5+ is ready when:

- the operator happy path can be completed through UI CTAs starting from OGV demand import;
- the Phase 5+ recovery path can be completed through UI CTAs with Next Action guidance;
- flow runtime state matches domain DB truth at every step;
- a selected recovery recommendation has explicit root-cause assessment;
- publishability is visible and blocks manual publish until clear;
- automatic publishing is still impossible;
- approval authority remains with Berau, ABL, and joint-control roles;
- commercial outputs are labeled as projections, not settlement;
- audit lineage explains every recommendation, scenario, approval, publish, and export decision.
