# 24 - Phase 5 Operator Runbook

## Purpose

Phase 5 is not just another screen. It is the first decision-support layer.

The operator starts from a real operating problem, retrieves the affected plan context, asks the system for recovery choices, compares the choices, tests the best choice as a scenario, and then sends it through governance.

The important business question is:

> Given the current coal movement plan, which recovery action reduces disruption without silently changing the live plan?

Phase 5 answers that question with a ranked recommendation, scenario evidence, approvals, and audit history.

## Run Type Map

Do not use the same run label for every rehearsal. There are four different flows:

| Run type | Command or entry point | Use it for | Expected end state |
|---|---|---|---|
| Operator happy path | UI from `http://localhost:8080`, starting with **Import OGV demand** | Manual operator rehearsal of the clean planning transaction. | A `PLAN-UI-... V1` plan is generated, approved, and published with no open blocking conflicts. |
| Automated happy-path regression | `docker compose exec -T api python manage.py phase1_e2e_proof --json` | Machine-readable regression proof for the same clean planning capability. | `PLAN-PHASE1-E2E` is `published` and `feasible`, with 2 trips, 14 schedule events, a live snapshot, and a governed printable export. |
| Phase 5 staged recovery practice | `operator_trial_practice reset`, `import-demand`, `enter-windows`, `generate-plan` | Manual operator practice from empty demand into a deliberately blocked recovery case. | `PLAN-<trial date> V1` is generated with 6 trips and 4 open exceptions. |
| Phase 5 proof and closure | `phase5_recovery_proof --json`, then `phase5_resolve_trial_pack --json` | Automated evidence for recommendation retrieval/ranking/scenario handoff, followed by clean closure. | Recovery proof is audit-visible; closure version is approved, feasible, and ready to publish. |

The operator happy path is **not** the Phase 5 recovery drill. The happy path proves that the ordinary planning transaction can finish from imported demand through publication. The Phase 5 drill proves that the operator can recover a disrupted transaction without silently editing the live plan.

## Operator Happy Path Run

The happy path starts with the first business action: importing OGV demand. The master-data reset is setup only; it is not part of the operator transaction.

Setup from `F:\ocean`:

```text
docker compose up -d
docker compose exec -T api python manage.py seed_phase0 --master-data-only
```

Then run the operator flow in the UI:

| Step | Screen | Operator action | Expected evidence |
|---|---|---|---|
| 1 | **Planning -> OGV Demand & Laycan** | Click **Import demand**. | One clean operator OGV demand is imported: `MV Operator UI Import`, 64,000 MT, with two cargo layers. |
| 2 | **Planning -> Coal Grade Sequence** | Review the imported hatch/layer chain. | Sequence is readable before planning: `EBONY` H1/L1 and `AGATHIS` H2/L1. For the clean import there should be no blocking sequence conflict. |
| 3 | **Constraints -> Tide & Bridge Window** | Click **Enter operating windows**. | Two tide windows, two bridge windows, asset availability, jetty availability, and navigation checks are created. |
| 4 | **Operations -> Tug/Barge Assignment** | Click **Regenerate plan**. | The first `PLAN-UI-... V1` version is created and generated; it has 2 trips and no open blocking conflicts. |
| 5 | **Schedule -> Published Plan & Schedule** | Click **Submit approval**. | One dual-authority approval request is created for the generated plan. |
| 6 | **Recovery Loop -> Approvals & Publishing** | Click **Approve** for the first required authority. | First approval decision is recorded. |
| 7 | **Recovery Loop -> Approvals & Publishing** | Click **Approve** for the second required authority. | Required approvals are complete and **Publish plan** becomes available. |
| 8 | **Recovery Loop -> Approvals & Publishing** | Click **Publish plan**. | The active `PLAN-UI-... V1` plan becomes `published`; a live published snapshot exists. |
| 9 | **Admin Console -> Exports & Handoff** | Optional: generate the printable schedule export. | A governed export artifact exists for external handoff. This is post-publication handoff, not a precondition for publication. |

Latest local validation on 26 May 2026 reached the required publication endpoint:

| Evidence | Runtime value |
|---|---|
| OGV demand | 1 voyage |
| Cargo layers | 2 |
| Tide windows | 2 |
| Bridge windows | 2 |
| Plan version | `PLAN-UI-... V1` |
| Plan status | `published` |
| Validation status | `feasible` |
| Trips | 2 |
| Open conflicts | 0 |
| Approval requests | 1 |
| Approval decisions | 2 |
| Published snapshots | 1 |

Business interpretation:

The happy path proves a clean planning transaction: demand is imported first, the cargo sequence is visible, operating constraints are entered, the plan is generated without blockers, both required authorities approve, and the final plan is published.

Use these UI routes while walking the flow:

- `http://localhost:8080/#/dashboard/situation`
- `http://localhost:8080/#/schedule/ogv-demand`
- `http://localhost:8080/#/schedule/coal-grade-sequence`
- `http://localhost:8080/#/constraints/tide-bridge`
- `http://localhost:8080/#/operations/tug-barge-assignment`
- `http://localhost:8080/#/schedule/published-plan`
- `http://localhost:8080/#/approvals/publishing`
- `http://localhost:8080/#/admin/export-handoff`

Automated regression check:

```text
docker compose exec -T api python manage.py phase1_e2e_proof --json
```

This command is useful evidence, but it is not the operator happy-path run because it executes the workflow automatically. Use it to confirm the clean transaction still works in CI or release validation.

## Seed And Proof Command Availability

Availability was checked in the running `api` container with `python manage.py help` on 26 May 2026.

| Command | Available | Purpose | Notes |
|---|---:|---|---|
| `seed_phase0` | Yes | Baseline local-development seed. | Supports `--master-data-only` and `--reset-operational-data`. `--master-data-only` clears planning/scheduling/export/audit records and keeps users, roles, permissions, and master data. |
| `seed_phase3_replay` | Yes | Deterministic Phase 3 synthetic replay runs. | Supports `--preserve-status`. |
| `seed_assistant_recovery_practice` | Yes | Multi-OGV Assist Super recovery practice case. | Supports `--skip-reset` and `--json`. This is a recovery practice seed, not the clean happy path. |
| `operator_trial_practice` | Yes | Staged Phase 5 operator recovery practice and Phase 6 DB-truth trial preparation. | Supports `reset`, `import-demand`, `enter-windows`, `generate-plan`, `status`, and `prepare-db-truth --flow happy-path\|recovery`, plus `--json`. Preparation commands set deterministic DB truth only; accepted operator evidence still comes from visible UI CTAs assisted by Next Action. |
| `phase1_e2e_proof` | Yes | Automated clean-transaction regression proof. | Supports `--json` and `--skip-seed`. Use it for evidence/CI, not as the operator happy-path definition. |
| `phase2_scenario_proof` | Yes | Phase 2 scenario proof. | Supports `--json` and `--skip-seed`. |
| `phase3_tracking_proof` | Yes | Phase 3 synthetic tracking proof. | Supports `--json` and `--skip-seed`. |
| `phase4_operations_proof` | Yes | Phase 4 synthetic operations replay proof. | Supports `--json` and `--skip-seed`. |
| `phase5_recovery_proof` | Yes | Phase 5 recommendation proof. | Supports `--json` and `--skip-seed`. It proves recovery recommendation flow, not full closure. |
| `phase5_resolve_trial_pack` | Yes | Phase 5 clean closure command. | Supports `--json`. It resolves the staged trial pack into an approved feasible closure state. |
| `seed_happy_path` | No | Not implemented. | No dedicated seed is required. Start from `seed_phase0 --master-data-only`, then begin the happy path with the UI **Import demand** action. |

## Practice Reset And Staged Commands

Run these commands from `F:\ocean`.

```text
docker compose up -d --build db redis object-store api frontend proxy worker beat
docker compose ps
```

These commands start the application services. They do not create a new business scenario by themselves. They bring up the database, API, frontend, worker, scheduler, object store, and proxy.

The operator practice pack now starts with **no OGV demand and no generated schedule**. Run:

```text
docker compose exec -T api python manage.py operator_trial_practice reset --json
```

Expected state after reset:

| Area | Trial state |
|---|---|
| Master data | Seeded |
| Users and roles | Seeded |
| Telemetry identities | Seeded |
| Operations feeds/devices | Seeded |
| OGV orders | 0 |
| Cargo requirements | 0 |
| Hatch/layer steps | 0 |
| Operating windows | 0 |
| Plan versions | 0 |
| Trips | 0 |
| Exceptions | 0 |

The first operator business action is demand import, not recovery.

```text
docker compose exec -T api python manage.py operator_trial_practice import-demand --json
```

Expected state after demand import:

| Area | Trial state |
|---|---|
| OGV orders | 5 active or planned vessel orders |
| Cargo requirements | 8 cargo requirement rows |
| Hatch/layer steps | 6 cargo layer steps |
| Import job | 1 governed OGV demand import |
| Operating windows | 0 |
| Generated plan | None |
| Planned trips | 0 |
| Starting exceptions | 0 |

Then enter the operational windows and resource availability package:

```text
docker compose exec -T api python manage.py operator_trial_practice enter-windows --json
```

Expected state after window entry:

| Area | Trial state |
|---|---|
| Tide windows | 3 |
| Bridge windows | 3 |
| Asset availability rows | 3 |
| Jetty availability rows | 3 |
| Navigation checks | 5 |
| Generated plan | None |
| Planned trips | 0 |

Then generate the schedule and tug/barge/jetty/CTS assignments:

```text
docker compose exec -T api python manage.py operator_trial_practice generate-plan --json
```

Expected state after plan generation:

