# Project Status — Core

Current feature status by area. Update this file whenever functionality status changes.

**Last review:** 2026-08-16 | **Core Version:** see `VERSION`

---

## Current and Next Tasks

> Task type convention:
> - **(Manual)** — requires direct user guidance; direction is defined interactively and should not be delegated without that guidance.
> - **(Agent)** — delegable; requires a master plan but not continuous user decisions.

### In progress

| Module | Type | Description | Spec |
|--------|------|-------------|------|
| _(none)_ | — | — | — |

### Next available task

Pick based on capacity: execute **(Agent)** tasks when delegation bandwidth exists; execute **(Manual)** tasks when guided collaboration time is available.

| Module | Type | Description | Spec |
|--------|------|-------------|------|
| Investment portfolio - Phase 1 | Agent | Create the Core portfolio domain, safe bootstrap and independent performance/detail coverage. | `tasks/investment-portfolio/phase-1-domain-foundation/backend.md` |
| Investment portfolio - Phase 2 | Agent | Add confirmed automatic prices, manual valuations, freshness and provider health. Requires Phase 1. | `tasks/investment-portfolio/phase-2-hybrid-valuations/backend.md` |
| Investment portfolio - Phase 3 | Agent | Deliver TWR/MWR/P&L/FX engine, read APIs and independent mathematical QA. Requires Phase 2. | `tasks/investment-portfolio/phase-3-performance-engine/backend.md` + `qa.md` |
| Investment portfolio - Phase 5 | Agent | Add complete operations, corporate actions, generic CSV import and reconciliation. Requires SaaS Phase 4. | `tasks/investment-portfolio/phase-5-operations-import/backend.md` + `qa.md` |
| Investment portfolio - Phase 6 | Agent | Add versioned allocation and contribution-only rebalancing baskets. Requires Phase 5. | `tasks/investment-portfolio/phase-6-allocation-rebalancing/backend.md` |
| Investment portfolio - Phase 7 | Agent | Add strategic benchmark and progressive risk engine. Requires Phase 6. | `tasks/investment-portfolio/phase-7-benchmark-risk/backend.md` + `qa.md` |
| Investment portfolio - Phase 8 | Agent | Add alerts, Mi Plan integration and functional closeout. Requires Phase 7. | `tasks/investment-portfolio/phase-8-product-integration/backend.md` |

> Module overview, binding design decisions, and validated spec: `tasks/financial-plan/README.md` + `tasks/financial-plan/spec.md`. Frontend phases (2, 3, 4, 5, 8, 9) live in the SaaS repo root (`docs/tasks/financial-plan/`).

> Investment portfolio overview and binding decisions: `tasks/investment-portfolio/README.md`. The SaaS workspace and frontend phases live in the root repo under `docs/tasks/investment-portfolio/`.

> Monthly-close settlement overview and binding contract: `tasks/monthly-close-settlement/README.md` + `tasks/monthly-close-settlement/spec.md`. SaaS frontend phases 4-6 live in the root repo under `docs/tasks/monthly-close-settlement/`.

### Pre-production roadmap snapshot (by area)

Consolidated view of what remains in Core before production launch. See `roadmap/product-roadmap.md` for module-level details.

