# Operational Blueprinting & Application Build Extension

**BERAU COAL TRANSSHIPMENT OPERATIONS**

_Dynamic Operational Synchronization & Scheduling Platform_

| Prepared for | ABL Group |
| --- | --- |
| Prepared by | PT Vector Management Consulting |
| Operating context | ABL - Berau Coal transshipment, port, barging, CTS and OGV loading operations |
| Document role | Product development extension to the Operational Blueprinting & Simulation Prototype Proposal |
| Date | 31-05-2026 |

> **Purpose:** This extension translates the validated operational blueprint into a client-facing application build plan, including Vector proprietary scheduling and scenario scaffolding, phased delivery blocks, operating-window logic, integration assumptions, operational readiness gates and governed deployment boundaries.

## Contents

1. Executive Summary
2. Business Use Case
3. Operating Flow Challenges
4. Core Scheduling Philosophy
5. Vector Proprietary Scheduling And Scenario Scaffolding
6. Product Development Layers
7. Phase Of Development In Sprint Level
8. Release 1 - Governed Scheduling Spine
9. Operational Readiness And Adoption Review
10. Exception Taxonomy And Operating Governance
11. Working Flow Details
12. Application Modules
13. Assumptions Made To Determine The Flow
14. Proposed Implementation Architecture
15. External Data Sources Assumed To Be Available
16. Build Deliverables
17. Implementation Clarification
18. Important Build Boundaries
19. Glossary
20. Reference Inputs

## 1. Executive Summary

The Operational Blueprinting and Simulation Prototype engagement establishes the operating logic, data assumptions, decision workflows and implementation priorities for the ABL - Berau Coal transshipment environment. This extension defines how that validated blueprint moves into the application build.

The proposed product is a Dynamic Operational Synchronization & Scheduling Platform. It will convert Berau shipment demand into an executable ABL logistics plan by coordinating cargo readiness, jetty loading, tug-barge movement, tide and bridge windows, CTS availability, OGV loading sequence, exception recovery, approval and publication.

The platform is not only a fleet-tracking screen, map view or digital Excel replacement. It is a governed scheduling and simulation application designed to place each shipment movement through eligible route steps, available operating windows and approved decision workflows.

Vector will use its proprietary scheduling, scenario and dynamic-constraint scaffolding as the base for the application build. The ABL-specific implementation will configure and extend this base around Berau demand, ABL assets, tide and bridge logic, port/CTS operations, operating exceptions, recovery workflows, approval governance and required integrations.

The build path begins by establishing the governed scheduling spine and operating-window logic. Subsequent delivery blocks extend the same product foundation into scenario simulation, live evidence, confirmed operational events, recovery guidance and management review surfaces.

## 2. Business Use Case

The business use case is:

> **Operating principle:** Synchronize Berau Coal's shipment commitments with ABL's real operational flow capacity so that cargo readiness, asset availability, tide/bridge windows, jetty/CTS capacity, OGV loading sequence and recovery decisions are planned and governed from one shared operating platform.

### 2.1 Business problems addressed

| Business problem | Application response |
| --- | --- |
| Static Excel planning cannot absorb daily and intra-day changes | Structured demand intake, versioned plan generation, conflict checks, approval and governed replanning |
| Shipment demand is not continuously synchronized with logistics capacity | OGV demand, cargo grade, route, tug-barge, jetty, CTS and operating-window capacity are held in one planning model |
| Tide, bridge and berth windows keep changing the feasible plan | Movement windows are treated as schedulable capacity |
| Coal grade and loading sequence affect execution | Cargo requirement and layer sequence are first-class planning inputs |
| Existing work in progress affects new planning | Active plans, sailing barges, loaded barges, queues and confirmed actuals are plotted before new planning decisions |
| Operating exceptions are currently handled through experience and manual coordination | Exception families, reason codes, manual override and recovery workflows are captured in the governed process |
| Asset position is visible but operational status may require confirmation | GPS/AIS evidence is separated from confirmed operational events and schedule authority |
| Approvals and operating decisions require traceability | Dual-party approvals, immutable published snapshots, audit events and governed exports |

