# 07 — Frontend Build Handoff and Phase-wise Implementation Plan

**Project:** Coalflow Tower / Berau–ABL Transshipment Scheduling Simulation and Live Planning Platform  
**Audience:** frontend build team, backend/API team, product owner, QA, implementation lead  
**Status:** build-stage handoff document  
**Generated:** 2026-05-15

---

## 1. Purpose of this document

This document consolidates the frontend resources, validated mock screens, MVP priorities, and phase-wise implementation plan for the Berau–ABL scheduling simulation and live planning platform.

The wider documentation set already defines:

- the operational ground reality of Berau Coal and ABL transshipment;
- the planning scope of the tool;
- the GPS/AIS/IoT/data architecture context;
- the RBAC and Django architecture addendum;
- the frontend visual thesis and operational UI hardening rules;
- hardened frontend mock resources under `docs/frontend_resources/`.

This document translates that into a coding handoff plan.

---

## 2. BRD alignment summary

The uploaded BRD defines the product as a replacement for manual/static Excel scheduling between Berau Coal and ABL. The workflow must support:

- OGV schedule and demand ingestion;
- coal grade and layering sequence control;
- tug/barge/CTS fleet scheduling;
- jetty availability and loading readiness;
- river tide and bridge constraints;
- GPS/AIS or internal tracking of fleet status;
- operational events such as breakdowns and delays;
- real-time alerts and schedule updates.

The frontend screens created so far cover the required operating loop:

```text
Demand → planning → logistics assignment → constraint check → exception → simulation → approval → published plan → live execution monitoring → audit
```

The frontend should therefore be treated as a **dense operational planning cockpit**, not a generic map dashboard or marketing portal.

---

## 3. Frontend visual standard to freeze

The frontend style is now sufficiently mature to freeze the visual language.

Mandatory visual rules:

- rich dark theme;
- compact/dense layout;
- minimal padding;
- compact grids and row heights;
- no hero banners;
- no marketing artifacts;
- no decorative empty panels;
- sidebar with module/submodule hierarchy;
- right-side detail/decision rails;
- bottom audit/status strip;
- status colors used only for operational meaning;
- all actions routed into governed workflows.

Approved semantic color usage:

| Meaning | Treatment |
|---|---|
| Active / planned / selected | cyan / blue |
| Healthy / completed / on-plan | green |
| Warning / tight margin / waiting | amber |
| Critical / violation / blocked | red |
| Override / approval pending | purple or muted accent |
| Inactive / superseded / stale | grey |

---

## 4. Frontend resource pack inventory

The `docs/frontend_resources/` folder contains hardened mock resources. Each zip generally includes:

- `screen.png` — approved or near-approved visual reference;
- `code.html` — prototype HTML output from the mock tool;
- `DESIGN.md` — tool-generated local design notes.

These resources are **visual and interaction baselines**, not production-ready source code. The frontend team should re-implement them using the agreed application architecture and component system.

| Resource zip | Screen represented | Handoff use |
|---|---|---|
| `Network Situation - Hardened Cockpit.zip` | Network Situation / Operations Cockpit | detailed network control-room pattern |
| `OGV Demand & Schedule - Detail Cockpit.zip` | OGV Demand & Laycan | OGV demand and schedule table pattern |
| `TugBarge Assignment - Hardened Console.zip` | Tug/Barge Assignment | dispatcher assignment console pattern |
| `Jetty Loading - Hardened Execution Plan.zip` | Jetty Loading Plan | jetty queue/loading execution pattern |
| `Tide & Bridge Window - Hardened Analytics.zip` | Tide / Bridge Window Board | constraint timeline and affected trips pattern |
| `CTS  Floating Crane - Hardened Operations Board.zip` | CTS / Floating Crane Operations | CTS discharge and queue board pattern |
| `Coal Grade Sequence - Hardened Standard.zip` | Coal Grade Sequence / Layering | grade/hatch/layer governance pattern |
| `Simulation & Scenario - Hardened Operations Console.zip` | Simulation Workspace | scenario comparison and recovery workflow |
| `Exception Center - Hardened Triage Cockpit.zip` | Exception Center | active exception triage pattern |
| `Plan Approvals & Publishing - Hardened Governance Cockpit.zip` | Plan Approvals | approval and publishing governance pattern |
| `Published Plan & Schedule - Hardened Operating Standard v2.zip` | Published Plan + Schedule Gantt | live execution contract pattern |
| `Live Resource Map - Operational Radar.zip` | Live Resource Map | spatial visibility and selected-asset pattern |
| `Admin  Master Data Console - Hardened Operational Standard.zip` | Master Data Console | governed admin/config pattern |
| `Users & RBAC - Hardened Governance Cockpit Standard.zip` | Users & RBAC | RBAC governance pattern, near-freeze |
| `Audit & Logs - Hardened Governance Standard.zip` | Audit & Logs | audit event table and traceability pattern |

