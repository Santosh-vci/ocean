# Frontend Operational UI Hardening Addendum

**Document:** 06 Frontend Operational UI Hardening Addendum  
**Project:** Berau Coal × ABL Scheduling Simulation and Live Planning Platform  
**Audience:** Frontend build team, UX designer, product owner, backend/API team  
**Status:** Implementation correction note after first mock review  
**Purpose:** Tighten the frontend visual thesis so the UI becomes a real operations planning tool, not a spaced-out logistics-themed dashboard.

---

## 1. Executive correction

The current mock direction is visually polished but **not operationally dense enough** and does not yet surface the real work the product must perform.

The tool is not a generic “Coalflow Tower” showcase. It is a **joint Berau Coal + ABL transshipment planning and live execution cockpit**. It must support planners, dispatchers, jetty coordinators, CTS/floating-crane teams, maintenance, commercial users, and customer-facing viewers who need to act on conflicts quickly.

The frontend must therefore move from:

> broad visual panels, large empty space, decorative control-tower styling, and generic exception cards

To:

> compact operational boards, live schedule state, OGV-vessel demand pressure, tug/barge/CTS availability, coal grade sequencing, tide/bridge windows, dispatch actions, and auditable plan changes.

---

## 2. What is wrong with the current mock direction

### 2.1 It is too spacious for a dispatcher/planner tool

Observed issues:

- Left navigation consumes too much fixed width.
- Grids have tall rows and low object density.
- Large panels show too few records.
- The first fold does not show enough operational state.
- Important objects are separated into isolated decorative panels rather than compressed into a working board.

Correction:

- Default to **dense mode**.
- Grid row heights should target **26–32 px**.
- KPI strips should be **thin bands**, not large cards.
- Page headers should be **32–44 px**, not hero bars.
- Sidebars should collapse to icon rail and expand only on demand.

### 2.2 It looks like a theme demo, not a planning product

Observed issues:

- Screens show strong dark style but not enough domain mechanics.
- Some panels are more cinematic than useful.
- Simulation screens show comparison bars but not enough scheduling cause/effect.
- Placeholder chart panels dilute operational seriousness.

Correction:

Every screen must answer a real operational question:

- Which OGV is at risk?
- Which coal grade/layer is blocked?
- Which tug/barge/CTS is the constraint?
- Which tide or bridge window is being missed?
- Which assignment should be changed?
- Who must approve the replan?
- What changed from the last published plan?

### 2.3 Alerts are not operationally complete

The mock alerts show a few useful labels, but the product needs a much richer **exception model**.

Alerts must not be only visual notifications. They must be actionable operational cases with:

- severity
- object impacted
- root cause
- current plan variance
- recommended action
- owner team
- acknowledgement status
- SLA/timer
- downstream impact
- audit history

### 2.4 The mock does not expose enough domain-specific planning concepts

The product must visibly surface:

- OGV laycan / ETA / ETB / ETC
- cargo quantity committed, loaded, in-transit, discharged, remaining
- coal grade and layering sequence
- tug-barge pair availability
- CTS/floating crane loading/discharge capacity
- jetty queue and loading readiness
- tide windows
- bridge windows
- GPS/AIS freshness
- asset status confidence
- missed-window risk
- demurrage exposure
- plan version status
- simulation vs live plan variance

These are not optional backend concepts. They must be first-class UI concepts.

---

## 3. Revised visual thesis

The UI should now follow this thesis:

> A compact, dark, multi-party transshipment operations cockpit where Berau and ABL users can plan, simulate, approve, execute, and recover vessel movements across OGV demand, coal grade sequence, tug/barge/CTS capacity, jetty readiness, tide windows, bridge windows, GPS/AIS state, and live exceptions.

Design personality:

- industrial
- compact
- information-heavy
- role-aware
- low-padding
- operationally serious
- not decorative
- not marketing-like
- not a generic fleet map
- not a BI dashboard first

