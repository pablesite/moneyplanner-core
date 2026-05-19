# Core Design System

## Objective
Define the Core visual foundation used by the MoneyPlanner product UI before screen-by-screen polish.

## Canonical Source
1. Tokens and shared classes live in `core/frontend/src/styles/app.css`.
2. The shared visual contract is documented in `../../docs/frontend/frontend-visual-contract.md`.
3. Core owns the base product experience; SaaS should only mirror these styles when the task scope includes SaaS.

## Visual Direction
1. Calm, financially credible, and operational rather than decorative.
2. Clear hierarchy through spacing, type weight, and surface grouping.
3. Restrained dark surfaces with teal as the primary product accent and amber reserved for secondary emphasis.
4. Reusable primitives before local page CSS.

## Token Families
1. Colors:
   - `--color-canvas`, `--color-canvas-subtle`
   - `--color-surface`, `--color-surface-muted`, `--color-surface-strong`
   - `--color-border`, `--color-border-strong`
   - `--color-text`, `--color-text-muted`, `--color-text-soft`
   - `--color-accent`, `--color-accent-muted`, `--color-accent-alt`
   - `--color-positive`, `--color-negative`, `--color-info`, `--color-warning`
2. Layout:
   - `--container-max`
   - `--space-2`, `--space-3`, `--space-4`, `--space-6`, `--space-8`
3. Shape and depth:
   - `--radius-sm`, `--radius-md`, `--radius-lg`
   - `--shadow-surface`, `--shadow-surface-soft`

## Shared Classes
1. Page shell: `ui-page-shell`, `ui-page-head`, `ui-page-eyebrow`, `ui-page-title`, `ui-page-lead`, `ui-page-actions`.
2. Section shell: `ui-section-card`, `ui-section-head`, `ui-section-copy`, `ui-section-title`, `ui-section-subtitle`, `ui-section-actions`.
3. Surfaces: `ui-surface-muted`, `ui-surface-strong`.
4. State blocks: `ui-state-block`, `ui-state-empty`, `ui-state-error`, `ui-state-success`, `ui-state-loading`.
5. Controls: `btn`, `btn-primary`, `btn-ghost`, `btn-sm`, `icon-btn`, `input`, `textarea`.

## Migration Notes
1. Existing `card` and `ui-pro-*` classes are compatibility classes while views migrate to the shared contract.
2. New reusable UI should use semantic tokens directly, not raw color values.
3. New page-level CSS should be added only when the shared primitives cannot express the required layout.

## Next Passes
1. Migrate the most visible Core views to the canonical `ui-page-*` and `ui-section-*` naming.
2. Review view-specific CSS for raw colors, large radius values, and repeated control styles.
3. Validate the main screens visually after each migration pass.
