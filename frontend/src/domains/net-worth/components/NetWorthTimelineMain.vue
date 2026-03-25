<script setup lang="ts">
import { NetWorthDeltaChart, NetWorthDonut, NetWorthTimelineChart } from '@/domains/net-worth';
import type { NetWorthTimelineChartPoint } from './NetWorthTimelineChart.vue';

type CategoryType = 'asset' | 'liability';
type TimelinePreset = '1m' | '3m' | '6m' | '1a' | 'all';

type HeroAnalysis = {
  assets: number;
  liabilities: number;
  backedDebt: number;
  unbackedDebt: number;
  netWorth: number;
};

type TimelineRow = {
  date: string;
  label: string;
  value: number;
};

type SelectedPosition = {
  id: number;
} | null;

type AccountingActivityRow = {
  id: number | string;
  date: string;
  description: string;
  sideLabel: string;
  counterpartLabel: string;
  note?: string | null;
  amount: number;
  currency: string;
};

type PositionActivityRow = {
  id: number | string;
  kind: string;
  date: string;
  label: string;
  meta: string;
  note?: string | null;
  amount: number;
};

defineProps<{
  analysis: HeroAnalysis;
  heroUnitLabel: string;
  effectiveCategoryKeys: string[];
  effectiveCategoryLabels: string[];
  effectiveCategoryAssets: number[];
  effectiveCategoryLiabilities: number[];
  effectiveCategoryAssetCounts: number[];
  effectiveCategoryLiabilityCounts: number[];
  selectedTimelineCategory: string | null;
  selectedTimelineCategoryType: CategoryType;
  applyCompositionCategoryFilter: (payload: { key: string; type: CategoryType }) => void;
  handleCompositionAddType: (payload: { type: CategoryType }) => void;
  displayedTimelineLoading: boolean;
  visibleTimelineRows: TimelineRow[];
  selectedPosition: SelectedPosition;
  timelinePresetOptions: readonly TimelinePreset[];
  customTimelineWindow: { start: number; end: number } | null;
  selectedTimelinePreset: TimelinePreset;
  setTimelinePreset: (preset: TimelinePreset) => void;
  timelineRangeCaption: string;
  setTimelineExpanded: (value: boolean) => void;
  timelineChartPoints: NetWorthTimelineChartPoint[];
  displayedTimelineUnit: string;
  timelineSummaryLabel: string;
  displayedTimelineSeriesColor: string;
  timelineYAxisStartsAtZero: boolean;
  formatNumber: (value: number, decimals?: number) => string;
  timelineChartRows: TimelineRow[];
  showAccountingActivityBlock: boolean;
  accountingActivityLoading: boolean;
  accountingActivityYear: number;
  showAccountingActivityNeedsReview: boolean;
  showAccountingActivitySetupGap: boolean;
  accountingActivityError: string | null;
  accountingActivityRows: AccountingActivityRow[];
  positionActivityLoading: boolean;
  positionActivityRows: PositionActivityRow[];
}>();
</script>

