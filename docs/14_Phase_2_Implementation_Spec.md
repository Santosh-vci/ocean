# 14 - Phase 2 Implementation Spec

**Project:** Coalflow Tower / Berau-ABL Transshipment Scheduling Simulation and Live Planning Platform  
**Status:** draft implementation specification for product Phase 2  
**Generated:** 2026-05-17  
**Primary inputs:** `00_README_Index.md`, `01_Ground_Reality_Operations.md`, `02_Planning_Tool_Scope.md`, `03_Data_Architecture_and_IoT_Scope.md`, `04_RBAC_and_Django_Architecture_Addendum.md`, `07_Frontend_Build_Handoff_and_Phasewise_Plan.md`, `08_Phase_1_Implementation_Spec.md`, `11_API_Contract_Baseline.md`, `12_Phase_1_Completion_Evidence.md`, `13_Phase_1_Operator_Manual.md`, and the current Phase 1 codebase.

---

## 1. Scope interpretation

This document defines **product Phase 2** from `02_Planning_Tool_Scope.md`: **simulation and scenario planning**.

It is intentionally distinct from the frontend build-phase numbering in `07_Frontend_Build_Handoff_and_Phasewise_Plan.md`, where "Phase 2" means core operational boards. Product Phase 1 has already delivered those boards plus the governed scheduling spine.

### Phase 2 objective

Turn the Phase 1 governed schedule into a planner-grade what-if system where authorized users can:

1. create explicit delay, outage, and constraint-change scenarios from a live or draft plan;
2. enter structured scenario assumptions without mutating the baseline plan;
3. calculate plan-wide projected consequences across trips, windows, OGV completion, demurrage, and asset utilization;
4. compare baseline vs scenario outputs with explainable deltas;
5. promote a chosen scenario into a governed proposed plan for the existing approval and publication workflow.

### What Phase 2 must prove

The system can answer these questions from computed scenario data rather than static narrative:

- If a jetty start slips by 120 minutes, which downstream trips and windows are affected?
- If a tug, barge, CTS, or jetty becomes unavailable, which assignments are impacted over the horizon?
- If a tide or bridge window changes, which movements miss the gate and by how much?
- What is the revised OGV completion time and demurrage exposure for each scenario?
- How does fleet utilization change between baseline and scenario?
- Which scenario was promoted, by whom, against which baseline, and through which approval path?

### Explicitly out of scope for product Phase 2

- live AIS/GPS ingestion as a required input;
- MQTT/Kafka/Redpanda event streaming;
- geofence-derived actual state;
- global optimizer-driven reassignment;
- automatic recovery recommendation;
- customer portal and external shipment visibility;
- fuel, emissions, or route-cost optimization;
- deep digital-twin physics;
- full commercial exposure modeling beyond scenario-level demurrage projection.

Phase 2 should make consequences calculable and auditable. It should not yet claim to compute the best recovery plan.

---

## 2. Product invariants

The following Phase 1 invariants remain binding:

1. **Published plan immutability remains intact.** Simulation never edits a live baseline in place.
2. **Observed, confirmed, derived, planned, projected, and recommended states remain separate.**
3. **Cross-party governance remains mandatory.** Promotion does not bypass approval or publication.
4. **Every result must be explainable.** A planner must be able to trace the source assumption, affected event, violated window, and derived delta.
5. **Scenarios are comparable artifacts, not hidden side effects.**
6. **No automatic optimization is smuggled into simulation.** If the engine changes an assignment, that change must come from an explicit scenario assumption or later optimizer work.
7. **The UI is a projection surface, not the source of authority.** The backend owns calculations, permissions, lifecycle, and audit.

---

## 3. Phase 1 baseline carried forward

Phase 2 should extend the current implementation rather than restart it.

| Existing capability | Phase 2 interpretation |
|---|---|
| deterministic schedule generation | canonical scenario baseline |
| `PlanVersion`, `Trip`, `Assignment`, `ScheduleEvent` | source schedule graph |
| `Conflict`, `OverrideRequest`, approvals, published snapshots | governed context and lifecycle |
| `SimulationScenario` shell | retained and expanded into a real scenario aggregate |
| `ImpactChainAssessment` | reused as the normalized impact-node contract across override, conflict, planning forecast, and simulation sources |
| plan diff service | seed for scenario comparison, expanded from trip-only deltas |
| Stage 7.1 current-trip impact calculation | first reusable calculation pattern, generalized in Phase 2 |
| Simulation Workspace MVP-lite UI | replaced with computed runs, assumption capture, comparison, and drill-downs |

