# ABL Operational Blueprinting Proposal - Application Build Extension v2

**Prepared for:** ABL Group  
**Operating context:** ABL - Berau Coal transshipment, port, barging, CTS and OGV loading operations  
**Document purpose:** Product development extension to the Operational Blueprinting & Simulation Prototype Proposal  
**Date:** 31 May 2026

---

## 1. Executive Summary

The original proposal establishes the need for Operational Diagnostic, Blueprinting, Simulation Prototype and Workflow Validation before entering full-scale implementation. This extension defines how the validated blueprint can be converted into an application build.

The proposed product is a **Dynamic Operational Synchronization & Scheduling Platform** for ABL and Berau Coal operations. It is not only a fleet-tracking screen, not only a map, and not only a digital replacement for Excel. The product is designed to convert Berau shipment demand into a feasible ABL execution plan by matching each movement requirement with the right cargo, jetty, tug, barge, route, tide window, bridge window, CTS asset, OGV sequence and approval workflow.

The key build philosophy is simple:

> Every shipment movement should be treated as a schedulable flow entity moving through a defined route of operational steps, where each step requires a valid resource, a valid time window, and enough continuous capacity to execute without breaking the downstream commitment.

The proposed system should therefore contain a scheduling spine, scenario workflow, live evidence layer, trusted operational event layer, recovery recommendation workflow, guided operator flow, publishability gate, audit trail and governed export surfaces.

The application build should therefore be proposed as a phased product implementation after blueprint validation, with each sprint building one layer of operational scheduling maturity.

---

## 2. Business Use Case

The business use case is:

> Synchronize Berau Coal's shipment commitments with ABL's real operational flow capacity so that cargo readiness, asset availability, tide/bridge windows, jetty/CTS capacity, OGV loading sequence and recovery decisions can be planned and governed from one shared operating platform.

### 2.1 Business problems addressed

| Business problem | Application response |
|---|---|
| Static Excel planning cannot absorb daily and intra-day changes | Structured demand intake, versioned plan generation, conflict checks and governed replanning |
| Shipment demand is not continuously synchronized with logistics capacity | OGV demand, cargo grade, route, tug-barge, jetty, CTS and window capacity are held in one planning model |
| Asset position is visible but operational status is unclear | GPS/AIS evidence is separated from confirmed operational events and schedule authority |
| Tide, bridge and berth windows keep changing the feasible plan | Movement windows are treated as schedulable capacity, not as notes beside the plan |
| Coal grade and loading sequence affect execution | Cargo requirement and layer sequence are first-class planning inputs |
| Existing work in progress affects all new planning | Active plans, sailing barges, loaded barges, queues and confirmed actuals are plotted before new planning decisions |
| Disruption recovery is manual and experience-driven | Scenario simulation and recovery recommendations show candidate options, impact and approval path |
| Approvals and operating decisions require traceability | Dual-party approvals, immutable published snapshots, audit events and governed exports |

---

## 3. Scheduling Philosophy For The ABL Build

The ABL platform should be explained as a flow scheduler. The product does not simply place vessels on a timeline. It creates start and end commitments for operational activities across a chain of resources and constraints.

### 3.1 Scheduling entity

The minimum schedulable entity is the movement or shipment flow item that requires execution. Depending on the operating layer, this may be:

- an OGV cargo requirement;
- a cargo grade/layer step;
- a barge movement;
- a tug-barge trip;
- a jetty loading operation;
- a CTS discharge operation;
- a recovery scenario movement;
- a published plan execution step.

Each entity carries demand, priority, route, quantity, grade, eligible resources, target date, predecessor dependencies and downstream impact.

### 3.2 Route and dependency chain

Every entity moves through a route of operational steps. For ABL, the route is not only geographical. It is also operational:

```text
Cargo readiness
-> Jetty / BLC loading
-> Tug-barge departure
-> Tide / river movement
-> Bridge crossing
-> Anchorage / CTS queue
-> CTS discharge
-> OGV hatch / layer completion
-> Survey / handover closure
```

The system must understand predecessor and successor logic. A CTS discharge cannot start before the barge arrives. A hatch/layer sequence cannot be completed before the required grade arrives. A return cycle cannot release the tug-barge until the previous movement is actually complete.

