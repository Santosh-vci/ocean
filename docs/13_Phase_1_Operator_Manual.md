# 13 — Phase 1 Operator Manual

## Purpose

This manual gives an operations user a repeatable UI-first path for Phase 1 planning inside the Dockerized Coalflow Tower system. Terminal commands are limited to starting Docker and choosing the seed state. End-to-end planning validation is performed through the application interface.

## 1. Start or reset the instance

Run commands from `F:\ocean`.

### 1.1 Start the Dockerized system

```text
docker compose up -d --build db redis object-store api frontend proxy worker beat
docker compose ps
```

Open the application in a browser:

```text
http://localhost:8080
```

Expected readiness in the UI: the login screen loads, and after login the top bar, sidebar, dashboard, and workspace pages render without backend error banners.

### 1.2 Reset to master-data-only mode

Use this before an operator needs to start a plan with no prior operational records.

```text
docker compose run --rm -e RUN_STARTUP_TASKS=0 api python manage.py seed_phase0 --reset-operational-data --master-data-only
```

Expected state after this command:

- organizations, roles, users, permissions, master data, routes, assets, jetties, CTS, locations, and coal grades exist;
- OGV demand, cargo layers, availability windows, tide windows, bridge windows, plans, trips, conflicts, approvals, exports, and audit events are empty;
- the operator can create a fresh planning run using the UI actions below.

### 1.3 Reset to the full pilot demonstration seed

Use this only when a pre-filled demo environment is required.

```text
docker compose run --rm -e RUN_STARTUP_TASKS=0 api python manage.py seed_phase0 --reset-operational-data
```

This restores the seeded Phase 1 scenario plan, demand, constraints, conflicts, and approval examples.

### 1.4 Generate automated proof evidence, if required

This is not an operator step. Use it only for regression evidence.

```text
docker compose run --rm -e RUN_STARTUP_TASKS=0 api python manage.py phase1_e2e_proof --json
```

### 1.5 Generate Phase 2 scenario proof evidence, if required

This is also a regression step, not a live operator action. Use it when validating that the Phase 2 scenario workspace, selected-run promotion, approval gate, scenario-diff export, and audit lineage are still wired end to end.

```text
docker compose run --rm -e RUN_STARTUP_TASKS=0 api python manage.py phase2_scenario_proof --json
```

The proof reseeds the pilot data by default and verifies these scenario families:

- `SIM-JETTY-DELAY`;
- `SIM-TUG-OUTAGE`;
- `SIM-TIDE-RECOVERY`;
- `SIM-CTS-RATE`;
- `SIM-TOPUP-DEMAND`;
- `SIM-MANUAL-REASSIGNMENT`;
- `SIM-MULTI-CANDIDATE`.

To keep a host-side evidence copy, redirect the JSON output to `docs/evidence/phase2/phase2_scenario_evidence.json`.

### 1.6 Generate Phase 3 tracking proof evidence, if required

This is a regression and closure step for the live-tracking phase, not a normal planning operator action. Use it to verify Synthetic Live Data Mode, movement events, ETA variance, tracking alerts, observed-delay scenario handoff, and audit proof.

```text
docker compose exec -T api python manage.py phase3_tracking_proof --json > docs\evidence\phase3\phase3_tracking_evidence.json
node scripts\capture_phase3_browser_evidence.mjs
```

See `18_Phase_3_Operator_Runbook.md` for the UI-first Phase 3 flow.

## 2. Login roles

| Role | User | Password | Operational use |
|---|---|---|---|
| Admin | `admin@coalflow.local` | `admin12345` | setup, UAT, full access |
| Berau Scheduler | `berau.scheduler@coalflow.local` | `welcome12345` | demand intake, cargo layers, schedule edits, Berau approval |
| ABL Dispatcher | `abl.dispatcher@coalflow.local` | `welcome12345` | fleet/windows/jetty execution, ABL approval |
| Joint Control Tower | `control.tower@coalflow.local` | `welcome12345` | publication and governed exports |
| Viewer | `viewer@coalflow.local` | `welcome12345` | read-only observation |

Change all passwords before any shared or externally reachable environment.

## 3. UI-first end-to-end planning run from master-data-only state

