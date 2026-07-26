import type { LedgerEntry } from '@/domains/accounting';
import type { Asset } from '@/domains/net-worth/models';
import type { AnnualExpenseEntry, AnnualIncomeEntry } from '@/domains/budget/annual-entries';
import {
  normalizeExpenseTaxonomy,
  incomeCategories,
  expenseCategories,
  incomeSubcategories,
  expenseSubcategories,
} from '@/domains/budget/taxonomy';

export {
  incomeCategories,
  incomeSubcategories,
  expenseCategories,
  expenseSubcategories,
} from '@/domains/budget/taxonomy';

// ── Types ──────────────────────────────────────────────────────────────────────

export type MonthlyCloseStepId = 'liq' | 'income' | 'expense' | 'result';

export type ExpenseMonthlySummaryMonth = {
  month: number;
  planned: string;
  executed: string;
  executed_budgeted?: string;
  executed_unbudgeted?: string;
  executed_total?: string;
  pending: string;
  completion_ratio: number;
  checkins_confirmed: number;
  checkins_expected: number;
};

export type ExpenseExecutionBreakdownMonth = {
  month: number;
  planned: string;
  executed_budgeted: string;
  executed_unbudgeted: string;
  executed_total: string;
};

export type ExpenseExecutionBreakdownSubcategory = {
  subcategory: string;
  planned_total: string;
  executed_budgeted_total: string;
  executed_unbudgeted_total: string;
  executed_total: string;
  has_budgeted_line: boolean;
  has_unbudgeted_execution: boolean;
  months: ExpenseExecutionBreakdownMonth[];
};

export type ExpenseExecutionBreakdownCategory = {
  category: string;
  planned_total: string;
  executed_budgeted_total: string;
  executed_unbudgeted_total: string;
  executed_total: string;
  has_budgeted_lines: boolean;
  has_unbudgeted_execution: boolean;
  subcategories: ExpenseExecutionBreakdownSubcategory[];
};

export type ExpenseExecutionBreakdown = {
  categories: ExpenseExecutionBreakdownCategory[];
  executed_budgeted_total: string;
  executed_unbudgeted_total: string;
  executed_total: string;
};

export type ExpenseMonthlySummaryResponse = {
  fiscal_year: number;
  planned_total: string;
  executed_total: string;
  executed_budgeted_total?: string;
  executed_unbudgeted_total?: string;
  pending_total: string;
  variance_total: string;
  months: ExpenseMonthlySummaryMonth[];
  completion_ratio: number;
  months_with_checkins: number;
  has_executed_data: boolean;
  expense_execution_breakdown?: ExpenseExecutionBreakdown;
  income_execution_breakdown?: ExpenseExecutionBreakdown;
};

export type IncomeMonthlySummaryMonth = ExpenseMonthlySummaryMonth;
export type IncomeMonthlySummaryResponse = ExpenseMonthlySummaryResponse;

export type ExpenseMonthlyCheckinApiItem = {
  id: number;
  annual_expense_entry_id: number;
  fiscal_year: number;
  month: number;
  status: 'confirmed' | 'adjusted' | 'skipped' | 'estimated';
  executed_amount: string | null;
  note: string;
  confirmed_at: string | null;
  created_at: string;
  updated_at: string;
};

