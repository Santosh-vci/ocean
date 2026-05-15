# Seed Data Specification for Berau–ABL Transshipment Scheduling MVP

## 1. Purpose of the Seed-Data Workbook

Create a multi-sheet spreadsheet workbook that allows the development team to seed the application with realistic data for:

- End-to-end happy-path planning
- OGV demand and laycan planning
- Coal grade / hatch / layer sequence planning
- Tug-barge assignment
- Jetty loading
- CTS / floating crane discharge
- Tide and bridge constraint testing
- GPS/AIS live-map simulation
- Exception generation
- Simulation/recovery workflow
- Approvals and published plan flow
- RBAC and user-role behavior
- Audit/log review

The seed data must support the full user journey:

```text
OGV demand
→ coal grade sequence
→ jetty loading
→ tug/barge assignment
→ tide/bridge movement
→ CTS discharge
→ exception detection
→ simulation recovery
→ approval
→ published plan
→ live execution monitoring
→ audit trail
```

The objective is to make a demo user feel:

> “This is a real Berau–ABL coal transshipment control system, not a generic logistics dashboard.”

---

## 2. Geographic and Operational Grounding

The dataset should reflect the actual operating region and business context of Berau Coal and ABL in East Kalimantan, Indonesia.

Use the public Berau operation map and website context as visual/geographic grounding. The map reference includes Lati, Binungan, Sambarata, Gurimbang, Suaran, Berau River, Rantau Delta, and Muara Pantai Transshipment Point.

### 2.1 Mine / Production Origin Areas

Seed at least these operating clusters:

| Cluster | Business Meaning | Suggested Seed Role |
|---|---|---|
| Lati | Mine area and Lati Port flow | Source mine + CPP + Lati Port flow |
| Binungan | Mine area and CPP Binungan/Suaran flow | Source mine + CPP + Suaran terminal flow |
| Sambarata | Mine area and Sambarata Port flow | Source mine + CPP + Sambarata Port flow |
| Gurimbang / Berau River corridor | River movement corridor | Route segment / checkpoint |
| Suaran / Rantau Delta corridor | River-to-estuary operating corridor | Tide/bridge/route constraint zone |
| Muara Pantai Transshipment Point | Offshore/estuary transshipment destination | OGV/CTS operation zone |

### 2.2 Seed Route Geography

Use approximate coordinates, not legally exact coordinates. Coordinates only need to be plausible and internally consistent enough to render maps and movement traces.

Create these location types:

```text
Mine
CPP
Stockpile
Jetty / Port
River checkpoint
Bridge / restricted passage
Tide gate
Anchorage
CTS operation zone
OGV transshipment point
Maintenance / dock zone
```

Recommended named locations:

```text
LATI_MINE
LATI_CPP
LATI_PORT
BINUNGAN_MINE
CPP_BINUNGAN
SUARAN_PORT
SAMBARATA_MINE
SAMBARATA_PORT
GURIMBANG_CHECKPOINT
KM20_SUARAN_CHECKPOINT
KM28_SUARAN_CHECKPOINT
KM30_SUARAN_CHECKPOINT
BERAU_RIVER_GATE
RANTAU_DELTA_GATE
BRIDGE_GATE_B
ANCHORAGE_SOUTH
ANCHORAGE_MUARA_PANTAI
MUARA_PANTAI_TRANSSHIPMENT
CTS_ZONE_ALPHA
CTS_ZONE_BRAVO
MAINTENANCE_DOCK_01
```

---

## 3. Workbook Structure

Create one Excel workbook named:

```text
berau_abl_seed_data_v1.xlsx
```

The workbook should contain these sheets:

```text
00_README
01_ORGANIZATIONS
02_USERS_RBAC
03_LOCATIONS_GEOFENCES
04_ROUTE_SEGMENTS
05_COAL_GRADES
06_STOCKPILES
07_JETTIES
08_OGV_DEMAND
09_OGV_HATCH_LAYER_SEQUENCE
10_TUGS
11_BARGES
12_TUG_BARGE_COMPATIBILITY
13_CTS_FLOATING_CRANES
14_TIDE_WINDOWS
15_BRIDGE_WINDOWS
16_JETTY_LOADING_PLAN
17_TUG_BARGE_ASSIGNMENTS
18_CTS_DISCHARGE_PLAN
19_GPS_AIS_POSITION_EVENTS
20_EXCEPTIONS
21_SIMULATION_SCENARIOS
22_APPROVAL_REQUESTS
23_PUBLISHED_PLAN
24_AUDIT_LOGS
25_DEVICE_MAPPING
26_INTEGRATION_FEEDS
27_TEST_SCENARIOS_INDEX
```

---

## 4. Sheet-by-Sheet Specification

## 00_README

Purpose: explain workbook scope, assumptions, and seed scenario coverage.

Columns:

```text
section
description
owner
notes
```

Include notes:

- Coordinates are approximate and for simulation/testing only.
- Names are realistic but should not represent actual contracts or confidential data.
- Berau operation geography is inspired by public information and the concession map context.
- Loading capacities and site flows are benchmarked against public Berau website information where available.
- Data must support happy path and constraint/disruption path.

---

## 01_ORGANIZATIONS

Purpose: support RBAC and multi-party workflow.

Columns:

```text
organization_id
organization_name
organization_type
parent_organization_id
visibility_scope
is_active
```

Seed rows:

```text
ORG_BERAU | Berau Coal | Producer | null | shared_control | true
ORG_ABL | ABL Operations | Transshipment Operator | null | shared_control | true
ORG_JCT | Joint Control Tower | Joint Operations | null | shared_control | true
ORG_CUSTOMER_GLENCORE | Glencore | Customer | null | customer_limited | true
ORG_CUSTOMER_VITOL | Vitol | Customer | null | customer_limited | true
ORG_PLATFORM | Platform Admin | Platform | null | platform | true
```

---

## 02_USERS_RBAC

Purpose: seed role behavior and access control.

Columns:

```text
user_id
display_name
email
organization_id
role
module_access
data_scope
approval_authority
status
last_login
mfa_status
```

Seed core users:

```text
USR_BERAU_SCHED_01 | Berau Scheduler 01 | scheduler@berau.example | ORG_BERAU | Berau Scheduler
USR_ABL_DISP_01 | ABL Dispatcher 01 | dispatcher@abl.example | ORG_ABL | ABL Dispatcher
USR_JCT_MANAGER_01 | Joint Control Manager | jct@ops.example | ORG_JCT | Joint Control Tower Manager
USR_BERAU_QUALITY_01 | Berau Quality Planner | quality@berau.example | ORG_BERAU | Berau Coal Quality Planner
USR_ABL_CTS_01 | ABL CTS Coordinator | cts@abl.example | ORG_ABL | ABL CTS Coordinator
USR_ADMIN_01 | Platform Admin | admin@coalflow.example | ORG_PLATFORM | Platform Admin
USR_VIEWER_01 | Read Only Viewer | viewer@example | ORG_JCT | Read-only Viewer
```

Role coverage required:

- Berau Scheduler can edit OGV demand and coal grade sequence.
- ABL Dispatcher can edit tug/barge assignments.
- CTS Coordinator can manage CTS operations.
- Joint Control Manager can triage and coordinate approvals.
- Admin can manage master data and users.
- Viewer can only see published plan and dashboard.

---

## 03_LOCATIONS_GEOFENCES

Purpose: support map, route, jetty, tide/bridge, and GPS/AIS testing.

Columns:

```text
location_id
location_name
location_type
latitude
longitude
geofence_radius_m
parent_area
operational_notes
is_active
```

Use approximate coordinates around Berau/East Kalimantan. Create at least 25–35 rows.

Seed examples:

