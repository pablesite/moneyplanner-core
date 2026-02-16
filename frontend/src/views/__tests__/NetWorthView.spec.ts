/** @vitest-environment jsdom */
import { defineComponent, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import NetWorthView from '../NetWorthView.vue';

const mockUseNetWorthViewState = vi.fn();
const mockUseNetWorthViewExtensions = vi.fn();
const mockPush = vi.fn();

function makeStub(name: string) {
  return defineComponent({
    name,
    template: `<div data-test="${name}"><slot /></div>`,
  });
}

vi.mock('@/domains/net-worth', () => ({
  ItemForm: makeStub('ItemForm'),
  ItemList: makeStub('ItemList'),
  NetWorthByCategoryBar: makeStub('NetWorthByCategoryBar'),
  NetWorthDonut: makeStub('NetWorthDonut'),
  SettingsPopover: makeStub('SettingsPopover'),
  useNetWorthViewState: () => mockUseNetWorthViewState(),
  useNetWorthViewExtensions: () => mockUseNetWorthViewExtensions(),
}));

vi.mock('@/domains/ui', () => ({
  BaseModal: defineComponent({
    name: 'BaseModal',
    props: {
      open: { type: Boolean, required: true },
      title: { type: String, required: false, default: '' },
    },
    template: '<div><slot v-if="open" /></div>',
  }),
}));

function makeState(overrides: Record<string, unknown> = {}) {
  const store = {
    loading: false,
    error: null as string | null,
    baseCurrency: 'EUR',
    summary: {
      base_currency: 'EUR',
      total_assets: '1000',
      total_liabilities: '250',
      net_worth: '750',
      assets_by_category: {},
      assets_by_subcategory: {},
      liabilities_by_category: {},
    },
    assets: [],
    liabilities: [],
    snapshots: [],
    refreshAll: vi.fn(),
    createTodaySnapshot: vi.fn(),
    updateBaseCurrency: vi.fn(),
    updateAsset: vi.fn(),
    archiveAsset: vi.fn(),
    updateLiability: vi.fn(),
    archiveLiability: vi.fn(),
  };

  return {
    store,
    valueMode: ref<'nominal' | 'real'>('nominal'),
    currencies: [{ value: 'EUR', label: 'EUR' }],
    assetCategories: [{ value: 'cash', label: 'Liquidez' }],
    assetSubcategories: [{ category: 'cash', value: 'bank_account', label: 'Cuenta bancaria' }],
    liabilityCategories: [{ value: 'mortgage', label: 'Hipoteca' }],
    prettyError: vi.fn(() => 'Error bonito'),
    showAssetModal: ref(false),
    showLiabilityModal: ref(false),
    showBreakdown: ref(false),
    showEditModal: ref(false),
    editKind: ref<'asset' | 'liability' | null>(null),
    canShowReal: vi.fn(() => true),
    submitAsset: vi.fn(),
    submitLiability: vi.fn(),
    openEdit: vi.fn(),
    closeEdit: vi.fn(),
    confirmDeleteSnapshot: vi.fn(),
    editTitle: 'Editar activo',
    editCategories: [],
    editInitial: null,
    submitEdit: vi.fn(),
    formatMoney: vi.fn((v: string) => v),
    unitLabel: vi.fn(() => 'EUR'),
    modeLabel: vi.fn(() => 'Nominal'),
    realBaseLabel: ref(''),
    summaryAssets: '1000',
    summaryLiabilities: '250',
    summaryNetWorth: '750',
    byCategoryLabels: ['Liquidez'],
    byCategoryAssets: [1000],
    byCategoryLiabilities: [250],
    byCategoryUnit: 'EUR',
    summaryAssetBackedLiabilities: '150',
    summaryUnbackedLiabilities: '100',
    ...overrides,
  };
}

describe('NetWorthView', () => {
  beforeEach(() => {
    mockUseNetWorthViewState.mockReset();
    mockUseNetWorthViewExtensions.mockReset();
    mockPush.mockReset();
  });

  it('renders key sections and toggles breakdown', async () => {
    mockUseNetWorthViewState.mockReturnValue(makeState());
    mockUseNetWorthViewExtensions.mockReturnValue({
      HeaderActions: null,
      itemFormProps: {},
      itemListProps: {},
    });

    const wrapper = mount(NetWorthView, {
      global: {
        mocks: {
          $router: { push: mockPush },
        },
      },
    });

    expect(wrapper.text()).toContain('Patrimonio');
    expect(wrapper.text()).toContain('Desglose');
    expect(wrapper.findAll('[data-test="ItemList"]')).toHaveLength(2);
    expect(wrapper.text()).toContain('No hay snapshots');

    const toggleButton = wrapper
      .findAll('button')
      .find((button) => button.text().includes('Mostrar'));
    expect(toggleButton).toBeTruthy();

    await toggleButton!.trigger('click');
    expect(wrapper.text()).toContain('Ocultar');
  });

  it('wires header actions and snapshot deletion callback', async () => {
    const state = makeState({
      store: {
        ...makeState().store,
        snapshots: [
          {
            id: 5,
            snapshot_date: '2026-01-01',
            net_worth: '750',
            total_assets: '1000',
            total_liabilities: '250',
            base_currency: 'EUR',
          },
        ],
      },
      confirmDeleteSnapshot: vi.fn(),
    });
    mockUseNetWorthViewState.mockReturnValue(state);
    mockUseNetWorthViewExtensions.mockReturnValue({
      HeaderActions: null,
      itemFormProps: {},
      itemListProps: {},
    });

    const wrapper = mount(NetWorthView, {
      global: {
        mocks: {
          $router: { push: mockPush },
        },
      },
    });

    await wrapper.get('button[aria-label="Refrescar"]').trigger('click');
    await wrapper.get('button[aria-label="Guardar snapshot"]').trigger('click');
    await wrapper.get('button[aria-label="Eliminar snapshot"]').trigger('click');
    await wrapper.get('button.btn').trigger('click');

    expect(state.store.refreshAll).toHaveBeenCalled();
    expect(state.store.createTodaySnapshot).toHaveBeenCalled();
    expect(state.confirmDeleteSnapshot).toHaveBeenCalledWith(5);
    expect(mockPush).toHaveBeenCalledWith('/data');
  });
});
