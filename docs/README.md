# Core Documentation

Canonical documentation for the open-source `MoneyPlanner Core` repository.

## Read First
1. `architecture/architecture.md` -> current Core architecture
2. `architecture/accounting-movements-architecture.md` -> canonical accounting movements architecture
3. `operations/dev-setup.md` -> local setup, validation, and troubleshooting
4. `roadmap/community-roadmap.md` -> current Core priorities
5. `roadmap/backend-refactor-roadmap.md` -> backend maintainability roadmap
6. `roadmap/accounting-movements-roadmap.md` -> executable roadmap for accounting movements
7. `../CONTRIBUTING.md` -> contribution workflow
8. `../RELEASING.md` -> release process

## Active Documents
1. `architecture/`
   - Core architecture and internal product boundaries
2. `operations/`
   - local development and operational guides
   - market data sync
   - portable import
3. `roadmap/`
   - community roadmap
   - backend refactor roadmap
4. `frontend/`
   - active frontend UX notes
5. `tasks/`
   - executable task specs by specialty
6. `scoring/`
   - financial guide scoring models by phase

## Usage Rule
1. This directory is the canonical source for Core product and domain documentation.
2. SaaS documentation must reference Core docs instead of duplicating Core behavior.
3. If Core behavior, architecture, or operational flows change, update these docs first.
