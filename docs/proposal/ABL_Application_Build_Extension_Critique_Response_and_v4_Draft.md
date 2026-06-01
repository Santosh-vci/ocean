# ABL Application Build Extension - Critique Response And v4 Draft Direction

**Context:** Response to external critique of the ABL Operational Blueprinting Application Build Extension v3  
**Purpose:** Objectively separate supported proposal facts, critique points worth adopting, partial disagreements and proposed v4 changes  
**Prepared for:** Internal proposal refinement before client-facing revision  
**Date:** 31-05-2026

---

## 1. Executive Response

The critique is directionally useful. It does not reject the operating logic or technical feasibility of the proposed application. It mainly challenges the **client-facing framing**, especially whether the current proposal reads too much like a high-ambition control tower roadmap instead of a sharply scoped operational digitization program.

The key conclusion is:

> The current proposal is factually grounded in the repository build, the operating context and the existing phase evidence, but the next version should present the client roadmap more conservatively: scheduling-first, adoption-gated and less architecture-centric.

The current repository has already matured beyond a simple concept. It contains a Dockerized product foundation, governed scheduling flow, scenario/recovery evidence, telemetry/event layers, flow guidance and review surfaces. However, the proposal should not force the client to consume the entire maturity path as one immediate implementation promise. The client-facing document should distinguish:

- what is proposed as **first operational value**;
- what is available as **Vector-owned/product scaffolding**;
- what is introduced only after **data readiness, workflow adoption and user validation**;
- what remains **future optional enrichment**.

---

## 2. Facts Supporting Assertions Already Made In The Proposal

### 2.1 The domain constraint set is real and correctly represented

The proposal asserts that ABL planning must coordinate OGV demand, cargo sequence, tug-barge movement, jetty/BLC loading, tide windows, bridge windows, CTS availability, approval and publication.

Supporting facts:

| Assertion in proposal | Supporting facts from proposal/repo | Interpretation |
|---|---|---|
| ABL planning is not generic fleet tracking. It is constraint-aware transshipment scheduling. | `docs/proposal/ABL_Operational_Blueprinting_Application_Build_Extension_v3.md` defines the route as cargo readiness, jetty/BLC loading, tug-barge departure, tide/river movement, bridge crossing, CTS queue/discharge, OGV hatch/layer completion and closure. | The proposal accurately captures the physical and operational chain. |
| Tide, bridge, jetty, CTS, cargo readiness and OGV laycan can become moving constraints. | The v3 proposal states that the controlling constraint shifts during the day across tide, bridge, jetty, CTS, berth, tug-barge availability, cargo readiness and laycan pressure. | This is a valid scheduling philosophy for ABL transshipment operations. |
| The system must surface explicit conflicts rather than hide infeasibility. | `docs/12_Phase_1_Completion_Evidence.md` includes seeded blocker evidence: `BARGE_UNAVAILABLE`, `BRIDGE_WINDOW_MISSED`, `LAYER_SEQUENCE_VIOLATION`, `TUG_BARGE_INCOMPATIBLE`, `JETTY_OVERLAP` and `TIDE_WINDOW_MISSED`. | The repository already proves conflict surfacing for representative operational blockers. |
| Published plans and approvals need governance. | Phase 1 evidence proves dual approval, published snapshot, audit trail and governed export for `PLAN-PHASE1-E2E`. | Governance is not only conceptual; it is represented in the current build evidence. |

### 2.2 The proposed technology stack matches the current implementation base

The critique questions whether the stack is too heavy for usability, but the technology choices themselves are not speculative.

Supporting facts:

| Layer | Proposal stack | Repository evidence |
|---|---|---|
| Operator web application | React, Vite, TypeScript | `frontend/package.json` uses React, Vite, TypeScript and Vitest. |
| API and services | Django, Django REST Framework | `backend/requirements.txt` includes Django and Django REST Framework. |
| Background jobs | Celery, Celery Beat | `backend/requirements.txt` includes Celery with Redis; `docker-compose.yml` defines `worker` and `beat` services. |
| Application server | Gunicorn | `docker-compose.yml` runs `gunicorn config.wsgi:application`. |
| Database | PostgreSQL with PostGIS | `docker-compose.yml` uses `postgis/postgis:17-3.5`. |
| Cache / broker | Redis | `docker-compose.yml` defines Redis and uses it for Celery. |
| Object storage | MinIO / S3-compatible storage | `docker-compose.yml` defines MinIO object storage and bucket initialization. |
| Edge routing | Nginx | `docker-compose.yml` defines an Nginx `proxy` service. |
| Runtime | Containerized deployment | `README.md` identifies the stack as Docker-first and Docker Compose based. |

