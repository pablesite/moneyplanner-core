import type { Asset, Liability, Summary } from '@/domains/net-worth/models';

type SummaryExtended = Summary & {
  liabilities_unbacked?: string | null;
};

type AnnualIncomeLike = {
  incomeType: 'recurrent' | 'one_off';
  amountAnnual: number;
};

type AnnualExpenseLike = {
  expenseType: 'recurrent' | 'one_off';
  amountAnnual: number;
};

export type GuidePhaseDiagnosticsInput = {
  summary: SummaryExtended | null;
  assets: Asset[];
  liabilities: Liability[];
  annualIncomeEntries: AnnualIncomeLike[];
  annualExpenseEntries: AnnualExpenseLike[];
};

export type GuidePhaseDiagnostics = {
  phase1GlobalScore: number;
  phase2GlobalScore: number;
  phase4GlobalScore: number;
};

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

function isPositiveTae(raw: string | null | undefined): boolean {
  if (raw == null) return false;
  return toNumber(raw) > 0;
}

const ILLIQUID_INVESTMENT_SUBCATEGORIES = new Set([
  'pension_plans',
  'real_estate_crowd',
  'crowdlending',
  'other',
]);

function sumAnnualByType<
  TEntry extends { amountAnnual: number },
  TKey extends keyof TEntry,
  TValue extends TEntry[TKey],
>(entries: TEntry[], key: TKey, expected: TValue): number {
  return entries.reduce(
    (acc, entry) => (entry[key] === expected ? acc + Number(entry.amountAnnual ?? 0) : acc),
    0,
  );
}

function computePhase2CashFlowAdjustedScore(input: {
  annualIncomeEntries: AnnualIncomeLike[];
  annualExpenseEntries: AnnualExpenseLike[];
}): number {
  const recurrentAnnualIncome = sumAnnualByType(
    input.annualIncomeEntries,
    'incomeType',
    'recurrent',
  );
  const recurrentAnnualExpense = sumAnnualByType(
    input.annualExpenseEntries,
    'expenseType',
    'recurrent',
  );
  const recurrentAnnualCashFlow = recurrentAnnualIncome - recurrentAnnualExpense;
  const recurrentSavingsToIncomeRatio =
    recurrentAnnualIncome > 0 ? recurrentAnnualCashFlow / recurrentAnnualIncome : null;
  const recurrentExpenseToIncomeRatio =
    recurrentAnnualIncome > 0 ? recurrentAnnualExpense / recurrentAnnualIncome : null;
  const recurrentExpenseCoverage =
    recurrentAnnualExpense > 0
      ? recurrentAnnualIncome / recurrentAnnualExpense
      : recurrentAnnualIncome > 0
        ? 2
        : null;

  return weightedScore([
    { score: linearScoreIncreasing(recurrentSavingsToIncomeRatio, 0, 0.2), weight: 0.45 },
    { score: linearScoreDecreasing(recurrentExpenseToIncomeRatio, 0.7, 0.95), weight: 0.25 },
    { score: linearScoreIncreasing(recurrentExpenseCoverage, 1, 1.2), weight: 0.3 },
  ]);
}

