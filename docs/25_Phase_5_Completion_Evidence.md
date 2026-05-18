# 25 - Phase 5 Completion Evidence

## Status

Phase 5 is closed as **PASS for deterministic recovery recommendation scope** on May 18, 2026.

The implementation now proves the full operator path from disruption input to ranked recommendation, scenario materialization, promotion into approval, recommendation proof-pack reconstruction, and browser-visible evidence. It also preserves the existing governance rule: a recommendation-origin candidate may be dual-approved and still remain publish-blocked if unresolved blocking risk remains.

## Hardening Added In Chunk 5.6

The Chunk 5.6 closure pass added:

- recommendation proof-pack assembly from persisted runtime state;
- `GET /api/scheduling/recommendations/{id}/proof-pack/`;
- governed recommendation dismissal support;
- compatibility alias for the shorter `/recommendations/` API path while preserving `/recovery-recommendations/`;
- audited proof-pack access;
- repeatable `phase5_recovery_proof` command;
- browser evidence capture script;
- this completion document and the Phase 5 operator runbook.

Two closure defects were found and fixed while exercising the runtime:

1. the Recommendation Console lost all optimizer runs after a recommendation-origin scenario was promoted because the overview only read the active successor version, not its source version;
2. rerunning the seeded proof after a scenario run existed could fail during reset because scenario projection children were not cleared before scenarios.

The closure pass now keeps baseline recommendation lineage visible while a promoted successor is active, and the seed reset path explicitly clears scenario projections and runs before deleting scenarios.

## Machine Evidence

Latest proof file:

```text
docs/evidence/phase5/phase5_recovery_evidence.json
```

Key values from the latest proof:

| Evidence | Value |
|---|---|
| Run ID | `P5-RECOVERY-20260518173204` |
| Generated at | `2026-05-18T17:32:05.744155+00:00` |
| Overall result | `PASS` |
| Proof stages | `7/7` |
| Governed optimizer run | `OPT-P5-RECOVERY-20260518173204` |
| Ranked recommendations | `5` |
| Selected recommendation | `REC-BC6AEB2A0C00` |
| Selected strategy | `cts_reassignment` |
| Selected score / risk | `89.0 / low` |
| Materialized scenario | `SIM-PLAN-2026-05-20-V1-08` |
| Scenario run | `RUN-SIM-PLAN-2026-05-20-V1-08-01` |
| Approval request | `APR-PLAN-2026-05-20-V2` |
| Approval status | `approved` with 2 decisions |
| Candidate validation | `blocked` |
| Publish blocked by risk | `true` |
| Proof-pack version | `phase5.6-recommendation-proof-pack` |
| Proof-pack audit trail rows | `7` |

The proof stages are:

1. recommendation seed pack verified;
2. governed recovery run verified;
3. ranking verified;
4. recommendation materialized into a scenario;
5. promotion and approval handoff verified;
6. recommendation proof pack verified;
7. proof audit evidence verified.

## Browser Evidence

Browser evidence file:

```text
docs/evidence/phase5/browser_visibility_evidence.json
```

Screenshots:

- `docs/evidence/phase5/screenshots/phase5-exception-center.png`
- `docs/evidence/phase5/screenshots/phase5-recommendation-console.png`
- `docs/evidence/phase5/screenshots/phase5-simulation-workspace.png`
- `docs/evidence/phase5/screenshots/phase5-approvals-publishing.png`
- `docs/evidence/phase5/screenshots/phase5-audit-logs.png`

Visible UI proof from the latest browser capture:

- Exception Center exposes **Generate recovery options**.
- Recommendation Console shows the ranked candidate set, before/after actions, and explanation chain.
- Simulation Workspace shows the materialized recovery recommendation scenario and lineage.
- Approvals & Publishing shows the promoted candidate inside the approval workflow.
- Audit & Logs shows `phase5.proof.*` evidence.

## Commands Run

```text
docker compose exec -T api python manage.py phase5_recovery_proof --json > docs\evidence\phase5\phase5_recovery_evidence.json
docker compose exec -T api pytest apps/core/tests/test_phase5_recovery_proof.py -q
docker compose exec -T api pytest apps/scheduling/tests/test_schedule_generation.py -q
node scripts\capture_phase5_browser_evidence.mjs
```

## Closure Decision

Phase 5 lands correctly for the intended first-pass scope:

- it starts from real persisted disruption state;
- it generates deterministic ranked recovery options;
- it explains recommendation score, risk, hard constraints, and changed actions;
- it converts the chosen recommendation into a scenario instead of mutating the active plan;
- it routes the scenario into existing approval governance;
- it preserves publication blocking when unresolved risk remains;
- it reconstructs a recommendation proof pack from persisted lineage and audit events.

No additional Phase 5 scenario is required before closure of the deterministic recommendation MVP.

## Deferred By Design

The following remain intentionally out of scope for the first Phase 5 pass:

- global commercial optimization;
- fuel or emissions optimization;
- autonomous publication;
- external optimizer integration;
- customer commitment workflows;
- broad multi-trip what-if search beyond the deterministic repair families already implemented.
