# 21 - Phase 4 Operator Runbook

## Purpose

Phase 4 adds the operational trust layer on top of Phase 3 live-shaped telemetry. The current build runs in **Synthetic Event Feed Mode**: deterministic seed and replay messages behave like jetty PLC, CTS, tide, bridge, and device-health feeds, but they are not connected to real hardware yet.

Use this runbook to test whether candidate operational events are visible, reviewable, confirmable, auditable, and reflected as actual execution evidence without rewriting the planned schedule.

## Roles

| Role | User | What to test |
|---|---|---|
| Admin | `admin@coalflow.local` | Full proof, manual confirmation, all boards, audit review |
| ABL Dispatcher | `abl.dispatcher@coalflow.local` | CTS, bridge, tide, and replay authority |
| Berau Scheduler | `berau.scheduler@coalflow.local` | Jetty confirmation and exception review |
| Joint Control Tower | `control.tower@coalflow.local` | Cross-party governance and publish context |
| Viewer | `viewer@coalflow.local` | Read-only visibility where allowed |

## Reset And Proof Commands

Run commands from `F:\ocean`.

Start or refresh the stack:

```text
docker compose up -d --build db redis object-store api frontend proxy worker beat
docker compose ps
```

Run the repeatable Phase 4 proof:

```text
docker compose exec -T api python manage.py phase4_operations_proof --json > docs\evidence\phase4\phase4_operations_evidence.json
```

Capture browser evidence:

```text
node scripts\capture_phase4_browser_evidence.mjs
```

The browser capture writes:

- `docs/evidence/phase4/browser_visibility_evidence.json`
- `docs/evidence/phase4/screenshots/phase4-event-console.png`
- `docs/evidence/phase4/screenshots/phase4-event-console-after-confirm.png`
- `docs/evidence/phase4/screenshots/phase4-jetty-actuals.png`
- `docs/evidence/phase4/screenshots/phase4-cts-actuals.png`
- `docs/evidence/phase4/screenshots/phase4-tide-bridge-state.png`
- `docs/evidence/phase4/screenshots/phase4-exception-row.png`
- `docs/evidence/phase4/screenshots/phase4-audit-logs.png`

## What Phase 4 Proves

The Phase 4 proof is complete when the operator can verify:

- synthetic edge batches can be replayed idempotently;
- operational event candidates remain separate from confirmed facts;
- trusted events can auto-confirm according to feed policy;
- pending events require an authorized reasoned confirmation or rejection;
- confirmed events update actual execution fields only;
- planned timestamps remain intact beside actual timestamps;
- device/feed health creates visible risk evidence;
- event-driven exceptions appear in the Exception Center;
- audit logs show ingestion, duplicate handling, replay, confirmation, actualization, and proof events.

## UI Flow

### Stage 1 - Open Operations Event Console

1. Open `http://localhost:8080`.
2. Log in as `admin@coalflow.local`.
3. Open **Operations -> Event Confirmation**.
4. Confirm the KPI strip shows pending, confirmed, duplicate, offline-device, and degraded-feed counts.
5. Confirm **Feed and device health** shows the latest device health state.
6. Select a pending event candidate and inspect:
   - event type;
   - asset;
   - feed and device;
   - planned timestamp, when matched;
   - candidate timestamp;
   - variance and confidence.

Acceptance evidence: the screen is a trust desk. A candidate is not treated as operational truth until confirmed.

### Stage 2 - Confirm A Pending Candidate

1. In **Operations Event Console**, keep a pending candidate selected.
2. Review or edit **Confirmed actual time**.
3. Keep or edit the confirmation reason.
4. Click **Confirm event**.
5. Confirm a success banner appears.
6. Confirm the selected event leaves the pending queue and appears in **Confirmed event ledger** with actor, reason, mode, and actual time.

Acceptance evidence: confirmation is governed. It is not a silent table edit.

### Stage 3 - Review Jetty Actuals

