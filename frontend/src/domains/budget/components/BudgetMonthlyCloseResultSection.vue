<script setup lang="ts">
type MonthlyCloseStepId = 'liq' | 'income' | 'expense' | 'result';
type MonthlyCloseStatus = 'draft' | 'finalized' | 'locked';
type ResultTone = 'positive' | 'warning' | 'negative' | 'neutral';
type ResultSeverity = 'ok' | 'watch' | 'alert';

type ResultFlowRow = {
  id: string;
  label: string;
  meta?: string | null;
  amount: number;
  tone: ResultTone;
  isResult?: boolean;
};

type ResultCompositionRow = {
  id: string;
  label: string;
  amount: number;
  tone: ResultTone;
  shareOfVolume: number | null;
};

type ResultBreakdownRow = {
  key: string;
  subcategoryLabel: string;
  executedTotal: number;
  shareOfExecuted: number;
  deviation: number;
};

type ResultBreakdownGroup = {
  key: string;
  categoryLabel: string;
  lineCount: number;
  plannedTotal: number;
  executedTotal: number;
  deviation: number;
  completionRatio: number;
  shareOfExecuted: number;
  rows: ResultBreakdownRow[];
};

defineProps<{
  isMonthlyCloseView: boolean;
  activeMonthlyCloseStep: MonthlyCloseStepId;
  selectedLiquidityStartBase: number;
  selectedMonthlyCloseExpected: number;
  selectedLiquidityMonthExecuted: number;
  selectedMonthlyCloseResidual: number;
  selectedIncomeMonthExecuted: number;
  selectedExpenseMonthExecuted: number;
  selectedMonthlyCloseCompletionRatio: number | null;
  selectedLiquidityMonthDeviation: number;
  selectedMonthlyExecutedVolume: number;
  selectedMonthlyResidualSeverity: ResultSeverity;
  selectedMonthlyResidualSeverityLabel: string;
  selectedMonthlyResidualVolumeRatio: number | null;
  selectedMonthlyResidualIncomeRatio: number | null;
  selectedMonthlyResidualExpenseRatio: number | null;
  selectedMonthlyResidualExpectedCloseRatio: number | null;
  resultReconciliationFlowRows: ResultFlowRow[];
  resultReconciliationCompositionRows: ResultCompositionRow[];
  monthlyIncomeExecutionEntries: Array<{ entry: { id: number } }>;
  monthlyExpenseExecutionEntries: Array<{ entry: { id: number } }>;
  monthlyIncomeResultBreakdown: ResultBreakdownGroup[];
  monthlyExpenseResultBreakdown: ResultBreakdownGroup[];
  closeStatus?: MonthlyCloseStatus;
  isCloseLocked?: boolean;
  monthlyCloseActionBusy?: boolean;
  hasDistributionSuggestion?: boolean;
  formatMoney: (value: number, decimals?: number) => string;
  formatPercent: (value: number | null, decimals?: number) => string;
  formatSignedMoney: (value: number, decimals?: number) => string;
  goToPreviousMonthlyCloseStep: () => void;
  onFinalizeClose?: () => void | Promise<void>;
  onReopenClose?: () => void | Promise<void>;
  onLockClose?: () => void | Promise<void>;
  onApplyDistribution?: () => void | Promise<void>;
}>();
</script>

