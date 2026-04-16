<script setup lang="ts">
import { computed, ref } from 'vue';
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

ChartJS.register(ArcElement, Tooltip, Legend);

type BudgetEntryViewMode = 'all' | 'recurrent' | 'one_off';
type MonthlyCloseStepId = 'liq' | 'income' | 'expense' | 'result';
type MonthlyCloseStatus = 'draft' | 'finalized' | 'locked';

const props = defineProps<{
  isMonthlyCloseView: boolean;
  monthLabels: string[];
  selectedExecutionMonth: number;
  selectedOwnershipFilterLabel: string;
  ownershipFilter: string;
  ownershipOptions: Array<{ value: string; label: string }>;
  selectedFiscalYearLabel: string;
  fiscalYear: number;
  fiscalYearOptions: number[];
  isLoading: boolean;
  monthlyCloseFlowSteps: Array<{ id: MonthlyCloseStepId; label: string; subtitle: string }>;
  activeMonthlyCloseStep: MonthlyCloseStepId;
  budgetSuggestionsLoading: boolean;
  budgetSuggestionsError: string | null;
  budgetSuggestions: { window_months?: number | null } | null;
  incomeBudgetSuggestions: Array<{
    key: string;
    subcategoryLabel: string;
    plannedAnnual: number;
    suggestedAnnual: number;
    observedMonths: number;
  }>;
  expenseBudgetSuggestions: Array<{
    key: string;
    subcategoryLabel: string;
    plannedAnnual: number;
    suggestedAnnual: number;
    observedMonths: number;
  }>;
  plannedIncomeTotal: number;
  plannedExpenseTotal: number;
  plannedBalanceTotal: number;
  executionStatusLabel: string;
  executionStatusDetail: string;
  activeViewSummary: string;
  incomeViewMode: BudgetEntryViewMode;
  expenseViewMode: BudgetEntryViewMode;
  formatMoney: (value: number, decimals?: number) => string;
  formatPercent: (value: number | null, decimals?: number) => string;
  viewModeLabel: (mode: BudgetEntryViewMode) => string;
  updateIncomeViewMode: (mode: BudgetEntryViewMode) => void;
  updateExpenseViewMode: (mode: BudgetEntryViewMode) => void;
  closeStatus?: MonthlyCloseStatus;
  setActiveMonthlyCloseStep: (step: MonthlyCloseStepId) => void;
  updateSelectedExecutionMonth: (value: number) => void;
  selectOwnershipFilterOption: (value: string, event: Event) => void;
  selectFiscalYearOption: (year: number, event: Event) => void;
}>();

const closeStatusLabel = computed(() => {
  if (props.closeStatus === 'finalized') return 'Finalizado';
  if (props.closeStatus === 'locked') return 'Bloqueado';
  if (props.closeStatus === 'draft') return 'Borrador';
  return null;
});
const isSuggestionsModalOpen = ref(false);

const hasBudgetSuggestions = computed(
  () => props.incomeBudgetSuggestions.length > 0 || props.expenseBudgetSuggestions.length > 0,
);

const observedSuggestionMonths = computed(() => props.budgetSuggestions?.window_months ?? 0);

