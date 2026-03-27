import { computed, onBeforeUnmount, onMounted, reactive, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAccountingStore } from '@/domains/accounting/store';
import { coreAccountingApi } from '@/domains/accounting/api';
import { coreNetWorthApi } from '@/domains/net-worth/api';
import {
  expenseCategories,
  expenseSubcategories,
  incomeCategories,
  incomeSubcategories,
  useAnnualExpenseStore,
  useAnnualIncomeStore,
  type AnnualExpenseEntry,
  type AnnualIncomeEntry,
  type ExpenseCategoryKey,
  type IncomeCategoryKey,
} from '@/domains/data-input';
import { usePeopleStore, type OwnershipRead } from '@/domains/people/store';
import type {
  LedgerAccount,
  LedgerAccountBalanceSummaryItem,
  LedgerAccountType,
  LedgerEntrySide,
  LedgerTransaction,
  LedgerTransactionWritePayload,
  QuickLedgerMovementType,
  QuickLedgerTransactionWritePayload,
} from '@/domains/accounting/models';
import type { Asset, Liability } from '@/domains/net-worth/models';
import { toApiErrorMessage } from '@/lib/errors';

type TransactionFormRow = {
  key: number;
  account_id: number | null;
  side: LedgerEntrySide;
  amount: string;
  currency: string;
  notes: string;
};
type TransactionFormState = {
  booking_date: string;
  value_date: string;
  booking_time: string;
  description: string;
  notes: string;
  ownership_id: number | null;
  account_id: number | null;
  counterparty_account_id: number | null;
  amount: string;
  destination_amount: string;
  currency: string;
  kind: EditableActivityKind;
  initial_kind: EditableActivityKind;
  investment_direction: 'inflow' | 'outflow';
  category_key: string;
  subcategory_key: string;
  kind_label: string;
};
type PersistedTransactionEntry = {
  account_id: number;
  side: LedgerEntrySide;
  amount: string;
  currency: string;
  flow_family: '' | 'income' | 'expense';
  category_key: string;
  subcategory_key: string;
  annual_income_entry_id: number | null;
  annual_expense_entry_id: number | null;
  asset_id: number | null;
  liability_id: number | null;
  notes: string;
};

type ActivityFilter =
  | 'all'
  | 'income'
  | 'expense'
  | 'transfer'
  | 'investment'
  | 'debt_payment'
  | 'revaluation';
type EditableActivityKind =
  | 'income'
  | 'expense'
  | 'transfer'
  | 'investment'
  | 'debt_payment'
  | 'balance_adjustment'
  | 'revaluation';
type ClassificationActivityKind = 'income' | 'expense';
type CounterpartyEditableKind = 'transfer' | 'investment' | 'debt_payment';
type LiabilityCategoryKey = 'mortgage' | 'personal_loan' | 'credit_card' | 'other';

type LastQuickClassification = {
  category_key: string;
  subcategory_key: string;
};

type ManualPositionType = 'asset' | 'liability';
type AccountPositionMeta = {
  position_type: ManualPositionType;
  category: string;
  subcategory: string;
};
type AccountTimelineTransaction = LedgerTransaction & {
  impactValue: number;
  tone: 'positive' | 'negative' | 'neutral';
};
const EXPENSE_MOVEMENT_CATEGORY_KEYS: ExpenseCategoryKey[] = [
  'consumption_expenses',
  'real_estate_assets',
  'tangible_assets',
];

function formatDecimalInput(raw: string): string {
  return raw.replace(',', '.').trim();
}

