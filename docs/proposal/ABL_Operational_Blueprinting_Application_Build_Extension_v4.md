# ABL Operational Blueprinting Application Build Extension v4

**BERAU COAL TRANSSHIPMENT OPERATIONS**

_Constraint-Governed Operational Scheduling Platform_

| Prepared for | ABL Group |
| --- | --- |
| Prepared by | PT Vector Management Consulting |
| Operating context | ABL - Berau Coal transshipment, port, barging, CTS and OGV loading operations |
| Document role | Application build extension to the Operational Blueprinting & Simulation Prototype Proposal |
| Date | 31-05-2026 |

> **Purpose:** This extension defines how the operational blueprint will be translated into a client-facing application build. It frames the first release around governed scheduling and operating-window logic, while positioning scenario, telemetry, recovery and broader flow-management capabilities as phase-gated maturity blocks.

## Contents

1. Executive Summary
2. Business Use Case And First-Release Objective
3. Client Flow Challenges
4. Scheduling-First Operating Philosophy
5. Vector Proprietary Scheduling And Scenario Scaffolding
6. Product Scope: Phase-Gated Build Model
7. Release 1 - Governed Scheduling MVP
8. Operational Adoption Gate
9. Exception Taxonomy And Human Operating Reality
10. Later Maturity Blocks
11. Working Flow Details
12. Application Modules
13. Proposed Implementation Architecture
14. Data Sources And Integration Readiness
15. Build Deliverables
16. Assumptions, Readiness Gates And Boundaries
17. Glossary
18. Reference Inputs

## 1. Executive Summary

This extension defines the application build direction for the ABL - Berau Coal operational blueprint. The proposed product is a **Constraint-Governed Operational Scheduling Platform** that converts shipment demand into a controlled, publishable logistics plan across cargo readiness, jetty/BLC loading, tug-barge movement, tide and bridge windows, CTS operations, OGV loading sequence, approval and plan publication.

The first release is deliberately focused. It will prove the governed scheduling spine and operating-window logic between Sprint 0 and Sprint 5. At this stage, the client receives a working scheduling application that replaces spreadsheet-only planning for the core ABL-Berau flow and creates an approved execution contract.

Vector will use its proprietary scheduling, scenario and dynamic-constraint scaffolding as the implementation base. The ABL-specific application will configure this base around Berau demand, ABL resources, operating windows, route eligibility, conflict handling, approvals and publishable schedule output.

Later capabilities such as exception recovery, scenario impact simulation, telemetry-assisted execution, confirmed field events and broader flow-management review will be introduced only after adoption, data readiness and governance behavior are validated.

## 2. Business Use Case And First-Release Objective

The business use case is:

> **Operating principle:** Synchronize Berau Coal shipment commitments with ABL operational capacity so that cargo readiness, asset availability, tide/bridge windows, jetty/CTS capacity, OGV loading sequence and recovery decisions are planned through one governed scheduling platform.

### 2.1 Business problems addressed

| Business problem | Application response |
| --- | --- |
| Spreadsheet planning is difficult to govern when demand, windows and assets change during the day | Structured demand intake, versioned plan generation, conflict checks, approval and published schedule output |
| Shipment demand is not always synchronized with real route and asset capacity | Demand, cargo sequence, resource eligibility, jetty/BLC capacity, CTS operations and movement windows are handled in one planning model |
| Tide, bridge, berth and operational windows can become the controlling constraint | Operating windows are treated as schedulable capacity, not as static notes |
| Cargo grade and loading sequence affect execution | Cargo requirements and loading sequence are captured as planning inputs |
| Active trips and occupied resources affect new scheduling decisions | Work in progress, occupied windows, unavailable assets and queues are plotted before new movements are placed |
| Planners need discretion for negotiated exceptions | Manual overrides remain available but are reason-coded, auditable and visible in plan lineage |
| Approval and publication require traceability | Published plans carry version, approval, audit and export lineage |

### 2.2 First-release objective

Release 1 will deliver a governed scheduling MVP. The product objective is to provide:

- one structured intake for OGV demand and cargo sequence;
- one operating model for assets, routes, tide windows, bridge windows, jetty/BLC capacity and CTS capacity;
- one draft-plan generation flow with explicit feasibility and conflict output;
- one approval and publish path that creates an execution contract;
- one controlled export and audit trail for operational use.

Release 1 does not depend on live telemetry, autonomous recovery, commercial settlement logic or automatic optimization.

