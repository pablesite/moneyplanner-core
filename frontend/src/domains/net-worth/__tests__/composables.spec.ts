import { beforeEach, describe, expect, it, vi } from 'vitest';
import { nextTick, reactive } from 'vue';
import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';
import { useNetWorthViewState } from '@/domains/net-worth/composables';
import type { Asset, Liability, Summary } from '@/domains/net-worth/models';

const mocks = vi.hoisted(() => ({
  useNetWorthStore: vi.fn(),
}));

vi.mock('@/domains/net-worth/store', () => ({
  useNetWorthStore: mocks.useNetWorthStore,
}));

function makeSummary(overrides: Partial<Summary> = {}): Summary {
  return {
    base_currency: 'EUR',
    total_assets: '1000',
    total_liabilities: '200',
    net_worth: '800',
    assets_by_category: {},
    assets_by_subcategory: {},
    liabilities_by_category: {},
    inflation_region: 'ES',
    inflation_base_period: '2025-01',
    inflation_available: true,
    inflation_status: 'available',
    total_assets_real: '900',
    total_liabilities_real: '180',
    net_worth_real: '720',
    assets_by_category_real: {},
    liabilities_by_category_real: {},
    ...overrides,
  };
}

function makeItem(overrides: Partial<Asset> = {}): Asset {
  return {
    id: 1,
    name: 'Asset',
    category: 'cash',
    subcategory: 'bank_account',
    tracking_mode: 'manual',
    accounting_account_id: null,
    currency: 'EUR',
    amount: '1000.5000',
    is_active: true,
    notes: 'N',
    ...overrides,
  };
}

describe('useNetWorthViewState (core)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal(
      'confirm',
      vi.fn(() => true),
    );
  });

  it('loads store on mount and maps submit/delete flows', async () => {
    const store = reactive({
      loading: false,
      error: null as string | null,
      baseCurrency: 'EUR',
      summary: makeSummary(),
      byCategoryChart: { keys: [], assets: [], liabilities: [], unit: 'EUR' },
      fetchSettings: vi.fn(async () => undefined),
      refreshAll: vi.fn(async () => undefined),
      createAsset: vi.fn(async () => undefined),
      createLiability: vi.fn(async () => undefined),
      deleteSnapshot: vi.fn(async () => undefined),
      updateAsset: vi.fn(async () => undefined),
      updateLiability: vi.fn(async () => undefined),
    });
    mocks.useNetWorthStore.mockReturnValue(store);

    const Harness = defineComponent({
      setup() {
        return useNetWorthViewState();
      },
      template: '<div />',
    });
    const wrapper = mount(Harness);
    const state = wrapper.vm;
    await wrapper.vm.$nextTick();
    state.showAssetModal = true;
    await state.submitAsset({ name: 'A' });
    expect(store.createAsset).toHaveBeenCalledWith({ name: 'A' });
    expect(state.showAssetModal).toBe(false);

    state.showLiabilityModal = true;
    await state.submitLiability({ name: 'L' });
    expect(store.createLiability).toHaveBeenCalledWith({ name: 'L' });
    expect(state.showLiabilityModal).toBe(false);

    state.confirmDeleteSnapshot(7);
    expect(store.deleteSnapshot).toHaveBeenCalledWith(7);
  });

  it('reacts to mode changes, computes labels, edit payloads and error messages', async () => {
    const store = reactive({
      loading: false,
      error: '{"detail":"boom"}',
      baseCurrency: 'EUR',
      summary: {
        ...makeSummary(),
        assets_by_category_real: {
          cash: '9',
          mortgage: '0',
        },
        liabilities_by_category_real: {
          cash: '0',
          mortgage: '4',
        },
        liabilities_asset_backed: '100',
        liabilities_unbacked: '50',
        liabilities_asset_backed_real: '80',
        liabilities_unbacked_real: '40',
      } as Summary,
      byCategoryChart: {
        keys: ['cash', 'mortgage', 'other'],
        assets: [10, 0, 0],
        liabilities: [0, 5, 0],
        unit: 'EUR',
      },
      fetchSettings: vi.fn(async () => undefined),
      refreshAll: vi.fn(async () => undefined),
      createAsset: vi.fn(async () => undefined),
      createLiability: vi.fn(async () => undefined),
      deleteSnapshot: vi.fn(async () => undefined),
      updateAsset: vi.fn(async () => undefined),
      updateLiability: vi.fn(async () => undefined),
    });
    mocks.useNetWorthStore.mockReturnValue(store);

    const Harness = defineComponent({
      setup() {
        return useNetWorthViewState();
      },
      template: '<div />',
    });
    const wrapper = mount(Harness);
    const state = wrapper.vm;

    expect(state.prettyError()).toBe('boom');
    expect(state.canShowReal()).toBe(true);
    state.valueMode = 'real';
    expect(state.unitLabel()).toBe('EUR (2025-01)');
    expect(state.modeLabel()).toContain('2025-01');
    expect(state.realBaseLabel).toBe('Base: 2025-01');
    expect(state.summaryAssets).toBe('900');
    expect(state.summaryAssetBackedLiabilities).toBe('80');
    expect(state.summaryUnbackedLiabilities).toBe('40');
    expect(state.byCategoryKeys).toEqual(['cash', 'mortgage']);
    expect(state.byCategoryLabels).toEqual(['Liquidez', 'Hipoteca']);
    expect(state.byCategoryAssets).toEqual([9, 0]);
    expect(state.byCategoryLiabilities).toEqual([0, 4]);

    const asset = makeItem({
      financed_asset_ref: 33,
      valuation_model: 'real_estate_auto',
      land_value_share_percent: '42.3',
      land_annual_appreciation_percent: '3',
      building_annual_depreciation_percent: '1',
    });
    state.openEdit(asset, 'asset');
    expect(state.showEditModal).toBe(true);
    expect(state.editTitle).toBe('Editar activo');
    expect(state.editInitial?.amount).toBe('1000.5');
    expect(state.editInitial?.financed_asset_id).toBe(33);
    expect(state.editInitial?.valuation_model).toBe('real_estate_auto');
    expect(state.editInitial?.land_value_share_percent).toBe('42.3');
    expect(state.editInitial?.land_annual_appreciation_percent).toBe('3');
    expect(state.editInitial?.building_annual_depreciation_percent).toBe('1');
    await state.submitEdit({ name: 'edited', financed_asset_id: 99 });
    expect(store.updateAsset).toHaveBeenCalledWith(1, { name: 'edited' });
    expect(state.showEditModal).toBe(false);

    const liability = makeItem({ id: 2, name: 'Liability' }) as Liability;
    state.openEdit(liability, 'liability');
    expect(state.editTitle).toBe('Editar pasivo');
    await state.submitEdit({ name: 'L2', financed_asset_id: 88 });
    expect(store.updateLiability).toHaveBeenCalledWith(2, { name: 'L2', financed_asset_id: 88 });

    store.baseCurrency = 'USD';
    await nextTick();
    expect(state.valueMode).toBe('nominal');
  });
});
