/** @vitest-environment jsdom */
import { defineComponent, nextTick, ref } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import GuidePhaseDetailView from '../GuidePhaseDetailView.vue';

const mockRoute = { params: { phaseId: '2' } };
const mockNetWorthStore = {
  loading: false,
  error: null as string | null,
  summary: {
    base_currency: 'EUR',
    total_assets: '50000',
    total_liabilities: '10000',
    net_worth: '40000',
    liabilities_unbacked: '10000',
    assets_by_category: { cash: '50000' },
    assets_by_subcategory: {},
    liabilities_by_category: { mortgage: '10000' },
  },
  assets: [] as any[],
  liabilities: [] as any[],
  byCategoryChart: { keys: [], assets: [], liabilities: [] },
  fetchSettings: vi.fn(),
  refreshAll: vi.fn(),
};

const mockAnnualIncomeEntries = ref<any[]>([]);
const mockAnnualExpenseEntries = ref<any[]>([]);
const mockAnnualIncomeLoadAll = vi.fn();
const mockAnnualExpenseLoadAll = vi.fn();

vi.mock('vue-router', () => ({
  useRoute: () => mockRoute,
  RouterLink: defineComponent({
    name: 'RouterLink',
    props: { to: { type: [String, Object], required: false, default: '' } },
    template: '<a><slot /></a>',
  }),
}));

vi.mock('@/domains/net-worth', () => ({
  useNetWorthStore: () => mockNetWorthStore,
}));

vi.mock('@/domains/budget/annual-entries', () => ({
  useAnnualIncomeStore: () => ({
    entries: mockAnnualIncomeEntries,
    loadAll: mockAnnualIncomeLoadAll,
  }),
  useAnnualExpenseStore: () => ({
    entries: mockAnnualExpenseEntries,
    loadAll: mockAnnualExpenseLoadAll,
  }),
}));

describe('GuidePhaseDetailView (fase 2)', () => {
  beforeEach(() => {
    mockRoute.params.phaseId = '2';
    mockNetWorthStore.loading = false;
    mockNetWorthStore.error = null;
    mockNetWorthStore.fetchSettings.mockReset();
    mockNetWorthStore.refreshAll.mockReset();
    mockAnnualIncomeLoadAll.mockReset();
    mockAnnualExpenseLoadAll.mockReset();
    mockNetWorthStore.liabilities = [
      {
        id: 1,
        is_active: true,
        amount_base: '10000',
        annual_interest_tae: '3.5',
        monthly_payment_amount: '200',
      },
    ];
    mockAnnualIncomeEntries.value = [
      { incomeType: 'recurrent', amountAnnual: 30000 },
      { incomeType: 'one_off', amountAnnual: 5000 },
    ];
    mockAnnualExpenseEntries.value = [
      { category: 'consumption_expenses', expenseType: 'recurrent', amountAnnual: 17100 },
      { category: 'savings_allocation', expenseType: 'recurrent', amountAnnual: 3000 },
      { category: 'financial_investments', expenseType: 'recurrent', amountAnnual: 6000 },
      { category: 'tangible_assets', expenseType: 'recurrent', amountAnnual: 300 },
      { category: 'real_estate_assets', expenseType: 'recurrent', amountAnnual: 1200 },
      { category: 'consumption_expenses', expenseType: 'one_off', amountAnnual: 20000 },
    ];
  });

  it('renders phase 2 summary, operational score and savings distribution info', async () => {
    const wrapper = mount(GuidePhaseDetailView);
    await nextTick();

    expect(wrapper.text()).toContain('Tension de caja');
    expect(wrapper.text()).toContain('Ingresos recurrentes anuales');
    expect(wrapper.text()).toContain('Flujo anual total');
    expect(wrapper.text()).toContain('Distribucion del ahorro');
    expect(wrapper.text()).toContain('% inversiones / ingresos recurrentes');
    expect(wrapper.text()).toContain('Colchon mensual tras cargas temporales');
    expect(wrapper.text()).toContain('Año con eventos extraordinarios');

    expect(mockNetWorthStore.fetchSettings).toHaveBeenCalledTimes(1);
    expect(mockNetWorthStore.refreshAll).toHaveBeenCalledTimes(1);
    expect(mockAnnualIncomeLoadAll).toHaveBeenCalledTimes(1);
    expect(mockAnnualExpenseLoadAll).toHaveBeenCalledTimes(1);
  });

  it('omits warning and monthly capacity detail when recurrent income is missing', async () => {
    mockAnnualIncomeEntries.value = [];
    mockAnnualExpenseEntries.value = [
      { category: 'consumption_expenses', expenseType: 'recurrent', amountAnnual: 500 },
    ];

    const wrapper = mount(GuidePhaseDetailView);
    await nextTick();

    expect(wrapper.text()).toContain('Tension de caja');
    expect(wrapper.text()).not.toContain('Capacidad de asignacion recurrente mensual');
    expect(wrapper.text()).not.toContain('Año con eventos extraordinarios');
  });
});

