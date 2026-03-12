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
    timeline: { rows: [], base_currency: 'EUR' },
    timelineLoading: false,
    positionTimeline: { rows: [], base_currency: 'EUR', position_type: 'asset', position_id: 1 },
    positionTimelineLoading: false,
    positionActivityLoading: false,
    assetValuations: [],
    liabilityValuations: [],
    investmentEvents: [],
    liquidityEvents: [],
    liabilityEvents: [],
    refreshAll: vi.fn(),
    fetchTimeline: vi.fn(),
    fetchPositionTimeline: vi.fn(),
    fetchPositionActivity: vi.fn(),
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
    summaryAssets: ref('1000'),
    summaryLiabilities: ref('250'),
    summaryNetWorth: ref('750'),
    byCategoryKeys: ref(['cash']),
    byCategoryLabels: ref(['Liquidez']),
    byCategoryAssets: ref([1000]),
    byCategoryLiabilities: ref([250]),
    byCategoryUnit: ref('EUR'),
    summaryAssetBackedLiabilities: ref('150'),
    summaryUnbackedLiabilities: ref('100'),
    ...overrides,
  };
}

describe('NetWorthView', () => {
  beforeEach(() => {
    mockUseNetWorthViewState.mockReset();
    mockUseNetWorthViewExtensions.mockReset();
    mockPush.mockReset();
  });

  it('renders key sections and current analytics blocks', () => {
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
    expect(wrapper.text()).toContain('Patrimonio neto');
    expect(wrapper.text()).toContain('Evolucion temporal');
    expect(wrapper.text()).toContain('Detalle por posicion');
    expect(wrapper.text()).toContain('Elige una posicion para inspeccionar su curva temporal');
    expect(wrapper.text()).toContain('Capital propio sobre activos');
    expect(wrapper.text()).toContain('Ratio deuda / activos');
    expect(wrapper.find('[data-test="NetWorthDonut"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('No hay snapshots');
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

    expect(state.store.refreshAll).toHaveBeenCalled();
    expect(state.store.createTodaySnapshot).toHaveBeenCalled();
    expect(state.confirmDeleteSnapshot).toHaveBeenCalledWith(5);
  });

  it('requests timeline when changing the category filter', async () => {
    const state = makeState({
      store: {
        ...makeState().store,
        timeline: {
          base_currency: 'EUR',
          rows: [
            {
              date: '2026-03-31',
              net_worth: '750',
              total_assets: '1000',
              total_liabilities: '250',
            },
          ],
        },
        fetchTimeline: vi.fn(),
      },
    });
    mockUseNetWorthViewState.mockReturnValue(state);
    mockUseNetWorthViewExtensions.mockReturnValue({
      HeaderActions: null,
      itemFormProps: {},
      itemListProps: {},
    });

    const wrapper = mount(NetWorthView);

    await wrapper.get('button.ui-nw-timeline-filter').trigger('click');
    expect(state.store.fetchTimeline).toHaveBeenCalledWith(null, 'asset');
  });

  it('requests liability timeline when selecting a liability category filter', async () => {
    const state = makeState({
      store: {
        ...makeState().store,
        timeline: {
          base_currency: 'EUR',
          rows: [
            {
              date: '2026-02-28',
              net_worth: '750',
              total_assets: '1000',
              total_liabilities: '250',
            },
          ],
        },
        fetchTimeline: vi.fn(),
      },
    });
    mockUseNetWorthViewState.mockReturnValue(state);
    mockUseNetWorthViewExtensions.mockReturnValue({
      HeaderActions: null,
      itemFormProps: {},
      itemListProps: {},
    });

    const wrapper = mount(NetWorthView);
    const liabilityFilter = wrapper
      .findAll('button.ui-nw-timeline-filter')
      .find((button) => button.text().includes('Pasivos'));

    expect(liabilityFilter).toBeTruthy();
    await liabilityFilter!.trigger('click');
    expect(state.store.fetchTimeline).toHaveBeenCalledWith('mortgage', 'liability');
  });

  it('fetches per-position timeline when selecting an asset', async () => {
    const state = makeState({
      store: {
        ...makeState().store,
        assets: [
          {
            id: 11,
            name: 'Cuenta nomina',
            category: 'cash',
            subcategory: 'bank_account',
            amount: '1000',
            amount_base: '1000',
            currency: 'EUR',
            is_active: true,
          },
        ],
        liabilities: [],
        fetchPositionTimeline: vi.fn(),
        fetchPositionActivity: vi.fn(),
      },
    });
    mockUseNetWorthViewState.mockReturnValue(state);
    mockUseNetWorthViewExtensions.mockReturnValue({
      HeaderActions: null,
      itemFormProps: {},
      itemListProps: {},
    });

    const wrapper = mount(NetWorthView);

    await wrapper.get('button.ui-nw-position-button').trigger('click');
    expect(state.store.fetchPositionTimeline).toHaveBeenCalledWith('asset', 11);
    expect(state.store.fetchPositionActivity).toHaveBeenCalledWith('asset', 11, 'cash');
  });
});
