<script setup lang="ts">
import { computed } from 'vue';
import type { AnnualExpenseEntry } from '@/domains/data-input';

type MonthlyCloseStepId = 'liq' | 'income' | 'expense' | 'result';
type ExpenseResetMode = 'zero' | 'planned';
type ExpenseExecutionOrigin =
  | 'categorized_ledger'
  | 'legacy_ledger'
  | 'user_override'
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

type ExpenseExecutionEntry = AnnualExpenseEntry & {
  baseAmountAnnual: number;
};

type ExpenseRow = {
  entry: ExpenseExecutionEntry;
  planned: number;
  executed: number | null;
  categorizedLedgerExecuted: number | null;
  legacyLedgerExecuted: number | null;
  executionSource: ExpenseExecutionSource;
  executionOrigin: ExpenseExecutionOrigin;
  checkin: ExpenseCheckin | null;
};

type ExpenseGroup = {
  key: string;
  categoryKey: string;
  categoryLabel: string;
  subcategoryKey: string;
  subcategoryLabel: string;
  plannedTotal: number;
  ledgerDetectedTotal: number;
  executedTotal: number;
  deviation: number;
  completionRatio: number;
  checkedCount: number;
  rows: ExpenseRow[];
  editableRow: ExpenseRow | null;
};

type ExpenseCategoryBlock = {
  key: string;
  label: string;
  plannedTotal: number;
  executedTotal: number;
  deviation: number;
  completionRatio: number;
  reviewedCount: number;
  groups: ExpenseGroup[];
};

function hasManualExpenseAdjustment(group: ExpenseGroup): boolean {
  return Math.abs(group.executedTotal - group.ledgerDetectedTotal) >= 0.005;
}

const props = defineProps<{
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
  isExpenseGroupUnlocked: (groupKey: string) => boolean;
  goToPreviousMonthlyCloseStep: () => void;
  goToNextMonthlyCloseStep: () => void;
  resetExpenseCheckinDraftValue: (row: ExpenseRow, mode: ExpenseResetMode) => void | Promise<void>;
  resetExpenseGroupCheckinDraftValue: (
    group: ExpenseGroup,
    mode: ExpenseResetMode,
  ) => void | Promise<void>;
  ensureExpenseAdjustAmountPrefilled: (row: ExpenseRow) => void;
  ensureExpenseGroupAdjustAmountPrefilled: (group: ExpenseGroup) => void;
  onExpenseAdjustAmountBlur: (row: ExpenseRow) => void | Promise<void>;
  saveExpenseCheckinFromInput: (row: ExpenseRow) => void | Promise<void>;
  saveExpenseGroupCheckinFromInput: (group: ExpenseGroup) => void | Promise<void>;
  onExpenseCheckinCheckboxToggle: (row: ExpenseRow, checked: boolean) => void | Promise<void>;
  onExpenseGroupReviewedToggle: (group: ExpenseGroup, checked: boolean) => void | Promise<void>;
  unlockExpenseGroupManualAdjustment: (group: ExpenseGroup) => void | Promise<void>;
  relockExpenseGroupManualAdjustment: (group: ExpenseGroup) => void | Promise<void>;
}>();

