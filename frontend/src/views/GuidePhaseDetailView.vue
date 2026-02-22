<script setup lang="ts">
import { computed, onMounted, watch } from 'vue';
import { RouterLink, useRoute } from 'vue-router';
import { useAnnualIncomeStore } from '@/domains/data-input/annualIncomeStore';
import { computeGuidePhaseDiagnostics } from '@/domains/guide/phaseDiagnostics';
import { findGuidePhaseById, guidePhases } from '@/domains/guide/phases';
import { gradeFromScore, scoreBadgeStyle, scoreColor } from '@/domains/guide/scoreVisuals';
import { useNetWorthStore } from '@/stores/netWorth';

type ScoreTone = 'solid' | 'medium' | 'watch' | 'risk';

type SummaryExtended = {
  liabilities_asset_backed?: string | null;
  liabilities_unbacked?: string | null;
};

type ScoreKpi = {
  id: string;
  label: string;
  valueText: string;
  score: number | null;
  hint: string;
  incomplete?: boolean;
};

type ScoreCard = {
  id: string;
  title: string;
  score: number;
  description: string;
  kpis: ScoreKpi[];
};

type SummaryCard = {
  id: string;
  label: string;
  valueText: string;
};

const route = useRoute();
const store = useNetWorthStore();
const annualIncomeStore = useAnnualIncomeStore('saas');

const phaseId = computed(() => {
  const raw = String(route.params.phaseId ?? '');
  const parsed = Number.parseInt(raw, 10);
  return Number.isFinite(parsed) ? parsed : null;
});

const phase = computed(() => (phaseId.value == null ? null : findGuidePhaseById(phaseId.value)));
const isDebtPhase = computed(() => phase.value?.id === 1);
const isNetWorthHealthPhase = computed(() => phase.value?.id === 4);
const hasDiagnosticPhase = computed(() => isDebtPhase.value || isNetWorthHealthPhase.value);
const summaryExtended = computed(() => store.summary as SummaryExtended | null);
const sharedPhaseDiagnostics = computed(() =>
  computeGuidePhaseDiagnostics({
    summary: store.summary as (typeof store.summary & { liabilities_unbacked?: string | null }),
    assets: store.assets,
    liabilities: store.liabilities,
    annualIncomeEntries: annualIncomeStore.entries.value,
  }),
);

function toNumber(raw: unknown): number {
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
  const value = Number(normalized);
  return Number.isFinite(value) ? value : 0;
}

function hasTextValue(raw: unknown): boolean {
  return String(raw ?? '').trim() !== '';
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
}

