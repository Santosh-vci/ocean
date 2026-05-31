# Proposal Context Note: Fleet Management & Transshipment Scheduling Tool for ABL

**Prepared for:** Proposal development for PT Asian Bulk Logistics (ABL)  
**Operating context:** ABL - Berau Coal transshipment, port, blending, barging and OGV loading operations  
**Solution theme:** Flow Management Control Tower for end-to-end shipment synchronization

---

## 1. Executive Framing

ABL's operating reality is not a simple tug-and-barge scheduling problem. The operation sits at the intersection of coal production readiness, coal quality and blending, port handling, barge loading, river/coastal movement, tide and bridge constraints, CTS/floating crane allocation, OGV hatch/layering requirements, survey milestones, third-party asset coordination and final shipment closure.

The proposed scheduling solution should therefore be positioned as a **Flow Management Control Tower** rather than only a fleet allocation tool. Its role should be to convert Berau Coal's shipment commitments into a constraint-aware, executable and continuously updated flow plan for ABL.

In simple terms:

> Berau determines what has to be shipped, in what quantity and quality, against which vessel/customer commitment. ABL must ensure that the cargo, port assets, barges, tugs, transshipment assets, survey milestones and OGV loading sequence are synchronized so the shipment leaves on time with the correct cargo.

---

## 2. Introduction: ABL and Berau Coal

### 2.1 PT Asian Bulk Logistics (ABL)

PT Asian Bulk Logistics is presented in its company profile as an integrated logistics and infrastructure solutions provider with services spanning port management, barging capability, transshipment capability, transshipment support capability, stevedoring, open-sea shipment, rail freight, onshore infrastructure and discharge port management. The profile states that ABL uses technology such as **Spinergie** for real-time operational and performance tracking, **Captain's Eyes** for 24/7 AI-enabled vessel safety monitoring and **Starlink** for continuous connectivity.

The ABL profile also expands the scope significantly beyond marine movement. It states that ABL **operates and manages port facilities in Berau, East Kalimantan**, including a **coal processing plant for coal blending with capacity above 20 million tonnes per annum**, dedicated to one of Indonesia's leading coal producers. It also states that ABL manages more than 60 barges, tugs in the 1,600-3,300 HP range, self-propelled barges, CTS assets and port facilities including a barge loading conveyor of 2,000 tph.

### 2.2 Berau Coal

PT Berau Coal operates in Berau Regency, East Kalimantan, under a large coal concession. Berau's public operation description refers to mining areas such as Lati, Binungan and Sambarata. For example, Berau describes coal from Lati being transported from mine to coal processing plant, crushed, blended, placed onto stockpiles and loaded into barges. Similar descriptions are provided for Binungan and Sambarata operations.

This makes Berau the natural owner of commercial demand, mine production, customer-grade commitment and shipment priority, while ABL is the operator that turns those commitments into an executable logistics and transshipment flow.

---

## 3. Expansive End-to-End Scope: From Mining to OGV Departure

The system boundary should be defined from shipment demand through OGV departure, while recognizing that not every stage is fully owned by ABL.

### 3.1 Commercial demand and shipping program

The flow begins with customer demand or shipping commitments, which may arise from annual contracts, staggered delivery programs, shipment nominations or spot cargo commitments. Operationally, this demand becomes visible as:

- OGV nomination
- laycan window
- required quantity
- required coal grade/specification
- customer priority
- hatch/layering requirement
- planned shipment completion date

### 3.2 Mining, hauling and coal processing

Coal mined from different seams/pits may have different calorific value, moisture, ash, sulphur, fines and contamination characteristics. The mined coal is hauled to a processing/crushing/blending facility and then placed into stockpiles. Rain, drainage, stockpile age and reclaiming sequence can alter physical handling behavior and quality readiness.

### 3.3 Stockpile, quality and blending readiness

This is a critical scheduling dependency. A shipment plan is only executable when the required coal grade is physically available and quality-ready. The tool must recognize:

- stockpile source
- available quantity
- coal quality parameters
- rain/moisture impact
- blending recipe
- sample status
- quality release status
- blocked quantity or disputed quantity
- ready-to-load time

Because ABL's profile indicates that it manages Berau port facilities including coal processing/blending capacity, blending cannot be treated as an outside black box. It becomes a scheduling constraint.

### 3.4 Port operations and BLC loading

The port facility and Barge Loading Conveyor (BLC) become the gateway between cargo readiness and marine execution. The BLC capacity, loading slot, jetty readiness, survey availability, equipment uptime and loading sequence determine whether barges can actually be loaded as scheduled.

### 3.5 Tug-barge movement

Once barges are loaded, they must move through route-specific constraints:

- tug-barge pairing
- loaded sailing time
- empty return time
- tide window
- bridge window
- river/route draft restriction
- waiting queue at jetty or transshipment point
- tug/bargedown or breakdown risk
- third-party asset availability

Samuel's feedback indicates that this is not a uniform cycle. The nearest jetty may involve approximately 9 hours of sailing plus loading/unloading time, while the farthest jetty may be a 48-70 hour cycle. This difference materially affects fleet availability and recovery planning.

### 3.6 CTS / floating crane / transshipment execution

At the transshipment point, barges interface with CTS/floating cranes and the OGV. ABL's profile lists multiple CTS assets with different daily capacities, including conveyor and crane-and-grab types. Several conveyor-type CTS assets include metal detectors, mechanical samplers, rotating chutes and blending capability.

The scheduling system must match the right asset to the right vessel requirement, considering:

- CTS availability
- CTS capacity
- conveyor vs crane-and-grab mode
- metal detector / sampler / rotating chute capability
- blending capability
- OGV hatch plan
- layering sequence
- loading productivity
- weather and sea condition

### 3.7 Survey, draft and certification milestones

Surveying is the verification layer for quantity, quality and cargo condition. Draft survey is used to calculate cargo quantity loaded into the OGV based on vessel displacement before and after loading. The system should treat survey activity as a scheduling checkpoint, not merely documentation.

Key milestones include:

- hold inspection
- initial draft survey
- sampling and quality checks
- barge-wise quantity record
- loading supervision
- final draft survey
- certificate of weight/quality
- statement of facts

### 3.8 OGV loading completion and departure

The shipment is not complete when the last barge arrives. It is complete only when:

- hatch/layering plan is satisfied
- final quantity is certified
- quality documents are available
- final draft survey is completed
- operational exceptions are recorded
- loading documents are closed
- the OGV is cleared to depart

---

## 4. Current Landscape of Systems, Tools and Data Availability

### 4.1 Current BRD view

The BRD frames the workflow as the **Transshipping Scheduling and Fleet Management process between Berau Coal and ABL**. It identifies the current operating pain around static Excel planning, OGV schedule misalignment, actual fleet-status disconnect, environmental constraints, waiting time, idle time and manual document updates.

The BRD lists the current/source landscape as:

- **Microsoft Excel** as the current manual schedule source
- **Spinergie** as the smart fleet management platform for operational reports and AIS position
- OGV scheduling feeds
- real-time fleet status feeds via GPS/AIS or internal tracking
- environmental data feeds such as tides and weather
- demand data including OGV arrival schedules, coal quantity, coal quality type and layering sequence
- constraint data including river tides, bridge schedules and jetty availability
- fleet data including CTS/floating cranes and tug-barge status/location

The BRD also states that the target output should be a unified real-time fleet schedule visible to both Berau Coal and ABL, with automated updates and alerts when environmental or operational conditions change.

### 4.2 Spinergie / AIS layer

Spinergie's public ABL case study indicates that ABL uses Smart Fleet Management for real-time positioning, vessel reporting, daily reports, statement of facts, activity tracking, performance dashboards and remote monitoring of offshore project areas. It also refers to AIS sensor/live map capability and private AIS antenna integration.

This should be viewed as a **visibility and reporting foundation**. It likely provides:

- live vessel map
- AIS/GPS position
- geofence entry/exit
- movement history
- daily reports
- statement-of-facts reporting
- cycle dashboards
- activity tracking
- consumption / ROB data where captured

However, AIS and reporting dashboards do not by themselves solve scheduling. AIS can say where an asset is, but it cannot reliably confirm cargo grade, blending status, loading completion, survey status, hatch sequence, tide feasibility, delay reason or next-best allocation.

### 4.3 ABL physical asset landscape

From the ABL profile, the operational landscape includes:

- port facilities in Berau with coal blending capacity above 20 million tonnes per annum
- Barge Loading Conveyor of 2,000 tph
- more than 60 barges ranging from 270 ft to 340 ft
- tugs of 1,600-3,300 HP
- self-propelled barges
- CTS fleet including conveyor and crane-and-grab assets, with capacities up to 55,000 tonnes/day
- support facilities such as assist tugs, crew transfer vessels, accommodation barges and work barges
- heavy equipment and stevedoring operations
- OGV dry bulk shipment capability

This makes the planning problem multi-layered: port capacity, cargo quality, barge loading, tug-barge cycle, CTS loading, OGV sequence, weather/tide and survey must be planned together.

---

## 5. Current Business Challenges from Samuel's Feedback

The following challenge themes are synthesized from Samuel's discussion as referenced in the prior ABL operational challenges conversation.

### 5.1 Frequent changes in demand, production plan and source jetty

