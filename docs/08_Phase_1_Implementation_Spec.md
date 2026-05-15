# 08 — Phase 1 Implementation Spec

**Project:** Coalflow Tower / Berau–ABL Transshipment Scheduling Simulation and Live Planning Platform  
**Status:** implementation specification for product Phase 1  
**Generated:** 2026-05-15  
**Primary inputs:** `00_README_Index.md`, `01_Ground_Reality_Operations.md`, `02_Planning_Tool_Scope.md`, `03_Data_Architecture_and_IoT_Scope.md`, `04_RBAC_and_Django_Architecture_Addendum.md`, `07_Frontend_Build_Handoff_and_Phasewise_Plan.md`, and `BRD - Schedulling Simulation.docx`

---

## 1. Scope interpretation

This document defines **product Phase 1** from `02_Planning_Tool_Scope.md`: the **digital scheduling model** that replaces manual Excel planning with a governed, constraint-aware operational plan.

It is intentionally distinct from the frontend phase numbering in `07_Frontend_Build_Handoff_and_Phasewise_Plan.md`.

### Phase 1 objective

Deliver a Dockerized, multi-organization scheduling application where authorized Berau and ABL users can:

1. maintain planning master data;
2. upload or enter OGV demand and cargo requirements;
3. maintain manual fleet, jetty, CTS, tide, and bridge availability;
4. generate and validate a feasible schedule;
5. inspect conflicts on dense operational boards;
6. version, review, approve, publish, and audit schedule changes.

The uploaded BRD names **July 2026** as the expected deployment target. That makes Phase 1 a delivery-focused build: ship the governed scheduling spine first, then extend it rather than diluting the first release with later-phase telemetry and optimization work.

### What Phase 1 must prove

The system can answer these questions from structured data rather than spreadsheet interpretation:

- Which OGV demand must be served, in what coal-grade sequence, by when?
- Which source, jetty, tug, barge, CTS, tide, and bridge constraints govern each trip?
- Is the current plan feasible?
- If not, exactly which constraint breaks first?
- Which version is live, who changed it, and who approved it?

### Explicitly out of scope for product Phase 1

- live AIS/GPS ingestion as a dependency for core planning;
- automated geofence state detection;
- MQTT/Kafka/Redpanda event streaming;
- optimization beyond deterministic feasible-schedule generation;
- advanced what-if simulation and automated recovery recommendation;
- customer portal;
- advanced analytics and commercial exposure dashboards;
- full IoT/device-management console.

Phase 1 should leave clean extension points for those later phases without paying their full complexity cost now.

---

## 2. Product invariants

These are not implementation preferences; they are business rules implied across the BRD and the documentation spine.

1. **This is a scheduler first.** A map is a later interface over the plan, not the product core.
2. **Coal is not generic tonnage.** Grade, product, and layer sequence are first-class constraints.
3. **Resources are coupled.** A feasible move requires compatible source, jetty, barge, tug, route, tide/bridge windows, CTS, and OGV sequence.
4. **The approved plan is sacred.** Drafts, validations, overrides, approvals, and published plans must remain separate.
5. **Manual reality still exists.** Phase 1 must work even before telemetry integrations arrive.
6. **Multiple organizations share one network.** RBAC, data scope, workflow authority, and audit cannot be postponed.
7. **Observed state, confirmed state, derived state, and recommended state must never be conflated.**

---

## 3. Phase 1 user journeys

### 3.1 Daily planning setup

1. Planner selects planning horizon.
2. Berau user uploads or enters OGV demand.
3. Authorized users confirm master data and availability:
   - coal grades / source eligibility;
   - jetty readiness;
   - tug/barge/CTS availability;
   - manual tide windows;
   - manual bridge windows.
4. System validates required data completeness.
5. Planner generates a draft feasible schedule.

### 3.2 Feasibility review

1. System shows planned trip chain by OGV.
2. System flags conflicts:
   - grade/source mismatch;
   - layer-sequence violation;
   - jetty overlap;
   - asset overlap or incompatibility;
   - tide/bridge infeasibility;
   - CTS overload;
   - unmet cargo quantity;
   - missing availability.
3. Planner edits assignment or timing where permitted.
4. System revalidates after every meaningful change.

### 3.3 Governance and publication

1. Draft plan becomes a versioned proposed plan.
2. Required reviewers inspect deltas from the previous live plan.
3. Authorized approvers approve or reject with comments.
4. Approved plan is published.
5. Every material action is auditable.