The UI should feel closer to:

- port control-room system
- vessel dispatch board
- industrial terminal operations desk
- rail/yard planning tool
- SCADA-adjacent operations monitor
- trader-style multi-panel control interface

---

## 4. Mandatory information architecture

The previous module names are acceptable, but the hierarchy must become more operational.

### 4.1 Preferred sidebar hierarchy

```text
Control Tower
  - Network Situation
  - Live Execution Board
  - Exception Queue
  - Published Plan Status

Planning
  - OGV Demand & Laycan
  - Coal Grade Sequence
  - Jetty Loading Plan
  - Tug/Barge Assignment
  - CTS / Floating Crane Plan
  - Tide & Bridge Windows
  - Plan Version Board

Simulation
  - Scenario Builder
  - Constraint Stress Test
  - Impact Comparison
  - Recovery Recommendations
  - Promote / Reject Scenario

Live Tracking
  - Fleet Map
  - GPS/AIS Feed Health
  - Geofence Events
  - Route Progress
  - Signal Gaps

Fleet & Assets
  - Tug Fleet
  - Barge Fleet
  - Tug-Barge Pairing
  - CTS / Floating Cranes
  - Maintenance & Breakdown
  - Device Health

Coal & Jetty
  - Stockpile Readiness
  - Coal Grades
  - Jetty Capacity
  - Loading Events
  - Quality / Layering Exceptions

Approvals & Audit
  - Plan Approvals
  - Manual Overrides
  - Published Schedules
  - Change Log
  - User Action Audit

Reports
  - OGV Service Performance
  - Demurrage Risk
  - Tug/Barge Utilization
  - Jetty Utilization
  - Delay Root Cause
  - Customer ETA Report

Admin
  - Organizations
  - Users
  - Roles & Permissions
  - Master Data
  - Integration Settings
```

### 4.2 Sidebar behavior

Requirements:

- Expanded width: maximum **220–240 px**.
- Collapsed width: **52–64 px**.
- Nested modules must expand inline, not open full overlay menus.
- Current submodule must remain visible.
- Role-based hiding is mandatory.
- Operational badges should appear beside modules, for example `Exceptions 7`, `Approvals 3`, `Signal Gaps 4`.
- Avoid oversized icons.
- Avoid large logo/header space.

---

## 5. Global layout specification

### 5.1 Shell layout

Preferred shell:

```text
┌────────────────────────────────────────────────────────────────────┐
│ Top Utility Bar: plan version, period, search, alerts, publish     │
├───────────────┬──────────────────────────────────────┬─────────────┤
│ Collapsible   │ Main Operational Workspace            │ Right Rail  │
│ Sidebar       │ Boards / grids / timeline / map       │ Exceptions  │
│               │                                      │ Details     │
├───────────────┴──────────────────────────────────────┴─────────────┤
│ Bottom Status Bar: feed health, last sync, live plan state          │
└────────────────────────────────────────────────────────────────────┘
```

### 5.2 Dimensions and density

| Element | Rule |
|---|---|
| Top bar | 36–44 px height |
| Bottom status bar | 22–28 px height |
| Sidebar collapsed | 52–64 px |
| Sidebar expanded | 220–240 px maximum |
| Grid row height | 26–32 px default |
| Dense timeline row | 28–36 px |
| KPI strip height | 52–72 px |
| Right rail | 300–380 px, collapsible |
| Filter bar | 32–40 px |
| Panel padding | 8–12 px maximum |
| Card padding | 8–12 px maximum |

### 5.3 No hero areas

Forbidden:

- giant page headers
- large marketing cards
- decorative charts with no decision
- wide empty banners
- oversized icons
- large whitespace around title text

Allowed:

- thin KPI strips
- compact status bands
- dense grids
- Gantt/timeline boards
- split panes
- right-side operational detail drawers

---

## 6. Required primary screens

## 6.1 Network Situation / Control Tower