export function computeGuidePhaseDiagnostics(
  input: GuidePhaseDiagnosticsInput,
): GuidePhaseDiagnostics {
  const { summary, assets, liabilities, annualIncomeEntries } = input;
  const annualExpenseEntries = input.annualExpenseEntries ?? [];

  const activeAssets = assets.filter((asset) => asset.is_active);
  const activeLiabilities = liabilities.filter((liability) => liability.is_active);

  const assetsValue = Math.max(0, toNumber(summary?.total_assets));
  const liabilitiesValue = Math.max(0, toNumber(summary?.total_liabilities));
  const unbackedDebtValue = Math.max(0, toNumber(summary?.liabilities_unbacked));

  const assetsByCategoryValues = Object.values(summary?.assets_by_category ?? {})
    .map((value) => Math.max(0, toNumber(value)))
    .filter((value) => value > 0);

  const illiquidAssetsValue = activeAssets.reduce((acc, asset) => {
    const amountBase = Math.max(0, toNumber(asset.amount_base));
    if (amountBase <= 0) return acc;

    const illiquidByCategory =
      asset.category === 'real_estate' ||
      asset.category === 'furnishings' ||
      asset.category === 'other';

    const illiquidByInvestmentSubcategory =
      asset.category === 'investments' &&
      ILLIQUID_INVESTMENT_SUBCATEGORIES.has(asset.subcategory || 'other');

    const illiquidByCashOtherDeposit =
      asset.category === 'cash' &&
      asset.subcategory === 'other' &&
      isPositiveTae(asset.annual_interest_tae);

    return illiquidByCategory || illiquidByInvestmentSubcategory || illiquidByCashOtherDeposit
      ? acc + amountBase
      : acc;
  }, 0);

  const illiquidAssetsShare = assetsValue > 0 ? illiquidAssetsValue / assetsValue : null;
  const unbackedDebtToAssets = assetsValue > 0 ? unbackedDebtValue / assetsValue : null;
  const unbackedDebtToLiabilities =
    liabilitiesValue > 0 ? unbackedDebtValue / liabilitiesValue : null;

  const topAssetShare =
    assetsValue > 0 ? (assetsByCategoryValues.sort((a, b) => b - a)[0] ?? 0) / assetsValue : null;

  const diversificationIndex = (() => {
    if (assetsValue <= 0) return null;
    const shares = assetsByCategoryValues.map((value) => value / assetsValue);
    if (!shares.length) return null;
    const hhi = shares.reduce((acc, share) => acc + share * share, 0);
    const minHhi = 1 / 5;
    const maxHhi = 1;
    return clamp((maxHhi - hhi) / (maxHhi - minHhi), 0, 1);
  })();

  const debtRows = activeLiabilities
    .map((liability) => {
      const amountBase = Math.max(0, toNumber(liability.amount_base));
      const taeRaw = liability.annual_interest_tae;
      const taePct = taeRaw == null || String(taeRaw).trim() === '' ? null : toNumber(taeRaw);
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
    .filter((row) => row.amountBase > 0);

  const topLiabilityShare = (() => {
    if (liabilitiesValue <= 0) return null;
    const topLiability = debtRows.map((row) => row.amountBase).sort((a, b) => b - a)[0] ?? 0;
    return topLiability / liabilitiesValue;
  })();

  const maxLiabilityTaePct = (() => {
    const taes = debtRows
      .map((row) => row.taePct)
      .filter((value): value is number => value != null && Number.isFinite(value));
    if (!taes.length) return null;
    return Math.max(...taes);
  })();

  const weightedLiabilityTaePct = (() => {
    const rows = debtRows.filter((row) => row.taePct != null);
    const denominator = rows.reduce((acc, row) => acc + row.amountBase, 0);
    if (denominator <= 0) return null;
    const numerator = rows.reduce((acc, row) => acc + row.amountBase * (row.taePct ?? 0), 0);
    return numerator / denominator;
  })();

  const liabilitiesWithAmountCount = debtRows.filter((row) => row.amountBase > 0).length;
  const liabilitiesWithPaymentInputCount = debtRows.filter(
    (row) => row.hasMonthlyPaymentInput,
  ).length;
  const hasNoDebtPaymentInputs =
    liabilitiesWithAmountCount > 0 && liabilitiesWithPaymentInputCount === 0;
  const totalMonthlyDebtPayment = debtRows.reduce((acc, row) => acc + row.monthlyPaymentAmount, 0);

  const recurrentAnnualIncome = sumAnnualByType(annualIncomeEntries, 'incomeType', 'recurrent');
  const monthlyIncome =
    Number.isFinite(recurrentAnnualIncome) && recurrentAnnualIncome > 0
      ? recurrentAnnualIncome / 12
      : null;

  const debtPaymentToIncome =
    liabilitiesValue <= 0
      ? 0
      : monthlyIncome == null || monthlyIncome <= 0 || hasNoDebtPaymentInputs
        ? null
        : totalMonthlyDebtPayment / monthlyIncome;

  const highInterestDebtThresholdPct = 8;
  const highInterestDebtValue = debtRows.reduce(
    (acc, row) =>
      row.taePct != null && row.taePct >= highInterestDebtThresholdPct ? acc + row.amountBase : acc,
    0,
  );
  const highInterestDebtShare =
    liabilitiesValue > 0 ? highInterestDebtValue / liabilitiesValue : null;

  const phase4SupportScore = weightedScore([
    { score: linearScoreDecreasing(unbackedDebtToAssets, 0.05, 0.35), weight: 0.5 },
    { score: linearScoreDecreasing(illiquidAssetsShare, 0.25, 0.8), weight: 0.5 },
  ]);
  const phase4RiskDistributionScore = weightedScore([
    { score: linearScoreDecreasing(topAssetShare, 0.4, 0.9), weight: 0.5 },
    { score: linearScoreIncreasing(diversificationIndex, 0.2, 0.8), weight: 0.5 },
  ]);
  const phase4GlobalScore = weightedScore([
    { score: phase4SupportScore, weight: 0.5 },
    { score: phase4RiskDistributionScore, weight: 0.5 },
  ]);

  const phase1DebtCostScore = weightedScore([
    { score: linearScoreDecreasing(maxLiabilityTaePct, 0.5, 10), weight: 0.4 },
    { score: linearScoreDecreasing(weightedLiabilityTaePct, 0.5, 10), weight: 0.4 },
    {
      score: hasNoDebtPaymentInputs ? 100 : linearScoreDecreasing(debtPaymentToIncome, 0.15, 0.6),
      weight: 0.2,
    },
  ]);
  const phase1DebtRiskScore = weightedScore([
    { score: linearScoreDecreasing(unbackedDebtToLiabilities, 0.01, 0.5), weight: 0.4 },
    { score: linearScoreDecreasing(topLiabilityShare, 0.25, 0.95), weight: 0.3 },
    { score: linearScoreDecreasing(highInterestDebtShare, 0.05, 0.6), weight: 0.3 },
  ]);
  const phase1GlobalScore = weightedScore([
    { score: phase1DebtCostScore, weight: 0.5 },
    { score: phase1DebtRiskScore, weight: 0.5 },
  ]);

  const phase2GlobalScore = computePhase2CashFlowAdjustedScore({
    annualIncomeEntries,
    annualExpenseEntries,
  });

  return {
    phase1GlobalScore,
    phase2GlobalScore,
    phase4GlobalScore,
  };
}
