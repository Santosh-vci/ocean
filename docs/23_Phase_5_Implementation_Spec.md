## Phase 5 Implementation Spec Plan

**Status:** implemented through Chunk 5.6 with closure evidence

**Goal:** move from operational visibility to decision intelligence: generate recovery options, score them, convert the selected option into a governed scenario, and route it through approval before plan publication.

**Core Principle**
Phase 5 must not directly mutate the active plan. Optimizer output is a recommendation, then an explicit scenario, then a promoted plan version, then approval/publish. Phase 4 confirmed actuals become high-trust inputs.

## Scope

In scope:
- assignment optimizer for disrupted trips;
- trip resequencing;
- tug/barge/CTS/jetty conflict repair;
- tide/bridge-aware recovery options;
- recommendation scoring and explanation;
- planner approval workflow through existing scenario governance.

Out of scope for first Phase 5 pass:
- global commercial demurrage optimization;
- fuel/emission optimization;
- live vendor optimizer integration;
- autonomous plan publishing;
- customer-facing recovery commitment.

## Data Model Additions

Add scheduling/recovery models:

- `RecoveryInputSnapshot`
  - active plan version, source exception, confirmed actuals, active alerts, conflicts, resource state, generated_at.
- `OptimizerRun`
  - run_id, source_kind, source_ref, status, algorithm_version, objective_weights, input_snapshot, started_by, timestamps.
- `RecoveryRecommendation`
  - recommendation_id, optimizer_run, rank, status, score, risk_level, summary, explanation, metadata.
- `RecoveryAction`
  - recommendation, action_type, target_trip, target_assignment, before_state, after_state, constraints_checked.
- `RecommendationEvaluation`
  - recommendation, delay_minutes, missed_windows, resource_conflicts, utilization_delta, confidence_score.

## Engine Services

Implement services behind a stable optimizer interface:

- `build_recovery_input_snapshot(source)`
- `generate_recovery_recommendations(snapshot, objective_weights)`
- `score_recommendation(candidate)`
- `explain_recommendation(candidate)`
- `materialize_recommendation_as_scenario(recommendation)`
- `compare_recommendation_to_baseline(recommendation)`

Initial algorithm should be deterministic heuristic repair:
1. Freeze confirmed actuals.
2. Identify disrupted trip/resource.
3. Generate candidate repair actions:
   - delay trip;
   - swap tug/barge;
   - move to next tide/bridge window;
   - reassign CTS;
   - resequence nearby trips.
4. Re-run existing constraint checks.
5. Score feasible candidates.
6. Persist top recommendations with explanations.

## Constraints

Hard constraints:
- confirmed actuals cannot move;
- coal grade and hatch/layer rules;
- jetty loading capacity;
- tug/barge compatibility;
- CTS capability and queue;
- tide and bridge windows;
- resource availability;
- no duplicate assignment of the same resource.

Soft scoring:
- total delay minutes;
- OGV completion risk;
- missed-window count;
- number of manual changes;
- device/feed confidence;
- operational complexity;
- demurrage proxy, if available.

## API Surface

Add endpoints:

- `POST /api/scheduling/recovery-runs/`
- `GET /api/scheduling/recovery-runs/`
- `GET /api/scheduling/recovery-runs/{id}/`
- `POST /api/scheduling/recommendations/{id}/materialize-scenario/`
- `POST /api/scheduling/recommendations/{id}/dismiss/`
- `GET /api/scheduling/recommendations/{id}/proof-pack/`

## Frontend

Add a **Recovery Recommendation** surface, integrated with existing Recovery Loop:

- Exception Center: `Generate recovery options`.
- Recommendation Console:
  - ranked options;
  - score, risk, delay, missed windows;
  - changed trips/resources;
  - constraint pass/fail;
  - explanation chain.
- Detail panel:
  - before/after assignment state;
  - affected trips timeline;
  - why this option ranks first;
  - known risks.
- Action:
  - `Create scenario from recommendation`;
  - then use existing Simulation Workspace, promotion, approval, and publish flow.

## Chunk Plan

### Chunk 5.0 - Recovery Model Foundation
Add models, serializers, admin views, migrations, seed fixtures, and read APIs.

### Chunk 5.1 - Input Snapshot Builder
Build normalized optimizer input from active plan, conflicts, Phase 3 alerts, Phase 4 confirmed events, health risks, and constraints.

### Chunk 5.2 - Deterministic Repair Engine
Implement delay, resequence, tug/barge swap, CTS reassignment, and next-window repair candidates.

### Chunk 5.3 - Scoring And Explanation
Add objective weights, recommendation scoring, risk labels, and operator-readable explanation nodes.

### Chunk 5.4 - Scenario Materialization
Convert selected recommendation into existing scenario assumptions and run the scenario engine without bypassing governance.

### Chunk 5.5 - Recommendation UI
Build Recommendation Console and integrate Exception Center and Simulation Workspace handoff.

### Chunk 5.6 - Approval And Proof Pack
Add recommendation proof pack, audit events, browser evidence, runbook, and closure evidence.

## Acceptance Criteria

Phase 5 is complete when an operator can:
- select a real exception or confirmed operational disruption;
- generate ranked recovery recommendations;
- inspect why each option is ranked;
- see hard constraint pass/fail evidence;
- create a scenario from the chosen recommendation;
- run and compare the scenario;
- promote it through approval;
- publish only through existing governance;
- audit every optimizer input, output, and decision.
