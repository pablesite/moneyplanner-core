# Net Worth UX

## Objective
Describe the current UX structure and interaction model of the `Patrimonio` view in Core.

## Current layout
1. The view starts with a hero section that combines:
   - a prominent donut summary
   - the main net-worth summary
   - top-level asset and liability totals
2. The timeline workspace sits directly below the hero.
3. Category exploration and position drilldown happen in the same visual workspace as the timeline.

## Hero behavior
1. The donut is part of the main header, not a secondary block.
2. The main summary prioritizes:
   - net worth
   - liquid coverage
   - equity ratio
   - total assets
   - total liabilities
3. The header also includes the ownership filter and settings controls.

## Ownership filter
1. The ownership filter lives in the header beside the main context controls.
2. In nominal mode it filters by person and prorates shared ownership.
3. In real/IPC mode the ownership filter is disabled.

## Composition and timeline
1. Category selection starts from the composition panel.
2. Clicking the active category again resets the view to the global net-worth series.
3. When no category is selected, the timeline shows the overall net-worth series.
4. When a category is selected, the workspace switches to that category context.
5. In real/IPC mode, composition totals and liquidity indicators use the same real aggregates as the top summary.

## Position drilldown
1. The contextual position selector only appears when a concrete category is selected.
2. Position drilldown stays in the same workspace as the timeline instead of forcing navigation away.
3. The category workspace also exposes direct creation actions for new assets or liabilities in that context.
4. The selected position can show its own timeline plus events and checkpoints.

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
   - `frontend/src/domains/net-worth/components/NetWorthSnapshotsSection.vue`
   - `frontend/src/domains/net-worth/components/NetWorthItemModals.vue`
4. La coordinación de ownership, métricas, timeline, layout y acciones vive en composables
   del dominio `net-worth`, manteniendo el comportamiento UX sin rediseño funcional.
