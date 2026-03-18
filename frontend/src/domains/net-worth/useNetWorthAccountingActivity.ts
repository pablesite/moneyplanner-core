import { computed, ref, type ComputedRef } from 'vue';
import { coreAccountingApi, type LedgerTransaction } from '@/domains/accounting';
import { toApiErrorMessage } from '@/lib/errors';

type BasePositionRow = {
  id: number;
  type: 'asset' | 'liability';
  category?: string;
};

type SourceItem = {
  tracking_mode?: string | null;
  accounting_integration_state?: string | null;
  accounting_account_id?: number | null;
};

export type AccountingActivityRow = {
  id: string;
  date: string;
  description: string;
  sideLabel: string;
  amount: number;
  currency: string;
  counterpartLabel: string;
  note: string;
};

function summarizeCounterparts(
  transaction: LedgerTransaction,
  selectedAccountId: number,
  selectedEntryId: number,
): string {
  const counterparts = transaction.entries.filter(
    (entry) => entry.account_id !== selectedAccountId && entry.id !== selectedEntryId,
  );
  if (!counterparts.length) return 'Sin contrapartida visible';
  const names = Array.from(
    new Set(counterparts.map((entry) => entry.account_name).filter(Boolean)),
  );
  if (names.length <= 2) return names.join(' + ');
  return `${names.slice(0, 2).join(' + ')} +${names.length - 2}`;
}

export function useNetWorthAccountingActivity<TRow extends BasePositionRow>(params: {
  selectedPositionSource: ComputedRef<SourceItem | null>;
  sourceItemForRow: (row: TRow) => SourceItem | null;
  toNumber: (raw: unknown) => number;
}) {
  const accountingActivityLoading = ref(false);
  const accountingActivityError = ref<string | null>(null);
  const accountingActivityRows = ref<AccountingActivityRow[]>([]);
  const accountingActivityYear = ref(new Date().getFullYear());

  const selectedPositionUsesAccounting = computed(
    () => params.selectedPositionSource.value?.tracking_mode === 'accounting',
  );
  const selectedPositionAccountingIntegrationState = computed(
    () => params.selectedPositionSource.value?.accounting_integration_state ?? null,
  );
  const selectedPositionAccountingAccountId = computed(
    () => params.selectedPositionSource.value?.accounting_account_id ?? null,
  );
  const showAccountingActivitySetupGap = computed(
    () =>
      selectedPositionUsesAccounting.value &&
      selectedPositionAccountingIntegrationState.value !== 'needs_review' &&
      selectedPositionAccountingAccountId.value == null,
  );
  const showAccountingActivityNeedsReview = computed(
    () =>
      selectedPositionUsesAccounting.value &&
      selectedPositionAccountingIntegrationState.value === 'needs_review',
  );
  const showAccountingActivityBlock = computed(() => selectedPositionUsesAccounting.value);

  function resetAccountingActivity(): void {
    accountingActivityLoading.value = false;
    accountingActivityError.value = null;
    accountingActivityRows.value = [];
    accountingActivityYear.value = new Date().getFullYear();
  }

  async function loadAccountingActivity(row: TRow): Promise<void> {
    const source = params.sourceItemForRow(row);
    if (!source || source.tracking_mode !== 'accounting') {
      resetAccountingActivity();
      return;
    }

    accountingActivityYear.value = new Date().getFullYear();
    if (source.accounting_integration_state === 'needs_review' || !source.accounting_account_id) {
      accountingActivityError.value = null;
      accountingActivityRows.value = [];
      return;
    }

    accountingActivityLoading.value = true;
    accountingActivityError.value = null;
    try {
      const response = await coreAccountingApi.getTransactions({
        year: accountingActivityYear.value,
      });
      const relevantRows = response.data
        .flatMap((transaction) =>
          transaction.entries
            .filter((entry) => entry.account_id === source.accounting_account_id)
            .map((entry) => ({
              id: `accounting-${transaction.id}-${entry.id}`,
              date: transaction.booking_date,
              description: transaction.description,
              sideLabel: entry.side === 'debit' ? 'Debe' : 'Haber',
              amount: params.toNumber(entry.amount),
              currency: entry.currency,
              counterpartLabel: summarizeCounterparts(
                transaction,
                source.accounting_account_id ?? 0,
                entry.id,
              ),
              note: entry.notes || transaction.notes || '',
            })),
        )
        .sort((a, b) => b.date.localeCompare(a.date))
        .slice(0, 6);
      accountingActivityRows.value = relevantRows;
    } catch (error: unknown) {
      accountingActivityError.value = toApiErrorMessage(error);
      accountingActivityRows.value = [];
    } finally {
      accountingActivityLoading.value = false;
    }
  }

  return {
    accountingActivityLoading,
    accountingActivityError,
    accountingActivityRows,
    accountingActivityYear,
    showAccountingActivitySetupGap,
    showAccountingActivityNeedsReview,
    showAccountingActivityBlock,
    resetAccountingActivity,
    loadAccountingActivity,
  };
}