export type IncomeMonthlyCheckinApiItem = {
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

export type LiquidityMonthlyCheckinApiItem = {
  id: number;
  status: 'confirmed' | 'adjusted';
  closing_balance_real: string;
  note: string;
  confirmed_at: string | null;
  updated_at: string | null;
};

export type LiquidityMonthlySummaryRow = {
  row_type?: 'asset' | 'liability';
  asset_id: number;
  asset_name: string;
  asset_category: string;
  asset_subcategory: string;
  annual_interest_tae?: string | null;
  liability_id?: number;
  liability_name?: string;
  liability_category?: string;
  currency: string;
  planned_closing_balance: string;
  executed_closing_balance: string | null;
  effective_closing_balance: string;
  deviation: string;
  planned_closing_balance_base: string;
  executed_closing_balance_base: string | null;
  effective_closing_balance_base: string;
  deviation_base: string;
  coverage_source?: 'ledger' | 'checkin' | 'liability' | 'none';
  ledger_available?: boolean;
  checkin: LiquidityMonthlyCheckinApiItem | null;
};

export type LiquidityMonthlySummaryResponse = {
  fiscal_year: number;
  month: number;
  base_currency: string;
  planned_total: string;
  executed_total: string;
  deviation_total: string;
  gross_asset_planned_total?: string;
  gross_asset_executed_total?: string;
  liquid_liability_planned_total?: string;
  liquid_liability_executed_total?: string;
  perimeter_internal_expense_total?: string;
  completion_ratio: number;
  checkins_confirmed: number;
  checkins_expected: number;
  rows: LiquidityMonthlySummaryRow[];
};

export type BudgetRow = {
  key: string;
  categoryKey: string;
  categoryLabel: string;
  subcategoryKey: string;
  subcategoryLabel: string;
  plannedAnnual: number;
  itemsCount: number;
  detectedUnbudgeted?: boolean;
  detectedExecutedYtd?: number;
};

export type BudgetGroup = {
  categoryKey: string;
  categoryLabel: string;
  plannedAnnual: number;
  shareOfSection: number;
  rows: BudgetRow[];
};

export type BudgetSectionModel = {
  id: 'income' | 'expense';
  title: string;
  subtitle: string;
  emptyMessage: string;
  toneClass: string;
  totalAnnual: number;
  filterMode: BudgetEntryViewMode;
  categoryCount: number;
  subcategoryCount: number;
  groups: BudgetGroup[];
};

export type BudgetEntryViewMode = 'all' | 'recurrent' | 'one_off';
export type BudgetExecutionTone = 'neutral' | 'good' | 'warn' | 'danger';
export type BudgetExecutionSource =
  'categorized_ledger' | 'legacy_fallback' | 'pending_classification' | 'none';
export type BudgetExecutionOrigin =
  'categorized_ledger' | 'user_override' | 'legacy_checkin' | 'ambiguous_taxonomy' | 'none';
export type BudgetExecutionPreview = {
  ratio: number;
  widthPct: number;
  tone: BudgetExecutionTone;
  overflow: boolean;
};
export type MonthlyCoverageSummary = {
  total: number;
  viaLedger: number;
  viaFallback: number;
  pending: number;
  ratio: number;
};
export type PendingClassificationSummary = {
  amount: number;
  ambiguousRows: number;
};
export type AccountingPostedEntry = LedgerEntry & {
  bookingMonth: number;
  transactionId: number;
  transactionMemberTag: string;
  transactionQuickEntryKind: string;
  assetSubcategory: string;
};

export type MonthlyResultBreakdownSubrow = {
  key: string;
  subcategoryKey: string;
  subcategoryLabel: string;
  lineCount: number;
  plannedTotal: number;
  executedTotal: number;
  deviation: number;
  checkedCount: number;
  completionRatio: number;
  shareOfExecuted: number;
};

export type MonthlyResultBreakdownGroup = {
  key: string;
  categoryKey: string;
  categoryLabel: string;
  lineCount: number;
  plannedTotal: number;
  executedTotal: number;
  deviation: number;
  checkedCount: number;
  completionRatio: number;
  shareOfExecuted: number;
  rows: MonthlyResultBreakdownSubrow[];
};

export type DebtPaymentExpenseTarget = { categoryKey: string; subcategoryKey: string };
export type AccountingExecutionBucketAccumulator = {
  incomeCategorizedByMonthTaxonomy: Map<string, number>;
  expenseCategorizedByMonthTaxonomy: Map<string, number>;
  depositRotationIncomeByMonth: Map<number, number>;
  depositRotationExpenseByMonth: Map<number, number>;
  incomeUnclassifiedTotal: number;
  expenseUnclassifiedTotal: number;
};

export type BudgetActualExecution = {
  planned: number;
  executed: number;
  deviation: number;
  completionRatio: number;
  ratio: number;
  widthPct: number;
  tone: BudgetExecutionTone;
  overflow: boolean;
};

export type IncomeExecutionRow = {
  entry: AnnualIncomeEntry;
  planned: number;
  checkin: IncomeMonthlyCheckinApiItem | null;
  executed: number | null;
  executionOrigin: BudgetExecutionOrigin;
  categorizedLedgerExecuted: number | null;
  executionSource: BudgetExecutionSource;
};

export type ExpenseExecutionRow = {
  entry: AnnualExpenseEntry;
  planned: number;
  checkin: ExpenseMonthlyCheckinApiItem | null;
  executed: number | null;
  executionOrigin: BudgetExecutionOrigin;
  categorizedLedgerExecuted: number | null;
  executionSource: BudgetExecutionSource;
};

export type LiquidityExecutionRow = LiquidityMonthlySummaryRow & {
  planned: number;
  executed: number | null;
};

// ── Constants ─────────────────────────────────────────────────────────────────

export const EXECUTION_TONE_MONEY_TOLERANCE = 0.5;

export const incomeCategoryDisplayOrder = [
  'salary',
  'capital_gains',
  'business',
  'passive_income',
  'transfers_support',
  'public_benefits',
  'other_income',
] as const;

export const incomeCategoryOrderIndex = new Map(
  incomeCategoryDisplayOrder.map((categoryKey, index) => [categoryKey, index] as const),
);

export const expenseCategoryDisplayOrder = [
  'consumption_expenses',
  'real_estate_assets',
  'financial_investments',
  'tangible_assets',
] as const;

export const expenseCategoryOrderIndex = new Map(
  expenseCategoryDisplayOrder.map((categoryKey, index) => [categoryKey, index] as const),
);

export const INVESTMENT_ROTATION_INCOME_CATEGORY = 'capital_gains';
export const INVESTMENT_ROTATION_INCOME_SUBCATEGORY = 'sale_financial_assets';
export const INVESTMENT_ROTATION_EXPENSE_CATEGORY = 'financial_investments';
export const INVESTMENT_ROTATION_DEPOSIT_EXPENSE_SUBCATEGORY = 'deposits_fixed_income';

export const ROTATORY_DEPOSIT_ASSET_SUBCATEGORIES = new Set<Asset['subcategory']>([
  'deposits',
  'short_term_deposit',
]);

export const incomeSubcategoryOrderIndex = new Map(
  incomeSubcategories.map((subcategory, index) => [subcategory.value, index] as const),
);

export const monthLabels = [
  'Ene',
  'Feb',
  'Mar',
  'Abr',
  'May',
  'Jun',
  'Jul',
  'Ago',
  'Sep',
  'Oct',
  'Nov',
  'Dic',
];

export const currentCalendarYear = new Date().getFullYear();

export const incomeCategoryLabels = new Map(
  incomeCategories.map((row) => [row.value, row.label] as const),
);
export const incomeSubcategoryLabels = new Map(
  incomeSubcategories.map((row) => [row.value, row.label] as const),
);
export const expenseCategoryLabels = new Map(
  expenseCategories.map((row) => [row.value, row.label] as const),
);
export const expenseSubcategoryLabels = new Map(
  expenseSubcategories.map((row) => [row.value, row.label] as const),
);

// ── Pure utility functions ────────────────────────────────────────────────────

export function parseSharedOwnerShares(ownerLabel: string): { name: string; share: number }[] {
  const text = ownerLabel.trim();
  if (!text) return [];
  const match = text.match(/^Compartido\s*\((.*)\)$/i);
  if (!match?.[1]) return [];
  return match[1]
    .split(/\s*\/\s*/)
    .map((part) => {
      const piece = part.trim();
      const m = piece.match(/^(.*)\s+(\d+(?:[.,]\d+)?)\s*%$/);
      if (!m?.[1] || !m[2]) return null;
      const name = m[1].trim();
      const share = Number(m[2].replace(',', '.'));
      if (!name || !Number.isFinite(share) || share <= 0) return null;
      return { name, share };
    })
    .filter((row): row is { name: string; share: number } => row != null);
}

export function ownerNamesFromLabel(ownerLabel: string): string[] {
  const text = ownerLabel.trim();
  if (!text) return [];
  const shared = parseSharedOwnerShares(text);
  if (shared.length > 0) return shared.map((row) => row.name);
  return [text];
}

export function allocationFractionForOwnerLabel(ownerLabel: string, selectedOwner: string): number {
  if (selectedOwner === 'all') return 1;
  const text = ownerLabel.trim();
  if (!text) return 0;
  if (text.localeCompare(selectedOwner, 'es', { sensitivity: 'base' }) === 0) return 1;

  const shared = parseSharedOwnerShares(text);
  if (!shared.length) return 0;
  const totalShare = shared.reduce((sum, row) => sum + row.share, 0);
  const matchedShare = shared
    .filter((row) => row.name.localeCompare(selectedOwner, 'es', { sensitivity: 'base' }) === 0)
    .reduce((sum, row) => sum + row.share, 0);
  if (!Number.isFinite(matchedShare) || matchedShare <= 0) return 0;

  // Compatibility: older labels may encode shares as 0-1 fractions instead of 0-100 percentages.
  if (totalShare > 0 && totalShare <= 1.0001) {
    return clamp(matchedShare / totalShare, 0, 1);
  }
  if (totalShare > 0 && totalShare <= 100.0001) {
    return clamp(matchedShare / 100, 0, 1);
  }
  return clamp(matchedShare / totalShare, 0, 1);
}

export function closePopoverFromClick(event: Event): void {
  const target = event.currentTarget as HTMLElement | null;
  const details = target?.closest('details') as HTMLDetailsElement | null;
  if (details) details.open = false;
}

export function sumPlanned<T extends { amountAnnual: number }>(entries: T[]): number {
  return entries.reduce((sum, entry) => sum + entry.amountAnnual, 0);
}

export function toNumberOrZero(raw: unknown): number {
  const n = Number(raw ?? 0);
  return Number.isFinite(n) ? n : 0;
}

export function monthlySummaryExecutedTotal(
  row: ExpenseMonthlySummaryMonth | IncomeMonthlySummaryMonth | null | undefined,
): number | null {
  if (!row) return null;
  return toNumberOrZero(row.executed_total ?? row.executed);
}

export function budgetTaxonomyKey(category: string, subcategory: string): string {
  const normalized = normalizeExpenseTaxonomy(category, subcategory);
  return `${normalized.category}::${normalized.subcategory}`;
}

export function budgetMonthTaxonomyKey(
  month: number,
  category: string,
  subcategory: string,
): string {
  return `${month}::${budgetTaxonomyKey(category, subcategory)}`;
}

export function budgetMonthEntryKey(month: number, entryId: number): string {
  return `${month}::${entryId}`;
}

export function parseBudgetTaxonomyKey(rowKey: string): {
  categoryKey: string;
  subcategoryKey: string;
} {
  const [categoryKey = '', subcategoryKey = ''] = rowKey.split('::');
  return { categoryKey, subcategoryKey };
}

export function normalizedBudgetTaxonomy(
  category: string,
  subcategory: string,
): { categoryKey: string; subcategoryKey: string } {
  const normalized = normalizeExpenseTaxonomy(category, subcategory);
  return {
    categoryKey: normalized.category,
    subcategoryKey: normalized.subcategory,
  };
}

export function bookingMonthFromDate(value: string): number {
  const month = Number.parseInt(value.slice(5, 7), 10);
  return Number.isFinite(month) && month >= 1 && month <= 12 ? month : 0;
}

export function resolveLedgerEntryFlowFamily(entry: LedgerEntry): '' | 'income' | 'expense' {
  if (entry.flow_family === 'income' || entry.flow_family === 'expense') return entry.flow_family;
  return '';
}

export function isRotatoryDepositAssetSubcategory(subcategory: string | null | undefined): boolean {
  return ROTATORY_DEPOSIT_ASSET_SUBCATEGORIES.has((subcategory ?? '') as Asset['subcategory']);
}

export function isPositiveExecutionLedgerEntry(
  entry: LedgerEntry,
  flowFamily: 'income' | 'expense',
): boolean {
  if (
    flowFamily === 'expense' &&
    entry.side === 'credit' &&
    entry.flow_family === 'expense' &&
    (entry as AccountingPostedEntry).transactionQuickEntryKind === 'investment' &&
    entry.asset_id == null
  ) {
    return true;
  }
  return (
    (flowFamily === 'income' && entry.side === 'credit') ||
    (flowFamily === 'expense' && entry.side === 'debit')
  );
}

export function addMapAmount<K>(map: Map<K, number>, key: K, amount: number): void {
  map.set(key, (map.get(key) ?? 0) + amount);
}

export function buildDebtPaymentExpenseTargetByTransactionId(
  entries: AccountingPostedEntry[],
): Map<number, DebtPaymentExpenseTarget> {
  const targets = new Map<number, DebtPaymentExpenseTarget>();
  for (const entry of entries) {
    if (entry.transactionQuickEntryKind !== 'debt_payment') continue;
    if (entry.liability_id == null) continue;
    if (entry.side !== 'debit') continue;
    if (resolveLedgerEntryFlowFamily(entry) !== 'expense') continue;
    if (!entry.category_key || !entry.subcategory_key) continue;
    targets.set(entry.transactionId, {
      categoryKey: entry.category_key,
      subcategoryKey: entry.subcategory_key,
    });
  }
  return targets;
}

export function resolveDebtPaymentSiblingExpenseTarget(
  entry: AccountingPostedEntry,
  flowFamily: 'income' | 'expense',
  targets: Map<number, DebtPaymentExpenseTarget>,
): DebtPaymentExpenseTarget | undefined {
  if (flowFamily !== 'expense') return undefined;
  if (entry.transactionQuickEntryKind !== 'debt_payment') return undefined;
  if (entry.liability_id != null) return undefined;
  return targets.get(entry.transactionId);
}

export function collectDebtPaymentSiblingExpenseExecution(
  entry: AccountingPostedEntry,
  flowFamily: 'income' | 'expense',
  amount: number,
  bookingMonth: number,
  targets: Map<number, DebtPaymentExpenseTarget>,
  buckets: AccountingExecutionBucketAccumulator,
): boolean {
  const target = resolveDebtPaymentSiblingExpenseTarget(entry, flowFamily, targets);
  if (!target) return false;
  const key = budgetMonthTaxonomyKey(bookingMonth, target.categoryKey, target.subcategoryKey);
  addMapAmount(buckets.expenseCategorizedByMonthTaxonomy, key, amount);
  return true;
}

export function collectTaxonomyExecution(
  entry: AccountingPostedEntry,
  flowFamily: 'income' | 'expense',
  amount: number,
  bookingMonth: number,
  buckets: AccountingExecutionBucketAccumulator,
): boolean {
  if (!entry.category_key || !entry.subcategory_key) return false;
  const key = budgetMonthTaxonomyKey(bookingMonth, entry.category_key, entry.subcategory_key);
  const targetMap =
    flowFamily === 'income'
      ? buckets.incomeCategorizedByMonthTaxonomy
      : buckets.expenseCategorizedByMonthTaxonomy;
  addMapAmount(targetMap, key, amount);
  return true;
}

export function collectDepositRotationMonthBuckets(
  entry: AccountingPostedEntry,
  flowFamily: 'income' | 'expense',
  bookingMonth: number,
  amount: number,
  incomeBuckets: Map<number, number>,
  expenseBuckets: Map<number, number>,
): void {
  const isDepositRotationIncome =
    flowFamily === 'income' &&
    entry.category_key === INVESTMENT_ROTATION_INCOME_CATEGORY &&
    entry.subcategory_key === INVESTMENT_ROTATION_INCOME_SUBCATEGORY &&
    isRotatoryDepositAssetSubcategory(entry.assetSubcategory);
  if (isDepositRotationIncome) {
    incomeBuckets.set(bookingMonth, (incomeBuckets.get(bookingMonth) ?? 0) + amount);
    return;
  }

  const isDepositRotationExpense =
    flowFamily === 'expense' &&
    entry.category_key === INVESTMENT_ROTATION_EXPENSE_CATEGORY &&
    (entry.subcategory_key === INVESTMENT_ROTATION_DEPOSIT_EXPENSE_SUBCATEGORY ||
      isRotatoryDepositAssetSubcategory(entry.assetSubcategory));
  if (isDepositRotationExpense) {
    expenseBuckets.set(bookingMonth, (expenseBuckets.get(bookingMonth) ?? 0) + amount);
  }
}

export function collectAccountingExecutionEntry(
  entry: AccountingPostedEntry,
  targets: Map<number, DebtPaymentExpenseTarget>,
  buckets: AccountingExecutionBucketAccumulator,
  ownershipFilter: string,
): void {
  if (entry.transactionQuickEntryKind === 'revaluation') return;
  const flowFamily = resolveLedgerEntryFlowFamily(entry);
  if (!flowFamily || !isPositiveExecutionLedgerEntry(entry, flowFamily)) return;

  const ownershipFraction = allocationFractionForOwnerLabel(
    entry.transactionMemberTag ?? '',
    ownershipFilter,
  );
  if (ownershipFraction <= 0) return;
  const amount = toNumberOrZero(entry.amount_base ?? entry.amount) * ownershipFraction;
  const bookingMonth = entry.bookingMonth;
  if (!bookingMonth) return;

  collectDepositRotationMonthBuckets(
    entry,
    flowFamily,
    bookingMonth,
    amount,
    buckets.depositRotationIncomeByMonth,
    buckets.depositRotationExpenseByMonth,
  );
  if (
    collectDebtPaymentSiblingExpenseExecution(
      entry,
      flowFamily,
      amount,
      bookingMonth,
      targets,
      buckets,
    )
  ) {
    return;
  }
  if (collectTaxonomyExecution(entry, flowFamily, amount, bookingMonth, buckets)) return;
  if (flowFamily === 'income') buckets.incomeUnclassifiedTotal += amount;
  if (flowFamily === 'expense') buckets.expenseUnclassifiedTotal += amount;
}

export function monthlyPlannedAmountForExpenseEntry(
  entry: AnnualExpenseEntry,
  month: number,
): number {
  if (entry.expenseType === 'one_off') {
    return entry.targetMonth === month ? toNumberOrZero(entry.amountAnnual) : 0;
  }
  if (
    entry.timeProfile === 'term_recurrent' &&
    (entry.termEndYear == null || entry.termEndYear === entry.fiscalYear)
  ) {
    const endMonth = Math.min(12, Math.max(1, Number(entry.termEndMonth ?? 12)));
    if (month > endMonth) return 0;
    return toNumberOrZero(entry.amountAnnual) / endMonth;
  }
  return toNumberOrZero(entry.amountAnnual) / 12;
}

export function monthlyPlannedAmountForIncomeEntry(
  entry: AnnualIncomeEntry,
  month: number,
): number {
  if (entry.targetMonth != null) {
    return entry.targetMonth === month ? toNumberOrZero(entry.amountAnnual) : 0;
  }
  return toNumberOrZero(entry.amountAnnual) / 12;
}

export function buildMonthlyResultBreakdown<
  TEntry extends { category: string; subcategory: string },
  TRow extends {
    entry: TEntry;
    planned: number;
    checkin: { status: 'confirmed' | 'adjusted' | 'skipped' | 'estimated' } | null;
    executed: number | null;
    executionSource: BudgetExecutionSource;
  },
>(
  rows: TRow[],
  categoryLabels: Map<string, string>,
  subcategoryLabels: Map<string, string>,
  executedSectionTotal: number,
): MonthlyResultBreakdownGroup[] {
  const groups = new Map<
    string,
    {
      key: string;
      categoryKey: string;
      categoryLabel: string;
      lineCount: number;
      plannedTotal: number;
      executedTotal: number;
      checkedCount: number;
      rows: Map<
        string,
        {
          key: string;
          subcategoryKey: string;
          subcategoryLabel: string;
          lineCount: number;
          plannedTotal: number;
          executedTotal: number;
          checkedCount: number;
        }
      >;
    }
  >();

  for (const row of rows) {
    const categoryKey = row.entry.category;
    const subcategoryKey = row.entry.subcategory;
    const planned = Number.isFinite(row.planned) ? row.planned : 0;
    const executed = row.executed != null && Number.isFinite(row.executed) ? row.executed : 0;
    const isChecked = row.executionSource !== 'none';

    let group = groups.get(categoryKey);
    if (!group) {
      group = {
        key: categoryKey,
        categoryKey,
        categoryLabel: categoryLabels.get(categoryKey) ?? categoryKey,
        lineCount: 0,
        plannedTotal: 0,
        executedTotal: 0,
        checkedCount: 0,
        rows: new Map(),
      };
      groups.set(categoryKey, group);
    }

    group.lineCount += 1;
    group.plannedTotal += planned;
    group.executedTotal += executed;
    if (isChecked) group.checkedCount += 1;

    let subrow = group.rows.get(subcategoryKey);
    if (!subrow) {
      subrow = {
        key: `${categoryKey}::${subcategoryKey}`,
        subcategoryKey,
        subcategoryLabel: subcategoryLabels.get(subcategoryKey) ?? subcategoryKey,
        lineCount: 0,
        plannedTotal: 0,
        executedTotal: 0,
        checkedCount: 0,
      };
      group.rows.set(subcategoryKey, subrow);
    }

    subrow.lineCount += 1;
    subrow.plannedTotal += planned;
    subrow.executedTotal += executed;
    if (isChecked) subrow.checkedCount += 1;
  }

  return Array.from(groups.values())
    .map((group) => {
      const rowsSorted = Array.from(group.rows.values())
        .map((subrow) => ({
          ...subrow,
          deviation: subrow.executedTotal - subrow.plannedTotal,
          completionRatio: subrow.lineCount ? subrow.checkedCount / subrow.lineCount : 0,
          shareOfExecuted:
            executedSectionTotal > 0 ? subrow.executedTotal / executedSectionTotal : 0,
        }))
        .sort(
          (a, b) =>
            b.executedTotal - a.executedTotal ||
            b.plannedTotal - a.plannedTotal ||
            a.subcategoryLabel.localeCompare(b.subcategoryLabel, 'es'),
        );

      return {
        key: group.key,
        categoryKey: group.categoryKey,
        categoryLabel: group.categoryLabel,
        lineCount: group.lineCount,
        plannedTotal: group.plannedTotal,
        executedTotal: group.executedTotal,
        deviation: group.executedTotal - group.plannedTotal,
        checkedCount: group.checkedCount,
        completionRatio: group.lineCount ? group.checkedCount / group.lineCount : 0,
        shareOfExecuted: executedSectionTotal > 0 ? group.executedTotal / executedSectionTotal : 0,
        rows: rowsSorted,
      } satisfies MonthlyResultBreakdownGroup;
    })
    .sort(
      (a, b) =>
        b.executedTotal - a.executedTotal ||
        b.plannedTotal - a.plannedTotal ||
        a.categoryLabel.localeCompare(b.categoryLabel, 'es'),
    );
}

export function buildActualExecution(
  sectionId: BudgetSectionModel['id'],
  planned: number,
  executed: number,
  completionRatio: number,
): BudgetActualExecution | null {
  if (!Number.isFinite(planned) || planned <= 0) {
    if (!Number.isFinite(executed) || executed <= 0) {
      return {
        planned: 0,
        executed: 0,
        deviation: 0,
        completionRatio,
        ratio: 0,
        widthPct: 0,
        tone: 'neutral',
        overflow: false,
      };
    }
    if (Number.isFinite(executed) && executed > 0) {
      const tone: BudgetExecutionTone = sectionId === 'income' ? 'neutral' : 'warn';
      return {
        planned: 0,
        executed,
        deviation: executed,
        completionRatio,
        ratio: 1,
        widthPct: 100,
        tone,
        overflow: false,
      };
    }
    return null;
  }
  const deviation = executed - planned;
  const ratio = executed / planned;
  const normalizedRatio = Math.abs(deviation) <= EXECUTION_TONE_MONEY_TOLERANCE ? 1 : ratio;
  return {
    planned,
    executed,
    deviation,
    completionRatio,
    ratio,
    widthPct: ratio <= 0 ? 0 : clamp(ratio * 100, 4, 100),
    tone: executionToneFor(sectionId, normalizedRatio),
    overflow: ratio > 1,
  };
}

export function isLockedExecutionRow(row: { executionOrigin: BudgetExecutionOrigin }): boolean {
  return row.executionOrigin === 'categorized_ledger';
}

export function resolveCoverageMode(summary: MonthlyCoverageSummary): string {
  if (summary.total === 0 || summary.viaLedger + summary.viaFallback === 0) return 'none';
  if (summary.pending > 0) return 'partial';
  if (summary.viaLedger > 0 && summary.viaFallback > 0) return 'mixed';
  if (summary.viaLedger > 0) return 'ledger';
  return 'fallback';
}

export function coverageBadgeLabel(summary: MonthlyCoverageSummary): string {
  const mode = resolveCoverageMode(summary);
  if (mode === 'ledger' || mode === 'fallback' || mode === 'mixed') return 'Completo';
  if (mode === 'partial') return 'Parcial';
  return 'Pendiente';
}

export function coverageDetail(summary: MonthlyCoverageSummary): string {
  const mode = resolveCoverageMode(summary);
  if (mode === 'ledger' || mode === 'fallback' || mode === 'mixed') {
    return 'Todas las líneas del mes tienen importe registrado.';
  }
  if (mode === 'partial') {
    return 'Ya hay importes registrados; revisa solo las líneas pendientes.';
  }
  return 'Todavía no hay importes registrados para este mes.';
}

export function executionSourceLabel(origin: BudgetExecutionOrigin): string {
  if (origin === 'categorized_ledger') return 'Movimientos';
  if (origin === 'legacy_checkin') return 'Manual';
  if (origin === 'user_override') return 'Ajuste manual';
  if (origin === 'ambiguous_taxonomy') return 'Pendiente clasificar';
  return '';
}

export function formatMoney(value: number, decimals = 2): string {
  return new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    useGrouping: true,
  }).format(Number.isFinite(value) ? value : 0);
}

