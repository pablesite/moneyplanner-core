/** @vitest-environment jsdom */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { ref } from 'vue';
import AuxDataView from '../AuxDataView.vue';

const mockUseAuxDataPage = vi.fn();

vi.mock('@/domains/aux-data', () => ({
  useAuxDataPage: () => mockUseAuxDataPage(),
}));

function makeState(overrides: Record<string, unknown> = {}) {
  return {
    loading: ref(false),
    error: ref<string | null>(null),
    successMessage: ref<string | null>(null),
    fxRates: ref([]),
    inflation: ref([]),
    fxForm: ref({ rate_date: '', pair: 'USD_EUR', rate: '' }),
    fxPairs: [{ value: 'USD_EUR', label: 'USD -> EUR' }],
    fxRatePlaceholder: ref('0.92'),
    ipcForm: ref({ region: 'ES', period: '', index: '' }),
    createFxRate: vi.fn(),
    deleteFxRate: vi.fn(),
    createInflation: vi.fn(),
    deleteInflation: vi.fn(),
    formatFxRate: vi.fn(() => '0.9200'),
    formatInflationIndex: vi.fn(() => '118.0'),
    ...overrides,
  };
}

describe('AuxDataView', () => {
  beforeEach(() => {
    mockUseAuxDataPage.mockReset();
  });

  it('renders settings and accordion sections', () => {
    mockUseAuxDataPage.mockReturnValue(makeState());
    const wrapper = mount(AuxDataView);

    expect(wrapper.text()).toContain('Settings');
    expect(wrapper.text()).toContain('Datos IPC');
    expect(wrapper.text()).toContain('Tasas de conversion');
    expect(wrapper.text()).toContain('No hay indices IPC todavia.');
    expect(wrapper.text()).not.toContain('No hay FX rates todavia.');
  });

  it('toggles IPC and FX sections in place', async () => {
    mockUseAuxDataPage.mockReturnValue(makeState());
    const wrapper = mount(AuxDataView);

    const toggles = wrapper.findAll('.ui-settings-toggle');
    await toggles[0]!.trigger('click');
    expect(wrapper.text()).not.toContain('No hay indices IPC todavia.');

    await toggles[1]!.trigger('click');
    expect(wrapper.text()).toContain('No hay FX rates todavia.');
  });

  it('renders loading, error and success messages', () => {
    mockUseAuxDataPage.mockReturnValue(
      makeState({
        loading: ref(true),
        error: ref('Error de red'),
        successMessage: ref('FX rate creado correctamente.'),
      }),
    );
    const wrapper = mount(AuxDataView);

    expect(wrapper.text()).toContain('Error de red');
    expect(wrapper.text()).toContain('FX rate creado correctamente.');
    expect(wrapper.text()).toContain('Cargando datos auxiliares...');
  });
});
