import { computed, nextTick, onMounted, reactive, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAccountingStore } from '@/domains/accounting/store';
import { coreAccountingApi } from '@/domains/accounting/api';
import { coreNetWorthApi } from '@/domains/net-worth/api';
import {
  useAnnualExpenseStore,
  useAnnualIncomeStore,
  type AnnualExpenseEntry,
  type AnnualIncomeEntry,
} from '@/domains/data-input';
import {
  type EditableActivityKind,
  type ClassificationActivityKind,
  type LiabilityCategoryKey,
  EXPENSE_MOVEMENT_CATEGORY_KEYS,
  DEBT_PAYMENT_ALLOWED_CATEGORY_KEYS,
  isAutoInvestmentBridgeAccount,
  normalizeAccountId,
  subcategoryOptionsByCategory,
  kindUsesClassification,
  isCounterpartyKind,
  incomeCategories,
  expenseCategories,
  incomeSubcategories,
  expenseSubcategories,
  type IncomeCategoryKey,
  type ExpenseCategoryKey,
} from '@/domains/accounting/useTransactionClassification';
import { useQuickEntry, type QuickEntryContext } from '@/domains/accounting/useQuickEntry';
import { usePeopleStore, type OwnershipRead } from '@/domains/people/store';
import type {
  LedgerAccount,
  LedgerAccountType,
  LedgerEntrySide,
  LedgerTransaction,
  LedgerTransactionWritePayload,
  QuickLedgerMovementType,
  QuickLedgerTransactionWritePayload,
} from '@/domains/accounting/models';
import type { Asset, Liability } from '@/domains/net-worth/models';
import { toApiErrorMessage } from '@/lib/errors';
import { useAccountingDailyTimeline } from '@/domains/accounting/useAccountingDailyTimeline';
import {
  getInvestmentDirection,
  getTransactionActivityKind,
  useAccountingTransactionLabels,
} from '@/domains/accounting/useAccountingTransactionLabels';
import { useAccountingMovementsList } from '@/domains/accounting/useAccountingMovementsList';

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
  interest_account_id: number | null;
  principal_amount: string;
  interest_amount: string;
  kind: EditableActivityKind;
  initial_kind: EditableActivityKind;
  investment_direction: 'inflow' | 'outflow' | 'reinvestment';
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
  asset_id: number | null;
  liability_id: number | null;
  notes: string;
};

type DebtBreakdownResolution = {
  total: number;
  principal: number;
  interest: number;
  valid: boolean;
  error: string | null;
};

