import { beforeEach, describe, expect, it, vi } from 'vitest';
import { useAnnualIncomeStore } from '../annualIncomeStore';

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

describe('annual income store (core)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads entries and totals from core api', async () => {
    mocks.api.get
      .mockResolvedValueOnce({
        data: [
          {
            id: 1,
            name: 'CTN',
            category: 'salary',
            subcategory: 'employee_salary',
            owner_name: 'Pablo',
            income_type: 'recurrent',
            amount_annual: '32460.00',
            fiscal_year: 2026,
            currency: 'EUR',
            notes: '',
            created_at: '2026-02-20T00:00:00Z',
          },
        ],
      })
      .mockResolvedValueOnce({ data: { total_annual: '32460.00', currency_hint: 'mixed' } });

    const store = useAnnualIncomeStore('core');
    await store.loadAll(2026);

    expect(store.entries.value).toHaveLength(1);
    expect(store.totalAnnual.value).toBe(32460);
  });

  it('creates, updates and deletes entries via core api', async () => {
    mocks.api.post.mockResolvedValue({ data: { id: 1 } });
    mocks.api.patch.mockResolvedValue({ data: { id: 1 } });
    mocks.api.delete.mockResolvedValue({ data: {} });
    mocks.api.get.mockResolvedValue({ data: [] });

    const store = useAnnualIncomeStore('core');
    const createResult = await store.addEntry(
      {
        name: 'CTN',
        category: 'salary',
        subcategory: 'employee_salary',
        incomeType: 'recurrent',
        amountAnnual: '32460,00',
        fiscalYear: 2026,
        currency: 'EUR',
        notes: '',
      },
      2026,
    );

    expect(createResult.ok).toBe(true);
    expect(mocks.api.post).toHaveBeenCalledWith(
      '/api/budget/annual-income/',
      expect.objectContaining({
        name: 'CTN',
        category: 'salary',
        subcategory: 'employee_salary',
        amount_annual: '32460.00',
        fiscal_year: 2026,
      }),
    );

    const updateResult = await store.updateEntry(
      1,
      {
        name: 'CTN actualizado',
        category: 'salary',
        subcategory: 'employee_salary',
        incomeType: 'recurrent',
        amountAnnual: '33000,00',
        fiscalYear: 2026,
        currency: 'EUR',
        notes: 'update',
      },
      2026,
    );

    expect(updateResult.ok).toBe(true);
    expect(mocks.api.patch).toHaveBeenCalledWith(
      '/api/budget/annual-income/1/',
      expect.objectContaining({
        name: 'CTN actualizado',
        category: 'salary',
        subcategory: 'employee_salary',
        amount_annual: '33000.00',
        fiscal_year: 2026,
      }),
    );

    await store.deleteEntry(10, 2026);
    expect(mocks.api.delete).toHaveBeenCalledWith('/api/budget/annual-income/10/');
  });

  it('rejects invalid subcategory before calling api', async () => {
    const store = useAnnualIncomeStore('core');
    const result = await store.addEntry(
      {
        name: 'Linea invalida',
        category: 'salary',
        subcategory: 'inheritance',
        incomeType: 'one_off',
        amountAnnual: '1000',
        fiscalYear: 2026,
        currency: 'EUR',
        notes: '',
      },
      2026,
    );

    expect(result.ok).toBe(false);
    expect(mocks.api.post).not.toHaveBeenCalled();
  });
});
