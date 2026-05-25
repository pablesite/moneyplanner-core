# Title
Core importer QA - phase 2: investment outflows from MoneyWiz

## Context
Investment withdrawals affect balances, movement semantics, and user trust in the import flow. This QA phase documents the functional and technical validation needed before closing the importer adaptation for bidirectional investment flows.

## Area
`qa`

## Stack
`core`

## Scope
1. In scope
2. Validate preview and commit behavior for a representative MoneyWiz withdrawal dataset.
3. Validate that mirrored income rows are no longer created for investment exits.
4. Validate regressions for investment inflows, transfers, and debt payments.
5. Verify whether any later importer UI changes must be mirrored in Core.
6. Out of scope
7. Full portfolio accounting audit.
8. Fiscal correctness of realized gains/losses.

## Plan
1. Diagnosis
2. Prepare a representative CSV with an investment withdrawal from portfolio to liquidity, including the previously observed duplicated-income pattern.
3. Establish baseline balances for the source investment account and target liquidity account before import.
4. Change implementation
5. Run preview and confirm the rows are classified as one investment outflow plus any mirrored row skipped or collapsed.
6. Run commit and confirm there is no double positive impact across both accounts.
7. Re-run import to confirm idempotency and stable preview warnings.
8. Validation
9. Regress classic investment inflow, plain transfer, and debt payment imports.
10. If importer UI changes in a later implementation phase, confirm whether the same user-facing flow must be mirrored in Core.

## Validation
- `docker compose -f core/docker-compose.yml exec backend ruff check .`
- `docker compose -f core/docker-compose.yml exec backend ruff format --check .`
- `docker compose -f core/docker-compose.yml exec backend mypy .`
- `docker compose -f core/docker-compose.yml exec backend python manage.py test accounting net_worth`
- `docker compose -f core/docker-compose.yml exec frontend npm run lint`
- `docker compose -f core/docker-compose.yml exec frontend npm run format:check`
- `docker compose -f core/docker-compose.yml exec frontend npm run typecheck`

## Required Documentation Updates
- [ ] `core/docs/project-status.md` - reflect this phase as an available agent task and later mark progress/closure.

## Risks
1. Preview may look correct while commit still generates wrong account impacts.
2. Existing importer regressions may reappear in transfer or debt mirror logic.
3. Core UX may drift later if the importer modal changes and the mirror is not reviewed explicitly.

## Completion Criteria
- [ ] All validation commands pass
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