Purpose:

> Show the current operational truth across OGV demand, active fleet, jetties, tide/bridge risk, and open exceptions.

Must contain above the fold:

- OGVs at risk
- active tug/barge pairs
- CTS availability
- jetties occupied / waiting / blocked
- next high tide / next bridge window
- delayed trips
- coal grade/layering conflicts
- GPS/AIS feed health
- published plan version

Recommended layout:

```text
Top KPI strip
- OGVs at Risk
- Cargo Remaining Today
- Active Tug/Barge Pairs
- CTS Available
- Jetty Queue
- Tide/Bridge Risks
- Feed Health

Left/main: Live Execution Board
- Time axis
- Rows: OGVs, Jetties, Tug/Barge pairs, CTS
- Events: loading, transit, waiting tide, waiting bridge, discharge, return

Right rail: Exception Queue
- Critical first
- Action buttons
- owner + SLA

Bottom: Change/Impact Log
- New delays
- manual overrides
- simulation promoted
```

This should not be a pure map screen. A map may be available as secondary tab/pane.

## 6.2 OGV Demand & Laycan Board

Purpose:

> Show customer/OGV demand and whether the transshipment plan can meet it.

Grid columns:

- OGV name
- customer
- laycan start/end
- ETA / ETB / ETC
- anchorage/transshipment point
- total nominated quantity
- loaded quantity
- in-transit quantity
- discharged quantity
- remaining quantity
- coal grade sequence status
- demurrage risk
- plan status
- next action

Row expansion:

- hatch/layering sequence
- grade-wise quantity
- assigned barges
- CTS assignment
- schedule events
- exceptions

## 6.3 Coal Grade Sequence Board

Purpose:

> Ensure coal is delivered in the required loading/layering order.

Required visualization:

- OGV-wise sequence ladder
- planned grade vs actual loaded grade
- blocked grade step
- stockpile/jetty source
- quantity required vs available
- next eligible loading
- override status

Exception types:

- wrong grade at jetty
- grade not available
- grade loaded out of sequence
- hatch/layer not ready
- substitute grade pending approval

## 6.4 Tug/Barge Assignment Board

Purpose:

> Dispatchers assign tug/barge pairs and see next availability.

Grid columns:

- tug
- barge
- pairing confidence
- current status
- current location
- assigned OGV
- assigned jetty
- cargo grade
- loaded/empty
- ETA next milestone
- next available time
- maintenance/breakdown flag
- signal age
- suggested action

Required actions:

- assign
- swap tug
- swap barge
- hold
- mark breakdown
- release
- send to maintenance
- simulate reassignment

## 6.5 Jetty Loading Plan

Purpose:

> Manage source-side readiness and loading queues.

Grid/timeline must show:

- jetty ID
- coal grade available
- stockpile readiness
- barge queue
- loading start/end
- loading rate
- expected quantity
- actual quantity
- loader/conveyor status
- berth/jetty availability
- queue conflict
- next tide/bridge feasibility after loading

Critical rule:

The jetty screen must not stop at “loading complete.” It must show whether the loaded barge can actually depart within a feasible tide/bridge window.

## 6.6 Tide & Bridge Window Board

Purpose:

> Convert river/navigation constraints into visible planning gates.

Must show:

- upcoming tide windows
- bridge opening windows
- affected route segment
- vessels eligible for window
- vessels likely to miss window
- next available window
- delay impact if missed
- recommended resequence

Layout:

- left: tide/bridge timeline
- main: affected trips grid
- right: risk/action panel

## 6.7 Simulation Scenario Builder

Purpose:

> Allow planners to model disruption and promote a better plan.

Inputs must be operational, not generic:

- OGV ETA delay
- OGV priority change
- tug breakdown
- barge unavailable
- CTS capacity reduced
- jetty unavailable
- coal grade short
- tide window missed
- bridge unavailable
- weather stoppage
- loading rate reduction
- discharge rate reduction