---

## 5. Screen inventory and validation status

### 5.1 MVP-critical screens

| # | Screen | Module | MVP priority | Validation status | Build note |
|---:|---|---|---|---|---|
| 1 | Dashboard / Situation Board | Network / Dashboard | P0 | **Approved / frozen** | role-aware landing cockpit; use as home screen |
| 2 | OGV Demand & Laycan | Schedule | P0 | **MVP-ready baseline** | validate final columns during implementation |
| 3 | Coal Grade Sequence / Layering | Schedule | P0 | **Approved with minor implementation checks** | ensure Schedule placement, Jetty/CTS/Blocking Reason columns |
| 4 | Tug/Barge Assignment | Logistics | P0 | **Approved / frozen** | use as standard dispatcher console |
| 5 | Jetty Loading Plan | Logistics | P0 | **Approved with functional hardening** | ensure queue position, OGV link, grade/hatch link, planned vs actual |
| 6 | CTS / Floating Crane Operations | Logistics | P0 | **Approved / frozen** | queue, rate, OGV completion risk, recovery panel |
| 7 | Tide & Bridge Window Board | Constraints | P0 | **Approved with minor timeline hardening** | make open/closed windows and ETA markers explicit |
| 8 | Exception Center | Exceptions | P0 | **Approved / frozen** | central triage, SLA, owner, simulation conversion |
| 9 | Simulation / Scenario Workspace | Simulation | P0 | **Approved / frozen** | baseline vs scenario, delta summary, approval workflow |
| 10 | Plan Approvals / Publishing | Schedule | P0 | **Approved / frozen** | publish blocked until approvals/checks pass |
| 11 | Published Plan + Schedule Gantt | Schedule | P0 | **Approved / frozen** | official live execution contract |
| 12 | Live Resource Map | Map | P1 | **Approved / frozen for MVP** | spatial visibility only; no direct mutation |
| 13 | Users & RBAC | Admin | P0 | **Near-freeze; MVP-critical** | final hardening: grid columns, full module matrix, approval authority limits |
| 14 | Admin / Master Data Console | Admin | P1 | **Approved / frozen** | config validation, dependency impact, publish flow |
| 15 | Audit & Logs | Admin | P1 | **Near-freeze** | final hardening: product name, correlation chain, contextual actions |

### 5.2 Post-MVP or V1.1 screens

| Screen | Module | Timing | Reason |
|---|---|---|---|
| Device & Feed Health | Admin / IoT | MVP-lite or V1.1 | needed if live GPS/AIS feed is in pilot scope |
| Integration Health Console | Admin / Ops | V1.1 | important for production hardening, not first UI loop |
| Route & Geofence Editor | Admin / Map | V1.1 | route/geofence setup can start as master data table in MVP |
| Stale Signal Monitor | Map / IoT | V1.1 | can be represented via Live Map filters in MVP |
| Shift Handover / My Actions | Dashboard / Ops | V1.1 | useful but can start as dashboard panel |
| Customer / Shipment Visibility Portal | Customer | Post-MVP | expose only after internal published-plan workflow is stable |
| Advanced Map History / Playback | Map | Post-MVP | not required for first operational pilot |
| Executive Analytics / Financial Exposure Dashboard | Analytics | Post-MVP | useful later; not part of core planning loop |

---

## 6. MVP frontend scope recommendation

The MVP frontend should prove the full operating loop, not the full future product.

MVP operating loop:

