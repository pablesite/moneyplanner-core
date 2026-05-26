import { describe, it, expect, beforeEach, vi } from 'vitest';
import { ref } from 'vue';
import { flushPromises } from '@vue/test-utils';

import { useAccountingExecutionData } from '@/views/budget/useAccountingExecutionData';
import { coreAccountingApi } from '@/domains/accounting';
import { coreNetWorthApi } from '@/domains/net-worth/api';

vi.mock('@/domains/accounting', () => ({
  coreAccountingApi: {
    getTransactions: vi.fn(),
    getMonthlySummary: vi.fn(),
  },
}));

vi.mock('@/domains/net-worth/api', () => ({
  coreNetWorthApi: {
    getAssets: vi.fn(),
  },
}));

vi.mock('@/domains/budget', () => ({
  toBudgetErrorMessage: (e: unknown) => String(e),
}));

const EMPTY_SUMMARY = { months: [] };
const EMPTY_TRANSACTIONS = { results: [], next_cursor: null };

function seedHappyPath() {
  vi.mocked(coreAccountingApi.getMonthlySummary).mockResolvedValue({
    data: EMPTY_SUMMARY,
  } as never);
  vi.mocked(coreAccountingApi.getTransactions).mockResolvedValue({
    data: EMPTY_TRANSACTIONS,
  } as never);
  vi.mocked(coreNetWorthApi.getAssets).mockResolvedValue({ data: [] } as never);
}

describe('useAccountingExecutionData', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads data and clears loading flag on success', async () => {
    seedHappyPath();
    const { accountingExecutionLoading, accountingPostedEntries, refreshAccountingExecutionData } =
      useAccountingExecutionData(ref(2024), ref('all'));

    const promise = refreshAccountingExecutionData();
    expect(accountingExecutionLoading.value).toBe(true);
    await promise;

    expect(accountingExecutionLoading.value).toBe(false);
    expect(accountingPostedEntries.value).toEqual([]);
  });

  it('maps asset subcategories onto posted entries', async () => {
    vi.mocked(coreAccountingApi.getMonthlySummary).mockResolvedValue({
      data: EMPTY_SUMMARY,
    } as never);
    vi.mocked(coreAccountingApi.getTransactions).mockResolvedValue({
      data: {
        results: [
          {
            id: 1,
            booking_date: '2024-03-15',
            member_tag: null,
            quick_entry_kind: null,
            entries: [
              { asset_id: 42, account_id: 1, side: 'debit', amount: '100.00', currency: 'EUR' },
            ],
          },
        ],
        next_cursor: null,
      },
    } as never);
    vi.mocked(coreNetWorthApi.getAssets).mockResolvedValue({
      data: [{ id: 42, subcategory: 'bank_account' }],
    } as never);

    const { accountingPostedEntries, refreshAccountingExecutionData } = useAccountingExecutionData(
      ref(2024),
      ref('all'),
    );

    await refreshAccountingExecutionData();

    expect(accountingPostedEntries.value[0].assetSubcategory).toBe('bank_account');
  });

  it('sets error and clears data on fetch failure', async () => {
    vi.mocked(coreAccountingApi.getMonthlySummary).mockRejectedValue(new Error('network error'));
    vi.mocked(coreAccountingApi.getTransactions).mockResolvedValue({
      data: EMPTY_TRANSACTIONS,
    } as never);
    vi.mocked(coreNetWorthApi.getAssets).mockResolvedValue({ data: [] } as never);

    const { accountingExecutionError, accountingMonthlySummary, refreshAccountingExecutionData } =
      useAccountingExecutionData(ref(2024), ref('all'));

    await refreshAccountingExecutionData();

    expect(accountingExecutionError.value).toBeTruthy();
    expect(accountingMonthlySummary.value).toBeNull();
  });

  it('discards stale results when a newer call supersedes in-flight request', async () => {
    let resolveFirst!: (v: unknown) => void;
    const firstCall = new Promise((r) => (resolveFirst = r));

    vi.mocked(coreAccountingApi.getMonthlySummary)
      .mockImplementationOnce(() => firstCall as never)
      .mockResolvedValue({ data: { months: [{ month: 5 }] } } as never);
    vi.mocked(coreAccountingApi.getTransactions).mockResolvedValue({
      data: EMPTY_TRANSACTIONS,
    } as never);
    vi.mocked(coreNetWorthApi.getAssets).mockResolvedValue({ data: [] } as never);

    const { accountingMonthlySummary, accountingExecutionLoading, refreshAccountingExecutionData } =
      useAccountingExecutionData(ref(2024), ref('all'));

    // First call blocks on getMonthlySummary.
    const first = refreshAccountingExecutionData();
    // Second call starts immediately and completes.
    const second = refreshAccountingExecutionData();
    await second;

    // Resolve the first call after the second has already finished.
    resolveFirst({ data: { months: [{ month: 99 }] } });
    await first;
    await flushPromises();

    // State must reflect the second (newer) call, not the first.
    expect(accountingMonthlySummary.value?.months[0]?.month).toBe(5);
    expect(accountingExecutionLoading.value).toBe(false);
  });

  it('discards stale error when a newer call supersedes a failing request', async () => {
    let rejectFirst!: (e: unknown) => void;
    const firstCall = new Promise((_, r) => (rejectFirst = r));

    vi.mocked(coreAccountingApi.getMonthlySummary)
      .mockImplementationOnce(() => firstCall as never)
      .mockResolvedValue({ data: EMPTY_SUMMARY } as never);
    vi.mocked(coreAccountingApi.getTransactions).mockResolvedValue({
      data: EMPTY_TRANSACTIONS,
    } as never);
    vi.mocked(coreNetWorthApi.getAssets).mockResolvedValue({ data: [] } as never);

    const { accountingExecutionError, refreshAccountingExecutionData } = useAccountingExecutionData(
      ref(2024),
      ref('all'),
    );

    const first = refreshAccountingExecutionData();
    const second = refreshAccountingExecutionData();
    await second;

    // Fail the first call after the second already succeeded.
    rejectFirst(new Error('stale error'));
    await first;
    await flushPromises();

    // The stale error must not overwrite the successful second call.
    expect(accountingExecutionError.value).toBeNull();
  });
});
