# Core Documentation

Canonical documentation for the open-source `MoneyPlanner Core` repository.

## Read First
1. `project-status.md` -> current feature status and active tasks
2. `architecture/architecture.md` -> current Core architecture
3. `architecture/accounting-movements-architecture.md` -> canonical accounting movements architecture
4. `operations/dev-setup.md` -> local setup, validation, and troubleshooting
5. `roadmap/product-roadmap.md` -> product evolution roadmap by module
6. `roadmap/community-roadmap.md` -> high-level public roadmap and future ideas
7. `roadmap/terminados/backend-refactor-roadmap.md` -> completed backend structural refactor roadmap
8. `roadmap/terminados/accounting-category-budget-separation-roadmap.md` -> completed accounting/budget boundary roadmap (all 5 phases done)
9. `roadmap/terminados/frontend-refactor-roadmap.md` -> completed frontend structural refactor roadmap
10. `roadmap/frontend-maintainability-backlog.md` -> frontend maintainability backlog
11. `roadmap/terminados/accounting-movements-roadmap.md` -> completed accounting movements rollout
12. `../CONTRIBUTING.md` -> contribution workflow
13. `../RELEASING.md` -> release process

## Active Documents
1. `architecture/`
   - Core architecture and internal product boundaries
2. `operations/`
   - local development and operational guides
   - market data sync
   - portable import
3. `roadmap/`
   - community roadmap
   - backend/frontend maintainability backlogs
   - active execution roadmaps
   - `terminados/` for completed roadmaps
4. `frontend/`
   - active frontend UX notes
   - Core design system foundation
5. `tasks/`
   - executable task specs by specialty
   - `terminados/` subfolders for completed task specs
6. `scoring/`
   - financial guide scoring models by phase

## Usage Rule
1. This directory is the canonical source for Core product and domain documentation.
2. SaaS documentation must reference Core docs instead of duplicating Core behavior.
3. If Core behavior, architecture, or operational flows change, update these docs first.
