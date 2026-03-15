# Core Development Setup

## Objective
Describe how to run, validate, and troubleshoot `MoneyPlanner Core` locally.

## Local Startup
1. From `core/`, run `docker compose up --build -d`
2. Frontend: `http://localhost:5173`
3. Backend: `http://localhost:8000`

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

## Related Operational Docs
1. `fx-sync.md`
2. `portable-import.md`