| Area | Trial state |
|---|---|
| Generated plan | `PLAN-2026-05-26 V1` |
| Planned trips | 6 tug/barge trips |
| Starting exceptions | 4 unresolved exceptions |
| Blocking exceptions | 3 |
| Warning exceptions | 1 |

The trial is built around a Berau-to-CTS/OGV flow. The plan has to move coal from source jetties, through tug/barge assignments, through bridge and tide constraints, into CTS/floating-crane discharge.

## Starting Business State

The import step creates these OGV orders.

| OGV order | Customer | Cargo requirement | Business state |
|---|---|---|---|
| `MV PACIFIC PRIDE` | Glencore | 165,000 MT across `EBONY` and `AGATHIS` | Active. Most of the cargo is already handled, but one remaining movement is blocked. |
| `MV OCEAN VOYAGER` | Vitol | 120,000 MT `MAHONI` | At risk. Final top-off remains exposed to low-tide draft restriction. |
| `MV TRITON STAR` | Trafigura | 180,000 MT `EBONY` | At risk. Feeder delay is already visible. |
| `MV NORTH STAR` | Nippon Steel | 98,000 MT across `AGATHIS` and `SUNGKAI` | At risk. Bridge timing and grade sequence are both problematic. |
| `MV GOLDEN ORIOLE` | Korea Power | 210,000 MT across `EBONY` and `MAHONI` | Planned. ETA confirmation is still pending. |

The schedule generation step creates these six trip movements.

| Trip | OGV order | Cargo | Jetty | Tug / barge | CTS | Business context |
|---|---|---|---|---|---|---|
| `PI-PLAN-2026-05-26-0001` | `MV PACIFIC PRIDE` | 32,000 MT `EBONY` | `JTY-SUARAN` | `BER-TUG-08` / `BRG-VAL-08` | `CTS-BORNEO` | Already at CTS. No critical blocker. |
| `PI-PLAN-2026-05-26-0002` | `MV PACIFIC PRIDE` | 28,000 MT `AGATHIS` | `JTY-LATI` | `BER-TUG-08` / `BRG-NUS-17` | `CTS-JAVA` | Loading, but `JTY-LATI` is reduced in the loading window. |
| `PI-PLAN-2026-05-26-0003` | `MV PACIFIC PRIDE` | 34,000 MT `EBONY` | `JTY-SUARAN` | `BER-TUG-08` / `BRG-KAL-22` | `CTS-BORNEO` | Blocked. This is the main Phase 5 recovery case. |
| `PI-PLAN-2026-05-26-0004` | `MV TRITON STAR` | 36,000 MT `EBONY` | `JTY-SUARAN` | `BER-TUG-09` / `BRG-VAL-08` | `CTS-BORNEO` | Feeder delay is visible. |
| `PI-PLAN-2026-05-26-0005` | `MV NORTH STAR` | 26,000 MT `SUNGKAI` | `JTY-LATI` | `BER-TUG-08` / `BRG-NUS-17` | `FC-CHLOE` | Waiting bridge, and the grade/layer sequence is not clean. |
| `PI-PLAN-2026-05-26-0006` | `MV GOLDEN ORIOLE` | 42,000 MT `MAHONI` | `JTY-SUARAN` | `BER-TUG-08` / `BRG-KAL-22` | `CTS-JAVA` | Future planned movement with ETA uncertainty. |

The generated plan has four starting exceptions.

| Exception | Severity | Affected order and resource | What happened |
|---|---|---|---|
| `BARGE_UNAVAILABLE` | Critical | `MV PACIFIC PRIDE`, trip `0003`, barge `BRG-KAL-22` | The planned barge is unavailable inside the trip window. This makes the planned movement unsafe to rely on. |
| `BRIDGE_WINDOW_MISSED` | Critical | `MV NORTH STAR`, trip `0005` | The projected movement misses the bridge timing requirement. |
| `LAYER_SEQUENCE_VIOLATION` | Critical | `MV NORTH STAR`, trip `0005` | The cargo sequence is not valid: Mahoni cannot precede Sungkai approval. |
| `JETTY_OVERLAP` | Warning | `MV PACIFIC PRIDE`, trip `0002`, jetty `JTY-LATI` | The jetty is reduced during the loading window. This is a monitoring risk, not the main recovery case. |

The key Phase 5 practice case is the `BARGE_UNAVAILABLE` exception on `MV PACIFIC PRIDE`.

Business interpretation:

`MV PACIFIC PRIDE` still needs an `EBONY` movement from `JTY-SUARAN`. The planned chain uses `BER-TUG-08`, `BRG-KAL-22`, and `CTS-BORNEO`. The plan says this movement should depart around 27 May 2026 00:00 UTC and arrive around 27 May 2026 07:00 UTC. The problem is that `BRG-KAL-22` is not available inside that window, so the operator needs a recovery choice before the plan can be trusted.

## What The Proof Command Adds

Run:

```text
docker compose exec -T api python manage.py phase5_recovery_proof --json > docs\evidence\phase5\phase5_recovery_evidence.json
```

