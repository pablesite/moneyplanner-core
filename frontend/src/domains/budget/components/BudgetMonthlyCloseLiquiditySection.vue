<script setup lang="ts">
type MonthlyCloseStepId = 'liq' | 'income' | 'expense' | 'result';
type LiquidityResetMode = 'zero' | 'planned';

type LiquidityRow = {
  asset_id: number;
  asset_name: string;
  asset_category: string;
  asset_subcategory: string;
  planned: number;
  executed: number | null;
  currency: string;
  coverage_source?: 'ledger' | 'checkin' | 'none';
  planned_closing_balance: string;
  executed_closing_balance: string | null;
  effective_closing_balance: string;
  deviation: string;
  planned_closing_balance_base: string;
  executed_closing_balance_base: string | null;
  effective_closing_balance_base: string;
  deviation_base: string;
  checkin: {
    id: number;
    status: 'confirmed' | 'adjusted';
    closing_balance_real: string;
    note: string;
    confirmed_at: string | null;
    updated_at: string | null;
  } | null;
};

defineProps<{
  isMonthlyCloseView: boolean;
  activeMonthlyCloseStep: MonthlyCloseStepId;
  isCloseLocked?: boolean;
  previousMonthlyCloseStep: MonthlyCloseStepId | null;
  monthLabels: string[];
  selectedExecutionMonth: number;
  liquidityMonthlySummary: { completion_ratio?: number | null } | null;
  liquidityExecutionLoading: boolean;
  liquidityExecutionBusyAssetId: number | null;
  monthlyLiquidityExecutionRows: LiquidityRow[];
  selectedLiquidityMonthPlanned: number;
  selectedLiquidityMonthExecuted: number;
  selectedLiquidityMonthDeviation: number;
  liquidityAdjustAmounts: Record<number, string>;
  setLiquidityAdjustAmount: (assetId: number, value: string) => void;
  formatMoney: (value: number, decimals?: number) => string;
  formatPercent: (value: number | null, decimals?: number) => string;
  checkinStatusLabel: (status: 'confirmed' | 'adjusted' | 'skipped') => string;
  liquidityCheckinRowSummary: (row: LiquidityRow) => string;
  goToPreviousMonthlyCloseStep: () => void;
  goToNextMonthlyCloseStep: () => void;
  updateSelectedExecutionMonth: (value: number) => void;
  resetLiquidityCheckinDraftValue: (
    row: LiquidityRow,
    mode: LiquidityResetMode,
  ) => void | Promise<void>;
  ensureLiquidityAdjustAmountPrefilled: (row: LiquidityRow) => void;
  onLiquidityAdjustAmountBlur: (row: LiquidityRow) => void | Promise<void>;
  saveLiquidityCheckinFromInput: (row: LiquidityRow) => void | Promise<void>;
  onLiquidityCheckinCheckboxToggle: (row: LiquidityRow, checked: boolean) => void | Promise<void>;
}>();
</script>

