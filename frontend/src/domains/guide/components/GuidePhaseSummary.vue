<script setup lang="ts">
import ScoreGradeLabel from './ScoreGradeLabel.vue';
import ScoreHealthBadge from './ScoreHealthBadge.vue';
import ScoreMeterRow from './ScoreMeterRow.vue';

type ScoreKpi = {
  id: string;
  label: string;
  valueText: string;
  score: number | null;
  hint: string;
  detailText?: string;
  incomplete?: boolean;
};

type ScoreCard = {
  id: string;
  title: string;
  score: number;
  description: string;
  kpis: ScoreKpi[];
};

type SummaryCard = {
  id: string;
  label: string;
  valueText: string;
  valueTone?: 'neutral' | 'positive' | 'negative' | 'warning';
  metaText?: string;
};

const props = defineProps<{
  isCashFlowPhase: boolean;
  cashFlowHeroSummaryCards: SummaryCard[];
  summaryCards: SummaryCard[];
  cashFlowDistortionWarning: string | null;
  globalLabelValue: string;
  globalScoreValue: number;
  globalToneValue: 'solid' | 'medium' | 'watch' | 'risk';
  scoreCards: ScoreCard[];
  formatNumber: (value: number, fractionDigits?: number) => string;
}>();

void props;
</script>

<template>
  <div>
    <template v-if="isCashFlowPhase">
      <div class="ui-guide-summary-grid ui-guide-summary-grid-cols-4">
        <article
          v-for="summaryCard in cashFlowHeroSummaryCards"
          :key="summaryCard.id"
          class="ui-guide-summary-card"
        >
          <div class="ui-guide-summary-label">{{ summaryCard.label }}</div>
          <div
            class="ui-guide-summary-value"
            :class="summaryCard.valueTone ? `ui-guide-summary-value-${summaryCard.valueTone}` : ''"
          >
            {{ summaryCard.valueText }}
          </div>
          <div v-if="summaryCard.metaText" class="ui-guide-summary-meta">
            {{ summaryCard.metaText }}
          </div>
        </article>
      </div>
    </template>
    <div v-else class="ui-guide-summary-grid">
      <article
        v-for="summaryCard in summaryCards"
        :key="summaryCard.id"
        class="ui-guide-summary-card"
      >
        <div class="ui-guide-summary-label">{{ summaryCard.label }}</div>
        <div class="ui-guide-summary-value">{{ summaryCard.valueText }}</div>
      </article>
    </div>

    <div v-if="cashFlowDistortionWarning" class="ui-status-line">
      {{ cashFlowDistortionWarning }}
    </div>

    <div class="ui-guide-score-top">
      <ScoreHealthBadge
        :label="globalLabelValue"
        :score="globalScoreValue"
        :tone="globalToneValue"
        :formatted-score="`${formatNumber(globalScoreValue, 0)}%`"
      />
    </div>

    <ScoreMeterRow :score="globalScoreValue" large-grade />

    <div class="ui-guide-score-grid" :class="`ui-guide-score-grid-cols-${scoreCards.length}`">
      <article v-for="card in scoreCards" :key="card.id" class="ui-guide-score-card">
        <div class="ui-guide-score-card-head">
          <h3 class="ui-guide-score-card-title">{{ card.title }}</h3>
          <div class="ui-guide-score-card-value-wrap">
            <ScoreGradeLabel :score="card.score" class="ui-guide-score-card-grade" />
            <div class="ui-guide-score-card-value">{{ formatNumber(card.score, 0) }}%</div>
          </div>
        </div>
        <p class="ui-guide-score-card-copy">{{ card.description }}</p>

        <div class="ui-guide-score-kpi-list">
          <div v-for="kpi in card.kpis" :key="kpi.id" class="ui-guide-score-kpi">
            <div class="ui-guide-score-kpi-head">
              <span>{{ kpi.label }}</span>
              <strong class="ui-guide-score-kpi-value">
                {{ kpi.valueText }}
                <span
                  v-if="kpi.incomplete"
                  class="ui-guide-score-kpi-alert"
                  title="Faltan cuotas por completar"
                  aria-label="Faltan cuotas por completar"
                  >!</span
                >
              </strong>
            </div>
            <ScoreMeterRow
              v-if="kpi.score != null"
              :score="kpi.score"
              row-class="ui-guide-meter-row-kpi"
              track-class="ui-guide-score-kpi-track"
            />
            <div v-else class="ui-guide-score-kpi-pending">Indicador informativo (no puntua)</div>
            <div class="ui-guide-score-kpi-hint">{{ kpi.hint }}</div>
            <div v-if="kpi.detailText" class="ui-guide-score-kpi-hint">{{ kpi.detailText }}</div>
          </div>
        </div>
      </article>
    </div>
  </div>
</template>
