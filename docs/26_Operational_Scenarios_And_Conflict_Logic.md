# Operational Scenarios and Conflict Logic Map

## Purpose

This document maps the business intent from the scheduling simulation specification against the behavior currently encoded in the codebase. It focuses on OGV demand planning after import, tug and barge assignment, CTS and jetty handling, tide and bridge windows, laycan risk, cargo layer sequence, scenario recovery, and closed-loop use of operational asset availability data.

Terminology note:

- "JETI" in some business conversations is treated as "jetty" in the codebase.
- "Tier bar assignment" is interpreted here as tug and barge assignment, based on the operational clarification.
- "Closed loop" means operational events, telemetry, and asset state data feeding back into plan status, alerts, scenarios, or recovery recommendations.

## Source Areas Reviewed

Business and product documentation:

- `docs/BRD - Schedulling Simulation.docx`
- `docs/00_README_Index.md`
- `docs/02_Planning_Tool_Scope.md`
- `docs/08_Phase_1_Implementation_Spec.md`
- `docs/12_Phase_1_Completion_Evidence.md`
- `docs/14_Phase_2_Implementation_Spec.md`
- `docs/23_Phase_5_Implementation_Spec.md`
- `docs/24_Phase_5_Operator_Runbook.md`
- `docs/berau_abl_seed_data_instructions.md`

Main implementation files:

- `backend/apps/planning/models.py`
- `backend/apps/planning/views.py`
- `backend/apps/masters/models.py`
- `backend/apps/scheduling/models.py`
- `backend/apps/scheduling/services.py`
- `backend/apps/scheduling/recovery_services.py`
- `backend/apps/scheduling/read_models.py`
- `backend/apps/operations/services.py`
- `backend/apps/telemetry/services.py`

## Executive Summary

| Area | Business intent in specification | Current encoded behavior | Gap level |
| --- | --- | --- | --- |
| OGV demand planning | Import OGV demand, laycan, required quantity, grade, layering, source, and schedule it against operational constraints. | OGV and cargo layer rows are imported. If no cargo layers are provided, default layers are created. Plan generation uses imported layer chain values. | Partial |
| Tug assignment | Choose feasible tug considering availability, trip overlap, route, and plan conflicts. | Generator chooses the first available non-overlapping tug where possible. If no clean tug exists, it falls back to the first available tug and validation raises conflicts. | Partial |
| Barge assignment | Choose feasible barge considering capacity, availability, compatibility, cargo, and route. | Barge is not optimized by generator. It is read from imported `CargoLayerStep.planned_barge`. Validation checks missing/unavailable window. | Partial |
| Tug-barge compatibility | Reject incompatible tug and barge pairings. | `TUG_BARGE_INCOMPATIBLE` is implemented through `AssetCompatibilityRule` for `rule_type="tug_barge"`. | Implemented |
| CTS assignment | Assign CTS by compatibility, queue, capacity, and availability. | CTS is read from imported layer. Missing/unavailable CTS is critical. A `CTS_CAPACITY_CONFLICT` warning exists, but it is based on CTS availability windows, not true throughput capacity. | Partial |
| Jetty assignment | Choose feasible source jetty based on grade, source, availability, rate, and barge draft. | Jetty is read from imported layer. Validation checks overlapping jetty windows and blocking status. Grade/jetty compatibility is not enforced in plan generation. | Partial |
| Cargo layer sequence | Enforce required coal loading sequence per OGV. | Imported `sequence_violation` flag creates `LAYER_SEQUENCE_VIOLATION`. Generation orders by `required_sequence_no`. It does not independently calculate grade sequence correctness. | Partial |
| Tide and bridge | Calculate feasible movement windows using route, draft, tide, bridge opening, and clearance. | Validation consumes precomputed `NavigationConstraintCheck` rows with status `MISSED` or `MARGINAL`. It does not compute draft/clearance feasibility from `TideWindow` and `BridgeWindow` during base generation. | Partial |
| Laycan | Sort and prioritize OGVs by laycan and quantify completion/demurrage risk. | Generation filters by plan horizon and sorts by laycan/priority. Recovery scoring calculates laycan completion risk and demurrage proxy. Base validation does not raise a laycan conflict. | Partial |
| Scenario simulation | Model impact of delay, outage, rate change, window change, ETA change, and manual reassignment. | Scenario assumptions and propagation are implemented for these major categories. | Mostly implemented |
| Recovery recommendation | Generate repair options and score them by delay, windows, conflicts, manual changes, health, laycan, and demurrage. | Delay, next-window, resequence, tug/barge swap, and CTS reassignment candidates are implemented and scored. | Mostly implemented |
| Closed-loop asset data | Use live operational events, GPS/AIS, availability, and health to refresh plan and recovery logic. | Events actualize schedule/trip/assignment status. Telemetry creates projections and alerts. Alerts can become delay scenarios. There is no automatic creation of asset unavailability windows from breakdown/health events. | Partial |

## End-to-End Flow Currently Encoded

1. Import OGV demand.
   - `ImportJobViewSet.validate_ogv_demand` validates required demand fields.
   - `_commit_ogv_demand_rows` creates or updates `OGVVoyage`.
   - `_commit_cargo_layers` creates `CargoLayerStep` rows from uploaded `cargo_layers`.
   - If `cargo_layers` is missing, two default cargo layers are created.
   - If `cargo_layers` is present but empty, no cargo layer steps are created.