### 3.3 Resource capacity and calendars

Each operational resource has a capacity calendar or availability window:

- jetty/BLC working window;
- tug availability;
- barge availability;
- CTS availability;
- bridge opening window;
- tide-safe movement window;
- berth or anchorage capacity;
- cargo readiness window;
- survey and documentation window.

The platform should treat these windows as schedulable capacity. A movement is feasible only when the required resource and the required window are both available for the required duration.

### 3.4 Free, occupied and blocked windows

The plan should clearly distinguish:

- free capacity;
- occupied capacity;
- blocked or non-working capacity;
- tentative capacity;
- confirmed actual capacity usage;
- recommended future capacity usage.

This is important because a movement cannot be allowed to overlap with another movement on the same constrained resource. It also cannot be allowed to jump over an occupied or blocked window when the operation requires continuous execution.

### 3.5 Current work before new work

The system should first plot current execution state before scheduling new or revised movements. This includes:

- active published trips;
- loaded barges already in movement;
- barges waiting at jetty or CTS;
- confirmed loading or discharge events;
- unavailable assets;
- bridge/tide windows already consumed;
- operational exceptions already active.

Only after the current state is plotted should the system attempt to place new demand, revised movements or recovery options.

### 3.6 Moving primary constraint

In ABL operations, the primary limiting factor can shift continuously. It may be:

- a tide window;
- a bridge window;
- a jetty slot;
- a CTS queue;
- a berth or anchorage limitation;
- tug-barge availability;
- cargo readiness;
- OGV laycan pressure;
- survey or handover closure.

This makes the ABL application different from a static planning board. The system must evaluate which constraint is controlling the flow at the time of scheduling and must expose that constraint when the movement cannot be placed.

### 3.7 Forward and reverse planning

The platform should support both planning directions:

- forward scheduling from current readiness and available operating windows;
- reverse planning from OGV laycan, required completion date or hatch/layer target.

This is important because the operating team often needs to ask two questions:

1. Given today's real capacity, what can be executed?
2. Given the OGV commitment, what must be ready earlier in the chain?

### 3.8 Candidate paths and best feasible plan

For the same movement requirement, the system may evaluate multiple candidate paths:

- different tug-barge pair;
- different departure window;
- different jetty slot;
- different CTS asset;
- different bridge/tide passage;
- different sequence against nearby movements.

The scheduler should evaluate feasible options, reject impossible options, rank usable candidates and preserve the reason for selection.

---

## 4. Product Development Direction

The build should extend the blueprinting proposal through three product layers.

### 4.1 Layer 1 - Governed scheduling model

This layer creates the structured planning spine:

- OGV voyage and laycan intake;
- cargo quantity, coal grade and loading sequence;
- source, stockpile, jetty and route master data;
- tug, barge and CTS availability;
- tide and bridge calendars;
- deterministic schedule generation;
- conflict detection;
- plan versioning;
- approval, publish and audit.

This layer replaces spreadsheet interpretation with structured operational truth.

### 4.2 Layer 2 - Simulation and operational evidence

This layer adds scenario and live-state interpretation:

- delay, outage, window-change and reassignment assumptions;
- projected trip, event, OGV completion and utilization impact;
- GPS/AIS-style position evidence;
- geofence, ETA variance and stale-signal alerts;
- event candidates from device, operator or feed input;
- trusted confirmation before schedule actualization.

This layer lets planners test consequences without mutating the approved baseline.

### 4.3 Layer 3 - Recovery and guided execution

This layer adds guided decision support:

- recovery input snapshots from active plan, alerts, confirmed events and conflicts;
- ranked recovery options;
- root-cause validation;
- scenario creation from selected recovery option;
- publishability assessment;
- guided Next Action workflow;
- projection-only commercial and telemetry trust review surfaces.

This layer improves recovery speed while preserving Berau and ABL approval authority.

---

## 5. Phase Of Development In Sprint Level

For proposal purposes, the product build can be presented as the following sprint-level application plan.

