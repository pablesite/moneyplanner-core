import { beforeEach, describe, expect, it, vi } from 'vitest';
import { coreNetWorthApi } from '@/domains/net-worth/api';

const mocks = vi.hoisted(() => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    put: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('@/lib/api', () => ({
  api: mocks.api,
}));

describe('net worth api (core)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('maps all net worth endpoints', async () => {
    await coreNetWorthApi.getSummary();
    await coreNetWorthApi.getAssets();
    await coreNetWorthApi.getLiabilities();
    await coreNetWorthApi.getSnapshots();
    await coreNetWorthApi.createSnapshotFromCurrent();
    await coreNetWorthApi.deleteSnapshot(3);
    await coreNetWorthApi.createAsset({ name: 'Cash' });
    await coreNetWorthApi.updateAsset(2, { name: 'Cash EUR' });
    await coreNetWorthApi.createLiability({ name: 'Loan' });
    await coreNetWorthApi.updateLiability(4, { name: 'Loan EUR' });
    await coreNetWorthApi.getSettings();
    await coreNetWorthApi.updateSettings({ base_currency: 'EUR' });

    expect(mocks.api.get).toHaveBeenCalledWith('/api/net-worth/summary/');
    expect(mocks.api.get).toHaveBeenCalledWith('/api/net-worth/assets/');
    expect(mocks.api.get).toHaveBeenCalledWith('/api/net-worth/liabilities/');
    expect(mocks.api.get).toHaveBeenCalledWith('/api/net-worth/snapshots/');
    expect(mocks.api.post).toHaveBeenCalledWith('/api/net-worth/snapshots/from-current/');
    expect(mocks.api.delete).toHaveBeenCalledWith('/api/net-worth/snapshots/3/');
    expect(mocks.api.post).toHaveBeenCalledWith('/api/net-worth/assets/', { name: 'Cash' });
    expect(mocks.api.patch).toHaveBeenCalledWith('/api/net-worth/assets/2/', { name: 'Cash EUR' });
    expect(mocks.api.post).toHaveBeenCalledWith('/api/net-worth/liabilities/', { name: 'Loan' });
    expect(mocks.api.patch).toHaveBeenCalledWith('/api/net-worth/liabilities/4/', {
      name: 'Loan EUR',
    });
    expect(mocks.api.get).toHaveBeenCalledWith('/api/auth/settings/');
    expect(mocks.api.put).toHaveBeenCalledWith('/api/auth/settings/', { base_currency: 'EUR' });
  });
});
