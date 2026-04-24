# Core API Registry

## Broker Integrations (`/api/v1/broker/`)

### Credentials and Sync
1. `POST /api/v1/broker/credentials/`
2. `GET /api/v1/broker/credentials/`
3. `DELETE /api/v1/broker/credentials/{id}/`
4. `POST /api/v1/broker/sync/{id}/`
5. `GET /api/v1/broker/sync/{id}/status/`

### CSV and Fiscal Report
1. `POST /api/v1/broker/csv-import/`
2. `GET /api/v1/broker/fiscal-report/?year=YYYY`
3. `POST /api/v1/broker/manual-cost-basis/`
4. `GET /api/v1/broker/manual-cost-basis/?asset=<ASSET>`
5. `DELETE /api/v1/broker/manual-cost-basis/{id}/`

### Sync Run Drill-Down (Phase 5B)
1. `GET /api/v1/broker/sync-runs/?credential=<id>&year=YYYY`
2. `GET /api/v1/broker/sync-runs/{id}/`
3. `GET /api/v1/broker/trades/?credential=<id>&year=YYYY&source=<...>&symbol=<...>&side=<...>&bot_id=<...>&sync_run=<id>`
4. `GET /api/v1/broker/income-events/?credential=<id>&year=YYYY&source=<...>&sync_run=<id>`
5. `GET /api/v1/broker/bot-results/?credential=<id>&year=YYYY&bot_id=<...>&sync_run=<id>`
6. `GET /api/v1/broker/bot-results/{id}/`

## Notes
1. All endpoints require authenticated user context.
2. Drill-down endpoints are ownership-scoped through `credential.user`.
3. Pagination uses DRF page-number format (`count`, `next`, `previous`, `results`).
4. Fiscal report response uses `schema_version: 2` with trade detail in `ganancias_perdidas_trades[].sales[].matched_lots[]` and typed `gap_reason`.
