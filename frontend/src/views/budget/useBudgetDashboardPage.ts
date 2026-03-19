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
  type MonthlyAccountingSummary,
} from '@/domains/accounting';
import {
  expenseCategories,
  expenseSubcategories,
  incomeCategories,
  incomeSubcategories,
  useAnnualExpenseStore,
  useAnnualIncomeStore,
} from '@/domains/data-input';

export type BudgetDashboardMode = 'budget' | 'monthly-close';
type MonthlyCloseStepId = 'liq' | 'income' | 'expense' | 'result';
export function useBudgetDashboardPage(mode: Ref<BudgetDashboardMode>) {
  type ExpenseMonthlySummaryMonth = {
    month: number;
    planned: string;
    executed: string;
    pending: string;
    completion_ratio: number;
    checkins_confirmed: number;
    checkins_expected: number;
  };

  type ExpenseMonthlySummaryResponse = {
    fiscal_year: number;
    planned_total: string;
    executed_total: string;
    pending_total: string;
    variance_total: string;
    months: ExpenseMonthlySummaryMonth[];
    completion_ratio: number;
    months_with_checkins: number;
    has_executed_data: boolean;
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
    asset_id: number;
    asset_name: string;
    asset_category: string;
    asset_subcategory: string;
    currency: string;
    planned_closing_balance: string;
    executed_closing_balance: string | null;
    effective_closing_balance: string;
    deviation: string;
    planned_closing_balance_base: string;
    executed_closing_balance_base: string | null;
    effective_closing_balance_base: string;
    deviation_base: string;
    checkin: LiquidityMonthlyCheckinApiItem | null;
  };

  type LiquidityMonthlySummaryResponse = {
    fiscal_year: number;
    month: number;
    base_currency: string;
    planned_total: string;
    executed_total: string;
    deviation_total: string;
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
  const accountingExecutionLoading = ref(false);
  const accountingExecutionError = ref<string | null>(null);
  const accountingMonthlySummary = ref<MonthlyAccountingSummary | null>(null);
  const accountingPostedEntries = ref<LedgerEntry[]>([]);
  const budgetSuggestionsLoading = ref(false);
  const budgetSuggestionsError = ref<string | null>(null);
  const budgetSuggestions = ref<BudgetDerivedSuggestions | null>(null);
  const liquidityMonthlySummary = ref<LiquidityMonthlySummaryResponse | null>(null);
  const liquidityExecutionLoading = ref(false);
  const liquidityExecutionBusyAssetId = ref<number | null>(null);
  const liquidityExecutionError = ref<string | null>(null);
  const liquidityAdjustAmounts = ref<Record<number, string>>({});
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
    { id: 'liq', label: 'Liquidez', subtitle: 'Saldo real de cuentas' },
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

  function setExpenseAdjustAmount(entryId: number, value: string): void {
    expenseAdjustAmounts.value = { ...expenseAdjustAmounts.value, [entryId]: value };
  }

  function setLiquidityAdjustAmount(assetId: number, value: string): void {
    liquidityAdjustAmounts.value = { ...liquidityAdjustAmounts.value, [assetId]: value };
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
        return { ...entry, amountAnnual: entry.amountAnnual * fraction };
      })
      .filter((entry) => entry.amountAnnual > 0),
  );

  const ownerAdjustedExpenseEntries = computed(() =>
    expenseEntries.value
      .map((entry) => {
        const fraction = allocationFractionForOwnerLabel(entry.owner ?? '', ownershipFilter.value);
        return { ...entry, amountAnnual: entry.amountAnnual * fraction };
      })
      .filter((entry) => entry.amountAnnual > 0),
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
    ownerAdjustedExpenseEntries.value.filter((entry) =>
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

  function budgetTaxonomyKey(category: string, subcategory: string): string {
    return `${category}::${subcategory}`;
  }

  function resolveLedgerEntryFlowFamily(entry: LedgerEntry): '' | 'income' | 'expense' {
    if (entry.flow_family === 'income' || entry.flow_family === 'expense') return entry.flow_family;
    if (entry.annual_income_entry_id != null) return 'income';
    if (entry.annual_expense_entry_id != null) return 'expense';
    return '';
  }

  function isPositiveExecutionLedgerEntry(
    entry: LedgerEntry,
    flowFamily: 'income' | 'expense',
  ): boolean {
    return (
      (flowFamily === 'income' && entry.side === 'credit') ||
      (flowFamily === 'expense' && entry.side === 'debit')
    );
  }

  function monthlyPlannedAmountForExpenseEntry(
    entry: (typeof expenseEntries.value)[number],
    month: number,
  ): number {
    if (entry.expenseType === 'one_off') {
      return entry.targetMonth === month ? toNumberOrZero(entry.amountAnnual) : 0;
    }
    return toNumberOrZero(entry.amountAnnual) / 12;
  }

  function monthlyPlannedAmountForIncomeEntry(
    entry: (typeof incomeEntries.value)[number],
    _month: number,
  ): number {
    if (entry.incomeType === 'one_off') return 0;
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
    const incomeCategorizedByTaxonomy = new Map<string, number>();
    const expenseCategorizedByTaxonomy = new Map<string, number>();
    const incomeLegacyByEntryId = new Map<number, number>();
    const expenseLegacyByEntryId = new Map<number, number>();
    let incomeUnclassifiedTotal = 0;
    let expenseUnclassifiedTotal = 0;

    for (const entry of accountingPostedEntries.value) {
      const flowFamily = resolveLedgerEntryFlowFamily(entry);
      if (!flowFamily || !isPositiveExecutionLedgerEntry(entry, flowFamily)) continue;

      const amount = toNumberOrZero(entry.amount);
      if (entry.category_key && entry.subcategory_key) {
        const key = budgetTaxonomyKey(entry.category_key, entry.subcategory_key);
        const targetMap =
          flowFamily === 'income' ? incomeCategorizedByTaxonomy : expenseCategorizedByTaxonomy;
        targetMap.set(key, (targetMap.get(key) ?? 0) + amount);
        continue;
      }

      if (flowFamily === 'income' && entry.annual_income_entry_id != null) {
        incomeLegacyByEntryId.set(
          entry.annual_income_entry_id,
          (incomeLegacyByEntryId.get(entry.annual_income_entry_id) ?? 0) + amount,
        );
        continue;
      }
      if (flowFamily === 'expense' && entry.annual_expense_entry_id != null) {
        expenseLegacyByEntryId.set(
          entry.annual_expense_entry_id,
          (expenseLegacyByEntryId.get(entry.annual_expense_entry_id) ?? 0) + amount,
        );
        continue;
      }

      if (flowFamily === 'income') incomeUnclassifiedTotal += amount;
      if (flowFamily === 'expense') expenseUnclassifiedTotal += amount;
    }

    return {
      incomeCategorizedByTaxonomy,
      expenseCategorizedByTaxonomy,
      incomeLegacyByEntryId,
      expenseLegacyByEntryId,
      incomeUnclassifiedTotal,
      expenseUnclassifiedTotal,
    };
  });

  const incomeTaxonomyLineCounts = computed(() => {
    const map = new Map<string, number>();
    for (const entry of incomeEntries.value) {
      if (entry.fiscalYear !== fiscalYear.value || entry.incomeType === 'one_off') continue;
      const planned = monthlyPlannedAmountForIncomeEntry(entry, selectedExecutionMonth.value);
      if (planned <= 0) continue;
      const key = budgetTaxonomyKey(entry.category, entry.subcategory);
      map.set(key, (map.get(key) ?? 0) + 1);
    }
    return map;
  });

  const expenseTaxonomyLineCounts = computed(() => {
    const map = new Map<string, number>();
    for (const entry of expenseEntries.value) {
      const planned = monthlyPlannedAmountForExpenseEntry(entry, selectedExecutionMonth.value);
      if (planned <= 0) continue;
      const key = budgetTaxonomyKey(entry.category, entry.subcategory);
      map.set(key, (map.get(key) ?? 0) + 1);
    }
    return map;
  });

  const selectedExpenseSummaryMonth = computed(() => {
    return expenseSummaryByMonth.value.get(selectedExecutionMonth.value) ?? null;
  });

  const selectedExpenseMonthPlanned = computed(() =>
    toNumberOrZero(selectedExpenseSummaryMonth.value?.planned),
  );
  const selectedExpenseMonthDeviation = computed(
    () => selectedExpenseMonthExecuted.value - selectedExpenseMonthPlanned.value,
  );

  const monthlyIncomeExecutionEntries = computed(() => {
    return incomeEntries.value
      .filter((entry) => entry.fiscalYear === fiscalYear.value && entry.incomeType !== 'one_off')
      .map((entry) => {
        const checkin = incomeCheckinsByEntryId.value[entry.id] ?? null;
        const planned = monthlyPlannedAmountForIncomeEntry(entry, selectedExecutionMonth.value);
        const taxonomyKey = budgetTaxonomyKey(entry.category, entry.subcategory);
        const categorizedLedgerExecuted =
          accountingExecutionBuckets.value.incomeCategorizedByTaxonomy.get(taxonomyKey) ?? null;
        const legacyLedgerExecuted =
          accountingExecutionBuckets.value.incomeLegacyByEntryId.get(entry.id) ?? null;
        const taxonomyLineCount = incomeTaxonomyLineCounts.value.get(taxonomyKey) ?? 0;
        const fallbackExecuted =
          checkin && checkin.status !== 'skipped' ? toNumberOrZero(checkin.executed_amount) : 0;
        const uniqueCategorizedLedgerExecuted =
          categorizedLedgerExecuted != null && taxonomyLineCount === 1
            ? categorizedLedgerExecuted
            : 0;
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
      .filter((row) => row.planned > 0)
      .sort((a, b) => b.planned - a.planned || a.entry.name.localeCompare(b.entry.name, 'es'));
  });

  const selectedIncomeMonthPlanned = computed(() =>
    monthlyIncomeExecutionEntries.value.reduce((sum, row) => sum + row.planned, 0),
  );
  const selectedIncomeMonthExecuted = computed(() =>
    monthlyIncomeExecutionEntries.value.reduce((sum, row) => sum + (row.executed ?? 0), 0),
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
      const summary = incomeSummaryByMonth.value.get(month);
      const planned = toNumberOrZero(summary?.planned);
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

  const incomeEvolutionBaseMonthly = computed(() => {
    if (incomeMonthlySummary.value)
      return toNumberOrZero(incomeMonthlySummary.value.planned_total) / 12;
    return plannedIncomeTotal.value / 12;
  });

  const selectedLiquidityMonthPlanned = computed(() =>
    toNumberOrZero(liquidityMonthlySummary.value?.planned_total),
  );
  const selectedLiquidityMonthExecuted = computed(() =>
    toNumberOrZero(liquidityMonthlySummary.value?.executed_total),
  );
  const selectedLiquidityMonthDeviation = computed(
    () => selectedLiquidityMonthExecuted.value - selectedLiquidityMonthPlanned.value,
  );
  const selectedLiquidityStartBase = computed(() => selectedLiquidityMonthPlanned.value);
  const selectedMonthlyCloseExpected = computed(
    () =>
      selectedLiquidityStartBase.value +
      selectedIncomeMonthExecuted.value -
      selectedExpenseMonthExecuted.value,
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
      const executed = row.checkin ? toNumberOrZero(row.executed_closing_balance) : null;
      return { ...row, planned, executed };
    }),
  );

  const monthlyExpenseExecutionEntries = computed(() => {
    const month = selectedExecutionMonth.value;
    return expenseEntries.value
      .filter((entry) => {
        if (entry.expenseType === 'one_off') return entry.targetMonth === month;
        return true;
      })
      .map((entry) => {
        const checkin = expenseCheckinsByEntryId.value[entry.id] ?? null;
        const planned = monthlyPlannedAmountForExpenseEntry(entry, month);
        const taxonomyKey = budgetTaxonomyKey(entry.category, entry.subcategory);
        const categorizedLedgerExecuted =
          accountingExecutionBuckets.value.expenseCategorizedByTaxonomy.get(taxonomyKey) ?? null;
        const legacyLedgerExecuted =
          accountingExecutionBuckets.value.expenseLegacyByEntryId.get(entry.id) ?? null;
        const taxonomyLineCount = expenseTaxonomyLineCounts.value.get(taxonomyKey) ?? 0;
        const fallbackExecuted =
          checkin && checkin.status !== 'skipped' ? toNumberOrZero(checkin.executed_amount) : 0;
        const uniqueCategorizedLedgerExecuted =
          categorizedLedgerExecuted != null && taxonomyLineCount === 1
            ? categorizedLedgerExecuted
            : 0;
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
      .filter((row) => row.planned > 0)
      .sort(
        (a, b) =>
          expenseCheckinCategorySortWeight(a.entry.category) -
            expenseCheckinCategorySortWeight(b.entry.category) ||
          b.planned - a.planned ||
          a.entry.name.localeCompare(b.entry.name, 'es'),
      );
  });

  const selectedExpenseMonthExecuted = computed(() =>
    monthlyExpenseExecutionEntries.value.reduce((sum, row) => sum + (row.executed ?? 0), 0),
  );

  const groupedMonthlyExpenseExecutionEntries = computed(() => {
    type Row = (typeof monthlyExpenseExecutionEntries.value)[number];
    const groups = new Map<
      string,
      {
        categoryKey: string;
        categoryLabel: string;
        rows: Row[];
        plannedTotal: number;
        executedTotal: number;
        checkedCount: number;
      }
    >();

    for (const row of monthlyExpenseExecutionEntries.value) {
      const key = row.entry.category;
      let group = groups.get(key);
      if (!group) {
        group = {
          categoryKey: key,
          categoryLabel: shortExpenseCategoryLabel(key),
          rows: [],
          plannedTotal: 0,
          executedTotal: 0,
          checkedCount: 0,
        };
        groups.set(key, group);
      }
      group.rows.push(row);
      group.plannedTotal += row.planned;
      if (row.executionSource !== 'none') {
        group.checkedCount += 1;
        if (row.executed != null) {
          group.executedTotal += row.executed;
        }
      }
    }

    return Array.from(groups.values())
      .map((group) => ({
        ...group,
        deviation: group.executedTotal - group.plannedTotal,
        completionRatio: group.rows.length ? group.checkedCount / group.rows.length : 0,
      }))
      .sort(
        (a, b) =>
          expenseCheckinCategorySortWeight(a.categoryKey) -
            expenseCheckinCategorySortWeight(b.categoryKey) || b.plannedTotal - a.plannedTotal,
      );
  });

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

  type BudgetActualAggregateRow = {
    planned: number;
    executed: number;
    checkedCount: number;
    expectedCount: number;
  };

  const incomeYtdActualByCategory = computed(() => {
    const monthsCount = Math.max(0, Math.min(12, selectedExecutionMonth.value));
    const map = new Map<string, BudgetActualAggregateRow>();
    for (const entry of filteredIncomeEntries.value) {
      if (entry.incomeType === 'one_off') continue;
      const categoryKey = entry.category;
      const monthlyPlanned = monthlyPlannedAmountForIncomeEntry(
        entry,
        selectedExecutionMonth.value,
      );
      let row = map.get(categoryKey);
      if (!row) {
        row = { planned: 0, executed: 0, checkedCount: 0, expectedCount: 0 };
        map.set(categoryKey, row);
      }
      row.planned += monthlyPlanned * monthsCount;
      row.expectedCount += monthsCount;
      for (let month = 1; month <= monthsCount; month++) {
        const checkin = incomeCheckinsByEntryMonth.value[incomeEntryMonthKey(entry.id, month)];
        if (!checkin) continue;
        row.checkedCount += 1;
        if (checkin.status !== 'skipped') row.executed += toNumberOrZero(checkin.executed_amount);
      }
    }
    return map;
  });

  const incomeYtdActualBySubcategoryKey = computed(() => {
    const monthsCount = Math.max(0, Math.min(12, selectedExecutionMonth.value));
    const map = new Map<string, BudgetActualAggregateRow>();
    for (const entry of filteredIncomeEntries.value) {
      if (entry.incomeType === 'one_off') continue;
      const key = `${entry.category}::${entry.subcategory}`;
      const monthlyPlanned = monthlyPlannedAmountForIncomeEntry(
        entry,
        selectedExecutionMonth.value,
      );
      let row = map.get(key);
      if (!row) {
        row = { planned: 0, executed: 0, checkedCount: 0, expectedCount: 0 };
        map.set(key, row);
      }
      row.planned += monthlyPlanned * monthsCount;
      row.expectedCount += monthsCount;
      for (let month = 1; month <= monthsCount; month++) {
        const checkin = incomeCheckinsByEntryMonth.value[incomeEntryMonthKey(entry.id, month)];
        if (!checkin) continue;
        row.checkedCount += 1;
        if (checkin.status !== 'skipped') row.executed += toNumberOrZero(checkin.executed_amount);
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
    if (!Number.isFinite(planned) || planned <= 0) return null;
    const ratio = executed / planned;
    return {
      planned,
      executed,
      deviation: executed - planned,
      completionRatio,
      ratio,
      widthPct: ratio <= 0 ? 0 : clamp(ratio * 100, 4, 100),
      tone: executionToneFor(sectionId, ratio),
      overflow: ratio > 1,
    };
  }

  function budgetCategoryActualExecution(
    sectionId: BudgetSectionModel['id'],
    categoryKey: string,
  ): BudgetActualExecution | null {
    if (sectionId !== 'income') return null;
    const row = incomeYtdActualByCategory.value.get(categoryKey);
    if (!row) return null;
    return buildActualExecution(
      sectionId,
      row.planned,
      row.executed,
      row.expectedCount > 0 ? row.checkedCount / row.expectedCount : 0,
    );
  }

  function budgetSubcategoryActualExecution(
    sectionId: BudgetSectionModel['id'],
    rowKey: string,
  ): BudgetActualExecution | null {
    if (sectionId !== 'income') return null;
    const row = incomeYtdActualBySubcategoryKey.value.get(rowKey);
    if (!row) return null;
    return buildActualExecution(
      sectionId,
      row.planned,
      row.executed,
      row.expectedCount > 0 ? row.checkedCount / row.expectedCount : 0,
    );
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
      label: 'Liquidez inicio (referencia)',
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
      label: 'Gastos ejecutados',
      amount: -selectedExpenseMonthExecuted.value,
      tone: 'warning' as const,
      meta:
        selectedMonthlyExecutedVolume.value > 0
          ? `${formatPercent(selectedExpenseMonthExecuted.value / selectedMonthlyExecutedVolume.value, 0)} del volumen`
          : undefined,
    },
    {
      id: 'expected-close',
      label: 'Cierre esperado',
      amount: selectedMonthlyCloseExpected.value,
      tone: 'neutral' as const,
      meta: 'Liquidez inicio + ingresos - gastos',
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
      label: 'Cierre real',
      amount: selectedLiquidityMonthExecuted.value,
      tone: 'neutral' as const,
      meta: 'Cierre de liquidez confirmado',
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
    if (accountingExecutionLoading.value) return 'Sincronizando ledger';
    if (accountingExecutionError.value) return 'Fallback legacy';
    const monthsWithLedger = Array.from(accountingSummaryByMonth.value.values()).filter(
      (row) => toNumberOrZero(row.income_total) > 0 || toNumberOrZero(row.expense_total) > 0,
    ).length;
    if (monthsWithLedger > 0) return 'Ledger categorizado + fallback';
    if (!expenseMonthlySummary.value) return 'Cargando ejecucion';
    if (expenseMonthlySummary.value.has_executed_data) return 'Fallback legacy';
    return 'Sin ejecucion';
  });
  const executionStatusDetail = computed(() => {
    if (accountingExecutionError.value) {
      return 'No se pudo leer accounting. El cierre mensual sigue usando check-ins legacy como fallback.';
    }
    const monthsWithLedger = Array.from(accountingSummaryByMonth.value.values()).filter(
      (row) => toNumberOrZero(row.income_total) > 0 || toNumberOrZero(row.expense_total) > 0,
    ).length;
    if (monthsWithLedger > 0) {
      return `Ledger categorizado en ${monthsWithLedger}/12 meses. BudgetDashboardView usa taxonomia compartida como fuente primaria y fallback legacy solo cuando falta clasificacion nueva.`;
    }
    if (!expenseMonthlySummary.value) {
      return 'Cargando agregados mensuales para ledger y check-ins legacy.';
    }
    return `Sin cobertura ledger todavia. Check-ins legacy disponibles en ${expenseMonthlySummary.value.months_with_checkins}/12 meses para gastos.`;
  });

  const monthlyIncomeCoverageSummary = computed<MonthlyCoverageSummary>(() => {
    const total = monthlyIncomeExecutionEntries.value.length;
    const viaLedger = monthlyIncomeExecutionEntries.value.filter(
      (row) => row.executionSource === 'categorized_ledger',
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
    const total = monthlyExpenseExecutionEntries.value.length;
    const viaLedger = monthlyExpenseExecutionEntries.value.filter(
      (row) => row.executionSource === 'categorized_ledger',
    ).length;
    const viaFallback = monthlyExpenseExecutionEntries.value.filter(
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

  const monthlyIncomePendingClassification = computed<PendingClassificationSummary>(() => {
    const ambiguousRows = monthlyIncomeExecutionEntries.value.filter(
      (row) => row.executionSource === 'pending_classification',
    ).length;
    const ambiguousAmount = monthlyIncomeExecutionEntries.value.reduce((sum, row) => {
      if (row.executionSource !== 'pending_classification') return sum;
      return sum + (row.categorizedLedgerExecuted ?? 0);
    }, 0);
    return {
      amount: ambiguousAmount + accountingExecutionBuckets.value.incomeUnclassifiedTotal,
      ambiguousRows,
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
    if (mode === 'ledger') return 'Cobertura ledger completa';
    if (mode === 'fallback') return 'Cobertura fallback legacy';
    if (mode === 'mixed') return 'Cobertura mixta completa';
    if (mode === 'partial') return 'Cobertura parcial';
    return 'Sin cobertura';
  }

  function coverageDetail(summary: MonthlyCoverageSummary): string {
    const mode = resolveCoverageMode(summary);
    if (mode === 'ledger') {
      return 'Todas las lineas del mes estan cubiertas por ledger y las acciones legacy quedan bloqueadas.';
    }
    if (mode === 'fallback') {
      return 'Todas las lineas cubiertas usan check-ins legacy; puedes editar cada fila.';
    }
    if (mode === 'mixed') {
      return 'Hay lineas con ledger y lineas legacy; solo se pueden editar las filas en fallback.';
    }
    if (mode === 'partial') {
      return 'Hay lineas cubiertas y lineas pendientes; completa solo las filas sin cobertura.';
    }
    return 'Todavia no hay lineas ejecutadas para este mes.';
  }

  function executionSourceLabel(origin: BudgetExecutionOrigin): string {
    if (origin === 'categorized_ledger') return 'Ledger categorizado';
    if (origin === 'legacy_ledger' || origin === 'legacy_checkin') return 'Fallback legacy';
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
      const [summaryResponse, transactionsResponse] = await Promise.all([
        coreAccountingApi.getMonthlySummary(fiscalYear.value),
        coreAccountingApi.getTransactions({
          year: fiscalYear.value,
          month: selectedExecutionMonth.value,
          status: 'posted',
        }),
      ]);
      accountingMonthlySummary.value = summaryResponse.data ?? null;
      accountingPostedEntries.value = (transactionsResponse.data ?? []).flatMap(
        (transaction) => transaction.entries,
      );
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
      if (ratio > 1) return 'danger';
      if (ratio > 0.85) return 'warn';
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
      const key = `${entry.category}::${entry.subcategory}`;
      const prev = bucket.get(key);
      if (prev) {
        prev.plannedAnnual += amount;
        prev.itemsCount += 1;
        continue;
      }
      bucket.set(key, {
        key,
        categoryKey: entry.category,
        categoryLabel: categoryLabels.get(entry.category) ?? entry.category,
        subcategoryKey: entry.subcategory,
        subcategoryLabel: subcategoryLabels.get(entry.subcategory) ?? entry.subcategory,
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

  const incomeGroups = computed(() =>
    aggregateBudgetRows(filteredIncomeEntries.value, incomeCategoryLabels, incomeSubcategoryLabels),
  );
  const expenseGroups = computed(() =>
    aggregateBudgetRows(
      filteredExpenseEntries.value,
      expenseCategoryLabels,
      expenseSubcategoryLabels,
    ),
  );

  function viewModeLabel(mode: BudgetEntryViewMode): string {
    if (mode === 'recurrent') return 'Solo recurrentes';
    if (mode === 'one_off') return 'Solo puntuales';
    return 'Todos';
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
      subtitle: 'Detalle previsto por categorias y subcategorias del balance anual',
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
      subtitle: 'Detalle previsto por categorias y subcategorias del balance anual',
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
      `Ingresos: ${viewModeLabel(incomeViewMode.value)} · Gastos: ${viewModeLabel(expenseViewMode.value)}`,
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

  async function refreshExpenseExecutionData(): Promise<void> {
    expenseExecutionLoading.value = true;
    expenseExecutionError.value = null;
    try {
      await Promise.all([loadExpenseExecutionSummary(), loadExpenseCheckinsForSelectedMonth()]);
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
    return `${subcategory} · ${row.entry.name}`;
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

  function cleanedExpenseCheckinName(name: string): string {
    return name.replace(/^Compromiso pasivo:\s*/i, '').trim();
  }

  function shortExpenseCategoryLabel(category: string): string {
    if (category === 'real_estate_assets') return 'Act. Inm';
    if (category === 'tangible_assets') return 'Act. Mob';
    if (category === 'consumption_expenses') return 'Gastos';
    if (category === 'financial_investments') return 'Inv. Fin';
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
    return `${subcategory} · ${name}`;
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

  function shortLiquiditySubcategoryLabel(subcategory: string): string {
    if (subcategory === 'bank_account') return 'Cuenta bancaria';
    if (subcategory === 'short_term_deposit') return 'Deposito corto plazo';
    if (subcategory === 'wallet') return 'Monedero';
    if (subcategory === 'crypto_spot_earn') return 'Spot/Earn';
    return 'Liquidez';
  }

  function liquidityCheckinRowSummary(
    row: (typeof monthlyLiquidityExecutionRows.value)[number],
  ): string {
    return `${shortLiquiditySubcategoryLabel(row.asset_subcategory)} · ${row.asset_name}`;
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
      await budgetApi.delete(`/api/net-worth/liquidity-checkins/${row.checkin.id}/`);
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
    incomeTaxonomyLineCounts,
    expenseTaxonomyLineCounts,
    selectedExpenseSummaryMonth,
    selectedExpenseMonthPlanned,
    selectedExpenseMonthDeviation,
    monthlyIncomeExecutionEntries,
    selectedIncomeMonthPlanned,
    selectedIncomeMonthExecuted,
    selectedIncomeMonthDeviation,
    selectedIncomeMonthCompletionRatio,
    incomeEvolutionMonths,
    incomeEvolutionBaseMonthly,
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
    incomeYtdActualByCategory,
    incomeYtdActualBySubcategoryKey,
    buildActualExecution,
    budgetCategoryActualExecution,
    budgetSubcategoryActualExecution,
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
    loadIncomeExecutionSummary,
    refreshIncomeExecutionData,
    loadExpenseExecutionSummary,
    loadExpenseCheckinsForSelectedMonth,
    refreshExpenseExecutionData,
    suggestedExecutedAmountForRow,
    ensureExpenseAdjustAmountPrefilled,
    parseDecimalInput,
    checkinStatusLabel,
    incomeCheckinRowSummary,
    suggestedIncomeExecutedAmountForRow,
    ensureIncomeAdjustAmountPrefilled,
    clearIncomeCheckin,
    upsertIncomeCheckin,
    saveIncomeCheckinFromInput,
    onIncomeCheckinCheckboxToggle,
    onIncomeAdjustAmountBlur,
    resetIncomeCheckinDraftValue,
    cleanedExpenseCheckinName,
    shortExpenseCategoryLabel,
    expenseCheckinCategorySortWeight,
    amountsEqualCents,
    expenseCheckinRowSummary,
    clearExpenseCheckin,
    setExpenseAdjustAmountZero,
    setExpenseAdjustAmountPlanned,
    resetExpenseCheckinDraftValue,
    saveExpenseCheckinFromInput,
    onExpenseCheckinCheckboxToggle,
    onExpenseAdjustAmountBlur,
    upsertExpenseCheckin,
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
    onLiquidityCheckinCheckboxToggle,
    onLiquidityAdjustAmountBlur,
  };
}
