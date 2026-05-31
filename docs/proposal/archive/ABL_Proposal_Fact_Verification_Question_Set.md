# ABL Proposal Fact Verification Question Set

**Purpose:**  
This questionnaire converts the factual gaps between **Set A** and **Set B** into business-owner verification questions. Set A is the interaction-based current-reality feedback. Set B is the synthesized proposal context and proposal document, which also includes internal research and inferred product requirements.

**How to use this document:**  
Ask the business owner to answer with facts, source documents, screenshots, sample files, data dictionaries, or system extracts wherever possible. The objective is to verify operating facts already asserted or implied in the proposal before final handover.

---

## 1. Operating Scope, Ownership and Control Boundaries

| No. | Verification question | Expected answer format |
|---|---|---|
| 1.1 | Which parts of the Berau flow are directly operated by ABL: port facility, coal processing/blending, stockpile handling, jetty queue, BLC operation, tug-barge dispatch, CTS/floating crane operation, OGV loading coordination, survey coordination, documentation closure? | Checklist with owner per activity: ABL / Berau / contractor / surveyor / agent / other. |
| 1.2 | What is ABL's decision authority for each operating layer: can ABL decide, recommend, execute after approval, or only receive instruction? | Matrix: activity vs decision authority. |
| 1.3 | Which Berau-side functions create or modify the demand plan, source-jetty plan, coal quality plan, and OGV loading priority? | Text response with role/team names. |
| 1.4 | What formal handoff points exist between Berau and ABL from cargo plan release to OGV departure? | Process step list with document/system used at each handoff. |
| 1.5 | Which locations are in scope for the current proposal: mine/CPP/stockpile names, jetties, river routes, transshipment points, anchorage zones, OGV loading areas? | Location list with codes/names and map if available. |
| 1.6 | Are Lati, Binungan, Sambarata and Suaran/KM locations part of the active operating scope for this proposal? | Yes/no per location with current operational role. |
| 1.7 | What entities own the operational KPIs for jetty productivity, fleet utilization, CTS productivity, OGV completion, demurrage, and safety? | KPI owner table. |

---

## 2. Demand, OGV Programme and Customer Commitments

| No. | Verification question | Expected answer format |
|---|---|---|
| 2.1 | What demand fields does ABL receive today for each OGV or shipment: vessel name, voyage, buyer, quantity, coal grade, laycan, ETA/ETB, priority, source jetty, hatch plan, layering sequence, completion target? | Checklist with field source and format. |
| 2.2 | How often is the OGV programme updated: monthly, weekly, daily, intra-day, or event-driven? | Frequency plus examples of actual update cadence. |
| 2.3 | What is the current change notification process when Berau changes source jetty, buyer requirement, coal quality, quantity, or OGV timing? | Process description with communication channel and approval owner. |
| 2.4 | Are OGV hatch plans and layering sequences available before barge assignment, during execution, or only at OGV loading stage? | Multiple choice plus sample document if available. |
| 2.5 | What fields identify shipment priority or customer urgency in the current plan? | Field name/value examples or note if informal. |
| 2.6 | How is demurrage risk currently calculated or recognized: by date threshold, laycan breach, OGV waiting time, manual escalation, or no formal calculation? | Text response with formula/rule if any. |
| 2.7 | What are typical OGV cargo sizes and typical barge-load counts per OGV by cargo type or barge size? | Numeric ranges and representative example. |

---

## 3. Mine, CPP, Stockpile, Cargo Quality and Blending

| No. | Verification question | Expected answer format |
|---|---|---|
| 3.1 | What cargo-readiness levels are visible to ABL today: mine production readiness, CPP output, stockpile quantity, jetty availability, blend plan, sample status, quality release, or ready-to-load status? | Checklist with source and update frequency. |
| 3.2 | Which coal quality parameters are used operationally for scheduling or assignment: CV, ash, moisture, sulphur, fines, contamination, brand/grade, buyer spec, other? | Checklist with parameter owner. |
| 3.3 | Does ABL receive the blend recipe or only the final required grade/brand for execution? | Multiple choice with sample artifact. |
| 3.4 | When one OGV uses cargo from multiple jetties or grades, how is the required loading sequence communicated to ABL? | Process description and document/source. |
| 3.5 | How is quality-locking handled when a barge has been assigned to a buyer/OGV/grade combination? | Text response with reassignment rules. |
| 3.6 | Are rain, moisture change, stockpile age, drainage, rehandling, or contamination events captured as operational constraints today? | Checklist with event source and impact rule. |
| 3.7 | What are the current status values for cargo quality or release: planned, sampled, released, blocked, disputed, under recheck, ready-to-load, other? | Status list with definitions. |
| 3.8 | Are blocked/disputed quantities visible in the operating plan before tug-barge dispatch? | Yes/no/partial plus data source. |
| 3.9 | What is the normal lead time between quality release and physical BLC/jetty loading? | Numeric range by jetty/grade if available. |