## 3. Client Flow Challenges

The ABL-Berau flow is difficult to schedule because the planning constraint does not stay fixed. At one point the limiting factor may be cargo readiness. Later the same shipment may be blocked by a tide window, a bridge crossing slot, a tug-barge availability issue, a CTS queue or an OGV laycan pressure.

The application is therefore designed around a moving-constraint operating flow.

| Flow challenge | Planning implication |
| --- | --- |
| OGV demand changes or sequence changes | The schedule must be revalidated against cargo, route and downstream commitments |
| Cargo may be ready but an asset may not be available | Resource eligibility and availability must be checked before movement placement |
| A tug-barge movement may miss tide or bridge timing | The movement chain must be placed against continuous feasible windows |
| Jetty/BLC operations may delay barge loading | Upstream delays must be visible before downstream movements are committed |
| CTS or floating equipment may become the bottleneck | Discharge and transshipment capacity must be represented as a schedulable constraint |
| Planners may negotiate practical exceptions | The tool must preserve planner discretion while capturing reason and approval lineage |
| Live signals may be incomplete or stale | Field evidence must be separated from confirmed schedule authority |

## 4. Scheduling-First Operating Philosophy

The scheduling philosophy is simple:

> Each shipment movement is treated as schedulable work that must pass through eligible route steps, available resources and valid operating windows.

For ABL, the route is both physical and operational:

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

The first release will not overcomplicate this philosophy. It will focus on making the planning chain structured, visible, governable and publishable. Later maturity blocks can add richer scenario, recovery and live-execution behavior after the governed scheduling spine is adopted.

## 5. Vector Proprietary Scheduling And Scenario Scaffolding

Vector owns proprietary scaffolding for constraint-aware scheduling, scenario simulation and dynamic-capacity planning. This base will be used for the application build so that the client implementation can focus on ABL-specific operating rules, user workflows, data interfaces and adoption.

The operator does not need to see the internal engine mechanics. The visible behavior of the tool is:

- identify whether a movement is schedulable;
- surface the first meaningful blocker when it is not schedulable;
- show the affected resource, window, movement or downstream commitment;
- preserve manual override and approval lineage;
- compare candidate options when scenario and recovery capability is activated.

### 5.1 Capability provided by the base scaffolding

| Capability | Role in the ABL build |
| --- | --- |
| Scheduling entity model | Represents shipment movements, route steps, dependencies, priorities and target dates |
| Route and resource eligibility | Matches each movement with valid jetties, routes, tug-barge pairs, CTS assets and operating steps |
| Capacity-window placement | Places movements into free operating windows and prevents invalid overlap |
| Current-state loading | Considers active work, occupied resources, queues and confirmed actuals before placing new work |
| Dynamic constraint evaluation | Rechecks feasibility when tide, bridge, asset, berth or cargo readiness changes |
| Scenario engine | Supports delay, outage, window-change, reassignment and recovery assumptions after adoption gates are met |
| Candidate comparison | Evaluates alternate paths and recovery options against feasibility and operational impact |
| Exception and blocker output | Identifies the operating blocker and the affected downstream commitments |

### 5.2 ABL-specific configuration

The build will configure the scaffolding around:

- Berau OGV demand, laycan, cargo quantity, coal grade and loading sequence;
- ABL jetties, BLC capability, tug-barge fleet, CTS assets and route timings;
- tide windows, bridge windows, river movement rules and safe crossing logic;
- cargo readiness, source eligibility and quality-release status;
- active trip state, loaded barges, queues and confirmed operational events;
- exception categories, override rules, approvals and publishability checks;
- reporting, dashboard, audit, export and integration requirements.

## 6. Product Scope: Phase-Gated Build Model

The application build is structured as a phase-gated maturity path. The first client-owned product is the governed scheduling MVP. Later blocks expand the product only when the operating model, user adoption and data readiness support the next level of automation.

