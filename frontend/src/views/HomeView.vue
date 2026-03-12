<script setup lang="ts">
import { computed, onMounted } from 'vue';
import { RouterLink } from 'vue-router';
import { useAnnualExpenseStore, useAnnualIncomeStore } from '@/domains/data-input';
import ScoreGradeBadge from '@/domains/guide/components/ScoreGradeBadge.vue';
import { computeGuidePhaseDiagnostics } from '@/domains/guide/phaseDiagnostics';
import { getActiveGuidePhase, guidePhases, type GuidePhase } from '@/domains/guide/phases';
import { gradeFromScore, scoreColor } from '@/domains/guide/scoreVisuals';
import { useNetWorthStore } from '@/domains/net-worth';

const phases = guidePhases;
const store = useNetWorthStore();
const annualIncomeStore = useAnnualIncomeStore('core');
const annualExpenseStore = useAnnualExpenseStore('core');
const sharedPhaseDiagnostics = computed(() =>
  computeGuidePhaseDiagnostics({
    summary: store.summary as typeof store.summary & { liabilities_unbacked?: string | null },
    assets: store.assets,
    liabilities: store.liabilities,
    annualIncomeEntries: annualIncomeStore.entries.value,
    annualExpenseEntries: annualExpenseStore.entries.value,
  }),
);
const activePhase = computed(() => getActiveGuidePhase());

function phaseState(phase: GuidePhase): 'done' | 'active' | 'next' {
  if (phase.progress >= 100) return 'done';
  if (phase.id === activePhase.value.id) return 'active';
  return 'next';
}

function phaseDetailTo(phaseId: number): string {
  return `/guia/fases/${phaseId}`;
}

type PhaseSnapshot = {
  phase: GuidePhase;
  score: number;
  grade: string;
};

type SummaryExtended = {
  liabilities_unbacked?: string | null;
};

function toNumber(raw: unknown): number {
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
  const value = Number(normalized);
  return Number.isFinite(value) ? value : 0;
}

