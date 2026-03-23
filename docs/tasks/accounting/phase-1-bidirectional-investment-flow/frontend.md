# Title
Core accounting frontend - phase 1: bidirectional investment flow

## Context
The current UI exposes investment movements as a purchase-oriented flow, which makes manual withdrawals or investment exits conceptually awkward and pushes users toward transfers or misclassified income edits. This phase documents the frontend changes needed to expose one investment flow with explicit direction while keeping the accounting form understandable.

## Area
`frontend`

## Stack
`core`

## Scope
1. In scope
2. Redesign the investment movement UX in `AccountingMovementsView` to use one investment flow with direction selector: `Aporte` / `Desinversion`.
3. Support editing of existing investment movements without breaking the balanced-entry model.
4. Update position-level accounting activity in `NetWorthView` so investment entries and exits are visibly distinct.
5. Keep the visual model as one investment type, not as two separate movement families.
6. Out of scope
7. Redesign of unrelated movement types.
8. Importer UI changes in the MoneyWiz modal.
9. Dedicated realized PnL dashboards or portfolio analytics screens.

## Plan
1. Diagnosis
2. Review the current movement modal, quick-entry form state, and activity chips for `investment_purchase`.
3. Confirm where the UI currently assumes that investment always means liquidity to asset.
4. Change implementation
5. Replace the purchase-only investment affordance with a direction selector inside the investment flow.
6. Adjust labels, helper text, and account pickers so the user understands source/destination for both `Aporte` and `Desinversion`.
7. Make the edit modal preserve balance while allowing direction changes, account swaps, and optional realized PnL metadata when present.
8. Update `NetWorthView` activity rendering so investment inflows and outflows remain readable and the net contributed concept is not hidden behind generic transfer styling.
9. Validation
10. Cover investment create/edit scenarios, investment activity rendering, and regression against transfer/debt flows.

## Validation
- `docker compose -f core/docker-compose.yml exec frontend npm run lint`
- `docker compose -f core/docker-compose.yml exec frontend npm run format:check`
- `docker compose -f core/docker-compose.yml exec frontend npm run typecheck`

## Required Documentation Updates
- [ ] `core/docs/frontend/accounting-movements-ux-notes.md` - replace purchase-only wording with bidirectional investment UX.
- [ ] `core/docs/project-status.md` - reflect this phase as an available agent task and later mark progress/closure.

## Risks
1. Making the form heavier than the current fast-entry flow. Mitigation: keep one investment type and reveal direction-specific fields progressively.
2. Confusing `Transferencia` with `Desinversion`. Mitigation: reserve transfer for cash movement without investment semantics and make the copy explicit.
3. Divergence between movement history and net-worth activity if labels or chips are not aligned.

## Completion Criteria
- [ ] All validation commands pass
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
