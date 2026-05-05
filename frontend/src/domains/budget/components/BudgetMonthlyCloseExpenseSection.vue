<script setup lang="ts">
import type { AnnualExpenseEntry } from '@/domains/data-input';

type MonthlyCloseStepId = 'liq' | 'income' | 'expense' | 'result';
type ExpenseResetMode = 'zero' | 'planned';
type ExpenseExecutionOrigin =
  | 'categorized_ledger'
  | 'legacy_ledger'
  | 'legacy_checkin'
  | 'ambiguous_taxonomy'
  | 'none';
type ExpenseExecutionSource =
  | 'categorized_ledger'
  | 'legacy_fallback'
  | 'pending_classification'
  | 'none';

type ExpenseCheckin = {
  id: number;
  annual_expense_entry_id: number;
  fiscal_year: number;
  month: number;
  status: 'confirmed' | 'adjusted' | 'skipped' | 'estimated';
  executed_amount: string | null;
  note: string;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
};

type ExpenseRow = {
  entry: AnnualExpenseEntry;
  planned: number;
  executed: number | null;
  categorizedLedgerExecuted: number | null;
  legacyLedgerExecuted: number | null;
  executionSource: ExpenseExecutionSource;
  executionOrigin: ExpenseExecutionOrigin;
  checkin: ExpenseCheckin | null;
};

type ExpenseGroup = {
  categoryKey: string;
  categoryLabel: string;
  plannedTotal: number;
  executedTotal: number;
  deviation: number;
  completionRatio: number;
  rows: ExpenseRow[];
};

defineProps<{
  isMonthlyCloseView: boolean;
  activeMonthlyCloseStep: MonthlyCloseStepId;
  expenseMonthlySummary: unknown;
  expenseExecutionLoading: boolean;
  expenseExecutionBusyEntryId: number | null;
  groupedMonthlyExpenseExecutionEntries: ExpenseGroup[];
  monthlyExpenseCoverageSummary: {
    ratio: number;
    viaLedger: number;
    viaFallback: number;
    pending: number;
  };
  monthlyExpenseCoverageDetail: string;
  monthlyExpenseCoverageLabel: string;
  monthlyExpensePendingClassification: { amount: number; ambiguousRows: number };
  expenseAdjustAmounts: Record<number, string>;
  setExpenseAdjustAmount: (entryId: number, value: string) => void;
  selectedExpenseMonthPlanned: number;
  selectedExpenseMonthExecuted: number;
  selectedExpenseMonthDeviation: number;
  formatMoney: (value: number, decimals?: number) => string;
  formatPercent: (value: number | null, decimals?: number) => string;
  executionSourceLabel: (origin: ExpenseExecutionOrigin) => string;
  expenseCheckinRowSummary: (row: ExpenseRow) => string;
  isCloseLocked?: boolean;
  checkinStatusLabel: (status: 'confirmed' | 'adjusted' | 'skipped' | 'estimated') => string;
  isLockedExecutionRow: (row: ExpenseRow) => boolean;
  goToPreviousMonthlyCloseStep: () => void;
  goToNextMonthlyCloseStep: () => void;
  resetExpenseCheckinDraftValue: (row: ExpenseRow, mode: ExpenseResetMode) => void | Promise<void>;
  ensureExpenseAdjustAmountPrefilled: (row: ExpenseRow) => void;
  onExpenseAdjustAmountBlur: (row: ExpenseRow) => void | Promise<void>;
  saveExpenseCheckinFromInput: (row: ExpenseRow) => void | Promise<void>;
  onExpenseCheckinCheckboxToggle: (row: ExpenseRow, checked: boolean) => void | Promise<void>;
}>();
</script>

