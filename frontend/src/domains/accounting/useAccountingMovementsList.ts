import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue';
import type { Ref } from 'vue';
import { useAccountingStore } from '@/domains/accounting/store';
import { isCanceledRequestError } from '@/lib/errors';
import {
  type ActivityFilter,
  categoryOptionsByKind,
} from '@/domains/accounting/useTransactionClassification';
import type {
  LedgerAccount,
  LedgerAccountType,
  LedgerTransaction,
} from '@/domains/accounting/models';

type MovementsTab = 'cuentas' | 'todos' | 'estadisticas';

type AccountTimelineTransaction = LedgerTransaction & {
  impactValue: number;
  accountBalanceAfterValue: number | null;
  tone: 'positive' | 'negative' | 'neutral';
};

function toNumber(raw: string): number {
  const parsed = Number(raw.replace(',', '.').trim());
  return Number.isFinite(parsed) ? parsed : 0;
}

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

function toAccountTimelineRows(
  rows: LedgerTransaction[],
  accountId: number,
  accountType: LedgerAccountType,
): AccountTimelineTransaction[] {
  return rows.map((transaction) => {
    const impactValue = (transaction.entries ?? [])
      .filter((entry) => entry.account_id === accountId)
      .reduce((sum, entry) => sum + signedImpact(accountType, entry.side, entry.amount), 0);
    const accountBalanceAfterValue =
      transaction.account_balance_after != null
        ? toNumber(transaction.account_balance_after)
        : null;
    return {
      ...transaction,
      impactValue,
      accountBalanceAfterValue,
      tone: impactTone(impactValue),
    };
  });
}

export function useAccountingMovementsList(
  accounts: Ref<LedgerAccount[]>,
  reloadDailyBalanceSeries: () => Promise<void>,
) {
  const store = useAccountingStore();

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

  const filterCategoryOptions = computed(() => categoryOptionsByKind(activityFilters.kind));
  const cuentasFilterCategoryOptions = computed(() => categoryOptionsByKind(cuentasFilters.kind));

  const MOVEMENTS_PAGE_SIZE = 50;
  const activeTab = ref<MovementsTab>('cuentas');
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
          include_entries: false,
          include_total: reset,
        },
        { signal: controller.signal },
      );
      todosTransactions.value = reset ? page.results : todosTransactions.value.concat(page.results);
      todosNextCursor.value = page.next_cursor;
      if (page.total_count !== null) todosTotalCount.value = page.total_count;
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
          include_total: reset,
        },
        { signal: controller.signal },
      );
      const pageRows = toAccountTimelineRows(page.results, accountId, account.account_type);
      cuentasTransactions.value = reset ? pageRows : cuentasTransactions.value.concat(pageRows);
      cuentasNextCursor.value = page.next_cursor;
      if (page.total_count !== null) cuentasTotalCount.value = page.total_count;
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

  async function reloadMovementPagesAfterMutation(): Promise<void> {
    const previousTodosLoaded = todosTransactions.value.length;
    const previousCuentasLoaded = cuentasTransactions.value.length;
    const hasSelectedAccount = cuentasSelectedAccountId.value != null;

    await fetchTodosPage(true);
    const desiredTodos = Math.min(previousTodosLoaded, todosTotalCount.value);
    while (todosHasMore.value && todosTransactions.value.length < desiredTodos) {
      await fetchTodosPage(false);
    }

    if (hasSelectedAccount) {
      await fetchCuentasPage(true);
      const desiredCuentas = Math.min(previousCuentasLoaded, cuentasTotalCount.value);
      while (cuentasHasMore.value && cuentasTransactions.value.length < desiredCuentas) {
        await fetchCuentasPage(false);
      }
    }
    await reloadDailyBalanceSeries();
  }

  function transactionMainAmount(t: LedgerTransaction): number {
    return toNumber(t.amount ?? '0');
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
  };
}
