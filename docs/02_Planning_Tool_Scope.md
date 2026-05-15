# 02 — Scope of the Scheduling Simulation and Live Planning Tool

## 1. Product positioning

The tool should be positioned as:

> A constraint-aware coal transshipment scheduling simulation and live planning platform for ABL and Berau Coal operations.

It is not merely:
- a GPS map,
- an AIS dashboard,
- a digital Excel sheet,
- or a generic fleet-management screen.

It should support operational decisions across demand, fleet, jetty, river constraints, transshipment equipment, and OGV loading sequence.

## 2. Primary users

| User group | What they need from the tool |
|---|---|
| ABL dispatch/planning team | Build feasible tug/barge/CTS schedule and recover from disruptions. |
| Berau scheduling/commercial team | See whether OGV cargo commitments and coal grade sequence can be met. |
| Jetty/terminal operators | Know which barge is coming, what grade to load, and when. |
| CTS/floating-crane operators | See barge queue, OGV assignment, discharge plan, and exceptions. |
| Customers/network stakeholders | Controlled visibility of shipment status, OGV progress, and risk. |
| Management/control tower | View throughput, delay, utilization, demurrage risk, and operational bottlenecks. |

## 3. Core planning objects

The system should maintain the following planning objects:

| Object | Why it matters |
|---|---|
| OGV voyage | Defines demand timing and cargo requirement. |
| Cargo requirement | Defines grade, quantity, and sequence/layering. |
| Mine/CPP/stockpile | Defines source availability. |
| Jetty/BLC | Defines loading resource and queue. |
| Tug | Defines towing resource. |
| Barge | Defines cargo movement unit and capacity. |
| CTS/FTS/FC | Defines transshipment/discharge resource. |
| River route | Defines travel time and restrictions. |
| Tide window | Defines feasible movement windows. |
| Bridge window | Defines feasible crossing windows. |
| Live asset position | Converts plan into actual status. |
| Operational event | Represents breakdown, delay, loading completion, missed tide, etc. |
| Simulation scenario | Allows what-if comparison and recovery planning. |

## 4. Core planning cycle

The tool should support this end-to-end cycle:

1. Import OGV schedule and cargo demand.
2. Import Berau source/grade/stockpile/jetty readiness.
3. Read available ABL fleet and transshipment assets.
4. Read tide, bridge, jetty, and route constraints.
5. Generate feasible trip candidates.
6. Assign tug + barge + jetty + CTS + OGV sequence.
7. Simulate loading, sailing, waiting, transshipment, and return.
8. Compare planned vs actual movement using GPS/AIS/manual events.
9. Alert on risk or infeasibility.
10. Re-simulate/recover plan when events occur.
11. Save every planning version and manual override.

## 5. Planning constraints

The planning engine must enforce the following constraints.

### 5.1 Cargo and grade constraints

- Coal is not a generic commodity tonnage.
- Grade/product/brand must be respected.
- OGV layering/loading sequence must be preserved.
- Stockpile and jetty eligibility must match grade.
- Substitution should require controlled approval.

### 5.2 Jetty/loading constraints

- Jetty availability.
- Loading rate.
- Queue.
- Loading equipment availability.
- Conveyor/BLC availability.
- Working calendar.
- Stockpile readiness.
- Weather stoppage or safety closure.

### 5.3 Tug/barge constraints

- Tug availability.
- Barge availability.
- Tug-barge compatibility.
- Barge capacity.
- Loaded vs empty speed.
- Maintenance and breakdown status.
- Return cycle time.
- Current location and next available time.

### 5.4 River/tide/bridge constraints

- River segment travel time.
- Tide windows.
- Bridge opening windows.
- Draft clearance.
- Waiting zones.
- Route choke points.
- Navigation closures.

### 5.5 CTS/transshipment constraints

- CTS type: conveyor vs conventional.
- Daily loading/discharge capacity.
- OGV compatibility.
- Current queue.
- Breakdown/downtime.
- Metal detection/quality events if relevant.
- Transshipment anchorage availability.

### 5.6 OGV/customer constraints

- OGV ETA/ETB/laycan.
- Required cargo quantity.
- Hatch/layering plan.
- Contractual priority.
- Demurrage exposure.
- Customer visibility level.

## 6. Simulation outputs

The tool should output:

