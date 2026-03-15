/** @vitest-environment jsdom */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { mount } from '@vue/test-utils';
import { computed, ref } from 'vue';
import AccountingMovementsView from '../AccountingMovementsView.vue';

const mockUseAccountingPage = vi.fn();

vi.mock('@/domains/accounting', () => ({
  useAccountingPage: () => mockUseAccountingPage(),
}));

function makeState(overrides: Record<string, unknown> = {}) {
  return {
    loading: ref(false),
    accountCreationLoading: ref(false),
    transactionCreationLoading: ref(false),
    error: ref<string | null>(null),
    successMessage: ref<string | null>(null),
    accounts: ref([
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
        current_balance: '2100.00',
        created_at: '',
        updated_at: '',
      },
    ]),
    transactions: ref([
      {
        id: 7,
        booking_date: '2026-03-15',
        value_date: '2026-03-15',
        description: 'Nomina marzo',
        status: 'posted',
        origin: 'manual',
        notes: '',
        created_at: '',
        updated_at: '',
        entries: [
          {
            id: 1,
            account_id: 1,
            account_name: 'Cuenta corriente',
            side: 'debit',
            amount: '2100.00',
            currency: 'EUR',
            annual_income_entry_id: 11,
            annual_expense_entry_id: null,
            asset_id: null,
            liability_id: null,
            notes: '',
            created_at: '',
            updated_at: '',
          },
        ],
      },
    ]),
    accountBalancesSummary: ref({
      filters: { year: 2026, month: 3, account_type: 'asset', status: 'posted' },
      totals_by_account_type: { asset: '2100.00' },
      accounts: [
        {
          account_id: 1,
          name: 'Cuenta corriente',
          account_type: 'asset',
          currency: 'EUR',
          origin: 'user',
          current_balance: '2100.00',
          period_debit_total: '2100.00',
          period_credit_total: '0.00',
          period_net_change: '2100.00',
        },
      ],
    }),
    selectedYear: computed({
      get: () => 2026,
      set: () => undefined,
    }),
    selectedMonth: computed({
      get: () => 3,
      set: () => undefined,
    }),
    yearOptions: computed(() => [2026]),
    monthOptions: [
      { value: 1, label: 'Enero' },
      { value: 2, label: 'Febrero' },
      { value: 3, label: 'Marzo' },
    ],
    accountTypeOptions: [{ value: 'asset', label: 'Activo' }],
    quickMovementTypeOptions: [
      { value: 'income', label: 'Ingreso' },
      { value: 'expense', label: 'Gasto' },
      { value: 'transfer', label: 'Transferencia' },
      { value: 'investment_purchase', label: 'Compra inversion' },
      { value: 'debt_payment', label: 'Pago deuda' },
    ],
    accountForm: {
      name: '',
      account_type: 'asset',
      currency: 'EUR',
      origin: 'user',
      notes: '',
    },
    quickEntryForm: {
      movement_type: 'expense',
      booking_date: '2026-03-15',
      value_date: '2026-03-15',
      description: 'Compra semanal',
      amount: '100.00',
      account_id: 1,
      counterparty_account_id: null,
      liability_account_id: null,
      interest_account_id: null,
      principal_amount: '',
      interest_amount: '',
      annual_income_entry_id: null,
      annual_expense_entry_id: null,
      notes: '',
    },
    transactionForm: {
      booking_date: '2026-03-15',
      value_date: '2026-03-15',
      description: '',
      status: 'posted',
      origin: 'manual',
      notes: '',
      entries: [
        {
          key: 1,
          account_id: 1,
          side: 'debit',
          amount: '100.00',
          currency: 'EUR',
          notes: '',
        },
        {
          key: 2,
          account_id: 1,
          side: 'credit',
          amount: '100.00',
          currency: 'EUR',
          notes: '',
        },
      ],
    },
    debitTotal: computed(() => 100),
    creditTotal: computed(() => 100),
    activityFilters: {
      query: '',
      accountId: 'all',
      kind: 'all',
    },
    liquidityAccounts: computed(() => [
      {
        id: 1,
        name: 'Cuenta corriente',
        account_type: 'asset',
        currency: 'EUR',
      },
    ]),
    liquidityBalanceRows: computed(() => [
      {
        account_id: 1,
        name: 'Cuenta corriente',
        account_type: 'asset',
        currency: 'EUR',
        origin: 'user',
        current_balance: '2100.00',
        period_debit_total: '2100.00',
        period_credit_total: '0.00',
        period_net_change: '2100.00',
      },
    ]),
    liquidityBalanceTotal: computed(() => 2100),
    incomeOptions: computed(() => [{ id: 11, name: 'Nomina' }]),
    expenseOptions: computed(() => [{ id: 22, name: 'Supermercado' }]),
    transferCounterpartyOptions: computed(() => []),
    investmentCounterpartyOptions: computed(() => []),
    liabilityCounterpartyOptions: computed(() => []),
    debtInterestOptions: computed(() => []),
    quickEntryReady: computed(() => true),
    transactionBalanced: computed(() => true),
    summaryRows: computed(() => [
      {
        month: 3,
        income_total: '2100.00',
        expense_total: '700.00',
        uncategorized_total: '0.00',
        incomeValue: 2100,
        expenseValue: 700,
        uncategorizedValue: 0,
      },
    ]),
    filteredTransactions: computed(() => [
      {
        id: 7,
        booking_date: '2026-03-15',
        value_date: '2026-03-15',
        description: 'Nomina marzo',
        status: 'posted',
        origin: 'manual',
        notes: '',
        created_at: '',
        updated_at: '',
        entries: [
          {
            id: 1,
            account_id: 1,
            account_name: 'Cuenta corriente',
            side: 'debit',
            amount: '2100.00',
            currency: 'EUR',
            annual_income_entry_id: 11,
            annual_expense_entry_id: null,
            asset_id: null,
            liability_id: null,
            notes: '',
            created_at: '',
            updated_at: '',
          },
        ],
      },
    ]),
    addEntry: vi.fn(),
    activityKindLabel: vi.fn(() => 'Ingreso'),
    liquidityBalanceDeltaTone: vi.fn(() => 'positive'),
    removeEntry: vi.fn(),
    reloadPeriod: vi.fn(),
    submitAccount: vi.fn(),
    submitQuickEntry: vi.fn(),
    submitTransaction: vi.fn(),
    ...overrides,
  };
}

