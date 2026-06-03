# ABL Proposal Fact Verification - Operating Scope and Data Access - Question List

Source: `F:\ocean\docs\proposal\ABL_Google_Form_Definition.json`
Total questions: 113


## 1. Operating Scope, Ownership and Control Boundaries

1.1. For each operating activity in the Berau-to-OGV flow, what is ABL's current role?
1.2. What is ABL's decision authority for each operating layer in the proposed ABL-governed planning scope?
1.3. Which Berau-side functions create or modify the demand plan, source-jetty plan, coal quality plan, and OGV loading priority?
1.4. What formal handoff points exist between Berau and ABL from cargo plan release to OGV departure?
1.5. Which locations are in scope for the current proposal: mine/CPP/stockpile names, jetties, river routes, transshipment points, anchorage zones, OGV loading areas?
1.6. Are Lati, Binungan, Sambarata and Suaran/KM locations part of the active operating scope for this proposal?
1.7. What entities own the operational KPIs for jetty productivity, fleet utilisation, CTS productivity, OGV completion, demurrage risk, flow time and asset productivity?

## 2. Demand, OGV Programme and Delivery Commitments

2.1. What demand fields does ABL receive today for each OGV or shipment: vessel name, voyage, buyer/customer if used, quantity, coal grade, laycan, ETA/ETB, priority, source jetty, hatch plan, layering sequence, completion target?
2.2. How often is the OGV programme updated: monthly, weekly, daily, intra-day, or event-driven?
2.3. What is the current change notification process when Berau changes source jetty, buyer requirement, coal quality, quantity, or OGV timing?
2.4. Are OGV hatch plans and layering sequences available before barge assignment, during execution, or only at OGV loading stage?
2.5. What fields identify shipment priority or delivery urgency in the current plan?
2.6. How is demurrage risk currently calculated or recognized: by date threshold, laycan breach, OGV waiting time, manual escalation, or no formal calculation?
2.7. What are typical OGV cargo sizes and typical barge-load counts per OGV by cargo type or barge size?

## 3. Mine, CPP, Stockpile, Cargo Quality and Blending

3.1. What cargo-readiness levels are visible to ABL today: mine production readiness, CPP output, stockpile quantity, jetty availability, blend plan, sample status, quality release, or ready-to-load status?
3.2. Which coal quality parameters are used operationally for scheduling or assignment: CV, ash, moisture, sulphur, fines, contamination, brand/grade, buyer spec, other?
3.3. Does ABL receive the blend recipe or only the final required grade/brand for execution?
3.4. When one OGV uses cargo from multiple jetties or grades, how is the required loading sequence communicated to ABL?
3.5. How is quality-locking handled when a barge has been assigned to a buyer/OGV/grade combination?
3.6. Are rain, moisture change, stockpile age, drainage, rehandling, or contamination events captured as operational constraints today?
3.7. What are the current status values for cargo quality or release: planned, sampled, released, blocked, disputed, under recheck, ready-to-load, other?
3.8. Are blocked/disputed quantities visible in the operating plan before tug-barge dispatch?
3.9. What is the normal lead time between quality release and physical BLC/jetty loading?

## 4. Port, Jetty and BLC Operations

4.1. Which jetties and BLCs are currently used for the operation, and what are their operating codes/names?
4.2. What is the confirmed BLC capacity by loading point, and is 2,000 tph the correct planning value for the main BLC?
4.3. What is the typical barge loading duration by jetty, cargo type, and barge size?
4.4. What is the typical pre-loading waiting time at each jetty, and how often does it exceed the planning assumption?
4.5. What operational statuses exist for a jetty/BLC: available, queueing, loading, breakdown, maintenance, no cargo, weather hold, survey hold, other?
4.6. Is jetty queue currently captured as a structured queue with vessel/barge sequence, or managed informally by field coordination?
4.7. What data is available for BLC downtime, loader rate, loading start/end, queue arrival, queue release, and loading completion?
4.8. Are survey or inspection readiness checks required before jetty loading, or are they relevant only at OGV loading/closure?

## 5. Tug-Barge Fleet, Route Cycle and Operational Availability

