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
    accountActivationLoading: ref(false),
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
        asset_id: 91,
        liability_id: null,
        is_active: true,
        notes: '',
        current_balance: '2100.00',
        created_at: '',
        updated_at: '',
      },
      {
        id: 2,
        name: 'Ingresos sistema',
        account_type: 'income',
        currency: 'EUR',
        origin: 'system',
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
            flow_family: 'income',
            category_key: 'salary',
            subcategory_key: 'employee_salary',
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
    accountTypeOptions: [
      { value: 'asset', label: 'Activo' },
      { value: 'liability', label: 'Pasivo' },
      { value: 'equity', label: 'Patrimonio neto contable' },
      { value: 'income', label: 'Ingreso' },
      { value: 'expense', label: 'Gasto' },
    ],
    manualPositionTypeOptions: [
      { value: 'asset', label: 'Activo manual' },
      { value: 'liability', label: 'Pasivo manual' },
    ],
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
    activationForm: {
      position_type: 'asset',
      position_id: null,
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
      flow_family: 'expense',
      category_key: 'consumption_expenses',
      subcategory_key: 'living_expenses',
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
    editTransactionForm: {
      booking_date: '2026-03-15',
      description: 'Nomina marzo',
      notes: '',
      amount: '2100.00',
      currency: 'EUR',
      kind_label: 'Ingreso',
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
    availableManualPositionOptions: computed(() => [
      {
        id: 91,
        name: 'Broker manual',
        currency: 'EUR',
      },
    ]),
    hasAvailableManualPositions: computed(() => true),
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
    annualIncomeOptionsCompatible: computed(() => [{ id: 11, name: 'Nomina' }]),
    annualExpenseOptionsCompatible: computed(() => [{ id: 22, name: 'Supermercado' }]),
    quickEntryNeedsClassification: computed(() => true),
    quickCategoryOptions: computed(() => [{ value: 'salary', label: 'Salarios y trabajo' }]),
    quickSubcategoryOptions: computed(() => [{ value: 'employee_salary', label: 'Nomina' }]),
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
            flow_family: 'income',
            category_key: 'salary',
            subcategory_key: 'employee_salary',
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
    removeEntry: vi.fn(),
    reloadPeriod: vi.fn(),
    activateNetWorthPosition: vi.fn(),
    activateNetWorthPositions: vi.fn(),
    removeNetWorthTracking: vi.fn(),
    refreshManualPositionOptions: vi.fn(),
    submitAccount: vi.fn(),
    deleteAccount: vi.fn(),
    deleteTransaction: vi.fn(),
    openTransactionForEditing: vi.fn(() => true),
    submitQuickEntry: vi.fn(),
    submitEditedTransaction: vi.fn(),
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
    expect(wrapper.text()).toContain('Cuentas + historico por cuenta');
    expect(wrapper.text()).toContain('Saldo neto contable');
    expect(wrapper.text()).toContain('Activo contable - Pasivo contable');
    expect(wrapper.text()).not.toContain('Saldos derivados del ledger');
    expect(wrapper.text()).not.toContain('Entradas');
    expect(wrapper.text()).not.toContain('Salidas');
    expect(wrapper.find('button[title="Activar tracking contable"]').exists()).toBe(true);
    expect(wrapper.find('button[title="Registrar movimiento diario"]').exists()).toBe(true);
  });

  it('shows empty state and error message when needed', () => {
    mockUseAccountingPage.mockReturnValue(
      makeState({
        error: ref('La transaccion no esta balanceada.'),
        accounts: ref([]),
        transactions: ref([]),
        filteredTransactions: computed(() => []),
      }),
    );
    const wrapper = mount(AccountingMovementsView);

    expect(wrapper.text()).toContain('La transaccion no esta balanceada.');
    expect(wrapper.text()).toContain('Sin cuentas operativas para el periodo seleccionado.');
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

  it('opens the quick-entry modal and submits from there', async () => {
    const state = makeState();
    mockUseAccountingPage.mockReturnValue(state);
    const wrapper = mount(AccountingMovementsView, {
      attachTo: document.body,
    });

    await wrapper.find('button[title="Registrar movimiento diario"]').trigger('click');
    const modalForm = document.body.querySelector(
      'form.ui-accounting-modal-form.ui-accounting-transaction-form',
    ) as HTMLFormElement | null;
    modalForm?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await wrapper.vm.$nextTick();

    expect(state.submitQuickEntry).toHaveBeenCalled();
  });

  it('shows filter controls and derived transaction label', () => {
    mockUseAccountingPage.mockReturnValue(makeState());
    const wrapper = mount(AccountingMovementsView);

    expect(wrapper.find('input[placeholder="Filtrar por texto o cuenta"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Ingreso');
  });

  it('opens movement edit modal from timeline and submits changes', async () => {
    const state = makeState();
    mockUseAccountingPage.mockReturnValue(state);
    const wrapper = mount(AccountingMovementsView, {
      attachTo: document.body,
    });

    const editButton = wrapper.find('button[aria-label="Editar movimiento"]');
    await editButton?.trigger('click');
    await wrapper.vm.$nextTick();

    expect(state.openTransactionForEditing).toHaveBeenCalledWith(7);

    const editForm = document.body.querySelector(
      'form.ui-accounting-modal-form.ui-accounting-transaction-form',
    ) as HTMLFormElement | null;
    editForm?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await wrapper.vm.$nextTick();

    expect(state.submitEditedTransaction).toHaveBeenCalled();
  });

  it('deletes movement from timeline', async () => {
    const state = makeState();
    mockUseAccountingPage.mockReturnValue(state);
    const wrapper = mount(AccountingMovementsView);

    const deleteButton = wrapper.find('button[aria-label="Eliminar movimiento"]');
    await deleteButton?.trigger('click');

    expect(state.deleteTransaction).toHaveBeenCalledWith(7, 'Nomina marzo');
  });

  it('marks account timeline movement in green when it increases balance', () => {
    mockUseAccountingPage.mockReturnValue(makeState());
    const wrapper = mount(AccountingMovementsView);

    const firstDelta = wrapper.find('.ui-accounting-account-timeline .ui-accounting-balance-delta');
    expect(firstDelta.exists()).toBe(true);
    expect(firstDelta.classes()).toContain('ui-accounting-balance-delta-positive');
  });

  it('shows transfer impact in red for origin and green for destination', () => {
    mockUseAccountingPage.mockReturnValue(
      makeState({
        accounts: ref([
          {
            id: 1,
            name: 'Cuenta origen',
            account_type: 'asset',
            currency: 'EUR',
            origin: 'user',
            asset_id: null,
            liability_id: null,
            is_active: true,
            notes: '',
            current_balance: '900.00',
            created_at: '',
            updated_at: '',
          },
          {
            id: 3,
            name: 'Cuenta destino',
            account_type: 'asset',
            currency: 'EUR',
            origin: 'user',
            asset_id: null,
            liability_id: null,
            is_active: true,
            notes: '',
            current_balance: '1200.00',
            created_at: '',
            updated_at: '',
          },
        ]),
        filteredTransactions: computed(() => [
          {
            id: 9,
            booking_date: '2026-03-17',
            value_date: '2026-03-17',
            description: 'Transferencia interna',
            status: 'posted',
            origin: 'manual',
            notes: '',
            created_at: '',
            updated_at: '',
            entries: [
              {
                id: 11,
                account_id: 1,
                account_name: 'Cuenta origen',
                side: 'credit',
                amount: '100.00',
                currency: 'EUR',
                flow_family: '',
                category_key: '',
                subcategory_key: '',
                annual_income_entry_id: null,
                annual_expense_entry_id: null,
                asset_id: null,
                liability_id: null,
                notes: '',
                created_at: '',
                updated_at: '',
              },
              {
                id: 12,
                account_id: 3,
                account_name: 'Cuenta destino',
                side: 'debit',
                amount: '100.00',
                currency: 'EUR',
                flow_family: '',
                category_key: '',
                subcategory_key: '',
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
        activityKindLabel: vi.fn(() => 'Transferencia'),
      }),
    );
    const wrapper = mount(AccountingMovementsView);

    const originCard = wrapper
      .findAll('.ui-accounting-account-timeline')
      .find((card) => card.text().includes('Cuenta origen'));
    const destinationCard = wrapper
      .findAll('.ui-accounting-account-timeline')
      .find((card) => card.text().includes('Cuenta destino'));

    expect(originCard).toBeTruthy();
    expect(destinationCard).toBeTruthy();
    expect(originCard?.find('.ui-accounting-balance-delta').classes()).toContain(
      'ui-accounting-balance-delta-negative',
    );
    expect(destinationCard?.find('.ui-accounting-balance-delta').classes()).toContain(
      'ui-accounting-balance-delta-positive',
    );
  });

  it('opens the activation modal and allows batch activation', async () => {
    const state = makeState();
    mockUseAccountingPage.mockReturnValue(state);
    const wrapper = mount(AccountingMovementsView, {
      attachTo: document.body,
    });

    await wrapper.find('button[title="Activar tracking contable"]').trigger('click');
    const checkbox = document.body.querySelector(
      'input.ui-accounting-activation-checkbox',
    ) as HTMLInputElement | null;
    checkbox?.click();
    const activationForm = document.body.querySelector(
      'form.ui-accounting-modal-form',
    ) as HTMLFormElement | null;
    activationForm?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await wrapper.vm.$nextTick();

    expect(state.activateNetWorthPositions).toHaveBeenCalledWith('asset', [91]);
    expect(wrapper.text()).toContain('Patrimonio neto contable');
    expect(wrapper.text()).toContain('Contrapartidas tecnicas del sistema');
  });

  it('allows removing accounting tracking for linked positions', async () => {
    const state = makeState();
    mockUseAccountingPage.mockReturnValue(state);
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true);
    const wrapper = mount(AccountingMovementsView);

    const untrackButton = wrapper
      .findAll('button')
      .find((candidate) => candidate.text().includes('Quitar tracking'));
    await untrackButton?.trigger('click');

    expect(state.removeNetWorthTracking).toHaveBeenCalledWith(
      expect.objectContaining({ id: 1, asset_id: 91 }),
    );
    confirmSpy.mockRestore();
  });
});
