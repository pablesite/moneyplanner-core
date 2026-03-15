# Phase 2 Cash Flow Score Model

## Objective
Document the current `Flujo de caja` score (`0..100`) used in the financial guide for phase 2.

## Current product location
1. The score belongs to `Guia financiera`, phase 2.
2. It focuses on recurring cash-flow health first, with annual context as a secondary modifier.

## Score range
1. Final range: `0..100`
2. Best state: `100`
3. Worst state: `0`

## Current structure
The runtime model is a weighted score built from four indicators:

1. `Structural operating ratio`
2. `Committed load ratio`
3. `Temporary commitment ratio`
4. `Total annual cash-flow ratio`

## Inputs
The model distinguishes:

1. recurring income
2. structural operating expense
3. temporary commitments
4. one-off income and expense
5. total annual cash flow

## Global score

```text
phase2GlobalScore =
  weightedScore(
    linearScoreDecreasing(structuralOperatingRatio, 0.5, 1.0) * 0.4,
    linearScoreDecreasing(committedLoadRatio, 0.65, 1.05) * 0.35,
    linearScoreDecreasing(temporaryCommitmentRatio, 0.05, 0.35) * 0.15,
    linearScoreIncreasing(totalAnnualCashFlowRatio, -0.2, 0.2) * 0.1
  )
```

## Reading of the model
1. The main reading is recurring operating tension.
2. Structural cost and current committed load dominate the score.
3. Temporary commitments matter, but with lower weight.
4. Total annual flow is informative and only modestly affects the score.

## Interpretation
1. Lower structural operating burden improves the score.
2. Lower current committed load improves the score.
3. Less dependence on temporary commitments improves the score.
4. A better annual close improves the score.
5. Extraordinary events are contextualized, but should not dominate the main operational diagnosis.

## Important note
The phase detail view also shows informational context that does not fully define the score:

1. savings distribution
2. patrimonial allocation
3. extraordinary-event context

Those views help interpretation, but the global phase score comes from the four weighted indicators above.

## Implementation reference
Implemented in:

1. `frontend/src/domains/guide/phaseDiagnostics.ts`
2. `frontend/src/views/GuidePhaseDetailView.vue`
3. `frontend/src/views/HomeView.vue`
4. `frontend/src/domains/guide/phaseDiagnostics.ts`
5. `frontend/src/views/GuidePhaseDetailView.vue`
6. `frontend/src/views/HomeView.vue`
