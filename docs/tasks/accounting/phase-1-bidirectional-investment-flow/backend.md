# Title
Core accounting backend - phase 1: bidirectional investment flow

## Context
The current accounting model treats investment operations primarily as `investment_purchase`, which is enough for inflows from liquidity into an investment account but not for withdrawals or partial exits back to liquidity. This phase documents the backend redesign needed to support a single investment flow with explicit direction while preserving the current accounting guarantees and legacy compatibility.

## Area
`backend`

## Stack
`core`

## Scope
1. In scope
2. Define a bidirectional investment contract based on one functional flow plus `inflow` / `outflow` direction.
3. Preserve backwards compatibility for `investment_purchase` as a legacy alias of investment inflow.
4. Define the validation and accounting rules for both directions.
5. Define optional realized PnL metadata (`realized_cost_basis`, `realized_gain_loss`) as manual and non-blocking.
6. Define minimum aggregate outputs per investment asset: total inflows, total outflows, net contributed capital.
7. Out of scope
8. Automatic realized PnL calculation.
9. FIFO/LIFO lots, tax logic, or fiscal reporting.
10. Importer heuristics for MoneyWiz.

## Plan
1. Diagnosis
2. Review the current quick-entry payload and transaction serialization for `investment_purchase`.
3. Identify every read path that currently infers investment semantics from movement type or sign.
4. Change implementation
5. Extend the backend contract so investment movements carry explicit direction (`inflow`, `outflow`) under a single conceptual investment flow.
6. Keep `investment_purchase` accepted during the transition and normalize it internally to investment inflow.
7. Define balanced-entry rules:
8. `inflow`: liquidity account credited, investment account debited.
9. `outflow`: investment account credited, liquidity account debited.
10. Store optional realized PnL metadata without making it mandatory for saves or historical edits.
11. Extend backend summaries and position-level accounting readers to expose inflow total, outflow total, and net contributed capital per investment asset.
12. Validation
13. Cover quick-entry create/edit flows for both directions and compatibility with legacy `investment_purchase`.
14. Cover aggregates and serialization for inflow/outflow/net contributed fields.

## Validation
- `docker compose -f core/docker-compose.yml exec backend ruff check .`
- `docker compose -f core/docker-compose.yml exec backend ruff format --check .`
- `docker compose -f core/docker-compose.yml exec backend mypy .`
- `docker compose -f core/docker-compose.yml exec backend python manage.py test accounting net_worth`

## Required Documentation Updates
- [ ] `core/docs/architecture/accounting-movements-architecture.md` - document the bidirectional investment flow and direction semantics.
- [ ] `core/docs/architecture/architecture.md` - update public contract notes if quick-entry payloads or serialized movement fields change.
- [ ] `core/docs/project-status.md` - reflect this phase as an available agent task and later mark progress/closure.

## Risks
1. Breaking existing `investment_purchase` writers or readers if compatibility is incomplete.
2. Mixing accounting semantics with transfer semantics and losing the analytical meaning of investment exits.
3. Exposing optional realized PnL fields too early as if they were fully computed values. Mitigation: mark them as manual metadata only in this phase.

## Completion Criteria
- [ ] All validation commands pass
- [ ] All required documentation updates done
- [ ] Spec moved to `terminados/`
- [ ] Commit created (Conventional Commits)