Samuel indicated that ABL's demand comes from Berau Coal, but the operating plan is not stable. Production plans and source jetties change frequently. This forces repeated changes in tug-barge allocation and makes static planning unreliable.

### 5.2 Coal quality and blending drive vessel assignment

Coal quality and blending are not side issues. Samuel's feedback indicates that coal grade/blending decisions can drive OGV assignments and change the required barge movement plan. If the required grade or blend is not ready, a marine plan that looked feasible on paper may fail.

### 5.3 Long and unequal cycle times

The operation has materially different route/cycle profiles. A nearby jetty can still involve around 9 hours of sailing plus loading/unloading time, while the farthest jetty may involve 48-70 hours. This means the same barge/tug cannot be treated as a generic interchangeable unit. Cycle-time modelling is essential.

### 5.4 Low tide and grounding risk

Samuel described low tide grounding as one of the biggest operational issues. This means movement feasibility is not based only on asset availability; it must also consider water level, route, loaded draft and safe movement window.

### 5.5 Waiting and queueing across multiple control points

Waiting time occurs at multiple points:

- jetty waiting
- crane/CTS waiting
- tide waiting
- bridge waiting
- waiting for instructions
- OGV delay waiting
- survey or release waiting
- third-party asset waiting

This creates idle time for barges, tugs, jetties and floating cranes. The system must measure not only total delay but the exact control point where flow is blocked.

### 5.6 Productivity gap in fleet and floating crane utilization

Samuel's feedback indicates that ABL's fleet is only around 55-60% productive, while floating cranes may be around 35% productive. This suggests the main opportunity is not simply adding more assets; it is improving synchronization, reducing waiting and improving flow reliability.

### 5.7 AIS gives position, not true activity status

Samuel's feedback aligns with the technical limitation discussed earlier: AIS helps locate the asset, but it does not confirm the real business state. A tug-master may not consistently report, and AIS does not automatically tell whether the asset is loading, discharging, waiting for cargo, waiting for tide, under breakdown or available for the next assignment.

### 5.8 Inconsistent operational reporting

The current operating process depends on manual updates, captain/tug-master reporting and Excel-based coordination. This makes real-time replanning difficult and affects the reliability of actual-vs-plan reporting.

### 5.9 Extra chartered assets are not immediately available

Samuel indicated that extra chartered tugs may take about one week to prepare. Therefore, recovery planning must not assume that external assets can be added instantly. The system must track third-party asset lead time and readiness.

---

## 6. Key Complication Points the Proposal Must Address

### 6.1 ABL scope includes upstream port/blending operations

Since ABL appears to manage Berau port facilities and coal processing/blending capacity, the tool should not limit itself to fleet scheduling. It must synchronize cargo readiness with marine execution.

### 6.2 Cargo readiness is dynamic

Coal quality can change due to source variation, rain, stockpile exposure, moisture increase, drainage, rehandling and blending decisions. Therefore, cargo readiness must be modelled as a changing state rather than a fixed plan value.

### 6.3 Layering and hatch sequence constrain loading

The BRD specifically states that coal grades must be loaded onto OGVs in a specific layering sequence and cannot be delivered randomly. This converts cargo sequencing into a hard scheduling constraint.

### 6.4 Environmental constraints create hard feasibility windows

Tide windows, bridge crossings, weather and draft restrictions are not optional planning inputs. They determine whether a planned movement is feasible.

### 6.5 Asset availability must be calculated as a closed-loop cycle

A tug or barge becomes available only after completing its loaded movement, discharge/loading support, return movement and any turnaround requirement. If the system does not model the closed loop, it may overstate availability.

### 6.6 Survey and certification can block completion

Draft survey, hold inspection, sampling and certificates can delay shipment closure. These must be visible in the plan and not handled only after loading.

### 6.7 AIS needs business-state enrichment

AIS should be consumed as the actual-movement signal, but business events must be layered over it: assigned, arrived, loading started, loading completed, departed, reached transshipment, discharge started, discharge completed, return started, available again, delayed and breakdown.

### 6.8 Third-party assets need commitment reliability tracking

Externally supplied assets must be tracked separately from ABL-owned or ABL-managed assets. Their confirmation status, lead time, readiness and availability confidence should influence the plan.

---

## 7. Broader Direction of the Scheduling Solution

The recommended solution direction is a phased **Flow Management Scheduling Control Tower**.

### 7.1 Core design principle

The tool should not merely show where vessels are. It should answer:

1. What shipment commitment must be fulfilled?
2. Is the required cargo quality-ready and physically available?
3. Which port, jetty, BLC, barge, tug and CTS path can fulfill it?
4. Is the movement feasible against tide, bridge, route and weather?
5. Is the OGV loading sequence still achievable within laycan?
6. What is the current deviation from plan?
7. What is the next best recovery action?

