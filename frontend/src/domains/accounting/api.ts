import { coreApi } from '@/lib/api';
import type {
  LedgerAccount,
  LedgerAccountWritePayload,
  LedgerEntry,
  LedgerTransaction,
  LedgerTransactionWritePayload,
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
  createQuickEntry(payload: QuickLedgerTransactionWritePayload) {
    return coreApi.post<LedgerTransaction>('/api/accounting/transactions/quick-entry/', payload);
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
};