| Stage | Sprint direction | Client-owned product | Deferred by design |
| --- | --- | --- | --- |
| Stage 1 - Governed scheduling MVP | Sprint 0 to Sprint 5 | Demand intake, cargo sequence, master data, operating windows, assignments, conflicts, approvals, publish and export | Live telemetry dependency, autonomous recovery, full commercial optimization |
| Stage 1A - Operational adoption gate | After Release 1 pilot usage | Evidence of planner usage, data gaps, overrides, false positives and approval behavior | Expansion before operating fit is validated |
| Stage 2 - Exception and replanning support | Sprint 6 onward, subject to gate | Exception taxonomy, delay propagation, manual recovery options and impact review | Autonomous recovery publication |
| Stage 3 - Scenario and impact simulation | Subject to scenario readiness | Baseline-versus-scenario comparison, projected downstream impact and utilization review | Scenario use without agreed data and decision rules |
| Stage 4 - Telemetry-assisted execution | Subject to integration readiness | Position/status evidence, event candidate workflow and confirmed event updates | Treating raw telemetry as automatic truth |
| Stage 5 - Governed flow-management maturity | Later maturity state | Guided recovery, management review surfaces and projection indicators | Final commercial settlement unless separately scoped |

## 7. Release 1 - Governed Scheduling MVP

Release 1 proves the governed scheduling spine and operating-window logic. This release falls between **Sprint 0 and Sprint 5** of the ten-sprint build plan.

### 7.1 Sprint coverage

| Sprint | Build focus | Key outcome |
| --- | --- | --- |
| Sprint 0 | Application foundation: web application, API service, database, background processing, object storage and routing layer | Runnable product spine |
| Sprint 1 | Master data and governance: organizations, roles, audit, locations, cargo, jetties, routes, assets and compatibility | Safe multi-party operating model |
| Sprint 2 | Demand and capacity intake: OGV demand, cargo layer, asset windows, jetty windows, tide windows and bridge windows | Structured inputs for planning |
| Sprint 3 | Scheduling entity and route model: trips, assignments, schedule events and route-step dependencies | Movement chain represented as schedulable work |
| Sprint 4 | Capacity placement and feasibility: candidate paths, occupied/free windows, conflict checks and movement candidates | Feasible draft plan with explicit blockers |
| Sprint 5 | Plan governance: versions, overrides, approval requests, approval decisions, published snapshots and exports | Approved execution contract |

### 7.2 Client deliverables in Release 1

| Deliverable type | What the client receives |
| --- | --- |
| System screens | Login, role-based navigation, master data, OGV demand, cargo layer sequence, tide/bridge windows, asset availability, tug-barge assignment, jetty/BLC loading, CTS operations, conflict review, approval, published plan, audit and export screens |
| Scheduling capability | Structured demand intake, route/resource eligibility, candidate movement generation, capacity-window placement, feasibility checks, conflict output and manual override capture |
| Governance capability | Plan versioning, dual approval, publishability check, immutable published snapshot, audit trail and governed export |
| Product owned at this stage | A working scheduling application that replaces spreadsheet-only planning for the core ABL-Berau flow and creates an approved operating schedule |

### 7.3 MVP success criteria

| Success measure | Validation direction |
| --- | --- |
| Publishable-plan cycle time | Time from demand intake to publishable plan is reduced or made more predictable |
| Schedule rework | Repeated spreadsheet revisions and manual reconciliation are reduced |
| Conflict clarity | Hard blockers carry a reason code, affected movement and next review action |
| Approval traceability | Published plans carry approval, version and audit lineage |
| Planner adoption | Named pilot users can complete representative planning workflows with acceptable override usage |
| Data readiness | Demand, master data and operating-window inputs meet minimum completeness expectations |

Specific numeric targets will be baselined with ABL and Berau during pilot usage.

## 8. Operational Adoption Gate

Before expanding beyond the governed scheduling MVP, ABL, Berau and Vector will review whether the tool matches real planning behavior.

The adoption gate will review:

- planner usage across representative scheduling workflows;
- demand completeness and master-data stability;
- conflict false positives and missed operational constraints;
- manual override frequency and reason-code quality;
- approval latency and escalation behavior;
- data gaps that prevent reliable scheduling;
- operating rules that need refinement before scenario or telemetry expansion.

The output of this gate is a clear decision on whether to move into exception support, scenario simulation, telemetry-assisted execution or additional workflow hardening.

## 9. Exception Taxonomy And Human Operating Reality

The application will preserve planner discretion during early adoption. Planners will still be able to handle negotiated exceptions, operational judgment and manual escalation. The difference is that these decisions will be captured with reason codes, approval state and plan lineage.

During pilot usage, repeated manual decisions will be reviewed to determine whether they should become formal scheduling rules, exception categories or operator guidance.

### 9.1 Initial exception taxonomy

