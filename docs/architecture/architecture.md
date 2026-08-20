# Core Architecture

## Objective
Describe the current architecture of `MoneyPlanner Core` as a self-contained open-source product.

## Summary
1. Core owns the product domain and shared business behavior.
2. Core is designed to be useful on its own.
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
4. Account workspace (includes portable data transfer: export/import/replace)
5. Financial guide v1
6. Family and ownership
7. Financial Plan (`plan`): deterministic projection engine and `/api/plan/*`
8. Investment portfolio (`portfolio`): containers, instruments, positions, historical ownership and migration readiness
9. Supporting product capabilities that belong to the Core domain baseline

## Architectural Rule
1. Shared product behavior belongs in Core.
2. Domain rules should live in backend domain layers, not in deployment-specific integrations.
3. Core documentation must remain self-contained and understandable without Core documentation.

## Internal Structure
1. Backend apps organize domain areas such as accounts, budget, net worth, accounting, memberships, portfolio, and shared core services.
2. Frontend code is organized by product domains under `frontend/src/domains/*`, including domain-specific UI such as `accounting`.
3. Operational and functional documentation for the OSS product lives under `core/docs/`.

## External SaaS Authentication Boundary

1. Core standalone JWTs keep their local blacklist and rotation behavior.
2. When `AUTH_ACCEPT_EXTERNAL_TOKENS=1`, a SaaS-issued JWT must pass signature, issuer and audience validation and then live session introspection against SaaS.
3. Introspection makes Core respect SaaS account deactivation, password revocation and `must_change_password` immediately.
4. The only non-introspected external token is a two-minute `core_bootstrap` token signed by SaaS and accepted exclusively by `POST /api/family-members/ensure-primary/`.

## Budget Execution Coverage Contract
1. `GET /api/budget/annual-income/monthly-summary/?year=YYYY` and `GET /api/budget/annual-expense/monthly-summary/?year=YYYY` are the canonical contracts to explain budget coverage vs real execution.
2. The payload distinguishes:
   - `executed_budgeted_total`: real execution matched to budgeted annual lines
   - `executed_unbudgeted_total`: real execution detected in ledger without annual budget line
   - `executed_total`: full real execution (`budgeted + unbudgeted`)
3. Monthly rows mirror the same split with `executed_budgeted`, `executed_unbudgeted`, and `executed_total`.
4. Responses include taxonomy breakdowns by category/subcategory (with monthly detail):
   - `income_execution_breakdown` for income summary
   - `expense_execution_breakdown` for expense summary
   so Core frontends can render unbudgeted execution visibility without duplicating backend rules.

## Ownership Allocation Contract

1. `Ownership.allocation_basis` is backward compatible: existing and newly created ownerships use
   `explicit_split` unless a shared ownership explicitly enables `recurring_income_12m`.
2. Individual ownership is always 100% of its member. Dynamic allocation is valid only for shared
   ownership and never mutates its persisted `OwnershipSplit` rows.
   Read responses for a dynamic ownership expose the current resolved shares as `effective_splits`;
   their persisted `splits` remain the participant set and must not be presented as the allocation.
3. Dynamic shares for a close month use the twelve complete natural months immediately before it.
   The source is posted ledger income with individual transaction ownership and an explicit
   `OwnershipIncomeRule`; `salary` is the default rule when dynamic allocation is first enabled.
4. Every eligible entry is converted to the user's base currency with FX effective on its booking
   date. Drafts, shared/unassigned transaction ownership and unmatched taxonomies do not contribute.
5. `OwnershipAllocationSnapshot` stores the source window, source hash, quality status and member
   shares. Draft snapshots can be recomputed; frozen snapshots are immutable inputs for finalized
   monthly closes.
6. Quality is `ready` with 12 observed months, `provisional` with 3-11 and `blocked` below 3, without
   positive income, with negative member income or with missing FX. Blocked results expose no
   effective percentages and never fall back silently to the old explicit split.

## Monthly-close Settlement Inputs

1. `SettlementProfile` is one-to-one with the user and defaults to disabled. Existing close flows do
   not require settlement configuration and retain their previous behavior.
2. A participating `SettlementAccount` references one user-owned asset and gives it one explicit
   role: operating, primary personal destination, allocation destination or physical cash. Operating
   and personal accounts are liquidity; allocation destinations may also be investment assets.
3. `AnnualIncomeEntry.ownership` and `AnnualExpenseEntry.ownership` are optional planning metadata
   because one aggregate forecast may cover realized movements from several owners. Realized
   settlement flows use posted transaction ownership; future reserves use the ownership of their
   configured operating or allocation destination account.
4. Recurrent expenses route through nullable `settlement_account`. Asset-generated investment rows
   inherit both ownership and an allocation destination only from unambiguous structural links;
   liability-generated rows inherit ownership. Plan-managed rows remain writable only by Mi Plan.
5. Readiness is period-specific and reports missing operating/personal accounts, account ownership,
   ambiguous operating reserve routes, movement ownership, dynamic-allocation coverage, non-zero
   opening adjustments and unnormalized wallets. It does not require ownership on budget rows;
   allocations without a destination are omitted with a warning instead of blocking activation.
6. Activation is explicit and idempotent. It captures one member/account opening baseline using the
   effective account ownership for the activation month. A wallet baseline uses accepted physical
   cash while preserving its modeled balance and historical movements for audit.
7. Opening adjustments are signed member/account entries that must sum exactly zero. They carry
   prior fictitious wallet compensations into the economic baseline without representing liquidity.
8. Readiness accepts an exact `balance_date` for activation previews and returns one
   `wallet_reconciliations` row per physical-cash account. Each row exposes the modeled balance,
   accepted cash and monetary difference for that same date; clients must not mix it with a current
   balance or with the first day of the selected close month.

## Monthly-close Settlement Engine

1. `compute_monthly_close_settlement` advances the previous finalized settlement position, or the
   activation baseline for the first close, through posted ledger movements inside the configured
   account perimeter. It never writes ledger movements.
2. External income and expense change each member's economic balance using transaction ownership.
   Internal transfers are economically neutral and only relocate the member/account position.
3. The next complete month supplies recurrent operating reserves and active temporary commitments.
   Savings and investment rows increase their explicit allocation destination; one-off and transfer
   rows are excluded, and unsupported roles are returned as warnings.
