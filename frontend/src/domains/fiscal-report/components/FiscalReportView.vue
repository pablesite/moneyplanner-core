<script setup lang="ts">
import { computed } from 'vue';
import FiscalCapitalMobiliarioTable from './FiscalCapitalMobiliarioTable.vue';
import FiscalBotResultsTable from './FiscalBotResultsTable.vue';
import FiscalFuturesTable from './FiscalFuturesTable.vue';
import FiscalGananciasPerdidaTable from './FiscalGananciasPerdidaTable.vue';
import FiscalReportSummary from './FiscalReportSummary.vue';
import FiscalAvisos from './FiscalAvisos.vue';
import FiscalDataSourcesBadge from './FiscalDataSourcesBadge.vue';
import type { FiscalReportPayload } from '@/domains/fiscal-report/api';

const props = defineProps<{
  report: FiscalReportPayload | null;
  loading: boolean;
  error: string | null;
  selectedYear: number;
}>();

const emit = defineEmits<{
  generate: [year: number];
  updateYear: [year: number];
}>();

const availableYears = computed(() => {
  const current = new Date().getFullYear();
  return Array.from({ length: 6 }, (_, index) => current - index);
});

function onYearChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  emit('updateYear', Number(target.value));
}
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h2 class="ui-section-title">Informe fiscal anual</h2>
        <p class="ui-section-subtitle">Genera y revisa las casillas 029/332.</p>
      </div>
      <div class="ui-section-actions">
        <select
          class="select fiscal-year-select"
          :value="props.selectedYear"
          @change="onYearChange"
        >
          <option v-for="year in availableYears" :key="year" :value="year">{{ year }}</option>
        </select>
        <button
          class="btn btn-primary"
          type="button"
          :disabled="props.loading"
          @click="emit('generate', props.selectedYear)"
        >
          {{ props.loading ? 'Generando...' : 'Generar informe' }}
        </button>
      </div>
    </header>
  </section>

  <div v-if="props.error" class="ui-state-block ui-state-error fiscal-state">{{ props.error }}</div>
  <div v-else-if="props.loading" class="ui-state-block ui-state-loading fiscal-state">
    Generando informe fiscal...
  </div>
  <div v-else-if="!props.report" class="ui-state-block ui-state-empty fiscal-state">
    Aun no hay informe cargado. Selecciona año y pulsa "Generar informe".
  </div>

  <div v-else class="fiscal-report-stack">
    <FiscalDataSourcesBadge :data-sources="props.report.data_sources" />
    <FiscalReportSummary :report="props.report" />
    <FiscalCapitalMobiliarioTable :rows="props.report.capital_mobiliario" />
    <FiscalGananciasPerdidaTable :rows="props.report.ganancias_perdidas_trades" />
    <FiscalBotResultsTable :rows="props.report.ganancias_perdidas_bots" />
    <FiscalFuturesTable :rows="props.report.ganancias_perdidas_futuros" />
    <FiscalAvisos :avisos="props.report.avisos" />
  </div>
</template>
