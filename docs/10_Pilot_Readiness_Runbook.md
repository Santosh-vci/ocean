# 10 — Pilot Readiness Runbook

## Purpose

This runbook is the Chunk 8 operating checklist for a local or pilot Coalflow Tower deployment.
It covers repeatable Docker start-up, observability checks, backup rehearsal, UAT, and incident-safe handling.

## 1. Repeatable Docker deployment

```powershell
Copy-Item .env.example .env
docker compose up -d --build
docker compose ps
```

Expected healthy services:

- `db`
- `redis`
- `object-store`
- `api`
- `worker`
- `beat`
- `frontend`
- `proxy`

The app entry point is `http://localhost:8080`.

## 2. Baseline smoke checks

```powershell
Invoke-RestMethod http://localhost:8080/api/health/
Invoke-RestMethod http://localhost:8080/api/ready/
docker compose run --rm api python manage.py check
docker compose run --rm api pytest
docker compose run --rm frontend npm test -- --run
docker compose run --rm frontend npm run build
docker compose run --rm -e RUN_STARTUP_TASKS=0 api python manage.py phase1_e2e_proof --json
```

`/api/health/` is a liveness check. `/api/ready/` checks database, cache, and export artifact storage.
`/api/metrics/` is admin-only and exposes counts only; it must not include customer names, passwords, tokens, or raw payloads.

The Phase 1 proof command creates `PLAN-PHASE1-E2E`, publishes
`LIVE-PLAN-PHASE1-E2E-V1`, generates a governed export, and leaves the proof records visible in
the application. The latest captured evidence is documented in
`docs/12_Phase_1_Completion_Evidence.md`; operator usage is documented in
`docs/13_Phase_1_Operator_Manual.md`.

## 3. Seeded pilot users

| User | Password | Intended use |
|---|---|---|
| `admin@coalflow.local` | `admin12345` | full local administrator |
| `control.tower@coalflow.local` | `welcome12345` | all-network schedule approval / publish / export |
| `berau.scheduler@coalflow.local` | `welcome12345` | Berau scoped demand and schedule review |
| `abl.dispatcher@coalflow.local` | `welcome12345` | ABL scoped fleet dispatch |
| `viewer@coalflow.local` | `welcome12345` | read-only observation |

Change all credentials before any shared environment.

## 4. UAT scripts

### UAT-01 — Demand validation to schedule board

1. Sign in as `admin@coalflow.local`.
2. Open **Planning → OGV Demand & Laycan**.
3. Confirm seeded OGV demand rows, laycan windows, and remaining MT are visible.
4. Run the backend demand validation API using a valid row payload.
5. Confirm an import job appears in the planning overview and an audit event is recorded.

### UAT-02 — Conflict and recovery loop

1. Open **Control Tower → Network Situation**.
2. Confirm open blockers and priority actions are visible.
3. Open **Recovery Loop → Exception Center**.
4. Confirm conflicts link to trip/vessel context.
5. Open **Simulation Workspace** and confirm scenario deltas are visible.

### UAT-03 — Approval, publish, and immutable plan

1. Resolve pilot blockers in the seeded data or use the regression test flow.
2. Open **Recovery Loop → Approvals & Publishing**.
3. Record Berau and ABL approval decisions.
4. Publish the plan.
5. Open **Operations → Published Plan & Schedule** and confirm the live snapshot is visible.
6. Confirm a direct override attempt on the published plan is rejected.

### UAT-04 — Governed handoff export

1. Sign in as `control.tower@coalflow.local`.
2. Open **Admin Console → Exports & Handoff**.
3. Generate the printable schedule export.
4. Confirm export history shows file name, record count, checksum, storage URI, and download link.
5. Sign in as `viewer@coalflow.local` and confirm export generation is not available.

### UAT-05 — Role regression

1. Sign in as each seeded non-admin user.
2. Confirm only permission-appropriate sidebar modules are visible.
3. Confirm direct API requests to forbidden modules return `403`.
4. Confirm frontend route hiding never substitutes for backend permission enforcement.

## 5. Backup rehearsal

Run the non-destructive backup rehearsal:

```powershell
powershell -ExecutionPolicy Bypass -File infra/scripts/backup-rehearsal.ps1
```

This creates a PostgreSQL custom-format dump, archives export artifacts from the shared export volume,
and validates the dump with `pg_restore -l` without replacing the current database.

Backups are written to `backups/` and should not be committed.

## 6. Local restore

Restore is destructive for the target local database and requires `-Force`:

```powershell
powershell -ExecutionPolicy Bypass -File infra/scripts/restore.ps1 `
  -DatabaseDump backups/coalflow-db-YYYYMMDD-HHMMSS.dump `
  -ExportArchive backups/coalflow-exports-YYYYMMDD-HHMMSS.tgz `
  -Force
```

Restart API/worker after restore if they were running.

## 7. Incident-safe logging

- Logs pass through a redaction filter for authorization, cookie, CSRF, password, secret, and token patterns.
- Do not log raw import rows, export payloads, session cookies, or credentials.
- Use audit events for governed business traceability; use logs for service operations.
- When diagnosing incidents, capture request ID, actor, action, object type/id, and safe counts rather than payload contents.

## 8. Pilot readiness acceptance

Chunk 8 is considered ready when:

- backend tests and frontend tests/build/lint pass through Docker;
- role regression remains green;
- backup rehearsal passes;
- `/api/health/` and `/api/ready/` return healthy status;
- a second engineer can follow this runbook from a clean checkout.
