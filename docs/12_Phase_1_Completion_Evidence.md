# 12 ? Phase 1 Completion Evidence

**Evidence run:** `P1-E2E-20260516033031`
**Generated at:** `2026-05-16T03:30:31.664875+00:00`
**Runtime:** Dockerized Coalflow stack, command executed in the `api` container.
**Machine-readable evidence:** `docs/evidence/phase1/phase1_e2e_evidence.json`
**Browser visibility evidence:** `docs/evidence/phase1/browser_visibility_evidence.json`

## Result

Phase 1 is proven complete for the current implementation baseline: **10 / 10 definition-of-done stages passed**.

The proof run creates a clean happy-path operational plan that is visible in the application:

| Item | Runtime evidence |
|---|---|
| Plan | `PLAN-PHASE1-E2E` |
| Plan version ID | `5` |
| Status | `published` |
| Validation | `feasible` |
| Voyage | `VOY-PHASE1-HAPPY-001` / MV Phase One Reliance |
| Required demand | 64,000 MT |
| Trips generated | 2 |
| Schedule events | 14 |
| Published snapshot | `LIVE-PLAN-PHASE1-E2E-V1` |
| Governed export | `coalflow-plan-plan-phase1-e2e-v1-all-network-20260516033031.txt` |
| Export checksum | `f6b75100ee3b54703946d90edbf78d9824cb2b772607bf8b0e01659c1ea5fbb3` |

## Definition-of-done evidence matrix

| # | Required Phase 1 capability | Actor proven | Runtime evidence | Visible application route | Record evidence |
|---:|---|---|---|---|---|
| 1 | Login under correct organization and role | admin@coalflow.local | 5 seeded users verified with role-shaped permissions | `/me/` | ablDispatcher, admin, berauScheduler, controlTowerPublish, viewerReadOnly |
| 2 | Review planning master data | admin@coalflow.local | 4 coal grades, 3 jetties, 17 locations | `/admin/master-data` | bargeSample: BRG-VAL-08, BRG-NUS-17; coalGrades: 4; jetties: 3; jettySample: JTY-SUARAN, JTY-LATI; locations: 17 |
| 3 | Upload OGV demand and cargo-layer requirements | berau.scheduler@coalflow.local | VOY-PHASE1-HAPPY-001 / 64000 MT / 2 cargo layers | `/schedule/ogv-demand` | cargoRequirements: 13, 14; filename: phase1_e2e_operator_demand.xlsx; importJobId: 4; layerSteps: 11, 12; voyageId: VOY-PHASE1-HAPPY-001 |
| 4 | Enter manual availability plus tide/bridge windows | abl.dispatcher@coalflow.local | 6 asset windows, TIDE-P1-E2E-RANTAU, BRDG-P1-E2E-GATE-B | `/constraints/tide-bridge` | assetAvailabilityWindows: 6; bridgeWindow: BRDG-P1-E2E-GATE-B; jettyWindows: 2; navigationChecks: 2; tideWindow: TIDE-P1-E2E-RANTAU |
| 5 | Generate a draft schedule | admin@coalflow.local | PLAN-PHASE1-E2E V1 generated 2 trips with 0 blockers | `/schedule/published-plan` | blockingConflictCount: 0; conflictCount: 0; planCode: PLAN-PHASE1-E2E; planVersionId: 5; status: validated |
| 6 | Inspect full trip chain and conflicts | control.tower@coalflow.local | 2 trips / 14 schedule events / 0 conflicts | `/operations/tug-barge-assignment` | PI-PLAN-PHASE1-E2E-0001 BER-TUG-08/BRG-VAL-08 32000MT; PI-PLAN-PHASE1-E2E-0002 BER-TUG-08/BRG-NUS-17 32000MT |
| 7 | Make governed adjustments with reasons | abl.dispatcher@coalflow.local | Override 36 applied with reason manual_correction | `/exceptions/center` | changedFields: next_action, next_constraint; description: Dispatcher confirmed tow readiness after manual VHF check.; overrideId: 36; reasonCode: manual_correction |
| 8 | Submit, approve, and publish a plan | control.tower@coalflow.local | APR-PLAN-PHASE1-E2E-V1 approved and published as LIVE-PLAN-PHASE1-E2E-V1 | `/approvals/publishing` | approvalRequestId: APR-PLAN-PHASE1-E2E-V1; approvalStatus: published; planVersionStatus: published; requiredAuthorities: berau_scheduler, abl_dispatcher; snapshotId: LIVE-PLAN-PHASE1-E2E-V1 |
| 9 | Retrieve live published version and audit trail | control.tower@coalflow.local | LIVE-PLAN-PHASE1-E2E-V1 active with 8 proof audit events before retrieval marker | `/admin/audit-logs` | auditEventsBeforeMarker: 8; payloadTripCount: 2; snapshotId: LIVE-PLAN-PHASE1-E2E-V1; snapshotStatus: active |
| 10 | Export the governed schedule | control.tower@coalflow.local | coalflow-plan-plan-phase1-e2e-v1-all-network-20260516033031.txt / 2 trips / f6b75100ee3b... | `/admin/export-handoff` | EXP-PLAN-20260516033031-F1137A / 2 records / checksum f6b75100ee3b... |

## Constraint scenario evidence

The proof run also preserves the seeded constraint-heavy plan so the happy path is not the only demonstrated behavior.

