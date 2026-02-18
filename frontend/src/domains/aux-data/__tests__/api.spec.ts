import { beforeEach, describe, expect, it, vi } from 'vitest';
import { auxDataApi, coreAuxDataApi } from '@/domains/aux-data/api';

const mocks = vi.hoisted(() => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('@/lib/api', () => ({
  api: mocks.api,
}));

describe('aux-data api (core)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exports core adapter as active api', () => {
    expect(auxDataApi).toBe(coreAuxDataApi);
  });

  it('maps all endpoints through core api client', async () => {
    const payloadFx = {
      rate_date: '2026-02-18',
      from_currency: 'USD',
      to_currency: 'EUR',
      rate: '0.95',
    };
    const payloadInflation = { region: 'ES', period: '2026-02-01', index: '101.2' };

    await coreAuxDataApi.getFxRates();
    await coreAuxDataApi.getInflation();
    await coreAuxDataApi.createFxRate(payloadFx);
    await coreAuxDataApi.deleteFxRate(3);
    await coreAuxDataApi.createInflation(payloadInflation);
    await coreAuxDataApi.deleteInflation(4);

    expect(mocks.api.get).toHaveBeenCalledWith('/api/core/fx-rates/');
    expect(mocks.api.get).toHaveBeenCalledWith('/api/core/inflation/');
    expect(mocks.api.post).toHaveBeenCalledWith('/api/core/fx-rates/', payloadFx);
    expect(mocks.api.delete).toHaveBeenCalledWith('/api/core/fx-rates/3/');
    expect(mocks.api.post).toHaveBeenCalledWith('/api/core/inflation/', payloadInflation);
    expect(mocks.api.delete).toHaveBeenCalledWith('/api/core/inflation/4/');
  });
});