---

## 4. Port, Jetty and BLC Operations

| No. | Verification question | Expected answer format |
|---|---|---|
| 4.1 | Which jetties and BLCs are currently used for the operation, and what are their operating codes/names? | Master-data list. |
| 4.2 | What is the confirmed BLC capacity by loading point, and is 2,000 tph the correct planning value for the main BLC? | Numeric value by asset with source. |
| 4.3 | What is the typical barge loading duration by jetty, cargo type, and barge size? | Numeric range/table. |
| 4.4 | What is the typical pre-loading waiting time at each jetty, and how often does it exceed the planning assumption? | Numeric range/table plus comments. |
| 4.5 | What operational statuses exist for a jetty/BLC: available, queueing, loading, breakdown, maintenance, no cargo, weather hold, survey hold, other? | Status list with definitions. |
| 4.6 | Is jetty queue currently captured as a structured queue with vessel/barge sequence, or managed informally by field coordination? | Multiple choice plus sample if structured. |
| 4.7 | What data is available for BLC downtime, loader rate, loading start/end, queue arrival, queue release, and loading completion? | Field list with source and update frequency. |
| 4.8 | Are survey or inspection readiness checks required before jetty loading, or are they relevant only at OGV loading/closure? | Text response by stage. |

---

## 5. Tug-Barge Fleet, Route Cycle and Closed-Loop Availability

| No. | Verification question | Expected answer format |
|---|---|---|
| 5.1 | What is the current owned and chartered fleet count by asset class: tug, barge, self-propelled barge, assist tug, support craft? | Master-data table. |
| 5.2 | What vessel identifiers are used across systems: asset code, AIS MMSI, IMO, tug/barge name, Spinergie ID, internal ERP ID? | ID-mapping table. |
| 5.3 | What tug HP range and barge capacity range should be used for planning? | Numeric range by asset class. |
| 5.4 | What are the standard route cycle components currently tracked: assignment time, departure, arrival jetty, queue start, loading start/end, departure loaded, arrival CTS/OGV, discharge start/end, return start, available time? | Checklist with source per event. |
| 5.5 | Are loaded sailing time and empty return time separately measured today? | Yes/no/partial plus sample data. |
| 5.6 | What are the planning cycle-time ranges for each active route, including near, medium and far jetties? | Route-time table. |
| 5.7 | Are the indicative assumptions valid: nearby movement around 9-12 hours plus loading/unloading, farthest movement around 48-70 hours? | Confirm/correct with route examples. |
| 5.8 | How is mid-route reassignment recorded when a tug-barge is redirected to another jetty, OGV or buyer? | Text response plus event/status fields. |
| 5.9 | What makes an asset "available" for next assignment: discharge complete, return started, arrived safe point, empty at jetty, crew ready, maintenance clear, other? | Definition list. |
| 5.10 | Are breakdown, maintenance, crew availability and inspection status captured in a structured way? | Checklist with source. |

---

## 6. Tide, Bridge, River Navigation and Safety Constraints

| No. | Verification question | Expected answer format |
|---|---|---|
| 6.1 | What tide data source is used for dispatch planning, and what format is available: PDF/table, Excel, API, website, internal system, manual update? | Source and format description. |
| 6.2 | What bridge-window data source is used, and is it available as structured time windows? | Source, format, update frequency. |
| 6.3 | Which river segments, bridges, draft restrictions, choke points, and safe waiting points must be represented in the schedule? | Route constraint list/map. |
| 6.4 | What vessel, barge, cargo, tide-height or draft rules determine whether a movement is safe? | Rule table or operational guideline. |
| 6.5 | How is grounding currently recorded: event type, delay code, safety incident, operational exception, or informal report? | Status/event code list. |
| 6.6 | What data exists for historical missed tide windows, bridge waits, grounding, traffic congestion and weather-related stoppage? | Dataset/source list with date range. |
| 6.7 | What are the current field rules for intentional waiting at a safe point before a tide/bridge bottleneck? | Text response with approval owner. |
| 6.8 | Are speed adjustments used operationally to align with tide/bridge windows, and are they recorded anywhere? | Yes/no/partial plus source. |