Conclusion: the architecture table in the proposal is supported by the current repository. The improvement needed is not to remove these facts, but to explain them as **implementation infrastructure**, not as operator-facing complexity.

### 2.3 Release 1 is already the right first value anchor

The critique recommends a scheduling-first MVP. The v3 proposal already identifies Release 1 as the governed scheduling spine covering Sprint 0 to Sprint 5.

Supporting facts:

| Release 1 capability in proposal | Repository evidence |
|---|---|
| Demand intake | Phase 1 proof imports OGV demand and cargo-layer requirements. |
| Master data and operating windows | Phase 1 proof reviews master data and enters manual availability, tide and bridge windows. |
| Schedule generation | Phase 1 proof generates a draft schedule with trips and schedule events. |
| Conflict review | Phase 1 proof preserves seeded conflict-heavy plan evidence. |
| Governed override | Phase 1 proof applies a manual override with a reason code. |
| Dual approval and publish | Phase 1 proof submits, approves and publishes a plan. |
| Governed export | Phase 1 proof generates a controlled export with checksum evidence. |

Conclusion: the critique's recommended first phase is largely aligned with the strongest part of the proposal and the current implementation evidence.

### 2.4 The proposal correctly avoids treating telemetry as automatic truth

The critique positively notes that the proposal avoids "AI magic" and treats evidence as advisory.

Supporting facts:

- v3 build boundaries state that GPS/AIS is evidence, not automatic truth.
- Raw pings do not update the execution plan directly.
- Confirmed field events update actual execution state.
- Planned, observed, confirmed, projected and recommended states remain separate.
- `docs/27_Phase_6_Completion_Evidence.md` confirms that GPS/AIS is gated by telemetry trust assessment and not unconditional production truth.

Conclusion: the proposal is already operationally mature in this area. The v4 document should keep this boundary but phrase it in operator language.

### 2.5 Scenario, recovery and control-tower concepts are supported, but should be phase-gated

The critique says the roadmap is ambitious. That is valid for client-facing sequencing, but the capabilities are not unsupported.

Supporting facts:

| Capability | Repository evidence |
|---|---|
| Scenario simulation | `docs/14_Phase_2_Implementation_Spec.md`, `docs/15_Phase_2_Scenario_Proof_Evidence.md`, and `docs/16_Phase_2_Scenario_Operator_Guide.md`. |
| GPS/AIS live tracking mode | `docs/17_Phase_3_Implementation_Spec.md`, `docs/18_Phase_3_Operator_Runbook.md`, and `docs/19_Phase_3_Completion_Evidence.md`. |
| Event candidate and confirmed operations | `docs/20_Phase_4_Implementation_Spec.md`, `docs/21_Phase_4_Operator_Runbook.md`, and `docs/22_Phase_4_Completion_Evidence.md`. |
| Recovery recommendations | `docs/23_Phase_5_Implementation_Spec.md`, `docs/24_Phase_5_Operator_Runbook.md`, and `docs/25_Phase_5_Completion_Evidence.md`. |
| Guided recovery and review surfaces | `docs/26_Phase_6_Phase_5_Plus_Implementation_Spec.md` and `docs/27_Phase_6_Completion_Evidence.md`. |

Conclusion: the issue is not that these ideas are imaginary. The issue is that the proposal should not make them feel like one immediate delivery obligation.

---

## 3. Critique Facts Worth Emulating In A New Proposal Version

The following critique points should be adopted into v4.

### 3.1 Reframe the first product as scheduling-first

The proposal should lead with:

> Constraint-Governed Operational Scheduling Platform

Rather than leading with:

> Dynamic Operational Synchronization & Scheduling Platform

The latter can remain as the longer-term product direction, but the first client commitment should be narrower and easier to approve.

Recommended v4 shift:

- Make Release 1 the dominant story.
- Position later releases as optional maturity blocks.
- Keep "control tower" as a future state, not the opening promise.

### 3.2 Add explicit operational adoption checkpoints

The critique correctly identifies that data discipline, planner adoption, event trust and approval standardization are organizational transformations.

Recommended v4 addition:

> Before progressing beyond the governed scheduling spine, ABL and Berau will jointly review planner usage, override frequency, conflict false positives, decision latency, manual escalation patterns and data readiness.

This is important because a technically complete scheduling tool can still fail if the operational organization does not adopt the process.

### 3.3 Add a practical exception taxonomy

The critique is right that "recovery" is broad unless the exception families are explicit.

Recommended v4 exception categories:

| Exception family | Examples |
|---|---|
| Cargo/source readiness | Cargo not ready, quality hold, source switch, cargo layer mismatch |
| Jetty/BLC operations | Loading delay, queue, reduced loading rate, equipment stoppage |
| Navigation constraint | Tide missed, bridge window missed, draft restriction change, grounding risk |
| Fleet/asset availability | Tug unavailable, barge unavailable, incompatibility, breakdown, external charter lead time |
| CTS/transshipment | CTS queue, floating crane downtime, discharge rate reduction |
| OGV/laycan | OGV ETA change, hatch sequence change, laycan pressure, loading completion risk |
| Weather/marine | Rain, wind, visibility, wave restriction, river condition |
| Survey/clearance | Draft survey delay, documentation hold, port clearance interruption |
| Human/governance | Approval delay, manual override, escalation, disputed operating decision |
| Data/integration | Missing feed, stale signal, duplicate event, untrusted telemetry |

This taxonomy should be described as an initial blueprint taxonomy, not final production truth.

### 3.4 Add human-operational reality

The critique is correct that planners may rely on informal overrides, negotiated exceptions, tacit heuristics and manual escalation.

Recommended v4 language:

- The tool will not eliminate planner discretion.
- Manual overrides remain available but reason-coded.
- Shadow-mode validation may be used before enforcing strict workflow behavior.
- False-positive blockers should be reviewed during pilot.
- Planner heuristics should be captured as candidate rules only after operational validation.

### 3.5 Add measurable MVP success criteria

The current proposal describes deliverables, but it should define narrower first-release success measures.

Recommended v4 Release 1 metrics:

| Metric | Example target direction |
|---|---|
| Publishable-plan cycle time | Reduce time from demand intake to publishable plan. |
| Schedule rework | Reduce repeated spreadsheet revisions and manual reconciliation. |
| Conflict clarity | All hard blockers carry reason code, affected movement and suggested next action. |
| Approval traceability | All published plans carry approval, version and audit lineage. |
| Planner adoption | Named pilot users complete representative planning workflows with acceptable manual override rate. |
| Data readiness | Demand, master data and operating-window inputs meet minimum completeness threshold. |

Specific numeric targets should be agreed with ABL and Berau after baseline observation.

### 3.6 Reduce architecture-centric language in the client-facing narrative

The critique is correct that terms like "trust layer", "actualization layer", "evidence ingestion contracts" and "governed publication pathways" can sound like system semantics rather than operating value.

Recommended v4 operator-facing language:

| Architecture phrase | Operator-facing phrase |
|---|---|
| Trust layer | Which field update is reliable enough to act on? |
| Actualization layer | Which event is confirmed and should update the plan status? |
| Evidence ingestion | What position/status evidence has arrived? |
| Publishability gate | Is the plan ready to publish? |
| Recovery recommendation | What are the safest feasible recovery options? |
| Immutable snapshot | Which approved plan was released and when? |

### 3.7 Move telemetry and industrial protocol detail to later/optional scope

The critique is right that MQTT, NMEA, OPC-UA, PLC and similar integrations should not be presented as early structural dependencies.

Recommended v4 shift:

- Release 1 should work with manual entry, file import and seeded/replay data.
- Telemetry should be positioned as optional enrichment after operating workflow stabilizes.
- Protocol definitions should remain in glossary/appendix, not core implementation promise.

---

## 4. Facts We Do Not Disagree With In Totality

This section identifies critique points where the concern is valid, but the conclusion should be moderated.

### 4.1 "The roadmap is overextended"

Position: **Partially agree.**

The v3 document can read as if scheduling, simulation, telemetry, actualization, recovery and control tower are one continuous commitment. For a client proposal, that is too much.

However, the repository has already implemented or evidenced several of these maturity layers. Therefore, the problem is not technical imagination; it is proposal sequencing and expectation management.

v4 response:

- Keep the full maturity model.
- Present it as a staged option set.
- Make Release 2+ contingent on Release 1 adoption and data readiness.

### 4.2 "The tool risks cognitive overhead for planners"

Position: **Agree with the risk, not with inevitability.**

The repo includes Next Action guidance and operator flow support, which directly addresses cognitive load. Still, the critique is valid that the proposal must not expose internal state complexity to operators.

v4 response:

- Lead with simple operator questions:
  - What is the latest demand?
  - What can be scheduled?
  - What is blocked?
  - What changed?
  - What must I approve?
  - What recovery option is safest?
- Keep plan versions, evidence state, actualization and publishability as governance mechanics, not screen labels unless needed.

### 4.3 "The economic optimization layer is missing"

Position: **Partially agree.**