2. Enter operating windows.
   - `PlanningOverviewViewSet.enter_operating_windows` creates sample asset availability windows, jetty windows, tide windows, bridge windows, and navigation checks.
   - It marks editable plan versions stale so users regenerate or revalidate after source inputs change.

3. Generate a plan.
   - `generate_plan_version` loads cargo layer steps within plan horizon.
   - Steps are ordered by OGV laycan start, OGV priority, voyage id, and required sequence.
   - Barge, jetty, and CTS are taken from the cargo layer row.
   - Tug is selected by `_choose_tug`.
   - Fixed schedule events are created for loading, departure, bridge crossing, tide gate, CTS arrival, and discharge completion.

4. Validate operational conflicts.
   - `_validate_trip` creates active conflicts for layer sequence, tug, barge, CTS, jetty, tug-barge compatibility, tide, and bridge issues.
   - `_reconcile_generated_trip_statuses` sets trip and assignment status based on blocking conflicts.

5. Simulate scenarios.
   - Scenario assumptions apply delays, outages, rate changes, OGV ETA changes, window changes, and manual reassignments.
   - Projection graph edges propagate delays through repeated resources and cargo layer ordering.

6. Recommend recovery.
   - Recovery logic generates deterministic candidates such as delay, next window, resequence, tug/barge swap, and CTS reassignment.
   - Candidates are scored and can be materialized as a scenario.

7. Close the loop from operations.
   - Operational events can actualize schedule events, trip status, assignment status, and loaded quantity.
   - Telemetry pings update latest asset state, projections, and alerts.
   - Certain tracking delay alerts can be converted into scenario assumptions.

## Implemented Conflict Codes

| Conflict code | Implemented trigger | Severity/blocking | Simple example |
| --- | --- | --- | --- |
| `LAYER_SEQUENCE_VIOLATION` | `CargoLayerStep.sequence_violation` is true. | Critical and blocking. | OGV requires Layer 1 AGATHIS then Layer 2 EBONY, but the imported layer row marks Layer 2 as planned before Layer 1. |
| `TUG_UNAVAILABLE` | No tug is assigned, or assigned tug has an overlapping non-available `AssetAvailabilityWindow`. | Critical and blocking. | Trip uses `BER-TUG-08`, but `BER-TUG-08` has a breakdown window overlapping planned departure. |
| `BARGE_UNAVAILABLE` | No barge is assigned, or assigned barge has an overlapping non-available `AssetAvailabilityWindow`. | Critical and blocking. | Layer step names `BRG-KAL-22`, but the barge has a maintenance window during loading. |
| `CTS_UNAVAILABLE` | No CTS is assigned, or assigned CTS master record has `is_available=false`. | Critical and blocking. | Layer step needs `CTS-BORNEO`, but `CTS-BORNEO` is marked unavailable in master data. |
| `CTS_CAPACITY_CONFLICT` | Assigned CTS has an overlapping non-available `AssetAvailabilityWindow`. | Warning and non-blocking. | `CTS-JAVA` has a reduced/maintenance-style availability window overlapping discharge. The code labels this as capacity conflict, although it does not calculate tonnage capacity. |
| `JETTY_OVERLAP` | Assigned jetty has an overlapping `JettyAvailabilityWindow` where status is not `WORKING`. | Warning if reduced or maintenance. Blocking only if status is `BLOCKED`. | `JTY-LATI` is reduced during planned loading, so the trip gets a warning. If `JTY-LATI` is blocked, the conflict blocks the trip. |
| `TUG_BARGE_INCOMPATIBLE` | `AssetCompatibilityRule` has `rule_type="tug_barge"`, tug as left asset, barge as right asset, and `is_compatible=false`. | Critical and blocking. | `BER-TUG-08` is assigned to `BRG-KAL-22`, but compatibility master data marks that pair invalid. |
| `TIDE_WINDOW_MISSED` | A matching `NavigationConstraintCheck` has `constraint_type="tide"` and status `MISSED` or `MARGINAL`. | Critical/blocking for `MISSED`; warning/non-blocking for `MARGINAL`. | Barge reaches the river tide gate at 14:30 but the acceptable tide window closed at 14:00. |
| `BRIDGE_WINDOW_MISSED` | A matching `NavigationConstraintCheck` has `constraint_type="bridge"` and status `MISSED` or `MARGINAL`. | Critical/blocking for `MISSED`; warning/non-blocking for `MARGINAL`. | Tug-barge reaches bridge at 23:00, but bridge opening was 21:00 to 22:00. |

## Scenario Logic by Operational Area

### 1. OGV Demand Import and Missing Demand Detail

Business intent:

- OGV plan should start from vessel demand, customer, laycan, ETA, required quantity, coal quality, source, and loading layer sequence.
- Demand quality should be sufficient to create feasible transshipment trips.

Current implementation:

