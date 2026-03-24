/** @vitest-environment jsdom */
import { defineComponent } from 'vue';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { flushPromises, mount } from '@vue/test-utils';
import BudgetDashboardView from '../BudgetDashboardView.vue';

const currentYear = new Date().getFullYear();
const currentMonth = new Date().getMonth() + 1;

const mockUseRoute = vi.fn(() => ({ name: 'budget', path: '/presupuesto' }));
const mockCoreApiGet = vi.hoisted(() => vi.fn());
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
  expenseCategories: [{ value: 'consumption_expenses', label: 'Gastos' }],
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
}));

vi.mock('@/lib/api', () => ({
  coreApi: {
    get: mockCoreApiGet,
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('@/domains/accounting', () => ({
  coreAccountingApi: mockAccountingApi,
}));

vi.mock('@/domains/data-input', () => ({
  incomeCategories: [{ value: 'salary', label: 'Salario' }],
  incomeSubcategories: [{ category: 'salary', value: 'employee_salary', label: 'Nomina' }],
  expenseCategories: [{ value: 'consumption_expenses', label: 'Gastos' }],
  expenseSubcategories: [
    { category: 'consumption_expenses', value: 'living_expenses', label: 'Alimentacion' },
  ],
  AnnualEntryModalForm: defineComponent({
    name: 'AnnualEntryModalForm',
    template: '<div />',
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

function makeLiquiditySummary() {
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
  };
}

function configureCoreApi(overrides?: {
  incomeCheckins?: unknown[];
  expenseCheckins?: unknown[];
  incomeSummaryExecuted?: string;
  expenseSummaryExecuted?: string;
  incomeSummary?: Record<string, unknown>;
  expenseSummary?: Record<string, unknown>;
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
      return { data: makeLiquiditySummary() };
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
    expect(wrapper.text()).toContain('Ledger categorizado');
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
    expect(wrapper.text()).toContain('Nomina A');
    expect(wrapper.text()).toContain('Nomina B');
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

    const toggleDetail = wrapper
      .findAll('button')
      .find((candidate) => candidate.text().includes('Ver detalle'));
    await toggleDetail?.trigger('click');
    await flushPromises();

    expect(wrapper.text()).toContain('Gestionar subcategoria');
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
    expect(wrapper.text()).toContain('Anadir al presupuesto');
  });
});