```text
LOC_LATI_MINE | Lati Mine | mine | approx | approx | 2000 | Lati | Source mine
LOC_LATI_PORT | Lati Port | jetty | approx | approx | 500 | Lati | Barge loading point
LOC_CPP_BINUNGAN | CPP Binungan | cpp | approx | approx | 800 | Binungan | Processing plant
LOC_SUARAN_PORT | Suaran Port | jetty | approx | approx | 500 | Suaran | Barge loading terminal
LOC_SAMBARATA_PORT | Sambarata Port | jetty | approx | approx | 500 | Sambarata | Barge loading point
LOC_GURIMBANG | Gurimbang Checkpoint | checkpoint | approx | approx | 300 | Berau River | Route checkpoint
LOC_BRIDGE_GATE_B | Bridge Gate B | bridge | approx | approx | 300 | Berau River | Bridge/restricted crossing
LOC_RANTAU_DELTA_GATE | Rantau Delta Gate | tide_gate | approx | approx | 1000 | Rantau Delta | Tide-sensitive segment
LOC_MUARA_PANTAI_TP | Muara Pantai Transshipment Point | transshipment | approx | approx | 2000 | Estuary | OGV/CTS zone
LOC_ANCHORAGE_SOUTH | Anchorage South | anchorage | approx | approx | 1500 | Estuary | Waiting zone
LOC_CTS_ALPHA | CTS Zone Alpha | cts_zone | approx | approx | 1500 | Transshipment | CTS operating area
```

Instruction: coordinate values should be internally consistent so route lines look realistic on the map.

---

## 04_ROUTE_SEGMENTS

Purpose: support movement planning and ETA calculations.

Columns:

```text
route_segment_id
from_location_id
to_location_id
segment_type
distance_km
standard_duration_loaded_min
standard_duration_empty_min
constraint_type
requires_tide_window
requires_bridge_window
is_active
```

Create route chain:

```text
LATI_PORT → GURIMBANG
GURIMBANG → BERAU_RIVER_GATE
BERAU_RIVER_GATE → RANTAU_DELTA_GATE
RANTAU_DELTA_GATE → MUARA_PANTAI_TRANSSHIPMENT

SUARAN_PORT → KM30_SUARAN_CHECKPOINT
KM30_SUARAN_CHECKPOINT → RANTAU_DELTA_GATE
RANTAU_DELTA_GATE → MUARA_PANTAI_TRANSSHIPMENT

SAMBARATA_PORT → GURIMBANG
GURIMBANG → BERAU_RIVER_GATE
```

Create both normal and constraint-heavy segments.

---

## 05_COAL_GRADES

Purpose: support grade sequence and customer/OGV demand.

Columns:

```text
coal_grade_id
coal_grade_name
brand_family
source_cluster
quality_band
compatible_jetties
requires_quality_hold_check
is_active
```

Seed grades inspired by public Berau product/brand families:

```text
GRADE_AGATHIS_HG | Agathis High Grade | Agathis | Lati | HG
GRADE_SUNGKAI_M | Sungkai Medium | Sungkai | Lati | M
GRADE_EBONY_M | Ebony Medium | Ebony | Sambarata/Binungan | M
GRADE_MAHONI_B | Mahoni-B | Mahoni | Binungan | M
GRADE_THERMAL_LG | Thermal Low Grade | Generic | Mixed | LG
```

---

## 06_STOCKPILES

Purpose: provide stock availability and quality readiness.

Columns:

```text
stockpile_id
location_id
coal_grade_id
available_mt
reserved_mt
quality_status
moisture_status
last_updated
```

Seed both clean and issue rows:

- Available stock ready
- Quality hold
- Low stock
- Reserved stock
- Moisture warning

---

## 07_JETTIES

Purpose: support jetty loading screen.

Columns:

```text
jetty_id
location_id
jetty_name
loading_rate_mtph
daily_capacity_mt
compatible_grades
draft_limit_m
queue_capacity
working_calendar
status
```