1. Open **Operations -> Jetty Loading**.
2. Confirm the board shows **Planned start / end** and **Actual start / end**.
3. Confirm `JTY-SUARAN` shows actual loading evidence from the replay.
4. Confirm the side panel shows feed health and a pending confirmation panel for any remaining jetty candidate.

Acceptance evidence: the jetty board can compare the planned loading schedule with confirmed actual execution.

### Stage 4 - Review CTS Actuals

1. Open **Operations -> CTS / Floating Crane**.
2. Confirm the board shows planned discharge timing, actual complete timing, and low-rate signal status.
3. Confirm the side panel shows CTS event detail and pending confirmation evidence.

Acceptance evidence: CTS operational signals are visible beside the plan and can drive exception review.

### Stage 5 - Review Tide And Bridge Operational State

1. Open **Constraints -> Tide & Bridge Window**.
2. Confirm the planned window timeline remains visible.
3. Confirm **Observed gate state** shows bridge and tide signals with actual time, variance, and feed health.

Acceptance evidence: observed bridge/tide facts augment the constraint board without replacing the planned windows.

### Stage 6 - Review Event-Driven Exceptions

1. Open **Recovery Loop -> Exception Center**.
2. Confirm event-driven rows appear, such as:
   - `CTS_LOW_RATE_CANDIDATE`;
   - `TIDE_SENSOR_BELOW_THRESHOLD`;
   - device-health risk rows.
3. Select an event-driven row and inspect the right detail panel.
4. Confirm the impact chain uses operational evidence and states that board actuals remain separate from planned timestamps.

Acceptance evidence: operational events become triage evidence, not automatic replanning.

### Stage 7 - Review Audit Evidence

1. Open **Admin Console -> Audit & Logs**.
2. Confirm audit rows exist for:
   - `operations.edge_batch.replayed`;
   - `operations.edge_batch.replay_skipped`;
   - `operations.device_health.ingested`;
   - `operational_event.ingested`;
   - `operational_event.duplicate`;
   - `operational_event.confirmed`;
   - `phase4.proof.*`.
3. Select a row and inspect actor, object, request ID, archive status, and metadata.

Acceptance evidence: the proof chain is traceable from replay to confirmation and board actualization.

## Synthetic Event Feed Mode Vs Real Hardware Mode

Synthetic Event Feed Mode:

- uses deterministic seed/replay edge batches;
- is safe to rerun locally;
- proves contracts, governance, UI behavior, and auditability;
- does not prove production device connectivity, broker reliability, or hardware calibration.

Real Hardware Mode later should attach actual PLC, weighbridge, CTS, bridge, tide, MQTT, or HTTP feeds to the same candidate-event contracts. The operator screens should not need a new mental model: real feeds still create candidates, confirmation policies still decide trust, and confirmed events still actualize only scoped actual fields.

## Replay Batches

| Batch | Meaning | Expected evidence |
|---|---|---|
| `PHASE4-EXECUTION-001` | Jetty, bridge, tide, CTS, and discharge event stream | Candidates, auto-confirmed facts, pending manual-review rows, actualizations |
| `PHASE4-HEALTH-001` | Device heartbeat and synthetic outage | Health snapshots, offline device risk, audit events |

## Current Limits

Phase 4 does not include:

- live broker credentials or production hardware adapters;
- device calibration workflows;
- automatic recovery optimization;
- fleet-wide resequencing;
- customer-facing milestone publication;
- external data-sharing rules for raw candidate payloads.

These are intentionally deferred to later phases. Phase 4 closes the governed operations-event confirmation layer.

## Troubleshooting

If the Event Console shows no candidates, rerun:

```text
docker compose exec -T api python manage.py phase4_operations_proof --json
```

If screenshots fail, set `CHROME_PATH` to a Chromium-compatible browser and rerun:

```text
set CHROME_PATH=C:\Program Files\Google\Chrome\Application\chrome.exe
node scripts\capture_phase4_browser_evidence.mjs
```

If confirmation is disabled, use a role with the relevant confirmation permission. Admin has all Phase 4 confirmation permissions.

If actuals do not appear on Jetty or CTS boards, confirm the replay proof ran and refresh the browser after the frontend service is healthy.