This command resets the seed again, then runs the Phase 5 recovery proof flow automatically.

Use this for automated evidence only. For manual operator practice, use the staged commands above so that demand import, window entry, and plan generation are visible as separate business actions.

It does the same business workflow an operator would do manually:

1. It retrieves the `BARGE_UNAVAILABLE` exception.
2. It freezes the current operating context into a recovery input snapshot.
3. It runs the deterministic recovery engine.
4. It creates 5 ranked recommendations.
5. It selects the top recommendation.
6. It materializes that recommendation into a simulation scenario.
7. It promotes the scenario to a proposed candidate plan.
8. It records Berau and ABL approval decisions.
9. It keeps publication blocked because unresolved critical risks remain.
10. It writes audit and proof-pack evidence.

Expected proof evidence:

| Evidence | Expected result |
|---|---|
| Optimizer run | A run like `OPT-P5-RECOVERY-...` |
| Candidate count | 5 recovery options |
| Best strategy | `cts_reassignment` |
| Best score | 89.0 |
| Best risk | Low |
| Scenario | A recommendation-origin scenario such as `SIM-PLAN-2026-05-26-V1-08` |
| Approval | Berau Scheduler and ABL Dispatcher decisions recorded |
| Publish | Still blocked |

The blocked publish state is important. It proves Phase 5 does not bypass governance. A good recovery recommendation can be approved for review, but the plan still cannot publish while critical blockers remain.

## What The Closure Command Adds

The recommendation proof command is intentionally a decision-support proof. It demonstrates retrieval, ranking, scenario handoff, approval, and publish blocking. It does not claim that one recommendation fully repairs every seeded exception.

For formal Phase 5 closure, run the exception-resolution command after the recovery proof flow:

```text
docker compose exec -T api python manage.py phase5_resolve_trial_pack --json
```

This command takes the trial pack from "recommendation proved, but not publishable" to "all seeded exceptions handled and ready to publish".

In the latest runtime validation, the command produced:

| Evidence | Runtime value |
|---|---|
| Prior version | `PLAN-2026-05-26 V1` |
| Closure version | `PLAN-2026-05-26 V2` |
| Closure status | `approved` |
| Closure validation | `feasible` |
| Trips retained | 6 |
| Prior open conflicts | 4 |
| Prior open telemetry alerts | 0 |
| Resolved telemetry alerts | 0 |
| Closure open conflicts | 0 |
| Closure open tracking alerts | 0 |
| Approval request | `APR-PLAN-2026-05-26-V2` |
| Approval decisions | 2 of 2 |
| Definition of done | `PASS`, all exceptions handled |

Business interpretation:

The earlier loop was caused by unresolved exception sources surviving across candidate versions. In the staged trial, the generated plan starts with four open scheduling exceptions. In a replay state that also contains open telemetry alerts, the closure command resolves those alerts too. The command then creates a governed approved successor version.

The command is idempotent. If it is run again after the closure version is already clean and approved, it returns the existing closure version instead of creating another plan version.

After this command, the operator should see:

- **Exception Center**: active `0`, critical `0`, warning `0`, observed `0`, pending `0`, overrides `0`, health `0`;
- **Recommendation Console**: no recovery run required for the clean active plan;
- **Simulation Workspace**: no active scenario required for the clean active plan;
- **Approvals & Publishing**: `READY TO PUBLISH`, `PLAN STATE APPROVED`, and the publish action enabled;
- **Audit & Logs**: `phase5.trial.exceptions_resolved` for the closure version.

## Phase 5 Capability In Simple Terms

Phase 5 has three business capabilities.

### 1. Retrieval

Retrieval means the system can take an operational problem and collect the evidence needed to reason about it.

For the trial case, the retrieved problem is:

`BARGE_UNAVAILABLE` on `MV PACIFIC PRIDE`, trip `PI-PLAN-2026-05-26-0003`, using `BER-TUG-08` / `BRG-KAL-22` from `JTY-SUARAN` to `CTS-BORNEO`.

When the operator generates recovery options, the backend creates a `RecoveryInputSnapshot`. That snapshot captures:

- the active plan version;
- the source exception;
- the affected trip and assignment;
- current unresolved conflicts;
- current resource state;
- schedule events;
- bridge and tide constraint state;
- tracking alerts and confirmed operational events, where available.

Business value:

The recommendation is not based on a loose comment. It is based on a frozen snapshot of the operating situation at the time the operator asked for recovery options.

### 2. Recovery

Recovery means the system calculates possible decisions and ranks them.

For the trial case, the seeded recovery engine produces these options for the `MV PACIFIC PRIDE` disruption.

