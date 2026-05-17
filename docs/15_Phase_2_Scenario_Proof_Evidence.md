# 15 - Phase 2 Scenario Proof Evidence

**Evidence run:** `P2-SCENARIO-20260517142209`

**Generated at:** `2026-05-17T14:22:10Z`

**Machine-readable evidence:** `docs/evidence/phase2/phase2_scenario_evidence.json`

**Browser visibility evidence:** `docs/evidence/phase2/browser_visibility_evidence.json`

## Definition-of-done summary

| Item | Runtime evidence |
|---|---|
| Scenario seed pack | 7 scenarios verified |
| Projection materialization | 42 trip projections and 105 constraint evaluations |
| Multi-run comparison | `RUN-SIM-MULTI-CANDIDATE-01` max delay 60m; `RUN-SIM-MULTI-CANDIDATE-02` max delay 120m |
| Selected-run promotion | `SIM-JETTY-DELAY` promoted to `PLAN-2026-05-18 V2` |
| Governance gate | Approval `APR-PLAN-2026-05-18-V2` remains pending and publish-blocked by risk |
| Governed export | `EXP-SCENARIO_DIFF-20260517142210-533EB9` generated with checksum |
| Audit lineage | 7 `phase2.proof.*` audit events recorded |

## Formal closure publish run

The scenario proof above intentionally demonstrates the governance block for a risky promoted candidate. A separate green-path closure run was executed to prove that a low-risk Phase 2 scenario can also move through the unchanged approval and publication workflow.

| Closure item | Runtime evidence |
|---|---|
| Closure run | `P2-FORMAL-CLOSURE-20260517195630` |
| Baseline | `PLAN-PHASE1-E2E V1`, status `published`, validation `feasible`, open blockers `0` |
| Scenario | `SIM-P2-CLOSURE-PUBLISH` |
| Assumptions | manual tug reassignment `BER-TUG-08` -> `BER-TUG-09`; confirmed tide and bridge windows `TIDE-P1-E2E-RANTAU`, `BRDG-P1-E2E-GATE-B` |
| Scenario run | `RUN-SIM-P2-CLOSURE-PUBLISH-01`, status `succeeded` |
| Projection evidence | 2 trip projections, 14 event projections, 8 resource utilization rows, 0 critical evaluations |
| Promoted candidate | `PLAN-PHASE1-E2E V2`, validation `feasible`, open blockers `0` |
| Scenario diff | changed trips `1`, delay delta `0`, quantity delta `0` |
| Dual approval | `APR-PLAN-PHASE1-E2E-V2`, approved by `berau.scheduler@coalflow.local` and `abl.dispatcher@coalflow.local` |
| Publication | `LIVE-PLAN-PHASE1-E2E-V2`, status `active`; previous `LIVE-PLAN-PHASE1-E2E-V1` superseded |
| Governed export | `EXP-SCENARIO_DIFF-20260517195631-7810F8`, record count `2`, checksum `4f1c1d8574613a088e7094953e5435d61e4ff1fd0d37227f713019d4824fcb37` |
| Audit trail | 6 `phase2.closure.*` audit events for the successful closure run |

Formal closure conclusion: product Phase 2 is now proven for both required governance outcomes. The risky scenario path remains publish-blocked by constraint risk, and the green scenario path can be promoted, dual-approved, published, audited, and exported with scenario lineage intact.

## Seeded scenario pack

| Scenario | Purpose |
|---|---|
| `SIM-JETTY-DELAY` | delay propagation from a governed override |
| `SIM-TUG-OUTAGE` | tug outage recovery impact |
| `SIM-TIDE-RECOVERY` | tight tide/bridge recovery assessment |
| `SIM-CTS-RATE` | CTS rate degradation effect |
| `SIM-TOPUP-DEMAND` | top-up demand queue-impact proxy |
| `SIM-MANUAL-REASSIGNMENT` | manual tug reassignment comparison |
| `SIM-MULTI-CANDIDATE` | repeat-run comparison with different assumptions |

## Browser evidence artifacts

The in-app browser was used after the proof run to confirm the proof data is visible in the UI.

| Route | Screenshot artifact | Visible evidence |
|---|---|---|
| `/simulation/workspace` | `docs/evidence/phase2/screenshots/01_simulation_workspace.png` | scenario pack, selected run, baseline-vs-scenario output |
| `/approvals/publishing` | `docs/evidence/phase2/screenshots/02_approvals_publishing.png` | scenario source lineage and publish-blocked gate |
| `/admin/export-handoff` | `docs/evidence/phase2/screenshots/03_export_handoff.png` | scenario-diff export with checksum |
| `/admin/audit-logs` | `docs/evidence/phase2/screenshots/04_audit_logs.png` | `phase2.proof.*` audit events |

## How to rerun

From `F:\ocean`:

```text
docker compose exec -T api python manage.py phase2_scenario_proof --json
```

To refresh the host-side evidence file:

```text
docker compose exec -T api python manage.py phase2_scenario_proof --json > docs/evidence/phase2/phase2_scenario_evidence.json
```

Then open `http://localhost:8080/#/simulation/workspace` as `admin@coalflow.local` and confirm the seven scenario IDs are visible.
