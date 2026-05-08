<script setup lang="ts">
import { computed } from 'vue';

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

const props = defineProps<{
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
  selectedPerimeterInternalExpenseTotal: number;
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

const residualReading = computed(() => {
  if (props.selectedMonthlyCloseResidual < 0) return 'Falta caja vs explicado';
  if (props.selectedMonthlyCloseResidual > 0) return 'Sobra caja vs explicado';
  return 'Sin diferencia';
});

const selectedMonthlyCloseDelta = computed(
  () => props.selectedLiquidityMonthExecuted - props.selectedMonthlyCloseExpected,
);

const resultBridgeMax = computed(() => {
  const values = [
    props.selectedLiquidityStartBase,
    props.selectedIncomeMonthExecuted,
    props.selectedExpenseMonthExecuted,
    props.selectedMonthlyCloseExpected,
    props.selectedLiquidityMonthExecuted,
    Math.abs(props.selectedMonthlyCloseResidual),
  ].map((value) => Math.abs(value));
  return Math.max(...values, 1);
});

const resultBridgeRows = computed(() =>
  props.resultReconciliationFlowRows
    .filter((row) => row.id !== 'internal-perimeter-expense')
    .map((row) => ({
      ...row,
      width: Math.max(3, Math.min(100, (Math.abs(row.amount) / resultBridgeMax.value) * 100)),
    })),
);
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
          Residual contable provisional a partir del perimetro real y de ingresos/gastos confirmados
          del mes.
        </p>
      </div>
    </div>

    <div class="ui-budget-result-hero-grid">
      <article
        class="ui-budget-result-hero-card ui-budget-result-hero-card-primary"
        :class="{
          'ui-budget-result-hero-card-danger': selectedMonthlyCloseResidual < 0,
          'ui-budget-result-hero-card-good': selectedMonthlyCloseResidual > 0,
        }"
      >
        <div class="ui-budget-result-hero-card-head">
          <span>Residual contable</span>
          <div
            class="ui-budget-result-badge"
            :class="`ui-budget-result-badge-${selectedMonthlyResidualSeverity}`"
          >
            {{ selectedMonthlyResidualSeverityLabel }}
          </div>
        </div>
        <strong>{{ formatSignedMoney(selectedMonthlyCloseResidual) }} EUR</strong>
        <small>
          {{ residualReading }} · {{ formatPercent(selectedMonthlyResidualVolumeRatio, 1) }} del
          volumen ejecutado
        </small>
      </article>
      <article class="ui-budget-result-hero-card">
        <span>Cierre esperado</span>
        <strong>{{ formatMoney(selectedMonthlyCloseExpected) }} EUR</strong>
        <small>Perimetro inicial + ingresos - gastos externos</small>
      </article>
      <article class="ui-budget-result-hero-card">
        <span>Cierre real</span>
        <strong>{{ formatMoney(selectedLiquidityMonthExecuted) }} EUR</strong>
        <small>
          {{ formatSignedMoney(selectedMonthlyCloseDelta) }} EUR frente al cierre esperado
        </small>
      </article>
      <article class="ui-budget-result-hero-card">
        <span>Completitud cierre</span>
        <strong>{{ formatPercent(selectedMonthlyCloseCompletionRatio, 0) }}</strong>
        <small>
          {{ monthlyIncomeExecutionEntries.length + monthlyExpenseExecutionEntries.length }} líneas
          revisadas
        </small>
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
        <div class="ui-budget-result-bridge">
          <div
            v-for="row in resultBridgeRows"
            :key="row.id"
            class="ui-budget-result-bridge-row"
            :class="{
              'ui-budget-result-bridge-row-result': !!row.isResult,
              'ui-budget-result-bridge-row-positive': row.tone === 'positive',
              'ui-budget-result-bridge-row-warning': row.tone === 'warning',
              'ui-budget-result-bridge-row-negative': row.tone === 'negative',
            }"
          >
            <div class="ui-budget-result-bridge-label">
              <span>{{ row.label }}</span>
              <small v-if="row.meta">{{ row.meta }}</small>
            </div>
            <div class="ui-budget-result-bridge-track" aria-hidden="true">
              <div class="ui-budget-result-bridge-fill" :style="{ width: `${row.width}%` }" />
            </div>
            <strong>{{ formatSignedMoney(row.amount) }} EUR</strong>
          </div>
        </div>
      </section>

      <section class="ui-budget-result-card">
        <div class="ui-budget-result-card-head">
          <h3 class="ui-budget-result-card-title">Diagnóstico del residual</h3>
          <div
            class="ui-budget-result-badge"
            :class="`ui-budget-result-badge-${selectedMonthlyResidualSeverity}`"
          >
            {{ selectedMonthlyResidualSeverityLabel }}
          </div>
        </div>
        <div
          class="ui-budget-result-diagnostic"
          :class="{
            'ui-budget-result-diagnostic-good': selectedMonthlyResidualSeverity === 'ok',
            'ui-budget-result-diagnostic-watch': selectedMonthlyResidualSeverity === 'watch',
            'ui-budget-result-diagnostic-alert': selectedMonthlyResidualSeverity === 'alert',
          }"
        >
          <span>{{ residualReading }}</span>
          <strong>{{ formatSignedMoney(selectedMonthlyCloseResidual) }} EUR</strong>
          <small>
            {{ formatPercent(selectedMonthlyResidualVolumeRatio, 1) }} del volumen ejecutado
          </small>
        </div>
        <div class="ui-budget-result-diagnostic-scale">
          <div class="ui-budget-result-diagnostic-scale-head">
            <span>Impacto del residual</span>
            <strong>{{ formatPercent(selectedMonthlyResidualVolumeRatio, 1) }}</strong>
          </div>
          <div class="ui-budget-result-diagnostic-track">
            <div class="ui-budget-result-diagnostic-zone ui-budget-result-diagnostic-zone-ok" />
            <div class="ui-budget-result-diagnostic-zone ui-budget-result-diagnostic-zone-watch" />
            <div class="ui-budget-result-diagnostic-zone ui-budget-result-diagnostic-zone-alert" />
            <div
              class="ui-budget-result-diagnostic-marker"
              :style="{
                left: `${
                  selectedMonthlyResidualVolumeRatio == null
                    ? 0
                    : Math.min(100, (selectedMonthlyResidualVolumeRatio / 0.03) * 100)
                }%`,
              }"
            />
          </div>
          <div class="ui-budget-result-diagnostic-scale-labels">
            <span>0 %</span>
            <span>1 %</span>
            <span>3 %+</span>
          </div>
        </div>
        <div class="ui-budget-result-residual-kpis">
          <article class="ui-budget-result-mini-kpi">
            <span>Sobre cierre esperado</span>
            <strong>{{ formatPercent(selectedMonthlyResidualExpectedCloseRatio, 1) }}</strong>
          </article>
          <article class="ui-budget-result-mini-kpi">
            <span>Volumen ejecutado</span>
            <strong>{{ formatMoney(selectedMonthlyExecutedVolume) }} EUR</strong>
          </article>
          <article class="ui-budget-result-mini-kpi">
            <span>Umbral OK</span>
            <strong>≤ 1,0 %</strong>
          </article>
          <article class="ui-budget-result-mini-kpi">
            <span>Umbral revisión</span>
            <strong>≤ 3,0 %</strong>
          </article>
        </div>
        <div v-if="selectedPerimeterInternalExpenseTotal > 0" class="ui-budget-result-footnote">
          {{ formatMoney(selectedPerimeterInternalExpenseTotal) }} EUR movidos dentro del perímetro
          no cuentan como gasto externo.
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