---

## 7. CTS, Floating Crane, Transshipment and OGV Loading

| No. | Verification question | Expected answer format |
|---|---|---|
| 7.1 | Which CTS, FTS and floating crane assets are in scope, and what are their operating names/codes? | Asset master list. |
| 7.2 | What is the confirmed daily capacity or discharge rate for each CTS/floating crane, and is 55,000 t/day a valid peak planning value? | Numeric table by asset. |
| 7.3 | Which capability attributes matter for assignment: conveyor, crane-and-grab, sampler, metal detector, rotating chute, blending capability, hatch reach, weather limit, other? | Checklist by asset. |
| 7.4 | Is CTS/floating crane queue captured as a structured queue, and does it link to OGV/hatch sequence? | Multiple choice plus sample. |
| 7.5 | What event timestamps are captured for CTS execution: barge arrived, discharge start, discharge end, CTS downtime, hatch change, OGV loading complete? | Checklist with source. |
| 7.6 | How are CTS downtime and productivity losses categorized today? | Reason-code list. |
| 7.7 | Is OGV loading progress tracked by hatch, by cargo grade, by barge, by tonnage, or only at total-vessel level? | Multiple choice with sample. |
| 7.8 | What happens operationally if barge arrival sequence conflicts with hatch/layering plan? | Text response with escalation path. |

---

## 8. Survey, Certification and Shipment Closure

| No. | Verification question | Expected answer format |
|---|---|---|
| 8.1 | Which survey milestones are mandatory for the operation: hold inspection, initial draft survey, sampling, barge-wise quantity record, loading supervision, final draft survey, certificate of weight, certificate of quality, statement of facts? | Checklist with responsible party. |
| 8.2 | Which survey milestones can block loading, OGV completion or departure? | Checklist with blocker definition. |
| 8.3 | Where are survey milestone statuses recorded today: Excel, surveyor report, email, Spinergie/SOF, operational database, WhatsApp, other? | Source list. |
| 8.4 | Are certificate dates/times and document closure dates/times available as data fields? | Yes/no/partial plus sample. |
| 8.5 | Who confirms shipment closure and OGV departure readiness? | Role/team response. |
| 8.6 | Are operational exceptions recorded before statement-of-facts closure? | Yes/no/partial with process description. |

---

## 9. Spinergie, AIS and Live Position Data: Technical Verification

