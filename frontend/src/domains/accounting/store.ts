import { defineStore } from 'pinia';
import { coreAccountingApi } from '@/domains/accounting/api';
import type {
  LedgerAccount,
  LedgerAccountWritePayload,
  LedgerTransaction,
  LedgerTransactionWritePayload,
  MonthlyAccountingSummary,
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
        const [accountsRes, transactionsRes, summaryRes] = await Promise.all([
          coreAccountingApi.getAccounts({ is_active: true }),
          coreAccountingApi.getTransactions({
            year: this.selectedYear,
            month: this.selectedMonth,
          }),
          coreAccountingApi.getMonthlySummary(this.selectedYear),
        ]);
        this.accounts = accountsRes.data;
        this.transactions = transactionsRes.data;
        this.monthlySummary = summaryRes.data;
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
  },
});