### Current debt that Phase 2 must retire

The present `simulate_scenario()` path is intentionally Phase 1-lite:

- fixed recovery text;
- fixed feasibility/demurrage numbers;
- no structured assumption model;
- no run history;
- no persisted event projections;
- no plan-wide propagation.

Phase 2 is not complete until those placeholder outputs are replaced with computed, persisted scenario results.

---

## 4. Phase 2 user journeys

### 4.1 Scenario from exception or override

1. User opens Exception Center.
2. User selects a conflict or governed override.
3. User clicks **Create scenario**.
4. Scenario opens with baseline version, source event, affected trip, and prefilled assumption draft.
5. User confirms or edits assumptions.
6. User runs simulation and reviews the computed impact chain and plan-wide deltas.

### 4.2 Manual what-if scenario

1. User opens Simulation Workspace.
2. User creates a manual scenario against the current live or draft baseline.
3. User enters one or more assumptions:
   - delayed start;
   - asset outage;
   - reduced loading/discharge rate;
   - changed bridge or tide window;
   - OGV ETA or laycan change;
   - explicit reassignment for a selected trip.
4. User runs the scenario.
5. System computes projections without changing the baseline.

### 4.3 Compare and choose

1. User compares baseline and one or more scenario runs.
2. UI shows:
   - revised trip times;
   - OGV completion delta;
   - constraint breaches;
   - demurrage delta;
   - fleet utilization delta;
   - changed assignments and assumptions.
3. User chooses one scenario for promotion or discards the candidate.

### 4.4 Governed promotion

1. User promotes a completed scenario.
2. System creates a successor `PlanVersion` from the scenario projection or applies approved scenario changes into a successor draft/proposed version.
3. The promoted version retains lineage to the scenario and baseline.
4. Existing dual-party approval and publish gates continue unchanged.

---

## 5. Phase 2 capability scope

### 5.1 Must build

- scenario assumption capture;
- scenario run execution and run history;
- deterministic projection engine;
- multi-trip event propagation over the active planning horizon;
- bridge/tide/availability re-evaluation;
- OGV completion projection;
- demurrage projection;
- asset utilization report;
- baseline vs scenario comparison;
- promotion lineage into successor plan versions;
- scenario-aware audit and exports;
- realistic scenario seed sets and operator proof flow.

### 5.2 Should build

- multiple runs per scenario;
- ability to clone a scenario;
- assumption presets for common operator cases;
- scenario result caching by input hash;
- drill-down from affected trip to assumption and violated gate;
- warning when a scenario baseline is stale relative to a newer live plan.

### 5.3 Should defer

- automatic "best plan" selection;
- MILP/CP-SAT/global optimization;
- learned ETA prediction;
- automatic fleet resequencing recommendation;
- live telemetry-driven auto-simulation;
- customer-visible scenario summaries.

---

## 6. Target architecture additions

Phase 2 can keep the Phase 1 Docker topology. The default runtime remains:

| Service | Phase 2 use |
|---|---|
| `api` | scenario lifecycle, calculation APIs, governance |
| `worker` | asynchronous scenario runs, comparison materialization, exports |
| `db` | persisted assumptions, runs, projections, assessments |
| `redis` | queue, locks, run status cache |
| `object-store` | scenario exports and optional large result artifacts |
| `frontend` | assumption editor, comparison workspace, drill-downs |

### 6.1 New backend modules or service layers

Keep these inside the existing Django scheduling boundary unless size later warrants extraction:

| Component | Responsibility |
|---|---|
| scenario assumption service | validate typed scenario inputs |
| projection engine | build scenario event graph from baseline plus assumptions |
| constraint evaluator | re-check windows, availability, compatibility, quantity, and sequencing |
| KPI calculator | OGV completion, demurrage, utilization, violation counts |
| comparison service | baseline vs scenario deltas |
| promotion adapter | convert selected projections into a successor `PlanVersion` |

### 6.2 Execution model

Scenario runs should be asynchronous:

```text
Scenario -> Assumptions -> Queue Run -> Build baseline graph -> Apply assumptions
         -> Propagate events -> Re-evaluate constraints -> Calculate KPIs
         -> Persist projections / assessments / summary -> Notify UI
```

Phase 2 may use request-thread execution only for trivial tests. User-facing runs should use worker jobs so larger horizons do not hold API requests open.

---

## 7. Domain model blueprint

### 7.1 Existing models to retain

| Model | Phase 2 role |
|---|---|
| `SimulationScenario` | human-readable scenario container and lifecycle |
| `ImpactChainAssessment` | ordered explainability nodes for UI rendering |
| `PlanVersion`, `Trip`, `Assignment`, `ScheduleEvent` | baseline truth |
| `Conflict`, `OverrideRequest` | scenario sources |

### 7.2 New scenario models

| Model | Purpose |
|---|---|
| `ScenarioAssumption` | one typed change applied to a scenario |
| `ScenarioRun` | one immutable execution of a scenario with algorithm version and input hash |
| `ScenarioEventProjection` | projected event time/status for one baseline schedule event |
| `ScenarioTripProjection` | trip-level projected start/end/status and assignment deltas |
| `ScenarioConstraintEvaluation` | persisted constraint result for a projected object |
| `ScenarioResourceUtilization` | summarized asset occupancy / idle / waiting metrics per run |
| `ScenarioOgvProjection` | OGV completion, laycan, and demurrage metrics per run |

### 7.3 Suggested key fields

#### `ScenarioAssumption`

```text
scenario
assumption_id
kind
scope_type
scope_id
payload_json
effective_from
effective_to
created_by
created_at
```

Initial `kind` values:

```text
trip_delay
asset_outage
rate_change
window_change
ogv_eta_change
manual_reassignment
```

#### `ScenarioRun`

```text
scenario
run_id
baseline_version
status
algorithm_version
input_hash
started_at
completed_at
summary_json
created_by
```

Initial `status` values:

```text
queued
running
succeeded
failed
canceled
```

#### Projection models

Projection rows should preserve both baseline and projected values so the UI does not need to reconstruct historical context from mutated plan data.

### 7.4 State and lineage rules

- A `ScenarioRun` is immutable after completion.
- A scenario may have multiple runs, but only one selected run may be promoted.
- Promotion stores:
  - baseline version;
  - scenario id;
  - selected run id;
  - assumption ids;
  - algorithm version.
- A promoted plan version remains subject to normal approval and publish transitions.
- `ImpactChainAssessment.source_kind = "simulation"` should reference the scenario/run context in metadata or a later explicit FK if needed.

---

## 8. Scenario engine specification

### 8.1 Engine goal

Generate deterministic, explainable **projections** for planner-authored assumptions. The engine answers "what happens if..." It does not yet answer "what is globally best..."

### 8.2 Baseline graph

Build a directed schedule graph from:

- trip sequence;
- schedule events;
- assignment/resource links;
- cargo layer order;
- OGV demand chain;
- active tide, bridge, jetty, CTS, and asset availability windows.

The graph should expose at least:

```text
load_start -> load_complete -> depart_jetty -> bridge_cross
           -> tide_gate -> arrive_cts -> discharge_complete
```

Across trips, add dependency edges for:

- shared tug/barge reuse;
- shared jetty queue;
- shared CTS queue;
- cargo layer order for the same OGV;
- explicit predecessor/successor trip order where modeled.

### 8.3 Propagation order

For each run:

1. validate assumptions;
2. clone baseline graph into scenario working memory;
3. apply direct assumption deltas;
4. propagate event shifts along dependency edges;
5. re-evaluate availability, compatibility, bridge, tide, layer, and quantity constraints;
6. calculate trip, OGV, demurrage, and utilization projections;
7. persist projection rows, constraint evaluations, impact assessments, and run summary;
8. expose comparison-ready deltas.

### 8.4 Initial propagation behavior

| Assumption | Required Phase 2 calculation |
|---|---|
| trip delay | shift current trip and dependent downstream events |
| asset outage | mark overlapping assignments infeasible and propagate wait/violation consequences |
| rate change | recalculate load/discharge durations and dependent events |
| window change | re-evaluate gate feasibility and wait/miss margins |
| OGV ETA change | recalculate completion risk and demurrage exposure |
| manual reassignment | evaluate selected replacement chain and resulting timing/compatibility |