Outputs must show:

- affected OGVs
- cargo delay
- demurrage exposure
- tug/barge utilization
- CTS utilization
- jetty queue effect
- missed tide/bridge windows
- recommended swaps
- operational explanation
- promote/reject decision

## 6.8 Exception Center

Purpose:

> Manage operational cases, not just alerts.

Exception card/list fields:

- severity
- exception type
- affected object
- owner team
- detected time
- SLA/aging
- root cause
- downstream impact
- recommended action
- action status
- approval required
- audit trail

Exception types to support:

```text
OGV_DELAY
LAYCAN_RISK
DEMURRAGE_RISK
COAL_GRADE_SEQUENCE_CONFLICT
COAL_GRADE_SHORTAGE
JETTY_BLOCKED
JETTY_QUEUE_OVERFLOW
LOADING_RATE_DROP
TUG_BREAKDOWN
BARGE_BREAKDOWN
CTS_BREAKDOWN
TUG_BARGE_PAIRING_CONFLICT
MISSED_TIDE_WINDOW
MISSED_BRIDGE_WINDOW
ROUTE_DEVIATION
GPS_SIGNAL_STALE
AIS_SIGNAL_GAP
ASSET_POSITION_CONFLICT
WEATHER_STOPPAGE
MANUAL_OVERRIDE_PENDING
PLAN_APPROVAL_PENDING
CUSTOMER_ETA_BREACH
```

Each exception must support:

- acknowledge
- assign owner
- run simulation
- apply recommended action
- request approval
- ignore with reason
- close with resolution

## 6.9 Live Map

Purpose:

> Provide spatial context, not replace the planning board.

Map must show:

- OGVs
- tugs
- barges
- tug/barge pairs
- CTS/floating cranes
- jetties
- bridge points
- tide-constrained segments
- geofences
- route lines
- stale signal markers
- planned vs actual path

Right drawer on asset click:

- asset ID
- current assignment
- planned next milestone
- ETA variance
- signal source: GPS/AIS/manual
- last signal age
- paired asset
- current job
- open exceptions
- action buttons

## 6.10 Approvals & Audit

Purpose:

> Govern joint Berau–ABL planning changes.

Must show:

- plan version
- change summary
- impacted OGVs
- impacted customer ETA
- Berau approval status
- ABL approval status
- overrides requested
- reason codes
- full audit timeline

No published plan should be overwritten silently.

---

## 7. Alert and exception design rules

### 7.1 Severity levels

Use severity with operational meaning:

| Severity | Meaning | UI behavior |
|---|---|---|
| Critical | Direct schedule/cargo/demurrage breach likely | pinned top, red, action required |
| Warning | Risk building, still recoverable | amber, action recommended |
| Plan Drift | Plan variance detected but controlled | blue/cyan |
| Info | Useful status or event | muted |
| Resolved | Closed but auditable | grey/green small state |

### 7.2 Alert card format

Compact exception card:

```text
[CRITICAL] Missed Tide Window          Age: 18m    Owner: ABL Dispatch
Barge B-012 cannot depart Jetty Alpha before 15:00 tide close.
Impact: OGV NORTH STAR +45m, Grade B layer delayed.
Recommended: Reassign Tug T-03 to Barge B-017 from Jetty Bravo.
[Run Simulation] [Apply Recommendation] [Assign] [Ignore w/ Reason]
```

### 7.3 Alerts must link to objects

Every alert must deep-link to:

- OGV
- tug
- barge
- CTS
- jetty
- tide/bridge window
- plan version
- simulation result

---

## 8. Component rules

### 8.1 Grids

All grids must support:

- compact density toggle, default compact
- sticky header
- sticky first column where useful
- column resize
- column visibility
- quick filter
- status chips
- inline row actions
- row expansion
- keyboard navigation
- CSV/export only by permission

Grid row height target: **26–32 px**.

### 8.2 Timelines / Gantt boards