| Area | Priority | Status | Description |
|------|----------|--------|-------------|
| Accounting — v1 | High | ✅ | Core contract supports the SaaS daily-operations workspace: calculated classification review queue and validated account-scoped daily balance series. Imported movement traceability remains preserved. |
| Investment portfolio | High | ⚪ | Planned as eight sequential Core/SaaS phases: safe domain bootstrap, hybrid valuation, professional performance, mobile-first workspace, complete operations/import, allocation/rebalancing, benchmark/risk and product integration. Canonical plan: `tasks/investment-portfolio/README.md`. |
| Budget — v1 | High | ✅ | Functional closeout applied and manually reviewed: canonical monthly summaries for execution/coverage, ledger precedence over manual check-ins, backend errors shown inside line modals, and header aligned with Net Worth. |
| Net Worth — asset/liability modals | Medium | ✅ | Full review of asset and liability create/edit modals completed. Accounting-backed mortgage cancellation forecasts reconcile the current ledger balance with remaining budget installments instead of rebuilding a stale historical schedule. Module v1 functionally closed. |
| Monthly Close — dual mode | High | ✅ | Automatic implementation completed (backend + frontend) and operational manual review completed. The state exposes a role-aware financial result that separates financial savings, property formation and tangible purchases from the reconciliation residual. v1 bugs fixed on 2026-05-20: reconciliation bridge column alignment (CSS subgrid) and per-account liquidity reference (previous month effective balance instead of `asset.amount`). |
| Crypto Tax Report | Medium | ⏸ | Full Spanish IRPF module: Pionex + Binance, global cross-exchange FIFO, boxes 029/332/337. Paused — reassess before resuming. |
| Financial coach — navigation | Medium | ✅ | Simplified v1: `/` -> `/patrimonio` landing, guide at `/guia`, phase 5 (financial independence) removed until an investment portfolio module exists. Contextual quick actions by phase already existed. |
| Remove Data Input module | High | ✅ | `/introduccion-datos` removed in Core. Portable data consolidated in `/account`; assets and liabilities in `/patrimonio`. |
| Unified design system | High (critical) | ✅ | 22 steps completed (see `docs/frontend/design-system.md`). Full foundation done: canonical views, full domain CSS tokenization, `ui-pro-*` layer removed, `--chart-*` palette, accounting hero aligned with Net Worth. Incremental view-by-view polish continues as needed. |
| Residual legacy cleanup | Medium | ✅ | Completed 2026-05-20. Removed: Data Input, `investment_purchase` alias, scalar contribution fields (migration 0042), external `net_worth.services` import, and `compat.*` in capabilities. Budget/check-in fallback is intentional design, not technical debt. See `roadmap/product-roadmap.md`. |
| Core backend refactor | Medium | ✅ | Structural refactor completed (phases 1-5). Contribution backlog remains documented in `roadmap/backend-maintainability-backlog.md`. |
| Core frontend refactor | Medium | ✅ | Structural roadmap completed; contribution backlog documented in `roadmap/frontend-maintainability-backlog.md`; see `roadmap/terminados/frontend-refactor-roadmap.md` and `core/docs/architecture/shared-package-candidates.md`. |
| Auth and security | High | ✅ | Logout with blacklist, cross-user isolation (31 tests), user signup in UI (`/registro`, JWT on signup, rate throttling). Frontend (12->0) and backend CVEs resolved. |
| DB backup/restore | Medium | ✅ | Admin-only endpoints `GET /api/core/db-backup/` and `POST /api/core/db-restore/` based on pg_dump/pg_restore. AccountView migrated to this flow; portable JSON removed. |

---

## Implemented and Stable Features

