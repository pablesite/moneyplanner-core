/** @vitest-environment jsdom */
import { defineComponent } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import BudgetDashboardView from '../BudgetDashboardView.vue';

const currentYear = new Date().getFullYear();
const currentMonth = new Date().getMonth() + 1;

const mockUseRoute = vi.fn(() => ({ name: 'budget', path: '/presupuesto' }));
const mockUseRouter = vi.fn(() => ({ push: vi.fn() }));
const mockCoreApiGet = vi.hoisted(() => vi.fn());
const mockCoreApiPost = vi.hoisted(() => vi.fn());
const mockCoreApiPatch = vi.hoisted(() => vi.fn());
const mockCoreApiDelete = vi.hoisted(() => vi.fn());
const mockIncomeStore = vi.hoisted(() => ({
  entries: { value: [] as unknown[] },
  totalAnnual: { value: 0 },
  loading: { value: false },
  error: { value: null as string | null },
  loadAll: vi.fn(async () => undefined),
}));
const mockExpenseStore = vi.hoisted(() => ({
  entries: { value: [] as unknown[] },
  totalAnnual: { value: 0 },
  loading: { value: false },
  error: { value: null as string | null },
  loadAll: vi.fn(async () => undefined),
}));
const mockAccountingApi = vi.hoisted(() => ({
  getMonthlySummary: vi.fn(async () => ({ data: { fiscal_year: currentYear, months: [] } })),
  getTransactions: vi.fn(async () => ({ data: [] })),
  getBudgetSuggestions: vi.fn(async () => ({
    data: {
      fiscal_year: currentYear,
      lookback_years: 2,
      window_months: 24,
      income: { series: [], categories: [], subcategories: [] },
      expense: { series: [], categories: [], subcategories: [] },
      method_note: '',
    },
  })),
}));
const mockDataInputPage = vi.hoisted(() => ({
  fiscalYear: { value: new Date().getFullYear() },
  showIncomeModal: { value: false },
  showExpenseModal: { value: false },
  incomeModalTitle: { value: 'Nuevo ingreso' },
  expenseModalTitle: { value: 'Nuevo gasto' },
  annualIncomeForm: {},
  annualExpenseForm: {},
  annualIncomeLoading: { value: false },
  annualExpenseLoading: { value: false },
  incomeSubmitLabel: { value: 'Guardar ingreso' },
  expenseSubmitLabel: { value: 'Guardar gasto' },
  incomeCategories: [{ value: 'salary', label: 'Salario' }],
  expenseCategories: [
    { value: 'consumption_expenses', label: 'Gastos' },
    { value: 'financial_investments', label: 'Inversion financiera' },
  ],
  annualSubcategoryOptions: { value: [{ value: 'employee_salary', label: 'Nomina' }] },
  annualExpenseSubcategoryOptions: { value: [{ value: 'living_expenses', label: 'Alimentacion' }] },
  showOwnerField: { value: false },
  ownerOptions: { value: [] },
  incomeTimeProfileOptions: { value: [{ value: 'structural_recurrent', label: 'Recurrente' }] },
  incomeCashflowRoleOptions: [{ value: 'operating', label: 'Operativo' }],
  annualEventGroupOptions: { value: [] },
  incomeAmountInputPlaceholder: { value: 'Importe anual' },
  expenseAmountInputPlaceholder: { value: 'Importe anual' },
  expenseTimeProfileOptions: [{ value: 'structural_recurrent', label: 'Recurrente' }],
  filteredExpenseCashflowRoleOptions: { value: [{ value: 'operating', label: 'Operativo' }] },
  showExpenseCashflowRoleField: { value: true },
  editingSystemGeneratedLiabilityExpense: { value: false },
  expenseBulkEditHint: { value: '' },
  openIncomeModal: vi.fn(),
  openExpenseModal: vi.fn(),
  patchAnnualIncomeForm: vi.fn(),
  patchAnnualExpenseForm: vi.fn(),
  closeIncomeModal: vi.fn(),
  closeExpenseModal: vi.fn(),
  submitAnnualIncome: vi.fn(),
  submitAnnualExpense: vi.fn(),
  removeAnnualIncome: vi.fn(async () => undefined),
  removeAnnualExpense: vi.fn(async () => undefined),
}));

vi.mock('vue-router', () => ({
  useRoute: () => mockUseRoute(),
  useRouter: () => mockUseRouter(),
}));

vi.mock('@/lib/api', () => ({
  coreApi: {
    get: mockCoreApiGet,
    post: mockCoreApiPost,
    patch: mockCoreApiPatch,
    delete: mockCoreApiDelete,
  },
}));

vi.mock('@/domains/accounting', () => ({
  coreAccountingApi: mockAccountingApi,
}));

vi.mock('@/domains/data-input', () => ({
  incomeCategories: [
    { value: 'salary', label: 'Salario' },
    { value: 'capital_gains', label: 'Ganancias de capital' },
  ],
  incomeSubcategories: [
    { category: 'salary', value: 'employee_salary', label: 'Nomina' },
    {
      category: 'capital_gains',
      value: 'sale_financial_assets',
      label: 'Venta de activos financieros',
    },
  ],
  expenseCategories: [{ value: 'consumption_expenses', label: 'Gastos' }],
  expenseSubcategories: [
    { category: 'consumption_expenses', value: 'living_expenses', label: 'Alimentacion' },
    {
      category: 'financial_investments',
      value: 'deposits_fixed_income',
      label: 'Depositos / renta fija',
    },
  ],
  AnnualEntryModalForm: defineComponent({
    name: 'AnnualEntryModalForm',
    template: '<div />',
  }),
  effectiveAnnualAmountForEntry: (entry: {
    amountAnnual: number;
    amountInputPeriod?: 'annual' | 'monthly';
    timeProfile?: string;
    termEndMonth?: number | null;
    termEndYear?: number | null;
    fiscalYear?: number | null;
  }) => {
    const annual = Number(entry.amountAnnual ?? 0);
    if (
      entry.amountInputPeriod === 'monthly' &&
      entry.timeProfile === 'term_recurrent' &&
      entry.fiscalYear != null &&
      (entry.termEndYear == null || entry.termEndYear === entry.fiscalYear)
    ) {
      return Math.round(((annual * Number(entry.termEndMonth ?? 12)) / 12) * 100) / 100;
    }
    return annual;
  },
  normalizeExpenseTaxonomy: (category: string, subcategory: string) => ({
    category,
    subcategory:
      category === 'financial_investments' && subcategory === 'index_funds_etf'
        ? 'etf_indexed'
        : subcategory,
  }),
  useAnnualIncomeStore: () => mockIncomeStore,
  useAnnualExpenseStore: () => mockExpenseStore,
}));
vi.mock('@/views/data-input/useDataInputPage', () => ({
  useDataInputPage: () => mockDataInputPage,
}));

