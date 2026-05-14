<script setup lang="ts">
import { computed } from 'vue';
import { Doughnut } from 'vue-chartjs';
import {
  Chart as ChartJS,
  ArcElement,
  Tooltip,
  Legend,
  type ChartData,
  type ChartOptions,
  type Plugin,
} from 'chart.js';
import type { AccountingMovementsPageState } from '@/domains/accounting/useAccountingMovementsPage';

ChartJS.register(ArcElement, Tooltip, Legend);

type OwnershipFilterValue = 'all' | number | null;
type OwnershipOption = { value: number | null; label: string };

const props = defineProps<{ page: AccountingMovementsPageState }>();
const state = props.page;

const accountingAssets = computed(() => Math.max(Number(state.accountingAssetsTotal ?? 0), 0));
const accountingLiabilities = computed(() =>
  Math.max(Number(state.accountingLiabilitiesTotal ?? 0), 0),
);

const hasDonutData = computed(
  () => accountingAssets.value + accountingLiabilities.value > Number.EPSILON,
);

const selectedOwnershipFilterLabel = computed(() => {
  if (state.dailyBalanceOwnershipFilter === 'all') return 'Todos';
  if (state.dailyBalanceOwnershipFilter === null) return 'Sin titularidad';
  const option = (state.ownershipFilterOptions as OwnershipOption[]).find(
    (entry) => entry.value === state.dailyBalanceOwnershipFilter,
  );
  return option?.label ?? 'Titularidad';
});

function closePopoverFromClick(event: Event): void {
  const target = event.currentTarget as HTMLElement | null;
  const details = target?.closest('details') as HTMLDetailsElement | null;
  if (details) details.open = false;
}

function selectOwnershipFilterOption(value: OwnershipFilterValue, event: Event): void {
  state.dailyBalanceOwnershipFilter = value;
  closePopoverFromClick(event);
}

