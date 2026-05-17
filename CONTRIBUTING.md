# Contributing to MoneyPlanner Core

Thank you for contributing to MoneyPlanner Core.

## Recommended workflow
1. Fork the repository and create a branch from `main`.
2. Make a small, focused change.
3. Run quality checks inside Docker (see below).
4. Open a PR with a clear scope and documented changes.

## Local setup
1. Copy the environment template: `cp backend/.env.example backend/.env`
2. Start all services: `docker compose up --build -d`
3. Verify services are running: `docker compose ps`

Frontend is available at `http://localhost:5173`, backend at `http://localhost:8000`.

## Backend guidelines
1. Follow the `views → serializers → services` flow.
2. Business logic belongs in `services.py`.
3. Update tests when behaviour changes.
4. Minimum validation before pushing:
   ```bash
   docker compose exec backend ruff check .
   docker compose exec backend ruff format --check .
   docker compose exec backend mypy .
   docker compose exec backend python manage.py test accounts budget memberships net_worth core
   ```

## Frontend guidelines
1. Organise code by domain under `frontend/src/domains/*`.
2. Keep views declarative; business logic lives in composables or domain services.
3. Reuse shared components and styles.
4. Minimum validation before pushing:
   ```bash
   docker compose exec frontend npm run lint
   docker compose exec frontend npm run format:check
   docker compose exec frontend npm run typecheck
   docker compose exec frontend npm run test:unit
   ```

## PR checklist
- [ ] Small, coherent scope.
- [ ] Quality checks passed inside Docker.
- [ ] Tests and documentation updated where applicable.
- [ ] Commits follow [Conventional Commits](https://www.conventionalcommits.org/).

## Optional: pre-commit hooks

You can run quality checks automatically before every commit using [pre-commit](https://pre-commit.com/):

```bash
pip install pre-commit
pre-commit install
```

This requires Python to be available locally. Alternatively, run the checks manually inside Docker before pushing (see Backend / Frontend guidelines above) — that is the authoritative path used in CI.

## Commit style
This project uses [Conventional Commits](https://www.conventionalcommits.org/) and
[release-please](https://github.com/googleapis/release-please) for automated versioning:

| Prefix | Effect |
|--------|--------|
| `fix:` | PATCH bump |
| `feat:` | MINOR bump |
| `feat!:` / `BREAKING CHANGE:` | MAJOR bump |
| `chore:`, `docs:`, `refactor:` | No release |

## Code of conduct
Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before participating.

---

*Para contribuidores hispanohablantes: este fichero está en inglés para facilitar la participación internacional. No dudes en abrir un issue o PR si algo no está claro.*
