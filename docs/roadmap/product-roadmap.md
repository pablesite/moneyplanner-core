# Product Roadmap

Product evolution plan by module. Captures pending work, improvements, and future lines for each Core functional area.

Conventions:
- `(Shared roadmap)` — item that also applies to, or must be coordinated with, Core roadmap.
- `(Private - Future)` — lower-priority item linked to family/ownership private workflows.
- `~~strikethrough~~` — resolved or discarded.

---

## NET WORTH

### For v1

- ✅ **Full review of create/edit asset and liability modals.** Visual consistency, validations, and flow reviewed; module v1 functionally closed.

### For v2

- **Onboarding assistant for easier asset input.** Ultra-simple flow to add assets, available anytime from the view (not only at first-time onboarding).

---

## BUDGET

- ✅ Phase 1 migration completed (2026-03-20): annual income/expense forms integrated into Budget view.
- ✅ Phase 2 integration completed (2026-03-20): data input and category visualization unified in a single contextual budget flow.
- ✅ Budget expense <-> monthly close <-> accounting movements connection completed.
- ✅ Monthly executed-evolution visual style reviewed.
- ✅ Financial status interpretation simplified.
- ✅ General UX improved (progress bars, budget status).
- ✅ v1 closeout applied and manually validated (2026-05-14): monthly summaries as canonical contract for bars/coverage, ledger precedence over manual check-ins, persistent backend errors inside line modals, and header aligned with Net Worth.

### For v2

- **Annual budget review assistant.** Automatically detect recurring deviations and propose category/subcategory adjustments with manual confirmation.

---

## MONTHLY / YEARLY CLOSE

> Dual-mode backend implemented (2026-03-19). Frontend integrated (2026-03-19) — spec: `core/docs/tasks/monthly-close/terminados/dual-mode-frontend.md`. v1 manual review completed (2026-05-14).

### Close modes — decisions made
- **No explicit mode selector.** The system automatically detects coverage (ledger / check-in / none) and adapts displayed data and suggestions.
- Three user profiles served by one adaptive flow:
  - **Power user:** records movements -> close = verification + sign-off
  - **Casual user:** provides bank balances -> system suggests proportional distribution over budget
  - **Hybrid user:** records only some movements -> system fills gaps
- `MonthlyClose` is the lifecycle wrapper around existing check-ins. Lifecycle: `DRAFT -> FINALIZED -> LOCKED`, with reopen (`FINALIZED -> DRAFT`).
- `estimated` status added to all three check-in models to distinguish algorithmic suggestions from manual data.

### Smart distribution algorithm
- Uses budget as prior; subtracts known movements (ledger + existing check-ins); distributes residual proportionally across uncovered entries.
- If liquidity data exists: residual = liquidity_delta - (known_income - known_expense). If not: uses budgeted amount.

### Movements integration
- Close detail view auto-fills from ledger and existing check-ins.
- Then user can adjust manually or accept suggestions (`PATCH accept_suggestions=true`).

### API (implemented)
- `GET /api/budget/monthly-close/{year}/{month}/` — complete state + suggestions
- `PATCH /api/budget/monthly-close/{year}/{month}/` — update notes / accept suggestions
- `POST /api/budget/monthly-close/{year}/{month}/finalize/` — DRAFT -> FINALIZED
- `POST /api/budget/monthly-close/{year}/{month}/reopen/` — FINALIZED -> DRAFT
- `POST /api/budget/monthly-close/{year}/{month}/lock/` — FINALIZED -> LOCKED

### Frontend integration ✅
- Unified fetch (`getMonthlyClose`) in close mode; `types.ts` + `api.ts` in budget domain.
- Smart distribution: inputs prefilled with backend suggestions for uncovered rows.
- UI lifecycle: status badge (draft/finalized/locked), finalize/reopen/lock buttons in ResultSection.
- Locked state: inputs disabled with info banner when FINALIZED/LOCKED.
- "Estimated" badge for check-ins with `estimated` status.
- Core <-> Core verification completed.