- Required import columns are `voyage_id`, `vessel_name`, `customer_name`, `laycan_start`, `laycan_end`, `eta`, and `required_mt`.
- Quantity must be positive.
- Optional fields such as `etb`, `etc_target`, `priority`, `demurrage_rate_usd_per_day`, `risk_status`, and `next_blocking_constraint` are accepted.
- Cargo layer data is loaded from `cargo_layers`.
- If `cargo_layers` is missing entirely, the importer creates two default layers with default grades, jetties, barges, and CTS assets.
- If `cargo_layers` is present as an empty list, no layer steps are created.

Conflict and scenario behavior:

- Missing required OGV-level fields stop import validation.
- Missing layer rows do not directly create a conflict. They can result in no schedulable layer steps.
- Default layer creation may hide incomplete business data when `cargo_layers` is absent.

Simple example:

- Input file has MV NORTH STAR with valid laycan and required quantity but no `cargo_layers` key.
- Code creates default Layer 1 and Layer 2 using predefined grade/jetty/barge/CTS values.
- A plan can be generated, but it is based on defaults rather than business-declared cargo sequence.

Spec-vs-code note:

- The specification expects real cargo, grade, source, and sequence data to drive planning.
- The code supports importing that data but does not enforce that real layer details must be present.

### 2. Laycan and OGV Priority

Business intent:

- OGVs should be scheduled by laycan, ETA, priority, demurrage exposure, and customer commitments.
- Late completion should be visible as operational and commercial risk.

Current implementation:

- `OGVVoyage` stores `laycan_start`, `laycan_end`, `eta`, `priority`, and `demurrage_rate_usd_per_day`.
- Plan generation filters cargo layer steps by laycan overlap with the plan horizon.
- Generation orders work by `voyage.laycan_start`, `voyage.priority`, `voyage_id`, and layer sequence.
- Recovery scoring calculates OGV completion risk when projected trip end exceeds `laycan_end`.
- Recovery scoring also calculates a demurrage proxy using laycan overrun or delay beyond a grace threshold.

Conflict and scenario behavior:

- There is no base conflict code such as `LAYCAN_MISSED`.
- Laycan affects ordering and recovery score, not base plan validation status.

Simple example:

- MV TRITON STAR has laycan ending at May 10 18:00.
- A recovery candidate pushes its final projected discharge to May 10 23:00.
- Recovery scores include 300 minutes of OGV completion risk and demurrage proxy if demurrage rate is available.
- The base generated plan does not create a blocking laycan conflict by itself.

Spec-vs-code note:

- Laycan risk is present in recovery economics, but not encoded as a normal scheduling conflict.

### 3. Cargo Layer Sequence

Business intent:

- OGV cargo must respect required coal grade and hatch layering sequence.
- Wrong sequence can cause quality, customer, or vessel loading failures.

Current implementation:

- `CargoLayerStep` stores `required_sequence_no`, hatch, layer, coal grade, source, planned barge, planned jetty, and planned CTS.
- Generator orders trips by required sequence.
- Validation creates `LAYER_SEQUENCE_VIOLATION` only when the imported layer row already has `sequence_violation=true`.

Conflict and scenario behavior:

- The code does not independently compare actual layer order against a business-defined grade stack.
- The conflict is driven by a flag on the layer record.

Simple example:

- Business rule says sequence 1 must be AGATHIS and sequence 2 must be EBONY.
- Imported data marks EBONY as `required_sequence_no=1`, or sets `sequence_violation=true`.
- If `sequence_violation=true`, validation blocks the trip.
- If the wrong grade sequence is present but the flag is false, the generator does not derive the violation by itself.

Spec-vs-code note:

- Sequence enforcement exists as an encoded conflict, but the actual detection is upstream/manual or importer-driven.

### 4. Tug Assignment

Business intent:

- Assign a tug that is available, operationally capable, compatible with the barge, and not double-booked.

Current implementation:

- Generator chooses tug through `_choose_tug`.
- It first tries an active tug with master status `AVAILABLE`, no overlapping non-available asset window, and no overlapping assignment inside the current generation run.
- If no clean tug is found, it falls back to the first tug with status `AVAILABLE`.
- Validation then creates `TUG_UNAVAILABLE` if the assigned tug has an overlapping non-available window.

Conflict and scenario behavior:

- Double-booking is avoided during generation by in-memory assigned windows for tugs.
- Existing plan overlap outside the current generation run is not used by `_choose_tug`.
- Tug availability windows are checked for conflict validation.

Simple example:

- `BER-TUG-08` and `BER-TUG-09` are active.
- Trip A gets `BER-TUG-08` from 08:00 to 18:00.
- Trip B overlaps that window, so generator prefers `BER-TUG-09`.
- If both tugs are blocked by availability windows, generator may still assign the first available-status tug, and validation raises `TUG_UNAVAILABLE`.

Spec-vs-code note:

- Tug assignment is deterministic and simple. It is not a global optimizer.

### 5. Barge Assignment

Business intent:

- Assign a barge based on availability, cargo quantity, draft, route constraints, jetty compatibility, CTS compatibility, and tug compatibility.

Current implementation:

- Generator does not choose a barge from a pool.
- Barge is copied from `CargoLayerStep.planned_barge`.
- Validation raises `BARGE_UNAVAILABLE` if the barge is missing or has an overlapping non-available availability window.
- Tug-barge compatibility is checked separately.

Conflict and scenario behavior:

- Missing planned barge blocks the trip.
- Barge maintenance, breakdown, or unavailable windows block the trip.
- No barge capacity-vs-layer quantity check is implemented.
- No draft-vs-tide or draft-vs-jetty check is calculated in base validation.

Simple example:

- Layer step says planned barge is `BRG-VAL-08`.
- `BRG-VAL-08` has an `AssetAvailabilityWindow` with status `BREAKDOWN` from 06:00 to 20:00.
- Loading is planned 10:00 to 14:00.
- Validation creates `BARGE_UNAVAILABLE`.

Spec-vs-code note:

- Barge conflict detection exists, but barge assignment optimization and capacity logic are not encoded in generation.

### 6. Tug-Barge Compatibility

Business intent:

- Some tugs and barges should not be paired due to bollard pull, size, route, draft, or operating policy.

Current implementation:

- `AssetCompatibilityRule` supports `rule_type="tug_barge"`.
- Validation checks whether the exact tug and barge pair has an incompatible rule.
- Recovery tug/barge swap also checks compatibility before passing hard constraints.

Conflict and scenario behavior:

- Incompatible pairs create a critical blocking conflict.
- Recovery candidates receive penalties if replacement resources create conflicts.

Simple example:

- Rule: `BER-TUG-08` plus `BRG-KAL-22` is not compatible.
- Trip assignment uses that pair.
- Validation creates `TUG_BARGE_INCOMPATIBLE`.

Spec-vs-code note:

- This is one of the more directly implemented business constraints.

### 7. CTS Assignment and CTS Capacity

Business intent:

- Assign CTS based on availability, queue, route compatibility, discharge capacity, and operational condition.

Current implementation:

- Generator does not select CTS from a pool.
- CTS is copied from `CargoLayerStep.planned_cts`.
- Validation creates `CTS_UNAVAILABLE` if CTS is missing or master record has `is_available=false`.
- Validation creates `CTS_CAPACITY_CONFLICT` if the CTS has an overlapping non-available `AssetAvailabilityWindow`.
- Dashboard queue pressure counts CTS usage but does not enforce capacity.
- Scenario rate change can recalculate discharge duration if a CTS rate change assumption is applied.

Conflict and scenario behavior:

- Missing CTS blocks the trip.
- Master-level unavailable CTS blocks the trip.
- CTS availability window overlap is a warning named `CTS_CAPACITY_CONFLICT`.
- No daily capacity or queue capacity calculation is performed for the base plan.

Simple example:

- `CTS-BORNEO` is assigned to two trips on the same day.
- If there is no availability window conflict and master `is_available=true`, base validation does not calculate daily throughput overload.
- Dashboard may show queue pressure, but the trip does not become blocked because of throughput capacity.

Spec-vs-code note:

- The name `CTS_CAPACITY_CONFLICT` is broader than its implementation. Current logic is availability-window based, not capacity-math based.

### 8. Jetty Assignment and Jetty Overlap

Business intent:

- Assign source jetty based on source stockpile, coal grade, loading readiness, loading rate, barge draft, and jetty availability.

Current implementation:

- Generator does not select a jetty from eligible candidates.
- Jetty is copied from `CargoLayerStep.planned_jetty`.
- Validation checks overlapping `JettyAvailabilityWindow`.
- A non-working jetty creates `JETTY_OVERLAP`.
- Blocking occurs only when jetty window status is `BLOCKED`.

Conflict and scenario behavior:

- Reduced or maintenance jetty windows produce warnings.
- Blocked jetty windows produce blocking conflicts.
- Loading rate override is stored on the jetty window but not used by base generation.
- Scenario rate change can recalculate load duration if a jetty rate change assumption is applied.

Simple example:

- `JTY-SUARAN` has status `REDUCED` during planned loading.
- Validation creates a warning `JETTY_OVERLAP`.
- If the status is changed to `BLOCKED`, the same overlap becomes blocking.

Spec-vs-code note:

- Jetty availability checking exists. Grade-to-jetty, source-to-jetty, barge-draft, and loading-rate optimization are not enforced in the base generator.

### 9. Tide Windows

Business intent:

- River movement should be scheduled against tide windows, loaded draft, route segment, and water-level constraints.

Current implementation:

- `TideWindow` stores window times, location, water-level metadata, max loaded draft, route segment, and risk level.
- Base validation does not calculate tide feasibility directly from `TideWindow`.
- Base validation uses `NavigationConstraintCheck` rows that are already marked `CAN_CROSS`, `WAITING`, `MARGINAL`, or `MISSED`.
- Only `MISSED` and `MARGINAL` navigation checks create conflicts.
- Recovery next-window logic searches active non-closed tide windows and can shift a plan to the next valid future window.

Conflict and scenario behavior:

- `MISSED` creates critical blocking `TIDE_WINDOW_MISSED`.
- `MARGINAL` creates warning `TIDE_WINDOW_MISSED`.
- `WAITING` and `CAN_CROSS` do not create conflicts.

Simple example:

- Trip departure implies tide gate ETA of 16:30.
- Precomputed navigation check says tide status is `MISSED`.
- Validation creates blocking `TIDE_WINDOW_MISSED`.
- Recovery may propose delaying to the next open tide window.