Before starting this run, execute the master-data-only reset in section 1.2.

### Stage 1 — Log in under the correct organization and role

1. Open `http://localhost:8080`.
2. Log in as `berau.scheduler@coalflow.local`.
3. Confirm the top bar shows the Berau scheduler context.
4. Confirm the sidebar exposes planning, schedule, constraints, recovery, dashboard, audit, and master-data review according to role permissions.

Acceptance evidence: the user reaches the dashboard without an error banner, and the visible modules match the role.

### Stage 2 — Review master data

1. Open **Admin Console → Master Data Console**.
2. Review these catalogs:
   - coal grades: `EBONY`, `MAHONI`, `AGATHIS`, `SUNGKAI`;
   - jetties: `JTY-SUARAN`, `JTY-LATI`, `JTY-GMB`;
   - tugs/barges: `BER-TUG-08`, `BER-TUG-09`, `BRG-VAL-08`, `BRG-NUS-17`;
   - CTS: `CTS-BORNEO`, `CTS-JAVA`, `FC-CHLOE`;
   - routes: `RTE-SUARAN-MUARA` and its tide/bridge segments.
3. Select a catalog row and click **Validate** in the detail drawer.
4. If needed, click **Export** from the page header to confirm governed master-data export behavior.

Acceptance evidence: required records are visible and active. Stop if a required asset, grade, route, jetty, or CTS is missing or inactive.

### Stage 3 — Upload OGV demand and cargo-layer requirements

1. Open **Planning → OGV Demand & Laycan**.
2. Confirm the board starts with `0` active voyages after master-data-only reset.
3. Click **Import demand**.
4. Wait for the success banner: `Import committed: operator-ui-demand-...`.
5. Confirm the table now shows `MV Operator UI Import` with `64,000 MT` demand.
6. Select the voyage row and inspect the detail panel.
7. Confirm two cargo-layer rows were created:
   - sequence 1: `EBONY`, `H1/L1`, planned via `BRG-VAL-08`, `JTY-SUARAN`, `CTS-BORNEO`;
   - sequence 2: `AGATHIS`, `H2/L1`, planned via `BRG-NUS-17`, `JTY-LATI`, `CTS-JAVA`.

Acceptance evidence: the voyage, import job, cargo requirement split, and hatch/layer chain are visible in the UI.

### Stage 4 — Enter manual availability plus tide/bridge windows

1. Open **Constraints → Tide & Bridge Window**.
2. Confirm the page starts with no operational windows after master-data-only reset.
3. Click **Enter operating windows**.
4. Wait for the success banner showing `TIDE-UI-OPERATING-01` and `BRDG-UI-OPERATING-01`.
5. Confirm the KPI strip now shows open windows.
6. Confirm the timeline shows:
   - tide: `TIDE-UI-OPERATING-01`;
   - bridge: `BRDG-UI-OPERATING-01`.
7. Confirm the affected trips matrix shows `can_cross` checks for the imported voyage and planned barges.

Acceptance evidence: manually entered operating windows and navigation checks are visible before schedule generation.

### Stage 5 — Generate a draft schedule

1. Open **Operations → Tug/Barge Assignment**.
2. Click **Regenerate plan**.
3. If no plan exists, the UI creates the first operator plan/version and then generates the schedule.
4. Wait for the success banner: `Schedule generated: PLAN-UI-... V1`.
5. Confirm the board now shows assignment rows for `MV Operator UI Import`.
6. Confirm the selected chain panel shows tug, barge, jetty, and CTS assignments.

Acceptance evidence: generated trips, assignments, and schedule events are visible in the UI without manually creating a plan through API calls.

### Stage 6 — Inspect the full trip chain and conflicts

1. Stay in **Operations → Tug/Barge Assignment** and inspect each generated row.
2. Open **Operations → Jetty Loading** and confirm the same OGV appears in the jetty queue.
3. Open **Operations → CTS / Floating Crane** and confirm the same cargo layers appear in the CTS queue.
4. Open **Recovery Loop → Exception Center**.
5. If conflicts exist, select each conflict row and review severity, source object, affected OGV, and recommended next action.
6. If no conflicts exist, record that the happy path is feasible and continue.