### 3.4 Replanning without telemetry

1. Dispatcher manually marks a tug unavailable, a jetty delayed, or a bridge window changed.
2. Existing live plan remains preserved.
3. Planner clones live plan into a new draft.
4. New draft is regenerated or manually adjusted.
5. Conflicts, deltas, approvals, and publication repeat through the same governed path.

---

## 4. Recommended Dockerized stack

Phase 1 should be implemented as a Docker-first monorepo. Local development, CI, and deployment should all use the same service topology wherever practical.

### 4.1 Core services

| Service | Responsibility |
|---|---|
| `frontend` | React/Next.js + TypeScript operational UI |
| `api` | Django + Django REST Framework |
| `worker` | Celery worker for imports, schedule generation, validation, exports |
| `beat` | Celery Beat for recurring housekeeping / scheduled jobs |
| `db` | PostgreSQL, preferably PostGIS-enabled for future route/geofence use |
| `redis` | cache, Celery broker/result backend, locks |
| `object-store` | S3-compatible storage such as MinIO for uploaded files / exports |
| `proxy` | Nginx or equivalent edge routing for frontend/API in shared environments |

### 4.2 Development-only helpers

| Service | Use |
|---|---|
| `mailpit` | email capture for invitations / approvals |
| `flower` | Celery monitoring |

### 4.3 Deferred services

Keep these out of the default Phase 1 runtime, but reserve architectural seams for them:

| Deferred service | Planned later use |
|---|---|
| TimescaleDB or ClickHouse | telemetry/time-series history |
| MQTT broker | IoT feeds |
| Redpanda/Kafka | event backbone |
| dedicated ingestion service | AIS/GPS/PLC input |

### 4.4 Docker acceptance

Phase 1 is not considered properly scaffolded until a new developer can:

```text
docker compose up --build
```

and obtain:

- running web UI;
- running API;
- initialized database;
- Redis-backed task queue;
- seeded development data;
- health checks for every core service;
- no host-installed Python or Node dependency required for normal development.

---

## 5. Repository layout

```text
/
  agent.md
  docker-compose.yml
  .env.example
  docs/
  backend/
    config/
    apps/
      accounts/
      organizations/
      rbac/
      masters/
      coal/
      fleet/
      ogv/
      jetties/
      routes/
      constraints/
      scheduling/
      approvals/
      audit/
      imports/
      reports/
  frontend/
    src/
      app/
      components/
      features/
      layouts/
      lib/
      styles/
  infra/
    nginx/
    docker/
  fixtures/
  tests/
```

The split is deliberate:

- Django owns transactional truth, governance, and audit.
- The frontend owns dense operational presentation, never business authority.
- Celery owns long-running work, not request threads.

---

## 6. Domain model blueprint

### 6.1 Organization and access

| Entity | Purpose |
|---|---|
| `Organization` | Berau, ABL, platform admin, later customers |
| `BusinessUnit` / `Department` | local scoping |
| `User` | authenticated actor |
| `Role` | named capability bundle |
| `Permission` | feature/action permission |
| `UserRoleAssignment` | role granted within org/scope |
| `DataScope` | what objects the role may see or mutate |
| `ApprovalAuthority` | what workflow transitions the user may perform |

### 6.2 Planning masters

| Entity | Purpose |
|---|---|
| `CoalGrade` / `ProductBrand` | Ebony, Mahoni, etc. |
| `Mine` / `Stockpile` | cargo source |
| `Jetty` | loading point |
| `Route` / `RouteSegment` | travel path and timing |
| `Tug` | towing asset |
| `Barge` | cargo carrier |
| `CTS` | transshipment asset |
| `AssetCompatibilityRule` | tug-barge / jetty / CTS / route compatibility |
| `LoadingRateProfile` | jetty/CTS throughput assumptions |

### 6.3 Demand and constraints

| Entity | Purpose |
|---|---|
| `OGVVoyage` | voyage-level demand |
| `CargoRequirement` | grade + quantity requirement |
| `CargoLayerStep` | mandated loading sequence |
| `AssetAvailabilityWindow` | manual availability / downtime |
| `JettyAvailabilityWindow` | working / blocked windows |
| `TideWindow` | feasible movement period |
| `BridgeWindow` | feasible crossing period |
| `PlanningCalendar` | horizon / timezone / day structure |

### 6.4 Scheduling and governance

