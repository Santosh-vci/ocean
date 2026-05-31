# 29 - Phase 5 Recovery UI State Guide

## Purpose

This guide is for the operator running the Phase 5 recovery trial from the UI.

It explains what each dense screen is showing, which exact vessel/cargo/asset facts matter, why the state exists, and what the Next Action recommendation should be guiding next.

Use the reset command in `28_Phase_5_Recovery_Operator_Trial_Runbook.md`, then perform the business steps from the UI. Do not use shortcut commands for the operator walkthrough.

## Stable Trial References

Runtime-generated row IDs include values like `EX-3799`, `MAC-31657E06B56E`, `REC-...`, `SIM-...`, and `PLAN-UI-...`. They can change after reset. The stable facts to recognize are the vessel, cargo, asset, gate, and state names below.

| Stable reference | What it means in the recovery trial |
|---|---|
| `MV PACIFIC PRIDE` | Main vessel with three executable movements: `EBONY H1/L1`, `AGATHIS H1/L2`, and blocked `EBONY H2/L1`. |
| `MV PACIFIC PRIDE / EBONY / H2/L1` | Main recovery movement. Initially planned around `JTY-SUARAN`, `BRG-KAL-22` or recovery candidate `BRG-NUS-17`, and `CTS-BORNEO`. |
| `MV NORTH STAR / SUNGKAI / H2/L2` | Sequence recovery movement. Uses `JTY-LATI`, `BRG-NUS-17`, and `FC-CHLOE`; blocked by the Mahoni-before-Sungkai sequence rule and bridge timing. |
| `MV TRITON STAR / EBONY / H1/L1` | Feasible movement normally using `BER-TUG-09`, `BRG-VAL-08`, `JTY-SUARAN`, and `CTS-BORNEO`. |
| `MV GOLDEN ORIOLE / MAHONI / H1/L1` | Future/pre-laycan movement. It can show warning state because it may not yet have a matching movement-intent navigation check. |
| `Rantau Delta` | Tide gate used by the Pacific Pride and Triton movements. |
| `Bridge Gate B` | Bridge gate used by North Star and other restricted movements. |
| `TIDE-TRIAL-RANTAU-01` | Normal Rantau tide slot. |
| `TIDE-TRIAL-RANTAU-02` | Tight Rantau tide slot used to expose recovery risk. |
| `BRDG-TRIAL-GATE-B-02` | Restricted Bridge Gate B slot with pilot approval requirement. |
| `BRDG-TRIAL-GATE-B-03` | Closed Bridge Gate B maintenance hold. |

## What To Watch

At every step, look at four things:

| UI signal | What to read |
|---|---|
| Next Action | The recommended next screen or CTA for the current flow state. |
| Counts | Demand rows, cargo movements, candidate-covered movements, trips, active conflicts, approvals, blockers, and warnings. |
| Status labels | `generated/blocked`, `proposed/feasible`, `approved/feasible`, `publishable`, `warning`, or `published`. |
| Detail panels | The exact vessel, cargo layer, gate, asset, and root-cause or publishability reason. |

## Step-By-Step UI State