<template>
  <section
    v-if="isMonthlyCloseView && activeMonthlyCloseStep === 'result'"
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
          <h2 class="ui-budget-checkin-title">Paso 4 - Resultado</h2>
          <button type="button" class="btn ui-monthly-close-step-nav-btn" disabled>&rarr;</button>
        </div>
        <p class="ui-budget-checkin-subtitle">
          Residual contable provisional a partir de liquidez real y de ingresos/gastos confirmados
          del mes.
        </p>
      </div>
    </div>

    <div class="ui-budget-checkin-summary-grid">
      <article class="ui-budget-checkin-kpi">
        <span>Liquidez mes anterior</span>
        <strong>{{ formatMoney(selectedLiquidityStartBase) }} EUR</strong>
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Cierre esperado</span>
        <strong>{{ formatMoney(selectedMonthlyCloseExpected) }} EUR</strong>
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Cierre real</span>
        <strong>{{ formatMoney(selectedLiquidityMonthExecuted) }} EUR</strong>
      </article>
      <article
        class="ui-budget-checkin-kpi"
        :class="{
          'ui-budget-checkin-kpi-danger': selectedMonthlyCloseResidual < 0,
          'ui-budget-checkin-kpi-good': selectedMonthlyCloseResidual > 0,
        }"
      >
        <span>Residual contable</span>
        <strong>
          {{ selectedMonthlyCloseResidual > 0 ? '+' : ''
          }}{{ formatMoney(selectedMonthlyCloseResidual) }} EUR
        </strong>
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Ingresos ejecutados</span>
        <strong>{{ formatMoney(selectedIncomeMonthExecuted) }} EUR</strong>
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Gastos ejecutados</span>
        <strong>{{ formatMoney(selectedExpenseMonthExecuted) }} EUR</strong>
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Completitud cierre</span>
        <strong>{{ formatPercent(selectedMonthlyCloseCompletionRatio, 0) }}</strong>
      </article>
      <article class="ui-budget-checkin-kpi">
        <span>Variación liquidez</span>
        <strong>
          {{ selectedLiquidityMonthDeviation > 0 ? '+' : ''
          }}{{ formatMoney(selectedLiquidityMonthDeviation) }} EUR
        </strong>
      </article>
    </div>

    <div class="ui-budget-result-grid">
      <section class="ui-budget-result-card">
        <div class="ui-budget-result-card-head">
          <h3 class="ui-budget-result-card-title">Conciliacion de cierre</h3>
          <div class="ui-budget-result-card-meta">
            Volumen ejecutado {{ formatMoney(selectedMonthlyExecutedVolume) }} EUR
          </div>
        </div>
        <div class="ui-budget-recon-flow">
          <div
            v-for="row in resultReconciliationFlowRows"
            :key="row.id"
            class="ui-budget-recon-flow-row"
            :class="{
              'ui-budget-recon-flow-row-result': !!row.isResult,
              'ui-budget-recon-flow-row-positive': row.tone === 'positive',
              'ui-budget-recon-flow-row-warning': row.tone === 'warning',
              'ui-budget-recon-flow-row-negative': row.tone === 'negative',
            }"
          >
            <div class="ui-budget-recon-flow-row-main">
              <div class="ui-budget-recon-flow-label">{{ row.label }}</div>
              <div v-if="row.meta" class="ui-budget-recon-flow-meta">{{ row.meta }}</div>
            </div>
            <strong class="ui-budget-recon-flow-value"
              >{{ formatSignedMoney(row.amount) }} EUR</strong
            >
          </div>
        </div>
      </section>

      <section class="ui-budget-result-card">
        <div class="ui-budget-result-card-head">
          <h3 class="ui-budget-result-card-title">Ajuste de conciliacion</h3>
          <div
            class="ui-budget-result-badge"
            :class="`ui-budget-result-badge-${selectedMonthlyResidualSeverity}`"
          >
            {{ selectedMonthlyResidualSeverityLabel }}
          </div>
        </div>
        <div class="ui-budget-result-residual-kpis">
          <article class="ui-budget-result-mini-kpi">
            <span>Residual no contabilizado</span>
            <strong>{{ formatSignedMoney(selectedMonthlyCloseResidual) }} EUR</strong>
          </article>
          <article class="ui-budget-result-mini-kpi">
            <span>% sobre volumen ejecutado</span>
            <strong>{{ formatPercent(selectedMonthlyResidualVolumeRatio, 1) }}</strong>
          </article>
          <article class="ui-budget-result-mini-kpi">
            <span>% sobre ingresos ejecutados</span>
            <strong>{{ formatPercent(selectedMonthlyResidualIncomeRatio, 1) }}</strong>
          </article>
          <article class="ui-budget-result-mini-kpi">
            <span>% sobre gastos ejecutados</span>
            <strong>{{ formatPercent(selectedMonthlyResidualExpenseRatio, 1) }}</strong>
          </article>
          <article class="ui-budget-result-mini-kpi">
            <span>% impacto sobre cierre esperado</span>
            <strong>{{ formatPercent(selectedMonthlyResidualExpectedCloseRatio, 1) }}</strong>
          </article>
          <article class="ui-budget-result-mini-kpi">
            <span>Lectura</span>
            <strong>{{
              selectedMonthlyCloseResidual < 0
                ? 'Falta caja vs explicado'
                : selectedMonthlyCloseResidual > 0
                  ? 'Sobra caja vs explicado'
                  : 'Sin diferencia'
            }}</strong>
          </article>
        </div>
        <div class="ui-budget-result-composition">
          <div
            v-for="row in resultReconciliationCompositionRows"
            :key="row.id"
            class="ui-budget-result-composition-row"
          >
            <div class="ui-budget-result-composition-main">
              <span>{{ row.label }}</span>
              <small>{{ formatSignedMoney(row.amount) }} EUR</small>
            </div>
            <div class="ui-budget-result-composition-bar">
              <div
                class="ui-budget-result-composition-fill"
                :class="{
                  'ui-budget-result-composition-fill-positive': row.tone === 'positive',
                  'ui-budget-result-composition-fill-warning': row.tone === 'warning',
                  'ui-budget-result-composition-fill-negative': row.tone === 'negative',
                }"
                :style="{
                  width: `${
                    row.shareOfVolume == null || row.shareOfVolume <= 0
                      ? 0
                      : Math.max(4, Math.min(100, row.shareOfVolume * 100))
                  }%`,
                }"
              />
            </div>
            <div class="ui-budget-result-composition-share">
              {{ formatPercent(row.shareOfVolume, 1) }}
            </div>
          </div>
        </div>
      </section>
    </div>

    <div class="ui-budget-result-grid ui-budget-result-grid-detail">
      <section class="ui-budget-result-card">
        <div class="ui-budget-result-card-head">
          <h3 class="ui-budget-result-card-title">Ingresos ejecutados (detalle del mes)</h3>
          <div class="ui-budget-result-card-meta">
            {{ monthlyIncomeExecutionEntries.length }} líneas
          </div>
        </div>
        <div v-if="!monthlyIncomeResultBreakdown.length" class="subtle">
          No hay ingresos ejecutables para este mes.
        </div>
        <div v-else class="ui-budget-result-breakdown-list">
          <article
            v-for="group in monthlyIncomeResultBreakdown"
            :key="`result-income-${group.key}`"
            class="ui-budget-result-breakdown-group"
          >
            <div class="ui-budget-result-breakdown-group-head">
              <div>
                <strong>{{ group.categoryLabel }}</strong>
                <div class="ui-budget-result-breakdown-submeta">
                  {{ group.lineCount }} líneas -
                  {{ formatPercent(group.completionRatio, 0) }} completitud
                </div>
              </div>
              <div class="ui-budget-result-breakdown-kpis">
                <span>E {{ formatMoney(group.executedTotal) }} EUR</span>
                <span>P {{ formatMoney(group.plannedTotal) }} EUR</span>
                <span
                  :class="{
                    'ui-budget-checkin-group-dev-pos': group.deviation > 0,
                    'ui-budget-checkin-group-dev-neg': group.deviation < 0,
                  }"
                >
                  D {{ formatSignedMoney(group.deviation) }} EUR
                </span>
                <span>{{ formatPercent(group.shareOfExecuted, 0) }} del total</span>
              </div>
            </div>
            <div class="ui-budget-result-breakdown-rows">
              <div
                v-for="row in group.rows.slice(0, 5)"
                :key="row.key"
                class="ui-budget-result-breakdown-row"
              >
                <span class="ui-budget-result-breakdown-name">{{ row.subcategoryLabel }}</span>
                <span>{{ formatMoney(row.executedTotal) }} EUR</span>
                <span>{{ formatPercent(row.shareOfExecuted, 0) }}</span>
                <span
                  :class="{
                    'ui-budget-checkin-group-dev-pos': row.deviation > 0,
                    'ui-budget-checkin-group-dev-neg': row.deviation < 0,
                  }"
                >
                  {{ formatSignedMoney(row.deviation) }} EUR
                </span>
              </div>
              <div v-if="group.rows.length > 5" class="ui-budget-result-breakdown-more">
                + {{ group.rows.length - 5 }} subcategorías más
              </div>
            </div>
          </article>
        </div>
      </section>

      <section class="ui-budget-result-card">
        <div class="ui-budget-result-card-head">
          <h3 class="ui-budget-result-card-title">Gastos ejecutados (detalle del mes)</h3>
          <div class="ui-budget-result-card-meta">
            {{ monthlyExpenseExecutionEntries.length }} líneas
          </div>
        </div>
        <div v-if="!monthlyExpenseResultBreakdown.length" class="subtle">
          No hay gastos ejecutables para este mes.
        </div>
        <div v-else class="ui-budget-result-breakdown-list">
          <article
            v-for="group in monthlyExpenseResultBreakdown"
            :key="`result-expense-${group.key}`"
            class="ui-budget-result-breakdown-group"
          >
            <div class="ui-budget-result-breakdown-group-head">
              <div>
                <strong>{{ group.categoryLabel }}</strong>
                <div class="ui-budget-result-breakdown-submeta">
                  {{ group.lineCount }} líneas -
                  {{ formatPercent(group.completionRatio, 0) }} completitud
                </div>
              </div>
              <div class="ui-budget-result-breakdown-kpis">
                <span>E {{ formatMoney(group.executedTotal) }} EUR</span>
                <span>P {{ formatMoney(group.plannedTotal) }} EUR</span>
                <span
                  :class="{
                    'ui-budget-checkin-group-dev-pos': group.deviation > 0,
                    'ui-budget-checkin-group-dev-neg': group.deviation < 0,
                  }"
                >
                  D {{ formatSignedMoney(group.deviation) }} EUR
                </span>
                <span>{{ formatPercent(group.shareOfExecuted, 0) }} del total</span>
              </div>
            </div>
            <div class="ui-budget-result-breakdown-rows">
              <div
                v-for="row in group.rows.slice(0, 5)"
                :key="row.key"
                class="ui-budget-result-breakdown-row"
              >
                <span class="ui-budget-result-breakdown-name">{{ row.subcategoryLabel }}</span>
                <span>{{ formatMoney(row.executedTotal) }} EUR</span>
                <span>{{ formatPercent(row.shareOfExecuted, 0) }}</span>
                <span
                  :class="{
                    'ui-budget-checkin-group-dev-pos': row.deviation > 0,
                    'ui-budget-checkin-group-dev-neg': row.deviation < 0,
                  }"
                >
                  {{ formatSignedMoney(row.deviation) }} EUR
                </span>
              </div>
              <div v-if="group.rows.length > 5" class="ui-budget-result-breakdown-more">
                + {{ group.rows.length - 5 }} subcategorías más
              </div>
            </div>
          </article>
        </div>
      </section>
    </div>

    <div v-if="closeStatus" class="ui-monthly-close-actions">
      <template v-if="closeStatus === 'locked'">
        <span class="ui-monthly-close-locked-banner" style="flex: 1">Este mes está bloqueado.</span>
      </template>
      <template v-else-if="closeStatus === 'finalized'">
        <button
          type="button"
          class="btn"
          :disabled="monthlyCloseActionBusy"
          @click="onReopenClose && onReopenClose()"
        >
          Reabrir cierre
        </button>
        <button
          type="button"
          class="btn"
          style="color: rgba(255, 140, 140, 0.95); border-color: rgba(255, 92, 92, 0.3)"
          :disabled="monthlyCloseActionBusy"
          @click="onLockClose && onLockClose()"
        >
          Bloquear
        </button>
      </template>
      <template v-else>
        <button
          type="button"
          class="btn"
          :disabled="monthlyCloseActionBusy"
          @click="onFinalizeClose && onFinalizeClose()"
        >
          Finalizar cierre
        </button>
        <button
          v-if="hasDistributionSuggestion"
          type="button"
          class="btn"
          :disabled="monthlyCloseActionBusy"
          @click="onApplyDistribution && onApplyDistribution()"
        >
          Aplicar distribución
        </button>
      </template>
    </div>
  </section>
</template>
