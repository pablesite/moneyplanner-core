import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useAccountingStore } from '../store';
import { coreAccountingApi } from '../api';

vi.mock('../api', () => ({
  coreAccountingApi: {
    getAccounts: vi.fn(),
    getTransactions: vi.fn(),
    getMonthlySummary: vi.fn(),
    getAccountBalances: vi.fn(),
    createAccount: vi.fn(),
    createTransaction: vi.fn(),
    createQuickEntry: vi.fn(),
    previewMoneyWizImport: vi.fn(),
    commitMoneyWizImport: vi.fn(),
    deleteImportedTransactions: vi.fn(),
  },
}));

describe('useAccountingStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('refreshes accounts and monthly summary together', async () => {
    vi.mocked(coreAccountingApi.getAccounts).mockResolvedValue({
      data: [{ id: 1, name: 'Banco', is_active: true }],
    } as never);
    vi.mocked(coreAccountingApi.getMonthlySummary).mockResolvedValue({
      data: { fiscal_year: 2026, months: [] },
    } as never);
    vi.mocked(coreAccountingApi.getAccountBalances).mockResolvedValue({
      data: {
        filters: { year: 2026, month: 3, account_type: 'asset', status: 'posted' },
        totals_by_account_type: { asset: '2100.00' },
        accounts: [],
      },
    } as never);

    const store = useAccountingStore();
    store.selectedYear = 2026;
    store.selectedMonth = 3;

    await store.refreshAll();

    expect(coreAccountingApi.getTransactions).not.toHaveBeenCalled();
    expect(coreAccountingApi.getAccountBalances).not.toHaveBeenCalled();
    expect(store.accounts).toHaveLength(1);
    expect(store.monthlySummary?.fiscal_year).toBe(2026);
    expect(store.accountBalancesSummary).toBeNull();
  });

  it('creates a transaction and reloads data', async () => {
    vi.mocked(coreAccountingApi.createTransaction).mockResolvedValue({ data: {} } as never);
    vi.mocked(coreAccountingApi.getAccounts).mockResolvedValue({ data: [] } as never);
    vi.mocked(coreAccountingApi.getMonthlySummary).mockResolvedValue({
      data: { fiscal_year: 2026, months: [] },
    } as never);
    vi.mocked(coreAccountingApi.getAccountBalances).mockResolvedValue({
      data: {
        filters: { year: 2026, month: 3, account_type: 'asset', status: 'posted' },
        totals_by_account_type: { asset: '0.00' },
        accounts: [],
      },
    } as never);

    const store = useAccountingStore();
    await store.createTransaction({
      booking_date: '2026-03-15',
      value_date: '2026-03-15',
      description: 'Nomina marzo',
      entries: [
        { account_id: 1, side: 'debit', amount: '100.00' },
        { account_id: 2, side: 'credit', amount: '100.00' },
      ],
    });

    expect(coreAccountingApi.createTransaction).toHaveBeenCalled();
    expect(coreAccountingApi.getTransactions).not.toHaveBeenCalled();
  });

  it('creates a quick entry and reloads balances', async () => {
    vi.mocked(coreAccountingApi.createQuickEntry).mockResolvedValue({ data: {} } as never);
    vi.mocked(coreAccountingApi.getAccounts).mockResolvedValue({ data: [] } as never);
    vi.mocked(coreAccountingApi.getMonthlySummary).mockResolvedValue({
      data: { fiscal_year: 2026, months: [] },
    } as never);
    vi.mocked(coreAccountingApi.getAccountBalances).mockResolvedValue({
      data: {
        filters: { year: 2026, month: 3, account_type: 'asset', status: 'posted' },
        totals_by_account_type: { asset: '500.00' },
        accounts: [{ account_id: 1, name: 'Banco', period_net_change: '500.00' }],
      },
    } as never);

    const store = useAccountingStore();
    await store.createQuickEntry({
      movement_type: 'income',
      booking_date: '2026-03-15',
      value_date: '2026-03-15',
      description: 'Nomina marzo',
      amount: '500.00',
      account_id: 1,
    });

    expect(coreAccountingApi.createQuickEntry).toHaveBeenCalled();
    expect(coreAccountingApi.getTransactions).not.toHaveBeenCalled();
  });

  it('stores MoneyWiz preview and commit results', async () => {
    vi.mocked(coreAccountingApi.previewMoneyWizImport).mockResolvedValue({
      data: {
        delimiter: ';',
        row_count: 2,
        valid_row_count: 2,
        error_row_count: 0,
        duplicate_row_count: 0,
        existing_row_count: 0,
        warnings: [],
        stats: {
          income: 1,
          expense: 1,
          transfer: 0,
          investment_purchase: 0,
          debt_payment: 0,
        },
        detected_accounts: [],
        rows: [],
      },
    } as never);
    vi.mocked(coreAccountingApi.commitMoneyWizImport).mockResolvedValue({
      data: {
        source: 'moneywiz',
        row_count: 2,
        created_count: 2,
        skipped_existing_count: 0,
        warning_count: 0,
        rows: [],
        preview: {
          delimiter: ';',
          row_count: 2,
          valid_row_count: 2,
          error_row_count: 0,
          duplicate_row_count: 0,
          existing_row_count: 0,
          warnings: [],
          stats: {
            income: 1,
            expense: 1,
            transfer: 0,
            investment_purchase: 0,
            debt_payment: 0,
          },
          detected_accounts: [],
          rows: [],
        },
        created_transaction_ids: [1, 2],
      },
    } as never);
    vi.mocked(coreAccountingApi.getAccounts).mockResolvedValue({ data: [] } as never);
    vi.mocked(coreAccountingApi.getMonthlySummary).mockResolvedValue({
      data: { fiscal_year: 2026, months: [] },
    } as never);
    vi.mocked(coreAccountingApi.getAccountBalances).mockResolvedValue({
      data: {
        filters: { year: 2026, month: 3, account_type: 'asset', status: 'posted' },
        totals_by_account_type: { asset: '0.00' },
        accounts: [],
      },
    } as never);

    const store = useAccountingStore();
    const file = new File(['csv'], 'moneywiz.csv', { type: 'text/csv' });

    await store.previewMoneyWizImport(file);
    await store.commitMoneyWizImport(file);

    expect(store.moneyWizImportPreview?.row_count).toBe(2);
    expect(store.moneyWizImportCommitResult?.created_count).toBe(2);
    expect(coreAccountingApi.commitMoneyWizImport).toHaveBeenCalledWith(file, {});
  });

  it('deletes imported transactions and refreshes data', async () => {
    vi.mocked(coreAccountingApi.deleteImportedTransactions).mockResolvedValue({
      data: { deleted_count: 3 },
    } as never);
    vi.mocked(coreAccountingApi.getAccounts).mockResolvedValue({ data: [] } as never);
    vi.mocked(coreAccountingApi.getTransactions).mockResolvedValue({ data: [] } as never);
    vi.mocked(coreAccountingApi.getMonthlySummary).mockResolvedValue({
      data: { fiscal_year: 2026, months: [] },
    } as never);

    const store = useAccountingStore();
    const result = await store.deleteImportedTransactions();

    expect(result.deleted_count).toBe(3);
    expect(coreAccountingApi.deleteImportedTransactions).toHaveBeenCalledTimes(1);
    expect(coreAccountingApi.getTransactions).not.toHaveBeenCalled();
  });
});