| Exception family | Initial examples | Release 1 treatment |
| --- | --- | --- |
| Cargo/source readiness | Cargo not ready, quality hold, source switch, cargo layer mismatch | Conflict reason or readiness note |
| Jetty/BLC operations | Loading delay, queue, reduced loading rate, equipment stoppage | Capacity-window conflict or manual override |
| Navigation constraint | Tide missed, bridge window missed, draft restriction change, crossing risk | Operating-window blocker |
| Fleet/asset availability | Tug unavailable, barge unavailable, incompatibility, breakdown, charter lead-time pressure | Resource availability or eligibility blocker |
| CTS/transshipment | CTS queue, floating crane downtime, discharge rate reduction | Downstream capacity blocker |
| OGV/laycan | OGV ETA change, hatch sequence change, laycan pressure, loading completion risk | Demand priority and completion-risk note |
| Weather/marine | Rain, wind, visibility, wave restriction, river condition | Exception note or window blocker |
| Survey/clearance | Draft survey delay, documentation hold, port clearance interruption | Closure, readiness or handover blocker |
| Human/governance | Approval delay, manual override, escalation, disputed decision | Workflow and audit event |
| Data/integration | Missing feed, stale signal, duplicate event, untrusted telemetry | Data quality warning |

### 9.2 Human-operational model

Release 1 will support human operation through:

- manual override with mandatory reason capture;
- planner notes and exception comments where operational judgment is required;
- approval workflow before publication;
- shadow-mode validation where rules need observation before enforcement;
- review of recurring overrides as candidates for future rule formalization.

## 10. Later Maturity Blocks

Later maturity blocks are part of the product direction, but they are not treated as dependencies for the first scheduling MVP.

| Release block | Capability | Activation condition |
| --- | --- | --- |
| Release 2 - Exception and manual recovery support | Delay propagation, exception queue, recovery option review and manual replanning path | Adoption gate confirms planning fit and exception taxonomy |
| Release 3 - Scenario and impact simulation | What-if assumptions, baseline-versus-scenario comparison, projected trip/event impact and utilization review | Data quality and scenario decision rules are agreed |
| Release 4 - Telemetry-assisted execution | GPS/AIS-style evidence, latest asset state, geofence/ETA variance, event candidates and confirmed event workflow | Integration owners, data trust and operating confirmation rules are ready |
| Release 5 - Governed flow-management maturity | Guided recovery, management review surfaces, publishability checks and projection-only operating impact indicators | Recovery governance and decision authority are stable |

### 10.1 Economic and operating impact indicators

The first release prioritizes feasible and publishable scheduling. Commercial optimization is not treated as final settlement logic. Where data is available, later maturity blocks can expose projection-only indicators such as:

- laycan risk;
- waiting time;
- fleet utilization;
- queue impact;
- charter lead-time pressure;
- demurrage exposure proxy.

Final demurrage, invoicing, despatch and settlement remain outside the scheduling MVP unless separately scoped.

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

### 11.2 Capacity placement logic

At planning time, the platform will:

1. load current demand and master data;
2. plot current work and already occupied capacity;
3. identify eligible resources for each movement;
4. generate candidate route and resource paths;
5. search for continuous feasible operating windows;
6. mark selected windows as occupied;
7. record conflicts where no feasible placement exists;
8. preserve reason codes, override notes and audit lineage.

### 11.3 Disruption flow in later maturity blocks

```text
Open active exception
-> Review operating cause
-> Generate recovery options
-> Compare impact
-> Create scenario from selected option
-> Simulate downstream effect
-> Promote feasible scenario
-> Repair remaining blockers if required
-> Submit approval
-> Manually publish recovery plan
```

### 11.4 State separation

The application will keep five states separate:

| State | Meaning |
| --- | --- |
| Planned | The approved schedule expectation |
| Observed | Field signal or external evidence that may indicate status |
| Confirmed | Operationally trusted event that updates actual execution status |
| Projected | Future impact estimated by the scheduling or scenario engine |
| Recommended | Candidate action for review, not an automatic publication |

## 12. Application Modules

### 12.1 Core MVP modules

| Module | Working responsibility |
| --- | --- |
| Organizations and access control | Multi-party users, roles, permissions, data scope and approval authority |
| Master data | Locations, coal grades, mines, stockpiles, jetties, tug/barge/CTS assets, routes, loading rates and compatibility |
| Planning intake | OGV voyages, cargo requirements, cargo layer sequence, availability windows, tide windows, bridge windows and import jobs |
| Scheduling | Plan, plan version, trip, assignment, schedule event, conflict, override, approval, publish and export |
| Audit | Request and domain audit trail for governed actions |
| Operator cockpit | Dense operational screens for demand, cargo sequence, assignments, jetty/BLC, CTS, tide/bridge, conflicts, approvals and published plan |

