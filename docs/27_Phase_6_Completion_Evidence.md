# 27 - Phase 6 / Phase 5+ Completion Evidence

**Status:** closure evidence captured

**Captured:** 30 May 2026

## Summary

Phase 6 / Phase 5+ is closed with browser-visible UI CTA evidence for the clean operator happy path, browser-visible UI CTA evidence for the Phase 5+ recovery path, and review-surface evidence for the read-only Phase 6 additions.

This closure does not add automatic publishing. It proves that implemented flow runtime, Next Action guidance, root-cause validation, publishability gate, global optimizer review, telemetry trust, and commercial projection surfaces are visible and governed.

## Evidence Commands

```powershell
node scripts/capture_operator_trial_flow_evidence.mjs
node scripts/capture_phase6_recovery_flow_evidence.mjs
node scripts/capture_phase6_review_surface_evidence.mjs
```

## UI CTA Evidence

| Evidence | Result | Artifact |
|---|---:|---|
| Clean operator happy path | Passed, 16 browser steps | `docs/evidence/operator_trial_flow/operator_trial_flow_capture.json` |
| Phase 5+ recovery path | Passed, 17 browser steps | `docs/evidence/phase6_recovery_flow/phase6_recovery_flow_capture.json` |
| Phase 6 review surfaces | Passed, 3 review surfaces | `docs/evidence/phase6_review_surfaces/phase6_review_surface_capture.json` |

### Clean Operator Happy Path

The happy-path run starts from deterministic DB truth with no demand, plans, approvals, publishability assessments, published snapshots, or exports. The browser then clicks visible UI CTAs assisted by Next Action:

1. import OGV demand;
2. review coal sequence;
3. enter operating windows;
4. generate plan;
5. submit approval;
6. approve both authorities;
7. run publishability check;
8. manually publish;
9. generate governed export.

Final assertions recorded in the JSON evidence:

- `operator_happy_path_v1` flow completed;
- active published snapshot exists;
- approvals are complete;
- publishability allows publish;
- governed export exists.

Screenshots are under `docs/evidence/operator_trial_flow/screenshots/`.

### Phase 5+ Recovery Path

The recovery run starts from deterministic DB truth with disrupted demand and a blocked plan, but with no pre-created recommendations, scenarios, root-cause assessments, publishability assessments, approvals, or published recovery snapshot. The browser then clicks visible UI CTAs:

1. open Exception Center;
2. generate recovery options;
3. validate root-cause repair;
4. materialize recommendation as scenario;
5. rerun simulation;
6. promote scenario;
7. repair remaining conflicts through windows and regeneration;
8. submit approval;
9. approve both authorities;
10. run publishability check;
11. manually publish.

Final assertions recorded in the JSON evidence:

- `phase5_plus_recovery_v1` flow completed;
- recommendations were created through UI CTAs;
- root-cause assessment exists;
- scenario was materialized through UI CTAs;
- publishability assessment exists;
- approvals are complete;
- active published snapshot exists.

Screenshots are under `docs/evidence/phase6_recovery_flow/screenshots/`.

### Read-Only Review Surfaces

The review-surface capture uses backend setup/generation only to create visibility data for read-only pages. It is not counted as operator happy-path execution.

Captured surfaces:

- `/optimization/global`: global optimizer run with 3 candidates; no materialize, promote, approve, or publish controls.
- `/map/live`: telemetry trust profile `telemetry_trust_default_v1` with trust assessment summary visible.
- `/commercial/projections`: commercial projection run with projection-only labels and no settlement, invoice, commitment, approval, materialization, or publish controls.

Screenshots are under `docs/evidence/phase6_review_surfaces/screenshots/`.

## Verification Commands

The closure verification command set was run after evidence capture:

```powershell
docker compose exec -T api python manage.py check
docker compose exec -T api python manage.py makemigrations --check --dry-run
docker compose exec -T api pytest apps/flows/tests apps/assistant/tests apps/core/tests/test_phase5_recovery_proof.py apps/scheduling/tests/test_root_cause_repair_assessment.py apps/scheduling/tests/test_publishability_gate.py apps/scheduling/tests/test_global_optimizer_scaffold.py apps/scheduling/tests/test_commercial_projection.py apps/telemetry/tests/test_telemetry_trust_profiles.py -q
docker compose exec -T frontend npm test -- App.test.tsx types/assistant.test.ts lib/flowEvidence.test.ts
docker compose exec -T frontend npm run build
```

Results:

- `python manage.py check`: passed.
- `python manage.py makemigrations --check --dry-run`: passed, no changes detected.
- targeted backend pytest suite: passed, 135 tests.
- targeted frontend Vitest suite: passed, 43 tests; existing React `act(...)` warnings were emitted by older component tests.
- frontend production build: passed.

## Implementation Notes From Closure

Two evidence-breaking defects were fixed during closure:

- flow evaluation now treats completed steps as monotonic, so a completed early step is not reopened when later domain state changes;
- flow selectors now prefer the latest current operational plan version over an older approved baseline, which lets promoted recovery candidates satisfy conflict-repair selectors before approval.

The recovery UI also records `REPAIR_PLAN_CONFLICTS` flow CTA evidence after the page-owned `Regenerate plan` mutation succeeds.

## Remaining Business Decisions

- Automatic publishing remains out of scope.
- Berau and ABL approval remains required and is not replaced.
- Global optimizer objective weights are configurable defaults pending commercial sign-off.
- GPS/AIS is evidence gated by telemetry trust assessment, not unconditional production truth.
- Commercial output remains projection-only and excludes final customer commitment, NOR/SOF, laytime, demurrage settlement, invoicing, and despatch settlement.
