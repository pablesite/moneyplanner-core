import { computed, onMounted, ref, watch } from 'vue';
import { useRoute } from 'vue-router';
import { useAnnualExpenseStore, useAnnualIncomeStore } from '@/domains/data-input';
import { effectiveAnnualAmountForEntry } from '@/domains/data-input/annualEntryUtils';
import { useNetWorthStore } from '@/domains/net-worth';
import {
  findGuidePhaseById,
  getActiveGuidePhase,
  guidePhaseDetailTo,
  guidePhases,
  type GuidePhase,
} from './phases';
import { computeGuidePhaseDiagnostics } from './phaseDiagnostics';
import { gradeFromScore, scoreColor } from './scoreVisuals';

export type GuideScope = 'core' | 'saas';

export function useGuideHomeState(scope: GuideScope) {
  const phases = guidePhases;
  const store = useNetWorthStore();
  const annualIncomeStore = useAnnualIncomeStore(scope);
  const annualExpenseStore = useAnnualExpenseStore(scope);
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

  const phaseDetailTo = guidePhaseDetailTo;

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
      liabilitiesWithAmountCountValue.value > 0 &&
      liabilitiesWithPaymentInputCountValue.value === 0,
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
        row.taePct != null && row.taePct >= highInterestDebtThresholdPct
          ? acc + row.amountBase
          : acc,
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

  const isLoading = computed(
    () =>
      store.loading ||
      annualIncomeStore.loading.value ||
      annualExpenseStore.loading.value ||
      store.summary === null,
  );

  onMounted(() => {
    void store.fetchSettings();
    void store.refreshAll();
    void annualIncomeStore.loadAll();
    void annualExpenseStore.loadAll();
  });

  return {
    isLoading,
    phaseState,
    phaseDetailTo,
    phaseDisplayProgress,
    phaseDonutStyle,
    phaseSummaryStyle,
    phaseCardStyle,
    mostTensePhase,
    strongestPhase,
  };
}