Seed:

```text
JETTY_LATI_A
JETTY_SUARAN_A
JETTY_SUARAN_B
JETTY_SAMBARATA_A
JETTY_MAINT_HOLD
```

Create statuses:

- Active
- Blocked
- Maintenance
- Reduced rate

---

## 08_OGV_DEMAND

Purpose: core demand plan.

Columns:

```text
ogv_id
voyage_id
vessel_name
customer_id
vessel_class
eta
etb
etc_target
laycan_start
laycan_end
required_mt
priority
demurrage_rate_usd_per_day
anchorage_location_id
status
```

Seed at least 8–10 OGVs:

```text
MV_PACIFIC_PRIDE
MV_OCEAN_VOYAGER
MV_IRON_ORE
MV_GOLDEN_ORIOLE
MV_NORTH_STAR
MV_OCEAN_BRIGHT
MV_CORAL_SEA
MV_TRITON_STAR
```

Include:

- 3 happy-path OGVs
- 2 tide-risk OGVs
- 1 grade-sequence conflict OGV
- 1 CTS bottleneck OGV
- 1 demurrage-critical OGV
- 1 customer ETA-sensitive OGV

---

## 09_OGV_HATCH_LAYER_SEQUENCE

Purpose: support coal grade sequence / layering board.

Columns:

```text
sequence_id
ogv_id
hatch_no
layer_no
required_sequence_no
coal_grade_id
required_mt
planned_barge_id
planned_jetty_id
planned_cts_id
status
```

Create realistic layered sequences:

```text
MV Pacific Pride:
H1/L1 Agathis HG
H1/L2 Ebony M
H2/L1 Agathis HG
H2/L2 Mahoni-B

MV Ocean Voyager:
H1/L1 Ebony M
H2/L1 Thermal LG
H3/L1 Sungkai M
```

Include conflict case:

- Later layer arriving before earlier layer
- Wrong grade assigned to barge
- Quality hold for planned grade

---

## 10_TUGS

Purpose: tug master data.

Columns:

```text
tug_id
tug_name
owner_org_id
mmsi
horsepower
max_draft_m
speed_loaded_kn
speed_empty_kn
device_id
status
home_location_id
maintenance_status
```

Seed 20–25 tugs.

Use names:

```text
SEA_TITAN_01
WAVE_RUNNER_04
DELTA_PUSH_07
BULK_RUNNER_08
RIVER_HAWK_11
BORNEO_TUG_12
```

Include statuses:

- Active
- Idle
- Breakdown
- Maintenance
- Standby
- Stale signal

---

## 11_BARGES

Purpose: barge master data.

Columns:

```text
barge_id
barge_name
owner_org_id
capacity_mt
draft_empty_m
draft_loaded_m
gps_device_id
status
current_location_id
cargo_grade_id
loaded_mt
```

Seed 35–50 barges.

Include:

- Loaded barges
- Empty barges
- Waiting tide
- Waiting bridge
- Discharging
- Maintenance
- Stale signal

---

## 12_TUG_BARGE_COMPATIBILITY

Purpose: assignment feasibility.

Columns:

```text
compatibility_id
tug_id
barge_id
compatible
reason
max_route_class
notes
```

Create both compatible and incompatible rows.

Constraint examples:

- Horsepower insufficient
- Draft route limit
- Maintenance restriction
- Emergency override allowed

---

## 13_CTS_FLOATING_CRANES

Purpose: support CTS board.

Columns:

```text
cts_id
cts_name
cts_type
location_id
daily_capacity_mt
discharge_rate_mtph
compatible_ogv_class
status
current_ogv_id
next_available_time
```

Seed with public-inspired capacity bands from Berau shipping-device context:

```text
CTS_BULK_BORNEO | conveyor/FTS | 32000 MT/day
CTS_BULK_JAVA | conveyor/FTS | 28000 MT/day
CTS_DERAWAN | FOTP | 28000 MT/day
CTS_BULK_SUMATERA | FTS | 30000 MT/day
CTS_CHLOE | FC | 30000 MT/day
CTS_BLITZ | FC | 20000 MT/day
```

---

## 14_TIDE_WINDOWS

Purpose: constraint testing.

Columns:

```text
tide_window_id
location_id
window_start
window_end
min_water_level_m
max_loaded_draft_m
applicable_route_segment_id
risk_level
source
```

Create 3 days of tide windows.

Include:

- Normal window
- Tight window
- Missed-window scenario
- Low water level scenario

---

## 15_BRIDGE_WINDOWS

Purpose: bridge clearance and crossing windows.

Columns:

```text
bridge_window_id
location_id
window_start
window_end
clearance_m
allowed_asset_class
status
notes
```

Seed:

- Normal crossing
- Restricted crossing
- Closure window
- Emergency opening window

---

## 16_JETTY_LOADING_PLAN

Purpose: pre-seed jetty loading screen.

Columns:

```text
loading_plan_id
jetty_id
barge_id
ogv_id
coal_grade_id
planned_start
planned_end
actual_start
actual_end
planned_mt
loaded_mt
status
delay_reason
```

Statuses:

```text
planned
waiting_barge
loading
loaded
delayed
blocked
quality_hold
```

---

## 17_TUG_BARGE_ASSIGNMENTS

Purpose: dispatcher board.

Columns:

```text
assignment_id
tug_id
barge_id
ogv_id
jetty_id
cts_id
route_id
cargo_grade_id
planned_departure
actual_departure
planned_arrival
predicted_arrival
status
variance_min
exception_id
```

Create scenarios:

- Happy path
- Tug breakdown
- Late departure
- Missed tide
- Reassignment candidate
- Route deviation

---

## 18_CTS_DISCHARGE_PLAN

Purpose: CTS operations board.

Columns:

```text
discharge_plan_id
cts_id
ogv_id
barge_id
coal_grade_id
hatch_no
layer_no
planned_start
actual_start
planned_end
predicted_end
planned_mt
discharged_mt
discharge_rate_mtph
status
delay_reason
```

Statuses:

```text
planned
waiting_barge
discharging
low_rate
completed
breakdown
hold_grade_sequence
```

---

## 19_GPS_AIS_POSITION_EVENTS

Purpose: live map and movement event simulation.

Columns:

```text
position_event_id
asset_id
asset_type
timestamp
latitude
longitude
speed_kn
heading_deg
signal_source
signal_freshness
data_confidence
route_segment_id
geofence_id
event_type
linked_exception_id
```

Asset types:

```text
tug
barge
cts
ogv
```

Event types:

```text
position_ping
entered_geofence
departed_jetty
route_deviation
stale_signal
arrived_anchorage
started_discharge
```

Create sample event tracks:

- Sea-Titan-01 + BG-805-N moving normally
- Wave-04 stale/breakdown
- One barge route deviation
- One OGV anchorage position
- One CTS stationary discharge position

---

## 20_EXCEPTIONS

Purpose: exception center testing.

Columns:

```text
exception_id
exception_type
severity
status
created_at
affected_ogv_id
affected_asset_id
location_id
owner_team
sla_deadline
impact_summary
recommended_action
source
```

Seed types:

```text
TUG_BREAKDOWN
MISSED_TIDE_WINDOW
GRADE_MISMATCH
CTS_LOW_RATE
JETTY_BLOCKED
BARGE_DELAY
ROUTE_DEVIATION
GPS_AIS_STALE
APPROVAL_PENDING
QUALITY_HOLD
```

Include at least:

- 4 critical
- 7 warnings
- 3 approval pending
- 2 SLA breached
- 5 simulation candidates

---

## 21_SIMULATION_SCENARIOS

Purpose: simulation workspace testing.

Columns:

```text
simulation_id
scenario_name
scenario_type
source_exception_id
baseline_plan_id
affected_ogv_id
affected_asset_id
start_time
duration_hours
feasibility_score
baseline_delay_hours
simulated_delay_hours
net_recovery_hours
remaining_risk
status
```

Seed:

```text
SIM_105_A | Tug Reassignment A | tug_breakdown_recovery
SIM_106_B | Tide Recovery Plan | missed_tide
SIM_107_C | CTS Rate Recovery | cts_low_rate
SIM_108_D | Grade Sequence Recovery | grade_mismatch
```

---

## 22_APPROVAL_REQUESTS

Purpose: plan approval screen.

Columns:

```text
approval_id
approval_type
source_simulation_id
source_exception_id
requested_by
required_approver_role
affected_ogv_id
requested_change
operational_impact
status
created_at
sla_deadline
decision_comment
```

Statuses:

```text
pending
approved
rejected
returned
escalated
published
```

Create:

- Pending simulation promotion
- Approved tug reassignment
- Rejected constraint bypass
- Returned grade override

---

## 23_PUBLISHED_PLAN

Purpose: published plan + Gantt.

Columns:

```text
plan_item_id
published_plan_id
plan_version
plan_state
source_approval_id
source_simulation_id
ogv_id
coal_grade_id
hatch_no
layer_no
jetty_id
tug_id
barge_id
cts_id
planned_start
planned_end
actual_start
predicted_end
status
variance_min
linked_exception_id
owner_team
```

Seed:

- LIVE-PLAN-104
- PROPOSED-PLAN-105

Plan item statuses:

```text
on_plan
at_risk
delay
planned
completed
replan_candidate
```

---

## 24_AUDIT_LOGS

Purpose: audit screen and bottom tickers.

Columns:

```text
audit_event_id
timestamp
category
event_type
severity
actor
actor_org
object_type
object_id
action
result
before_value
after_value
reason_comment
correlation_id
```

Seed correlation chain:

```text
EX-0241 created
SIM-105.A created
APR-942 requested
APR-942 approved
LIVE-PLAN-104 published
PI-1042 marked at risk
```

---

## 25_DEVICE_MAPPING

Purpose: GPS/AIS/IoT management.

Columns:

```text
device_id
device_type
asset_id
asset_type
mmsi
source_system
last_signal_time
health_status
confidence_rule
battery_status
```

Include:

- GPS devices on barges
- AIS/GPS hybrid on tugs
- Fixed CTS devices
- Stale device
- Unmapped device
- Duplicate MMSI warning

---

## 26_INTEGRATION_FEEDS

Purpose: integration health screen.

Columns:

```text
feed_id
feed_name
feed_type
source_system
last_sync_time
status
records_received
error_count
data_confidence
notes
```

Feeds:

```text
OGV_SCHEDULE_FEED
GPS_AIS_FEED
TIDE_FEED
BRIDGE_SCHEDULE_FEED
WEATHER_FEED
JETTY_LOADING_FEED
CTS_DISCHARGE_FEED
```

---

## 27_TEST_SCENARIOS_INDEX

Purpose: tell developers which rows support which demo flow.

Columns:

```text
scenario_id
scenario_name
scenario_type
sheets_involved
primary_user_flow
expected_result
screen_coverage
```

Seed scenarios:

```text
SCN_001 Happy Path OGV Loading
SCN_002 Tug Breakdown Recovery
SCN_003 Missed Tide Window
SCN_004 Coal Grade Sequence Violation
SCN_005 CTS Low Rate
SCN_006 Jetty Blockage
SCN_007 GPS/AIS Stale Signal
SCN_008 Approval and Publish Flow
SCN_009 RBAC Restricted Viewer
SCN_010 Published Plan Live Variance
```

---

# 5. Phase-Wise Seed Data Generation Plan

## Phase 1 — Static Master Data Seed

Goal: allow the app shell, admin console, and base planning screens to render.

