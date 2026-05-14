import { coreApi } from '@/lib/api';
import type {
  BudgetDerivedSuggestions,
  DeleteImportedTransactionsResult,
  LedgerAccount,
  LedgerAccountBalanceSummary,
  LedgerDailyBalanceSeries,
  LedgerAccountWritePayload,
  LedgerEntry,
  LedgerTransaction,
  PaginatedTransactionsResponse,
  LedgerTransactionWritePayload,
  MoneyWizImportCommitResult,
  MoneyWizImportPreview,
  MonthlyAccountingSummary,
  QuickLedgerTransactionWritePayload,
} from '@/domains/accounting/models';

function buildTransactionQueryParams(params?: {
  year?: number;
  month?: number;
  status?: string;
  cursor?: string;
  page_size?: number;
  date_from?: string;
  date_to?: string;
  account_id?: number;
  query?: string;
  kind?: string;
  category_key?: string;
  subcategory_key?: string;
}) {
  if (!params) return undefined;
  const queryParams = {
    ...(params.year ? { year: params.year } : {}),
    ...(params.month ? { month: params.month } : {}),
    ...(params.status ? { status: params.status } : {}),
    ...(params.cursor ? { cursor: params.cursor } : {}),
    ...(params.page_size ? { page_size: params.page_size } : {}),
    ...(params.date_from ? { date_from: params.date_from } : {}),
    ...(params.date_to ? { date_to: params.date_to } : {}),
    ...(params.account_id ? { account_id: params.account_id } : {}),
    ...(params.query ? { query: params.query } : {}),
    ...(params.kind ? { kind: params.kind } : {}),
    ...(params.category_key ? { category_key: params.category_key } : {}),
    ...(params.subcategory_key ? { subcategory_key: params.subcategory_key } : {}),
  };
  return Object.keys(queryParams).length ? queryParams : undefined;
}

export const coreAccountingApi = {
  getAccounts(params?: { account_type?: string; is_active?: boolean }) {
    return coreApi.get<LedgerAccount[]>('/api/accounting/accounts/', {
      params:
        params && (params.account_type || typeof params.is_active === 'boolean')
          ? {
              ...(params.account_type ? { account_type: params.account_type } : {}),
              ...(typeof params.is_active === 'boolean'
                ? { is_active: String(params.is_active) }
                : {}),
            }
          : undefined,
    });
  },
  createAccount(payload: LedgerAccountWritePayload) {
    return coreApi.post<LedgerAccount>('/api/accounting/accounts/', payload);
  },
  deleteAccount(id: number) {
    return coreApi.delete<void>(`/api/accounting/accounts/${id}/`);
  },
  updateAccount(id: number, payload: Partial<LedgerAccountWritePayload>) {
    return coreApi.patch<LedgerAccount>(`/api/accounting/accounts/${id}/`, payload);
  },
  getTransactions(
    params?: {
      year?: number;
      month?: number;
      status?: string;
      cursor?: string;
      page_size?: number;
      date_from?: string;
      date_to?: string;
      account_id?: number;
      query?: string;
      kind?: string;
      category_key?: string;
      subcategory_key?: string;
    },
    options?: { signal?: AbortSignal },
  ) {
    return coreApi.get<PaginatedTransactionsResponse>('/api/accounting/transactions/', {
      params: buildTransactionQueryParams(params),
      signal: options?.signal,
    });
  },
  createTransaction(payload: LedgerTransactionWritePayload) {
    return coreApi.post<LedgerTransaction>('/api/accounting/transactions/', payload);
  },
  updateTransaction(id: number, payload: LedgerTransactionWritePayload) {
    return coreApi.patch<LedgerTransaction>(`/api/accounting/transactions/${id}/`, payload);
  },
  deleteTransaction(id: number) {
    return coreApi.delete<void>(`/api/accounting/transactions/${id}/`);
  },
  createQuickEntry(payload: QuickLedgerTransactionWritePayload) {
    return coreApi.post<LedgerTransaction>('/api/accounting/transactions/quick-entry/', payload);
  },
  deleteImportedTransactions() {
    return coreApi.post<DeleteImportedTransactionsResult>(
      '/api/accounting/transactions/delete-imported/',
    );
  },
  previewMoneyWizImport(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    return coreApi.post<MoneyWizImportPreview>(
      '/api/accounting/transactions/import/moneywiz/preview/',
      formData,
    );
  },
  commitMoneyWizImport(file: File, options: Record<string, unknown> = {}) {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('options', JSON.stringify(options));
    return coreApi.post<MoneyWizImportCommitResult>(
      '/api/accounting/transactions/import/moneywiz/commit/',
      formData,
    );
  },
  getEntries(params?: {
    account_id?: number;
    transaction_id?: number;
    year?: number;
    month?: number;
  }) {
    return coreApi.get<LedgerEntry[]>('/api/accounting/entries/', {
      params:
        params && (params.account_id || params.transaction_id || params.year || params.month)
          ? {
              ...(params.account_id ? { account_id: params.account_id } : {}),
              ...(params.transaction_id ? { transaction_id: params.transaction_id } : {}),
              ...(params.year ? { year: params.year } : {}),
              ...(params.month ? { month: params.month } : {}),
            }
          : undefined,
    });
  },
  getMonthlySummary(year: number) {
    return coreApi.get<MonthlyAccountingSummary>('/api/accounting/transactions/monthly-summary/', {
      params: { year },
    });
  },
  getBudgetSuggestions(year: number, lookbackYears = 2) {
    return coreApi.get<BudgetDerivedSuggestions>(
      '/api/accounting/transactions/budget-suggestions/',
      {
        params: { year, lookback_years: lookbackYears },
      },
    );
  },
  getDailyBalanceSeries(params?: {
    date_from?: string;
    date_to?: string;
    status?: 'posted' | 'draft';
    ownership_id?: number | 'null';
  }) {
    return coreApi.get<LedgerDailyBalanceSeries>(
      '/api/accounting/transactions/daily-balance-series/',
      {
        params: params
          ? {
              ...(params.date_from ? { date_from: params.date_from } : {}),
              ...(params.date_to ? { date_to: params.date_to } : {}),
              ...(params.status ? { status: params.status } : {}),
              ...(params.ownership_id != null ? { ownership_id: params.ownership_id } : {}),
            }
          : undefined,
      },
    );
  },
  getAccountBalances(params?: {
    year?: number;
    month?: number;
    account_type?: string;
    status?: string;
  }) {
    return coreApi.get<LedgerAccountBalanceSummary>('/api/accounting/accounts/balances/', {
      params:
        params && (params.year || params.month || params.account_type || params.status)
          ? {
              ...(params.year ? { year: params.year } : {}),
              ...(params.month ? { month: params.month } : {}),
              ...(params.account_type ? { account_type: params.account_type } : {}),
              ...(params.status ? { status: params.status } : {}),
            }
          : undefined,
    });
  },
};