function formatMoneyLocal(value: number, decimals = 2): string {
  return new Intl.NumberFormat('es-ES', {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

const ASSET_COLOR = 'rgba(52, 211, 153, 0.92)';
const LIABILITY_COLOR = 'rgba(251, 113, 133, 0.9)';

const chartData = computed<ChartData<'doughnut'>>(() => ({
  labels: hasDonutData.value ? ['Activos', 'Pasivos'] : ['Sin datos'],
  datasets: [
    {
      data: hasDonutData.value ? [accountingAssets.value, accountingLiabilities.value] : [1],
      backgroundColor: hasDonutData.value
        ? [ASSET_COLOR, LIABILITY_COLOR]
        : ['rgba(148, 163, 184, 0.25)'],
      borderColor: 'rgba(0,0,0,0)',
      borderWidth: 0,
      hoverOffset: 6,
      spacing: 2,
      cutout: '72%',
    },
  ],
}));

const chartOptions = computed<ChartOptions<'doughnut'>>(() => ({
  responsive: true,
  maintainAspectRatio: false,
  plugins: {
    legend: { display: false },
    tooltip: {
      callbacks: {
        label: (ctx) => {
          const label = ctx.label ?? '';
          const value = typeof ctx.raw === 'number' ? ctx.raw : 0;
          return `${label}: ${formatMoneyLocal(value, 2)} EUR`;
        },
      },
    },
  },
}));

const centerTextPlugin = computed<Plugin<'doughnut'>>(() => ({
  id: 'accountingHeroCenterText',
  afterDraw(chart) {
    const { ctx, chartArea } = chart;
    if (!chartArea) return;

    const cx = (chartArea.left + chartArea.right) / 2;
    const cy = (chartArea.top + chartArea.bottom) / 2;
    const netBalance = Number(state.accountingNetBalance ?? 0);
    const netLabel = formatMoneyLocal(netBalance, 2);
    const netColor = netBalance < 0 ? 'rgba(255, 120, 140, 0.95)' : 'rgba(140, 240, 180, 0.95)';

    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    ctx.font = '700 16px "Plus Jakarta Sans", "Segoe UI", sans-serif';
    ctx.fillStyle = netColor;
    ctx.fillText(netLabel, cx, cy - 10);

    ctx.font = '12px "Plus Jakarta Sans", "Segoe UI", sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.72)';
    ctx.fillText('Saldo neto', cx, cy + 8);

    ctx.font = '12px "Plus Jakarta Sans", "Segoe UI", sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.6)';
    ctx.fillText('EUR', cx, cy + 26);

    ctx.restore();
  },
}));
</script>

<template>
  <section class="card ui-pro-panel ui-hero-shell ui-accounting-hero-panel">
    <div class="ui-hero-topbar">
      <p class="ui-pro-kicker ui-hero-topbar-kicker">Accounting Movements</p>
    </div>

    <div class="ui-hero-main">
      <div class="ui-nw-hero-donut">
        <div class="ui-nw-hero-donut-frame ui-hero-donut-pane">
          <div class="nw-donut-wrap nw-donut-wrap-chart-only">
            <div class="nw-donut-chart">
              <Doughnut :data="chartData" :options="chartOptions" :plugins="[centerTextPlugin]" />
            </div>
            <div class="nw-donut-legend">
              <span class="nw-donut-legend-item">
                <span class="nw-donut-legend-dot" :style="{ background: ASSET_COLOR }" />
                <span class="nw-donut-legend-label">Activos</span>
              </span>
              <span class="nw-donut-legend-item">
                <span class="nw-donut-legend-dot" :style="{ background: LIABILITY_COLOR }" />
                <span class="nw-donut-legend-label">Pasivos</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      <article class="ui-hero-summary">
        <div class="ui-hero-summary-head">
          <div>
            <div class="ui-hero-title">Saldo neto contable</div>
            <h1 class="ui-accounting-hero-title">Libro diario operativo</h1>
          </div>
          <div class="ui-hero-summary-controls">
            <label class="ui-hero-context">
              <span class="ui-hero-context-label">Titularidad</span>
              <details
                class="ui-select-popover ui-hero-context-popover ui-accounting-ownership-popover"
              >
                <summary class="ui-select-popover-trigger ui-hero-context-trigger">
                  <span class="ui-select-popover-text">{{ selectedOwnershipFilterLabel }}</span>
                  <span class="ui-select-popover-caret" aria-hidden="true">&#8964;</span>
                </summary>
                <div
                  class="ui-select-popover-menu ui-accounting-ownership-menu"
                  role="listbox"
                  aria-label="Titularidad"
                >
                  <button
                    type="button"
                    class="ui-select-popover-option"
                    :class="{
                      'ui-select-popover-option-active':
                        state.dailyBalanceOwnershipFilter === 'all',
                    }"
                    @click="selectOwnershipFilterOption('all', $event)"
                  >
                    Todos
                  </button>
                  <button
                    v-for="option in state.ownershipFilterOptions"
                    :key="String(option.value)"
                    type="button"
                    class="ui-select-popover-option"
                    :class="{
                      'ui-select-popover-option-active':
                        state.dailyBalanceOwnershipFilter === option.value,
                    }"
                    @click="selectOwnershipFilterOption(option.value, $event)"
                  >
                    {{ option.label }}
                  </button>
                </div>
              </details>
            </label>
          </div>
        </div>

        <div class="ui-hero-summary-body">
          <div class="ui-hero-value">{{ state.formatMoney(state.accountingNetBalance) }}</div>
          <p class="ui-accounting-hero-value-note">Activo contable - Pasivo contable</p>
          <div class="ui-hero-bottom-row ui-accounting-hero-bottom-row">
            <div class="ui-hero-stat ui-hero-stat-assets">
              <span class="ui-hero-stat-label">Activos contables</span>
              <strong class="ui-hero-stat-value">
                {{ state.formatMoney(state.accountingAssetsTotal) }}
              </strong>
            </div>
            <div class="ui-hero-stat ui-hero-stat-liabilities">
              <span class="ui-hero-stat-label">Pasivos contables</span>
              <strong class="ui-hero-stat-value">
                {{ state.formatMoney(state.accountingLiabilitiesTotal) }}
              </strong>
            </div>
          </div>
        </div>
      </article>
    </div>

    <div v-if="state.error" class="ui-state-block ui-state-error">{{ state.error }}</div>
    <div v-if="state.successMessage" class="ui-state-block ui-state-success">
      {{ state.successMessage }}
    </div>
  </section>
</template>