| Entity | Purpose |
|---|---|
| `Plan` | logical schedule container |
| `PlanVersion` | draft/proposed/approved/published snapshot |
| `Trip` | one coal movement chain |
| `Assignment` | selected tug, barge, jetty, CTS, OGV linkage |
| `ScheduleEvent` | load, depart, cross bridge, arrive CTS, discharge, return |
| `Conflict` | validation failure |
| `Override` | manual deviation with reason |
| `ApprovalRequest` | workflow review |
| `ApprovalDecision` | approval/rejection record |
| `AuditEvent` | immutable trace |

### 6.5 Required state distinctions

Model these separately from day one:

| State type | Example |
|---|---|
| planned | “Barge B-12 departs at 14:00” |
| manually confirmed | “Jetty operator confirmed loaded at 14:18” |
| observed | later AIS/GPS observation |
| derived | later inferred waiting-tide status |
| recommended | future proposed schedule |

Even if only the first two are heavily used in Phase 1, the schema and vocabulary should not collapse them.

---

## 7. Scheduling engine specification

### 7.1 Phase 1 engine goal

Generate a **feasible**, explainable schedule — not a mathematically optimal global solution.

### 7.2 Suggested generation order

1. sort OGV voyages by laycan / ETA / explicit priority;
2. expand each voyage into required cargo layer steps;
3. for each layer step, find eligible source and jetty candidates;
4. choose earliest feasible tug/barge pair compatible with cargo, route, and jetty;
5. determine the earliest load slot;
6. find the next tide + bridge combination that supports departure and passage;
7. assign CTS based on compatibility, queue, and capacity;
8. produce full trip timeline;
9. continue until requirement quantity is satisfied or infeasibility is proven.

### 7.3 Deterministic rule set

The engine should be deterministic for identical inputs:

- stable sort order;
- reason codes for all selection decisions;
- no hidden randomness;
- full reproducibility per `PlanVersion`.

### 7.4 Validation categories

The validator must emit machine-readable conflicts at minimum for:

```text
MISSING_REQUIRED_DATA
GRADE_SOURCE_MISMATCH
LAYER_SEQUENCE_VIOLATION
JETTY_INCOMPATIBLE
JETTY_OVERLAP
TUG_UNAVAILABLE
BARGE_UNAVAILABLE
TUG_BARGE_INCOMPATIBLE
CTS_UNAVAILABLE
CTS_CAPACITY_CONFLICT
TIDE_WINDOW_MISSED
BRIDGE_WINDOW_MISSED
ROUTE_INFEASIBLE
ASSET_DOUBLE_BOOKED
CARGO_QUANTITY_UNMET
PLAN_APPROVAL_REQUIRED
```

### 7.5 Explainability requirement

Every generated trip should preserve enough evidence to answer:

- why this source was chosen;
- why this jetty was chosen;
- why this tug/barge pair was chosen;
- which tide and bridge windows were used;
- which alternatives were rejected and why, where practical.

The first implementation may store this as structured `selection_reason` metadata if a richer recommendation model is deferred.

---

## 8. API contract outline

The frontend should bind to stable resource-oriented APIs rather than screen-specific ad hoc payloads.

### 8.1 Access and organization

```text
/api/auth/*
/api/me
/api/organizations
/api/roles
/api/permissions
/api/users
```

### 8.2 Master data

```text
/api/coal-grades
/api/mines
/api/stockpiles
/api/jetties
/api/tugs
/api/barges
/api/cts-assets
/api/routes
/api/compatibility-rules
```

### 8.3 Demand and constraints

```text
/api/ogv-voyages
/api/cargo-requirements
/api/cargo-layer-steps
/api/asset-availability
/api/jetty-availability
/api/tide-windows
/api/bridge-windows
/api/import-jobs
```

### 8.4 Scheduling and governance

```text
/api/plans
/api/plan-versions
/api/plan-versions/{id}/generate
/api/plan-versions/{id}/validate
/api/plan-versions/{id}/submit
/api/plan-versions/{id}/approve
/api/plan-versions/{id}/reject
/api/plan-versions/{id}/publish
/api/trips
/api/assignments
/api/conflicts
/api/overrides
/api/audit-events
```

### 8.5 API behavior rules

- all mutating endpoints enforce backend permission checks;
- all state-changing operations emit audit events;
- plan generation and imports run asynchronously through Celery;
- published versions are immutable except via successor versions;
- API responses include both IDs and display-ready fields required by dense boards.

---

## 9. Frontend implementation surface for Phase 1