### 2.2 First release objective

The first release establishes the governed scheduling spine. It provides the minimum complete operating product required to intake demand, represent cargo and capacity, evaluate operating windows, generate movement candidates, surface conflicts, capture overrides, obtain approval and publish the execution schedule.

At this stage, ABL receives a working scheduling application for the core ABL-Berau flow. The product creates an approved operating schedule and a governed plan lineage before later simulation, live-evidence and recovery layers are activated.

## 3. Operating Flow Challenges

The ABL-Berau transshipment flow is governed by constraints that move during the day. A shipment may start with cargo readiness as the controlling factor, then become constrained by jetty/BLC availability, tide timing, bridge crossing, tug-barge availability, CTS queue, OGV laycan pressure or approval timing.

The application therefore needs to place each movement through the operating chain, while continuously respecting current availability, operating windows and decision authority.

| Operating challenge | Scheduling implication |
| --- | --- |
| OGV demand, laycan or hatch/layer sequence changes | Demand must be revalidated against cargo, route, resource and downstream commitments |
| Cargo is ready but asset or route capacity is unavailable | Resource eligibility and availability must be checked before placement |
| Tug-barge movement timing interacts with tide and bridge windows | Movement chains must be placed within continuous feasible windows |
| Jetty/BLC loading affects downstream sailing and CTS discharge | Upstream delays must be visible before downstream commitments are published |
| CTS or floating equipment can become the bottleneck | Transshipment capacity must be represented as a schedulable constraint |
| Field status may be observed before it is operationally confirmed | Observed evidence must remain separate from confirmed schedule actuals |
| Practical exceptions require planner judgment | Manual decisions must be allowed, reason-coded and auditable |

## 4. Core Scheduling Philosophy

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

## 5. Vector Proprietary Scheduling And Scenario Scaffolding

Vector owns a proprietary base scaffolding for constraint-aware scheduling, scenario simulation and dynamic-capacity planning. This base will be used as the starting point for the ABL application build.

### 5.1 Capabilities provided by the base scaffolding

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

### 5.2 ABL-specific configuration and extension

The ABL build will configure this base around:

- Berau OGV demand, cargo quantity, coal grade and layer sequence
- ABL jetties, BLC loading capability, tug-barge fleet and CTS assets
- tide windows, bridge windows, river movement and route cycle times
- cargo readiness, stockpile/source eligibility and quality-release status
- active trip state, loaded barges, queues and confirmed operational events
- exception categories, recovery rules, approvals and publishability gates
- reporting, dashboard, audit and export requirements.

The proprietary base accelerates implementation while the blueprinting phase ensures that ABL-specific business rules, data interfaces and governance logic are validated before full deployment.

## 6. Product Development Layers

### 6.1 Layer 1 - Governed scheduling model

This layer creates the structured planning spine:

- OGV voyage and laycan intake
- cargo quantity, coal grade and loading sequence
- source, stockpile, jetty and route master data
- tug, barge and CTS availability
- tide and bridge calendars
- deterministic schedule generation
- conflict detection
- manual override with reason capture
- plan versioning
- approval, publish and audit.

### 6.2 Layer 2 - Operating readiness and exception governance

This layer organizes how the scheduling model is adopted into day-to-day planning:

- planner workflow validation
- demand completeness and master-data readiness
- conflict reason review
- override pattern review
- exception family definition
- approval latency review
- readiness review before activating later operating layers.

### 6.3 Layer 3 - Simulation and operational evidence

This layer adds scenario and live-state interpretation:

- delay, outage, window-change and reassignment assumptions
- projected trip, event, OGV completion and utilization impact
- GPS/AIS-style position evidence
- geofence, ETA variance and stale-signal alerts
- event candidates from device, operator or feed input
- trusted confirmation before schedule actualization.

### 6.4 Layer 4 - Recovery and guided execution

