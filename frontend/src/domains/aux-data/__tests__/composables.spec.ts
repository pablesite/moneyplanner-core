import { describe, expect, it, vi, beforeEach } from 'vitest';
import { useAuxData } from '@/domains/aux-data/composables';

const mocks = vi.hoisted(() => ({
  getStatus: vi.fn(),
  toApiErrorMessage: vi.fn(() => 'mapped-error'),
}));

vi.mock('@/domains/aux-data/api', () => ({
  auxDataApi: {
    getStatus: mocks.getStatus,
  },
}));

vi.mock('@/lib/errors', () => ({
  toApiErrorMessage: mocks.toApiErrorMessage,
}));

describe('useAuxData (core)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('loads market data status', async () => {
    mocks.getStatus.mockResolvedValueOnce({
      data: {
        supported_inflation_regions: [{ code: 'ES', label: 'Espana' }],
        datasets: {
          fx: { states: [{ scope: 'USD->EUR' }], latest_rows: [{ id: 1 }] },
          inflation: { states: [{ scope: 'ES' }], latest_rows: [{ id: 2 }] },
        },
      },
    });
    const state = useAuxData();

    await state.loadAll();

    expect(state.fxRates.value).toEqual([{ id: 1 }]);
    expect(state.inflation.value).toEqual([{ id: 2 }]);
    expect(state.fxStates.value).toEqual([{ scope: 'USD->EUR' }]);
    expect(state.supportedInflationRegions.value).toEqual([{ code: 'ES', label: 'Espana' }]);
    expect(state.loading.value).toBe(false);
    expect(state.error.value).toBeNull();
  });

  it('maps API errors and formats helper outputs', async () => {
    mocks.getStatus.mockRejectedValueOnce(new Error('boom'));
    const state = useAuxData();

    await state.loadAll();

    expect(state.error.value).toBe('mapped-error');
    expect(state.formatFxRate('1,2345', 'USD', 'EUR')).toBe('1.2345');
    expect(state.formatInflationIndex('100,55')).toBe('100.550');
  });
});