5.1. What is the current owned and chartered fleet count by asset class: tug, barge, self-propelled barge, assist tug, support craft?
5.2. What vessel identifiers are used across systems: asset code, AIS MMSI, IMO, tug/barge name, Spinergie ID, internal ERP ID?
5.3. What tug HP range and barge capacity range should be used for planning?
5.4. What are the standard route cycle components currently tracked: assignment time, departure, arrival jetty, queue start, loading start/end, departure loaded, arrival CTS/OGV, discharge start/end, return start, available time?
5.5. Are loaded sailing time and empty return time separately measured today?
5.6. What are the planning cycle-time ranges for each active route, including near, medium and far jetties?
5.7. Are the indicative assumptions valid: nearby movement around 9-12 hours plus loading/unloading, farthest movement around 48-70 hours?
5.8. How is mid-route reassignment recorded when a tug-barge is redirected to another jetty, OGV or buyer?
5.9. What makes a tug-barge asset operationally available for next assignment: discharge complete, return started, arrived safe point, empty at jetty, crew ready, maintenance clear, planner release, other?
5.10. Are breakdown, maintenance, crew availability and inspection status captured in a structured way?

## 6. Tide, Bridge, River Navigation and Route-Window Constraints

6.1. What tide data source is used for dispatch planning, and what format is available: PDF/table, Excel, API, website, internal system, manual update?
6.2. What bridge-window data source is used, and is it available as structured time windows?
6.3. Which river segments, bridges, draft restrictions, choke points, and safe waiting points must be represented in the schedule?
6.4. What vessel, barge, cargo, tide-height or draft rules determine whether a movement is feasible within a route window?
6.5. How are grounding or low-water events currently recorded: delay code, operational exception, route-window miss, informal field report, or safety incident where applicable?
6.6. What data exists for historical missed tide windows, bridge waits, grounding/low-water events, traffic congestion and weather-related stoppage?
6.7. What are the current field rules for intentional waiting at a safe point before a tide/bridge bottleneck?
6.8. Are speed adjustments used operationally to align with tide/bridge windows, and are they recorded anywhere?

## 7. CTS, Floating Crane, Transshipment and OGV Loading

7.1. Which CTS, FTS and floating crane assets are in scope, and what are their operating names/codes?
7.2. What is the confirmed daily capacity or discharge rate for each CTS/floating crane, and is 55,000 t/day a valid peak planning value?
7.3. Which capability attributes matter for assignment: conveyor, crane-and-grab, sampler, metal detector, rotating chute, blending capability, hatch reach, weather limit, other?
7.4. Is CTS/floating crane queue captured as a structured queue, and does it link to OGV/hatch sequence?
7.5. What event timestamps are captured for CTS execution: barge arrived, discharge start, discharge end, CTS downtime, hatch change, OGV loading complete?
7.6. How are CTS downtime and productivity losses categorized today?
7.7. Is OGV loading progress tracked by hatch, by cargo grade, by barge, by tonnage, or only at total-vessel level?
7.8. What happens operationally if barge arrival sequence conflicts with hatch/layering plan?

## 8. Survey, Certification and Shipment Closure

8.1. Which survey milestones are mandatory for the operation: hold inspection, initial draft survey, sampling, barge-wise quantity record, loading supervision, final draft survey, certificate of weight, certificate of quality, statement of facts?
8.2. Which survey milestones can block loading, OGV completion or departure?
8.3. Where are survey milestone statuses recorded today: Excel, surveyor report, email, Spinergie/SOF, operational database, WhatsApp, other?
8.4. Are certificate dates/times and document closure dates/times available as data fields?
8.5. Who confirms shipment closure and OGV departure readiness?
8.6. Are operational exceptions recorded before statement-of-facts closure?

## 9. Spinergie, AIS/GPS and Live Movement Evidence: Technical Verification

9.1. Which Spinergie/AIS capabilities are actively used for scheduling or operating visibility in the Berau-ABL flow?
9.2. What is the current method for accessing Spinergie/AIS/GPS data for the ABL operating scope?
9.3. If programmatic access or export exists, what interface type is available?
9.4. What authentication or access-control method is used or available for data sharing?
9.5. What data formats can be shared for the current build: JSON, CSV, Excel, XML, PDF report, database view, Parquet or other?
9.6. What is the available refresh cadence or data latency for position/movement evidence?
9.7. What fields are available in each AIS/GPS or position record: timestamp, latitude, longitude, speed, heading, course, MMSI, asset name, tug/barge link, source system ID, geofence, status, destination, ETA?
9.8. Are geofence/zone events available directly from Spinergie/AIS exports, or must the platform generate candidate geofence events from raw coordinates?
9.9. Can Spinergie/AIS/GPS exports be joined to Excel schedule data through a stable key such as asset code, MMSI, trip ID, OGV name, jetty code or timestamp range?
9.10. What data-sharing approach is feasible for the current build phase?