### 7.2 Proposed solution modules

| Module | Purpose |
|---|---|
| Demand and shipping program intake | Capture OGV nomination, laycan, quantity, grade, customer priority and hatch/layering requirement. |
| Cargo readiness and blending module | Track stockpile, grade, moisture, blend recipe, sample status, quality release and ready-to-load time. |
| Port and BLC scheduling | Plan BLC slots, jetty readiness, loading rates and port-side constraints. |
| Tug-barge scheduling | Assign tug-barge combinations using actual availability, route time, loaded/empty cycle and priority. |
| Tide/bridge/environment constraint engine | Validate feasible movement windows and prevent impossible schedules. |
| CTS/transshipment scheduling | Allocate CTS/floating crane assets based on capacity, OGV requirement, equipment capability and sequence. |
| OGV hatch/layering control | Ensure coal grades are delivered in the required sequence and not only by total quantity. |
| Survey and documentation milestones | Track draft survey, sampling, hold inspection, quality/quantity certificates and SOF. |
| AIS/GPS actuals ingestion | Consume live position/movement feeds from Spinergie or direct feeds. |
| Business-state inference | Convert position/geofence signals into operational events and actual trip milestones. |
| Exception management | Detect delay, missed tide, queue, breakdown, under-supply, cargo release delay and demurrage risk. |
| Shared control tower | Provide a unified view for Berau and ABL with role-based visibility and approved actions. |

### 7.3 Phased implementation direction

#### Phase 1: Visibility and planning baseline

- Digitize shipment program and current Excel planning structure.
- Create common master data for jetties, routes, barges, tugs, CTS, OGVs and operational zones.
- Integrate or import Spinergie/AIS positions as actual-movement visibility.
- Create planned vs actual dashboard.
- Capture key milestones manually where automation is not reliable.

#### Phase 2: Constraint-aware scheduling

- Add tide, bridge, jetty and route feasibility rules.
- Add tug-barge pairing and closed-loop availability.
- Add OGV laycan and hatch/layering constraints.
- Add cargo readiness status and blend-release dependency.
- Generate feasible assignment recommendations.

#### Phase 3: Exception and recovery engine

- Detect schedule breaks from AIS/geofence/manual events.
- Show impact on OGV completion, CTS utilization, jetty queue and demurrage risk.
- Recommend reallocation or resequencing options.
- Track delay reason and responsibility bucket.

#### Phase 4: Flow analytics and governance

- Measure throughput loss, waiting time, productivity and asset utilization.
- Identify recurring bottlenecks by jetty, route, tide window, asset class and cargo readiness status.
- Provide governance reports for Berau-ABL coordination.
- Use historical data to improve cycle-time assumptions and scheduling accuracy.

---

## 8. Expected Business Outcomes

The proposal should emphasize the following outcomes:

- reduction in static Excel dependency
- one shared schedule between Berau and ABL
- improved tug-barge and CTS utilization
- reduction in avoidable waiting time
- better compliance with OGV laycan and hatch/layering requirements
- visibility of cargo readiness and blending impact
- tide/bridge-aware movement planning
- faster exception response
- clearer delay attribution
- improved survey/documentation closure
- better integration of third-party assets
- transition from reactive coordination to flow-managed execution

---

## 9. Suggested Proposal Positioning Statement

> ABL's operation requires a system that does more than track assets. The proposed Fleet Management and Transshipment Scheduling Tool will create a shared flow-management layer between Berau Coal's shipment commitments and ABL's port, blending, barging, transshipment and OGV loading execution. By combining demand, cargo readiness, environmental constraints, asset availability, AIS actuals, survey milestones and exception management into one governed scheduling platform, the solution will help ABL move from manual reactive planning to synchronized, constraint-aware execution.

---

## 10. Source Notes Used for This Draft

1. **ABL Company Profile PDF** - PT Asian Bulk Logistics capability profile, including port management, Berau coal processing/blending facility, barging, CTS, BLC, Spinergie, Captain's Eyes and Starlink references.  
2. **BRD - Schedulling Simulation.docx** - business requirement framing for transshipping scheduling and fleet management between Berau Coal and ABL.  
3. **Samuel feedback synthesis from ABL operational challenges chat** - demand volatility, jetty changes, quality/blending impact, tide/grounding, waiting points, productivity gap, AIS limitations and charter lead time.  
4. **Berau Coal public operations page** - mining, processing, blending, stockpiling and barge loading operation descriptions.  
5. **Spinergie ABL case study and press release** - Smart Fleet Management, AIS/live map, reporting, activity tracking, daily reports and statement-of-facts context.