function toNumber(raw: string): number {
  const parsed = Number(formatDecimalInput(raw));
  return Number.isFinite(parsed) ? parsed : 0;
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function currencyDecimals(currency: string): number {
  const code = currency.trim().toUpperCase();
  return code === 'BTC' || code === 'ETH' ? 8 : 2;
}

function roundByCurrency(value: number, currency: string): number {
  const decimals = currencyDecimals(currency);
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

export function useAccountingPage() {
  const store = useAccountingStore();
  const incomeStore = useAnnualIncomeStore('core');
  const expenseStore = useAnnualExpenseStore('core');
  const peopleStore = usePeopleStore();
  const {
    loading,
    accountCreationLoading,
    transactionCreationLoading,
    importPreviewLoading,
    importCommitLoading,
    error,
  } = storeToRefs(store);
  const {
    accounts,
    monthlySummary,
    accountBalancesSummary,
    moneyWizImportPreview,
    moneyWizImportCommitResult,
  } = storeToRefs(store);

  const successMessage = ref<string | null>(null);
  const accountActivationLoading = ref(false);
  const manualAssets = ref<Asset[]>([]);
  const manualLiabilities = ref<Liability[]>([]);
  const moneyWizImportFile = ref<File | null>(null);

  const accountForm = reactive({
    name: '',
    account_type: 'asset' as LedgerAccountType,
    currency: 'EUR',
    origin: 'user' as const,
    notes: '',
  });
  const activationForm = reactive({
    position_type: 'asset' as ManualPositionType,
    position_id: null as number | null,
  });

  const quickEntryForm = reactive({
    movement_type: 'expense' as QuickLedgerMovementType,
    investment_direction: 'inflow' as 'inflow' | 'outflow',
    booking_date: new Date().toISOString().slice(0, 10),
    value_date: new Date().toISOString().slice(0, 10),
    description: '',
    ownership_id: null as number | null,
    amount: '',
    destination_amount: '',
    account_id: null as number | null,
    counterparty_account_id: null as number | null,
    liability_account_id: null as number | null,
    interest_account_id: null as number | null,
    principal_amount: '',
    interest_amount: '',
    realized_cost_basis: '',
    realized_gain_loss: '',
    flow_family: '' as '' | 'income' | 'expense',
    category_key: '',
    subcategory_key: '',
    annual_income_entry_id: null as number | null,
    annual_expense_entry_id: null as number | null,
    notes: '',
    revaluation_new_value: '',
  });
  const lastQuickClassification = reactive<
    Record<'income' | 'expense' | 'debt_payment', LastQuickClassification>
  >({
    income: { category_key: '', subcategory_key: '' },
    expense: { category_key: '', subcategory_key: '' },
    debt_payment: { category_key: '', subcategory_key: '' },
  });

  const activityFilters = reactive({
    query: '',
    accountId: 'all',
    kind: 'all' as ActivityFilter,
    categoryKey: '',
    subcategoryKey: '',
  });
  const cuentasFilters = reactive({
    query: '',
    kind: 'all' as ActivityFilter,
    categoryKey: '',
    subcategoryKey: '',
  });

  let rowId = 0;
  const transactionForm = reactive({
    booking_date: new Date().toISOString().slice(0, 10),
    value_date: new Date().toISOString().slice(0, 10),
    description: '',
    status: 'posted' as const,
    origin: 'manual' as const,
    notes: '',
    entries: [
      {
        key: ++rowId,
        account_id: null,
        side: 'debit' as LedgerEntrySide,
        amount: '',
        currency: 'EUR',
        notes: '',
      },
      {
        key: ++rowId,
        account_id: null,
        side: 'credit' as LedgerEntrySide,
        amount: '',
        currency: 'EUR',
        notes: '',
      },
    ] as TransactionFormRow[],
  });
  const editTransactionId = ref<number | null>(null);
  const editTransactionForm = reactive<TransactionFormState>({
    booking_date: new Date().toISOString().slice(0, 10),
    value_date: new Date().toISOString().slice(0, 10),
    booking_time: '12:00',
    description: '',
    notes: '',
    ownership_id: null,
    account_id: null,
    counterparty_account_id: null,
    amount: '',
    destination_amount: '',
    currency: 'EUR',
    kind: 'transfer',
    initial_kind: 'transfer',
    investment_direction: 'inflow',
    category_key: '',
    subcategory_key: '',
    kind_label: '',
  });
  const editTransactionPersistedEntries = ref<PersistedTransactionEntry[]>([]);

  const selectedYear = computed({
    get: () => store.selectedYear,
    set: (value: number) => {
      store.selectedYear = value;
    },
  });

  const selectedMonth = computed({
    get: () => store.selectedMonth,
    set: (value: number) => {
      store.selectedMonth = value;
    },
  });

  const accountTypeOptions: { value: LedgerAccountType; label: string }[] = [
    { value: 'asset', label: 'Activo' },
    { value: 'liability', label: 'Pasivo' },
    { value: 'equity', label: 'Patrimonio neto contable' },
    { value: 'income', label: 'Ingreso' },
    { value: 'expense', label: 'Gasto' },
  ];

  const monthOptions = [
    { value: 1, label: 'Enero' },
    { value: 2, label: 'Febrero' },
    { value: 3, label: 'Marzo' },
    { value: 4, label: 'Abril' },
    { value: 5, label: 'Mayo' },
    { value: 6, label: 'Junio' },
    { value: 7, label: 'Julio' },
    { value: 8, label: 'Agosto' },
    { value: 9, label: 'Septiembre' },
    { value: 10, label: 'Octubre' },
    { value: 11, label: 'Noviembre' },
    { value: 12, label: 'Diciembre' },
  ];

  const yearOptions = computed(() => {
    const currentYear = new Date().getFullYear();
    const values = new Set([currentYear - 1, currentYear, currentYear + 1, selectedYear.value]);
    return Array.from(values).sort((a, b) => b - a);
  });
  function ownershipLabel(ownership: OwnershipRead): string {
    if (ownership.kind === 'individual') {
      return ownership.member?.name?.trim() || `Titularidad #${ownership.id}`;
    }
    const parts = (ownership.splits ?? [])
      .map((split) => {
        const name = split.member?.name?.trim();
        if (!name) return '';
        const percent = String(split.percent ?? '').trim();
        return percent ? `${name} ${percent}%` : name;
      })
      .filter(Boolean);
    return parts.length ? `Compartido (${parts.join(' / ')})` : 'Compartido';
  }
  const ownershipById = computed(() => {
    const map = new Map<number, OwnershipRead>();
    for (const ownership of peopleStore.ownerships) {
      map.set(ownership.id, ownership);
    }
    return map;
  });
  const ownershipOptions = computed(() => {
    const options = peopleStore.ownerships
      .slice()
      .sort((left, right) => left.id - right.id)
      .map((ownership) => ({
        value: ownership.id,
        label: ownershipLabel(ownership),
      }));
    return [{ value: null as number | null, label: 'Sin titularidad' }, ...options];
  });

  const accountMap = computed(
    () => new Map(accounts.value.map((account) => [account.id, account])),
  );
  const liabilityMap = computed(
    () => new Map(manualLiabilities.value.map((liability) => [liability.id, liability])),
  );
  const liquidityAccounts = computed(() =>
    accounts.value.filter((account) => account.account_type === 'asset'),
  );
  const manualPositionTypeOptions: { value: ManualPositionType; label: string }[] = [
    { value: 'asset', label: 'Activo manual' },
    { value: 'liability', label: 'Pasivo manual' },
  ];
  const availableManualAssetOptions = computed(() =>
    manualAssets.value.filter((asset) => asset.is_active && asset.tracking_mode === 'manual'),
  );
  const availableManualLiabilityOptions = computed(() =>
    manualLiabilities.value.filter(
      (liability) => liability.is_active && liability.tracking_mode === 'manual',
    ),
  );
  const availableManualPositionOptions = computed(() =>
    activationForm.position_type === 'asset'
      ? availableManualAssetOptions.value
      : availableManualLiabilityOptions.value,
  );
  const assetNameById = computed(
    () => new Map(manualAssets.value.map((asset) => [asset.id, String(asset.name ?? '').trim()])),
  );
  const liabilityNameById = computed(
    () =>
      new Map(
        manualLiabilities.value.map((liability) => [
          liability.id,
          String(liability.name ?? '').trim(),
        ]),
      ),
  );
  function accountDisplayName(account: LedgerAccount): string {
    if (account.asset_id != null) {
      return assetNameById.value.get(account.asset_id) || account.name;
    }
    if (account.liability_id != null) {
      return liabilityNameById.value.get(account.liability_id) || account.name;
    }
    return account.name;
  }
  const accountPositionMetaByAccountId = computed(() => {
    const map = new Map<number, AccountPositionMeta>();
    accounts.value.forEach((account) => {
      if (account.asset_id != null) {
        const asset = manualAssets.value.find((row) => row.id === account.asset_id);
        if (asset) {
          map.set(account.id, {
            position_type: 'asset',
            category: String(asset.category ?? '').trim() || 'other',
            subcategory: String(asset.subcategory ?? '').trim() || 'other',
          });
          return;
        }
      }
      if (account.liability_id != null) {
        const liability = manualLiabilities.value.find((row) => row.id === account.liability_id);
        if (liability) {
          map.set(account.id, {
            position_type: 'liability',
            category: String(liability.category ?? '').trim() || 'other',
            subcategory: String(liability.subcategory ?? '').trim() || 'other',
          });
        }
      }
    });
    return map;
  });
  const hasAvailableManualPositions = computed(
    () =>
      availableManualAssetOptions.value.length > 0 ||
      availableManualLiabilityOptions.value.length > 0,
  );
  const incomeOptions = computed<AnnualIncomeEntry[]>(() =>
    incomeStore.entries.value
      .filter((entry) => entry.fiscalYear === selectedYear.value)
      .sort((a, b) => a.name.localeCompare(b.name, 'es')),
  );
  const expenseOptions = computed<AnnualExpenseEntry[]>(() =>
    expenseStore.entries.value
      .filter((entry) => entry.fiscalYear === selectedYear.value)
      .sort((a, b) => a.name.localeCompare(b.name, 'es')),
  );
  const transferCounterpartyOptions = computed(() =>
    liquidityAccounts.value.filter((account) => account.id !== quickEntryForm.account_id),
  );
  const investmentCounterpartyOptions = computed(() =>
    accounts.value.filter(
      (account) =>
        account.account_type === 'asset' &&
        account.id !== normalizeAccountId(quickEntryForm.account_id) &&
        account.asset_id != null,
    ),
  );
  function normalizeAccountId(value: unknown): number | null {
    if (typeof value === 'number') return Number.isFinite(value) ? value : null;
    if (typeof value === 'string') {
      const trimmed = value.trim();
      if (!trimmed) return null;
      const parsed = Number(trimmed);
      return Number.isFinite(parsed) ? parsed : null;
    }
    return null;
  }
  const quickSelectedLiquidityAccountId = computed(() =>
    normalizeAccountId(quickEntryForm.account_id),
  );
  const quickSelectedInvestmentAccountId = computed(() =>
    normalizeAccountId(quickEntryForm.counterparty_account_id),
  );
  function resolveAccountById(value: unknown): LedgerAccount | null {
    const id = normalizeAccountId(value);
    if (id == null) return null;
    return (
      accountMap.value.get(id) ??
      accounts.value.find((account) => normalizeAccountId(account.id) === id) ??
      null
    );
  }
  const quickSelectedLiquidityAccount = computed(() =>
    resolveAccountById(quickEntryForm.account_id),
  );
  const quickSelectedInvestmentAccount = computed(() =>
    resolveAccountById(quickEntryForm.counterparty_account_id),
  );
  const quickInvestmentOriginCurrency = computed(() => {
    if (quickEntryForm.movement_type !== 'investment') return '';
    if (quickEntryForm.investment_direction === 'outflow') {
      return quickSelectedInvestmentAccount.value?.currency ?? '';
    }
    return quickSelectedLiquidityAccount.value?.currency ?? '';
  });
  const quickInvestmentDestinationCurrency = computed(() => {
    if (quickEntryForm.movement_type !== 'investment') return '';
    if (quickEntryForm.investment_direction === 'outflow') {
      return quickSelectedLiquidityAccount.value?.currency ?? '';
    }
    return quickSelectedInvestmentAccount.value?.currency ?? '';
  });
  const quickInvestmentIsCrossCurrency = computed(() => {
    const origin = quickInvestmentOriginCurrency.value.trim().toUpperCase();
    const destination = quickInvestmentDestinationCurrency.value.trim().toUpperCase();
    return Boolean(origin && destination && origin !== destination);
  });
  const revaluationAccountOptions = computed(() =>
    accounts.value.filter(
      (account) => account.account_type === 'asset' && account.asset_id != null,
    ),
  );
  const revaluationCurrentBalance = computed((): number | null => {
    if (quickEntryForm.movement_type !== 'revaluation') return null;
    if (quickEntryForm.account_id == null) return null;
    const account = accountMap.value.get(quickEntryForm.account_id);
    return account != null ? toNumber(account.current_balance) : null;
  });
  const revaluationDelta = computed((): number | null => {
    const raw = quickEntryForm.revaluation_new_value.trim();
    if (!raw) return null;
    const currentBalance = revaluationCurrentBalance.value;
    if (currentBalance == null) return null;
    return round2(toNumber(raw) - currentBalance);
  });
  const liabilityCounterpartyOptions = computed(() =>
    accounts.value.filter(
      (account) => account.account_type === 'liability' && account.liability_id != null,
    ),
  );
  const quickSelectedLiabilityCategory = computed<LiabilityCategoryKey | null>(() => {
    const liabilityAccountId = normalizeAccountId(quickEntryForm.liability_account_id);
    if (liabilityAccountId == null) return null;
    const liabilityId = accountMap.value.get(liabilityAccountId)?.liability_id ?? null;
    if (liabilityId == null) return null;
    const category = liabilityMap.value.get(liabilityId)?.category ?? null;
    if (
      category === 'mortgage' ||
      category === 'personal_loan' ||
      category === 'credit_card' ||
      category === 'other'
    ) {
      return category;
    }
    return null;
  });
  const debtInterestOptions = computed(() =>
    accounts.value.filter((account) => account.account_type === 'expense'),
  );
  function hasQuickClassification(): boolean {
    return Boolean(quickEntryForm.category_key && quickEntryForm.subcategory_key);
  }
  function debtPaymentBreakdownReady(amountValue: number): boolean {
    const principalValue = toNumber(quickEntryForm.principal_amount);
    const interestValue = toNumber(quickEntryForm.interest_amount);
    if (quickEntryForm.liability_account_id == null) return false;
    if (principalValue <= 0 || interestValue < 0) return false;
    if (interestValue > 0 && quickEntryForm.interest_account_id == null) return false;
    if (interestValue > 0 && !hasQuickClassification()) return false;
    return Math.abs(principalValue + interestValue - amountValue) < 0.000001;
  }
  const quickEntryReady = computed(() => {
    if (!quickEntryForm.description.trim()) return false;
    if (!quickEntryForm.booking_date || !quickEntryForm.value_date) return false;
    if (quickEntryForm.movement_type === 'revaluation') {
      if (quickEntryForm.account_id == null) return false;
      const delta = revaluationDelta.value;
      return delta != null && Math.abs(delta) >= 0.005;
    }
    const amountValue = toNumber(quickEntryForm.amount);
    if (amountValue <= 0) return false;
    if (quickSelectedLiquidityAccountId.value == null) return false;
    if (quickEntryForm.movement_type === 'transfer') {
      return normalizeAccountId(quickEntryForm.counterparty_account_id) != null;
    }
    if (quickEntryForm.movement_type === 'investment') {
      if (quickSelectedInvestmentAccountId.value == null) return false;
      if (!quickInvestmentIsCrossCurrency.value) return true;
      return toNumber(quickEntryForm.destination_amount) > 0;
    }
    if (quickEntryForm.movement_type === 'debt_payment') {
      return debtPaymentBreakdownReady(amountValue);
    }
    if (
      (quickEntryForm.movement_type === 'income' || quickEntryForm.movement_type === 'expense') &&
      !hasQuickClassification()
    ) {
      return false;
    }
    return true;
  });
  const quickEntryNeedsClassification = computed(
    () =>
      quickEntryForm.movement_type === 'income' ||
      quickEntryForm.movement_type === 'expense' ||
      quickEntryForm.movement_type === 'investment' ||
      quickEntryForm.movement_type === 'debt_payment',
  );
  const quickCategoryOptions = computed(() => {
    if (quickEntryForm.movement_type === 'income') return incomeCategories;
    if (quickEntryForm.movement_type === 'expense') {
      return expenseCategories.filter((row) =>
        EXPENSE_MOVEMENT_CATEGORY_KEYS.includes(row.value as ExpenseCategoryKey),
      );
    }
    if (quickEntryForm.movement_type === 'investment') {
      if (quickEntryForm.investment_direction === 'outflow') {
        return incomeCategories.filter((row) => row.value === 'capital_gains');
      }
      return expenseCategories.filter((row) =>
        ['financial_investments', 'real_estate_assets', 'tangible_assets'].includes(row.value),
      );
    }
    if (quickEntryForm.movement_type === 'debt_payment') {
      if (quickSelectedLiabilityCategory.value === 'mortgage') {
        return expenseCategories.filter((row) => row.value === 'real_estate_assets');
      }
      return expenseCategories.filter((row) => row.value === 'consumption_expenses');
    }
    return [];
  });
  const quickSubcategoryOptions = computed(() => {
    if (!quickEntryForm.category_key) return [];
    if (quickEntryForm.movement_type === 'income') {
      return incomeSubcategories.filter(
        (row) => row.category === (quickEntryForm.category_key as IncomeCategoryKey),
      );
    }
    if (quickEntryForm.movement_type === 'expense' || quickEntryForm.movement_type === 'debt_payment') {
      return expenseSubcategories.filter(
        (row) => row.category === (quickEntryForm.category_key as ExpenseCategoryKey),
      );
    }
    if (quickEntryForm.movement_type === 'investment') {
      if (quickEntryForm.investment_direction === 'outflow') {
        return incomeSubcategories.filter(
          (row) => row.category === (quickEntryForm.category_key as IncomeCategoryKey),
        );
      }
      return expenseSubcategories.filter(
        (row) => row.category === (quickEntryForm.category_key as ExpenseCategoryKey),
      );
    }
    return [];
  });
  const quickCategoryLocked = computed(() => {
    if (quickEntryForm.movement_type === 'investment') return true;
    if (quickEntryForm.movement_type === 'debt_payment') return true;
    return false;
  });
  const quickSubcategoryLocked = computed(() => {
    if (quickEntryForm.movement_type === 'investment') {
      return quickEntryForm.investment_direction === 'outflow';
    }
    if (quickEntryForm.movement_type === 'debt_payment') {
      return quickSelectedLiabilityCategory.value === 'mortgage';
    }
    return false;
  });
  function categoryOptionsByKind(kind: ActivityFilter) {
    if (kind === 'income') return incomeCategories;
    if (kind === 'expense') {
      return expenseCategories.filter((row) =>
        EXPENSE_MOVEMENT_CATEGORY_KEYS.includes(row.value as ExpenseCategoryKey),
      );
    }
    if (kind === 'investment') {
      return [
        ...expenseCategories.filter((row) =>
          [
            'savings_allocation',
            'financial_investments',
            'real_estate_assets',
            'tangible_assets',
          ].includes(row.value),
        ),
        ...incomeCategories.filter((row) => row.value === 'capital_gains'),
      ];
    }
    if (kind === 'debt_payment') {
      return expenseCategories.filter((row) =>
        ['real_estate_assets', 'tangible_assets', 'consumption_expenses'].includes(row.value),
      );
    }
    return [...incomeCategories, ...expenseCategories];
  }
  const filterCategoryOptions = computed(() => categoryOptionsByKind(activityFilters.kind));
  const cuentasFilterCategoryOptions = computed(() => categoryOptionsByKind(cuentasFilters.kind));

  function subcategoryOptionsByCategory(categoryKey: string) {
    if (!categoryKey) return [];
    const asIncome = incomeSubcategories.filter((row) => row.category === categoryKey);
    if (asIncome.length) return asIncome;
    return expenseSubcategories.filter((row) => row.category === categoryKey);
  }
  const filterSubcategoryOptions = computed(() =>
    subcategoryOptionsByCategory(activityFilters.categoryKey),
  );
  const cuentasFilterSubcategoryOptions = computed(() =>
    subcategoryOptionsByCategory(cuentasFilters.categoryKey),
  );

  const annualIncomeOptionsCompatible = computed<AnnualIncomeEntry[]>(() => {
    if (quickEntryForm.movement_type !== 'income') return [];
    if (!quickEntryForm.category_key || !quickEntryForm.subcategory_key) return [];
    return incomeOptions.value.filter(
      (entry) =>
        entry.category === quickEntryForm.category_key &&
        entry.subcategory === quickEntryForm.subcategory_key,
    );
  });
  const annualExpenseOptionsCompatible = computed<AnnualExpenseEntry[]>(() => {
    if (
      quickEntryForm.movement_type !== 'expense' &&
      quickEntryForm.movement_type !== 'debt_payment'
    ) {
      return [];
    }
    if (!quickEntryForm.category_key || !quickEntryForm.subcategory_key) return [];
    return expenseOptions.value.filter(
      (entry) =>
        entry.category === quickEntryForm.category_key &&
        entry.subcategory === quickEntryForm.subcategory_key,
    );
  });
  const quickMovementTypeOptions: { value: QuickLedgerMovementType; label: string }[] = [
    { value: 'income', label: 'Ingreso' },
    { value: 'expense', label: 'Gasto' },
    { value: 'transfer', label: 'Transferencia' },
    { value: 'investment', label: 'Inversion' },
    { value: 'debt_payment', label: 'Pago deuda' },
    { value: 'revaluation', label: 'Revalorizacion' },
  ];
  const editMovementTypeOptions: { value: EditableActivityKind; label: string }[] = [
    { value: 'income', label: 'Ingreso' },
    { value: 'expense', label: 'Gasto' },
    { value: 'transfer', label: 'Transferencia' },
    { value: 'investment', label: 'Inversion' },
    { value: 'debt_payment', label: 'Deuda' },
    { value: 'balance_adjustment', label: 'Ajuste' },
    { value: 'revaluation', label: 'Revalorizacion' },
  ];
  const editAccountOptions = computed(() =>
    accounts.value
      .filter((account) => account.account_type === 'asset' || account.account_type === 'liability')
      .sort((a, b) => a.name.localeCompare(b.name, 'es')),
  );
  function isClassificationKind(kind: EditableActivityKind): boolean {
    return kind === 'income' || kind === 'expense' || kind === 'investment' || kind === 'debt_payment';
  }

  function isCounterpartyKind(kind: EditableActivityKind): kind is CounterpartyEditableKind {
    return kind === 'transfer' || kind === 'investment' || kind === 'debt_payment';
  }

  const editKindNeedsClassification = computed(() =>
    isClassificationKind(editTransactionForm.kind),
  );
  const editKindNeedsCounterparty = computed(() => isCounterpartyKind(editTransactionForm.kind));
  const editCounterpartyLabel = computed(() => {
    if (editTransactionForm.kind === 'investment') return 'Cuenta de inversion';
    if (editTransactionForm.kind === 'debt_payment') return 'Cuenta de pasivo';
    return 'Contracuenta';
  });
  const editSelectedAccountCurrentBalance = computed(() => {
    if (editTransactionForm.account_id == null) return null;
    const account = accountMap.value.get(editTransactionForm.account_id);
    if (!account) return null;
    return toNumber(account.current_balance).toFixed(2);
  });
  const editCounterpartyOptions = computed(() => {
    const baseOptions = editAccountOptions.value.filter(
      (account) => account.id !== editTransactionForm.account_id,
    );
    if (editTransactionForm.kind === 'investment') {
      return baseOptions.filter(
        (account) => account.account_type === 'asset' && account.asset_id != null,
      );
    }
    if (editTransactionForm.kind === 'debt_payment') {
      return baseOptions.filter(
        (account) => account.account_type === 'liability' && account.liability_id != null,
      );
    }
    return baseOptions;
  });
  const editCounterpartyMissingHint = computed(() => {
    if (!editKindNeedsCounterparty.value) return '';
    if (editCounterpartyOptions.value.length > 0) return '';
    if (editTransactionForm.kind === 'investment') {
      return 'No hay cuentas de inversion contables activas. Activa tracking contable en la posicion manual para poder usarla aqui.';
    }
    if (editTransactionForm.kind === 'debt_payment') {
      return 'No hay cuentas de pasivo contables activas. Activa tracking contable en el pasivo manual para poder usarlo aqui.';
    }
    return 'No hay contracuentas disponibles para el tipo seleccionado.';
  });
  const editSelectedLiquidityAccount = computed(() =>
    editTransactionForm.account_id != null ? accountMap.value.get(editTransactionForm.account_id) ?? null : null,
  );
  const editSelectedInvestmentAccount = computed(() =>
    editTransactionForm.counterparty_account_id != null
      ? accountMap.value.get(editTransactionForm.counterparty_account_id) ?? null
      : null,
  );
  const editSelectedDebtLiabilityCategory = computed<LiabilityCategoryKey | null>(() => {
    if (editTransactionForm.kind !== 'debt_payment') return null;
    const liabilityAccountId = editTransactionForm.counterparty_account_id;
    if (liabilityAccountId == null) return null;
    const liabilityId = accountMap.value.get(liabilityAccountId)?.liability_id ?? null;
    if (liabilityId == null) return null;
    const category = liabilityMap.value.get(liabilityId)?.category ?? null;
    if (
      category === 'mortgage' ||
      category === 'personal_loan' ||
      category === 'credit_card' ||
      category === 'other'
    ) {
      return category;
    }
    return null;
  });
  const editInvestmentOriginCurrency = computed(() => {
    if (editTransactionForm.kind === 'transfer') {
      return editSelectedLiquidityAccount.value?.currency ?? '';
    }
    if (editTransactionForm.kind !== 'investment') return '';
    if (editTransactionForm.investment_direction === 'outflow') {
      return editSelectedInvestmentAccount.value?.currency ?? '';
    }
    return editSelectedLiquidityAccount.value?.currency ?? '';
  });
  const editInvestmentDestinationCurrency = computed(() => {
    if (editTransactionForm.kind === 'transfer') {
      return editSelectedInvestmentAccount.value?.currency ?? '';
    }
    if (editTransactionForm.kind !== 'investment') return '';
    if (editTransactionForm.investment_direction === 'outflow') {
      return editSelectedLiquidityAccount.value?.currency ?? '';
    }
    return editSelectedInvestmentAccount.value?.currency ?? '';
  });
  const editInvestmentIsCrossCurrency = computed(() => {
    const origin = editInvestmentOriginCurrency.value.trim().toUpperCase();
    const destination = editInvestmentDestinationCurrency.value.trim().toUpperCase();
    return Boolean(origin && destination && origin !== destination);
  });

  function hasValidEditCounterpartySelection(kind: EditableActivityKind): boolean {
    if (!isCounterpartyKind(kind)) return true;
    const selectedId = editTransactionForm.counterparty_account_id;
    if (selectedId == null) return false;
    return editCounterpartyOptions.value.some((account) => account.id === selectedId);
  }
  const editCategoryOptions = computed(() => {
    if (editTransactionForm.kind === 'income') return incomeCategories;
    if (editTransactionForm.kind === 'expense') {
      return expenseCategories.filter((row) =>
        EXPENSE_MOVEMENT_CATEGORY_KEYS.includes(row.value as ExpenseCategoryKey),
      );
    }
    if (editTransactionForm.kind === 'investment') {
      if (editTransactionForm.investment_direction === 'outflow') {
        return incomeCategories.filter((row) => row.value === 'capital_gains');
      }
      return expenseCategories.filter((row) =>
        ['financial_investments', 'real_estate_assets', 'tangible_assets'].includes(row.value),
      );
    }
    if (editTransactionForm.kind === 'debt_payment') {
      if (editSelectedDebtLiabilityCategory.value === 'mortgage') {
        return expenseCategories.filter((row) => row.value === 'real_estate_assets');
      }
      return expenseCategories.filter((row) => row.value === 'consumption_expenses');
    }
    return [];
  });
  const editSubcategoryOptions = computed(() => {
    if (!editTransactionForm.category_key) return [];
    if (editTransactionForm.kind === 'income') {
      return incomeSubcategories.filter(
        (row) => row.category === (editTransactionForm.category_key as IncomeCategoryKey),
      );
    }
    if (editTransactionForm.kind === 'expense' || editTransactionForm.kind === 'debt_payment') {
      return expenseSubcategories.filter(
        (row) => row.category === (editTransactionForm.category_key as ExpenseCategoryKey),
      );
    }
    if (editTransactionForm.kind === 'investment') {
      if (editTransactionForm.investment_direction === 'outflow') {
        return incomeSubcategories.filter(
          (row) => row.category === (editTransactionForm.category_key as IncomeCategoryKey),
        );
      }
      return expenseSubcategories.filter(
        (row) => row.category === (editTransactionForm.category_key as ExpenseCategoryKey),
      );
    }
    return [];
  });
  const editCategoryLocked = computed(() => {
    if (editTransactionForm.kind === 'investment') return true;
    if (editTransactionForm.kind === 'debt_payment') return true;
    return false;
  });
  const editSubcategoryLocked = computed(() => {
    if (editTransactionForm.kind === 'investment') {
      return editTransactionForm.investment_direction === 'outflow';
    }
    if (editTransactionForm.kind === 'debt_payment') {
      return editSelectedDebtLiabilityCategory.value === 'mortgage';
    }
    return false;
  });
  const editEntryReady = computed(() => {
    if (!editTransactionForm.description.trim()) return false;
    if (!editTransactionForm.booking_date || !editTransactionForm.value_date) return false;
    if (editTransactionForm.account_id == null) return false;
    const parsedAmount = Number(formatDecimalInput(editTransactionForm.amount));
    if (!Number.isFinite(parsedAmount)) return false;
    if (
      editTransactionForm.kind !== 'balance_adjustment' &&
      editTransactionForm.kind !== 'revaluation' &&
      parsedAmount <= 0
    )
      return false;
    if (editTransactionForm.kind === 'revaluation' && parsedAmount === 0) return false;
    if (
      editKindNeedsCounterparty.value &&
      (editTransactionForm.counterparty_account_id == null ||
        editTransactionForm.counterparty_account_id === editTransactionForm.account_id)
    ) {
      return false;
    }
    if (editKindNeedsClassification.value) {
      return Boolean(editTransactionForm.category_key && editTransactionForm.subcategory_key);
    }
    if (
      (editTransactionForm.kind === 'investment' || editTransactionForm.kind === 'transfer') &&
      editInvestmentIsCrossCurrency.value
    ) {
      const destinationValue = Number(formatDecimalInput(editTransactionForm.destination_amount));
      return Number.isFinite(destinationValue) && destinationValue > 0;
    }
    return true;
  });

  watch(
    () => transactionForm.entries.map((entry) => entry.account_id),
    (accountIds) => {
      accountIds.forEach((accountId, index) => {
        if (accountId == null) return;
        const account = accountMap.value.get(accountId);
        if (!account) return;
        transactionForm.entries[index]!.currency = account.currency;
      });
    },
    { deep: true },
  );
  watch(
    () => quickEntryForm.movement_type,
    (movementType) => {
      quickEntryForm.counterparty_account_id = null;
      quickEntryForm.liability_account_id = null;
      quickEntryForm.interest_account_id = null;
      quickEntryForm.principal_amount = '';
      quickEntryForm.interest_amount = '';
      quickEntryForm.realized_cost_basis = '';
      quickEntryForm.realized_gain_loss = '';
      quickEntryForm.destination_amount = '';
      quickEntryForm.flow_family = '';
      quickEntryForm.revaluation_new_value = '';
      quickEntryForm.investment_direction = 'inflow';
      if (movementType !== 'income') quickEntryForm.annual_income_entry_id = null;
      if (movementType !== 'expense' && movementType !== 'debt_payment') {
        quickEntryForm.annual_expense_entry_id = null;
      }
      const remembered =
        movementType === 'income' || movementType === 'expense' || movementType === 'debt_payment'
          ? lastQuickClassification[movementType]
          : null;
      if (remembered) {
        quickEntryForm.category_key = remembered.category_key;
        quickEntryForm.subcategory_key = remembered.subcategory_key;
      } else {
        quickEntryForm.category_key = '';
        quickEntryForm.subcategory_key = '';
      }
    },
  );
  watch(
    () => [quickEntryForm.movement_type, quickEntryForm.investment_direction] as const,
    () => {
      if (quickEntryForm.movement_type !== 'investment') return;
      if (quickEntryForm.investment_direction === 'outflow') {
        quickEntryForm.category_key = 'capital_gains';
        quickEntryForm.subcategory_key = 'sale_financial_assets';
      } else if (!quickEntryForm.category_key) {
        quickEntryForm.category_key = 'financial_investments';
      }
    },
    { immediate: true },
  );
  watch(
    () => [quickEntryForm.movement_type, quickEntryForm.liability_account_id] as const,
    () => {
      if (quickEntryForm.movement_type !== 'debt_payment') return;
      if (quickSelectedLiabilityCategory.value === 'mortgage') {
        quickEntryForm.category_key = 'real_estate_assets';
        quickEntryForm.subcategory_key = 'mortgage_principal';
      } else {
        quickEntryForm.category_key = 'consumption_expenses';
        if (quickEntryForm.subcategory_key === 'mortgage_principal') {
          quickEntryForm.subcategory_key = 'financial_commitments';
        }
      }
    },
    { immediate: true },
  );
  watch(
    () => quickEntryForm.movement_type,
    (movementType) => {
      if (movementType !== 'expense') return;
      if (
        !EXPENSE_MOVEMENT_CATEGORY_KEYS.includes(quickEntryForm.category_key as ExpenseCategoryKey)
      ) {
        quickEntryForm.category_key = 'consumption_expenses';
      }
    },
  );
  watch(
    () => quickEntryForm.category_key,
    () => {
      if (
        quickEntryForm.subcategory_key &&
        !quickSubcategoryOptions.value.some((row) => row.value === quickEntryForm.subcategory_key)
      ) {
        quickEntryForm.subcategory_key = '';
        quickEntryForm.annual_income_entry_id = null;
        quickEntryForm.annual_expense_entry_id = null;
      }
    },
  );
  watch(
    () => quickEntryForm.subcategory_key,
    (value) => {
      if (!value) return;
      if (quickEntryForm.movement_type === 'income') {
        lastQuickClassification.income = {
          category_key: quickEntryForm.category_key,
          subcategory_key: value,
        };
      } else if (quickEntryForm.movement_type === 'expense') {
        lastQuickClassification.expense = {
          category_key: quickEntryForm.category_key,
          subcategory_key: value,
        };
      } else if (quickEntryForm.movement_type === 'debt_payment') {
        lastQuickClassification.debt_payment = {
          category_key: quickEntryForm.category_key,
          subcategory_key: value,
        };
      }
    },
  );
  watch(
    () => editTransactionForm.kind,
    (kind) => {
      if (editTransactionForm.account_id == null && editAccountOptions.value.length) {
        editTransactionForm.account_id = editAccountOptions.value[0]!.id;
      }
      if (!isClassificationKind(kind)) {
        editTransactionForm.category_key = '';
        editTransactionForm.subcategory_key = '';
      }
      if (kind !== 'investment') {
        editTransactionForm.investment_direction = 'inflow';
      }
      if (isCounterpartyKind(kind)) {
        if (!hasValidEditCounterpartySelection(kind)) {
          editTransactionForm.counterparty_account_id =
            editCounterpartyOptions.value[0]?.id ?? null;
        }
        if (
          editTransactionForm.counterparty_account_id == null &&
          editCounterpartyOptions.value.length
        ) {
          editTransactionForm.counterparty_account_id = editCounterpartyOptions.value[0]!.id;
        }
        return;
      }
      editTransactionForm.counterparty_account_id = null;
      if (kind === 'balance_adjustment' && editTransactionForm.account_id != null) {
        const selectedAccount = accountMap.value.get(editTransactionForm.account_id);
        if (selectedAccount) {
          editTransactionForm.amount = toNumber(selectedAccount.current_balance).toFixed(2);
        }
      }
    },
  );
  watch(
    () =>
      [
        editTransactionForm.kind,
        editTransactionForm.investment_direction,
        editTransactionForm.counterparty_account_id,
      ] as const,
    () => {
      if (editTransactionForm.kind === 'investment') {
        if (editTransactionForm.investment_direction === 'outflow') {
          editTransactionForm.category_key = 'capital_gains';
          editTransactionForm.subcategory_key = 'sale_financial_assets';
        } else if (!editTransactionForm.category_key) {
          editTransactionForm.category_key = 'financial_investments';
        }
        return;
      }
      if (editTransactionForm.kind === 'expense') {
        if (
          !EXPENSE_MOVEMENT_CATEGORY_KEYS.includes(
            editTransactionForm.category_key as ExpenseCategoryKey,
          )
        ) {
          editTransactionForm.category_key = 'consumption_expenses';
        }
        return;
      }
      if (editTransactionForm.kind !== 'debt_payment') return;
      if (editSelectedDebtLiabilityCategory.value === 'mortgage') {
        editTransactionForm.category_key = 'real_estate_assets';
        editTransactionForm.subcategory_key = 'mortgage_principal';
      } else {
        editTransactionForm.category_key = 'consumption_expenses';
        if (editTransactionForm.subcategory_key === 'mortgage_principal') {
          editTransactionForm.subcategory_key = 'financial_commitments';
        }
      }
    },
    { immediate: true },
  );
  watch(
    () => editTransactionForm.account_id,
    (accountId) => {
      if (accountId == null) {
        editTransactionForm.currency = 'EUR';
        return;
      }
      const account = accountMap.value.get(accountId);
      if (!account) return;
      editTransactionForm.currency = account.currency;
      if (editTransactionForm.kind === 'balance_adjustment') {
        editTransactionForm.amount = toNumber(account.current_balance).toFixed(2);
      }
      if (!isCounterpartyKind(editTransactionForm.kind)) return;
      if (editTransactionForm.counterparty_account_id === accountId) {
        editTransactionForm.counterparty_account_id = editCounterpartyOptions.value[0]?.id ?? null;
      }
    },
  );
  watch(
    () => editTransactionForm.category_key,
    () => {
      if (
        editTransactionForm.subcategory_key &&
        !editSubcategoryOptions.value.some(
          (row) => row.value === editTransactionForm.subcategory_key,
        )
      ) {
        editTransactionForm.subcategory_key = '';
      }
    },
  );
  watch(
    () => activationForm.position_type,
    () => {
      activationForm.position_id = null;
    },
  );

  const debitTotal = computed(() =>
    transactionForm.entries
      .filter((entry) => entry.side === 'debit')
      .reduce((sum, entry) => sum + toNumber(entry.amount), 0),
  );
  const creditTotal = computed(() =>
    transactionForm.entries
      .filter((entry) => entry.side === 'credit')
      .reduce((sum, entry) => sum + toNumber(entry.amount), 0),
  );
  const transactionBalanced = computed(
    () =>
      transactionForm.entries.length >= 2 &&
      debitTotal.value > 0 &&
      debitTotal.value === creditTotal.value,
  );
  const summaryRows = computed(() =>
    (monthlySummary.value?.months ?? []).map((row) => ({
      ...row,
      incomeValue: toNumber(row.income_total),
      expenseValue: toNumber(row.expense_total),
      uncategorizedValue: toNumber(row.uncategorized_total),
    })),
  );
  const liquidityBalanceRows = computed(() =>
    (accountBalancesSummary.value?.accounts ?? []).map((row) => ({
      ...row,
      currentBalanceValue: toNumber(row.current_balance),
      periodDebitValue: toNumber(row.period_debit_total),
      periodCreditValue: toNumber(row.period_credit_total),
      periodNetChangeValue: toNumber(row.period_net_change),
    })),
  );
  const liquidityBalanceTotal = computed(() =>
    toNumber(accountBalancesSummary.value?.totals_by_account_type.asset ?? '0'),
  );

  // ── Tab state & per-account/all-movements pagination ──────────────
  type MovementsTab = 'cuentas' | 'todos' | 'estadisticas';
  const activeTab = ref<MovementsTab>('cuentas');

  const MOVEMENTS_PAGE_SIZE = 50;
  const cuentasSelectedAccountId = ref<number | null>(null);
  const cuentasDateFrom = ref('');
  const cuentasDateTo = ref('');
  const todosDateFrom = ref('');
  const todosDateTo = ref('');
  const todosTransactions = ref<LedgerTransaction[]>([]);
  const todosNextCursor = ref<string | null>(null);
  const todosTotalCount = ref(0);
  const todosLoading = ref(false);
  const todosLoadingMore = ref(false);
  const cuentasTransactions = ref<AccountTimelineTransaction[]>([]);
  const cuentasNextCursor = ref<string | null>(null);
  const cuentasTotalCount = ref(0);
  const cuentasLoading = ref(false);
  const cuentasLoadingMore = ref(false);
  let todosAbortController: AbortController | null = null;
  let cuentasAbortController: AbortController | null = null;
  let todosSearchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  let cuentasSearchDebounceTimer: ReturnType<typeof setTimeout> | null = null;
  const hasImportedTransactions = computed(() =>
    todosTransactions.value.some((transaction) => transaction.origin === 'import'),
  );

  function signedImpact(accountType: string, side: 'debit' | 'credit', amount: string): number {
    const value = toNumber(amount);
    if (value === 0) return 0;
    const increasesOnDebit = accountType === 'asset' || accountType === 'expense';
    return (increasesOnDebit ? side === 'debit' : side === 'credit') ? value : -value;
  }

  function impactTone(value: number): 'positive' | 'negative' | 'neutral' {
    if (value > 0) return 'positive';
    if (value < 0) return 'negative';
    return 'neutral';
  }

  function toApiKind(kind: ActivityFilter): string | undefined {
    if (kind === 'all') return undefined;
    if (kind === 'investment') return 'investment_purchase';
    return kind;
  }

  function toApiAccountId(rawAccountId: string): number | undefined {
    const parsed = rawAccountId === 'all' ? NaN : Number(rawAccountId);
    return Number.isFinite(parsed) ? parsed : undefined;
  }

  function isCanceledRequestError(error: unknown): boolean {
    if ((error as { name?: string }).name === 'CanceledError') return true;
    if ((error as { name?: string }).name === 'AbortError') return true;
    if ((error as { code?: string }).code === 'ERR_CANCELED') return true;
    const message = (error as { message?: string }).message;
    if (typeof message === 'string') {
      const normalized = message.trim().toLowerCase();
      if (normalized === 'canceled' || normalized === 'cancelled') return true;
    }
    return false;
  }

  function toAccountTimelineRows(
    rows: LedgerTransaction[],
    accountId: number,
    accountType: LedgerAccountType,
  ): AccountTimelineTransaction[] {
    return rows.map((transaction) => {
      const impactValue = transaction.entries
        .filter((entry) => entry.account_id === accountId)
        .reduce((sum, entry) => sum + signedImpact(accountType, entry.side, entry.amount), 0);
      return { ...transaction, impactValue, tone: impactTone(impactValue) };
    });
  }

  const cuentasSelectedAccount = computed(() =>
    cuentasSelectedAccountId.value != null
      ? (accounts.value.find((a) => a.id === cuentasSelectedAccountId.value) ?? null)
      : null,
  );

  const todosHasMore = computed(() => todosNextCursor.value !== null);
  const cuentasHasMore = computed(() => cuentasNextCursor.value !== null);

  async function fetchTodosPage(reset: boolean): Promise<void> {
    if (reset) {
      todosAbortController?.abort();
      todosAbortController = new AbortController();
      todosNextCursor.value = null;
      todosTotalCount.value = 0;
    } else if (!todosNextCursor.value || todosLoading.value || todosLoadingMore.value) {
      return;
    }
    const controller = todosAbortController ?? new AbortController();
    todosAbortController = controller;
    todosLoading.value = reset;
    todosLoadingMore.value = !reset;
    try {
      const page = await store.fetchTransactionsPage(
        {
          page_size: MOVEMENTS_PAGE_SIZE,
          cursor: reset ? undefined : (todosNextCursor.value ?? undefined),
          query: activityFilters.query.trim() || undefined,
          kind: toApiKind(activityFilters.kind),
          account_id: toApiAccountId(activityFilters.accountId),
          date_from: todosDateFrom.value || undefined,
          date_to: todosDateTo.value || undefined,
          category_key: activityFilters.categoryKey || undefined,
          subcategory_key: activityFilters.subcategoryKey || undefined,
        },
        { signal: controller.signal },
      );
      todosTransactions.value = reset ? page.results : todosTransactions.value.concat(page.results);
      todosNextCursor.value = page.next_cursor;
      todosTotalCount.value = page.total_count;
    } catch (error: unknown) {
      if (isCanceledRequestError(error)) return;
      throw error;
    } finally {
      todosLoading.value = false;
      todosLoadingMore.value = false;
    }
  }

  async function fetchCuentasPage(reset: boolean): Promise<void> {
    const account = cuentasSelectedAccount.value;
    const accountId = cuentasSelectedAccountId.value;
    if (!account || accountId == null) {
      cuentasTransactions.value = [];
      cuentasNextCursor.value = null;
      cuentasTotalCount.value = 0;
      return;
    }
    if (reset) {
      cuentasAbortController?.abort();
      cuentasAbortController = new AbortController();
      cuentasNextCursor.value = null;
      cuentasTotalCount.value = 0;
    } else if (!cuentasNextCursor.value || cuentasLoading.value || cuentasLoadingMore.value) {
      return;
    }
    const controller = cuentasAbortController ?? new AbortController();
    cuentasAbortController = controller;
    cuentasLoading.value = reset;
    cuentasLoadingMore.value = !reset;
    try {
      const page = await store.fetchTransactionsPage(
        {
          page_size: MOVEMENTS_PAGE_SIZE,
          cursor: reset ? undefined : (cuentasNextCursor.value ?? undefined),
          account_id: accountId,
          query: cuentasFilters.query.trim() || undefined,
          kind: toApiKind(cuentasFilters.kind),
          date_from: cuentasDateFrom.value || undefined,
          date_to: cuentasDateTo.value || undefined,
          category_key: cuentasFilters.categoryKey || undefined,
          subcategory_key: cuentasFilters.subcategoryKey || undefined,
        },
        { signal: controller.signal },
      );
      const pageRows = toAccountTimelineRows(page.results, accountId, account.account_type);
      cuentasTransactions.value = reset ? pageRows : cuentasTransactions.value.concat(pageRows);
      cuentasNextCursor.value = page.next_cursor;
      cuentasTotalCount.value = page.total_count;
    } catch (error: unknown) {
      if (isCanceledRequestError(error)) return;
      throw error;
    } finally {
      cuentasLoading.value = false;
      cuentasLoadingMore.value = false;
    }
  }

  async function loadMoreCuentas() {
    await fetchCuentasPage(false);
  }

  async function loadMoreTodos() {
    await fetchTodosPage(false);
  }

  watch(cuentasSelectedAccountId, () => {
    void fetchCuentasPage(true);
  });

  watch([cuentasDateFrom, cuentasDateTo], () => {
    if (cuentasSelectedAccountId.value != null) {
      void fetchCuentasPage(true);
    }
  });
  watch(
    [
      () => cuentasFilters.kind,
      () => cuentasFilters.categoryKey,
      () => cuentasFilters.subcategoryKey,
    ],
    () => {
      if (cuentasSelectedAccountId.value != null) {
        void fetchCuentasPage(true);
      }
    },
  );

  watch(
    [
      () => activityFilters.kind,
      () => activityFilters.accountId,
      () => activityFilters.categoryKey,
      () => activityFilters.subcategoryKey,
      todosDateFrom,
      todosDateTo,
    ],
    () => {
      void fetchTodosPage(true);
    },
  );

  watch(
    () => activityFilters.kind,
    () => {
      const nextOptions = filterCategoryOptions.value;
      activityFilters.categoryKey = nextOptions.length === 1 ? nextOptions[0]!.value : '';
      activityFilters.subcategoryKey = '';
    },
  );
  watch(
    () => cuentasFilters.kind,
    () => {
      const nextOptions = cuentasFilterCategoryOptions.value;
      cuentasFilters.categoryKey = nextOptions.length === 1 ? nextOptions[0]!.value : '';
      cuentasFilters.subcategoryKey = '';
    },
  );

  watch(
    () => activityFilters.categoryKey,
    () => {
      activityFilters.subcategoryKey = '';
    },
  );
  watch(
    () => cuentasFilters.categoryKey,
    () => {
      cuentasFilters.subcategoryKey = '';
    },
  );

  watch(
    () => activityFilters.query,
    () => {
      if (todosSearchDebounceTimer) clearTimeout(todosSearchDebounceTimer);
      todosSearchDebounceTimer = setTimeout(() => {
        void fetchTodosPage(true);
      }, 300);
    },
  );
  watch(
    () => cuentasFilters.query,
    () => {
      if (cuentasSearchDebounceTimer) clearTimeout(cuentasSearchDebounceTimer);
      cuentasSearchDebounceTimer = setTimeout(() => {
        if (cuentasSelectedAccountId.value != null) {
          void fetchCuentasPage(true);
        }
      }, 300);
    },
  );

  function transactionMainAmount(t: LedgerTransaction): number {
    const debitTotal = t.entries
      .filter((e) => e.side === 'debit')
      .reduce((sum, e) => sum + toNumber(e.amount), 0);
    return debitTotal;
  }

  function resetAccountForm() {
    accountForm.name = '';
    accountForm.account_type = 'asset';
    accountForm.currency = 'EUR';
    accountForm.origin = 'user';
    accountForm.notes = '';
  }

  function resetTransactionForm() {
    transactionForm.booking_date = new Date().toISOString().slice(0, 10);
    transactionForm.value_date = transactionForm.booking_date;
    transactionForm.description = '';
    transactionForm.status = 'posted';
    transactionForm.origin = 'manual';
    transactionForm.notes = '';
    transactionForm.entries = [
      {
        key: ++rowId,
        account_id: null,
        side: 'debit',
        amount: '',
        currency: 'EUR',
        notes: '',
      },
      {
        key: ++rowId,
        account_id: null,
        side: 'credit',
        amount: '',
        currency: 'EUR',
        notes: '',
      },
    ];
  }

  function resetQuickEntryForm() {
    quickEntryForm.movement_type = 'expense';
    quickEntryForm.investment_direction = 'inflow';
    quickEntryForm.booking_date = new Date().toISOString().slice(0, 10);
    quickEntryForm.value_date = quickEntryForm.booking_date;
    quickEntryForm.description = '';
    quickEntryForm.ownership_id = null;
    quickEntryForm.amount = '';
    quickEntryForm.destination_amount = '';
    quickEntryForm.account_id = null;
    quickEntryForm.counterparty_account_id = null;
    quickEntryForm.liability_account_id = null;
    quickEntryForm.interest_account_id = null;
    quickEntryForm.principal_amount = '';
    quickEntryForm.interest_amount = '';
    quickEntryForm.realized_cost_basis = '';
    quickEntryForm.realized_gain_loss = '';
    quickEntryForm.flow_family = '';
    quickEntryForm.category_key = '';
    quickEntryForm.subcategory_key = '';
    quickEntryForm.annual_income_entry_id = null;
    quickEntryForm.annual_expense_entry_id = null;
    quickEntryForm.notes = '';
    quickEntryForm.revaluation_new_value = '';
  }
  function resetEditTransactionForm() {
    editTransactionId.value = null;
    editTransactionPersistedEntries.value = [];
    editTransactionForm.booking_date = new Date().toISOString().slice(0, 10);
    editTransactionForm.value_date = editTransactionForm.booking_date;
    editTransactionForm.booking_time = '12:00';
    editTransactionForm.description = '';
    editTransactionForm.notes = '';
    editTransactionForm.ownership_id = null;
    editTransactionForm.account_id = null;
    editTransactionForm.counterparty_account_id = null;
    editTransactionForm.amount = '';
    editTransactionForm.destination_amount = '';
    editTransactionForm.currency = 'EUR';
    editTransactionForm.kind = 'transfer';
    editTransactionForm.initial_kind = 'transfer';
    editTransactionForm.investment_direction = 'inflow';
    editTransactionForm.category_key = '';
    editTransactionForm.subcategory_key = '';
    editTransactionForm.kind_label = '';
  }

  function toEditableKind(transaction: LedgerTransaction): EditableActivityKind {
    const detected = getTransactionActivityKind(transaction);
    if (detected === 'income') return 'income';
    if (detected === 'expense') return 'expense';
    if (detected === 'investment') return 'investment';
    if (detected === 'debt_payment') return 'debt_payment';
    if (detected === 'revaluation') return 'revaluation';
    return 'transfer';
  }

  function activityKindDisplay(kind: EditableActivityKind): string {
    if (kind === 'income') return 'Ingreso';
    if (kind === 'expense') return 'Gasto';
    if (kind === 'transfer') return 'Transferencia';
    if (kind === 'investment') return 'Inversion';
    if (kind === 'debt_payment') return 'Deuda';
    if (kind === 'revaluation') return 'Revalorizacion';
    return 'Ajuste';
  }

  function getTransactionEditAmount(transaction: LedgerTransaction): string {
    const displayCurrency = transaction.entries[0]?.currency ?? 'EUR';
    const decimals = currencyDecimals(displayCurrency);
    const debitTotalValue = transaction.entries
      .filter((entry) => entry.side === 'debit')
      .reduce((sum, entry) => sum + toNumber(entry.amount), 0);
    if (transaction.activity_kind === 'revaluation') {
      const assetEntry = transaction.entries.find(
        (entry) => accountMap.value.get(entry.account_id)?.account_type === 'asset',
      );
      if (assetEntry?.side === 'credit') return (-debitTotalValue).toFixed(decimals);
    }
    if (transaction.activity_kind === 'investment_purchase') {
      const creditEntry =
        transaction.entries.find((entry) => entry.side === 'credit') ?? transaction.entries[1] ?? null;
      if (creditEntry) {
        return toNumber(creditEntry.amount).toFixed(currencyDecimals(creditEntry.currency));
      }
    }
    if (transaction.activity_kind === 'transfer') {
      const creditEntry =
        transaction.entries.find((entry) => entry.side === 'credit') ?? transaction.entries[1] ?? null;
      if (creditEntry) {
        return toNumber(creditEntry.amount).toFixed(currencyDecimals(creditEntry.currency));
      }
    }
    return debitTotalValue.toFixed(decimals);
  }

  function getTransactionEditDestinationAmount(transaction: LedgerTransaction): string {
    if (
      transaction.activity_kind !== 'investment_purchase' &&
      transaction.activity_kind !== 'transfer'
    )
      return '';
    const debitEntry =
      transaction.entries.find((entry) => entry.side === 'debit') ?? transaction.entries[0] ?? null;
    if (!debitEntry) return '';
    return toNumber(debitEntry.amount).toFixed(currencyDecimals(debitEntry.currency));
  }

  function getInvestmentDirection(transaction: LedgerTransaction): 'inflow' | 'outflow' {
    if (
      transaction.investment_direction === 'inflow' ||
      transaction.investment_direction === 'outflow'
    ) {
      return transaction.investment_direction;
    }
    const investmentEntry = transaction.entries.find((entry) => entry.asset_id != null);
    if (!investmentEntry) return 'inflow';
    return investmentEntry.side === 'credit' ? 'outflow' : 'inflow';
  }

  function resolveEditAccountsForKind(
    transaction: LedgerTransaction,
    kind: EditableActivityKind,
    debitEntry: LedgerTransaction['entries'][number] | null,
    creditEntry: LedgerTransaction['entries'][number] | null,
  ): { accountId: number | null; counterpartyAccountId: number | null } {
    type EditAccountsResolution = {
      accountId: number | null;
      counterpartyAccountId: number | null;
    };
    type KindResolver = () => EditAccountsResolution;

    const resolveIncome: KindResolver = () => {
      return {
        accountId: debitEntry?.account_id ?? null,
        counterpartyAccountId: null,
      };
    };

    const resolveExpense: KindResolver = () => {
      return {
        accountId: creditEntry?.account_id ?? null,
        counterpartyAccountId: null,
      };
    };

    const resolveDebtPayment: KindResolver = () => {
      const liabilityEntry =
        transaction.entries.find(
          (entry) => accountMap.value.get(entry.account_id)?.account_type === 'liability',
        ) ??
        transaction.entries.find((entry) => entry.side === 'debit') ??
        debitEntry;
      return {
        accountId: creditEntry?.account_id ?? null,
        counterpartyAccountId: liabilityEntry?.account_id ?? null,
      };
    };

    const resolveInvestment: KindResolver = () => {
      const direction = getInvestmentDirection(transaction);
      if (direction === 'outflow') {
        return {
          accountId: debitEntry?.account_id ?? null,
          counterpartyAccountId: creditEntry?.account_id ?? null,
        };
      }
      return {
        accountId: creditEntry?.account_id ?? null,
        counterpartyAccountId: debitEntry?.account_id ?? null,
      };
    };

    const resolveRevaluation: KindResolver = () => {
      const assetEntry =
        transaction.entries.find(
          (entry) => accountMap.value.get(entry.account_id)?.account_type === 'asset',
        ) ?? debitEntry;
      return {
        accountId: assetEntry?.account_id ?? null,
        counterpartyAccountId: null,
      };
    };

    const resolveTransfer: KindResolver = () => ({
      accountId: creditEntry?.account_id ?? null,
      counterpartyAccountId: debitEntry?.account_id ?? null,
    });

    const resolverMap: Record<EditableActivityKind, KindResolver> = {
      income: resolveIncome,
      expense: resolveExpense,
      debt_payment: resolveDebtPayment,
      investment: resolveInvestment,
      revaluation: resolveRevaluation,
      transfer: resolveTransfer,
      balance_adjustment: resolveTransfer,
    };
    return resolverMap[kind]();
  }

  function fillEditTransactionForm(transaction: LedgerTransaction) {
    const primaryClassifiedEntry =
      transaction.entries.find(
        (entry) =>
          Boolean(entry.flow_family) &&
          Boolean(entry.category_key) &&
          Boolean(entry.subcategory_key),
      ) ?? null;
    editTransactionId.value = transaction.id;
    editTransactionPersistedEntries.value = transaction.entries.map((entry) => ({
      account_id: entry.account_id,
      side: entry.side,
      amount: String(entry.amount),
      currency: entry.currency,
      flow_family: entry.flow_family ?? '',
      category_key: entry.category_key ?? '',
      subcategory_key: entry.subcategory_key ?? '',
      annual_income_entry_id: entry.annual_income_entry_id ?? null,
      annual_expense_entry_id: entry.annual_expense_entry_id ?? null,
      asset_id: entry.asset_id ?? null,
      liability_id: entry.liability_id ?? null,
      notes: entry.notes ?? '',
    }));
    editTransactionForm.booking_date = transaction.booking_date;
    editTransactionForm.value_date = transaction.value_date;
    editTransactionForm.booking_time = '12:00';
    editTransactionForm.description = transaction.description;
    editTransactionForm.notes = transaction.notes ?? '';
    editTransactionForm.ownership_id = transaction.ownership_id ?? null;
    editTransactionForm.currency = transaction.entries[0]?.currency ?? 'EUR';
    editTransactionForm.amount = getTransactionEditAmount(transaction);
    editTransactionForm.destination_amount = getTransactionEditDestinationAmount(transaction);
    const kind = toEditableKind(transaction);
    editTransactionForm.kind = kind;
    editTransactionForm.initial_kind = kind;
    const debitEntry =
      transaction.entries.find((entry) => entry.side === 'debit') ?? transaction.entries[0] ?? null;
    const creditEntry =
      transaction.entries.find((entry) => entry.side === 'credit') ??
      transaction.entries[1] ??
      null;
    const { accountId, counterpartyAccountId } = resolveEditAccountsForKind(
      transaction,
      kind,
      debitEntry,
      creditEntry,
    );
    editTransactionForm.account_id = accountId;
    editTransactionForm.counterparty_account_id = counterpartyAccountId;
    editTransactionForm.investment_direction =
      kind === 'investment' ? getInvestmentDirection(transaction) : 'inflow';
    editTransactionForm.category_key = primaryClassifiedEntry?.category_key ?? '';
    editTransactionForm.subcategory_key = primaryClassifiedEntry?.subcategory_key ?? '';
    editTransactionForm.kind_label = activityKindDisplay(kind);
  }

  function scaleEntriesToAmount(
    entries: PersistedTransactionEntry[],
    targetAmount: number,
    currency: string,
  ): PersistedTransactionEntry[] {
    const decimals = currencyDecimals(currency);
    const scaled = entries.map((entry) => ({ ...entry }));
    const debitIndexes = scaled
      .map((entry, index) => (entry.side === 'debit' ? index : -1))
      .filter((index) => index >= 0);
    const creditIndexes = scaled
      .map((entry, index) => (entry.side === 'credit' ? index : -1))
      .filter((index) => index >= 0);
    const currentDebitTotal = debitIndexes.reduce(
      (sum, index) => sum + toNumber(scaled[index]!.amount),
      0,
    );
    if (currentDebitTotal <= 0) return scaled;
    const factor = targetAmount / currentDebitTotal;
    const roundForCurrency = (value: number) => roundByCurrency(value, currency);
    const applySide = (indexes: number[]) => {
      if (!indexes.length) return;
      let allocated = 0;
      indexes.forEach((index, position) => {
        const currentValue = toNumber(scaled[index]!.amount);
        const isLast = position === indexes.length - 1;
        const nextValue = isLast
          ? roundForCurrency(targetAmount - allocated)
          : roundForCurrency(currentValue * factor);
        allocated = roundForCurrency(allocated + nextValue);
        scaled[index]!.amount = nextValue.toFixed(decimals);
      });
    };
    applySide(debitIndexes);
    applySide(creditIndexes);
    return scaled;
  }

  function scaleLegacyMixedCurrencyEntries(
    entries: PersistedTransactionEntry[],
    anchorAccountId: number,
    targetAmount: number,
  ): PersistedTransactionEntry[] {
    const scaled = entries.map((entry) => ({ ...entry }));
    const anchorIndexes = scaled
      .map((entry, index) => (entry.account_id === anchorAccountId ? index : -1))
      .filter((index) => index >= 0);
    if (!anchorIndexes.length) return scaled;
    const currentAnchorTotal = anchorIndexes.reduce(
      (sum, index) => sum + toNumber(scaled[index]!.amount),
      0,
    );
    if (currentAnchorTotal <= 0) return scaled;
    const factor = targetAmount / currentAnchorTotal;
    const sideBuckets = new Map<'debit' | 'credit', number[]>();
    scaled.forEach((entry, index) => {
      const bucket = sideBuckets.get(entry.side) ?? [];
      bucket.push(index);
      sideBuckets.set(entry.side, bucket);
    });
    const applySide = (indexes: number[]) => {
      if (!indexes.length) return;
      const currentSideTotal = indexes.reduce(
        (sum, index) => sum + toNumber(scaled[index]!.amount),
        0,
      );
      if (currentSideTotal <= 0) return;
      let allocated = 0;
      indexes.forEach((index, position) => {
        const row = scaled[index]!;
        const currentValue = toNumber(row.amount);
        const roundedValue = roundByCurrency(currentValue * factor, row.currency);
        const targetSideTotal = roundByCurrency(currentSideTotal * factor, row.currency);
        const isLast = position === indexes.length - 1;
        const nextValue = isLast
          ? roundByCurrency(targetSideTotal - allocated, row.currency)
          : roundedValue;
        allocated = roundByCurrency(allocated + nextValue, row.currency);
        row.amount = nextValue.toFixed(currencyDecimals(row.currency));
      });
    };
    applySide(sideBuckets.get('debit') ?? []);
    applySide(sideBuckets.get('credit') ?? []);
    return scaled;
  }

  function setEditedKindOnEntries(
    entries: PersistedTransactionEntry[],
    kind: EditableActivityKind,
    categoryKey: string,
    subcategoryKey: string,
    investmentDirection: 'inflow' | 'outflow',
  ): PersistedTransactionEntry[] {
    const nextEntries = entries.map((entry) => ({
      ...entry,
      flow_family: '' as '' | 'income' | 'expense',
      category_key: '',
      subcategory_key: '',
      annual_income_entry_id: null,
      annual_expense_entry_id: null,
      asset_id: null,
      liability_id: null,
    }));
    if (!isClassificationKind(kind)) return nextEntries;

    const classifyAsIncome =
      kind === 'income' || (kind === 'investment' && investmentDirection === 'outflow');
    const preferredSide = classifyAsIncome ? 'credit' : 'debit';
    const preferredEntry =
      nextEntries.find((entry) => entry.side === preferredSide) ?? nextEntries[0] ?? null;
    if (!preferredEntry) return nextEntries;
    preferredEntry.flow_family = classifyAsIncome ? 'income' : 'expense';
    preferredEntry.category_key = categoryKey;
    preferredEntry.subcategory_key = subcategoryKey;
    return nextEntries;
  }

  function setEditedAccountsOnEntries(
    entries: PersistedTransactionEntry[],
    kind: EditableActivityKind,
    accountId: number,
    counterpartyAccountId: number | null,
    investmentDirection: 'inflow' | 'outflow',
  ): PersistedTransactionEntry[] {
    const nextEntries = entries.map((entry) => ({ ...entry }));
    const debitEntry =
      nextEntries.find((entry) => entry.side === 'debit') ?? nextEntries[0] ?? null;
    const creditEntry =
      nextEntries.find((entry) => entry.side === 'credit') ?? nextEntries[1] ?? null;
    const setAccount = (entry: PersistedTransactionEntry | null, targetId: number | null) => {
      if (!entry || targetId == null) return;
      const targetAccount = accountMap.value.get(targetId);
      if (!targetAccount) return;
      entry.account_id = targetId;
      entry.currency = targetAccount.currency;
      entry.asset_id =
        targetAccount.account_type === 'asset' ? (targetAccount.asset_id ?? null) : null;
      entry.liability_id =
        targetAccount.account_type === 'liability' ? (targetAccount.liability_id ?? null) : null;
    };
    if (kind === 'income') {
      setAccount(debitEntry, accountId);
      setAccount(creditEntry, counterpartyAccountId);
      return nextEntries;
    }
    if (kind === 'expense') {
      setAccount(creditEntry, accountId);
      setAccount(debitEntry, counterpartyAccountId);
      return nextEntries;
    }
    if (kind === 'investment') {
      if (investmentDirection === 'outflow') {
        setAccount(debitEntry, accountId);
        setAccount(creditEntry, counterpartyAccountId);
      } else {
        setAccount(creditEntry, accountId);
        setAccount(debitEntry, counterpartyAccountId);
      }
      return nextEntries;
    }
    if (kind === 'balance_adjustment' || kind === 'revaluation') {
      return nextEntries;
    }
    setAccount(creditEntry, accountId);
    setAccount(debitEntry, counterpartyAccountId);
    return nextEntries;
  }

  function resolveClassificationCounterpartyAccountId(
    kind: ClassificationActivityKind,
    currency: string,
  ): number | null {
    const expectedType = kind === 'income' ? 'income' : 'expense';
    const candidates = accounts.value.filter((account) => account.account_type === expectedType);
    if (!candidates.length) return null;
    return (
      candidates.find((account) => account.currency === currency && account.origin === 'system')
        ?.id ??
      candidates.find((account) => account.currency === currency)?.id ??
      candidates.find((account) => account.origin === 'system')?.id ??
      candidates[0]?.id ??
      null
    );
  }

  async function ensureClassificationCounterpartyAccountId(
    kind: ClassificationActivityKind,
    currency: string,
  ): Promise<number | null> {
    const existingId = resolveClassificationCounterpartyAccountId(kind, currency);
    if (existingId != null) return existingId;

    const normalizedCurrency = currency.trim().toUpperCase();
    const accountType = kind === 'income' ? 'income' : 'expense';
    const defaultName = kind === 'income' ? 'Ingresos sin categoria' : 'Gastos sin categoria';
    try {
      const created = await coreAccountingApi.createAccount({
        name: defaultName,
        account_type: accountType,
        currency: normalizedCurrency,
        origin: 'system',
        notes: 'Autogenerada al reclasificar movimiento desde edicion.',
      });
      await store.refreshAll();
      return created.data.id;
    } catch (error: unknown) {
      store.error = toApiErrorMessage(error);
      return null;
    }
  }

  function resolveAdjustmentCounterpartyAccountId(currency: string): number | null {
    const candidates = accounts.value.filter((account) => account.account_type === 'equity');
    if (!candidates.length) return null;
    return (
      candidates.find((account) => account.currency === currency && account.origin === 'system')
        ?.id ??
      candidates.find((account) => account.currency === currency)?.id ??
      candidates.find((account) => account.origin === 'system')?.id ??
      candidates[0]?.id ??
      null
    );
  }

  async function ensureAdjustmentCounterpartyAccountId(currency: string): Promise<number | null> {
    const existingId = resolveAdjustmentCounterpartyAccountId(currency);
    if (existingId != null) return existingId;

    const normalizedCurrency = currency.trim().toUpperCase();
    try {
      const created = await coreAccountingApi.createAccount({
        name: 'Ajustes de saldo',
        account_type: 'equity',
        currency: normalizedCurrency,
        origin: 'system',
        notes: 'Autogenerada al ajustar saldos desde edicion de movimientos.',
      });
      await store.refreshAll();
      return created.data.id;
    } catch (error: unknown) {
      store.error = toApiErrorMessage(error);
      return null;
    }
  }

  function accountDeltaSide(accountType: LedgerAccountType, delta: number): LedgerEntrySide {
    const debitIncreases = accountType === 'asset' || accountType === 'expense';
    if (delta >= 0) return debitIncreases ? 'debit' : 'credit';
    return debitIncreases ? 'credit' : 'debit';
  }

  function buildBalanceAdjustmentEntries(
    amount: number,
    targetAccount: LedgerAccount,
    counterpartyAccount: LedgerAccount,
  ): PersistedTransactionEntry[] {
    const targetSide = accountDeltaSide(targetAccount.account_type, amount);
    const counterpartySide = targetSide === 'debit' ? 'credit' : 'debit';
    const decimals = currencyDecimals(targetAccount.currency);
    const absoluteAmount = Math.abs(roundByCurrency(amount, targetAccount.currency)).toFixed(
      decimals,
    );
    const makeEntry = (
      account: LedgerAccount,
      side: LedgerEntrySide,
    ): PersistedTransactionEntry => ({
      account_id: account.id,
      side,
      amount: absoluteAmount,
      currency: account.currency,
      flow_family: '',
      category_key: '',
      subcategory_key: '',
      annual_income_entry_id: null,
      annual_expense_entry_id: null,
      asset_id: null,
      liability_id: null,
      notes: '',
    });
    return [makeEntry(targetAccount, targetSide), makeEntry(counterpartyAccount, counterpartySide)];
  }

  // eslint-disable-next-line complexity
  function validateEditedTransactionInput(): {
    parsedAmount: number;
    selectedAccount: LedgerAccount;
  } | null {
    const parsedAmount = Number(formatDecimalInput(editTransactionForm.amount));
    if (!Number.isFinite(parsedAmount)) {
      store.error = 'Introduce un importe valido.';
      return null;
    }
    if (
      editTransactionForm.kind !== 'balance_adjustment' &&
      editTransactionForm.kind !== 'revaluation' &&
      parsedAmount <= 0
    ) {
      store.error = 'El importe debe ser mayor que 0.';
      return null;
    }
    if (editTransactionForm.kind === 'revaluation' && parsedAmount === 0) {
      store.error = 'El importe de la revalorizacion no puede ser cero.';
      return null;
    }
    if (
      (editTransactionForm.kind === 'investment' || editTransactionForm.kind === 'transfer') &&
      editInvestmentIsCrossCurrency.value
    ) {
      const parsedDestination = Number(formatDecimalInput(editTransactionForm.destination_amount));
      if (!Number.isFinite(parsedDestination) || parsedDestination <= 0) {
        store.error = 'Introduce un importe destino valido para el movimiento multimoneda.';
        return null;
      }
    }
    if (editKindNeedsClassification.value) {
      if (!editTransactionForm.category_key || !editTransactionForm.subcategory_key) {
        store.error = 'Selecciona categoria y subcategoria para el tipo elegido.';
        return null;
      }
    }
    if (editTransactionForm.account_id == null) {
      store.error = 'Selecciona una cuenta.';
      return null;
    }
    if (
      editKindNeedsCounterparty.value &&
      (editTransactionForm.counterparty_account_id == null ||
        editTransactionForm.counterparty_account_id === editTransactionForm.account_id)
    ) {
      store.error =
        editTransactionForm.kind === 'debt_payment'
          ? 'Selecciona una cuenta de pasivo distinta para la deuda.'
          : 'Selecciona una contracuenta distinta.';
      return null;
    }
    if (
      editKindNeedsCounterparty.value &&
      !hasValidEditCounterpartySelection(editTransactionForm.kind)
    ) {
      store.error =
        editTransactionForm.kind === 'investment'
          ? 'Selecciona una cuenta de inversion contable valida.'
          : editTransactionForm.kind === 'debt_payment'
            ? 'Selecciona una cuenta de pasivo contable valida.'
            : 'Selecciona una contracuenta valida para el tipo elegido.';
      return null;
    }
    const selectedAccount = accountMap.value.get(editTransactionForm.account_id);
    if (!selectedAccount) {
      store.error = 'La cuenta seleccionada no existe o no esta activa.';
      return null;
    }
    return { parsedAmount, selectedAccount };
  }

  async function resolveEditedTransactionEntries(
    parsedAmount: number,
    selectedAccount: LedgerAccount,
  ): Promise<PersistedTransactionEntry[] | null> {
    if (editTransactionForm.kind === 'revaluation') {
      // Rebuild entries from scratch so that sign changes (gain↔loss) correctly flip debit/credit sides.
      // Use the currently selected account, not the persisted asset account, so account changes are applied.
      const counterpartyEntry = editTransactionPersistedEntries.value.find(
        (entry) =>
          entry.account_id !== selectedAccount.id &&
          accountMap.value.get(entry.account_id)?.account_type !== 'asset',
      );
      const counterpartyAccount = counterpartyEntry
        ? accountMap.value.get(counterpartyEntry.account_id)
        : undefined;
      if (!counterpartyAccount) {
        const scaled = scaleEntriesToAmount(
          editTransactionPersistedEntries.value,
          roundByCurrency(Math.abs(parsedAmount), selectedAccount.currency),
          selectedAccount.currency,
        );
        const firstEntry = scaled[0] ?? null;
        if (firstEntry) {
          firstEntry.account_id = selectedAccount.id;
          firstEntry.currency = selectedAccount.currency;
          firstEntry.asset_id = selectedAccount.asset_id ?? null;
          firstEntry.liability_id = null;
        }
        return scaled;
      }
      return buildBalanceAdjustmentEntries(parsedAmount, selectedAccount, counterpartyAccount);
    }
    if (editTransactionForm.kind === 'balance_adjustment') {
      const targetBalance = round2(parsedAmount);
      const currentBalance = round2(toNumber(selectedAccount.current_balance));
      const delta = round2(targetBalance - currentBalance);
      if (Math.abs(delta) < 0.005) {
        store.error = 'El saldo de la cuenta ya coincide con el objetivo.';
        return null;
      }
      const counterpartyId = await ensureAdjustmentCounterpartyAccountId(selectedAccount.currency);
      if (counterpartyId == null) {
        store.error = 'No hay cuenta de contrapartida para registrar el ajuste.';
        return null;
      }
      const counterpartyAccount = accountMap.value.get(counterpartyId);
      if (!counterpartyAccount) {
        store.error = 'No se pudo resolver la cuenta de contrapartida del ajuste.';
        return null;
      }
      return buildBalanceAdjustmentEntries(delta, selectedAccount, counterpartyAccount);
    }
    const editedAmount = roundByCurrency(parsedAmount, selectedAccount.currency);
    const classificationCounterpartyAccountId = editKindNeedsCounterparty.value
      ? editTransactionForm.counterparty_account_id
      : await ensureClassificationCounterpartyAccountId(
          editTransactionForm.kind as ClassificationActivityKind,
          selectedAccount.currency,
        );
    if (!editKindNeedsCounterparty.value && classificationCounterpartyAccountId == null) {
      store.error = 'No hay cuenta contable de contrapartida para ese tipo y moneda.';
      return null;
    }
    const scaledEntries = scaleEntriesToAmount(
      editTransactionPersistedEntries.value,
      editedAmount,
      selectedAccount.currency,
    );
    const kindAdjustedEntries =
      editTransactionForm.kind === editTransactionForm.initial_kind
        ? scaledEntries
        : setEditedKindOnEntries(
            scaledEntries,
            editTransactionForm.kind,
            editTransactionForm.category_key,
            editTransactionForm.subcategory_key,
            editTransactionForm.investment_direction,
          );
    const accountAdjustedEntries = setEditedAccountsOnEntries(
      kindAdjustedEntries,
      editTransactionForm.kind,
      editTransactionForm.account_id!,
      classificationCounterpartyAccountId,
      editTransactionForm.investment_direction,
    );
    if (
      (editTransactionForm.kind === 'investment' || editTransactionForm.kind === 'transfer') &&
      editInvestmentIsCrossCurrency.value
    ) {
      const destinationAmount = Number(formatDecimalInput(editTransactionForm.destination_amount));
      const debitEntry = accountAdjustedEntries.find((entry) => entry.side === 'debit') ?? null;
      const creditEntry = accountAdjustedEntries.find((entry) => entry.side === 'credit') ?? null;
      if (debitEntry) {
        debitEntry.amount = roundByCurrency(destinationAmount, debitEntry.currency).toFixed(
          currencyDecimals(debitEntry.currency),
        );
      }
      if (creditEntry) {
        creditEntry.amount = roundByCurrency(parsedAmount, creditEntry.currency).toFixed(
          currencyDecimals(creditEntry.currency),
        );
      }
    }
    return accountAdjustedEntries;
  }

  function getTransactionActivityKind(
    transaction: LedgerTransaction,
  ): Exclude<ActivityFilter, 'all'> | 'other' {
    if (transaction.activity_kind === 'investment_purchase') return 'investment';
    if (transaction.activity_kind === 'income') return 'income';
    if (transaction.activity_kind === 'expense') return 'expense';
    if (transaction.activity_kind === 'transfer') return 'transfer';
    if (transaction.activity_kind === 'debt_payment') return 'debt_payment';
    if (transaction.activity_kind === 'revaluation') return 'revaluation';
    return 'other';
  }

  function activityKindLabel(transaction: LedgerTransaction): string {
    const kind = getTransactionActivityKind(transaction);
    if (kind === 'income') return 'Ingreso';
    if (kind === 'expense') return 'Gasto';
    if (kind === 'transfer') return 'Transferencia';
    if (kind === 'investment') {
      return getInvestmentDirection(transaction) === 'outflow'
        ? 'Retirada inversion'
        : 'Aporte inversion';
    }
    if (kind === 'debt_payment') return 'Pago deuda';
    if (kind === 'revaluation') return 'Revalorizacion';
    return 'Asiento';
  }
  function transactionOwnershipLabel(transaction: LedgerTransaction): string | null {
    if (transaction.ownership_id == null) return null;
    const ownership = ownershipById.value.get(transaction.ownership_id);
    if (!ownership) return `Titularidad #${transaction.ownership_id}`;
    return ownershipLabel(ownership);
  }
  function transactionClassificationLabel(transaction: LedgerTransaction): string | null {
    const classifiedEntry =
      transaction.entries.find(
        (entry) =>
          Boolean(entry.flow_family) &&
          Boolean(entry.category_key) &&
          Boolean(entry.subcategory_key),
      ) ?? null;
    if (!classifiedEntry) return null;
    const categoryKey = classifiedEntry.category_key;
    const subcategoryKey = classifiedEntry.subcategory_key;
    if (classifiedEntry.flow_family === 'income') {
      const categoryLabel =
        incomeCategories.find((row) => row.value === categoryKey)?.label ?? categoryKey;
      const subcategoryLabel =
        incomeSubcategories.find(
          (row) => row.category === categoryKey && row.value === subcategoryKey,
        )?.label ?? subcategoryKey;
      return `${categoryLabel} -> ${subcategoryLabel}`;
    }
    const categoryLabel =
      expenseCategories.find((row) => row.value === categoryKey)?.label ?? categoryKey;
    const subcategoryLabel =
      expenseSubcategories.find(
        (row) => row.category === categoryKey && row.value === subcategoryKey,
      )?.label ?? subcategoryKey;
    return `${categoryLabel} -> ${subcategoryLabel}`;
  }
  function transactionAccountTrailLabel(transaction: LedgerTransaction): string {
    const operationalEntries = transaction.entries.filter((entry) => {
      const account = accountMap.value.get(entry.account_id);
      return account?.account_type === 'asset' || account?.account_type === 'liability';
    });
    if (!operationalEntries.length) {
      return '-';
    }
    const uniqueDebit = Array.from(
      new Set(
        operationalEntries
          .filter((entry) => entry.side === 'debit')
          .map((entry) => entry.account_name.trim())
          .filter((name) => name.length > 0),
      ),
    );
    const uniqueCredit = Array.from(
      new Set(
        operationalEntries
          .filter((entry) => entry.side === 'credit')
          .map((entry) => entry.account_name.trim())
          .filter((name) => name.length > 0),
      ),
    );
    const kind = getTransactionActivityKind(transaction);
    if (kind === 'income') return uniqueDebit.join(' + ') || uniqueCredit.join(' + ') || '-';
    if (kind === 'expense') return uniqueCredit.join(' + ') || uniqueDebit.join(' + ') || '-';
    const from = uniqueCredit.join(' + ');
    const to = uniqueDebit.join(' + ');
    if (from && to) return `${from} -> ${to}`;
    return from || to || '-';
  }

  function liquidityBalanceDeltaTone(
    row: Pick<LedgerAccountBalanceSummaryItem, 'account_type'> & { period_net_change: string },
  ): 'positive' | 'negative' | 'neutral' {
    const value = toNumber(row.period_net_change);
    if (value === 0) return 'neutral';
    if (row.account_type === 'asset' || row.account_type === 'expense') {
      return value > 0 ? 'positive' : 'negative';
    }
    return value > 0 ? 'negative' : 'positive';
  }

  function addEntry(side: LedgerEntrySide) {
    transactionForm.entries.push({
      key: ++rowId,
      account_id: null,
      side,
      amount: '',
      currency: 'EUR',
      notes: '',
    });
  }

  function removeEntry(key: number) {
    if (transactionForm.entries.length <= 2) return;
    transactionForm.entries = transactionForm.entries.filter((entry) => entry.key !== key);
  }

  async function reloadPeriod() {
    successMessage.value = null;
    await Promise.all([
      incomeStore.loadAll(selectedYear.value),
      expenseStore.loadAll(selectedYear.value),
    ]);
    await store.setStatsYear(selectedYear.value);
  }

  async function refreshManualPositionOptions() {
    try {
      const [assetsRes, liabilitiesRes] = await Promise.all([
        coreNetWorthApi.getAssets(),
        coreNetWorthApi.getLiabilities(),
      ]);
      manualAssets.value = assetsRes.data;
      manualLiabilities.value = liabilitiesRes.data;
      if (
        activationForm.position_id != null &&
        !availableManualPositionOptions.value.some((row) => row.id === activationForm.position_id)
      ) {
        activationForm.position_id = null;
      }
    } catch (error: unknown) {
      store.error = toApiErrorMessage(error);
    }
  }

  async function submitAccount() {
    successMessage.value = null;
    await store.createAccount({
      name: accountForm.name.trim(),
      account_type: accountForm.account_type,
      currency: accountForm.currency.trim().toUpperCase(),
      origin: accountForm.origin,
      notes: accountForm.notes.trim(),
    });
    resetAccountForm();
    successMessage.value = 'Cuenta contable creada.';
  }

  async function activateNetWorthPosition() {
    if (activationForm.position_id == null) return;

    await activateNetWorthPositions(activationForm.position_type, [activationForm.position_id]);
  }

  async function activateNetWorthPositions(
    positionType: ManualPositionType,
    positionIds: number[],
  ) {
    if (!positionIds.length) return;

    accountActivationLoading.value = true;
    successMessage.value = null;
    store.error = null;
    try {
      if (positionType === 'asset') {
        await Promise.all(
          positionIds.map((positionId) =>
            coreNetWorthApi.updateAsset(positionId, {
              tracking_mode: 'accounting',
            }),
          ),
        );
      } else {
        await Promise.all(
          positionIds.map((positionId) =>
            coreNetWorthApi.updateLiability(positionId, {
              tracking_mode: 'accounting',
            }),
          ),
        );
      }
      activationForm.position_id = null;
      await Promise.all([store.refreshAll(), refreshManualPositionOptions()]);
      successMessage.value =
        positionIds.length === 1
          ? 'Tracking contable activado para la posicion seleccionada.'
          : `Tracking contable activado para ${positionIds.length} posiciones seleccionadas.`;
    } catch (error: unknown) {
      store.error = toApiErrorMessage(error);
      throw error;
    } finally {
      accountActivationLoading.value = false;
    }
  }

  async function removeNetWorthTracking(account: LedgerAccount) {
    const targetType =
      account.asset_id != null ? 'asset' : account.liability_id != null ? 'liability' : null;
    const targetId = account.asset_id ?? account.liability_id;
    if (!targetType || targetId == null) return;

    successMessage.value = null;
    if (
      !confirm(
        `Quitar tracking contable de "${account.name}"?\n\n` +
          'La posicion volvera a tracking manual y dejara de formar parte del resumen contable.',
      )
    )
      return;

    accountActivationLoading.value = true;
    store.error = null;
    try {
      if (targetType === 'asset') {
        await coreNetWorthApi.updateAsset(targetId, { tracking_mode: 'manual' });
      } else {
        await coreNetWorthApi.updateLiability(targetId, { tracking_mode: 'manual' });
      }
      await coreAccountingApi.updateAccount(account.id, {
        is_active: false,
        asset_id: null,
        liability_id: null,
      });
      await Promise.all([store.refreshAll(), refreshManualPositionOptions()]);
      successMessage.value = 'Tracking contable desactivado para la cuenta seleccionada.';
    } catch (error: unknown) {
      store.error = toApiErrorMessage(error);
      throw error;
    } finally {
      accountActivationLoading.value = false;
    }
  }

  async function deleteAccount(accountId: number, accountName: string) {
    successMessage.value = null;
    if (
      !confirm(
        `Eliminar cuenta "${accountName}"?\n\n` +
          'Esto borrara tambien todos sus asientos y transacciones relacionadas. ' +
          'La accion es irreversible y puede afectar saldos e historico.',
      )
    )
      return;
    await store.deleteAccount(accountId);
    successMessage.value = 'Cuenta contable eliminada.';
  }

  function findLoadedTransactionById(transactionId: number): LedgerTransaction | undefined {
    return (
      todosTransactions.value.find((row) => row.id === transactionId) ??
      cuentasTransactions.value.find((row) => row.id === transactionId)
    );
  }

  async function reloadMovementPagesAfterMutation(): Promise<void> {
    const previousTodosLoaded = todosTransactions.value.length;
    const previousCuentasLoaded = cuentasTransactions.value.length;
    const hasSelectedAccount = cuentasSelectedAccountId.value != null;

    await fetchTodosPage(true);
    const desiredTodos = Math.min(previousTodosLoaded, todosTotalCount.value);
    while (todosHasMore.value && todosTransactions.value.length < desiredTodos) {
      await fetchTodosPage(false);
    }

    if (!hasSelectedAccount) return;

    await fetchCuentasPage(true);
    const desiredCuentas = Math.min(previousCuentasLoaded, cuentasTotalCount.value);
    while (cuentasHasMore.value && cuentasTransactions.value.length < desiredCuentas) {
      await fetchCuentasPage(false);
    }
  }

  async function submitTransaction() {
    successMessage.value = null;
    const payload: LedgerTransactionWritePayload = {
      booking_date: transactionForm.booking_date,
      value_date: transactionForm.value_date,
      description: transactionForm.description.trim(),
      status: transactionForm.status,
      origin: transactionForm.origin,
      notes: transactionForm.notes.trim(),
      entries: transactionForm.entries.map((entry) => ({
        account_id: entry.account_id ?? 0,
        side: entry.side,
        amount: formatDecimalInput(entry.amount),
        currency: entry.currency.trim().toUpperCase(),
        notes: entry.notes.trim(),
      })),
    };
    await store.createTransaction(payload);
    await reloadMovementPagesAfterMutation();
    resetTransactionForm();
    successMessage.value = 'Movimiento contable registrado.';
  }

  function openTransactionForEditing(transactionId: number) {
    const transaction = findLoadedTransactionById(transactionId);
    if (!transaction) return false;
    if (transaction.origin === 'system') {
      store.error = 'Los asientos de origen system no se pueden editar desde esta vista.';
      return false;
    }
    fillEditTransactionForm(transaction);
    return true;
  }

  // eslint-disable-next-line complexity
  async function submitEditedTransaction(): Promise<boolean> {
    if (editTransactionId.value == null) return false;
    if (!editTransactionPersistedEntries.value.length) return false;
    const validated = validateEditedTransactionInput();
    if (!validated) return false;
    const hasMixedCurrencyEntries =
      new Set(
        editTransactionPersistedEntries.value.map((entry) =>
          entry.currency.trim().toUpperCase(),
        ),
      ).size > 1;
    if (hasMixedCurrencyEntries) {
      let compatibilityEntries = scaleLegacyMixedCurrencyEntries(
        editTransactionPersistedEntries.value,
        validated.selectedAccount.id,
        validated.parsedAmount,
      );
      if (
        (editTransactionForm.kind === 'investment' || editTransactionForm.kind === 'transfer') &&
        editInvestmentIsCrossCurrency.value
      ) {
        const destinationAmount = Number(formatDecimalInput(editTransactionForm.destination_amount));
        const updatedAccounts = setEditedAccountsOnEntries(
          compatibilityEntries,
          editTransactionForm.kind,
          editTransactionForm.account_id!,
          editTransactionForm.counterparty_account_id,
          editTransactionForm.investment_direction,
        );
        compatibilityEntries = updatedAccounts.map((entry) => ({ ...entry }));
        const debitEntry = compatibilityEntries.find((entry) => entry.side === 'debit') ?? null;
        const creditEntry = compatibilityEntries.find((entry) => entry.side === 'credit') ?? null;
        if (debitEntry) {
          debitEntry.amount = roundByCurrency(destinationAmount, debitEntry.currency).toFixed(
            currencyDecimals(debitEntry.currency),
          );
        }
        if (creditEntry) {
          creditEntry.amount = roundByCurrency(validated.parsedAmount, creditEntry.currency).toFixed(
            currencyDecimals(creditEntry.currency),
          );
        }
      }
      const compatibilityPayload: LedgerTransactionWritePayload = {
        booking_date: editTransactionForm.booking_date,
        value_date: editTransactionForm.value_date,
        description: editTransactionForm.description.trim(),
        notes: editTransactionForm.notes.trim(),
        ownership_id: editTransactionForm.ownership_id,
        quick_entry_kind:
          editTransactionForm.kind === 'investment' ? 'investment' : editTransactionForm.kind,
        investment_direction:
          editTransactionForm.kind === 'investment' ? editTransactionForm.investment_direction : '',
        entries: compatibilityEntries.map((entry) => ({
          account_id: entry.account_id,
          side: entry.side,
          amount: formatDecimalInput(entry.amount),
          currency: entry.currency.trim().toUpperCase(),
          flow_family: entry.flow_family,
          category_key: entry.category_key,
          subcategory_key: entry.subcategory_key,
          annual_income_entry_id: entry.annual_income_entry_id,
          annual_expense_entry_id: entry.annual_expense_entry_id,
          asset_id: entry.asset_id,
          liability_id: entry.liability_id,
          notes: entry.notes.trim(),
        })),
      };
      try {
        await store.updateTransaction(editTransactionId.value, compatibilityPayload);
      } catch {
        return false;
      }
      try {
        await reloadMovementPagesAfterMutation();
      } catch {
        if (!store.error) {
          store.error =
            'Movimiento guardado, pero no se pudo refrescar el listado. Recarga la vista si no ves el cambio.';
        }
      }
      resetEditTransactionForm();
      successMessage.value = 'Movimiento multimoneda actualizado (modo compatibilidad legacy).';
      return true;
    }
    const payloadEntries = await resolveEditedTransactionEntries(
      validated.parsedAmount,
      validated.selectedAccount,
    );
    if (!payloadEntries?.length) {
      store.error = 'No se pudo construir el asiento actualizado.';
      return false;
    }
    successMessage.value = null;
    store.error = null;
    const kindToQuickEntryKind: Record<string, string> = {
      income: 'income',
      expense: 'expense',
      transfer: 'transfer',
      investment: 'investment',
      debt_payment: 'debt_payment',
      revaluation: 'revaluation',
    };
    const payload: LedgerTransactionWritePayload = {
      booking_date: editTransactionForm.booking_date,
      value_date: editTransactionForm.value_date,
      description: editTransactionForm.description.trim(),
      status: 'posted',
      origin: 'manual',
      notes: editTransactionForm.notes.trim(),
      ownership_id: editTransactionForm.ownership_id,
      quick_entry_kind: kindToQuickEntryKind[editTransactionForm.kind] ?? '',
      investment_direction:
        editTransactionForm.kind === 'investment' ? editTransactionForm.investment_direction : '',
      entries: payloadEntries.map((entry) => ({
        account_id: entry.account_id,
        side: entry.side,
        amount: formatDecimalInput(entry.amount),
        currency: entry.currency.trim().toUpperCase(),
        flow_family: entry.flow_family,
        category_key: entry.category_key,
        subcategory_key: entry.subcategory_key,
        annual_income_entry_id: entry.annual_income_entry_id,
        annual_expense_entry_id: entry.annual_expense_entry_id,
        asset_id: entry.asset_id,
        liability_id: entry.liability_id,
        notes: entry.notes.trim(),
      })),
    };
    try {
      await store.updateTransaction(editTransactionId.value, payload);
    } catch {
      return false;
    }
    try {
      await reloadMovementPagesAfterMutation();
    } catch {
      // El guardado ya se aplico; si falla el refresh no bloqueamos el cierre del modal.
      if (!store.error) {
        store.error =
          'Movimiento guardado, pero no se pudo refrescar el listado. Recarga la vista si no ves el cambio.';
      }
    }
    resetEditTransactionForm();
    successMessage.value = 'Movimiento contable actualizado.';
    return true;
  }

  async function deleteTransaction(transactionId: number, transactionDescription: string) {
    const transaction = findLoadedTransactionById(transactionId);
    if (transaction?.origin === 'system') {
      store.error = 'Los asientos de origen system no se pueden eliminar desde esta vista.';
      return;
    }
    successMessage.value = null;
    if (
      !confirm(
        `Eliminar movimiento "${transactionDescription}"?\n\n` +
          'La accion es irreversible y puede afectar saldos e historico.',
      )
    ) {
      return;
    }
    await store.deleteTransaction(transactionId);
    await reloadMovementPagesAfterMutation();
    successMessage.value = 'Movimiento contable eliminado.';
  }

  async function deleteImportedTransactions() {
    if (!hasImportedTransactions.value) {
      successMessage.value = 'No hay movimientos importados para eliminar.';
      return;
    }
    successMessage.value = null;
    if (
      !confirm(
        'Eliminar todos los movimientos importados?\n\n' +
          'Solo se borraran movimientos con origen import. La accion es irreversible.',
      )
    ) {
      return;
    }
    const result = await store.deleteImportedTransactions();
    await reloadMovementPagesAfterMutation();
    successMessage.value =
      result.deleted_count > 0
        ? `Limpieza completada: ${result.deleted_count} movimientos importados eliminados.`
        : 'No habia movimientos importados para eliminar.';
  }

  async function submitRevaluationEntry() {
    successMessage.value = null;
    const delta = revaluationDelta.value;
    if (delta == null || Math.abs(delta) < 0.005) {
      store.error = 'El valor nuevo no genera una variacion suficiente respecto al saldo actual.';
      return;
    }
    if (quickEntryForm.account_id == null) {
      store.error = 'Selecciona la cuenta de inversion.';
      return;
    }
    const payload: QuickLedgerTransactionWritePayload = {
      movement_type: 'revaluation',
      booking_date: quickEntryForm.booking_date,
      value_date: quickEntryForm.value_date,
      description: quickEntryForm.description.trim(),
      amount: delta.toFixed(2),
      account_id: quickEntryForm.account_id,
      ownership_id: quickEntryForm.ownership_id,
      notes: quickEntryForm.notes.trim(),
    };
    await store.createQuickEntry(payload);
    await reloadMovementPagesAfterMutation();
    resetQuickEntryForm();
    successMessage.value = 'Revalorizacion registrada.';
  }

  async function submitQuickEntry() {
    if (quickEntryForm.movement_type === 'revaluation') {
      await submitRevaluationEntry();
      return;
    }
    successMessage.value = null;
    const payload: QuickLedgerTransactionWritePayload = {
      movement_type: quickEntryForm.movement_type,
      booking_date: quickEntryForm.booking_date,
      value_date: quickEntryForm.value_date,
      description: quickEntryForm.description.trim(),
      amount: formatDecimalInput(quickEntryForm.amount),
      account_id: normalizeAccountId(quickEntryForm.account_id) ?? 0,
      ownership_id: quickEntryForm.ownership_id,
      notes: quickEntryForm.notes.trim(),
      status: 'posted',
      origin: 'manual',
      ...(quickEntryNeedsClassification.value
        ? {
            flow_family:
              quickEntryForm.movement_type === 'income' ||
              (quickEntryForm.movement_type === 'investment' &&
                quickEntryForm.investment_direction === 'outflow')
                ? 'income'
                : ('expense' as const),
            category_key: quickEntryForm.category_key,
            subcategory_key: quickEntryForm.subcategory_key,
          }
        : {}),
      ...(quickEntryForm.movement_type === 'transfer'
        ? {
            counterparty_account_id: normalizeAccountId(quickEntryForm.counterparty_account_id),
          }
        : {}),
      ...(quickEntryForm.movement_type === 'income'
        ? quickEntryForm.annual_income_entry_id != null
          ? { annual_income_entry_id: quickEntryForm.annual_income_entry_id }
          : {}
        : {}),
      ...(quickEntryForm.movement_type === 'expense'
        ? quickEntryForm.annual_expense_entry_id != null
          ? { annual_expense_entry_id: quickEntryForm.annual_expense_entry_id }
          : {}
        : {}),
      ...(quickEntryForm.movement_type === 'investment'
        ? {
            counterparty_account_id: normalizeAccountId(quickEntryForm.counterparty_account_id),
            investment_direction: quickEntryForm.investment_direction,
            ...(quickInvestmentIsCrossCurrency.value
              ? { destination_amount: formatDecimalInput(quickEntryForm.destination_amount) }
              : {}),
            ...(quickEntryForm.realized_cost_basis.trim()
              ? { realized_cost_basis: formatDecimalInput(quickEntryForm.realized_cost_basis) }
              : {}),
            ...(quickEntryForm.realized_gain_loss.trim()
              ? { realized_gain_loss: formatDecimalInput(quickEntryForm.realized_gain_loss) }
              : {}),
          }
        : {}),
      ...(quickEntryForm.movement_type === 'debt_payment'
        ? {
            liability_account_id: normalizeAccountId(quickEntryForm.liability_account_id),
            principal_amount: formatDecimalInput(quickEntryForm.principal_amount),
            interest_amount: formatDecimalInput(quickEntryForm.interest_amount || '0'),
            ...(quickEntryForm.annual_expense_entry_id != null
              ? { annual_expense_entry_id: quickEntryForm.annual_expense_entry_id }
              : {}),
            ...(toNumber(quickEntryForm.interest_amount) > 0
              ? { interest_account_id: normalizeAccountId(quickEntryForm.interest_account_id) }
              : {}),
          }
        : {}),
    };
    await store.createQuickEntry(payload);
    await reloadMovementPagesAfterMutation();
    resetQuickEntryForm();
    successMessage.value = 'Movimiento rapido registrado.';
  }

  function setMoneyWizImportFile(file: File | null) {
    moneyWizImportFile.value = file;
    store.clearMoneyWizImportState();
  }

  async function previewMoneyWizImport() {
    if (!moneyWizImportFile.value) {
      store.error = 'Selecciona antes un CSV exportado desde MoneyWiz.';
      return null;
    }
    successMessage.value = null;
    const preview = await store.previewMoneyWizImport(moneyWizImportFile.value);
    successMessage.value =
      preview.error_row_count > 0
        ? 'Preview generada con filas que necesitan revision antes de importar.'
        : 'Preview MoneyWiz lista para confirmar la importacion.';
    return preview;
  }

  async function commitMoneyWizImport(accountIdMap: Record<string, number> = {}) {
    if (!moneyWizImportFile.value) {
      store.error = 'Selecciona antes un CSV exportado desde MoneyWiz.';
      return null;
    }
    if (!moneyWizImportPreview.value) {
      store.error = 'Genera primero la preview del CSV antes de confirmar.';
      return null;
    }
    if (moneyWizImportPreview.value.error_row_count > 0) {
      store.error = 'Corrige o elimina las filas con errores antes de confirmar la importacion.';
      return null;
    }
    successMessage.value = null;
    const result = await store.commitMoneyWizImport(moneyWizImportFile.value, accountIdMap);
    await reloadMovementPagesAfterMutation();
    successMessage.value =
      result.created_count > 0
        ? `Importacion MoneyWiz completada: ${result.created_count} movimientos nuevos.`
        : 'Importacion MoneyWiz completada sin crear movimientos nuevos.';
    return result;
  }

  onMounted(() => {
    void (async () => {
      await Promise.all([
        store.refreshAll(),
        incomeStore.loadAll(selectedYear.value),
        expenseStore.loadAll(selectedYear.value),
        peopleStore.fetchOwnerships(),
        refreshManualPositionOptions(),
      ]);
      await fetchTodosPage(true);
      if (cuentasSelectedAccountId.value != null) {
        await fetchCuentasPage(true);
      }
    })();
  });
  onBeforeUnmount(() => {
    todosAbortController?.abort();
    cuentasAbortController?.abort();
    if (todosSearchDebounceTimer) {
      clearTimeout(todosSearchDebounceTimer);
      todosSearchDebounceTimer = null;
    }
    if (cuentasSearchDebounceTimer) {
      clearTimeout(cuentasSearchDebounceTimer);
      cuentasSearchDebounceTimer = null;
    }
  });

  return {
    loading,
    accountCreationLoading,
    accountActivationLoading,
    transactionCreationLoading,
    importPreviewLoading,
    importCommitLoading,
    error,
    successMessage,
    accounts,
    monthlySummary,
    accountBalancesSummary,
    moneyWizImportPreview,
    moneyWizImportCommitResult,
    selectedYear,
    selectedMonth,
    yearOptions,
    monthOptions,
    accountTypeOptions,
    manualPositionTypeOptions,
    quickMovementTypeOptions,
    editMovementTypeOptions,
    editAccountOptions,
    editCounterpartyOptions,
    editCounterpartyMissingHint,
    editKindNeedsCounterparty,
    editKindNeedsClassification,
    editCounterpartyLabel,
    editInvestmentOriginCurrency,
    editInvestmentDestinationCurrency,
    editInvestmentIsCrossCurrency,
    editSelectedAccountCurrentBalance,
    editCategoryOptions,
    editSubcategoryOptions,
    editCategoryLocked,
    editSubcategoryLocked,
    accountForm,
    activationForm,
    ownershipOptions,
    quickEntryForm,
    transactionForm,
    editTransactionId,
    editTransactionForm,
    activityFilters,
    cuentasFilters,
    moneyWizImportFile,
    liquidityAccounts,
    availableManualPositionOptions,
    accountPositionMetaByAccountId,
    accountDisplayName,
    hasAvailableManualPositions,
    liquidityBalanceRows,
    liquidityBalanceTotal,
    incomeOptions,
    expenseOptions,
    annualIncomeOptionsCompatible,
    annualExpenseOptionsCompatible,
    quickEntryNeedsClassification,
    quickCategoryOptions,
    quickSubcategoryOptions,
    quickCategoryLocked,
    quickSubcategoryLocked,
    filterCategoryOptions,
    filterSubcategoryOptions,
    cuentasFilterCategoryOptions,
    cuentasFilterSubcategoryOptions,
    transferCounterpartyOptions,
    investmentCounterpartyOptions,
    quickInvestmentOriginCurrency,
    quickInvestmentDestinationCurrency,
    quickInvestmentIsCrossCurrency,
    liabilityCounterpartyOptions,
    debtInterestOptions,
    revaluationAccountOptions,
    revaluationCurrentBalance,
    revaluationDelta,
    quickEntryReady,
    editEntryReady,
    debitTotal,
    creditTotal,
    transactionBalanced,
    summaryRows,
    hasImportedTransactions,
    activeTab,
    cuentasSelectedAccountId,
    cuentasSelectedAccount,
    cuentasDateFrom,
    cuentasDateTo,
    cuentasTransactions,
    cuentasTotalCount,
    cuentasLoading,
    cuentasLoadingMore,
    cuentasHasMore,
    loadMoreCuentas,
    todosDateFrom,
    todosDateTo,
    todosTransactions,
    todosTotalCount,
    todosLoading,
    todosLoadingMore,
    todosHasMore,
    loadMoreTodos,
    transactionMainAmount,
    addEntry,
    activityKindLabel,
    transactionOwnershipLabel,
    transactionClassificationLabel,
    transactionAccountTrailLabel,
    liquidityBalanceDeltaTone,
    removeEntry,
    reloadPeriod,
    activateNetWorthPosition,
    activateNetWorthPositions,
    removeNetWorthTracking,
    refreshManualPositionOptions,
    submitAccount,
    setMoneyWizImportFile,
    previewMoneyWizImport,
    commitMoneyWizImport,
    deleteAccount,
    submitQuickEntry,
    submitTransaction,
    openTransactionForEditing,
    submitEditedTransaction,
    resetEditTransactionForm,
    deleteTransaction,
    deleteImportedTransactions,
  };
}