| Step | Screen | Next Action should guide to | What the operator should see | Why this matters |
|---:|---|---|---|---|
| 1 | Planning -> OGV Demand & Laycan | Import demand | 5 OGV demand rows are imported: `MV PACIFIC PRIDE`, `MV OCEAN VOYAGER`, `MV NORTH STAR`, `MV GOLDEN ORIOLE`, and `MV TRITON STAR`. The imported pack contains 8 cargo requirement rows and 6 executable cargo-layer movements. No plan exists yet. | This is the business start. The system knows the vessels and cargo demand, but no tug/barge/jetty/CTS assignment has been committed. |
| 2 | Planning -> Coal Grade Sequence | Review coal grade sequence, then continue to operating windows | The key row to notice is `MV NORTH STAR / SUNGKAI / H2/L2`. Its state can show `SEQUENCE VIOLATION` with the reason `Mahoni layer cannot precede Sungkai approval`. | This is a known recovery issue. It is not a live failure yet; it is a planning rule problem that must be carried into recovery and cleared before publish. |
| 3 | Constraints -> Tide & Bridge Window | Enter tide and bridge windows | The page creates trial windows: `TIDE-TRIAL-RANTAU-01`, `TIDE-TRIAL-RANTAU-02`, `TIDE-TRIAL-DEEP-01`, `BRDG-TRIAL-GATE-B-01`, `BRDG-TRIAL-GATE-B-02`, and `BRDG-TRIAL-GATE-B-03`. It also creates 6 movement-intent checks. Important checks include `MV PACIFIC PRIDE / EBONY H2/L1` waiting on Rantau Delta and `MV NORTH STAR / SUNGKAI H2/L2` missing Bridge Gate B. | These are forward-looking feasibility checks against imported movement intents. They are not retrospective live misses. They explain which future movements will fail if planned against the current windows. |
| 4 | Operations -> Tug/Barge Assignment | Generate candidates, then Generate plan / Regenerate plan | Candidate coverage should show 6 movements. The important candidate rows are: `MV PACIFIC PRIDE / EBONY H2/L1` blocked with `Waiting for tide window at Rantau Delta`; `MV NORTH STAR / SUNGKAI H2/L2` blocked with `Mahoni layer cannot precede Sungkai approval`; feasible rows for `MV PACIFIC PRIDE / EBONY H1/L1`, `MV PACIFIC PRIDE / AGATHIS H1/L2`, and `MV TRITON STAR / EBONY H1/L1`; `MV GOLDEN ORIOLE / MAHONI H1/L1` can remain warning. | This is where the app converts demand plus constraints into proposed operating chains. Blocked candidates must not silently assign invalid tug/barge/CTS resources. They should create plan conflicts for recovery. |
| 5 | Recovery Loop -> Exception Center | Generate recovery options | The conflict queue should show generated-plan blockers tied to concrete movements. In the current recovery flow, the stable blockers are `MOVEMENT_ASSIGNMENT_BLOCKED` for `MV PACIFIC PRIDE / EBONY H2/L1` with `Waiting for tide window at Rantau Delta`, and `MOVEMENT_ASSIGNMENT_BLOCKED` for `MV NORTH STAR / SUNGKAI H2/L2` with `Mahoni layer cannot precede Sungkai approval`. Older evidence may also show `TIDE_WINDOW_MISSED` at Rantau Delta or `BRIDGE_WINDOW_MISSED` at Bridge Gate B when running the prepared recovery segment. | The generated plan is not publishable. These rows are the formal recovery problem statement. The operator should not submit approval while these rows are active. |
| 6 | Recovery Loop -> Recommendation Console | Validate root-cause repair | Five recovery options are generated. Do not trust rank alone. Validate the chosen option. A useful option must produce root-cause status `addresses_cause` or `mitigates_cause`. The tested recovery closure used recommendation `REC-7BED0F612590`, which produced `mitigates_cause` for source cause `BRIDGE_WINDOW_MISSED`. | Recovery recommendations are advisory. A high-ranked option that fails root-cause validation must not be used for publish. The validation tells the operator whether the option really fixes or mitigates the original physical cause. |
| 7 | Recovery Loop -> Recommendation Console | Test recommendation as scenario | The selected recommendation gets materialized as a scenario, for example `SIM-PLAN-RECOVERY-PRACTICE-20260531-V1-01`. The UI should then move toward simulation. | The recommendation still has not changed the plan. Scenario materialization creates a controlled candidate path that can be tested without silently editing the live plan. |
| 8 | Recovery Loop -> Simulation Workspace | Run simulation or Enter operating windows | The first scenario run can still show simulated constraints. In evidence, the first run had critical simulated constraints, so promotion was blocked. | A scenario is not ready just because it exists. The operator must see whether the proposed repair actually clears the modeled tide, bridge, resource, and sequence risks. |
| 9 | Constraints -> Tide & Bridge Window | Enter operating windows | The repair CTA adds targeted recovery windows. The UI should show additional `TIDE-OPERATOR-RECOVERY-*` and `BRDG-OPERATOR-RECOVERY-*` slots, not one blanket horizon-wide opening. | This is a repair of the operating context for the selected scenario path. It gives the candidate a governed window to clear the physical timing problem. |
| 10 | Recovery Loop -> Simulation Workspace | Run simulation | A second scenario run should be created. In the tested closure, selected run `RUN-SIM-PLAN-RECOVERY-PRACTICE-20260531-V1-01-02` cleared critical blockers. | This is the proof that the repair can work operationally. Promotion should only become available after the selected run clears critical blockers. |
| 11 | Recovery Loop -> Simulation Workspace | Promote scenario | The promoted plan becomes the recovery candidate, for example `PLAN-RECOVERY-PRACTICE-20260531 V2`, with status `proposed` and validation `feasible`. Open blocking conflicts for the publish candidate should be 0. | The recovery path has now created a governed plan candidate. It is still not approved and not published. |
| 12 | Schedule -> Published Plan & Schedule | Submit approval | The recovered plan should be visible as the plan candidate. It should carry recovery provenance back to the selected recommendation, scenario, baseline version, and selected simulation run. | This is the governance handoff. The operator is reviewing the recovered candidate before asking Berau/ABL for approval. |
| 13 | Recovery Loop -> Approvals & Publishing | Approve plan | One approval request should exist. The first approval records one authority; the second approval completes the required `berau_scheduler` and `abl_dispatcher` approvals. | Approval is business sign-off. It does not replace the publishability gate. |
| 14 | Recovery Loop -> Approvals & Publishing | Check publishability | Publishability must show 0 blockers. For the tested closure, status was `warning`, blockers `0`, warnings `1`, with detail `recommendation_origin_root_cause`: source cause `BRIDGE_WINDOW_MISSED`, root-cause status `mitigates_cause`, residual risk medium. | This is the final operational gate. A warning means the hard gates are clear but the operator must understand residual risk. A blocker means do not publish. |
| 15 | Recovery Loop -> Approvals & Publishing | Publish plan | The publish button should be enabled only after approvals are complete and publishability is `publishable` or `warning`. After click, the plan status becomes `published`, validation remains `feasible`, and an active published snapshot exists with recovery provenance. | The recovered plan is now the execution contract. This is the end of the recovery walkthrough. |