### 12.2 Later maturity modules

| Module | Working responsibility |
| --- | --- |
| Scenario | Delay, outage, window-change and reassignment assumptions with projected impact |
| Telemetry | Source registry, asset mapping, position evidence, geofence zones, latest state, ETA projection and tracking alerts |
| Operations events | Integration feeds, device endpoints, health snapshots, event candidates, confirmed events and actualization |
| Recovery guidance | Recovery input snapshots, ranked options, root-cause review, scenario creation and publishability assessment |
| Management review | Operating impact, utilization, exception pattern and projection-only commercial indicators |

## 13. Proposed Implementation Architecture

The implementation stack is the infrastructure behind the operator experience. Operators interact with workflows, screens, approvals and schedules; the stack provides the reliability, testability and deployment structure required to run those workflows.

| Layer | Technology | Role in the application |
| --- | --- | --- |
| Operator web application | React, Vite, TypeScript | Builds the browser-based screens for planners, approvers and operations users |
| Web application testing | Vitest, Testing Library, jsdom | Tests user interface behavior, screen logic and component interaction before release |
| API and business services | Django, Django REST Framework | Provides business APIs, workflow rules, access control and application services |
| Background jobs | Celery, Celery Beat | Runs asynchronous jobs such as imports, exports, scheduled checks and periodic processing |
| Application server | Gunicorn | Serves the backend application in a production deployment pattern |
| Service testing | pytest, pytest-django | Tests business services, data rules, API behavior and scheduling logic |
| Database | PostgreSQL with PostGIS | Stores operational data and supports location-aware/geospatial data where required |
| Cache / broker | Redis | Supports fast shared state and message brokering for background jobs |
| Object storage | MinIO / S3-compatible storage | Stores imported files, exports, generated documents and object artifacts |
| Edge routing | Nginx | Routes web and API traffic, supports deployment hardening and reverse-proxy needs |
| Runtime approach | Containerized deployment model | Packages services into repeatable deployment units for local, UAT and production environments |

### 13.1 Integration technology positioning

Release 1 does not depend on live industrial integration. Where required by later scope, the integration layer can use:

- HTTP/API callbacks for business-system events;
- MQTT for lightweight device or event messaging;
- NMEA or AIS-derived feeds for marine position data;
- OPC-UA or PLC/operator-console integration for industrial equipment status;
- batch file exchange where operational readiness is lower than API readiness.

## 14. Data Sources And Integration Readiness

The first release can operate with manual entry, controlled upload and validated seed/replay data. Live integration should be activated only when data ownership, timing, reliability and operating response are agreed.

| External data source | Assumed content | Release 1 handling | Later integration direction |
| --- | --- | --- | --- |
| Existing schedule files | Current OGV plan and operating schedule | Import or controlled upload | Governed file ingestion or direct integration |
| OGV schedule | ETA, ETB, laycan, quantity, priority and vessel status | Manual/imported demand | API feed from Berau or shipping system |
| Cargo/source data | Mine, CPP, stockpile, grade, product, available quantity, quality release and jetty eligibility | Master data and demand setup | Cargo, quality or ERP integration |
| Cargo layer sequence | Hatch/layer order, grade requirement and substitution rule | Cargo layer model | Structured demand feed |
| Jetty/BLC data | Loading rate, queue, working hours, equipment status and readiness | Manual windows/status | Terminal, PLC or operator-console feed |
| ABL fleet data | Tug, barge, CTS capacity, compatibility, status, location and availability | Master data and availability windows | GPS/AIS, Spinergie-style feed or fleet API |
| Tide data | Tide tables, height, safe movement windows and water-level observations | Manual tide windows | Sensor/API feed |
| Bridge data | Opening schedule, crossing rule and queue | Manual bridge windows | Bridge operator console or device feed |
| Weather/marine data | Rain, wind, wave, visibility and closure alerts | Exception input or planning note | Weather API or local station |
| GPS/AIS data | Position, speed, heading, timestamp, signal quality and external asset identity | Not required for Release 1 | Tracker, AIS receiver, vendor API or NMEA-derived source |
| Operational events | Loading start/end, discharge start/end, stoppage, breakdown and crossing confirmation | Operator-entered confirmation or pilot replay | MQTT, HTTP callback, PLC, weighbridge, tablet or edge gateway |
| Survey and documents | Draft survey, sampling, certificates, SOF and final quantity/quality documents | Deferred milestone visibility | Document management or survey integration |
| Commercial parameters | Laycan risk, waiting-time proxy and exposure proxy | Deferred from MVP | Separate commercial sign-off |

