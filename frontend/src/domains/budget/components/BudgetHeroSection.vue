<script setup lang="ts">
import { computed } from 'vue';

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
        <div v-if="index < monthlyCloseFlowSteps.length - 1" class="ui-monthly-close-arrow">→</div>
      </template>
    </div>
  </section>

  <section v-else class="card ui-pro-panel ui-budget-hero">
    <div class="ui-budget-hero-header">
      <div>
        <p class="ui-pro-kicker">Presupuesto</p>
        <h1 class="ui-budget-title">Dashboard de presupuesto</h1>
        <p class="ui-budget-subtitle">
          Compara el presupuesto anual previsto con la ejecucion real (cuando se active
          contabilidad).
        </p>
      </div>

      <div class="ui-budget-toolbar">
        <label class="ui-budget-owner-picker">
          <span>Titularidad</span>
          <details class="ui-select-popover">
            <summary class="ui-select-popover-trigger">
              <span class="ui-select-popover-text">{{ selectedOwnershipFilterLabel }}</span>
              <span class="ui-select-popover-caret" aria-hidden="true">⌄</span>
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
              <span class="ui-select-popover-caret" aria-hidden="true">⌄</span>
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

    <div class="ui-budget-suggestions">
      <div class="ui-budget-suggestions-head">
        <div>
          <strong>Sugerencias desde historico ledger</strong>
          <p>
            Referencia orientativa para plan anual. El presupuesto sigue siendo editable y manual.
          </p>
        </div>
        <span class="ui-budget-pill"
          >{{ budgetSuggestions?.window_months ?? 0 }} meses observados</span
        >
      </div>

      <div v-if="budgetSuggestionsLoading" class="subtle">Calculando sugerencias...</div>
      <div v-else-if="budgetSuggestionsError" class="subtle text-red-400">
        {{ budgetSuggestionsError }}
      </div>
      <div
        v-else-if="!incomeBudgetSuggestions.length && !expenseBudgetSuggestions.length"
        class="subtle"
      >
        Sin cobertura ledger por subcategoria para sugerir ajustes todavia.
      </div>
      <div v-else class="ui-budget-suggestions-grid">
        <article class="ui-budget-suggestions-col">
          <h3>Ingresos (top diferencias)</h3>
          <ul>
            <li v-for="row in incomeBudgetSuggestions" :key="`inc-${row.key}`">
              <span>{{ row.subcategoryLabel }}</span>
              <span>
                Plan {{ formatMoney(row.plannedAnnual) }} EUR · Sug
                {{ formatMoney(row.suggestedAnnual) }} EUR ({{ row.observedMonths }} meses)
              </span>
            </li>
          </ul>
        </article>
        <article class="ui-budget-suggestions-col">
          <h3>Gastos (top diferencias)</h3>
          <ul>
            <li v-for="row in expenseBudgetSuggestions" :key="`exp-${row.key}`">
              <span>{{ row.subcategoryLabel }}</span>
              <span>
                Plan {{ formatMoney(row.plannedAnnual) }} EUR · Sug
                {{ formatMoney(row.suggestedAnnual) }} EUR ({{ row.observedMonths }} meses)
              </span>
            </li>
          </ul>
        </article>
      </div>
    </div>

    <div class="ui-budget-kpi-grid">
      <article class="ui-budget-kpi ui-budget-kpi-income">
        <div class="ui-budget-kpi-label">Ingresos previstos</div>
        <div class="ui-budget-kpi-value">{{ formatMoney(plannedIncomeTotal) }} EUR</div>
        <div class="ui-budget-kpi-meta">
          {{ formatMoney(plannedIncomeTotal / 12) }} EUR/mes (promedio) ·
          {{ viewModeLabel(incomeViewMode) }}
        </div>
      </article>

      <article class="ui-budget-kpi ui-budget-kpi-expense">
        <div class="ui-budget-kpi-label">Gastos previstos</div>
        <div class="ui-budget-kpi-value">{{ formatMoney(plannedExpenseTotal) }} EUR</div>
        <div class="ui-budget-kpi-meta">
          {{ formatMoney(plannedExpenseTotal / 12) }} EUR/mes (promedio) ·
          {{ viewModeLabel(expenseViewMode) }}
        </div>
      </article>

      <article
        class="ui-budget-kpi"
        :class="
          plannedBalanceTotal >= 0 ? 'ui-budget-kpi-balance-good' : 'ui-budget-kpi-balance-bad'
        "
      >
        <div class="ui-budget-kpi-label">Saldo anual previsto</div>
        <div class="ui-budget-kpi-value">{{ formatMoney(plannedBalanceTotal) }} EUR</div>
        <div class="ui-budget-kpi-meta">
          {{
            plannedIncomeTotal > 0
              ? `${formatPercent(plannedBalanceTotal / plannedIncomeTotal, 0)} sobre ingresos`
              : 'Sin base de ingresos'
          }}
        </div>
      </article>

      <article class="ui-budget-kpi ui-budget-kpi-muted">
        <div class="ui-budget-kpi-label">Estado de ejecucion</div>
        <div class="ui-budget-kpi-value ui-budget-kpi-value-sm">{{ executionStatusLabel }}</div>
        <div class="ui-budget-kpi-meta">
          {{ executionStatusDetail }}
          <br />
          {{ activeViewSummary }}
        </div>
      </article>
    </div>
  </section>
</template>