Phase 1 should borrow the visual standard from `07_Frontend_Build_Handoff_and_Phasewise_Plan.md` without trying to ship every future screen.

### 9.0 Frontend resource adaptation rule

The hardened packs in `docs/frontend_resources/` are **scenario-complete screen baselines**, not loose moodboards and not production code to copy verbatim.

Implementation must therefore follow this rule:

1. map each build chunk to the smallest set of frontend packs whose backend truth already exists;
2. adapt the scenario logic to the actual API/domain model for that chunk;
3. preserve the hardened cockpit density, hierarchy, and interaction intent;
4. never fabricate later-phase operational data merely to make a screen look complete.

Initial mapping:

| Build chunk | Primary frontend resource packs to adapt |
|---|---|
| Chunk 1 | `Users & RBAC`, `Audit & Logs`, shell cues from `Network Situation` |
| Chunk 2 | `Admin / Master Data Console` |
| Chunk 3 | `OGV Demand & Schedule`, `Coal Grade Sequence`, `Tide & Bridge Window` |
| Chunk 4 | `TugBarge Assignment`, `Jetty Loading`, `CTS / Floating Crane`, `Published Plan & Schedule` |
| Chunk 5 | `Plan Approvals & Publishing`, scenario-delta portions of `Simulation & Scenario` |
| Chunk 6 | full `Network Situation`, validator-backed parts of `Exception Center` |
| Later chunks | `Live Resource Map` and the remaining simulation/exception surfaces as their backend services become real |

### 9.1 Required screens

| Screen | Why in Phase 1 |
|---|---|
| Dashboard / Situation Board | role-aware landing page and operational summary |
| OGV Demand & Laycan | demand intake and risk review |
| Coal Grade Sequence / Layering | sequence control |
| Tug/Barge Assignment | fleet feasibility |
| Jetty Loading Plan | source-side queue and readiness |
| CTS / Floating Crane Operations | transshipment capacity |
| Tide & Bridge Window Board | navigation feasibility |
| Plan Approvals / Publishing | governance |
| Published Plan + Schedule Gantt | live execution contract |
| Users & RBAC | mandatory multi-party control |
| Admin / Master Data | system setup |
| Audit & Logs | traceability |

### 9.2 Deferred or MVP-lite screens

| Screen | Treatment in product Phase 1 |
|---|---|
| Live Resource Map | optional static placeholder or manual-state view only |
| Exception Center | lightweight conflict center backed by validator output |
| Simulation Workspace | version comparison shell only; rich what-if engine later |

### 9.3 Shared UI components that must be built first

- application shell;
- hierarchical sidebar;
- compact top bar;
- bottom audit/status strip;
- dense data grid;
- KPI strip;
- status chips;
- right detail rail;
- schedule/Gantt primitive;
- version selector;
- approval chain component;
- conflict list component;
- RBAC route/action guard layer.

---

## 10. Chunked implementation plan

### Chunk 0 — Repository and Docker foundation

**Goal:** create the execution spine before domain code.

**Build**

- monorepo folder structure;
- Dockerfiles for `frontend`, `api`, and worker image;
- `docker-compose.yml` with services listed in section 4;
- `.env.example`;
- health checks;
- database migrations bootstrap;
- lint/test commands;
- seed command skeleton;
- CI pipeline that builds containers and runs tests.

**Exit criteria**

- `docker compose up --build` succeeds from a clean checkout;
- API, frontend, database, Redis, worker, and object storage are healthy;
- migrations run inside containers;
- one sample API endpoint and one sample frontend route load.

---

### Chunk 1 — Identity, organizations, RBAC, and audit kernel

**Goal:** make every later feature safe to add.

**Backend**

- accounts, organizations, RBAC, approval-authority, and audit apps;
- role/permission schema;
- object/data-scope primitives;
- seed role templates:
  - Berau Scheduler;
  - ABL Dispatcher;
  - Joint Control Tower Manager;
  - Admin;
  - Read-only Viewer;
- audit middleware / service hooks;
- basic approval-state primitives.

**Frontend**

- login/session flow;
- role-aware shell;
- route guards;
- users/RBAC console MVP;
- audit strip reusable component.

**Tests**

- permission matrix tests;
- cross-organization visibility tests;
- audit-on-mutation tests.

**Exit criteria**

- each seeded role sees only intended navigation/actions;
- unauthorized API writes are rejected server-side;
- every sensitive mutation creates an audit event.

---

### Chunk 2 — Master data and reference catalogs

**Goal:** model the network before scheduling it.

