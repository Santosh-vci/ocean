# Operational Blueprinting & Application Build Extension

**BERAU COAL TRANSSHIPMENT OPERATIONS**

_Dynamic Operational Synchronization & Scheduling Platform_

| Prepared for | ABL Group |
| --- | --- |
| Prepared by | PT Vector Management Consulting |
| Operating context | ABL - Berau Coal transshipment, port, barging, CTS and OGV loading operations |
| Document role | Product development extension to the Operational Blueprinting & Simulation Prototype Proposal |
| Date | 31-05-2026 |

> **Purpose:** This extension translates the validated operational blueprint into a client-facing application build plan, including Vector proprietary scheduling and scenario scaffolding, phased delivery blocks, operating-window logic, integration assumptions and governed deployment boundaries.

## Contents

1. Executive Summary
2. Business Use Case
3. Core Scheduling Philosophy
4. Vector Proprietary Scheduling And Scenario Scaffolding
5. Product Development Layers
6. Phase Of Development In Sprint Level
7. Working Flow Details
8. Application Modules
9. Assumptions Made To Determine The Flow
10. Proposed Implementation Architecture
11. External Data Sources Assumed To Be Available
12. Build Deliverables
13. Implementation Clarification
14. Important Build Boundaries
15. Reference Inputs

## 1. Executive Summary

The Operational Blueprinting and Simulation Prototype engagement establishes the operating logic, data assumptions, decision workflows and implementation priorities for the ABL - Berau Coal transshipment environment. This extension defines how that validated blueprint moves into the application build.

The proposed product is a Dynamic Operational Synchronization & Scheduling Platform. It will convert Berau shipment demand into an executable ABL logistics plan by coordinating cargo readiness, jetty loading, tug-barge movement, tide and bridge windows, CTS availability, OGV loading sequence, exception recovery, approval and publication.

The platform is not only a fleet-tracking screen, map view or digital Excel replacement. It is a governed scheduling and simulation application designed to place each shipment movement through eligible route steps, available operating windows and approved decision workflows.

Vector will use its proprietary scheduling, scenario and dynamic-constraint scaffolding as the base for the application build. The ABL-specific implementation will configure and extend this base around Berau demand, ABL assets, tide and bridge logic, port/CTS operations, recovery workflows, approval governance and required integrations.

## 2. Business Use Case

The business use case is:

> **Operating principle:** Synchronize Berau Coal's shipment commitments with ABL's real operational flow capacity so that cargo readiness, asset availability, tide/bridge windows, jetty/CTS capacity, OGV loading sequence and recovery decisions are planned and governed from one shared operating platform.

### 2.1 Business problems addressed

| Business problem | Application response |
| --- | --- |
| Static Excel planning cannot absorb daily and intra-day changes | Structured demand intake, versioned plan generation, conflict checks and governed replanning |
| Shipment demand is not continuously synchronized with logistics capacity | OGV demand, cargo grade, route, tug-barge, jetty, CTS and operating-window capacity are held in one planning model |
| Asset position is visible but operational status is unclear | GPS/AIS evidence is separated from confirmed operational events and schedule authority |
| Tide, bridge and berth windows keep changing the feasible plan | Movement windows are treated as schedulable capacity |
| Coal grade and loading sequence affect execution | Cargo requirement and layer sequence are first-class planning inputs |
| Existing work in progress affects new planning | Active plans, sailing barges, loaded barges, queues and confirmed actuals are plotted before new planning decisions |
| Disruption recovery is manual and experience-driven | Scenario simulation and recovery recommendations show options, impact and approval path |
| Approvals and operating decisions require traceability | Dual-party approvals, immutable published snapshots, audit events and governed exports |

## 3. Core Scheduling Philosophy

The scheduling logic is based on a flow principle:

> **Operating principle:** Each shipment movement is treated as a schedulable entity that must pass through a defined route of operational steps. Each step needs the right resource, enough available capacity and a valid operating window.

For ABL, the route is operational as well as physical:

```text
Cargo readiness
-> Jetty / BLC loading
-> Tug-barge departure
-> Tide / river movement
-> Bridge crossing
-> CTS / anchorage queue
-> CTS discharge
-> OGV hatch / layer completion
-> Survey / handover closure
```

The controlling constraint shifts during the day between tide, bridge, jetty, CTS, berth, tug-barge availability, cargo readiness and OGV laycan pressure. The application will therefore recalculate feasibility around moving operating windows and current execution state, not only around static planned dates.

## 4. Vector Proprietary Scheduling And Scenario Scaffolding