<template>
  <div class="ui-pro-panel ui-nw-balance-panel ui-nw-balance-panel-integrated">
    <NetWorthDonut
      :total-assets="analysis.assets"
      :total-liabilities="analysis.liabilities"
      :asset-backed-liabilities="analysis.backedDebt"
      :unbacked-liabilities="analysis.unbackedDebt"
      :net-worth="analysis.netWorth"
      :unit="heroUnitLabel"
      :category-keys="effectiveCategoryKeys"
      :category-labels="effectiveCategoryLabels"
      :category-assets="effectiveCategoryAssets"
      :category-liabilities="effectiveCategoryLiabilities"
      :category-asset-counts="effectiveCategoryAssetCounts"
      :category-liability-counts="effectiveCategoryLiabilityCounts"
      :selected-category-key="selectedTimelineCategory"
      :selected-category-type="selectedTimelineCategoryType"
      :show-chart="false"
      @select-category="applyCompositionCategoryFilter"
      @add-type="handleCompositionAddType"
    />
  </div>

  <div
    v-if="visibleTimelineRows.length === 0 && !displayedTimelineLoading"
    class="subtle"
  >
    {{
      selectedPosition
        ? 'Esta posicion aun no tiene suficientes puntos para construir una serie mensual.'
        : 'Aun no hay datos suficientes para construir la serie temporal.'
    }}
  </div>
  <div v-else class="ui-nw-timeline-main">
    <div class="ui-nw-timeline-body">
      <div class="ui-nw-timeline-toolbar">
        <div class="ui-nw-timeline-range-group" role="group" aria-label="Rango temporal">
          <button
            v-for="preset in timelinePresetOptions"
            :key="preset"
            class="ui-nw-timeline-range-button"
            :class="{
              'ui-nw-timeline-range-button-active':
                customTimelineWindow === null && selectedTimelinePreset === preset,
            }"
            type="button"
            @click="setTimelinePreset(preset)"
          >
            {{ preset }}
          </button>
        </div>

        <div class="ui-nw-timeline-toolbar-actions">
          <span class="ui-nw-timeline-range-caption">{{ timelineRangeCaption }}</span>
          <button
            class="ui-nw-timeline-expand-button"
            type="button"
            @click="setTimelineExpanded(true)"
          >
            Expandir
          </button>
        </div>
      </div>

      <div class="ui-nw-timeline-chart-shell">
        <div v-if="displayedTimelineLoading" class="ui-nw-timeline-loading-overlay">
          <span class="ui-nw-timeline-loading-pill">Actualizando serie...</span>
        </div>
        <NetWorthTimelineChart
          :points="timelineChartPoints"
          :unit="displayedTimelineUnit"
          :series-label="timelineSummaryLabel"
          :series-color="displayedTimelineSeriesColor"
          :y-axis-min-zero="timelineYAxisStartsAtZero"
        />
      </div>

      <NetWorthDeltaChart :rows="timelineChartRows" :unit="displayedTimelineUnit" />

      <div class="ui-nw-timeline-points">
        <div
          v-for="row in timelineChartRows.slice(-6)"
          :key="row.date"
          class="ui-nw-timeline-point"
        >
          <span>{{ row.label }}</span>
          <strong>{{ formatNumber(row.value, 0) }}</strong>
        </div>
      </div>
    </div>

    <div v-if="selectedPosition" class="ui-nw-position-activity">
      <div
        v-if="showAccountingActivityBlock"
        class="ui-nw-position-activity ui-nw-position-activity-accounting"
      >
        <div class="ui-nw-position-activity-head">
          <h3 class="ui-nw-position-activity-title">Actividad contable</h3>
          <span v-if="accountingActivityLoading" class="subtle">Cargando...</span>
          <span v-else class="subtle">Ejercicio {{ accountingActivityYear }}</span>
        </div>
        <div v-if="showAccountingActivityNeedsReview" class="subtle">
          Esta posicion esta en estado <strong>needs_review</strong>: la cuenta contable actual no
          es compatible (usuario, moneda o tipo). Se mantiene fallback legacy hasta corregir el
          enlace.
        </div>
        <div v-else-if="showAccountingActivitySetupGap" class="subtle">
          Esta posicion usa tracking contable pero aun no tiene una cuenta enlazada. Vinculala desde
          editar posicion para derivar saldo y movimientos.
        </div>
        <div v-else-if="accountingActivityError" class="subtle">
          No se pudo cargar la actividad contable: {{ accountingActivityError }}
        </div>
        <div v-else-if="accountingActivityRows.length === 0" class="subtle">
          No hay asientos del ejercicio actual vinculados a esta posicion contable.
        </div>
        <div v-else class="ui-nw-position-activity-list">
          <div
            v-for="row in accountingActivityRows"
            :key="row.id"
            class="ui-nw-position-activity-row ui-nw-position-activity-row-accounting"
          >
            <div class="ui-nw-position-activity-main">
              <strong>{{ row.date }}</strong>
              <span>{{ row.description }}</span>
              <span>{{ row.sideLabel }} | Contrapartida: {{ row.counterpartLabel }}</span>
              <span v-if="row.note">{{ row.note }}</span>
            </div>
            <div class="ui-nw-position-activity-amount">
              {{ formatNumber(row.amount, 2) }} {{ row.currency }}
            </div>
          </div>
        </div>
      </div>

      <div class="ui-nw-position-activity-head">
        <h3 class="ui-nw-position-activity-title">Eventos y checkpoints</h3>
        <span v-if="positionActivityLoading" class="subtle">Cargando...</span>
      </div>
      <div v-if="positionActivityRows.length === 0" class="subtle">
        No hay eventos ni valoraciones manuales registrados para esta posicion.
      </div>
      <div v-else class="ui-nw-position-activity-list">
        <div
          v-for="row in positionActivityRows"
          :key="row.id"
          class="ui-nw-position-activity-row"
          :class="{ 'ui-nw-position-activity-row-valuation': row.kind === 'valuation' }"
        >
          <div class="ui-nw-position-activity-main">
            <strong>{{ row.date }}</strong>
            <span>{{ row.label }} | {{ row.meta }}</span>
            <span v-if="row.note">{{ row.note }}</span>
          </div>
          <div class="ui-nw-position-activity-amount">
            {{ formatNumber(row.amount, 2) }}
          </div>
        </div>
      </div>
    </div>
  </div>
</template>
