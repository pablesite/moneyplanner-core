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
    ]),
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
    liquidityAccounts: computed(() => [
      {
        id: 1,
        name: 'Cuenta corriente',
        account_type: 'asset',
        currency: 'EUR',
      },
    ]),
    incomeOptions: computed(() => [{ id: 11, name: 'Nomina' }]),
    expenseOptions: computed(() => [{ id: 22, name: 'Supermercado' }]),
    transferCounterpartyOptions: computed(() => []),
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
    addEntry: vi.fn(),
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
  });

  it('shows empty state and error message when needed', () => {
    mockUseAccountingPage.mockReturnValue(
      makeState({
        error: ref('La transaccion no esta balanceada.'),
        accounts: ref([]),
        transactions: ref([]),
      }),
    );
    const wrapper = mount(AccountingMovementsView);

    expect(wrapper.text()).toContain('La transaccion no esta balanceada.');
    expect(wrapper.text()).toContain('No hay movimientos para el periodo seleccionado.');
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
});
