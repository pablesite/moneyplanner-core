import { defineStore } from 'pinia';
import { coreAccountingApi } from '@/domains/accounting/api';
import type {
  LedgerAccount,
  LedgerAccountBalanceSummary,
  LedgerAccountWritePayload,
  LedgerTransaction,
  LedgerTransactionWritePayload,
  MonthlyAccountingSummary,
  QuickLedgerTransactionWritePayload,
} from '@/domains/accounting/models';
import { toApiErrorMessage } from '@/lib/errors';

export const useAccountingStore = defineStore('accounting', {
  state: () => ({
    loading: false as boolean,
    accountCreationLoading: false as boolean,
    transactionCreationLoading: false as boolean,
    error: null as string | null,
    accounts: [] as LedgerAccount[],
    transactions: [] as LedgerTransaction[],
    monthlySummary: null as MonthlyAccountingSummary | null,
    accountBalancesSummary: null as LedgerAccountBalanceSummary | null,
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
        const [accountsRes, transactionsRes, summaryRes, balancesRes] = await Promise.all([
          coreAccountingApi.getAccounts({ is_active: true }),
          coreAccountingApi.getTransactions({
            year: this.selectedYear,
            month: this.selectedMonth,
          }),
          coreAccountingApi.getMonthlySummary(this.selectedYear),
          coreAccountingApi.getAccountBalances({
            year: this.selectedYear,
            month: this.selectedMonth,
            account_type: 'asset',
            status: 'posted',
          }),
        ]);
        this.accounts = accountsRes.data;
        this.transactions = transactionsRes.data;
        this.monthlySummary = summaryRes.data;
        this.accountBalancesSummary = balancesRes.data;
      } catch (error: unknown) {
        this.error = toApiErrorMessage(error);
      } finally {
        this.loading = false;
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
  },
});