| Area | Status | Notes |
|------|--------|-------|
| Net Worth (assets, liabilities, liquidity) | ✅ | Complete baseline. Snapshots removed. Added investment-asset generated-expense review modal. Multiple periodic contribution intervals completed (phases 1-2 archived). Charts (timeline + donut) and KPIs validated. Asset and liability create/edit modals reviewed; module v1 functionally closed. |
| Budget (annual income/expense, monthly check-ins) | ✅ | Full category-based flow. Executed evolution bars, recurring/one-time filter, YTD bars, and canonical coverage all functional. Monthly summaries are the canonical execution/coverage contract; line modals show backend errors without losing form state; header aligned with Net Worth. Manual review completed on 2026-05-14. |
| Monthly Close | ✅ | Integrated with budget and accounting. Automatic dual mode remains unchanged for profiles without settlement. The opt-in ownership settlement resolves per-member positions, compensations, recurrent reserves and fixed/dynamic destinations. Finalized routes can be applied fully or partially as idempotent ledger transfers, reconciled with compatible existing movements, cancelled or explicitly reversed. Applied history prevents reopen; locked closes reject execution. |
| Data Input (annual entries) | ✅ | Module/route removed. Responsibilities moved to Budget (income/expense), Net Worth (assets/liabilities), and Account (portable data). |
| Financial Guide / Coach v1 | ✅ | Phases 1-4 scoring implemented. Phase 5 removed until portfolio module exists. Guide at `/guia`; `/` redirects to `/patrimonio`. |
| Family & Ownership (`FamilyMember`, `OwnershipLink`) | ✅ | Explicit ownership remains the default. Shared ownership can opt into a previous-12-complete-month recurring-income allocation, with explicit income taxonomy, booking-date FX, quality/readiness output and immutable frozen monthly snapshots. Preview: `GET /api/ownerships/{id}/allocation-preview/?year=YYYY&month=M`; read-only audit: `audit_ownership_allocation`. Phase 1 spec archived under `tasks/monthly-close-settlement/phase-1-dynamic-ownership/terminados/`. |
| Accounting Movements (`LedgerAccount` / `LedgerTransaction` / `LedgerEntry`) | ✅ | Cursor-paginated transaction API includes server filters, `activity_kind`, calculated `needs_review`, review counts and safe daily series scoped by accounts. Bidirectional and multi-currency investment flows, manual realized metadata, invested-capital aggregates and import traceability remain supported. |
| Market data sync (FX, national + regional CPI) | ✅ | Phases 1-6 complete, `market_data_sync` worker live. Tables use server pagination (`page_size=50`) and frontend infinite scroll. |
| DB Backup/Restore (pg_dump) | ✅ | Admin-only backup/restore endpoints based on pg_dump/pg_restore. Portable JSON flow removed from UI and replaced with this flow. |
| Financial scoring phases 1-4 | ✅ | Debt, cash flow, emergency fund, net worth health. |
| Core auth (JWT) | ✅ | User signup from UI (`/registro`), logout with blacklist, token refresh, and rate throttling. |
| Financial Plan — projection engine | ✅ | New Core `plan` app: single financial plan, seeded assumptions, deterministic yearly projection, bridge-period capital, asset function overrides, data quality, snapshots and `/api/plan/*`. Employment end and pension start are derived from configurable adult ages; 67 is only the initial pension value. |
| Financial Plan — scenario lab backend | ✅ | Phase 3 backend complete: `Scenario`/`ScenarioEvent`/`PlanEvent`, non-contaminating comparison snapshots, accept/discard API, accepted events in future projections, and automatic future budget entries without creating real assets/liabilities/accounting rows. Named one-off expense concepts sum into projection impact and remain separate in managed budget lineage. |
| Financial Plan — findings/recommendations backend | ✅ | Phase 4 backend complete: `Finding`/`Recommendation`, backend-owned foundations, deterministic recommendation templates, recommendation-to-scenario simulation, monthly-close hook and plan-impact API. |
| Financial Plan — guided decisions contract | ✅ | `target_date` cuts structural labour income; pension ages remain configurable. Setup reuses shared adult identities without breaking Patrimonio references. Contributions target productive/security/debt capital. Recommendations preserve lifecycle state, prioritize cash-flow recovery, link to scenarios and expose side-effect-free preview, snooze and aggregated `/overview/`. |
| Financial Plan — affordable contribution improvements | ✅ | `INCREASE_CONTRIBUTION` is no longer proposed against a structural deficit. During a temporary squeeze it starts at the recovery date and explains that funding comes from the future margin; its amount and start date can be overridden consistently in preview and draft simulation. Recommendations with zero projected effect are omitted instead of creating cosmetic budget lines. |
| Financial Plan — engine correctness | ✅ | Phase 7 complete: current-FY inputs, structural-only income, aggregate labour cut-off, exhaustive expense buckets and explicit data-quality factors. Current-year projection starts after the live snapshot, uses remaining monthly budget slices, prorates decision debt service and carries unfunded cash as a recoverable `financing_gap`. Positive free cash is allocated 25% to Security until reaching two inflation-adjusted years of recurring expenses and 75% to Productive; once the security target is full, all excess becomes Productive. The same configurable allocation applies to positive net cash from same-month decisions and standalone one-offs after recovering any financing gap. The projected balance separates gross Liquidity, Investments, Real estate, Furnishings/vehicles and Other assets; housing/vehicle decisions move their physical category, furnishings depreciate at an explicit 12% default instead of receiving real-estate appreciation, and every row reconciles exactly as assets minus liabilities. Disposing a financed asset removes its net classified value, so its associated mortgage is not subtracted twice. Historical snapshots remain immutable. |
| Financial Plan — savings/investment cash reconciliation | ✅ | Budget savings and investment rows now drive a year-by-year destination schedule without creating cash. The engine funds them only from free operating surplus, caps an over-allocation proportionally, reports planned/effective/unfunded amounts and applies any unassigned remainder through the default Security/Productive policy. One-off contributions no longer behave as inflows. Budget, monthly summaries and Plan share recurrence semantics, so structural and term rows remain effective after their start fiscal year while linked system mirrors stay exact-year. Live budget edits change the projection input hash immediately. |
| Financial Plan — budget/plan boundary | ✅ | Phase 8 complete: reserved `PlanEvent` lineage, read-only managed budget rows, inverse budget trace endpoint and non-destructive lineage audit/repair command. Grouped planned decisions now mirror their forecast financing into annual Budget rows, regenerate it on edit and remove it on cancellation/materialization without double-counting the Plan projection. |
| Financial Plan — event lifecycle | ✅ | Phase 6 complete: event closure date, traced budget-line retirement, recurring projection cut-off and isolated close API. Real asset disposal remains in Patrimonio. |
| Financial Plan — decision cash flow counted once | ✅ | Una Decisión toca la caja por tres vías que no pueden solaparse. El desembolso inicial ya entraba solo por el evento (`one_off_flows` excluye sus partidas). Ahora la **cuota** hace lo mismo: `temporary_commitment_schedule` y el tramo del año en curso excluyen las partidas de las decisiones planificadas **con financiación** (`financed_decision_event_groups`), cuya cuota ya sirve `decision_debt_service_for_year`; antes se restaba dos veces del superávit libre. Una decisión ya ocurrida sigue contando sus partidas adoptadas, que son la única vía por la que el plan las conoce. Y el **gasto recurrente** de una decisión pasa a recortar la capacidad de ahorro (`annual_operating_expense_delta`), prorrateado en su año de arranque y sin doble conteo cuando el presupuesto del año en curso ya lo incluye (`baseline_absorbed`). Su horizonte deja de morir con el préstamo: sin fecha de fin el gasto es indefinido —el coste de uso de un coche sigue tras amortizarlo—, igual que ya asumía la partida de presupuesto que la propia decisión genera. |
| Financial Plan — la comparación mide la fecha del titular | ✅ | La tabla "Plan vigente vs escenario" comparaba `summary.projected_year`: el año en que la trayectoria que se retira en la **fecha deseada** alcanza el capital objetivo. En un plan que aún no llega, ese cruce acaba cayendo en el tramo en que el capital requerido ya es 0 porque las pensiones cubren solas el nivel de vida objetivo, y ese año no depende de la decisión simulada: la tabla decía "sin variación" mientras patrimonio y capital productivo se movían decenas de miles de euros. `ScenarioService.compare` expone ahora `sustainable_year` (`current`/`simulated`) y su delta, vía `earliest_sustainable_retirement_year`, que es exactamente la fecha que titula el plan ("podrías dejar de trabajar en X"). `summary.projected_year` se mantiene intacto —responde a otra pregunta legítima, desde cuándo te cubre la pensión— pero deja de ser lo que compara la tabla. Pendiente: la vista de mejoras (`preview.before/after.projected_year`) y el impacto del cierre mensual siguen usando la métrica antigua. |
| Financial Plan — decision lifecycle | ✅ | The plan owns the future; net worth owns the present. Occurred (retrospective) decisions adopt existing manual budget rows and **link** — never adopt — the assets/liabilities that keep generating their own rows. Planned grouping decisions retain their transaction month and can edit their future impact without releasing adopted rows or links; saving recalculates the official projection. Planned decisions created from an accepted one-event scenario can also be edited: the source scenario and only its managed future budget rows are regenerated in the same transaction. A forecast either **materializes** (`/materialize/`: real `Asset`/`Liability` prefilled from the scenario, forecast financing dropped, the rest released back to the user) or is **cancelled** (`/cancel/`: forecast rows deleted, scenario back to draft, projection restored). `baseline_absorbed` suppresses deltas already present in the current budget. |

## Active progress trackers

| Area | Status | Canonical roadmap |
|------|--------|-------------------|
| Accounting-budget separation | ✅ Phases 1-5 complete | `roadmap/terminados/accounting-category-budget-separation-roadmap.md` |
| Frontend refactor | ✅ Completed | Phases 0-6 closed; archived specs in `core/docs/tasks/frontend-refactor/*/terminados/`; `core/docs/architecture/shared-package-candidates.md` created. |

## Deliberately parked (future functionality)

| Module | Description | Specs |
|--------|-------------|-------|
| Crypto Tax Report | Full Spanish IRPF module: Pionex + Binance integration, global cross-exchange FIFO engine, and tax boxes 029/332/337. Parked before public OSS publication; reassess exploration status before resuming. | `core/docs/tasks/fiscal-report/` |

---

## Legend

| Symbol | Meaning |
|--------|---------|
| ✅ | Implemented and working |
| 🔄 | In progress |
| ⚪ | Not started (future scope) |
| ⛔ | Explicitly out of scope (decision made) |
| ⏸ | Deliberately parked |