```text
1. User logs in with organization/role/scope
2. Dashboard shows network state and priority actions
3. OGV demand and coal grade sequence are reviewed
4. Tug/barge, jetty, CTS, and tide/bridge boards show feasible execution plan
5. Exception Center captures operational disruption
6. Simulation Workspace tests recovery
7. Plan Approvals governs cross-party approval
8. Published Plan becomes the execution contract
9. Live Resource Map shows spatial status and signal confidence
10. Audit & Logs records all governed actions
```

MVP must include:

- role-aware shell and navigation;
- RBAC route/component guards;
- dashboard / situation board;
- core schedule and logistics boards;
- exception, simulation, approval, published-plan screens;
- live map MVP;
- audit strips and compact audit console;
- master data and RBAC minimum viable admin flows.

MVP should defer:

- customer portal;
- advanced analytics;
- advanced map playback;
- full integration monitoring suite;
- full route/geofence editor;
- deep IoT management console.

---

## 7. Recommended frontend implementation phases

## Phase 0 — Frontend foundation and design system

**Goal:** create the coding foundation before screen-by-screen build.

Deliverables:

- application shell;
- dark theme design tokens;
- typography scale;
- dense table/grid component;
- KPI strip component;
- right detail rail component;
- bottom audit/status strip component;
- sidebar with module/submodule hierarchy;
- tab bar component;
- status pill/severity marker component;
- timeline/Gantt primitive;
- RBAC-aware route guard scaffold;
- mock data service layer;
- shared layout templates.

Key routes to scaffold:

```text
/dashboard/situation
/schedule/ogv-demand
/schedule/coal-grade
/schedule/published-plan
/schedule/plan-approvals
/logistics/tug-barge
/logistics/jetty-loading
/logistics/cts-operations
/constraints/tide-bridge
/exceptions/active
/simulation/workspace
/map/live
/admin/master-data
/admin/users-rbac
/admin/audit-logs
```

Acceptance gate:

- every screen can mount inside the same shell;
- theme is consistent;
- sidebar and top header are stable;
- mock API layer can be swapped later for backend APIs.

---

## Phase 1 — Governance and access MVP

**Goal:** make the app safe for multi-party pilot usage.

Build:

1. Users & RBAC Console
2. Role-aware shell behavior
3. Admin / Master Data Console, MVP subset
4. Audit strip component across all screens
5. Audit & Logs, compact MVP console

Why first:

- Berau, ABL, joint control tower, and read-only users must see different data/actions.
- Approval authority must be explicit before Plan Approvals is used.
- Access mistakes in a shared Berau–ABL system are high-risk.

Minimum role templates:

- Berau Scheduler
- ABL Dispatcher
- Joint Control Tower Manager
- Admin
- Read-only Viewer

Phase 1 acceptance gate:

- user can log in as each role and see correct navigation/actions;
- direct unauthorized actions are hidden or disabled;
- every sensitive action requires audit event;
- admin can validate user access and request review.

---

## Phase 2 — Core planning and logistics boards

**Goal:** expose the operational plan components before simulation/recovery.

Build:

1. OGV Demand & Laycan Board
2. Coal Grade Sequence / Layering Board
3. Tug/Barge Assignment Board
4. Jetty Loading Plan
5. CTS / Floating Crane Operations Board
6. Tide & Bridge Window Board

Core UX rule:

Every board must show:

```text
object → status → owner → constraint → next action → linked exception/simulation/approval
```

Phase 2 acceptance gate:

- OGV demand can be understood by laycan, quantity, grade, hatch/layer;
- tug/barge, jetty, CTS assignments are visible and linked to OGV;
- tide/bridge constraints are visible against affected movements;
- coal grade sequence violations are visible;
- every row has drilldowns to related modules.

---

## Phase 3 — Exception, simulation, approval, publish loop

**Goal:** complete the decision loop.

Build:

1. Exception Center
2. Simulation / Scenario Workspace
3. Plan Approvals / Publishing
4. Published Plan + Schedule Gantt

This is the core MVP value chain.

Required flow:

```text
Exception created → convert to scenario → simulate recovery → promote to proposed → approve → publish → monitor in published plan
```

Phase 3 acceptance gate:

- exception can open simulation with context;
- simulation can show baseline vs scenario variance;
- simulation can promote to proposed plan;
- approval screen blocks publish until gates pass;
- published plan displays live version, source approval, source simulation, and variance;
- no screen directly mutates live plan outside governed flow.

---

## Phase 4 — Live execution visibility

**Goal:** add spatial and feed-based operational trust.

Build:

1. Live Resource Map, MVP-hardened
2. Stale GPS/AIS state in map and dashboard
3. Device/feed status mini-panels
4. Map-to-exception/simulation/assignment drilldowns

Phase 4 acceptance gate:

- selected asset shows paired asset, signal source, signal freshness, ETA variance, linked exception;
- map actions route to governed screens;
- stale/lost signals are visible;
- no direct drag/drop reassignment or direct route editing exists in MVP.

---

## Phase 5 — MVP production hardening

**Goal:** prepare for pilot usage.

Build/refine:

- audit/export restrictions;
- integration/feed health MVP-lite;
- master-data validation and dependency expansion;
- error/loading/empty states;
- role-based regression pass;
- responsive/density pass;
- QA test scenarios;
- backend API integration.

Phase 5 acceptance gate:

- screens handle empty/partial/stale data;
- API errors are visible without breaking layout;
- all sensitive actions are auditable;
- feature flags can hide non-MVP items;
- all MVP roles pass navigation/action tests.

---

## Phase 6 — Post-MVP expansion

Candidate features:

- customer shipment portal;
- advanced map playback/history;
- route/geofence visual editor;
- integration health console;
- device management console;
- shift handover module;
- advanced analytics and commercial exposure dashboard;
- mobile/tablet variants for jetty/CTS/vessel users.

---

## 8. Frontend route and module structure

Recommended route hierarchy:

```text
/dashboard
  /situation
  /my-actions
  /shift-handover

/schedule
  /ogv-demand
  /coal-grade-sequence
  /published-plan
  /plan-approvals
  /gantt

/logistics
  /tug-barge-assignment
  /jetty-loading
  /cts-operations

/constraints
  /tide-bridge
  /route-restrictions

/exceptions
  /active
  /assigned-to-me
  /escalations
  /resolved
  /rules

/simulation
  /workspace
  /comparison
  /templates

/map
  /live
  /route-geofence
  /stale-signals

/admin
  /master-data
  /users-rbac
  /organizations
  /device-mapping
  /integration-health
  /audit-logs
```

For MVP, only build routes that support the MVP flow. Post-MVP routes can appear disabled/hidden behind feature flags.

---

## 9. Component library required for build

### Layout components

- `AppShell`
- `ModuleSidebar`
- `TopHeader`
- `KpiStrip`
- `RightDetailRail`
- `BottomAuditStrip`
- `PageTabs`
- `FilterPanel`
- `SplitPaneLayout`

### Data display components

- `DenseDataGrid`
- `StatusPill`
- `SeverityMarker`
- `VarianceBadge`
- `OwnerSlaCell`
- `ConstraintChecklist`
- `ApprovalChain`
- `ResourceChain`
- `VersionSelector`
- `EventTicker`

### Planning components

- `ScheduleGantt`
- `TimelineRowGroup`
- `PlanBlock`
- `CurrentTimeMarker`
- `TideBridgeWindowBand`
- `ScenarioDeltaCard`
- `GradeSequenceStrip`
- `ImpactChain`

### Map components

- `LiveResourceMap`
- `MapLayerControl`
- `AssetMarker`
- `RouteOverlay`
- `GeofenceOverlay`
- `MapLegend`
- `SelectedAssetPanel`

### Governance components

- `ApprovalDecisionPanel`
- `DecisionCommentBox`
- `ValidationChecklist`
- `DependencyImpactPanel`
- `AuditEventDetail`
- `RbacPermissionMatrix`
- `ScopeSummary`

---

## 10. API integration readiness checklist

Before frontend-backend binding, each screen needs API contracts for:

| Domain | API contract needed |
|---|---|
| RBAC | user, org, role, permission, scope, approval authority |
| Dashboard | network state, priority actions, KPIs, role-specific panels |
| OGV demand | voyages, laycan, quantity, customer, grade, risk |
| Coal grade | hatch/layer sequence, grade status, conflicts |
| Tug/Barge | pairings, status, availability, assignment timeline |
| Jetty | queues, loading plan, grade readiness, actuals |
| CTS | discharge queue, rate, current OGV, downtime |
| Tide/Bridge | windows, asset eligibility, missed-window risks |
| Exceptions | exception lifecycle, owner, SLA, impact, recovery |
| Simulation | scenario input, baseline, scenario output, variance, recovery |
| Approvals | approval request, chain, status, publish readiness |
| Published plan | plan version, plan items, Gantt data, live variance |
| Live map | asset positions, routes, geofences, signal freshness |
| Master data | records, validations, dependencies, config versions |
| Audit | audit events, deltas, correlation chains, export restrictions |

---

## 11. MVP completion assessment

### Complete enough for coding handoff

The documentation set is now sufficient for frontend implementation handoff because it contains:

- business context;
- planning scope;
- data/IoT architecture;
- RBAC/Django architecture direction;
- frontend visual thesis;
- operational UI hardening addendum;
- hardened mock resources for the primary MVP screens;
- this build handoff and phase-wise implementation plan.

### Remaining gaps before sprint execution

These are not conceptual blockers, but they should be closed during sprint planning:

1. Final route list and feature flags.
2. API contract stubs for each MVP screen.
3. Exact role-permission matrix for MVP users.
4. Data model names and IDs aligned with backend naming.
5. Mock dataset that exercises all key states: normal, late, blocked, stale, approval pending, violation.
6. Definition of source of truth for live state: backend state API vs stream updates.
7. Mobile/tablet behavior decision for jetty/CTS operators.
8. Final copy/naming pass: keep `COALFLOW TOWER` consistent.

---

## 12. Coding handoff rules

Frontend team should follow these rules:

1. Build the component system before individual screens.
2. Use mock APIs, not hardcoded screen-only data.
3. Do not copy prototype HTML blindly into production.
4. Keep all screens dense and operational.
5. Never add hero panels or large decorative visuals.
6. Use status colors only for real operational meaning.
7. Implement RBAC gating at route and action level.
8. Route all plan changes through simulation/approval/publishing flow.
9. Make every KPI/filter/action drillable where relevant.
10. Make audit/event strips reusable across screens.
11. Use feature flags for non-MVP screens.
12. Keep customer-facing views separate and restricted post-MVP.

---

## 13. Recommended first coding sprint

Sprint 1 should not start with all screens. It should create the application spine.

Sprint 1 deliverables:

- app shell;
- sidebar/header/bottom strip;
- theme tokens;
- dense data grid;
- KPI strip;
- right detail rail;
- mock data service;
- RBAC route guard placeholder;
- dashboard route skeleton;
- users/RBAC route skeleton;
- published-plan route skeleton.

Sprint 1 acceptance:

- same shell renders at least three screens;
- role-aware navigation can hide/show modules;
- mock data can be swapped by route;
- no screen-level one-off styling drift.

---

## 14. Recommended MVP sprint sequencing

| Sprint | Focus | Screens / components |
|---:|---|---|
| 1 | Foundation | App shell, theme, grid, KPI, rail, audit strip, mock API |
| 2 | Governance MVP | Users & RBAC, Admin master-data shell, Audit strip/events |
| 3 | Planning boards | OGV Demand, Coal Grade Sequence, Tide/Bridge |
| 4 | Logistics boards | Tug/Barge, Jetty Loading, CTS Operations |
| 5 | Exception + Simulation | Exception Center, Simulation Workspace |
| 6 | Approval + Published Plan | Plan Approvals, Published Plan + Gantt |
| 7 | Dashboard + Map | Situation Board, Live Resource Map MVP |
| 8 | Integration hardening | role tests, audit logs, feed health, error/empty states |

---

## 15. Final handoff conclusion

The documentation and mock resources are now complete enough to hand over to coding, provided the team treats them as a governed frontend build system rather than isolated screen mockups.

The critical MVP path is:

```text
RBAC → Dashboard → Planning Boards → Exception → Simulation → Approval → Published Plan → Live Map → Audit
```

The design direction is frozen: dense, dark, operational, governed, role-aware, and audit-backed.

