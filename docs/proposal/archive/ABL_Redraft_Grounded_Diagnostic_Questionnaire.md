# ABL Redraft-Grounded Diagnostic Questionnaire

Source anchors:

- Proposal redraft: `F:\ocean\docs\proposal\ABL_Proposal_Redraft_VCI.docx`
- Interaction synthesis: `F:\ocean\docs\proposal\ABL_Operational_Feedback_Current_Reality_Challenges.md`

Purpose: validate the high-level operating challenges described in the redraft proposal and interaction synthesis before diagnostic and blueprinting. The questionnaire is designed to confirm whether the core problem statement is directionally correct: ABL’s challenge is not only scheduling software or asset tracking, but end-to-end flow coordination across cargo readiness, quality, jetties, tug-barge movement, navigation constraints, CTS/OGV execution, exception handling and decision governance.

This draft is not intended to collect detailed master data, formulas, technical API details, system architecture requirements or feature requests.

Total questions: 38

## 1. Overall Flow Challenge and Diagnostic Focus

| No. | Question | Response type | Expected answer guidance |
|---|---|---|---|
| 1.1 | Which statement best describes the current operating challenge? | Multiple choice | Choose one: mainly fleet scheduling; mainly asset visibility; end-to-end flow coordination; mainly upstream production variability; mainly field execution discipline; not sure. |
| 1.2 | Which parts of the flow most often need to stay synchronised for shipment execution to work reliably? | Checkboxes | Cargo/source readiness; quality/blending; jetty/BLC loading; tug-barge assignment; river/tide/bridge movement; CTS/floating crane availability; OGV laycan/hatch sequence; survey/closure; other. |
| 1.3 | When one part of the chain changes, how often does it create downstream disruption in other parts of the operation? | Multiple choice | Rarely / sometimes / often / almost always / not tracked. |
| 1.4 | In the last few months, which coordination gaps have created the most operational pressure? | Checkboxes | Late plan change; unclear latest plan; cargo not ready; quality/source change; jetty queue; tide/bridge restriction; CTS queue; OGV delay; field update gap; decision approval delay; other. |
| 1.5 | What should the diagnostic prioritise first if time is limited? | Multiple choice | Planning volatility; cargo/quality readiness; tug-barge cycle and waiting; tide/bridge/grounding; CTS/OGV bottleneck; visibility/reporting gap; decision governance; shared KPI alignment. |

## 2. Planning Volatility and Replanning Burden

| No. | Question | Response type | Expected answer guidance |
|---|---|---|---|
| 2.1 | After the monthly or OGV shipment plan is released, how often does it materially change before execution? | Multiple choice | Monthly / weekly / daily / intra-day / event-driven / not tracked. |
| 2.2 | Which changes most commonly force replanning? | Checkboxes | Source jetty change; production shift; coal quality or blending change; OGV ETA/laycan change; hatch/loading sequence change; tug-barge availability; CTS/floating crane availability; tide/bridge/weather; survey or closure issue; other. |
| 2.3 | When a plan changes, is the latest approved plan clearly visible to all relevant teams? | Multiple choice | Yes consistently / partly / no, multiple versions exist / depends on team / not sure. |
| 2.4 | How much manual effort is typically required to revise the plan after a material change? | Multiple choice | Low / moderate / high / very high / not tracked. |
| 2.5 | How often are assets already assigned or moving when the instruction changes? | Multiple choice | Rarely / monthly / weekly / daily / multiple times per day / not tracked. |
| 2.6 | Please describe one recent replanning event that illustrates the current challenge. | Paragraph | Briefly describe what changed, how late it was known, and what operational impact followed. |

## 3. Cargo Readiness, Quality and Source Dependency

