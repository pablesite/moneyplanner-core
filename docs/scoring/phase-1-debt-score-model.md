# Phase 1 Debt Score Model

## Objective
Document the current `Deuda` score (`0..100`) used in the financial guide for phase 1.

## Current product location
1. The score belongs to `Guia financiera`, phase 1.
2. It is not a standalone score in `Patrimonio`.
3. It evaluates debt quality, debt cost, and debt structure.

## Score range
1. Final range: `0..100`
2. Best state: `100`
3. Worst state: `0`

## Current structure
The phase 1 score is built from two blocks:

1. `Coste y visibilidad de deuda`
2. `Riesgo estructural de deuda`

Each block contributes 50% to the global phase score.

## Block 1: Coste y visibilidad de deuda
Indicators:

1. `Max liability TAE`
2. `Weighted liability TAE`
3. `Debt payment / recurring income`

Current aggregation:

```text
phase1DebtCostScore =
  weightedScore(
    linearScoreDecreasing(maxLiabilityTaePct, 0.5, 10) * 0.4,
    linearScoreDecreasing(weightedLiabilityTaePct, 0.5, 10) * 0.4,
    debtPaymentScore * 0.2
  )
```

Where:

```text
debtPaymentScore =
  100 if no monthly payment inputs exist at all
  otherwise linearScoreDecreasing(debtPaymentToIncome, 0.15, 0.6)
```

## Block 2: Riesgo estructural de deuda
Indicators:

1. `% deuda sin respaldo / pasivos`
2. `Concentracion top pasivo`
3. `% deuda con TAE alta`

Current aggregation:

```text
phase1DebtRiskScore =
  weightedScore(
    linearScoreDecreasing(unbackedDebtToLiabilities, 0.01, 0.5) * 0.4,
    linearScoreDecreasing(topLiabilityShare, 0.25, 0.95) * 0.3,
    linearScoreDecreasing(highInterestDebtShare, 0.05, 0.6) * 0.3
  )
```

## Global score

```text
phase1GlobalScore =
  weightedScore(
    phase1DebtCostScore * 0.5,
    phase1DebtRiskScore * 0.5
  )
```

## Interpretation
1. Lower TAE improves the score.
2. Lower debt-payment pressure improves the score.
3. Less unbacked debt improves the score.
4. Less concentration in one liability improves the score.
5. Lower exposure to expensive debt improves the score.

## Important implementation note
1. Missing monthly payment inputs do not automatically destroy the score.
2. If no payment inputs exist at all, that sub-score is currently treated as `100`.
3. The phase detail view still marks partial payment-input coverage as incomplete data.

## Implementation reference
Implemented in:

1. `frontend/src/domains/guide/phaseDiagnostics.ts`
2. `frontend/src/views/GuidePhaseDetailView.vue`
3. `frontend/src/views/HomeView.vue`
4. `frontend/src/domains/guide/phaseDiagnostics.ts`
5. `frontend/src/views/GuidePhaseDetailView.vue`
6. `frontend/src/views/HomeView.vue`
