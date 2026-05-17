import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAnnualExpenseStore } from '../annualExpenseStore';

const mocks = vi.hoisted(() => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('@/lib/api', () => ({
  api: mocks.api,
}));

vi.mock('@/lib/errors', () => ({
  toApiErrorMessage: (error: unknown) => (error instanceof Error ? error.message : 'error'),
}));

describe('annual expense store (core)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads entries and totals from core api', async () => {
    mocks.api.get
      .mockResolvedValueOnce({
        data: [
          {
            id: 1,
            name: 'Alimentacion',
            category: 'consumption_expenses',
            subcategory: 'living_expenses',
            owner_name: 'Pablo',
            expense_type: 'recurrent',
            amount_annual: '5500.00',
            fiscal_year: 2026,
            currency: 'EUR',
            notes: '',
            created_at: '2026-02-20T00:00:00Z',
          },
        ],
      })
      .mockResolvedValueOnce({ data: { total_annual: '5500.00', currency_hint: 'mixed' } });

    const store = useAnnualExpenseStore('core');
    await store.loadAll(2026);

    expect(store.entries.value).toHaveLength(1);
    expect(store.totalAnnual.value).toBe(5500);
  });

  it('creates, updates and deletes entries via core api', async () => {
    mocks.api.post.mockResolvedValue({ data: { id: 1 } });
    mocks.api.patch.mockResolvedValue({ data: { id: 1 } });
    mocks.api.delete.mockResolvedValue({ data: {} });
    mocks.api.get.mockResolvedValue({ data: [] });

    const store = useAnnualExpenseStore('core');
    const createResult = await store.addEntry(
      {
        name: 'Alimentacion',
        category: 'consumption_expenses',
        subcategory: 'living_expenses',
        expenseType: 'recurrent',
        amountAnnual: '5500,00',
        fiscalYear: 2026,
        currency: 'EUR',
        notes: '',
      },
      2026,
    );

    expect(createResult.ok).toBe(true);
    expect(mocks.api.post).toHaveBeenCalledWith(
      '/api/budget/annual-expense/',
      expect.objectContaining({
        name: 'Alimentacion',
        category: 'consumption_expenses',
        subcategory: 'living_expenses',
        amount_annual: '5500.00',
        fiscal_year: 2026,
      }),
    );

    const updateResult = await store.updateEntry(
      1,
      {
        name: 'Alimentacion actualizada',
        category: 'consumption_expenses',
        subcategory: 'living_expenses',
        expenseType: 'recurrent',
        amountAnnual: '1.234,56',
        fiscalYear: 2026,
        currency: 'EUR',
        notes: 'update',
      },
      2026,
    );

    expect(updateResult.ok).toBe(true);
    expect(mocks.api.patch).toHaveBeenCalledWith(
      '/api/budget/annual-expense/1/',
      expect.objectContaining({
        name: 'Alimentacion actualizada',
        amount_annual: '1234.56',
      }),
    );

    await store.deleteEntry(10, 2026);
    expect(mocks.api.delete).toHaveBeenCalledWith('/api/budget/annual-expense/10/');
  });

  it('shares reactive state across consumers in the same scope', async () => {
    mocks.api.get
      .mockResolvedValueOnce({
        data: [
          {
            id: 1,
            name: 'Alimentacion',
            category: 'consumption_expenses',
            subcategory: 'living_expenses',
            owner_name: 'Pablo',
            expense_type: 'recurrent',
            amount_annual: '5500.00',
            fiscal_year: 2026,
            currency: 'EUR',
            notes: '',
            created_at: '2026-02-20T00:00:00Z',
          },
        ],
      })
      .mockResolvedValueOnce({ data: { total_annual: '5500.00', currency_hint: 'mixed' } });

    const firstConsumer = useAnnualExpenseStore('core');
    const secondConsumer = useAnnualExpenseStore('core');
    await firstConsumer.loadAll(2026);

    expect(secondConsumer.entries.value).toHaveLength(1);
    expect(secondConsumer.entries.value[0]?.name).toBe('Alimentacion');
  });
});
