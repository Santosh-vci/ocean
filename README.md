# Coalflow Tower

Docker-first monorepo for the Berau–ABL transshipment scheduling and live planning platform.

## Foundation decisions

- **Frontend:** React + Vite + TypeScript
- **Backend:** Django + Django REST Framework
- **Database:** PostgreSQL with PostGIS
- **Async jobs:** Celery + Redis
- **Object storage:** MinIO
- **Edge routing:** Nginx
- **Local runtime:** Docker Compose

## Quick start

```bash
cp .env.example .env
docker compose up --build
```

PowerShell equivalent:

```powershell
Copy-Item .env.example .env
docker compose up --build
```

## Docker-only local policy

Do not run `npm install`, `npm ci`, `pip install`, or virtualenv setup in the workspace. Frontend and backend dependencies are installed by the Docker images from `frontend/package-lock.json` and `backend/requirements.txt`.

Run app, test, lint, and management commands through `docker compose`. Host-side dependency folders such as `node_modules/`, `.venv/`, `venv/`, `dist/`, and Python cache directories are ignored and disposable.

Then open:

- App shell: `http://localhost:8080`
- API health: `http://localhost:8080/api/health/`
- API readiness: `http://localhost:8080/api/ready/`
- Django admin: `http://localhost:8080/admin/`
- MinIO console: `http://localhost:9001`

Seeded local admin:

- email: `admin@coalflow.local`
- password: `admin12345`

Change these values in `.env` before using any shared environment.

## Useful commands

```bash
# backend
docker compose run --rm api python manage.py check
docker compose run --rm api pytest
docker compose run --rm api ruff check .

# frontend
docker compose run --rm frontend npm run test
docker compose run --rm frontend npm run lint

# pilot backup rehearsal
powershell -ExecutionPolicy Bypass -File infra/scripts/backup-rehearsal.ps1

# Phase 1 end-to-end proof run
docker compose run --rm -e RUN_STARTUP_TASKS=0 api python manage.py phase1_e2e_proof --json

# optional dev tools
docker compose --profile devtools up flower mailpit
```

## Current milestone

Product Phase 1 now has a repeatable completion proof:

- real Dockerized happy-path workflow from demand and cargo layers to manual windows, schedule generation, override, dual approval, publish, audit, and governed export;
- seeded constraint scenario proving tide, bridge, layer-sequence, barge, jetty, and compatibility blockers;
- completion evidence in `docs/12_Phase_1_Completion_Evidence.md` and `docs/evidence/phase1/phase1_e2e_evidence.json`;
- operator instructions in `docs/13_Phase_1_Operator_Manual.md`;
- governed RBAC/audit/export controls;
- observability endpoints for liveness, readiness, and admin-only safe metrics;
- persisted export artifact volume for local Docker runs;
- backup/restore rehearsal scripts;
- pilot runbook and API contract baseline under `docs/`.