| Output | Description |
|---|---|
| Feasible schedule | Planned tug/barge/jetty/CTS/OGV assignments. |
| Trip timeline | Load start/end, departure, bridge/tide crossing, arrival, discharge, return. |
| Constraint conflicts | Missed tide, bridge clash, jetty queue, CTS overload, grade mismatch. |
| ETA and completion projection | OGV loading progress and expected completion. |
| Asset utilization | Tug/barge/CTS idle time, active time, waiting time. |
| Recovery recommendation | Alternative assignment or resequencing after disruption. |
| Scenario comparison | Baseline vs revised vs manually overridden plan. |
| Alerts | Delay, breakdown, queue, missed window, stock/grade conflict, ETA risk. |

## 7. MVP scope

The MVP should avoid overbuilding. It should focus on simulation-first scheduling.

### MVP must include

- OGV schedule input.
- Cargo grade and quantity requirement.
- Tug/barge/CTS/jetty master.
- Manual tide and bridge windows.
- Manual fleet status.
- Feasible schedule generation.
- Exception/conflict list.
- Gantt/timeline-style planning board.
- Scenario versioning.
- Manual override and audit trail.

### MVP should not depend on

- fully automated AIS/GPS,
- AI optimization,
- fuel/emission optimization,
- deep ERP integration,
- customer portal,
- complex digital twin simulation.

## 8. Phase-wise build roadmap

### Phase 1 — Digital scheduling model

Goal: replace Excel with a structured schedule and constraint model.

Deliverables:
- Master data model.
- Manual OGV demand upload.
- Manual fleet/jetty/CTS availability update.
- Tide/bridge calendar input.
- Feasible schedule board.
- Conflict checks.

### Phase 2 — Simulation and scenario planning

Goal: make the planner simulate consequences.

Deliverables:
- What-if engine.
- Delay/breakdown scenarios.
- OGV completion projection.
- Asset utilization report.
- Version comparison.

### Phase 3 — GPS/AIS live tracking

Goal: connect planned schedule with actual position.

Deliverables:
- GPS tracker ingestion.
- AIS ingestion or vendor API.
- Geofence events.
- Planned vs actual ETA.
- Live map.
- Delay alerts.

### Phase 4 — IoT/event-driven operations

Goal: convert field activities into trusted operational events.

Deliverables:
- Jetty loading events.
- CTS discharge events.
- bridge/tide status updates.
- equipment/device health.
- MQTT/event broker.
- local edge buffering.

### Phase 5 — Optimization and recovery recommendation

Goal: move from visibility to decision intelligence.

Deliverables:
- assignment optimizer.
- trip sequencing.
- resource conflict repair.
- recovery recommendation.
- planner approval workflow.

### Phase 6 — Multi-party control tower

Goal: role-based visibility for ABL, Berau, and customers.

Deliverables:
- ABL dispatcher view.
- Berau cargo/OGV view.
- customer shipment view.
- management KPI dashboard.
- alert escalation and SLA tracking.

## 9. Screens that should exist

| Screen | Purpose |
|---|---|
| Today’s OGV risk board | Shows OGVs, required quantity, loaded quantity, ETA risk, demurrage risk. |
| Tug/barge control board | Shows live/plan status of each fleet pair. |
| Jetty loading board | Shows queue, grade, loading status, and upcoming barge. |
| CTS transshipment board | Shows OGV assignment, barge queue, discharge rate, and completion projection. |
| Tide/bridge window board | Shows available windows and missed-window risk. |
| Simulation comparison | Compares baseline plan, disruption plan, and recommended recovery. |
| Exception center | Central list of late vessel, breakdown, grade conflict, jetty congestion, missed tide, bridge issue. |
| Map view | Live asset visibility, geofences, and route status. |
| Master data admin | Vessels, jetties, routes, grades, constraints, compatibility. |
| Audit/history | Who changed what, why, and when. |

## 10. Key implementation principle

The tool should always distinguish:

- planned state,
- live observed state,
- manually confirmed state,
- derived/inferred state,
- recommended future state.

This distinction is crucial because AIS/GPS can be stale, missing, or noisy, and manual operations may lag reality. The scheduler must never blindly overwrite the planning baseline without audit and approval.

## 11. Source URLs used

- Uploaded BRD: `BRD - Schedulling Simulation.docx`
- Berau Coal Energy — Operations: https://beraucoalenergy.co.id/our-profile/operation/
- Berau Coal Energy — Marketing / Our Market: https://beraucoalenergy.co.id/our-profile/our-market/
- Berau Coal Energy — Shipping Devices: https://beraucoalenergy.co.id/shipping-devices/
- ABL — Home: https://abl.co.id/
- ABL — Transshipment: https://abl.co.id/transhipment
- ABL — Tug Boat / Barging: https://abl.co.id/tug-boat
- ABL — Dry Bulk / OGV: https://abl.co.id/dry-bulk
- ABL — Port Management: https://abl.co.id/port-management
