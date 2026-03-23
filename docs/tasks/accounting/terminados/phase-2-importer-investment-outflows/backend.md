# Title
Core importer backend - phase 2: investment outflows from MoneyWiz

## Context
Once the accounting domain supports bidirectional investment flows, the MoneyWiz importer must stop representing investment exits as duplicated income rows or generic transfers without investment meaning. This phase documents the importer adaptation needed to classify portfolio withdrawals and similar exits using the new investment outflow model.

## Area
`backend`

## Stack
`core`

## Scope
1. In scope
2. Detect MoneyWiz patterns that represent investment exits or withdrawals from portfolio accounts back to liquidity.
3. Reclassify those imports to the new investment outflow model instead of creating mirrored `income` rows.
4. Define pairing, de-duplication, and idempotency rules for these mirrored import cases.
5. Keep the scope limited to importer behavior and importer-side payload generation.
6. Out of scope
7. Further redesign of accounting movement semantics.
8. Automatic realized PnL calculation from MoneyWiz data.
9. Broad heuristics unrelated to investment outflow cases.

## Plan
1. Diagnosis
2. Inventory current importer rules for mirrored transfers, investment mirrors, and misclassified `income` rows.
3. Reproduce the known failure mode where a withdrawal is imported as positive movement on both liquidity and investment accounts.
4. Change implementation
5. Add importer rules that collapse known withdrawal mirrors into a single investment outflow operation using the new backend contract.
6. Ensure the importer prefers investment semantics over generic `income` when the pair clearly represents money leaving an investment account and arriving in liquidity.
7. Preserve idempotency for already imported rows and define how legacy duplicated imports are recognized or skipped.
8. Keep pairing rules explicit so they do not accidentally collapse unrelated income rows.
9. Validation
10. Cover preview stats, commit results, created transaction shape, and duplicate-import behavior for withdrawal cases.

## Validation
- `docker compose -f core/docker-compose.yml exec backend ruff check .`
- `docker compose -f core/docker-compose.yml exec backend ruff format --check .`
- `docker compose -f core/docker-compose.yml exec backend mypy .`
- `docker compose -f core/docker-compose.yml exec backend python manage.py test accounting net_worth`

## Required Documentation Updates
- [ ] `core/docs/architecture/architecture.md` - update import API notes if preview/commit payload semantics change.
- [ ] `core/docs/project-status.md` - reflect this phase as an available agent task and later mark progress/closure.

## Risks
1. Over-pairing rows that are actually unrelated income movements.
2. Re-import drift if the new fingerprints do not align with already committed data.
3. Leaving legacy duplicated imports unresolved in existing user datasets. Mitigation: document clearly whether old imports stay manual or get explicit repair rules.

## Completion Criteria
- [ ] All validation commands pass
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
