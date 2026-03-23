# Title
Core accounting backend — server-side cursor pagination for transactions

## Context
The `GET /api/accounting/transactions/` endpoint returns all transactions for a user in a single response (11k+ rows in production). This causes multi-second delays on page load. The frontend currently does all filtering (text search, activity kind, account, date range) and pagination (slice-based, 50 per page) client-side.

This task adds cursor-based server-side pagination and server-side filters so that the initial page load fetches only 50 rows and subsequent pages are loaded on demand.

## Area
`backend`

## Stack
`core`

## Scope

### In scope
1. Cursor pagination on the transactions list endpoint using composite cursor `(booking_date, id)`.
2. Server-side filters: `query` (text search), `kind` (activity kind), `account_id`, `date_from`, `date_to`.
3. New `activity_kind` read-only field on the transaction serializer (computed from prefetched entries).
4. Paginated response envelope: `{ results, next_cursor, total_count }`.
5. Composite database index for pagination ordering `(user, -booking_date, -id)`.
6. Backward compatibility: existing `year`, `month`, `status` filters keep working.

### Out of scope
1. Offset-based pagination (cursor-only).
2. Changes to `monthly-summary`, `budget-suggestions`, or `import-moneywiz` endpoints.
3. Changes to `LedgerEntry`, `LedgerAccount` endpoints.
4. Frontend changes (separate spec).

## Plan

### 1. Diagnosis
1. Review `LedgerTransactionViewSet.list()` and `get_queryset()` in `core/backend/accounting/views.py`.
2. Review `LedgerTransactionSerializer` in `core/backend/accounting/serializers.py`.
3. Confirm existing indexes on `LedgerTransaction` in `core/backend/accounting/models.py`.
4. Identify the client-side `getTransactionActivityKind` logic in the frontend composable to replicate server-side.

### 2. Implementation

#### 2.1 Pagination utility (`core/backend/accounting/pagination.py`)
Create a `paginate_transactions(queryset, page_size, cursor)` function:
- Decode cursor: base64 of `{booking_date_iso}:{id}`.
- Apply `WHERE`: `Q(booking_date__lt=cursor_date) | Q(booking_date=cursor_date, id__lt=cursor_id)`.
- Order by `-booking_date, -id`.
- Fetch `page_size + 1` rows; detect `has_more`.
- Encode `next_cursor` from last returned row.
- Compute `total_count` via `queryset.count()`.
- Return `(results, next_cursor | None, total_count)`.

#### 2.2 Activity kind classification (`core/backend/accounting/services.py`)
Add `classify_transaction_activity_kind(transaction) -> str` that mirrors the frontend logic:
- `income`: entries with `flow_family='income'` or `annual_income_entry_id`.
- `expense`: entries with `flow_family='expense'` or `annual_expense_entry_id` (excluding those with `liability_id`).
- `transfer`: 2+ entries on asset-type accounts, no investment/liability entries.
- `investment_purchase`: entry with `asset_id` on an investment-linked account.
- `debt_payment`: entry with `liability_id`.
- `revaluation`: system-origin or revaluation-typed entries.
- Fallback: `other`.

#### 2.3 Serializer update (`core/backend/accounting/serializers.py`)
Add `activity_kind = serializers.SerializerMethodField()` to `LedgerTransactionSerializer`.
The method calls `classify_transaction_activity_kind(obj)` using the prefetched entries.

#### 2.4 Server-side filters (`core/backend/accounting/services.py`)
Add `apply_transaction_list_filters(queryset, params) -> QuerySet`:
- `date_from`: `booking_date__gte`.
- `date_to`: `booking_date__lte`.
- `account_id`: `entries__account_id=X` + `.distinct()`.
- `query`: `Q(description__icontains) | Q(notes__icontains) | Q(entries__account__name__icontains)` + `.distinct()`.
- `kind`: map to queryset filters using `Exists()` subqueries on `LedgerEntry`:
  - `income` → `entries.filter(flow_family='income')` exists.
  - `expense` → `entries.filter(flow_family='expense')` exists.
  - `transfer` → 2+ asset-type entries, no income/expense flow.
  - `investment_purchase` → `entries.filter(asset_id__isnull=False)` exists.
  - `debt_payment` → `entries.filter(liability_id__isnull=False)` exists.
  - `revaluation` → `origin='system'` or equivalent.

#### 2.5 ViewSet update (`core/backend/accounting/views.py`)
Override `list()` on `LedgerTransactionViewSet`:
- Apply existing `year/month/status` filters from `get_queryset()`.
- Call `apply_transaction_list_filters()` with new params.
- Call `paginate_transactions()` with cursor and page_size (default 50, max 200).
- Return `Response({ results, next_cursor, total_count })`.

New query params: `cursor`, `page_size`, `date_from`, `date_to`, `account_id`, `query`, `kind`.

#### 2.6 Database index (`core/backend/accounting/models.py`)
Add composite index:
```python
models.Index(fields=["user", "-booking_date", "-id"], name="acct_tx_user_book_id_desc")
```
Generate and apply migration.

### 3. Validation
Run tests and quality checks.

## Validation
- `docker compose -f core/docker-compose.yml exec backend python manage.py makemigrations --check` (no pending migrations after applying)
- `docker compose -f core/docker-compose.yml exec backend python manage.py migrate`
- `docker compose -f core/docker-compose.yml exec backend ruff check .`
- `docker compose -f core/docker-compose.yml exec backend ruff format --check .`
- `docker compose -f core/docker-compose.yml exec backend mypy .`
- `docker compose -f core/docker-compose.yml exec backend python manage.py test accounting`

## Required Documentation Updates
- [ ] `core/docs/architecture/accounting-movements-architecture.md` — document paginated response envelope, new query params, and `activity_kind` field.
- [ ] `core/docs/project-status.md` — reflect task status.

## Risks
1. **`total_count` performance**: `COUNT(*)` on filtered queryset with 10k+ rows. Mitigation: existing `(user, booking_date)` index makes this fast. If it becomes a bottleneck at much larger scale, make it optional via `include_count` param.
2. **Activity kind filter accuracy**: Queryset-level `kind` filters use `Exists()` subqueries that may not be a 100% exact match to the serializer method for edge cases. Mitigation: the serializer always returns the authoritative `activity_kind` per row, so displayed values are always correct. The filter is "good enough" for practical use.
3. **Breaking existing API consumers**: The list endpoint changes from returning a flat array to a paginated envelope. Mitigation: all known consumers are our own frontend. Coordinate with frontend task.

## Completion Criteria
- [ ] All validation commands pass
- [ ] Cursor pagination works: first page returns 50 results + `next_cursor`
- [ ] `next_cursor` returns next page without overlap or gaps
- [ ] Each server-side filter works individually and in combination
- [ ] `activity_kind` field present on every serialized transaction
- [ ] `total_count` reflects filtered count
- [ ] New composite index applied
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
