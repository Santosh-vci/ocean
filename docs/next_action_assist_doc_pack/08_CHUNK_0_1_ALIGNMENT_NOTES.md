# Next Action Assist - Chunk 0/1 Alignment Notes

Date: 2026-05-19
Branch: `dev`

## Chunk 0 Findings

- Backend settings module: `backend/config/settings.py`.
- Root API routing: `backend/config/urls.py`, with app URLs included under `/api/`.
- Auth model: Django session authentication through DRF defaults.
- Permission enforcement pattern: app viewsets use `apps.rbac.permissions.RequiresAccessPermission` and action-to-permission maps.
- Backend test runner: `pytest` from the `backend` directory, with `DJANGO_SETTINGS_MODULE=config.settings`.
- Frontend route ownership remains centralized in `frontend/src/App.tsx` and `frontend/src/lib/navigation.ts`.
- Phase 5 route and handler ownership exists:
  - `/recovery/recommendations`
  - `RecommendationConsolePage`
  - `handleGenerateRecoveryOptions`
  - `handleMaterializeRecommendation`
- Phase 5 persisted objects are in `backend/apps/scheduling/models.py`:
  - `RecoveryInputSnapshot`
  - `OptimizerRun`
  - `RecoveryRecommendation`
  - `RecoveryAction`
  - `RecommendationEvaluation`
- Phase 5 services are in `backend/apps/scheduling/recovery_services.py`.
- Phase 5 proof command exists at `backend/apps/core/management/commands/phase5_recovery_proof.py`.

No code/document mismatch was found that blocks Chunk 1.

## Chunk 1 Implementation Notes

- Added backend assistant app skeleton at `backend/apps/assistant/`.
- Registered `apps.assistant` in Django settings.
- Added assistant URL module for future `/api/assistant/` endpoint registration.
- Added immutable action registry with all first-sprint and Product Phase 5 action IDs.
- Added route ownership mapping including `/recovery/recommendations`.
- Added `ActionRecommendation` and `build_recommendation` factory using registry defaults.
- Added registry tests covering uniqueness, required fields, audited mutations, Phase 5 action coverage, route ownership, and recommendation factory defaults.