## How To Read The Dense Screens

### Coal Grade Sequence

Focus on `MV NORTH STAR / SUNGKAI / H2/L2`.

If the UI says `Mahoni layer cannot precede Sungkai approval`, it means the cargo order is not clean for that vessel. This is why the recovery path must prove the final promoted plan has no active cargo-sequence blocker before publish.

### Tide & Bridge Window

Stage 3 is not showing live failures. It is showing projected movement-intent feasibility.

Use these exact checks as anchors:

| Movement | Expected check meaning |
|---|---|
| `MV PACIFIC PRIDE / EBONY H1/L1 / BRG-VAL-08` | Can cross Rantau Delta on the normal tide slot. |
| `MV PACIFIC PRIDE / AGATHIS H1/L2 / BRG-NUS-17` | Can use restricted Bridge Gate B with pilot clearance. |
| `MV PACIFIC PRIDE / EBONY H2/L1 / BRG-KAL-22` | Waiting on the tight Rantau Delta tide slot. |
| `MV NORTH STAR / SUNGKAI H2/L2 / BRG-NUS-17` | Misses Bridge Gate B and needs recovery. |
| `MV GOLDEN ORIOLE / MAHONI H1/L1 / BRG-KAL-22` | Awaiting a future bridge slot before dispatch. |
| `MV TRITON STAR / EBONY H1/L1 / BRG-VAL-08` | Can cross on the tight Rantau Delta tide slot. |

### Tug/Barge Assignment

The candidate table is a pre-generation planning surface.

The operator should check that every cargo movement is covered and that blocked movements do not receive an invalid committed chain.

Use these exact rows as anchors:

| Movement | Expected candidate state | Why |
|---|---|---|
| `MV PACIFIC PRIDE / EBONY H1/L1` | Feasible, usually `BER-TUG-08 / BRG-VAL-08 / JTY-SUARAN / CTS-BORNEO`. | Already safe against current constraints. |
| `MV PACIFIC PRIDE / AGATHIS H1/L2` | Feasible, using `BER-TUG-08 / BRG-NUS-17` with a valid jetty/CTS chain. | Can proceed while the blocked EBONY movement is recovered separately. |
| `MV PACIFIC PRIDE / EBONY H2/L1` | Blocked, reason `Waiting for tide window at Rantau Delta`. | This is the primary movement that drives recovery. |
| `MV NORTH STAR / SUNGKAI H2/L2` | Blocked, reason `Mahoni layer cannot precede Sungkai approval`; may also show bridge miss. | This protects the cargo sequence and bridge rule. |
| `MV TRITON STAR / EBONY H1/L1` | Feasible, usually `BER-TUG-09 / BRG-VAL-08 / JTY-SUARAN / CTS-BORNEO`. | This should not be the main recovery blocker. |
| `MV GOLDEN ORIOLE / MAHONI H1/L1` | Warning possible, because it can be outside the current movement-intent gate check. | This is future/pre-laycan risk, not the main recovery block. |

### Exception Center

Read each row as a formal blocker on the generated plan, not as a suggestion.

Important rows are:

| Conflict type | Stable business object | Why it blocks |
|---|---|---|
| `MOVEMENT_ASSIGNMENT_BLOCKED` | `MV PACIFIC PRIDE / EBONY H2/L1` | The planned movement cannot be safely dispatched because the Rantau Delta tide timing is not feasible. |
| `MOVEMENT_ASSIGNMENT_BLOCKED` | `MV NORTH STAR / SUNGKAI H2/L2` | The movement violates the cargo sequence rule and can also miss Bridge Gate B. |
| `TIDE_WINDOW_MISSED` if visible | Rantau Delta / tight tide slot | The selected dispatch timing cannot make the tide gate. |
| `BRIDGE_WINDOW_MISSED` if visible | Bridge Gate B / restricted slot | The selected movement timing cannot make the bridge lift. |

If these rows are active, approval and publish should not proceed.

### Recommendation Console

Use ranking as a starting point, not as authority.

The operator must inspect the selected recommendation and root-cause assessment:

| Root-cause status | Meaning | Publish outcome |
|---|---|---|
| `addresses_cause` | The option directly removes the source cause. | Can proceed if later gates are clear. |
| `mitigates_cause` | The option manages the risk but leaves residual risk. | Can proceed as publishability warning if later gates are clear. |
| `does_not_address_cause` | The option improves something else but not the real source cause. | Must block publishability. |
| `unknown` | The system cannot prove the option addresses the source cause. | Must block publishability. |

### Simulation Workspace

The operator should not promote just because a scenario exists.

Look for:

- selected scenario from the tested closure: `SIM-PLAN-RECOVERY-PRACTICE-20260531-V1-01`;
- selected run from the tested closure: `RUN-SIM-PLAN-RECOVERY-PRACTICE-20260531-V1-01-02`;
- critical simulated constraints cleared before `Promote to proposed` is allowed.

### Approvals & Publishing

The operator should confirm three things:

| Gate | Required state |
|---|---|
| Approval | Both required approvals complete: `berau_scheduler` and `abl_dispatcher`. |
| Publishability | 0 blockers. Status must be `publishable` or `warning`. |
| Recovery-origin detail | `recommendation_origin_root_cause` present, with `addresses_cause` or `mitigates_cause`. |

If the gate shows a blocker, the operator must fix the blocker and run `Check publishability` again.

## Final State To Confirm

At the end of the recovery trial, the UI should show:

| Final UI state | Expected result |
|---|---|
| Plan | Recovery candidate version, normally V2 or later |
| Plan status | `published` |
| Validation status | `feasible` |
| Open blocking conflicts | `0` |
| Approval decisions | Required Berau/ABL approvals complete |
| Publishability | `publishable` or `warning`, with `0` blockers |
| Root-cause assessment | `addresses_cause` or `mitigates_cause` |
| Published snapshot | Active and carrying recovery provenance |

If any one of these is missing, the recovery flow is not complete.