Spec-vs-code note:

- Tide windows are modeled, but base feasibility depends on precomputed navigation checks rather than direct draft and water-level calculation.

### 10. Bridge Windows

Business intent:

- Bridge passage should be scheduled against bridge opening windows, clearance, allowed asset class, and route timing.

Current implementation:

- `BridgeWindow` stores window times, bridge location, clearance metadata, allowed asset class, and status.
- Base validation does not calculate bridge feasibility directly from `BridgeWindow`.
- Base validation uses `NavigationConstraintCheck` rows.
- Recovery next-window logic searches active bridge windows that are not closed and can shift a plan to the next bridge opening.

Conflict and scenario behavior:

- `MISSED` creates critical blocking `BRIDGE_WINDOW_MISSED`.
- `MARGINAL` creates warning `BRIDGE_WINDOW_MISSED`.
- Bridge `WAITING` and `CAN_CROSS` checks do not create conflicts.

Simple example:

- Tug-barge planned bridge crossing is 23:30.
- Precomputed bridge check says the crossing missed the available bridge opening.
- Validation creates blocking `BRIDGE_WINDOW_MISSED`.
- Recovery may propose waiting for the next bridge opening.

Spec-vs-code note:

- Bridge data is modeled, but clearance and allowed asset class are not directly evaluated during base generation.

### 11. Asset Outage Scenario

Business intent:

- When a tug, barge, CTS, or other asset becomes unavailable, the plan should show downstream delay and recovery options.

Current implementation:

- Scenario assumption `ASSET_OUTAGE` delays affected trips when the outage overlaps the baseline assignment.
- The projection graph then propagates delay to downstream trips sharing resources or sequence dependencies.
- Recovery can recommend delay, next window, resequence, tug/barge swap, or CTS reassignment.

Conflict and scenario behavior:

- Scenario outage does not automatically create base `AssetAvailabilityWindow`.
- It affects projected schedule state and impact assessments.

Simple example:

- `BRG-VAL-08` outage starts 09:00 and ends 15:00.
- A trip using `BRG-VAL-08` was planned 10:00 to 14:00.
- Scenario shifts that trip until the outage ends.
- Later trips sharing the same barge or dependent cargo sequence are pushed later.

Spec-vs-code note:

- Outage simulation exists. Automatic conversion of a confirmed breakdown event into a future unavailability window was not found.

### 12. Rate Change Scenario

Business intent:

- Reduced jetty or CTS rates should affect loading/discharge duration and downstream completion risk.

Current implementation:

- Scenario assumption `RATE_CHANGE` can target jetty or CTS.
- For jetty, load duration is recalculated from planned quantity and rate.
- For CTS, discharge duration is recalculated from planned quantity and rate.
- Base generated events use fixed default event offsets and do not calculate durations from rates unless scenario logic applies.

Simple example:

- Jetty loading rate drops from 2,000 tph to 1,000 tph for a 10,000 mt layer.
- Scenario recalculates loading span from about 5 hours to about 10 hours.
- Downstream trips may shift because the projected graph propagates the longer duration.

Spec-vs-code note:

- Rate-based duration is implemented in scenario projection, not in the first-pass generator.

### 13. OGV ETA Change Scenario

Business intent:

- If OGV ETA changes, cargo sequence and transshipment timing should move with the vessel readiness.

Current implementation:

- Scenario assumption `OGV_ETA_CHANGE` shifts the first trip for a voyage when the projected ETA is later than baseline ETA.
- Delay then propagates through cargo layer and resource edges.

Simple example:

- MV PACIFIC PRIDE ETA changes from 08:00 to 14:00.
- First trip for that voyage shifts by 6 hours.
- Later layers for the same OGV shift through cargo layer sequence dependency.

Spec-vs-code note:

- ETA delay is modeled. Early ETA acceleration is not emphasized in the same way as delay.

### 14. Manual Reassignment Scenario

Business intent:

- Operators should be able to test changing tug, barge, or CTS assignment before promoting changes.

Current implementation:

- Scenario assumption `MANUAL_REASSIGNMENT` can replace projected tug, barge, or CTS resource codes.
- Scenario projection rebuilds resource edges after reassignment.
- Recovery recommendations for tug/barge swap or CTS reassignment materialize as manual reassignment assumptions.

Simple example:

- Current trip uses `CTS-BORNEO`.
- Operator tests reassignment to `CTS-JAVA`.
- Scenario rebuilds CTS resource conflicts and scores the impact.

Spec-vs-code note:

- Reassignment is scenario-first. It does not directly mutate the active plan until governance/promotion flow is used.

### 15. Resequencing Scenario

Business intent:

- When one trip is disrupted, operators may resequence nearby trips to reduce delay and missed windows.

Current implementation:

- Recovery can create a resequence candidate by swapping the disrupted assignment with the next assignment in sequence.
- It applies a resequence delay and records an `ogv_laycan_guardrail` evidence label.

Conflict and scenario behavior:

- Resequence candidates are scored, including delay, missed windows, resource conflicts, laycan risk, and demurrage proxy.
- The laycan guardrail is evidence and scoring context, not a hard base conflict.

Simple example:

- Trip 4 is blocked by barge availability.
- Trip 5 is ready and uses different resources.
- Recovery proposes moving Trip 5 ahead of Trip 4 if score is better than waiting.

Spec-vs-code note:

- Resequencing exists in recovery, but it is a deterministic local swap rather than a broad optimizer.

## Closed-Loop Logic From Asset Availability and Operations

### What Exists

Operational event loop:

- `ingest_operational_event` ingests events from feeds/devices/manual sources.
- Events are matched to schedule events, trips, and assignments.
- Trust policy decides whether an event can be auto-confirmed.
- Confirmed events actualize schedule events and update trip or assignment status.
- Loading completion can update loaded quantity.

Telemetry loop:

- `ingest_position_ping` records latest asset position and freshness.
- It estimates ETA to relevant schedule events such as jetty departure, bridge crossing, tide gate, and CTS arrival.
- It creates projection records and alerts for departure delay, ETA risk, stale signal, route deviation, and dwell.
- Positive delay tracking alerts can be converted into scenario assumptions.

Recovery loop:

- Recovery snapshots combine plan conflicts, projected status, resource state, tracking alerts, and operational events.
- Deterministic repair candidates are generated and scored.
- Accepted recommendations become scenarios, not direct active-plan changes.

Availability-window loop:

- Base validation uses `AssetAvailabilityWindow` for tug and barge unavailability.
- CTS availability window overlap creates a warning.
- Operator-entered windows mark existing draft/generated plans stale.

### What Does Not Exist or Is Limited

| Closed-loop expectation | Current state |
| --- | --- |
| Confirmed breakdown automatically creates future `AssetAvailabilityWindow`. | Not found. Breakdown/high-impact events require review and can feed recovery context, but no automatic availability-window mutation was identified. |
| GPS/AIS stale signal automatically marks asset unavailable in planning. | Not found. Stale signal creates alert; it does not directly change master status or availability windows. |
| Telemetry ETA risk directly mutates trip times in active plan. | Not found. ETA risk creates projections/alerts. Some delay alerts can become scenarios. |
| Accepted recovery recommendation directly edits active assignment. | Not direct. Recommendation materializes as a scenario; promotion/governance flow is separate. |
| Recovery replacement asset search checks `AssetAvailabilityWindow`. | Limited. Replacement tug/barge/CTS search uses master status, compatibility, and assignment overlap, but does not appear to check availability windows directly. |
| Plan generator recomputes all feasibility after operating windows are entered. | Partial. Entering windows marks plan versions stale and creates sample checks; regeneration/validation is still required. |

Simple closed-loop example:

1. AIS ping shows `BRG-VAL-08` will reach the bridge 45 minutes late.
2. Telemetry creates an ETA risk or delay alert.
3. If the alert is convertible and has positive variance, it can become a `TRIP_DELAY` scenario assumption.
4. Scenario projection shifts the affected trip and downstream dependencies.
5. Recovery recommends delay, next window, resequence, tug/barge swap, or CTS reassignment.
6. The active plan is not changed until the scenario/recommendation is promoted through the workflow.

## Recovery Recommendation Logic

Recovery candidates currently implemented:

| Candidate | What it does | Main checks |
| --- | --- | --- |
| Delay trip | Holds the disrupted trip by a calculated delay. | Missed tide/bridge windows, laycan risk, demurrage proxy. |
| Next window | Shifts the trip to the next available tide and/or bridge window. | Requires future non-closed tide/bridge windows where applicable. |
| Resequence | Swaps disrupted assignment with the next trip in sequence. | Resource conflicts, delay, laycan guardrail evidence. |
| Tug/barge swap | Chooses replacement tug and/or barge. | Tug-barge compatibility and overlapping assignments. |
| CTS reassignment | Chooses a different available CTS. | CTS master availability and overlapping assignments. |

Scoring dimensions:

- Delay minutes
- Missed windows
- Resource conflicts
- Manual change complexity
- Health risk
- OGV completion risk against laycan
- Demurrage proxy
- Hard-constraint pass/fail

Important behavior:

- A recommendation can target a different operational lever from the source exception. For example, a `BARGE_UNAVAILABLE` source conflict can still rank a CTS reassignment highest if the scoring model finds it lowers projected risk in the snapshot.
- This behavior is documented in the Phase 5 runbook and should be treated as an intentionally modeled recommendation pattern, not necessarily a full physical repair.

Simple example:

- Source issue: `BARGE_UNAVAILABLE` for MV PACIFIC PRIDE.
- Candidate A: Delay trip 90 minutes.
- Candidate B: Wait for next tide/bridge window.
- Candidate C: Swap tug/barge if compatible replacement exists.
- Candidate D: Reassign CTS if it reduces projected downstream queue risk.
- The top score may be Candidate D even though the original conflict mentions a barge, because scoring evaluates plan-wide impact rather than only one physical cause.

## Business Logic Present in Spec But Missing or Partial in Code