| No. | Question | Response type | Expected answer guidance |
|---|---|---|---|
| 3.1 | Does ABL usually receive cargo source, quality and release information early enough to plan execution confidently? | Multiple choice | Yes consistently / partly / usually late / not visible enough / varies by shipment. |
| 3.2 | How often does an OGV require cargo from multiple jetties, grades or sources? | Multiple choice | Rarely / sometimes / often / most shipments / not tracked. |
| 3.3 | When source or quality requirements change, what impact is most common? | Checkboxes | Barge reassignment; jetty sequence change; waiting for cargo release; loading delay; OGV loading sequence change; quality recheck; no major impact; not tracked; other. |
| 3.4 | Once a tug-barge load is linked to a buyer, OGV or quality requirement, how flexible is reassignment? | Multiple choice | Freely reassignable / possible with approval / difficult due to quality constraints / usually not allowed / unclear. |
| 3.5 | Are cargo blocks, quality holds or release delays visible before tug-barge dispatch? | Multiple choice | Yes consistently / partly / usually late / no / not sure. |
| 3.6 | Please share one example where source, quality or cargo readiness created waiting, reassignment or delay. | Paragraph | Short factual example only; no detailed quality data needed. |

## 4. Tug-Barge Cycle, Waiting and Capacity Stress

| No. | Question | Response type | Expected answer guidance |
|---|---|---|---|
| 4.1 | Does the current planning process adequately account for the difference between near, medium and far jetty cycle times? | Multiple choice | Yes / partly / no / mostly experience-based / not sure. |
| 4.2 | Are the directional cycle-time ranges in the synthesis broadly valid: near movements around 9-12 hours plus loading/unloading, far movements around 48-70 hours? | Multiple choice | Broadly valid / partially valid / too high / too low / not known. |
| 4.3 | When production shifts from near jetties to far jetties, what happens operationally? | Checkboxes | More fleet required; OGV delay risk increases; urgent charter need; more waiting/queueing; plan becomes unstable; little impact; not tracked; other. |
| 4.4 | Is the directional feedback that tug-barge productive time is around 55-60 percent broadly accepted as a current operating reality? | Multiple choice | Yes / directionally yes but needs validation / no / not measured / not sure. |
| 4.5 | What are the most common causes of tug-barge waiting or unproductive time? | Checkboxes | Waiting for instruction; jetty queue; CTS/floating crane queue; OGV delay; tide/bridge wait; cargo/quality hold; breakdown/maintenance; reassignment; survey/closure hold; weather; other. |
| 4.6 | How quickly can additional charter capacity normally become operational when demand increases? | Multiple choice | Same day / 1-3 days / around one week / more than one week / varies / not known. |

## 5. Navigation Constraints, Grounding and Controlled Waiting

| No. | Question | Response type | Expected answer guidance |
|---|---|---|---|
| 5.1 | Before releasing a tug-barge movement, are tide, bridge and draft constraints consistently considered? | Multiple choice | Yes consistently / checked manually / only for selected movements / not consistently / not sure. |
| 5.2 | How often do missed tide windows, bridge waits, draft limits or low-water/grounding events create material delay? | Multiple choice | Rarely / monthly / weekly / daily / not tracked. |
| 5.3 | Is controlled waiting accepted as a valid operational decision when it prevents grounding or larger downstream delay? | Multiple choice | Yes and documented / accepted informally / depends on person/team / usually challenged / not accepted. |
| 5.4 | When field teams hold or delay movement for tide/bridge reasons, can they justify the decision with clear evidence? | Multiple choice | Yes, with evidence / sometimes / mostly verbal / no / not sure. |
| 5.5 | Which evidence is available today to support route-window decisions? | Checkboxes | Tide table; bridge-window information; draft restriction guidance; known safe waiting points; grounding/low-water incident history; weather stoppage history; none; unknown. |

## 6. Execution Visibility and Operating Truth

| No. | Question | Response type | Expected answer guidance |
|---|---|---|---|
| 6.1 | Which sources currently provide operating visibility? | Checkboxes | AIS/Spinergie position view; Spinergie reports; Excel updates; WhatsApp; phone/radio; operational database; field report form; meeting updates; other. |
| 6.2 | Does current fleet tracking reliably show what the asset is doing, or mainly where it is located? | Multiple choice | Reliably shows activity state / partly shows activity state / mainly location only / not used consistently / not sure. |
| 6.3 | Which activity states are reliably visible during execution? | Checkboxes | Assigned; sailing; arrived jetty; waiting; loading; loaded/departed; waiting tide/bridge; arrived CTS/OGV; discharging; returning; available; breakdown/maintenance; reassigned; not reliable. |
| 6.4 | How consistent and timely are field updates from tug-barge, jetty and CTS operations? | Multiple choice | Consistent and timely / timely but not standardised / delayed but usable / inconsistent / not reliable. |
| 6.5 | Where are waiting and delay reasons normally captured today? | Checkboxes | Excel; operational report; Spinergie/SOF; WhatsApp; phone/voice only; delay log; not captured consistently; other. |
| 6.6 | Please share one example where position was known but actual activity status or reason for waiting was unclear. | Paragraph | Short factual example. |