### Result view
- ✅ Reconciliation bridge alignment fixed (CSS subgrid, 2026-05-20).
- Pending simplification: there are still two reconciliation blocks with repeated data; reduce duplication.
- Show only relevant insights; add explainable charts (executed income/expense with expandable detail).

### Liquidity perimeter
- ✅ Per-account reference now uses previous month's effective balance, not `asset.amount` (2026-05-20).

### Yearly close
- ⛔ Discarded — monthly close is sufficient for v1.

### Ownership transfers on close
- ✅ **Core v1 engine implemented.** Canonical plan:
  `core/docs/tasks/monthly-close-settlement/README.md` + `spec.md`.
- Version 1 resolves fixed 50/50 and dynamic income-weighted ownership, reserves the next month's
  recurring obligations in compatible accounts, separates physical wallets from member
  compensations, and recommends transfers without creating ledger movements.
- Version 2 materializes accepted recommendations as idempotent, auditable ledger transfers.
- The feature is opt-in and disabled by default; individual users, common-pool households and
  existing close flows remain unchanged until explicitly configured.
- SaaS configuration and result presentation remain in phases 4-5; automatic ledger materialization
  remains version 2.

---

## ACCOUNTING MODULE

> ✅ **Manual review completed (user) on 2026-03-17.** Fine-grained accounting adjustments will be validated during importer implementation/testing.

### For v1

- ✅ **Operational account tracker review** — 106/106 accounts reviewed (2026-05-20). Tracker: `core/docs/operations/movements-user1-review-tracker.md`.
- ✅ **Category/subcategory re-review** — completed together with tracker.
- ✅ **Header update** — aligned with Net Worth style.
- ✅ **View body style review** — closed.

### For v2

- **Fast-entry UX:** simple movement entry flow, ultra-light banking-app-like form. Optionally exposed as quick assistant or conversational agent (four key inputs -> done).

### Data import

- ✅ Ad-hoc MoneyWiz importer removed before production.
- ✅ Imported movement traceability is preserved in accounting via `origin`, `import_source`, and `import_fingerprint`.
- ✅ Portable import remains the supported path to move/copy datasets between instances.

---

## FX RATES AND INFLATION

- `(Shared roadmap)` Add support for additional currencies as needed.

---

## FINANCIAL COACH

Coach phases 1-4 are functional. v1 decisions:

- ~~Coach bars were not rendered in Core frontend~~ (resolved)
- ✅ **Simplified v1 navigation** (2026-05-20): `/` redirects to `/patrimonio`; guide at `/guia` and `/guia/fases/:id`. Contextual phase quick actions already existed. Deeper coach <-> product integration is parked for v2.
- ✅ **Phase 5 (Financial Independence) removed** — will return once an investment portfolio module with real data exists.

### For v2
- Smooth coach <-> modules integration: jump from a recommendation directly to the exact module point without losing context.

---

## DATA INPUT MODULE

- ✅ `/introduccion-datos` module/route removed (2026-03-20).
- Applied relocation:
  - Annual income/expense forms -> Budget.
  - Asset/liability-related inputs -> Net Worth.
  - Portable data (export/import/replace) -> Account (`/account`).

---

## DESIGN AND USER EXPERIENCE

### Unified design system (critical for production)
- ✅ Foundation completed (2026-05-20): 22 steps closed in `core/frontend/src/styles/app.css` and canonical views. Semantic tokens for color/layout/radius/shadow/state/base controls applied; `ui-pro-*` layer removed. See `core/docs/frontend/design-system.md`.
- ✅ Coherent design system applied: colors, typography, spacing, and base components.
- ✅ Views unified under a common system.
- ✅ Visual quality raised to production baseline.
- Incremental per-view polish continues as needed.

### Cross-cutting UX
- Simplify data input flows.
- Improve navigation across modules.
- Reduce general friction for end users.