| Sprint level | Build focus | Key outcome |
|---:|---|---|
| Sprint 0 | Application foundation: web application, API service, database, background processing, file storage and routing layer | Runnable product spine |
| Sprint 1 | Master data and governance: organizations, RBAC, audit, locations, cargo, jetties, routes, assets and compatibility | Safe multi-party operating model |
| Sprint 2 | Demand and capacity intake: OGV demand, cargo layer, asset windows, jetty windows, tide windows and bridge windows | Structured inputs for planning |
| Sprint 3 | Scheduling entity and route model: trips, assignments, schedule events and route-step dependencies | Movement chain represented as schedulable work |
| Sprint 4 | Capacity placement and feasibility: candidate paths, occupied/free windows, conflict checks and movement candidates | Feasible plan with explicit blockers |
| Sprint 5 | Plan governance: versions, overrides, approval requests, approval decisions, published snapshots and exports | Approved execution contract |
| Sprint 6 | Scenario simulation: assumptions, projected events, projected trips, constraint evaluations and utilization outputs | What-if planning and impact visibility |
| Sprint 7 | Live evidence: telemetry sources, asset identities, position pings, latest asset state, geofences and ETA variance | Planned-vs-observed movement visibility |
| Sprint 8 | Confirmed operations: integration feeds, devices, event candidates, confirmed events, actualization and device health | Trusted execution status layer |
| Sprint 9 | Recovery recommendations: input snapshots, ranked options, recovery actions and proof pack | Decision support for disrupted flow |
| Sprint 10 | Guided recovery and hardening: flow runtime, Next Action guidance, root-cause validation, publishability, review surfaces and tests | Pilot-ready governed control tower |

### 5.1 Proposal interpretation

The sprint sequence should be treated as a product development path, not as a single large software release. The first release should prove the governed scheduling spine and operating-window logic. Later releases should progressively add simulation, live evidence, trusted field events, recovery guidance and management review surfaces.

This approach allows ABL and Berau to validate the operating rules early while keeping later integrations and advanced decision-support features under controlled scope.

---

## 6. Working Details

### 6.1 Clean planning flow

```text
Import OGV demand
-> Review cargo grade and layer sequence
-> Enter operating windows
-> Generate movement candidates
-> Generate draft plan
-> Review conflicts
-> Submit approval
-> Complete Berau / ABL approvals
-> Run publishability check
-> Manually publish
-> Generate governed export
```

The clean flow proves that the system can move from demand to execution contract using structured route, resource and window data.

### 6.2 Disruption and recovery flow

```text
Open active exception
-> Generate recovery options
-> Review ranked candidates
-> Validate whether the option resolves the operating cause
-> Create scenario from selected option
-> Run simulation
-> Promote feasible scenario
-> Repair remaining blockers if required
-> Submit approval
-> Complete approvals
-> Run publishability check
-> Manually publish recovery plan
```

This flow keeps recovery advisory until it has passed simulation, approval and publishability gates.

### 6.3 Capacity placement logic

At planning time, the platform should:

1. load current demand and master data;
2. plot current work and already occupied capacity;
3. identify eligible resources for each movement;
4. generate candidate paths;
5. search for continuous feasible windows;
6. mark selected windows as occupied;
7. record conflicts where no feasible placement exists;
8. preserve all reason codes and audit lineage.

This is the working logic that converts operational planning into a repeatable product workflow.

### 6.4 Live evidence and actualization

The live evidence flow is:

```text
GPS/AIS or synthetic position evidence
-> Normalize asset identity
-> Store raw evidence
-> Derive latest state, geofence and ETA variance
-> Raise alert where required
-> Use alert as scenario input when replanning is needed
```

The trusted actualization flow is:

```text
Device/operator/event candidate
-> Match to planned trip or schedule event
-> Apply confidence, trust and dedupe rules
-> Confirm or reject
-> Update actual event only after confirmation
-> Create exception if variance requires action
-> Record audit trail
```

The system deliberately separates planned, observed, confirmed, projected and recommended state.

---

## 7. Application Modules

