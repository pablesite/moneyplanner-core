# Contributing to MoneyPlanner Core

Thank you for contributing to MoneyPlanner Core.

## Table of contents

1. [Prerequisites](#prerequisites)
2. [Local setup](#local-setup)
3. [Environment variables](#environment-variables)
4. [Running quality checks locally](#running-quality-checks-locally)
5. [Contribution workflow](#contribution-workflow)
6. [CI pipeline](#ci-pipeline)
7. [Self-hosted production setup](#self-hosted-production-setup)
8. [Commit style](#commit-style)
9. [Code of conduct](#code-of-conduct)

---

## Prerequisites

Only Docker and Docker Compose v2 are required. Everything else (Python, Node, PostgreSQL) runs
inside containers.

- Docker 24+ and Docker Compose v2 — verify with `docker compose version`
- Works on Linux, macOS, and Windows (WSL2)

> **Windows / WSL2**: if file-watching doesn't trigger hot-reloads, set
> `FRONTEND_USE_POLLING=true` in `docker-compose.override.yml`. See
> [docs/operations/dev-setup.md](docs/operations/dev-setup.md#windows--wsl) for details.

---

## Local setup

```bash
# 1. Copy the environment template
cp backend/.env.example backend/.env

# 2. Build and start all services
make setup   # copies .env if missing, builds images
make start   # starts in detached mode

# 3. Verify services are running
docker compose ps
```

After startup:
- Frontend: `http://localhost:5173`
- Backend API: `http://localhost:8000`
- A default admin user is created automatically — credentials are in `backend/.env` under
  `SEED_ADMIN_*` (default: `admin` / `admin`).

**`make` shortcuts:**

| Command | What it does |
|---|---|
| `make setup` | Copy `.env` template if missing, build images |
| `make start` | Start all services detached |
| `make stop` | Stop all services |
| `make logs` | Follow logs from all services |
| `make quality` | Run all quality checks (backend + frontend) |
| `make test-backend` | Django test suite |
| `make test-frontend` | Vitest unit tests |
| `make demo` | Seed a demo user with sample Spanish financial data |

---

## Environment variables

The file `backend/.env.example` documents every variable. Copy it to `backend/.env` before
starting. The defaults work for local development — you only need to change values for
production.

### Key variables

**Authentication & security**

| Variable | Dev default | Required in prod | Notes |
|---|---|---|---|
| `DJANGO_SECRET_KEY` | insecure dev key | Yes — generate 50+ char random string | `python -c "import secrets; print(secrets.token_urlsafe(50))"` |
| `JWT_SIGNING_KEY` | insecure dev key | Yes — independent of `SECRET_KEY` | Same generation command |
| `DJANGO_DEBUG` | `1` | Must be `0` | Exposes stack traces when `1` |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Your domain(s) | Comma-separated |
| `CORS_ALLOWED_ORIGINS` | `http://localhost:5173` | Your frontend origin | Comma-separated |

**Database**

| Variable | Dev default | Notes |
|---|---|---|
| `DB_NAME` | `core` | Matches `POSTGRES_DB` in `docker-compose.yml` |
| `DB_USER` | `core` | Matches `POSTGRES_USER` |
| `DB_PASSWORD` | `core` | Use a strong password in prod |
| `DB_HOST` | `db` | Docker service name — do not change for Docker setups |
| `DB_PORT` | `5432` | |

**Admin seed user** (created on first `docker compose up`)

| Variable | Dev default | Notes |
|---|---|---|
| `SEED_CREATE_ADMIN` | `1` | Set to `0` to disable auto-creation |
| `SEED_ADMIN_USERNAME` | `admin` | |
| `SEED_ADMIN_EMAIL` | `admin@example.com` | |
| `SEED_ADMIN_PASSWORD` | `admin` | Change before exposing to the internet |

**Market data sync**

| Variable | Default | Notes |
|---|---|---|
| `FX_SYNC_ENABLED` | `1` | Set to `0` to disable the background FX/IPC sync |
| `FX_SYNC_QUOTE_CURRENCY` | `EUR` | Your base currency for net-worth calculations |
| `FX_SYNC_INTERVAL_SECONDS` | `86400` | Sync cadence in seconds (default: daily) |

**Advanced / optional** (leave at defaults for community use)

| Variable | Default | Notes |
|---|---|---|
| `AUTH_ACCEPT_EXTERNAL_TOKENS` | `0` | Leave `0` unless integrating with an external auth issuer |
| `BROKER_ENCRYPTION_KEY` | empty | Required only if using broker integrations (Pionex, Binance) |

**Frontend** (optional — `frontend/.env`)

The frontend has a single optional variable:

```
VITE_API_BASE_URL=http://localhost:8000
```

If not set, relative URLs are used (correct for production behind a reverse proxy). Only needed
locally if the backend is on a non-default port.

---

## Running quality checks locally

Run all checks before opening a PR — CI will run the same commands.

```bash
make quality        # lint + typecheck for backend and frontend
make test-backend   # Django test suite
make test-frontend  # Vitest unit tests with coverage
```

Or individually:

```bash
# Backend
docker compose exec backend ruff check .
docker compose exec backend ruff format --check .
docker compose exec backend mypy .
docker compose exec backend python manage.py test accounts budget memberships net_worth core

# Frontend
docker compose exec frontend npm run lint
docker compose exec frontend npm run format:check
docker compose exec frontend npm run typecheck
docker compose exec frontend npm run test:unit
```

---

## Contribution workflow

```
fork → feature branch → commits → open PR to main → CI passes → review → merge
```

1. **Fork** the repository on GitHub.
2. **Create a branch** from `main` with a short descriptive name:
   ```bash
   git checkout -b feat/my-feature
   ```
3. **Make focused commits** following [Conventional Commits](#commit-style).
4. **Run quality checks** locally (`make quality && make test-backend && make test-frontend`).
5. **Open a PR** targeting `main`. Fill in the PR description with what changed and why.
6. **CI runs automatically** — all four required checks must be green before merging.
7. After approval and passing CI, the PR is merged by a maintainer (or you, if you have write
   access).

> There is no `develop` branch. All contributions go directly to `main` via PR.

---

## CI pipeline

Three workflow files run automatically:

### `quality-core.yml` — runs on every PR and on push to `main`

Four jobs, all **required** to merge:

| Job | What it does | Fails if |
|---|---|---|
| **Secret scan** | Gitleaks scans the full git history for accidentally committed secrets | Any secret pattern found |
| **Dependency audit** | `pip-audit` (any CVE) + `npm audit` (HIGH/CRITICAL, production deps only) | Any CVE in backend deps; HIGH+ CVE in frontend production deps |
| **backend** | Ruff lint, Ruff format, Mypy, Django tests with coverage | Lint/type error; coverage < 50% |
| **frontend** | ESLint, Prettier, TypeScript check, Vitest with coverage | Lint/type error; coverage < 80% lines (branches ≥ 72%) |

### `codeql.yml` — runs on PRs and weekly cron (Mondays 03:00 UTC)

Static analysis (SAST) for Python and TypeScript/JavaScript using GitHub CodeQL.
Results appear in **GitHub → Security → Code scanning**. This job is **informational** — it does
not block merging. Review findings before shipping to production.

### `ci-main.yml` — runs on push to `main` only

Triggered after merge. Builds Docker images, scans them with Trivy (CRITICAL/HIGH CVEs,
`ignore-unfixed: true`), pushes to GitHub Container Registry, and runs
[Release Please](https://github.com/googleapis/release-please) to manage versioning.

> **`ignore-unfixed: true`**: Trivy skips CVEs that have no upstream patch yet. This prevents the
> pipeline from being blocked by OS-level CVEs in the base image that nobody can fix. See
> [docs/security/ci-security-decisions.md](docs/security/ci-security-decisions.md) for the full
> rationale.

### Running CI checks locally before pushing

```bash
# Equivalent to the Secret scan job
docker run --rm -v "$(pwd):/path" zricethezav/gitleaks:latest detect --source=/path

# Equivalent to the Dependency audit job
pip-audit -r backend/requirements.txt
cd frontend && npm audit --omit=dev --audit-level=high

# Equivalent to the backend job
make lint-backend && make test-backend

# Equivalent to the frontend job
make lint-frontend && make test-frontend
```

---

## Self-hosted production setup

Use `docker-compose.prod.yml` to self-host MoneyPlanner Core:

```bash
# 1. Create a .env.prod file with required secrets
cat > .env.prod << 'EOF'
POSTGRES_PASSWORD=<strong-random-password>
DJANGO_SECRET_KEY=<50-char-random-string>
JWT_SIGNING_KEY=<50-char-random-string>
DJANGO_ALLOWED_HOSTS=yourdomain.com
CORS_ALLOWED_ORIGINS=https://yourdomain.com
EOF

# 2. Generate strong secrets
python -c "import secrets; print(secrets.token_urlsafe(50))"

# 3. Start
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

The production stack:
- **backend** — Django + Gunicorn + Whitenoise (serves `/api/` and `/admin/`)
- **frontend** — Nginx serving the built Vue SPA, proxying `/api/` and `/admin/` to backend
- **db** — PostgreSQL 16
- **market_data_sync** — background FX/IPC sync worker

> Store your `.env.prod` file outside the repository and never commit it.

---

## Commit style

This project uses [Conventional Commits](https://www.conventionalcommits.org/) and
[Release Please](https://github.com/googleapis/release-please) for automated versioning:

| Prefix | Release effect |
|---|---|
| `fix:` | PATCH bump |
| `feat:` | MINOR bump |
| `feat!:` / `BREAKING CHANGE:` | MAJOR bump |
| `chore:`, `docs:`, `refactor:`, `test:` | No release |

Scope is optional but encouraged: `feat(net-worth): add timeline chart`.

---

## PR checklist

- [ ] Small, coherent scope — one feature or fix per PR.
- [ ] All four required CI checks pass.
- [ ] Tests added or updated for changed behaviour.
- [ ] Commits follow Conventional Commits format.
- [ ] Documentation updated if the change affects public behaviour.

---

## Code of conduct

Please read [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) before participating.

---

*Para contribuidores hispanohablantes: este fichero está en inglés para facilitar la participación
internacional. No dudes en abrir un issue si algo no está claro.*