describe('AccountingMovementsView', () => {
  beforeEach(() => {
    mockUseAccountingPage.mockReset();
  });

  it('renders accounting workspace with accounts and transactions', () => {
    mockUseAccountingPage.mockReturnValue(makeState());
    const wrapper = mount(AccountingMovementsView);

    expect(wrapper.text()).toContain('Libro diario operativo');
    expect(wrapper.text()).toContain('Cuenta corriente');
    expect(wrapper.text()).toContain('Nomina marzo');
    expect(wrapper.text()).toContain('Registrar movimiento diario');
    expect(wrapper.text()).toContain('Registrar movimiento rapido');
    expect(wrapper.text()).toContain('Saldos derivados del ledger');
  });

  it('shows empty state and error message when needed', () => {
    mockUseAccountingPage.mockReturnValue(
      makeState({
        error: ref('La transaccion no esta balanceada.'),
        accounts: ref([]),
        transactions: ref([]),
        filteredTransactions: computed(() => []),
        liquidityAccounts: computed(() => []),
        liquidityBalanceRows: computed(() => []),
      }),
    );
    const wrapper = mount(AccountingMovementsView);

    expect(wrapper.text()).toContain('La transaccion no esta balanceada.');
    expect(wrapper.text()).toContain('No hay movimientos para el periodo seleccionado.');
    expect(wrapper.text()).toContain('Necesitas al menos una cuenta de liquidez');
  });

  it('wires entry add action from quick controls', async () => {
    const state = makeState();
    mockUseAccountingPage.mockReturnValue(state);
    const wrapper = mount(AccountingMovementsView);

    const button = wrapper
      .findAll('button')
      .find((candidate) => candidate.text().includes('Anadir debe'));
    await button?.trigger('click');

    expect(state.addEntry).toHaveBeenCalledWith('debit');
  });

  it('submits fast entry from the primary form', async () => {
    const state = makeState();
    mockUseAccountingPage.mockReturnValue(state);
    const wrapper = mount(AccountingMovementsView);

    const button = wrapper
      .findAll('button')
      .find((candidate) => candidate.text().includes('Registrar movimiento rapido'));
    await button?.trigger('submit');
    await wrapper.find('form.ui-accounting-transaction-form').trigger('submit.prevent');

    expect(state.submitQuickEntry).toHaveBeenCalled();
  });

  it('shows filter controls and derived transaction label', () => {
    mockUseAccountingPage.mockReturnValue(makeState());
    const wrapper = mount(AccountingMovementsView);

    expect(wrapper.find('input[placeholder="Filtrar por texto o cuenta"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Ingreso');
  });
});