type ManualPositionType = 'asset' | 'liability';
type AccountPositionMeta = {
  position_type: ManualPositionType;
  category: string;
  subcategory: string;
  amount_base?: string;
};
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
  const { loading, accountCreationLoading, transactionCreationLoading, error } = storeToRefs(store);
  const { accounts, monthlySummary, accountBalancesSummary } = storeToRefs(store);

  const successMessage = ref<string | null>(null);
  const accountActivationLoading = ref(false);
  const manualAssets = ref<Asset[]>([]);
  const manualLiabilities = ref<Liability[]>([]);

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
    interest_account_id: null,
    principal_amount: '',
    interest_amount: '',
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
  const ownershipFilterOptions = computed(() => {
    const options = peopleStore.ownerships
      .filter((ownership) => ownership.kind === 'individual')
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
            amount_base: asset.amount_base,
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
            amount_base: liability.amount_base,
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
  const ctx: QuickEntryContext = {
    accounts,
    accountMap,
    liabilityMap,
    accountPositionMetaByAccountId,
    manualAssets,
  };
  const {
    quickEntryForm,
    quickMovementTypeOptions,
    quickAdjustmentAccountOptions,
    transferOriginOptions,
    transferCounterpartyOptions,
    investmentOriginOptions,
    investmentCounterpartyOptions,
    quickSelectedLiquidityAccount,
    quickTransferOriginCurrency,
    quickTransferDestinationCurrency,
    quickTransferIsCrossCurrency,
    quickInvestmentOriginCurrency,
    quickInvestmentDestinationCurrency,
    quickInvestmentIsCrossCurrency,
    revaluationAccountOptions,
    revaluationCurrentBalance,
    revaluationDelta,
    quickAdjustmentCurrentBalance,
    quickAdjustmentCurrency,
    quickAdjustmentDisplayDecimals,
    quickAdjustmentDelta,
    liabilityCounterpartyOptions,
    debtInterestOptions,
    quickEntryReady,
    quickEntryNeedsClassification,
    quickCategoryOptions,
    quickSubcategoryOptions,
    quickCategoryLocked,
    quickSubcategoryLocked,
    resolveFlexibleDebtBreakdown,
    resolveQuickDebtBreakdown,
    resolveDefaultDebtInterestAccountId,
    debtPaymentDefaultCategoryForAccount,
    resolveInvestmentExpenseSubcategoryFromAccount,
    resetQuickEntryForm,
  } = useQuickEntry(ctx);

  const filterSubcategoryOptions = computed(() =>
    subcategoryOptionsByCategory(activityFilters.categoryKey),
  );
  const cuentasFilterSubcategoryOptions = computed(() =>
    subcategoryOptionsByCategory(cuentasFilters.categoryKey),
  );

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
      .filter(
        (account) =>
          (account.account_type === 'asset' || account.account_type === 'liability') &&
          !isAutoInvestmentBridgeAccount(account),
      )
      .sort((a, b) => a.name.localeCompare(b.name, 'es')),
  );
  const editKindNeedsClassification = computed(() =>
    kindUsesClassification(editTransactionForm.kind, editTransactionForm.investment_direction),
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
  const editInvestmentOriginOptions = computed(() => {
    const selectedCounterpartyId = editTransactionForm.counterparty_account_id;
    return editAccountOptions.value.filter((account) => {
      if (account.account_type !== 'asset') return false;
      if (account.asset_id == null) return false;
      if (selectedCounterpartyId == null) return true;
      return account.id !== selectedCounterpartyId;
    });
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
    editTransactionForm.account_id != null
      ? (accountMap.value.get(editTransactionForm.account_id) ?? null)
      : null,
  );
  const editSelectedInvestmentAccount = computed(() =>
    editTransactionForm.counterparty_account_id != null
      ? (accountMap.value.get(editTransactionForm.counterparty_account_id) ?? null)
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
    if (editTransactionForm.investment_direction === 'reinvestment') {
      return editSelectedLiquidityAccount.value?.currency ?? '';
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
    if (editTransactionForm.investment_direction === 'reinvestment') {
      return editSelectedInvestmentAccount.value?.currency ?? '';
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
      if (editTransactionForm.investment_direction === 'reinvestment') {
        return [];
      }
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
      return expenseCategories.filter((row) =>
        DEBT_PAYMENT_ALLOWED_CATEGORY_KEYS.includes(row.value as ExpenseCategoryKey),
      );
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
      if (editTransactionForm.investment_direction === 'reinvestment') {
        return [];
      }
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
    if (editTransactionForm.kind === 'investment') {
      return editTransactionForm.investment_direction !== 'reinvestment';
    }
    if (editTransactionForm.kind === 'debt_payment') {
      return editSelectedDebtLiabilityCategory.value === 'mortgage';
    }
    return false;
  });
  const editSubcategoryLocked = computed(() => {
    if (editTransactionForm.kind === 'investment') {
      return (
        editTransactionForm.investment_direction === 'outflow' ||
        editTransactionForm.investment_direction === 'reinvestment'
      );
    }
    if (editTransactionForm.kind === 'debt_payment') {
      return editSelectedDebtLiabilityCategory.value === 'mortgage';
    }
    return false;
  });
  const editDebtComputedInterest = computed((): number | null => {
    if (editTransactionForm.kind !== 'debt_payment') return null;
    if (editTransactionForm.interest_amount.trim()) return null;
    const currency =
      (editTransactionForm.account_id != null
        ? accountMap.value.get(editTransactionForm.account_id)?.currency
        : null) ?? 'EUR';
    const breakdown = resolveFlexibleDebtBreakdown(
      editTransactionForm.amount,
      editTransactionForm.principal_amount,
      editTransactionForm.interest_amount,
      currency,
    );
    return breakdown.valid ? breakdown.interest : null;
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
    () => editTransactionForm.kind,
    (kind) => {
      if (editTransactionForm.account_id == null && editAccountOptions.value.length) {
        editTransactionForm.account_id = editAccountOptions.value[0]!.id;
      }
      if (!kindUsesClassification(kind, editTransactionForm.investment_direction)) {
        editTransactionForm.category_key = '';
        editTransactionForm.subcategory_key = '';
      }
      if (kind !== 'investment') {
        editTransactionForm.investment_direction = 'inflow';
      }
      if (kind !== 'debt_payment') {
        editTransactionForm.interest_account_id = null;
        editTransactionForm.principal_amount = '';
        editTransactionForm.interest_amount = '';
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
        if (editTransactionForm.investment_direction === 'reinvestment') {
          editTransactionForm.category_key = '';
          editTransactionForm.subcategory_key = '';
          return;
        }
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
      const defaultCategory = debtPaymentDefaultCategoryForAccount(
        editTransactionForm.counterparty_account_id,
      );
      if (editSelectedDebtLiabilityCategory.value === 'mortgage') {
        editTransactionForm.category_key = 'real_estate_assets';
        editTransactionForm.subcategory_key = 'mortgage_principal';
      } else {
        if (
          !editTransactionForm.category_key ||
          !DEBT_PAYMENT_ALLOWED_CATEGORY_KEYS.includes(
            editTransactionForm.category_key as ExpenseCategoryKey,
          )
        ) {
          editTransactionForm.category_key = defaultCategory;
        }
        if (editTransactionForm.subcategory_key === 'mortgage_principal') {
          editTransactionForm.subcategory_key =
            editTransactionForm.category_key === 'consumption_expenses'
              ? 'financial_commitments'
              : '';
        }
      }
    },
    { immediate: true },
  );
  watch(
    () =>
      [
        editTransactionForm.kind,
        editTransactionForm.investment_direction,
        editTransactionForm.category_key,
        editTransactionForm.counterparty_account_id,
      ] as const,
    () => {
      if (editTransactionForm.kind !== 'investment') return;
      if (editTransactionForm.investment_direction === 'reinvestment') return;
      if (editTransactionForm.category_key !== 'financial_investments') return;
      const inferredSubcategory = resolveInvestmentExpenseSubcategoryFromAccount(
        editTransactionForm.counterparty_account_id,
      );
      if (inferredSubcategory) {
        editTransactionForm.subcategory_key = inferredSubcategory;
        return;
      }
      if (editTransactionForm.subcategory_key === 'deposits_fixed_income') {
        editTransactionForm.subcategory_key = '';
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
  const {
    dailyBalanceOwnershipFilter,
    dailyBalanceSeriesRows,
    dailyBalanceSeriesLoading,
    dailyBalanceSeriesError,
    dailyBalanceSeriesUnit,
    dailyBalanceSeriesChartPoints,
    dailyBalanceSeriesChartRows,
    dailyBalanceSeriesMonthlyRows,
    dailyBalanceSeriesRangeLabel,
    dailyBalanceLatestChartPoint,
    dailyTimelinePresetOptions,
    selectedDailyTimelinePreset,
    dailyTimelineCustomWindow,
    dailyTimelineWindow,
    dailyTimelineExpanded,
    setDailyTimelinePreset,
    updateDailyTimelineWindowStart,
    updateDailyTimelineWindowEnd,
    reloadDailyBalanceSeries,
  } = useAccountingDailyTimeline();

  const {
    activityFilters,
    cuentasFilters,
    filterCategoryOptions,
    cuentasFilterCategoryOptions,
    activeTab,
    cuentasSelectedAccountId,
    cuentasSelectedAccount,
    cuentasDateFrom,
    cuentasDateTo,
    todosDateFrom,
    todosDateTo,
    todosTransactions,
    todosTotalCount,
    todosLoading,
    todosLoadingMore,
    todosHasMore,
    cuentasTransactions,
    cuentasTotalCount,
    cuentasLoading,
    cuentasLoadingMore,
    cuentasHasMore,
    fetchTodosPage,
    fetchCuentasPage,
    loadMoreCuentas,
    loadMoreTodos,
    reloadMovementPagesAfterMutation,
    transactionMainAmount,
  } = useAccountingMovementsList(accounts, reloadDailyBalanceSeries);

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
    editTransactionForm.interest_account_id = null;
    editTransactionForm.principal_amount = '';
    editTransactionForm.interest_amount = '';
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
        transaction.entries.find((entry) => entry.side === 'credit') ??
        transaction.entries[1] ??
        null;
      if (creditEntry) {
        return toNumber(creditEntry.amount).toFixed(currencyDecimals(creditEntry.currency));
      }
    }
    if (transaction.activity_kind === 'transfer') {
      const creditEntry =
        transaction.entries.find((entry) => entry.side === 'credit') ??
        transaction.entries[1] ??
        null;
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

  function resolveDebtBreakdownFromEntries(transaction: LedgerTransaction): {
    principalAmount: string;
    interestAmount: string;
    interestAccountId: number | null;
  } {
    const transactionCurrency = transaction.entries[0]?.currency ?? 'EUR';
    const decimals = currencyDecimals(transactionCurrency);
    const liabilityEntry =
      transaction.entries.find(
        (entry) =>
          entry.side === 'debit' &&
          (entry.liability_id != null ||
            accountMap.value.get(entry.account_id)?.account_type === 'liability'),
      ) ?? null;
    const principalValue = liabilityEntry ? toNumber(liabilityEntry.amount) : 0;
    const interestEntries = transaction.entries.filter(
      (entry) => entry.side === 'debit' && entry.account_id !== liabilityEntry?.account_id,
    );
    const interestValue = interestEntries.reduce((sum, entry) => sum + toNumber(entry.amount), 0);
    return {
      principalAmount: principalValue > 0 ? principalValue.toFixed(decimals) : '',
      interestAmount: interestValue > 0 ? interestValue.toFixed(decimals) : '',
      interestAccountId:
        interestEntries.length === 1 ? (interestEntries[0]?.account_id ?? null) : null,
    };
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
      if (direction === 'reinvestment') {
        return {
          accountId: creditEntry?.account_id ?? null,
          counterpartyAccountId: debitEntry?.account_id ?? null,
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
    if (kind === 'debt_payment') {
      const debtBreakdown = resolveDebtBreakdownFromEntries(transaction);
      editTransactionForm.principal_amount = debtBreakdown.principalAmount;
      editTransactionForm.interest_amount = debtBreakdown.interestAmount;
      editTransactionForm.interest_account_id = debtBreakdown.interestAccountId;
    } else {
      editTransactionForm.interest_account_id = null;
      editTransactionForm.principal_amount = '';
      editTransactionForm.interest_amount = '';
    }
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
    investmentDirection: 'inflow' | 'outflow' | 'reinvestment',
  ): PersistedTransactionEntry[] {
    const nextEntries = entries.map((entry) => ({
      ...entry,
      flow_family: '' as '' | 'income' | 'expense',
      category_key: '',
      subcategory_key: '',
      asset_id: null,
      liability_id: null,
    }));
    if (!kindUsesClassification(kind, investmentDirection)) return nextEntries;

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
    investmentDirection: 'inflow' | 'outflow' | 'reinvestment',
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
      } else if (investmentDirection === 'reinvestment') {
        setAccount(creditEntry, accountId);
        setAccount(debitEntry, counterpartyAccountId);
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

  function applyClassificationToEntries(
    entries: PersistedTransactionEntry[],
    options: {
      kind: EditableActivityKind;
      categoryKey: string;
      subcategoryKey: string;
      investmentDirection: 'inflow' | 'outflow' | 'reinvestment';
    },
  ): PersistedTransactionEntry[] {
    const { kind, categoryKey, subcategoryKey, investmentDirection } = options;
    if (!kindUsesClassification(kind, investmentDirection)) return entries;
    const classifyAsIncome =
      kind === 'income' || (kind === 'investment' && investmentDirection === 'outflow');
    const preferredSide: LedgerEntrySide = classifyAsIncome ? 'credit' : 'debit';
    const next = entries.map((entry) => ({ ...entry }));
    let classifiedAssigned = false;
    next.forEach((entry) => {
      if (!classifiedAssigned && entry.side === preferredSide) {
        entry.flow_family = classifyAsIncome ? 'income' : 'expense';
        entry.category_key = categoryKey;
        entry.subcategory_key = subcategoryKey;
        classifiedAssigned = true;
      } else {
        entry.flow_family = '';
        entry.category_key = '';
        entry.subcategory_key = '';
      }
    });
    if (!classifiedAssigned && next[0]) {
      next[0].flow_family = classifyAsIncome ? 'income' : 'expense';
      next[0].category_key = categoryKey;
      next[0].subcategory_key = subcategoryKey;
    }
    return next;
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
    debtBreakdown: DebtBreakdownResolution | null;
  } | null {
    let parsedAmount = Number(formatDecimalInput(editTransactionForm.amount));
    let debtBreakdown: DebtBreakdownResolution | null = null;
    if (editTransactionForm.kind === 'debt_payment') {
      const accountCurrency =
        (editTransactionForm.account_id != null
          ? accountMap.value.get(editTransactionForm.account_id)?.currency
          : null) ?? 'EUR';
      debtBreakdown = resolveFlexibleDebtBreakdown(
        editTransactionForm.amount,
        editTransactionForm.principal_amount,
        editTransactionForm.interest_amount,
        accountCurrency,
      );
      if (!debtBreakdown.valid) {
        store.error = debtBreakdown.error;
        return null;
      }
      parsedAmount = debtBreakdown.total;
      if (debtBreakdown.interest > 0 && editTransactionForm.interest_account_id == null) {
        const defaultInterestAccountId = resolveDefaultDebtInterestAccountId(accountCurrency);
        if (defaultInterestAccountId != null) {
          editTransactionForm.interest_account_id = defaultInterestAccountId;
        } else {
          store.error = 'Selecciona una cuenta de gasto para registrar el interés.';
          return null;
        }
      }
    } else if (!Number.isFinite(parsedAmount)) {
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
    return { parsedAmount, selectedAccount, debtBreakdown };
  }

  // eslint-disable-next-line complexity
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
    if (editTransactionForm.kind === 'debt_payment') {
      const breakdown = resolveFlexibleDebtBreakdown(
        editTransactionForm.amount,
        editTransactionForm.principal_amount,
        editTransactionForm.interest_amount,
        selectedAccount.currency,
      );
      if (!breakdown.valid) {
        store.error = breakdown.error;
        return null;
      }
      const liabilityAccountId = editTransactionForm.counterparty_account_id;
      if (liabilityAccountId == null) {
        store.error = 'Selecciona la cuenta de pasivo.';
        return null;
      }
      const liabilityAccount = accountMap.value.get(liabilityAccountId);
      if (!liabilityAccount || liabilityAccount.account_type !== 'liability') {
        store.error = 'Selecciona una cuenta de pasivo contable valida.';
        return null;
      }
      if (liabilityAccount.currency !== selectedAccount.currency) {
        store.error = 'Liquidez y pasivo deben usar la misma moneda en pago deuda.';
        return null;
      }
      const entryNotesByAccountId = new Map(
        editTransactionPersistedEntries.value.map((entry) => [entry.account_id, entry.notes]),
      );
      const decimals = currencyDecimals(selectedAccount.currency);
      const entries: PersistedTransactionEntry[] = [
        {
          account_id: liabilityAccount.id,
          side: 'debit',
          amount: breakdown.principal.toFixed(decimals),
          currency: liabilityAccount.currency,
          flow_family: 'expense',
          category_key: editTransactionForm.category_key,
          subcategory_key: editTransactionForm.subcategory_key,
          asset_id: null,
          liability_id: liabilityAccount.liability_id ?? null,
          notes: entryNotesByAccountId.get(liabilityAccount.id) ?? '',
        },
      ];
      if (breakdown.interest > 0) {
        const interestAccountId = editTransactionForm.interest_account_id;
        if (interestAccountId == null) {
          store.error = 'Selecciona una cuenta de gasto para registrar el interés.';
          return null;
        }
        const interestAccount = accountMap.value.get(interestAccountId);
        if (!interestAccount || interestAccount.account_type !== 'expense') {
          store.error = 'La cuenta de interés debe ser una cuenta de gasto.';
          return null;
        }
        if (interestAccount.currency !== selectedAccount.currency) {
          store.error = 'La cuenta de interés debe usar la misma moneda que la cuenta de liquidez.';
          return null;
        }
        entries.push({
          account_id: interestAccount.id,
          side: 'debit',
          amount: breakdown.interest.toFixed(currencyDecimals(interestAccount.currency)),
          currency: interestAccount.currency,
          flow_family: 'expense',
          category_key: editTransactionForm.category_key,
          subcategory_key: editTransactionForm.subcategory_key,
          asset_id: null,
          liability_id: null,
          notes: entryNotesByAccountId.get(interestAccount.id) ?? '',
        });
      }
      entries.push({
        account_id: selectedAccount.id,
        side: 'credit',
        amount: breakdown.total.toFixed(decimals),
        currency: selectedAccount.currency,
        flow_family: '',
        category_key: '',
        subcategory_key: '',
        asset_id: selectedAccount.asset_id ?? null,
        liability_id: null,
        notes: entryNotesByAccountId.get(selectedAccount.id) ?? '',
      });
      return entries;
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
    const classifiedEntries = applyClassificationToEntries(accountAdjustedEntries, {
      kind: editTransactionForm.kind,
      categoryKey: editTransactionForm.category_key,
      subcategoryKey: editTransactionForm.subcategory_key,
      investmentDirection: editTransactionForm.investment_direction,
    });
    if (
      (editTransactionForm.kind === 'investment' || editTransactionForm.kind === 'transfer') &&
      editInvestmentIsCrossCurrency.value
    ) {
      const destinationAmount = Number(formatDecimalInput(editTransactionForm.destination_amount));
      const debitEntry = classifiedEntries.find((entry) => entry.side === 'debit') ?? null;
      const creditEntry = classifiedEntries.find((entry) => entry.side === 'credit') ?? null;
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
    return classifiedEntries;
  }

  const {
    activityKindLabel,
    transactionOwnershipLabel,
    transactionClassificationLabel,
    transactionAccountTrailLabel,
    liquidityBalanceDeltaTone,
  } = useAccountingTransactionLabels(accountMap, ownershipById, ownershipLabel);

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
        editTransactionPersistedEntries.value.map((entry) => entry.currency.trim().toUpperCase()),
      ).size > 1;
    if (hasMixedCurrencyEntries) {
      let compatibilityEntries = scaleLegacyMixedCurrencyEntries(
        editTransactionPersistedEntries.value,
        validated.selectedAccount.id,
        validated.parsedAmount,
      );
      const kindAdjustedEntries =
        editTransactionForm.kind === editTransactionForm.initial_kind
          ? compatibilityEntries
          : setEditedKindOnEntries(
              compatibilityEntries,
              editTransactionForm.kind,
              editTransactionForm.category_key,
              editTransactionForm.subcategory_key,
              editTransactionForm.investment_direction,
            );
      const accountAdjustedEntries = setEditedAccountsOnEntries(
        kindAdjustedEntries,
        editTransactionForm.kind,
        editTransactionForm.account_id!,
        editTransactionForm.counterparty_account_id,
        editTransactionForm.investment_direction,
      );
      compatibilityEntries = applyClassificationToEntries(accountAdjustedEntries, {
        kind: editTransactionForm.kind,
        categoryKey: editTransactionForm.category_key,
        subcategoryKey: editTransactionForm.subcategory_key,
        investmentDirection: editTransactionForm.investment_direction,
      });
      if (
        (editTransactionForm.kind === 'investment' || editTransactionForm.kind === 'transfer') &&
        editInvestmentIsCrossCurrency.value
      ) {
        const destinationAmount = Number(
          formatDecimalInput(editTransactionForm.destination_amount),
        );
        const debitEntry = compatibilityEntries.find((entry) => entry.side === 'debit') ?? null;
        const creditEntry = compatibilityEntries.find((entry) => entry.side === 'credit') ?? null;
        if (debitEntry) {
          debitEntry.amount = roundByCurrency(destinationAmount, debitEntry.currency).toFixed(
            currencyDecimals(debitEntry.currency),
          );
        }
        if (creditEntry) {
          creditEntry.amount = roundByCurrency(
            validated.parsedAmount,
            creditEntry.currency,
          ).toFixed(currencyDecimals(creditEntry.currency));
        }
      } else {
        compatibilityEntries = scaleEntriesToAmount(
          compatibilityEntries,
          roundByCurrency(validated.parsedAmount, validated.selectedAccount.currency),
          validated.selectedAccount.currency,
        );
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

  // eslint-disable-next-line complexity
  async function submitQuickEntry() {
    if (quickEntryForm.movement_type === 'revaluation') {
      await submitRevaluationEntry();
      return;
    }
    successMessage.value = null;
    const adjustmentDelta =
      quickEntryForm.movement_type === 'adjustment' ? quickAdjustmentDelta.value : null;
    if (quickEntryForm.movement_type === 'adjustment' && adjustmentDelta == null) {
      store.error =
        'Selecciona cuenta y saldo final objetivo para calcular automaticamente el ajuste.';
      return;
    }
    const debtBreakdown =
      quickEntryForm.movement_type === 'debt_payment' ? resolveQuickDebtBreakdown() : null;
    if (quickEntryForm.movement_type === 'debt_payment' && debtBreakdown && !debtBreakdown.valid) {
      store.error = debtBreakdown.error;
      return;
    }
    if (
      quickEntryForm.movement_type === 'debt_payment' &&
      (debtBreakdown?.interest ?? 0) > 0 &&
      quickEntryForm.interest_account_id == null
    ) {
      const currency = quickSelectedLiquidityAccount.value?.currency ?? 'EUR';
      const defaultInterestAccountId = resolveDefaultDebtInterestAccountId(currency);
      if (defaultInterestAccountId != null) {
        quickEntryForm.interest_account_id = defaultInterestAccountId;
      } else {
        store.error = 'Selecciona una cuenta de gasto para registrar el interés.';
        return;
      }
    }
    const payload: QuickLedgerTransactionWritePayload = {
      movement_type: quickEntryForm.movement_type,
      booking_date: quickEntryForm.booking_date,
      value_date: quickEntryForm.value_date,
      description: quickEntryForm.description.trim(),
      amount:
        quickEntryForm.movement_type === 'adjustment'
          ? String(adjustmentDelta)
          : formatDecimalInput(quickEntryForm.amount),
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
            ...(quickTransferIsCrossCurrency.value && quickEntryForm.destination_amount.trim()
              ? { destination_amount: formatDecimalInput(quickEntryForm.destination_amount) }
              : {}),
          }
        : {}),
      ...(quickEntryForm.movement_type === 'income' ? {} : {}),
      ...(quickEntryForm.movement_type === 'expense' ? {} : {}),
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
            amount: String(debtBreakdown?.total ?? 0),
            principal_amount: String(debtBreakdown?.principal ?? 0),
            interest_amount: String(debtBreakdown?.interest ?? 0),
            ...((debtBreakdown?.interest ?? 0) > 0
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

  onMounted(() => {
    void (async () => {
      await Promise.all([
        store.refreshAll(),
        incomeStore.loadAll(selectedYear.value),
        expenseStore.loadAll(selectedYear.value),
        peopleStore.fetchOwnerships(),
        refreshManualPositionOptions(),
        reloadDailyBalanceSeries(),
      ]);
      await fetchTodosPage(true);
      if (cuentasSelectedAccountId.value != null) {
        await fetchCuentasPage(true);
      }
    })();
  });
  // eslint-disable-next-line complexity
  async function fillQuickEntryFromTransaction(transaction: LedgerTransaction): Promise<void> {
    const rawKind: string = transaction.quick_entry_kind || transaction.activity_kind;
    let movementType: QuickLedgerMovementType = 'expense';
    if (rawKind === 'income') movementType = 'income';
    else if (rawKind === 'expense') movementType = 'expense';
    else if (rawKind === 'transfer') movementType = 'transfer';
    else if (rawKind === 'adjustment') movementType = 'adjustment';
    else if (rawKind === 'investment' || rawKind === 'investment_purchase')
      movementType = 'investment';
    else if (rawKind === 'debt_payment') movementType = 'debt_payment';
    else if (rawKind === 'revaluation') movementType = 'revaluation';

    const editableKind: EditableActivityKind =
      movementType === 'adjustment'
        ? 'balance_adjustment'
        : movementType === 'revaluation'
          ? 'revaluation'
          : movementType === 'investment'
            ? 'investment'
            : movementType === 'transfer'
              ? 'transfer'
              : movementType === 'debt_payment'
                ? 'debt_payment'
                : movementType === 'income'
                  ? 'income'
                  : 'expense';

    const direction =
      movementType === 'investment' ? getInvestmentDirection(transaction) : 'inflow';
    const debitEntry =
      transaction.entries.find((e) => e.side === 'debit') ?? transaction.entries[0] ?? null;
    const creditEntry =
      transaction.entries.find((e) => e.side === 'credit') ?? transaction.entries[1] ?? null;

    const { accountId, counterpartyAccountId } = resolveEditAccountsForKind(
      transaction,
      editableKind,
      debitEntry,
      creditEntry,
    );

    const liabilityId = movementType === 'debt_payment' ? counterpartyAccountId : null;
    const counterpartyId = movementType !== 'debt_payment' ? counterpartyAccountId : null;

    const amount = getTransactionEditAmount(transaction);
    const destinationAmount = getTransactionEditDestinationAmount(transaction);

    const classifiedEntry =
      transaction.entries.find(
        (e) => Boolean(e.flow_family) && Boolean(e.category_key) && Boolean(e.subcategory_key),
      ) ?? null;

    // Phase 1: set movement_type to trigger watcher that resets dependent fields
    quickEntryForm.movement_type = movementType;

    // Phase 2: after watcher settles, fill all fields
    await nextTick();

    quickEntryForm.investment_direction = direction;
    const today = new Date().toISOString().slice(0, 10);
    quickEntryForm.booking_date = today;
    quickEntryForm.value_date = today;
    quickEntryForm.description = transaction.description;
    quickEntryForm.ownership_id = transaction.ownership_id ?? null;
    quickEntryForm.amount = amount;
    quickEntryForm.destination_amount = destinationAmount;
    quickEntryForm.account_id = accountId;
    quickEntryForm.counterparty_account_id = counterpartyId;
    quickEntryForm.liability_account_id = liabilityId;
    if (movementType === 'debt_payment') {
      const debtBreakdown = resolveDebtBreakdownFromEntries(transaction);
      quickEntryForm.interest_account_id = debtBreakdown.interestAccountId;
      quickEntryForm.principal_amount = debtBreakdown.principalAmount;
      quickEntryForm.interest_amount = debtBreakdown.interestAmount;
    } else {
      quickEntryForm.interest_account_id = null;
      quickEntryForm.principal_amount = '';
      quickEntryForm.interest_amount = '';
    }
    quickEntryForm.realized_cost_basis = transaction.realized_cost_basis ?? '';
    quickEntryForm.realized_gain_loss = transaction.realized_gain_loss ?? '';
    quickEntryForm.category_key = classifiedEntry?.category_key ?? '';
    quickEntryForm.subcategory_key = classifiedEntry?.subcategory_key ?? '';
    quickEntryForm.notes = transaction.notes ?? '';
    quickEntryForm.revaluation_new_value = '';
  }

  return {
    loading,
    accountCreationLoading,
    accountActivationLoading,
    transactionCreationLoading,
    error,
    successMessage,
    accounts,
    monthlySummary,
    accountBalancesSummary,
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
    editInvestmentOriginOptions,
    editInvestmentOriginCurrency,
    editInvestmentDestinationCurrency,
    editInvestmentIsCrossCurrency,
    editSelectedAccountCurrentBalance,
    editCategoryOptions,
    editSubcategoryOptions,
    editCategoryLocked,
    editSubcategoryLocked,
    editDebtComputedInterest,
    accountForm,
    activationForm,
    ownershipOptions,
    ownershipFilterOptions,
    quickEntryForm,
    transactionForm,
    editTransactionId,
    editTransactionForm,
    activityFilters,
    cuentasFilters,
    liquidityAccounts,
    quickAdjustmentAccountOptions,
    availableManualPositionOptions,
    accountPositionMetaByAccountId,
    accountDisplayName,
    hasAvailableManualPositions,
    liquidityBalanceRows,
    liquidityBalanceTotal,
    incomeOptions,
    expenseOptions,
    quickEntryNeedsClassification,
    quickCategoryOptions,
    quickSubcategoryOptions,
    quickCategoryLocked,
    quickSubcategoryLocked,
    filterCategoryOptions,
    filterSubcategoryOptions,
    cuentasFilterCategoryOptions,
    cuentasFilterSubcategoryOptions,
    transferOriginOptions,
    transferCounterpartyOptions,
    investmentOriginOptions,
    investmentCounterpartyOptions,
    quickInvestmentOriginCurrency,
    quickInvestmentDestinationCurrency,
    quickInvestmentIsCrossCurrency,
    quickTransferOriginCurrency,
    quickTransferDestinationCurrency,
    quickTransferIsCrossCurrency,
    liabilityCounterpartyOptions,
    debtInterestOptions,
    revaluationAccountOptions,
    revaluationCurrentBalance,
    revaluationDelta,
    quickAdjustmentCurrency,
    quickAdjustmentDisplayDecimals,
    quickAdjustmentCurrentBalance,
    quickAdjustmentDelta,
    quickEntryReady,
    editEntryReady,
    debitTotal,
    creditTotal,
    transactionBalanced,
    summaryRows,
    dailyBalanceSeriesRows,
    dailyBalanceSeriesLoading,
    dailyBalanceSeriesError,
    dailyBalanceSeriesUnit,
    dailyBalanceOwnershipFilter,
    dailyBalanceSeriesChartPoints,
    dailyBalanceSeriesChartRows,
    dailyBalanceSeriesMonthlyRows,
    dailyBalanceSeriesRangeLabel,
    dailyBalanceLatestChartPoint,
    dailyTimelinePresetOptions,
    selectedDailyTimelinePreset,
    dailyTimelineCustomWindow,
    dailyTimelineWindow,
    dailyTimelineExpanded,
    setDailyTimelinePreset,
    updateDailyTimelineWindowStart,
    updateDailyTimelineWindowEnd,
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
    deleteAccount,
    submitQuickEntry,
    submitTransaction,
    openTransactionForEditing,
    submitEditedTransaction,
    resetEditTransactionForm,
    deleteTransaction,
    fillQuickEntryFromTransaction,
  };
}
