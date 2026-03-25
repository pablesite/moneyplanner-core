# Net Worth UX

## Objective
Describe the current UX structure and interaction model of the `Patrimonio` view in Core.

## Current layout
1. The view starts with a hero section that combines:
   - a donut by asset category (up to 5 slices + one red slice for liabilities)
   - the main net-worth summary (net worth value, delta indicator, KPI metrics)
   - asset and liability totals in side stat cards
2. The timeline workspace sits directly below the hero in a second card.
3. Category exploration and position drilldown happen in the same visual workspace as the timeline.

## Hero layout (post-redesign)
1. The hero is a single outer card (`ui-nw-hero-shell`). There are no inner cards — donut and summary live directly on the card surface.
2. Layout: two-column grid (donut column 300 px wide, summary fills remaining space), separated by a subtle vertical line.
3. On ≤1024 px the separator switches to horizontal and the donut legend collapses below the chart.
4. The topbar ("PATRIMONIO" kicker + refresh button) is fused into the same card row above the hero grid, eliminating dead vertical space.
5. The settings popover (gear icon) lives in the summary head alongside the ownership selector — not in the topbar.

## Donut (NetWorthDonut.vue)
1. Shows slices per asset category (up to 5, ordered by value) + one red slice for liabilities.
2. Color palette per category:
   - Liquidez → sky blue
   - Inversiones → teal
   - Inmuebles → amber
   - Bienes/mobiliario → violet
   - Otros → green
   - Pasivos → red
3. Tooltip shows value + percentage over total assets (same criterion as the user's Excel).
4. Legend is displayed to the right of the donut (flex row) inside the hero, saving vertical height.
5. Falls back to equity/backed/unbacked mode if no category data is available.

## Summary section
1. The main summary prioritizes:
   - net worth (large value)
   - monthly delta indicator (absolute + %) immediately below the value
   - liquid coverage (KPI metric)
   - equity ratio (KPI metric)
   - total assets (stat card)
   - total liabilities (stat card)
2. The "Balance actual" badge sits at the top of the summary head.
3. The ownership filter and settings gear are grouped in the summary head controls.

## Monthly delta indicator
1. Appears below the main net-worth value when the global timeline is active (no category selected).
2. Shows the change between the last two monthly timeline points:
   - Format: `+29.998 € este mes (+13,4%)`
   - Green badge when positive, red badge when negative.
3. Hidden when a category is selected (timeline reflects category, not global net worth).
4. Hidden when there are fewer than two timeline data points.

## Ownership filter
1. The ownership filter lives in the summary head beside the settings gear.
2. In nominal mode it filters by person and prorates shared ownership.
3. In real/IPC mode the ownership filter is disabled.

## Composition and timeline
1. Category selection starts from the composition panel in the timeline sidebar.
2. Clicking the active category again resets the view to the global net-worth series.
3. When no category is selected, the timeline shows the overall net-worth series.
4. When a category is selected, the workspace switches to that category context.
5. In real/IPC mode, composition totals and liquidity indicators use the same real aggregates as the top summary.

## Position drilldown
1. The contextual position selector only appears when a concrete category is selected.
2. Position drilldown stays in the same workspace as the timeline instead of forcing navigation away.
3. The category workspace also exposes direct creation actions for new assets or liabilities in that context.
4. The selected position can show its own timeline plus events and checkpoints.

## Liability form (loan grace period)
1. Liability creation/edit now separates:
   - `Fecha contratación préstamo` (`start_date`)
   - `Fecha inicio pago` (`payment_start_date`, optional)
2. When `payment_start_date` is set, the installment schedule is anchored to that date.
3. When `payment_start_date` is empty, legacy behavior is preserved (first installment one period after `start_date`).

## UX principles of the current view
1. Keep the main financial picture visible at the top.
2. Let the user move from summary to category to position without losing context.
3. Treat composition as an operational panel, not just a passive chart.
4. Preserve a strong desktop hierarchy while keeping the layout clean on mobile.

## Related implementation
1. `frontend/src/views/NetWorthView.vue`
2. `frontend/src/domains/net-worth/components/NetWorthDonut.vue`
3. La vista ahora actúa como orquestador ligero y delega bloques principales en:
   - `frontend/src/domains/net-worth/components/NetWorthHeroSection.vue`
   - `frontend/src/domains/net-worth/components/NetWorthTimelineMain.vue`
   - `frontend/src/domains/net-worth/components/NetWorthCategoryWorkspace.vue`
   - `frontend/src/domains/net-worth/components/NetWorthItemModals.vue`
4. La coordinación de ownership, métricas, timeline, layout y acciones vive en composables
   del dominio `net-worth`, manteniendo el comportamiento UX sin rediseño funcional.
5. El cálculo del delta mensual (`monthlyDelta`) se hace en `NetWorthView.vue` a partir de
   los dos últimos puntos de `timelineRows`, y se pasa como prop a `NetWorthHeroSection`.