function makeMonthlySummary(executed = '0.00', overrides: Record<string, unknown> = {}) {
  return {
    fiscal_year: currentYear,
    planned_total: '12000.00',
    executed_total: executed,
    pending_total: '0.00',
    variance_total: '0.00',
    completion_ratio: 0,
    months_with_checkins: 0,
    has_executed_data: executed !== '0.00',
    months: [
      {
        month: currentMonth,
        planned: '1000.00',
        executed,
        pending: '0.00',
        completion_ratio: 0,
        checkins_confirmed: 0,
        checkins_expected: 1,
      },
    ],
    ...overrides,
  };
}

function makeLiquiditySummary(overrides: Record<string, unknown> = {}) {
  return {
    fiscal_year: currentYear,
    month: currentMonth,
    base_currency: 'EUR',
    planned_total: '0.00',
    executed_total: '0.00',
    deviation_total: '0.00',
    completion_ratio: 0,
    checkins_confirmed: 0,
    checkins_expected: 0,
    rows: [],
    ...overrides,
  };
}

function configureCoreApi(overrides?: {
  incomeCheckins?: unknown[];
  expenseCheckins?: unknown[];
  assets?: unknown[];
  incomeSummaryExecuted?: string;
  expenseSummaryExecuted?: string;
  incomeSummary?: Record<string, unknown>;
  expenseSummary?: Record<string, unknown>;
  liquiditySummary?: Record<string, unknown>;
}) {
  mockCoreApiGet.mockImplementation(async (url: string) => {
    if (url === '/api/budget/annual-income/monthly-summary/') {
      return {
        data: overrides?.incomeSummary ?? makeMonthlySummary(overrides?.incomeSummaryExecuted),
      };
    }
    if (url === '/api/budget/annual-expense/monthly-summary/') {
      return {
        data: overrides?.expenseSummary ?? makeMonthlySummary(overrides?.expenseSummaryExecuted),
      };
    }
    if (url === '/api/budget/annual-income-checkins/') {
      return { data: overrides?.incomeCheckins ?? [] };
    }
    if (url === '/api/budget/annual-expense-checkins/') {
      return { data: overrides?.expenseCheckins ?? [] };
    }
    if (url === '/api/net-worth/liquidity/monthly-summary/') {
      return { data: makeLiquiditySummary(overrides?.liquiditySummary ?? {}) };
    }
    if (url === '/api/net-worth/assets/') {
      return { data: overrides?.assets ?? [] };
    }
    throw new Error(`Unexpected GET ${url}`);
  });
}

async function openMonthlyStep(wrapper: ReturnType<typeof mount>, label: string) {
  const button = wrapper.findAll('button').find((candidate) => candidate.text().includes(label));
  await button?.trigger('click');
  await flushPromises();
}

function mountMonthlyCloseView() {
  return mount(BudgetDashboardView, {
    props: { mode: 'monthly-close' },
    global: {
      stubs: {
        RouterLink: defineComponent({
          name: 'RouterLink',
          template: '<a><slot /></a>',
        }),
      },
    },
  });
}

function mountBudgetView() {
  return mount(BudgetDashboardView, {
    global: {
      stubs: {
        RouterLink: defineComponent({
          name: 'RouterLink',
          template: '<a><slot /></a>',
        }),
      },
    },
  });
}