The v3 document intentionally limits commercial exposure to projection-only and excludes final settlement. That boundary is correct.

However, the critique is right that operating decisions often need commercial context: demurrage exposure, waiting cost, utilization, charter cost, route tradeoff and throughput/margin impact.

Repository evidence shows Phase 6 includes commercial projection surfaces and global optimization scaffolding, but these are read-only/review surfaces and not final settlement logic.

v4 response:

- Add "commercial and operating impact indicators" as an optional decision-support layer.
- Avoid promising full demurrage, invoicing or margin optimization.
- State that economic weights require commercial sign-off and historical baseline data.

### 4.4 "The proposal assumes clean data and stable process discipline"

Position: **Agree.**

This should be made explicit. The v3 assumptions already mention demand format, master-data naming, manual windows, confirmation rules and approval authority. But they should be reframed as **readiness gates**, not passive assumptions.

v4 response:

- Add a readiness checklist.
- Define minimum viable data.
- Use pilot shadow mode where data trust is uncertain.
- Gate telemetry and recovery automation behind data quality.

### 4.5 "Telemetry should be optional enrichment"

Position: **Mostly agree.**

The current v3 release table already places live evidence after Release 1 and Release 2, not in the first scheduling spine. The critique is still useful because the proposal may overemphasize telemetry in the broader product story.

v4 response:

- Explicitly state that Release 1 does not depend on live telemetry.
- Treat GPS/AIS, MQTT, NMEA, OPC-UA, PLC and operator-console integrations as later integration paths.

### 4.6 "Control tower language is too ambitious"

Position: **Agree for initial framing; retain as future state.**

"Control tower" is credible only after governed scheduling, adoption, exception handling and data reliability are proven.

v4 response:

- Remove "control tower" from executive headline.
- Use it only in the final maturity stage.

### 4.7 "OR-Tools / CP-SAT should be considered"

Position: **Do not adopt as a proposal commitment without implementation decision.**

The critique's solver suggestion is technically reasonable for some constraint scheduling problems, but the current proposal states that Vector proprietary scheduling and scenario scaffolding will be used. The current repository does not establish OR-Tools as the chosen scheduling engine.

v4 response:

- Do not introduce OR-Tools or CP-SAT into client-facing architecture unless Vector elects to use it.
- Keep solver/engine internals behind the proprietary scaffolding language.
- Explain the externally visible behavior: feasibility checks, conflict surfacing, candidate options and scenario impact.

---

## 5. Draft v4 Change Direction

### 5.1 Proposed v4 title

Current:

> Dynamic Operational Synchronization & Scheduling Platform

Recommended:

> Constraint-Governed Operational Scheduling Platform

Optional subtitle:

> A phase-gated path from spreadsheet replacement to governed transshipment flow management.

### 5.2 Proposed v4 executive summary rewrite

Draft:

> This extension defines how the validated ABL-Berau operational blueprint will move into an application build. The first release will focus on a governed scheduling spine: structured demand intake, cargo sequence, master data, operating windows, tug-barge assignment, conflict surfacing, approval and published schedule output.
>
> Vector will use its proprietary scheduling and scenario scaffolding as the implementation base, but the initial client value will be deliberately narrow: replacing spreadsheet-only planning with a controlled, constraint-aware, publishable operating plan.
>
> Later capabilities such as scenario simulation, telemetry-assisted execution, event confirmation, recovery recommendation and control-tower review will be introduced only after operational adoption, data readiness and governance behavior are validated.

### 5.3 Proposed v4 release framing

| Delivery block | Framing change |
|---|---|
| Release 1 - Governed scheduling spine | Present as the primary committed MVP. |
| Release 1A - Adoption and operating-rule validation | Add a new checkpoint before expanding scope. |
| Release 2 - Exception and manual recovery support | Add after planner behavior and override patterns are understood. |
| Release 3 - Scenario and impact simulation | Gate behind data readiness and clear scenario use cases. |
| Release 4 - Telemetry-assisted execution | Make optional enrichment, not structural dependency. |
| Release 5 - Control tower maturity | Present as future state, not initial expectation. |

### 5.4 Proposed v4 sprint/delivery wording

Replace a linear "Sprint 0 to Sprint 10 equals full product" impression with:

| Stage | Sprint direction | Client promise |
|---|---|---|
| Stage 1 | Sprint 0 to Sprint 5 | Governed scheduling MVP and publishable operating plan. |
| Stage 1A | Adoption checkpoint | Validate usage, false positives, overrides, data gaps and operational fit. |
| Stage 2 | Sprint 6 onward, subject to gate | Scenario and exception handling expansion. |
| Stage 3 | Later, subject to integration readiness | Telemetry-assisted execution and confirmed operations. |
| Stage 4 | Later, subject to business validation | Recovery guidance, optimization review and control-tower maturity. |