| No. | Verification question | Expected answer format |
|---|---|---|
| 9.1 | Which Spinergie modules are actively used in the Berau operation: Smart Fleet Management, live map, AIS tracking, reporting, daily reports, statement of facts, activity tracking, fuel/ROB, performance dashboards? | Checklist with usage level: active / occasional / not used. |
| 9.2 | What is the current method for accessing Spinergie data: web UI only, scheduled export, manual report download, API, database extract, webhook/event feed, or vendor-managed integration? | Multiple choice plus details. |
| 9.3 | If an API exists, what API type is available: REST, GraphQL, SOAP, streaming API, webhook, SFTP file drop, other? | Interface type and vendor documentation if available. |
| 9.4 | What authentication method is used or available for integration: API key, OAuth2, bearer token, basic auth, IP allowlist, VPN, SFTP credentials, vendor-managed token, other? | Technical description. |
| 9.5 | What data format can be shared: JSON, CSV, Excel, XML, PDF report, database view, Parquet, other? | Format list with sample file. |
| 9.6 | What is the available data refresh cadence for live position: real-time, 1-minute, 5-minute, 15-minute, hourly, daily report, manual export? | Cadence value by data type. |
| 9.7 | What historical AIS/position data can be provided for model calibration: 1 month, 3 months, 6 months, 12 months, more? | Date range and volume estimate. |
| 9.8 | What fields are available in each AIS/position record: timestamp, latitude, longitude, speed, heading, course, MMSI, asset name, tug/barge link, source system ID, geofence, status, destination, ETA? | Field dictionary or sample extract. |
| 9.9 | What timestamp standard is used in Spinergie/AIS exports: local time, UTC, server time, timezone included, timezone omitted? | Technical response with sample. |
| 9.10 | What coordinate standard is used: WGS84 lat/long, projected coordinates, decimal degrees, degrees/minutes/seconds? | Technical response with sample. |
| 9.11 | Are geofence events available directly from Spinergie, or must geofence events be generated by the new platform from raw AIS coordinates? | Multiple choice plus available geofence list. |
| 9.12 | Which geofences already exist: jetty arrival/departure, BLC zone, bridge zone, tide/choke point, CTS/OGV zone, anchorage, safe waiting point, maintenance area? | Geofence inventory with coordinates if possible. |
| 9.13 | Does Spinergie expose operational activity events separately from AIS position, such as loading, discharging, waiting, breakdown, idle, bunkering, maintenance, available? | Checklist with source and reliability. |
| 9.14 | How are tug-barge pairings represented in the data: explicit linked IDs, manual pairing table, voyage/trip ID, same geofence/time inference, not represented? | Data model explanation. |
| 9.15 | Is there a trip/voyage identifier that links demand, tug, barge, jetty, CTS/OGV and actual movement events? | Yes/no/partial plus field name. |
| 9.16 | What is the quality/completeness of AIS coverage in river, jetty, bridge and transshipment zones? | Coverage rating by zone: good / intermittent / poor / no signal. |
| 9.17 | What known AIS data issues exist: missing pings, duplicate pings, wrong asset name, delayed updates, incorrect MMSI mapping, tug/barge ambiguity, GPS drift, offline zones? | Issue list with examples. |
| 9.18 | What current business decisions are already made using Spinergie/AIS data, and which decisions still rely on phone/WhatsApp/manual judgment? | Use-case list. |
| 9.19 | Can Spinergie exports be joined to Excel schedule data through a stable key such as asset code, MMSI, trip ID, OGV name, jetty code or timestamp range? | Join-key mapping. |
| 9.20 | What data-sharing approach is feasible for the current build phase: one-time historical extract, daily CSV export, scheduled SFTP feed, API polling, webhook feed, database view, manual upload? | Preferred method plus constraints. |
| 9.21 | Who is the technical owner for Spinergie access, API approval, vendor coordination and security approval? | Name/role/team. |
| 9.22 | Are there restrictions on storing AIS/Spinergie data in the new platform: retention limit, data residency, security classification, vendor terms, user-access restrictions? | Policy/contract response. |
| 9.23 | Can the current build consume position data only, or can it also consume operational reports, daily reports, statement-of-facts data and activity logs? | Data-source checklist with priority. |
| 9.24 | What minimum data fields must be available for the first planned-vs-actual build: asset ID, timestamp, coordinates, speed, heading, geofence, assignment ID, status? | Confirm/correct minimum field list. |

---

## 10. Excel, Master Data and Operational Report Data

| No. | Verification question | Expected answer format |
|---|---|---|
| 10.1 | What Excel planning files are currently used, and what is the owner, update frequency and file structure for each? | File inventory. |
| 10.2 | Which master-data lists already exist: jetties, routes, tug assets, barges, CTS assets, OGVs, cargo grades, buyers, reason codes, tide/bridge windows? | Checklist with source file/system. |
| 10.3 | Are asset master IDs consistent across Excel, Spinergie, AIS, operational reports and finance/charter records? | Yes/no/partial plus mismatch examples. |
| 10.4 | What fields define route master data: origin, destination, distance, standard loaded time, standard empty time, tide dependency, bridge dependency, draft restriction, safe waiting point? | Field list with sample. |
| 10.5 | Are delay and waiting reason codes standardized today? | Yes/no/partial plus code list. |
| 10.6 | What historical operational reports are available for calibration of waiting time, cycle time and productivity? | Dataset list with date range. |
| 10.7 | Can operational reports be shared as structured data rather than PDF/image/manual notes? | Available formats and constraints. |
| 10.8 | What data fields are required to calculate planned-vs-actual at trip level? | Confirm/correct field list. |

---

## 11. Event Model and Business-State Inference