Acceptance evidence: the operator can trace the chain from OGV demand to barge/tug, jetty, CTS, events, and exception state.

### Stage 7 — Make a governed adjustment with reason

1. Open **Operations → Jetty Loading**.
2. Click **Force start jetty**.
3. In the governed override panel, review the selected assignment and planned load start.
4. Confirm or edit **Effective start time**. The UI defaults this to planned load start plus 120 minutes so the Phase 1 trial has a visible calculated impact, but the operator-entered timestamp is the source of truth.
5. Click **Apply governed override**.
6. Wait for the success banner confirming a governed jetty override and calculated impact.
7. Open **Recovery Loop → Exception Center** and select the override row.
8. Confirm the right detail panel shows reason code, actor, before/after state, timestamp, effective start, delay, and risk status.
9. Confirm **Impact chain propagation** renders calculated nodes such as `JETTY DELAY`, `BARGE DELAY`, bridge-window result, tide-window result, and final risk target.
10. Open **Admin Console → Audit & Logs** and confirm the override event is recorded.

Acceptance evidence: the adjustment is not a silent table edit; it is captured as a governed override, audit event, and calculated current-trip impact assessment.

### Stage 7A — Optional Simulation Workspace check

Use this check before Phase 1 closure if the operator wants to exercise the transition scenario surface that product Phase 2 expands. The current Phase 2 workspace now supports seeded and manually created what-if scenarios, assumption capture, deterministic scenario runs, baseline-vs-scenario comparison, selected-run promotion, approval gating, scenario-diff export, and audit lineage. It still does not perform fleet-wide optimization or automatically choose the best recovery plan.

1. Open **Recovery Loop → Exception Center**.
2. If active conflicts exist, select the conflict to test and click **Convert to scenario**.
3. If no active conflicts exist, click **Convert to scenario** anyway to create a manual scenario against the active plan version.
4. Open **Recovery Loop → Simulation Workspace**.
5. Confirm the active scenario ID, source conflict/override/manual source, status, selected run, changed trips, max delay, and remaining risk flags are visible.
6. Click **Run simulation**.
7. Confirm the baseline-vs-scenario table, two-lane timeline, constraint evaluations, OGV projections, resource utilization, impact-chain nodes, and recovery action list update.
8. Optional: select another run in the run ledger to compare a different assumption set before promotion.
9. Optional: click **Promote to proposed** only if the operator intentionally wants to create a proposed successor version for approval review.

Acceptance evidence: a scenario is visible in Simulation Workspace, calculated projection rows are visible, recovery actions are listed, selected-run lineage is retained if promoted, and audit events exist for scenario creation/simulation/promotion when those actions are used.

### Stage 7B — Optional top-up successor plan

Use this check when the first seeded/operator plan has been published and a second demand intake needs to be planned on top of it.

1. Open **Planning → OGV Demand & Laycan**.
2. Click **Import demand** again to create an additional `MV Operator UI Import` demand and two cargo-layer rows.
3. Open **Schedule → Published Plan & Schedule**.
4. Click **Create draft**. If a successor draft already exists, the UI should report that the draft is already active rather than creating another duplicate draft.
5. Open **Operations → Tug/Barge Assignment**.
6. Click **Regenerate plan**.
7. Confirm the successor draft now includes the additional demand rows in the trip chain.
8. Review **Exception Center** before approval. If new blockers appear, handle them through the same recovery loop before publication.

Acceptance evidence: the live published plan remains preserved, a successor draft carries the top-up demand, and the regenerated trip count reflects the additional cargo-layer work.

### Stage 8 — Submit, approve, and publish the plan

1. Open **Schedule → Published Plan & Schedule** as Berau Scheduler.
2. Click **Submit approval**.
3. Open **Schedule → Plan Approvals & Publishing**.
4. Click **Approve** as Berau Scheduler.
5. Log out.
6. Log in as `abl.dispatcher@coalflow.local`.
7. Open **Schedule → Plan Approvals & Publishing**.
8. Click **Approve** as ABL Dispatcher.
9. Log out.
10. Log in as `control.tower@coalflow.local`.
11. Open **Schedule → Plan Approvals & Publishing**.
12. Confirm the page shows **Ready to publish**.
13. Click **Publish**.