### 8.5 Constraint evaluation outputs

Continue using machine-readable codes. At minimum Phase 2 should calculate:

```text
TIDE_WINDOW_MISSED
BRIDGE_WINDOW_MISSED
ASSET_OUTAGE_OVERLAP
JETTY_OVERLAP
CTS_CAPACITY_CONFLICT
ASSET_DOUBLE_BOOKED
LAYER_SEQUENCE_VIOLATION
LAYCAN_BREACH
DEMURRAGE_RISK
```

Each evaluation should carry:

- severity;
- affected object;
- baseline value;
- projected value;
- miss/wait margin where applicable;
- source assumption ids;
- explanation text.

### 8.6 KPIs

Phase 2 reports must include:

| KPI | Minimum definition |
|---|---|
| OGV completion delta | projected final discharge completion minus baseline completion |
| demurrage delta | projected exposure minus baseline exposure using configured voyage rate |
| trip delay delta | projected end minus baseline end |
| resource utilization delta | occupied / idle / waiting time difference per tug, barge, jetty, CTS |
| remaining violations | unresolved projected blocking evaluations |
| recovered hours | reduction versus source disruption baseline where a manual recovery assumption exists |

### 8.7 Determinism and auditability

- identical baseline + assumptions + algorithm version must produce the same run output;
- every run stores `algorithm_version` and `input_hash`;
- every promoted version stores scenario/run lineage;
- no result may rely on hidden current wall-clock values except recorded calculation time metadata;
- all user-created assumptions and lifecycle transitions emit audit events.

---

## 9. API contract additions

Retain the Phase 1 endpoints and add scenario-specific APIs.

### 9.1 Scenario lifecycle

```text
GET    /api/scheduling/scenarios/
POST   /api/scheduling/scenarios/
GET    /api/scheduling/scenarios/{id}/
POST   /api/scheduling/scenarios/{id}/clone/
POST   /api/scheduling/scenarios/{id}/cancel/
```

### 9.2 Assumptions

```text
GET    /api/scheduling/scenarios/{id}/assumptions/
POST   /api/scheduling/scenarios/{id}/assumptions/
PATCH  /api/scheduling/scenario-assumptions/{id}/
DELETE /api/scheduling/scenario-assumptions/{id}/
```

### 9.3 Runs and results

```text
POST   /api/scheduling/scenarios/{id}/runs/
GET    /api/scheduling/scenarios/{id}/runs/
GET    /api/scheduling/scenario-runs/{id}/
GET    /api/scheduling/scenario-runs/{id}/projections/
GET    /api/scheduling/scenario-runs/{id}/constraints/
GET    /api/scheduling/scenario-runs/{id}/utilization/
GET    /api/scheduling/scenario-runs/{id}/ogv-projections/
GET    /api/scheduling/scenario-runs/{id}/compare/?against={run_or_baseline}
POST   /api/scheduling/scenario-runs/{id}/promote/
```

### 9.4 Compatibility notes

- `/api/scheduling/scenarios/{id}/simulate/` may remain as a compatibility alias during migration, but new work should use run-based APIs.
- Existing `SimulationScenarioSerializer` summary fields may be kept as denormalized latest-run read fields for the current UI, not as the source of truth.
- Existing `ImpactChainAssessmentSerializer` should continue rendering ordered nodes so Stage 7.1 and Phase 2 share a UI contract.

---

## 10. Frontend implementation surface

### 10.1 Simulation Workspace evolution

Replace the Phase 1 MVP-lite static workspace with:

- scenario list and baseline badge;
- scenario assumption editor;
- run history and run status;
- baseline vs selected-run summary strip;
- projected event timeline;
- constraint evaluation table;
- OGV completion and demurrage panel;
- asset utilization panel;
- changed trips / changed assignments table;
- impact-chain drill-down;
- promotion action bound to selected successful run.

### 10.2 Cross-screen integration