## 7. CTS, OGV, Survey and Downstream Dependencies

| No. | Question | Response type | Expected answer guidance |
|---|---|---|---|
| 7.1 | How often does CTS/floating crane availability cause tug-barge waiting, resequencing or delay? | Multiple choice | Rarely / monthly / weekly / daily / not tracked. |
| 7.2 | Is OGV hatch/layering or loading sequence information available early enough to guide barge sequencing? | Multiple choice | Yes consistently / partly / usually late / only during OGV loading / not sure. |
| 7.3 | Are survey, certification or statement-of-facts holds visible before they block loading, completion or departure? | Multiple choice | Yes consistently / partly / usually late / only after closure / not sure. |
| 7.4 | Which downstream dependencies most often affect upstream scheduling? | Checkboxes | CTS queue; floating crane downtime; OGV ETA/laycan change; hatch/layering sequence; survey hold; statement-of-facts closure; demurrage risk; customer priority; other. |
| 7.5 | Please describe one recent downstream dependency that caused upstream waiting or re-planning. | Paragraph | Short factual example. |

## 8. Cross-Entity Coordination, Governance and Outcomes

| No. | Question | Response type | Expected answer guidance |
|---|---|---|---|
| 8.1 | Which operating decisions are hardest to make quickly today? | Checkboxes | Release now vs wait; redirect to another jetty; reassign to another OGV/buyer; change CTS priority; trigger charter capacity; recover from OGV delay; explain delay reason; confirm asset availability; other. |
| 8.2 | When significant decisions are made, are they clearly approved and recorded? | Multiple choice | Yes / partly / informal only / no / not sure. |
| 8.3 | What most often causes disagreement after delays? | Checkboxes | Multiple plan versions; unclear timestamp; no agreed delay reason; local KPI conflict; AIS/report conflict; upstream change not visible; waiting seen as idle; decision owner unclear; other. |
| 8.4 | Which shared outcomes should the diagnostic validate first? | Checkboxes | Improved operational synchronisation; reduced avoidable waiting; better laycan/OGV compliance; faster disruption response; process-backed field decisions; clearer delay attribution; better charter/resource planning; cross-functional KPI alignment. |
| 8.5 | What kind of evidence would make a release, wait, redirect or recovery recommendation credible to operations leadership? | Paragraph | Examples: plan change, tide/bridge risk, queue status, OGV delay, cargo release status, asset availability, field confirmation. |
| 8.6 | What would make the diagnostic and blueprinting phase successful from ABL’s perspective? | Paragraph | High-level expectation, decision needed, or outcome desired. |

## 9. Evidence Availability for Diagnostic and Blueprinting

This section confirms whether representative evidence exists. It does not request detailed master data inside the form.

| No. | Question | Response type | Expected answer guidance |
|---|---|---|---|
| 9.1 | Which representative evidence can be made available for diagnostic review? | Checkbox grid | Rows: current schedule file; OGV programme/change history; cargo/source readiness view; sample quality/release status; trip movement history; waiting/delay records; AIS/Spinergie sample; tide/bridge information; CTS/OGV status sample; survey/SOF sample; charter lead-time example. Columns: exists and shareable; exists but needs approval; exists but not structured; not available; unknown. |
| 9.2 | What diagnostic sample period is realistic? | Multiple choice | Selected incidents only / last 2 weeks / last 1 month / last 3 months / last 6 months / not sure. |
| 9.3 | Can sample data or documents be shared with sensitive fields redacted if needed? | Multiple choice | Yes / yes with approval / no / not sure. |
| 9.4 | Who should coordinate evidence collection and workshop scheduling from the ABL side? | Short answer | Name or role only. |
| 9.5 | What known reliability issues should the diagnostic account for when reviewing evidence? | Paragraph | Examples: delayed updates, manual correction, missing timestamp, inconsistent reason codes, multiple plan versions, incomplete tracking coverage. |
