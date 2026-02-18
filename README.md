# moneyplanner core

Open-source basic net-worth manager with Vue frontend and Django/DRF backend.

## Stack
1. Frontend: Vue 3 + Vite
2. Backend: Django + DRF + SimpleJWT
3. DB: PostgreSQL 16
4. Local infra: Docker Compose

## Requirements
1. Docker Desktop

## Quick Start (Docker)
1. Create `backend/.env` from `backend/.env.example`.
2. (Optional) Create root `.env` if you want to override `POSTGRES_*` in Docker.
3. Start all services:

```bash
docker compose up --build
```

Local endpoints:
1. Frontend: `http://localhost:5173`
2. Backend API: `http://localhost:8000`

## Backend Env Vars
Backend reads `backend/.env`. Minimal example:

```env
DJANGO_SECRET_KEY=dev-insecure-secret
DJANGO_DEBUG=1
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
CORS_ALLOWED_ORIGINS=http://localhost:5173

DB_NAME=core
DB_USER=core
DB_PASSWORD=core
DB_HOST=db
DB_PORT=5432

SEED_CREATE_ADMIN=1
SEED_ADMIN_USERNAME=admin
SEED_ADMIN_EMAIL=admin@example.com
SEED_ADMIN_PASSWORD=admin
SEED_FORCE_ADMIN_PASSWORD=0

FX_PIVOT=USD
```

## Seed Data
On Docker startup backend runs:
1. `python manage.py migrate`
2. `python manage.py seed`

Manual run:

```bash
docker compose exec backend python manage.py seed
```

## Migrations

```bash
docker compose exec backend python manage.py makemigrations
docker compose exec backend python manage.py migrate
```

## Core Scope (Current)
1. Authentication + user settings
2. Assets
3. Liabilities
4. Net-worth summary
5. Daily snapshots

Core no longer includes premium ownership/member domain.

## Release 0.2.0 - Migration Notes
This release removes premium domain entities from core:
1. Removed models: `FamilyMember`, `Ownership`, `OwnershipSplit`
2. Removed fields: `Asset.ownership`, `Liability.ownership`
3. Removed premium endpoints previously under `api/net-worth/*` for members/ownership

If you are upgrading an existing core deployment:
1. Backup your database before migrating.
2. Run migrations:

```bash
docker compose exec backend python manage.py migrate
```

3. Update clients to stop sending/reading ownership/member fields on core endpoints.
4. Move premium ownership data/workflows to SaaS extension before upgrade.

## Troubleshooting
1. API not responding: `docker compose logs -f backend`
2. CORS issues: verify `CORS_ALLOWED_ORIGINS` in `backend/.env`
3. Port conflicts: adjust ports in `docker-compose.yml`

## OSS Collaboration
1. Contribution guide: `CONTRIBUTING.md`
2. Release/versioning policy: `RELEASING.md`