| Rank | Option | Affected trip | Business meaning | Score / risk |
|---|---|---|---|---|
| 1 | Reassign CTS | `PI-PLAN-2026-05-26-0003` | Keep the trip chain, but move discharge handling from `CTS-BORNEO` to `CTS-JAVA`. This avoids adding missed windows or new resource conflicts in the recommendation evaluation. | 89.0, low |
| 2 | Resequence trips | `PI-PLAN-2026-05-26-0003` and `0004` | Move the Pacific Pride blocked movement after the Triton Star movement, and move Triton Star earlier. | 78.0, medium |
| 3 | Delay trip | `PI-PLAN-2026-05-26-0003` | Keep all resources unchanged and push the movement by 90 minutes. | 70.1, high |
| 4 | Tug/barge swap | `PI-PLAN-2026-05-26-0003` | Change tug to `BER-TUG-09` and barge to `BRG-NUS-17`. | 24.5, high |
| 5 | Next window repair | `PI-PLAN-2026-05-26-0003` | Move the trip to the next feasible tide/bridge gate, shifting by 360 minutes. | 15.3, high |

The top option is:

`Reassign PI-PLAN-2026-05-26-0003 discharge handling to CTS-JAVA.`

Before:

- OGV: `MV PACIFIC PRIDE`
- Cargo: `EBONY`, 34,000 MT
- Jetty: `JTY-SUARAN`
- Tug: `BER-TUG-08`
- Barge: `BRG-KAL-22`
- CTS: `CTS-BORNEO`

After:

- OGV: `MV PACIFIC PRIDE`
- Cargo: `EBONY`, 34,000 MT
- Jetty: `JTY-SUARAN`
- Tug: `BER-TUG-08`
- Barge: `BRG-KAL-22`
- CTS: `CTS-JAVA`

Checks behind the recommendation:

- confirmed actuals are frozen;
- `CTS-JAVA` is available;
- CTS queue overlap needs review;
- no additional missed tide or bridge windows are introduced by this option;
- no additional resource conflict is introduced by this option.

Business interpretation:

The engine is not saying the entire plan is clean. It is saying this is the least risky recovery option among the options it can currently calculate for the selected disruption. It reduces one recovery decision to a governed scenario, while the remaining plan risks still need governance.

Important caveat for operators:

The source exception is `BARGE_UNAVAILABLE`, but the current top-ranked action is a CTS reassignment. That means the Phase 5 engine is proving recommendation ranking, scenario handoff, and governance, but it is not yet proving a complete physical repair of the unavailable barge. A real dispatcher should challenge this and read the remaining publish block correctly: the selected option improves one modeled part of the chain, but the plan still needs further repair before it can be published.

### 3. Governed Handoff

Governed handoff means the recommendation does not directly edit the live plan.

The top recommendation is converted into a simulation scenario. The scenario records one assumption:

`manual_reassignment`: move the affected assignment from `CTS-BORNEO` to `CTS-JAVA`.

The scenario then runs the planning simulation. The UI should show:

- scenario type: Recovery Recommendation;
- source recommendation ID;
- source snapshot ID;
- changed trip count: 1;
- the changed chain from `CTS-BORNEO` to `CTS-JAVA`;
- run output and constraint evaluations.

Only after that is the scenario promoted to a proposed plan candidate. The candidate still needs approval and publish validation.

Business value:

The operator can explain exactly what changed, why it changed, who approved it, and why the plan still could not publish if critical blockers remain.

## Operator Practice Flow

This section is the practical operator rehearsal. The important part is the business evidence at each stage.

### Stage 1 - Start With Empty Demand

Run:

```text
docker compose exec -T api python manage.py operator_trial_practice reset --json
```

Open **Planning -> OGV Demand & Laycan**.

Business context:

The system is ready, but there is no voyage demand yet. This is the correct starting point for operator rehearsal because the operator must first import the OGV demand file before any schedule, assignments, exceptions, recovery options, or approvals can exist.

Evidence to look for:

- Active voyages: `0`.
- Cargo requirements: `0`.
- No generated plan.
- No active exceptions.

Move forward when:

The operator can explain that master data is ready, but the planning horizon has not received demand.

### Stage 2 - Import OGV Demand

Either click **Import demand** on **Planning -> OGV Demand & Laycan**, or run:

```text
docker compose exec -T api python manage.py operator_trial_practice import-demand --json
```

Business context:

This imports the trial OGV file. It creates 5 vessel orders, 8 cargo requirement rows, and 6 executable hatch/layer rows. This is the first business event in the practice flow.

Evidence to look for:

- Import job status: imported.
- Active/planned OGV orders: 5.
- Cargo requirement rows: 8.
- Hatch/layer sequence rows: 6.
- No plan version yet.
- No trips yet.

Move forward when:

The operator can locate the 8 cargo requirement rows through **OGV Demand & Laycan -> select each OGV -> Cargo requirement split**.

### Stage 3 - Enter Operating Windows

Open **Constraints -> Tide & Bridge Window** and enter the trial windows, or run:

```text
docker compose exec -T api python manage.py operator_trial_practice enter-windows --json
```

Business context:

This adds the governed navigation and resource context for the imported demand: tide gates, bridge slots, asset availability, jetty availability, and navigation checks. These constraints are what later make the plan operationally meaningful.

