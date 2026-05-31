# ABL Operational Blueprinting Proposal - Application Build Extension

**Prepared for:** ABL Group  
**Operating context:** ABL - Berau Coal transshipment, port, barging, CTS and OGV loading operations  
**Document purpose:** Extension to the Operational Blueprinting & Simulation Prototype Proposal  
**Build reference:** Current Coalflow Tower working repository  
**Date:** 31 May 2026

---

## 1. Executive Summary

The original proposal establishes the need for Operational Diagnostic, Blueprinting, Simulation Prototype and Workflow Validation before entering full-scale implementation. This extension adds the application build interpretation based on the current working repository.

The application direction is a **Dynamic Operational Synchronization & Simulation Platform** for ABL and Berau Coal operations. The system is not positioned as a generic fleet tracking tool or a digital Excel replacement only. Its purpose is to synchronize Berau demand commitments with ABL's executable logistics flow capacity across cargo readiness, jetty loading, tug-barge movement, tide and bridge windows, CTS availability, OGV loading sequence, disruption handling, approval and publication.

The current repository already reflects this direction through a Dockerized application named **Coalflow Tower**. It contains the scheduling spine, simulation workflow, live tracking evidence layer, trusted operational event layer, recovery recommendation workflow, guided Next Action flow, publishability gate, audit and governed export surfaces.

The application build should therefore be proposed as a phased product implementation after blueprint validation, with each phase tied to operational proof, sprint-level delivery and explicit business assumptions.

---

## 2. Business Use Case

The core business use case is:

> Synchronize Berau Coal's shipment commitments with ABL's real operational flow capacity so that cargo, jetty, tug, barge, CTS, tide/bridge windows, OGV loading sequence and recovery decisions can be governed from one shared operating platform.

### 2.1 Business problems addressed

| Business problem | Application response |
|---|---|
| Static Excel planning cannot respond to daily and intra-day change | Structured demand intake, versioned plan generation, conflict checks and governed replanning |
| OGV schedule is not continuously synchronized with real ABL capacity | OGV demand, cargo grade sequence, tug-barge, jetty, CTS and constraint windows are held in one schedule model |
| Asset location is visible but business status is unclear | GPS/AIS evidence is separated from confirmed operational events and schedule authority |
| Tide, bridge and river windows create feasibility risk | Tide/bridge windows are modeled as hard operational constraints |
| Coal grade, blending and layering sequence affect execution | Cargo requirement and cargo layer sequence are first-class planning objects |
| Disruption recovery is manual and experience-driven | Scenario simulation and recovery recommendations show impact, candidate repair actions and approval path |
| Approvals and operating decisions require traceability | Dual-party approvals, immutable published snapshots, audit events and governed exports |
| Management needs bottleneck and risk visibility | Control tower, exception center, utilization, telemetry trust and projection-only commercial risk surfaces |

### 2.2 Primary user groups

| User group | Required use of the platform |
|---|---|
| ABL dispatch and planning team | Generate feasible schedules, manage exceptions, recover disrupted plans |
| Berau scheduling and commercial team | Validate whether OGV commitments, cargo quantity, grade and sequence can be met |
| Jetty and terminal operators | Confirm loading status, queue, grade readiness and actual milestones |
| CTS / floating-crane operators | Manage discharge queue, OGV assignment, operating rate and stoppage events |
| Joint control tower | Review cross-party risk, approvals, published plan and exception closure |
| Management | Review throughput risk, delays, utilization, bottlenecks and exposure projections |
| Customer or external viewers, later phase | Controlled shipment visibility after internal plan governance is stable |

---

## 3. Application Build Direction

The build should extend the blueprinting proposal in three layers.

### 3.1 Scheduling spine

The first layer is a governed digital scheduling model:

- OGV voyage and laycan intake;
- cargo quantity, coal grade and loading sequence;
- source, stockpile, jetty and route master data;
- tug, barge and CTS availability;
- tide and bridge windows;
- deterministic schedule generation;
- conflict detection;
- manual override with reason capture;
- plan versioning, approval, publication and audit.