This layer adds guided decision support:

- recovery input snapshots from active plan, alerts, confirmed events and conflicts
- ranked recovery options
- root-cause validation
- scenario creation from selected recovery option
- publishability assessment
- guided operator workflow
- projection-only commercial and operating-impact review surfaces.

## 7. Phase Of Development In Sprint Level

| Sprint level | Build focus | Key outcome |
| --- | --- | --- |
| Sprint 0 | Application foundation: web application, API service, database, background processing, file storage and routing layer | Runnable product spine |
| Sprint 1 | Master data and governance: organizations, roles, audit, locations, cargo, jetties, routes, assets and compatibility | Safe multi-party operating model |
| Sprint 2 | Demand and capacity intake: OGV demand, cargo layer, asset windows, jetty windows, tide windows and bridge windows | Structured inputs for planning |
| Sprint 3 | Scheduling entity and route model: trips, assignments, schedule events and route-step dependencies | Movement chain represented as schedulable work |
| Sprint 4 | Capacity placement and feasibility: candidate paths, occupied/free windows, conflict checks and movement candidates | Feasible plan with explicit blockers |
| Sprint 5 | Plan governance: versions, overrides, approval requests, approval decisions, published snapshots and exports | Approved execution contract |
| Sprint 6 | Scenario simulation and exception review: assumptions, projected events, projected trips, constraint evaluations, exception families and utilization outputs | What-if planning and exception impact visibility |
| Sprint 7 | Live evidence: telemetry sources, asset identities, position pings, latest asset state, geofences and ETA variance | Planned-vs-observed movement visibility |
| Sprint 8 | Confirmed operations: integration feeds, devices, event candidates, confirmed events, actualization and device health | Trusted execution status layer |
| Sprint 9 | Recovery recommendations: input snapshots, ranked options, recovery actions and proof pack | Decision support for disrupted flow |
| Sprint 10 | Guided recovery and hardening: workflow guidance, root-cause validation, publishability, review surfaces and tests | Pilot-ready governed flow-management platform |

The first release will prove the governed scheduling spine and operating-window logic. Later releases will progressively add simulation, live evidence, trusted field events, recovery guidance and management review surfaces.

### 7.1 Client delivery blocks

| Delivery block | Sprint coverage | System screens delivered | Capability delivered | Product owned by ABL at this stage |
| --- | --- | --- | --- | --- |
| Release 1 - Governed scheduling spine | Sprint 0 to Sprint 5 | Login and role-based navigation, master data, OGV demand, cargo layer sequence, tide/bridge windows, tug-barge assignment, jetty loading, CTS operations, conflict review, override reason capture, approval, published plan, audit and export screens | Structured demand intake, master-data setup, operating-window entry, route/resource eligibility, candidate movement generation, feasibility checks, conflict output, plan versioning, dual approval, manual publish and governed export | A working governed scheduling application that replaces spreadsheet-only planning for the core ABL-Berau flow and creates an approved execution contract |
| Release 2 - Exception and scenario support | Sprint 6 | Exception review, scenario assumption entry, baseline-versus-scenario comparison, projected trip/event impact, constraint impact and utilization review screens | Exception family handling, what-if planning for delay/outage/window change/reassignment, projected downstream impact and scenario promotion into approval path | A planning simulation and exception review product that allows ABL to test disruption impact before changing the published plan |
| Release 3 - Live evidence and confirmed operations | Sprint 7 to Sprint 8 | Live resource map, asset signal detail, tracking alert list, operations event console, device/feed health, jetty/CTS actualization and exception linkage screens | GPS/AIS-style evidence ingestion, latest asset state, geofence/ETA variance, stale-signal alerts, event candidate capture, event confirmation, actual execution update and trusted exception creation | An execution-monitoring layer that connects the approved schedule with observed and confirmed field reality |
| Release 4 - Recovery guidance and flow-management hardening | Sprint 9 to Sprint 10 | Recovery recommendation console, ranked option detail, root-cause validation, publishability review, guided workflow panel, management review surfaces and hardened audit evidence screens | Ranked recovery options, recovery proof pack, guided next action, publishability validation, telemetry-trust review and projection-only operating/commercial visibility | A governed flow-management platform that supports disruption recovery from exception identification to approved recovery publication |

