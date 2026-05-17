import { describe, it, expect, beforeEach, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { defineComponent } from 'vue';
import { mount } from '@vue/test-utils';

import { useAccountingPage } from '../composables';
import { useAccountingStore } from '../store';
import { coreAccountingApi } from '../api';
import { coreNetWorthApi } from '@/domains/net-worth/api';

const loadAnnualIncome = vi.fn();
const loadAnnualExpense = vi.fn();

vi.mock('../api', () => ({
  coreAccountingApi: {
    getAccounts: vi.fn(),
    getTransactions: vi.fn(),
    getMonthlySummary: vi.fn(),
    getAccountBalances: vi.fn(),
    createAccount: vi.fn(),
    deleteAccount: vi.fn(),
    createTransaction: vi.fn(),
    createQuickEntry: vi.fn(),
  },
}));

vi.mock('@/domains/net-worth/api', () => ({
  coreNetWorthApi: {
    getAssets: vi.fn(),
    getLiabilities: vi.fn(),
    updateAsset: vi.fn(),
    updateLiability: vi.fn(),
  },
}));

vi.mock('@/domains/budget/taxonomy', () => ({
  incomeCategories: [{ value: 'salary', label: 'Salarios y trabajo' }],
  incomeSubcategories: [{ category: 'salary', value: 'employee_salary', label: 'Nomina' }],
  expenseCategories: [{ value: 'consumption_expenses', label: 'Gastos de consumo' }],
  expenseSubcategories: [
    { category: 'consumption_expenses', value: 'living_expenses', label: 'Alimentacion' },
  ],
}));

vi.mock('@/domains/budget/annual-entries', () => ({
  useAnnualIncomeStore: () => ({
    entries: { value: [] },
    loadAll: loadAnnualIncome,
  }),
  useAnnualExpenseStore: () => ({
    entries: { value: [] },
    loadAll: loadAnnualExpense,
  }),
}));

function seedRefreshResponses() {
  vi.mocked(coreAccountingApi.getAccounts).mockResolvedValue({
    data: [
      {
        id: 1,
        name: 'Cuenta corriente',
        account_type: 'asset',
        currency: 'EUR',
        origin: 'user',
        asset_id: null,
        liability_id: null,
        is_active: true,
        notes: '',
        current_balance: '1000.00',
        created_at: '',
        updated_at: '',
      },
    ],
  } as never);
  vi.mocked(coreAccountingApi.getTransactions).mockResolvedValue({
    data: { results: [], next_cursor: null, total_count: 0 },
  } as never);
  vi.mocked(coreAccountingApi.getMonthlySummary).mockResolvedValue({
    data: { fiscal_year: 2026, months: [] },
  } as never);
  vi.mocked(coreAccountingApi.getAccountBalances).mockResolvedValue({
    data: {
      filters: { year: 2026, month: 3, account_type: 'asset', status: 'posted' },
      totals_by_account_type: { asset: '1000.00' },
      accounts: [],
    },
  } as never);
}

function seedNetWorthResponses() {
  vi.mocked(coreNetWorthApi.getAssets).mockResolvedValue({ data: [] } as never);
  vi.mocked(coreNetWorthApi.getLiabilities).mockResolvedValue({ data: [] } as never);
}

describe('useAccountingPage', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
    seedRefreshResponses();
    seedNetWorthResponses();
  });

  it('sends taxonomy in quick-entry payload', async () => {
    const store = useAccountingStore();
    const Harness = defineComponent({
      setup() {
        return useAccountingPage();
      },
      template: '<div />',
    });

    const wrapper = mount(Harness);
    await wrapper.vm.$nextTick();

    wrapper.vm.quickEntryForm.movement_type = 'income';
    wrapper.vm.quickEntryForm.booking_date = '2026-03-15';
    wrapper.vm.quickEntryForm.value_date = '2026-03-15';
    wrapper.vm.quickEntryForm.description = 'Nomina marzo';
    wrapper.vm.quickEntryForm.amount = '500.00';
    wrapper.vm.quickEntryForm.account_id = 1;
    wrapper.vm.quickEntryForm.category_key = 'salary';
    wrapper.vm.quickEntryForm.subcategory_key = 'employee_salary';
    vi.mocked(coreAccountingApi.createQuickEntry).mockResolvedValue({ data: {} } as never);

    await wrapper.vm.submitQuickEntry();

    expect(coreAccountingApi.createQuickEntry).toHaveBeenCalledWith(
      expect.objectContaining({
        movement_type: 'income',
        category_key: 'salary',
        subcategory_key: 'employee_salary',
      }),
    );
    expect(store.transactionCreationLoading).toBe(false);
  });
});
