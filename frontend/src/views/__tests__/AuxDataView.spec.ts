/** @vitest-environment jsdom */
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import { ref } from 'vue';
import AuxDataView from '../AuxDataView.vue';

const mockUseAuxDataPage = vi.fn();

vi.mock('@/domains/aux-data', () => ({
  useAuxDataPage: () => mockUseAuxDataPage(),
}));

vi.mock('@/domains/people', () => ({
  FamilyMemberManager: {
    name: 'FamilyMemberManager',
    template: '<div data-test="FamilyMemberManager" />',
  },
  OwnershipManager: {
    name: 'OwnershipManager',
    template: '<div data-test="OwnershipManager" />',
  },
}));

function makeState(overrides: Record<string, unknown> = {}) {
  return {
    loading: ref(false),
    error: ref<string | null>(null),
    fxRates: ref([]),
    inflation: ref([]),
    fxStates: ref([]),
    inflationStates: ref([]),
    supportedInflationRegions: ref([{ code: 'ES', label: 'Espana' }]),
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
    expect(wrapper.text()).toContain('No hay indices IPC sincronizados todavia.');
    expect(wrapper.text()).toContain('No hay FX rates sincronizados todavia.');
  });

  it('toggles IPC and FX sections in place', async () => {
    mockUseAuxDataPage.mockReturnValue(makeState());
    const wrapper = mount(AuxDataView);

    const toggles = wrapper.findAll('.ui-settings-toggle');
    await toggles[1]!.trigger('click');
    expect(wrapper.text()).not.toContain('No hay indices IPC sincronizados todavia.');

    await toggles[2]!.trigger('click');
    expect(wrapper.text()).not.toContain('No hay FX rates sincronizados todavia.');
  });

  it('renders loading and error messages', () => {
    mockUseAuxDataPage.mockReturnValue(
      makeState({
        loading: ref(true),
        error: ref('Error de red'),
      }),
    );
    const wrapper = mount(AuxDataView);

    expect(wrapper.text()).toContain('Error de red');
    expect(wrapper.text()).toContain('Cargando datos auxiliares...');
  });
});
