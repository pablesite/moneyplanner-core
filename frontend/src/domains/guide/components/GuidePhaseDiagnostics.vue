<script setup lang="ts">
type SummaryCard = {
  id: string;
  label: string;
  valueText: string;
  valueTone?: 'neutral' | 'positive' | 'negative' | 'warning';
  metaText?: string;
};

type SummarySection = {
  id: string;
  title: string;
  description?: string;
  columns: 2 | 4;
  cards: SummaryCard[];
};

type ScoreKpi = {
  id: string;
  label: string;
  valueText: string;
  hint: string;
};

type InfoCard = {
  id: string;
  title: string;
  description: string;
  kpis: ScoreKpi[];
};

const props = defineProps<{
  isCashFlowPhase: boolean;
  cashFlowContextSummarySections: SummarySection[];
  extraordinaryEventGroupOptions: string[];
  selectedExtraordinaryEventGroupLabel: string;
  selectedExtraordinaryEventGroup: string;
  selectExtraordinaryEventGroup: (eventGroup: string, event: MouseEvent) => void;
  phase2DistributionInfoCards: InfoCard[];
}>();

void props;
</script>

<template>
  <details v-if="isCashFlowPhase" class="ui-guide-context-details">
    <summary class="ui-guide-context-summary">
      <span class="ui-guide-context-summary-title">Ver contexto completo</span>
      <span class="ui-guide-context-summary-copy">
        Contexto de flujo, asignacion patrimonial y extraordinarios
      </span>
    </summary>

    <div class="ui-guide-context-details-content">
      <div v-if="cashFlowContextSummarySections.length" class="ui-guide-summary-sections">
        <section
          v-for="section in cashFlowContextSummarySections"
          :key="section.id"
          class="ui-guide-summary-section"
        >
          <div class="ui-guide-summary-section-head">
            <div>
              <h3 class="ui-guide-summary-section-title">{{ section.title }}</h3>
              <p v-if="section.description" class="ui-guide-summary-section-copy">
                {{ section.description }}
              </p>
            </div>
            <div
              v-if="section.id === 'cashflow-extraordinary' && extraordinaryEventGroupOptions.length"
              class="ui-guide-section-filter"
            >
              <span class="ui-guide-section-filter-label">Evento</span>
              <details class="ui-select-popover ui-guide-event-filter">
                <summary class="ui-select-popover-trigger ui-guide-event-filter-summary">
                  <span class="ui-select-popover-text ui-guide-event-filter-summary-text">
                    {{ selectedExtraordinaryEventGroupLabel }}
                  </span>
                  <span
                    class="ui-select-popover-caret ui-guide-event-filter-summary-caret"
                    aria-hidden="true"
                    >v</span
                  >
                </summary>
                <div class="ui-select-popover-menu ui-guide-event-filter-menu" role="listbox" aria-label="Evento">
                  <button
                    type="button"
                    class="ui-select-popover-option ui-guide-event-filter-option"
                    :class="{
                      'ui-select-popover-option-active ui-guide-event-filter-option-active':
                        selectedExtraordinaryEventGroup === 'all',
                    }"
                    @click="selectExtraordinaryEventGroup('all', $event)"
                  >
                    Todos los eventos
                  </button>
                  <button
                    v-for="eventGroup in extraordinaryEventGroupOptions"
                    :key="eventGroup"
                    type="button"
                    class="ui-select-popover-option ui-guide-event-filter-option"
                    :class="{
                      'ui-select-popover-option-active ui-guide-event-filter-option-active':
                        selectedExtraordinaryEventGroup === eventGroup,
                    }"
                    @click="selectExtraordinaryEventGroup(eventGroup, $event)"
                  >
                    {{ eventGroup }}
                  </button>
                </div>
              </details>
            </div>
          </div>
          <div class="ui-guide-summary-grid" :class="`ui-guide-summary-grid-cols-${section.columns}`">
            <article v-for="summaryCard in section.cards" :key="summaryCard.id" class="ui-guide-summary-card">
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
        </section>
      </div>

      <div
        v-if="phase2DistributionInfoCards.length"
        class="ui-guide-score-grid ui-guide-score-grid-cols-1 ui-guide-context-score-grid"
      >
        <article v-for="card in phase2DistributionInfoCards" :key="card.id" class="ui-guide-score-card">
          <div class="ui-guide-score-card-head">
            <h3 class="ui-guide-score-card-title">{{ card.title }}</h3>
          </div>
          <p class="ui-guide-score-card-copy">{{ card.description }}</p>
          <div class="ui-guide-score-kpi-list">
            <div v-for="kpi in card.kpis" :key="kpi.id" class="ui-guide-score-kpi">
              <div class="ui-guide-score-kpi-head">
                <span>{{ kpi.label }}</span>
                <strong class="ui-guide-score-kpi-value">{{ kpi.valueText }}</strong>
              </div>
              <div class="ui-guide-score-kpi-hint">{{ kpi.hint }}</div>
            </div>
          </div>
        </article>
      </div>
    </div>
  </details>
</template>