This layer replaces brittle spreadsheet planning with structured operational truth.

### 3.2 Simulation and operational evidence

The second layer adds scenario planning and live evidence:

- delay, outage, window-change and reassignment scenarios;
- projected trip, event, OGV completion, demurrage-proxy and utilization impact;
- GPS/AIS-style position ingestion;
- latest asset state, geofence, ETA variance and stale-signal alerts;
- event candidates from device/operator/synthetic feeds;
- trusted confirmation before actualizing schedule events.

This layer lets the team understand disruption impact without corrupting the approved plan.

### 3.3 Decision support and governed recovery

The third layer adds recommendation and guided execution:

- recovery input snapshots from active plans, alerts, confirmed events and conflicts;
- deterministic repair recommendations;
- root-cause validation;
- scenario materialization from recommendation;
- publishability assessment;
- Next Action guidance for operators;
- read-only review surfaces for global optimization, telemetry trust and commercial projection.

This layer improves recovery speed while preserving Berau and ABL approval authority.

---

## 4. Phase Of Development In Sprint Level

The current repository indicates a product roadmap that has been reverse-planned into product phases and build chunks. For proposal purposes, the build can be presented as the following sprint-level application plan.

| Sprint level | Product phase | Main build focus | Key outcome |
|---:|---|---|---|
| Sprint 0 | Repository and architecture foundation | Docker Compose, backend, frontend, database, Redis, object storage, proxy and seed discipline | A runnable application spine |
| Sprint 1 | Governance and master data | Organizations, RBAC, audit, locations, coal grades, mines, stockpiles, jetties, tugs, barges, CTS, routes | Safe multi-organization setup |
| Sprint 2 | Demand and constraint intake | OGV demand, cargo requirement, cargo layer sequence, asset windows, jetty windows, tide windows, bridge windows | Structured inputs replacing Excel logic |
| Sprint 3 | Schedule generation and feasibility | Trips, assignments, schedule events, conflict checks, movement candidates | Feasible plan with explicit blockers |
| Sprint 4 | Approval, publish and export | Plan versions, approval request, approval decisions, published snapshots, governed exports | Approved execution contract |
| Sprint 5 | Scenario simulation | Scenario assumptions, scenario runs, event/trip projections, constraint evaluations, OGV and utilization projections | What-if planning without baseline mutation |
| Sprint 6 | GPS/AIS live evidence | Telemetry sources, asset identities, position pings, latest asset state, geofences, ETA projections, tracking alerts | Planned-vs-observed movement visibility |
| Sprint 7 | IoT and confirmed operations | Integration feeds, devices, event candidates, confirmed operational events, actualization, device health, edge replay | Trusted field event layer |
| Sprint 8 | Recovery recommendations | Recovery snapshots, optimizer runs, ranked recommendations, recovery actions, proof packs | Decision support for disrupted operations |
| Sprint 9 | Guided recovery and publishability | Flow runtime, Next Action guidance, root-cause validation, publishability gate | Operator-guided recovery to approved publish |
| Sprint 10 | Review surfaces and hardening | Global optimization scaffold, telemetry trust, projection-only commercial views, browser evidence, regression tests | Pilot-ready governed control tower |

### 4.1 Current repository maturity

The working repository reflects implementation through **Product Phase 6 / Phase 5+** with closure evidence recorded in the documentation set. The current build includes:

- clean operator happy-path flow;
- Phase 5+ recovery path;
- negative publishability proof for failed root-cause repair;
- global optimizer review surface;
- telemetry trust review;
- customer-safe commercial projection view;
- backend and frontend test evidence for the above.

This does not mean production integration with every external system is complete. It means the application architecture, user flow, governance model and deterministic proof paths are already represented in the codebase.

---

## 5. Working Details

### 5.1 Clean planning flow

The clean planning flow is:

```text
Import OGV demand
-> Review coal grade and layer sequence
-> Enter operating windows
-> Generate movement assignment candidates
-> Generate draft plan
-> Submit approval
-> Complete Berau / ABL approvals
-> Run publishability check
-> Manually publish
-> Generate governed export
```

This flow proves that the application can move from demand to execution contract without relying on live telemetry.

### 5.2 Disruption and recovery flow

The disruption flow is:

```text
Open active exception
-> Generate recovery options
-> Review ranked recommendations
-> Validate whether selected option addresses root cause
-> Materialize recommendation as scenario
-> Run scenario simulation
-> Promote feasible scenario
-> Repair remaining conflicts where required
-> Submit approval
-> Complete approvals
-> Run publishability check
-> Manually publish recovery plan
```

This flow preserves the original operating principle: recommendations are advisory until they pass simulation, approval and publishability gates.

### 5.3 Telemetry and operational event flow

The live evidence flow is:

```text
GPS/AIS or synthetic position ping
-> Normalize asset identity
-> Store raw ping
-> Derive latest asset state and geofence event
-> Compare against planned schedule
-> Raise delay or stale-signal alert
-> Convert alert to scenario source where required
```

The trusted event flow is:

```text
Device/operator/synthetic event candidate
-> Match to planned trip or schedule event
-> Apply trust and dedupe rules
-> Confirm or reject
-> Actualize schedule event only after confirmation
-> Create exception if variance requires recovery
-> Record audit trail
```

The system deliberately separates observed data from confirmed operational truth.

### 5.4 Application module details

| Module | Working responsibility |
|---|---|
| Organizations and RBAC | Multi-party users, roles, permissions, data scope and approval authority |
| Master data | Locations, coal grades, mines, stockpiles, jetties, tug/barge/CTS assets, routes, loading rates and compatibility |
| Planning | OGV voyages, cargo requirements, cargo layers, availability windows, tide/bridge windows and import jobs |
| Scheduling | Plan, plan version, trip, assignment, schedule event, conflict, override, approval, publish, export and simulation |
| Telemetry | Source registry, asset mapping, position pings, geofence zones, latest state, ETA projection and tracking alerts |
| Operations | Integration feeds, device endpoints, health snapshots, event candidates, confirmed events and actualization |
| Assistant and flows | Next Action registry, flow runtime, operator guidance, action enablement and flow evidence |
| Audit | Request and domain audit trail for governed actions |
| Frontend | Dense operational cockpit with dashboard, OGV demand, coal sequence, assignment, jetty, CTS, tide/bridge, exception, simulation, approval, published plan, map, recovery, audit and admin pages |

---

## 6. Assumptions Made To Determine The Flow

The application flow is based on the following assumptions.

1. Berau provides OGV demand, laycan, cargo quantity, coal grade and layer sequence in a consistent spreadsheet or integration-ready format.
2. ABL and Berau agree the master-data vocabulary for jetties, routes, tugs, barges, CTS assets, coal grades, source locations and operating zones.
3. Tide and bridge windows can initially be entered manually or uploaded, even before live sensor integration is available.
4. GPS/AIS or Spinergie-style fleet data is available as evidence, but not treated as direct authority to change the schedule.
5. Field events such as loading start, loading completion, bridge crossing, tide gate pass and CTS discharge require confirmation rules before actualizing the plan.
6. A published plan must remain immutable. Replanning creates a successor version.
7. Approval requires at least Berau and ABL authority before publication.
8. Manual override is valid only with reason capture and audit.
9. Recovery recommendations do not bypass simulation, approval or manual publish.
10. External chartered assets are not instantly available and must carry readiness or lead-time assumptions.
11. Commercial exposure can be projected for planning awareness, but final demurrage, despatch, invoicing and settlement remain outside the scheduling platform unless separately scoped.
12. Synthetic seed and replay data are valid for blueprint, prototype, UAT and integration-contract proof before production feeds are connected.

---

## 7. Technology Stack Being Used

The current working repository uses the following stack.

### 7.1 Frontend