<template>
  <section
    v-if="isMonthlyCloseView && activeMonthlyCloseStep === 'expense'"
    class="card ui-pro-panel ui-budget-checkin mt-3"
  >
    <div class="ui-budget-checkin-header">
      <div>
        <div class="ui-monthly-close-step-headline">
          <button
            type="button"
            class="btn ui-monthly-close-step-nav-btn"
            @click="goToPreviousMonthlyCloseStep()"
          >
            &larr;
          </button>
          <h2 class="ui-budget-checkin-title">Paso 3 - Check-in mensual de gastos</h2>
          <button
            type="button"
            class="btn ui-monthly-close-step-nav-btn"
            @click="goToNextMonthlyCloseStep()"
          >
            &rarr;
          </button>
        </div>
        <p class="ui-budget-checkin-subtitle ui-budget-checkin-subtitle-note">
          El cierre usa movimientos cuando existen y deja para revisión solo las líneas pendientes.
        </p>
        <p class="ui-budget-checkin-subtitle">
          Cierre mensual rapido de `Gastos` (14C v1). `Ingresos` se integra con el mismo patron.
        </p>
      </div>
    </div>

    <div v-if="expenseMonthlySummary" class="ui-budget-checkin-summary-grid">
      <article class="ui-budget-checkin-kpi">
        <span>Previsto mes</span>
        <strong>{{ formatMoney(selectedExpenseMonthPlanned) }} EUR</strong>
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Ejecutado mes</span>
        <strong>{{ formatMoney(selectedExpenseMonthExecuted) }} EUR</strong>
      </article>
      <article
        class="ui-budget-checkin-kpi"
        :class="{
          'ui-budget-checkin-kpi-danger': selectedExpenseMonthDeviation > 0,
          'ui-budget-checkin-kpi-good': selectedExpenseMonthDeviation < 0,
        }"
      >
        <span>Desviación del mes</span>
        <strong>
          {{ selectedExpenseMonthDeviation > 0 ? '+' : ''
          }}{{ formatMoney(selectedExpenseMonthDeviation) }} EUR
        </strong>
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Completitud</span>
        <strong>{{ formatPercent(monthlyExpenseCoverageSummary.ratio, 0) }}</strong>
      </article>
    </div>

    <div v-if="isCloseLocked" class="ui-monthly-close-locked-banner">
      Este mes está finalizado. Reabre el cierre para editar.
    </div>

    <div class="ui-budget-checkin-list">
      <div v-if="expenseExecutionLoading" class="subtle">Cargando check-ins mensuales...</div>
      <div v-else-if="!groupedMonthlyExpenseExecutionEntries.length" class="subtle">
        No hay gastos previstos para este mes con los filtros actuales.
      </div>
      <div v-else class="ui-budget-checkin-groups-box">
        <div class="ui-budget-execution-note">
          <div class="ui-budget-execution-note-main">
            <strong>Estado del cierre</strong>
            <span>
              {{
                monthlyExpenseCoverageSummary.viaLedger + monthlyExpenseCoverageSummary.viaFallback
              }}
              líneas completadas ·
              {{ monthlyExpenseCoverageSummary.pending }} pendientes
            </span>
            <small class="ui-budget-execution-note-detail">{{
              monthlyExpenseCoverageDetail
            }}</small>
          </div>
          <span class="ui-budget-execution-badge">{{ monthlyExpenseCoverageLabel }}</span>
        </div>

        <div
          v-if="monthlyExpensePendingClassification.amount > 0"
          class="ui-state-block ui-state-error"
        >
          <strong>Pendiente clasificar</strong>
          <span>
            {{ formatMoney(monthlyExpensePendingClassification.amount) }} EUR del libro contable no
            se puede alinear automaticamente con el presupuesto de este mes.
          </span>
          <small v-if="monthlyExpensePendingClassification.ambiguousRows > 0">
            {{ monthlyExpensePendingClassification.ambiguousRows }} líneas comparten la misma
            subcategoría y requieren revisión manual.
          </small>
        </div>

        <details
          v-for="group in groupedMonthlyExpenseExecutionEntries"
          :key="`expense-checkin-group-${group.categoryKey}`"
          class="ui-budget-checkin-group"
          open
        >
          <summary class="ui-budget-checkin-group-summary">
            <div class="ui-budget-checkin-group-title-wrap">
              <strong class="ui-budget-checkin-group-title">{{ group.categoryLabel }}</strong>
              <span class="ui-budget-checkin-group-meta">
                {{ group.rows.length }} líneas - {{ Math.round(group.completionRatio * 100) }} %
                completitud
              </span>
            </div>
            <div class="ui-budget-checkin-group-kpis">
              <span>P {{ formatMoney(group.plannedTotal) }} EUR</span>
              <span>E {{ formatMoney(group.executedTotal) }} EUR</span>
              <span
                :class="{
                  'ui-budget-checkin-group-dev-pos': group.deviation > 0,
                  'ui-budget-checkin-group-dev-neg': group.deviation < 0,
                }"
              >
                D {{ group.deviation > 0 ? '+' : '' }}{{ formatMoney(group.deviation) }} EUR
              </span>
            </div>
          </summary>

          <div class="ui-budget-checkin-group-rows">
            <article
              v-for="row in group.rows"
              :key="`expense-checkin-${row.entry.id}`"
              class="ui-budget-checkin-row"
              :class="{ 'ui-budget-checkin-row-estimated': row.checkin?.status === 'estimated' }"
            >
              <div class="ui-budget-checkin-row-main">
                <div
                  v-if="row.executionSource !== 'none'"
                  class="ui-budget-execution-chip"
                  :class="{
                    'ui-budget-execution-chip-ledger': row.executionOrigin === 'categorized_ledger',
                  }"
                >
                  {{ executionSourceLabel(row.executionOrigin) }}
                </div>
                <div class="ui-budget-checkin-row-title" :title="expenseCheckinRowSummary(row)">
                  <span
                    v-if="row.checkin?.status === 'estimated'"
                    class="ui-budget-checkin-estimated-badge"
                    >Estimado</span
                  >
                  {{ expenseCheckinRowSummary(row) }}
                  <span class="ui-budget-checkin-row-planned">
                    (Previsto {{ formatMoney(row.planned) }} EUR)
                  </span>
                  <template v-if="row.entry.expenseType === 'one_off'"> - Puntual</template>
                </div>
                <div
                  v-if="
                    row.executionOrigin === 'categorized_ledger' ||
                    row.executionOrigin === 'legacy_ledger' ||
                    row.executionOrigin === 'ambiguous_taxonomy'
                  "
                  class="ui-budget-checkin-row-state"
                >
                  <strong>{{ executionSourceLabel(row.executionOrigin) }}</strong>
                  <template v-if="row.executed != null"
                    >({{ formatMoney(row.executed) }} EUR)</template
                  >
                  <span
                    v-if="
                      row.executionOrigin === 'categorized_ledger' ||
                      row.executionOrigin === 'legacy_ledger'
                    "
                    class="ui-budget-checkin-row-lock-note"
                  >
                    Edición legacy bloqueada
                  </span>
                  <span v-else class="ui-budget-checkin-row-lock-note">
                    Varias líneas comparten esta subcategoría.
                  </span>
                </div>
                <div v-if="row.checkin" class="ui-budget-checkin-row-state">
                  <strong>{{ checkinStatusLabel(row.checkin.status) }}</strong>
                  <template v-if="row.checkin.status !== 'skipped' && row.executed != null">
                    ({{ formatMoney(row.executed) }} EUR)
                  </template>
                </div>
              </div>

              <div class="ui-budget-checkin-row-actions">
                <div class="ui-budget-checkin-adjust">
                  <div class="ui-budget-checkin-quick-actions">
                    <button
                      type="button"
                      class="btn ui-budget-checkin-mini-btn"
                      :disabled="
                        isCloseLocked ||
                        isLockedExecutionRow(row) ||
                        expenseExecutionBusyEntryId === row.entry.id
                      "
                      title="Poner importe ejecutado a 0"
                      @click="resetExpenseCheckinDraftValue(row, 'zero')"
                    >
                      Borrar
                    </button>
                    <button
                      type="button"
                      class="btn ui-budget-checkin-mini-btn"
                      :disabled="
                        isCloseLocked ||
                        isLockedExecutionRow(row) ||
                        expenseExecutionBusyEntryId === row.entry.id
                      "
                      title="Restaurar importe previsto del mes"
                      @click="resetExpenseCheckinDraftValue(row, 'planned')"
                    >
                      Previsto
                    </button>
                  </div>
                  <input
                    :value="expenseAdjustAmounts[row.entry.id] ?? ''"
                    inputmode="decimal"
                    class="input ui-data-field"
                    :disabled="isCloseLocked || isLockedExecutionRow(row)"
                    placeholder="Importe ejecutado"
                    @input="
                      setExpenseAdjustAmount(
                        row.entry.id,
                        ($event.target as HTMLInputElement).value,
                      )
                    "
                    @focus="ensureExpenseAdjustAmountPrefilled(row)"
                    @blur="onExpenseAdjustAmountBlur(row)"
                    @keydown.enter.prevent="saveExpenseCheckinFromInput(row)"
                  />
                </div>
                <label class="ui-budget-checkin-confirm" title="Confirmar check-in del mes">
                  <input
                    type="checkbox"
                    :checked="row.executionSource !== 'none'"
                    :disabled="
                      isCloseLocked ||
                      isLockedExecutionRow(row) ||
                      expenseExecutionBusyEntryId === row.entry.id
                    "
                    aria-label="Confirmar check-in del mes"
                    @change="
                      onExpenseCheckinCheckboxToggle(
                        row,
                        Boolean(($event.target as HTMLInputElement).checked),
                      )
                    "
                  />
                </label>
              </div>
            </article>
          </div>
        </details>
      </div>
    </div>
  </section>
</template>