## 8. Release 1 - Governed Scheduling Spine

Release 1 establishes the governed scheduling spine and operating-window logic across Sprint 0 to Sprint 5. It creates the first complete product layer that ABL can use for structured planning, feasibility review, approval and publication.

### 8.1 Release 1 system screens

| Screen group | Release 1 coverage |
| --- | --- |
| Access and governance | Login, role-based navigation, organization, user, role and approval authority screens |
| Master data | Locations, cargo grades, sources, stockpiles, jetties, routes, tug/barge/CTS assets and compatibility |
| Demand and cargo | OGV demand intake, laycan, cargo quantity, coal grade and cargo layer sequence |
| Operating windows | Asset availability, jetty/BLC windows, tide windows, bridge windows and CTS capacity windows |
| Scheduling | Candidate movement generation, tug-barge assignment, schedule events, conflict output and draft plan review |
| Approval and publish | Override capture, approval request, approval decision, publishability check, published snapshot and export |
| Audit and evidence | Plan history, approvals, manual overrides, exports and audit events |

### 8.2 Release 1 capability delivered

Release 1 delivers:

- structured demand intake;
- master-data and resource setup;
- cargo layer and loading sequence representation;
- route and resource eligibility checks;
- operating-window entry and validation;
- candidate movement generation;
- explicit conflict and blocker output;
- reason-coded manual override;
- plan versioning;
- dual approval;
- published plan snapshot;
- governed export and audit trail.

### 8.3 Release 1 operating success measures

| Success measure | Validation direction |
| --- | --- |
| Publishable-plan cycle time | Time from demand intake to publishable plan becomes visible and measurable |
| Schedule rework | Repeated spreadsheet revisions and manual reconciliation are reduced |
| Conflict clarity | Hard blockers carry a reason code, affected movement and review action |
| Approval traceability | Published plans carry approval, version and audit lineage |
| Planner adoption | Named users can complete representative planning workflows with controlled override usage |
| Data readiness | Demand, master data and operating-window inputs meet agreed minimum completeness |

Specific numeric targets will be baselined with ABL and Berau during pilot use.

## 9. Operational Readiness And Adoption Review

The operational readiness review confirms that the governed scheduling spine is aligned with real planning behavior before subsequent product layers are activated.

The review will cover:

- planner usage across representative scheduling workflows;
- demand completeness and master-data stability;
- conflict accuracy and false-positive blockers;
- manual override frequency and reason-code quality;
- approval latency and escalation behavior;
- readiness of operating-window inputs;
- exception families that need formal workflow treatment;
- data and integration gaps to be resolved before live evidence or recovery automation.

The output of this review becomes the operating baseline for scenario simulation, exception support, live evidence, confirmed operations and recovery guidance.

## 10. Exception Taxonomy And Operating Governance

ABL transshipment execution requires a practical exception structure because disruptions can occur at multiple points in the flow. The application will treat exceptions as governed operating events, not only as informal planner notes.

### 10.1 Initial exception families

| Exception family | Initial examples | Application treatment |
| --- | --- | --- |
| Cargo/source readiness | Cargo not ready, quality hold, source switch, cargo layer mismatch | Readiness conflict, planning note or manual resolution |
| Jetty/BLC operations | Loading delay, queue, reduced loading rate, equipment stoppage | Capacity-window conflict or loading exception |
| Navigation constraint | Tide missed, bridge window missed, draft restriction change, crossing risk | Operating-window blocker |
| Fleet/asset availability | Tug unavailable, barge unavailable, incompatibility, breakdown, charter lead-time pressure | Resource availability or eligibility blocker |
| CTS/transshipment | CTS queue, floating crane downtime, discharge rate reduction | Downstream capacity blocker |
| OGV/laycan | OGV ETA change, hatch sequence change, laycan pressure, loading completion risk | Demand priority and completion-risk note |
| Weather/marine | Rain, wind, visibility, wave restriction, river condition | Exception note or window blocker |
| Survey/clearance | Draft survey delay, documentation hold, port clearance interruption | Closure, readiness or handover blocker |
| Human/governance | Approval delay, manual override, escalation, disputed decision | Workflow and audit event |
| Data/integration | Missing feed, stale signal, duplicate event, untrusted telemetry | Data quality warning |

