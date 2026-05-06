<script setup lang="ts">
import type { AnnualIncomeEntry } from '@/domains/data-input';

type MonthlyCloseStepId = 'liq' | 'income' | 'expense' | 'result';
type IncomeResetMode = 'zero' | 'planned';
type IncomeExecutionOrigin =
  | 'categorized_ledger'
  | 'legacy_ledger'
  | 'legacy_checkin'
  | 'ambiguous_taxonomy'
  | 'none';
type IncomeExecutionSource =
  | 'categorized_ledger'
  | 'legacy_fallback'
  | 'pending_classification'
  | 'none';

type IncomeCheckin = {
  id: number;
  annual_income_entry_id: number;
  fiscal_year: number;
  month: number;
  status: 'confirmed' | 'adjusted' | 'skipped' | 'estimated';
  executed_amount: string | null;
  note: string;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
};

type IncomeRow = {
  entry: AnnualIncomeEntry;
  planned: number;
  executed: number | null;
  categorizedLedgerExecuted: number | null;
  legacyLedgerExecuted: number | null;
  executionSource: IncomeExecutionSource;
  executionOrigin: IncomeExecutionOrigin;
  checkin: IncomeCheckin | null;
};

type IncomeGroup = {
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
  rows: IncomeRow[];
  editableRow: IncomeRow | null;
};

function hasManualIncomeAdjustment(group: IncomeGroup): boolean {
  return Math.abs(group.executedTotal - group.ledgerDetectedTotal) >= 0.005;
}

defineProps<{
  isMonthlyCloseView: boolean;
  activeMonthlyCloseStep: MonthlyCloseStepId;
  groupedMonthlyIncomeExecutionEntries: IncomeGroup[];
  incomeExecutionLoading: boolean;
  incomeExecutionError: string | null;
  incomeExecutionBusyEntryId: number | null;
  incomeAdjustAmounts: Record<number, string>;
  setIncomeAdjustAmount: (entryId: number, value: string) => void;
  selectedIncomeMonthPlanned: number;
  selectedIncomeMonthExecuted: number;
  selectedIncomeMonthDeviation: number;
  selectedIncomeMonthCompletionRatio: number | null;
  monthlyIncomeCoverageSummary: { viaLedger: number; viaFallback: number; pending: number };
  monthlyIncomeCoverageDetail: string;
  monthlyIncomeCoverageLabel: string;
  monthlyIncomePendingClassification: { amount: number; ambiguousRows: number };
  formatMoney: (value: number, decimals?: number) => string;
  formatPercent: (value: number | null, decimals?: number) => string;
  isCloseLocked?: boolean;
  checkinStatusLabel: (status: 'confirmed' | 'adjusted' | 'skipped' | 'estimated') => string;
  isIncomeGroupUnlocked: (groupKey: string) => boolean;
  goToPreviousMonthlyCloseStep: () => void;
  goToNextMonthlyCloseStep: () => void;
  resetIncomeGroupCheckinDraftValue: (
    group: IncomeGroup,
    mode: IncomeResetMode,
  ) => void | Promise<void>;
  ensureIncomeGroupAdjustAmountPrefilled: (group: IncomeGroup) => void;
  saveIncomeGroupCheckinFromInput: (group: IncomeGroup) => void | Promise<void>;
  onIncomeGroupReviewedToggle: (group: IncomeGroup, checked: boolean) => void | Promise<void>;
  unlockIncomeGroupManualAdjustment: (group: IncomeGroup) => void | Promise<void>;
  relockIncomeGroupManualAdjustment: (group: IncomeGroup) => void | Promise<void>;
}>();
</script>