Timeline boards must support:

- horizontal scroll
- now marker
- planned vs actual bars
- delay risk color
- constraint overlays
- tide/bridge window markers
- drag only where permission allows
- tooltip with full event details
- conflict markers

Rows should be compact and hierarchical:

```text
OGV
  └── CTS
      └── Tug/Barge Trip
          └── Jetty Loading Event
```

### 8.3 Right detail drawers

Use right drawers instead of full-page drilldowns for common inspection.

Drawer content:

- object summary
- live state
- planned next milestones
- exceptions
- recommended actions
- audit trail
- linked objects

### 8.4 Status chips

Status chips must be short and meaningful:

- LIVE
- DRAFT
- PROPOSED
- APPROVED
- PUBLISHED
- DELAYED
- WAIT TIDE
- WAIT BRIDGE
- LOADING
- DISCHARGING
- RETURNING
- BREAKDOWN
- SIGNAL STALE
- OVERRIDE

Avoid long decorative labels.

---

## 9. Visual density and typography

### 9.1 Font scale

Recommended:

| Use | Size |
|---|---|
| Main grid text | 12–13 px |
| Secondary grid text | 11–12 px |
| KPI label | 11–12 px uppercase |
| KPI value | 18–24 px only if important |
| Page title | 16–20 px |
| Section title | 12–13 px uppercase |
| Button text | 11–12 px |

### 9.2 Spacing

| Element | Padding |
|---|---|
| Panel | 8–12 px |
| Grid cell horizontal | 8–10 px |
| Grid cell vertical | 4–6 px |
| Toolbar item gap | 6–8 px |
| Card internal gap | 6–8 px |

### 9.3 Visual hierarchy

Use hierarchy through:

- compact section headers
- subtle borders
- status chips
- row grouping
- pinned critical exceptions
- right detail drawer
- timeline overlays

Do not use hierarchy through:

- huge whitespace
- large icons
- gradient cards
- decorative hero panels

---

## 10. Screen-specific acceptance criteria

The frontend mock is acceptable only when these criteria are met:

### 10.1 Network page acceptance

Must show at least:

- 6–8 KPI/state values in a thin strip
- live execution board with multiple resource rows
- exception queue with owner/action
- plan version and last sync
- GPS/AIS feed health
- tide/bridge risk marker

### 10.2 Schedule page acceptance

Must show:

- OGV rows
- quantity progress
- grade/layer status
- assigned trips
- ETA variance
- demurrage risk
- open exceptions
- plan status

### 10.3 Assignment page acceptance

Must show:

- tug-barge pairs
- unassigned assets
- conflicts
- next availability
- maintenance/breakdown
- suggested swaps
- compact 48–72 hour timeline

### 10.4 Simulation page acceptance

Must show:

- scenario input panel
- impacted OGVs
- baseline vs scenario differences
- constraint cause explanation
- recommended recovery plan
- promote/reject workflow
- audit implication

### 10.5 Live map acceptance

Must show:

- map plus operational list/table
- planned vs actual state
- geofence events
- signal freshness
- right drawer on asset click
- route and constraint overlays

A map alone is not acceptable.

---

## 11. Role-aware UX

The UI must change by user role.

### 11.1 Berau planner

Primary focus:

- OGV demand
- coal grade readiness
- stockpile/jetty loading readiness
- customer ETA
- plan approval
- demurrage exposure

### 11.2 ABL dispatcher

Primary focus:

- tug/barge assignment
- CTS capacity
- live fleet state
- route/tide/bridge feasibility
- recovery actions
- breakdown handling

### 11.3 Jetty operator

Primary focus:

- assigned loading tasks
- arrival confirmation
- loading start/end
- quantity loaded
- coal grade confirmation
- departure readiness

### 11.4 CTS/floating crane coordinator

Primary focus:

- OGV assignment
- discharge queue
- discharge rate
- waiting barges
- equipment status

