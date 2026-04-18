/** @vitest-environment jsdom */
import { describe, expect, it, vi } from 'vitest';
import { computed, ref } from 'vue';
import { shallowMount } from '@vue/test-utils';
import AccountingMovementsView from '../AccountingMovementsView.vue';

const mockUseAccountingMovementsPage = vi.fn();

vi.mock('@/domains/accounting/useAccountingMovementsPage', () => ({
  useAccountingMovementsPage: () => mockUseAccountingMovementsPage(),
}));

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: {} }),
  onBeforeRouteLeave: vi.fn(),
}));

function makeState(tab: 'cuentas' | 'todos' | 'estadisticas' = 'cuentas') {
  return {
    activeTab: tab,
    hasAvailableManualPositions: computed(() => true),
    liquidityAccounts: computed(() => [{ id: 1 }]),
    dailyBalanceSeriesRows: computed(() => []),
    dailyBalanceSeriesLoading: computed(() => false),
    dailyBalanceSeriesError: computed(() => null),
    dailyBalanceSeriesUnit: computed(() => 'EUR'),
    dailyBalanceSeriesChartPoints: computed(() => []),
    dailyBalanceSeriesChartRows: computed(() => []),
    dailyBalanceSeriesRangeLabel: computed(() => '2025-04-17 - 2026-04-17'),
    dailyBalanceLatestChartPoint: computed(() => null),
    dailyTimelinePresetOptions: computed(() => ['1m', '3m', '6m', '1a', '5a', 'all']),
    selectedDailyTimelinePreset: '1a',
    dailyTimelineCustomWindow: null,
    dailyTimelineWindow: computed(() => ({ start: 0, end: 0 })),
    dailyTimelineExpanded: false,
    setDailyTimelinePreset: vi.fn(),
    updateDailyTimelineWindowStart: vi.fn(),
    updateDailyTimelineWindowEnd: vi.fn(),
    formatNumber: vi.fn((value: number) => String(value)),
    showMoneyWizImportModal: ref(false),
    showQuickEntryModal: ref(false),
    openActivationModal: vi.fn(),
  };
}

describe('AccountingMovementsView', () => {
  it('renders hero actions and tabs', () => {
    mockUseAccountingMovementsPage.mockReturnValue(makeState());
    const wrapper = shallowMount(AccountingMovementsView);

    expect(wrapper.text()).toContain('Cuentas');
    expect(wrapper.text()).toContain('Todos los movimientos');
    expect(wrapper.text()).toContain('Estad');
  });

  it('switches tab when clicking controls', async () => {
    const state = makeState('cuentas');
    mockUseAccountingMovementsPage.mockReturnValue(state);
    const wrapper = shallowMount(AccountingMovementsView);

    const buttons = wrapper.findAll('button.ui-view-tab');
    await buttons[1]!.trigger('click');
    expect(state.activeTab).toBe('todos');
    await buttons[2]!.trigger('click');
    expect(state.activeTab).toBe('estadisticas');
  });
});