4. Every obligation and destination uses the same effective ownership resolver for its target month.
   Missing ownership, incompatible vectors, FX gaps, perimeter escapes and unexplained physical
   balance deltas make the result `not_ready`; the existing close can still be finalized.
5. The solver retains reserves in operating accounts, preserves existing physical cash and allocation
   positions, adds planned allocations, and routes the remaining member balance to primary personal
   destinations. Negative personal targets remain signed and therefore expose inverse contributions.
6. `SettlementSnapshot` freezes allocations, economic/account balances, reserves, compensations,
   reconciliation and quality when `MonthlyClose` is finalized. Recommendations are stored as
   `SettlementTransferRecommendation` route rows with an auditable lifecycle: recommended,
   accepted, partially applied, applied or cancelled.
7. `compute_monthly_close_state` exposes the additive `ownership_settlement` object with status
   `disabled`, `not_ready`, `ready` or `finalized`. Disabled profiles retain the previous lifecycle
   and have no additional readiness requirements.
8. A finalized recommendation can create a posted system transfer through the quick-entry service.
   The recommendation row is locked, `(user, settlement_idempotency_key)` is unique in the database,
   and partial applications expose the exact remaining amount. Apply-all is one atomic transaction.
9. Compatible manual/imported transfers may be linked only after matching accounts, currency,
   ownership, amount and date window. Reversal creates an opposite auditable transfer. Once any
   linked movement exists, the close remains historical and cannot be reopened or have its frozen
   snapshot deleted; locked closes reject all settlement actions.

## Net Worth Investment Contribution Intervals
1. Assets in category `investments` can be configured with multiple periodic contribution intervals through `contribution_intervals` in the asset serializer payload.
2. Each interval stores `start_date`, optional `end_date`, `amount`, `frequency` (`monthly` or `weekly`), and optional `currency`.
3. Legacy flat fields in `Asset` remain available for backward compatibility, while the schedule builder prioritizes interval rows when present.

## Investment Portfolio Domain Foundation

1. `Portfolio` is one-to-one with the user and owns the base currency used by the portfolio domain. `InvestmentContainer` groups positions operationally; `ContainerCashAccount` references one existing asset-type `LedgerAccount` per container and currency instead of creating another cash catalogue.
2. `Instrument` separates product identity from the user's patrimonial position. Canonical instruments have no user owner and require confirmed identifiers; custom instruments belong to one user. Legacy bootstrap creates custom instruments and does not infer an asset class for aggregated funds, ETFs, roboadvisors or pension plans.
3. `PortfolioPosition` references exactly one existing investment `Asset`, its container and instrument, and optionally its unique compatible `LedgerAccount`. It never stores a second balance. Active and archived assets are both migrated; archived positions remain queryable for historical calculations.
4. `PositionOwnershipPeriod` and `PositionOwnershipShare` freeze dated ownership evidence. Rows are immutable after creation. Explicit individual/shared ownership is copied only when it sums to 100%; missing, dynamic or invalid ownership remains an explicit `PortfolioMigrationIssue` instead of being guessed.
5. The idempotent bootstrap (`POST /api/portfolio/bootstrap/`) creates the single portfolio, a neutral legacy container and one position per investment asset. It classifies `units_based` only for an unambiguous cryptocurrency asset whose currency itself is the crypto unit; all other legacy rows remain `value_based`.
6. `GET /api/portfolio/readiness/` audits every investment asset and reports either a position or an explicit issue. `performance_coverage` derives independently from legacy/ledger investment flows and valuations; `position_detail_coverage` derives from confirmed unit tracking and investment ledger activity.
7. CRUD for portfolios, containers, cash-account links, custom instruments and positions lives under `/api/portfolio/`. Ownership periods support create/list/retrieve only, and migration issues are read-only. Every queryset and related-object field is scoped to the authenticated user; canonical instruments are the only shared rows.

## Investment Portfolio Valuation Layer

1. `InstrumentProviderMapping` is the explicit boundary between an instrument and a market-data provider. Automatic prices are accepted only from confirmed mappings with an exact symbol, quote currency and, for Twelve Data securities, market. Names and unverified ISIN/ticker guesses never create mappings.
2. `InstrumentPrice` stores immutable-at-source daily closes with provider, source key, market and fetch timestamp. `PositionValuation` stores dated total values from manual input or legacy derivation; importing legacy `AssetValuation` and posted ledger revaluations is idempotent and never edits accounting entries.
3. A units-based position uses its posted ledger-unit balance multiplied by the latest eligible close. A manual total value dated after the price takes precedence; value-based positions use their latest manual or legacy total value. Every resolved value reports date, freshness and provenance.
4. Freshness thresholds are instrument-specific: 3 days for stocks, ETFs, crypto and cash; 10 for funds; 35 for deposits; 45 for pension plans; 90 for crowdfunding; and 30 for other instruments. Missing, stale and mapping/price issues remain explicit in `/api/portfolio/valuation-health/`.
5. `instrument_prices` is a registered `market_data_sync` dataset. Reconciliation writes only persisted prices, refresh can run on demand per confirmed instrument, and a provider failure records sync health without deleting the last valid close.

### Initial provider decision (2026-08-16)

