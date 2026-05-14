import { defineStore } from 'pinia';
import { coreAccountingApi } from '@/domains/accounting/api';
import type {
  LedgerAccount,
  LedgerAccountBalanceSummary,
  LedgerAccountWritePayload,
  LedgerTransactionWritePayload,
  MoneyWizImportCommitResult,
  MoneyWizImportPreview,
  PaginatedTransactionsResponse,
  MonthlyAccountingSummary,
  QuickLedgerTransactionWritePayload,
} from '@/domains/accounting/models';
import { toApiErrorMessage } from '@/lib/errors';

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

export const useAccountingStore = defineStore('accounting', {
  state: () => ({
    loading: false as boolean,
    accountCreationLoading: false as boolean,
    transactionCreationLoading: false as boolean,
    error: null as string | null,
    accounts: [] as LedgerAccount[],
    monthlySummary: null as MonthlyAccountingSummary | null,
    accountBalancesSummary: null as LedgerAccountBalanceSummary | null,
    moneyWizImportPreview: null as MoneyWizImportPreview | null,
    moneyWizImportCommitResult: null as MoneyWizImportCommitResult | null,
    selectedYear: new Date().getFullYear() as number,
    selectedMonth: (new Date().getMonth() + 1) as number,
  }),

  getters: {
    activeAccounts(state) {
      return state.accounts.filter((account) => account.is_active);
    },
  },

  actions: {
    async refreshAll() {
      this.loading = true;
      this.error = null;
      try {
        const [accountsRes, summaryRes] = await Promise.all([
          coreAccountingApi.getAccounts({ is_active: true }),
          coreAccountingApi.getMonthlySummary(this.selectedYear),
        ]);
        this.accounts = accountsRes.data;
        this.monthlySummary = summaryRes.data;
      } catch (error: unknown) {
        this.error = toApiErrorMessage(error);
      } finally {
        this.loading = false;
      }
    },

    async fetchTransactionsPage(
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
    ): Promise<PaginatedTransactionsResponse> {
      this.error = null;
      try {
        const response = await coreAccountingApi.getTransactions(params, options);
        return response.data;
      } catch (error: unknown) {
        if (isCanceledRequestError(error)) {
          throw error;
        }
        this.error = toApiErrorMessage(error);
        throw error;
      }
    },

    async setStatsYear(year: number) {
      this.selectedYear = year;
      this.error = null;
      try {
        const summaryRes = await coreAccountingApi.getMonthlySummary(year);
        this.monthlySummary = summaryRes.data;
      } catch (error: unknown) {
        this.error = toApiErrorMessage(error);
      }
    },

    async setPeriod(year: number, month: number) {
      this.selectedYear = year;
      this.selectedMonth = month;
      await this.refreshAll();
    },

    async createAccount(payload: LedgerAccountWritePayload) {
      this.accountCreationLoading = true;
      this.error = null;
      try {
        await coreAccountingApi.createAccount(payload);
        await this.refreshAll();
      } catch (error: unknown) {
        this.error = toApiErrorMessage(error);
        throw error;
      } finally {
        this.accountCreationLoading = false;
      }
    },

    async deleteAccount(accountId: number) {
      this.accountCreationLoading = true;
      this.error = null;
      try {
        await coreAccountingApi.deleteAccount(accountId);
        await this.refreshAll();
      } catch (error: unknown) {
        this.error = toApiErrorMessage(error);
        throw error;
      } finally {
        this.accountCreationLoading = false;
      }
    },

    async createTransaction(payload: LedgerTransactionWritePayload) {
      this.transactionCreationLoading = true;
      this.error = null;
      try {
        await coreAccountingApi.createTransaction(payload);
        await this.refreshAll();
      } catch (error: unknown) {
        this.error = toApiErrorMessage(error);
        throw error;
      } finally {
        this.transactionCreationLoading = false;
      }
    },

    async updateTransaction(transactionId: number, payload: LedgerTransactionWritePayload) {
      this.transactionCreationLoading = true;
      this.error = null;
      try {
        await coreAccountingApi.updateTransaction(transactionId, payload);
        await this.refreshAll();
      } catch (error: unknown) {
        this.error = toApiErrorMessage(error);
        throw error;
      } finally {
        this.transactionCreationLoading = false;
      }
    },

    async deleteTransaction(transactionId: number) {
      this.transactionCreationLoading = true;
      this.error = null;
      try {
        await coreAccountingApi.deleteTransaction(transactionId);
        await this.refreshAll();
      } catch (error: unknown) {
        this.error = toApiErrorMessage(error);
        throw error;
      } finally {
        this.transactionCreationLoading = false;
      }
    },

    async createQuickEntry(payload: QuickLedgerTransactionWritePayload) {
      this.transactionCreationLoading = true;
      this.error = null;
      try {
        await coreAccountingApi.createQuickEntry(payload);
        await this.refreshAll();
      } catch (error: unknown) {
        this.error = toApiErrorMessage(error);
        throw error;
      } finally {
        this.transactionCreationLoading = false;
      }
    },

    async deleteImportedTransactions() {
      this.transactionCreationLoading = true;
      this.error = null;
      try {
        const response = await coreAccountingApi.deleteImportedTransactions();
        await this.refreshAll();
        return response.data;
      } catch (error: unknown) {
        this.error = toApiErrorMessage(error);
        throw error;
      } finally {
        this.transactionCreationLoading = false;
      }
    },

    async previewMoneyWizImport(file: File) {
      this.transactionCreationLoading = true;
      this.error = null;
      try {
        const response = await coreAccountingApi.previewMoneyWizImport(file);
        this.moneyWizImportPreview = response.data;
        return response.data;
      } catch (error: unknown) {
        this.error = toApiErrorMessage(error);
        throw error;
      } finally {
        this.transactionCreationLoading = false;
      }
    },

    async commitMoneyWizImport(file: File, options: Record<string, unknown> = {}) {
      this.transactionCreationLoading = true;
      this.error = null;
      try {
        const response = await coreAccountingApi.commitMoneyWizImport(file, options);
        this.moneyWizImportCommitResult = response.data;
        await this.refreshAll();
        return response.data;
      } catch (error: unknown) {
        this.error = toApiErrorMessage(error);
        throw error;
      } finally {
        this.transactionCreationLoading = false;
      }
    },
  },
});
