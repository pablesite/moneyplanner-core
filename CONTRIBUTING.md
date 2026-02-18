# Contributing To moneyplanner

Thanks for contributing to `moneyplanner`.

## Local Setup
1. Copy env file:
   - `cp backend/.env.example backend/.env`
2. Start services:
   - `docker compose up --build -d`

## Quality Checks (Required)
Run checks inside Docker:
1. Backend:
   - `docker compose exec backend ruff check .`
   - `docker compose exec backend ruff format --check .`
   - `docker compose exec backend mypy .`
   - `docker compose exec backend python manage.py test accounts net_worth core`
2. Frontend:
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`
   - `docker compose exec frontend npm run test:unit`

## Pull Request Guidelines
1. Keep changes focused and small.
2. Follow existing architecture patterns (`views -> serializers -> services` in backend).
3. Add or update tests for behavior changes.
4. Update docs when behavior/contracts change.
5. Use Conventional Commits.

## Frontend Guidelines
1. Organize code by domain under `frontend/src/domains/*`.
2. Keep views declarative:
   - put orchestration in composables/stores,
   - keep API calls in domain adapters.
3. Reuse shared UI primitives and style tokens:
   - `src/styles/app.css`
   - `src/styles/tailwind.css`
4. Avoid duplicated scoped styles when a shared class already exists.
5. For behavior changes, include or update tests in:
   - `frontend/src/**/__tests__`
   - component specs for critical UI flows.
6. Validate frontend quality before PR:
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`
   - `docker compose exec frontend npm run test:unit`

## Commit Conventions
Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):
- `feat: ...`
- `fix: ...`
- `docs: ...`
- `test: ...`
- `refactor: ...`
- `chore: ...`
