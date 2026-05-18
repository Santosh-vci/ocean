# 22 - Phase 4 Completion Evidence

## Status

Phase 4 is closed as **PASS with Synthetic Event Feed Mode** on May 18, 2026.

The implementation proves operational event candidates, trusted confirmations, manual confirmation with reason, device/feed health, actualization, board integration, event-driven exceptions, audit trail, idempotent replay, and browser-visible evidence without depending on live PLC, weighbridge, CTS, bridge, tide, MQTT, or HTTP hardware feeds.

## Audit Findings From This Closure Pass

One hardening gap was found and fixed during the Chunk 4.6 closure pass:

1. Phase 4 browser evidence and operator closure documentation did not exist yet.
2. Operations event/health board payloads were fetched without explicit runtime limits.

Fixes landed:

- repeatable Phase 4 browser evidence capture script;
- checked-in Phase 4 machine evidence and screenshots;
- Phase 4 operator runbook;
- this completion evidence document;
- bounded operations list responses for event candidates, confirmed events, devices, and health snapshots;
- frontend operations fetches now request explicit limits.

## Machine Evidence

Latest proof file:

```text
docs/evidence/phase4/phase4_operations_evidence.json
```

Key values from the latest proof:

| Evidence | Value |
|---|---|
| Run ID | `P4-OPERATIONS-20260518125246` |
| Generated at | `2026-05-18T12:52:46.415878+00:00` |
| Overall result | `PASS` |
| Proof stages | `5/5` |
| Candidate events | `12` |
| Confirmed events before browser manual confirmation | `6` |
| Actualizations | `18` |
| Health snapshots | `6` |
| Pending candidates before browser manual confirmation | `5` |
| Device offline risks | `1` |
| Proof audit events | `27` |

The proof stages are:

1. Synthetic batch pack seeded.
2. Synthetic operations batches replayed.
3. Operational evidence verified.
4. Edge batch rerun idempotence verified.
5. Replay audit verified.

## Browser Evidence

Browser evidence file:

```text
docs/evidence/phase4/browser_visibility_evidence.json
```

Screenshots:

- `docs/evidence/phase4/screenshots/phase4-event-console.png`
- `docs/evidence/phase4/screenshots/phase4-event-console-after-confirm.png`
- `docs/evidence/phase4/screenshots/phase4-jetty-actuals.png`
- `docs/evidence/phase4/screenshots/phase4-cts-actuals.png`
- `docs/evidence/phase4/screenshots/phase4-tide-bridge-state.png`
- `docs/evidence/phase4/screenshots/phase4-exception-row.png`
- `docs/evidence/phase4/screenshots/phase4-audit-logs.png`

Visible UI proof from the latest browser evidence:

- Operations Event Console shows pending, confirmed, duplicate, offline-device, and degraded-feed counts.
- Browser automation confirmed one pending event with reason `operator_verified`, producing `operational_event.confirmed` audit evidence.
- Jetty Loading shows planned start/end beside actual start/end and pending confirmation evidence.
- CTS / Floating Crane shows low-rate signal status, actual complete timing, and confirmation evidence.
- Tide & Bridge Window shows observed bridge and tide state beside the planned window timeline.
- Exception Center shows event-driven rows such as tide-threshold and device-health evidence.
- Audit & Logs shows `phase4.proof.*`, `operations.edge_batch.*`, `operations.device_health.*`, `operational_event.ingested`, and `operational_event.confirmed`.

## Performance Evidence

The browser capture records runtime payload timings for the operations event and health surfaces.

| Evidence | Value |
|---|---|
| Browser evidence generated at | `2026-05-18T12:52:46.705Z` |
| Manual confirmation action | `clicked_confirm_event` |
| Slowest board route check | `1183 ms` |
| Operations API resource count | `9` |
| Slowest operations API resource | `439 ms` |
| Performance pass | `true` |

The frontend uses explicit limits for:

- `/api/operations/event-candidates/?limit=160`
- `/api/operations/confirmed-events/?limit=160`
- `/api/operations/devices/?limit=80`

The backend also supports bounded list responses for operations event queues and health snapshots.

## Commands Run

Backend health:

```text
docker compose exec -T api python manage.py check
```

Phase 4 proof:

```text
docker compose exec -T api python manage.py phase4_operations_proof --json
```

Targeted backend tests:

```text
docker compose exec -T api pytest apps/operations/tests/test_operations_foundation.py apps/core/tests/test_phase4_operations_proof.py -q
```

Frontend checks:

```text
npm run lint
npm run test -- --run
npm run build
```

Browser evidence:

```text
node scripts/capture_phase4_browser_evidence.mjs
```

## Closure Decision

Phase 4 lands correctly for the intended scope:

- It ingests deterministic synthetic operational event batches.
- It separates event candidates from confirmed operational facts.
- It auto-confirms trusted events where policy permits.
- It supports reasoned manual confirmation from the UI.
- It actualizes scoped schedule/assignment/trip fields while preserving planned timestamps.
- It surfaces device/feed health and offline risk.
- It integrates actuals into Jetty, CTS, Tide/Bridge, Live Map, and Exception Center surfaces.
- It proves auditability from replay through confirmation and actualization.
- It can be rerun idempotently.
- It documents the difference between Synthetic Event Feed Mode and future real hardware mode.

No additional Phase 4 scenario is required before closure.

## Deferred By Design

The following remain out of scope for Phase 4 and should not block closure:

- production hardware integrations and credentials;
- MQTT/broker dead-letter handling beyond the synthetic edge-buffer proof;
- device calibration and source-of-truth reconciliation;
- automatic optimizer decisions;
- fleet-wide recovery repair;
- external/customer-facing publication of confirmed milestones;
- SLA/demurrage financial modeling.

These belong to later Phase 5 and downstream integration phases.
