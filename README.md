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

Then open:

- App shell: `http://localhost:8080`
- API health: `http://localhost:8080/api/health/`
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

# optional dev tools
docker compose --profile devtools up flower mailpit
```

## Current milestone

Chunk 0 is the execution spine only:

- container topology;
- backend/frontend bootstraps;
- database migrations on startup;
- seed command skeleton;
- health endpoints;
- lint/test commands;
- CI workflow.

Domain implementation begins in Chunk 1.