### 11.5 Maintenance team

Primary focus:

- unavailable assets
- breakdowns
- repair ETA
- maintenance blocks
- asset health

### 11.6 Customer viewer

Primary focus:

- own OGV/shipment ETA
- loaded/in-transit/discharged status
- milestone confidence
- exception summary without internal operational clutter

---

## 12. Functional features that must surface in frontend

The frontend must expose these features clearly:

1. Live published plan vs latest actual state
2. Plan versioning: Draft / Proposed / Approved / Published / Revised
3. OGV laycan risk
4. Coal grade sequence compliance
5. Tug-barge-CTS assignment status
6. Jetty loading queue and loading rate
7. Tide/bridge window feasibility
8. GPS/AIS feed freshness
9. Exception ownership and SLA
10. Simulation scenario comparison
11. Recommended recovery action
12. Manual override with reason
13. Approval workflow
14. Audit trail
15. Customer-visible ETA status

---

## 13. Developer implementation guidance

### 13.1 Frontend stack assumption

Recommended:

- React or Next.js
- TypeScript
- TanStack Table / AG Grid-style grid capability
- Timeline/Gantt component with custom rendering
- MapLibre/Leaflet/Mapbox-style map layer
- WebSocket/SSE for live updates
- Zustand/Redux Toolkit for local operational state if needed
- Design tokens for dark theme and density

### 13.2 Design token priorities

Create tokens for:

- surface background
- panel background
- raised panel
- grid border
- muted text
- primary text
- status red/amber/green/blue
- compact spacing scale
- row heights
- sidebar widths
- drawer widths

### 13.3 API contract expectation

Frontend must not invent operational state. Backend should provide shaped payloads for:

- network snapshot
- OGV schedule board
- assignment board
- jetty loading board
- tide/bridge window board
- exception queue
- simulation result
- live asset state
- audit trail

For each board, backend should send both raw IDs and display-ready fields.

---

## 14. Anti-pattern checklist

Do not build:

- marketing-style dashboard
- map-only experience
- giant KPI cards
- empty hero panels
- decorative fake charts
- one alert list without action ownership
- grid rows taller than needed
- navigation without submodule hierarchy
- simulation output without operational explanation
- frontend-only permission hiding without backend authorization
- color usage that is not tied to status/risk
- mock data that hides real domain constraints

---

## 15. Revised mock instruction for the frontend agent

Use this instruction for the next UI mock pass:

```text
Rebuild the UI as a dense dark operations cockpit for Berau Coal × ABL transshipment planning.
Do not create a marketing dashboard. Do not use hero panels. Default to compact grids, thin KPI strips, right-side exception/action rails, and timeline/Gantt execution boards.

The UI must visibly support: OGV laycan, coal grade layering sequence, tug-barge pairing, CTS/floating crane assignment, jetty loading queues, tide windows, bridge windows, GPS/AIS feed freshness, live plan variance, simulation comparison, recommended recovery actions, approvals, and audit trail.

Use a collapsible hierarchical sidebar with modules and submodules. Keep all paddings minimal. Use compact row heights. Put more operational objects above the fold. Every alert must have severity, owner, impacted object, downstream impact, recommended action, and action buttons.

The first mock must include these screens:
1. Network Situation / Control Tower
2. OGV Demand & Laycan Board
3. Tug/Barge Assignment Board
4. Jetty Loading Plan
5. Tide & Bridge Window Board
6. Simulation Impact Comparison
7. Exception Center
8. Live Map with operational right drawer

Every screen must show domain data, not generic placeholders.
```

---

## 16. Final direction

The UI must make the planner feel they are controlling a live transshipment network, not browsing a dashboard.

A good screen should immediately reveal:

- what is late
- what is blocked
- what is waiting
- what is at risk
- what can be reassigned
- who owns the next action
- what plan version is live
- what happens if the scenario is promoted

That is the operational standard for the next frontend build pass.
