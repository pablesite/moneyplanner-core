# Releasing moneyplanner-core

## Versioning Policy
- Use semantic versioning: `MAJOR.MINOR.PATCH`.
- `MAJOR`: breaking API/behavior changes.
- `MINOR`: backward-compatible features.
- `PATCH`: backward-compatible fixes/docs/tests.
- Canonical in-repo version is stored in `VERSION`.
- Public release version is the Git tag `vX.Y.Z`.

## Release Process
1. Merge normal feature/fix PRs into `main` only after the local quality matrix passes.
2. Quality and security checks run through `.github/workflows/quality-core.yml` and related workflows.
3. On every push to `main`, `.github/workflows/release-please.yml` runs `release-please`.
4. `release-please` opens or updates a release PR. That PR is the only place where release metadata is changed:
   - `VERSION`
   - `.release-please-manifest.json`
   - `CHANGELOG.md`
   - `frontend/package.json`
   - `frontend/package-lock.json`
5. Review and merge the release PR when ready to publish. Do not edit version files manually in feature/fix PRs.
6. After the release PR is merged, `release-please` creates the GitHub release and tag.

## Image Publishing Policy
- Core keeps community-facing quality, security, and semantic versioning workflows.
- Core does not publish production Docker images automatically on every `push` to `main`.
- Standalone Core images can be published manually from `./core` via `.github/workflows/publish-images.yml`.
- Private production image build and deploy for the integrated SaaS stack remain orchestrated from the root `moneyplanner-saas` repository, using the submodule commit pinned there.

## Manual Image Publishing
1. Open GitHub Actions in the `moneyplanner-core` repository.
2. Run `Publish Core Images`.
3. Provide the tag you want to publish, for example `v1.4.0` or `latest`.
4. The workflow builds:
   - `ghcr.io/pablesite/moneyplanner-core-backend:<tag>`
   - `ghcr.io/pablesite/moneyplanner-core-frontend:<tag>`
5. Each image is scanned with Trivy before push. High or critical findings fail the run.

## Local Quality Matrix
   - `docker compose exec backend ruff check .`
   - `docker compose exec backend ruff format --check .`
   - `docker compose exec backend mypy .`
   - `docker compose exec backend python manage.py test accounts budget memberships net_worth core`
   - `docker compose exec frontend npm run lint`
   - `docker compose exec frontend npm run format:check`
   - `docker compose exec frontend npm run typecheck`
   - `docker compose exec frontend npm run test:unit`

## Breaking Changes Checklist
- Document migration steps clearly.
- Keep API contract notes updated.
- Mention removed or renamed fields and endpoints.