**Backend**

- coal grades / brands;
- mines / stockpiles;
- jetties;
- tugs, barges, CTS;
- routes and route segments;
- loading-rate profiles;
- compatibility rules;
- CRUD + import/export for master data;
- versioning or activation flags for reference records.

**Frontend**

- master-data console MVP;
- dense tables;
- dependency/impact preview for edits;
- filtered views by organization / asset class.

**Tests**

- compatibility validation;
- unique code constraints;
- soft-delete / inactive-record behavior.

**Exit criteria**

- planners can configure all assets required to build a sample schedule;
- incompatible resources are not accepted silently;
- deactivated assets cannot be newly scheduled.

---

### Chunk 3 — Demand intake and manual constraints

**Goal:** replace Excel input with structured planning inputs.

**Backend**

- OGV voyage model;
- cargo requirement model;
- cargo layer sequence model;
- asset availability;
- jetty availability;
- tide windows;
- bridge windows;
- import pipeline for OGV demand and calendar inputs;
- validation jobs for required columns / formats / business rules.

**Frontend**

- OGV demand board;
- coal grade / layering board;
- tide & bridge board;
- manual availability editors;
- import job status and error review.

**Tests**

- import validation;
- layer-order validation;
- timezone/calendar tests;
- overlapping / contradictory window tests.

**Exit criteria**

- a planner can ingest a complete planning-day dataset without spreadsheet post-processing;
- invalid imports return actionable row-level errors;
- tide/bridge windows are visible against affected route segments.

---

### Chunk 4 — Schedule generation and feasibility validation

**Goal:** create the first real product value.

**Backend**

- plan and plan-version models;
- trip, assignment, and schedule-event models;
- deterministic generation service;
- validation engine;
- machine-readable conflicts;
- async generation job;
- plan cloning.

**Frontend**

- published-plan / schedule board;
- tug/barge assignment board;
- jetty loading plan;
- CTS operations board;
- conflict center MVP;
- version selector.

**Tests**

- deterministic generation regression tests;
- end-to-end happy path fixtures;
- conflict fixtures for every required validator category;
- idempotency tests for reruns against unchanged inputs.

**Exit criteria**

- system can generate a complete draft plan from seeded realistic data;
- system names the exact blocking constraint when feasibility fails;
- repeated generation on identical data returns identical scheduling output.

---

### Chunk 5 — Manual editing, override controls, and plan lifecycle

**Goal:** support human dispatch reality without corrupting governance.

**Backend**

- controlled assignment edits;
- override request model with reason codes;
- lifecycle transitions:
  - Draft;
  - Proposed;
  - Approved;
  - Published;
  - Superseded;
- approval requests / decisions;
- immutable published snapshots;
- plan diff service.

**Frontend**

- approval / publishing screen;
- compare-version view;
- override UI with reason capture;
- approval chain;
- publish-blocking checklist.

**Tests**

- illegal transition tests;
- mandatory reason-code tests;
- publish-blocking tests when conflicts remain;
- diff correctness tests.

**Exit criteria**

- no live plan can be overwritten silently;
- every manual override has reason, actor, timestamp, and impacted objects;
- publish is blocked until required approvals and validations pass.

---

### Chunk 6 — Dashboard and operational read models

**Goal:** turn the plan into a control-tower working surface.

**Backend**

- read-optimized endpoints for dashboard, KPI strip, plan risk, queue pressure, and latest version;
- conflict aggregation;
- role-aware summary shaping.

**Frontend**

- dashboard / situation board;
- KPI strip;
- right-side action rail;
- bottom audit/status strip;
- drill-down links into OGV, asset, constraint, and plan views.

**Tests**

- role-shaped response tests;
- KPI correctness tests from known fixtures;
- query-performance baselines.

**Exit criteria**

- a user can identify the highest-risk OGV, most constrained resource, and current live version in seconds;
- all dashboard numbers reconcile with the underlying schedule data.

---

### Chunk 7 — Reporting, exports, and operational handoff

**Goal:** make Phase 1 usable in the organization, not merely demonstrable.

**Backend**

- governed exports:
  - plan export;
  - conflict export;
  - audit export;
- object-storage integration;
- export permissions;
- printable / shareable schedule formats;
- seeded demo datasets.

**Frontend**

- export controls;
- import/export history;
- error/empty/loading states;
- access-aware export visibility.

**Tests**

- export permission tests;
- file-generation tests;
- empty-state regressions.

**Exit criteria**