Vector owns a proprietary base scaffolding for constraint-aware scheduling, scenario simulation and dynamic-capacity planning. This base will be used as the starting point for the ABL application build.

### 4.1 Capabilities provided by the base scaffolding

| Capability | Role in ABL build |
| --- | --- |
| Scheduling entity model | Represents shipment movements, route steps, dependencies, priorities and target dates |
| Route and resource eligibility | Matches each movement with allowed jetties, routes, tug-barge pairs, CTS assets and operating steps |
| Capacity-window placement | Places movements into free operating windows and prevents invalid overlap |
| Current-state loading | Considers active work, occupied resources, queues and confirmed actuals before placing new work |
| Dynamic constraint evaluation | Rechecks feasibility when tide, bridge, berth, asset or cargo readiness changes |
| Scenario engine | Simulates delay, outage, window-change, reassignment and recovery assumptions |
| Candidate comparison | Evaluates alternate paths and recovery options against feasibility and impact |
| Exception and blocker output | Identifies the first operating blocker and the affected downstream commitments |

### 4.2 ABL-specific configuration and extension

The ABL build will configure this base around:

- Berau OGV demand, cargo quantity, coal grade and layer sequence
- ABL jetties, BLC loading capability, tug-barge fleet and CTS assets
- tide windows, bridge windows, river movement and route cycle times
- cargo readiness, stockpile/source eligibility and quality-release status
- active trip state, loaded barges, queues and confirmed operational events
- exception categories, recovery rules, approvals and publishability gates
- reporting, dashboard, audit and export requirements.

The proprietary base accelerates implementation while the blueprinting phase ensures that ABL-specific business rules, data interfaces and governance logic are validated before full deployment.

## 5. Product Development Layers

### 5.1 Layer 1 - Governed scheduling model

This layer creates the structured planning spine:

- OGV voyage and laycan intake
- cargo quantity, coal grade and loading sequence
- source, stockpile, jetty and route master data
- tug, barge and CTS availability
- tide and bridge calendars
- deterministic schedule generation
- conflict detection
- plan versioning
- approval, publish and audit.

### 5.2 Layer 2 - Simulation and operational evidence

This layer adds scenario and live-state interpretation:

- delay, outage, window-change and reassignment assumptions
- projected trip, event, OGV completion and utilization impact
- GPS/AIS-style position evidence
- geofence, ETA variance and stale-signal alerts
- event candidates from device, operator or feed input
- trusted confirmation before schedule actualization.

### 5.3 Layer 3 - Recovery and guided execution

This layer adds guided decision support:

- recovery input snapshots from active plan, alerts, confirmed events and conflicts
- ranked recovery options
- root-cause validation
- scenario creation from selected recovery option
- publishability assessment
- guided operator workflow
- projection-only commercial and telemetry-trust review surfaces.

## 6. Phase Of Development In Sprint Level

| Sprint level | Build focus | Key outcome |
| --- | --- | --- |
| Sprint 0 | Application foundation: web application, API service, database, background processing, file storage and routing layer | Runnable product spine |
| Sprint 1 | Master data and governance: organizations, roles, audit, locations, cargo, jetties, routes, assets and compatibility | Safe multi-party operating model |
| Sprint 2 | Demand and capacity intake: OGV demand, cargo layer, asset windows, jetty windows, tide windows and bridge windows | Structured inputs for planning |
| Sprint 3 | Scheduling entity and route model: trips, assignments, schedule events and route-step dependencies | Movement chain represented as schedulable work |
| Sprint 4 | Capacity placement and feasibility: candidate paths, occupied/free windows, conflict checks and movement candidates | Feasible plan with explicit blockers |
| Sprint 5 | Plan governance: versions, overrides, approval requests, approval decisions, published snapshots and exports | Approved execution contract |
| Sprint 6 | Scenario simulation: assumptions, projected events, projected trips, constraint evaluations and utilization outputs | What-if planning and impact visibility |
| Sprint 7 | Live evidence: telemetry sources, asset identities, position pings, latest asset state, geofences and ETA variance | Planned-vs-observed movement visibility |
| Sprint 8 | Confirmed operations: integration feeds, devices, event candidates, confirmed events, actualization and device health | Trusted execution status layer |
| Sprint 9 | Recovery recommendations: input snapshots, ranked options, recovery actions and proof pack | Decision support for disrupted flow |
| Sprint 10 | Guided recovery and hardening: workflow guidance, root-cause validation, publishability, review surfaces and tests | Pilot-ready governed control tower |