Acceptance evidence: the approval chain shows both `BERAU_SCHEDULER` and `ABL_DISPATCHER` approved, and the published snapshot appears after publication. If **Publish** remains blocked, inspect active blocking conflicts and resolve them before publishing.

### Stage 9 — Retrieve the live published version and audit trail

1. Open **Schedule → Published Plan & Schedule**.
2. Confirm the active plan version is published and the generated trip chain remains visible.
3. Open **Admin Console → Audit & Logs**.
4. Confirm audit events exist for demand import, window entry, schedule generation, override, approval decisions, publish, and export.
5. Do not edit the published version directly. Use **Create draft** for a successor plan.

Acceptance evidence: the live published snapshot and lifecycle audit trail are visible in the application.

### Stage 10 — Export the governed schedule

1. Stay logged in as Joint Control Tower.
2. Open **Admin Console → Exports & Handoff**.
3. Click **Generate schedule**.
4. Confirm export history shows:
   - export ID;
   - file name;
   - record count;
   - storage URI;
   - checksum;
   - download link.
5. Click the download link to retrieve the artifact.
6. Do not manually edit the exported file as a substitute for governed planning.

Acceptance evidence: the governed export is generated by the system and is retrievable without spreadsheet surgery.

## 4. Additional UI action checks

Use these checks after any frontend or backend wiring change:

- **Planning → OGV Demand & Laycan**: **Import demand** creates visible OGV demand and cargo layers.
- **Constraints → Tide & Bridge Window**: **Enter operating windows** creates visible operating windows and navigation checks.
- **Operations → Tug/Barge Assignment**: **Regenerate plan** creates/generates the first plan when none exists.
- **Operations → Jetty Loading**: **Force start jetty** creates a governed override after assignments exist.
- **Recovery Loop → Exception Center**: **Convert to scenario** creates a recovery scenario from the selected conflict, or a manual scenario when no conflict is selected.
- **Recovery Loop → Simulation Workspace**: **Run simulation** calculates the transition scenario delta; **Promote to proposed** creates or marks a successor proposed plan version.
- **Schedule → Published Plan & Schedule**: **Create draft** creates the first draft when no plan exists, or clones a published/superseded version.
- **Schedule → Published Plan & Schedule**: **Submit approval** creates an approval request for an editable plan.
- **Schedule → Plan Approvals & Publishing**: **Approve** records the user’s remaining approval authority.
- **Schedule → Plan Approvals & Publishing**: **Publish** is enabled only after dual approval and zero unresolved blocking conflicts.
- **Admin Console → Master Data Console**: **Validate**, **Import**, and **Export** perform visible actions or show explicit governed-lock messaging.
- **Admin Console → Exports & Handoff**: export command buttons create export records and download links when the role has `export.generate`.

## 5. Stop conditions

Stop the planning run and escalate if any of these occur:

- master data is missing, inactive, or contradictory;
- demand import fails or does not create visible OGV/cargo-layer records;
- operating windows cannot be entered from the UI;
- schedule generation does not create trips, assignments, and events;
- cargo-layer sequence is violated and unresolved;
- tug/barge/jetty/CTS assignment is unavailable;
- tide or bridge window is missed and unresolved;
- approval request lacks either Berau or ABL approval;
- publish is attempted with unresolved blocking conflicts;
- export generation is attempted by a role without `export.generate`.
- simulation promotion is treated as publication; promotion only creates a proposed version and still requires the approval/publish gates.

## 6. Completion checklist

A Phase 1 planning run is complete only when all are true:

- operator roles and organization context are correct;
- master data was reviewed in the UI;
- OGV demand and cargo layers are visible;
- availability, tide, and bridge windows are visible;
- schedule has generated trips, assignments, and events;
- conflicts are understood or resolved;
- overrides include reason, actor, and before/after state;
- governed jetty-delay overrides include a calculated impact chain;
- any optional simulation or top-up run is visible as a scenario or successor draft, with audit trail;
- dual approval is complete;
- live published snapshot exists;
- audit trail is retrievable;
- governed export is generated and downloadable.