Evidence to look for:

- 3 tide windows.
- 3 bridge windows.
- 3 asset availability rows.
- 3 jetty availability rows.
- 5 navigation checks.
- Still no generated plan or trips.

Move forward when:

The operator can explain that demand is now combined with tide, bridge, jetty, and resource constraints.

### Stage 4 - Generate Assignment Plan

Open the planning action that generates the schedule, or run:

```text
docker compose exec -T api python manage.py operator_trial_practice generate-plan --json
```

Then open **Recovery Loop -> Exception Center**.

Business context to confirm:

- There are 5 active/planned OGV orders.
- The current generated plan is `PLAN-2026-05-26 V1`.
- The system has created 6 tug/barge/jetty/CTS trip assignments.
- The main recovery case is `BARGE_UNAVAILABLE`.
- The affected order is `MV PACIFIC PRIDE`.
- The affected trip is `PI-PLAN-2026-05-26-0003`.
- The planned equipment is `BER-TUG-08` / `BRG-KAL-22`.
- The planned jetty is `JTY-SUARAN`.
- The planned CTS is `CTS-BORNEO`.

What happened in the business process:

The schedule expected `BRG-KAL-22` to support an `EBONY` movement for `MV PACIFIC PRIDE`. That barge is unavailable inside the trip window. The operator needs to recover the movement without making a silent spreadsheet-style edit.

Evidence to look for:

- Open exceptions: 4.
- Blocking exceptions: 3.
- Exception code: `BARGE_UNAVAILABLE`.
- Resource: `BRG-KAL-22`.
- Affected OGV: `MV PACIFIC PRIDE`.
- Status: critical/blocking.
- Next action points to simulation or recovery.

Move forward when:

The operator can explain the disruption in one sentence:

`MV PACIFIC PRIDE has a planned EBONY movement from JTY-SUARAN, but BRG-KAL-22 is unavailable, so the trip needs a governed recovery decision.`

### Stage 5 - Retrieve The Recovery Input

From the exception, generate recovery options.

Business context:

This is the retrieval step. The operator is asking the system: "Take this disruption and retrieve all evidence needed to calculate recovery choices."

What the backend creates:

- `RecoveryInputSnapshot`, such as `RIS-PHASE5-SEED` or `RIS-...`.
- Source kind: `conflict`.
- Source reference: `BARGE_UNAVAILABLE`.
- Source plan: `PLAN-2026-05-26 V1`.
- Active conflicts in scope.
- Resource state, event state, and constraint state.

Evidence to look for:

- Recommendation Console shows an input snapshot ID.
- Source kind is `CONFLICT`.
- Source is `BARGE_UNAVAILABLE`.
- The optimizer run is succeeded.

Move forward when:

The operator can explain that the system has frozen the current plan state before making recommendations.

### Stage 6 - Read The Recovery Options

Open **Recovery Loop -> Recommendation Console**.

Business context:

This is where Phase 5 starts behaving like decision intelligence. The system is not merely showing the exception. It is showing possible recovery decisions and the tradeoffs for each one.

For the Phase 5 practice case, the key options are:

- reassign CTS from `CTS-BORNEO` to `CTS-JAVA`;
- resequence the Pacific Pride blocked trip against the Triton Star trip;
- delay the Pacific Pride trip by 90 minutes;
- swap tug/barge to `BER-TUG-09` / `BRG-NUS-17`;
- push the trip to the next tide/bridge window.

Evidence to look for:

- 5 ranked options.
- Rank 1 is `CTS_REASSIGNMENT`.
- Rank 1 score is around `89.0`.
- Rank 1 option risk is low.
- Rank 1 action changes `CTS-BORNEO` to `CTS-JAVA`.
- Other options have higher delay, missed windows, or hard-constraint risk.

How to interpret the ranking:

The top option is not chosen because it magically clears every plan risk. It is chosen because, among the currently modeled options, it introduces the least additional operational pain for the selected disruption.

Move forward when:

The operator can compare at least two options:

- `CTS_REASSIGNMENT` is low risk because it does not create additional missed windows or resource conflicts in the recommendation evaluation.
- `NEXT_WINDOW_REPAIR` is high risk because it delays the trip by 360 minutes and still carries hard-constraint exposure.

### Stage 7 - Test The Recommendation As A Scenario

Use **Test as scenario** for the selected recommendation. If the proof command already ran, the recommendation may already be materialized; in that case open the existing scenario.

Business context:

This is the governance boundary. The recommendation is being tested in a scenario. The active plan is not directly overwritten.

The scenario should represent this business change:

`For MV PACIFIC PRIDE trip PI-PLAN-2026-05-26-0003, use CTS-JAVA instead of CTS-BORNEO.`

What the backend creates:

- `SimulationScenario`, such as `SIM-PLAN-2026-05-26-V1-08`.
- One scenario assumption: manual reassignment.
- A scenario run, such as `RUN-SIM-PLAN-2026-05-26-V1-08-01`.
- Projection rows and constraint evaluations.