The first release will prove the governed scheduling spine and operating-window logic. Later releases will progressively add simulation, live evidence, trusted field events, recovery guidance and management review surfaces.

### 6.1 Client Delivery Blocks

| Delivery block | Sprint coverage | System screens delivered | Capability delivered | Product owned by ABL at this stage |
|---|---|---|---|---|
| Release 1 - Governed scheduling spine | Sprint 0 to Sprint 5 | Login and role-based navigation, master data, OGV demand, cargo layer sequence, tide/bridge windows, tug-barge assignment, jetty loading, CTS operations, conflict review, approval, published plan, audit and export screens | Structured demand intake, master-data setup, operating-window entry, route/resource eligibility, candidate movement generation, feasibility checks, conflict output, plan versioning, dual approval, manual publish and governed export | A working governed scheduling application that replaces spreadsheet-only planning for the core ABL-Berau flow and creates an approved execution contract |
| Release 2 - Scenario and impact simulation | Sprint 6 | Simulation workspace, scenario assumption entry, baseline-versus-scenario comparison, projected trip/event impact, constraint impact and utilization review screens | What-if planning for delay, outage, window change and reassignment; projected downstream impact; scenario promotion into governed approval path | A planning simulation product that allows ABL to test disruption impact before changing the published plan |
| Release 3 - Live evidence and confirmed operations | Sprint 7 to Sprint 8 | Live resource map, asset signal detail, tracking alert list, operations event console, device/feed health, jetty/CTS actualization and exception linkage screens | GPS/AIS-style evidence ingestion, latest asset state, geofence/ETA variance, stale-signal alerts, event candidate capture, event confirmation, actual execution update and trusted exception creation | An execution-monitoring layer that connects the approved schedule with observed and confirmed field reality |
| Release 4 - Recovery guidance and control tower hardening | Sprint 9 to Sprint 10 | Recovery recommendation console, ranked option detail, root-cause validation, publishability review, guided workflow panel, management review surfaces and hardened audit evidence screens | Ranked recovery options, recovery proof pack, guided next action, publishability validation, telemetry-trust review and projection-only commercial visibility | A governed flow-management control tower that supports disruption recovery from exception identification to approved recovery publication |

## 7. Working Flow Details

### 7.1 Clean planning flow

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

### 7.2 Disruption and recovery flow

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

### 7.3 Capacity placement logic

At planning time, the platform will:

1. load current demand and master data;
2. plot current work and already occupied capacity;
3. identify eligible resources for each movement;
4. generate candidate paths;
5. search for continuous feasible windows;
6. mark selected windows as occupied;
7. record conflicts where no feasible placement exists;
8. preserve reason codes and audit lineage.

### 7.4 Live evidence and actualization

```text
GPS/AIS or synthetic position evidence
-> Normalize asset identity
-> Store raw evidence
-> Derive latest state, geofence and ETA variance
-> Raise alert where required
-> Use alert as scenario input when replanning is needed
```
```text
Device/operator/event candidate
-> Match to planned trip or schedule event
-> Apply confidence, trust and dedupe rules
-> Confirm or reject
-> Update actual event only after confirmation
-> Create exception if variance requires action
-> Record audit trail
```

## 8. Application Modules

| Module | Working responsibility |
| --- | --- |
| Organizations and access control | Multi-party users, roles, permissions, data scope and approval authority |
| Master data | Locations, coal grades, mines, stockpiles, jetties, tug/barge/CTS assets, routes, loading rates and compatibility |
| Planning | OGV voyages, cargo requirements, cargo layer sequence, availability windows, tide windows, bridge windows and import jobs |
| Scheduling | Plan, plan version, trip, assignment, schedule event, conflict, override, approval, publish, export and simulation |
| Telemetry | Source registry, asset mapping, position evidence, geofence zones, latest state, ETA projection and tracking alerts |
| Operations | Integration feeds, device endpoints, health snapshots, event candidates, confirmed events and actualization |
| Guided workflow | Operator guidance, action enablement and flow evidence |
| Audit | Request and domain audit trail for governed actions |
| Operator cockpit | Dense operational cockpit covering demand, cargo sequence, assignments, jetty, CTS, tide/bridge, exceptions, simulation, approvals, published plan, map, recovery, audit and admin |

## 9. Assumptions Made To Determine The Flow