| No. | Verification question | Expected answer format |
|---|---|---|
| 11.1 | Which business states are valid for a tug-barge trip: planned, assigned, en route empty, arrived jetty, waiting jetty, loading, loaded, en route loaded, waiting tide/bridge, arrived CTS/OGV, discharging, discharged, returning, available, breakdown, maintenance, reassigned, cancelled? | Status list with definitions. |
| 11.2 | Which of these states are confirmed manually, which can be inferred from AIS/geofence, and which need both? | State vs source matrix. |
| 11.3 | What event timestamps are mandatory for operational control versus only useful for analytics? | Event priority list. |
| 11.4 | What confidence level is acceptable for inferred events before planner confirmation is required? | Rule/threshold response. |
| 11.5 | How should conflicting signals be resolved, for example AIS shows arrived but field report says still waiting outside jetty? | Business rule response. |
| 11.6 | Which exception events require immediate alerting: missed tide, bridge wait, grounding risk, breakdown, cargo hold, OGV delay, CTS queue, survey hold, reassignment? | Alert priority list. |
| 11.7 | Are current WhatsApp/voice updates structured enough to convert into reason codes, or do new field-event forms need to be introduced? | Multiple choice plus examples. |

---

## 12. Third-Party Charter Fleet and Capacity Planning

| No. | Verification question | Expected answer format |
|---|---|---|
| 12.1 | How many tugboats and barges are owned versus chartered in the operating scope? | Numeric table. |
| 12.2 | What is the normal process for requesting, inspecting, approving and mobilizing a charter tug? | Process steps and lead time. |
| 12.3 | Is one week a reliable planning assumption for charter tug readiness? | Confirm/correct numeric range. |
| 12.4 | What statuses exist for charter assets: requested, vendor confirmed, inspection pending, inspection passed, mobilizing, ready, rejected, unavailable? | Status list. |
| 12.5 | Are charter costs or commercial constraints considered in dispatch/recovery decisions? | Yes/no/partial plus owner. |
| 12.6 | Are third-party assets tracked in the same planning files and AIS systems as owned assets? | Yes/no/partial with source. |

---

## 13. Governance, KPIs, Decision Rights and Adoption

| No. | Verification question | Expected answer format |
|---|---|---|
| 13.1 | Who approves source-jetty changes, cargo reassignment, tug-barge reassignment, intentional waiting, route deviation, and charter mobilization? | Decision-right matrix. |
| 13.2 | What is the current escalation path for OGV delay, quality hold, grounding risk, CTS congestion and fleet shortage? | Escalation process. |
| 13.3 | Which KPIs are currently measured by ABL, and which are measured by Berau or other parties? | KPI table with owner and formula. |
| 13.4 | What formulas are used for fleet productive time, floating crane productive time, waiting time, idle time, OGV delay and demurrage risk? | Formula list. |
| 13.5 | Are fleet productive time around 55-60% and floating crane productive time around 35% current accepted baselines? | Confirm/correct with date period. |
| 13.6 | What delay attribution categories are acceptable for operational reporting: jetty queue, cargo hold, tide wait, bridge wait, CTS queue, OGV delay, survey, breakdown, instruction wait, weather, other? | Reason-code list. |
| 13.7 | Which user groups will operate or consume the platform: planner, dispatcher, field coordinator, tug master, CTS operator, port/BLC user, Berau planner, management, IT admin? | User-role list. |
| 13.8 | What language, device, connectivity and access constraints exist for field users? | Text response. |
| 13.9 | What operating process changes are already acceptable: standard event reporting, reason codes, approval workflow, planned-vs-actual review, daily control-tower meeting? | Checklist with adoption constraints. |

---

## 14. Validation Inputs Requested

| No. | Requested input | Preferred format |
|---|---|---|
| 14.1 | Latest OGV programme and historical OGV schedule changes. | Excel/CSV with 3-6 months history. |
| 14.2 | Current Excel scheduling files used by ABL. | Native Excel files. |
| 14.3 | Tug, barge, CTS and jetty master data. | Excel/CSV with IDs and names. |
| 14.4 | Route and cycle-time assumptions. | Table by origin/destination. |
| 14.5 | Tide, bridge and draft restriction data. | Structured table/API details where available. |
| 14.6 | Spinergie/AIS sample export and data dictionary. | CSV/JSON sample plus field definitions. |
| 14.7 | Historical operational reports and delay logs. | Excel/CSV preferred; PDF acceptable if no structured data exists. |
| 14.8 | Survey and statement-of-facts sample documents. | PDF/Excel sample with sensitive fields redacted if required. |
| 14.9 | Current reason codes, status codes and event definitions. | Code list or screenshot. |
| 14.10 | Integration/security constraints for sharing operational data. | IT/security note or vendor documentation. |