export function useGuidePhaseDetailState(scope: GuideScope) {
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
    detailText?: string;
    incomplete?: boolean;
  };

  type ScoreCard = {
    id: string;
    title: string;
    score: number;
    description: string;
    kpis: ScoreKpi[];
  };

  type InfoCard = {
    id: string;
    title: string;
    description: string;
    kpis: ScoreKpi[];
  };

  type SummaryCard = {
    id: string;
    label: string;
    valueText: string;
    valueTone?: 'neutral' | 'positive' | 'negative' | 'warning';
    metaText?: string;
  };

  type SummarySection = {
    id: string;
    title: string;
    description?: string;
    columns: 2 | 4;
    cards: SummaryCard[];
  };

  type PhaseQuickAction = {
    id: string;
    label: string;
    to: string;
  };

  const route = useRoute();
  const store = useNetWorthStore();
  const annualIncomeStore = useAnnualIncomeStore(scope);
  const annualExpenseStore = useAnnualExpenseStore(scope);
  const selectedExtraordinaryEventGroup = ref<string>('all');
  const guideFiscalYear = computed(() => new Date().getFullYear());

  const phaseId = computed(() => {
    const raw = String(route.params.phaseId ?? '');
    const parsed = Number.parseInt(raw, 10);
    return Number.isFinite(parsed) ? parsed : null;
  });

  const phase = computed(() => (phaseId.value == null ? null : findGuidePhaseById(phaseId.value)));
  const isDebtPhase = computed(() => phase.value?.id === 1);
  const isCashFlowPhase = computed(() => phase.value?.id === 2);
  const isEmergencyFundPhase = computed(() => phase.value?.id === 3);
  const isNetWorthHealthPhase = computed(() => phase.value?.id === 4);
  const hasDiagnosticPhase = computed(
    () =>
      isDebtPhase.value ||
      isCashFlowPhase.value ||
      isEmergencyFundPhase.value ||
      isNetWorthHealthPhase.value,
  );
  const phaseQuickActions = computed<PhaseQuickAction[]>(() => {
    const phaseValue = phase.value;
    if (!phaseValue) return [];

    const actionsById: Record<number, PhaseQuickAction[]> = {
      1: [
        {
          id: 'net-worth',
          label: 'Patrimonio',
          to: '/patrimonio',
        },
        {
          id: 'account',
          label: 'Cuenta',
          to: '/account',
        },
        {
          id: 'budget',
          label: 'Presupuesto',
          to: '/presupuesto',
        },
      ],
      2: [
        {
          id: 'budget',
          label: 'Presupuesto',
          to: '/presupuesto',
        },
        {
          id: 'account',
          label: 'Cuenta',
          to: '/account',
        },
        {
          id: 'net-worth',
          label: 'Patrimonio',
          to: '/patrimonio',
        },
      ],
      3: [
        {
          id: 'net-worth',
          label: 'Patrimonio',
          to: '/patrimonio',
        },
        {
          id: 'budget',
          label: 'Presupuesto',
          to: '/presupuesto',
        },
        {
          id: 'account',
          label: 'Cuenta',
          to: '/account',
        },
      ],
      4: [
        {
          id: 'net-worth',
          label: 'Patrimonio',
          to: '/patrimonio',
        },
        {
          id: 'account',
          label: 'Cuenta',
          to: '/account',
        },
        {
          id: 'budget',
          label: 'Presupuesto',
          to: '/presupuesto',
        },
      ],
      5: [
        {
          id: 'net-worth',
          label: 'Patrimonio',
          to: '/patrimonio',
        },
        {
          id: 'budget',
          label: 'Presupuesto',
          to: '/presupuesto',
        },
        {
          id: 'account',
          label: 'Cuenta',
          to: '/account',
        },
      ],
    };

    return (
      actionsById[phaseValue.id] ?? [
        {
          id: 'account',
          label: 'Cuenta',
          to: '/account',
        },
        {
          id: 'budget',
          label: 'Presupuesto',
          to: '/presupuesto',
        },
        {
          id: 'net-worth',
          label: 'Patrimonio',
          to: '/patrimonio',
        },
      ]
    );
  });
  const summaryExtended = computed(() => store.summary as SummaryExtended | null);
  const sharedPhaseDiagnostics = computed(() =>
    computeGuidePhaseDiagnostics({
      summary: store.summary as typeof store.summary & { liabilities_unbacked?: string | null },
      assets: store.assets,
      liabilities: store.liabilities,
      annualIncomeEntries: annualIncomeStore.entries.value,
      annualExpenseEntries: annualExpenseStore.entries.value,
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

  function valueToneFromSignedAmount(value: number): SummaryCard['valueTone'] {
    if (!Number.isFinite(value)) return 'neutral';
    if (value > 0) return 'positive';
    if (value < 0) return 'negative';
    return 'neutral';
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
  const liquidInvestmentSubcategories = new Set([
    'deposits',
    'funds',
    'etfs',
    'roboadvisor',
    'stocks',
    'cryptocurrencies',
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

  const emergencyLiquidAssetsValue = computed(() => {
    return activeAssets.value.reduce((acc, asset) => {
      const amountBase = Math.max(0, toNumber(asset.amount_base));
      if (amountBase <= 0) return acc;
      const isCashLiquidity = asset.category === 'cash';
      const isLiquidInvestment =
        asset.category === 'investments' &&
        liquidInvestmentSubcategories.has(asset.subcategory || 'other');
      return isCashLiquidity || isLiquidInvestment ? acc + amountBase : acc;
    }, 0);
  });

  const immediateLiquidityAssetsValue = computed(() => {
    return activeAssets.value.reduce((acc, asset) => {
      if (asset.category !== 'cash') return acc;
      const amountBase = Math.max(0, toNumber(asset.amount_base));
      return amountBase > 0 ? acc + amountBase : acc;
    }, 0);
  });

  const emergencyLiquidityToAssetsRatioValue = computed(() =>
    assetsValue.value > 0 ? emergencyLiquidAssetsValue.value / assetsValue.value : null,
  );

  const immediateLiquidityShareWithinEmergencyValue = computed(() =>
    emergencyLiquidAssetsValue.value > 0
      ? immediateLiquidityAssetsValue.value / emergencyLiquidAssetsValue.value
      : null,
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
      liabilitiesWithAmountCountValue.value > 0 &&
      liabilitiesWithPaymentInputCountValue.value === 0,
  );

  const totalMonthlyDebtPaymentValue = computed(() =>
    debtRows.value.reduce((acc, row) => acc + row.monthlyPaymentAmount, 0),
  );

  const recurrentAnnualIncomeValue = computed(() =>
    annualIncomeStore.entries.value.reduce(
      (acc, entry) =>
        (entry.timeProfile ??
          (entry.incomeType === 'one_off' ? 'one_off' : 'structural_recurrent')) !== 'one_off'
          ? acc + Number(entry.amountAnnual ?? 0)
          : acc,
      0,
    ),
  );
  const oneOffAnnualIncomeValue = computed(() =>
    annualIncomeStore.entries.value.reduce(
      (acc, entry) =>
        (entry.timeProfile ??
          (entry.incomeType === 'one_off' ? 'one_off' : 'structural_recurrent')) === 'one_off'
          ? acc + Number(entry.amountAnnual ?? 0)
          : acc,
      0,
    ),
  );
  const totalAnnualIncomeValue = computed(
    () => recurrentAnnualIncomeValue.value + oneOffAnnualIncomeValue.value,
  );
  const recurrentAnnualExpenseValue = computed(() =>
    annualExpenseStore.entries.value.reduce(
      (acc, entry) =>
        (entry.timeProfile ??
          (entry.expenseType === 'one_off' ? 'one_off' : 'structural_recurrent')) !== 'one_off'
          ? acc + Number(entry.amountAnnual ?? 0)
          : acc,
      0,
    ),
  );
  function resolveExpenseRole(entry: (typeof annualExpenseStore.entries.value)[number]): string {
    if (entry.cashflowRole) return entry.cashflowRole;
    if (entry.category === 'savings_allocation') return 'savings';
    if (entry.category === 'financial_investments') return 'investment';
    if (entry.category === 'real_estate_assets' || entry.category === 'tangible_assets') {
      return entry.subcategory === 'real_estate_fees_taxes' ? 'tax_fee' : 'asset_purchase';
    }
    return 'operating';
  }
  function resolveExpenseTimeProfile(
    entry: (typeof annualExpenseStore.entries.value)[number],
  ): string {
    return (
      entry.timeProfile ?? (entry.expenseType === 'one_off' ? 'one_off' : 'structural_recurrent')
    );
  }
  const recurrentOperationalExpenseValue = computed(() =>
    annualExpenseStore.entries.value.reduce((acc, entry) => {
      if (resolveExpenseTimeProfile(entry) !== 'structural_recurrent') return acc;
      return resolveExpenseRole(entry) === 'operating'
        ? acc + effectiveAnnualAmountForEntry(entry, entry.fiscalYear)
        : acc;
    }, 0),
  );
  const temporaryCommitmentExpenseValue = computed(() =>
    annualExpenseStore.entries.value.reduce((acc, entry) => {
      if (resolveExpenseTimeProfile(entry) !== 'term_recurrent') return acc;
      return resolveExpenseRole(entry) === 'temporary_commitment'
        ? acc + effectiveAnnualAmountForEntry(entry, entry.fiscalYear)
        : acc;
    }, 0),
  );
  const recurrentSavingsAllocationValue = computed(() =>
    annualExpenseStore.entries.value.reduce((acc, entry) => {
      if (resolveExpenseTimeProfile(entry) === 'one_off') return acc;
      return entry.category === 'savings_allocation' ? acc + Number(entry.amountAnnual ?? 0) : acc;
    }, 0),
  );
  const recurrentFinancialInvestmentAllocationValue = computed(() =>
    annualExpenseStore.entries.value.reduce((acc, entry) => {
      if (resolveExpenseTimeProfile(entry) === 'one_off') return acc;
      return entry.category === 'financial_investments'
        ? acc + Number(entry.amountAnnual ?? 0)
        : acc;
    }, 0),
  );
  const recurrentRealEstateAllocationValue = computed(() =>
    annualExpenseStore.entries.value.reduce((acc, entry) => {
      if (resolveExpenseTimeProfile(entry) === 'one_off') return acc;
      return entry.category === 'real_estate_assets' ? acc + Number(entry.amountAnnual ?? 0) : acc;
    }, 0),
  );
  const recurrentTangibleAllocationValue = computed(() =>
    annualExpenseStore.entries.value.reduce((acc, entry) => {
      if (resolveExpenseTimeProfile(entry) === 'one_off') return acc;
      return entry.category === 'tangible_assets' ? acc + Number(entry.amountAnnual ?? 0) : acc;
    }, 0),
  );
  const oneOffAnnualExpenseValue = computed(() =>
    annualExpenseStore.entries.value.reduce(
      (acc, entry) =>
        resolveExpenseTimeProfile(entry) === 'one_off'
          ? acc + Number(entry.amountAnnual ?? 0)
          : acc,
      0,
    ),
  );
  const totalAnnualExpenseValue = computed(
    () => recurrentAnnualExpenseValue.value + oneOffAnnualExpenseValue.value,
  );
  const totalAnnualCashFlowValue = computed(
    () => totalAnnualIncomeValue.value - totalAnnualExpenseValue.value,
  );
  const recurrentExpenseToIncomeRatioValue = computed(() =>
    recurrentAnnualIncomeValue.value > 0
      ? recurrentOperationalExpenseValue.value / recurrentAnnualIncomeValue.value
      : null,
  );
  const recurrentAfterCommitmentsMonthlyValue = computed(() => {
    if (recurrentAnnualIncomeValue.value <= 0) return null;
    return (
      (recurrentAnnualIncomeValue.value -
        recurrentOperationalExpenseValue.value -
        temporaryCommitmentExpenseValue.value) /
      12
    );
  });
  const recurrentFinancialInvestmentAllocationRatioValue = computed(() =>
    recurrentAnnualIncomeValue.value > 0
      ? recurrentFinancialInvestmentAllocationValue.value / recurrentAnnualIncomeValue.value
      : null,
  );
  const recurrentTangibleAllocationRatioValue = computed(() =>
    recurrentAnnualIncomeValue.value > 0
      ? recurrentTangibleAllocationValue.value / recurrentAnnualIncomeValue.value
      : null,
  );
  const recurrentRealEstateAllocationRatioValue = computed(() =>
    recurrentAnnualIncomeValue.value > 0
      ? recurrentRealEstateAllocationValue.value / recurrentAnnualIncomeValue.value
      : null,
  );
  const recurrentTotalCashFlowValue = computed(
    () => recurrentAnnualIncomeValue.value - recurrentAnnualExpenseValue.value,
  );
  const recurrentAfterCommitmentsCashFlowValue = computed(
    () =>
      recurrentAnnualIncomeValue.value -
      recurrentOperationalExpenseValue.value -
      temporaryCommitmentExpenseValue.value,
  );
  const recurrentPatrimonialAllocationTotalValue = computed(
    () =>
      recurrentSavingsAllocationValue.value +
      recurrentFinancialInvestmentAllocationValue.value +
      recurrentTangibleAllocationValue.value +
      recurrentRealEstateAllocationValue.value,
  );
  const extraordinaryEventGroupOptions = computed(() => {
    const values = new Set<string>();
    for (const entry of annualIncomeStore.entries.value) {
      const profile =
        entry.timeProfile ?? (entry.incomeType === 'one_off' ? 'one_off' : 'structural_recurrent');
      if (profile !== 'one_off') continue;
      const group = String(entry.eventGroup ?? '').trim();
      if (group) values.add(group);
    }
    for (const entry of annualExpenseStore.entries.value) {
      const profile =
        entry.timeProfile ?? (entry.expenseType === 'one_off' ? 'one_off' : 'structural_recurrent');
      if (profile !== 'one_off') continue;
      const group = String(entry.eventGroup ?? '').trim();
      if (group) values.add(group);
    }
    return Array.from(values).sort((a, b) => a.localeCompare(b, 'es'));
  });
  const structuralOperatingMonthlyExpenseValue = computed(() =>
    recurrentOperationalExpenseValue.value > 0 ? recurrentOperationalExpenseValue.value / 12 : null,
  );
  const currentCommittedMonthlyExpenseValue = computed(() => {
    const annualCommitted =
      recurrentOperationalExpenseValue.value + temporaryCommitmentExpenseValue.value;
    return annualCommitted > 0 ? annualCommitted / 12 : null;
  });
  const emergencyCoverageMonthsBaseValue = computed(() =>
    structuralOperatingMonthlyExpenseValue.value != null &&
    structuralOperatingMonthlyExpenseValue.value > 0
      ? emergencyLiquidAssetsValue.value / structuralOperatingMonthlyExpenseValue.value
      : null,
  );
  const emergencyCoverageMonthsCommittedValue = computed(() =>
    currentCommittedMonthlyExpenseValue.value != null &&
    currentCommittedMonthlyExpenseValue.value > 0
      ? emergencyLiquidAssetsValue.value / currentCommittedMonthlyExpenseValue.value
      : null,
  );
  const selectedExtraordinaryEventGroupLabel = computed(() =>
    selectedExtraordinaryEventGroup.value === 'all'
      ? 'Todos los eventos'
      : selectedExtraordinaryEventGroup.value,
  );
  const filteredOneOffAnnualIncomeValue = computed(() => {
    if (selectedExtraordinaryEventGroup.value === 'all') return oneOffAnnualIncomeValue.value;
    return annualIncomeStore.entries.value.reduce((acc, entry) => {
      const profile =
        entry.timeProfile ?? (entry.incomeType === 'one_off' ? 'one_off' : 'structural_recurrent');
      if (profile !== 'one_off') return acc;
      return String(entry.eventGroup ?? '').trim() === selectedExtraordinaryEventGroup.value
        ? acc + Number(entry.amountAnnual ?? 0)
        : acc;
    }, 0);
  });
  const filteredOneOffAnnualExpenseValue = computed(() => {
    if (selectedExtraordinaryEventGroup.value === 'all') return oneOffAnnualExpenseValue.value;
    return annualExpenseStore.entries.value.reduce((acc, entry) => {
      const profile =
        entry.timeProfile ?? (entry.expenseType === 'one_off' ? 'one_off' : 'structural_recurrent');
      if (profile !== 'one_off') return acc;
      return String(entry.eventGroup ?? '').trim() === selectedExtraordinaryEventGroup.value
        ? acc + Number(entry.amountAnnual ?? 0)
        : acc;
    }, 0);
  });
  const filteredExtraordinaryNetCashFlowValue = computed(
    () => filteredOneOffAnnualIncomeValue.value - filteredOneOffAnnualExpenseValue.value,
  );
  const extraordinaryVolumeRatioValue = computed(() => {
    const numerator =
      Math.abs(oneOffAnnualIncomeValue.value) + Math.abs(oneOffAnnualExpenseValue.value);
    if (totalAnnualIncomeValue.value <= 0) return null;
    return numerator / totalAnnualIncomeValue.value;
  });

  const monthlyIncomeValue = computed(() => {
    const annual = Number(recurrentAnnualIncomeValue.value ?? 0);
    if (!Number.isFinite(annual) || annual <= 0) return null;
    return annual / 12;
  });

  watch(extraordinaryEventGroupOptions, (options) => {
    if (
      selectedExtraordinaryEventGroup.value !== 'all' &&
      !options.includes(selectedExtraordinaryEventGroup.value)
    ) {
      selectedExtraordinaryEventGroup.value = 'all';
    }
  });

  function selectExtraordinaryEventGroup(value: string, event: Event): void {
    selectedExtraordinaryEventGroup.value = value;
    const target = event.currentTarget as HTMLElement | null;
    const details = target?.closest('details') as HTMLDetailsElement | null;
    if (details) details.open = false;
  }

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
        row.taePct != null && row.taePct >= highInterestDebtThresholdPct
          ? acc + row.amountBase
          : acc,
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

  const phase4GlobalScoreValue = computed(() => sharedPhaseDiagnostics.value.phase4GlobalScore);

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

  const phase1GlobalScoreValue = computed(() => sharedPhaseDiagnostics.value.phase1GlobalScore);
  const cashFlowStructuralOperatingScoreValue = computed(() =>
    linearScoreDecreasing(recurrentExpenseToIncomeRatioValue.value, 0.5, 1),
  );
  const committedLoadToIncomeRatioValue = computed(() =>
    recurrentAnnualIncomeValue.value > 0
      ? (recurrentOperationalExpenseValue.value + temporaryCommitmentExpenseValue.value) /
        recurrentAnnualIncomeValue.value
      : null,
  );
  const temporaryCommitmentToIncomeRatioValue = computed(() =>
    recurrentAnnualIncomeValue.value > 0
      ? temporaryCommitmentExpenseValue.value / recurrentAnnualIncomeValue.value
      : null,
  );
  const cashFlowCommittedLoadScoreValue = computed(() =>
    linearScoreDecreasing(committedLoadToIncomeRatioValue.value, 0.65, 1.05),
  );
  const cashFlowTemporaryCommitmentScoreValue = computed(() =>
    linearScoreDecreasing(temporaryCommitmentToIncomeRatioValue.value, 0.05, 0.35),
  );
  const totalAnnualCashFlowToRecurrentIncomeRatioValue = computed(() =>
    recurrentAnnualIncomeValue.value > 0
      ? totalAnnualCashFlowValue.value / recurrentAnnualIncomeValue.value
      : null,
  );
  const cashFlowTotalAnnualFlowScoreValue = computed(() =>
    linearScoreIncreasing(totalAnnualCashFlowToRecurrentIncomeRatioValue.value, -0.5, 0),
  );
  const phase2GlobalScoreValue = computed(() => sharedPhaseDiagnostics.value.phase2GlobalScore);
  const emergencyCoverageBaseScoreValue = computed(() =>
    linearScoreIncreasing(emergencyCoverageMonthsBaseValue.value, 3, 12),
  );
  const emergencyCoverageCommittedScoreValue = computed(() =>
    linearScoreIncreasing(emergencyCoverageMonthsCommittedValue.value, 3, 12),
  );
  const emergencyLiquidityToAssetsScoreValue = computed(() =>
    linearScoreIncreasing(emergencyLiquidityToAssetsRatioValue.value, 0.05, 0.3),
  );
  const emergencyImmediateLiquidityQualityScoreValue = computed(() =>
    linearScoreIncreasing(immediateLiquidityShareWithinEmergencyValue.value, 0.4, 0.85),
  );
  const phase3CoverageScoreValue = computed(() =>
    weightedScore([
      { score: emergencyCoverageBaseScoreValue.value, weight: 0.65 },
      { score: emergencyCoverageCommittedScoreValue.value, weight: 0.35 },
    ]),
  );
  const phase3LiquidityQualityScoreValue = computed(() =>
    weightedScore([
      { score: emergencyLiquidityToAssetsScoreValue.value, weight: 0.5 },
      { score: emergencyImmediateLiquidityQualityScoreValue.value, weight: 0.5 },
    ]),
  );
  const phase3GlobalScoreValue = computed(() => sharedPhaseDiagnostics.value.phase3GlobalScore);

  function toneFromScore(score: number): ScoreTone {
    if (score >= 75) return 'solid';
    if (score >= 55) return 'medium';
    if (score >= 35) return 'watch';
    return 'risk';
  }

  const globalScoreValue = computed(() => {
    if (isDebtPhase.value) return phase1GlobalScoreValue.value;
    if (isCashFlowPhase.value) return phase2GlobalScoreValue.value;
    if (isEmergencyFundPhase.value) return phase3GlobalScoreValue.value;
    if (isNetWorthHealthPhase.value) return phase4GlobalScoreValue.value;
    return 0;
  });

  const globalToneValue = computed(() => toneFromScore(globalScoreValue.value));

  const globalLabelValue = computed(() => {
    const tone = globalToneValue.value;
    if (isDebtPhase.value) {
      if (tone === 'solid') return 'Deuda saneada';
      if (tone === 'medium') return 'Deuda controlada';
      if (tone === 'watch') return 'Deuda en vigilancia';
      return 'Deuda critica';
    }
    if (isCashFlowPhase.value) {
      if (tone === 'solid') return 'Flujo operativo solido';
      if (tone === 'medium') return 'Flujo operativo estable';
      if (tone === 'watch') return 'Flujo operativo ajustado';
      return 'Flujo operativo en tension';
    }
    if (isEmergencyFundPhase.value) {
      if (tone === 'solid') return 'Colchon robusto';
      if (tone === 'medium') return 'Colchon suficiente';
      if (tone === 'watch') return 'Colchon justo';
      return 'Colchon insuficiente';
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

  const phase2ScoreCards = computed<ScoreCard[]>(() => [
    {
      id: 'cashflow-recurrent-tension',
      title: 'Tension de caja (recurrente)',
      score: weightedScore([
        { score: cashFlowStructuralOperatingScoreValue.value, weight: 0.4 },
        { score: cashFlowCommittedLoadScoreValue.value, weight: 0.35 },
      ]),
      description:
        'Lectura principal de tension recurrente: coste de vida base y carga actual de caja incluyendo compromisos temporales.',
      kpis: [
        {
          id: 'structural-operating-ratio',
          label: 'Base de gasto estructural (% ingresos recurrentes)',
          valueText: formatPct(recurrentExpenseToIncomeRatioValue.value, 0),
          score: cashFlowStructuralOperatingScoreValue.value,
          hint: 'Coste de vida base. Menor es mejor (score inverso).',
        },
        {
          id: 'committed-load-ratio',
          label: 'Tension total actual de caja (% ingresos recurrentes)',
          valueText: formatPct(committedLoadToIncomeRatioValue.value, 0),
          score: cashFlowCommittedLoadScoreValue.value,
          hint: 'Gasto base + cargas temporales de caja. Menor es mejor (score inverso).',
          detailText:
            recurrentAfterCommitmentsMonthlyValue.value == null
              ? undefined
              : `Colchon mensual tras cargas temporales: ${formatNumber(recurrentAfterCommitmentsMonthlyValue.value, 2)}`,
        },
      ],
    },
    {
      id: 'cashflow-temporality-and-year-close',
      title: 'Temporalidad y cierre anual',
      score: weightedScore([
        { score: cashFlowTemporaryCommitmentScoreValue.value, weight: 0.15 },
        { score: cashFlowTotalAnnualFlowScoreValue.value, weight: 0.1 },
      ]),
      description:
        'Complemento del diagnostico: peso de compromisos temporales y resultado anual total (incluye extraordinarios y asignacion patrimonial).',
      kpis: [
        {
          id: 'temporary-commitment-ratio',
          label: 'Peso de cargas temporales de caja (% ingresos recurrentes)',
          valueText: formatPct(temporaryCommitmentToIncomeRatioValue.value, 0),
          score: cashFlowTemporaryCommitmentScoreValue.value,
          hint: 'Parte de la tension que viene de cuotas con fecha fin. Menor es mejor (score inverso).',
        },
        {
          id: 'total-annual-cash-flow-ratio',
          label: 'Resultado anual total (% ingresos recurrentes)',
          valueText: formatPct(totalAnnualCashFlowToRecurrentIncomeRatioValue.value, 0),
          score: cashFlowTotalAnnualFlowScoreValue.value,
          hint: 'Resultado anual completo de caja (recurrente + puntual). Incluye asignacion patrimonial y extraordinarios. Mayor es mejor.',
          detailText: `Ingresos anuales totales ${formatNumber(totalAnnualIncomeValue.value, 2)} · Gastos anuales totales ${formatNumber(totalAnnualExpenseValue.value, 2)} · Flujo anual total ${formatNumber(totalAnnualCashFlowValue.value, 2)}`,
        },
      ],
    },
  ]);

  const phase2DistributionInfoCards = computed<InfoCard[]>(() => [
    {
      id: 'cashflow-savings-distribution',
      title: 'Distribucion del ahorro',
      description:
        'Indicadores informativos de asignacion recurrente a patrimonio sobre ingresos recurrentes.',
      kpis: [
        {
          id: 'financial-investments-income',
          label: '% inversiones / ingresos recurrentes',
          valueText: formatPct(recurrentFinancialInvestmentAllocationRatioValue.value, 0),
          score: null,
          hint: 'Categoria inversiones financieras / ingresos recurrentes',
        },
        {
          id: 'tangible-assets-income',
          label: '% activos mobiliarios / ingresos recurrentes',
          valueText: formatPct(recurrentTangibleAllocationRatioValue.value, 0),
          score: null,
          hint: 'Categoria activos mobiliarios / ingresos recurrentes',
        },
        {
          id: 'real-estate-assets-income',
          label: '% activos inmobiliarios / ingresos recurrentes',
          valueText: formatPct(recurrentRealEstateAllocationRatioValue.value, 0),
          score: null,
          hint: 'Categoria activos inmobiliarios / ingresos recurrentes',
        },
      ],
    },
  ]);

  const phase3ScoreCards = computed<ScoreCard[]>(() => [
    {
      id: 'emergency-coverage',
      title: 'Cobertura del colchon',
      score: phase3CoverageScoreValue.value,
      description:
        'Cobertura de liquidez util medida contra gasto base (Fase 2) y carga actual incluyendo compromisos temporales.',
      kpis: [
        {
          id: 'emergency-months-base',
          label: 'Meses de gasto base cubiertos',
          valueText:
            emergencyCoverageMonthsBaseValue.value == null
              ? '-'
              : `${formatNumber(emergencyCoverageMonthsBaseValue.value, 1)} meses`,
          score: emergencyCoverageBaseScoreValue.value,
          hint: 'Liquidez util / gasto operativo estructural mensual. Mayor es mejor.',
        },
        {
          id: 'emergency-months-committed',
          label: 'Meses de gasto actual cubiertos',
          valueText:
            emergencyCoverageMonthsCommittedValue.value == null
              ? '-'
              : `${formatNumber(emergencyCoverageMonthsCommittedValue.value, 1)} meses`,
          score: emergencyCoverageCommittedScoreValue.value,
          hint: 'Liquidez util / (gasto estructural + cargas temporales) mensual. Mayor es mejor.',
          detailText:
            currentCommittedMonthlyExpenseValue.value == null
              ? undefined
              : `Carga mensual actual estimada: ${formatNumber(currentCommittedMonthlyExpenseValue.value, 2)}`,
        },
      ],
    },
    {
      id: 'emergency-liquidity-quality',
      title: 'Calidad de liquidez',
      score: phase3LiquidityQualityScoreValue.value,
      description:
        'Peso de la liquidez dentro del patrimonio y porcentaje de liquidez inmediata dentro del colchon.',
      kpis: [
        {
          id: 'emergency-liquidity-assets-ratio',
          label: '% liquidez util / activos',
          valueText: formatPct(emergencyLiquidityToAssetsRatioValue.value, 0),
          score: emergencyLiquidityToAssetsScoreValue.value,
          hint: 'Liquidez util disponible para emergencia sobre activos totales. Mayor es mejor.',
        },
        {
          id: 'immediate-liquidity-share',
          label: '% liquidez inmediata / liquidez util',
          valueText: formatPct(immediateLiquidityShareWithinEmergencyValue.value, 0),
          score: emergencyImmediateLiquidityQualityScoreValue.value,
          hint: 'Parte del colchon que esta en cash y acceso inmediato. Mayor es mejor.',
        },
      ],
    },
  ]);

  const scoreCards = computed<ScoreCard[]>(() => {
    if (isDebtPhase.value) return phase1ScoreCards.value;
    if (isCashFlowPhase.value) return phase2ScoreCards.value;
    if (isEmergencyFundPhase.value) return phase3ScoreCards.value;
    if (isNetWorthHealthPhase.value) return phase4ScoreCards.value;
    return [];
  });

  const cashFlowSummarySections = computed<SummarySection[]>(() => {
    if (!isCashFlowPhase.value) return [];
    return [
      {
        id: 'cashflow-core',
        title: 'Caja Recurrente',
        description:
          'Lectura principal de tension de caja: base operativa y cargas temporales de caja.',
        columns: 4,
        cards: [
          {
            id: 'income-recurrent',
            label: 'Ingresos recurrentes anuales',
            valueText: formatNumber(recurrentAnnualIncomeValue.value, 2),
            valueTone: 'neutral',
            metaText:
              recurrentAnnualIncomeValue.value > 0
                ? `${formatNumber(recurrentAnnualIncomeValue.value / 12, 2)} / mes`
                : undefined,
          },
          {
            id: 'expense-operating-structural',
            label: 'Gasto operativo estructural',
            valueText: formatNumber(recurrentOperationalExpenseValue.value, 2),
            valueTone: 'warning',
            metaText:
              recurrentOperationalExpenseValue.value > 0
                ? `${formatNumber(recurrentOperationalExpenseValue.value / 12, 2)} / mes`
                : undefined,
          },
          {
            id: 'expense-temporary-commitments',
            label: 'Cargas temporales de caja',
            valueText: formatNumber(temporaryCommitmentExpenseValue.value, 2),
            valueTone: temporaryCommitmentExpenseValue.value > 0 ? 'warning' : 'neutral',
            metaText:
              temporaryCommitmentExpenseValue.value > 0
                ? `${formatNumber(temporaryCommitmentExpenseValue.value / 12, 2)} / mes`
                : 'Sin carga temporal',
          },
          {
            id: 'cashflow-recurrent-after-commitments',
            label: 'Colchon tras cargas temporales',
            valueText: formatNumber(recurrentAfterCommitmentsCashFlowValue.value, 2),
            valueTone: valueToneFromSignedAmount(recurrentAfterCommitmentsCashFlowValue.value),
            metaText:
              recurrentAfterCommitmentsMonthlyValue.value == null
                ? undefined
                : `${formatNumber(recurrentAfterCommitmentsMonthlyValue.value, 2)} / mes`,
          },
        ],
      },
      {
        id: 'cashflow-context',
        title: 'Contexto de Flujo',
        description: 'Contexto anual para no confundir caja operativa con asignacion patrimonial.',
        columns: 4,
        cards: [
          {
            id: 'expense-recurrent-total',
            label: 'Salidas recurrentes totales',
            valueText: formatNumber(recurrentAnnualExpenseValue.value, 2),
            valueTone: 'warning',
            metaText: 'Incluye ahorro e inversion',
          },
          {
            id: 'cashflow-recurrent-annual',
            label: 'Flujo recurrente neto total',
            valueText: formatNumber(recurrentTotalCashFlowValue.value, 2),
            valueTone: valueToneFromSignedAmount(recurrentTotalCashFlowValue.value),
            metaText: 'Tras todas las salidas recurrentes',
          },
          {
            id: 'cashflow-total-annual',
            label: 'Flujo anual total',
            valueText: formatNumber(totalAnnualCashFlowValue.value, 2),
            valueTone: valueToneFromSignedAmount(totalAnnualCashFlowValue.value),
            metaText: 'Incluye extraordinarios',
          },
          {
            id: 'extraordinary-volume-ratio',
            label: 'Peso de extraordinarios',
            valueText: formatPct(extraordinaryVolumeRatioValue.value, 0),
            valueTone:
              extraordinaryVolumeRatioValue.value != null &&
              extraordinaryVolumeRatioValue.value > 0.25
                ? 'warning'
                : 'neutral',
            metaText: 'Volumen de ingresos+gastos puntuales',
          },
        ],
      },
      {
        id: 'cashflow-patrimonial',
        title: 'Asignacion Patrimonial Recurrente',
        description: 'Asignaciones recurrentes no operativas (informativas, no puntuan el score).',
        columns: 4,
        cards: [
          {
            id: 'patrimonial-total',
            label: 'Asignacion patrimonial recurrente total',
            valueText: formatNumber(recurrentPatrimonialAllocationTotalValue.value, 2),
            valueTone: 'positive',
            metaText:
              recurrentAnnualIncomeValue.value > 0
                ? formatPct(
                    recurrentPatrimonialAllocationTotalValue.value /
                      recurrentAnnualIncomeValue.value,
                    0,
                  ) + ' de ingresos recurrentes'
                : undefined,
          },
          {
            id: 'savings-allocation-recurrent',
            label: 'Ahorro recurrente',
            valueText: formatNumber(recurrentSavingsAllocationValue.value, 2),
            valueTone: 'positive',
          },
          {
            id: 'financial-investments-allocation-recurrent',
            label: 'Inversiones financieras recurrentes',
            valueText: formatNumber(recurrentFinancialInvestmentAllocationValue.value, 2),
            valueTone: 'positive',
          },
          {
            id: 'assets-allocation-mixed',
            label: 'Activos (mobiliarios + inmobiliarios)',
            valueText: formatNumber(
              recurrentTangibleAllocationValue.value + recurrentRealEstateAllocationValue.value,
              2,
            ),
            valueTone: 'positive',
            metaText: `Mobiliarios ${formatNumber(recurrentTangibleAllocationValue.value, 2)} · Inmobiliarios ${formatNumber(recurrentRealEstateAllocationValue.value, 2)}`,
          },
        ],
      },
      {
        id: 'cashflow-extraordinary',
        title: 'Extraordinarios',
        description:
          'Eventos puntuales del ano (visibles como contexto, separados del score principal).',
        columns: 4,
        cards: [
          {
            id: 'income-one-off',
            label: 'Ingresos extraordinarios',
            valueText: formatNumber(filteredOneOffAnnualIncomeValue.value, 2),
            valueTone: filteredOneOffAnnualIncomeValue.value > 0 ? 'positive' : 'neutral',
            metaText:
              selectedExtraordinaryEventGroup.value === 'all'
                ? undefined
                : `Evento: ${selectedExtraordinaryEventGroupLabel.value}`,
          },
          {
            id: 'expense-one-off',
            label: 'Gastos extraordinarios',
            valueText: formatNumber(filteredOneOffAnnualExpenseValue.value, 2),
            valueTone: filteredOneOffAnnualExpenseValue.value > 0 ? 'warning' : 'neutral',
            metaText:
              selectedExtraordinaryEventGroup.value === 'all'
                ? undefined
                : `Evento: ${selectedExtraordinaryEventGroupLabel.value}`,
          },
          {
            id: 'cashflow-one-off-net',
            label: 'Flujo extraordinario neto',
            valueText: formatNumber(filteredExtraordinaryNetCashFlowValue.value, 2),
            valueTone: valueToneFromSignedAmount(filteredExtraordinaryNetCashFlowValue.value),
            metaText:
              selectedExtraordinaryEventGroup.value === 'all'
                ? 'Todos los eventos puntuales'
                : `Evento: ${selectedExtraordinaryEventGroupLabel.value}`,
          },
          {
            id: 'cashflow-one-off-grouping',
            label: 'Filtro por evento',
            valueText: selectedExtraordinaryEventGroupLabel.value,
            valueTone: 'neutral',
            metaText: 'Usa Grupo de evento para aislar una operacion puntual',
          },
        ],
      },
    ];
  });

  const cashFlowHeroSummaryCards = computed<SummaryCard[]>(() => {
    if (!isCashFlowPhase.value) return [];
    return cashFlowSummarySections.value[0]?.cards ?? [];
  });

  const cashFlowContextSummarySections = computed<SummarySection[]>(() => {
    if (!isCashFlowPhase.value) return [];
    return cashFlowSummarySections.value.slice(1);
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

    if (isEmergencyFundPhase.value) {
      return [
        {
          id: 'emergency-liquid-assets',
          label: 'Liquidez util para emergencia',
          valueText: formatNumber(emergencyLiquidAssetsValue.value, 2),
        },
        {
          id: 'emergency-immediate-liquidity',
          label: 'Liquidez inmediata',
          valueText: formatNumber(immediateLiquidityAssetsValue.value, 2),
        },
        {
          id: 'emergency-months-base',
          label: 'Meses gasto base',
          valueText:
            emergencyCoverageMonthsBaseValue.value == null
              ? '-'
              : `${formatNumber(emergencyCoverageMonthsBaseValue.value, 1)}m`,
        },
        {
          id: 'emergency-months-committed',
          label: 'Meses carga actual',
          valueText:
            emergencyCoverageMonthsCommittedValue.value == null
              ? '-'
              : `${formatNumber(emergencyCoverageMonthsCommittedValue.value, 1)}m`,
        },
      ];
    }

    if (isCashFlowPhase.value) {
      return [
        {
          id: 'cashflow-recurrent-annual',
          label: 'Flujo anual recurrente',
          valueText: formatNumber(recurrentTotalCashFlowValue.value, 2),
        },
        {
          id: 'cashflow-recurrent-after-commitments',
          label: 'Flujo recurrente tras cargas temporales',
          valueText: formatNumber(recurrentAfterCommitmentsCashFlowValue.value, 2),
        },
        {
          id: 'cashflow-total-annual',
          label: 'Flujo anual total',
          valueText: formatNumber(totalAnnualCashFlowValue.value, 2),
        },
        {
          id: 'savings-allocation-recurrent',
          label: 'Asignacion recurrente a ahorro',
          valueText: formatNumber(recurrentSavingsAllocationValue.value, 2),
        },
      ];
    }

    return [];
  });

  const cashFlowDistortionWarning = computed(() => {
    if (!isCashFlowPhase.value) return null;
    if (extraordinaryVolumeRatioValue.value == null) return null;
    if (extraordinaryVolumeRatioValue.value <= 0.25) return null;
    return `Ano con eventos extraordinarios (${formatPct(extraordinaryVolumeRatioValue.value, 0)} del ingreso total). El score prioriza tension recurrente estructural y cargas temporales de caja.`;
  });

  const phaseDiagnosticCopy = computed(() => {
    if (isDebtPhase.value) {
      return 'Diagnostico de deuda: coste, respaldo y concentracion para priorizar amortizacion.';
    }
    if (isNetWorthHealthPhase.value) {
      return 'Diagnostico de salud patrimonial: respaldo patrimonial y distribucion del riesgo.';
    }
    if (isCashFlowPhase.value) {
      return 'Diagnostico de flujo de caja: score compuesto de tension recurrente (operativo estructural + cargas temporales de caja) y contexto extraordinario separado.';
    }
    if (isEmergencyFundPhase.value) {
      return 'Diagnostico de fondo de emergencia: cobertura del colchon usando liquidez util (baseline Fase 4) contra gasto base y carga actual (semantica Fase 2).';
    }
    return phase.value?.objective ?? '';
  });

  function maybeLoadNetWorthContext() {
    if (!hasDiagnosticPhase.value) return;
    void store.fetchSettings();
    void store.refreshAll();
    if (isDebtPhase.value || isCashFlowPhase.value) {
      void annualIncomeStore.loadAll(guideFiscalYear.value);
    }
    if (isCashFlowPhase.value || isEmergencyFundPhase.value) {
      void annualExpenseStore.loadAll(guideFiscalYear.value);
    }
  }

  const phaseDetailTo = guidePhaseDetailTo;

  watch(
    phaseId,
    () => {
      maybeLoadNetWorthContext();
    },
    { immediate: true },
  );

  return {
    store,
    formatNumber,
    selectedExtraordinaryEventGroup,
    phase,
    isDebtPhase,
    isCashFlowPhase,
    isEmergencyFundPhase,
    isNetWorthHealthPhase,
    hasDiagnosticPhase,
    phaseQuickActions,
    phaseDiagnosticCopy,
    globalScoreValue,
    globalToneValue,
    globalLabelValue,
    scoreCards,
    summaryCards,
    cashFlowHeroSummaryCards,
    cashFlowContextSummarySections,
    cashFlowDistortionWarning,
    phase2DistributionInfoCards,
    phase1ScoreCards,
    phase2ScoreCards,
    phase3ScoreCards,
    phase4ScoreCards,
    phaseDetailTo,
    selectedExtraordinaryEventGroupLabel,
    extraordinaryEventGroupOptions,
    selectExtraordinaryEventGroup,
  };
}