| Item | Runtime evidence |
|---|---|
| Constraint plan | `PLAN-2026-10-24` |
| Plan version ID | `1` |
| Status | `proposed` |
| Validation | `blocked` |
| Total conflicts | 7 |
| Blocking conflicts | 5 |

| Conflict code | Severity | Vessel | Blocking | Message |
|---|---|---|---:|---|
| BARGE_UNAVAILABLE | critical | MV PACIFIC PRIDE | True | BRG-KAL-22 is unavailable inside the trip window. |
| BRIDGE_WINDOW_MISSED | critical | MV NORTH STAR | True | Hold upstream and request next bridge lift. |
| LAYER_SEQUENCE_VIOLATION | critical | MV NORTH STAR | True | Mahoni layer cannot precede Sungkai approval |
| TUG_BARGE_INCOMPATIBLE | critical | MV GOLDEN ORIOLE | True | BER-TUG-08 is incompatible with BRG-KAL-22. |
| TUG_BARGE_INCOMPATIBLE | critical | MV PACIFIC PRIDE | True | BER-TUG-08 is incompatible with BRG-KAL-22. |
| JETTY_OVERLAP | warning | MV PACIFIC PRIDE | False | JTY-LATI is reduced during this loading window. |
| TIDE_WINDOW_MISSED | warning | MV TRITON STAR | False | Use priority tow and reduce loading target if delayed. |

## Manual-window evidence

| Window type | Runtime evidence |
|---|---|
| Asset availability windows | 6 |
| Jetty windows | 2 |
| Tide window | `TIDE-P1-E2E-RANTAU` |
| Bridge window | `BRDG-P1-E2E-GATE-B` |
| Navigation checks | 2 |

## Audit trail evidence

The proof run wrote ten phase-specific audit events. These are visible in **Admin Console ? Audit & Logs** for users with `audit.view`.

| Action | Actor | Object ID | Created at |
|---|---|---|---|
| phase1.proof.login_roles_verified | admin@coalflow.local | P1-E2E-20260516033031-01 | 2026-05-16T03:30:31.453701+00:00 |
| phase1.proof.master_data_reviewed | admin@coalflow.local | P1-E2E-20260516033031-02 | 2026-05-16T03:30:31.459452+00:00 |
| phase1.proof.demand_uploaded | berau.scheduler@coalflow.local | P1-E2E-20260516033031-03 | 2026-05-16T03:30:31.473734+00:00 |
| phase1.proof.manual_windows_entered | abl.dispatcher@coalflow.local | P1-E2E-20260516033031-04 | 2026-05-16T03:30:31.497224+00:00 |
| phase1.proof.schedule_generated | admin@coalflow.local | P1-E2E-20260516033031-05 | 2026-05-16T03:30:31.546111+00:00 |
| phase1.proof.trip_chain_inspected | control.tower@coalflow.local | P1-E2E-20260516033031-06 | 2026-05-16T03:30:31.553841+00:00 |
| phase1.proof.governed_adjustment_applied | abl.dispatcher@coalflow.local | P1-E2E-20260516033031-07 | 2026-05-16T03:30:31.565127+00:00 |
| phase1.proof.plan_published | control.tower@coalflow.local | P1-E2E-20260516033031-08 | 2026-05-16T03:30:31.617970+00:00 |
| phase1.proof.live_version_retrieved | control.tower@coalflow.local | P1-E2E-20260516033031-09 | 2026-05-16T03:30:31.623760+00:00 |
| phase1.proof.governed_export_generated | control.tower@coalflow.local | P1-E2E-20260516033031-10 | 2026-05-16T03:30:31.653820+00:00 |

## Governed export evidence

| Field | Runtime value |
|---|---|
| Export ID | `EXP-PLAN-20260516033031-F1137A` |
| File | `coalflow-plan-plan-phase1-e2e-v1-all-network-20260516033031.txt` |
| Format | `print` |
| Records | 2 |
| Storage URI | `coalflow-local/exports/plan/2026/05/16/291b8e72367d4f8eae7e3b41a59b9361-coalflow-plan-plan-phase1-e2e-v1-all-network-20260516033031.txt` |
| SHA-256 | `f6b75100ee3b54703946d90edbf78d9824cb2b772607bf8b0e01659c1ea5fbb3` |

## How to rerun the evidence proof

```powershell
docker compose up -d --build db redis object-store api frontend proxy worker beat
docker compose run --rm -e RUN_STARTUP_TASKS=0 api python manage.py phase1_e2e_proof --json
```

The command refreshes baseline seed data, creates a deterministic Phase 1 proof plan, publishes it, generates a governed export, and leaves the records visible in the application at `http://localhost:8080`.

## Browser evidence artifacts

The in-app browser was used after the proof run to confirm the proof data is visible in the UI.
Browser console error count during the evidence pass: `0`.

| Route | Screenshot artifact |
|---|---|
| `/schedule/ogv-demand` | `docs/evidence/phase1/screenshots/01_ogv_demand.png` |
| `/constraints/tide-bridge` | `docs/evidence/phase1/screenshots/02_tide_bridge.png` |
| `/schedule/published-plan` | `docs/evidence/phase1/screenshots/03_published_plan.png` |
| `/approvals/publishing` | `docs/evidence/phase1/screenshots/04_approvals.png` |
| `/admin/export-handoff` | `docs/evidence/phase1/screenshots/05_exports.png` |
| `/admin/audit-logs` | `docs/evidence/phase1/screenshots/06_audit.png` |
