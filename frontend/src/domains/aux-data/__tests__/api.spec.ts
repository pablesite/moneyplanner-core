import { beforeEach, describe, expect, it, vi } from 'vitest';
import { auxDataApi, coreAuxDataApi } from '@/domains/aux-data/api';

const mocks = vi.hoisted(() => ({
  api: {
    get: vi.fn(),
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

  it('maps status endpoint through core api client', async () => {
    await coreAuxDataApi.getStatus();

    expect(mocks.api.get).toHaveBeenCalledWith('/api/core/market-data/status/');
  });
});
