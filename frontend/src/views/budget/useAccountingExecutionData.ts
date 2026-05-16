import { computed, ref, type Ref } from 'vue';
import {
  coreAccountingApi,
  type LedgerTransaction,
  type MonthlyAccountingSummary,
} from '@/domains/accounting';
import { coreNetWorthApi } from '@/domains/net-worth/api';
import { toBudgetErrorMessage } from '@/domains/budget';
import {
  type AccountingPostedEntry,
  type AccountingExecutionBucketAccumulator,
  bookingMonthFromDate,
  buildDebtPaymentExpenseTargetByTransactionId,
  collectAccountingExecutionEntry,
} from '@/views/budget/budgetDashboardUtils';

export function useAccountingExecutionData(fiscalYear: Ref<number>, ownershipFilter: Ref<string>) {
  const accountingExecutionLoading = ref(false);
  const accountingExecutionError = ref<string | null>(null);
  const accountingMonthlySummary = ref<MonthlyAccountingSummary | null>(null);
  const accountingPostedEntries = ref<AccountingPostedEntry[]>([]);

  const accountingSummaryByMonth = computed(() => {
    const map = new Map<number, MonthlyAccountingSummary['months'][number]>();
    for (const row of accountingMonthlySummary.value?.months ?? []) {
      map.set(row.month, row);
    }
    return map;
  });

  const accountingExecutionBuckets = computed(() => {
    const buckets: AccountingExecutionBucketAccumulator = {
      incomeCategorizedByMonthTaxonomy: new Map<string, number>(),
      expenseCategorizedByMonthTaxonomy: new Map<string, number>(),
      depositRotationIncomeByMonth: new Map<number, number>(),
      depositRotationExpenseByMonth: new Map<number, number>(),
      incomeUnclassifiedTotal: 0,
      expenseUnclassifiedTotal: 0,
    };
    const debtPaymentExpenseTargetByTransactionId = buildDebtPaymentExpenseTargetByTransactionId(
      accountingPostedEntries.value,
    );
    for (const entry of accountingPostedEntries.value) {
      collectAccountingExecutionEntry(
        entry,
        debtPaymentExpenseTargetByTransactionId,
        buckets,
        ownershipFilter.value,
      );
    }
    return buckets;
  });

  async function refreshAccountingExecutionData(): Promise<void> {
    accountingExecutionLoading.value = true;
    accountingExecutionError.value = null;
    try {
      const fetchAllTransactions = async (params: { year: number; status?: string }) => {
        const allResults: typeof accountingPostedEntries.value = [];
        let cursor: string | undefined;
        do {
          const response = await coreAccountingApi.getTransactions({
            ...params,
            page_size: 200,
            cursor,
          });
          allResults.push(
            ...(response.data.results ?? []).flatMap((transaction: LedgerTransaction) => {
              const bookingMonth = bookingMonthFromDate(transaction.booking_date);
              return transaction.entries.map((entry) => ({
                ...entry,
                bookingMonth,
                transactionId: transaction.id,
                transactionMemberTag: transaction.member_tag ?? '',
                transactionQuickEntryKind: transaction.quick_entry_kind ?? '',
                assetSubcategory: '',
              }));
            }),
          );
          cursor = response.data.next_cursor ?? undefined;
        } while (cursor);
        return allResults;
      };
      const [summaryResponse, transactionsResponse, assetsResponse] = await Promise.all([
        coreAccountingApi.getMonthlySummary(fiscalYear.value),
        fetchAllTransactions({ year: fiscalYear.value, status: 'posted' }),
        coreNetWorthApi.getAssets(),
      ]);
      const assetSubcategoryById = new Map<number, string>();
      for (const asset of assetsResponse.data ?? []) {
        assetSubcategoryById.set(asset.id, asset.subcategory ?? '');
      }
      accountingMonthlySummary.value = summaryResponse.data ?? null;
      accountingPostedEntries.value = transactionsResponse.map((entry) => ({
        ...entry,
        assetSubcategory:
          entry.asset_id != null ? (assetSubcategoryById.get(entry.asset_id) ?? '') : '',
      }));
    } catch (e: unknown) {
      accountingExecutionError.value = toBudgetErrorMessage(e);
      accountingMonthlySummary.value = null;
      accountingPostedEntries.value = [];
    } finally {
      accountingExecutionLoading.value = false;
    }
  }

  return {
    accountingExecutionLoading,
    accountingExecutionError,
    accountingMonthlySummary,
    accountingPostedEntries,
    accountingSummaryByMonth,
    accountingExecutionBuckets,
    refreshAccountingExecutionData,
  };
}