describe('BudgetDashboardView', () => {
  beforeEach(() => {
    mockCoreApiGet.mockReset();
    mockCoreApiPost.mockReset();
    mockCoreApiPatch.mockReset();
    mockCoreApiDelete.mockReset();
    mockCoreApiPost.mockResolvedValue({ data: {} });
    mockCoreApiPatch.mockResolvedValue({ data: {} });
    mockCoreApiDelete.mockResolvedValue({ data: {} });
    mockAccountingApi.getMonthlySummary.mockReset();
    mockAccountingApi.getTransactions.mockReset();
    mockAccountingApi.getBudgetSuggestions.mockReset();
    mockIncomeStore.entries.value = [];
    mockIncomeStore.totalAnnual.value = 0;
    mockExpenseStore.entries.value = [];
    mockExpenseStore.totalAnnual.value = 0;
    mockIncomeStore.loadAll.mockClear();
    mockExpenseStore.loadAll.mockClear();
    mockAccountingApi.getBudgetSuggestions.mockResolvedValue({
      data: {
        fiscal_year: currentYear,
        lookback_years: 2,
        window_months: 24,
        income: { series: [], categories: [], subcategories: [] },
        expense: { series: [], categories: [], subcategories: [] },
        method_note: '',
      },
    } as never);
  });

  it('shows ledger liquidity balance without opening manual editing', async () => {
    configureCoreApi({
      liquiditySummary: {
        planned_total: '200.00',
        executed_total: '189.44',
        deviation_total: '-10.56',
        completion_ratio: 1,
        coverage_confirmed: 1,
        coverage_expected: 1,
        ledger_rows_confirmed: 1,
        fallback_rows_confirmed: 0,
        has_ledger_data: true,
        rows: [
          {
            asset_id: 42,
            asset_name: 'Cuenta ledger',
            asset_category: 'cash',
            asset_subcategory: 'bank_account',
            currency: 'EUR',
            planned_closing_balance: '200.00',
            executed_closing_balance: '189.44',
            effective_closing_balance: '189.44',
            deviation: '-10.56',
            planned_closing_balance_base: '200.00',
            executed_closing_balance_base: '189.44',
            effective_closing_balance_base: '189.44',
            deviation_base: '-10.56',
            coverage_source: 'ledger',
            ledger_available: true,
            checkin: null,
          },
        ],
      },
    });
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: { fiscal_year: currentYear, months: [] },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({ data: [] } as never);

    const wrapper = mountMonthlyCloseView();
    await flushPromises();

    expect(wrapper.text()).toContain('Libro contable activo');
    expect(wrapper.text()).toContain('Saldo cierre189,44 EUR');
    expect(wrapper.text()).toContain('Desviación -10,56 EUR');
    expect(wrapper.text()).toContain('Ajustar manualmente');
    expect(wrapper.find('input[placeholder="Saldo real"]').exists()).toBe(false);
    expect(wrapper.find('.ui-budget-checkin-confirm').exists()).toBe(false);
  });

  it('opens ledger liquidity manual editing without persisting until the user confirms', async () => {
    configureCoreApi({
      liquiditySummary: {
        planned_total: '200.00',
        executed_total: '189.44',
        deviation_total: '-10.56',
        completion_ratio: 1,
        rows: [
          {
            asset_id: 42,
            asset_name: 'Cuenta ledger',
            asset_category: 'cash',
            asset_subcategory: 'bank_account',
            currency: 'EUR',
            planned_closing_balance: '200.00',
            executed_closing_balance: '189.44',
            effective_closing_balance: '189.44',
            deviation: '-10.56',
            planned_closing_balance_base: '200.00',
            executed_closing_balance_base: '189.44',
            effective_closing_balance_base: '189.44',
            deviation_base: '-10.56',
            coverage_source: 'ledger',
            ledger_available: true,
            checkin: null,
          },
        ],
      },
    });
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: { fiscal_year: currentYear, months: [] },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({ data: [] } as never);

    const wrapper = mountMonthlyCloseView();
    await flushPromises();

    const adjustButton = wrapper
      .findAll('button')
      .find((candidate) => candidate.text().includes('Ajustar manualmente'));
    await adjustButton?.trigger('click');
    await flushPromises();

    expect(mockCoreApiPost).not.toHaveBeenCalled();
    const input = wrapper.find('input[placeholder="Saldo real"]');
    expect((input.element as HTMLInputElement).value).toBe('189.44');

    await input.setValue('190,50');
    await input.trigger('blur');
    await flushPromises();

    expect(mockCoreApiPost).toHaveBeenCalledWith(
      '/api/net-worth/liquidity-checkins/',
      expect.objectContaining({
        asset_id: 42,
        status: 'adjusted',
        closing_balance_real: '190.50',
      }),
    );
  });

  it('removes a ledger liquidity manual override when returning to the ledger balance', async () => {
    configureCoreApi({
      liquiditySummary: {
        planned_total: '200.00',
        executed_total: '190.50',
        deviation_total: '-9.50',
        completion_ratio: 1,
        rows: [
          {
            asset_id: 42,
            asset_name: 'Cuenta ledger',
            asset_category: 'cash',
            asset_subcategory: 'bank_account',
            currency: 'EUR',
            planned_closing_balance: '200.00',
            executed_closing_balance: '190.50',
            effective_closing_balance: '189.44',
            deviation: '-9.50',
            planned_closing_balance_base: '200.00',
            executed_closing_balance_base: '190.50',
            effective_closing_balance_base: '189.44',
            deviation_base: '-9.50',
            coverage_source: 'checkin',
            ledger_available: true,
            checkin: {
              id: 77,
              status: 'adjusted',
              closing_balance_real: '190.50',
              note: '',
              confirmed_at: null,
              updated_at: null,
            },
          },
        ],
      },
    });
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: { fiscal_year: currentYear, months: [] },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({ data: [] } as never);

    const wrapper = mountMonthlyCloseView();
    await flushPromises();

    const relockButton = wrapper
      .findAll('button')
      .find((candidate) => candidate.text().includes('Usar libro'));
    await relockButton?.trigger('click');
    await flushPromises();

    expect(mockCoreApiDelete).toHaveBeenCalledWith('/api/net-worth/liquidity-checkins/77/');
  });

  it('uses ledger coverage for income rows and disables legacy check-in editing', async () => {
    mockIncomeStore.entries.value = [
      {
        id: 1,
        name: 'Nomina',
        category: 'salary',
        subcategory: 'employee_salary',
        owner: '',
        incomeType: 'recurrent',
        timeProfile: 'structural_recurrent',
        cashflowRole: 'operating',
        eventGroup: '',
        targetMonth: null,
        termEndMonth: null,
        termEndYear: null,
        amountInputPeriod: 'annual',
        amountAnnual: 12000,
        fiscalYear: currentYear,
        currency: 'EUR',
        notes: '',
        createdAt: '',
      },
    ];
    mockIncomeStore.totalAnnual.value = 12000;
    configureCoreApi();
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: {
        fiscal_year: currentYear,
        months: [
          {
            month: currentMonth,
            income_total: '1000.00',
            expense_total: '0.00',
            uncategorized_total: '0.00',
          },
        ],
      },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({
      data: {
        results: [
          {
            id: 10,
            booking_date: `${currentYear}-03-15`,
            value_date: `${currentYear}-03-15`,
            description: 'Nomina',
            status: 'posted',
            origin: 'manual',
            notes: '',
            created_at: '',
            updated_at: '',
            entries: [
              {
                id: 101,
                account_id: 1,
                account_name: 'Cuenta corriente',
                side: 'credit',
                amount: '1000.00',
                currency: 'EUR',
                flow_family: 'income',
                category_key: 'salary',
                subcategory_key: 'employee_salary',
                annual_income_entry_id: null,
                annual_expense_entry_id: null,
                asset_id: null,
                liability_id: null,
                notes: '',
                created_at: '',
                updated_at: '',
              },
            ],
          },
        ],
        next_cursor: null,
        total_count: 1,
      },
    } as never);

    const wrapper = mountMonthlyCloseView();
    await flushPromises();
    await openMonthlyStep(wrapper, 'Ingresos');

    expect(wrapper.text()).toContain('1 via ledger');
    expect(wrapper.text()).not.toContain('Movimientos');
    expect(wrapper.text()).not.toContain('Ledger categorizado');
    expect(wrapper.text()).not.toContain('Ledger subcategoría');
    const input = wrapper.find('input[placeholder="Importe ejecutado"]');
    expect(input.attributes('disabled')).toBeDefined();
  });

  it('keeps legacy expense fallback editable when there is no ledger coverage', async () => {
    mockExpenseStore.entries.value = [
      {
        id: 2,
        sourceLiabilityId: null,
        isSystemGenerated: false,
        name: 'Supermercado',
        category: 'consumption_expenses',
        subcategory: 'living_expenses',
        owner: '',
        expenseType: 'recurrent',
        timeProfile: 'structural_recurrent',
        cashflowRole: 'operating',
        eventGroup: '',
        targetMonth: null,
        termEndMonth: null,
        termEndYear: null,
        amountInputPeriod: 'annual',
        amountAnnual: 6000,
        fiscalYear: currentYear,
        currency: 'EUR',
        notes: '',
        createdAt: '',
      },
    ];
    mockExpenseStore.totalAnnual.value = 6000;
    configureCoreApi({
      expenseCheckins: [
        {
          id: 7,
          annual_expense_entry_id: 2,
          fiscal_year: currentYear,
          month: currentMonth,
          status: 'confirmed',
          executed_amount: '500.00',
          note: '',
          confirmed_at: null,
          created_at: '',
          updated_at: '',
        },
      ],
      expenseSummaryExecuted: '500.00',
    });
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: { fiscal_year: currentYear, months: [] },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({ data: [] } as never);

    const wrapper = mountMonthlyCloseView();
    await flushPromises();
    await openMonthlyStep(wrapper, 'Gastos');

    expect(wrapper.text()).toContain('1 via fallback legacy');
    const input = wrapper.find('input[placeholder="Importe ejecutado"]');
    expect(input.attributes('disabled')).toBeUndefined();
  });

  it('surfaces pendiente clasificar when categorized ledger is ambiguous across multiple lines', async () => {
    mockIncomeStore.entries.value = [
      {
        id: 1,
        name: 'Nomina A',
        category: 'salary',
        subcategory: 'employee_salary',
        owner: '',
        incomeType: 'recurrent',
        timeProfile: 'structural_recurrent',
        cashflowRole: 'operating',
        eventGroup: '',
        targetMonth: null,
        termEndMonth: null,
        termEndYear: null,
        amountInputPeriod: 'annual',
        amountAnnual: 12000,
        fiscalYear: currentYear,
        currency: 'EUR',
        notes: '',
        createdAt: '',
      },
      {
        id: 2,
        name: 'Nomina B',
        category: 'salary',
        subcategory: 'employee_salary',
        owner: '',
        incomeType: 'recurrent',
        timeProfile: 'structural_recurrent',
        cashflowRole: 'operating',
        eventGroup: '',
        targetMonth: null,
        termEndMonth: null,
        termEndYear: null,
        amountInputPeriod: 'annual',
        amountAnnual: 6000,
        fiscalYear: currentYear,
        currency: 'EUR',
        notes: '',
        createdAt: '',
      },
    ];
    mockIncomeStore.totalAnnual.value = 18000;
    configureCoreApi();
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: {
        fiscal_year: currentYear,
        months: [
          {
            month: currentMonth,
            income_total: '1500.00',
            expense_total: '0.00',
            uncategorized_total: '0.00',
          },
        ],
      },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({
      data: {
        results: [
          {
            id: 10,
            booking_date: `${currentYear}-03-15`,
            value_date: `${currentYear}-03-15`,
            description: 'Nomina',
            status: 'posted',
            origin: 'manual',
            notes: '',
            created_at: '',
            updated_at: '',
            entries: [
              {
                id: 101,
                account_id: 1,
                account_name: 'Cuenta corriente',
                side: 'credit',
                amount: '1500.00',
                currency: 'EUR',
                flow_family: 'income',
                category_key: 'salary',
                subcategory_key: 'employee_salary',
                annual_income_entry_id: null,
                annual_expense_entry_id: null,
                asset_id: null,
                liability_id: null,
                notes: '',
                created_at: '',
                updated_at: '',
              },
            ],
          },
        ],
        next_cursor: null,
        total_count: 1,
      },
    } as never);

    const wrapper = mountMonthlyCloseView();
    await flushPromises();
    await openMonthlyStep(wrapper, 'Ingresos');

    expect(wrapper.text()).toContain('Pendiente clasificar');
    expect(wrapper.text()).toContain('Nómina');
    expect(wrapper.text()).toContain('2 líneas agrupadas');
    expect(wrapper.text()).not.toContain('Nomina A');
    expect(wrapper.text()).not.toContain('Nomina B');
  });

  it('renders contextual management actions in budget detail rows', async () => {
    mockIncomeStore.entries.value = [
      {
        id: 1,
        name: 'Nomina',
        category: 'salary',
        subcategory: 'employee_salary',
        owner: '',
        incomeType: 'recurrent',
        timeProfile: 'structural_recurrent',
        cashflowRole: 'operating',
        eventGroup: '',
        targetMonth: null,
        termEndMonth: null,
        termEndYear: null,
        amountInputPeriod: 'annual',
        amountAnnual: 12000,
        fiscalYear: currentYear,
        currency: 'EUR',
        notes: '',
        createdAt: '',
      },
    ];
    mockIncomeStore.totalAnnual.value = 12000;
    configureCoreApi();
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: { fiscal_year: currentYear, months: [] },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({ data: [] } as never);

    const wrapper = mountBudgetView();
    await flushPromises();

    const expenseSection = wrapper.find('.ui-budget-section-expense');
    expect(expenseSection.text()).toContain('Previsto vs Ejecutado acumulado');
    expect(expenseSection.text()).toContain('250,00 EUR ejecutado');

    const toggleDetail = wrapper
      .findAll('button')
      .find((candidate) => candidate.text().includes('Ver detalle'));
    await toggleDetail?.trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('Gestionar subcategoría');
  });

  it('opens budget suggestions inside a modal when user asks for them', async () => {
    configureCoreApi();
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: { fiscal_year: currentYear, months: [] },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({ data: [] } as never);

    const wrapper = mountBudgetView();
    await flushPromises();

    expect(
      wrapper
        .findAll('button')
        .some((candidate) => candidate.attributes('aria-label') === 'Ver sugerencias'),
    ).toBe(true);
    expect(wrapper.text()).not.toContain('Sugerencias desde histórico ledger');
    expect(wrapper.text()).not.toContain(
      'Sin cobertura ledger por subcategoría para sugerir ajustes todavía.',
    );

    const toggleSuggestions = wrapper
      .findAll('button')
      .find((candidate) => candidate.attributes('aria-label') === 'Ver sugerencias');
    await toggleSuggestions?.trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('Sugerencias desde histórico ledger');
    expect(wrapper.text()).toContain('Cerrar');
    expect(wrapper.text()).toContain('Sin cobertura ledger por subcategoría para sugerir ajustes');
  });

  it('shows ledger-backed YTD execution in annual expense detail', async () => {
    mockExpenseStore.entries.value = [
      {
        id: 2,
        sourceLiabilityId: null,
        isSystemGenerated: false,
        name: 'Supermercado',
        category: 'consumption_expenses',
        subcategory: 'living_expenses',
        owner: '',
        expenseType: 'recurrent',
        timeProfile: 'structural_recurrent',
        cashflowRole: 'operating',
        eventGroup: '',
        targetMonth: null,
        termEndMonth: null,
        termEndYear: null,
        amountInputPeriod: 'annual',
        amountAnnual: 6000,
        fiscalYear: currentYear,
        currency: 'EUR',
        notes: '',
        createdAt: '',
      },
    ];
    mockExpenseStore.totalAnnual.value = 6000;
    configureCoreApi({ expenseSummaryExecuted: '250.00' });
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: {
        fiscal_year: currentYear,
        months: [
          {
            month: currentMonth,
            income_total: '0.00',
            expense_total: '250.00',
            uncategorized_total: '0.00',
          },
        ],
      },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({
      data: {
        results: [
          {
            id: 10,
            booking_date: `${currentYear}-${String(currentMonth).padStart(2, '0')}-15`,
            value_date: `${currentYear}-${String(currentMonth).padStart(2, '0')}-15`,
            description: 'Supermercado',
            status: 'posted',
            origin: 'manual',
            notes: '',
            created_at: '',
            updated_at: '',
            entries: [
              {
                id: 101,
                account_id: 1,
                account_name: 'Cuenta corriente',
                side: 'debit',
                amount: '250.00',
                currency: 'EUR',
                flow_family: 'expense',
                category_key: 'consumption_expenses',
                subcategory_key: 'living_expenses',
                annual_income_entry_id: null,
                annual_expense_entry_id: null,
                asset_id: null,
                liability_id: null,
                notes: '',
                created_at: '',
                updated_at: '',
              },
            ],
          },
        ],
        next_cursor: null,
        total_count: 1,
      },
    } as never);

    const wrapper = mountBudgetView();
    await flushPromises();

    const toggleDetail = wrapper
      .findAll('button')
      .find((candidate) => candidate.text().includes('Ver detalle'));
    await toggleDetail?.trigger('click');
    await flushPromises();

    expect(mockAccountingApi.getTransactions).toHaveBeenCalledWith(
      expect.objectContaining({
        year: currentYear,
        status: 'posted',
        page_size: 200,
      }),
    );
    expect(mockAccountingApi.getTransactions).not.toHaveBeenCalledWith(
      expect.objectContaining({ month: currentMonth }),
    );
    expect(wrapper.text()).toContain('250,00 EUR');
  });

  it('shows unbudgeted detected expense rows with contextual CTA', async () => {
    configureCoreApi({
      expenseSummary: {
        fiscal_year: currentYear,
        planned_total: '0.00',
        executed_total: '40.00',
        executed_budgeted_total: '0.00',
        executed_unbudgeted_total: '40.00',
        pending_total: '0.00',
        variance_total: '40.00',
        completion_ratio: 0,
        months_with_checkins: 0,
        has_executed_data: true,
        months: [
          {
            month: currentMonth,
            planned: '0.00',
            executed: '40.00',
            executed_budgeted: '0.00',
            executed_unbudgeted: '40.00',
            executed_total: '40.00',
            pending: '0.00',
            completion_ratio: 0,
            checkins_confirmed: 0,
            checkins_expected: 0,
          },
        ],
        expense_execution_breakdown: {
          categories: [
            {
              category: 'consumption_expenses',
              planned_total: '0.00',
              executed_budgeted_total: '0.00',
              executed_unbudgeted_total: '40.00',
              executed_total: '40.00',
              has_budgeted_lines: false,
              has_unbudgeted_execution: true,
              subcategories: [
                {
                  subcategory: 'health_wellbeing',
                  planned_total: '0.00',
                  executed_budgeted_total: '0.00',
                  executed_unbudgeted_total: '40.00',
                  executed_total: '40.00',
                  has_budgeted_line: false,
                  has_unbudgeted_execution: true,
                  months: Array.from({ length: 12 }, (_, idx) => ({
                    month: idx + 1,
                    planned: '0.00',
                    executed_budgeted: '0.00',
                    executed_unbudgeted: idx + 1 === currentMonth ? '40.00' : '0.00',
                    executed_total: idx + 1 === currentMonth ? '40.00' : '0.00',
                  })),
                },
              ],
            },
          ],
          executed_budgeted_total: '0.00',
          executed_unbudgeted_total: '40.00',
          executed_total: '40.00',
        },
      },
    });
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: { fiscal_year: currentYear, months: [] },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({ data: [] } as never);

    const wrapper = mountBudgetView();
    await flushPromises();

    const toggleDetail = wrapper
      .findAll('button')
      .find((candidate) => candidate.text().includes('Ver detalle'));
    await toggleDetail?.trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('Fuera de presupuesto (YTD)');
    expect(wrapper.text()).toContain('Detectado en movimientos');
    expect(wrapper.text()).toContain('Añadir al presupuesto');
  });

  it('shows unbudgeted income split and detected income rows', async () => {
    configureCoreApi({
      incomeSummary: {
        fiscal_year: currentYear,
        planned_total: '1200.00',
        executed_total: '165.00',
        executed_budgeted_total: '120.00',
        executed_unbudgeted_total: '45.00',
        pending_total: '0.00',
        variance_total: '-1035.00',
        completion_ratio: 1,
        months_with_checkins: 0,
        has_executed_data: true,
        months: [
          {
            month: currentMonth,
            planned: '100.00',
            executed: '165.00',
            executed_budgeted: '120.00',
            executed_unbudgeted: '45.00',
            executed_total: '165.00',
            pending: '0.00',
            completion_ratio: 1,
            checkins_confirmed: 1,
            checkins_expected: 1,
          },
        ],
        income_execution_breakdown: {
          categories: [
            {
              category: 'salary',
              planned_total: '100.00',
              executed_budgeted_total: '120.00',
              executed_unbudgeted_total: '45.00',
              executed_total: '165.00',
              has_budgeted_lines: true,
              has_unbudgeted_execution: true,
              subcategories: [
                {
                  subcategory: 'employee_salary',
                  planned_total: '100.00',
                  executed_budgeted_total: '120.00',
                  executed_unbudgeted_total: '0.00',
                  executed_total: '120.00',
                  has_budgeted_line: true,
                  has_unbudgeted_execution: false,
                  months: Array.from({ length: 12 }, (_, idx) => ({
                    month: idx + 1,
                    planned: idx + 1 === currentMonth ? '100.00' : '0.00',
                    executed_budgeted: idx + 1 === currentMonth ? '120.00' : '0.00',
                    executed_unbudgeted: '0.00',
                    executed_total: idx + 1 === currentMonth ? '120.00' : '0.00',
                  })),
                },
                {
                  subcategory: 'social_benefits',
                  planned_total: '0.00',
                  executed_budgeted_total: '0.00',
                  executed_unbudgeted_total: '45.00',
                  executed_total: '45.00',
                  has_budgeted_line: false,
                  has_unbudgeted_execution: true,
                  months: Array.from({ length: 12 }, (_, idx) => ({
                    month: idx + 1,
                    planned: '0.00',
                    executed_budgeted: '0.00',
                    executed_unbudgeted: idx + 1 === currentMonth ? '45.00' : '0.00',
                    executed_total: idx + 1 === currentMonth ? '45.00' : '0.00',
                  })),
                },
              ],
            },
          ],
          executed_budgeted_total: '120.00',
          executed_unbudgeted_total: '45.00',
          executed_total: '165.00',
        },
      },
    });
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: { fiscal_year: currentYear, months: [] },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({ data: [] } as never);

    const wrapper = mountBudgetView();
    await flushPromises();

    const incomeSection = wrapper.find('.ui-budget-section-income');
    expect(incomeSection.text()).toContain('Previsto vs Ejecutado acumulado');
    expect(incomeSection.text()).toContain('165,00 EUR ejecutado');
    expect(incomeSection.text()).toContain('En presupuesto (YTD)');
    expect(incomeSection.text()).toContain('Fuera de presupuesto (YTD)');
    expect(incomeSection.text()).toContain('45,00 EUR');

    const toggleDetail = incomeSection
      .findAll('button')
      .find((candidate) => candidate.text().includes('Ver detalle'));
    await toggleDetail?.trigger('click');
    await flushPromises();

    expect(incomeSection.text()).toContain('Detectado en movimientos');
    expect(incomeSection.text()).toContain('Añadir al presupuesto');
  });

  it('nets only rotatory deposit sales out of the income KPI', async () => {
    mockIncomeStore.entries.value = [
      {
        id: 7,
        name: 'Venta de activos financieros',
        category: 'capital_gains',
        subcategory: 'sale_financial_assets',
        owner: '',
        incomeType: 'recurrent',
        timeProfile: 'structural_recurrent',
        cashflowRole: 'asset_sale',
        eventGroup: '',
        targetMonth: null,
        termEndMonth: null,
        termEndYear: null,
        amountInputPeriod: 'annual',
        amountAnnual: 1200,
        fiscalYear: currentYear,
        currency: 'EUR',
        notes: '',
        createdAt: '',
      },
    ];
    mockIncomeStore.totalAnnual.value = 1200;
    configureCoreApi({
      assets: [{ id: 101, category: 'investments', subcategory: 'deposits' }],
      incomeSummary: {
        fiscal_year: currentYear,
        planned_total: '1200.00',
        executed_total: '1000.00',
        executed_budgeted_total: '1000.00',
        executed_unbudgeted_total: '0.00',
        pending_total: '0.00',
        variance_total: '-200.00',
        completion_ratio: 1,
        months_with_checkins: 0,
        has_executed_data: true,
        months: [
          {
            month: currentMonth,
            planned: '100.00',
            executed: '1000.00',
            executed_budgeted: '1000.00',
            executed_unbudgeted: '0.00',
            executed_total: '1000.00',
            pending: '0.00',
            completion_ratio: 1,
            checkins_confirmed: 1,
            checkins_expected: 1,
          },
        ],
        income_execution_breakdown: {
          categories: [
            {
              category: 'capital_gains',
              planned_total: '1200.00',
              executed_budgeted_total: '1000.00',
              executed_unbudgeted_total: '0.00',
              executed_total: '1000.00',
              has_budgeted_lines: true,
              has_unbudgeted_execution: false,
              subcategories: [
                {
                  subcategory: 'sale_financial_assets',
                  planned_total: '1200.00',
                  executed_budgeted_total: '1000.00',
                  executed_unbudgeted_total: '0.00',
                  executed_total: '1000.00',
                  has_budgeted_line: true,
                  has_unbudgeted_execution: false,
                  months: Array.from({ length: 12 }, (_, idx) => ({
                    month: idx + 1,
                    planned: idx + 1 === currentMonth ? '100.00' : '100.00',
                    executed_budgeted: idx + 1 === currentMonth ? '1000.00' : '0.00',
                    executed_unbudgeted: '0.00',
                    executed_total: idx + 1 === currentMonth ? '1000.00' : '0.00',
                  })),
                },
              ],
            },
          ],
          executed_budgeted_total: '1000.00',
          executed_unbudgeted_total: '0.00',
          executed_total: '1000.00',
        },
      },
      expenseSummary: {
        fiscal_year: currentYear,
        planned_total: '0.00',
        executed_total: '1000.00',
        executed_budgeted_total: '0.00',
        executed_unbudgeted_total: '1000.00',
        pending_total: '0.00',
        variance_total: '1000.00',
        completion_ratio: 1,
        months_with_checkins: 0,
        has_executed_data: true,
        months: [
          {
            month: currentMonth,
            planned: '0.00',
            executed: '1000.00',
            executed_budgeted: '0.00',
            executed_unbudgeted: '1000.00',
            executed_total: '1000.00',
            pending: '0.00',
            completion_ratio: 1,
            checkins_confirmed: 1,
            checkins_expected: 0,
          },
        ],
        expense_execution_breakdown: {
          categories: [
            {
              category: 'financial_investments',
              planned_total: '0.00',
              executed_budgeted_total: '0.00',
              executed_unbudgeted_total: '1000.00',
              executed_total: '1000.00',
              has_budgeted_lines: false,
              has_unbudgeted_execution: true,
              subcategories: [
                {
                  subcategory: 'deposits_fixed_income',
                  planned_total: '0.00',
                  executed_budgeted_total: '0.00',
                  executed_unbudgeted_total: '1000.00',
                  executed_total: '1000.00',
                  has_budgeted_line: false,
                  has_unbudgeted_execution: true,
                  months: Array.from({ length: 12 }, (_, idx) => ({
                    month: idx + 1,
                    planned: '0.00',
                    executed_budgeted: '0.00',
                    executed_unbudgeted: idx + 1 === currentMonth ? '1000.00' : '0.00',
                    executed_total: idx + 1 === currentMonth ? '1000.00' : '0.00',
                  })),
                },
              ],
            },
          ],
          executed_budgeted_total: '0.00',
          executed_unbudgeted_total: '1000.00',
          executed_total: '1000.00',
        },
      },
    });
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: { fiscal_year: currentYear, months: [] },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({
      data: {
        results: [
          {
            id: 31,
            booking_date: `${currentYear}-${String(currentMonth).padStart(2, '0')}-05`,
            value_date: `${currentYear}-${String(currentMonth).padStart(2, '0')}-05`,
            description: 'Renovacion deposito',
            status: 'posted',
            origin: 'manual',
            member_tag: '',
            ownership_id: null,
            quick_entry_kind: 'investment',
            investment_direction: 'inflow',
            realized_cost_basis: null,
            realized_gain_loss: null,
            activity_kind: 'investment',
            notes: '',
            created_at: '',
            updated_at: '',
            entries: [
              {
                id: 311,
                account_id: 3,
                account_name: 'Depositos',
                side: 'debit',
                amount: '1000.00',
                currency: 'EUR',
                flow_family: 'expense',
                category_key: 'financial_investments',
                subcategory_key: 'deposits_fixed_income',
                annual_income_entry_id: null,
                annual_expense_entry_id: null,
                asset_id: 101,
                liability_id: null,
                notes: '',
                created_at: '',
                updated_at: '',
              },
            ],
          },
          {
            id: 32,
            booking_date: `${currentYear}-${String(currentMonth).padStart(2, '0')}-07`,
            value_date: `${currentYear}-${String(currentMonth).padStart(2, '0')}-07`,
            description: 'Vencimiento deposito',
            status: 'posted',
            origin: 'manual',
            member_tag: '',
            ownership_id: null,
            quick_entry_kind: 'investment',
            investment_direction: 'outflow',
            realized_cost_basis: null,
            realized_gain_loss: null,
            activity_kind: 'investment',
            notes: '',
            created_at: '',
            updated_at: '',
            entries: [
              {
                id: 321,
                account_id: 3,
                account_name: 'Depositos',
                side: 'credit',
                amount: '1000.00',
                currency: 'EUR',
                flow_family: 'income',
                category_key: 'capital_gains',
                subcategory_key: 'sale_financial_assets',
                annual_income_entry_id: null,
                annual_expense_entry_id: null,
                asset_id: 101,
                liability_id: null,
                notes: '',
                created_at: '',
                updated_at: '',
              },
            ],
          },
        ],
        next_cursor: null,
        total_count: 2,
      },
    } as never);

    const wrapper = mountBudgetView();
    await flushPromises();

    const incomeSection = wrapper.find('.ui-budget-section-income');
    expect(incomeSection.text()).toContain(
      'Cambio neto en depósitos aplicado (YTD): -1.000,00 EUR',
    );
    expect(incomeSection.text()).toContain('Cambio neto dep. YTD');
    expect(incomeSection.text()).toContain('0,00 EUR');
  });

  it('keeps non-deposit investment sales on the gross income KPI', async () => {
    mockIncomeStore.entries.value = [
      {
        id: 8,
        name: 'Venta de cripto',
        category: 'capital_gains',
        subcategory: 'sale_financial_assets',
        owner: '',
        incomeType: 'recurrent',
        timeProfile: 'structural_recurrent',
        cashflowRole: 'asset_sale',
        eventGroup: '',
        targetMonth: null,
        termEndMonth: null,
        termEndYear: null,
        amountInputPeriod: 'annual',
        amountAnnual: 1200,
        fiscalYear: currentYear,
        currency: 'EUR',
        notes: '',
        createdAt: '',
      },
    ];
    mockIncomeStore.totalAnnual.value = 1200;
    configureCoreApi({
      assets: [{ id: 202, category: 'investments', subcategory: 'cryptocurrencies' }],
      incomeSummary: {
        fiscal_year: currentYear,
        planned_total: '1200.00',
        executed_total: '1000.00',
        executed_budgeted_total: '1000.00',
        executed_unbudgeted_total: '0.00',
        pending_total: '0.00',
        variance_total: '-200.00',
        completion_ratio: 1,
        months_with_checkins: 0,
        has_executed_data: true,
        months: [
          {
            month: currentMonth,
            planned: '100.00',
            executed: '1000.00',
            executed_budgeted: '1000.00',
            executed_unbudgeted: '0.00',
            executed_total: '1000.00',
            pending: '0.00',
            completion_ratio: 1,
            checkins_confirmed: 1,
            checkins_expected: 1,
          },
        ],
        income_execution_breakdown: {
          categories: [
            {
              category: 'capital_gains',
              planned_total: '1200.00',
              executed_budgeted_total: '1000.00',
              executed_unbudgeted_total: '0.00',
              executed_total: '1000.00',
              has_budgeted_lines: true,
              has_unbudgeted_execution: false,
              subcategories: [
                {
                  subcategory: 'sale_financial_assets',
                  planned_total: '1200.00',
                  executed_budgeted_total: '1000.00',
                  executed_unbudgeted_total: '0.00',
                  executed_total: '1000.00',
                  has_budgeted_line: true,
                  has_unbudgeted_execution: false,
                  months: Array.from({ length: 12 }, (_, idx) => ({
                    month: idx + 1,
                    planned: idx + 1 === currentMonth ? '100.00' : '100.00',
                    executed_budgeted: idx + 1 === currentMonth ? '1000.00' : '0.00',
                    executed_unbudgeted: '0.00',
                    executed_total: idx + 1 === currentMonth ? '1000.00' : '0.00',
                  })),
                },
              ],
            },
          ],
          executed_budgeted_total: '1000.00',
          executed_unbudgeted_total: '0.00',
          executed_total: '1000.00',
        },
      },
    });
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: { fiscal_year: currentYear, months: [] },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({
      data: {
        results: [
          {
            id: 41,
            booking_date: `${currentYear}-${String(currentMonth).padStart(2, '0')}-07`,
            value_date: `${currentYear}-${String(currentMonth).padStart(2, '0')}-07`,
            description: 'Venta cripto',
            status: 'posted',
            origin: 'manual',
            member_tag: '',
            ownership_id: null,
            quick_entry_kind: 'investment',
            investment_direction: 'outflow',
            realized_cost_basis: null,
            realized_gain_loss: null,
            activity_kind: 'investment',
            notes: '',
            created_at: '',
            updated_at: '',
            entries: [
              {
                id: 411,
                account_id: 4,
                account_name: 'Cripto',
                side: 'credit',
                amount: '1000.00',
                currency: 'EUR',
                flow_family: 'income',
                category_key: 'capital_gains',
                subcategory_key: 'sale_financial_assets',
                annual_income_entry_id: null,
                annual_expense_entry_id: null,
                asset_id: 202,
                liability_id: null,
                notes: '',
                created_at: '',
                updated_at: '',
              },
            ],
          },
        ],
        next_cursor: null,
        total_count: 1,
      },
    } as never);

    const wrapper = mountBudgetView();
    await flushPromises();

    const incomeSection = wrapper.find('.ui-budget-section-income');
    expect(incomeSection.text()).not.toContain('Cambio neto en depósitos aplicado');
    expect(incomeSection.text()).not.toContain('Cambio neto dep. YTD');
    expect(incomeSection.text()).toContain('1.000,00 EUR');
  });

  it('updates income evolution executed bars when switching recurrent/one-off filter', async () => {
    mockIncomeStore.entries.value = [
      {
        id: 1,
        name: 'Nomina',
        category: 'salary',
        subcategory: 'employee_salary',
        owner: '',
        incomeType: 'recurrent',
        timeProfile: 'structural_recurrent',
        cashflowRole: 'operating',
        eventGroup: '',
        targetMonth: null,
        termEndMonth: null,
        termEndYear: null,
        amountInputPeriod: 'annual',
        amountAnnual: 12000,
        fiscalYear: currentYear,
        currency: 'EUR',
        notes: '',
        createdAt: '',
      },
      {
        id: 2,
        name: 'Bonus',
        category: 'salary',
        subcategory: 'employee_salary',
        owner: '',
        incomeType: 'one_off',
        timeProfile: 'non_structural_recurrent',
        cashflowRole: 'operating',
        eventGroup: '',
        targetMonth: 1,
        termEndMonth: null,
        termEndYear: null,
        amountInputPeriod: 'annual',
        amountAnnual: 1200,
        fiscalYear: currentYear,
        currency: 'EUR',
        notes: '',
        createdAt: '',
      },
    ];
    mockIncomeStore.totalAnnual.value = 13200;
    configureCoreApi();
    mockAccountingApi.getMonthlySummary.mockResolvedValue({
      data: { fiscal_year: currentYear, months: [] },
    } as never);
    mockAccountingApi.getTransactions.mockResolvedValue({
      data: {
        results: [
          {
            id: 10,
            booking_date: `${currentYear}-${String(currentMonth).padStart(2, '0')}-10`,
            value_date: `${currentYear}-${String(currentMonth).padStart(2, '0')}-10`,
            description: 'Nomina',
            status: 'posted',
            origin: 'manual',
            notes: '',
            created_at: '',
            updated_at: '',
            entries: [
              {
                id: 101,
                account_id: 1,
                account_name: 'Cuenta corriente',
                side: 'credit',
                amount: '1000.00',
                currency: 'EUR',
                flow_family: 'income',
                category_key: null,
                subcategory_key: null,
                annual_income_entry_id: 1,
                annual_expense_entry_id: null,
                asset_id: null,
                liability_id: null,
                notes: '',
                created_at: '',
                updated_at: '',
              },
            ],
          },
          {
            id: 11,
            booking_date: `${currentYear}-01-15`,
            value_date: `${currentYear}-01-15`,
            description: 'Bonus puntual',
            status: 'posted',
            origin: 'manual',
            notes: '',
            created_at: '',
            updated_at: '',
            entries: [
              {
                id: 111,
                account_id: 1,
                account_name: 'Cuenta corriente',
                side: 'credit',
                amount: '1200.00',
                currency: 'EUR',
                flow_family: 'income',
                category_key: null,
                subcategory_key: null,
                annual_income_entry_id: 2,
                annual_expense_entry_id: null,
                asset_id: null,
                liability_id: null,
                notes: '',
                created_at: '',
                updated_at: '',
              },
            ],
          },
        ],
        next_cursor: null,
        total_count: 2,
      },
    } as never);

    const wrapper = mountBudgetView();
    await flushPromises();

    const incomeSection = wrapper.find('.ui-budget-section-income');
    const incomeFilterButtons = () => incomeSection.findAll('.ui-budget-filter-segment button');
    const januaryExec = () => {
      const monthCols = incomeSection.findAll('.ui-budget-month-col');
      const januaryCol = monthCols[0];
      if (!januaryCol) throw new Error('Income January column not found');
      return januaryCol.find('div[class^="ui-budget-month-exec"]');
    };

    await incomeFilterButtons()
      .find((candidate) => candidate.text().includes('Recurrentes'))
      ?.trigger('click');
    await flushPromises();
    expect(januaryExec().classes()).toContain('ui-budget-month-exec-pending');

    await incomeFilterButtons()
      .find((candidate) => candidate.text().includes('Puntuales'))
      ?.trigger('click');
    await flushPromises();
    expect(januaryExec().classes()).toContain('ui-budget-month-exec');
  });
});