Evidence to look for:

- Scenario type: Recovery Recommendation.
- Source recommendation ID is visible.
- Source snapshot ID is visible.
- Changed trips: 1.
- The changed resource chain shows `CTS-BORNEO -> CTS-JAVA`.
- The scenario output is visible before any publish action.

Important interpretation:

The recommendation score may show a small delay or coordination penalty, while the scenario output may show no additional schedule delay from the CTS change itself. That is acceptable. The score includes recovery effort and operational risk; the scenario output shows the projected plan impact from the materialized assumption.

Move forward when:

The operator can explain that this is a what-if test, not a live-plan edit.

### Stage 8 - Promote The Scenario For Approval

Promote the scenario to proposed.

Business context:

Promotion means the operator believes the recovery scenario is worth formal review. It still does not mean the plan is published.

What the backend creates:

- A successor candidate plan version, such as `PLAN-2026-05-26 V2`.
- Scenario lineage from the recommendation to the candidate.
- Scenario diff summary.
- Approval request for the required authorities.

Evidence to look for:

- Scenario status becomes `PROPOSED`.
- Approvals & Publishing shows a request for the candidate plan.
- The request identifies the scenario source.
- The request requires Berau Scheduler and ABL Dispatcher.

Move forward when:

The operator can trace the candidate plan back to the recommendation and the original disruption.

### Stage 9 - Review Approval And Publish Block

Open **Recovery Loop -> Approvals & Publishing**.

Business context:

Approval is a business sign-off. Publishing is a stricter operational gate.

In the proof run, both authorities approve:

- Berau Scheduler approves.
- ABL Dispatcher approves.

But publish remains blocked.

Why publish remains blocked:

The recovery option addresses one selected disruption. The wider candidate plan still contains unresolved critical risk, such as bridge/tide misses or other resource conflicts created by the full candidate context. Phase 5 is designed to preserve that block.

In this trial, publish blocking is also a useful warning about the current recovery model. The selected recommendation changes CTS handling, but it does not replace `BRG-KAL-22`. The system therefore demonstrates governed recovery handoff, not full autonomous plan repair.

Evidence to look for:

- Approval request status: approved.
- Berau Scheduler decision: approve.
- ABL Dispatcher decision: approve.
- Ready to publish: blocked.
- Publish button: disabled or blocked.
- Constraint checklist still shows blocking items.

Move forward when:

The operator can explain the difference:

`The recovery recommendation can be approved for governance, but the plan cannot publish until remaining critical blockers are cleared.`

### Stage 10 - Resolve The Remaining Trial Exceptions

Run:

```text
docker compose exec -T api python manage.py phase5_resolve_trial_pack --json
```

Business context:

This is the formal closure step for the trial pack. It confirms that Phase 5 can stop the recovery loop instead of only creating more candidate versions. The command clears remaining seeded operational blockers, resolves still-open telemetry alerts, regenerates a clean successor plan, and records approvals and audit evidence.

If the trial pack is already closed, the same command returns the existing clean approved version and reports `idempotent: true`.

In the validated runtime, the remaining issue was not another schedule conflict. It was two open synthetic telemetry alerts tied to `BRG-VAL-08`: a `delay` alert and a `geofence_dwell` alert. Those alerts kept the assistant in recovery mode even after the candidate plan had no open plan conflicts.

Expected final state:

- active plan version: latest closure version, for example `PLAN-2026-05-26 V9`;
- plan status: `approved`;
- validation: `feasible`;
- planned trips: 6;
- open conflicts: 0;
- blocking conflicts: 0;
- open tracking alerts: 0;
- approval request: approved with Berau Scheduler and ABL Dispatcher decisions;
- global next action: `PUBLISH_PLAN`.

Move forward when:

The operator can state that the plan has moved from recovery investigation to publish readiness.

### Stage 11 - Retrieve The Proof Pack And Audit Trail

Open **Recommendation Console** and review the proof pack. Then open **Admin Console -> Audit & Logs**.

Business context:

This is the after-action evidence. It proves the recommendation was not a silent edit.

The proof pack should reconstruct:

- the source exception;
- the input snapshot;
- the optimizer run;
- the ranked recommendation;
- the before/after action;
- the scenario handoff;
- the approval chain;
- the audit trail.

Evidence to look for in audit:

- `recovery.input_snapshot.build`;
- `recovery.optimizer.run`;
- `recovery.recommendation.materialize_scenario`;
- `approval.request`;
- `approval.decision`;
- `recovery.recommendation.proof_pack_viewed`;
- `phase5.proof.*` events if the proof command was used.

Move to closure when:

The operator can tell the complete story:

1. `MV PACIFIC PRIDE` had a blocked `EBONY` trip because `BRG-KAL-22` was unavailable.
2. The system retrieved the plan context into a recovery input snapshot.
3. The optimizer calculated 5 options.
4. The top option reassigned CTS handling from `CTS-BORNEO` to `CTS-JAVA`.
5. The recommendation became a scenario, not a direct plan edit.
6. The scenario became a proposed candidate plan.
7. Berau and ABL approvals were recorded.
8. Publish stayed blocked during the recommendation proof because remaining critical risk still existed.
9. The closure command resolved the remaining trial-pack exception sources.
10. The active closure version is approved, feasible, and ready to publish.
11. The entire chain is visible in proof pack and audit logs.

## What Phase 5 Can Do Today

Phase 5 can:

- retrieve a disruption from an exception, override, tracking alert, operational event, or scenario source;
- freeze the active plan context into a recovery input snapshot;
- calculate deterministic recovery candidates;
- score options by delay, missed windows, resource conflicts, manual-change effort, health risk, OGV completion risk, and demurrage proxy;
- explain why an option ranked where it did;
- convert a recommendation into a scenario;
- preserve scenario lineage back to the original disruption;
- promote the scenario into approval governance;
- block publication when unresolved critical risk remains;
- provide proof-pack and audit evidence.

## What Original Phase 5 Did Not Do Yet

Original Phase 5 did not yet:

- automatically repair every conflict in the plan;
- guarantee that the top option fully removes the original physical cause, such as an unavailable barge;
- guarantee a publishable plan from one selected recovery option;
- run a global commercial optimizer across all OGVs and all assets;
- autonomously publish a plan;
- replace Berau or ABL approval;
- consume live third-party GPS/AIS feeds as production truth;
- calculate final customer commitment or demurrage settlement.

Phase 6 / Phase 5+ now closes part of that gap with persistent flow runtime, flow-aware Next Action guidance, UI CTA operator-trial evidence, root-cause repair assessment, explicit publishability checks, global optimizer review candidates, telemetry trust assessment, and projection-only commercial outputs. The closure evidence is documented in `27_Phase_6_Completion_Evidence.md`.

For recovery-origin publication, Phase 6 / Phase 5+ adds a production gate: the selected recovery recommendation must have root-cause assessment status `addresses_cause` or `mitigates_cause` before publishability can clear. `does_not_address_cause`, `unknown`, or missing root-cause validation blocks manual publish at the publishability service and at the backend publish endpoint.

The following limitations still remain deliberate business boundaries:

- automatic publishing remains out of scope; the operator must still click the visible `Publish plan` CTA;
- Berau and ABL approval remains required and is not replaced by optimizer, assistant, flow, telemetry, or commercial outputs;
- global optimizer objective weights are configurable defaults pending commercial sign-off;
- GPS/AIS is evidence gated by trust assessment, not unconditional production truth;
- commercial output remains projection-only and excludes final customer commitment, NOR/SOF, laytime, demurrage settlement, invoicing, and despatch settlement.

## How To Judge Successful Phase 5 Practice

The practice run is successful when the operator can answer these questions with evidence from the UI:

| Question | Expected answer |
|---|---|
| Which order was disrupted? | `MV PACIFIC PRIDE`. |
| Which trip was disrupted? | `PI-PLAN-2026-05-26-0003`. |
| Which resource caused the disruption? | `BRG-KAL-22`, unavailable inside the trip window. |
| Which jetty and CTS were involved? | `JTY-SUARAN` and `CTS-BORNEO`. |
| What did the best recommendation change? | CTS handling changed from `CTS-BORNEO` to `CTS-JAVA`. |
| Why was it ranked first? | Lowest risk among modeled options: no missed windows and no added resource conflicts in the recommendation evaluation. |
| Does ranking alone make it publishable? | No. A recovery-origin plan also needs root-cause validation and publishability to pass or warn. A CTS-only action for an unavailable barge is blocked as `does_not_address_cause`. |
| Did it silently change the active plan? | No. It became a governed simulation scenario first. |
| Was it approved? | Yes, in the proof flow Berau and ABL approvals are recorded. |
| Was it published? | Not automatically. After the closure command, the plan is ready to publish and the operator can perform the final publish action. |
| Where is the evidence? | Recommendation Console, Simulation Workspace, Approvals & Publishing, Audit & Logs, and the proof-pack endpoint. |

## Evidence Files

The repeatable evidence is written under `docs/evidence/phase5/`.

| File | Use |
|---|---|
| `phase5_recovery_evidence.json` | Machine-readable proof that the Phase 5 recovery flow passed. |
| `browser_visibility_evidence.json` | Text extracted from browser evidence screens. |
| `screenshots/phase5-exception-center.png` | Exception Center evidence. |
| `screenshots/phase5-recommendation-console.png` | Ranked recommendation evidence. |
| `screenshots/phase5-simulation-workspace.png` | Scenario handoff evidence. |
| `screenshots/phase5-approvals-publishing.png` | Approval and publish-block evidence. |
| `screenshots/phase5-audit-logs.png` | Audit trail evidence. |