| Component | Technology |
|---|---|
| Application framework | React |
| Build tool | Vite |
| Language | TypeScript |
| Testing | Vitest, Testing Library, jsdom |
| Linting | ESLint and TypeScript ESLint |
| UI pattern | Dense dark operational cockpit, sidebar navigation, right decision rails, audit/status strips and role-aware actions |

### 7.2 Backend

| Component | Technology |
|---|---|
| Web framework | Django |
| API framework | Django REST Framework |
| Background processing | Celery and Celery Beat |
| Application server | Gunicorn |
| Testing | pytest and pytest-django |
| Linting | Ruff |
| Authentication approach | Django session authentication for the current application |

### 7.3 Platform and infrastructure

| Component | Technology |
|---|---|
| Database | PostgreSQL with PostGIS |
| Cache / broker | Redis |
| Object storage | MinIO / S3-compatible storage |
| Edge routing | Nginx |
| Runtime | Docker Compose first |
| Development helpers | Mailpit and Flower |
| Export persistence | Docker volume-backed export storage plus object-storage metadata |

### 7.4 Deferred or future integration technology

The repository deliberately keeps room for:

- MQTT broker for IoT/device events;
- HTTP/REST callbacks for vendor systems;
- TCP/NMEA ingestion for AIS receiver data;
- Kafka/Redpanda for higher-volume event streaming;
- TimescaleDB or ClickHouse for high-volume telemetry history;
- OPC-UA or Modbus for industrial/PLC integration;
- WebSocket or push updates for live UI refresh.

These are not required to prove the current governed planning and simulation flows.

---

## 8. External Data Sources Assumed To Be Available

| External data source | Assumed content | Initial handling | Later integration direction |
|---|---|---|---|
| Existing Excel schedule | Current OGV plan, shipment schedule and operational planning baseline | Import or manual upload | Direct integration or governed file ingestion |
| OGV scheduling feed | ETA, ETB, laycan, cargo quantity, customer priority and vessel status | Manual/imported demand | API feed from Berau or shipping system |
| Berau cargo/source data | Mine, CPP, stockpile, grade, product, available quantity, quality release and jetty eligibility | Master-data and demand setup | Integration with cargo/quality or ERP source |
| Coal grade and layer sequence | Hatch/layer order, grade requirement, substitution rules | Cargo requirement and layer-step model | Structured demand feed |
| Jetty/BLC data | Loading rate, queue, working hours, equipment status, loading readiness | Manual windows and status updates | PLC, operator terminal or terminal system |
| ABL fleet data | Tug, barge, CTS capacity, compatibility, status, location and availability | Master data and availability windows | Spinergie, GPS/AIS, fleet-management API |
| Tide data | Tide tables, height, safe movement windows and water-level observations | Manual tide windows | Sensor/API feed |
| Bridge data | Bridge opening schedule, crossing rule and queue | Manual bridge windows | Bridge operator console or device feed |
| Weather and marine condition | Rain, wind, wave, visibility and safety closure alerts | Exception input or planning note | Weather API or local station integration |
| GPS/AIS data | Position, speed, heading, timestamp, signal quality and external asset identity | Synthetic replay or vendor-shaped payload | Spinergie, AIS receiver, GPS tracker or vendor API |
| Operational event feeds | Loading start/end, discharge start/end, stoppage, breakdown, crossing confirmation | Synthetic event feed and operator confirmation | MQTT, HTTP callbacks, PLC, weighbridge, tablet or edge gateway |
| Device health feeds | Last seen, power, battery, network, firmware, signal gap | Synthetic/device health snapshot | Device-management or IoT platform |
| Survey and documents | Draft survey, sampling, certificates, SOF, final quantity and quality documents | Deferred document milestone visibility | Document management or survey integration |
| Commercial parameters | Laycan risk, demurrage exposure proxy and customer-safe ETA projection | Projection-only review surface | Separate commercial sign-off and settlement integration |

---

## 9. Build Deliverables

The application build should be scoped into deliverables that correspond to operational value, not only technical milestones.