## 10. Excel, Master Data and Operational Report Data

10.1. What Excel planning files are currently used, and what is the owner, update frequency and file structure for each?
10.2. Which master-data lists already exist: jetties, routes, tug assets, barges, CTS assets, OGVs, cargo grades, buyers, reason codes, tide/bridge windows?
10.3. Are asset master IDs consistent across Excel, Spinergie, AIS, operational reports and finance/charter records?
10.4. What fields define route master data: origin, destination, distance, standard loaded time, standard empty time, tide dependency, bridge dependency, draft restriction, safe waiting point?
10.5. Are delay and waiting reason codes standardized today?
10.6. What historical operational reports are available for calibration of waiting time, cycle time and productivity?
10.7. Can operational reports be shared as structured data rather than PDF/image/manual notes?
10.8. What data fields are required to calculate planned-vs-actual at trip level?

## 11. Event Confirmation and Operating Truth

11.1. Which operating states are valid for a tug-barge trip: planned, assigned, en route empty, arrived jetty, waiting jetty, loading, loaded, en route loaded, waiting tide/bridge, arrived CTS/OGV, discharging, discharged, returning, available, breakdown, maintenance, reassigned, cancelled?
11.2. For each operating state, what is the current evidence or confirmation source?
11.3. What event timestamps are mandatory for operational control versus only useful for analytics?
11.4. What freshness, confidence or exception rule should require planner confirmation before an inferred event changes schedule status?
11.5. How should conflicting signals be resolved, for example AIS/GPS suggests arrival but field confirmation says the asset is still waiting outside the jetty?
11.6. Which exception events require immediate alerting: missed tide, bridge wait, low-water/grounding risk, breakdown, cargo hold, OGV delay, CTS queue, survey hold, reassignment?
11.7. How structured are current WhatsApp/voice updates for conversion into event timestamps and reason codes?

## 12. Third-Party Charter Fleet and Capacity Planning

12.1. How many tugboats and barges are owned versus chartered in the operating scope?
12.2. What is the normal process for requesting, inspecting, approving and mobilizing a charter tug?
12.3. Is one week a reliable planning assumption for charter tug readiness?
12.4. What statuses exist for charter assets: requested, vendor confirmed, inspection pending, inspection passed, mobilizing, ready, rejected, unavailable?
12.5. Which charter constraints are considered in dispatch or recovery decisions today?
12.6. Are third-party assets tracked in the same planning files and AIS systems as owned assets?

## 13. Governance, KPIs, Decision Rights and Adoption

13.1. Who approves source-jetty changes, cargo reassignment, tug-barge reassignment, intentional waiting, route deviation, and charter mobilization?
13.2. What is the current escalation path for OGV delay, quality hold, grounding risk, CTS congestion and fleet shortage?
13.3. Which KPIs are currently measured by ABL, and which are measured by Berau or other parties?
13.4. What formulas are used for fleet productive time, floating crane productive time, waiting time, idle time, OGV delay and demurrage risk?
13.5. Are fleet productive time around 55-60% and floating crane productive time around 35% current accepted baselines?
13.6. What delay attribution categories are acceptable for operational reporting: jetty queue, cargo hold, tide wait, bridge wait, CTS queue, OGV delay, survey, breakdown, instruction wait, weather, other?
13.7. For each user or stakeholder group, what is the expected role in the ABL-governed platform or handoff process?
13.8. What language, device, connectivity and access constraints exist for field users?
13.9. What operating process changes are already acceptable: standard event reporting, reason codes, approval workflow, planned-vs-actual review, daily control-tower meeting?

## 14. Validation Inputs Requested

14.1. Latest OGV programme and historical OGV schedule changes.
14.2. Current Excel scheduling files used by ABL.
14.3. Tug, barge, CTS and jetty master data.
14.4. Route and cycle-time assumptions.
14.5. Tide, bridge and draft restriction data.
14.6. Spinergie/AIS sample export and data dictionary.
14.7. Historical operational reports and delay logs.
14.8. Survey and statement-of-facts sample documents.
14.9. Current reason codes, status codes and event definitions.
14.10. Integration/security constraints for confirmed operational data-sharing methods.