const expenseCategoryBlocks = computed<ExpenseCategoryBlock[]>(() => {
  const blocks = new Map<string, ExpenseCategoryBlock>();

  for (const group of props.groupedMonthlyExpenseExecutionEntries) {
    let block = blocks.get(group.categoryKey);
    if (!block) {
      block = {
        key: group.categoryKey,
        label: group.categoryLabel,
        plannedTotal: 0,
        executedTotal: 0,
        deviation: 0,
        completionRatio: 0,
        reviewedCount: 0,
        groups: [],
      };
      blocks.set(group.categoryKey, block);
    }

    block.groups.push(group);
    block.plannedTotal += group.plannedTotal;
    block.executedTotal += group.executedTotal;
    if (group.ledgerDetectedTotal > 0 || group.checkedCount > 0) block.reviewedCount += 1;
  }

  return Array.from(blocks.values()).map((block) => ({
    ...block,
    deviation: block.executedTotal - block.plannedTotal,
    completionRatio: block.groups.length ? block.reviewedCount / block.groups.length : 1,
  }));
});
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
          Confirma los gastos previstos del mes; el cierre usa movimientos y deja pendientes solo
          las líneas a revisar.
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
        <span>Revisión</span>
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
        <details
          v-for="block in expenseCategoryBlocks"
          :key="`expense-checkin-category-${block.key}`"
          class="ui-budget-checkin-group"
          :open="block.completionRatio < 1 || block.deviation > 0"
        >
          <summary class="ui-budget-checkin-group-summary">
            <div class="ui-budget-checkin-group-title-wrap">
              <strong class="ui-budget-checkin-group-title">{{ block.label }}</strong>
              <span class="ui-budget-checkin-group-meta">
                {{ block.groups.length }} subcategorías -
                {{ Math.round(block.completionRatio * 100) }} % revisión
              </span>
            </div>
            <div class="ui-budget-checkin-group-kpis">
              <span>P {{ formatMoney(block.plannedTotal) }} EUR</span>
              <span>E {{ formatMoney(block.executedTotal) }} EUR</span>
              <span
                :class="{
                  'ui-budget-checkin-group-dev-pos': block.deviation > 0,
                  'ui-budget-checkin-group-dev-neg': block.deviation < 0,
                }"
              >
                D {{ block.deviation > 0 ? '+' : '' }}{{ formatMoney(block.deviation) }} EUR
              </span>
            </div>
          </summary>

          <div class="ui-budget-checkin-group-rows ui-budget-checkin-subcategory-rows">
            <article
              v-for="group in block.groups"
              :key="`expense-checkin-group-${group.key}`"
              class="ui-budget-checkin-row"
              :class="{
                'ui-budget-checkin-row-estimated':
                  group.editableRow?.checkin?.status === 'estimated',
              }"
            >
              <div class="ui-budget-checkin-row-main">
                <div class="ui-budget-checkin-row-title" :title="group.subcategoryLabel">
                  <span
                    v-if="group.editableRow?.checkin?.status === 'estimated'"
                    class="ui-budget-checkin-estimated-badge"
                    >Estimado</span
                  >
                  {{ group.subcategoryLabel }}
                </div>
                <div class="ui-budget-checkin-row-state ui-budget-checkin-subcategory-meta">
                  <span>{{ group.categoryLabel }}</span>
                  <span v-if="group.rows.length > 1">{{ group.rows.length }} líneas agrupadas</span>
                  <span v-if="group.editableRow?.checkin">
                    {{ checkinStatusLabel(group.editableRow.checkin.status) }}
                  </span>
                </div>
              </div>
              <div class="ui-budget-checkin-row-actions">
                <div class="ui-budget-checkin-subcategory-metrics">
                  <span>
                    <small>Previsto</small>
                    <strong>{{ formatMoney(group.plannedTotal) }} EUR</strong>
                  </span>
                  <span>
                    <small>Ejecutado</small>
                    <strong>{{ formatMoney(group.executedTotal) }} EUR</strong>
                  </span>
                  <span
                    :class="{
                      'ui-budget-checkin-group-dev-pos': group.deviation > 0,
                      'ui-budget-checkin-group-dev-neg': group.deviation < 0,
                    }"
                  >
                    <small>Desv.</small>
                    <strong
                      >{{ group.deviation > 0 ? '+' : ''
                      }}{{ formatMoney(group.deviation) }} EUR</strong
                    >
                  </span>
                </div>
                <div
                  v-if="group.editableRow && !isExpenseGroupUnlocked(group.key)"
                  class="ui-budget-checkin-adjust"
                >
                  <div
                    v-if="hasManualExpenseAdjustment(group)"
                    class="ui-budget-checkin-ledger-readout"
                  >
                    <span>Movimientos</span>
                    <strong>{{ formatMoney(group.ledgerDetectedTotal) }} EUR</strong>
                  </div>
                  <button
                    type="button"
                    class="btn ui-budget-checkin-mini-btn ui-budget-checkin-add-btn"
                    :disabled="
                      isCloseLocked || expenseExecutionBusyEntryId === group.editableRow.entry.id
                    "
                    title="Añadir un gasto manual a esta subcategoría sin tocar el libro contable"
                    @click="unlockExpenseGroupManualAdjustment(group)"
                  >
                    Añadir gasto
                  </button>
                  <label
                    class="ui-budget-checkin-confirm"
                    title="Marcar esta subcategoría como revisada"
                  >
                    <input
                      type="checkbox"
                      :checked="group.checkedCount > 0"
                      :disabled="
                        isCloseLocked ||
                        group.ledgerDetectedTotal > 0 ||
                        expenseExecutionBusyEntryId === group.editableRow.entry.id
                      "
                      aria-label="Marcar subcategoría de gastos como revisada"
                      @change="
                        onExpenseGroupReviewedToggle(
                          group,
                          Boolean(($event.target as HTMLInputElement).checked),
                        )
                      "
                    />
                  </label>
                </div>
                <div
                  v-else-if="group.editableRow"
                  class="ui-budget-checkin-adjust ui-budget-checkin-adjust-ledger-manual"
                >
                  <div class="ui-budget-checkin-ledger-readout">
                    <span>Movimientos</span>
                    <strong>{{ formatMoney(group.ledgerDetectedTotal) }} EUR</strong>
                  </div>
                  <input
                    :value="expenseAdjustAmounts[group.editableRow.entry.id] ?? ''"
                    inputmode="decimal"
                    class="input ui-data-field"
                    :disabled="isCloseLocked"
                    placeholder="Gasto adicional"
                    @input="
                      setExpenseAdjustAmount(
                        group.editableRow.entry.id,
                        ($event.target as HTMLInputElement).value,
                      )
                    "
                    @focus="ensureExpenseGroupAdjustAmountPrefilled(group)"
                    @blur="saveExpenseGroupCheckinFromInput(group)"
                    @keydown.enter.prevent="saveExpenseGroupCheckinFromInput(group)"
                  />
                  <div
                    class="ui-budget-checkin-quick-actions ui-budget-checkin-quick-actions-inline"
                  >
                    <button
                      type="button"
                      class="btn ui-budget-checkin-mini-btn"
                      :disabled="
                        isCloseLocked || expenseExecutionBusyEntryId === group.editableRow.entry.id
                      "
                      @click="resetExpenseGroupCheckinDraftValue(group, 'planned')"
                    >
                      Previsto
                    </button>
                    <button
                      type="button"
                      class="btn ui-budget-checkin-mini-btn ui-budget-checkin-link-btn"
                      :disabled="
                        isCloseLocked || expenseExecutionBusyEntryId === group.editableRow.entry.id
                      "
                      title="Guardar el gasto adicional"
                      @click="saveExpenseGroupCheckinFromInput(group)"
                    >
                      Guardar
                    </button>
                    <button
                      type="button"
                      class="btn ui-budget-checkin-mini-btn ui-budget-checkin-link-btn"
                      :disabled="
                        isCloseLocked || expenseExecutionBusyEntryId === group.editableRow.entry.id
                      "
                      title="Volver a usar sólo el importe detectado en el libro contable"
                      @click="relockExpenseGroupManualAdjustment(group)"
                    >
                      Usar detectado
                    </button>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </details>
      </div>
    </div>
  </section>
</template>