- authorized users can share a plan without reverting to manual spreadsheet assembly;
- unauthorized users cannot exfiltrate full-network data.

---

### Chunk 8 — Hardening and pilot readiness

**Goal:** prepare the system for real users.

**Build**

- performance pass on dense boards;
- indexes and query tuning;
- backup/restore rehearsal;
- observability baseline;
- fixture refresh;
- user acceptance test scripts;
- role-based regression suite;
- API documentation;
- admin runbook;
- incident-safe logging without leaking sensitive data.

**Exit criteria**

- full seeded workflow passes from demand upload to published plan;
- role regression suite is green;
- backup restore is proven;
- Docker deployment instructions are repeatable by a second engineer.

---

## 11. Suggested milestone sequence

| Milestone | Contents |
|---|---|
| M0 | Docker foundation live |
| M1 | RBAC + audit kernel |
| M2 | Master data + constraints configured |
| M3 | OGV demand intake works |
| M4 | Draft schedule generation + conflict validation |
| M5 | Governed approval / publish workflow |
| M6 | Situation board + exports |
| M7 | Pilot-ready hardening |

The project should not wait until late implementation to test with realistic seeded data. Domain fixtures should arrive by M2 and become stricter over time.

---

## 12. Data, testing, and seed strategy

### 12.1 Seed datasets

Maintain at least:

1. **happy path day** — all demand feasible;
2. **tight tide day** — missed-window risk;
3. **grade sequence failure day**;
4. **asset outage day**;
5. **approval pending day**;
6. **multi-org visibility day**.

### 12.2 Test layers

| Layer | Purpose |
|---|---|
| unit | business-rule correctness |
| service | schedule generation / validation |
| API | authorization + contracts |
| integration | import → generation → approval → publish |
| frontend | route guards, dense board rendering, state behavior |
| regression fixtures | deterministic outputs on known datasets |

### 12.3 Non-negotiable regression cases

- wrong grade cannot satisfy the next layer step;
- a barge cannot be double-booked;
- unavailable tug cannot be assigned;
- bridge/tide violations are detected;
- published plan remains immutable;
- users cannot cross organization/data-scope boundaries;
- exports obey permission scope.

---

## 13. Definition of done for product Phase 1

Phase 1 is complete when a realistic operations user can, inside the Dockerized system:

1. log in under the correct organization and role;
2. configure or review the relevant master data;
3. upload OGV demand and cargo-layer requirements;
4. enter manual availability plus tide/bridge windows;
5. generate a draft schedule;
6. inspect a full trip chain and any conflicts;
7. make governed adjustments with reasons;
8. submit, approve, and publish a plan;
9. retrieve the live published version and its audit trail;
10. export the governed schedule without falling back to spreadsheet surgery.

That is the first usable brick. Later phases can add telemetry, richer simulation, optimization, and customer visibility on top of a product that already understands the work.

---

## 14. Frozen build decisions after Chunk 0

The following choices are now fixed for the first implementation line:

1. **Frontend:** React + Vite SPA, not Next.js.  
   Rationale: this is a desktop-heavy operational cockpit with no SEO requirement; a lean SPA keeps the frontend simple while Django remains the API and workflow authority.

2. **Database:** PostGIS-enabled PostgreSQL image from day one.  
   Rationale: route, geofence, and later live-map work are certain extensions of the product even though Phase 1 does not yet require telemetry.

3. **Object storage:** MinIO included in local/dev from day one.  
   Rationale: uploaded OGV files, exports, and later raw vendor payloads need an object-storage seam early.

4. **Initial import contract:** XLSX as the primary legacy-input format, with CSV accepted where lossless.  
   Rationale: the current process is Excel-based, so the first release should meet operators where they already work while keeping a simpler machine-friendly path available.

5. **Publish governance:** dual-party approval before publication.  
   Rationale: a published plan affects both Berau demand commitments and ABL execution resources; one-sided publication is the wrong default for a shared operating network.

6. **Seed roles for the first pilot:** Berau Scheduler, ABL Dispatcher, Joint Control Tower Manager, Admin, and Read-only Viewer.  
   Rationale: this is the smallest role set that still preserves planning ownership, dispatch ownership, shared control, administration, and safe observation.

7. **Live Resource Map in product Phase 1:** manually driven view only, if included.  
   Rationale: spatial context is useful, but live AIS/GPS must not become a hidden dependency for the digital scheduling model.

Everything else can evolve behind the architecture above without bending the product out of shape.