function formatNumber(n: number, decimals = 2): string {
  return new Intl.NumberFormat('es-ES', {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function formatPct(n: number | null, decimals = 0): string {
  if (n == null || !Number.isFinite(n)) return '-';
  return new Intl.NumberFormat('es-ES', {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function formatPctFromPercentValue(n: number | null, decimals = 1): string {
  if (n == null || !Number.isFinite(n)) return '-';
  return formatPct(n / 100, decimals);
}

function linearScoreIncreasing(value: number | null, min: number, max: number): number {
  if (value == null || !Number.isFinite(value) || max <= min) return 0;
  const normalized = (value - min) / (max - min);
  return clamp(normalized * 100, 0, 100);
}

function linearScoreDecreasing(value: number | null, min: number, max: number): number {
  if (value == null || !Number.isFinite(value) || max <= min) return 0;
  const normalized = (max - value) / (max - min);
  return clamp(normalized * 100, 0, 100);
}

function weightedScore(items: { score: number; weight: number }[]): number {
  const totalWeight = items.reduce((acc, item) => acc + item.weight, 0);
  if (totalWeight <= 0) return 0;
  const sum = items.reduce((acc, item) => acc + item.score * item.weight, 0);
  return clamp(sum / totalWeight, 0, 100);
}

function scoreFillStyle(score: number): Record<string, string> {
  const normalized = clamp(score, 0, 100);
  return {
    width: `${normalized}%`,
    backgroundColor: scoreColor(score),
  };
}

function gradeStyle(score: number): Record<string, string> {
  return { color: scoreColor(score) };
}

const chartRows = computed(() => {
  const chart = store.byCategoryChart;
  return chart.keys.map((key, index) => ({
    key,
    assets: Math.max(0, chart.assets[index] ?? 0),
    liabilities: Math.max(0, chart.liabilities[index] ?? 0),
  }));
});

const assetRows = computed(() => chartRows.value.filter((row) => row.assets > 0));
const activeAssets = computed(() => store.assets.filter((asset) => asset.is_active));
const activeLiabilities = computed(() =>
  store.liabilities.filter((liability) => liability.is_active),
);

const assetsValue = computed(() => Math.max(0, toNumber(store.summary?.total_assets)));
const liabilitiesValue = computed(() => Math.max(0, toNumber(store.summary?.total_liabilities)));
const netWorthValue = computed(() => toNumber(store.summary?.net_worth));
const unbackedDebtValue = computed(() =>
  Math.max(0, toNumber(summaryExtended.value?.liabilities_unbacked)),
);

function isPositiveTae(raw: string | null | undefined): boolean {
  if (raw == null) return false;
  return toNumber(raw) > 0;
}

const illiquidInvestmentSubcategories = new Set([
  'pension_plans',
  'real_estate_crowd',
  'crowdlending',
  'other',
]);

const illiquidAssetsValue = computed(() => {
  return activeAssets.value.reduce((acc, asset) => {
    const amountBase = Math.max(0, toNumber(asset.amount_base));
    if (amountBase <= 0) return acc;

    const illiquidByCategory =
      asset.category === 'real_estate' ||
      asset.category === 'furnishings' ||
      asset.category === 'other';

    const illiquidByInvestmentSubcategory =
      asset.category === 'investments' &&
      illiquidInvestmentSubcategories.has(asset.subcategory || 'other');

    const illiquidByCashOtherDeposit =
      asset.category === 'cash' &&
      asset.subcategory === 'other' &&
      isPositiveTae(asset.annual_interest_tae);

    return illiquidByCategory || illiquidByInvestmentSubcategory || illiquidByCashOtherDeposit
      ? acc + amountBase
      : acc;
  }, 0);
});

const illiquidAssetsShareValue = computed(() =>
  assetsValue.value > 0 ? illiquidAssetsValue.value / assetsValue.value : null,
);

const debtRows = computed(() =>
  activeLiabilities.value
    .map((liability) => {
      const amountBase = Math.max(0, toNumber(liability.amount_base));
      const tae = liability.annual_interest_tae;
      const taePct = tae == null || String(tae).trim() === '' ? null : toNumber(tae);
      const hasKnownTae = taePct != null && Number.isFinite(taePct) && taePct >= 0;
      const hasMonthlyPaymentInput = hasTextValue(liability.monthly_payment_amount);
      const monthlyPaymentAmount = hasMonthlyPaymentInput
        ? Math.max(0, toNumber(liability.monthly_payment_amount))
        : 0;
      return {
        amountBase,
        taePct: hasKnownTae ? taePct : null,
        hasMonthlyPaymentInput,
        monthlyPaymentAmount,
      };
    })
    .filter((row) => row.amountBase > 0),
);

const unbackedDebtToAssetsValue = computed(() =>
  assetsValue.value > 0 ? unbackedDebtValue.value / assetsValue.value : null,
);

const unbackedDebtToLiabilitiesValue = computed(() =>
  liabilitiesValue.value > 0 ? unbackedDebtValue.value / liabilitiesValue.value : null,
);

const topAssetShareValue = computed(() => {
  if (assetsValue.value <= 0) return null;
  const topAssets = assetRows.value.map((row) => row.assets).sort((a, b) => b - a)[0] ?? 0;
  return topAssets / assetsValue.value;
});

const diversificationIndexValue = computed(() => {
  if (assetsValue.value <= 0) return null;
  const shares = assetRows.value.map((row) => row.assets / assetsValue.value);
  if (!shares.length) return null;
  const hhi = shares.reduce((acc, share) => acc + share * share, 0);
  const minHhi = 1 / 5;
  const maxHhi = 1;
  return clamp((maxHhi - hhi) / (maxHhi - minHhi), 0, 1);
});

const topLiabilityShareValue = computed(() => {
  if (liabilitiesValue.value <= 0) return null;
  const topLiability = debtRows.value.map((row) => row.amountBase).sort((a, b) => b - a)[0] ?? 0;
  return topLiability / liabilitiesValue.value;
});

const maxLiabilityTaePctValue = computed(() => {
  const taes = debtRows.value
    .map((row) => row.taePct)
    .filter((value): value is number => value != null && Number.isFinite(value));
  if (!taes.length) return null;
  return Math.max(...taes);
});

const weightedLiabilityTaePctValue = computed(() => {
  const rows = debtRows.value.filter((row) => row.taePct != null);
  const denominator = rows.reduce((acc, row) => acc + row.amountBase, 0);
  if (denominator <= 0) return null;
  const numerator = rows.reduce((acc, row) => acc + row.amountBase * (row.taePct ?? 0), 0);
  return numerator / denominator;
});

const liabilityTaeDispersionPctValue = computed(() => {
  if (maxLiabilityTaePctValue.value == null || weightedLiabilityTaePctValue.value == null)
    return null;
  return Math.max(0, maxLiabilityTaePctValue.value - weightedLiabilityTaePctValue.value);
});

const liabilitiesWithAmountCountValue = computed(
  () => debtRows.value.filter((row) => row.amountBase > 0).length,
);

const liabilitiesWithPaymentInputCountValue = computed(
  () => debtRows.value.filter((row) => row.hasMonthlyPaymentInput).length,
);

const hasMissingDebtPaymentInputsValue = computed(
  () =>
    liabilitiesWithAmountCountValue.value > 0 &&
    liabilitiesWithPaymentInputCountValue.value < liabilitiesWithAmountCountValue.value,
);

const hasNoDebtPaymentInputsValue = computed(
  () =>
    liabilitiesWithAmountCountValue.value > 0 && liabilitiesWithPaymentInputCountValue.value === 0,
);

const totalMonthlyDebtPaymentValue = computed(() =>
  debtRows.value.reduce((acc, row) => acc + row.monthlyPaymentAmount, 0),
);

const recurrentAnnualIncomeValue = computed(() =>
  annualIncomeStore.entries.value.reduce(
    (acc, entry) => (entry.incomeType === 'recurrent' ? acc + Number(entry.amountAnnual ?? 0) : acc),
    0,
  ),
);

const monthlyIncomeValue = computed(() => {
  const annual = Number(recurrentAnnualIncomeValue.value ?? 0);
  if (!Number.isFinite(annual) || annual <= 0) return null;
  return annual / 12;
});

const debtPaymentToIncomeValue = computed(() => {
  if (liabilitiesValue.value <= 0) return 0;
  if (monthlyIncomeValue.value == null || monthlyIncomeValue.value <= 0) return null;
  if (hasNoDebtPaymentInputsValue.value) return null;
  return totalMonthlyDebtPaymentValue.value / monthlyIncomeValue.value;
});

const highInterestDebtThresholdPct = 8;
const highInterestDebtValue = computed(() =>
  debtRows.value.reduce(
    (acc, row) =>
      row.taePct != null && row.taePct >= highInterestDebtThresholdPct ? acc + row.amountBase : acc,
    0,
  ),
);

const highInterestDebtShareValue = computed(() =>
  liabilitiesValue.value > 0 ? highInterestDebtValue.value / liabilitiesValue.value : null,
);

const illiquidScoreValue = computed(() =>
  linearScoreDecreasing(illiquidAssetsShareValue.value, 0.25, 1),
);
const unbackedDebtScoreValue = computed(() =>
  linearScoreDecreasing(unbackedDebtToAssetsValue.value, 0.05, 0.35),
);

const concentrationScoreValue = computed(() =>
  linearScoreDecreasing(topAssetShareValue.value, 0.4, 0.9),
);
const diversificationScoreValue = computed(() =>
  linearScoreIncreasing(diversificationIndexValue.value, 0.2, 0.8),
);

const phase4SupportScoreValue = computed(() =>
  weightedScore([
    { score: unbackedDebtScoreValue.value, weight: 0.5 },
    { score: illiquidScoreValue.value, weight: 0.5 },
  ]),
);

const phase4RiskDistributionScoreValue = computed(() =>
  weightedScore([
    { score: concentrationScoreValue.value, weight: 0.5 },
    { score: diversificationScoreValue.value, weight: 0.5 },
  ]),
);

const phase4GlobalScoreValue = computed(() =>
  sharedPhaseDiagnostics.value.phase4GlobalScore,
);

const debtMaxTaeScoreValue = computed(() =>
  linearScoreDecreasing(maxLiabilityTaePctValue.value, 0.5, 10),
);
const debtWeightedTaeScoreValue = computed(() =>
  linearScoreDecreasing(weightedLiabilityTaePctValue.value, 0.5, 10),
);
const debtPaymentToIncomeScoreValue = computed(() =>
  hasNoDebtPaymentInputsValue.value
    ? 100
    : linearScoreDecreasing(debtPaymentToIncomeValue.value, 0.15, 0.6),
);
const debtUnbackedScoreValue = computed(() =>
  linearScoreDecreasing(unbackedDebtToLiabilitiesValue.value, 0.01, 0.5),
);
const debtConcentrationScoreValue = computed(() =>
  linearScoreDecreasing(topLiabilityShareValue.value, 0.25, 0.95),
);
const debtHighInterestShareScoreValue = computed(() =>
  linearScoreDecreasing(highInterestDebtShareValue.value, 0.05, 0.6),
);

const phase1DebtCostScoreValue = computed(() =>
  weightedScore([
    { score: debtMaxTaeScoreValue.value, weight: 0.4 },
    { score: debtWeightedTaeScoreValue.value, weight: 0.4 },
    { score: debtPaymentToIncomeScoreValue.value, weight: 0.2 },
  ]),
);

const phase1DebtRiskScoreValue = computed(() =>
  weightedScore([
    { score: debtUnbackedScoreValue.value, weight: 0.4 },
    { score: debtConcentrationScoreValue.value, weight: 0.3 },
    { score: debtHighInterestShareScoreValue.value, weight: 0.3 },
  ]),
);

const phase1GlobalScoreValue = computed(() =>
  sharedPhaseDiagnostics.value.phase1GlobalScore,
);

function toneFromScore(score: number): ScoreTone {
  if (score >= 75) return 'solid';
  if (score >= 55) return 'medium';
  if (score >= 35) return 'watch';
  return 'risk';
}

const globalScoreValue = computed(() => {
  if (isDebtPhase.value) return phase1GlobalScoreValue.value;
  if (isNetWorthHealthPhase.value) return phase4GlobalScoreValue.value;
  return 0;
});

const globalToneValue = computed(() => toneFromScore(globalScoreValue.value));
const globalBadgeStyleValue = computed(() => scoreBadgeStyle(globalScoreValue.value));

const globalLabelValue = computed(() => {
  const tone = globalToneValue.value;
  if (isDebtPhase.value) {
    if (tone === 'solid') return 'Deuda saneada';
    if (tone === 'medium') return 'Deuda controlada';
    if (tone === 'watch') return 'Deuda en vigilancia';
    return 'Deuda critica';
  }
  if (tone === 'solid') return 'Salud patrimonial solida';
  if (tone === 'medium') return 'Salud patrimonial equilibrada';
  if (tone === 'watch') return 'Salud patrimonial mejorable';
  return 'Salud patrimonial vulnerable';
});

const phase4ScoreCards = computed<ScoreCard[]>(() => [
  {
    id: 'support',
    title: 'Respaldo patrimonial',
    score: phase4SupportScoreValue.value,
    description: 'Calidad de respaldo del patrimonio frente a iliquidez y deuda no respaldada.',
    kpis: [
      {
        id: 'unbacked-debt-assets',
        label: '% deuda sin respaldo / activos',
        valueText: formatPct(unbackedDebtToAssetsValue.value, 0),
        score: unbackedDebtScoreValue.value,
        hint: 'Pasivos sin activo asociado (inverso)',
      },
      {
        id: 'illiquid-assets',
        label: '% activos iliquidos',
        valueText: formatPct(illiquidAssetsShareValue.value, 0),
        score: illiquidScoreValue.value,
        hint: 'Inmuebles + mobiliario + otros + inversiones iliquidas + liquidez/otros con TAE (inverso)',
      },
    ],
  },
  {
    id: 'distribution',
    title: 'Distribucion del riesgo',
    score: phase4RiskDistributionScoreValue.value,
    description: 'Dependencia de un unico bloque frente a reparto patrimonial equilibrado.',
    kpis: [
      {
        id: 'top-share',
        label: 'Concentracion top activo',
        valueText: formatPct(topAssetShareValue.value, 0),
        score: concentrationScoreValue.value,
        hint: 'Peso del activo dominante (inverso)',
      },
      {
        id: 'diversification',
        label: 'Indice de diversificacion',
        valueText: formatPct(diversificationIndexValue.value, 0),
        score: diversificationScoreValue.value,
        hint: 'HHI normalizado',
      },
    ],
  },
]);

const phase1ScoreCards = computed<ScoreCard[]>(() => [
  {
    id: 'debt-cost',
    title: 'Coste y visibilidad de deuda',
    score: phase1DebtCostScoreValue.value,
    description:
      'Coste financiero de los pasivos y calidad del dato de TAE para priorizar amortizacion.',
    kpis: [
      {
        id: 'max-liability-tae',
        label: 'TAE maxima de pasivos',
        valueText: formatPctFromPercentValue(maxLiabilityTaePctValue.value, 1),
        score: debtMaxTaeScoreValue.value,
        hint: 'Peor pasivo por coste (inverso)',
      },
      {
        id: 'weighted-liability-tae',
        label: 'TAE media ponderada',
        valueText: formatPctFromPercentValue(weightedLiabilityTaePctValue.value, 1),
        score: debtWeightedTaeScoreValue.value,
        hint: 'Coste medio ponderado por importe (inverso)',
      },
      {
        id: 'debt-payment-income',
        label: '% cuota / ingresos',
        valueText: formatPct(debtPaymentToIncomeValue.value, 0),
        score: debtPaymentToIncomeScoreValue.value,
        hint: 'Suma de cuotas mensuales manuales / ingreso mensual recurrente (inverso)',
        incomplete: hasMissingDebtPaymentInputsValue.value,
      },
    ],
  },
  {
    id: 'debt-structure',
    title: 'Riesgo estructural de deuda',
    score: phase1DebtRiskScoreValue.value,
    description:
      'Respaldo, concentracion y exposicion a deuda cara para ordenar el plan de reduccion.',
    kpis: [
      {
        id: 'unbacked-debt-liabilities',
        label: '% deuda sin respaldo / pasivos',
        valueText: formatPct(unbackedDebtToLiabilitiesValue.value, 0),
        score: debtUnbackedScoreValue.value,
        hint: 'Pasivo sin activo asociado (inverso)',
      },
      {
        id: 'top-liability-share',
        label: 'Concentracion top pasivo',
        valueText: formatPct(topLiabilityShareValue.value, 0),
        score: debtConcentrationScoreValue.value,
        hint: 'Peso del mayor pasivo sobre el total (inverso)',
      },
      {
        id: 'high-interest-debt-share',
        label: `% deuda con TAE >= ${highInterestDebtThresholdPct}%`,
        valueText: formatPct(highInterestDebtShareValue.value, 0),
        score: debtHighInterestShareScoreValue.value,
        hint: 'Exposicion a deuda cara (inverso)',
      },
    ],
  },
]);

const scoreCards = computed<ScoreCard[]>(() => {
  if (isDebtPhase.value) return phase1ScoreCards.value;
  if (isNetWorthHealthPhase.value) return phase4ScoreCards.value;
  return [];
});

const summaryCards = computed<SummaryCard[]>(() => {
  if (isDebtPhase.value) {
    return [
      {
        id: 'liabilities-total',
        label: 'Pasivos totales',
        valueText: formatNumber(liabilitiesValue.value, 2),
      },
      {
        id: 'unbacked-debt',
        label: 'Deuda sin respaldo',
        valueText: formatNumber(unbackedDebtValue.value, 2),
      },
      {
        id: 'high-interest-debt',
        label: `Deuda TAE >= ${highInterestDebtThresholdPct}%`,
        valueText: formatNumber(highInterestDebtValue.value, 2),
      },
      {
        id: 'tae-dispersion',
        label: 'Dispersion de TAE',
        valueText: formatPctFromPercentValue(liabilityTaeDispersionPctValue.value, 1),
      },
    ];
  }

  if (isNetWorthHealthPhase.value) {
    return [
      {
        id: 'net-worth',
        label: 'Patrimonio neto',
        valueText: formatNumber(netWorthValue.value, 2),
      },
      {
        id: 'assets-total',
        label: 'Activos totales',
        valueText: formatNumber(assetsValue.value, 2),
      },
      {
        id: 'liabilities-total',
        label: 'Pasivos totales',
        valueText: formatNumber(liabilitiesValue.value, 2),
      },
      {
        id: 'unbacked-debt',
        label: 'Deuda sin respaldo',
        valueText: formatNumber(unbackedDebtValue.value, 2),
      },
    ];
  }

  return [];
});

const phaseDiagnosticCopy = computed(() => {
  if (isDebtPhase.value) {
    return 'Diagnostico de deuda: coste, respaldo y concentracion para priorizar amortizacion.';
  }
  if (isNetWorthHealthPhase.value) {
    return 'Diagnostico de salud patrimonial: respaldo patrimonial y distribucion del riesgo.';
  }
  return phase.value?.objective ?? '';
});

function maybeLoadNetWorthContext() {
  if (!hasDiagnosticPhase.value) return;
  void store.fetchSettings();
  void store.refreshAll();
  if (isDebtPhase.value) {
    void annualIncomeStore.loadAll();
  }
}

function phaseDetailTo(phaseIdParam: number): string {
  return `/guia/fases/${phaseIdParam}`;
}

onMounted(() => {
  maybeLoadNetWorthContext();
});

watch(hasDiagnosticPhase, () => {
  maybeLoadNetWorthContext();
});
</script>

<template>
  <div class="container ui-pro-page">
    <section class="card ui-pro-panel ui-guide-phase-head">
      <div class="ui-guide-phase-nav-row">
        <RouterLink class="ui-guide-back-link" to="/inicio">Ver ruta completa</RouterLink>
        <div class="ui-guide-phase-switch">
          <RouterLink
            v-for="phaseItem in guidePhases"
            :key="phaseItem.id"
            class="ui-guide-phase-switch-link"
            :class="{ 'ui-guide-phase-switch-link-active': phaseItem.id === phase?.id }"
            :to="phaseDetailTo(phaseItem.id)"
          >
            F{{ phaseItem.id }}
          </RouterLink>
        </div>
      </div>

      <template v-if="phase">
        <h1 class="h1 ui-guide-phase-title ui-guide-phase-title-inline">
          <span class="ui-pro-kicker ui-guide-phase-title-inline-kicker">Fase {{ phase.id }}</span>
          <span class="ui-pro-kicker ui-guide-phase-title-inline-name">{{ phase.title }}</span>
        </h1>
        <p class="subtle ui-guide-phase-copy">
          {{ phaseDiagnosticCopy }}
        </p>
      </template>

      <template v-else>
        <h1 class="h1 ui-guide-phase-title">Fase no encontrada</h1>
      </template>
    </section>

    <section v-if="!phase" class="card ui-pro-panel">
      <p class="subtle">La fase seleccionada no existe en la guia actual.</p>
    </section>

    <section v-else-if="!hasDiagnosticPhase" class="card ui-pro-panel">
      <h2 class="h2">Detalle en construccion</h2>
      <p class="subtle">
        Esta fase ya tiene su contexto funcional, pero el diagnostico detallado se publicara en
        siguientes entregas del roadmap.
      </p>
      <ul class="list">
        <li>Objetivo: {{ phase.objective }}</li>
        <li>Foco operativo: {{ phase.focus }}</li>
        <li>Prerrequisito: completar antes la fase activa en Guia.</li>
      </ul>
    </section>

    <section v-else class="card ui-pro-panel ui-guide-score-panel">
      <div class="ui-guide-summary-grid">
        <article
          v-for="summaryCard in summaryCards"
          :key="summaryCard.id"
          class="ui-guide-summary-card"
        >
          <div class="ui-guide-summary-label">{{ summaryCard.label }}</div>
          <div class="ui-guide-summary-value">{{ summaryCard.valueText }}</div>
        </article>
      </div>

      <div class="ui-guide-score-top">
        <div
          class="ui-guide-health-score-badge"
          :class="`ui-guide-health-${globalToneValue}`"
          :style="globalBadgeStyleValue"
        >
          <span class="ui-guide-health-score-text">{{ globalLabelValue }}</span>
          <strong class="ui-guide-health-score-value"
            >{{ formatNumber(globalScoreValue, 0) }}%</strong
          >
        </div>
      </div>

      <div class="ui-guide-meter-row">
        <span class="ui-guide-grade ui-guide-grade-global" :style="gradeStyle(globalScoreValue)">{{
          gradeFromScore(globalScoreValue)
        }}</span>
        <div class="ui-guide-global-meter">
          <span class="ui-guide-global-meter-fill" :style="scoreFillStyle(globalScoreValue)"></span>
        </div>
      </div>

      <div class="ui-guide-score-grid" :class="`ui-guide-score-grid-cols-${scoreCards.length}`">
        <article v-for="card in scoreCards" :key="card.id" class="ui-guide-score-card">
          <div class="ui-guide-score-card-head">
            <h3 class="ui-guide-score-card-title">{{ card.title }}</h3>
            <div class="ui-guide-score-card-value-wrap">
              <span class="ui-guide-score-card-grade" :style="gradeStyle(card.score)">{{
                gradeFromScore(card.score)
              }}</span>
              <div class="ui-guide-score-card-value">{{ formatNumber(card.score, 0) }}%</div>
            </div>
          </div>
          <p class="ui-guide-score-card-copy">{{ card.description }}</p>

          <div class="ui-guide-score-kpi-list">
            <div v-for="kpi in card.kpis" :key="kpi.id" class="ui-guide-score-kpi">
              <div class="ui-guide-score-kpi-head">
                <span>{{ kpi.label }}</span>
                <strong class="ui-guide-score-kpi-value">
                  {{ kpi.valueText }}
                  <span
                    v-if="kpi.incomplete"
                    class="ui-guide-score-kpi-alert"
                    title="Faltan cuotas por completar"
                    aria-label="Faltan cuotas por completar"
                    >!</span
                  >
                </strong>
              </div>
              <div v-if="kpi.score != null" class="ui-guide-meter-row ui-guide-meter-row-kpi">
                <span class="ui-guide-grade" :style="gradeStyle(kpi.score)">{{
                  gradeFromScore(kpi.score)
                }}</span>
                <div class="ui-guide-score-kpi-track">
                  <span class="ui-guide-score-kpi-fill" :style="scoreFillStyle(kpi.score)"></span>
                </div>
              </div>
              <div v-else class="ui-guide-score-kpi-pending">Indicador informativo (pendiente)</div>
              <div class="ui-guide-score-kpi-hint">{{ kpi.hint }}</div>
            </div>
          </div>
        </article>
      </div>

      <div v-if="store.loading" class="ui-status-line">Cargando diagnostico...</div>
      <div v-else-if="store.error" class="alert">{{ store.error }}</div>
    </section>
  </div>
</template>

<style scoped>
.ui-guide-phase-head {
  display: grid;
  gap: 10px;
}

.ui-guide-phase-nav-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
}

.ui-guide-back-link {
  color: rgba(45, 212, 191, 0.95);
  text-decoration: none;
  font-size: 13px;
  font-weight: 600;
}

.ui-guide-back-link:hover {
  text-decoration: underline;
}

.ui-guide-phase-switch {
  display: inline-flex;
  gap: 6px;
  flex-wrap: wrap;
}

.ui-guide-phase-switch-link {
  border: 1px solid rgba(255, 255, 255, 0.14);
  border-radius: 999px;
  padding: 4px 10px;
  font-size: 12px;
  text-decoration: none;
  color: var(--text);
  background: rgba(255, 255, 255, 0.02);
}

.ui-guide-phase-switch-link-active {
  border-color: rgba(45, 212, 191, 0.72);
  background: rgba(45, 212, 191, 0.12);
}

.ui-guide-phase-title {
  margin-bottom: 2px;
}

.ui-guide-phase-title-inline {
  display: flex;
  flex-wrap: wrap;
  align-items: baseline;
  gap: 10px;
  margin: 0 0 2px;
}

.ui-guide-phase-title-inline-kicker {
  margin: 0;
  font-size: 13px;
}

.ui-guide-phase-title-inline-name {
  margin: 0;
  font-size: 13px;
}

.ui-guide-phase-copy {
  margin: 0;
}

.ui-guide-phase-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.ui-guide-score-panel {
  padding: 16px;
}

.ui-guide-score-top {
  margin-top: 12px;
  display: grid;
  grid-template-columns: auto minmax(0, 1fr);
  gap: 14px;
  align-items: center;
}

.ui-guide-health-score-badge {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  border-radius: 999px;
  padding: 8px 14px;
  font-size: 12px;
  font-weight: 600;
  border: 1px solid rgba(255, 255, 255, 0.18);
  line-height: 1;
}

.ui-guide-health-score-text {
  white-space: nowrap;
}

.ui-guide-health-score-value {
  font-size: 24px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: rgba(255, 255, 255, 0.96);
}

.ui-guide-health-solid {
  background: rgba(74, 222, 128, 0.16);
  color: rgba(134, 239, 172, 0.95);
}

.ui-guide-health-medium {
  background: rgba(163, 230, 53, 0.18);
  color: rgba(190, 242, 100, 0.95);
}

.ui-guide-health-watch {
  background: rgba(250, 204, 21, 0.16);
  color: rgba(253, 224, 71, 0.95);
}

.ui-guide-health-risk {
  background: rgba(251, 113, 133, 0.16);
  color: rgba(251, 113, 133, 0.95);
}

.ui-guide-health-copy {
  font-size: 14px;
  color: var(--muted);
}

.ui-guide-global-meter {
  flex: 1 1 auto;
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  overflow: hidden;
}

.ui-guide-global-meter-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
}

.ui-guide-meter-row {
  margin-top: 12px;
  display: flex;
  align-items: center;
  gap: 8px;
}

.ui-guide-meter-row-kpi {
  margin-top: 4px;
}

.ui-guide-grade {
  min-width: 16px;
  font-size: 14px;
  font-weight: 700;
  line-height: 1;
  text-align: center;
}

.ui-guide-grade-global {
  font-size: 28px;
  font-weight: 800;
}

.ui-guide-score-grid {
  margin-top: 12px;
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(auto-fit, minmax(360px, 1fr));
}

.ui-guide-score-grid-cols-1 {
  grid-template-columns: minmax(0, 1fr);
}

.ui-guide-score-grid-cols-2 {
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.ui-guide-score-card {
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.02);
  padding: 12px;
  height: 100%;
}

.ui-guide-score-card-head {
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 8px;
}

.ui-guide-score-card-title {
  margin: 0;
  font-size: 15px;
  font-weight: 600;
}

.ui-guide-score-card-value {
  font-size: 14px;
  font-weight: 700;
}

.ui-guide-score-card-value-wrap {
  display: inline-flex;
  align-items: baseline;
  gap: 8px;
}

.ui-guide-score-card-grade {
  font-size: 22px;
  font-weight: 800;
  line-height: 1;
}

.ui-guide-score-card-copy {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--muted);
}

.ui-guide-score-kpi-list {
  margin-top: 10px;
  display: grid;
  gap: 10px;
}

.ui-guide-score-kpi-head {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  font-size: 13px;
}

.ui-guide-score-kpi-value {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ui-guide-score-kpi-alert {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  border-radius: 999px;
  font-size: 11px;
  font-weight: 800;
  line-height: 1;
  color: hsl(34 100% 72%);
  border: 1px solid hsl(34 100% 68% / 0.45);
  background: hsl(34 100% 50% / 0.14);
}

.ui-guide-score-kpi-track {
  flex: 1 1 auto;
  height: 7px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.ui-guide-score-kpi-fill {
  display: block;
  height: 100%;
  border-radius: 999px;
  width: 0%;
  background: hsl(0 82% 52%);
}

.ui-guide-score-kpi-hint {
  margin-top: 4px;
  font-size: 12px;
  color: var(--muted);
}

.ui-guide-score-kpi-pending {
  margin-top: 4px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.72);
}

.ui-guide-summary-grid {
  margin-top: 0;
  display: grid;
  gap: 10px;
  grid-template-columns: repeat(4, minmax(0, 1fr));
}

.ui-guide-summary-card {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  background: rgba(255, 255, 255, 0.02);
  padding: 10px 11px;
}

.ui-guide-summary-label {
  font-size: 12px;
  color: var(--muted);
}

.ui-guide-summary-value {
  margin-top: 3px;
  font-size: 20px;
  font-weight: 700;
}

.ui-guide-summary-meta {
  margin-top: 4px;
  font-size: 11px;
  color: var(--muted);
}

@media (max-width: 1024px) {
  .ui-guide-score-grid {
    grid-template-columns: 1fr;
  }

  .ui-guide-summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 720px) {
  .ui-guide-score-top {
    grid-template-columns: 1fr;
  }

  .ui-guide-summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
