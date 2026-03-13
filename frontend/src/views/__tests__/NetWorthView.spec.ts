/** @vitest-environment jsdom */
import { defineComponent, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import NetWorthView from '../NetWorthView.vue';

const mockUseNetWorthViewState = vi.fn();
const mockUseNetWorthViewExtensions = vi.fn();
const mockPush = vi.fn();
const mockCoreNetWorthApi = vi.hoisted(() => ({
  getAssetTimeline: vi.fn(async () => ({ data: { rows: [], base_currency: 'EUR' } })),
  getLiabilityTimeline: vi.fn(async () => ({ data: { rows: [], base_currency: 'EUR' } })),
}));

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
  NetWorthDonut: defineComponent({
    name: 'NetWorthDonut',
    emits: ['select-category', 'add-type', 'add-category'],
    template: `
      <div data-test="NetWorthDonut">
        <button
          data-test="donut-select-asset"
          type="button"
          @click="$emit('select-category', { key: 'cash', type: 'asset' })"
        >
          asset
        </button>
        <button
          data-test="donut-select-liability"
          type="button"
          @click="$emit('select-category', { key: 'mortgage', type: 'liability' })"
        >
          liability
        </button>
        <button
          data-test="donut-add-asset"
          type="button"
          @click="$emit('add-type', { type: 'asset' })"
        >
          add-asset
        </button>
      </div>
    `,
  }),
  SettingsPopover: makeStub('SettingsPopover'),
  coreNetWorthApi: mockCoreNetWorthApi,
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
    ownerships: [],
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
    mockCoreNetWorthApi.getAssetTimeline.mockClear();
    mockCoreNetWorthApi.getLiabilityTimeline.mockClear();
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
    expect(wrapper.text()).not.toContain('Detalle por posicion');
    expect(wrapper.find('select.ui-nw-position-select-input').exists()).toBe(false);
    expect(wrapper.text()).toContain('Capital propio sobre activos');
    expect(wrapper.text()).toContain('Ratio deuda / activos');
    expect(wrapper.find('[data-test="NetWorthDonut"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('No hay snapshots');
  });

  it('filters current net worth metrics by ownership from the header selector', async () => {
    const state = makeState({
      store: {
        ...makeState().store,
        ownerships: [
          {
            id: 7,
            kind: 'shared',
            member: null,
            splits: [
              { member: { id: 3, name: 'Ana', role: 'adult' }, percent: '60' },
              { member: { id: 4, name: 'Lucas', role: 'adult' }, percent: '40' },
            ],
            notes: '',
          },
        ],
        assets: [
          {
            id: 11,
            name: 'Cuenta Ana',
            category: 'cash',
            subcategory: 'bank_account',
            amount: '1000',
            amount_base: '1000',
            currency: 'EUR',
            is_active: true,
            ownership_ref: 7,
          },
          {
            id: 12,
            name: 'Cuenta comun',
            category: 'cash',
            subcategory: 'bank_account',
            amount: '200',
            amount_base: '200',
            currency: 'EUR',
            is_active: true,
            ownership_ref: null,
          },
        ],
        liabilities: [
          {
            id: 21,
            name: 'Tarjeta Ana',
            category: 'credit_card',
            amount: '500',
            amount_base: '500',
            currency: 'EUR',
            is_active: true,
            ownership_ref: 7,
          },
        ],
      },
    });
    mockUseNetWorthViewState.mockReturnValue(state);
    mockUseNetWorthViewExtensions.mockReturnValue({
      HeaderActions: null,
      itemFormProps: {},
      itemListProps: {},
    });

    const wrapper = mount(NetWorthView);

    await wrapper.get('[data-test="ownership-filter-option-3"]').trigger('click');

    expect(wrapper.text()).toContain('300,00 EUR');
    expect(wrapper.text()).toContain('600,00 EUR');
    expect(wrapper.text()).toContain('Ana');
  });

  it('uses the current summary totals in the general timeline highlight instead of the projected month-end row', () => {
    const state = makeState({
      summaryAssets: ref('1000'),
      summaryLiabilities: ref('250'),
      summaryNetWorth: ref('750'),
      store: {
        ...makeState().store,
        timeline: {
          base_currency: 'EUR',
          rows: [
            {
              date: '2026-03-31',
              net_worth: '900',
              total_assets: '1150',
              total_liabilities: '250',
            },
          ],
        },
      },
    });
    mockUseNetWorthViewState.mockReturnValue(state);
    mockUseNetWorthViewExtensions.mockReturnValue({
      HeaderActions: null,
      itemFormProps: {},
      itemListProps: {},
    });

    const wrapper = mount(NetWorthView);

    expect(wrapper.text()).toContain('Ultimo patrimonio neto');
    expect(wrapper.text()).toContain('750,00 EUR');
    expect(wrapper.text()).toContain('Actual | Activos 1.000 | Pasivos 250');
    expect(wrapper.text()).not.toContain('900,00 EUR');
    expect(wrapper.text()).not.toContain('Activos 1.150');
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

  it('requests timeline when selecting an asset category from composition', async () => {
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

    await wrapper.get('[data-test="donut-select-asset"]').trigger('click');
    expect(state.store.fetchTimeline).toHaveBeenCalledWith('cash', 'asset');
    expect(wrapper.find('select.ui-nw-position-select-input').exists()).toBe(true);
    expect(wrapper.text()).toContain('Liquidez dentro de activos');
    expect(wrapper.text()).toContain('1 posiciones');
  });

  it('opens the asset modal from composition actions', async () => {
    const state = makeState({
      showAssetModal: ref(false),
    });
    mockUseNetWorthViewState.mockReturnValue(state);
    mockUseNetWorthViewExtensions.mockReturnValue({
      HeaderActions: null,
      itemFormProps: {},
      itemListProps: {},
    });

    const wrapper = mount(NetWorthView);

    await wrapper.get('[data-test="donut-add-asset"]').trigger('click');

    expect(state.showAssetModal.value).toBe(true);
    expect(wrapper.find('[data-test="ItemForm"]').exists()).toBe(true);
  });

  it('returns to the general timeline when clicking the active composition category again', async () => {
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

    await wrapper.get('[data-test="donut-select-asset"]').trigger('click');
    await wrapper.get('[data-test="donut-select-asset"]').trigger('click');

    expect(state.store.fetchTimeline).toHaveBeenNthCalledWith(1, 'cash', 'asset');
    expect(state.store.fetchTimeline).toHaveBeenNthCalledWith(2, null, 'asset');
    expect(wrapper.find('select.ui-nw-position-select-input').exists()).toBe(false);
  });

  it('requests liability timeline when selecting a liability category from composition', async () => {
    const state = makeState({
      store: {
        ...makeState().store,
        liabilities: [
          {
            id: 21,
            name: 'Hipoteca casa',
            category: 'mortgage',
            amount: '250',
            amount_base: '250',
            currency: 'EUR',
            is_active: true,
          },
        ],
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

    await wrapper.get('[data-test="donut-select-liability"]').trigger('click');
    expect(state.store.fetchTimeline).toHaveBeenCalledWith('mortgage', 'liability');
  });

  it('fetches per-position timeline when selecting an asset from the integrated selector', async () => {
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

    await wrapper.get('[data-test="donut-select-asset"]').trigger('click');
    await wrapper.get('select.ui-nw-position-select-input').setValue('11');

    expect(state.store.fetchPositionTimeline).toHaveBeenCalledWith('asset', 11);
    expect(state.store.fetchPositionActivity).toHaveBeenCalledWith('asset', 11, 'cash');
  });
});
