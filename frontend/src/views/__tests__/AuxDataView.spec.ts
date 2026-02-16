/** @vitest-environment jsdom */
import { ref } from 'vue';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import AuxDataView from '../AuxDataView.vue';

const mockPush = vi.fn();
const mockUseAuxDataPage = vi.fn();

vi.mock('vue-router', () => ({
  useRouter: () => ({ push: mockPush }),
}));

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
    mockPush.mockReset();
    mockUseAuxDataPage.mockReset();
  });

  it('renders empty states for FX and IPC tables', () => {
    mockUseAuxDataPage.mockReturnValue(makeState());
    const wrapper = mount(AuxDataView);

    expect(wrapper.text()).toContain('No hay FX rates');
    expect(wrapper.text()).toContain('No hay');
    expect(wrapper.text()).toContain('IPC');
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

  it('navigates back to net-worth view', async () => {
    mockUseAuxDataPage.mockReturnValue(makeState());
    const wrapper = mount(AuxDataView);

    await wrapper.get('button.btn').trigger('click');
    expect(mockPush).toHaveBeenCalledWith('/');
  });
});
