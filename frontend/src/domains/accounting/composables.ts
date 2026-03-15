import { computed, onMounted, reactive, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAccountingStore } from '@/domains/accounting/store';
import {
  useAnnualExpenseStore,
  useAnnualIncomeStore,
  type AnnualExpenseEntry,
  type AnnualIncomeEntry,
} from '@/domains/data-input';
import type {
  LedgerAccountType,
  LedgerEntrySide,
  LedgerTransactionWritePayload,
  QuickLedgerMovementType,
  QuickLedgerTransactionWritePayload,
} from '@/domains/accounting/models';

type TransactionFormRow = {
  key: number;
  account_id: number | null;
  side: LedgerEntrySide;
  amount: string;
  currency: string;
  notes: string;
};

function formatDecimalInput(raw: string): string {
  return raw.replace(',', '.').trim();
}

function toNumber(raw: string): number {
  const parsed = Number(formatDecimalInput(raw));
  return Number.isFinite(parsed) ? parsed : 0;
}

export function useAccountingPage() {
  const store = useAccountingStore();
  const incomeStore = useAnnualIncomeStore('core');
  const expenseStore = useAnnualExpenseStore('core');
  const { loading, accountCreationLoading, transactionCreationLoading, error } = storeToRefs(store);
  const { accounts, transactions, monthlySummary } = storeToRefs(store);

  const successMessage = ref<string | null>(null);

  const accountForm = reactive({
    name: '',
    account_type: 'asset' as LedgerAccountType,
    currency: 'EUR',
    origin: 'user' as const,
    notes: '',
  });

  const quickEntryForm = reactive({
    movement_type: 'expense' as QuickLedgerMovementType,
    booking_date: new Date().toISOString().slice(0, 10),
    value_date: new Date().toISOString().slice(0, 10),
    description: '',
    amount: '',
    account_id: null as number | null,
    counterparty_account_id: null as number | null,
    annual_income_entry_id: null as number | null,
    annual_expense_entry_id: null as number | null,
    notes: '',
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
    { value: 'equity', label: 'Patrimonio neto' },
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
  const quickEntryReady = computed(() => {
    if (!quickEntryForm.description.trim()) return false;
    if (!quickEntryForm.booking_date || !quickEntryForm.value_date) return false;
    if (toNumber(quickEntryForm.amount) <= 0) return false;
    if (quickEntryForm.account_id == null) return false;
    if (quickEntryForm.movement_type === 'transfer') {
      return quickEntryForm.counterparty_account_id != null;
    }
    return true;
  });
  const quickMovementTypeOptions: { value: QuickLedgerMovementType; label: string }[] = [
    { value: 'income', label: 'Ingreso' },
    { value: 'expense', label: 'Gasto' },
    { value: 'transfer', label: 'Transferencia' },
  ];

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
      if (movementType !== 'income') quickEntryForm.annual_income_entry_id = null;
      if (movementType !== 'expense') quickEntryForm.annual_expense_entry_id = null;
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
    quickEntryForm.annual_income_entry_id = null;
    quickEntryForm.annual_expense_entry_id = null;
    quickEntryForm.notes = '';
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
      ...(quickEntryForm.movement_type === 'transfer'
        ? { counterparty_account_id: quickEntryForm.counterparty_account_id }
        : {}),
      ...(quickEntryForm.movement_type === 'income'
        ? { annual_income_entry_id: quickEntryForm.annual_income_entry_id }
        : {}),
      ...(quickEntryForm.movement_type === 'expense'
        ? { annual_expense_entry_id: quickEntryForm.annual_expense_entry_id }
        : {}),
    };
    await store.createQuickEntry(payload);
    resetQuickEntryForm();
    successMessage.value = 'Movimiento rapido registrado.';
  }

  onMounted(() => {
    void Promise.all([
      store.refreshAll(),
      incomeStore.loadAll(selectedYear.value),
      expenseStore.loadAll(selectedYear.value),
    ]);
  });

  return {
    loading,
    accountCreationLoading,
    transactionCreationLoading,
    error,
    successMessage,
    accounts,
    transactions,
    monthlySummary,
    selectedYear,
    selectedMonth,
    yearOptions,
    monthOptions,
    accountTypeOptions,
    quickMovementTypeOptions,
    accountForm,
    quickEntryForm,
    transactionForm,
    liquidityAccounts,
    incomeOptions,
    expenseOptions,
    transferCounterpartyOptions,
    quickEntryReady,
    debitTotal,
    creditTotal,
    transactionBalanced,
    summaryRows,
    addEntry,
    removeEntry,
    reloadPeriod,
    submitAccount,
    submitQuickEntry,
    submitTransaction,
  };
}