function clamp(value: number, min: number, max: number): number {
  return Math.max(min, Math.min(max, value));
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

const summaryExtended = computed(() => store.summary as SummaryExtended | null);
const assetsValue = computed(() => Math.max(0, toNumber(store.summary?.total_assets)));
const unbackedDebtValue = computed(() =>
  Math.max(0, toNumber(summaryExtended.value?.liabilities_unbacked)),
);

const chartRows = computed(() => {
  const chart = store.byCategoryChart;
  return chart.keys.map((key, index) => ({
    key,
    assets: Math.max(0, chart.assets[index] ?? 0),
  }));
});

const assetRows = computed(() => chartRows.value.filter((row) => row.assets > 0));
const activeAssets = computed(() => store.assets.filter((asset) => asset.is_active));
const activeLiabilities = computed(() =>
  store.liabilities.filter((liability) => liability.is_active),
);
const liabilitiesValue = computed(() => Math.max(0, toNumber(store.summary?.total_liabilities)));

const illiquidInvestmentSubcategories = new Set([
  'pension_plans',
  'real_estate_crowd',
  'crowdlending',
  'other',
]);

function isPositiveTae(raw: string | null | undefined): boolean {
  if (raw == null) return false;
  return toNumber(raw) > 0;
}

function hasTextValue(raw: unknown): boolean {
  return String(raw ?? '').trim() !== '';
}

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

const unbackedDebtToAssetsValue = computed(() =>
  assetsValue.value > 0 ? unbackedDebtValue.value / assetsValue.value : null,
);

const debtRows = computed(() =>
  activeLiabilities.value
    .map((liability) => {
      const amountBase = Math.max(0, toNumber(liability.amount_base));
      const tae = liability.annual_interest_tae;
      const taePct = tae == null || String(tae).trim() === '' ? null : toNumber(tae);
      const hasKnownTae = taePct != null && Number.isFinite(taePct) && taePct >= 0;
      const paymentRaw = liability.estimated_monthly_payment_amount;
      const hasMonthlyPaymentInput = hasTextValue(paymentRaw);
      const monthlyPaymentAmount = hasMonthlyPaymentInput ? Math.max(0, toNumber(paymentRaw)) : 0;
      return {
        amountBase,
        taePct: hasKnownTae ? taePct : null,
        hasMonthlyPaymentInput,
        monthlyPaymentAmount,
      };
    })
    .filter((row) => row.amountBase > 0),
);

const unbackedDebtToLiabilitiesValue = computed(() =>
  liabilitiesValue.value > 0 ? unbackedDebtValue.value / liabilitiesValue.value : null,
);

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

const liabilitiesWithAmountCountValue = computed(
  () => debtRows.value.filter((row) => row.amountBase > 0).length,
);
const liabilitiesWithPaymentInputCountValue = computed(
  () => debtRows.value.filter((row) => row.hasMonthlyPaymentInput).length,
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
    (acc, entry) =>
      entry.incomeType === 'recurrent' ? acc + Number(entry.amountAnnual ?? 0) : acc,
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

const supportScoreValue = computed(() =>
  weightedScore([
    { score: linearScoreDecreasing(unbackedDebtToAssetsValue.value, 0.05, 0.35), weight: 0.5 },
    { score: linearScoreDecreasing(illiquidAssetsShareValue.value, 0.25, 0.8), weight: 0.5 },
  ]),
);

const riskDistributionScoreValue = computed(() =>
  weightedScore([
    { score: linearScoreDecreasing(topAssetShareValue.value, 0.4, 0.9), weight: 0.5 },
    { score: linearScoreIncreasing(diversificationIndexValue.value, 0.2, 0.8), weight: 0.5 },
  ]),
);

const phase4HealthScoreValue = computed(() =>
  weightedScore([
    { score: supportScoreValue.value, weight: 0.5 },
    { score: riskDistributionScoreValue.value, weight: 0.5 },
  ]),
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

const phase1HealthScoreValue = computed(() =>
  weightedScore([
    {
      score: weightedScore([
        { score: debtMaxTaeScoreValue.value, weight: 0.4 },
        { score: debtWeightedTaeScoreValue.value, weight: 0.4 },
        { score: debtPaymentToIncomeScoreValue.value, weight: 0.2 },
      ]),
      weight: 0.5,
    },
    {
      score: weightedScore([
        { score: debtUnbackedScoreValue.value, weight: 0.4 },
        { score: debtConcentrationScoreValue.value, weight: 0.3 },
        { score: debtHighInterestShareScoreValue.value, weight: 0.3 },
      ]),
      weight: 0.5,
    },
  ]),
);

function phaseDisplayProgress(phase: GuidePhase): number {
  if (!store.summary) return phase.progress;
  if (phase.id === 1) {
    const localScore = Math.round(phase1HealthScoreValue.value);
    const sharedScore = Math.round(sharedPhaseDiagnostics.value.phase1GlobalScore);
    return Number.isFinite(sharedScore) ? sharedScore : localScore;
  }
  if (phase.id === 4) {
    const localScore = Math.round(phase4HealthScoreValue.value);
    const sharedScore = Math.round(sharedPhaseDiagnostics.value.phase4GlobalScore);
    return Number.isFinite(sharedScore) ? sharedScore : localScore;
  }
  if (phase.id === 2) {
    const sharedScore = Math.round(sharedPhaseDiagnostics.value.phase2GlobalScore);
    return Number.isFinite(sharedScore) ? sharedScore : phase.progress;
  }
  if (phase.id === 3) {
    const sharedScore = Math.round(sharedPhaseDiagnostics.value.phase3GlobalScore);
    return Number.isFinite(sharedScore) ? sharedScore : phase.progress;
  }
  return phase.progress;
}

function phaseDonutStyle(phase: GuidePhase): Record<string, string> {
  const progress = phaseDisplayProgress(phase);
  return {
    '--phase-progress': `${progress}%`,
    '--phase-progress-color': scoreColor(progress),
  };
}

const phaseSnapshots = computed<PhaseSnapshot[]>(() =>
  phases.map((phase) => {
    const score = phaseDisplayProgress(phase);
    return {
      phase,
      score,
      grade: gradeFromScore(score),
    };
  }),
);

const mostTensePhase = computed(
  () => phaseSnapshots.value.slice().sort((a, b) => a.score - b.score)[0] ?? null,
);

const strongestPhase = computed(
  () => phaseSnapshots.value.slice().sort((a, b) => b.score - a.score)[0] ?? null,
);

function phaseSummaryStyle(snapshot: PhaseSnapshot | null): Record<string, string> {
  if (!snapshot) return {};
  const color = scoreColor(snapshot.score);
  return {
    borderColor: color.replace(')', ' / 0.28)'),
  };
}

function phaseCardStyle(phase: GuidePhase): Record<string, string> {
  const score = phaseDisplayProgress(phase);
  const grade = gradeFromScore(score);
  const tintColor =
    grade === 'A' || grade === 'B' ? scoreColor(score).replace(')', ' / 0.08)') : 'transparent';
  return {
    '--ui-home-phase-border-color': scoreColor(score),
    '--ui-home-phase-tint': tintColor,
  };
}

onMounted(() => {
  void store.fetchSettings();
  void store.refreshAll();
  void annualIncomeStore.loadAll();
  void annualExpenseStore.loadAll();
});
</script>

<template>
  <div class="container ui-pro-page">
    <section class="card ui-pro-panel ui-home-intro">
      <div class="ui-home-intro-text">
        <p class="ui-pro-kicker">Guia financiera</p>
        <h1 class="h1 ui-home-title">Mapa de fases financieras</h1>
        <p class="subtle ui-home-copy">
          Cada fase refleja una dimension distinta de tu situacion. Mejorar una puede afectar
          temporalmente a otra, asi que conviene revisar el equilibrio global.
        </p>
        <p v-if="mostTensePhase" class="ui-home-focus-line">
          <span class="ui-home-focus-label">Foco actual:</span>
          F{{ mostTensePhase.phase.id }} - {{ mostTensePhase.phase.title }}
          <span class="ui-home-focus-meta">
            ({{ mostTensePhase.grade }} · {{ mostTensePhase.score }}%)
          </span>
        </p>
      </div>
      <div class="ui-home-intro-kpis">
        <div class="ui-home-intro-kpi" :style="phaseSummaryStyle(mostTensePhase)">
          <span>Mayor tension</span>
          <strong v-if="mostTensePhase">
            F{{ mostTensePhase.phase.id }} · {{ mostTensePhase.grade }} ·
            {{ mostTensePhase.score }}%
          </strong>
          <strong v-else>-</strong>
        </div>
        <div class="ui-home-intro-kpi" :style="phaseSummaryStyle(strongestPhase)">
          <span>Mejor posicionada</span>
          <strong v-if="strongestPhase">
            F{{ strongestPhase.phase.id }} · {{ strongestPhase.grade }} ·
            {{ strongestPhase.score }}%
          </strong>
          <strong v-else>-</strong>
        </div>
      </div>
    </section>

    <article class="section card ui-pro-panel">
      <h2 class="h2">Ruta por fases</h2>
      <p class="subtle ui-home-block-copy">
        Selecciona una fase para abrir su vista de detalle y revisar el diagnostico asociado.
      </p>

      <ol class="ui-home-phase-row">
        <li
          v-for="phase in phases"
          :key="phase.id"
          class="ui-home-phase-card"
          :style="phaseCardStyle(phase)"
          :class="{
            'ui-home-phase-done': phaseState(phase) === 'done',
            'ui-home-phase-active': phaseState(phase) === 'active',
          }"
        >
          <RouterLink class="ui-home-phase-link" :to="phaseDetailTo(phase.id)">
            <div class="ui-home-phase-head">
              <span class="ui-home-phase-id">F{{ phase.id }}</span>
              <ScoreGradeBadge :score="phaseDisplayProgress(phase)" />
            </div>

            <div class="ui-home-phase-title">{{ phase.title }}</div>
            <div class="ui-home-phase-focus">{{ phase.focus }}</div>

            <div class="ui-home-phase-donut" :style="phaseDonutStyle(phase)">
              <div class="ui-home-phase-donut-inner">{{ phaseDisplayProgress(phase) }}%</div>
            </div>

            <div class="ui-home-phase-cta">Ver detalle de fase</div>
          </RouterLink>
        </li>
      </ol>
    </article>
  </div>
</template>