### 10.2 Manual override and planner discretion

The application will preserve planner discretion where practical operating judgment is required. Manual overrides, negotiated exceptions and escalation decisions will remain possible, but they will be captured with reason code, user, timestamp, affected movement and approval lineage.

Repeated manual decisions can then be reviewed with ABL and Berau to decide whether they should become formal scheduling rules, exception categories or operator guidance.

## 11. Working Flow Details

### 11.1 Clean planning flow

```text
Import OGV demand
-> Review cargo grade and layer sequence
-> Enter operating windows
-> Generate movement candidates
-> Generate draft plan
-> Review conflicts
-> Apply reason-coded override if required
-> Submit approval
-> Complete Berau / ABL approvals
-> Run publishability check
-> Manually publish
-> Generate governed export
```

### 11.2 Disruption and recovery flow

```text
Open active exception
-> Review operating cause
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

### 11.3 Capacity placement logic

At planning time, the platform will:

1. load current demand and master data;
2. plot current work and already occupied capacity;
3. identify eligible resources for each movement;
4. generate candidate paths;
5. search for continuous feasible windows;
6. mark selected windows as occupied;
7. record conflicts where no feasible placement exists;
8. preserve reason codes and audit lineage.

### 11.4 Live evidence and actualization

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

### 11.5 Operating state separation

| State | Meaning |
| --- | --- |
| Planned | Approved schedule expectation |
| Observed | Field signal or external evidence that may indicate status |
| Confirmed | Operationally trusted event that updates actual execution status |
| Projected | Future impact estimated by the scheduling or scenario engine |
| Recommended | Candidate action for review, not an automatic publication |

## 12. Application Modules

| Module | Working responsibility |
| --- | --- |
| Organizations and access control | Multi-party users, roles, permissions, data scope and approval authority |
| Master data | Locations, coal grades, mines, stockpiles, jetties, tug/barge/CTS assets, routes, loading rates and compatibility |
| Planning | OGV voyages, cargo requirements, cargo layer sequence, availability windows, tide windows, bridge windows and import jobs |
| Scheduling | Plan, plan version, trip, assignment, schedule event, conflict, override, approval, publish, export and simulation |
| Exception management | Exception family, reason code, operating note, escalation path and recovery linkage |
| Telemetry | Source registry, asset mapping, position evidence, geofence zones, latest state, ETA projection and tracking alerts |
| Operations | Integration feeds, device endpoints, health snapshots, event candidates, confirmed events and actualization |
| Guided workflow | Operator guidance, action enablement and flow evidence |
| Audit | Request and domain audit trail for governed actions |
| Operator cockpit | Dense operational cockpit covering demand, cargo sequence, assignments, jetty, CTS, tide/bridge, exceptions, simulation, approvals, published plan, map, recovery, audit and admin |

## 13. Assumptions Made To Determine The Flow

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

## 14. Proposed Implementation Architecture

The implementation architecture provides the operating foundation behind the planner and approval workflows.

| Layer | Technology | Role in the application |
| --- | --- | --- |
| Operator web application | React, Vite, TypeScript | Browser-based screens for planners, approvers and operations users |
| Web application testing | Vitest, Testing Library, jsdom | UI behavior, screen logic and component interaction testing |
| API and business services | Django, Django REST Framework | Business APIs, workflow rules, access control and application services |
| Background jobs | Celery, Celery Beat | Imports, exports, scheduled checks and periodic processing |
| Application server | Gunicorn | Production application serving pattern |
| Service testing | pytest, pytest-django | Business services, data rules, API behavior and scheduling logic testing |
| Database | PostgreSQL with PostGIS | Operational data store with geospatial capability where required |
| Cache / broker | Redis | Fast shared state and message brokering for background jobs |
| Object storage | MinIO / S3-compatible storage | Imported files, exports, generated documents and object artifacts |
| Edge routing | Nginx | Web/API routing, reverse proxy and deployment hardening |
| Runtime approach | Containerized deployment model | Repeatable deployment units for local, UAT and production environments |

Deferred integration technology includes, where required by confirmed integration scope, MQTT, HTTP callbacks, AIS/NMEA feeds, Kafka/Redpanda, TimescaleDB or ClickHouse, OPC-UA or Modbus, and live UI push updates.

## 15. External Data Sources Assumed To Be Available

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
| Commercial parameters | Laycan risk, waiting-time proxy, queue impact, utilization and exposure proxy | Projection-only review | Separate commercial sign-off |

## 16. Build Deliverables

### 16.1 Release 1 deliverables

| Deliverable | Description |
| --- | --- |
| Vector scheduling base configuration | ABL-specific setup of proprietary scheduling and dynamic-constraint scaffolding |
| Application foundation | Containerized web application, API service, database, Redis, object storage and routing layer |
| Master and capacity model | Assets, routes, eligibility, calendars, operating windows and compatibility |
| Demand and cargo intake | OGV demand, laycan, cargo quantity, coal grade and cargo sequence |
| Scheduling configuration | Shipment movement entity, candidate paths, capacity placement, moving-window checks and conflict output |
| Operator screens | Role-aware screens for demand, master data, windows, assignments, conflicts, overrides, approvals, publish and export |
| Governance layer | Access control, dual approval, publishability, immutable snapshots and governed exports |
| Evidence and test pack | Service tests, web application tests, proof commands, UAT scripts and runbook |

### 16.2 Later release deliverables

| Deliverable | Description |
| --- | --- |
| Exception and scenario configuration | Exception families, what-if assumptions, projected impacts, utilization views and scenario comparison |
| Recovery support | Recovery input snapshot, ranked options, impact review and proof pack |
| Telemetry-assisted execution | GPS/AIS-shaped evidence, latest state, geofence/ETA variance and data trust review |
| Operations event layer | Event candidates, confirmations, rejection, actual event updates and device/feed health |
| Management review surfaces | Exception patterns, operating impact, projection-only indicators and maturity reporting |

### 16.3 Operating impact indicators

Where the required data is available, later release layers may expose projection-only operating indicators:

- laycan risk;
- waiting time;
- fleet utilization;
- queue impact;
- charter lead-time pressure;
- demurrage exposure proxy.

These indicators support planning and review. Final demurrage, despatch, invoicing and settlement remain separately scoped.

## 17. Implementation Clarification

This extension defines the application build direction that follows the blueprinting and prototype scope.

Final implementation timeline, team size and commercials will be confirmed after:

- ABL and Berau validate the operational rules
- required external data sources are confirmed
- integration owners and access methods are known
- master-data ownership is agreed
- pilot users and approval authorities are named
- UAT scope and deployment environment are confirmed
- licensing and usage terms for Vector proprietary scheduling and scenario scaffolding are finalized.

## 18. Important Build Boundaries

1. GPS/AIS is evidence, not automatic truth.
2. Raw pings do not update the execution plan directly.
3. Confirmed field events update actual execution state.
4. Recovery options are advisory until simulated, approved and checked for publish readiness.
5. Published plans remain immutable.
6. External visibility is governed through approved publication rules.
7. Commercial projection is not final settlement logic.
8. Synthetic proof data is acceptable for prototype and UAT, but production claims require real integration testing.
9. Planned, observed, confirmed, projected and recommended states remain separate.

## 19. Glossary

| Term | Definition |
| --- | --- |
| ABL | The operating organization responsible for transshipment logistics coordination in this proposal context. |
| AIS | Automatic Identification System, a marine tracking signal used to identify vessel location, heading, speed and related navigation information. |
| BLC | Barge Loading Conveyor or barge loading capability used at jetty/loading points for coal movement into barges. |
| Berau | Berau Coal, the shipment-demand context for the proposed ABL operating blueprint. |
| Bridge window | A permitted time range for a tug-barge movement to pass a bridge based on opening rules, navigation safety or operating coordination. |
| Candidate movement | A possible scheduled movement generated by the planning logic before it is accepted into a draft or published plan. |
| Cargo layer sequence | The required sequence in which coal grades or cargo layers are loaded into an OGV hold or hatch. |
| Constraint | A limiting factor that affects whether a movement can be planned, such as asset availability, tide timing, bridge opening, jetty capacity or cargo readiness. |
| CTS | Coal Transshipment Station or transshipment asset used for floating transfer/discharge operations between barges and ocean-going vessels. |
| Demurrage exposure proxy | A planning indicator that estimates potential commercial exposure due to waiting or delay. It is not final settlement logic. |
| Dynamic constraint | A constraint whose value or effect changes during operations, such as tide level, bridge availability, equipment status or asset position. |
| Feasibility check | A schedule validation step that confirms whether a movement can be placed within eligible resources and valid operating windows. |
| Geofence | A virtual geographic boundary used to detect whether an asset has entered, exited or remained within an operating zone. |
| Governed scheduling spine | The controlled planning workflow from demand intake through schedule generation, conflict review, approval, publish and export. |
| Jetty | The loading point where cargo is transferred to barges before movement toward CTS or OGV operations. |
| Laycan | The contractual or operating window within which an OGV is expected to be ready for loading. |
| Manual override | A planner action that allows a schedule decision to proceed despite a blocker or rule exception, with reason and audit capture. |
| MQTT | Message Queuing Telemetry Transport, a lightweight publish/subscribe protocol commonly used for IoT, device and event-message integration. |
| NMEA | National Marine Electronics Association data format family used by marine navigation equipment, often carrying GPS, AIS and vessel instrument data. |
| OGV | Ocean Going Vessel, the receiving vessel for the final coal-loading operation. |
| OPC-UA | Open Platform Communications Unified Architecture, an industrial communication standard used to exchange structured machine, equipment and process data. |
| Operating window | A time range within which an activity is permitted or feasible, such as tide movement, bridge crossing, jetty loading or CTS discharge. |
| Operator console | A local system, screen or control interface used by operational staff to enter, confirm or view equipment and process status. |
| PLC | Programmable Logic Controller, an industrial controller used to monitor and control equipment such as conveyors, loading systems and related plant operations. |
| Planned state | The approved schedule expectation before field execution changes are confirmed. |
| Publishability check | A final validation that a plan is ready to be released as an approved operating schedule. |
| Published plan | An approved, immutable schedule snapshot that becomes the operating reference until a successor version is approved. |
| Reason code | A standardized explanation attached to a conflict, exception or manual override. |
| Recovery option | A candidate corrective action proposed for review after an operational disruption. |
| Scenario | A what-if schedule view that tests assumptions before changing the published plan. |
| Tide window | A time range during which water level and navigation conditions allow a safe or permitted movement. |
| Tug-barge pair | A tug and barge combination considered together for movement eligibility, availability and compatibility. |
| UAT | User Acceptance Testing, the client-side validation stage for workflows, screens and outputs before production use. |

## 20. Reference Inputs

This extension is based on:

- the Operational Blueprinting & Simulation Prototype Proposal
- the Scheduling Simulation BRD
- ABL and Berau Coal operating context
- observed transshipment planning and fleet-coordination challenges
- cargo, route, asset, tide, bridge, CTS and OGV scheduling logic
- the shared scheduling principle that work must be placed through eligible route steps, available resources and continuous operating windows
- the product-development direction for the ABL flow-management platform.
