# Releasing moneyplanner-core

## Versioning Policy
- Use semantic versioning: `MAJOR.MINOR.PATCH`.
- `MAJOR`: breaking API/behavior changes.
- `MINOR`: backward-compatible features.
- `PATCH`: backward-compatible fixes/docs/tests.
- Canonical in-repo version is stored in `VERSION`.
- Public release version is the Git tag `vX.Y.Z`.

## Release Process
1. Ensure `main` is green in CI if the mirror or repo has CI configured.
2. Run local quality matrix in Docker:
   - `docker compose exec backend ruff check .`
   - `docker compose exec backend ruff format --check .`
   - `docker compose exec backend mypy .`
   - `docker compose exec backend python manage.py test accounts budget memberships net_worth core`
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`
   - `docker compose exec frontend npm run test:unit`
3. Update release notes in `README.md` and docs when needed.
4. Update `VERSION` with `X.Y.Z`.
5. Create and push tag:
   - `git tag vX.Y.Z`
   - `git push origin main --tags`
6. Publish GitHub release from tag with a short changelog.

## Breaking Changes Checklist
- Document migration steps clearly.
- Keep API contract notes updated.
- Mention removed or renamed fields and endpoints.
