import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useNetWorthStore } from '@/domains/net-worth/store';

const mocks = vi.hoisted(() => ({
  coreNetWorthApi: {
    getSummary: vi.fn(),
    getAssets: vi.fn(),
    getLiabilities: vi.fn(),
    getSnapshots: vi.fn(),
    createSnapshotFromCurrent: vi.fn(),
    deleteSnapshot: vi.fn(),
    createAsset: vi.fn(),
    updateAsset: vi.fn(),
    createLiability: vi.fn(),
    updateLiability: vi.fn(),
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
  },
  buildByCategoryChart: vi.fn(() => ({ labels: [], assets: [], liabilities: [] })),
  toApiErrorMessage: vi.fn(() => 'mapped-error'),
}));

vi.mock('@/domains/net-worth/api', () => ({
  coreNetWorthApi: mocks.coreNetWorthApi,
}));

vi.mock('@/domains/net-worth/charts', () => ({
  buildByCategoryChart: mocks.buildByCategoryChart,
}));

vi.mock('@/lib/errors', () => ({
  toApiErrorMessage: mocks.toApiErrorMessage,
}));

describe('net worth store (core)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('refreshes summary datasets', async () => {
    mocks.coreNetWorthApi.getSummary.mockResolvedValue({ data: { base_currency: 'EUR' } });
    mocks.coreNetWorthApi.getAssets.mockResolvedValue({ data: [{ id: 1 }] });
    mocks.coreNetWorthApi.getLiabilities.mockResolvedValue({ data: [{ id: 2 }] });
    mocks.coreNetWorthApi.getSnapshots.mockResolvedValue({ data: [{ id: 3 }] });
    const store = useNetWorthStore();

    await store.refreshAll();

    expect(store.baseCurrency).toBe('EUR');
    expect(store.assets).toEqual([{ id: 1 }]);
    expect(store.liabilities).toEqual([{ id: 2 }]);
    expect(store.snapshots).toEqual([{ id: 3 }]);
    expect(store.loading).toBe(false);
  });

  it('handles snapshot creation errors and resets loading', async () => {
    mocks.coreNetWorthApi.createSnapshotFromCurrent.mockRejectedValue(new Error('boom'));
    const store = useNetWorthStore();

    await store.createTodaySnapshot();

    expect(store.error).toBe('mapped-error');
    expect(store.loading).toBe(false);
  });
});