| Business logic or control | Specification intent | Current implementation status |
| --- | --- | --- |
| Global optimal assignment of barges, tugs, jetties, CTS, and OGV sequences | Calculate optimal assignment across fleet, OGV demand, environment, and operational constraints. | Partial. Generator is deterministic and simple. It does not run a global optimizer. |
| Barge pool selection | Select best barge by capacity, draft, cargo, route, availability, and compatibility. | Missing in base generator. Planned barge comes from imported layer. |
| CTS pool selection | Select CTS by compatibility, route, queue, capacity, and availability. | Missing in base generator. Planned CTS comes from imported layer. Recovery can propose CTS reassignment. |
| Jetty/source candidate selection | Choose source jetty based on stockpile, grade, readiness, loading rate, barge draft, and customer priority. | Missing in base generator. Planned jetty comes from imported layer. |
| Grade-to-jetty enforcement | Prevent grade from loading at invalid jetty/source. | Not enforced in validation, although compatibility rule model has `grade_jetty`. |
| Barge-to-jetty enforcement | Prevent invalid barge/jetty combination. | Not enforced in validation, although compatibility rule model has `barge_jetty`. |
| CTS-route enforcement | Prevent invalid CTS/route combination. | Not enforced in validation, although compatibility rule model has `cts_route`. |
| Barge capacity check | Ensure required layer quantity fits assigned barge capacity. | Not found in validation. |
| Stockpile/source availability | Ensure source stockpile has available quantity and release status. | Data model exists in masters, but generator/validator does not appear to enforce stockpile quantity availability. |
| Quality hold and QC release | Block/release cargo based on coal quality readiness. | Not found as an automated scheduling constraint beyond imported sequence/blocking flags. |
| Loading duration from jetty rate in base plan | Compute load start/end using planned quantity and jetty rate. | Partial. Scenario rate change supports rate math. Base generator uses fixed offsets/default spans. |
| CTS daily capacity throughput | Detect CTS over-capacity by tonnage/day or queue throughput. | Not implemented as true capacity math. `CTS_CAPACITY_CONFLICT` is availability-window based. |
| Tide draft calculation | Compare loaded draft with tide water level and max loaded draft. | Tide metadata is stored but base validation uses precomputed navigation checks. |
| Bridge clearance calculation | Compare asset class/draft/clearance against bridge rules. | Bridge metadata is stored but base validation uses precomputed navigation checks. |
| Laycan conflict in base validation | Block or warn when projected completion exceeds laycan. | Not a base conflict code. Present in recovery/scenario scoring. |
| Automatic operational breakdown to availability window | Convert confirmed breakdown into unavailable asset window. | Not found. |
| Automatic telemetry ETA to active schedule mutation | Update active plan dates directly from GPS/AIS ETA. | Not found. Telemetry creates projections/alerts and can feed scenarios. |
| Recovery replacement search using availability windows | Avoid replacement assets that have non-available windows. | Partial. Replacement uses master status and assignment overlap, not direct availability-window checks. |
| Full physical repair semantics for every recommendation | Recommendation should directly fix the same root cause. | Partial by design. Scoring may recommend an indirect operational lever that improves plan KPIs. |

## Simple Conflict Scenario Catalog

### Scenario A: Barge Missing After Demand Import

Data:

- OGV: MV NORTH STAR
- Layer: Sequence 1, 8,000 mt EBONY
- Planned barge: empty

Code result:

- Trip is generated from the layer.
- Assignment has no barge.
- Validation creates `BARGE_UNAVAILABLE`.
- Trip becomes blocked.

Business meaning:

- The OGV demand cannot be operationalized because the physical barge chain is incomplete.

### Scenario B: Barge Breakdown During Planned Loading

Data:

- Planned barge: `BRG-VAL-08`
- Loading: 10:00 to 14:00
- Asset availability: `BRG-VAL-08` `BREAKDOWN` from 09:00 to 15:00

Code result:

- Validation creates critical blocking `BARGE_UNAVAILABLE`.
- Recovery may recommend delay, next window, resequence, or tug/barge swap.

Business meaning:

- Cargo cannot move on the declared barge during the planned loading window.

### Scenario C: Tug Double-Booked During Generation

Data:

- Tug pool: `BER-TUG-08`, `BER-TUG-09`
- Trip 1 uses `BER-TUG-08` 08:00 to 18:00
- Trip 2 overlaps 12:00 to 22:00

Code result:

- Generator avoids reusing `BER-TUG-08` for Trip 2 within the same generation run.
- If `BER-TUG-09` is clean, Trip 2 gets `BER-TUG-09`.
- If no clean tug exists, fallback may assign an available-status tug and validation can create `TUG_UNAVAILABLE`.

Business meaning:

- Tug assignment is conflict-aware but not globally optimized.

### Scenario D: Tug-Barge Incompatible

Data:

- Tug: `BER-TUG-08`
- Barge: `BRG-KAL-22`
- Compatibility rule: incompatible

Code result:

- Validation creates critical blocking `TUG_BARGE_INCOMPATIBLE`.

Business meaning:

- The physical chain is invalid even if both assets are individually available.

### Scenario E: Jetty Reduced, Not Blocked

Data:

- Jetty: `JTY-LATI`
- Planned loading: 10:00 to 14:00
- Jetty window: `REDUCED` 08:00 to 16:00

Code result:

- Validation creates warning `JETTY_OVERLAP`.
- Trip is not blocked unless the status is `BLOCKED`.

Business meaning:

- The plan carries risk or operational attention, but the system does not stop execution.

### Scenario F: Jetty Blocked

