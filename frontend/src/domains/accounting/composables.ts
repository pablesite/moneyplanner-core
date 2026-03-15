import { computed, onMounted, reactive, ref, watch } from 'vue';
import { storeToRefs } from 'pinia';
import { useAccountingStore } from '@/domains/accounting/store';
import type {
  LedgerAccountType,
  LedgerEntrySide,
  LedgerTransactionWritePayload,
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

  onMounted(() => {
    void store.refreshAll();
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
    accountForm,
    transactionForm,
    debitTotal,
    creditTotal,
    transactionBalanced,
    summaryRows,
    addEntry,
    removeEntry,
    reloadPeriod,
    submitAccount,
    submitTransaction,
  };
}
