# Core Architecture

## Objective
Describe the current architecture of `MoneyPlanner Core` as a self-contained open-source product.

## Summary
1. Core owns the product domain and shared business behavior.
2. Core is designed to be useful on its own, without requiring the SaaS layer.
3. Core includes both backend and frontend for the main personal-finance product experience.

## Core Stack
1. `backend/`
   - Django + DRF
   - domain logic and product APIs
2. `frontend/`
   - Vue + Vite
   - Core product interface
3. PostgreSQL
4. Docker Compose for local development

## Product Scope
1. Net worth
2. Budget and monthly close
3. Accounting / daily movements
4. Data input
5. Financial guide v1
6. Family and ownership
7. Supporting product capabilities that belong to the Core domain baseline

## Architectural Rule
1. Shared product behavior belongs in Core.
2. Domain rules should live in backend domain layers, not in deployment-specific integrations.
3. Core documentation must remain self-contained and understandable without SaaS documentation.

## Internal Structure
1. Backend apps organize domain areas such as accounts, budget, net worth, accounting, memberships, and shared core services.
2. Frontend code is organized by product domains under `frontend/src/domains/*`, including domain-specific UI such as `accounting`.
3. Operational and functional documentation for the OSS product lives under `core/docs/`.

## Related Documents
1. `../../README.md`
2. `../../CONTRIBUTING.md`
3. `../../RELEASING.md`
4. `accounting-movements-architecture.md`
5. `../operations/dev-setup.md`
6. `../roadmap/community-roadmap.md`
7. `../roadmap/backend-refactor-roadmap.md`
