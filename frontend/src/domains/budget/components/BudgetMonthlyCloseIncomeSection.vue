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

defineProps<{
  isMonthlyCloseView: boolean;
  activeMonthlyCloseStep: MonthlyCloseStepId;
  monthlyIncomeExecutionEntries: IncomeRow[];
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
  executionSourceLabel: (origin: IncomeExecutionOrigin) => string;
  incomeCheckinRowSummary: (row: IncomeRow) => string;
  isCloseLocked?: boolean;
  checkinStatusLabel: (status: 'confirmed' | 'adjusted' | 'skipped' | 'estimated') => string;
  isLockedExecutionRow: (row: IncomeRow) => boolean;
  goToPreviousMonthlyCloseStep: () => void;
  goToNextMonthlyCloseStep: () => void;
  resetIncomeCheckinDraftValue: (row: IncomeRow, mode: IncomeResetMode) => void | Promise<void>;
  ensureIncomeAdjustAmountPrefilled: (row: IncomeRow) => void;
  onIncomeAdjustAmountBlur: (row: IncomeRow) => void | Promise<void>;
  saveIncomeCheckinFromInput: (row: IncomeRow) => void | Promise<void>;
  onIncomeCheckinCheckboxToggle: (row: IncomeRow, checked: boolean) => void | Promise<void>;
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
          <h2 class="ui-budget-checkin-title">Paso 2 ? Check-in mensual de ingresos</h2>
          <button
            type="button"
            class="btn ui-monthly-close-step-nav-btn"
            @click="goToNextMonthlyCloseStep()"
          >
            &rarr;
          </button>
        </div>
        <p class="ui-budget-checkin-subtitle">
          Confirma o ajusta ingresos recurrentes del mes. Los puntuales se integraran cuando tengan
          mes objetivo.
        </p>
        <p class="ui-budget-checkin-subtitle ui-budget-checkin-subtitle-note">
          Ledger categorizado por taxonomia compartida y fallback legacy solo cuando esa
          clasificacion todavia no exista.
        </p>
      </div>
    </div>
    <div class="ui-budget-checkin-summary-grid">
      <article class="ui-budget-checkin-kpi">
        <span>Previsto mes</span>
        <strong>{{ formatMoney(selectedIncomeMonthPlanned) }} â‚¬</strong>
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Ejecutado mes</span>
        <strong>{{ formatMoney(selectedIncomeMonthExecuted) }} â‚¬</strong>
      </article>
      <article
        class="ui-budget-checkin-kpi"
        :class="{
          'ui-budget-checkin-kpi-good': selectedIncomeMonthDeviation > 0,
          'ui-budget-checkin-kpi-danger': selectedIncomeMonthDeviation < 0,
        }"
      >
        <span>Desviacion del mes</span>
        <strong
          >{{ selectedIncomeMonthDeviation > 0 ? '+' : ''
          }}{{ formatMoney(selectedIncomeMonthDeviation) }} â‚¬</strong
        >
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Completitud</span>
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
      <div v-else-if="!monthlyIncomeExecutionEntries.length" class="subtle">
        No hay ingresos recurrentes previstos para este mes.
      </div>
      <div v-else class="ui-budget-checkin-groups-box">
        <div class="ui-budget-execution-note">
          <div class="ui-budget-execution-note-main">
            <strong>Cobertura del mes</strong>
            <span>
              {{ monthlyIncomeCoverageSummary.viaLedger }} via ledger categorizado Â·
              {{ monthlyIncomeCoverageSummary.viaFallback }} via fallback legacy Â·
              {{ monthlyIncomeCoverageSummary.pending }} pendientes
            </span>
            <small class="ui-budget-execution-note-detail">{{ monthlyIncomeCoverageDetail }}</small>
          </div>
          <span class="ui-budget-execution-badge">{{ monthlyIncomeCoverageLabel }}</span>
        </div>
        <div
          v-if="monthlyIncomePendingClassification.amount > 0"
          class="ui-state-block ui-state-error"
        >
          <strong>Pendiente clasificar</strong>
          <span>
            {{ formatMoney(monthlyIncomePendingClassification.amount) }} EUR del ledger no se puede
            alinear automaticamente con el presupuesto de este mes.
          </span>
          <small v-if="monthlyIncomePendingClassification.ambiguousRows > 0">
            {{ monthlyIncomePendingClassification.ambiguousRows }} lineas comparten la misma
            subcategoria y requieren revision manual.
          </small>
        </div>
        <div class="ui-budget-checkin-group">
          <div class="ui-budget-checkin-group-summary">
            <div class="ui-budget-checkin-group-title-wrap">
              <strong class="ui-budget-checkin-group-title">Ingresos recurrentes</strong>
              <span class="ui-budget-checkin-group-meta">
                {{ monthlyIncomeExecutionEntries.length }} lineas Â·
                {{ formatPercent(selectedIncomeMonthCompletionRatio, 0) }} completitud
              </span>
            </div>
            <div class="ui-budget-checkin-group-kpis">
              <span>P {{ formatMoney(selectedIncomeMonthPlanned) }} â‚¬</span>
              <span>E {{ formatMoney(selectedIncomeMonthExecuted) }} â‚¬</span>
              <span
                :class="{
                  'ui-budget-checkin-group-dev-pos': selectedIncomeMonthDeviation > 0,
                  'ui-budget-checkin-group-dev-neg': selectedIncomeMonthDeviation < 0,
                }"
              >
                D {{ selectedIncomeMonthDeviation > 0 ? '+' : ''
                }}{{ formatMoney(selectedIncomeMonthDeviation) }} â‚¬
              </span>
            </div>
          </div>
          <div class="ui-budget-checkin-group-rows">
            <article
              v-for="row in monthlyIncomeExecutionEntries"
              :key="`income-checkin-${row.entry.id}`"
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
                <div class="ui-budget-checkin-row-title" :title="incomeCheckinRowSummary(row)">
                  <span
                    v-if="row.checkin?.status === 'estimated'"
                    class="ui-budget-checkin-estimated-badge"
                    >Estimado</span
                  >
                  {{ incomeCheckinRowSummary(row) }}
                  <span class="ui-budget-checkin-row-planned"
                    >(Previsto {{ formatMoney(row.planned) }} €)</span
                  >
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
                    Edicion legacy bloqueada
                  </span>
                  <span v-else class="ui-budget-checkin-row-lock-note">
                    Varias lineas comparten esta subcategoria.
                  </span>
                </div>
                <div
                  v-if="row.executionOrigin === 'legacy_checkin' && row.checkin"
                  class="ui-budget-checkin-row-state"
                >
                  <strong>{{ checkinStatusLabel(row.checkin.status) }}</strong>
                  <template v-if="row.checkin.status !== 'skipped' && row.executed != null">
                    ({{ formatMoney(row.executed) }} â‚¬)
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
                        incomeExecutionBusyEntryId === row.entry.id
                      "
                      @click="resetIncomeCheckinDraftValue(row, 'zero')"
                    >
                      Borrar
                    </button>
                    <button
                      type="button"
                      class="btn ui-budget-checkin-mini-btn"
                      :disabled="
                        isCloseLocked ||
                        isLockedExecutionRow(row) ||
                        incomeExecutionBusyEntryId === row.entry.id
                      "
                      @click="resetIncomeCheckinDraftValue(row, 'planned')"
                    >
                      Previsto
                    </button>
                  </div>
                  <input
                    :value="incomeAdjustAmounts[row.entry.id] ?? ''"
                    inputmode="decimal"
                    class="input ui-data-field"
                    :disabled="isCloseLocked || isLockedExecutionRow(row)"
                    placeholder="Importe ejecutado"
                    @input="
                      setIncomeAdjustAmount(row.entry.id, ($event.target as HTMLInputElement).value)
                    "
                    @focus="ensureIncomeAdjustAmountPrefilled(row)"
                    @blur="onIncomeAdjustAmountBlur(row)"
                    @keydown.enter.prevent="saveIncomeCheckinFromInput(row)"
                  />
                </div>
                <label class="ui-budget-checkin-confirm" title="Confirmar check-in del mes">
                  <input
                    type="checkbox"
                    :checked="row.executionSource !== 'none'"
                    :disabled="
                      isCloseLocked ||
                      isLockedExecutionRow(row) ||
                      incomeExecutionBusyEntryId === row.entry.id
                    "
                    @change="
                      onIncomeCheckinCheckboxToggle(
                        row,
                        Boolean(($event.target as HTMLInputElement).checked),
                      )
                    "
                  />
                </label>
              </div>
            </article>
          </div>
        </div>
      </div>
    </div>
  </section>
</template>