| Screen | Phase 2 change |
|---|---|
| Exception Center | create scenario from conflict or override; show linked runs |
| Tide & Bridge Window | show baseline vs projected gate result when opened from a run |
| Tug/Barge Assignment | show projected assignment/resource conflicts for selected run |
| OGV Demand & Laycan | show completion and demurrage delta |
| Approvals & Publishing | show source scenario/run lineage for proposed versions |
| Published Plan & Schedule | expose promoted-scenario ancestry and scenario diff |
| Audit & Logs | filter scenario creation, run, promotion, and export events |

### 10.3 UX rules

- never imply that a scenario is live;
- make baseline, scenario, selected run, and promoted plan visually distinct;
- show computed values before narrative explanation;
- every red/amber result must drill down to source assumption and violated rule;
- do not use hidden auto-reassignment language until optimization exists;
- preserve the existing dense dark operational cockpit style.

---

## 11. Chunked implementation plan

### Chunk 2.0 - Contract cleanup and transition

**Goal:** turn the Phase 1 simulation shell into a stable starting point.

**Build**

- freeze current scenario API behavior;
- replace placeholder labels in docs with Phase 2 terminology;
- preserve `ImpactChainAssessment` node contract;
- formalize baseline/version lineage rules;
- ensure approved/publish-ready plan selection remains stable.

**Exit criteria**

- current Phase 1 operator flow still passes;
- current scenario shell can be migrated without breaking approvals or exports.

### Chunk 2.1 - Scenario assumptions and run model

**Goal:** capture explicit what-if inputs.

**Backend**

- add scenario assumptions;
- add scenario runs and statuses;
- add validation serializers and audit events;
- add source links from conflict/override/manual creation.

**Frontend**

- scenario creation drawer;
- typed assumption editor;
- run queue/status surface.

**Exit criteria**

- a user can create a manual or source-linked scenario and persist assumptions without changing the plan.

### Chunk 2.2 - Projection engine

**Goal:** compute consequence chains.

**Backend**

- build baseline schedule graph;
- implement assumption application;
- implement dependency propagation;
- persist event/trip projections;
- generalize Stage 7.1 window evaluation logic for scenario runs.

**Exit criteria**

- deterministic delay, outage, rate, and window scenarios produce persisted projections over the horizon.

### Chunk 2.3 - Constraint and KPI evaluation

**Goal:** turn projections into operator decisions.

**Backend**

- projected constraint evaluations;
- OGV completion projection;
- demurrage calculation;
- asset utilization calculation;
- latest-run summary materialization.

**Exit criteria**

- each run returns computed violations, completion risk, demurrage delta, and utilization delta.

### Chunk 2.4 - Comparison and operator UI

**Goal:** make scenario consequences legible.

**Frontend**

- baseline vs scenario summary;
- projected timeline;
- changed trips and assignments;
- constraint table;
- OGV/demurrage panel;
- utilization panel;
- impact-chain drill-down.

**Exit criteria**

- an operator can explain the difference between baseline and scenario without inspecting raw JSON.

### Chunk 2.5 - Promotion and governance

**Goal:** convert chosen scenarios into governed plan candidates.

**Backend**

- selected-run promotion adapter;
- successor plan creation from projected result;
- source scenario/run lineage;
- approval-screen source context;
- export support for scenario diff.

**Exit criteria**

- promotion creates a proposed successor version while preserving baseline immutability and existing approval gates.

### Chunk 2.6 - Seed data, proof flow, and hardening

**Goal:** make Phase 2 testable and operationally credible.

**Build**

- realistic scenario seed pack;
- operator manual extension;
- evidence command for scenario proof;
- browser evidence set;
- performance pass for scenario workspaces;
- regression coverage for determinism and lineage.

**Exit criteria**

- the full Phase 2 proof flow can be rerun from seed data and produces stable browser-visible evidence.

---

## 12. Seed and data strategy

Phase 2 needs richer operational data than the Phase 1 happy path.

### 12.1 Required seed families

Maintain at least:

1. **published baseline day** - live approved plan;
2. **jetty delay day** - current Stage 7.1 case generalized into scenario form;
3. **tug outage day** - affects more than one downstream trip;
4. **tight tide / bridge day** - produces gate wait or miss margins;
5. **rate degradation day** - slower jetty or CTS throughput;
6. **top-up demand day** - successor-plan consequence after additional demand;
7. **manual reassignment day** - planner-authored alternative chain;
8. **multi-scenario comparison day** - at least two runs against the same baseline.

