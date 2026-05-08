import { computed, ref, watch, type Ref } from 'vue';
import {
  budgetApi,
  toBudgetErrorMessage,
  getMonthlyClose,
  patchMonthlyClose,
  finalizeMonthlyClose,
  reopenMonthlyClose,
  lockMonthlyClose,
  type MonthlyCloseStateResponse,
} from '@/domains/budget';
import {
  coreAccountingApi,
  type BudgetDerivedSuggestions,
  type BudgetSuggestionSubcategoryRow,
  type LedgerEntry,
  type LedgerTransaction,
  type MonthlyAccountingSummary,
} from '@/domains/accounting';
import { coreNetWorthApi } from '@/domains/net-worth/api';
import type { Asset } from '@/domains/net-worth/models';
import {
  expenseCategories,
  normalizeExpenseTaxonomy,
  expenseSubcategories,
  effectiveAnnualAmountForEntry,
  incomeCategories,
  incomeSubcategories,
  useAnnualExpenseStore,
  useAnnualIncomeStore,
} from '@/domains/data-input';

export type BudgetDashboardMode = 'budget' | 'monthly-close';
const EXECUTION_TONE_MONEY_TOLERANCE = 0.5;
type MonthlyCloseStepId = 'liq' | 'income' | 'expense' | 'result';
export function useBudgetDashboardPage(mode: Ref<BudgetDashboardMode>) {
  const incomeCategoryDisplayOrder = [
    'salary',
    'capital_gains',
    'business',
    'passive_income',
    'transfers_support',
    'public_benefits',
    'other_income',
  ] as const;
  const incomeCategoryOrderIndex = new Map(
    incomeCategoryDisplayOrder.map((categoryKey, index) => [categoryKey, index] as const),
  );
  const expenseCategoryDisplayOrder = [
    'consumption_expenses',
    'real_estate_assets',
    'financial_investments',
    'tangible_assets',
  ] as const;
  const expenseCategoryOrderIndex = new Map(
    expenseCategoryDisplayOrder.map((categoryKey, index) => [categoryKey, index] as const),
  );
  const INVESTMENT_ROTATION_INCOME_CATEGORY = 'capital_gains';
  const INVESTMENT_ROTATION_INCOME_SUBCATEGORY = 'sale_financial_assets';
  const INVESTMENT_ROTATION_EXPENSE_CATEGORY = 'financial_investments';
  const INVESTMENT_ROTATION_DEPOSIT_EXPENSE_SUBCATEGORY = 'deposits_fixed_income';
  const ROTATORY_DEPOSIT_ASSET_SUBCATEGORIES = new Set<Asset['subcategory']>([
    'deposits',
    'short_term_deposit',
  ]);
  const incomeSubcategoryOrderIndex = new Map(
    incomeSubcategories.map((subcategory, index) => [subcategory.value, index] as const),
  );

  type ExpenseMonthlySummaryMonth = {
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

  type ExpenseExecutionBreakdownMonth = {
    month: number;
    planned: string;
    executed_budgeted: string;
    executed_unbudgeted: string;
    executed_total: string;
  };

  type ExpenseExecutionBreakdownSubcategory = {
    subcategory: string;
    planned_total: string;
    executed_budgeted_total: string;
    executed_unbudgeted_total: string;
    executed_total: string;
    has_budgeted_line: boolean;
    has_unbudgeted_execution: boolean;
    months: ExpenseExecutionBreakdownMonth[];
  };

  type ExpenseExecutionBreakdownCategory = {
    category: string;
    planned_total: string;
    executed_budgeted_total: string;
    executed_unbudgeted_total: string;
    executed_total: string;
    has_budgeted_lines: boolean;
    has_unbudgeted_execution: boolean;
    subcategories: ExpenseExecutionBreakdownSubcategory[];
  };

  type ExpenseExecutionBreakdown = {
    categories: ExpenseExecutionBreakdownCategory[];
    executed_budgeted_total: string;
    executed_unbudgeted_total: string;
    executed_total: string;
  };

  type ExpenseMonthlySummaryResponse = {
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

  type IncomeMonthlySummaryMonth = ExpenseMonthlySummaryMonth;
  type IncomeMonthlySummaryResponse = ExpenseMonthlySummaryResponse;

  type ExpenseMonthlyCheckinApiItem = {
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

  type IncomeMonthlyCheckinApiItem = {
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

  type LiquidityMonthlyCheckinApiItem = {
    id: number;
    status: 'confirmed' | 'adjusted';
    closing_balance_real: string;
    note: string;
    confirmed_at: string | null;
    updated_at: string | null;
  };

  type LiquidityMonthlySummaryRow = {
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

  type LiquidityMonthlySummaryResponse = {
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

  type BudgetRow = {
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

  type BudgetGroup = {
    categoryKey: string;
    categoryLabel: string;
    plannedAnnual: number;
    shareOfSection: number;
    rows: BudgetRow[];
  };

  type BudgetSectionModel = {
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

  type BudgetEntryViewMode = 'all' | 'recurrent' | 'one_off';
  type BudgetExecutionTone = 'neutral' | 'good' | 'warn' | 'danger';
  type BudgetExecutionSource =
    | 'categorized_ledger'
    | 'legacy_fallback'
    | 'pending_classification'
    | 'none';
  type BudgetExecutionOrigin =
    | 'categorized_ledger'
    | 'legacy_ledger'
    | 'legacy_checkin'
    | 'ambiguous_taxonomy'
    | 'none';
  type BudgetExecutionPreview = {
    ratio: number;
    widthPct: number;
    tone: BudgetExecutionTone;
    overflow: boolean;
  };
  type MonthlyCoverageSummary = {
    total: number;
    viaLedger: number;
    viaFallback: number;
    pending: number;
    ratio: number;
  };
  type PendingClassificationSummary = {
    amount: number;
    ambiguousRows: number;
  };
  type AccountingPostedEntry = LedgerEntry & {
    bookingMonth: number;
    transactionId: number;
    transactionMemberTag: string;
    transactionQuickEntryKind: string;
    assetSubcategory: string;
  };

  type MonthlyResultBreakdownSubrow = {
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

  type MonthlyResultBreakdownGroup = {
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

  const incomeStore = useAnnualIncomeStore('saas');
  const expenseStore = useAnnualExpenseStore('saas');

  const fiscalYear = ref(new Date().getFullYear());
  const ownershipFilter = ref<string>('all');
  const incomeViewMode = ref<BudgetEntryViewMode>('all');
  const expenseViewMode = ref<BudgetEntryViewMode>('all');
  const incomeDetailsExpanded = ref(false);
  const expenseDetailsExpanded = ref(false);
  const budgetDetailMonth = ref(new Date().getMonth() + 1);
  const currentCalendarYear = new Date().getFullYear();
  const monthLabels = [
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
  const selectedExecutionMonth = ref(new Date().getMonth() + 1);
  const expenseMonthlySummary = ref<ExpenseMonthlySummaryResponse | null>(null);
  const incomeMonthlySummary = ref<IncomeMonthlySummaryResponse | null>(null);
  const expenseCheckinsByEntryId = ref<Record<number, ExpenseMonthlyCheckinApiItem>>({});
  const expenseCheckinsByEntryMonth = ref<Record<string, ExpenseMonthlyCheckinApiItem>>({});
  const expenseExecutionLoading = ref(false);
  const expenseExecutionBusyEntryId = ref<number | null>(null);
  const expenseExecutionError = ref<string | null>(null);
  const expenseAdjustAmounts = ref<Record<number, string>>({});
  const incomeCheckinsByEntryId = ref<Record<number, IncomeMonthlyCheckinApiItem>>({});
  const incomeCheckinsByEntryMonth = ref<Record<string, IncomeMonthlyCheckinApiItem>>({});
  const incomeExecutionLoading = ref(false);
  const incomeExecutionBusyEntryId = ref<number | null>(null);
  const incomeExecutionError = ref<string | null>(null);
  const incomeAdjustAmounts = ref<Record<number, string>>({});
  const unlockedIncomeGroupKeys = ref<Set<string>>(new Set());
  const unlockedExpenseGroupKeys = ref<Set<string>>(new Set());
  const accountingExecutionLoading = ref(false);
  const accountingExecutionError = ref<string | null>(null);
  const accountingMonthlySummary = ref<MonthlyAccountingSummary | null>(null);
  const accountingPostedEntries = ref<AccountingPostedEntry[]>([]);
  const budgetSuggestionsLoading = ref(false);
  const budgetSuggestionsError = ref<string | null>(null);
  const budgetSuggestions = ref<BudgetDerivedSuggestions | null>(null);
  const liquidityMonthlySummary = ref<LiquidityMonthlySummaryResponse | null>(null);
  const liquidityExecutionLoading = ref(false);
  const liquidityExecutionBusyAssetId = ref<number | null>(null);
  const liquidityExecutionError = ref<string | null>(null);
  const liquidityAdjustAmounts = ref<Record<number, string>>({});
  const unlockedLiquidityLedgerAssetIds = ref<Set<number>>(new Set());
  const activeMonthlyCloseStep = ref<MonthlyCloseStepId>('liq');
  const monthlyCloseData = ref<MonthlyCloseStateResponse | null>(null);
  const monthlyCloseLoading = ref(false);
  const monthlyCloseError = ref<string | null>(null);
  const monthlyCloseActionBusy = ref(false);

  const incomeCategoryLabels = new Map(
    incomeCategories.map((row) => [row.value, row.label] as const),
  );
  const incomeSubcategoryLabels = new Map(
    incomeSubcategories.map((row) => [row.value, row.label] as const),
  );
  const expenseCategoryLabels = new Map(
    expenseCategories.map((row) => [row.value, row.label] as const),
  );
  const expenseSubcategoryLabels = new Map(
    expenseSubcategories.map((row) => [row.value, row.label] as const),
  );
  const isMonthlyCloseView = computed(() => mode.value === 'monthly-close');
  const monthlyCloseFlowSteps = computed<
    { id: MonthlyCloseStepId; label: string; subtitle: string }[]
  >(() => [
    { id: 'liq', label: 'Perimetro', subtitle: 'Caja + activos incluidos - tarjetas' },
    { id: 'income', label: 'Ingresos', subtitle: 'Confirmar / ajustar' },
    { id: 'expense', label: 'Gastos', subtitle: 'Confirmar / ajustar' },
    { id: 'result', label: 'Resultado', subtitle: 'Residual y KPIs' },
  ]);
  const monthlyCloseStepIds = computed(() => monthlyCloseFlowSteps.value.map((s) => s.id));
  const activeMonthlyCloseStepIndex = computed(() =>
    monthlyCloseStepIds.value.findIndex((id) => id === activeMonthlyCloseStep.value),
  );
  const previousMonthlyCloseStep = computed<MonthlyCloseStepId | null>(() => {
    const idx = activeMonthlyCloseStepIndex.value;
    if (idx <= 0) return null;
    return monthlyCloseStepIds.value[idx - 1] ?? null;
  });
  const nextMonthlyCloseStep = computed<MonthlyCloseStepId | null>(() => {
    const idx = activeMonthlyCloseStepIndex.value;
    if (idx < 0 || idx >= monthlyCloseStepIds.value.length - 1) return null;
    return monthlyCloseStepIds.value[idx + 1] ?? null;
  });

  const fiscalYearOptions = computed(() => {
    const years = new Set<number>([
      currentCalendarYear - 1,
      currentCalendarYear,
      currentCalendarYear + 1,
      2026,
    ]);
    for (const entry of incomeStore.entries.value) years.add(entry.fiscalYear);
    for (const entry of expenseStore.entries.value) years.add(entry.fiscalYear);
    years.add(fiscalYear.value);
    return Array.from(years).sort((a, b) => b - a);
  });
  const selectedOwnershipFilterLabel = computed(() => {
    if (ownershipFilter.value === 'all') return 'Todos';
    return (
      ownershipOptions.value.find((option) => option.value === ownershipFilter.value)?.label ??
      ownershipFilter.value
    );
  });
  const selectedFiscalYearLabel = computed(() => String(fiscalYear.value));

  const isLoading = computed(() => incomeStore.loading.value || expenseStore.loading.value);
  const firstError = computed(() => incomeStore.error.value || expenseStore.error.value);
  const incomeEntries = computed(() => incomeStore.entries.value);
  const expenseEntries = computed(() => expenseStore.entries.value);

  type OwnerOption = { value: string; label: string };

  function parseSharedOwnerShares(ownerLabel: string): { name: string; share: number }[] {
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

  function ownerNamesFromLabel(ownerLabel: string): string[] {
    const text = ownerLabel.trim();
    if (!text) return [];
    const shared = parseSharedOwnerShares(text);
    if (shared.length > 0) return shared.map((row) => row.name);
    return [text];
  }

  function allocationFractionForOwnerLabel(ownerLabel: string, selectedOwner: string): number {
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

  const ownershipOptions = computed<OwnerOption[]>(() => {
    const names = new Set<string>();
    for (const entry of incomeEntries.value) {
      for (const name of ownerNamesFromLabel(entry.owner ?? '')) names.add(name);
    }
    for (const entry of expenseEntries.value) {
      for (const name of ownerNamesFromLabel(entry.owner ?? '')) names.add(name);
    }
    return Array.from(names)
      .sort((a, b) => a.localeCompare(b, 'es'))
      .map((name) => ({ value: name, label: name }));
  });

  watch(ownershipOptions, (options) => {
    if (ownershipFilter.value === 'all') return;
    if (!options.some((option) => option.value === ownershipFilter.value)) {
      ownershipFilter.value = 'all';
    }
  });

  function closePopoverFromClick(event: Event): void {
    const target = event.currentTarget as HTMLElement | null;
    const details = target?.closest('details') as HTMLDetailsElement | null;
    if (details) details.open = false;
  }

  function setActiveMonthlyCloseStep(step: MonthlyCloseStepId): void {
    activeMonthlyCloseStep.value = step;
  }

  function goToPreviousMonthlyCloseStep(): void {
    if (previousMonthlyCloseStep.value)
      activeMonthlyCloseStep.value = previousMonthlyCloseStep.value;
  }

  function goToNextMonthlyCloseStep(): void {
    if (nextMonthlyCloseStep.value) activeMonthlyCloseStep.value = nextMonthlyCloseStep.value;
  }

  function selectOwnershipFilterOption(value: string, event: Event): void {
    ownershipFilter.value = value;
    closePopoverFromClick(event);
  }

  function selectFiscalYearOption(year: number, event: Event): void {
    fiscalYear.value = year;
    closePopoverFromClick(event);
  }

  function updateSelectedExecutionMonth(month: number): void {
    selectedExecutionMonth.value = month;
  }

  function setIncomeAdjustAmount(entryId: number, value: string): void {
    incomeAdjustAmounts.value = { ...incomeAdjustAmounts.value, [entryId]: value };
  }

  function isIncomeGroupUnlocked(groupKey: string): boolean {
    return unlockedIncomeGroupKeys.value.has(groupKey);
  }

  function setIncomeGroupUnlocked(groupKey: string, unlocked: boolean): void {
    const next = new Set(unlockedIncomeGroupKeys.value);
    if (unlocked) next.add(groupKey);
    else next.delete(groupKey);
    unlockedIncomeGroupKeys.value = next;
  }

  function isExpenseGroupUnlocked(groupKey: string): boolean {
    return unlockedExpenseGroupKeys.value.has(groupKey);
  }

  function setExpenseGroupUnlocked(groupKey: string, unlocked: boolean): void {
    const next = new Set(unlockedExpenseGroupKeys.value);
    if (unlocked) next.add(groupKey);
    else next.delete(groupKey);
    unlockedExpenseGroupKeys.value = next;
  }

  function setExpenseAdjustAmount(entryId: number, value: string): void {
    expenseAdjustAmounts.value = { ...expenseAdjustAmounts.value, [entryId]: value };
  }

  function setLiquidityAdjustAmount(assetId: number, value: string): void {
    liquidityAdjustAmounts.value = { ...liquidityAdjustAmounts.value, [assetId]: value };
  }

  function isLiquidityLedgerRowUnlocked(assetId: number): boolean {
    return unlockedLiquidityLedgerAssetIds.value.has(assetId);
  }

  function setLiquidityLedgerRowUnlocked(assetId: number, unlocked: boolean): void {
    const next = new Set(unlockedLiquidityLedgerAssetIds.value);
    if (unlocked) next.add(assetId);
    else next.delete(assetId);
    unlockedLiquidityLedgerAssetIds.value = next;
  }

  function updateIncomeViewMode(mode: BudgetEntryViewMode): void {
    incomeViewMode.value = mode;
  }

  function updateExpenseViewMode(mode: BudgetEntryViewMode): void {
    expenseViewMode.value = mode;
  }

  const ownerAdjustedIncomeEntries = computed(() =>
    incomeEntries.value
      .map((entry) => {
        const fraction = allocationFractionForOwnerLabel(entry.owner ?? '', ownershipFilter.value);
        const amountAnnual = effectiveAnnualAmountForEntry(
          {
            ...entry,
            amountAnnual: entry.amountAnnual * fraction,
          },
          entry.fiscalYear,
        );
        return {
          ...entry,
          amountAnnual,
          baseAmountAnnual: entry.amountAnnual,
        };
      })
      .filter((entry) => entry.baseAmountAnnual === 0 || entry.amountAnnual > 0),
  );

  const ownerAdjustedExpenseEntries = computed(() =>
    expenseEntries.value
      .map((entry) => {
        const fraction = allocationFractionForOwnerLabel(entry.owner ?? '', ownershipFilter.value);
        const amountAnnual = effectiveAnnualAmountForEntry(
          {
            ...entry,
            amountAnnual: entry.amountAnnual * fraction,
          },
          entry.fiscalYear,
        );
        return {
          ...entry,
          amountAnnual,
          baseAmountAnnual: entry.amountAnnual,
        };
      })
      .filter((entry) => entry.baseAmountAnnual === 0 || entry.amountAnnual > 0),
  );

  function matchesIncomeViewMode(
    entry: (typeof incomeEntries.value)[number],
    mode: BudgetEntryViewMode,
  ): boolean {
    if (mode === 'all') return true;
    return mode === 'recurrent' ? entry.incomeType === 'recurrent' : entry.incomeType === 'one_off';
  }

  function matchesExpenseViewMode(
    entry: (typeof expenseEntries.value)[number],
    mode: BudgetEntryViewMode,
  ): boolean {
    if (mode === 'all') return true;
    return mode === 'recurrent'
      ? entry.expenseType === 'recurrent'
      : entry.expenseType === 'one_off';
  }

  function sumPlanned<T extends { amountAnnual: number }>(entries: T[]): number {
    return entries.reduce(
      (sum, entry) => sum + (Number.isFinite(entry.amountAnnual) ? entry.amountAnnual : 0),
      0,
    );
  }

  const filteredIncomeEntries = computed(() =>
    ownerAdjustedIncomeEntries.value.filter((entry) =>
      matchesIncomeViewMode(entry, incomeViewMode.value),
    ),
  );
  const filteredExpenseEntries = computed(() =>
    ownerAdjustedExpenseEntries.value.filter(
      (entry) =>
        entry.category !== 'savings_allocation' &&
        matchesExpenseViewMode(entry, expenseViewMode.value),
    ),
  );

  const plannedIncomeTotal = computed(() => sumPlanned(filteredIncomeEntries.value));
  const plannedExpenseTotal = computed(() => sumPlanned(filteredExpenseEntries.value));
  const plannedBalanceTotal = computed(() => plannedIncomeTotal.value - plannedExpenseTotal.value);

  function toNumberOrZero(raw: unknown): number {
    const n = Number(raw ?? 0);
    return Number.isFinite(n) ? n : 0;
  }

  function monthlySummaryExecutedTotal(
    row: ExpenseMonthlySummaryMonth | IncomeMonthlySummaryMonth | null | undefined,
  ): number | null {
    if (!row) return null;
    return toNumberOrZero(row.executed_total ?? row.executed);
  }

  function incomeBreakdownMonthForTaxonomy(
    categoryKey: string,
    subcategoryKey: string,
    month: number,
  ): ExpenseExecutionBreakdownMonth | null {
    return (
      incomeExecutionBreakdownCategories.value
        .find((category) => category.category === categoryKey)
        ?.subcategories.find((subcategory) => subcategory.subcategory === subcategoryKey)
        ?.months.find((monthRow) => monthRow.month === month) ?? null
    );
  }

  function expenseBreakdownMonthForTaxonomy(
    categoryKey: string,
    subcategoryKey: string,
    month: number,
  ): ExpenseExecutionBreakdownMonth | null {
    return (
      expenseExecutionBreakdownCategories.value
        .find((category) => category.category === categoryKey)
        ?.subcategories.find((subcategory) => subcategory.subcategory === subcategoryKey)
        ?.months.find((monthRow) => monthRow.month === month) ?? null
    );
  }

  function budgetTaxonomyKey(category: string, subcategory: string): string {
    const normalized = normalizeExpenseTaxonomy(category, subcategory);
    return `${normalized.category}::${normalized.subcategory}`;
  }

  function budgetMonthTaxonomyKey(month: number, category: string, subcategory: string): string {
    return `${month}::${budgetTaxonomyKey(category, subcategory)}`;
  }

  function budgetMonthEntryKey(month: number, entryId: number): string {
    return `${month}::${entryId}`;
  }

  function parseBudgetTaxonomyKey(rowKey: string): { categoryKey: string; subcategoryKey: string } {
    const [categoryKey = '', subcategoryKey = ''] = rowKey.split('::');
    return { categoryKey, subcategoryKey };
  }

  function normalizedBudgetTaxonomy(
    category: string,
    subcategory: string,
  ): {
    categoryKey: string;
    subcategoryKey: string;
  } {
    const normalized = normalizeExpenseTaxonomy(category, subcategory);
    return {
      categoryKey: normalized.category,
      subcategoryKey: normalized.subcategory,
    };
  }

  function bookingMonthFromDate(value: string): number {
    const month = Number.parseInt(value.slice(5, 7), 10);
    return Number.isFinite(month) && month >= 1 && month <= 12 ? month : 0;
  }

  function resolveLedgerEntryFlowFamily(entry: LedgerEntry): '' | 'income' | 'expense' {
    if (entry.flow_family === 'income' || entry.flow_family === 'expense') return entry.flow_family;
    if (entry.annual_income_entry_id != null) return 'income';
    if (entry.annual_expense_entry_id != null) return 'expense';
    return '';
  }

  function isRotatoryDepositAssetSubcategory(subcategory: string | null | undefined): boolean {
    return ROTATORY_DEPOSIT_ASSET_SUBCATEGORIES.has((subcategory ?? '') as Asset['subcategory']);
  }

  function collectDepositRotationMonthBuckets(
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

  function isPositiveExecutionLedgerEntry(
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

  type DebtPaymentExpenseTarget = { categoryKey: string; subcategoryKey: string };
  type AccountingExecutionBucketAccumulator = {
    incomeCategorizedByMonthTaxonomy: Map<string, number>;
    expenseCategorizedByMonthTaxonomy: Map<string, number>;
    incomeLegacyByMonthEntryId: Map<string, number>;
    expenseLegacyByMonthEntryId: Map<string, number>;
    depositRotationIncomeByMonth: Map<number, number>;
    depositRotationExpenseByMonth: Map<number, number>;
    incomeUnclassifiedTotal: number;
    expenseUnclassifiedTotal: number;
  };

  function addMapAmount<K>(map: Map<K, number>, key: K, amount: number): void {
    map.set(key, (map.get(key) ?? 0) + amount);
  }

  function buildDebtPaymentExpenseTargetByTransactionId(
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

  function resolveDebtPaymentSiblingExpenseTarget(
    entry: AccountingPostedEntry,
    flowFamily: 'income' | 'expense',
    targets: Map<number, DebtPaymentExpenseTarget>,
  ): DebtPaymentExpenseTarget | undefined {
    if (flowFamily !== 'expense') return undefined;
    if (entry.transactionQuickEntryKind !== 'debt_payment') return undefined;
    if (entry.liability_id != null) return undefined;
    return targets.get(entry.transactionId);
  }

  function collectDebtPaymentSiblingExpenseExecution(
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

  function collectTaxonomyExecution(
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

  function collectLegacyExecution(
    entry: AccountingPostedEntry,
    flowFamily: 'income' | 'expense',
    amount: number,
    bookingMonth: number,
    buckets: AccountingExecutionBucketAccumulator,
  ): boolean {
    if (flowFamily === 'income' && entry.annual_income_entry_id != null) {
      const key = budgetMonthEntryKey(bookingMonth, entry.annual_income_entry_id);
      addMapAmount(buckets.incomeLegacyByMonthEntryId, key, amount);
      return true;
    }
    if (flowFamily === 'expense' && entry.annual_expense_entry_id != null) {
      const key = budgetMonthEntryKey(bookingMonth, entry.annual_expense_entry_id);
      addMapAmount(buckets.expenseLegacyByMonthEntryId, key, amount);
      return true;
    }
    return false;
  }

  function collectAccountingExecutionEntry(
    entry: AccountingPostedEntry,
    targets: Map<number, DebtPaymentExpenseTarget>,
    buckets: AccountingExecutionBucketAccumulator,
  ): void {
    if (entry.transactionQuickEntryKind === 'revaluation') return;
    const flowFamily = resolveLedgerEntryFlowFamily(entry);
    if (!flowFamily || !isPositiveExecutionLedgerEntry(entry, flowFamily)) return;

    const ownershipFraction = allocationFractionForOwnerLabel(
      entry.transactionMemberTag ?? '',
      ownershipFilter.value,
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
    if (collectLegacyExecution(entry, flowFamily, amount, bookingMonth, buckets)) return;
    if (flowFamily === 'income') buckets.incomeUnclassifiedTotal += amount;
    if (flowFamily === 'expense') buckets.expenseUnclassifiedTotal += amount;
  }

  function monthlyPlannedAmountForExpenseEntry(
    entry: (typeof expenseEntries.value)[number],
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

  function monthlyPlannedAmountForIncomeEntry(
    entry: (typeof incomeEntries.value)[number],
    month: number,
  ): number {
    if (entry.targetMonth != null) {
      return entry.targetMonth === month ? toNumberOrZero(entry.amountAnnual) : 0;
    }
    return toNumberOrZero(entry.amountAnnual) / 12;
  }

  const expenseSummaryByMonth = computed(() => {
    const map = new Map<number, ExpenseMonthlySummaryMonth>();
    for (const row of expenseMonthlySummary.value?.months ?? []) {
      map.set(row.month, row);
    }
    return map;
  });

  const incomeSummaryByMonth = computed(() => {
    const map = new Map<number, IncomeMonthlySummaryMonth>();
    for (const row of incomeMonthlySummary.value?.months ?? []) {
      map.set(row.month, row);
    }
    return map;
  });

  const accountingSummaryByMonth = computed(() => {
    const map = new Map<number, MonthlyAccountingSummary['months'][number]>();
    for (const row of accountingMonthlySummary.value?.months ?? []) {
      map.set(row.month, row);
    }
    return map;
  });

  const accountingExecutionBuckets = computed(() => {
    const buckets: AccountingExecutionBucketAccumulator = {
      incomeCategorizedByMonthTaxonomy: new Map<string, number>(),
      expenseCategorizedByMonthTaxonomy: new Map<string, number>(),
      incomeLegacyByMonthEntryId: new Map<string, number>(),
      expenseLegacyByMonthEntryId: new Map<string, number>(),
      depositRotationIncomeByMonth: new Map<number, number>(),
      depositRotationExpenseByMonth: new Map<number, number>(),
      incomeUnclassifiedTotal: 0,
      expenseUnclassifiedTotal: 0,
    };
    const debtPaymentExpenseTargetByTransactionId = buildDebtPaymentExpenseTargetByTransactionId(
      accountingPostedEntries.value,
    );

    for (const entry of accountingPostedEntries.value) {
      collectAccountingExecutionEntry(entry, debtPaymentExpenseTargetByTransactionId, buckets);
    }

    return buckets;
  });

  const incomeTaxonomyLineCountsByMonth = computed(() => {
    const map = new Map<string, number>();
    for (const entry of incomeEntries.value) {
      if (entry.fiscalYear !== fiscalYear.value) continue;
      for (let month = 1; month <= 12; month++) {
        const planned = monthlyPlannedAmountForIncomeEntry(entry, month);
        if (planned <= 0) continue;
        const key = budgetMonthTaxonomyKey(month, entry.category, entry.subcategory);
        map.set(key, (map.get(key) ?? 0) + 1);
      }
    }
    return map;
  });

  const expenseTaxonomyLineCountsByMonth = computed(() => {
    const map = new Map<string, number>();
    for (const entry of expenseEntries.value) {
      for (let month = 1; month <= 12; month++) {
        const planned = monthlyPlannedAmountForExpenseEntry(entry, month);
        if (planned <= 0) continue;
        const key = budgetMonthTaxonomyKey(month, entry.category, entry.subcategory);
        map.set(key, (map.get(key) ?? 0) + 1);
      }
    }
    return map;
  });

  function resolveIncomeExecutionForMonth(
    entry: (typeof incomeEntries.value)[number],
    month: number,
    checkin: IncomeMonthlyCheckinApiItem | null,
  ) {
    const taxonomyKey = budgetMonthTaxonomyKey(month, entry.category, entry.subcategory);
    const categorizedLedgerExecuted =
      accountingExecutionBuckets.value.incomeCategorizedByMonthTaxonomy.get(taxonomyKey) ?? null;
    const legacyLedgerExecuted =
      accountingExecutionBuckets.value.incomeLegacyByMonthEntryId.get(
        budgetMonthEntryKey(month, entry.id),
      ) ?? null;
    const taxonomyLineCount = incomeTaxonomyLineCountsByMonth.value.get(taxonomyKey) ?? 0;
    const fallbackExecuted =
      checkin && checkin.status !== 'skipped' ? toNumberOrZero(checkin.executed_amount) : 0;
    const uniqueCategorizedLedgerExecuted =
      categorizedLedgerExecuted != null && taxonomyLineCount <= 1 ? categorizedLedgerExecuted : 0;
    let executionOrigin: BudgetExecutionOrigin = 'none';
    let executionSource: BudgetExecutionSource = 'none';
    let executed: number | null = null;

    if (uniqueCategorizedLedgerExecuted > 0 || legacyLedgerExecuted != null) {
      executionOrigin =
        uniqueCategorizedLedgerExecuted > 0 ? 'categorized_ledger' : 'legacy_ledger';
      executionSource =
        uniqueCategorizedLedgerExecuted > 0 ? 'categorized_ledger' : 'legacy_fallback';
      executed = uniqueCategorizedLedgerExecuted + (legacyLedgerExecuted ?? 0);
    } else if (categorizedLedgerExecuted != null && taxonomyLineCount > 1) {
      executionOrigin = 'ambiguous_taxonomy';
      executionSource = 'pending_classification';
    } else if (checkin) {
      executionOrigin = 'legacy_checkin';
      executionSource = 'legacy_fallback';
      executed = fallbackExecuted;
    }

    return {
      executed,
      executionOrigin,
      executionSource,
      categorizedLedgerExecuted,
      legacyLedgerExecuted,
    };
  }

  function resolveExpenseExecutionForMonth(
    entry: (typeof expenseEntries.value)[number],
    month: number,
    checkin: ExpenseMonthlyCheckinApiItem | null,
  ) {
    const taxonomyKey = budgetMonthTaxonomyKey(month, entry.category, entry.subcategory);
    const categorizedLedgerExecuted =
      accountingExecutionBuckets.value.expenseCategorizedByMonthTaxonomy.get(taxonomyKey) ?? null;
    const legacyLedgerExecuted =
      accountingExecutionBuckets.value.expenseLegacyByMonthEntryId.get(
        budgetMonthEntryKey(month, entry.id),
      ) ?? null;
    const taxonomyLineCount = expenseTaxonomyLineCountsByMonth.value.get(taxonomyKey) ?? 0;
    const fallbackExecuted =
      checkin && checkin.status !== 'skipped' ? toNumberOrZero(checkin.executed_amount) : 0;
    const uniqueCategorizedLedgerExecuted =
      categorizedLedgerExecuted != null && taxonomyLineCount <= 1 ? categorizedLedgerExecuted : 0;
    let executionOrigin: BudgetExecutionOrigin = 'none';
    let executionSource: BudgetExecutionSource = 'none';
    let executed: number | null = null;

    if (uniqueCategorizedLedgerExecuted > 0 || legacyLedgerExecuted != null) {
      executionOrigin =
        uniqueCategorizedLedgerExecuted > 0 ? 'categorized_ledger' : 'legacy_ledger';
      executionSource =
        uniqueCategorizedLedgerExecuted > 0 ? 'categorized_ledger' : 'legacy_fallback';
      executed = uniqueCategorizedLedgerExecuted + (legacyLedgerExecuted ?? 0);
    } else if (categorizedLedgerExecuted != null && taxonomyLineCount > 1) {
      executionOrigin = 'ambiguous_taxonomy';
      executionSource = 'pending_classification';
    } else if (checkin) {
      executionOrigin = 'legacy_checkin';
      executionSource = 'legacy_fallback';
      executed = fallbackExecuted;
    }

    return {
      executed,
      executionOrigin,
      executionSource,
      categorizedLedgerExecuted,
      legacyLedgerExecuted,
    };
  }

  const selectedExpenseSummaryMonth = computed(() => {
    return expenseSummaryByMonth.value.get(selectedExecutionMonth.value) ?? null;
  });

  const selectedIncomeSummaryMonth = computed(() => {
    return incomeSummaryByMonth.value.get(selectedExecutionMonth.value) ?? null;
  });

  const selectedExpenseMonthPlanned = computed(() =>
    monthlyExpenseExecutionEntries.value.reduce((sum, row) => sum + row.planned, 0),
  );
  const selectedExpenseMonthDeviation = computed(
    () => selectedExpenseMonthExecuted.value - selectedExpenseMonthPlanned.value,
  );

  const monthlyIncomeExecutionEntries = computed(() => {
    return incomeEntries.value
      .filter((entry) => {
        if (entry.fiscalYear !== fiscalYear.value) return false;
        const summaryMonth = incomeBreakdownMonthForTaxonomy(
          entry.category,
          entry.subcategory,
          selectedExecutionMonth.value,
        );
        const hasExecutionInSelectedMonth =
          summaryMonth != null && toNumberOrZero(summaryMonth.executed_total) > 0;
        const hasCheckinInSelectedMonth = incomeCheckinsByEntryId.value[entry.id] != null;
        if (entry.incomeType === 'one_off') {
          return (
            entry.targetMonth === selectedExecutionMonth.value ||
            hasExecutionInSelectedMonth ||
            hasCheckinInSelectedMonth
          );
        }
        return true;
      })
      .map((entry) => {
        const checkin = incomeCheckinsByEntryId.value[entry.id] ?? null;
        const planned = monthlyPlannedAmountForIncomeEntry(entry, selectedExecutionMonth.value);
        const {
          categorizedLedgerExecuted,
          legacyLedgerExecuted,
          executed,
          executionOrigin,
          executionSource,
        } = resolveIncomeExecutionForMonth(entry, selectedExecutionMonth.value, checkin);
        return {
          entry,
          planned,
          checkin,
          executed,
          executionOrigin,
          categorizedLedgerExecuted,
          legacyLedgerExecuted,
          executionSource,
        };
      })
      .filter((row) => row.planned > 0 || row.executed != null || row.checkin != null)
      .sort((a, b) => b.planned - a.planned || a.entry.name.localeCompare(b.entry.name, 'es'));
  });

  const selectedIncomeMonthPlanned = computed(() =>
    monthlyIncomeExecutionEntries.value.reduce((sum, row) => sum + row.planned, 0),
  );

  const groupedMonthlyIncomeExecutionEntries = computed(() => {
    type Row = (typeof monthlyIncomeExecutionEntries.value)[number];
    const groups = new Map<
      string,
      {
        key: string;
        categoryKey: string;
        categoryLabel: string;
        subcategoryKey: string;
        subcategoryLabel: string;
        rows: Row[];
        plannedTotal: number;
        executedTotal: number;
        checkedCount: number;
        ledgerDetectedTotal: number;
        editableRow: Row | null;
      }
    >();

    for (const row of monthlyIncomeExecutionEntries.value) {
      const categoryKey = row.entry.category;
      const subcategoryKey = row.entry.subcategory;
      const key = `${categoryKey}:${subcategoryKey}`;
      let group = groups.get(key);
      if (!group) {
        group = {
          key,
          categoryKey,
          categoryLabel: incomeCategoryLabels.get(categoryKey) ?? categoryKey,
          subcategoryKey,
          subcategoryLabel: incomeSubcategoryLabels.get(subcategoryKey) ?? subcategoryKey,
          rows: [],
          plannedTotal: 0,
          executedTotal: 0,
          checkedCount: 0,
          ledgerDetectedTotal: 0,
          editableRow: null,
        };
        groups.set(key, group);
      }

      group.rows.push(row);
      group.plannedTotal += row.planned;
      if (row.executed != null && row.executionOrigin !== 'legacy_checkin') {
        group.ledgerDetectedTotal += row.executed;
      }
      if (row.executionSource !== 'none') {
        group.checkedCount += 1;
        if (row.executed != null) group.executedTotal += row.executed;
      }
    }

    for (const category of incomeExecutionBreakdownCategories.value) {
      for (const subcategory of category.subcategories) {
        const summaryMonth = subcategory.months.find(
          (monthRow) => monthRow.month === selectedExecutionMonth.value,
        );
        const summaryExecutedTotal =
          summaryMonth != null ? toNumberOrZero(summaryMonth.executed_total) : 0;
        const summaryPlanned = summaryMonth != null ? toNumberOrZero(summaryMonth.planned) : 0;
        if (summaryExecutedTotal === 0 && summaryPlanned === 0) continue;
        const key = `${category.category}:${subcategory.subcategory}`;
        if (groups.has(key)) continue;
        groups.set(key, {
          key,
          categoryKey: category.category,
          categoryLabel: incomeCategoryLabels.get(category.category as never) ?? category.category,
          subcategoryKey: subcategory.subcategory,
          subcategoryLabel:
            incomeSubcategoryLabels.get(subcategory.subcategory) ?? subcategory.subcategory,
          rows: [],
          plannedTotal: summaryPlanned,
          executedTotal: summaryExecutedTotal,
          checkedCount: summaryExecutedTotal > 0 ? 1 : 0,
          ledgerDetectedTotal: summaryExecutedTotal,
          editableRow: null,
        });
      }
    }

    return Array.from(groups.values())
      .map((group) => {
        const manualOverrideTotal = group.rows.reduce((sum, row) => {
          if (!row.checkin || row.checkin.status === 'skipped') return sum;
          return sum + toNumberOrZero(row.checkin.executed_amount);
        }, 0);
        const hasManualOverride = manualOverrideTotal > 0;
        const summaryMonth = incomeBreakdownMonthForTaxonomy(
          group.categoryKey,
          group.subcategoryKey,
          selectedExecutionMonth.value,
        );
        const summaryExecutedTotal =
          summaryMonth != null ? toNumberOrZero(summaryMonth.executed_total) : null;
        const detectedLedgerTotal = group.rows.some(
          (row) => row.executionSource === 'pending_classification',
        )
          ? (summaryExecutedTotal ??
            Math.max(...group.rows.map((row) => row.categorizedLedgerExecuted ?? 0)))
          : group.ledgerDetectedTotal;
        const executedTotal = hasManualOverride
          ? manualOverrideTotal
          : (summaryExecutedTotal ??
            group.executedTotal +
              (detectedLedgerTotal === group.ledgerDetectedTotal ? 0 : detectedLedgerTotal));
        return {
          ...group,
          ledgerDetectedTotal: detectedLedgerTotal,
          executedTotal,
          deviation: executedTotal - group.plannedTotal,
          completionRatio: group.rows.length ? group.checkedCount / group.rows.length : 0,
          editableRow: group.rows[0] ?? null,
        };
      })
      .sort(
        (a, b) =>
          b.plannedTotal - a.plannedTotal ||
          a.subcategoryLabel.localeCompare(b.subcategoryLabel, 'es'),
      );
  });
  const selectedIncomeMonthExecuted = computed(
    () =>
      monthlySummaryExecutedTotal(selectedIncomeSummaryMonth.value) ??
      groupedMonthlyIncomeExecutionEntries.value.reduce(
        (sum, group) => sum + group.executedTotal,
        0,
      ),
  );
  const selectedIncomeMonthDeviation = computed(
    () => selectedIncomeMonthExecuted.value - selectedIncomeMonthPlanned.value,
  );
  const selectedIncomeMonthCompletionRatio = computed(() => {
    const total = monthlyIncomeExecutionEntries.value.length;
    if (!total) return 1;
    const checked = monthlyIncomeExecutionEntries.value.filter(
      (row) => row.executionSource !== 'none',
    ).length;
    return checked / total;
  });

  const incomeEvolutionMonths = computed(() => {
    const rows = monthLabels.map((label, index) => {
      const month = index + 1;
      const planned = filteredIncomeEntries.value.reduce(
        (sum, entry) => sum + monthlyPlannedAmountForIncomeEntry(entry, month),
        0,
      );
      let executedBudgeted = 0;
      let executedUnbudgeted = 0;
      for (const category of incomeExecutionBreakdownCategories.value) {
        for (const subcategory of category.subcategories) {
          for (const monthRow of subcategory.months) {
            if (monthRow.month !== month) continue;
            const weight = incomePlannedTaxonomyWeight(
              month,
              category.category,
              subcategory.subcategory,
            );
            const executionWeight = incomeExecutionTaxonomyWeight(
              month,
              category.category,
              subcategory.subcategory,
            );
            const taxonomyKey = budgetMonthTaxonomyKey(
              month,
              category.category,
              subcategory.subcategory,
            );
            const taxonomyExecuted =
              accountingExecutionBuckets.value.incomeCategorizedByMonthTaxonomy.get(taxonomyKey) ??
              null;
            if (weight <= 0) continue;
            let grossBudgeted = 0;
            let grossUnbudgeted = 0;
            let scale = weight;
            if (taxonomyExecuted != null) {
              scale = executionWeight;
              if (subcategory.has_budgeted_line) grossBudgeted = taxonomyExecuted * executionWeight;
              else grossUnbudgeted = taxonomyExecuted * executionWeight;
            } else {
              grossBudgeted = toNumberOrZero(monthRow.executed_budgeted) * weight;
              grossUnbudgeted = toNumberOrZero(monthRow.executed_unbudgeted) * weight;
            }
            const netExecution = applyIncomeInvestmentRotationNet(
              category.category,
              subcategory.subcategory,
              month,
              grossBudgeted,
              grossUnbudgeted,
              scale,
            );
            executedBudgeted += netExecution.budgeted;
            executedUnbudgeted += netExecution.unbudgeted;
          }
        }
      }
      const executed = executedBudgeted + executedUnbudgeted;
      const monthSummary = incomeSummaryByMonth.value.get(month);
      return {
        month,
        label,
        planned,
        executed,
        hasExecuted: (monthSummary?.checkins_confirmed ?? 0) > 0 || executed > 0,
      };
    });
    const maxMonthAmount = Math.max(1, ...rows.map((row) => Math.max(row.planned, row.executed)));
    const toHeightPct = (value: number) => {
      if (value <= 0) return 0;
      return Math.max(6, Math.min(100, (value / maxMonthAmount) * 100));
    };
    return rows.map((row) => ({
      ...row,
      planHeightPct: toHeightPct(row.planned),
      execHeightPct: toHeightPct(row.executed),
    }));
  });

  const incomeEvolutionBaseMonthly = computed(() => plannedIncomeTotal.value / 12);

  const expenseEvolutionMonths = computed(() => {
    const rows = monthLabels.map((label, index) => {
      const month = index + 1;
      const summary = expenseSummaryByMonth.value.get(month);
      const planned = filteredExpenseEntries.value.reduce(
        (sum, entry) => sum + monthlyPlannedAmountForExpenseEntry(entry, month),
        0,
      );
      const executed = toNumberOrZero(summary?.executed);
      return {
        month,
        label,
        planned,
        executed,
        hasExecuted: (summary?.checkins_confirmed ?? 0) > 0 || executed > 0,
      };
    });
    const maxMonthAmount = Math.max(1, ...rows.map((row) => Math.max(row.planned, row.executed)));
    const toHeightPct = (value: number) => {
      if (value <= 0) return 0;
      return Math.max(6, Math.min(100, (value / maxMonthAmount) * 100));
    };
    return rows.map((row) => ({
      ...row,
      planHeightPct: toHeightPct(row.planned),
      execHeightPct: toHeightPct(row.executed),
    }));
  });

  const expenseEvolutionBaseMonthly = computed(() => plannedExpenseTotal.value / 12);

  const selectedLiquidityMonthPlanned = computed(() =>
    monthlyCloseData.value?.liquidity.previous_total != null
      ? toNumberOrZero(monthlyCloseData.value.liquidity.previous_total)
      : toNumberOrZero(liquidityMonthlySummary.value?.planned_total),
  );
  const selectedLiquidityMonthExecuted = computed(() =>
    toNumberOrZero(liquidityMonthlySummary.value?.executed_total),
  );
  const selectedLiquidityMonthDeviation = computed(
    () => selectedLiquidityMonthExecuted.value - selectedLiquidityMonthPlanned.value,
  );
  const selectedPerimeterInternalExpenseTotal = computed(() =>
    toNumberOrZero(liquidityMonthlySummary.value?.perimeter_internal_expense_total),
  );
  const selectedExpenseMonthExternalExecuted = computed(() =>
    Math.max(0, selectedExpenseMonthExecuted.value - selectedPerimeterInternalExpenseTotal.value),
  );
  const selectedLiquidityStartBase = computed(() => selectedLiquidityMonthPlanned.value);
  const selectedMonthlyCloseExpected = computed(
    () =>
      selectedLiquidityStartBase.value +
      selectedIncomeMonthExecuted.value -
      selectedExpenseMonthExternalExecuted.value,
  );
  const selectedMonthlyCloseResidual = computed(
    () => selectedLiquidityMonthExecuted.value - selectedMonthlyCloseExpected.value,
  );
  const selectedMonthlyCloseCompletionRatio = computed(() => {
    const ratios = [
      monthlyLiquidityExecutionRows.value.length
        ? (liquidityMonthlySummary.value?.completion_ratio ?? 0)
        : 1,
      selectedIncomeMonthCompletionRatio.value,
      monthlyExpenseCoverageSummary.value.ratio,
    ];
    return ratios.reduce((sum, r) => sum + r, 0) / ratios.length;
  });

  const monthlyLiquidityExecutionRows = computed(() =>
    (liquidityMonthlySummary.value?.rows ?? []).map((row) => {
      const planned = toNumberOrZero(row.planned_closing_balance);
      const executed =
        row.executed_closing_balance != null ? toNumberOrZero(row.executed_closing_balance) : null;
      return { ...row, planned, executed };
    }),
  );

  const monthlyExpenseExecutionEntries = computed(() => {
    const month = selectedExecutionMonth.value;
    return filteredExpenseEntries.value
      .filter((entry) => {
        const summaryMonth = expenseBreakdownMonthForTaxonomy(
          entry.category,
          entry.subcategory,
          month,
        );
        const hasExecutionInSelectedMonth =
          summaryMonth != null && toNumberOrZero(summaryMonth.executed_total) > 0;
        const hasCheckinInSelectedMonth = expenseCheckinsByEntryId.value[entry.id] != null;
        if (entry.expenseType === 'one_off') {
          return (
            entry.targetMonth === month || hasExecutionInSelectedMonth || hasCheckinInSelectedMonth
          );
        }
        return true;
      })
      .map((entry) => {
        const checkin = expenseCheckinsByEntryId.value[entry.id] ?? null;
        const planned = monthlyPlannedAmountForExpenseEntry(entry, month);
        const {
          categorizedLedgerExecuted,
          legacyLedgerExecuted,
          executed,
          executionOrigin,
          executionSource,
        } = resolveExpenseExecutionForMonth(entry, month, checkin);
        return {
          entry,
          planned,
          checkin,
          executed,
          executionOrigin,
          categorizedLedgerExecuted,
          legacyLedgerExecuted,
          executionSource,
        };
      })
      .filter((row) => row.planned > 0 || row.executed != null || row.checkin != null)
      .sort(
        (a, b) =>
          expenseCheckinCategorySortWeight(a.entry.category) -
            expenseCheckinCategorySortWeight(b.entry.category) ||
          b.planned - a.planned ||
          a.entry.name.localeCompare(b.entry.name, 'es'),
      );
  });

  const groupedMonthlyExpenseExecutionEntries = computed(() => {
    type Row = (typeof monthlyExpenseExecutionEntries.value)[number];
    const groups = new Map<
      string,
      {
        key: string;
        categoryKey: string;
        categoryLabel: string;
        subcategoryKey: string;
        subcategoryLabel: string;
        rows: Row[];
        plannedTotal: number;
        executedTotal: number;
        checkedCount: number;
        ledgerDetectedTotal: number;
        editableRow: Row | null;
      }
    >();

    for (const row of monthlyExpenseExecutionEntries.value) {
      const { categoryKey, subcategoryKey } = normalizedBudgetTaxonomy(
        row.entry.category,
        row.entry.subcategory,
      );
      const key = `${categoryKey}:${subcategoryKey}`;
      let group = groups.get(key);
      if (!group) {
        group = {
          key,
          categoryKey,
          categoryLabel: shortExpenseCategoryLabel(categoryKey),
          subcategoryKey,
          subcategoryLabel: expenseSubcategoryLabels.get(subcategoryKey) ?? subcategoryKey,
          rows: [],
          plannedTotal: 0,
          executedTotal: 0,
          checkedCount: 0,
          ledgerDetectedTotal: 0,
          editableRow: null,
        };
        groups.set(key, group);
      }
      group.rows.push(row);
      group.plannedTotal += row.planned;
      if (row.executed != null && row.executionOrigin !== 'legacy_checkin') {
        group.ledgerDetectedTotal += row.executed;
      }
      if (row.executionSource !== 'none') {
        group.checkedCount += 1;
        if (row.executed != null) {
          group.executedTotal += row.executed;
        }
      }
    }

    for (const category of expenseExecutionBreakdownCategories.value) {
      for (const subcategory of category.subcategories) {
        const summaryMonth = subcategory.months.find(
          (monthRow) => monthRow.month === selectedExecutionMonth.value,
        );
        const summaryExecutedTotal =
          summaryMonth != null ? toNumberOrZero(summaryMonth.executed_total) : 0;
        const summaryPlanned = summaryMonth != null ? toNumberOrZero(summaryMonth.planned) : 0;
        if (summaryExecutedTotal === 0 && summaryPlanned === 0) continue;
        const key = `${category.category}:${subcategory.subcategory}`;
        if (groups.has(key)) continue;
        groups.set(key, {
          key,
          categoryKey: category.category,
          categoryLabel: shortExpenseCategoryLabel(category.category),
          subcategoryKey: subcategory.subcategory,
          subcategoryLabel:
            expenseSubcategoryLabels.get(subcategory.subcategory) ?? subcategory.subcategory,
          rows: [],
          plannedTotal: summaryPlanned,
          executedTotal: summaryExecutedTotal,
          checkedCount: summaryExecutedTotal > 0 ? 1 : 0,
          ledgerDetectedTotal: summaryExecutedTotal,
          editableRow: null,
        });
      }
    }

    return Array.from(groups.values())
      .map((group) => {
        const manualOverrideTotal = group.rows.reduce((sum, row) => {
          if (!row.checkin || row.checkin.status === 'skipped') return sum;
          return sum + toNumberOrZero(row.checkin.executed_amount);
        }, 0);
        const hasManualOverride = manualOverrideTotal > 0;
        const summaryMonth = expenseBreakdownMonthForTaxonomy(
          group.categoryKey,
          group.subcategoryKey,
          selectedExecutionMonth.value,
        );
        const summaryExecutedTotal =
          summaryMonth != null ? toNumberOrZero(summaryMonth.executed_total) : null;
        const detectedLedgerTotal = group.rows.some(
          (row) => row.executionSource === 'pending_classification',
        )
          ? (summaryExecutedTotal ??
            Math.max(...group.rows.map((row) => row.categorizedLedgerExecuted ?? 0)))
          : group.ledgerDetectedTotal;
        const executedTotal = hasManualOverride
          ? manualOverrideTotal
          : (summaryExecutedTotal ??
            group.executedTotal +
              (detectedLedgerTotal === group.ledgerDetectedTotal ? 0 : detectedLedgerTotal));
        return {
          ...group,
          ledgerDetectedTotal: detectedLedgerTotal,
          executedTotal,
          deviation: executedTotal - group.plannedTotal,
          completionRatio: group.rows.length ? group.checkedCount / group.rows.length : 0,
          editableRow: group.rows[0] ?? null,
        };
      })
      .sort(
        (a, b) =>
          expenseCheckinCategorySortWeight(a.categoryKey) -
            expenseCheckinCategorySortWeight(b.categoryKey) ||
          b.plannedTotal - a.plannedTotal ||
          a.subcategoryLabel.localeCompare(b.subcategoryLabel, 'es'),
      );
  });
  const selectedExpenseMonthExecuted = computed(
    () =>
      monthlySummaryExecutedTotal(selectedExpenseSummaryMonth.value) ??
      groupedMonthlyExpenseExecutionEntries.value.reduce(
        (sum, group) => sum + group.executedTotal,
        0,
      ),
  );

  function buildMonthlyResultBreakdown<
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
          shareOfExecuted:
            executedSectionTotal > 0 ? group.executedTotal / executedSectionTotal : 0,
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

  const monthlyIncomeResultBreakdown = computed(() =>
    buildMonthlyResultBreakdown(
      monthlyIncomeExecutionEntries.value,
      incomeCategoryLabels,
      incomeSubcategoryLabels,
      selectedIncomeMonthExecuted.value,
    ),
  );

  const monthlyExpenseResultBreakdown = computed(() =>
    buildMonthlyResultBreakdown(
      monthlyExpenseExecutionEntries.value,
      expenseCategoryLabels,
      expenseSubcategoryLabels,
      selectedExpenseMonthExecuted.value,
    ),
  );

  const selectedExecutionMonthLabel = computed(
    () => monthLabels[selectedExecutionMonth.value - 1] ?? String(selectedExecutionMonth.value),
  );

  const budgetDetailMonthLabel = computed(
    () => monthLabels[budgetDetailMonth.value - 1] ?? String(budgetDetailMonth.value),
  );

  function updateBudgetDetailMonth(month: number): void {
    budgetDetailMonth.value = month;
  }

  type BudgetActualAggregateRow = {
    planned: number;
    executed: number;
    checkedCount: number;
    expectedCount: number;
  };

  const incomePlannedTotalsByMonthTaxonomy = computed(() => {
    const map = new Map<string, number>();
    for (const entry of incomeEntries.value) {
      if (entry.fiscalYear !== fiscalYear.value) continue;
      for (let month = 1; month <= 12; month++) {
        const planned = monthlyPlannedAmountForIncomeEntry(entry, month);
        if (planned <= 0) continue;
        const key = budgetMonthTaxonomyKey(month, entry.category, entry.subcategory);
        map.set(key, (map.get(key) ?? 0) + planned);
      }
    }
    return map;
  });

  const incomePlannedFilteredByMonthTaxonomy = computed(() => {
    const map = new Map<string, number>();
    for (const entry of filteredIncomeEntries.value) {
      if (entry.fiscalYear !== fiscalYear.value) continue;
      for (let month = 1; month <= 12; month++) {
        const planned = monthlyPlannedAmountForIncomeEntry(entry, month);
        if (planned <= 0) continue;
        const key = budgetMonthTaxonomyKey(month, entry.category, entry.subcategory);
        map.set(key, (map.get(key) ?? 0) + planned);
      }
    }
    return map;
  });

  const incomePlannedViewModeByMonthTaxonomy = computed(() => {
    const map = new Map<string, number>();
    for (const entry of incomeEntries.value) {
      if (entry.fiscalYear !== fiscalYear.value) continue;
      if (!matchesIncomeViewMode(entry, incomeViewMode.value)) continue;
      for (let month = 1; month <= 12; month++) {
        const planned = monthlyPlannedAmountForIncomeEntry(entry, month);
        if (planned <= 0) continue;
        const key = budgetMonthTaxonomyKey(month, entry.category, entry.subcategory);
        map.set(key, (map.get(key) ?? 0) + planned);
      }
    }
    return map;
  });

  function incomePlannedTaxonomyWeight(
    month: number,
    category: string,
    subcategory: string,
  ): number {
    const key = budgetMonthTaxonomyKey(month, category, subcategory);
    const allPlanned = incomePlannedTotalsByMonthTaxonomy.value.get(key) ?? 0;
    if (allPlanned <= 0) return incomeViewMode.value === 'all' ? 1 : 0;
    const filteredPlanned = incomePlannedFilteredByMonthTaxonomy.value.get(key) ?? 0;
    return Math.max(0, Math.min(1, filteredPlanned / allPlanned));
  }

  function incomeExecutionTaxonomyWeight(
    month: number,
    category: string,
    subcategory: string,
  ): number {
    if (incomeViewMode.value === 'all') return 1;
    const key = budgetMonthTaxonomyKey(month, category, subcategory);
    const allPlanned = incomePlannedTotalsByMonthTaxonomy.value.get(key) ?? 0;
    if (allPlanned <= 0) return 0;
    const viewModePlanned = incomePlannedViewModeByMonthTaxonomy.value.get(key) ?? 0;
    return Math.max(0, Math.min(1, viewModePlanned / allPlanned));
  }

  type IncomeCoverageYtdAggregate = BudgetActualAggregateRow & {
    executedBudgeted: number;
    executedUnbudgeted: number;
  };

  function emptyIncomeCoverageAggregate(): IncomeCoverageYtdAggregate {
    return {
      planned: 0,
      executed: 0,
      executedBudgeted: 0,
      executedUnbudgeted: 0,
      checkedCount: 0,
      expectedCount: 0,
    };
  }

  const expenseExecutionBreakdownCategories = computed(
    () => expenseMonthlySummary.value?.expense_execution_breakdown?.categories ?? [],
  );
  const incomeExecutionBreakdownCategories = computed(
    () => incomeMonthlySummary.value?.income_execution_breakdown?.categories ?? [],
  );
  const investmentOutflowByMonthForIncomeNetting = computed(() => {
    return accountingExecutionBuckets.value.depositRotationExpenseByMonth;
  });

  function applyIncomeInvestmentRotationNet(
    categoryKey: string,
    subcategoryKey: string,
    month: number,
    budgetedAmount: number,
    unbudgetedAmount: number,
    scale = 1,
  ): { budgeted: number; unbudgeted: number } {
    if (
      categoryKey !== INVESTMENT_ROTATION_INCOME_CATEGORY ||
      subcategoryKey !== INVESTMENT_ROTATION_INCOME_SUBCATEGORY
    ) {
      return { budgeted: budgetedAmount, unbudgeted: unbudgetedAmount };
    }
    const adjustment = (investmentOutflowByMonthForIncomeNetting.value.get(month) ?? 0) * scale;
    if (adjustment <= 0) return { budgeted: budgetedAmount, unbudgeted: unbudgetedAmount };

    const netUnbudgeted = Math.max(0, unbudgetedAmount - adjustment);
    const consumedFromUnbudgeted = unbudgetedAmount - netUnbudgeted;
    const remaining = Math.max(0, adjustment - consumedFromUnbudgeted);
    const netBudgeted = Math.max(0, budgetedAmount - remaining);
    return { budgeted: netBudgeted, unbudgeted: netUnbudgeted };
  }

  const incomeInvestmentRotationAdjustmentByCategory = computed(() => {
    const monthsCount = Math.max(0, Math.min(12, budgetDetailMonth.value));
    const map = new Map<string, number>();
    for (const category of incomeExecutionBreakdownCategories.value) {
      for (const subcategory of category.subcategories) {
        for (const monthRow of subcategory.months) {
          if (monthRow.month < 1 || monthRow.month > monthsCount) continue;
          const weight = incomePlannedTaxonomyWeight(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const executionWeight = incomeExecutionTaxonomyWeight(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const taxonomyKey = budgetMonthTaxonomyKey(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const taxonomyExecuted =
            accountingExecutionBuckets.value.incomeCategorizedByMonthTaxonomy.get(taxonomyKey) ??
            null;
          let grossBudgeted = 0;
          let grossUnbudgeted = 0;
          let scale = weight;
          if (taxonomyExecuted != null) {
            scale = executionWeight;
            if (subcategory.has_budgeted_line) grossBudgeted = taxonomyExecuted * executionWeight;
            else grossUnbudgeted = taxonomyExecuted * executionWeight;
          } else {
            grossBudgeted = toNumberOrZero(monthRow.executed_budgeted) * weight;
            grossUnbudgeted = toNumberOrZero(monthRow.executed_unbudgeted) * weight;
          }
          const netExecution = applyIncomeInvestmentRotationNet(
            category.category,
            subcategory.subcategory,
            monthRow.month,
            grossBudgeted,
            grossUnbudgeted,
            scale,
          );
          const adjustment =
            grossBudgeted + grossUnbudgeted - (netExecution.budgeted + netExecution.unbudgeted);
          if (adjustment <= 0) continue;
          map.set(category.category, (map.get(category.category) ?? 0) + adjustment);
        }
      }
    }
    return map;
  });

  const incomeInvestmentRotationAdjustmentBySubcategoryKey = computed(() => {
    const monthsCount = Math.max(0, Math.min(12, budgetDetailMonth.value));
    const map = new Map<string, number>();
    for (const category of incomeExecutionBreakdownCategories.value) {
      for (const subcategory of category.subcategories) {
        for (const monthRow of subcategory.months) {
          if (monthRow.month < 1 || monthRow.month > monthsCount) continue;
          const weight = incomePlannedTaxonomyWeight(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const executionWeight = incomeExecutionTaxonomyWeight(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const taxonomyKey = budgetMonthTaxonomyKey(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const taxonomyExecuted =
            accountingExecutionBuckets.value.incomeCategorizedByMonthTaxonomy.get(taxonomyKey) ??
            null;
          let grossBudgeted = 0;
          let grossUnbudgeted = 0;
          let scale = weight;
          if (taxonomyExecuted != null) {
            scale = executionWeight;
            if (subcategory.has_budgeted_line) grossBudgeted = taxonomyExecuted * executionWeight;
            else grossUnbudgeted = taxonomyExecuted * executionWeight;
          } else {
            grossBudgeted = toNumberOrZero(monthRow.executed_budgeted) * weight;
            grossUnbudgeted = toNumberOrZero(monthRow.executed_unbudgeted) * weight;
          }
          const netExecution = applyIncomeInvestmentRotationNet(
            category.category,
            subcategory.subcategory,
            monthRow.month,
            grossBudgeted,
            grossUnbudgeted,
            scale,
          );
          const adjustment =
            grossBudgeted + grossUnbudgeted - (netExecution.budgeted + netExecution.unbudgeted);
          if (adjustment <= 0) continue;
          const key = `${category.category}::${subcategory.subcategory}`;
          map.set(key, (map.get(key) ?? 0) + adjustment);
        }
      }
    }
    return map;
  });

  const incomeYtdActualByCategory = computed(() => {
    const monthsCount = Math.max(0, Math.min(12, budgetDetailMonth.value));
    const map = new Map<string, IncomeCoverageYtdAggregate>();
    for (const category of incomeExecutionBreakdownCategories.value) {
      let row = map.get(category.category);
      if (!row) {
        row = emptyIncomeCoverageAggregate();
        map.set(category.category, row);
      }
      for (const subcategory of category.subcategories) {
        for (const monthRow of subcategory.months) {
          if (monthRow.month < 1 || monthRow.month > monthsCount) continue;
          const weight = incomePlannedTaxonomyWeight(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const executionWeight = incomeExecutionTaxonomyWeight(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const taxonomyKey = budgetMonthTaxonomyKey(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const taxonomyExecuted =
            accountingExecutionBuckets.value.incomeCategorizedByMonthTaxonomy.get(taxonomyKey) ??
            null;
          if (weight > 0) {
            row.planned += toNumberOrZero(monthRow.planned) * weight;
            let executedBudgetedChunk = 0;
            let executedUnbudgetedChunk = 0;
            if (taxonomyExecuted != null) {
              if (subcategory.has_budgeted_line) {
                executedBudgetedChunk += taxonomyExecuted * executionWeight;
              } else {
                executedUnbudgetedChunk += taxonomyExecuted * executionWeight;
              }
            } else {
              executedBudgetedChunk += toNumberOrZero(monthRow.executed_budgeted) * weight;
              executedUnbudgetedChunk += toNumberOrZero(monthRow.executed_unbudgeted) * weight;
            }
            row.executedBudgeted += executedBudgetedChunk;
            row.executedUnbudgeted += executedUnbudgetedChunk;
          }
        }
      }
      row.executed = row.executedBudgeted + row.executedUnbudgeted;
      row.expectedCount = row.planned > 0 ? 1 : 0;
      row.checkedCount = row.executed > 0 ? 1 : 0;
    }
    return map;
  });

  const incomeYtdActualBySubcategoryKey = computed(() => {
    const monthsCount = Math.max(0, Math.min(12, budgetDetailMonth.value));
    const map = new Map<string, IncomeCoverageYtdAggregate>();
    for (const category of incomeExecutionBreakdownCategories.value) {
      for (const subcategory of category.subcategories) {
        const key = `${category.category}::${subcategory.subcategory}`;
        let row = map.get(key);
        if (!row) {
          row = emptyIncomeCoverageAggregate();
          map.set(key, row);
        }
        for (const monthRow of subcategory.months) {
          if (monthRow.month < 1 || monthRow.month > monthsCount) continue;
          const weight = incomePlannedTaxonomyWeight(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const executionWeight = incomeExecutionTaxonomyWeight(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const taxonomyKey = budgetMonthTaxonomyKey(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const taxonomyExecuted =
            accountingExecutionBuckets.value.incomeCategorizedByMonthTaxonomy.get(taxonomyKey) ??
            null;
          if (weight > 0) {
            row.planned += toNumberOrZero(monthRow.planned) * weight;
            let executedBudgetedChunk = 0;
            let executedUnbudgetedChunk = 0;
            if (taxonomyExecuted != null) {
              if (subcategory.has_budgeted_line) {
                executedBudgetedChunk += taxonomyExecuted * executionWeight;
              } else {
                executedUnbudgetedChunk += taxonomyExecuted * executionWeight;
              }
            } else {
              executedBudgetedChunk += toNumberOrZero(monthRow.executed_budgeted) * weight;
              executedUnbudgetedChunk += toNumberOrZero(monthRow.executed_unbudgeted) * weight;
            }
            row.executedBudgeted += executedBudgetedChunk;
            row.executedUnbudgeted += executedUnbudgetedChunk;
          }
        }
        row.executed = row.executedBudgeted + row.executedUnbudgeted;
        row.expectedCount = row.planned > 0 ? 1 : 0;
        row.checkedCount = row.executed > 0 ? 1 : 0;
      }
    }
    return map;
  });

  type ExpenseCoverageYtdAggregate = BudgetActualAggregateRow & {
    executedBudgeted: number;
    executedUnbudgeted: number;
  };

  function emptyExpenseCoverageAggregate(): ExpenseCoverageYtdAggregate {
    return {
      planned: 0,
      executed: 0,
      executedBudgeted: 0,
      executedUnbudgeted: 0,
      checkedCount: 0,
      expectedCount: 0,
    };
  }

  const expenseYtdActualByCategory = computed(() => {
    const monthsCount = Math.max(0, Math.min(12, budgetDetailMonth.value));
    const map = new Map<string, ExpenseCoverageYtdAggregate>();
    for (const category of expenseExecutionBreakdownCategories.value) {
      let row = map.get(category.category);
      if (!row) {
        row = emptyExpenseCoverageAggregate();
        map.set(category.category, row);
      }
      for (const subcategory of category.subcategories) {
        for (const monthRow of subcategory.months) {
          if (monthRow.month < 1 || monthRow.month > monthsCount) continue;
          row.planned += toNumberOrZero(monthRow.planned);
          row.executedBudgeted += toNumberOrZero(monthRow.executed_budgeted);
          row.executedUnbudgeted += toNumberOrZero(monthRow.executed_unbudgeted);
        }
      }
      row.executed = row.executedBudgeted + row.executedUnbudgeted;
      row.expectedCount = row.planned > 0 ? 1 : 0;
      row.checkedCount = row.executed > 0 ? 1 : 0;
    }
    return map;
  });

  const expenseYtdActualBySubcategoryKey = computed(() => {
    const monthsCount = Math.max(0, Math.min(12, budgetDetailMonth.value));
    const map = new Map<string, ExpenseCoverageYtdAggregate>();
    for (const category of expenseExecutionBreakdownCategories.value) {
      for (const subcategory of category.subcategories) {
        const key = `${category.category}::${subcategory.subcategory}`;
        let row = map.get(key);
        if (!row) {
          row = emptyExpenseCoverageAggregate();
          map.set(key, row);
        }
        for (const monthRow of subcategory.months) {
          if (monthRow.month < 1 || monthRow.month > monthsCount) continue;
          row.planned += toNumberOrZero(monthRow.planned);
          row.executedBudgeted += toNumberOrZero(monthRow.executed_budgeted);
          row.executedUnbudgeted += toNumberOrZero(monthRow.executed_unbudgeted);
        }
        row.executed = row.executedBudgeted + row.executedUnbudgeted;
        row.expectedCount = row.planned > 0 ? 1 : 0;
        row.checkedCount = row.executed > 0 ? 1 : 0;
      }
    }
    return map;
  });

  type BudgetActualExecution = {
    planned: number;
    executed: number;
    deviation: number;
    completionRatio: number;
    ratio: number;
    widthPct: number;
    tone: BudgetExecutionTone;
    overflow: boolean;
  };

  function buildActualExecution(
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

  function budgetCategoryActualExecution(
    sectionId: BudgetSectionModel['id'],
    categoryKey: string,
  ): BudgetActualExecution | null {
    if (sectionId === 'income') {
      const row = incomeYtdActualByCategory.value.get(categoryKey);
      if (!row) return null;
      return buildActualExecution(
        sectionId,
        row.planned,
        row.executed,
        row.expectedCount > 0 ? row.checkedCount / row.expectedCount : 0,
      );
    }
    if (sectionId === 'expense') {
      const row = expenseYtdActualByCategory.value.get(categoryKey);
      if (!row) return null;
      return buildActualExecution(
        sectionId,
        row.planned,
        row.executed,
        row.expectedCount > 0 ? row.checkedCount / row.expectedCount : 0,
      );
    }
    return null;
  }

  function budgetSubcategoryActualExecution(
    sectionId: BudgetSectionModel['id'],
    rowKey: string,
  ): BudgetActualExecution | null {
    if (sectionId === 'income') {
      const row = incomeYtdActualBySubcategoryKey.value.get(rowKey);
      if (!row) {
        const { categoryKey, subcategoryKey } = parseBudgetTaxonomyKey(rowKey);
        const planned = filteredIncomeEntries.value.reduce((sum, entry) => {
          if (entry.fiscalYear !== fiscalYear.value) return sum;
          if (entry.category !== categoryKey || entry.subcategory !== subcategoryKey) return sum;
          let next = sum;
          for (let month = 1; month <= budgetDetailMonth.value; month += 1) {
            next += monthlyPlannedAmountForIncomeEntry(entry, month);
          }
          return next;
        }, 0);
        return buildActualExecution(sectionId, planned, 0, planned > 0 ? 1 : 0);
      }
      return buildActualExecution(
        sectionId,
        row.planned,
        row.executed,
        row.expectedCount > 0 ? row.checkedCount / row.expectedCount : 0,
      );
    }
    if (sectionId === 'expense') {
      const row = expenseYtdActualBySubcategoryKey.value.get(rowKey);
      if (!row) {
        const { categoryKey, subcategoryKey } = parseBudgetTaxonomyKey(rowKey);
        const planned = filteredExpenseEntries.value.reduce((sum, entry) => {
          if (entry.fiscalYear !== fiscalYear.value) return sum;
          if (entry.category !== categoryKey || entry.subcategory !== subcategoryKey) return sum;
          let next = sum;
          for (let month = 1; month <= budgetDetailMonth.value; month += 1) {
            next += monthlyPlannedAmountForExpenseEntry(entry, month);
          }
          return next;
        }, 0);
        return buildActualExecution(sectionId, planned, 0, planned > 0 ? 1 : 0);
      }
      return buildActualExecution(
        sectionId,
        row.planned,
        row.executed,
        row.expectedCount > 0 ? row.checkedCount / row.expectedCount : 0,
      );
    }
    return null;
  }

  function budgetSectionActualExecution(
    sectionId: BudgetSectionModel['id'],
  ): BudgetActualExecution | null {
    if (sectionId === 'income') {
      const totals = incomeExecutionYtdTotals.value;
      return buildActualExecution(
        sectionId,
        totals.planned,
        totals.executedTotal,
        totals.planned > 0 ? 1 : 0,
      );
    }
    if (sectionId === 'expense') {
      const totals = expenseExecutionYtdTotals.value;
      return buildActualExecution(
        sectionId,
        totals.planned,
        totals.executedTotal,
        totals.planned > 0 ? 1 : 0,
      );
    }
    return null;
  }

  const selectedMonthlyExecutedVolume = computed(
    () => selectedIncomeMonthExecuted.value + selectedExpenseMonthExecuted.value,
  );
  const selectedMonthlyResidualAbs = computed(() => Math.abs(selectedMonthlyCloseResidual.value));
  const selectedMonthlyResidualVolumeRatio = computed(() =>
    selectedMonthlyExecutedVolume.value > 0
      ? selectedMonthlyResidualAbs.value / selectedMonthlyExecutedVolume.value
      : null,
  );
  const selectedMonthlyResidualIncomeRatio = computed(() =>
    selectedIncomeMonthExecuted.value > 0
      ? selectedMonthlyResidualAbs.value / selectedIncomeMonthExecuted.value
      : null,
  );
  const selectedMonthlyResidualExpenseRatio = computed(() =>
    selectedExpenseMonthExecuted.value > 0
      ? selectedMonthlyResidualAbs.value / selectedExpenseMonthExecuted.value
      : null,
  );
  const selectedMonthlyResidualExpectedCloseRatio = computed(() =>
    Math.abs(selectedMonthlyCloseExpected.value) > 0
      ? selectedMonthlyResidualAbs.value / Math.abs(selectedMonthlyCloseExpected.value)
      : null,
  );

  const selectedMonthlyResidualSeverity = computed<'ok' | 'watch' | 'alert'>(() => {
    const ratio = selectedMonthlyResidualVolumeRatio.value;
    if (ratio == null) return 'ok';
    if (ratio <= 0.01) return 'ok';
    if (ratio <= 0.03) return 'watch';
    return 'alert';
  });

  const selectedMonthlyResidualSeverityLabel = computed(() => {
    if (selectedMonthlyResidualSeverity.value === 'ok') return 'Conciliacion OK';
    if (selectedMonthlyResidualSeverity.value === 'watch') return 'Revisar residual';
    return 'Residual alto';
  });

  const resultReconciliationFlowRows = computed(() => [
    {
      id: 'start',
      label: 'Perimetro inicio (referencia)',
      amount: selectedLiquidityStartBase.value,
      tone: 'neutral' as const,
      meta: 'Base de referencia del paso de liquidez',
    },
    {
      id: 'income',
      label: 'Ingresos ejecutados',
      amount: selectedIncomeMonthExecuted.value,
      tone: 'positive' as const,
      meta:
        selectedMonthlyExecutedVolume.value > 0
          ? `${formatPercent(selectedIncomeMonthExecuted.value / selectedMonthlyExecutedVolume.value, 0)} del volumen`
          : undefined,
    },
    {
      id: 'expense',
      label: 'Gastos externos al perimetro',
      amount: -selectedExpenseMonthExternalExecuted.value,
      tone: 'warning' as const,
      meta:
        selectedMonthlyExecutedVolume.value > 0
          ? `${formatPercent(selectedExpenseMonthExternalExecuted.value / selectedMonthlyExecutedVolume.value, 0)} del volumen`
          : undefined,
    },
    ...(selectedPerimeterInternalExpenseTotal.value > 0
      ? [
          {
            id: 'internal-perimeter-expense',
            label: 'Aportes dentro del perimetro',
            amount: 0,
            tone: 'neutral' as const,
            meta: `${formatMoney(selectedPerimeterInternalExpenseTotal.value)} EUR reclasificados como movimiento interno`,
          },
        ]
      : []),
    {
      id: 'expected-close',
      label: 'Cierre esperado',
      amount: selectedMonthlyCloseExpected.value,
      tone: 'neutral' as const,
      meta: 'Perimetro inicio + ingresos - gastos externos',
      isResult: true,
    },
    {
      id: 'residual',
      label: 'Ajuste de conciliacion (residual)',
      amount: selectedMonthlyCloseResidual.value,
      tone: selectedMonthlyCloseResidual.value < 0 ? ('negative' as const) : ('positive' as const),
      meta:
        selectedMonthlyResidualVolumeRatio.value == null
          ? 'Sin volumen ejecutado'
          : `${formatPercent(selectedMonthlyResidualVolumeRatio.value, 1)} del volumen ejecutado`,
    },
    {
      id: 'real-close',
      label: 'Cierre real del perimetro',
      amount: selectedLiquidityMonthExecuted.value,
      tone: 'neutral' as const,
      meta: 'Cierre del perimetro confirmado',
      isResult: true,
    },
  ]);

  const resultReconciliationCompositionRows = computed(() => {
    const volume = selectedMonthlyExecutedVolume.value;
    return [
      {
        id: 'income',
        label: 'Ingresos ejecutados',
        amount: selectedIncomeMonthExecuted.value,
        shareOfVolume: volume > 0 ? selectedIncomeMonthExecuted.value / volume : null,
        tone: 'positive' as const,
      },
      {
        id: 'expense',
        label: 'Gastos ejecutados',
        amount: selectedExpenseMonthExecuted.value,
        shareOfVolume: volume > 0 ? selectedExpenseMonthExecuted.value / volume : null,
        tone: 'warning' as const,
      },
      {
        id: 'residual',
        label: 'Ajuste de conciliacion (residual)',
        amount: selectedMonthlyCloseResidual.value,
        shareOfVolume: volume > 0 ? selectedMonthlyResidualAbs.value / volume : null,
        tone: selectedMonthlyCloseResidual.value < 0 ? ('negative' as const) : ('neutral' as const),
      },
    ];
  });

  const executionStatusLabel = computed(() => {
    if (accountingExecutionLoading.value) return 'Sincronizando movimientos';
    if (accountingExecutionError.value) return 'Revisión manual';
    const monthsWithLedger = Array.from(accountingSummaryByMonth.value.values()).filter(
      (row) => toNumberOrZero(row.income_total) > 0 || toNumberOrZero(row.expense_total) > 0,
    ).length;
    if (monthsWithLedger > 0) return 'Movimientos + revisión';
    if (!expenseMonthlySummary.value) return 'Cargando ejecución';
    if (expenseMonthlySummary.value.has_executed_data) return 'Revisión manual';
    return 'Sin ejecución';
  });
  const executionStatusDetail = computed(() => {
    if (accountingExecutionError.value) {
      return 'No se pudieron leer los movimientos. Puedes completar el cierre manualmente.';
    }
    const monthsWithLedger = Array.from(accountingSummaryByMonth.value.values()).filter(
      (row) => toNumberOrZero(row.income_total) > 0 || toNumberOrZero(row.expense_total) > 0,
    ).length;
    if (monthsWithLedger > 0) {
      return `Hay movimientos detectados en ${monthsWithLedger}/12 meses. El cierre los usa automáticamente y deja pendientes las líneas que necesitan revisión.`;
    }
    if (!expenseMonthlySummary.value) {
      return 'Cargando importes mensuales.';
    }
    return `Todavía no hay movimientos detectados. Hay datos manuales disponibles en ${expenseMonthlySummary.value.months_with_checkins}/12 meses para gastos.`;
  });

  const monthlyIncomeCoverageSummary = computed<MonthlyCoverageSummary>(() => {
    const total = monthlyIncomeExecutionEntries.value.length;
    const viaLedger = monthlyIncomeExecutionEntries.value.filter(
      (row) =>
        row.executionSource === 'categorized_ledger' ||
        row.executionSource === 'pending_classification',
    ).length;
    const viaFallback = monthlyIncomeExecutionEntries.value.filter(
      (row) => row.executionSource === 'legacy_fallback',
    ).length;
    const pending = total - viaLedger - viaFallback;
    return {
      total,
      viaLedger,
      viaFallback,
      pending,
      ratio: total > 0 ? (viaLedger + viaFallback) / total : 1,
    };
  });

  const monthlyExpenseCoverageSummary = computed<MonthlyCoverageSummary>(() => {
    const total = groupedMonthlyExpenseExecutionEntries.value.length;
    const viaLedger = groupedMonthlyExpenseExecutionEntries.value.filter(
      (group) => group.ledgerDetectedTotal > 0,
    ).length;
    const viaFallback = groupedMonthlyExpenseExecutionEntries.value.filter(
      (group) => group.ledgerDetectedTotal <= 0 && group.checkedCount > 0,
    ).length;
    const pending = total - viaLedger - viaFallback;
    return {
      total,
      viaLedger,
      viaFallback,
      pending,
      ratio: total > 0 ? (viaLedger + viaFallback) / total : 1,
    };
  });

  const monthlyIncomePendingClassification = computed<PendingClassificationSummary>(() => {
    return {
      amount: accountingExecutionBuckets.value.incomeUnclassifiedTotal,
      ambiguousRows: 0,
    };
  });

  const monthlyExpensePendingClassification = computed<PendingClassificationSummary>(() => {
    const ambiguousRows = monthlyExpenseExecutionEntries.value.filter(
      (row) => row.executionSource === 'pending_classification',
    ).length;
    const ambiguousAmount = monthlyExpenseExecutionEntries.value.reduce((sum, row) => {
      if (row.executionSource !== 'pending_classification') return sum;
      return sum + (row.categorizedLedgerExecuted ?? 0);
    }, 0);
    return {
      amount: ambiguousAmount + accountingExecutionBuckets.value.expenseUnclassifiedTotal,
      ambiguousRows,
    };
  });

  function isLockedExecutionRow(row: { executionOrigin: BudgetExecutionOrigin }): boolean {
    return row.executionOrigin === 'categorized_ledger' || row.executionOrigin === 'legacy_ledger';
  }

  function resolveCoverageMode(summary: MonthlyCoverageSummary): string {
    if (summary.total === 0 || summary.viaLedger + summary.viaFallback === 0) return 'none';
    if (summary.pending > 0) return 'partial';
    if (summary.viaLedger > 0 && summary.viaFallback > 0) return 'mixed';
    if (summary.viaLedger > 0) return 'ledger';
    return 'fallback';
  }

  function coverageBadgeLabel(summary: MonthlyCoverageSummary): string {
    const mode = resolveCoverageMode(summary);
    if (mode === 'ledger' || mode === 'fallback' || mode === 'mixed') return 'Completo';
    if (mode === 'partial') return 'Parcial';
    return 'Pendiente';
  }

  function coverageDetail(summary: MonthlyCoverageSummary): string {
    const mode = resolveCoverageMode(summary);
    if (mode === 'ledger' || mode === 'fallback' || mode === 'mixed') {
      return 'Todas las líneas del mes tienen importe registrado.';
    }
    if (mode === 'partial') {
      return 'Ya hay importes registrados; revisa solo las líneas pendientes.';
    }
    return 'Todavía no hay importes registrados para este mes.';
  }

  function executionSourceLabel(origin: BudgetExecutionOrigin): string {
    if (origin === 'categorized_ledger') return 'Movimientos';
    if (origin === 'legacy_ledger' || origin === 'legacy_checkin') return 'Manual';
    if (origin === 'ambiguous_taxonomy') return 'Pendiente clasificar';
    return '';
  }

  const monthlyExpenseCoverageLabel = computed(() =>
    coverageBadgeLabel(monthlyExpenseCoverageSummary.value),
  );
  const monthlyExpenseCoverageDetail = computed(() =>
    coverageDetail(monthlyExpenseCoverageSummary.value),
  );
  const monthlyIncomeCoverageLabel = computed(() =>
    coverageBadgeLabel(monthlyIncomeCoverageSummary.value),
  );
  const monthlyIncomeCoverageDetail = computed(() =>
    coverageDetail(monthlyIncomeCoverageSummary.value),
  );

  async function refreshAccountingExecutionData(): Promise<void> {
    accountingExecutionLoading.value = true;
    accountingExecutionError.value = null;
    try {
      const fetchAllTransactions = async (params: { year: number; status?: string }) => {
        const allResults: typeof accountingPostedEntries.value = [];
        let cursor: string | undefined;
        do {
          const response = await coreAccountingApi.getTransactions({
            ...params,
            page_size: 200,
            cursor,
          });
          allResults.push(
            ...(response.data.results ?? []).flatMap((transaction: LedgerTransaction) => {
              const bookingMonth = bookingMonthFromDate(transaction.booking_date);
              return transaction.entries.map((entry) => ({
                ...entry,
                bookingMonth,
                transactionId: transaction.id,
                transactionMemberTag: transaction.member_tag ?? '',
                transactionQuickEntryKind: transaction.quick_entry_kind ?? '',
                assetSubcategory: '',
              }));
            }),
          );
          cursor = response.data.next_cursor ?? undefined;
        } while (cursor);
        return allResults;
      };
      const [summaryResponse, transactionsResponse, assetsResponse] = await Promise.all([
        coreAccountingApi.getMonthlySummary(fiscalYear.value),
        fetchAllTransactions({
          year: fiscalYear.value,
          status: 'posted',
        }),
        coreNetWorthApi.getAssets(),
      ]);
      const assetSubcategoryById = new Map<number, string>();
      for (const asset of assetsResponse.data ?? []) {
        assetSubcategoryById.set(asset.id, asset.subcategory ?? '');
      }
      accountingMonthlySummary.value = summaryResponse.data ?? null;
      accountingPostedEntries.value = transactionsResponse.map((entry) => ({
        ...entry,
        assetSubcategory:
          entry.asset_id != null ? (assetSubcategoryById.get(entry.asset_id) ?? '') : '',
      }));
    } catch (e: unknown) {
      accountingExecutionError.value = toBudgetErrorMessage(e);
      accountingMonthlySummary.value = null;
      accountingPostedEntries.value = [];
    } finally {
      accountingExecutionLoading.value = false;
    }
  }

  async function refreshBudgetSuggestionData(): Promise<void> {
    budgetSuggestionsLoading.value = true;
    budgetSuggestionsError.value = null;
    try {
      const response = await coreAccountingApi.getBudgetSuggestions(fiscalYear.value, 2);
      budgetSuggestions.value = response.data ?? null;
    } catch (e: unknown) {
      budgetSuggestionsError.value = toBudgetErrorMessage(e);
      budgetSuggestions.value = null;
    } finally {
      budgetSuggestionsLoading.value = false;
    }
  }

  function formatMoney(value: number, decimals = 2): string {
    return new Intl.NumberFormat('es-ES', {
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
      useGrouping: true,
    }).format(Number.isFinite(value) ? value : 0);
  }

  function formatSignedMoney(value: number, decimals = 2): string {
    return `${value > 0 ? '+' : ''}${formatMoney(value, decimals)}`;
  }

  function formatPercent(value: number | null, decimals = 0): string {
    if (value == null || !Number.isFinite(value)) return '-';
    return new Intl.NumberFormat('es-ES', {
      style: 'percent',
      minimumFractionDigits: decimals,
      maximumFractionDigits: decimals,
    }).format(value);
  }

  function formatCompactMoney(value: number): string {
    const abs = Math.abs(value);
    if (abs >= 1_000_000) return `${formatMoney(value / 1_000_000, 1)} M`;
    if (abs >= 1_000) return `${formatMoney(value / 1_000, 1)} k`;
    return formatMoney(value, 0);
  }

  function clamp(value: number, min: number, max: number): number {
    return Math.min(max, Math.max(min, value));
  }

  function hashToUnitInterval(input: string): number {
    let hash = 0;
    for (let i = 0; i < input.length; i++) {
      hash = (hash * 31 + input.charCodeAt(i)) >>> 0;
    }
    return (hash % 1000) / 1000;
  }

  function executionToneFor(
    sectionId: BudgetSectionModel['id'],
    ratio: number,
  ): BudgetExecutionTone {
    if (!Number.isFinite(ratio) || ratio <= 0) return 'neutral';
    if (sectionId === 'expense') {
      if (ratio > 1.05) return 'danger';
      if (ratio >= 0.95) return 'warn';
      return 'good';
    }
    if (ratio >= 1) return 'good';
    if (ratio >= 0.85) return 'warn';
    return 'danger';
  }

  function mockExecutionRatio(sectionId: BudgetSectionModel['id'], seedKey: string): number {
    const u = hashToUnitInterval(seedKey);
    if (sectionId === 'expense') {
      if (u < 0.34) return 0.62 + u * 0.55;
      if (u < 0.72) return 0.86 + (u - 0.34) * 0.34;
      return 1.01 + (u - 0.72) * 0.62;
    }
    if (u < 0.34) return 0.62 + u * 0.5;
    if (u < 0.72) return 0.85 + (u - 0.34) * 0.34;
    return 1.0 + (u - 0.72) * 0.72;
  }

  function executionPreview(
    sectionId: BudgetSectionModel['id'],
    seedKey: string,
  ): BudgetExecutionPreview {
    const ratio = mockExecutionRatio(sectionId, seedKey);
    return {
      ratio,
      widthPct: clamp(ratio * 100, 8, 100),
      tone: executionToneFor(sectionId, ratio),
      overflow: ratio > 1,
    };
  }

  function aggregateBudgetRows<
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

  // eslint-disable-next-line complexity
  const incomeGroups = computed(() => {
    const groups = aggregateBudgetRows(
      filteredIncomeEntries.value,
      incomeCategoryLabels,
      incomeSubcategoryLabels,
    );
    const groupsByCategory = new Map(groups.map((group) => [group.categoryKey, group]));
    const monthsCount = Math.max(0, Math.min(12, budgetDetailMonth.value));

    for (const category of incomeExecutionBreakdownCategories.value) {
      for (const subcategory of category.subcategories) {
        if (subcategory.has_budgeted_line) continue;
        let detectedExecutedYtd = 0;
        for (const monthRow of subcategory.months) {
          if (monthRow.month < 1 || monthRow.month > monthsCount) continue;
          const weight = incomeExecutionTaxonomyWeight(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          if (weight <= 0) continue;
          const taxonomyKey = budgetMonthTaxonomyKey(
            monthRow.month,
            category.category,
            subcategory.subcategory,
          );
          const taxonomyExecuted =
            accountingExecutionBuckets.value.incomeCategorizedByMonthTaxonomy.get(taxonomyKey) ??
            null;
          let detectedChunk = 0;
          if (taxonomyExecuted != null) {
            detectedChunk = taxonomyExecuted * weight;
          } else {
            detectedChunk = toNumberOrZero(monthRow.executed_unbudgeted) * weight;
          }
          detectedExecutedYtd += detectedChunk;
        }
        if (detectedExecutedYtd <= 0) continue;

        const rowKey = `${category.category}::${subcategory.subcategory}`;
        let group = groupsByCategory.get(category.category);
        if (!group) {
          group = {
            categoryKey: category.category,
            categoryLabel:
              incomeCategoryLabels.get(category.category as never) ?? category.category,
            plannedAnnual: 0,
            shareOfSection: 0,
            rows: [],
          };
          groups.push(group);
          groupsByCategory.set(category.category, group);
        }
        const exists = group.rows.some((row) => row.key === rowKey);
        if (exists) continue;
        group.rows.push({
          key: rowKey,
          categoryKey: category.category,
          categoryLabel: incomeCategoryLabels.get(category.category as never) ?? category.category,
          subcategoryKey: subcategory.subcategory,
          subcategoryLabel:
            incomeSubcategoryLabels.get(subcategory.subcategory) ?? subcategory.subcategory,
          plannedAnnual: 0,
          itemsCount: 0,
          detectedUnbudgeted: true,
          detectedExecutedYtd,
        });
      }
    }

    for (const cat of incomeCategories) {
      const existingSubcatKeys = new Set(
        groupsByCategory.get(cat.value)?.rows.map((r: any) => r.subcategoryKey) ?? [],
      );
      const missing = incomeSubcategories.filter(
        (s) => s.category === cat.value && !existingSubcatKeys.has(s.value),
      );
      if (missing.length === 0) continue;
      let targetGroup = groupsByCategory.get(cat.value);
      if (!targetGroup) {
        targetGroup = {
          categoryKey: cat.value,
          categoryLabel: cat.label,
          plannedAnnual: 0,
          shareOfSection: 0,
          rows: [],
        };
        groups.push(targetGroup);
        groupsByCategory.set(cat.value, targetGroup);
      }
      for (const sub of missing) {
        targetGroup.rows.push({
          key: `${cat.value}::${sub.value}`,
          categoryKey: cat.value,
          categoryLabel: cat.label,
          subcategoryKey: sub.value,
          subcategoryLabel: sub.label,
          plannedAnnual: 0,
          itemsCount: 0,
        });
      }
    }

    for (const group of groups) {
      group.rows.sort((a, b) => {
        const orderDiff =
          incomeSubcategorySortIndex(a.subcategoryKey) -
          incomeSubcategorySortIndex(b.subcategoryKey);
        if (orderDiff !== 0) return orderDiff;
        return a.subcategoryLabel.localeCompare(b.subcategoryLabel, 'es');
      });
      group.plannedAnnual = group.rows.reduce((sum, row) => sum + row.plannedAnnual, 0);
    }
    const sectionTotal = groups.reduce((sum, group) => sum + group.plannedAnnual, 0);
    for (const group of groups) {
      group.shareOfSection = sectionTotal > 0 ? group.plannedAnnual / sectionTotal : 0;
    }
    return groups.sort((a, b) => {
      const orderDiff =
        incomeCategorySortIndex(a.categoryKey) - incomeCategorySortIndex(b.categoryKey);
      if (orderDiff !== 0) return orderDiff;
      return a.categoryLabel.localeCompare(b.categoryLabel, 'es');
    });
  });
  // eslint-disable-next-line complexity
  const expenseGroups = computed(() => {
    const groups = aggregateBudgetRows(
      filteredExpenseEntries.value,
      expenseCategoryLabels,
      expenseSubcategoryLabels,
    );
    const groupsByCategory = new Map(groups.map((group) => [group.categoryKey, group]));
    const monthsCount = Math.max(0, Math.min(12, budgetDetailMonth.value));

    for (const category of expenseExecutionBreakdownCategories.value) {
      for (const subcategory of category.subcategories) {
        if (subcategory.has_budgeted_line) continue;
        let detectedExecutedYtd = 0;
        for (const monthRow of subcategory.months) {
          if (monthRow.month < 1 || monthRow.month > monthsCount) continue;
          detectedExecutedYtd += toNumberOrZero(monthRow.executed_unbudgeted);
        }
        if (detectedExecutedYtd <= 0) continue;

        const rowKey = `${category.category}::${subcategory.subcategory}`;
        let group = groupsByCategory.get(category.category);
        if (!group) {
          group = {
            categoryKey: category.category,
            categoryLabel:
              expenseCategoryLabels.get(category.category as never) ?? category.category,
            plannedAnnual: 0,
            shareOfSection: 0,
            rows: [],
          };
          groups.push(group);
          groupsByCategory.set(category.category, group);
        }
        const exists = group.rows.some((row) => row.key === rowKey);
        if (exists) continue;
        group.rows.push({
          key: rowKey,
          categoryKey: category.category,
          categoryLabel: expenseCategoryLabels.get(category.category as never) ?? category.category,
          subcategoryKey: subcategory.subcategory,
          subcategoryLabel:
            expenseSubcategoryLabels.get(subcategory.subcategory) ?? subcategory.subcategory,
          plannedAnnual: 0,
          itemsCount: 0,
          detectedUnbudgeted: true,
          detectedExecutedYtd,
        });
      }
    }

    for (const cat of expenseCategories) {
      const existingSubcatKeys = new Set(
        groupsByCategory.get(cat.value)?.rows.map((r: any) => r.subcategoryKey) ?? [],
      );
      const missing = expenseSubcategories.filter(
        (s) => s.category === cat.value && !existingSubcatKeys.has(s.value),
      );
      if (missing.length === 0) continue;
      let targetGroup = groupsByCategory.get(cat.value);
      if (!targetGroup) {
        targetGroup = {
          categoryKey: cat.value,
          categoryLabel: cat.label,
          plannedAnnual: 0,
          shareOfSection: 0,
          rows: [],
        };
        groups.push(targetGroup);
        groupsByCategory.set(cat.value, targetGroup);
      }
      for (const sub of missing) {
        targetGroup.rows.push({
          key: `${cat.value}::${sub.value}`,
          categoryKey: cat.value,
          categoryLabel: cat.label,
          subcategoryKey: sub.value,
          subcategoryLabel: sub.label,
          plannedAnnual: 0,
          itemsCount: 0,
        });
      }
    }

    for (const group of groups) {
      group.rows.sort((a, b) => {
        const aDetected = a.detectedUnbudgeted ? 1 : 0;
        const bDetected = b.detectedUnbudgeted ? 1 : 0;
        if (aDetected !== bDetected) return bDetected - aDetected;
        if (b.plannedAnnual !== a.plannedAnnual) return b.plannedAnnual - a.plannedAnnual;
        const aDetectedAmount = a.detectedExecutedYtd ?? 0;
        const bDetectedAmount = b.detectedExecutedYtd ?? 0;
        if (bDetectedAmount !== aDetectedAmount) return bDetectedAmount - aDetectedAmount;
        return a.subcategoryLabel.localeCompare(b.subcategoryLabel, 'es');
      });
      group.plannedAnnual = group.rows.reduce((sum, row) => sum + row.plannedAnnual, 0);
    }
    const sectionTotal = groups.reduce((sum, group) => sum + group.plannedAnnual, 0);
    for (const group of groups) {
      group.shareOfSection = sectionTotal > 0 ? group.plannedAnnual / sectionTotal : 0;
    }
    return groups
      .filter((g) => g.categoryKey !== 'savings_allocation')
      .sort((a, b) => {
        const orderDiff =
          expenseCategorySortIndex(a.categoryKey) - expenseCategorySortIndex(b.categoryKey);
        if (orderDiff !== 0) return orderDiff;
        return a.categoryLabel.localeCompare(b.categoryLabel, 'es');
      });
  });

  const expenseExecutionYtdTotals = computed(() => {
    let planned = 0;
    let executedBudgeted = 0;
    let executedUnbudgeted = 0;
    for (const row of expenseYtdActualBySubcategoryKey.value.values()) {
      planned += row.planned;
      executedBudgeted += row.executedBudgeted;
      executedUnbudgeted += row.executedUnbudgeted;
    }
    const executedTotal = executedBudgeted + executedUnbudgeted;
    return {
      planned,
      executedBudgeted,
      executedUnbudgeted,
      executedTotal,
    };
  });

  const incomeExecutionYtdTotals = computed(() => {
    let planned = 0;
    let executedBudgeted = 0;
    let executedUnbudgeted = 0;
    for (const row of incomeYtdActualBySubcategoryKey.value.values()) {
      planned += row.planned;
      executedBudgeted += row.executedBudgeted;
      executedUnbudgeted += row.executedUnbudgeted;
    }
    const executedTotal = executedBudgeted + executedUnbudgeted;
    return {
      planned,
      executedBudgeted,
      executedUnbudgeted,
      executedTotal,
    };
  });

  function viewModeLabel(mode: BudgetEntryViewMode): string {
    if (mode === 'recurrent') return 'Solo recurrentes';
    if (mode === 'one_off') return 'Solo puntuales';
    return 'Todos';
  }

  function incomeCategorySortIndex(categoryKey: string): number {
    return (
      incomeCategoryOrderIndex.get(categoryKey as (typeof incomeCategoryDisplayOrder)[number]) ??
      999
    );
  }

  function incomeSubcategorySortIndex(subcategoryKey: string): number {
    return incomeSubcategoryOrderIndex.get(subcategoryKey) ?? 999;
  }

  function expenseCategorySortIndex(categoryKey: string): number {
    return (
      expenseCategoryOrderIndex.get(categoryKey as (typeof expenseCategoryDisplayOrder)[number]) ??
      999
    );
  }

  function incomeInvestmentRotationCategoryAdjustment(
    sectionId: BudgetSectionModel['id'],
    categoryKey: string,
  ): number {
    if (sectionId !== 'income') return 0;
    return incomeInvestmentRotationAdjustmentByCategory.value.get(categoryKey) ?? 0;
  }

  function incomeInvestmentRotationSubcategoryAdjustment(
    sectionId: BudgetSectionModel['id'],
    rowKey: string,
  ): number {
    if (sectionId !== 'income') return 0;
    return incomeInvestmentRotationAdjustmentBySubcategoryKey.value.get(rowKey) ?? 0;
  }

  function isSectionExpanded(sectionId: BudgetSectionModel['id']): boolean {
    return sectionId === 'income' ? incomeDetailsExpanded.value : expenseDetailsExpanded.value;
  }

  function toggleSectionExpanded(sectionId: BudgetSectionModel['id']): void {
    if (sectionId === 'income') {
      incomeDetailsExpanded.value = !incomeDetailsExpanded.value;
      return;
    }
    expenseDetailsExpanded.value = !expenseDetailsExpanded.value;
  }

  const sections = computed<BudgetSectionModel[]>(() => [
    {
      id: 'income',
      title: 'Ingresos',
      subtitle: 'Detalle previsto por categorías y subcategorías del balance anual',
      emptyMessage: 'No hay ingresos anuales cargados para este ejercicio.',
      toneClass: 'ui-budget-section-income',
      totalAnnual: plannedIncomeTotal.value,
      filterMode: incomeViewMode.value,
      categoryCount: incomeGroups.value.length,
      subcategoryCount: incomeGroups.value.reduce((sum, group) => sum + group.rows.length, 0),
      groups: incomeGroups.value,
    },
    {
      id: 'expense',
      title: 'Gastos',
      subtitle: 'Detalle previsto por categorías y subcategorías del balance anual',
      emptyMessage: 'No hay gastos anuales cargados para este ejercicio.',
      toneClass: 'ui-budget-section-expense',
      totalAnnual: plannedExpenseTotal.value,
      filterMode: expenseViewMode.value,
      categoryCount: expenseGroups.value.length,
      subcategoryCount: expenseGroups.value.reduce((sum, group) => sum + group.rows.length, 0),
      groups: expenseGroups.value,
    },
  ]);

  const budgetSuggestionBySubcategory = computed(() => {
    const income = new Map<string, BudgetSuggestionSubcategoryRow>();
    const expense = new Map<string, BudgetSuggestionSubcategoryRow>();
    for (const row of budgetSuggestions.value?.income.subcategories ?? []) {
      income.set(`${row.category}:${row.subcategory}`, row);
    }
    for (const row of budgetSuggestions.value?.expense.subcategories ?? []) {
      expense.set(`${row.category}:${row.subcategory}`, row);
    }
    return { income, expense };
  });

  const incomeBudgetSuggestions = computed(() =>
    incomeGroups.value
      .flatMap((group) =>
        group.rows.map((row) => {
          const key = `${row.categoryKey}:${row.subcategoryKey}`;
          const suggestion = budgetSuggestionBySubcategory.value.income.get(key);
          if (!suggestion) return null;
          return {
            key,
            subcategoryLabel: row.subcategoryLabel,
            plannedAnnual: row.plannedAnnual,
            suggestedAnnual: toNumberOrZero(suggestion.suggested_annual),
            observedMonths: suggestion.observed_months,
          };
        }),
      )
      .filter((row): row is NonNullable<typeof row> => row != null)
      .sort(
        (a, b) =>
          Math.abs(b.suggestedAnnual - b.plannedAnnual) -
          Math.abs(a.suggestedAnnual - a.plannedAnnual),
      )
      .slice(0, 6),
  );

  const expenseBudgetSuggestions = computed(() =>
    expenseGroups.value
      .flatMap((group) =>
        group.rows.map((row) => {
          const key = `${row.categoryKey}:${row.subcategoryKey}`;
          const suggestion = budgetSuggestionBySubcategory.value.expense.get(key);
          if (!suggestion) return null;
          return {
            key,
            subcategoryLabel: row.subcategoryLabel,
            plannedAnnual: row.plannedAnnual,
            suggestedAnnual: toNumberOrZero(suggestion.suggested_annual),
            observedMonths: suggestion.observed_months,
          };
        }),
      )
      .filter((row): row is NonNullable<typeof row> => row != null)
      .sort(
        (a, b) =>
          Math.abs(b.suggestedAnnual - b.plannedAnnual) -
          Math.abs(a.suggestedAnnual - a.plannedAnnual),
      )
      .slice(0, 6),
  );

  const hasAnyPlannedData = computed(
    () => plannedIncomeTotal.value > 0 || plannedExpenseTotal.value > 0,
  );

  const closeStatus = computed(() => monthlyCloseData.value?.monthly_close.status ?? null);
  const isCloseLocked = computed(
    () => closeStatus.value === 'finalized' || closeStatus.value === 'locked',
  );
  const hasDistributionSuggestion = computed(() => {
    const s = monthlyCloseData.value?.suggestions;
    if (!s) return false;
    return Object.keys(s.income).length > 0 || Object.keys(s.expense).length > 0;
  });

  const activeViewSummary = computed(
    () =>
      `Ingresos: ${viewModeLabel(incomeViewMode.value)} - Gastos: ${viewModeLabel(expenseViewMode.value)}`,
  );

  async function refreshBudgetData(year = fiscalYear.value): Promise<void> {
    await Promise.all([incomeStore.loadAll(year), expenseStore.loadAll(year)]);
  }

  async function loadIncomeCheckinsForSelectedMonth(): Promise<void> {
    try {
      const response = await budgetApi.get<IncomeMonthlyCheckinApiItem[]>(
        '/api/budget/annual-income-checkins/',
        {
          params: { year: fiscalYear.value, month: selectedExecutionMonth.value },
        },
      );
      const nextMap: Record<number, IncomeMonthlyCheckinApiItem> = {};
      for (const row of response.data ?? []) nextMap[row.annual_income_entry_id] = row;
      incomeCheckinsByEntryId.value = nextMap;
    } catch (e: unknown) {
      incomeExecutionError.value = toBudgetErrorMessage(e);
    }
  }

  function incomeEntryMonthKey(entryId: number, month: number): string {
    return `${entryId}:${month}`;
  }

  function expenseEntryMonthKey(entryId: number, month: number): string {
    return `${entryId}:${month}`;
  }

  async function loadIncomeCheckinsForYear(): Promise<void> {
    try {
      const response = await budgetApi.get<IncomeMonthlyCheckinApiItem[]>(
        '/api/budget/annual-income-checkins/',
        {
          params: { year: fiscalYear.value },
        },
      );
      const nextMap: Record<string, IncomeMonthlyCheckinApiItem> = {};
      for (const row of response.data ?? []) {
        nextMap[incomeEntryMonthKey(row.annual_income_entry_id, row.month)] = row;
      }
      incomeCheckinsByEntryMonth.value = nextMap;
    } catch (e: unknown) {
      incomeExecutionError.value = toBudgetErrorMessage(e);
    }
  }

  async function loadIncomeExecutionSummary(year = fiscalYear.value): Promise<void> {
    try {
      const response = await budgetApi.get<IncomeMonthlySummaryResponse>(
        '/api/budget/annual-income/monthly-summary/',
        { params: { year } },
      );
      incomeMonthlySummary.value = response.data ?? null;
    } catch (e: unknown) {
      incomeExecutionError.value = toBudgetErrorMessage(e);
    }
  }

  async function refreshIncomeExecutionData(): Promise<void> {
    incomeExecutionLoading.value = true;
    incomeExecutionError.value = null;
    try {
      await Promise.all([
        loadIncomeExecutionSummary(),
        loadIncomeCheckinsForYear(),
        loadIncomeCheckinsForSelectedMonth(),
      ]);
    } finally {
      incomeExecutionLoading.value = false;
    }
  }

  async function loadExpenseExecutionSummary(year = fiscalYear.value): Promise<void> {
    try {
      const response = await budgetApi.get<ExpenseMonthlySummaryResponse>(
        '/api/budget/annual-expense/monthly-summary/',
        { params: { year } },
      );
      expenseMonthlySummary.value = response.data ?? null;
    } catch (e: unknown) {
      expenseExecutionError.value = toBudgetErrorMessage(e);
    }
  }

  async function loadExpenseCheckinsForSelectedMonth(): Promise<void> {
    try {
      const response = await budgetApi.get<ExpenseMonthlyCheckinApiItem[]>(
        '/api/budget/annual-expense-checkins/',
        {
          params: { year: fiscalYear.value, month: selectedExecutionMonth.value },
        },
      );
      const nextMap: Record<number, ExpenseMonthlyCheckinApiItem> = {};
      for (const row of response.data ?? []) {
        nextMap[row.annual_expense_entry_id] = row;
      }
      expenseCheckinsByEntryId.value = nextMap;
    } catch (e: unknown) {
      expenseExecutionError.value = toBudgetErrorMessage(e);
    }
  }

  async function loadExpenseCheckinsForYear(): Promise<void> {
    try {
      const response = await budgetApi.get<ExpenseMonthlyCheckinApiItem[]>(
        '/api/budget/annual-expense-checkins/',
        { params: { year: fiscalYear.value } },
      );
      const nextMap: Record<string, ExpenseMonthlyCheckinApiItem> = {};
      for (const row of response.data ?? []) {
        nextMap[expenseEntryMonthKey(row.annual_expense_entry_id, row.month)] = row;
      }
      expenseCheckinsByEntryMonth.value = nextMap;
    } catch (e: unknown) {
      expenseExecutionError.value = toBudgetErrorMessage(e);
    }
  }

  async function refreshExpenseExecutionData(): Promise<void> {
    expenseExecutionLoading.value = true;
    expenseExecutionError.value = null;
    try {
      await Promise.all([
        loadExpenseExecutionSummary(),
        loadExpenseCheckinsForSelectedMonth(),
        loadExpenseCheckinsForYear(),
      ]);
    } finally {
      expenseExecutionLoading.value = false;
    }
  }

  function suggestedExecutedAmountForRow(
    row: (typeof monthlyExpenseExecutionEntries.value)[number],
  ): string {
    if (row.checkin?.status === 'skipped') return '0.00';
    if (row.executed != null) return row.executed.toFixed(2);
    return row.planned.toFixed(2);
  }

  function ensureExpenseAdjustAmountPrefilled(
    row: (typeof monthlyExpenseExecutionEntries.value)[number],
  ): void {
    const current = String(expenseAdjustAmounts.value[row.entry.id] ?? '').trim();
    if (current) return;
    expenseAdjustAmounts.value[row.entry.id] = suggestedExecutedAmountForRow(row);
  }

  function parseDecimalInput(raw: string): number | null {
    const normalized = raw.trim().replace(',', '.');
    if (!normalized) return null;
    const value = Number(normalized);
    if (!Number.isFinite(value) || value < 0) return null;
    return value;
  }

  function checkinStatusLabel(
    status: ExpenseMonthlyCheckinApiItem['status'] | IncomeMonthlyCheckinApiItem['status'],
  ): string {
    if (status === 'confirmed') return 'Confirmado';
    if (status === 'adjusted') return 'Ajustado';
    if (status === 'estimated') return 'Estimado';
    return 'No ocurrió';
  }

  function incomeCheckinRowSummary(
    row: (typeof monthlyIncomeExecutionEntries.value)[number],
  ): string {
    const subcategory = incomeSubcategoryLabels.get(row.entry.subcategory) ?? row.entry.subcategory;
    return `${subcategory} - ${row.entry.name}`;
  }

  function suggestedIncomeExecutedAmountForRow(
    row: (typeof monthlyIncomeExecutionEntries.value)[number],
  ): string {
    if (row.checkin?.status === 'skipped') return '0.00';
    if (row.executed != null) return row.executed.toFixed(2);
    return row.planned.toFixed(2);
  }

  function ensureIncomeAdjustAmountPrefilled(
    row: (typeof monthlyIncomeExecutionEntries.value)[number],
  ): void {
    const current = String(incomeAdjustAmounts.value[row.entry.id] ?? '').trim();
    if (current) return;
    incomeAdjustAmounts.value[row.entry.id] = suggestedIncomeExecutedAmountForRow(row);
  }

  function ensureIncomeGroupAdjustAmountPrefilled(
    group: (typeof groupedMonthlyIncomeExecutionEntries.value)[number],
  ): void {
    if (!group.editableRow) return;
    const current = String(incomeAdjustAmounts.value[group.editableRow.entry.id] ?? '').trim();
    if (current) return;
    incomeAdjustAmounts.value[group.editableRow.entry.id] = Math.max(
      group.executedTotal - group.ledgerDetectedTotal,
      0,
    ).toFixed(2);
  }

  function cacheIncomeCheckin(checkin: IncomeMonthlyCheckinApiItem): void {
    incomeCheckinsByEntryId.value = {
      ...incomeCheckinsByEntryId.value,
      [checkin.annual_income_entry_id]: checkin,
    };
    incomeCheckinsByEntryMonth.value = {
      ...incomeCheckinsByEntryMonth.value,
      [incomeEntryMonthKey(checkin.annual_income_entry_id, checkin.month)]: checkin,
    };
  }

  function removeCachedIncomeCheckin(checkin: IncomeMonthlyCheckinApiItem): void {
    const nextByEntryId = { ...incomeCheckinsByEntryId.value };
    delete nextByEntryId[checkin.annual_income_entry_id];
    incomeCheckinsByEntryId.value = nextByEntryId;

    const nextByEntryMonth = { ...incomeCheckinsByEntryMonth.value };
    delete nextByEntryMonth[incomeEntryMonthKey(checkin.annual_income_entry_id, checkin.month)];
    incomeCheckinsByEntryMonth.value = nextByEntryMonth;
  }

  async function clearIncomeCheckin(
    row: (typeof monthlyIncomeExecutionEntries.value)[number],
  ): Promise<void> {
    const existing = incomeCheckinsByEntryId.value[row.entry.id];
    if (!existing) return;
    incomeExecutionBusyEntryId.value = row.entry.id;
    incomeExecutionError.value = null;
    try {
      await budgetApi.delete(`/api/budget/annual-income-checkins/${existing.id}/`);
      await refreshIncomeExecutionData();
    } catch (e: unknown) {
      incomeExecutionError.value = toBudgetErrorMessage(e);
    } finally {
      incomeExecutionBusyEntryId.value = null;
    }
  }

  async function clearIncomeGroupCheckins(
    group: (typeof groupedMonthlyIncomeExecutionEntries.value)[number],
  ): Promise<void> {
    const existingCheckins = group.rows
      .map((row) => incomeCheckinsByEntryId.value[row.entry.id])
      .filter((checkin): checkin is IncomeMonthlyCheckinApiItem => !!checkin);
    if (!existingCheckins.length) return;
    const firstCheckin = existingCheckins[0];
    const busyEntryId = group.editableRow?.entry.id ?? firstCheckin?.annual_income_entry_id;
    if (busyEntryId == null) return;
    incomeExecutionBusyEntryId.value = busyEntryId;
    incomeExecutionError.value = null;
    try {
      await Promise.all(
        existingCheckins.map((checkin) =>
          budgetApi.delete(`/api/budget/annual-income-checkins/${checkin.id}/`),
        ),
      );
      for (const checkin of existingCheckins) removeCachedIncomeCheckin(checkin);
    } catch (e: unknown) {
      incomeExecutionError.value = toBudgetErrorMessage(e);
    } finally {
      incomeExecutionBusyEntryId.value = null;
    }
  }

  async function upsertIncomeCheckin(
    row: (typeof monthlyIncomeExecutionEntries.value)[number],
    status: 'confirmed' | 'adjusted',
  ): Promise<void> {
    incomeExecutionError.value = null;
    incomeExecutionBusyEntryId.value = row.entry.id;
    try {
      const parsed = parseDecimalInput(
        String(incomeAdjustAmounts.value[row.entry.id] ?? '').trim(),
      );
      if (parsed == null) {
        incomeExecutionError.value =
          'Indica un importe valido para confirmar (por ejemplo 123,45).';
        return;
      }
      incomeAdjustAmounts.value[row.entry.id] = parsed.toFixed(2);
      const payload = {
        annual_income_entry_id: row.entry.id,
        fiscal_year: fiscalYear.value,
        month: selectedExecutionMonth.value,
        status,
        executed_amount: parsed.toFixed(2),
      };
      const existing = incomeCheckinsByEntryId.value[row.entry.id];
      if (existing)
        await budgetApi.patch(`/api/budget/annual-income-checkins/${existing.id}/`, payload);
      else await budgetApi.post('/api/budget/annual-income-checkins/', payload);
      await refreshIncomeExecutionData();
    } catch (e: unknown) {
      incomeExecutionError.value = toBudgetErrorMessage(e);
    } finally {
      incomeExecutionBusyEntryId.value = null;
    }
  }

  async function saveIncomeCheckinFromInput(
    row: (typeof monthlyIncomeExecutionEntries.value)[number],
  ): Promise<void> {
    ensureIncomeAdjustAmountPrefilled(row);
    const parsed = parseDecimalInput(String(incomeAdjustAmounts.value[row.entry.id] ?? '').trim());
    if (parsed == null) {
      incomeExecutionError.value = 'Indica un importe valido para confirmar (por ejemplo 123,45).';
      return;
    }
    incomeAdjustAmounts.value[row.entry.id] = parsed.toFixed(2);
    const status = amountsEqualCents(parsed, row.planned) ? 'confirmed' : 'adjusted';
    await upsertIncomeCheckin(row, status);
  }

  async function saveIncomeGroupCheckinFromInput(
    group: (typeof groupedMonthlyIncomeExecutionEntries.value)[number],
  ): Promise<void> {
    if (!group.editableRow) return;
    ensureIncomeGroupAdjustAmountPrefilled(group);
    const parsed = parseDecimalInput(
      String(incomeAdjustAmounts.value[group.editableRow.entry.id] ?? '').trim(),
    );
    if (parsed == null) {
      incomeExecutionError.value = 'Indica un importe valido para confirmar (por ejemplo 123,45).';
      return;
    }
    incomeAdjustAmounts.value[group.editableRow.entry.id] = parsed.toFixed(2);
    const totalExecuted = group.ledgerDetectedTotal + parsed;
    incomeAdjustAmounts.value[group.editableRow.entry.id] = totalExecuted.toFixed(2);
    const status = amountsEqualCents(totalExecuted, group.plannedTotal) ? 'confirmed' : 'adjusted';
    await upsertIncomeCheckin(group.editableRow, status);
    setIncomeGroupUnlocked(group.key, false);
  }

  async function markIncomeGroupAsSkipped(
    group: (typeof groupedMonthlyIncomeExecutionEntries.value)[number],
  ): Promise<void> {
    const editableEntryId = group.editableRow?.entry.id;
    if (editableEntryId == null) return;
    incomeExecutionBusyEntryId.value = editableEntryId;
    incomeExecutionError.value = null;
    try {
      const responses = await Promise.all(
        group.rows.map((row) => {
          const payload = {
            annual_income_entry_id: row.entry.id,
            fiscal_year: fiscalYear.value,
            month: selectedExecutionMonth.value,
            status: 'skipped' as const,
            executed_amount: null,
          };
          const existing = incomeCheckinsByEntryId.value[row.entry.id];
          if (existing) {
            return budgetApi.patch<IncomeMonthlyCheckinApiItem>(
              `/api/budget/annual-income-checkins/${existing.id}/`,
              payload,
            );
          }
          return budgetApi.post<IncomeMonthlyCheckinApiItem>(
            '/api/budget/annual-income-checkins/',
            payload,
          );
        }),
      );
      setIncomeGroupUnlocked(group.key, false);
      for (const response of responses) cacheIncomeCheckin(response.data);
    } catch (e: unknown) {
      incomeExecutionError.value = toBudgetErrorMessage(e);
    } finally {
      incomeExecutionBusyEntryId.value = null;
    }
  }

  async function onIncomeGroupReviewedToggle(
    group: (typeof groupedMonthlyIncomeExecutionEntries.value)[number],
    checked: boolean,
  ): Promise<void> {
    if (checked) {
      await markIncomeGroupAsSkipped(group);
      return;
    }
    await clearIncomeGroupCheckins(group);
  }

  async function onIncomeCheckinCheckboxToggle(
    row: (typeof monthlyIncomeExecutionEntries.value)[number],
    checked: boolean,
  ): Promise<void> {
    if (checked) {
      await saveIncomeCheckinFromInput(row);
      return;
    }
    await clearIncomeCheckin(row);
  }

  async function onIncomeAdjustAmountBlur(
    row: (typeof monthlyIncomeExecutionEntries.value)[number],
  ): Promise<void> {
    if (!incomeCheckinsByEntryId.value[row.entry.id]) return;
    await saveIncomeCheckinFromInput(row);
  }

  async function resetIncomeCheckinDraftValue(
    row: (typeof monthlyIncomeExecutionEntries.value)[number],
    mode: 'zero' | 'planned',
  ): Promise<void> {
    incomeAdjustAmounts.value[row.entry.id] = mode === 'zero' ? '0.00' : row.planned.toFixed(2);
    if (incomeCheckinsByEntryId.value[row.entry.id]) await clearIncomeCheckin(row);
  }

  async function resetIncomeGroupCheckinDraftValue(
    group: (typeof groupedMonthlyIncomeExecutionEntries.value)[number],
    mode: 'zero' | 'planned',
  ): Promise<void> {
    if (!group.editableRow) return;
    incomeAdjustAmounts.value[group.editableRow.entry.id] =
      mode === 'zero'
        ? '0.00'
        : Math.max(group.plannedTotal - group.ledgerDetectedTotal, 0).toFixed(2);
  }

  function unlockIncomeGroupManualAdjustment(
    group: (typeof groupedMonthlyIncomeExecutionEntries.value)[number],
  ): void {
    ensureIncomeGroupAdjustAmountPrefilled(group);
    setIncomeGroupUnlocked(group.key, true);
  }

  async function relockIncomeGroupManualAdjustment(
    group: (typeof groupedMonthlyIncomeExecutionEntries.value)[number],
  ): Promise<void> {
    setIncomeGroupUnlocked(group.key, false);
    await clearIncomeGroupCheckins(group);
  }

  function cleanedExpenseCheckinName(name: string): string {
    return name.replace(/^Compromiso pasivo:\s*/i, '').trim();
  }

  function shortExpenseCategoryLabel(category: string): string {
    if (category === 'real_estate_assets') return 'Activos inmobiliarios';
    if (category === 'tangible_assets') return 'Activos mobiliarios';
    if (category === 'consumption_expenses') return 'Gastos';
    if (category === 'financial_investments') return 'Inversion financiera';
    if (category === 'savings_allocation') return 'Ahorro';
    return (
      expenseCategoryLabels.get(category as (typeof expenseCategories)[number]['value']) ?? category
    );
  }

  function expenseCheckinCategorySortWeight(category: string): number {
    if (category === 'real_estate_assets') return 0; // Act. Inm
    if (category === 'tangible_assets') return 1; // Act. mob
    if (category === 'financial_investments') return 2; // Inversiones
    if (category === 'consumption_expenses') return 3; // Gastos
    if (category === 'savings_allocation') return 4; // Ahorro
    return 99;
  }

  function amountsEqualCents(left: number, right: number): boolean {
    return Math.round(left * 100) === Math.round(right * 100);
  }

  function expenseCheckinRowSummary(
    row: (typeof monthlyExpenseExecutionEntries.value)[number],
  ): string {
    const name = cleanedExpenseCheckinName(row.entry.name);
    const subcategory =
      expenseSubcategoryLabels.get(row.entry.subcategory) ?? row.entry.subcategory;
    return `${subcategory} - ${name}`;
  }

  function cacheExpenseCheckin(checkin: ExpenseMonthlyCheckinApiItem): void {
    expenseCheckinsByEntryId.value = {
      ...expenseCheckinsByEntryId.value,
      [checkin.annual_expense_entry_id]: checkin,
    };
    expenseCheckinsByEntryMonth.value = {
      ...expenseCheckinsByEntryMonth.value,
      [expenseEntryMonthKey(checkin.annual_expense_entry_id, checkin.month)]: checkin,
    };
  }

  function removeCachedExpenseCheckin(checkin: ExpenseMonthlyCheckinApiItem): void {
    const nextByEntryId = { ...expenseCheckinsByEntryId.value };
    delete nextByEntryId[checkin.annual_expense_entry_id];
    expenseCheckinsByEntryId.value = nextByEntryId;

    const nextByEntryMonth = { ...expenseCheckinsByEntryMonth.value };
    delete nextByEntryMonth[expenseEntryMonthKey(checkin.annual_expense_entry_id, checkin.month)];
    expenseCheckinsByEntryMonth.value = nextByEntryMonth;
  }

  async function clearExpenseCheckin(
    row: (typeof monthlyExpenseExecutionEntries.value)[number],
  ): Promise<void> {
    const existing = expenseCheckinsByEntryId.value[row.entry.id];
    if (!existing) return;
    expenseExecutionBusyEntryId.value = row.entry.id;
    expenseExecutionError.value = null;
    try {
      await budgetApi.delete(`/api/budget/annual-expense-checkins/${existing.id}/`);
      await refreshExpenseExecutionData();
    } catch (e: unknown) {
      expenseExecutionError.value = toBudgetErrorMessage(e);
    } finally {
      expenseExecutionBusyEntryId.value = null;
    }
  }

  async function clearExpenseGroupCheckins(
    group: (typeof groupedMonthlyExpenseExecutionEntries.value)[number],
  ): Promise<void> {
    const existingCheckins = group.rows
      .map((row) => expenseCheckinsByEntryId.value[row.entry.id])
      .filter((checkin): checkin is ExpenseMonthlyCheckinApiItem => !!checkin);
    if (!existingCheckins.length) return;
    const firstCheckin = existingCheckins[0];
    const busyEntryId = group.editableRow?.entry.id ?? firstCheckin?.annual_expense_entry_id;
    if (busyEntryId == null) return;
    expenseExecutionBusyEntryId.value = busyEntryId;
    expenseExecutionError.value = null;
    try {
      await Promise.all(
        existingCheckins.map((checkin) =>
          budgetApi.delete(`/api/budget/annual-expense-checkins/${checkin.id}/`),
        ),
      );
      for (const checkin of existingCheckins) removeCachedExpenseCheckin(checkin);
    } catch (e: unknown) {
      expenseExecutionError.value = toBudgetErrorMessage(e);
    } finally {
      expenseExecutionBusyEntryId.value = null;
    }
  }

  function ensureExpenseGroupAdjustAmountPrefilled(
    group: (typeof groupedMonthlyExpenseExecutionEntries.value)[number],
  ): void {
    if (!group.editableRow) return;
    const current = String(expenseAdjustAmounts.value[group.editableRow.entry.id] ?? '').trim();
    if (current) return;
    expenseAdjustAmounts.value[group.editableRow.entry.id] = Math.max(
      group.executedTotal - group.ledgerDetectedTotal,
      0,
    ).toFixed(2);
  }

  function setExpenseAdjustAmountZero(
    row: (typeof monthlyExpenseExecutionEntries.value)[number],
  ): void {
    expenseAdjustAmounts.value[row.entry.id] = '0.00';
  }

  function setExpenseAdjustAmountPlanned(
    row: (typeof monthlyExpenseExecutionEntries.value)[number],
  ): void {
    expenseAdjustAmounts.value[row.entry.id] = row.planned.toFixed(2);
  }

  async function resetExpenseCheckinDraftValue(
    row: (typeof monthlyExpenseExecutionEntries.value)[number],
    mode: 'zero' | 'planned',
  ): Promise<void> {
    if (mode === 'zero') setExpenseAdjustAmountZero(row);
    else setExpenseAdjustAmountPlanned(row);
    if (expenseCheckinsByEntryId.value[row.entry.id]) {
      await clearExpenseCheckin(row);
    }
  }

  async function resetExpenseGroupCheckinDraftValue(
    group: (typeof groupedMonthlyExpenseExecutionEntries.value)[number],
    mode: 'zero' | 'planned',
  ): Promise<void> {
    if (!group.editableRow) return;
    expenseAdjustAmounts.value[group.editableRow.entry.id] =
      mode === 'zero'
        ? '0.00'
        : Math.max(group.plannedTotal - group.ledgerDetectedTotal, 0).toFixed(2);
  }

  async function saveExpenseCheckinFromInput(
    row: (typeof monthlyExpenseExecutionEntries.value)[number],
  ): Promise<void> {
    ensureExpenseAdjustAmountPrefilled(row);
    const rawAdjusted = String(expenseAdjustAmounts.value[row.entry.id] ?? '').trim();
    const parsedAdjusted = parseDecimalInput(rawAdjusted);
    if (parsedAdjusted == null) {
      expenseExecutionError.value = 'Indica un importe valido para confirmar (por ejemplo 123,45).';
      return;
    }
    expenseAdjustAmounts.value[row.entry.id] = parsedAdjusted.toFixed(2);
    const status = amountsEqualCents(parsedAdjusted, row.planned) ? 'confirmed' : 'adjusted';
    await upsertExpenseCheckin(row, status);
  }

  async function saveExpenseGroupCheckinFromInput(
    group: (typeof groupedMonthlyExpenseExecutionEntries.value)[number],
  ): Promise<void> {
    if (!group.editableRow) return;
    ensureExpenseGroupAdjustAmountPrefilled(group);
    const parsed = parseDecimalInput(
      String(expenseAdjustAmounts.value[group.editableRow.entry.id] ?? '').trim(),
    );
    if (parsed == null) {
      expenseExecutionError.value = 'Indica un importe valido para confirmar (por ejemplo 123,45).';
      return;
    }
    expenseAdjustAmounts.value[group.editableRow.entry.id] = parsed.toFixed(2);
    const totalExecuted = group.ledgerDetectedTotal + parsed;
    expenseAdjustAmounts.value[group.editableRow.entry.id] = totalExecuted.toFixed(2);
    const status = amountsEqualCents(totalExecuted, group.plannedTotal) ? 'confirmed' : 'adjusted';
    await upsertExpenseCheckin(group.editableRow, status);
    setExpenseGroupUnlocked(group.key, false);
  }

  async function markExpenseGroupAsSkipped(
    group: (typeof groupedMonthlyExpenseExecutionEntries.value)[number],
  ): Promise<void> {
    const editableEntryId = group.editableRow?.entry.id;
    if (editableEntryId == null) return;
    expenseExecutionBusyEntryId.value = editableEntryId;
    expenseExecutionError.value = null;
    try {
      const responses = await Promise.all(
        group.rows.map((row) => {
          const payload = {
            annual_expense_entry_id: row.entry.id,
            fiscal_year: fiscalYear.value,
            month: selectedExecutionMonth.value,
            status: 'skipped' as const,
            executed_amount: null,
          };
          const existing = expenseCheckinsByEntryId.value[row.entry.id];
          if (existing) {
            return budgetApi.patch<ExpenseMonthlyCheckinApiItem>(
              `/api/budget/annual-expense-checkins/${existing.id}/`,
              payload,
            );
          }
          return budgetApi.post<ExpenseMonthlyCheckinApiItem>(
            '/api/budget/annual-expense-checkins/',
            payload,
          );
        }),
      );
      setExpenseGroupUnlocked(group.key, false);
      for (const response of responses) cacheExpenseCheckin(response.data);
    } catch (e: unknown) {
      expenseExecutionError.value = toBudgetErrorMessage(e);
    } finally {
      expenseExecutionBusyEntryId.value = null;
    }
  }

  async function onExpenseGroupReviewedToggle(
    group: (typeof groupedMonthlyExpenseExecutionEntries.value)[number],
    checked: boolean,
  ): Promise<void> {
    if (checked) {
      await markExpenseGroupAsSkipped(group);
      return;
    }
    await clearExpenseGroupCheckins(group);
  }

  async function onExpenseCheckinCheckboxToggle(
    row: (typeof monthlyExpenseExecutionEntries.value)[number],
    checked: boolean,
  ): Promise<void> {
    if (checked) {
      await saveExpenseCheckinFromInput(row);
      return;
    }
    await clearExpenseCheckin(row);
  }

  async function onExpenseAdjustAmountBlur(
    row: (typeof monthlyExpenseExecutionEntries.value)[number],
  ): Promise<void> {
    if (!expenseCheckinsByEntryId.value[row.entry.id]) return;
    await saveExpenseCheckinFromInput(row);
  }

  async function upsertExpenseCheckin(
    row: (typeof monthlyExpenseExecutionEntries.value)[number],
    status: 'confirmed' | 'adjusted',
  ): Promise<void> {
    expenseExecutionError.value = null;
    expenseExecutionBusyEntryId.value = row.entry.id;
    try {
      const existing = expenseCheckinsByEntryId.value[row.entry.id];
      const draftAmount = String(expenseAdjustAmounts.value[row.entry.id] ?? '').trim();

      const payload = {
        annual_expense_entry_id: row.entry.id,
        fiscal_year: fiscalYear.value,
        month: selectedExecutionMonth.value,
        status,
        executed_amount: draftAmount || null,
      };

      if (existing) {
        await budgetApi.patch(`/api/budget/annual-expense-checkins/${existing.id}/`, payload);
      } else {
        await budgetApi.post('/api/budget/annual-expense-checkins/', payload);
      }
      await refreshExpenseExecutionData();
    } catch (e: unknown) {
      expenseExecutionError.value = toBudgetErrorMessage(e);
    } finally {
      expenseExecutionBusyEntryId.value = null;
    }
  }

  function unlockExpenseGroupManualAdjustment(
    group: (typeof groupedMonthlyExpenseExecutionEntries.value)[number],
  ): void {
    ensureExpenseGroupAdjustAmountPrefilled(group);
    setExpenseGroupUnlocked(group.key, true);
  }

  async function relockExpenseGroupManualAdjustment(
    group: (typeof groupedMonthlyExpenseExecutionEntries.value)[number],
  ): Promise<void> {
    setExpenseGroupUnlocked(group.key, false);
    await clearExpenseGroupCheckins(group);
  }

  function shortLiquiditySubcategoryLabel(subcategory: string): string {
    if (subcategory === 'credit_card') return 'Tarjeta de credito';
    if (subcategory === 'bank_account') return 'Cuenta bancaria';
    if (subcategory === 'short_term_deposit') return 'Deposito corto plazo';
    if (subcategory === 'wallet') return 'Monedero';
    if (subcategory === 'crypto_spot_earn') return 'Spot/Earn';
    return 'Liquidez';
  }

  function liquidityCheckinRowSummary(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
  ): string {
    if (row.row_type === 'liability') {
      return `${shortLiquiditySubcategoryLabel(row.liability_category ?? row.asset_subcategory)} - ${
        row.liability_name ?? row.asset_name
      }`;
    }
    return `${shortLiquiditySubcategoryLabel(row.asset_subcategory)} - ${row.asset_name}`;
  }

  function selectedLiquidityValuationDate(): string {
    const lastDay = new Date(fiscalYear.value, selectedExecutionMonth.value, 0).getDate();
    return `${fiscalYear.value}-${String(selectedExecutionMonth.value).padStart(2, '0')}-${String(
      lastDay,
    ).padStart(2, '0')}`;
  }

  function suggestedLiquidityClosingBalanceForRow(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
  ): string {
    if (row.executed != null) return row.executed.toFixed(2);
    return row.planned.toFixed(2);
  }

  function ensureLiquidityAdjustAmountPrefilled(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
  ): void {
    const current = String(liquidityAdjustAmounts.value[row.asset_id] ?? '').trim();
    if (current) return;
    liquidityAdjustAmounts.value[row.asset_id] = suggestedLiquidityClosingBalanceForRow(row);
  }

  async function loadLiquidityExecutionSummary(): Promise<void> {
    try {
      const response = await budgetApi.get<LiquidityMonthlySummaryResponse>(
        '/api/net-worth/liquidity/monthly-summary/',
        { params: { year: fiscalYear.value, month: selectedExecutionMonth.value } },
      );
      liquidityMonthlySummary.value = response.data ?? null;
    } catch (e: unknown) {
      liquidityExecutionError.value = toBudgetErrorMessage(e);
    }
  }

  async function refreshLiquidityExecutionData(): Promise<void> {
    liquidityExecutionLoading.value = true;
    liquidityExecutionError.value = null;
    try {
      await loadLiquidityExecutionSummary();
    } finally {
      liquidityExecutionLoading.value = false;
    }
  }

  async function refreshMonthlyCloseData(): Promise<void> {
    if (!isMonthlyCloseView.value) return;
    monthlyCloseLoading.value = true;
    monthlyCloseError.value = null;
    try {
      monthlyCloseData.value = await getMonthlyClose(
        fiscalYear.value,
        selectedExecutionMonth.value,
      );
    } catch (e: unknown) {
      monthlyCloseError.value = toBudgetErrorMessage(e);
    } finally {
      monthlyCloseLoading.value = false;
    }
  }

  async function handleFinalizeClose(): Promise<void> {
    monthlyCloseActionBusy.value = true;
    monthlyCloseError.value = null;
    try {
      await finalizeMonthlyClose(fiscalYear.value, selectedExecutionMonth.value);
      await refreshMonthlyCloseData();
    } catch (e: unknown) {
      monthlyCloseError.value = toBudgetErrorMessage(e);
    } finally {
      monthlyCloseActionBusy.value = false;
    }
  }

  async function handleReopenClose(): Promise<void> {
    monthlyCloseActionBusy.value = true;
    monthlyCloseError.value = null;
    try {
      await reopenMonthlyClose(fiscalYear.value, selectedExecutionMonth.value);
      await refreshMonthlyCloseData();
    } catch (e: unknown) {
      monthlyCloseError.value = toBudgetErrorMessage(e);
    } finally {
      monthlyCloseActionBusy.value = false;
    }
  }

  async function handleLockClose(): Promise<void> {
    monthlyCloseActionBusy.value = true;
    monthlyCloseError.value = null;
    try {
      await lockMonthlyClose(fiscalYear.value, selectedExecutionMonth.value);
      await refreshMonthlyCloseData();
    } catch (e: unknown) {
      monthlyCloseError.value = toBudgetErrorMessage(e);
    } finally {
      monthlyCloseActionBusy.value = false;
    }
  }

  async function handleApplyDistribution(): Promise<void> {
    monthlyCloseActionBusy.value = true;
    monthlyCloseError.value = null;
    try {
      await patchMonthlyClose(fiscalYear.value, selectedExecutionMonth.value, {
        accept_suggestions: true,
      });
      await refreshMonthlyCloseData();
      await Promise.all([refreshIncomeExecutionData(), refreshExpenseExecutionData()]);
    } catch (e: unknown) {
      monthlyCloseError.value = toBudgetErrorMessage(e);
    } finally {
      monthlyCloseActionBusy.value = false;
    }
  }

  async function clearLiquidityCheckin(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
  ): Promise<void> {
    if (!row.checkin) return;
    liquidityExecutionBusyAssetId.value = row.asset_id;
    liquidityExecutionError.value = null;
    try {
      const endpoint =
        row.row_type === 'liability'
          ? `/api/net-worth/liability-valuations/${row.checkin.id}/`
          : row.asset_category !== 'cash'
            ? `/api/net-worth/asset-valuations/${row.checkin.id}/`
            : `/api/net-worth/liquidity-checkins/${row.checkin.id}/`;
      await budgetApi.delete(endpoint);
      await refreshLiquidityExecutionData();
    } catch (e: unknown) {
      liquidityExecutionError.value = toBudgetErrorMessage(e);
    } finally {
      liquidityExecutionBusyAssetId.value = null;
    }
  }

  function setLiquidityAdjustAmountZero(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
  ): void {
    liquidityAdjustAmounts.value[row.asset_id] = '0.00';
  }

  function setLiquidityAdjustAmountPlanned(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
  ): void {
    liquidityAdjustAmounts.value[row.asset_id] = row.planned.toFixed(2);
  }

  async function resetLiquidityCheckinDraftValue(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
    mode: 'zero' | 'planned',
  ): Promise<void> {
    if (mode === 'zero') setLiquidityAdjustAmountZero(row);
    else setLiquidityAdjustAmountPlanned(row);
    if (row.checkin) {
      await clearLiquidityCheckin(row);
    }
  }

  async function upsertLiquidityCheckin(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
    status: 'confirmed' | 'adjusted',
  ): Promise<void> {
    liquidityExecutionError.value = null;
    liquidityExecutionBusyAssetId.value = row.asset_id;
    try {
      const rawAdjusted = String(liquidityAdjustAmounts.value[row.asset_id] ?? '').trim();
      const parsedAdjusted = parseDecimalInput(rawAdjusted);
      if (parsedAdjusted == null) {
        liquidityExecutionError.value =
          'Indica un saldo válido para confirmar (por ejemplo 1234,56).';
        return;
      }
      liquidityAdjustAmounts.value[row.asset_id] = parsedAdjusted.toFixed(2);
      if (row.row_type === 'liability') {
        if (row.liability_id == null) {
          liquidityExecutionError.value = 'No se ha podido identificar la tarjeta para ajustarla.';
          return;
        }
        const payload = {
          liability_id: row.liability_id,
          valuation_date: selectedLiquidityValuationDate(),
          value: parsedAdjusted.toFixed(2),
          source: 'manual_checkpoint',
          note: `Ajuste manual cierre ${selectedLiquidityValuationDate()}`,
        };
        if (row.checkin) {
          await budgetApi.patch(`/api/net-worth/liability-valuations/${row.checkin.id}/`, payload);
        } else {
          await budgetApi.post('/api/net-worth/liability-valuations/', payload);
        }
      } else if (row.asset_category !== 'cash') {
        const payload = {
          asset_id: row.asset_id,
          valuation_date: selectedLiquidityValuationDate(),
          value: parsedAdjusted.toFixed(2),
          source: 'manual_checkpoint',
          note: `Ajuste manual cierre ${selectedLiquidityValuationDate()}`,
        };
        if (row.checkin) {
          await budgetApi.patch(`/api/net-worth/asset-valuations/${row.checkin.id}/`, payload);
        } else {
          await budgetApi.post('/api/net-worth/asset-valuations/', payload);
        }
      } else {
        const payload = {
          asset_id: row.asset_id,
          fiscal_year: fiscalYear.value,
          month: selectedExecutionMonth.value,
          status,
          closing_balance_real: parsedAdjusted.toFixed(2),
        };
        if (row.checkin) {
          await budgetApi.patch(`/api/net-worth/liquidity-checkins/${row.checkin.id}/`, payload);
        } else {
          await budgetApi.post('/api/net-worth/liquidity-checkins/', payload);
        }
      }
      setLiquidityLedgerRowUnlocked(row.asset_id, false);
      await refreshLiquidityExecutionData();
    } catch (e: unknown) {
      liquidityExecutionError.value = toBudgetErrorMessage(e);
    } finally {
      liquidityExecutionBusyAssetId.value = null;
    }
  }

  async function saveLiquidityCheckinFromInput(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
  ): Promise<void> {
    if (liquidityExecutionBusyAssetId.value === row.asset_id) return;
    ensureLiquidityAdjustAmountPrefilled(row);
    const rawAdjusted = String(liquidityAdjustAmounts.value[row.asset_id] ?? '').trim();
    const parsedAdjusted = parseDecimalInput(rawAdjusted);
    if (parsedAdjusted == null) {
      liquidityExecutionError.value =
        'Indica un saldo válido para confirmar (por ejemplo 1234,56).';
      return;
    }
    const status = amountsEqualCents(parsedAdjusted, row.planned) ? 'confirmed' : 'adjusted';
    await upsertLiquidityCheckin(row, status);
  }

  async function unlockLiquidityLedgerRow(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
  ): Promise<void> {
    const seed = row.executed ?? row.planned;
    liquidityAdjustAmounts.value[row.asset_id] = seed.toFixed(2);
    setLiquidityLedgerRowUnlocked(row.asset_id, true);
  }

  async function relockLiquidityLedgerRow(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
  ): Promise<void> {
    if (!row.ledger_available) return;
    setLiquidityLedgerRowUnlocked(row.asset_id, false);
    if (!row.checkin) return;
    await clearLiquidityCheckin(row);
  }

  async function onLiquidityCheckinCheckboxToggle(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
    checked: boolean,
  ): Promise<void> {
    if (checked) {
      await saveLiquidityCheckinFromInput(row);
      return;
    }
    await clearLiquidityCheckin(row);
  }

  async function onLiquidityAdjustAmountBlur(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
  ): Promise<void> {
    await saveLiquidityCheckinFromInput(row);
  }

  watch(
    monthlyIncomeExecutionEntries,
    (rows) => {
      for (const row of rows) ensureIncomeAdjustAmountPrefilled(row);
    },
    { immediate: true },
  );

  watch(
    monthlyExpenseExecutionEntries,
    (rows) => {
      for (const row of rows) {
        ensureExpenseAdjustAmountPrefilled(row);
      }
    },
    { immediate: true },
  );

  watch(
    monthlyLiquidityExecutionRows,
    (rows) => {
      const currentAssetIds = new Set(rows.map((row) => row.asset_id));
      unlockedLiquidityLedgerAssetIds.value = new Set(
        [...unlockedLiquidityLedgerAssetIds.value].filter((assetId) =>
          currentAssetIds.has(assetId),
        ),
      );
      for (const row of rows) {
        ensureLiquidityAdjustAmountPrefilled(row);
      }
    },
    { immediate: true },
  );

  watch(monthlyCloseData, (data: MonthlyCloseStateResponse | null) => {
    if (!data?.has_gaps) return;
    for (const entryIdStr of Object.keys(data.suggestions.income)) {
      const entryId = Number(entryIdStr);
      const amount = data.suggestions.income[entryIdStr];
      if (amount !== undefined && !incomeAdjustAmounts.value[entryId]) {
        incomeAdjustAmounts.value = { ...incomeAdjustAmounts.value, [entryId]: amount };
      }
    }
    for (const entryIdStr of Object.keys(data.suggestions.expense)) {
      const entryId = Number(entryIdStr);
      const amount = data.suggestions.expense[entryIdStr];
      if (amount !== undefined && !expenseAdjustAmounts.value[entryId]) {
        expenseAdjustAmounts.value = { ...expenseAdjustAmounts.value, [entryId]: amount };
      }
    }
  });

  watch(
    fiscalYear,
    (year) => {
      void Promise.all([
        refreshBudgetData(year),
        refreshBudgetSuggestionData(),
        refreshAccountingExecutionData(),
        refreshIncomeExecutionData(),
        refreshExpenseExecutionData(),
        refreshLiquidityExecutionData(),
        refreshMonthlyCloseData(),
      ]);
    },
    { immediate: true },
  );

  watch(selectedExecutionMonth, () => {
    void Promise.all([
      refreshAccountingExecutionData(),
      loadIncomeCheckinsForSelectedMonth(),
      loadExpenseCheckinsForSelectedMonth(),
      refreshLiquidityExecutionData(),
      refreshMonthlyCloseData(),
    ]);
  });

  watch(
    isMonthlyCloseView,
    (enabled) => {
      if (enabled) activeMonthlyCloseStep.value = 'liq';
    },
    { immediate: true },
  );

  return {
    incomeStore,
    expenseStore,
    fiscalYear,
    ownershipFilter,
    incomeViewMode,
    expenseViewMode,
    incomeDetailsExpanded,
    expenseDetailsExpanded,
    currentCalendarYear,
    monthLabels,
    selectedExecutionMonth,
    expenseMonthlySummary,
    incomeMonthlySummary,
    expenseCheckinsByEntryId,
    expenseCheckinsByEntryMonth,
    expenseExecutionLoading,
    expenseExecutionBusyEntryId,
    expenseExecutionError,
    expenseAdjustAmounts,
    incomeCheckinsByEntryId,
    incomeCheckinsByEntryMonth,
    incomeExecutionLoading,
    incomeExecutionBusyEntryId,
    incomeExecutionError,
    incomeAdjustAmounts,
    accountingExecutionLoading,
    accountingExecutionError,
    accountingMonthlySummary,
    accountingPostedEntries,
    budgetSuggestionsLoading,
    budgetSuggestionsError,
    budgetSuggestions,
    liquidityMonthlySummary,
    liquidityExecutionLoading,
    liquidityExecutionBusyAssetId,
    liquidityExecutionError,
    liquidityAdjustAmounts,
    unlockedLiquidityLedgerAssetIds,
    activeMonthlyCloseStep,
    monthlyCloseData,
    monthlyCloseLoading,
    monthlyCloseError,
    monthlyCloseActionBusy,
    incomeCategoryLabels,
    incomeSubcategoryLabels,
    expenseCategoryLabels,
    expenseSubcategoryLabels,
    isMonthlyCloseView,
    monthlyCloseFlowSteps,
    monthlyCloseStepIds,
    activeMonthlyCloseStepIndex,
    previousMonthlyCloseStep,
    nextMonthlyCloseStep,
    fiscalYearOptions,
    selectedOwnershipFilterLabel,
    selectedFiscalYearLabel,
    isLoading,
    firstError,
    incomeEntries,
    expenseEntries,
    parseSharedOwnerShares,
    ownerNamesFromLabel,
    allocationFractionForOwnerLabel,
    ownershipOptions,
    closePopoverFromClick,
    setActiveMonthlyCloseStep,
    goToPreviousMonthlyCloseStep,
    goToNextMonthlyCloseStep,
    selectOwnershipFilterOption,
    selectFiscalYearOption,
    updateSelectedExecutionMonth,
    setIncomeAdjustAmount,
    setExpenseAdjustAmount,
    setLiquidityAdjustAmount,
    isExpenseGroupUnlocked,
    isLiquidityLedgerRowUnlocked,
    updateIncomeViewMode,
    updateExpenseViewMode,
    ownerAdjustedIncomeEntries,
    ownerAdjustedExpenseEntries,
    matchesIncomeViewMode,
    matchesExpenseViewMode,
    sumPlanned,
    filteredIncomeEntries,
    filteredExpenseEntries,
    plannedIncomeTotal,
    plannedExpenseTotal,
    plannedBalanceTotal,
    toNumberOrZero,
    budgetTaxonomyKey,
    resolveLedgerEntryFlowFamily,
    isPositiveExecutionLedgerEntry,
    monthlyPlannedAmountForExpenseEntry,
    monthlyPlannedAmountForIncomeEntry,
    expenseSummaryByMonth,
    incomeSummaryByMonth,
    accountingSummaryByMonth,
    accountingExecutionBuckets,
    incomeTaxonomyLineCounts: incomeTaxonomyLineCountsByMonth,
    expenseTaxonomyLineCounts: expenseTaxonomyLineCountsByMonth,
    selectedExpenseSummaryMonth,
    selectedExpenseMonthPlanned,
    selectedExpenseMonthDeviation,
    monthlyIncomeExecutionEntries,
    selectedIncomeMonthPlanned,
    selectedIncomeMonthExecuted,
    selectedIncomeMonthDeviation,
    selectedIncomeMonthCompletionRatio,
    groupedMonthlyIncomeExecutionEntries,
    incomeEvolutionMonths,
    incomeEvolutionBaseMonthly,
    expenseEvolutionMonths,
    expenseEvolutionBaseMonthly,
    selectedLiquidityMonthPlanned,
    selectedLiquidityMonthExecuted,
    selectedLiquidityMonthDeviation,
    selectedLiquidityStartBase,
    selectedMonthlyCloseExpected,
    selectedMonthlyCloseResidual,
    selectedMonthlyCloseCompletionRatio,
    monthlyLiquidityExecutionRows,
    monthlyExpenseExecutionEntries,
    selectedExpenseMonthExecuted,
    groupedMonthlyExpenseExecutionEntries,
    buildMonthlyResultBreakdown,
    monthlyIncomeResultBreakdown,
    monthlyExpenseResultBreakdown,
    selectedExecutionMonthLabel,
    budgetDetailMonth,
    budgetDetailMonthLabel,
    updateBudgetDetailMonth,
    incomeYtdActualByCategory,
    incomeYtdActualBySubcategoryKey,
    buildActualExecution,
    budgetSectionActualExecution,
    budgetCategoryActualExecution,
    budgetSubcategoryActualExecution,
    incomeInvestmentRotationCategoryAdjustment,
    incomeInvestmentRotationSubcategoryAdjustment,
    selectedMonthlyExecutedVolume,
    selectedMonthlyResidualAbs,
    selectedMonthlyResidualVolumeRatio,
    selectedMonthlyResidualIncomeRatio,
    selectedMonthlyResidualExpenseRatio,
    selectedMonthlyResidualExpectedCloseRatio,
    selectedMonthlyResidualSeverity,
    selectedMonthlyResidualSeverityLabel,
    resultReconciliationFlowRows,
    resultReconciliationCompositionRows,
    executionStatusLabel,
    executionStatusDetail,
    monthlyIncomeCoverageSummary,
    monthlyExpenseCoverageSummary,
    monthlyIncomePendingClassification,
    monthlyExpensePendingClassification,
    isLockedExecutionRow,
    resolveCoverageMode,
    coverageBadgeLabel,
    coverageDetail,
    executionSourceLabel,
    monthlyExpenseCoverageLabel,
    monthlyExpenseCoverageDetail,
    monthlyIncomeCoverageLabel,
    monthlyIncomeCoverageDetail,
    refreshAccountingExecutionData,
    refreshBudgetSuggestionData,
    formatMoney,
    formatSignedMoney,
    formatPercent,
    formatCompactMoney,
    clamp,
    hashToUnitInterval,
    executionToneFor,
    mockExecutionRatio,
    executionPreview,
    aggregateBudgetRows,
    incomeGroups,
    expenseGroups,
    incomeExecutionYtdTotals,
    expenseExecutionYtdTotals,
    viewModeLabel,
    isSectionExpanded,
    toggleSectionExpanded,
    sections,
    budgetSuggestionBySubcategory,
    incomeBudgetSuggestions,
    expenseBudgetSuggestions,
    hasAnyPlannedData,
    closeStatus,
    isCloseLocked,
    hasDistributionSuggestion,
    activeViewSummary,
    refreshBudgetData,
    loadIncomeCheckinsForSelectedMonth,
    incomeEntryMonthKey,
    loadIncomeCheckinsForYear,
    isIncomeGroupUnlocked,
    loadIncomeExecutionSummary,
    refreshIncomeExecutionData,
    loadExpenseExecutionSummary,
    loadExpenseCheckinsForSelectedMonth,
    loadExpenseCheckinsForYear,
    refreshExpenseExecutionData,
    suggestedExecutedAmountForRow,
    ensureExpenseAdjustAmountPrefilled,
    ensureExpenseGroupAdjustAmountPrefilled,
    parseDecimalInput,
    checkinStatusLabel,
    incomeCheckinRowSummary,
    suggestedIncomeExecutedAmountForRow,
    ensureIncomeAdjustAmountPrefilled,
    ensureIncomeGroupAdjustAmountPrefilled,
    clearIncomeCheckin,
    upsertIncomeCheckin,
    saveIncomeCheckinFromInput,
    saveIncomeGroupCheckinFromInput,
    markIncomeGroupAsSkipped,
    onIncomeGroupReviewedToggle,
    onIncomeCheckinCheckboxToggle,
    onIncomeAdjustAmountBlur,
    resetIncomeCheckinDraftValue,
    resetIncomeGroupCheckinDraftValue,
    unlockIncomeGroupManualAdjustment,
    relockIncomeGroupManualAdjustment,
    cleanedExpenseCheckinName,
    shortExpenseCategoryLabel,
    expenseCheckinCategorySortWeight,
    amountsEqualCents,
    expenseCheckinRowSummary,
    clearExpenseCheckin,
    clearExpenseGroupCheckins,
    setExpenseAdjustAmountZero,
    setExpenseAdjustAmountPlanned,
    resetExpenseCheckinDraftValue,
    resetExpenseGroupCheckinDraftValue,
    saveExpenseCheckinFromInput,
    saveExpenseGroupCheckinFromInput,
    markExpenseGroupAsSkipped,
    onExpenseGroupReviewedToggle,
    onExpenseCheckinCheckboxToggle,
    onExpenseAdjustAmountBlur,
    upsertExpenseCheckin,
    unlockExpenseGroupManualAdjustment,
    relockExpenseGroupManualAdjustment,
    shortLiquiditySubcategoryLabel,
    liquidityCheckinRowSummary,
    suggestedLiquidityClosingBalanceForRow,
    ensureLiquidityAdjustAmountPrefilled,
    loadLiquidityExecutionSummary,
    refreshLiquidityExecutionData,
    refreshMonthlyCloseData,
    handleFinalizeClose,
    handleReopenClose,
    handleLockClose,
    handleApplyDistribution,
    clearLiquidityCheckin,
    setLiquidityAdjustAmountZero,
    setLiquidityAdjustAmountPlanned,
    resetLiquidityCheckinDraftValue,
    upsertLiquidityCheckin,
    saveLiquidityCheckinFromInput,
    unlockLiquidityLedgerRow,
    relockLiquidityLedgerRow,
    onLiquidityCheckinCheckboxToggle,
    onLiquidityAdjustAmountBlur,
  };
}