Generate sheets:

```text
01_ORGANIZATIONS
02_USERS_RBAC
03_LOCATIONS_GEOFENCES
04_ROUTE_SEGMENTS
05_COAL_GRADES
06_STOCKPILES
07_JETTIES
10_TUGS
11_BARGES
12_TUG_BARGE_COMPATIBILITY
13_CTS_FLOATING_CRANES
25_DEVICE_MAPPING
```

Screens supported:

- Admin / Master Data
- Users & RBAC
- Dashboard shell
- Live Map shell
- Tug/Barge Assignment shell

Validation:

- No duplicate IDs
- Every asset has owner org
- Every live asset has device mapping or manual status
- Every jetty has location
- Every route has from/to location

---

## Phase 2 — Demand and Schedule Seed

Goal: allow the planning workflow to operate.

Generate sheets:

```text
08_OGV_DEMAND
09_OGV_HATCH_LAYER_SEQUENCE
14_TIDE_WINDOWS
15_BRIDGE_WINDOWS
16_JETTY_LOADING_PLAN
17_TUG_BARGE_ASSIGNMENTS
18_CTS_DISCHARGE_PLAN
```

Screens supported:

- OGV Demand
- Coal Grade Sequence
- Jetty Loading
- Tug/Barge Assignment
- CTS Operations
- Tide/Bridge Board

Validation:

- Every OGV has laycan and required MT
- Every OGV has hatch/layer sequence
- Every assignment has tug, barge, jetty, CTS, OGV
- Every assigned grade matches OGV sequence unless intentionally seeded as conflict
- Every planned route has tide/bridge windows where applicable

---

## Phase 3 — Happy Path End-to-End Seed

Goal: allow a user to experience a clean plan.

Create one full OGV movement:

```text
MV Ocean Voyager
→ grade sequence valid
→ jetty available
→ tug/barge assigned
→ tide window available
→ CTS available
→ discharge completed
→ plan remains on schedule
```

Screens covered:

- Dashboard
- OGV Demand
- Jetty Loading
- Tug/Barge Assignment
- Tide/Bridge
- CTS
- Published Plan
- Audit Logs

Expected user impression:

> “The system can plan and execute a clean coal transshipment cycle.”

---

## Phase 4 — Constraint Scenario Seed

Goal: allow exception and simulation testing.

Generate scenarios:

### Scenario A — Tug Breakdown

```text
Tug Wave-04 breaks down.
Assigned barge delayed.
OGV Pacific Pride delayed +5h.
Recommended recovery: Sea-Titan-01 reassignment.
```

### Scenario B — Missed Tide Window

```text
Barge BG-702 misses Rantau Delta tide window.
Next feasible window creates +8h delay.
```

### Scenario C — Grade Sequence Violation

```text
Barge carrying Ebony arrives before required Agathis layer.
Coal Grade Sequence screen shows violation.
Recovery holds wrong barge and prioritizes correct grade.
```

### Scenario D — CTS Low Rate

```text
CTS Bulk Java discharges 18% below plan.
Barge queue increases.
OGV completion risk changes to medium/high.
```

### Scenario E — Jetty Blockage

```text
Suaran Jetty B blocked for maintenance.
Loading sequence shifts to Lati/Sambarata alternative.
```

Screens covered:

- Exception Center
- Simulation Workspace
- Plan Approvals
- Published Plan
- Audit Logs

---

## Phase 5 — Live GPS/AIS and Map Seed

Goal: make map and live variance feel real.

Generate:

```text
19_GPS_AIS_POSITION_EVENTS
25_DEVICE_MAPPING
26_INTEGRATION_FEEDS
```

Include:

- Fresh signal asset
- Delayed signal asset
- Stale signal asset
- Route deviation
- Entered geofence
- Departed jetty
- Arrived anchorage
- CTS stationary discharge
- OGV anchorage marker

Screens supported:

- Live Resource Map
- Dashboard data-confidence KPIs
- Exception Center stale signal events
- Published Plan live variance

---

## Phase 6 — Approval, Publish, and Audit Seed

Goal: demonstrate governance.

Generate:

```text
21_SIMULATION_SCENARIOS
22_APPROVAL_REQUESTS
23_PUBLISHED_PLAN
24_AUDIT_LOGS
```

Seed full chain:

```text
Exception created
→ simulation created
→ recovery generated
→ approval requested
→ Berau/ABL approval
→ proposed plan promoted
→ live plan published
→ audit trail visible
```

Screens supported:

- Simulation Workspace
- Plan Approvals
- Published Plan
- Audit Logs

---

## Phase 7 — RBAC and Role Experience Seed

Goal: prove multi-party UI behavior.

For each role, create a demo login:

```text
Berau Scheduler
ABL Dispatcher
Joint Control Tower Manager
Admin
Read-only Viewer
```

Each should see different permissions:

- Berau Scheduler cannot reassign tug directly.
- ABL Dispatcher cannot edit OGV demand.
- Joint Control Tower can coordinate shared action.
- Admin can change master data but not bypass approval.
- Viewer can see published plan only.

---

# 6. Data Quality Rules for Seed Generation

Every sheet must follow these rules:

```text
1. Use stable IDs, not random opaque IDs.
2. Use realistic names.
3. Use consistent timestamps over a 2–3 day planning horizon.
4. Use approximate coordinates around Berau/East Kalimantan.
5. Every foreign key must resolve to a valid master record.
6. Every exception must link to an affected object.
7. Every simulation must link to a source exception or manual scenario.
8. Every approval must link to simulation/exception/plan.
9. Every published plan item must link to OGV, grade, jetty, tug/barge, CTS.
10. Every audit log should link to a business object.
```

Use time windows that make sense:

```text
planning_date = 2026-10-24
planning_horizon = 72 hours
shift_day = 06:00–18:00
shift_night = 18:00–06:00
```

---

# 7. Recommended Row Volumes

| Sheet | Row Count |
|---|---:|
| Organizations | 5–8 |
| Users/RBAC | 8–15 |
| Locations/geofences | 25–40 |
| Route segments | 15–25 |
| Coal grades | 5–8 |
| Stockpiles | 20–40 |
| Jetties | 5–8 |
| OGV demand | 8–12 |
| Hatch/layer sequence | 30–60 |
| Tugs | 20–30 |
| Barges | 40–60 |
| Compatibility | 80–150 |
| CTS | 5–8 |
| Tide windows | 20–40 |
| Bridge windows | 10–20 |
| Loading plan | 25–50 |
| Assignments | 25–50 |
| CTS discharge plan | 20–40 |
| GPS/AIS events | 150–300 |
| Exceptions | 15–30 |
| Simulations | 6–12 |
| Approvals | 8–15 |
| Published plan items | 30–60 |
| Audit logs | 80–150 |
| Device mapping | 60–100 |
| Integration feeds | 8–12 |
| Test scenario index | 8–12 |

---

# 8. Final Handoff Note to Data-Seeding Agent

The seed workbook must be built as a **business simulation dataset**, not as random test rows.

The user testing the app should experience:

1. A real Berau-region coal movement context.
2. Mine/CPP/stockpile/jetty origin logic.
3. Barge movement through river and estuary corridors.
4. OGV demand with laycan and grade sequence.
5. Tug/barge/CTS capacity constraints.
6. Tide and bridge timing constraints.
7. GPS/AIS freshness and route deviation.
8. Operational exceptions.
9. Simulation recovery.
10. Joint Berau–ABL approval.
11. Published plan execution.
12. Audit traceability.

The map reference should be used for naming and route realism: **Lati, Binungan, Sambarata, Suaran, Gurimbang, Berau River, Rantau Delta, and Muara Pantai Transshipment Point** should all appear in the dataset where relevant.
