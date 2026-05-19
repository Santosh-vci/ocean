# Next Action Assist - Release Hardening Notes

## Scope

This release hardens the deterministic Next Action Assist workflow through Chunk 12:

- Registry-backed action definitions and route ownership.
- Read-only backend context selectors and recommendation rules.
- API serialization for global, page, row, blocked, and checklist recommendations.
- Frontend assisted/off mode storage, shell next-action UI, dashboard inbox, page cards, row hints, and disabled reasons.
- Product Phase 5 recovery recommendation integration through optimizer result review, recommendation materialization, simulation, approval, publish blocking, and proof-pack review.

## Governance Checks

Automated coverage now verifies:

- All emitted rule action IDs exist in `ACTION_REGISTRY`.
- Every registry action is owned by its default route and by at least one non-dashboard route.
- Route ownership maps only to registered action IDs.
- Mutating actions declare audit requirements.
- No disabled recommendation can become `global_next_action`.
- Blocking conflicts and recommendation-origin blocking risk keep publish/export out of the top action.
- `/recovery/recommendations` owns object-scoped recommendation actions.
- Phase 5 mutating recommendation actions do not point at the assistant endpoint and require existing scheduling permissions.
- The assistant endpoint remains read-only and rejects mutating HTTP methods.
- Any future frontend `data-action-id` attributes are statically checked against the registry.

Current exemptions:

- `/dashboard/situation` is a deliberate catch-all inbox. It does not exempt actions from route ownership on their workflow pages.
- Frontend action buttons currently rely on typed recommendation payloads rather than explicit `data-action-id` attributes. The scanner is present for future additions.
- The assistant recommends Phase 5 recovery actions but does not execute optimizer runs, materialize recommendations, publish plans, generate exports, or write proof-pack audit entries.

## UAT Coverage

`backend/apps/assistant/tests/test_uat_flows.py` models the expected action sequence for:

- Happy path: demand import, sequence review, operating windows, plan generation, approval, publish, and export.
- Blocking conflict path: Exception Center, recovery options, scenario creation, simulation, promotion, and approval handoff.
- Event confirmation path: high-confidence confirmation, noisy rejection, and actualization risk guidance.
- Published-plan change path: create draft before regenerating a changed published plan.
- Product Phase 5 path: recovery options, recommendation console, object-scoped materialization, scenario workflow, publish blocking under unresolved risk, and proof-pack review.

## Release Proof Commands

Use these commands as the release gate:

```powershell
docker compose exec -T api pytest apps/assistant/tests -q
docker compose exec -T api python manage.py check
docker compose exec -T api python manage.py phase5_recovery_proof --json > docs\evidence\phase5\phase5_recovery_evidence.json
docker compose exec -T api pytest apps/core/tests/test_phase5_recovery_proof.py -q
docker compose exec -T api pytest apps/scheduling/tests/test_schedule_generation.py -q
node scripts\capture_phase5_browser_evidence.mjs
```

Target acceptance:

- Assistant endpoint p95 remains below 250 ms on seed data.
- No assistant selector performs optimizer generation, proof-pack audit writes, scenario materialization, approval, publish, or export.
- Cockpit pages remain usable if the assistant API fails.
- Browser evidence covers Dashboard, Exception Center, Recommendation Console, Simulation Workspace, Approvals, Event Console, Export Handoff, Audit Logs, and shell/topbar in assisted and off modes.

## Known Limitations

- Guided mode currently exposes checklist scaffolding; it does not enforce step-by-step navigation.
- Supervisor mode remains a stored/displayed mode placeholder and does not yet aggregate cross-role SLA ownership.
- Recommendation copy is deterministic rule text. LLM summarization is still deferred and must remain bounded by registry fields if introduced.
- Phase 5 proof-pack review is advisory evidence guidance; the assistant does not mark proof packs reviewed.
