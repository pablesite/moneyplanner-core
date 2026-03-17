import { computed, onMounted, reactive, ref, watch } from 'vue';
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
  account_id: number | null;
  counterparty_account_id: number | null;
  amount: string;
  currency: string;
  kind: EditableActivityKind;
  initial_kind: EditableActivityKind;
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
  | 'investment_purchase'
  | 'debt_payment';
type EditableActivityKind =
  | 'income'
  | 'expense'
  | 'transfer'
  | 'investment_purchase'
  | 'debt_payment'
  | 'balance_adjustment';
type ClassificationActivityKind = 'income' | 'expense';
type CounterpartyEditableKind = 'transfer' | 'investment_purchase' | 'debt_payment';

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

export function useAccountingPage() {
  const store = useAccountingStore();
  const incomeStore = useAnnualIncomeStore('core');
  const expenseStore = useAnnualExpenseStore('core');
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
    transactions,
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
    booking_date: new Date().toISOString().slice(0, 10),
    value_date: new Date().toISOString().slice(0, 10),
    description: '',
    amount: '',
    account_id: null as number | null,
    counterparty_account_id: null as number | null,
    liability_account_id: null as number | null,
    interest_account_id: null as number | null,
    principal_amount: '',
    interest_amount: '',
    flow_family: '' as '' | 'income' | 'expense',
    category_key: '',
    subcategory_key: '',
    annual_income_entry_id: null as number | null,
    annual_expense_entry_id: null as number | null,
    notes: '',
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
    account_id: null,
    counterparty_account_id: null,
    amount: '',
    currency: 'EUR',
    kind: 'transfer',
    initial_kind: 'transfer',
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

  const accountMap = computed(
    () => new Map(accounts.value.map((account) => [account.id, account])),
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
        account.id !== quickEntryForm.account_id &&
        account.asset_id != null,
    ),
  );
  const liabilityCounterpartyOptions = computed(() =>
    accounts.value.filter(
      (account) => account.account_type === 'liability' && account.liability_id != null,
    ),
  );
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
    const amountValue = toNumber(quickEntryForm.amount);
    if (amountValue <= 0) return false;
    if (quickEntryForm.account_id == null) return false;
    if (quickEntryForm.movement_type === 'transfer') {
      return quickEntryForm.counterparty_account_id != null;
    }
    if (quickEntryForm.movement_type === 'investment_purchase') {
      return quickEntryForm.counterparty_account_id != null;
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
  const quickEntryNeedsClassification = computed(() => {
    if (quickEntryForm.movement_type === 'income') return true;
    if (quickEntryForm.movement_type === 'expense') return true;
    if (quickEntryForm.movement_type !== 'debt_payment') return false;
    return toNumber(quickEntryForm.interest_amount) > 0;
  });
  const quickCategoryOptions = computed(() => {
    if (quickEntryForm.movement_type === 'income') return incomeCategories;
    if (quickEntryForm.movement_type === 'expense') return expenseCategories;
    if (
      quickEntryForm.movement_type === 'debt_payment' &&
      toNumber(quickEntryForm.interest_amount) > 0
    ) {
      return expenseCategories;
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
    if (
      quickEntryForm.movement_type === 'expense' ||
      (quickEntryForm.movement_type === 'debt_payment' &&
        toNumber(quickEntryForm.interest_amount) > 0)
    ) {
      return expenseSubcategories.filter(
        (row) => row.category === (quickEntryForm.category_key as ExpenseCategoryKey),
      );
    }
    return [];
  });
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
    { value: 'investment_purchase', label: 'Compra inversion' },
    { value: 'debt_payment', label: 'Pago deuda' },
  ];
  const editMovementTypeOptions: { value: EditableActivityKind; label: string }[] = [
    { value: 'income', label: 'Ingreso' },
    { value: 'expense', label: 'Gasto' },
    { value: 'transfer', label: 'Transferencia' },
    { value: 'investment_purchase', label: 'Inversion' },
    { value: 'debt_payment', label: 'Deuda' },
    { value: 'balance_adjustment', label: 'Ajuste' },
  ];
  const editAccountOptions = computed(() =>
    accounts.value
      .filter((account) => account.account_type === 'asset' || account.account_type === 'liability')
      .sort((a, b) => a.name.localeCompare(b.name, 'es')),
  );
  function isClassificationKind(kind: EditableActivityKind): kind is ClassificationActivityKind {
    return kind === 'income' || kind === 'expense';
  }

  function isCounterpartyKind(kind: EditableActivityKind): kind is CounterpartyEditableKind {
    return kind === 'transfer' || kind === 'investment_purchase' || kind === 'debt_payment';
  }

  const editKindNeedsClassification = computed(() =>
    isClassificationKind(editTransactionForm.kind),
  );
  const editKindNeedsCounterparty = computed(() => isCounterpartyKind(editTransactionForm.kind));
  const editCounterpartyLabel = computed(() => {
    if (editTransactionForm.kind === 'investment_purchase') return 'Cuenta de inversion';
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
    if (editTransactionForm.kind === 'investment_purchase') {
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
    if (editTransactionForm.kind === 'investment_purchase') {
      return 'No hay cuentas de inversion contables activas. Activa tracking contable en la posicion manual para poder usarla aqui.';
    }
    if (editTransactionForm.kind === 'debt_payment') {
      return 'No hay cuentas de pasivo contables activas. Activa tracking contable en el pasivo manual para poder usarlo aqui.';
    }
    return 'No hay contracuentas disponibles para el tipo seleccionado.';
  });
  const editCategoryOptions = computed(() => {
    if (editTransactionForm.kind === 'income') return incomeCategories;
    if (editTransactionForm.kind === 'expense') return expenseCategories;
    return [];
  });
  const editSubcategoryOptions = computed(() => {
    if (!editTransactionForm.category_key) return [];
    if (editTransactionForm.kind === 'income') {
      return incomeSubcategories.filter(
        (row) => row.category === (editTransactionForm.category_key as IncomeCategoryKey),
      );
    }
    if (editTransactionForm.kind === 'expense') {
      return expenseSubcategories.filter(
        (row) => row.category === (editTransactionForm.category_key as ExpenseCategoryKey),
      );
    }
    return [];
  });
  const editEntryReady = computed(() => {
    if (!editTransactionForm.description.trim()) return false;
    if (!editTransactionForm.booking_date || !editTransactionForm.value_date) return false;
    if (editTransactionForm.account_id == null) return false;
    const parsedAmount = Number(formatDecimalInput(editTransactionForm.amount));
    if (!Number.isFinite(parsedAmount)) return false;
    if (editTransactionForm.kind !== 'balance_adjustment' && parsedAmount <= 0) return false;
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
      quickEntryForm.flow_family = '';
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
      if (isCounterpartyKind(kind)) {
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
  const filteredTransactions = computed(() =>
    transactions.value.filter((transaction) => {
      const normalizedQuery = activityFilters.query.trim().toLocaleLowerCase('es');
      if (normalizedQuery) {
        const haystack = [
          transaction.description,
          transaction.notes,
          ...transaction.entries.map((entry) => `${entry.account_name} ${entry.notes}`),
        ]
          .join(' ')
          .toLocaleLowerCase('es');
        if (!haystack.includes(normalizedQuery)) return false;
      }

      if (activityFilters.accountId !== 'all') {
        const expectedAccountId = Number(activityFilters.accountId);
        if (!transaction.entries.some((entry) => entry.account_id === expectedAccountId))
          return false;
      }

      if (activityFilters.kind !== 'all') {
        if (getTransactionActivityKind(transaction) !== activityFilters.kind) return false;
      }

      return true;
    }),
  );

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
    quickEntryForm.booking_date = new Date().toISOString().slice(0, 10);
    quickEntryForm.value_date = quickEntryForm.booking_date;
    quickEntryForm.description = '';
    quickEntryForm.amount = '';
    quickEntryForm.account_id = null;
    quickEntryForm.counterparty_account_id = null;
    quickEntryForm.liability_account_id = null;
    quickEntryForm.interest_account_id = null;
    quickEntryForm.principal_amount = '';
    quickEntryForm.interest_amount = '';
    quickEntryForm.flow_family = '';
    quickEntryForm.category_key = '';
    quickEntryForm.subcategory_key = '';
    quickEntryForm.annual_income_entry_id = null;
    quickEntryForm.annual_expense_entry_id = null;
    quickEntryForm.notes = '';
  }
  function resetEditTransactionForm() {
    editTransactionId.value = null;
    editTransactionPersistedEntries.value = [];
    editTransactionForm.booking_date = new Date().toISOString().slice(0, 10);
    editTransactionForm.value_date = editTransactionForm.booking_date;
    editTransactionForm.booking_time = '12:00';
    editTransactionForm.description = '';
    editTransactionForm.notes = '';
    editTransactionForm.account_id = null;
    editTransactionForm.counterparty_account_id = null;
    editTransactionForm.amount = '';
    editTransactionForm.currency = 'EUR';
    editTransactionForm.kind = 'transfer';
    editTransactionForm.initial_kind = 'transfer';
    editTransactionForm.category_key = '';
    editTransactionForm.subcategory_key = '';
    editTransactionForm.kind_label = '';
  }

  function toEditableKind(transaction: LedgerTransaction): EditableActivityKind {
    const detected = getTransactionActivityKind(transaction);
    if (detected === 'income') return 'income';
    if (detected === 'expense') return 'expense';
    if (detected === 'investment_purchase') return 'investment_purchase';
    if (detected === 'debt_payment') return 'debt_payment';
    return 'transfer';
  }

  function activityKindDisplay(kind: EditableActivityKind): string {
    if (kind === 'income') return 'Ingreso';
    if (kind === 'expense') return 'Gasto';
    if (kind === 'transfer') return 'Transferencia';
    if (kind === 'investment_purchase') return 'Inversion';
    if (kind === 'debt_payment') return 'Deuda';
    return 'Ajuste';
  }

  function getTransactionEditAmount(transaction: LedgerTransaction): string {
    const debitTotalValue = transaction.entries
      .filter((entry) => entry.side === 'debit')
      .reduce((sum, entry) => sum + toNumber(entry.amount), 0);
    return debitTotalValue.toFixed(2);
  }

  function resolveEditAccountsForKind(
    transaction: LedgerTransaction,
    kind: EditableActivityKind,
    debitEntry: LedgerTransaction['entries'][number] | null,
    creditEntry: LedgerTransaction['entries'][number] | null,
  ): { accountId: number | null; counterpartyAccountId: number | null } {
    if (kind === 'income') {
      return {
        accountId: debitEntry?.account_id ?? null,
        counterpartyAccountId: null,
      };
    }
    if (kind === 'expense') {
      return {
        accountId: creditEntry?.account_id ?? null,
        counterpartyAccountId: null,
      };
    }
    if (kind === 'debt_payment') {
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
    }
    return {
      accountId: creditEntry?.account_id ?? null,
      counterpartyAccountId: debitEntry?.account_id ?? null,
    };
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
    editTransactionForm.currency = transaction.entries[0]?.currency ?? 'EUR';
    editTransactionForm.amount = getTransactionEditAmount(transaction);
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
    editTransactionForm.category_key = primaryClassifiedEntry?.category_key ?? '';
    editTransactionForm.subcategory_key = primaryClassifiedEntry?.subcategory_key ?? '';
    editTransactionForm.kind_label = activityKindDisplay(kind);
  }

  function scaleEntriesToAmount(
    entries: PersistedTransactionEntry[],
    targetAmount: number,
  ): PersistedTransactionEntry[] {
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
    const round2 = (value: number) => Math.round(value * 100) / 100;
    const applySide = (indexes: number[]) => {
      if (!indexes.length) return;
      let allocated = 0;
      indexes.forEach((index, position) => {
        const currentValue = toNumber(scaled[index]!.amount);
        const isLast = position === indexes.length - 1;
        const nextValue = isLast ? round2(targetAmount - allocated) : round2(currentValue * factor);
        allocated = round2(allocated + nextValue);
        scaled[index]!.amount = nextValue.toFixed(2);
      });
    };
    applySide(debitIndexes);
    applySide(creditIndexes);
    return scaled;
  }

  function setEditedKindOnEntries(
    entries: PersistedTransactionEntry[],
    kind: EditableActivityKind,
    categoryKey: string,
    subcategoryKey: string,
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

    const preferredSide = kind === 'income' ? 'credit' : 'debit';
    const preferredEntry =
      nextEntries.find((entry) => entry.side === preferredSide) ?? nextEntries[0] ?? null;
    if (!preferredEntry) return nextEntries;
    preferredEntry.flow_family = kind;
    preferredEntry.category_key = categoryKey;
    preferredEntry.subcategory_key = subcategoryKey;
    return nextEntries;
  }

  function setEditedAccountsOnEntries(
    entries: PersistedTransactionEntry[],
    kind: EditableActivityKind,
    accountId: number,
    counterpartyAccountId: number | null,
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
    if (kind === 'balance_adjustment') {
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
    const absoluteAmount = Math.abs(round2(amount)).toFixed(2);
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

  function validateEditedTransactionInput(): {
    parsedAmount: number;
    selectedAccount: LedgerAccount;
  } | null {
    const parsedAmount = Number(formatDecimalInput(editTransactionForm.amount));
    if (!Number.isFinite(parsedAmount)) {
      store.error = 'Introduce un importe valido.';
      return null;
    }
    if (editTransactionForm.kind !== 'balance_adjustment' && parsedAmount <= 0) {
      store.error = 'El importe debe ser mayor que 0.';
      return null;
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
    const editedAmount = round2(parsedAmount);
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
    const scaledEntries = scaleEntriesToAmount(editTransactionPersistedEntries.value, editedAmount);
    const kindAdjustedEntries =
      editTransactionForm.kind === editTransactionForm.initial_kind
        ? scaledEntries
        : setEditedKindOnEntries(
            scaledEntries,
            editTransactionForm.kind,
            editTransactionForm.category_key,
            editTransactionForm.subcategory_key,
          );
    return setEditedAccountsOnEntries(
      kindAdjustedEntries,
      editTransactionForm.kind,
      editTransactionForm.account_id!,
      classificationCounterpartyAccountId,
    );
  }

  function getTransactionActivityKind(
    transaction: LedgerTransaction,
  ): Exclude<ActivityFilter, 'all'> | 'other' {
    const hasIncomeClassified = transaction.entries.some((entry) => entry.flow_family === 'income');
    if (hasIncomeClassified) return 'income';
    const hasExpenseClassified = transaction.entries.some(
      (entry) => entry.flow_family === 'expense',
    );

    const hasIncomeLink = transaction.entries.some((entry) => entry.annual_income_entry_id != null);
    if (hasIncomeLink) return 'income';

    const hasExpenseLink = transaction.entries.some(
      (entry) => entry.annual_expense_entry_id != null,
    );
    const hasLiabilityLink = transaction.entries.some((entry) => entry.liability_id != null);
    if (hasLiabilityLink) return 'debt_payment';
    if (hasExpenseClassified) return 'expense';
    if (hasExpenseLink) return 'expense';

    const assetEntries = transaction.entries.filter(
      (entry) => accountMap.value.get(entry.account_id)?.account_type === 'asset',
    );
    const hasAssetPositionLink = transaction.entries.some((entry) => entry.asset_id != null);
    if (hasAssetPositionLink) return 'investment_purchase';
    if (assetEntries.length >= 2) return 'transfer';

    return 'other';
  }

  function activityKindLabel(transaction: LedgerTransaction): string {
    const kind = getTransactionActivityKind(transaction);
    if (kind === 'income') return 'Ingreso';
    if (kind === 'expense') return 'Gasto';
    if (kind === 'transfer') return 'Transferencia';
    if (kind === 'investment_purchase') return 'Compra inversion';
    if (kind === 'debt_payment') return 'Pago deuda';
    return 'Asiento';
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
    await store.setPeriod(selectedYear.value, selectedMonth.value);
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
    resetTransactionForm();
    successMessage.value = 'Movimiento contable registrado.';
  }

  function openTransactionForEditing(transactionId: number) {
    const transaction = transactions.value.find((row) => row.id === transactionId);
    if (!transaction) return false;
    if (transaction.origin === 'system') {
      store.error = 'Los asientos de origen system no se pueden editar desde esta vista.';
      return false;
    }
    fillEditTransactionForm(transaction);
    return true;
  }

  async function submitEditedTransaction(): Promise<boolean> {
    if (editTransactionId.value == null) return false;
    if (!editTransactionPersistedEntries.value.length) return false;
    const validated = validateEditedTransactionInput();
    if (!validated) return false;
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
    const payload: LedgerTransactionWritePayload = {
      booking_date: editTransactionForm.booking_date,
      value_date: editTransactionForm.value_date,
      description: editTransactionForm.description.trim(),
      status: 'posted',
      origin: 'manual',
      notes: editTransactionForm.notes.trim(),
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
      resetEditTransactionForm();
      successMessage.value = 'Movimiento contable actualizado.';
      return true;
    } catch {
      return false;
    }
  }

  async function deleteTransaction(transactionId: number, transactionDescription: string) {
    const transaction = transactions.value.find((row) => row.id === transactionId);
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
    successMessage.value = 'Movimiento contable eliminado.';
  }

  async function submitQuickEntry() {
    successMessage.value = null;
    const payload: QuickLedgerTransactionWritePayload = {
      movement_type: quickEntryForm.movement_type,
      booking_date: quickEntryForm.booking_date,
      value_date: quickEntryForm.value_date,
      description: quickEntryForm.description.trim(),
      amount: formatDecimalInput(quickEntryForm.amount),
      account_id: quickEntryForm.account_id ?? 0,
      notes: quickEntryForm.notes.trim(),
      status: 'posted',
      origin: 'manual',
      ...(quickEntryNeedsClassification.value
        ? {
            flow_family:
              quickEntryForm.movement_type === 'income' ? 'income' : ('expense' as const),
            category_key: quickEntryForm.category_key,
            subcategory_key: quickEntryForm.subcategory_key,
          }
        : {}),
      ...(quickEntryForm.movement_type === 'transfer'
        ? { counterparty_account_id: quickEntryForm.counterparty_account_id }
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
      ...(quickEntryForm.movement_type === 'investment_purchase'
        ? { counterparty_account_id: quickEntryForm.counterparty_account_id }
        : {}),
      ...(quickEntryForm.movement_type === 'debt_payment'
        ? {
            liability_account_id: quickEntryForm.liability_account_id,
            principal_amount: formatDecimalInput(quickEntryForm.principal_amount),
            interest_amount: formatDecimalInput(quickEntryForm.interest_amount || '0'),
            ...(quickEntryForm.annual_expense_entry_id != null
              ? { annual_expense_entry_id: quickEntryForm.annual_expense_entry_id }
              : {}),
            ...(toNumber(quickEntryForm.interest_amount) > 0
              ? { interest_account_id: quickEntryForm.interest_account_id }
              : {}),
          }
        : {}),
    };
    await store.createQuickEntry(payload);
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

  async function commitMoneyWizImport() {
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
    const result = await store.commitMoneyWizImport(moneyWizImportFile.value);
    successMessage.value =
      result.created_count > 0
        ? `Importacion MoneyWiz completada: ${result.created_count} movimientos nuevos.`
        : 'Importacion MoneyWiz completada sin crear movimientos nuevos.';
    return result;
  }

  onMounted(() => {
    void Promise.all([
      store.refreshAll(),
      incomeStore.loadAll(selectedYear.value),
      expenseStore.loadAll(selectedYear.value),
      refreshManualPositionOptions(),
    ]);
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
    transactions,
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
    editSelectedAccountCurrentBalance,
    editCategoryOptions,
    editSubcategoryOptions,
    accountForm,
    activationForm,
    quickEntryForm,
    transactionForm,
    editTransactionId,
    editTransactionForm,
    activityFilters,
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
    transferCounterpartyOptions,
    investmentCounterpartyOptions,
    liabilityCounterpartyOptions,
    debtInterestOptions,
    quickEntryReady,
    editEntryReady,
    debitTotal,
    creditTotal,
    transactionBalanced,
    summaryRows,
    filteredTransactions,
    addEntry,
    activityKindLabel,
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
  };
}