### 12.2 Minimum scenario pack

Seed at least these reusable scenarios:

| Scenario | Purpose |
|---|---|
| `SIM-JETTY-DELAY` | delay propagation |
| `SIM-TUG-OUTAGE` | shared-resource conflict |
| `SIM-TIDE-RECOVERY` | window miss / wait evaluation |
| `SIM-CTS-RATE` | discharge-rate degradation |
| `SIM-TOPUP-DEMAND` | additional demand on successor draft |

### 12.3 Time handling

- seed dates must be generated relative to the current trial period, not hard-coded stale historical dates;
- every scenario result stores exact timestamps for audit;
- UI labels must show timezone-aware local operational times.

---

## 13. Testing strategy

### 13.1 Backend tests

- scenario assumption validation;
- deterministic run repeatability;
- trip-delay propagation;
- asset-outage overlap detection;
- tide/bridge wait and miss margins;
- OGV completion projection;
- demurrage calculation;
- utilization calculation;
- baseline immutability;
- run immutability;
- promotion lineage;
- permission and cross-organization visibility;
- audit events for create/run/promote/cancel.

### 13.2 Frontend tests

- assumption editor validation;
- run-status rendering;
- baseline vs scenario comparison;
- no static placeholder deltas remain;
- drill-down to source assumption and violated constraint;
- promotion disabled until a successful run exists;
- scenario/live distinction remains explicit.

### 13.3 Browser evidence

For each release candidate, prove:

1. create scenario from conflict or override;
2. edit assumptions;
3. run scenario;
4. inspect timeline, constraints, OGV completion, demurrage, and utilization;
5. compare two candidate runs;
6. promote one run;
7. confirm approval workflow and audit lineage.

---

## 14. Definition of done for product Phase 2

Phase 2 is complete when an authorized operations user can, inside the Dockerized system:

1. start from a live or draft baseline plan;
2. create a manual or source-linked scenario;
3. enter at least the initial assumption types listed in section 7.3;
4. run a deterministic scenario without mutating the baseline;
5. inspect persisted event, trip, constraint, OGV, demurrage, and utilization projections;
6. compare baseline against at least two scenario runs;
7. explain every material delta through source assumptions and constraint evaluations;
8. promote one chosen run into a successor proposed plan;
9. send the promoted plan through the unchanged dual-party approval and publish gates;
10. retrieve a full audit trail and governed export proving scenario lineage.

That is the second usable brick: Phase 1 proves the system can build and govern a plan; Phase 2 proves the system can reason about alternative futures before operators commit to one.

---

## 15. Compatibility with later product phases

### Phase 3 - GPS/AIS live tracking

Phase 3 can create scenario inputs from observed delay events, but it must not bypass the scenario assumption model.

### Phase 4 - IoT/event-driven operations

Field events can become confirmed or observed sources for scenarios. The state taxonomy in section 2 prevents event feeds from overwriting planned or projected states.

### Phase 5 - Optimization and recovery recommendation

Phase 5 should write recommendation candidates into the same scenario/run model:

- optimizer suggestion becomes explicit assumptions or a recommendation source;
- selected recommendation still materializes as a scenario run;
- promotion still follows approval and publication governance.

This is why Phase 2 must keep `ImpactChainAssessment.source_kind` extensible and projection contracts stable.

### Phase 6 - Multi-party control tower

Phase 6 can expose organization-shaped scenario views, SLA handling, and customer-safe projections without changing the underlying scenario lineage.

---

## 16. Frozen build decisions for the Phase 2 line

1. **Simulation before optimization.** Phase 2 computes consequences for explicit assumptions; it does not claim to solve the best plan automatically.
2. **Persisted projections, not transient-only JSON.** Scenario outputs must support audit, comparison, exports, and later recommendation lineage.
3. **Run-based scenario contract.** One scenario can have multiple immutable runs; one chosen run may be promoted.
4. **Existing governance remains authoritative.** No scenario promotion is itself publication.
5. **Relative seed dates.** Trial data must remain operationally relatable when reseeded later.
6. **Reuse the impact-node contract.** Stage 7.1 override assessment becomes the narrow first instance of the wider Phase 2 explainability model.
7. **No telemetry dependency.** Phase 2 remains fully operable from manual and seeded data.