| Module | Working responsibility |
|---|---|
| Organizations and RBAC | Multi-party users, roles, permissions, data scope and approval authority |
| Master data | Locations, coal grades, mines, stockpiles, jetties, tug/barge/CTS assets, routes, loading rates and compatibility |
| Planning | OGV voyages, cargo requirements, cargo layer sequence, availability windows, tide windows, bridge windows and import jobs |
| Scheduling | Plan, plan version, trip, assignment, schedule event, conflict, override, approval, publish, export and simulation |
| Telemetry | Source registry, asset mapping, position evidence, geofence zones, latest state, ETA projection and tracking alerts |
| Operations | Integration feeds, device endpoints, health snapshots, event candidates, confirmed events and actualization |
| Assistant and flows | Next Action registry, flow runtime, operator guidance, action enablement and flow evidence |
| Audit | Request and domain audit trail for governed actions |
| Operator cockpit | Dense operational cockpit covering demand, cargo sequence, assignments, jetty, CTS, tide/bridge, exceptions, simulation, approvals, published plan, map, recovery, audit and admin |

---

## 8. Assumptions Made To Determine The Flow

1. Berau can provide OGV demand, laycan, cargo quantity, coal grade and layer sequence in a consistent file or integration-ready format.
2. ABL and Berau will agree master-data naming for jetties, routes, assets, grades, locations and operating zones.
3. Tide and bridge windows can initially be entered manually or uploaded before live sensor integration is available.
4. Resource capacity must include both time availability and operational eligibility.
5. Active work in progress must be plotted before new schedules or recovery options are generated.
6. GPS/AIS or Spinergie-style fleet data is evidence and does not directly change schedule authority.
7. Field events such as loading start, loading completion, bridge crossing, tide gate pass and CTS discharge require confirmation before actualization.
8. Published plans are immutable; replanning creates successor versions.
9. Approval requires Berau and ABL authority before publication.
10. Manual override requires reason capture and audit.
11. Recovery recommendations do not bypass simulation, approval or manual publish.
12. External chartered assets require readiness and lead-time assumptions.
13. Commercial exposure can be projected for planning awareness, but final demurrage, despatch, invoicing and settlement remain separately scoped.
14. Synthetic seed and replay data are valid for blueprint, prototype, UAT and integration-contract proof before production feeds are connected.

---

## 9. Recommended Technology Stack

The application can be implemented using the following practical stack. The final stack should be confirmed during the blueprinting and architecture validation stage.

| Layer | Technology |
|---|---|
| Operator web application | React, Vite, TypeScript |
| Web application testing | Vitest, Testing Library, jsdom |
| Web application linting | ESLint, TypeScript ESLint |
| API and business services | Django, Django REST Framework |
| Background jobs | Celery, Celery Beat |
| Application server | Gunicorn |
| Service testing | pytest, pytest-django |
| Service linting | Ruff |
| Database | PostgreSQL with PostGIS |
| Cache / broker | Redis |
| Object storage | MinIO / S3-compatible storage |
| Edge routing | Nginx |
| Runtime approach | Containerized deployment model |
| Development helpers | Mailpit, Flower |

Deferred integration technology may include MQTT, HTTP callbacks, AIS/NMEA feeds, Kafka/Redpanda, TimescaleDB or ClickHouse, OPC-UA or Modbus, and live UI push updates.

---

## 10. External Data Sources Assumed To Be Available

