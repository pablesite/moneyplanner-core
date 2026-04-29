import type { Asset, Liability, Summary } from '@/domains/net-worth/models';
import { effectiveAnnualAmountForEntry } from '@/domains/data-input/annualEntryUtils';

type SummaryExtended = Summary & {
  liabilities_unbacked?: string | null;
};

type AnnualIncomeLike = {
  incomeType: 'recurrent' | 'one_off';
  timeProfile?: 'structural_recurrent' | 'term_recurrent' | 'one_off';
  cashflowRole?: 'operating' | 'transfer' | 'asset_sale' | 'tax_adjustment' | 'other';
  amountAnnual: number;
};

type AnnualExpenseLike = {
  category:
    | 'savings_allocation'
    | 'financial_investments'
    | 'real_estate_assets'
    | 'tangible_assets'
    | 'consumption_expenses';
  expenseType: 'recurrent' | 'one_off';
  timeProfile?: 'structural_recurrent' | 'term_recurrent' | 'one_off';
  cashflowRole?:
    | 'operating'
    | 'temporary_commitment'
    | 'savings'
    | 'investment'
    | 'asset_purchase'
    | 'tax_fee'
    | 'transfer'
    | 'other';
  subcategory?: string;
  termEndMonth?: number | null;
  termEndYear?: number | null;
  amountInputPeriod?: 'annual' | 'monthly';
  fiscalYear?: number | null;
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
  phase3GlobalScore: number;
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

const LIQUID_INVESTMENT_SUBCATEGORIES = new Set([
  'deposits',
  'funds',
  'etfs',
  'roboadvisor',
  'stocks',
  'cryptocurrencies',
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

function expenseTimeProfile(entry: AnnualExpenseLike) {
  return (
    entry.timeProfile ?? (entry.expenseType === 'one_off' ? 'one_off' : 'structural_recurrent')
  );
}

function expenseCashflowRole(entry: AnnualExpenseLike) {
  if (entry.cashflowRole) return entry.cashflowRole;
  if (entry.category === 'savings_allocation') return 'savings' as const;
  if (entry.category === 'financial_investments') return 'investment' as const;
  if (entry.category === 'real_estate_assets' || entry.category === 'tangible_assets') {
    return entry.subcategory === 'real_estate_fees_taxes'
      ? ('tax_fee' as const)
      : ('asset_purchase' as const);
  }
  return 'operating' as const;
}

function computeAssetLiquidityMetrics(params: {
  summary: SummaryExtended | null;
  activeAssets: Asset[];
  assetsValue: number;
}) {
  const { summary, activeAssets, assetsValue } = params;
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

  const emergencyLiquidAssetsValue = activeAssets.reduce((acc, asset) => {
    const amountBase = Math.max(0, toNumber(asset.amount_base));
    if (amountBase <= 0) return acc;

    const isCashLiquidity = asset.category === 'cash';
    const isLiquidInvestment =
      asset.category === 'investments' &&
      LIQUID_INVESTMENT_SUBCATEGORIES.has(asset.subcategory || 'other');

    return isCashLiquidity || isLiquidInvestment ? acc + amountBase : acc;
  }, 0);

  const immediateLiquidityAssetsValue = activeAssets.reduce((acc, asset) => {
    if (asset.category !== 'cash') return acc;
    const amountBase = Math.max(0, toNumber(asset.amount_base));
    return amountBase > 0 ? acc + amountBase : acc;
  }, 0);

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

  return {
    illiquidAssetsValue,
    illiquidAssetsShare: assetsValue > 0 ? illiquidAssetsValue / assetsValue : null,
    emergencyLiquidAssetsValue,
    immediateLiquidityAssetsValue,
    emergencyLiquidityToAssets: assetsValue > 0 ? emergencyLiquidAssetsValue / assetsValue : null,
    immediateLiquidityShareWithinEmergency:
      emergencyLiquidAssetsValue > 0
        ? immediateLiquidityAssetsValue / emergencyLiquidAssetsValue
        : null,
    topAssetShare,
    diversificationIndex,
  };
}

type DebtRow = {
  amountBase: number;
  taePct: number | null;
  hasMonthlyPaymentInput: boolean;
  monthlyPaymentAmount: number;
};

function buildDebtRows(activeLiabilities: Liability[]): DebtRow[] {
  return activeLiabilities
    .map((liability) => {
      const amountBase = Math.max(0, toNumber(liability.amount_base));
      const taeRaw = liability.annual_interest_tae;
      const taePct = taeRaw == null || String(taeRaw).trim() === '' ? null : toNumber(taeRaw);
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
    .filter((row) => row.amountBase > 0);
}

function computeDebtMetrics(params: {
  debtRows: DebtRow[];
  liabilitiesValue: number;
  annualIncomeEntries: AnnualIncomeLike[];
}) {
  const { debtRows, liabilitiesValue, annualIncomeEntries } = params;
  const topLiabilityShare =
    liabilitiesValue > 0
      ? (debtRows.map((row) => row.amountBase).sort((a, b) => b - a)[0] ?? 0) / liabilitiesValue
      : null;

  const taes = debtRows
    .map((row) => row.taePct)
    .filter((value): value is number => value != null && Number.isFinite(value));
  const maxLiabilityTaePct = taes.length ? Math.max(...taes) : null;

  const weightedLiabilityTaePct = (() => {
    const rows = debtRows.filter((row) => row.taePct != null);
    const denominator = rows.reduce((acc, row) => acc + row.amountBase, 0);
    if (denominator <= 0) return null;
    const numerator = rows.reduce((acc, row) => acc + row.amountBase * (row.taePct ?? 0), 0);
    return numerator / denominator;
  })();

  const liabilitiesWithAmountCount = debtRows.length;
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

  return {
    topLiabilityShare,
    maxLiabilityTaePct,
    weightedLiabilityTaePct,
    hasNoDebtPaymentInputs,
    debtPaymentToIncome,
    highInterestDebtShare: liabilitiesValue > 0 ? highInterestDebtValue / liabilitiesValue : null,
  };
}

function computePhase3ExpenseCoverageMetrics(params: {
  annualExpenseEntries: AnnualExpenseLike[];
  emergencyLiquidAssetsValue: number;
}) {
  const { annualExpenseEntries, emergencyLiquidAssetsValue } = params;
  const structuralOperatingExpense = annualExpenseEntries.reduce((acc, entry) => {
    if (expenseTimeProfile(entry) !== 'structural_recurrent') return acc;
    return expenseCashflowRole(entry) === 'operating' ? acc + Number(entry.amountAnnual ?? 0) : acc;
  }, 0);
  const temporaryCommitmentExpense = annualExpenseEntries.reduce((acc, entry) => {
    if (expenseTimeProfile(entry) !== 'term_recurrent') return acc;
    return expenseCashflowRole(entry) === 'temporary_commitment'
      ? acc + effectiveAnnualAmountForEntry(entry, entry.fiscalYear)
      : acc;
  }, 0);

  const structuralOperatingMonthlyExpense =
    structuralOperatingExpense > 0 ? structuralOperatingExpense / 12 : null;
  const currentCommittedMonthlyExpense =
    structuralOperatingExpense + temporaryCommitmentExpense > 0
      ? (structuralOperatingExpense + temporaryCommitmentExpense) / 12
      : null;

  return {
    emergencyCoverageMonthsBase:
      structuralOperatingMonthlyExpense != null && structuralOperatingMonthlyExpense > 0
        ? emergencyLiquidAssetsValue / structuralOperatingMonthlyExpense
        : null,
    emergencyCoverageMonthsCommitted:
      currentCommittedMonthlyExpense != null && currentCommittedMonthlyExpense > 0
        ? emergencyLiquidAssetsValue / currentCommittedMonthlyExpense
        : null,
  };
}

function computePhase2CashFlowAdjustedScore(input: {
  annualIncomeEntries: AnnualIncomeLike[];
  annualExpenseEntries: AnnualExpenseLike[];
}): number {
  const incomeTimeProfile = (entry: AnnualIncomeLike) =>
    entry.timeProfile ?? (entry.incomeType === 'one_off' ? 'one_off' : 'structural_recurrent');

  const recurrentAnnualIncome = input.annualIncomeEntries.reduce((acc, entry) => {
    const profile = incomeTimeProfile(entry);
    if (profile === 'one_off') return acc;
    return acc + Number(entry.amountAnnual ?? 0);
  }, 0);

  const structuralOperatingExpense = input.annualExpenseEntries.reduce((acc, entry) => {
    if (expenseTimeProfile(entry) !== 'structural_recurrent') return acc;
    return expenseCashflowRole(entry) === 'operating' ? acc + Number(entry.amountAnnual ?? 0) : acc;
  }, 0);

  const temporaryCommitmentExpense = input.annualExpenseEntries.reduce((acc, entry) => {
    if (expenseTimeProfile(entry) !== 'term_recurrent') return acc;
    return expenseCashflowRole(entry) === 'temporary_commitment'
      ? acc + effectiveAnnualAmountForEntry(entry, entry.fiscalYear)
      : acc;
  }, 0);
  const structuralOperatingRatio =
    recurrentAnnualIncome > 0 ? structuralOperatingExpense / recurrentAnnualIncome : null;
  const committedLoadRatio =
    recurrentAnnualIncome > 0
      ? (structuralOperatingExpense + temporaryCommitmentExpense) / recurrentAnnualIncome
      : null;
  const temporaryCommitmentRatio =
    recurrentAnnualIncome > 0 ? temporaryCommitmentExpense / recurrentAnnualIncome : null;
  const oneOffIncome = input.annualIncomeEntries.reduce(
    (acc, entry) =>
      incomeTimeProfile(entry) === 'one_off' ? acc + Number(entry.amountAnnual ?? 0) : acc,
    0,
  );
  const totalAnnualIncome = recurrentAnnualIncome + oneOffIncome;
  const totalAnnualExpense = input.annualExpenseEntries.reduce(
    (acc, entry) => acc + Number(entry.amountAnnual ?? 0),
    0,
  );
  const totalAnnualCashFlowRatio =
    recurrentAnnualIncome > 0
      ? (totalAnnualIncome - totalAnnualExpense) / recurrentAnnualIncome
      : null;
  // Total annual flow (including patrimonial allocation and one-offs) is informative and should
  // modestly affect the score, especially when the year closes with a net deficit.
  const totalAnnualCashFlowScore = linearScoreIncreasing(totalAnnualCashFlowRatio, -0.2, 0.2);

  return weightedScore([
    { score: linearScoreDecreasing(structuralOperatingRatio, 0.5, 1.0), weight: 0.4 },
    { score: linearScoreDecreasing(committedLoadRatio, 0.65, 1.05), weight: 0.35 },
    { score: linearScoreDecreasing(temporaryCommitmentRatio, 0.05, 0.35), weight: 0.15 },
    { score: totalAnnualCashFlowScore, weight: 0.1 },
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

  const {
    illiquidAssetsShare,
    emergencyLiquidAssetsValue,
    emergencyLiquidityToAssets,
    immediateLiquidityShareWithinEmergency,
    topAssetShare,
    diversificationIndex,
  } = computeAssetLiquidityMetrics({
    summary,
    activeAssets,
    assetsValue,
  });
  const unbackedDebtToAssets = assetsValue > 0 ? unbackedDebtValue / assetsValue : null;
  const unbackedDebtToLiabilities =
    liabilitiesValue > 0 ? unbackedDebtValue / liabilitiesValue : null;
  const debtRows = buildDebtRows(activeLiabilities);
  const {
    topLiabilityShare,
    maxLiabilityTaePct,
    weightedLiabilityTaePct,
    hasNoDebtPaymentInputs,
    debtPaymentToIncome,
    highInterestDebtShare,
  } = computeDebtMetrics({
    debtRows,
    liabilitiesValue,
    annualIncomeEntries,
  });

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

  const { emergencyCoverageMonthsBase, emergencyCoverageMonthsCommitted } =
    computePhase3ExpenseCoverageMetrics({
      annualExpenseEntries,
      emergencyLiquidAssetsValue,
    });

  const phase3GlobalScore = weightedScore([
    { score: linearScoreIncreasing(emergencyCoverageMonthsBase, 3, 12), weight: 0.45 },
    { score: linearScoreIncreasing(emergencyCoverageMonthsCommitted, 3, 12), weight: 0.25 },
    { score: linearScoreIncreasing(emergencyLiquidityToAssets, 0.05, 0.3), weight: 0.15 },
    {
      score: linearScoreIncreasing(immediateLiquidityShareWithinEmergency, 0.4, 0.85),
      weight: 0.15,
    },
  ]);

  return {
    phase1GlobalScore,
    phase2GlobalScore,
    phase3GlobalScore,
    phase4GlobalScore,
  };
}
