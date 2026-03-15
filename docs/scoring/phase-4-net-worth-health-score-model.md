# Phase 4 Net Worth Health Score Model

## Objective
Document how the current `Salud patrimonial` score (`0..100`) is modeled in the financial guide for phase 4.

This score reflects the quality of the current balance structure, not a time trend.

## Current product location
1. The score belongs to `Guia financiera`, not to the standalone `Patrimonio` view.
2. In the guide it appears as the score for phase 4: `Salud patrimonial`.
3. The `Patrimonio` view exposes the raw KPIs and composition data, but not this synthetic score as a primary UI element.

## Current implementation status
1. The implemented model is score-based, not penalty-based.
2. It uses `linearScoreIncreasing`, `linearScoreDecreasing`, and `weightedScore`.
3. The score is composed from sub-scores grouped into two blocks:
   - `Respaldo patrimonial`
   - `Distribucion del riesgo`
4. The final phase 4 score is the weighted combination of those two blocks.

## Score range
1. Final range: `0..100`
2. Best state: `100`
3. Worst state: `0`

## Current dimensions
The implemented phase 4 model uses 4 practical indicators:

1. `Unbacked debt to assets`
2. `Illiquid assets share`
3. `Top asset concentration`
4. `Diversification index`

## Current structure
### 1) Respaldo patrimonial
Built from:

1. `% deuda sin respaldo / activos`
2. `% activos iliquidos`

Current aggregation:

```text
phase4SupportScore =
  weightedScore(
    unbackedDebtScore * 0.5,
    illiquidScore * 0.5
  )
```

### 2) Distribucion del riesgo
Built from:

1. `Concentracion top activo`
2. `Indice de diversificacion`

Current aggregation:

```text
phase4RiskDistributionScore =
  weightedScore(
    concentrationScore * 0.5,
    diversificationScore * 0.5
  )
```

### 3) Global phase 4 score

```text
phase4GlobalScore =
  weightedScore(
    phase4SupportScore * 0.5,
    phase4RiskDistributionScore * 0.5
  )
```

## Interpretation
1. More unbacked debt reduces the score.
2. More illiquid concentration reduces the score.
3. Strong dependence on one dominant asset reduces the score.
4. Better diversification improves the score.

## Tone mapping in UI
Current phase label mapping:

1. `>= 75`: `solid`
2. `>= 55`: `medium`
3. `>= 35`: `watch`
4. `< 35`: `risk`

Current labels in Spanish:

1. `solid`: `Salud patrimonial solida`
2. `medium`: `Salud patrimonial equilibrada`
3. `watch`: `Salud patrimonial mejorable`
4. `risk`: `Salud patrimonial vulnerable`

## Important note
This document reflects the current implemented logic in the guide, not the older conceptual model based on explicit penalty curves.

That earlier penalty-based model can still be useful as design history or as a future refinement path, but it is not the main runtime model today.

## Implementation reference
Implemented in:

1. `frontend/src/domains/guide/phaseDiagnostics.ts`
2. `frontend/src/views/HomeView.vue`
3. `frontend/src/views/GuidePhaseDetailView.vue`
4. `frontend/src/domains/guide/phaseDiagnostics.ts`
5. `frontend/src/views/HomeView.vue`
6. `frontend/src/views/GuidePhaseDetailView.vue`
