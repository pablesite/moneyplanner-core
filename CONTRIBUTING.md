# Contributing To moneyplanner

Thanks for contributing to `moneyplanner`.

## Contribution Flow
1. Create a branch from `main`.
2. Keep the change focused on one concern.
3. Run required quality checks in Docker.
4. Open a PR with clear scope, tests, and docs updates.

## Local Setup
1. Copy env file:
   - `cp backend/.env.example backend/.env`
2. Start services:
   - `docker compose up --build -d`

## Backend Guidelines
1. Follow the service-oriented backend flow: `views -> serializers -> services`.
2. Keep business rules in `services.py`, not in views.
3. Keep serializers focused on validation/shape, not orchestration.
4. Add or update backend tests when behavior changes.
5. Validate backend before PR:
   - `docker compose exec backend ruff check .`
   - `docker compose exec backend ruff format --check .`
   - `docker compose exec backend mypy .`
   - `docker compose exec backend python manage.py test accounts net_worth core`

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
6. Validate frontend before PR:
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`
   - `docker compose exec frontend npm run test:unit`

## Pull Request Checklist
1. Scope is small and technically coherent.
2. Backend/frontend checks pass in Docker.
3. Tests are added/updated for behavior changes.
4. Docs are updated when contracts/behavior changed.
5. Commit messages follow Conventional Commits.

## Commit Conventions
Use [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/):
- `feat: ...`
- `fix: ...`
- `docs: ...`
- `test: ...`
- `refactor: ...`
- `chore: ...`