| Deliverable | Description |
|---|---|
| Application foundation | Dockerized frontend, backend, database, Redis, object storage and proxy |
| Domain model and APIs | Planning, scheduling, telemetry, operations, recovery, approval, audit and flow APIs |
| Operational cockpit | Role-aware UI for dashboard, demand, coal sequence, assignments, jetty, CTS, tide/bridge, exceptions, simulation, approvals, published plan, map, audit and admin |
| Scheduling engine | Deterministic feasible-plan generation and conflict detection |
| Scenario engine | What-if assumptions, run history, projected impacts and scenario promotion |
| Evidence ingestion layer | GPS/AIS-shaped telemetry and event-candidate ingestion contracts |
| Event trust layer | Confirmation, rejection, actualization and device/feed health logic |
| Recovery recommendation layer | Ranked deterministic recovery options and proof pack |
| Governance layer | RBAC, dual approval, publishability, immutable snapshots and governed exports |
| Operator guidance layer | Flow runtime and Next Action guidance for clean planning and recovery paths |
| Evidence and test pack | Backend tests, frontend tests, browser evidence, proof commands and runbooks |

---

## 10. Implementation Clarification

This extension does not replace the original blueprinting proposal. The original proposal correctly states that final software architecture, full software development, integration development, testing, deployment, change management and user rollout should be proposed separately after blueprint and prototype validation.

This document defines what that later application build should contain if the blueprint and prototype are accepted.

The final implementation timeline, team size and commercials should still be confirmed only after:

- ABL and Berau validate the operational rules;
- required external data sources are confirmed;
- integration owners and access methods are known;
- master-data ownership is agreed;
- pilot users and approval authorities are named;
- UAT scope and deployment environment are confirmed.

---

## 11. Important Build Boundaries

The following boundaries should remain explicit in any implementation proposal.

1. GPS/AIS is evidence, not automatic truth.
2. Confirmed field events may update actual execution state; raw pings may not.
3. Recommendations are advisory and must pass scenario, approval and publishability gates.
4. Manual publish remains required unless ABL and Berau explicitly approve automation.
5. Customer-facing visibility should come only after internal published-plan governance is stable.
6. Commercial projection is not final demurrage, despatch, invoice or settlement logic.
7. Synthetic proof data is acceptable for prototype and UAT, but production claims require real integration testing.
8. The system must preserve separate planned, observed, confirmed, projected and recommended states.

---

## 12. Suggested Proposal Positioning

The application build can be positioned as follows:

> Following the Operational Blueprinting and Simulation Prototype engagement, Vector proposes to extend the validated blueprint into a governed Flow Management Control Tower application. The platform will convert Berau shipment demand into an executable ABL logistics plan, validate the plan against cargo, resource, tide, bridge and OGV constraints, support simulation-backed recovery, and preserve Berau-ABL approval authority through immutable published plans and audit-backed workflows.

---

## 13. Source Documents And Repository References

This extension is based on:

- `ABL_Operational_Blueprinting_Proposal_Final-ver1.docx`
- `BRD - Schedulling Simulation.docx`
- `docs/proposal/archive/ABL_Flow_Management_Transshipment_Scheduling_Proposal_Context.md`
- `docs/02_Planning_Tool_Scope.md`
- `docs/03_Data_Architecture_and_IoT_Scope.md`
- `docs/07_Frontend_Build_Handoff_and_Phasewise_Plan.md`
- `docs/08_Phase_1_Implementation_Spec.md`
- `docs/14_Phase_2_Implementation_Spec.md`
- `docs/17_Phase_3_Implementation_Spec.md`
- `docs/20_Phase_4_Implementation_Spec.md`
- `docs/23_Phase_5_Implementation_Spec.md`
- `docs/26_Phase_6_Phase_5_Plus_Implementation_Spec.md`
- `docs/27_Phase_6_Completion_Evidence.md`
- Current repository code under `backend/`, `frontend/`, `infra/` and `docker-compose.yml`