---

## AUTHENTICATION AND USER MODEL

- Review complete login flow (Core).
- Validate users/families/asset-liability ownership system.
- Verify permissions and security.
- Full real-flow tests (signup, login, shared ownership, etc.).

---

## DATA IMPORT

- Keep portable import/export as supported flow.
- Do not reintroduce vendor-specific ad-hoc importers unless explicitly decided at product level.

---

## RESIDUAL LEGACY

Living inventory of compatibility pieces that still exist after removing active MoneyWiz import, `delete-imported`, `accounting/services.py`, `sync_fx_rates`, and generated `.js` artifacts. Not all legacy is waste: some pieces protect historical datasets and data portability.

### Pending

- ✅ **`net_worth.services.py` — external import removed (2026-05-20).** `get_base_currency_for_user` moved to `accounts/services.py`; `get_financed_asset_queryset_for_user` added to `services_assets_core.py`; `_serialize_money` moved to `services_liquidity.py`. `services.py` now re-exports for internal consumers and mocks; `portable_data.py` no longer imports from this module. No active external consumers.

- ✅ **`compat.*` in capabilities — removed (2026-05-20).** `AppCapabilitiesCompat`, `buildCompat`, and `withCompat` removed. `canUsePeople()`/`canUseOwnership()` now rely directly on `core.*`/`premium.*`. Four direct consumers of `capabilities.people` migrated to `canUsePeople()` in both Core.

### Removed or clarified

- ✅ **Data Input absorption into Budget — complete.** No remaining routes, domains, views, or CSS named `data-input`; `core.dataInput` removed from capabilities.

- ✅ **Legacy periodic-contribution fields in Net Worth — removed (2026-05-19).** Migration `net_worth/0039` moved data to `contribution_intervals`; migration `net_worth/0042` removed scalar fields (`monthly_contribution_amount`, `expected_end_date`, `investment_contribution_currency`, `investment_contribution_frequency`, `investment_contribution_mode`). Applied and verified.

- **Budget/check-in fallback — not technical code debt.** Check-in behavior is intentional in dual mode: authoritative when ledger coverage is missing, and ledger takes precedence when coverage exists. Remaining debt is operational: historical months that only have check-in coverage might still lack migrated ledger backing. No code change required.

### Keep for data safety

- **Portable import/export compatibility with legacy bundles.**
  - Current value: protects datasets exported from previous versions, bundles without metadata, and partially migrable historical formats.
  - Decision: keep. This is part of the "no data loss" guarantee.

- **Imported movement traceability.**
  - Current value: preserves `origin`, `import_source`, and `import_fingerprint` to identify movements created by historical imports.
  - Decision: keep. This does not reintroduce MoneyWiz importer or bulk delete for imported rows.

### Historical references

- Archived docs in `core/docs/tasks/**/terminados/` and `core/docs/roadmap/terminados/` may still mention MoneyWiz, `sync_fx_rates`, `accounting/services.py`, or old flows because they describe past decisions. They do not imply active code.

---

## SECURITY

- Code audit: backend vulnerabilities and input validations.
- Dependency audit: third-party libraries and known CVEs.
- Baseline verification: auth, permissions, input sanitization.

---

## REFACTOR AND TECHNICAL DEBT

> Deliberately parked until feature completion and visual redesign are done. Not a priority over product functionality.

### Core — Backend
- Verify import/export functions continue to work correctly.
- General Core backend review: logic cleanup, consistent structure, technical debt removal.

### Core — Frontend
- Move business logic to backend where appropriate.
- Make styles coherent across views (after design-system foundation).
- Improve navigation.
- Review text quality and consistency.

### Core — Frontend
- Keep aligned with Core frontend; only profile administration view should differ.
- Separate Core vs Core code boundaries clearly.

### Core — Backend
- General Core backend review.

### Documentation and operations
- Keep Core documentation updated.