1. Berau provides OGV demand, laycan, cargo quantity, coal grade and layer sequence in a consistent file or integration-ready format.
2. ABL and Berau will agree master-data naming for jetties, routes, assets, grades, locations and operating zones.
3. Tide and bridge windows are initially entered manually or uploaded before live sensor integration is available.
4. Resource capacity includes both time availability and operational eligibility.
5. Active work in progress is plotted before new schedules or recovery options are generated.
6. GPS/AIS or Spinergie-style fleet data is evidence and does not directly change schedule authority.
7. Field events such as loading start, loading completion, bridge crossing, tide gate pass and CTS discharge require confirmation before actualization.
8. Published plans are immutable; replanning creates successor versions.
9. Approval requires Berau and ABL authority before publication.
10. Manual override requires reason capture and audit.
11. Recovery recommendations do not bypass simulation, approval or manual publish.
12. External chartered assets require readiness and lead-time assumptions.
13. Commercial exposure is limited to planning projection, while final demurrage, despatch, invoicing and settlement remain separately scoped.
14. Synthetic seed and replay data are valid for blueprint, prototype, UAT and integration-contract proof before production feeds are connected.

## 10. Proposed Implementation Architecture

| Layer | Technology |
| --- | --- |
| Operator web application | React, Vite, TypeScript |
| Web application testing | Vitest, Testing Library, jsdom |
| API and business services | Django, Django REST Framework |
| Background jobs | Celery, Celery Beat |
| Application server | Gunicorn |
| Service testing | pytest, pytest-django |
| Database | PostgreSQL with PostGIS |
| Cache / broker | Redis |
| Object storage | MinIO / S3-compatible storage |
| Edge routing | Nginx |
| Runtime approach | Containerized deployment model |

Deferred integration technology includes, where required by confirmed integration scope, MQTT, HTTP callbacks, AIS/NMEA feeds, Kafka/Redpanda, TimescaleDB or ClickHouse, OPC-UA or Modbus, and live UI push updates.

## 11. External Data Sources Assumed To Be Available

| External data source | Assumed content | Initial handling | Later integration direction |
| --- | --- | --- | --- |
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

## 12. Build Deliverables

| Deliverable | Description |
| --- | --- |
| Vector scheduling and scenario base scaffolding | Proprietary scheduling, scenario and dynamic-constraint foundation owned by Vector and adapted for ABL operations |
| Application foundation | Containerized web application, API service, database, Redis, object storage and routing layer |
| Master and capacity model | Assets, routes, eligibility, calendars, operating windows and compatibility |
| ABL scheduling configuration | Shipment movement entity, candidate paths, capacity placement, moving-window checks and conflict output |
| Scenario and recovery configuration | What-if assumptions, projected impacts, ranked recovery options and proof pack |
| Operational cockpit | Role-aware UI for demand, cargo sequence, assignments, jetty, CTS, tide/bridge, exceptions, simulation, approvals, published plan, map, recovery, audit and admin |
| Evidence ingestion layer | GPS/AIS-shaped telemetry and operational event candidate contracts |
| Trust and actualization layer | Confirmation, rejection, actual event updates and device/feed health |
| Governance layer | Access control, dual approval, publishability, immutable snapshots and governed exports |
| Operator guidance layer | Guided workflow and next-action support |
| Evidence and test pack | Service tests, web application tests, browser evidence, proof commands and runbooks |

## 13. Implementation Clarification

This extension defines the application build direction that follows the blueprinting and prototype scope.

Final implementation timeline, team size and commercials will be confirmed after:

- ABL and Berau validate the operational rules
- required external data sources are confirmed
- integration owners and access methods are known
- master-data ownership is agreed
- pilot users and approval authorities are named
- UAT scope and deployment environment are confirmed
- licensing and usage terms for Vector proprietary scheduling and scenario scaffolding are finalized.

## 14. Important Build Boundaries

1. GPS/AIS is evidence, not automatic truth.
2. Raw pings do not update the execution plan directly.
3. Confirmed field events update actual execution state.
4. Recovery options are advisory until simulated, approved and checked for publish readiness.
5. Published plans remain immutable.
6. Customer-facing visibility comes after internal governance is stable.
7. Commercial projection is not final settlement logic.
8. Synthetic proof data is acceptable for prototype and UAT, but production claims require real integration testing.
9. Planned, observed, confirmed, projected and recommended states remain separate.

## 15. Reference Inputs

This extension is based on:

- the Operational Blueprinting & Simulation Prototype Proposal
- the Scheduling Simulation BRD
- ABL and Berau Coal operating context
- observed transshipment planning and fleet-coordination challenges
- cargo, route, asset, tide, bridge, CTS and OGV scheduling logic
- the shared scheduling principle that work must be placed through eligible route steps, available resources and continuous operating windows
- the product-development direction for the ABL flow-management platform.