### 5.5 Proposed v4 addition: operational validation checkpoint

Add a section:

> **Operational Adoption Gate**
>
> Before expanding beyond the governed scheduling spine, ABL, Berau and Vector will review whether the tool is matching real planning behavior. The review will check planner usage, demand completeness, master-data stability, conflict false positives, override frequency, approval latency, manual escalation patterns and the actual time required to generate a publishable plan.

### 5.6 Proposed v4 addition: human-operational model

Add a section:

> **Human Operating Reality**
>
> The application will preserve planner discretion during early adoption. Manual overrides, negotiated exceptions and escalation decisions will remain possible, but will be captured with reason codes and audit lineage. During pilot use, repeated manual decisions will be reviewed to decide whether they should become formal scheduling rules, exception categories or workflow guidance.

### 5.7 Proposed v4 addition: exception taxonomy

Add an initial table:

| Exception family | Initial examples | Treatment in MVP |
|---|---|---|
| Cargo/source readiness | Quality hold, source change, cargo unavailable | Conflict reason and manual resolution note |
| Jetty/BLC | Queue, loading delay, equipment outage | Window/capacity conflict |
| Navigation | Tide missed, bridge wait, draft restriction | Operating-window blocker |
| Fleet | Tug unavailable, barge unavailable, incompatibility | Resource eligibility/capacity blocker |
| CTS/transshipment | CTS queue, discharge delay, crane downtime | Downstream capacity blocker |
| OGV/laycan | ETA change, hatch sequence change, completion risk | Demand/priority pressure |
| Weather/marine | Rain, wind, visibility, river condition | Exception note or window blocker |
| Survey/clearance | Survey hold, documentation delay, port clearance | Closure or readiness blocker |
| Governance | Approval delay, manual override, escalation | Workflow/audit event |
| Data/integration | Missing feed, stale signal, duplicate event | Data quality warning |

### 5.8 Proposed v4 addition: economic and operating impact indicators

Add a bounded section:

> **Economic And Operating Impact Indicators**
>
> The first release will prioritize feasible and publishable scheduling. Commercial optimization will not be treated as final settlement logic. Where data is available, later stages may expose projection-only indicators such as laycan risk, waiting time, fleet utilization, queue impact, charter lead-time pressure and demurrage exposure proxy. Final demurrage, invoicing, despatch and settlement remain outside the scheduling MVP unless separately scoped.

### 5.9 Proposed v4 language cleanup

Replace architecture-heavy terms in the main narrative:

| Current wording | v4 wording |
|---|---|
| Dynamic Operational Synchronization & Scheduling Platform | Constraint-Governed Operational Scheduling Platform |
| Control tower | Future governed flow-management maturity |
| Evidence ingestion layer | Position/status evidence capture |
| Actualization layer | Confirmed event update |
| Trust layer | Field update reliability check |
| Publishability assessment | Ready-to-publish check |
| Recovery recommendation engine | Recovery option review |

### 5.10 Proposed v4 client-facing deliverable summary

Draft:

| Stage | What the client gets | What is intentionally deferred |
|---|---|---|
| Scheduling MVP | Demand intake, cargo sequence, master data, windows, assignments, conflicts, approvals, publish and export | Live telemetry dependency, advanced optimization, automatic recovery |
| Adoption gate | Evidence of planner usage, data gaps, overrides and false positives | Expansion before operating fit is proven |
| Exception/replanning | Delay propagation, manual recovery options and impact review | Autonomous recovery publication |
| Telemetry-assisted execution | Position/status evidence and confirmed event workflow | Treating raw telemetry as automatic truth |
| Control-tower maturity | Guided recovery, management review and projection surfaces | Final commercial settlement unless separately scoped |

---

## 6. Recommended Decision

The v3 proposal should not be discarded. It is technically and operationally grounded. The critique should be used to improve proposal credibility by changing the client-facing posture:

1. Make the first implementation promise narrower.
2. Make Release 1 the explicit client value case.
3. Introduce an adoption gate before later capability expansion.
4. Move telemetry, industrial protocols and control-tower language to later-stage optional scope.
5. Add exception taxonomy, human operating reality and MVP success metrics.
6. Keep the actual architecture and repo maturity as internal confidence, not as an overbroad client promise.

The recommended v4 is therefore a **phase-gated scheduling-first proposal**, backed by Vector's broader proprietary scaffolding and current product maturity.