Data:

- Jetty: `JTY-LATI`
- Planned loading: 10:00 to 14:00
- Jetty window: `BLOCKED` 08:00 to 16:00

Code result:

- Validation creates blocking `JETTY_OVERLAP`.
- Trip becomes blocked.

Business meaning:

- The declared loading point cannot be used.

### Scenario G: CTS Master Unavailable

Data:

- Planned CTS: `CTS-BORNEO`
- CTS master: `is_available=false`

Code result:

- Validation creates critical blocking `CTS_UNAVAILABLE`.

Business meaning:

- The receiving/discharging asset is not available for the operation.

### Scenario H: CTS Capacity Warning

Data:

- Planned CTS: `CTS-JAVA`
- CTS availability window overlaps trip and is not `AVAILABLE`

Code result:

- Validation creates warning `CTS_CAPACITY_CONFLICT`.

Business meaning:

- The system reports CTS risk, but the current check is availability-window based, not true daily capacity math.

### Scenario I: Tide Missed

Data:

- Trip planned tide gate time: 16:30
- Matching navigation check: `constraint_type=tide`, `status=MISSED`

Code result:

- Validation creates critical blocking `TIDE_WINDOW_MISSED`.
- Assignment status can become `WAITING_TIDE`.

Business meaning:

- River passage cannot proceed in the planned window.

### Scenario J: Bridge Marginal

Data:

- Trip planned bridge crossing: 21:50
- Bridge opening closes at 22:00
- Matching navigation check: `constraint_type=bridge`, `status=MARGINAL`

Code result:

- Validation creates warning `BRIDGE_WINDOW_MISSED`.
- It is not blocking because status is marginal, not missed.

Business meaning:

- There is little operational margin. The plan can continue, but dispatch should watch it.

### Scenario K: Wrong Cargo Layer Sequence

Data:

- Required layer order: Sequence 1 then Sequence 2
- Imported layer has `sequence_violation=true`

Code result:

- Validation creates critical blocking `LAYER_SEQUENCE_VIOLATION`.

Business meaning:

- Cargo loading sequence is invalid for the OGV demand plan.

### Scenario L: OGV Laycan Risk in Recovery

Data:

- Laycan end: 18:00
- Recovery projection ends final operation at 22:00

Code result:

- Recovery scoring includes 240 minutes of OGV completion risk.
- Demurrage proxy can be calculated if demurrage rate is available.
- No base `LAYCAN_MISSED` conflict is created.

Business meaning:

- The commercial risk is visible in recovery ranking, but not as a standard validation conflict.

### Scenario M: Telemetry Delay Becomes Scenario

Data:

- GPS/AIS projection shows departure or gate ETA 60 minutes late.
- Tracking alert is created with positive ETA variance.

Code result:

- Eligible delay alert can be converted to a `TRIP_DELAY` scenario.
- Scenario projection shifts affected trip and dependencies.
- Recovery scores possible repair candidates.

Business meaning:

- Live tracking can influence planning through scenarios rather than direct mutation of the active plan.

### Scenario N: Confirmed Loading Complete Updates Quantity

Data:

- Operational event: jetty loading completed
- Confirmed quantity: 7,800 mt
- Planned quantity: 8,000 mt

Code result:

- Confirmed event actualizes the schedule event.
- Trip status can move to transit/completed depending on event type.
- `loaded_quantity_mt` can be updated from confirmed quantity.

Business meaning:

- Actual execution data closes the loop into operational status and quantity visibility.

## Practical Reading of Current System Behavior

The current stack is strongest at:

- Representing OGV demand and cargo layer steps.
- Producing a deterministic schedule from declared layer chains.
- Detecting important hard conflicts for layer sequence, asset unavailability, tug-barge incompatibility, jetty block, and navigation misses.
- Modeling scenario impact and scoring recovery options.
- Feeding live operations and telemetry into actualization, alerts, scenarios, and recovery context.

The current stack is not yet a full optimizer for:

- Selecting the best barge, jetty, or CTS from business eligibility pools.
- Calculating capacity-driven schedule durations in the base generator.
- Enforcing stockpile, grade, route, draft, clearance, and throughput constraints directly from master data.
- Automatically turning all live asset health and breakdown signals into future availability constraints.

## Recommended Next Implementation Targets

1. Add explicit base validation conflict for laycan overrun, such as `LAYCAN_RISK` or `LAYCAN_MISSED`.
2. Implement true CTS capacity calculation using daily capacity, assigned tonnage, discharge duration, and queue overlap.
3. Enforce `grade_jetty`, `barge_jetty`, and `cts_route` compatibility rule types during validation.
4. Add barge capacity validation against layer quantity.
5. Calculate tide and bridge feasibility directly from route timing, draft, bridge clearance, allowed asset class, and windows.
6. Use jetty loading rate and CTS discharge rate in base plan generation instead of fixed event offsets.
7. Convert confirmed breakdown or maintenance operational events into reviewed `AssetAvailabilityWindow` records.
8. Make recovery replacement search reject assets with overlapping non-available availability windows.
9. Add a strict import mode that blocks OGV demand with missing cargo layers instead of creating defaults.
10. Add source/stockpile quantity and QC-release checks before trip generation.