## 15. Build Deliverables

### 15.1 Release 1 deliverables

| Deliverable | Description |
| --- | --- |
| Vector scheduling base configuration | ABL-specific setup of proprietary scheduling and dynamic-constraint scaffolding |
| Application foundation | Containerized web application, API service, database, Redis, object storage and routing layer |
| Master and capacity model | Assets, routes, eligibility, calendars, operating windows and compatibility |
| Demand and cargo intake | OGV demand, laycan, cargo quantity, coal grade and cargo sequence |
| Scheduling configuration | Shipment movement entity, candidate paths, capacity placement, moving-window checks and conflict output |
| Operator screens | Role-aware screens for demand, master data, windows, assignments, conflicts, approvals, publish and export |
| Governance layer | Access control, dual approval, publishability, immutable snapshots and governed exports |
| Evidence and test pack | Service tests, web application tests, proof commands, UAT scripts and runbook |

### 15.2 Later maturity deliverables

| Deliverable | Description |
| --- | --- |
| Scenario configuration | What-if assumptions, projected impacts, utilization views and scenario comparison |
| Exception and recovery support | Exception queue, impact review, recovery options and proof pack |
| Telemetry-assisted execution | GPS/AIS-shaped evidence, latest state, geofence/ETA variance and data trust review |
| Operations event layer | Event candidates, confirmations, rejection, actual event updates and device/feed health |
| Management review surfaces | Exception patterns, operating impact, projection-only indicators and maturity reporting |

## 16. Assumptions, Readiness Gates And Boundaries

### 16.1 Assumptions

1. Berau provides OGV demand, laycan, cargo quantity, coal grade and layer sequence in a consistent format.
2. ABL and Berau agree master-data naming for jetties, routes, assets, grades, locations and operating zones.
3. Tide and bridge windows are initially entered manually or uploaded before live integration is activated.
4. Resource capacity includes both time availability and operational eligibility.
5. Active work in progress is plotted before new schedules or recovery options are generated.
6. Field evidence does not directly change schedule authority without confirmation.
7. Published plans are immutable; replanning creates successor versions.
8. Approval requires agreed ABL and Berau authority before publication.
9. Manual override requires reason capture and audit.
10. External chartered assets require readiness and lead-time assumptions.

### 16.2 Readiness gates

| Gate | Required validation |
| --- | --- |
| Release 1 readiness | Core demand, master data, operating windows and approval users are available |
| Adoption gate | Pilot users can create, review, approve and publish schedules with acceptable manual intervention |
| Scenario gate | Delay, outage and reassignment assumptions are agreed and data quality is sufficient |
| Telemetry gate | Integration owner, feed reliability, identity mapping and confirmation rules are agreed |
| Recovery gate | Exception taxonomy, approval path and recovery decision authority are stable |

### 16.3 Build boundaries

1. Release 1 is a governed scheduling MVP, not a live control tower.
2. Live GPS/AIS is evidence, not automatic truth.
3. Raw pings do not update the execution plan directly.
4. Confirmed field events update actual execution state only after the confirmation rule is satisfied.
5. Recovery options are advisory until simulated, reviewed, approved and checked for publish readiness.
6. Commercial projection is not final settlement logic.
7. Customer-facing visibility comes after internal governance is stable.
8. Planned, observed, confirmed, projected and recommended states remain separate.

## 17. Glossary

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
| Shadow-mode validation | A pilot approach where rules are observed and measured before being strictly enforced in live operations. |
| Tide window | A time range during which water level and navigation conditions allow a safe or permitted movement. |
| Tug-barge pair | A tug and barge combination considered together for movement eligibility, availability and compatibility. |
| UAT | User Acceptance Testing, the client-side validation stage for workflows, screens and outputs before production use. |

## 18. Reference Inputs

This extension is based on:

- the Operational Blueprinting & Simulation Prototype Proposal;
- the Scheduling Simulation BRD;
- ABL and Berau Coal operating context;
- observed transshipment planning and fleet-coordination challenges;
- cargo, route, asset, tide, bridge, CTS and OGV scheduling logic;
- the product-development direction for a governed ABL operational scheduling platform.
