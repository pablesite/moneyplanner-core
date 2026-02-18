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

  it('maps refresh errors', async () => {
    mocks.coreNetWorthApi.getSummary.mockRejectedValue(new Error('boom'));
    const store = useNetWorthStore();

    await store.refreshAll();

    expect(store.error).toBe('mapped-error');
    expect(store.loading).toBe(false);
  });

  it('creates and updates assets and liabilities', async () => {
    mocks.coreNetWorthApi.createAsset.mockResolvedValue({});
    mocks.coreNetWorthApi.updateAsset.mockResolvedValue({});
    mocks.coreNetWorthApi.createLiability.mockResolvedValue({});
    mocks.coreNetWorthApi.updateLiability.mockResolvedValue({});
    mocks.coreNetWorthApi.getSummary.mockResolvedValue({ data: { base_currency: 'EUR' } });
    mocks.coreNetWorthApi.getAssets.mockResolvedValue({ data: [] });
    mocks.coreNetWorthApi.getLiabilities.mockResolvedValue({ data: [] });
    mocks.coreNetWorthApi.getSnapshots.mockResolvedValue({ data: [] });
    const store = useNetWorthStore();

    await store.createAsset({ name: 'Cash' });
    expect(mocks.coreNetWorthApi.createAsset).toHaveBeenCalledWith({ name: 'Cash' });

    await store.updateAsset(11, { name: 'Cash 2' });
    expect(mocks.coreNetWorthApi.updateAsset).toHaveBeenCalledWith(11, { name: 'Cash 2' });

    await store.archiveAsset(11);
    expect(mocks.coreNetWorthApi.updateAsset).toHaveBeenCalledWith(11, { is_active: false });

    await store.createLiability({ name: 'Debt' });
    expect(mocks.coreNetWorthApi.createLiability).toHaveBeenCalledWith({ name: 'Debt' });

    await store.updateLiability(22, { name: 'Debt 2' });
    expect(mocks.coreNetWorthApi.updateLiability).toHaveBeenCalledWith(22, { name: 'Debt 2' });

    await store.archiveLiability(22);
    expect(mocks.coreNetWorthApi.updateLiability).toHaveBeenCalledWith(22, { is_active: false });
  });

  it('deletes snapshots and maps delete errors', async () => {
    mocks.coreNetWorthApi.deleteSnapshot.mockResolvedValue({});
    mocks.coreNetWorthApi.getSummary.mockResolvedValue({ data: { base_currency: 'EUR' } });
    mocks.coreNetWorthApi.getAssets.mockResolvedValue({ data: [] });
    mocks.coreNetWorthApi.getLiabilities.mockResolvedValue({ data: [] });
    mocks.coreNetWorthApi.getSnapshots.mockResolvedValue({ data: [] });
    const store = useNetWorthStore();

    await store.deleteSnapshot(5);
    expect(mocks.coreNetWorthApi.deleteSnapshot).toHaveBeenCalledWith(5);
    expect(store.loading).toBe(false);

    mocks.coreNetWorthApi.deleteSnapshot.mockRejectedValueOnce(new Error('boom'));
    await store.deleteSnapshot(6);
    expect(store.error).toBe('mapped-error');
  });

  it('fetches settings and updates base currency', async () => {
    mocks.coreNetWorthApi.getSettings.mockResolvedValue({ data: { base_currency: 'USD' } });
    mocks.coreNetWorthApi.updateSettings.mockResolvedValue({ data: { base_currency: 'EUR' } });
    mocks.coreNetWorthApi.getSummary.mockResolvedValue({ data: { base_currency: 'EUR' } });
    mocks.coreNetWorthApi.getAssets.mockResolvedValue({ data: [] });
    mocks.coreNetWorthApi.getLiabilities.mockResolvedValue({ data: [] });
    mocks.coreNetWorthApi.getSnapshots.mockResolvedValue({ data: [] });
    const store = useNetWorthStore();

    await store.fetchSettings();
    expect(store.baseCurrency).toBe('USD');

    await store.updateBaseCurrency('EUR');
    expect(mocks.coreNetWorthApi.updateSettings).toHaveBeenCalledWith({ base_currency: 'EUR' });
    expect(store.baseCurrency).toBe('EUR');
  });

  it('maps settings and update errors', async () => {
    mocks.coreNetWorthApi.getSettings.mockRejectedValueOnce(new Error('boom'));
    mocks.coreNetWorthApi.updateSettings.mockRejectedValueOnce(new Error('boom'));
    const store = useNetWorthStore();

    await store.fetchSettings();
    expect(store.error).toBe('mapped-error');

    await store.updateBaseCurrency('USD');
    expect(store.error).toBe('mapped-error');
    expect(store.loading).toBe(false);
  });
});