| Provider | Coverage and history | Limits / licence | Decision |
|----------|----------------------|------------------|----------|
| [Twelve Data](https://twelvedata.com/docs/advanced) | Daily `time_series` plus exchange/currency metadata for global equities, ETFs and mutual funds. | Personal Basic is rate-limited; external commercial display requires an eligible [business plan](https://twelvedata.com/pricing-business) and may require exchange approval under its [commercial-use policy](https://support.twelvedata.com/en/articles/5332349-commercial-and-personal-usage). | First securities adapter, optional and inactive without `TWELVE_DATA_API_KEY`; production activation requires confirmed licensing and mappings. |
| [Alpha Vantage](https://www.alphavantage.co/documentation/) | Global equity, ETF and mutual-fund daily series. | API-key plans and provider-specific throttling; the evaluated contract gives less explicit exchange/currency validation for this workflow. | Technically viable fallback, not selected for the initial adapter. |
| [CoinGecko](https://docs.coingecko.com/docs/setting-up-your-api-key) | Crypto market history with explicit coin identifiers and quote currencies. | Keyless access is not a production contract; paid plans carry their own [usage and attribution terms](https://www.coingecko.com/en/api/pricing). | Primary crypto adapter; API base and header are configurable for Demo/Pro. |
| CryptoCompare | Crypto daily history. | API key and applicable commercial terms required for production. | Existing fallback when CoinGecko fails. |

The migrated local sample has no trustworthy securities identifiers, so those positions expose `mapping_missing` instead of guessed quotes. BTC/EUR and ETH/EUR reuse persisted `FxRate` history before any network request. The phase-2 reconciliation persisted 2,543 daily closes from two confirmed crypto mappings through 2026-08-16 and imported 831 daily legacy ledger valuations. Portfolio health reports 4 fresh, 17 stale and 2 missing positions plus 10 explicit mapping/price issues.

## Investment Portfolio Performance Engine

1. The portfolio boundary includes every selected `PortfolioPosition` and each linked `ContainerCashAccount`. Position performance reads posted investment ledger movements and falls back to `InvestmentAssetEvent` only when no ledger investment exists for that position/date. Purchases/sales funded from linked container cash and reinvestments between positions are internal and never change household contribution or return; they remain external to the individual position for its own return. Revaluations are values, never external flows.
2. Sign convention is portfolio-centric: contributions are positive external flows, withdrawals and distributed income are negative, and internal income/cost/reinvestment rows have zero external flow. Monetary result always reconciles as `closing value - opening value - net external flows`. Explicit cost is reported separately; gross analytical result is net result plus explicit cost, without adding costs already embedded in a quoted NAV twice.
3. Exact TWR chains `((Vt - CFt) / Vprev)` for every external-flow date, using the end-of-day/after-flow valuation convention. It is published only when every flow date has an exact portfolio valuation. Otherwise Core declares `modified_dietz` and uses `(Ve - Vb - sum(CF)) / (Vb + sum(weight * CF))`, where `weight = remaining days / period days`. It never labels the fallback as exact TWR.
4. MWR uses XIRR with investor signs: opening value and contributions are negative, withdrawals/distributions and closing value are positive. The bounded solver returns unavailable when cash-flow signs do not permit a root. The principal return is nominal; real return is `(1 + nominal) / (IPC_end / IPC_start) - 1` using persisted Spanish CPI.
5. Values and flows retain native currency and are converted at their effective date through persisted `FxRate`. Per-position attribution reports local asset result translated at closing FX and defines FX result as the residual, so `asset + FX = total` exactly. Attribution remains unavailable when native currencies are incompatible instead of guessing.
6. Historical member filters apply the immutable ownership share effective on each value/flow date. A share change creates a synthetic member-level flow at that day's position value, preventing an ownership transfer from becoming fictitious return while remaining neutral for the family portfolio. Linked cash without dated ownership makes member-level cash coverage unavailable rather than being guessed. Aggregate performance, TWR and MWR are unavailable when boundary values or FX are incomplete; `covered_opening_value`, `covered_closing_value` and per-metric coverage remain visible for diagnosis.
7. Read APIs are `/api/portfolio/overview/`, `/api/portfolio/positions/performance/`, `/api/portfolio/timeline/`, `/api/portfolio/performance/` and `/api/portfolio/quality/`. They accept `date_from`, `date_to` and optional user-owned `member_id`. Timeline range is capped at 20 years and bulk-loads positions, values, ledger prefixes, flows, FX and ownership with a query count independent of position count.
8. No persistent cache is currently used. Read models are deterministic and rebuildable; this avoids incomplete invalidation until profiling justifies caching. Any future cache must be invalidated by flow, price/value, FX, CPI or ownership changes and can never become a source of truth.

### Mathematical QA evidence (2026-08-16)

1. Independent golden fixtures cover no flows, multiple contributions, withdrawals, same-day after-flow valuations, fees, reinvested income, closed positions, XIRR, CPI and USD/EUR attribution. Property tests assert monetary reconciliation, internal-transfer invariance, exact TWR chaining and refusal to fake precision without a flow-date value.
2. The anonymized 2018-2026 local portfolio contains 23 positions and 1,008 classified rows. The all-time aggregate exposes EUR 27,294.69 of covered closing value and EUR 24,155.85 net contributions, but correctly withholds aggregate return because opening coverage is 0/23 and closing coverage is 21/23. Six directionless legacy investment rows were checked against their debit/credit sides and counterpart types: cashback remains internal income and a position-to-position funded purchase remains neutral at portfolio level.
3. On the controlled 2025-01-01 to 2026-08-16 comparison, 11 positions have complete boundaries and all 11 satisfy the monetary reconciliation exactly; five use exact TWR, four use declared Modified Dietz and the remaining positions stay unavailable. Aggregate return remains unavailable because coverage is only 11/23 at opening and 21/23 at closing. Differences are therefore coverage decisions, not hidden numerical residuals.

## Investment Portfolio Operations and Import

1. `PortfolioTrade` stores execution metadata for purchases, sales, dividends, interest and fees while its linked `LedgerTransaction` remains the monetary source of truth. Units, unit price, trade currency, fee, source, external identifier and fingerprint are auditable without duplicating ledger balances.
2. A new purchase must debit the position account from a `ContainerCashAccount` belonging to the same container, with enough posted cash for gross amount plus fee. Transfers fund container cash separately. A signed, 30-minute preview binds every direct confirmation to the exact payload and duplicate fingerprints are rejected.
3. Splits, identifier changes, position transfers and adjustments create `PortfolioCorporateAction` evidence. Monetary or unit-changing actions link to their posted adjustment/transfer transaction; identifier changes retain previous and new identifiers in the action payload.
4. Manual valuations update the same position/date/source row instead of duplicating history. Archive/reopen toggles operational state and the backing asset without deleting positions, trades, actions or ledger rows.
5. `PortfolioImportBatch` and `PortfolioImportRow` stage generic UTF-8 CSV files through explicit mapping, normalization, preview and per-row errors. Exact file hashes and external source identifiers provide idempotency; only valid selected rows confirm, atomically, through the same operation service as manual entry.
6. Migrated positions declare either reconstructed history or a dated cutoff and confirm their tracking style without rewriting legacy data. `performance_coverage` and `position_detail_coverage` remain independent. Legacy bank-to-investment flows continue to be interpreted as funded purchases by the performance engine and are never mutated into new trades.
7. This layer reports analytical, non-fiscal P&L. It does not implement tax FIFO, broker credentials or automatic broker synchronization.

## Investment Portfolio Allocation and Contribution Baskets

1. The unit of policy is an `Ownership`, not a member. "Pablo's", "Lucas's" and "shared 50/50" are different mandates with different horizons, so each carries its own `AllocationStrategy`, versioned by `effective_from`. Editing the version in force rewrites it; a new effective date creates a new version, and a basket records the version it was solved against, so historical targets never change underneath a past decision. The member filter answers a different question — what economic share of each position is yours — and stays as the inventory filter.
2. An `AllocationTarget` belongs to an asset class or to a position, never both, and `unclassified` is refused: it is the absence of an answer, not an answer. A class target is a share of the portfolio and they must total 100. A position target is a share **of its class** — "of my equity, 60% to the index fund" — which is the unit the second level is thought in and the only one that does not fall out of balance on its own when the class target changes; it therefore does not count towards that 100, and several within one class cannot exceed it. What is not split by hand is inherited, divided by current weight, so every position has an effective target whether or not anyone wrote one for it. Tolerance bands (`min_percent`/`max_percent`) are what trigger a recommendation, because a relative band avoids rebalancing on noise better than a calendar does. What is held without having been planned reports as `unplanned` rather than being hidden.
3. Tactical liquidity is a policy line with its own band, not the remainder of the operation. Linked `ContainerCashAccount` balances are the liquidity that line reads against, attributed to a scope through the `OwnershipLink` of the cash asset itself.
4. `PositionAllocationRule` carries the constraints that make a proposal executable: exclusion, minimum contribution, rounding step, operation cost and whether a fee-free recurring plan applies. `ContributionCommitment` carries what must reach a position regardless of drift — a monthly floor that keeps a broker perk, or an annual quota, which is a ceiling too, since contributing above a deductible cap does not deduct. `PortfolioPosition.tax_transferable` marks what can be moved without a tax toll, so the solver prefers the free pocket when two options tie. A commitment also declares `breach_cost`, what breaking it costs per year: a commitment is not worth its amount but what is lost by missing it — dropping the recurring plan that keeps a remunerated account can cost the yield of the whole bank balance. When the contribution cannot cover every commitment, that cost decides who is served first, and what is left uncovered is reported instead of quietly disappearing.
5. A class with a target and no position in it has nowhere to receive money: its share ends up spread over the rest, so the proposal reports it as `unreachable` instead of dropping it silently. The solver only directs new money: it never proposes a sale, which keeps the bands without a tax toll while the portfolio still grows by contribution. It honours commitments first, then closes gaps, then distributes the remainder pro rata by policy, capped at each gap. It conserves the amount exactly and explains what it could not place — a minimum that is not reached, a rounding step, or a fee that would eat the ticket beyond `max_cost_share`.
6. A `ContributionBasket` is a proposal: it touches no accounting. Confirmation is deliberately partial — `line_ids` executes the lines you choose, each batch can come from a different account, and the basket closes only when nothing is left to decide. A line to a container's cash is a transfer (loading a platform's wallet is not buying anything); a line to a position is a purchase funded from `source_account_id`, materialized through the same phase-5 operation service. Discarding does not delete: the proposal you did not follow is also information.

### Budget and Plan boundary

1. The allocation read model exposes `suggested_contribution`: what the budget had planned to invest that month, summed from active `financial_investments` entries through `planned_expense_monthly_distribution`. It is a read. Choosing another amount does not write to Budget, does not create budget lines and does not touch Mi Plan.
2. The direction is one-way on purpose. Budget decides how much you can invest; the portfolio decides where it goes. Letting a basket rewrite the budget would make the plan describe what happened instead of what was decided, and both modules would stop being reconcilable.
3. Confirming a basket writes only to Accounting, through the existing operation service. Budget execution then reads those movements like any other, so the planned-versus-executed comparison keeps working without a second source of truth.

## Net Worth Timeline Contract
1. `GET /api/net-worth/timeline/` returns monthly rows for the chart plus a `comparisons` object for summary UIs. Each row includes `assets_by_category` in the user's base currency so consumers can render the real historical composition without rebuilding valuation logic.
2. `comparisons` exposes four baseline points calculated by Core in the user's base currency:
   - `previous_month_close`
   - `same_day_previous_month`
   - `previous_year_close`
   - `same_day_previous_year`
3. Each point has `{date, total_assets, total_liabilities, net_worth}` or `null` when the reference date does not exist or predates the timeline range.
4. `prev_month_same_day` remains as a compatibility alias for `comparisons.same_day_previous_month`.

## Financial Plan Projection Contract
1. Core owns the `plan` app and exposes `/api/plan/*` for the SaaS frontend. The MVP has no Core frontend UI.
2. Each user has one `FinancialPlan`; `POST /api/plan/` is idempotent and updates the existing plan when present.
3. `AssumptionSet` is globally seeded with `prudent`, `expected` (default), and `favorable`; snapshots freeze the exact hypothesis values used.
4. `AssetClassificationService` infers asset function from net-worth taxonomy and applies optional `PlanAssetFunction` overrides. Associated liabilities through `Liability.financed_asset` are subtracted from the asset's functional net value to avoid double counting.
5. `ProjectionService` projects yearly in the user's base currency. Current positions are converted to `UserSettings.base_currency`; FX rates are not projected.
6. Target spending is entered in today's euros. Forward projection inflates target income and future pension/other income using the selected assumptions.
7. Recurring and one-off `savings/investment` budget rows describe the intended use of cash but never create cash themselves. `planned_contribution_schedule` carries their effective amount and destination for every projection year: `savings` directs cash to Security and `investment` to Productive. Asset-generated mirrors are excluded because `InvestmentContributionInterval` is their source of truth; future plan-managed rows are excluded until their event reaches the baseline, avoiding duplicate event deltas.
7b. Active `one_off` budget entries **not** governed by a decision feed the projection as year-specific flows in their `fiscal_year` across the whole horizon (`services_inputs.one_off_flows`): income adds cash, `asset_purchase` moves productive→non-productive (cash becomes an asset), and `tax_fee/transfer/other` are pure outflows. A one-off income in `transfers_support` (for example a gift, inheritance, or family support) is money new to the user: it increases net worth once. Investing that money later is a separate `savings/investment` expense and only changes its destination. A one-off `savings/investment` row is handled only as a planned allocation under point 7. Excluded from the cash path: past years (already in current capital), `is_system_generated` expenses (owned by Patrimonio), `asset_sale` income (modeled via decisions) and entries whose `event_group` starts with `plan_event:`. For the current year only not-yet-occurred entries count (`target_month` after the current month, or no month), so already-spent/received amounts are not double-counted.
7c. **Cash-flow reconciliation and allocation**: in each accumulation year (`year < target_year`), including the remaining months of the current year, `free_surplus = income − operating_expenses − active_temporary_commitments − decision_debt_service` (`services_projection.free_operating_surplus`). Positive surplus first recovers any `financing_gap` and honors debt contributions. Budget/event allocations to Security and Productive are funded next; if their total exceeds the remaining cash, both are reduced proportionally. Only the unassigned remainder follows `security_contribution_rate` (25% by default) until Security reaches `annual_operating_expense × security_target_expense_years`, with the excess going to Productive. Trajectory rows expose free cash, planned/effective/unfunded contribution, funded destination amounts and automatic remainder. A negative surplus consumes Security first, then Productive, and any uncovered amount remains as a recoverable negative `financing_gap`. Temporary commitments expire by `term_end_year`; a user's existing debt service is already represented by its budget line, while new decision debt uses `decision_debt_service_for_year`, so neither is paid "for free" nor counted twice. Known gap: `FoundationService.committed_surplus` reads budget lines only, so a decision's new debt is not yet reflected in the cash-flow *diagnosis* (only in the projection).
7d. Budget recurrence is shared by the Budget API, monthly summaries and Plan inputs. A one-off applies only to its exact `fiscal_year`; manual/non-linked structural rows remain effective from their start year; term rows remain effective through `term_end_year`; asset/liability-generated yearly mirrors apply only to their explicit fiscal slice.
7e. **Projected balance composition**: every trajectory row exposes gross `liquidity_assets`, `investment_assets`, `real_estate_assets`, `furnishings_assets`, `other_assets` and their `total_assets`. Housing/renovation decisions move Real estate; vehicle decisions move Furnishings; security allocations move Liquidity and productive allocations move Investments. Real estate uses `non_productive_appreciation_rate`; furnishings and vehicles use the explicit `furnishings_depreciation_rate` (12% default). Displayed amounts are rounded by category before totaling, and `net_worth = total_assets − liabilities` exactly.
8. If the target date is before pension start, the required capital is split into a bridge period plus post-pension gap capital. The engine does not apply a single withdrawal-rate rule to the full lifetime need.
8b. `preservation_target_eur` is untouchable capital: it is added on top of the required capital (denominator and yearly gate), so preserved wealth never funds the target income. The legacy net-worth check (`preservation_ok`, total net worth ≥ target at the achieving year) remains as an additional gate but rarely binds. `/api/plan/capital-requirements/` deliberately excludes preservation: its amounts describe expense needs only.
9. In Phase 1, financial cases such as car purchase, second home purchase, and sabbatical are represented as already-incorporated base data. Hypothetical non-contaminating scenarios are Phase 3 scope.
10. For adults with `birth_date`, employment end and pension start dates are derived from the configurable ages sent by the client; age 67 is only the initial pension value. `target_date` independently cuts structural labour income for the projection.
11. `GET /api/plan/capital-requirements/?monthly_amounts=a,b,...` returns, for each monthly need in today's euros (1–8 values), the capital required at the target date computed with the same math as the projection's target capital (inflation, pension/other-income offsets, bridge period, withdrawal rate). Plan-event deltas are deliberately excluded: an arbitrary need already defines the expense to cover. This keeps consumer-side progress milestones on the same axis as the projection denominator. Optional `target_year` moves that horizon: the capital required depends on how much bridge is left until the pension, so a consumer showing a denominator built for another year (the overview projects the **sustainable retirement year**, not `plan.target_date`) must request the milestones for that same year — otherwise a smaller monthly need can require more capital than the whole target.
12. Plan member writes reuse an existing same-name adult owned by the user. When setup replaces a draft member with that shared identity, Core moves the plan membership without deleting the draft record, preserving ownership and historical references outside the plan.
13. `GET /api/plan/members/` lists every active adult owned by the user, including plan-specific dates and future-income fields, even before a `FinancialPlan` exists. This is the candidate contract used by setup to link existing family identities instead of creating parallel records.

## Financial Plan Scenario Contract
1. `Scenario` and `ScenarioEvent` model hypothetical decisions without mutating real net worth, budget execution, or accounting.
2. Scenario comparison runs the projection engine with current accepted plan events plus the draft scenario deltas. It persists only non-official `ProjectionSnapshot` rows (`is_official=False`) linked to the scenario.
3. Accepted scenarios create a `PlanEvent` with the exact event payload in `planned_impact_json`. Active planned events are included in later official projections.
4. Scenario payments apply the agreed MVP rule: initial outflows reduce security capital first and then productive capital. New assets are classified with the same plan functions (`productive`, `security`, `short_term_goal`, `family_use`, `unknown`).
5. Monthly deltas apply from the event start date to the explicit end date. If no end date exists and the delta is tied to a new debt, it ends when that debt term ends; otherwise it remains active for projection purposes.
6. New scenario debt uses an amortizing monthly payment when term and interest are present; if no interest is present, it falls back to linear principal amortization.
7. Accepting a scenario does not create real `Asset`, `Liability`, `LedgerTransaction`, or check-in rows. It does create future budget entries from existing budget taxonomy defaults or from editable `metadata_json.budget_lines` supplied by the UI.
8. Temporary recurrent budget entries support `term_start_month`, `term_end_month`, and `term_end_year`, so scenario-generated rows can start and end in the intended months.
9. Scenario-generated annual budget rows use reserved lineage `plan_event:<PlanEvent.id>`. Budget serializers expose `is_plan_managed`, `plan_event_id`, and `plan_event_name`; general budget `PUT`/`PATCH`/`DELETE` operations reject managed rows with `403 plan_managed_entry`.
10. `GET /api/plan/events/{id}/budget-lines/` is the inverse trace from a user-owned plan event to its income and expense rows. `audit_plan_budget_lineage` reports invalid/orphan lineage and can explicitly repair the legacy scenario-ID format; it never deletes rows.
11. `PlanEvent.effective_end_date` is the first month in which a closed event no longer produces recurring effects. Closing preserves historical and one-off rows, splits/shortens the managed recurrent lineage at month precision, removes later rows, records the exact mutation in `actual_impact_json.closure`, and recalculates the official projection.
12. Event closure stops recurring income, expense, and contribution deltas. Asset **disposal** is modeled: an event may carry `disposed_asset_value`/`disposed_asset_type` (removed from its bucket at the projected value in the sale year, symmetric to `new_asset_value`), `proceeds` (added to productive capital) and `disposed_liability_value` (the cancelled associated debt, discounted from both the projected liabilities and `associated_liabilities` so net worth reconciles without double counting). Real asset archival in Patrimonio still happens on occurrence, not on planning.
13. `ScenarioEvent.metadata_json.one_off_items` may preserve several named one-off expenses within one decision. The serializer makes their sum the canonical `initial_outflow`; comparison applies that total once, while acceptance creates one traceable managed budget row per concept. Events without this metadata retain the legacy aggregate initial-outflow behavior.

## Occurred (Retrospective) Decisions

1. `POST /api/plan/events/occurred/` registers a decision the user already took. It creates a `PlanEvent` with `status=occurred` and `actual_date`, and creates **no** budget rows: the rows already exist.
2. Occurred events are excluded from the projection by construction — `plan_event_payloads` only reads `planned` events. This is required, not cosmetic: the effects of a past decision are already inside current net worth and the current fiscal year's budget, so re-applying its deltas would double-count them.
3. Registration **adopts** existing budget rows by rewriting their `event_group` to `plan_event:<id>`, which makes them `is_plan_managed` (so general budget writes reject them) and puts them under the event's closure lineage. Amounts, dates and taxonomy are never modified.
4. Rows whose `source_liability` or `source_asset` is set cannot be adopted. Liability/asset budget synchronization does `get_or_create` keyed on its own `event_group` (`liability_<id>`, `asset_<id>`), so rewriting it would make the next sync miss the row and create a duplicate. Their lineage is already the asset or liability.
5. Rows already owned by another plan event cannot be adopted twice.
6. `DELETE /api/plan/events/{id}/` releases an occurred event: every adopted row returns to the `previous_event_group` recorded in `actual_impact_json.registration`, and the event is deleted. Without this, a mistaken registration would leave real user rows frozen as plan-managed.
7. Real assets and liabilities are **linked**, never adopted: `PlanEvent.linked_assets` / `linked_liabilities` (M2M to `net_worth`). Net worth stays their owner and keeps generating their budget rows. Linking is what lets a decision state its full impact (outflow **and** debt taken on) without stealing that lineage. `GET /api/plan/events/{id}/budget-lines/` returns the linked entities and the annual expense they generate, alongside the adopted rows.

## Planned (Grouping) Decisions

1. `POST /api/plan/events/planned-decision/` (`register_planned_decision`) groups **existing** `one_off` budget rows into a `planned` `PlanEvent` **with** projection impact — a purchase (`new_asset_value`/`new_debt_*`/`initial_outflow`) or a sale (`disposed_asset_value`/`proceeds`/`disposed_liability_value`) applied in `transaction_year` + `transaction_month`. It is the forward-looking sibling of the occurred flow: same `_adopt_budget_entries`/`_link_net_worth` (adopt rows via `event_group`, link real assets/liabilities), but the event is `planned` and contributes to the official projection.
2. Adopting the rows removes them from the `one_off_flows` cash path (point 7b), so the decision counts them exactly once. The `impact` payload is built into `planned_impact_json.events[0]` with the same keys as `scenario_event_payload`.
3. Use it to migrate a transaction already entered as budget one-offs (e.g. a planned home sale) into a decision that disposes the asset and cancels its mortgage in the sale year, instead of counting the sale proceeds as plain income.
4. The current-year row starts after the current net-worth snapshot: structural cash flow and temporary commitments use only the remaining budget months, and new debt service is prorated from `transaction_month`. Decision inflows and outflows in the same month are netted before touching capital buckets, so a linked home sale funds its replacement purchase without artificially draining Security. A positive net remainder, like positive standalone one-off cash, follows the configurable Security/Productive allocation after recovering any financing gap and remains capped by the Security target. If the resulting cash need cannot be funded, the remainder is exposed as negative `financing_gap`, included in projected liabilities and repaid by future free cash before new contributions.
5. An unregistered asset sale and every one-off expense sharing its `event_group` stay outside `one_off_flows` until the sale becomes a Decision. This keeps proceeds, disposal and transaction costs atomic.
6. `PATCH /api/plan/events/{id}/planned-decision/` edits the date, transaction month/year and projected impact while a decision is still `planned`. Grouped decisions preserve their adopted rows and links; one-event accepted scenarios update their source and regenerate only their managed future rows. Both paths recalculate the official projection transactionally.
7. `POST /api/plan/events/planned-decision/preview/` is an ephemeral comparison for the create/edit forms. It persists neither a `PlanEvent` nor budget rows or snapshots: for a creation it excludes the selected one-off rows before applying the candidate event, and for an edit it replaces the existing event only in the projection inputs. It returns the current/candidate trajectories and their sustainable-year delta.
8. Mortgage cancellation forecasts respect the liability's source of truth. For `tracking_mode=accounting`, the cancellation principal starts from the effective ledger balance today and applies only the remaining budgeted installments through the configured cancellation month; it never rebuilds the historical loan from a stale manual principal. Manual liabilities retain the amortization-schedule estimate.
9. A grouped planned decision with `new_debt_principal` and `new_debt_term_years` creates one managed financing row per affected fiscal year (`plan_event:<id>`). These rows make the estimated installments visible in Budget, are regenerated when the decision changes, and are deleted when it is cancelled or replaced by the real liability on materialization. Projection excludes this managed lineage from temporary commitments because `decision_debt_service_for_year` already applies the same payment.

## Decision Lifecycle

The boundary: **the plan owns the future; net worth owns the present and the commitment already taken on.** A decision has two lives, and three ways to leave the first one.

1. **Forecast (`planned`).** Accepting a scenario creates a `PlanEvent` and the future budget rows the plan itself forecasts. Nothing exists in net worth yet: no asset, no liability, no real commitment. This is what feeds the projection deltas.
2. **Materialization** — `POST /api/plan/events/{id}/materialize/`. The decision actually happened, so the truth moves to net worth: the real `Asset` and `Liability` are created **prefilled from the `ScenarioEvent`** (principal, rate, term, start date), the liability starts generating its own real installments (lineage `liability_<id>`), and the event becomes `occurred` and stops feeding the projection. The plan's forecast **financing** rows are deleted — the liability is about to regenerate them and they would double up. Every other row (down payment already made, running costs, contributions) is **released back to the user** (`event_group=""`): they are real, they are his, and from now on he edits them in Presupuesto. The simulated `new_asset_type` is written as a `PlanAssetFunction` override so classification respects what was simulated.
3. **Cancellation** — `POST /api/plan/events/{id}/cancel/`. Changed your mind about something that has not happened. Only valid while `planned`: the forecast rows the plan created are deleted whole, the event is deleted, the source scenario returns to `draft` (so it can be compared and accepted again) and the projection returns to where it was. Nothing about the present changes. What already happened is undone in net worth, not here.
4. **Closure** (`/close/`) is a different thing and only applies to what already occurred: it retires the recurring effects of a real decision from a date onwards.

### Baseline absorption (double counting)

An accepted event contributes deltas to the projection, but the budget rows it created enter the **current fiscal year's** budget as soon as its year arrives — and the current fiscal year is exactly where `planned_contribution_amount` and `structural_income` read the projection's contribution and income baseline from. From that moment the event is already inside the baseline, and adding its deltas on top counts it twice (measured: a 6.000 €/yr contribution produced 6.000 €/yr of phantom savings, compounding).

`plan_event_payloads` therefore marks each payload `baseline_absorbed` when `start_year <= current fiscal year`, and `event_deltas_for_year` skips its **contribution and income** deltas. The **expense** delta keeps applying: it raises the target standard of living, which the user declares and the budget does not feed. Draft scenarios compared via `extra_events` are never absorbed — their rows do not exist yet, so their deltas must apply.

## Financial Plan Foundations And Recommendations
1. `Finding` and `Recommendation` live in the Core `plan` app. Findings are unique per `(plan, code, period)` and recommendations are unique per `(finding, code)`.
2. `FoundationService` ports the former frontend guide diagnostics into backend-owned metrics: cash flow, emergency fund, debt, net-worth health, planned contribution and data quality. Each scored block also publishes a product `status` band (`good` >= 70, `warning` >= 40, `critical` below) and an A-E `grade` (`A` >= 85, `B` >= 70, `C` >= 55, `D` >= 40, `E` below), both computed from the rounded score, so clients color and grade the diagnosis without owning thresholds. Debt service (`annual_debt_service`, `debt_payment_to_income`) counts **only commitments generated by a liability** (`source_liability`), not every temporary commitment: instalments of a purchase or a treatment with an end date are not debt, and counting them took a real pilot from 18.5% to 48.9% effort. That ratio is now 20% of the debt score (floor 15%, zero at 40%), so cheap debt that still eats the salary no longer scores clean. The grade recovers the Guide v1 scale but is fitted to the current bands — A/B are `good`, C/D `warning`, E `critical` — so letter and colour can never contradict each other. `planned_contribution` is scored too (savings rate = planned contribution / structural income, floor 5%, target 20%), and the payload adds an `overall` block: the weighted average of the six foundations (cash flow .28, emergency fund .22, debt .18, planned contribution .14, net-worth health .10, data quality .08) with the same score/status/grade shape, so a client can headline "health: C" instead of counting amber blocks. Emergency-fund eligible liquidity counts **cash and deposits only** (liquid investments such as funds/ETFs/stocks/crypto are sellable but are not the cushion), and its score is *only* coverage against **its own target** (`EMERGENCY_TARGET_MONTHS`, 6 months, floor at half the target): committed-expense coverage is published as detail but not averaged in (the cash-flow foundation already grades the squeeze) and liquidity-over-assets moved out (it is diversification, graded by net-worth health). All foundation metrics read **effective** asset/liability amounts (`get_effective_asset_amount` / `get_effective_liability_amount`, the same source as the plan's classification and as Patrimonio), not the raw `amount` column, which was stale for positions kept by accounting or valuations. Quality factors about people (`pensions`, `employment_income_end_dates`) look at **the plan's adults**, not every adult in the family: the setup leaves unlinked provisional identities behind, and those kept flagging data that was already complete. The data-quality block reuses `DataQualityService` (the same factor set that grades the projection) instead of a separate shallow checklist.
3. `FindingService` evaluates deterministic MVP findings from those foundations and the expected projection. Resolved findings are closed instead of duplicated.
4. `RecommendationService` generates deterministic template-based actions with full explanation payloads (`action_json`, `impact_json`, `alternatives_json`). Refresh preserves accepted, dismissed and future-snoozed states. Negative committed cash flow produces `RESTORE_CASH_FLOW` before any contribution increase.
5. Recommendation preview calculates the current and simulated projections without creating a scenario, snapshot or budget row. Contribution recommendations are constrained by the available cash-flow margin, deferred until temporary commitments recover when needed, accept amount/date overrides in preview and simulation, and are omitted when the proposed event produces no projection change. Simulation creates a draft `Scenario` linked through `source_recommendation`; the recommendation becomes accepted only when that scenario is incorporated.
6. `MonthlyClosePlanService` is invoked after monthly-close finalization. It is a no-op when the user has no financial plan and logs failures without breaking the monthly-close lifecycle.
7. Monthly-close plan impact exposes at most two open findings and one open recommendation. Projected-year deltas are only communicated when the rounded year change is material (`abs(delta) >= 1`).
8. The plan engine has one active fiscal-year window: the current natural year, resolved by `plan_fiscal_year()`. Foundations, structural income, and budget-based contributions never aggregate rows from different fiscal years.
9. Structural income excludes one-off rows. One-off income is not converted into recurring labour income or capital automatically in the MVP; future capital effects require an explicit plan event.
10. Structural labour income stops at `FinancialPlan.target_date`, the date when work is expected to become optional. Pension starts independently on each adult's configurable `pension_start_date`; age 67 is only the initial default.
11. Expense inputs use one exhaustive role-based classifier shared by foundations and projection: operating, temporary commitment, contribution, asset purchase, tax/other, or unclassifiable. Unknown values are surfaced through data quality instead of disappearing silently.
12. Scenario contributions carry `monthly_contribution_destination=productive|security|debt`; only productive contributions compound as productive capital.

## Import Traceability And Accounting API
1. The old ad-hoc MoneyWiz CSV importer has been retired from the public Core API.
2. Imported accounting rows remain traceable through `LedgerTransaction.origin`, `import_source` and `import_fingerprint`; consolidated imported rows are no longer treated as disposable cleanup data.
3. Portable data import/export remains the supported whole-dataset migration path.
4. The accounting movement contract supports bidirectional investment flow with explicit direction (`inflow` / `outflow`).
5. Quick-entry investment payloads support optional manual realized metadata (`realized_cost_basis`, `realized_gain_loss`) without enforcing automatic PnL calculation in this phase.
6. The accounting timeline API exposes a daily consolidated balance series for active ledger accounts:
   - `GET /api/accounting/transactions/daily-balance-series/?date_from=YYYY-MM-DD&date_to=YYYY-MM-DD&status=posted|draft`
   - optional `account_ids=1,2,3` scopes the series to validated active asset/liability accounts
7. Transaction lists expose the calculated `needs_review` classification signal, accept `review_state=needs_review|reviewed`, and return a filtered `needs_review_count` for operational review queues.

## Market Data Layer
1. External market datasets are synchronized by a dedicated worker service: `market_data_sync`.
2. The canonical sync command is `python manage.py sync_market_data --datasets fx inflation instrument_prices --mode reconcile|refresh`.
3. Core exposes a manual admin trigger endpoint for sync retries from UI: `POST /api/core/market-data/sync/` (defaults to `inflation` in `reconcile` mode).
4. Persisted datasets in Core are:
   - `FxRate` (daily FX and supported crypto crosses)
   - `InflationIndex` (monthly IPC national + CCAA)
   - `InstrumentPrice` (daily closes for confirmed portfolio mappings)
5. Sync coverage and operational status are tracked in `MarketDataSyncState`.
6. Domain consumers (for example `net_worth`) read only persisted data from Core; they do not call external providers.
7. Core exposes an authenticated conversion endpoint `GET /api/core/fx/convert/?amount=&from=&to=&date=` (service `convert_currency_detailed`). It preserves crypto precision (up to 8 decimals, unlike `convert_currency` which quantizes to 2), resolves the rate for the requested date (direct/inverse/triangulation), and on a miss triggers a targeted on-demand sync via `market_data` before falling back to the nearest earlier quote. The response reports `{ converted, rate, rate_date, resolution: same|exact|synced|fallback }`. `POST /api/core/fx/refresh/` accepts `{ from, to }` for any authenticated user and forces a provider refresh of that pair for today; it never exposes the broad admin market-data trigger.

## Monthly Close Data Model

`MonthlyClose` (app `budget`) is a lifecycle wrapper over the three monthly checkin models:
- `AnnualIncomeMonthlyCheckin` (budget)
- `AnnualExpenseMonthlyCheckin` (budget)
- `LiquidityMonthlyCheckin` (net_worth)

For liquidity rows covered by accounting ledger, monthly close uses ledger as default execution source. A user can create a manual liquidity checkin for the same month/asset to temporarily override ledger for reconciliation purposes; deleting that checkin restores ledger as source.

The liquidity monthly summary reports the monthly close perimeter: active cash assets plus interest-bearing investment assets (currently crowdlending, real-estate crowdfunding, and any investment asset with positive TAE) minus active credit-card liabilities. The existing `planned_total`, `executed_total`, and `deviation_total` fields are net perimeter totals so the monthly-close residual compares income/expense execution against the same position that includes card spending as short-term debt and passive income retained in scoped non-cash assets. The payload also exposes gross asset and liquid-liability totals (`gross_asset_*`, `liquid_liability_*`) and emits liability rows with `row_type=liability`. Asset rows include `annual_interest_tae` so clients can classify remunerated liquidity by actual expected interest instead of institution names. Liability rows use ledger/effective liability balance by default and can be manually adjusted through a month-end `LiabilityValuation` with `source=manual_checkpoint`. Expenses that move value into an asset already inside the close perimeter are exposed as `perimeter_internal_expense_total` and treated as internal movements for residual calculation. Posted `adjustment` entries on accounts within that perimeter are exposed by the monthly-close state as `liquidity_adjustments`; their signed total is included in expected liquidity before calculating the residual, so only unexplained cash remains as residual. Adjustments outside the perimeter do not affect the monthly close.

The monthly-close state also exposes `financial_result`, a role-aware reading of the period outcome. Its savings rate uses eligible income (excluding asset sales) and net savings: retained cash plus `savings`/`investment` contributions, wealth formation and debt-principal repayments. For ledger-backed entries, the account debited is authoritative: a debit on a liability account is principal and therefore formation/debt reduction, while a debit on an expense account in that same payment is interest or cost. This keeps mixed mortgage payments from treating principal as living expense. Manual check-ins retain their explicit `asset_purchase` role because they have no ledger account to inspect. The payload preserves `financial_savings` as the retained-cash subtotal and exposes `net_savings`, `real_estate_formation`, `tangible_asset_purchases` and `debt_principal_repayment` as the composition of the rate. This result is independent from the reconciliation residual, whose only purpose is to explain whether observed liquidity matches the ledger.

Each `MonthlyClose` is unique per `(user, fiscal_year, month)`. Lifecycle: `draft → finalized → locked`, with reopening (`finalized → draft`). Finalization freezes the opening liquidity, expected closing liquidity, observed closing liquidity and accepted residual. The observed close becomes the opening boundary for the next month, so an accepted residual is contained in its own period. Reopening a finalized month invalidates every later finalized close; reopening is rejected when the chain contains a locked close or a settlement already applied to the ledger. The three checkin models now support status `estimated` to distinguish algorithmically suggested distributions from manually entered data.

Key services in `budget/services_monthly_close.py`:
- `compute_monthly_close_state` — orchestrates the 3 summary builders, detects coverage, computes delta liquidity, generates suggestions
- `compute_smart_distribution` — proportional distribution of residual net cashflow across uncovered entries
- `apply_distribution_to_checkins` — persists suggestions as checkins with `status=estimated`
- `finalize_monthly_close / reopen_monthly_close / lock_monthly_close` — lifecycle transitions with `select_for_update`
- `compute_monthly_close_settlement` — per-member economic position, next-month targets and transfer preview
- `apply_settlement_recommendation / reconcile_settlement_recommendation` — idempotent transfer materialization and conservative linking

Checkin writes (create + update) in `budget/views.py` and `net_worth/views.py` are blocked with `403` if a `MonthlyClose` with status `finalized` or `locked` exists for that period.

## Related Documents
1. `../../README.md`
2. `../../CONTRIBUTING.md`
3. `../../RELEASING.md`
4. `accounting-movements-architecture.md`
5. `../operations/dev-setup.md`
6. `../roadmap/community-roadmap.md`
7. `../roadmap/terminados/backend-refactor-roadmap.md`
