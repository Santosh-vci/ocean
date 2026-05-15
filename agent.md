# Agent Guide — Coalflow Tower

## 1. Mission

Build a Docker-first, multi-organization coal transshipment planning platform for Berau and ABL. The product replaces brittle Excel scheduling with a governed, constraint-aware operational plan.

This is **not** a vessel-tracking app with scheduling bolted on later. The scheduler, approval workflow, and audit trail are the spine.

## 2. Read this first

Before making material changes, read in order:

1. `docs/00_README_Index.md`
2. `docs/01_Ground_Reality_Operations.md`
3. `docs/02_Planning_Tool_Scope.md`
4. `docs/03_Data_Architecture_and_IoT_Scope.md`
5. `docs/04_RBAC_and_Django_Architecture_Addendum.md`
6. `docs/07_Frontend_Build_Handoff_and_Phasewise_Plan.md`
7. `docs/08_Phase_1_Implementation_Spec.md`
8. `docs/berau_abl_seed_data_instructions.md` when creating or extending seed data
9. any BRD document in `docs/` whose filename starts with `BRD`

The hardened frontend zips under `docs/frontend_resources/` are visual references, not production code.

Treat those frontend resource packs as **scenario-complete screen baselines**. For each chunk, adapt only the resource packs whose backend truth exists in that chunk; preserve their cockpit structure and operational intent, but do not fabricate later-phase data just to make a screen look finished.

Treat `berau_abl_seed_data_instructions.md` as the seed-data operating map. Whenever a chunk reaches locations, routes, assets, compatibility, OGV demand, telemetry, exceptions, approvals, or published plans, seed data must use the Berau/ABL vocabulary, approximate geography, stable IDs, and scenario intent described there.

## 3. Product truths

- Coal is grade-specific, quantity-specific, and sequence-specific.
- A valid trip chain couples source, jetty, tug, barge, route, tide/bridge windows, CTS, and OGV.
- Plan state must stay distinct from observed, manually confirmed, derived, and recommended state.
- Published plans are immutable snapshots; revisions create successor versions.
- Multi-organization RBAC, data scope, workflow authority, and audit are core capabilities.
- A dense operational cockpit beats a decorative dashboard.
- Frontend permission hiding never substitutes for backend authorization.

## 4. Product Phase 1 boundary

Phase 1 means the **digital scheduling model**:

- master data;
- OGV demand intake;
- cargo grade / layer sequence;
- manual asset, jetty, CTS, tide, and bridge availability;
- deterministic feasible-schedule generation;
- conflict checks;
- versioning, approvals, publishing, audit;
- Dockerized runtime.

Do not quietly drag later-phase complexity into Phase 1:

- no dependency on live AIS/GPS;
- no optimizer masquerading as a first milestone;
- no customer portal;
- no advanced telemetry stack unless explicitly requested.

## 5. Target stack

- Backend: Django + Django REST Framework
- Database: PostgreSQL, preferably PostGIS-enabled
- Cache / broker: Redis
- Background work: Celery + Celery Beat
- Frontend: React + Vite + TypeScript
- Files: S3-compatible object storage such as MinIO
- Runtime: Docker Compose first

Chunk 0 froze these implementation choices:

- use a React/Vite SPA rather than Next.js;
- use a PostGIS-enabled PostgreSQL image from day one;
- include MinIO in local/dev from day one;
- treat XLSX as the primary legacy-import format, with CSV allowed where lossless;
- require dual-party approval before publish in the first pilot;
- keep the Live Resource Map manually driven in product Phase 1.

Later phases may add TimescaleDB/ClickHouse, MQTT, Redpanda/Kafka, and dedicated ingestion services. Keep seams clean for those additions.

## 6. Docker rules

- Assume developers should be able to work through Docker alone.
- Prefer containerized commands over host-global installs.
- Keep `.env.example` current.
- A clean checkout should come alive with `docker compose up --build`.
- New services need health checks and documented ports.
- New migrations, seeds, and workers must run inside the container workflow.

## 7. Architecture rules

- Django owns transactional truth.
- Celery owns imports, exports, generation, validation, and other long-running work.
- The frontend consumes APIs; it does not reimplement scheduling authority.
- Keep domain apps separated:
  - accounts / organizations / rbac;
  - masters / coal / fleet / ogv / jetties / routes / constraints;
  - scheduling / approvals / audit;
  - imports / reports.
- Prefer explicit service-layer business logic over burying rules in serializers or views.
- Use stable reason codes for generated decisions and validation conflicts.
- Keep published versions immutable.

## 8. Domain invariants to protect

Never merge or “simplify away” these concepts:

- `CoalGrade` vs generic cargo;
- `CargoLayerStep` vs free-form note;
- `Plan` vs `PlanVersion`;
- `Trip` vs `Assignment`;
- `Conflict` vs generic error;
- `Override` vs normal edit;
- `ApprovalDecision` vs audit comment;
- planned vs confirmed vs observed vs derived vs recommended state.

If a code change weakens one of these distinctions, stop and reconsider the model.

## 9. Security and governance

- Enforce permissions at API and service layer.
- Audit all sensitive mutations:
  - plan changes;
  - approvals;
  - overrides;
  - master-data edits;
  - role or scope changes;
  - exports.
- Keep organization/data-scope tests close to the code that grants access.
- Never let UI-only behavior become the security boundary.
- Require reason capture for overrides and rejection flows.

## 10. Frontend principles

- Use the hardened docs as the visual standard: dark, dense, operational, role-aware.
- Build the shell and reusable primitives before isolated screens.
- Prefer compact grids, right rails, thin KPI strips, and schedule timelines.
- Status color must mean something operational.
- Every board should make the next decision easier, not merely look complete.

## 11. Testing expectations

Maintain tests for:

- permission matrices;
- multi-org visibility;
- import validation;
- grade-sequence validation;
- resource overlap / compatibility;
- tide and bridge feasibility;
- deterministic schedule generation;
- lifecycle transitions;
- audit emission;
- export permissions.

Keep seeded fixtures for:

- happy path;
- tight tide day;
- grade-sequence failure;
- asset outage;
- approval-pending day;
- multi-org scope behavior.

## 12. Documentation discipline

- Update docs when API contracts, domain names, or phase boundaries change.
- Do not let frontend, backend, and docs drift into three vocabularies.
- When adding a new workflow, document:
  - actor;
  - trigger;
  - inputs;
  - outputs;
  - permissions;
  - audit events;
  - failure modes.

## 13. Definition of good work here

Good work in this repo leaves the system:

- more explicit;
- more auditable;
- more testable;
- more faithful to the planning reality;
- easier for the next engineer or agent to extend without guessing.

When forced to choose, prefer the design that preserves operational truth over the one that merely reduces lines of code.