function formatMoneyLocal(n: number, decimals = 2) {
  return new Intl.NumberFormat('es-ES', {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

const INCOME_COLOR = 'rgba(52, 211, 153, 0.92)';
const EXPENSE_COLOR = 'rgba(251, 113, 133, 0.92)';
const BALANCE_COLOR = 'rgba(110, 209, 255, 0.92)';

const chartData = computed<ChartData<'doughnut'>>(() => ({
  labels: ['Ingresos', 'Gastos', 'Saldo'],
  datasets: [
    {
      data: [
        Math.max(props.plannedIncomeTotal, 0),
        Math.max(props.plannedExpenseTotal, 0),
        Math.abs(props.plannedBalanceTotal),
      ],
      backgroundColor: [INCOME_COLOR, EXPENSE_COLOR, BALANCE_COLOR],
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
          const v = typeof ctx.raw === 'number' ? ctx.raw : 0;
          return `${label}: ${formatMoneyLocal(v, 2)} EUR`;
        },
      },
    },
  },
}));

const centerTextPlugin = computed<Plugin<'doughnut'>>(() => ({
  id: 'budgetCenterText',
  afterDraw(chart) {
    const { ctx, chartArea } = chart;
    if (!chartArea) return;

    const cx = (chartArea.left + chartArea.right) / 2;
    const cy = (chartArea.top + chartArea.bottom) / 2;

    const balanceStr = formatMoneyLocal(props.plannedBalanceTotal, 2);
    const isNeg = props.plannedBalanceTotal < 0;
    const valColor = isNeg ? 'rgba(255, 120, 140, 0.95)' : 'rgba(140, 240, 180, 0.95)';

    ctx.save();
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';

    ctx.font = '700 16px "Plus Jakarta Sans", "Segoe UI", sans-serif';
    ctx.fillStyle = valColor;
    ctx.fillText(balanceStr, cx, cy - 10);

    ctx.font = '12px "Plus Jakarta Sans", "Segoe UI", sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.70)';
    ctx.fillText('Saldo previsto', cx, cy + 8);

    ctx.font = '12px "Plus Jakarta Sans", "Segoe UI", sans-serif';
    ctx.fillStyle = 'rgba(255,255,255,0.60)';
    ctx.fillText('EUR', cx, cy + 26);

    ctx.restore();
  },
}));
</script>

<template>
  <section v-if="isMonthlyCloseView" class="card ui-pro-panel ui-budget-hero">
    <div class="ui-budget-hero-header">
      <div>
        <p class="ui-pro-kicker">Cierre mensual</p>
        <div style="display: flex; align-items: center; gap: 10px; flex-wrap: wrap">
          <h1 class="ui-budget-title" style="margin: 0">Flujo de cierre mensual</h1>
          <span
            v-if="closeStatus"
            class="ui-monthly-close-status-badge"
            :class="`ui-monthly-close-status-badge-${closeStatus}`"
            >{{ closeStatusLabel }}</span
          >
        </div>
        <p class="ui-budget-subtitle">
          Empieza por la liquidez real, luego confirma ingresos y gastos, y termina revisando el
          residual contable.
        </p>
      </div>
      <div class="ui-budget-checkin-controls">
        <label>
          <span>Mes</span>
          <select
            :value="selectedExecutionMonth"
            class="select ui-data-field"
            @change="
              updateSelectedExecutionMonth(Number(($event.target as HTMLSelectElement).value))
            "
          >
            <option
              v-for="(label, index) in monthLabels"
              :key="`close-${label}`"
              :value="index + 1"
            >
              {{ label }}
            </option>
          </select>
        </label>
      </div>
    </div>
    <div class="ui-monthly-close-flow">
      <template v-for="(step, index) in monthlyCloseFlowSteps" :key="step.id">
        <button
          type="button"
          class="ui-monthly-close-step-chip"
          :class="{ 'ui-monthly-close-step-chip-active': activeMonthlyCloseStep === step.id }"
          :aria-pressed="activeMonthlyCloseStep === step.id"
          @click="setActiveMonthlyCloseStep(step.id)"
        >
          <strong>{{ index + 1 }}. {{ step.label }}</strong>
          <span>{{ step.subtitle }}</span>
        </button>
        <div v-if="index < monthlyCloseFlowSteps.length - 1" class="ui-monthly-close-arrow">></div>
      </template>
    </div>
  </section>

  <section v-else class="card ui-pro-panel ui-hero-shell ui-budget-hero">
    <div class="ui-hero-topbar">
      <p class="ui-pro-kicker ui-hero-topbar-kicker">Presupuesto</p>
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
                <span class="nw-donut-legend-dot" :style="{ background: INCOME_COLOR }" />
                <span class="nw-donut-legend-label">Ingresos</span>
              </span>
              <span class="nw-donut-legend-item">
                <span class="nw-donut-legend-dot" :style="{ background: EXPENSE_COLOR }" />
                <span class="nw-donut-legend-label">Gastos</span>
              </span>
              <span class="nw-donut-legend-item">
                <span class="nw-donut-legend-dot" :style="{ background: BALANCE_COLOR }" />
                <span class="nw-donut-legend-label">Saldo</span>
              </span>
            </div>
          </div>
        </div>
      </div>

      <article class="ui-hero-summary">
        <div class="ui-hero-summary-head">
          <div class="ui-hero-title">Saldo anual previsto</div>
          <div class="ui-budget-hero-controls-col">
            <div class="ui-hero-summary-controls">
              <button
                type="button"
                class="ui-budget-suggestions-info-btn"
                aria-label="Ver sugerencias"
                @click="isSuggestionsModalOpen = true"
              >
                <span aria-hidden="true">i</span>
              </button>
              <label class="ui-hero-context">
                <span class="ui-hero-context-label">Titularidad</span>
                <details class="ui-select-popover ui-hero-context-popover">
                  <summary class="ui-select-popover-trigger ui-hero-context-trigger">
                    <span class="ui-select-popover-text">{{ selectedOwnershipFilterLabel }}</span>
                    <span class="ui-select-popover-caret" aria-hidden="true">&#8964;</span>
                  </summary>
                  <div class="ui-select-popover-menu" role="listbox" aria-label="Titularidad">
                    <button
                      type="button"
                      class="ui-select-popover-option"
                      :class="{ 'ui-select-popover-option-active': ownershipFilter === 'all' }"
                      @click="selectOwnershipFilterOption('all', $event)"
                    >
                      Todos
                    </button>
                    <button
                      v-for="ownerOption in ownershipOptions"
                      :key="ownerOption.value"
                      type="button"
                      class="ui-select-popover-option"
                      :class="{
                        'ui-select-popover-option-active': ownershipFilter === ownerOption.value,
                      }"
                      @click="selectOwnershipFilterOption(ownerOption.value, $event)"
                    >
                      {{ ownerOption.label }}
                    </button>
                  </div>
                </details>
              </label>
              <label class="ui-hero-context">
                <span class="ui-hero-context-label">Ejercicio</span>
                <details
                  class="ui-select-popover ui-hero-context-popover"
                  :class="{ 'opacity-60': isLoading }"
                >
                  <summary class="ui-select-popover-trigger ui-hero-context-trigger">
                    <span class="ui-select-popover-text">{{ selectedFiscalYearLabel }}</span>
                    <span class="ui-select-popover-caret" aria-hidden="true">&#8964;</span>
                  </summary>
                  <div class="ui-select-popover-menu" role="listbox" aria-label="Ejercicio">
                    <button
                      v-for="year in fiscalYearOptions"
                      :key="year"
                      type="button"
                      class="ui-select-popover-option"
                      :class="{ 'ui-select-popover-option-active': fiscalYear === year }"
                      :disabled="isLoading"
                      @click="selectFiscalYearOption(year, $event)"
                    >
                      {{ year }}
                    </button>
                  </div>
                </details>
              </label>
            </div>
            <div class="ui-budget-filter-segment" role="tablist" aria-label="Tipo de partida">
              <button
                type="button"
                class="ui-budget-filter-btn"
                :class="{ 'ui-budget-filter-btn-active': incomeViewMode === 'all' }"
                @click="
                  updateIncomeViewMode('all');
                  updateExpenseViewMode('all');
                "
              >
                Todos
              </button>
              <button
                type="button"
                class="ui-budget-filter-btn"
                :class="{ 'ui-budget-filter-btn-active': incomeViewMode === 'recurrent' }"
                @click="
                  updateIncomeViewMode('recurrent');
                  updateExpenseViewMode('recurrent');
                "
              >
                Recurrentes
              </button>
              <button
                type="button"
                class="ui-budget-filter-btn"
                :class="{ 'ui-budget-filter-btn-active': incomeViewMode === 'one_off' }"
                @click="
                  updateIncomeViewMode('one_off');
                  updateExpenseViewMode('one_off');
                "
              >
                Puntuales
              </button>
            </div>
          </div>
        </div>

        <div class="ui-hero-summary-body">
          <div class="ui-hero-value">{{ formatMoney(plannedBalanceTotal) }} EUR</div>
          <div class="ui-hero-bottom-row ui-hero-bottom-row-4">
            <div class="ui-hero-stat ui-hero-stat-assets">
              <span class="ui-hero-stat-label">Ingresos previstos</span>
              <strong class="ui-hero-stat-value">
                {{ formatMoney(plannedIncomeTotal) }} EUR
              </strong>
            </div>

            <div class="ui-hero-stat ui-hero-stat-liabilities">
              <span class="ui-hero-stat-label">Gastos previstos</span>
              <strong class="ui-hero-stat-value">
                {{ formatMoney(plannedExpenseTotal) }} EUR
              </strong>
            </div>
          </div>
        </div>
      </article>
    </div>

    <div
      v-if="isSuggestionsModalOpen"
      class="ui-budget-suggestions-modal-backdrop"
      @click.self="isSuggestionsModalOpen = false"
    >
      <section
        class="ui-budget-suggestions-modal"
        role="dialog"
        aria-modal="true"
        aria-labelledby="budget-suggestions-title"
      >
        <header class="ui-budget-suggestions-modal-head">
          <div>
            <h2 id="budget-suggestions-title">Sugerencias desde histórico del libro contable</h2>
            <p>
              Referencia orientativa para plan anual. El presupuesto sigue siendo editable y manual.
            </p>
          </div>
          <div class="ui-budget-suggestions-modal-actions">
            <span class="ui-budget-pill">{{ observedSuggestionMonths }} meses observados</span>
            <button
              type="button"
              class="ui-budget-suggestions-close-btn"
              @click="isSuggestionsModalOpen = false"
            >
              Cerrar
            </button>
          </div>
        </header>

        <div class="ui-budget-suggestions-modal-body">
          <div v-if="budgetSuggestionsLoading" class="subtle">Calculando sugerencias...</div>
          <div v-else-if="budgetSuggestionsError" class="subtle text-red-400">
            {{ budgetSuggestionsError }}
          </div>
          <div v-else-if="!hasBudgetSuggestions" class="subtle">
            Sin cobertura del libro contable por subcategoría para sugerir ajustes todavía.
          </div>
          <div v-else class="ui-budget-suggestions-grid">
            <article class="ui-budget-suggestions-col">
              <h3>Ingresos (top diferencias)</h3>
              <ul>
                <li v-for="row in incomeBudgetSuggestions" :key="`inc-${row.key}`">
                  <div class="ui-budget-suggestion-item-head">
                    <strong>{{ row.subcategoryLabel }}</strong>
                    <span class="ui-budget-suggestion-months">{{ row.observedMonths }} meses</span>
                  </div>
                  <div class="ui-budget-suggestion-values">
                    <span class="ui-budget-suggestion-metric">
                      <small>Plan</small>
                      <span>{{ formatMoney(row.plannedAnnual) }} EUR</span>
                    </span>
                    <span class="ui-budget-suggestion-metric">
                      <small>Sugerido</small>
                      <span>{{ formatMoney(row.suggestedAnnual) }} EUR</span>
                    </span>
                    <span
                      class="ui-budget-suggestion-metric ui-budget-suggestion-metric-delta"
                      :class="
                        row.suggestedAnnual >= row.plannedAnnual
                          ? 'ui-budget-suggestion-metric-delta-up'
                          : 'ui-budget-suggestion-metric-delta-down'
                      "
                    >
                      <small>Diferencia</small>
                      <span>
                        {{
                          row.suggestedAnnual >= row.plannedAnnual
                            ? `+${formatMoney(Math.abs(row.suggestedAnnual - row.plannedAnnual))}`
                            : `-${formatMoney(Math.abs(row.suggestedAnnual - row.plannedAnnual))}`
                        }}
                        EUR
                      </span>
                    </span>
                  </div>
                </li>
              </ul>
            </article>
            <article class="ui-budget-suggestions-col">
              <h3>Gastos (top diferencias)</h3>
              <ul>
                <li v-for="row in expenseBudgetSuggestions" :key="`exp-${row.key}`">
                  <div class="ui-budget-suggestion-item-head">
                    <strong>{{ row.subcategoryLabel }}</strong>
                    <span class="ui-budget-suggestion-months">{{ row.observedMonths }} meses</span>
                  </div>
                  <div class="ui-budget-suggestion-values">
                    <span class="ui-budget-suggestion-metric">
                      <small>Plan</small>
                      <span>{{ formatMoney(row.plannedAnnual) }} EUR</span>
                    </span>
                    <span class="ui-budget-suggestion-metric">
                      <small>Sugerido</small>
                      <span>{{ formatMoney(row.suggestedAnnual) }} EUR</span>
                    </span>
                    <span
                      class="ui-budget-suggestion-metric ui-budget-suggestion-metric-delta"
                      :class="
                        row.suggestedAnnual >= row.plannedAnnual
                          ? 'ui-budget-suggestion-metric-delta-up'
                          : 'ui-budget-suggestion-metric-delta-down'
                      "
                    >
                      <small>Diferencia</small>
                      <span>
                        {{
                          row.suggestedAnnual >= row.plannedAnnual
                            ? `+${formatMoney(Math.abs(row.suggestedAnnual - row.plannedAnnual))}`
                            : `-${formatMoney(Math.abs(row.suggestedAnnual - row.plannedAnnual))}`
                        }}
                        EUR
                      </span>
                    </span>
                  </div>
                </li>
              </ul>
            </article>
          </div>
        </div>
      </section>
    </div>
  </section>
</template>
