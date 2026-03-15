import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useAccountingStore } from '../store';
import { coreAccountingApi } from '../api';

vi.mock('../api', () => ({
  coreAccountingApi: {
    getAccounts: vi.fn(),
    getTransactions: vi.fn(),
    getMonthlySummary: vi.fn(),
    createAccount: vi.fn(),
    createTransaction: vi.fn(),
  },
}));

describe('useAccountingStore', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('refreshes accounts, transactions and monthly summary together', async () => {
    vi.mocked(coreAccountingApi.getAccounts).mockResolvedValue({
      data: [{ id: 1, name: 'Banco', is_active: true }],
    } as never);
    vi.mocked(coreAccountingApi.getTransactions).mockResolvedValue({
      data: [{ id: 2, description: 'Nomina' }],
    } as never);
    vi.mocked(coreAccountingApi.getMonthlySummary).mockResolvedValue({
      data: { fiscal_year: 2026, months: [] },
    } as never);

    const store = useAccountingStore();
    store.selectedYear = 2026;
    store.selectedMonth = 3;

    await store.refreshAll();

    expect(coreAccountingApi.getTransactions).toHaveBeenCalledWith({ year: 2026, month: 3 });
    expect(store.accounts).toHaveLength(1);
    expect(store.transactions).toHaveLength(1);
    expect(store.monthlySummary?.fiscal_year).toBe(2026);
  });

  it('creates a transaction and reloads data', async () => {
    vi.mocked(coreAccountingApi.createTransaction).mockResolvedValue({ data: {} } as never);
    vi.mocked(coreAccountingApi.getAccounts).mockResolvedValue({ data: [] } as never);
    vi.mocked(coreAccountingApi.getTransactions).mockResolvedValue({ data: [] } as never);
    vi.mocked(coreAccountingApi.getMonthlySummary).mockResolvedValue({
      data: { fiscal_year: 2026, months: [] },
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
    expect(coreAccountingApi.getTransactions).toHaveBeenCalled();
  });
});
