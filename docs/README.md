# Core Documentation

Canonical documentation for the open-source `MoneyPlanner Core` repository.

## Read First
1. `project-status.md` -> estado actual de funcionalidades y tareas en curso
2. `architecture/architecture.md` -> current Core architecture
2. `architecture/accounting-movements-architecture.md` -> canonical accounting movements architecture
3. `operations/dev-setup.md` -> local setup, validation, and troubleshooting
4. `roadmap/product-roadmap.md` -> product evolution roadmap by module
5. `roadmap/community-roadmap.md` -> high-level future areas and ideas (public-facing)
6. `roadmap/backend-refactor-roadmap.md` -> backend maintainability roadmap
7. `roadmap/terminados/accounting-category-budget-separation-roadmap.md` -> completed roadmap for the accounting/budget boundary (all 5 phases done)
8. `roadmap/frontend-refactor-roadmap.md` -> frontend maintainability roadmap
9. `roadmap/terminados/accounting-movements-roadmap.md` -> completed accounting movements rollout
9. `../CONTRIBUTING.md` -> contribution workflow
10. `../RELEASING.md` -> release process

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
   - active execution roadmaps
   - `terminados/` for completed roadmaps
4. `frontend/`
   - active frontend UX notes
5. `tasks/`
   - executable task specs by specialty
   - `terminados/` subfolders for completed task specs
6. `scoring/`
   - financial guide scoring models by phase

## Usage Rule
1. This directory is the canonical source for Core product and domain documentation.
2. SaaS documentation must reference Core docs instead of duplicating Core behavior.
3. If Core behavior, architecture, or operational flows change, update these docs first.
