import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { useNetWorthStore } from '@/domains/net-worth/store';

const mocks = vi.hoisted(() => ({
  coreNetWorthApi: {
    getSummary: vi.fn(),
    getAssets: vi.fn(),
    getLiabilities: vi.fn(),
    getTimeline: vi.fn(),
    getAssetTimeline: vi.fn(),
    getLiabilityTimeline: vi.fn(),
    getAssetValuations: vi.fn(),
    getLiabilityValuations: vi.fn(),
    getInvestmentEvents: vi.fn(),
    getLiquidityEvents: vi.fn(),
    getLiabilityEvents: vi.fn(),
    createAsset: vi.fn(),
    updateAsset: vi.fn(),
    deleteAsset: vi.fn(),
    createLiability: vi.fn(),
    updateLiability: vi.fn(),
    deleteLiability: vi.fn(),
    getSettings: vi.fn(),
    updateSettings: vi.fn(),
  },
  premiumOwnershipApi: {
    getOwnerships: vi.fn(),
    getOwnershipLinks: vi.fn(),
    syncOwnershipLink: vi.fn(),
  },
  buildByCategoryChart: vi.fn(() => ({ labels: [], assets: [], liabilities: [] })),
  toApiErrorMessage: vi.fn(() => 'mapped-error'),
}));

