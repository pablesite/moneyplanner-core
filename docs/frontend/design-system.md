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
2. Section shell: `ui-section-card`, `ui-section-card-padded`, `ui-section-head`, `ui-section-copy`, `ui-section-title`, `ui-section-subtitle`, `ui-section-actions`.
3. Surfaces: `ui-surface-muted`, `ui-surface-strong`.
4. State blocks: `ui-state-block`, `ui-state-empty`, `ui-state-error`, `ui-state-success`, `ui-state-loading`.
5. Controls: `btn`, `btn-primary`, `btn-ghost`, `btn-sm`, `icon-btn`, `input`, `textarea`.
6. Modal shell: `ui-modal-backdrop`, `ui-modal-panel`, `ui-modal-head`, `ui-modal-title`, `ui-modal-close`, `ui-modal-body`.

## Chart Token Palette
Chart.js renders to `<canvas>` and cannot use CSS `var()` directly. Tokens are read at render time via `getComputedStyle(document.documentElement).getPropertyValue(name).trim()` inside computed properties. Defined in `:root` in `app.css`:
- `--chart-tooltip-bg`, `--chart-series-stroke`, `--chart-series-fill`
- `--chart-positive-fill`, `--chart-positive-stroke`, `--chart-negative-fill`, `--chart-negative-stroke`
- `--chart-point-bg`, `--chart-point-hover-bg`, `--chart-point-current-bg`, `--chart-point-current-hover-bg`

Note: `withDefaults(defineProps<>(), {...})` is hoisted to module scope by the Vue compiler. Do not reference locally declared functions (e.g., `cssVar()`) in prop defaults — resolve tokens inside `computed()` instead.

## Migration Notes
1. The `ui-pro-*` compat layer has been fully removed. Use canonical `ui-page-*` / `ui-section-*` classes and the `badge` primitive.
2. New reusable UI must use semantic tokens directly, not raw color values or hardcoded `rgba()`.
3. New page-level CSS should be added only when the shared primitives cannot express the required layout.

## Migration Log
1. `HomeView` uses the canonical page/section shell and token-driven phase cards.
2. `AccountView`, `PeopleView`, `AuxDataView`, and `GuidePhaseDetailView` use the canonical page/section shell for their top-level layout.
3. Net Worth top-level layout, hero shell, timeline wrapper, and item lists use the canonical page/section shell while keeping their domain-specific `ui-nw-*` composition styles.
4. Budget dashboard hero, annual sections, annual entry cards, top-level error states, and monthly close step panels use the canonical section/state shell while keeping their domain-specific `ui-budget-*` composition styles.
5. Budget suggestion panels and monthly close step chips use semantic surface, border, text, focus, and accent tokens for their shared chrome.
6. Net Worth hero chrome, skeletons, category workspace surfaces, muted copy, neutral badges, KPI cards, filters, timeline shells, and modal range controls use semantic surface, border, text, and accent tokens.
7. Accounting hero notes, period controls, timeline shells, modal labels, floating filters, and date dropdown chrome use semantic surface, border, text, and muted tokens.
8. Accounting ledger groups, transaction rows, neutral deltas, modal form chrome, import review surfaces, segmented controls, unified tabs, and account catalog neutral states use semantic surface, border, text, focus, and accent tokens.
9. `BaseModal` uses the shared `ui-modal-*` shell and shared button classes instead of local Tailwind color utilities.
10. People members and ownership managers use the canonical section shell; the ownership split editor uses tokenized muted surface chrome instead of the legacy `card` class.
11. Guide/Coach phase header, inline phase actions, phase switcher, score cards, summary cards, context diagnostics, score meter tracks, and score badge borders use the canonical section shell and semantic tokens.
12. Guide/Coach home skeletons, phase progress rings, and phase-card neutral chrome use semantic surface, border, info, accent, and canvas tokens while keeping score-driven colors as data visualization.
13. Shared data tables, empty table rows, date-empty cells, and success alerts use semantic border, surface, text, and positive tokens instead of Tailwind `white/*` and emerald color utilities.
14. Auth login/register shell, card, labels, subtitle, footer, and auth links use semantic surface, border, text, accent, and shadow tokens.
15. Shared select controls and `ui-select-popover-*` menus use semantic surface, border, text, focus, and accent tokens for trigger, menu, hover, and active states.
16. Compatibility `card`, `badge`, `ui-pro-panel`, `ui-pro-chip`, and `ui-pro-divider` use semantic surface, border, text, and shadow tokens; Accounting hero now uses the canonical section shell.
17. Budget `dashboard.css` fully tokenized — ~120 hardcoded `rgba(255,255,255,x)` values replaced with semantic tokens (`--color-text*`, `--color-border*`, `--color-surface*`) and `color-mix()` for gradient stops with distinct opacity levels.
18. Net Worth `net-worth-view.css` fully tokenized — ~20 hardcoded rgba values replaced with semantic tokens.
19. `budget-annual-entries.css`, `guide-detail.css`, `guide-home.css`, `movements.css` cleaned — remaining `var(--muted)` / `var(--text)` aliases and hardcoded rgba values replaced with canonical tokens.
20. `ui-pro-*` compat layer fully removed from `app.css` — all selector aliases (`ui-pro-page`, `ui-pro-panel`, `ui-pro-header`, `ui-pro-title`, `ui-pro-kicker`, `ui-pro-toolbar`, `ui-pro-chip`, `ui-pro-divider`) deleted; `badge` extended with `display: inline-flex; align-items: center; gap: 6px` to cover chip layout; 4 consuming components updated.
21. Chart.js colors tokenized — `--chart-*` palette added to `:root`; `NetWorthDeltaChart.vue` and `NetWorthTimelineChart.vue` updated to read all colors via `cssVar()` / `getComputedStyle` at render time instead of hardcoded strings.

## Next Passes
1. Continue visual polish pass on the Accounting view: header (align with Net Worth) and body styles.
2. Coach financial navigation redesign: fluid integration between coach recommendations and product modules.
3. Validate the main screens visually after each polish pass.