<template>
  <section
    v-if="isMonthlyCloseView && activeMonthlyCloseStep === 'liq'"
    class="card ui-pro-panel ui-budget-checkin mt-3"
  >
    <div class="ui-budget-checkin-header">
      <div>
        <div v-if="isMonthlyCloseView" class="ui-monthly-close-step-headline">
          <button
            type="button"
            class="btn ui-monthly-close-step-nav-btn"
            :disabled="!previousMonthlyCloseStep"
            @click="goToPreviousMonthlyCloseStep()"
          >
            ←
          </button>
          <h2 class="ui-budget-checkin-title">Paso 1 · Cierre de liquidez</h2>
          <button
            type="button"
            class="btn ui-monthly-close-step-nav-btn"
            @click="goToNextMonthlyCloseStep()"
          >
            →
          </button>
        </div>
        <h2 v-else class="ui-budget-checkin-title">Cierre de liquidez</h2>
        <p class="ui-budget-checkin-subtitle">
          Ajusta el saldo real de cuentas y activos liquidos para el mes seleccionado (14C v1).
        </p>
      </div>
      <div v-if="!isMonthlyCloseView" class="ui-budget-checkin-controls">
        <label>
          <span>Mes</span>
          <select
            :value="selectedExecutionMonth"
            class="select ui-data-field"
            :disabled="liquidityExecutionLoading"
            @change="
              updateSelectedExecutionMonth(Number(($event.target as HTMLSelectElement).value))
            "
          >
            <option v-for="(label, index) in monthLabels" :key="`liq-${label}`" :value="index + 1">
              {{ label }}
            </option>
          </select>
        </label>
      </div>
    </div>

    <div v-if="liquidityMonthlySummary" class="ui-budget-checkin-summary-grid">
      <article class="ui-budget-checkin-kpi">
        <span>Saldo referencia</span>
        <strong>{{ formatMoney(selectedLiquidityMonthPlanned) }} €</strong>
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Real cierre</span>
        <strong>{{ formatMoney(selectedLiquidityMonthExecuted) }} €</strong>
      </article>
      <article
        class="ui-budget-checkin-kpi"
        :class="{
          'ui-budget-checkin-kpi-danger': selectedLiquidityMonthDeviation < 0,
          'ui-budget-checkin-kpi-good': selectedLiquidityMonthDeviation > 0,
        }"
      >
        <span>Desviacion liquidez</span>
        <strong>
          {{ selectedLiquidityMonthDeviation > 0 ? '+' : ''
          }}{{ formatMoney(selectedLiquidityMonthDeviation) }} €
        </strong>
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Completitud</span>
        <strong>{{ formatPercent(liquidityMonthlySummary.completion_ratio ?? null, 0) }}</strong>
      </article>
    </div>

    <div v-if="isCloseLocked" class="ui-monthly-close-locked-banner">
      Este mes está finalizado. Reabre el cierre para editar.
    </div>

    <div class="ui-budget-checkin-list">
      <div v-if="liquidityExecutionLoading" class="subtle">Cargando cierre de liquidez...</div>
      <div v-else-if="!monthlyLiquidityExecutionRows.length" class="subtle">
        No hay activos de liquidez activos para este mes.
      </div>
      <div v-else class="ui-budget-checkin-groups-box">
        <div class="ui-budget-checkin-group">
          <div class="ui-budget-checkin-group-summary">
            <div class="ui-budget-checkin-group-title-wrap">
              <strong class="ui-budget-checkin-group-title">Activos liquidos</strong>
              <span class="ui-budget-checkin-group-meta">
                {{ monthlyLiquidityExecutionRows.length }} cuentas ·
                {{ formatPercent(liquidityMonthlySummary?.completion_ratio ?? null, 0) }}
                completitud
              </span>
            </div>
            <div class="ui-budget-checkin-group-kpis">
              <span>Ref {{ formatMoney(selectedLiquidityMonthPlanned) }} €</span>
              <span>E {{ formatMoney(selectedLiquidityMonthExecuted) }} €</span>
              <span
                :class="{
                  'ui-budget-checkin-group-dev-pos': selectedLiquidityMonthDeviation > 0,
                  'ui-budget-checkin-group-dev-neg': selectedLiquidityMonthDeviation < 0,
                }"
              >
                D {{ selectedLiquidityMonthDeviation > 0 ? '+' : ''
                }}{{ formatMoney(selectedLiquidityMonthDeviation) }} €
              </span>
            </div>
          </div>

          <div class="ui-budget-checkin-group-rows">
            <article
              v-for="row in monthlyLiquidityExecutionRows"
              :key="`liquidity-checkin-${row.asset_id}`"
              class="ui-budget-checkin-row"
            >
              <div class="ui-budget-checkin-row-main">
                <div class="ui-budget-checkin-row-title" :title="liquidityCheckinRowSummary(row)">
                  {{ liquidityCheckinRowSummary(row) }}
                  <span class="ui-budget-checkin-row-planned">
                    (Referencia {{ formatMoney(row.planned) }}
                    {{ row.currency === 'EUR' ? '€' : row.currency }})
                  </span>
                </div>
                <div v-if="row.coverage_source === 'ledger'" class="ui-budget-checkin-row-state">
                  <strong>Ledger</strong>
                  <template v-if="row.executed != null">
                    ({{ formatMoney(row.executed) }}
                    {{ row.currency === 'EUR' ? '€' : row.currency }})
                  </template>
                </div>
                <div v-else-if="row.checkin" class="ui-budget-checkin-row-state">
                  <strong>{{ checkinStatusLabel(row.checkin.status) }}</strong>
                  <template v-if="row.executed != null">
                    ({{ formatMoney(row.executed) }}
                    {{ row.currency === 'EUR' ? '€' : row.currency }})
                  </template>
                </div>
              </div>

              <div class="ui-budget-checkin-row-actions">
                <div v-if="row.coverage_source === 'ledger'" class="ui-budget-checkin-adjust">
                  <span class="ui-budget-checkin-ledger-lock" title="Cubierto por ledger contable">
                    🔒 Ledger
                  </span>
                </div>
                <div v-else class="ui-budget-checkin-adjust">
                  <div class="ui-budget-checkin-quick-actions">
                    <button
                      type="button"
                      class="btn ui-budget-checkin-mini-btn"
                      :disabled="isCloseLocked || liquidityExecutionBusyAssetId === row.asset_id"
                      title="Poner saldo real a 0"
                      @click="resetLiquidityCheckinDraftValue(row, 'zero')"
                    >
                      Borrar
                    </button>
                    <button
                      type="button"
                      class="btn ui-budget-checkin-mini-btn"
                      :disabled="isCloseLocked || liquidityExecutionBusyAssetId === row.asset_id"
                      title="Restaurar saldo de referencia"
                      @click="resetLiquidityCheckinDraftValue(row, 'planned')"
                    >
                      Referencia
                    </button>
                  </div>
                  <input
                    :value="liquidityAdjustAmounts[row.asset_id] ?? ''"
                    inputmode="decimal"
                    class="input ui-data-field"
                    :disabled="isCloseLocked"
                    placeholder="Saldo real"
                    @input="
                      setLiquidityAdjustAmount(
                        row.asset_id,
                        ($event.target as HTMLInputElement).value,
                      )
                    "
                    @focus="ensureLiquidityAdjustAmountPrefilled(row)"
                    @blur="onLiquidityAdjustAmountBlur(row)"
                    @keydown.enter.prevent="saveLiquidityCheckinFromInput(row)"
                  />
                </div>
                <label class="ui-budget-checkin-confirm" title="Confirmar cierre de liquidez">
                  <input
                    type="checkbox"
                    :checked="row.coverage_source === 'ledger' || !!row.checkin"
                    :disabled="
                      isCloseLocked ||
                      row.coverage_source === 'ledger' ||
                      liquidityExecutionBusyAssetId === row.asset_id
                    "
                    aria-label="Confirmar cierre de liquidez"
                    @change="
                      onLiquidityCheckinCheckboxToggle(
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