describe('GuidePhaseDetailView (fase 3)', () => {
  beforeEach(() => {
    mockRoute.params.phaseId = '3';
    mockNetWorthStore.loading = false;
    mockNetWorthStore.error = null;
    mockNetWorthStore.fetchSettings.mockReset();
    mockNetWorthStore.refreshAll.mockReset();
    mockAnnualIncomeLoadAll.mockReset();
    mockAnnualExpenseLoadAll.mockReset();
    mockNetWorthStore.assets = [
      {
        id: 1,
        is_active: true,
        category: 'cash',
        subcategory: 'bank_account',
        amount_base: '6000',
      },
      { id: 2, is_active: true, category: 'investments', subcategory: 'etfs', amount_base: '4000' },
      {
        id: 3,
        is_active: true,
        category: 'real_estate',
        subcategory: 'primary_home',
        amount_base: '90000',
      },
    ];
    mockNetWorthStore.liabilities = [];
    mockNetWorthStore.summary = {
      ...mockNetWorthStore.summary,
      total_assets: '100000',
      total_liabilities: '0',
      net_worth: '100000',
      liabilities_unbacked: '0',
      assets_by_category: { cash: '6000', investments: '4000', real_estate: '90000' },
      liabilities_by_category: {},
    } as any;
    mockAnnualIncomeEntries.value = [];
    mockAnnualExpenseEntries.value = [
      {
        category: 'consumption_expenses',
        expenseType: 'recurrent',
        timeProfile: 'structural_recurrent',
        cashflowRole: 'operating',
        amountAnnual: 12000,
      },
      {
        category: 'consumption_expenses',
        expenseType: 'recurrent',
        timeProfile: 'term_recurrent',
        cashflowRole: 'temporary_commitment',
        amountAnnual: 2400,
      },
    ];
  });

  it('renders phase 3 emergency-fund diagnostics and loads expense context', async () => {
    const wrapper = mount(GuidePhaseDetailView);
    await nextTick();

    expect(wrapper.text()).toContain('Fase 3');
    expect(wrapper.text()).toContain('Fondo de emergencia');
    expect(wrapper.text()).toContain('Cobertura del colchón');
    expect(wrapper.text()).toContain('Calidad de liquidez');
    expect(wrapper.text()).toContain('Meses de gasto base cubiertos');
    expect(wrapper.text()).toContain('Liquidez util para emergencia');

    expect(mockNetWorthStore.fetchSettings).toHaveBeenCalledTimes(1);
    expect(mockNetWorthStore.refreshAll).toHaveBeenCalledTimes(1);
    expect(mockAnnualExpenseLoadAll).toHaveBeenCalledTimes(1);
    expect(mockAnnualIncomeLoadAll).toHaveBeenCalledTimes(0);
  });
});
