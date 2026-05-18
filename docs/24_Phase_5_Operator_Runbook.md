# 24 - Phase 5 Operator Runbook

## Purpose

Phase 5 adds decision support on top of the visibility and actualization layers delivered in Phases 3 and 4. It does not autonomously rewrite the live plan. The intended operator flow is:

1. identify a real exception or confirmed disruption;
2. generate ranked recovery options;
3. inspect the reasoning, hard-constraint evidence, and before/after actions;
4. create a governed scenario from the selected recommendation;
5. use the existing scenario, approval, and publish workflow.

## Roles

| Role | User | What to test |
|---|---|---|
| Admin | `admin@coalflow.local` | Full proof flow, audit review, closure evidence |
| Berau Scheduler | `berau.scheduler@coalflow.local` | Generate options, review recommendation detail, submit approval |
| ABL Dispatcher | `abl.dispatcher@coalflow.local` | Cross-party approval review |
| Joint Control Tower | `control.tower@coalflow.local` | Governance and publication context |

## Reset And Proof Commands

Run from `F:\ocean`.

```text
docker compose up -d --build db redis object-store api frontend proxy worker beat
docker compose exec -T api python manage.py phase5_recovery_proof --json > docs\evidence\phase5\phase5_recovery_evidence.json
node scripts\capture_phase5_browser_evidence.mjs
```

The browser capture writes:

- `docs/evidence/phase5/browser_visibility_evidence.json`
- `docs/evidence/phase5/screenshots/phase5-exception-center.png`
- `docs/evidence/phase5/screenshots/phase5-recommendation-console.png`
- `docs/evidence/phase5/screenshots/phase5-simulation-workspace.png`
- `docs/evidence/phase5/screenshots/phase5-approvals-publishing.png`
- `docs/evidence/phase5/screenshots/phase5-audit-logs.png`

## What Phase 5 Proves

Phase 5 is complete when the operator can verify:

- a disruption can seed a normalized recovery input snapshot;
- the optimizer returns ranked, deterministic recommendations;
- each recommendation explains score, risk, changed actions, and hard-constraint evidence;
- the operator can materialize a selected recommendation into a scenario without directly mutating the active plan;
- the scenario can be promoted into the existing approval flow;
- publish remains governed and can still be blocked by unresolved risk;
- the recommendation proof pack reconstructs the snapshot, optimizer run, selected recommendation, scenario lineage, approval lineage, and audit trail.

## UI Flow

### Stage 1 - Start From Triage

1. Open `http://localhost:8080`.
2. Sign in as `admin@coalflow.local` or `berau.scheduler@coalflow.local`.
3. Open **Recovery Loop -> Exception Center**.
4. Select a governed exception, observed alert, or confirmed operational disruption.
5. Click **Generate recovery options**.

Acceptance evidence: recovery starts from an explicit operational trigger, not from a silent free-form edit.

### Stage 2 - Review Ranked Options

1. Open **Recovery Loop -> Recommendation Console**.
2. Confirm the latest optimizer run is visible.
3. Review:
   - rank;
   - score;
   - risk;
   - delay;
   - missed windows;
   - resource conflicts.
4. Select the highest-ranked option and inspect:
   - strategy summary;
   - before/after actions;
   - hard-constraint evidence;
   - explanation chain.

Acceptance evidence: the operator can see both what the engine proposes and why.

### Stage 3 - Create A Scenario

1. Keep the selected recommendation open.
2. Click **Create scenario from recommendation**.
3. Open **Recovery Loop -> Simulation Workspace**.
4. Confirm the scenario shows recommendation lineage and the generated assumptions.

Acceptance evidence: the recommendation becomes a scenario handoff, not a direct production mutation.

### Stage 4 - Promote Through Governance

1. From **Simulation Workspace**, promote the chosen scenario.
2. Open **Recovery Loop -> Approvals & Publishing**.
3. Confirm the approval request shows the promoted candidate and the approval chain.
4. Have both Berau Scheduler and ABL Dispatcher approve.
5. Confirm the candidate can still remain publish-blocked if unresolved blocking risk exists.

Acceptance evidence: optimization does not bypass the existing approval and publication controls.

### Stage 5 - Inspect The Proof Pack

Use the API endpoint for the selected recommendation:

```text
GET /api/scheduling/recommendations/{id}/proof-pack/
```

Confirm the payload contains:

- `inputSnapshot`;
- `optimizerRun`;
- `recommendation`;
- `evaluation`;
- `actions`;
- `scenarioHandoff`;
- `approvalChain`;
- `auditTrail`.

Acceptance evidence: the recommendation can be reconstructed for review after the operator decision.

### Stage 6 - Review Audit

Open **Admin Console -> Audit & Logs** and confirm evidence exists for:

- `recovery.input_snapshot.build`;
- `recovery.optimizer.run`;
- `recovery.recommendation.materialize_scenario`;
- `recovery.recommendation.proof_pack_viewed`;
- `approval.request`;
- `approval.decision`;
- `phase5.proof.*`.

## Current Limits

Phase 5 currently uses a deterministic repair engine. It is intentionally not yet:

- a global optimizer across all trips and commercial objectives;
- an autonomous publisher;
- a replacement for planner judgment;
- a financial demurrage optimizer;
- a live vendor-optimizer integration.

## Troubleshooting

If Recommendation Console is empty, rerun:

```text
docker compose exec -T api python manage.py phase5_recovery_proof --json
```

If the scenario handoff is missing, confirm the selected recommendation is not dismissed and that it has at least one materializable action.

If approvals are complete but publication is still blocked, inspect unresolved blocking conflicts on the promoted candidate. Phase 5 is designed to preserve that governance block.

If browser evidence fails, set `CHROME_PATH` to a Chromium-compatible browser and rerun:

```text
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
node scripts\capture_phase5_browser_evidence.mjs
```