| External data source | Assumed content | Initial handling | Later integration direction |
|---|---|---|---|
| Existing Excel schedule | Current OGV plan and operating schedule | Import or manual upload | Governed file ingestion or direct integration |
| OGV schedule | ETA, ETB, laycan, quantity, priority and vessel status | Manual/imported demand | API feed from Berau or shipping system |
| Cargo/source data | Mine, CPP, stockpile, grade, product, available quantity, quality release and jetty eligibility | Master data and demand setup | Cargo/quality or ERP integration |
| Cargo layer sequence | Hatch/layer order, grade requirement and substitution rule | Cargo layer model | Structured demand feed |
| Jetty/BLC data | Loading rate, queue, working hours, equipment status and readiness | Manual windows/status | Terminal, PLC or operator console |
| ABL fleet data | Tug, barge, CTS capacity, compatibility, status, location and availability | Master data and availability windows | Spinergie, GPS/AIS or fleet API |
| Tide data | Tide tables, height, safe movement windows and water-level observations | Manual tide windows | Sensor/API feed |
| Bridge data | Opening schedule, crossing rule and queue | Manual bridge windows | Bridge operator console or device feed |
| Weather/marine data | Rain, wind, wave, visibility and closure alerts | Exception input or planning note | Weather API or local station |
| GPS/AIS data | Position, speed, heading, timestamp, signal quality and external asset identity | Synthetic replay or vendor-shaped payload | Spinergie, AIS receiver, tracker or vendor API |
| Operational events | Loading start/end, discharge start/end, stoppage, breakdown and crossing confirmation | Synthetic feed and operator confirmation | MQTT, HTTP callback, PLC, weighbridge, tablet or edge gateway |
| Device health | Last seen, power, battery, network, firmware and signal gap | Device health snapshot | IoT/device-management integration |
| Survey and documents | Draft survey, sampling, certificates, SOF and final quantity/quality documents | Deferred milestone visibility | Document management or survey integration |
| Commercial parameters | Laycan risk, exposure proxy and customer-safe ETA projection | Projection-only review | Separate commercial sign-off |

---

## 11. Build Deliverables

| Deliverable | Description |
|---|---|
| Application foundation | Containerized web application, API service, database, Redis, object storage and routing layer |
| Master and capacity model | Assets, routes, eligibility, calendars, operating windows and compatibility |
| Scheduling engine | Movement entity generation, candidate paths, capacity placement and conflict detection |
| Scenario engine | What-if assumptions, run history, projected impacts and scenario promotion |
| Operational cockpit | Role-aware UI for demand, cargo sequence, assignments, jetty, CTS, tide/bridge, exceptions, simulation, approvals, published plan, map, recovery, audit and admin |
| Evidence ingestion layer | GPS/AIS-shaped telemetry and operational event candidate contracts |
| Trust and actualization layer | Confirmation, rejection, actual event updates and device/feed health |
| Recovery layer | Ranked recovery options, root-cause validation and proof pack |
| Governance layer | RBAC, dual approval, publishability, immutable snapshots and governed exports |
| Operator guidance layer | Flow runtime and Next Action guidance |
| Evidence and test pack | Service tests, web application tests, browser evidence, proof commands and runbooks |

---

## 12. Implementation Clarification

This extension does not replace the original blueprinting proposal. It defines what the later application build should contain if the blueprint and prototype are accepted.

Final implementation timeline, team size and commercials should be confirmed only after:

- ABL and Berau validate the operational rules;
- required external data sources are confirmed;
- integration owners and access methods are known;
- master-data ownership is agreed;
- pilot users and approval authorities are named;
- UAT scope and deployment environment are confirmed.

---

## 13. Important Build Boundaries

1. GPS/AIS is evidence, not automatic truth.
2. Raw pings do not update the execution plan directly.
3. Confirmed field events may update actual execution state.
4. Recovery options are advisory until simulated, approved and checked for publish readiness.
5. Published plans remain immutable.
6. Customer-facing visibility should come after internal governance is stable.
7. Commercial projection is not final settlement logic.
8. Synthetic proof data is acceptable for prototype and UAT, but production claims require real integration testing.
9. Planned, observed, confirmed, projected and recommended states must remain separate.

---

## 14. Suggested Proposal Positioning

> Following the Operational Blueprinting and Simulation Prototype engagement, Vector proposes to extend the validated blueprint into a governed Flow Management Control Tower application. The platform will treat each shipment movement as a schedulable flow entity, place it through eligible route steps and operating windows, validate capacity against cargo, resource, tide, bridge, CTS and OGV constraints, and preserve Berau-ABL approval authority through immutable published plans and audit-backed workflows.

---

## 15. Reference Inputs

This extension is based on:

- the Operational Blueprinting & Simulation Prototype Proposal;
- the Scheduling Simulation BRD;
- ABL and Berau Coal operating context;
- observed transshipment planning and fleet-coordination challenges;
- cargo, route, asset, tide, bridge, CTS and OGV scheduling logic;
- the shared scheduling principle that work must be placed through eligible route steps, available resources and continuous operating windows;
- the proposed phased product-development direction for the ABL flow-management platform.