<template>
  <section
    v-if="isMonthlyCloseView && activeMonthlyCloseStep === 'income'"
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
          <h2 class="ui-budget-checkin-title">Paso 2 - Check-in mensual de ingresos</h2>
          <button
            type="button"
            class="btn ui-monthly-close-step-nav-btn"
            @click="goToNextMonthlyCloseStep()"
          >
            &rarr;
          </button>
        </div>
        <p class="ui-budget-checkin-subtitle ui-budget-checkin-subtitle-note">
          Confirma los ingresos previstos del mes; el cierre usa movimientos y deja pendientes solo
          las líneas a revisar.
        </p>
      </div>
    </div>
    <div class="ui-budget-checkin-summary-grid">
      <article class="ui-budget-checkin-kpi">
        <span>Previsto mes</span>
        <strong>{{ formatMoney(selectedIncomeMonthPlanned) }} EUR</strong>
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Ejecutado mes</span>
        <strong>{{ formatMoney(selectedIncomeMonthExecuted) }} EUR</strong>
      </article>
      <article
        class="ui-budget-checkin-kpi"
        :class="{
          'ui-budget-checkin-kpi-good': selectedIncomeMonthDeviation > 0,
          'ui-budget-checkin-kpi-danger': selectedIncomeMonthDeviation < 0,
        }"
      >
        <span>Desviación del mes</span>
        <strong
          >{{ selectedIncomeMonthDeviation > 0 ? '+' : ''
          }}{{ formatMoney(selectedIncomeMonthDeviation) }} EUR</strong
        >
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Revisión</span>
        <strong>{{ formatPercent(selectedIncomeMonthCompletionRatio, 0) }}</strong>
      </article>
    </div>
    <div v-if="isCloseLocked" class="ui-monthly-close-locked-banner">
      Este mes está finalizado. Reabre el cierre para editar.
    </div>

    <div class="ui-budget-checkin-list">
      <div v-if="incomeExecutionLoading" class="subtle">Cargando check-ins de ingresos...</div>
      <div v-else-if="incomeExecutionError" class="subtle text-red-400">
        {{ incomeExecutionError }}
      </div>
      <div v-else-if="!groupedMonthlyIncomeExecutionEntries.length" class="subtle">
        No hay ingresos previstos para este mes.
      </div>
      <div v-else class="ui-budget-checkin-groups-box">
        <div
          v-if="monthlyIncomePendingClassification.amount > 0"
          class="ui-state-block ui-state-error"
        >
          <strong>Sin subcategoría</strong>
          <span>
            {{ formatMoney(monthlyIncomePendingClassification.amount) }} EUR del libro contable no
            tiene subcategoría de presupuesto todavía.
          </span>
          <small v-if="monthlyIncomePendingClassification.ambiguousRows > 0">
            {{ monthlyIncomePendingClassification.ambiguousRows }} líneas comparten la misma
            subcategoría y requieren revisión manual.
          </small>
        </div>
        <div class="ui-budget-checkin-group">
          <div class="ui-budget-checkin-group-rows ui-budget-checkin-subcategory-rows">
            <article
              v-for="group in groupedMonthlyIncomeExecutionEntries"
              :key="`income-checkin-group-${group.key}`"
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
                      'ui-budget-checkin-income-dev-neg': group.deviation < 0,
                      'ui-budget-checkin-income-dev-pos': group.deviation > 0,
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
                  v-if="group.editableRow && !isIncomeGroupUnlocked(group.key)"
                  class="ui-budget-checkin-adjust"
                >
                  <div
                    v-if="hasManualIncomeAdjustment(group)"
                    class="ui-budget-checkin-ledger-readout"
                  >
                    <span>Movimientos</span>
                    <strong>{{ formatMoney(group.ledgerDetectedTotal) }} EUR</strong>
                  </div>
                  <button
                    type="button"
                    class="btn ui-budget-checkin-mini-btn ui-budget-checkin-add-btn"
                    :disabled="
                      isCloseLocked || incomeExecutionBusyEntryId === group.editableRow.entry.id
                    "
                    title="Añadir un ingreso manual a esta subcategoría sin tocar el libro contable"
                    @click="unlockIncomeGroupManualAdjustment(group)"
                  >
                    Añadir ingreso
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
                        incomeExecutionBusyEntryId === group.editableRow.entry.id
                      "
                      aria-label="Marcar subcategoría de ingresos como revisada"
                      @change="
                        onIncomeGroupReviewedToggle(
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
                    :value="incomeAdjustAmounts[group.editableRow.entry.id] ?? ''"
                    inputmode="decimal"
                    class="input ui-data-field"
                    :disabled="isCloseLocked"
                    placeholder="Ingreso adicional"
                    @input="
                      setIncomeAdjustAmount(
                        group.editableRow.entry.id,
                        ($event.target as HTMLInputElement).value,
                      )
                    "
                    @focus="ensureIncomeGroupAdjustAmountPrefilled(group)"
                    @blur="saveIncomeGroupCheckinFromInput(group)"
                    @keydown.enter.prevent="saveIncomeGroupCheckinFromInput(group)"
                  />
                  <div
                    class="ui-budget-checkin-quick-actions ui-budget-checkin-quick-actions-inline"
                  >
                    <button
                      type="button"
                      class="btn ui-budget-checkin-mini-btn"
                      :disabled="
                        isCloseLocked || incomeExecutionBusyEntryId === group.editableRow.entry.id
                      "
                      @click="resetIncomeGroupCheckinDraftValue(group, 'planned')"
                    >
                      Previsto
                    </button>
                    <button
                      type="button"
                      class="btn ui-budget-checkin-mini-btn ui-budget-checkin-link-btn"
                      :disabled="
                        isCloseLocked || incomeExecutionBusyEntryId === group.editableRow.entry.id
                      "
                      title="Guardar el ingreso adicional"
                      @click="saveIncomeGroupCheckinFromInput(group)"
                    >
                      Guardar
                    </button>
                    <button
                      type="button"
                      class="btn ui-budget-checkin-mini-btn ui-budget-checkin-link-btn"
                      :disabled="
                        isCloseLocked || incomeExecutionBusyEntryId === group.editableRow.entry.id
                      "
                      title="Volver a usar sólo el importe detectado en el libro contable"
                      @click="relockIncomeGroupManualAdjustment(group)"
                    >
                      Usar detectado
                    </button>
                  </div>
                </div>
              </div>
            </article>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
