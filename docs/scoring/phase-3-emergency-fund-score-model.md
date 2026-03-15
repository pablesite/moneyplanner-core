# Phase 3 Emergency Fund Score Model

## Objective
Document the current `Fondo de emergencia` score (`0..100`) used in the financial guide for phase 3.

## Current product location
1. The score belongs to `Guia financiera`, phase 3.
2. It evaluates both emergency coverage and liquidity quality.

## Score range
1. Final range: `0..100`
2. Best state: `100`
3. Worst state: `0`

## Current structure
The runtime model is built from four indicators:

1. `Months of base expense covered`
2. `Months of current committed expense covered`
3. `% emergency liquidity / assets`
4. `% immediate liquidity / emergency liquidity`

## Global score

```text
phase3GlobalScore =
  weightedScore(
    linearScoreIncreasing(emergencyCoverageMonthsBase, 3, 12) * 0.45,
    linearScoreIncreasing(emergencyCoverageMonthsCommitted, 3, 12) * 0.25,
    linearScoreIncreasing(emergencyLiquidityToAssets, 0.05, 0.3) * 0.15,
    linearScoreIncreasing(immediateLiquidityShareWithinEmergency, 0.4, 0.85) * 0.15
  )
```

## Reading of the model
1. Coverage against essential base expense is the strongest component.
2. Coverage against the current full burden also matters, but slightly less.
3. Liquidity quality is split between weight in total assets and immediate accessibility.

## Interpretation
1. More months of emergency coverage improve the score.
2. Better protection against current committed expense improves the score.
3. More useful liquidity within the balance sheet improves the score.
4. A higher immediate-cash share inside the emergency cushion improves the score.

## Important note
This phase uses useful emergency liquidity, not just any asset labeled as wealth.

The runtime logic distinguishes between:

1. emergency-liquid assets
2. immediate liquidity
3. illiquid assets that should not be treated as part of the emergency cushion

## Implementation reference
Implemented in:

1. `frontend/src/domains/guide/phaseDiagnostics.ts`
2. `frontend/src/views/GuidePhaseDetailView.vue`
3. `frontend/src/views/HomeView.vue`
4. `frontend/src/domains/guide/phaseDiagnostics.ts`
5. `frontend/src/views/GuidePhaseDetailView.vue`
6. `frontend/src/views/HomeView.vue`