vi.mock('@/domains/net-worth/api', () => ({
  coreNetWorthApi: mocks.coreNetWorthApi,
  premiumOwnershipApi: mocks.premiumOwnershipApi,
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
    mocks.coreNetWorthApi.getSettings.mockResolvedValue({
      data: { base_currency: 'EUR', inflation_region: 'ES' },
    });
    mocks.premiumOwnershipApi.getOwnerships.mockResolvedValue({ data: [] });
    mocks.premiumOwnershipApi.getOwnershipLinks.mockResolvedValue({ data: [] });
  });

  it('refreshes summary datasets', async () => {
    mocks.coreNetWorthApi.getSummary.mockResolvedValue({ data: { base_currency: 'EUR' } });
    mocks.coreNetWorthApi.getAssets.mockResolvedValue({ data: [{ id: 1 }] });
    mocks.coreNetWorthApi.getLiabilities.mockResolvedValue({ data: [{ id: 2 }] });
    mocks.coreNetWorthApi.getTimeline.mockResolvedValue({
      data: { rows: [], base_currency: 'EUR' },
    });
    const store = useNetWorthStore();

    await store.refreshAll();

    expect(store.baseCurrency).toBe('EUR');
    expect(store.assets).toEqual([{ id: 1, ownership_ref: null }]);
    expect(store.liabilities).toEqual([{ id: 2, ownership_ref: null }]);
    expect(store.loading).toBe(false);
    // Timeline loads independently (fire-and-forget) — flush microtasks
    await vi.waitFor(() => expect(store.timeline).toEqual({ rows: [], base_currency: 'EUR' }));
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
    mocks.coreNetWorthApi.getTimeline.mockResolvedValue({ data: { rows: [] } });
    const store = useNetWorthStore();

    await store.createAsset({ name: 'Cash' });
    expect(mocks.coreNetWorthApi.createAsset).toHaveBeenCalledWith({ name: 'Cash' });

    await store.updateAsset(11, { name: 'Cash 2' });
    expect(mocks.coreNetWorthApi.updateAsset).toHaveBeenCalledWith(11, { name: 'Cash 2' });

    await store.archiveAsset(11);
    expect(mocks.coreNetWorthApi.updateAsset).toHaveBeenCalledWith(11, { is_active: false });
    await store.deleteAsset(11);
    expect(mocks.coreNetWorthApi.deleteAsset).toHaveBeenCalledWith(11);

    await store.createLiability({ name: 'Debt' });
    expect(mocks.coreNetWorthApi.createLiability).toHaveBeenCalledWith({ name: 'Debt' });

    await store.updateLiability(22, { name: 'Debt 2' });
    expect(mocks.coreNetWorthApi.updateLiability).toHaveBeenCalledWith(22, { name: 'Debt 2' });

    await store.archiveLiability(22);
    expect(mocks.coreNetWorthApi.updateLiability).toHaveBeenCalledWith(22, { is_active: false });
    await store.deleteLiability(22);
    expect(mocks.coreNetWorthApi.deleteLiability).toHaveBeenCalledWith(22);
  });

  it('fetches settings and updates base currency', async () => {
    mocks.coreNetWorthApi.getSettings.mockResolvedValue({
      data: { base_currency: 'USD', inflation_region: 'ES' },
    });
    mocks.coreNetWorthApi.getSummary.mockResolvedValue({ data: { base_currency: 'USD' } });
    mocks.coreNetWorthApi.getAssets.mockResolvedValue({ data: [] });
    mocks.coreNetWorthApi.getLiabilities.mockResolvedValue({ data: [] });
    mocks.coreNetWorthApi.getTimeline.mockResolvedValue({ data: { rows: [] } });
    const store = useNetWorthStore();

    await store.fetchSettings();
    expect(store.baseCurrency).toBe('USD');
    expect(store.inflationRegion).toBe('ES');

    // After updateBaseCurrency, refreshAll re-fetches settings from the server
    mocks.coreNetWorthApi.updateSettings.mockResolvedValue({
      data: { base_currency: 'EUR', inflation_region: 'ES' },
    });
    mocks.coreNetWorthApi.getSettings.mockResolvedValue({
      data: { base_currency: 'EUR', inflation_region: 'ES' },
    });
    mocks.coreNetWorthApi.getSummary.mockResolvedValue({ data: { base_currency: 'EUR' } });
    await store.updateBaseCurrency('EUR');
    expect(mocks.coreNetWorthApi.updateSettings).toHaveBeenCalledWith({
      base_currency: 'EUR',
      inflation_region: 'ES',
    });
    expect(store.baseCurrency).toBe('EUR');

    mocks.coreNetWorthApi.updateSettings.mockResolvedValue({
      data: { base_currency: 'EUR', inflation_region: 'ES-MD' },
    });
    mocks.coreNetWorthApi.getSettings.mockResolvedValue({
      data: { base_currency: 'EUR', inflation_region: 'ES-MD' },
    });
    await store.updateInflationRegion('ES-MD');
    expect(mocks.coreNetWorthApi.updateSettings).toHaveBeenLastCalledWith({
      base_currency: 'EUR',
      inflation_region: 'ES-MD',
    });
    expect(store.inflationRegion).toBe('ES-MD');
  });

  it('fetches timeline with category filter', async () => {
    mocks.coreNetWorthApi.getTimeline.mockResolvedValue({
      data: {
        rows: [{ date: '2026-01-31', net_worth: '100.00' }],
        base_currency: 'EUR',
        filters: { asset_category: 'investments', liability_category: null },
      },
    });
    const store = useNetWorthStore();

    await store.fetchTimeline('investments');

    expect(mocks.coreNetWorthApi.getTimeline).toHaveBeenCalledWith({
      asset_category: 'investments',
      liability_category: null,
    });
    expect(store.timelineCategoryFilter).toBe('investments');
    expect(store.timelineCategoryFilterType).toBe('asset');
    expect(store.timeline?.filters.asset_category).toBe('investments');
    expect(store.timelineLoading).toBe(false);
  });

  it('fetches position timeline for assets and liabilities', async () => {
    mocks.coreNetWorthApi.getAssetTimeline.mockResolvedValue({
      data: {
        position_type: 'asset',
        position_id: 4,
        rows: [{ date: '2026-03-31', value: '100' }],
      },
    });
    mocks.coreNetWorthApi.getLiabilityTimeline.mockResolvedValue({
      data: {
        position_type: 'liability',
        position_id: 7,
        rows: [{ date: '2026-03-31', value: '50' }],
      },
    });
    const store = useNetWorthStore();

    await store.fetchPositionTimeline('asset', 4);
    expect(mocks.coreNetWorthApi.getAssetTimeline).toHaveBeenCalledWith(4);
    expect(store.positionTimeline?.position_id).toBe(4);

    await store.fetchPositionTimeline('liability', 7);
    expect(mocks.coreNetWorthApi.getLiabilityTimeline).toHaveBeenCalledWith(7);
    expect(store.positionTimeline?.position_type).toBe('liability');
    expect(store.positionTimelineLoading).toBe(false);
  });

  it('fetches position activity for asset and liability modes', async () => {
    mocks.coreNetWorthApi.getAssetValuations.mockResolvedValue({
      data: [{ id: 1, asset_ref: 4, value: '100', valuation_date: '2026-03-31', source: 'manual' }],
    });
    mocks.coreNetWorthApi.getInvestmentEvents.mockResolvedValue({
      data: [
        { id: 2, asset_ref: 4, amount: '20', event_date: '2026-03-15', event_type: 'contribution' },
      ],
    });
    mocks.coreNetWorthApi.getLiabilityValuations.mockResolvedValue({
      data: [
        { id: 3, liability_ref: 7, value: '50', valuation_date: '2026-03-31', source: 'manual' },
      ],
    });
    mocks.coreNetWorthApi.getLiabilityEvents.mockResolvedValue({
      data: [
        { id: 4, liability_ref: 7, amount: '10', event_date: '2026-03-18', event_type: 'payment' },
      ],
    });
    const store = useNetWorthStore();

    await store.fetchPositionActivity('asset', 4, 'investments');
    expect(store.assetValuations).toHaveLength(1);
    expect(store.investmentEvents).toHaveLength(1);

    await store.fetchPositionActivity('liability', 7);
    expect(store.liabilityValuations).toHaveLength(1);
    expect(store.liabilityEvents).toHaveLength(1);
    expect(store.positionActivityLoading).toBe(false);
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
