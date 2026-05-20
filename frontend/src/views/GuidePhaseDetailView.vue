<script setup lang="ts">
import GuidePhaseDiagnostics from '@/domains/guide/components/GuidePhaseDiagnostics.vue';
import GuidePhaseProgress from '@/domains/guide/components/GuidePhaseProgress.vue';
import GuidePhaseSummary from '@/domains/guide/components/GuidePhaseSummary.vue';
import { guidePhases, useGuidePhaseDetail } from '@/domains/guide';

const {
  store,
  formatNumber,
  selectedExtraordinaryEventGroup,
  phase,
  isDebtPhase,
  isCashFlowPhase,
  isEmergencyFundPhase,
  isNetWorthHealthPhase,
  hasDiagnosticPhase,
  phaseQuickActions,
  phaseDiagnosticCopy,
  globalScoreValue,
  globalToneValue,
  globalLabelValue,
  scoreCards,
  summaryCards,
  cashFlowHeroSummaryCards,
  cashFlowContextSummarySections,
  cashFlowDistortionWarning,
  phase2DistributionInfoCards,
  phaseDetailTo,
  selectedExtraordinaryEventGroupLabel,
  extraordinaryEventGroupOptions,
  selectExtraordinaryEventGroup,
} = useGuidePhaseDetail('core');

void [
  GuidePhaseDiagnostics,
  GuidePhaseProgress,
  GuidePhaseSummary,
  store,
  formatNumber,
  selectedExtraordinaryEventGroup,
  phase,
  isDebtPhase,
  isCashFlowPhase,
  isEmergencyFundPhase,
  isNetWorthHealthPhase,
  hasDiagnosticPhase,
  phaseQuickActions,
  phaseDiagnosticCopy,
  globalScoreValue,
  globalToneValue,
  globalLabelValue,
  scoreCards,
  summaryCards,
  cashFlowHeroSummaryCards,
  cashFlowContextSummarySections,
  cashFlowDistortionWarning,
  phase2DistributionInfoCards,
  phaseDetailTo,
  selectedExtraordinaryEventGroupLabel,
  extraordinaryEventGroupOptions,
  selectExtraordinaryEventGroup,
];
</script>

<template>
  <div class="container ui-page-shell">
    <GuidePhaseProgress
      :guide-phases="guidePhases"
      :phase="phase"
      :phase-quick-actions="phaseQuickActions"
      :phase-diagnostic-copy="phaseDiagnosticCopy"
      :phase-detail-to="phaseDetailTo"
    />

    <section v-if="!phase" class="ui-section-card ui-section-card-padded">
      <p class="ui-section-subtitle">La fase seleccionada no existe en la guia actual.</p>
    </section>

    <section v-else-if="!hasDiagnosticPhase" class="ui-section-card ui-section-card-padded">
      <div class="ui-section-head">
        <div class="ui-section-copy">
          <h2 class="ui-section-title">Detalle en construccion</h2>
          <p class="ui-section-subtitle">
            Esta fase ya tiene su contexto funcional, pero el diagnostico detallado se publicara en
            siguientes entregas del roadmap.
          </p>
        </div>
      </div>
      <ul class="list">
        <li>Objetivo: {{ phase.objective }}</li>
        <li>Foco operativo: {{ phase.focus }}</li>
        <li>Prerrequisito: completar antes la fase activa en Guía.</li>
      </ul>
    </section>

    <section v-else class="ui-section-card ui-guide-score-panel">
      <GuidePhaseSummary
        :is-cash-flow-phase="isCashFlowPhase"
        :cash-flow-hero-summary-cards="cashFlowHeroSummaryCards"
        :summary-cards="summaryCards"
        :cash-flow-distortion-warning="cashFlowDistortionWarning"
        :global-label-value="globalLabelValue"
        :global-score-value="globalScoreValue"
        :global-tone-value="globalToneValue"
        :score-cards="scoreCards"
        :format-number="formatNumber"
      />

      <GuidePhaseDiagnostics
        :is-cash-flow-phase="isCashFlowPhase"
        :cash-flow-context-summary-sections="cashFlowContextSummarySections"
        :extraordinary-event-group-options="extraordinaryEventGroupOptions"
        :selected-extraordinary-event-group-label="selectedExtraordinaryEventGroupLabel"
        :selected-extraordinary-event-group="selectedExtraordinaryEventGroup"
        :select-extraordinary-event-group="selectExtraordinaryEventGroup"
        :phase2-distribution-info-cards="phase2DistributionInfoCards"
      />

      <div v-if="store.loading" class="ui-state-block ui-state-loading">
        Cargando diagnostico...
      </div>
      <div v-else-if="store.error" class="ui-state-block ui-state-error" role="alert">
        {{ store.error }}
      </div>
    </section>
  </div>
</template>
