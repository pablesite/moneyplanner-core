# MoneyPlanner Core

Open-source personal finance app foundation for MoneyPlanner.

## What It Is
1. A self-contained product for personal finance management.
2. The open-core base that evolves independently.
3. A repository intended to be useful on its own and open to community contributions.

## Current Scope
1. Net worth
2. Budget and monthly close
3. Data input
4. Financial guide v1
5. Family and ownership
6. Daily accounting movements with monthly-close coexistence

## Stack
1. `backend/` Django + DRF
2. `frontend/` Vue + Vite
3. PostgreSQL
4. Docker Compose

## Prerequisites
- Docker 24+ and Docker Compose v2 (`docker compose version`)
- No other local dependencies required — everything runs inside containers.

Works on Linux, macOS, and Windows (WSL2). See [Windows / WSL notes](docs/operations/dev-setup.md#windows--wsl) if file-watching doesn't work.

## Quick Start

> **Windows:** clone this repo inside the WSL2 filesystem (e.g. `~/projects/`) so that hot-reload works without extra config. If you clone under `C:\...`, copy `.env.example` to `.env` and uncomment `FRONTEND_USE_POLLING=true` before step 2.

1. Copy the environment template:
   - Linux / macOS / WSL: `cp backend/.env.example backend/.env`
   - Windows CMD: `copy backend\.env.example backend\.env`
2. Start all services: `docker compose up --build -d`
3. Verify all services are `Up`: `docker compose ps`
4. Frontend: `http://localhost:5173`
5. Backend: `http://localhost:8000`

A default admin user is created automatically (credentials in `backend/.env` → `SEED_ADMIN_*`).

## Documentation
1. `docs/README.md` — documentation index and reading order
2. `docs/operations/dev-setup.md` — setup, quality checks, tests, troubleshooting
3. `CONTRIBUTING.md` — how to contribute
4. `RELEASING.md` — release process

## License
This project is licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**.

Key implication: if you modify MoneyPlanner Core and run it as a network service, you must make your modified source code available under the same license. See [`LICENSE`](LICENSE) for the full text.

## Community
- [Contributing](CONTRIBUTING.md)
- [Code of Conduct](CODE_OF_CONDUCT.md)
- [Security Policy](SECURITY.md)
- [Community Roadmap](docs/roadmap/community-roadmap.md)

## Goal
1. Ship a useful open-source base now.
2. Improve product quality and UX with real feedback.
3. Make contribution paths small, clear, and safe.
