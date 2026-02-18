import { describe, expect, it, vi, beforeEach } from 'vitest';
import { useAuxData } from '@/domains/aux-data/composables';

const mocks = vi.hoisted(() => ({
  getFxRates: vi.fn(),
  getInflation: vi.fn(),
  createFxRate: vi.fn(),
  deleteFxRate: vi.fn(),
  createInflation: vi.fn(),
  deleteInflation: vi.fn(),
  toApiErrorMessage: vi.fn(() => 'mapped-error'),
}));

vi.mock('@/domains/aux-data/api', () => ({
  auxDataApi: {
    getFxRates: mocks.getFxRates,
    getInflation: mocks.getInflation,
    createFxRate: mocks.createFxRate,
    deleteFxRate: mocks.deleteFxRate,
    createInflation: mocks.createInflation,
    deleteInflation: mocks.deleteInflation,
  },
}));

vi.mock('@/lib/errors', () => ({
  toApiErrorMessage: mocks.toApiErrorMessage,
}));

describe('useAuxData (core)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads FX and inflation data', async () => {
    mocks.getFxRates.mockResolvedValueOnce({ data: [{ id: 1 }] });
    mocks.getInflation.mockResolvedValueOnce({ data: [{ id: 2 }] });
    const state = useAuxData();

    await state.loadAll();

    expect(state.fxRates.value).toEqual([{ id: 1 }]);
    expect(state.inflation.value).toEqual([{ id: 2 }]);
    expect(state.loading.value).toBe(false);
    expect(state.error.value).toBeNull();
  });

  it('maps API errors and formats helper outputs', async () => {
    mocks.getFxRates.mockRejectedValueOnce(new Error('boom'));
    mocks.getInflation.mockResolvedValueOnce({ data: [] });
    const state = useAuxData();

    await state.loadAll();

    expect(state.error.value).toBe('mapped-error');
    expect(state.formatFxRate('1,2345', 'USD', 'EUR')).toBe('1.2345');
    expect(state.formatInflationIndex('100,55')).toBe('100.5');
  });
});
