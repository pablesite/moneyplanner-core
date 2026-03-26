<script setup lang="ts">
import { computed, ref } from 'vue';

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
const donutCircumference = 2 * Math.PI * 68;
const donutTotal = computed(
  () =>
    Math.max(props.plannedIncomeTotal, 0) +
    Math.max(props.plannedExpenseTotal, 0) +
    Math.abs(props.plannedBalanceTotal) +
    1,
);
const donutIncomeArc = computed(
  () => (Math.max(props.plannedIncomeTotal, 0) / donutTotal.value) * donutCircumference,
);
const donutExpenseArc = computed(
  () => (Math.max(props.plannedExpenseTotal, 0) / donutTotal.value) * donutCircumference,
);
const donutBalanceArc = computed(
  () => (Math.abs(props.plannedBalanceTotal) / donutTotal.value) * donutCircumference,
);
const donutExpenseOffset = computed(() => -donutIncomeArc.value);
const donutBalanceOffset = computed(() => -(donutIncomeArc.value + donutExpenseArc.value));
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

  <section v-else class="card ui-pro-panel ui-budget-hero">
    <p class="ui-pro-kicker">Presupuesto</p>
    <div class="ui-budget-hero-main">
      <div class="ui-budget-hero-donut-pane">
        <div class="ui-budget-hero-composition">
          <div class="ui-budget-hero-donut-wrap">
            <svg
              viewBox="0 0 170 170"
              class="ui-budget-hero-donut"
              role="img"
              aria-label="Resumen presupuesto"
            >
              <circle cx="85" cy="85" r="68" class="ui-budget-hero-donut-track" />
              <circle
                cx="85"
                cy="85"
                r="68"
                class="ui-budget-hero-donut-income"
                :stroke-dasharray="`${donutIncomeArc} ${donutCircumference}`"
              />
              <circle
                cx="85"
                cy="85"
                r="68"
                class="ui-budget-hero-donut-expense"
                :stroke-dasharray="`${donutExpenseArc} ${donutCircumference}`"
                :stroke-dashoffset="donutExpenseOffset"
              />
              <circle
                cx="85"
                cy="85"
                r="68"
                class="ui-budget-hero-donut-balance"
                :stroke-dasharray="`${donutBalanceArc} ${donutCircumference}`"
                :stroke-dashoffset="donutBalanceOffset"
              />
            </svg>
            <div class="ui-budget-hero-donut-center">
              <span>Saldo previsto</span>
              <strong>{{ formatMoney(plannedBalanceTotal) }} EUR</strong>
            </div>
          </div>
          <div class="ui-budget-hero-legend">
            <span><i class="ui-budget-hero-dot ui-budget-hero-dot-income"></i>Ingresos</span>
            <span><i class="ui-budget-hero-dot ui-budget-hero-dot-expense"></i>Gastos</span>
            <span><i class="ui-budget-hero-dot ui-budget-hero-dot-balance"></i>Saldo</span>
          </div>
        </div>
      </div>

      <article class="ui-budget-hero-summary">
        <div class="ui-budget-hero-summary-head">
          <div class="ui-budget-hero-title">Saldo anual previsto</div>
          <div class="ui-budget-toolbar">
            <button
              type="button"
              class="ui-budget-suggestions-info-btn"
              aria-label="Ver sugerencias"
              @click="isSuggestionsModalOpen = true"
            >
              <span aria-hidden="true">i</span>
            </button>
            <label class="ui-budget-owner-picker">
              <span>Titularidad</span>
              <details class="ui-select-popover">
                <summary class="ui-select-popover-trigger">
                  <span class="ui-select-popover-text">{{ selectedOwnershipFilterLabel }}</span>
                  <span class="ui-select-popover-caret" aria-hidden="true">v</span>
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
            <label class="ui-budget-year-picker">
              <span>Ejercicio</span>
              <details class="ui-select-popover" :class="{ 'opacity-60': isLoading }">
                <summary class="ui-select-popover-trigger">
                  <span class="ui-select-popover-text">{{ selectedFiscalYearLabel }}</span>
                  <span class="ui-select-popover-caret" aria-hidden="true">v</span>
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
        </div>

        <div class="ui-budget-hero-summary-body">
          <div class="ui-budget-hero-balance">{{ formatMoney(plannedBalanceTotal) }} EUR</div>
          <div class="ui-budget-hero-bottom-row">
            <article class="ui-budget-hero-stat ui-budget-hero-stat-income">
              <span class="ui-budget-hero-stat-label">Ingresos previstos</span>
              <strong class="ui-budget-hero-stat-value">{{ formatMoney(plannedIncomeTotal) }} EUR</strong>
              <small class="ui-budget-hero-stat-meta">
                {{ formatMoney(plannedIncomeTotal / 12) }} EUR/mes (promedio)
              </small>
            </article>

            <article class="ui-budget-hero-stat ui-budget-hero-stat-expense">
              <span class="ui-budget-hero-stat-label">Gastos previstos</span>
              <strong class="ui-budget-hero-stat-value">{{ formatMoney(plannedExpenseTotal) }} EUR</strong>
              <small class="ui-budget-hero-stat-meta">
                {{ formatMoney(plannedExpenseTotal / 12) }} EUR/mes (promedio)
              </small>
            </article>
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
            <h2 id="budget-suggestions-title">Sugerencias desde histórico ledger</h2>
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
            Sin cobertura ledger por subcategoría para sugerir ajustes todavía.
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
