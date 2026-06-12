# Core Development Setup

This document covers the standalone Core development workflow for contributors working directly
inside `./core`.

If you are developing from the integrated `moneyplanner-saas` root repo and want to run SaaS and
Core together, use `../../docs/operations/dev-setup.md` instead.

## Objective
Describe how to run, validate, and troubleshoot `MoneyPlanner Core` locally.

## Local Startup
1. From `core/`, run `docker compose up --build -d`
2. Verify `backend`, `frontend`, `db`, and `market_data_sync` are `Up` with `docker compose ps`
3. Frontend: `http://localhost:5173`
4. Backend: `http://localhost:8000`

The frontend points to `http://localhost:8000` by default, so a clean Core clone does not need
`frontend/.env`. If you run the Core backend on a different URL, set only
`VITE_API_BASE_URL` in `frontend/.env`. `VITE_CORE_API_BASE_URL` is an optional override for
hybrid deployments where Core API traffic must use a different backend than the default API URL.

Local startup creates an admin user from `SEED_ADMIN_*` and loads demo data by default.
Use `demo` / `demo1234demo` to explore the app with sample data. Set `SEED_CREATE_DEMO=0`
in `backend/.env` to skip demo data in a new local database.

`market_data_sync` is part of the standard Core startup. It reconciles and refreshes persisted
market datasets (`FX` and `IPC`) used by net worth calculations and the `/data` observability view.

## Standard Diagnostics
1. `docker compose ps`
2. `docker compose logs --tail 100 <service>`
3. Optional deeper diagnostics:
   - `docker compose ps -a`
   - `docker compose logs --tail 200 <service>`

## Safe Operation
1. Do not remove database volumes unless explicitly required.
2. Do not run `docker compose down -v` unless you intentionally want to destroy local data.
3. Run quality checks and tests inside Docker.

## Quality Checks
### Backend
```bash
docker compose exec backend ruff check .
docker compose exec backend ruff format --check .
docker compose exec backend mypy .
```

### Frontend
```bash
docker compose exec frontend npm run lint
docker compose exec frontend npm run format:check
docker compose exec frontend npm run typecheck
```

## Tests
Run the relevant domain tests for the change you made.

Examples:
```bash
docker compose exec backend python manage.py test accounts
docker compose exec backend python manage.py test budget
docker compose exec backend python manage.py test memberships
docker compose exec backend python manage.py test net_worth
docker compose exec backend python manage.py test core
docker compose exec frontend npm run test:unit
```

## Troubleshooting
### Django test DB fails with duplicate constraint names
Symptom examples during `python manage.py test`:
- `relation "uniq_member_name_per_user" already exists`
- `relation "ownership_individual_requires_member" already exists`
- `relation "uniq_split_member_per_ownership" already exists`

Root cause:
1. Historical migrations created legacy `FamilyMember/Ownership` constraints in `net_worth`.
2. The same constraint names were reused later in `memberships`.
3. PostgreSQL constraint names are global enough to collide during clean test DB bootstrap.

Fix implemented:
1. `memberships` constraints were renamed to unique names:
   - `uniq_member_name_per_user_memberships`
   - `ownership_individual_requires_member_memberships`
   - `uniq_split_member_per_ownership_memberships`
2. A compatibility migration renames existing constraints in already-migrated databases:
   - `backend/memberships/migrations/0005_rename_familymember_unique_constraint.py`

Files involved:
1. `backend/memberships/models.py`
2. `backend/memberships/migrations/0001_initial.py`
3. `backend/memberships/migrations/0002_remove_ownership_ownership_individual_requires_member_and_more.py`
4. `backend/memberships/migrations/0005_rename_familymember_unique_constraint.py`

Validation commands:
```bash
docker compose exec backend python manage.py migrate memberships
docker compose exec backend python manage.py test budget accounting --keepdb
```

## Windows / WSL

If file changes in the frontend container are not triggering hot-reload:

1. Copy `.env.example` to `.env` in the project root (next to `docker-compose.yml`) and uncomment:
   ```
   FRONTEND_USE_POLLING=true
   FRONTEND_POLLING_INTERVAL=500
   ```
2. Restart the frontend service:
   ```bash
   docker compose restart frontend
   ```

This is needed because WSL2 does not propagate inotify events from the Windows filesystem into Linux containers.

## Common Issues

### Port 5432 already in use
PostgreSQL is running locally on the same port. Options:
1. Stop the local Postgres: `sudo systemctl stop postgresql` (Linux) or stop the service via Docker Desktop.
2. Or remap the port in `docker-compose.yml` under the `db` service (`"5433:5432"`).

### Frontend doesn't reload changes (non-WSL)
Ensure Docker has access to the source directory. On macOS, check Docker Desktop → Settings → File Sharing.

### How to reset the database
Only do this if you intentionally want to destroy local data:
```bash
docker compose down -v   # removes volumes
docker compose up --build -d
```

### Viewing logs for a specific service
```bash
docker compose logs -f backend
docker compose logs -f frontend
docker compose logs -f market_data_sync
```

## Related Operational Docs
1. `market-data-sync.md`
2. `portable-import.md`
