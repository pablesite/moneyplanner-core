<script setup lang="ts">
import { computed } from 'vue';
import FiscalCapitalMobiliarioTable from './FiscalCapitalMobiliarioTable.vue';
import FiscalFuturesTable from './FiscalFuturesTable.vue';
import FiscalGananciasPerdidaTable from './FiscalGananciasPerdidaTable.vue';
import FiscalReportSummary from './FiscalReportSummary.vue';
import FiscalAvisos from './FiscalAvisos.vue';
import FiscalDataSourcesBadge from './FiscalDataSourcesBadge.vue';
import FiscalExportButton from './FiscalExportButton.vue';
import BotFillsPanel from './BotFillsPanel.vue';
import ManualCostBasisModal from './ManualCostBasisModal.vue';
import { useFiscalReportStore } from '@/domains/fiscal-report/store';
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

const store = useFiscalReportStore();

const availableYears = computed(() => {
  const current = new Date().getFullYear();
  return Array.from({ length: 6 }, (_, index) => current - index);
});

const manualModalAsset = computed(() => store.manualCostBasisAsset ?? '');
const manualModalOpen = computed(() => Boolean(store.manualCostBasisAsset));

function onYearChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  emit('updateYear', Number(target.value));
}

function onManualCostBasis(asset: string) {
  void store.fetchManualCostBases(asset);
}

function onCloseManualModal() {
  store.manualCostBasisAsset = null;
  store.manualCostBases = [];
}

function onCreateManualCostBasis(payload: Parameters<typeof store.createManualCostBasis>[0]) {
  void store.createManualCostBasis(payload);
}

function onDeleteManualCostBasis(rowId: number, asset: string) {
  void store.deleteManualCostBasis(rowId, asset);
}

function onExport(format: 'csv' | 'pdf') {
  void store.downloadFiscalExport(format);
}

function onOpenBotDetail(botResultId: number) {
  void store.fetchBotResultDetail(botResultId);
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
        <FiscalExportButton :loading="store.downloadingExport" @export="onExport" />
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
    <FiscalGananciasPerdidaTable
      :rows="props.report.ganancias_perdidas_trades"
      @manual-cost-basis="onManualCostBasis"
    />
    <BotFillsPanel
      :rows="store.botResultsForYear"
      :report-rows="props.report.ganancias_perdidas_bots"
      :detail-by-id="store.botResultDetailById"
      @open-detail="onOpenBotDetail"
    />
    <FiscalFuturesTable :rows="props.report.ganancias_perdidas_futuros" />
    <FiscalAvisos :avisos="props.report.avisos" />
  </div>

  <ManualCostBasisModal
    :open="manualModalOpen"
    :asset="manualModalAsset"
    :ownership-options="store.ownershipOptions"
    :rows="store.manualCostBases"
    :creating="store.creatingManualCostBasis"
    :deleting-by-id="store.deletingManualCostBasisById"
    @close="onCloseManualModal"
    @submit="onCreateManualCostBasis"
    @remove="onDeleteManualCostBasis"
  />
</template>
