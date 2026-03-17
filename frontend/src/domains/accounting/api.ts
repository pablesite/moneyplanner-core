import { coreApi } from '@/lib/api';
import type {
  BudgetDerivedSuggestions,
  LedgerAccount,
  LedgerAccountBalanceSummary,
  LedgerAccountWritePayload,
  LedgerEntry,
  LedgerTransaction,
  LedgerTransactionWritePayload,
  MoneyWizImportCommit,
  MoneyWizImportPreview,
  MonthlyAccountingSummary,
  QuickLedgerTransactionWritePayload,
} from '@/domains/accounting/models';

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
  getTransactions(params?: { year?: number; month?: number; status?: string }) {
    return coreApi.get<LedgerTransaction[]>('/api/accounting/transactions/', {
      params:
        params && (params.year || params.month || params.status)
          ? {
              ...(params.year ? { year: params.year } : {}),
              ...(params.month ? { month: params.month } : {}),
              ...(params.status ? { status: params.status } : {}),
            }
          : undefined,
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
  previewMoneyWizImport(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    return coreApi.post<MoneyWizImportPreview>(
      '/api/accounting/transactions/import-moneywiz/preview/',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
      },
    );
  },
  commitMoneyWizImport(file: File) {
    const formData = new FormData();
    formData.append('file', file);
    return coreApi.post<MoneyWizImportCommit>(
      '/api/accounting/transactions/import-moneywiz/commit/',
      formData,
      {
        headers: { 'Content-Type': 'multipart/form-data' },
      },
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