export function formatSignedMoney(value: number, decimals = 2): string {
  return `${value > 0 ? '+' : ''}${formatMoney(value, decimals)}`;
}

export function formatPercent(value: number | null, decimals = 0): string {
  if (value == null || !Number.isFinite(value)) return '-';
  return new Intl.NumberFormat('es-ES', {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

export function formatCompactMoney(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${formatMoney(value / 1_000_000, 1)} M`;
  if (abs >= 1_000) return `${formatMoney(value / 1_000, 1)} k`;
  return formatMoney(value, 0);
}

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}

export function hashToUnitInterval(input: string): number {
  let h = 0;
  for (let i = 0; i < input.length; i++) {
    h = (Math.imul(31, h) + input.charCodeAt(i)) | 0;
  }
  return (h >>> 0) / 4_294_967_295;
}

export function executionToneFor(
  sectionId: BudgetSectionModel['id'],
  ratio: number,
): BudgetExecutionTone {
  if (sectionId === 'income') {
    if (ratio >= 1) return 'good';
    if (ratio >= 0.8) return 'neutral';
    if (ratio >= 0.5) return 'warn';
    return 'danger';
  }
  if (ratio <= 1) return 'good';
  if (ratio <= 1.1) return 'neutral';
  if (ratio <= 1.25) return 'warn';
  return 'danger';
}

export function mockExecutionRatio(sectionId: BudgetSectionModel['id'], seedKey: string): number {
  const u = hashToUnitInterval(seedKey);
  if (sectionId === 'income') {
    if (u < 0.15) return 0.4 + u * 2;
    if (u < 0.4) return 0.75 + (u - 0.15) * 1.6;
    return 0.9 + (u - 0.4) * 0.25;
  }
  if (u < 0.15) return 0.5 + u * 2;
  if (u < 0.35) return 0.8 + (u - 0.15) * 1.5;
  if (u < 0.7) return 0.95 + (u - 0.35) * 0.2;
  return 1.02 + (u - 0.7) * 0.5;
}

export function executionPreview(
  sectionId: BudgetSectionModel['id'],
  seedKey: string,
): BudgetExecutionPreview {
  const ratio = mockExecutionRatio(sectionId, seedKey);
  return {
    ratio,
    widthPct: ratio <= 0 ? 0 : clamp(ratio * 100, 4, 100),
    tone: executionToneFor(sectionId, ratio),
    overflow: ratio > 1,
  };
}

export function aggregateBudgetRows<
  T extends { category: string; subcategory: string; amountAnnual: number },
>(
  entries: T[],
  categoryLabels: Map<string, string>,
  subcategoryLabels: Map<string, string>,
): BudgetGroup[] {
  const bucket = new Map<string, BudgetRow>();

  for (const entry of entries) {
    const amount = Number(entry.amountAnnual ?? 0);
    if (!Number.isFinite(amount) || amount <= 0) continue;
    const normalized = normalizedBudgetTaxonomy(entry.category, entry.subcategory);
    const key = `${normalized.categoryKey}::${normalized.subcategoryKey}`;
    const prev = bucket.get(key);
    if (prev) {
      prev.plannedAnnual += amount;
      prev.itemsCount += 1;
      continue;
    }
    bucket.set(key, {
      key,
      categoryKey: normalized.categoryKey,
      categoryLabel: categoryLabels.get(normalized.categoryKey) ?? normalized.categoryKey,
      subcategoryKey: normalized.subcategoryKey,
      subcategoryLabel:
        subcategoryLabels.get(normalized.subcategoryKey) ?? normalized.subcategoryKey,
      plannedAnnual: amount,
      itemsCount: 1,
    });
  }

  const rows = Array.from(bucket.values()).sort((a, b) => {
    if (b.plannedAnnual !== a.plannedAnnual) return b.plannedAnnual - a.plannedAnnual;
    return a.subcategoryLabel.localeCompare(b.subcategoryLabel, 'es');
  });

  const sectionTotal = rows.reduce((sum, row) => sum + row.plannedAnnual, 0);
  const byCategory = new Map<string, BudgetGroup>();
  for (const row of rows) {
    const group = byCategory.get(row.categoryKey);
    if (group) {
      group.plannedAnnual += row.plannedAnnual;
      group.rows.push(row);
      continue;
    }
    byCategory.set(row.categoryKey, {
      categoryKey: row.categoryKey,
      categoryLabel: row.categoryLabel,
      plannedAnnual: row.plannedAnnual,
      shareOfSection: 0,
      rows: [row],
    });
  }

  return Array.from(byCategory.values())
    .map((group) => ({
      ...group,
      rows: group.rows.sort((a, b) => b.plannedAnnual - a.plannedAnnual),
      shareOfSection: sectionTotal > 0 ? group.plannedAnnual / sectionTotal : 0,
    }))
    .sort((a, b) => b.plannedAnnual - a.plannedAnnual);
}

export function viewModeLabel(mode: BudgetEntryViewMode): string {
  if (mode === 'recurrent') return 'Solo recurrentes';
  if (mode === 'one_off') return 'Solo puntuales';
  return 'Todos';
}

export function incomeCategorySortIndex(categoryKey: string): number {
  return (
    incomeCategoryOrderIndex.get(categoryKey as (typeof incomeCategoryDisplayOrder)[number]) ?? 999
  );
}

export function incomeSubcategorySortIndex(subcategoryKey: string): number {
  return incomeSubcategoryOrderIndex.get(subcategoryKey) ?? 999;
}

export function expenseCategorySortIndex(categoryKey: string): number {
  return (
    expenseCategoryOrderIndex.get(categoryKey as (typeof expenseCategoryDisplayOrder)[number]) ??
    999
  );
}

export function parseDecimalInput(raw: string): number | null {
  const normalized = raw.trim().replace(',', '.');
  if (!normalized) return null;
  const value = Number(normalized);
  if (!Number.isFinite(value) || value < 0) return null;
  return value;
}

export function checkinStatusLabel(
  status: ExpenseMonthlyCheckinApiItem['status'] | IncomeMonthlyCheckinApiItem['status'],
): string {
  if (status === 'confirmed') return 'Confirmado';
  if (status === 'adjusted') return 'Ajustado';
  if (status === 'estimated') return 'Estimado';
  return 'No ocurrió';
}

export function incomeEntryMonthKey(entryId: number, month: number): string {
  return `${entryId}:${month}`;
}

export function expenseEntryMonthKey(entryId: number, month: number): string {
  return `${entryId}:${month}`;
}

export function cleanedExpenseCheckinName(name: string): string {
  return name.replace(/^Compromiso pasivo:\s*/i, '').trim();
}

export function shortExpenseCategoryLabel(category: string): string {
  if (category === 'real_estate_assets') return 'Activos inmobiliarios';
  if (category === 'tangible_assets') return 'Activos mobiliarios';
  if (category === 'consumption_expenses') return 'Gastos';
  if (category === 'financial_investments') return 'Inversion financiera';
  if (category === 'savings_allocation') return 'Ahorro';
  return (
    expenseCategoryLabels.get(category as (typeof expenseCategories)[number]['value']) ?? category
  );
}

export function expenseCheckinCategorySortWeight(category: string): number {
  if (category === 'real_estate_assets') return 0;
  if (category === 'tangible_assets') return 1;
  if (category === 'financial_investments') return 2;
  if (category === 'consumption_expenses') return 3;
  if (category === 'savings_allocation') return 4;
  return 99;
}

export function amountsEqualCents(left: number, right: number): boolean {
  return Math.round(left * 100) === Math.round(right * 100);
}

export function shortLiquiditySubcategoryLabel(subcategory: string): string {
  if (subcategory === 'credit_card') return 'Tarjeta de crédito';
  if (subcategory === 'bank_account') return 'Cuenta bancaria';
  if (subcategory === 'short_term_deposit') return 'Deposito corto plazo';
  if (subcategory === 'wallet') return 'Monedero';
  if (subcategory === 'crypto_spot_earn') return 'Spot/Earn';
  return 'Liquidez';
}

export function liquidityCheckinRowSummary(row: LiquidityExecutionRow): string {
  if (row.row_type === 'liability') {
    return `${shortLiquiditySubcategoryLabel(row.liability_category ?? row.asset_subcategory)} - ${
      row.liability_name ?? row.asset_name
    }`;
  }
  return `${shortLiquiditySubcategoryLabel(row.asset_subcategory)} - ${row.asset_name}`;
}

export function suggestedLiquidityClosingBalanceForRow(row: LiquidityExecutionRow): string {
  if (row.executed != null) return row.executed.toFixed(2);
  return row.planned.toFixed(2);
}

export function suggestedIncomeExecutedAmountForRow(row: IncomeExecutionRow): string {
  if (row.checkin?.status === 'skipped') return '0.00';
  if (row.executed != null) return row.executed.toFixed(2);
  return row.planned.toFixed(2);
}

export function suggestedExecutedAmountForRow(row: ExpenseExecutionRow): string {
  if (row.checkin?.status === 'skipped') return '0.00';
  if (row.executed != null) return row.executed.toFixed(2);
  return row.planned.toFixed(2);
}

export function incomeCheckinRowSummary(row: IncomeExecutionRow): string {
  const subcategory = incomeSubcategoryLabels.get(row.entry.subcategory) ?? row.entry.subcategory;
  return `${subcategory} - ${row.entry.name}`;
}

export function expenseCheckinRowSummary(row: ExpenseExecutionRow): string {
  const name = cleanedExpenseCheckinName(row.entry.name);
  const subcategory = expenseSubcategoryLabels.get(row.entry.subcategory) ?? row.entry.subcategory;
  return `${subcategory} - ${name}`;
}
