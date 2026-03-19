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
    importPreviewLoading: ref(false),
    importCommitLoading: ref(false),
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
    moneyWizImportPreview: ref(null),
    moneyWizImportCommitResult: ref(null),
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
    editMovementTypeOptions: [
      { value: 'income', label: 'Ingreso' },
      { value: 'expense', label: 'Gasto' },
      { value: 'transfer', label: 'Transferencia' },
      { value: 'investment_purchase', label: 'Inversion' },
      { value: 'debt_payment', label: 'Deuda' },
      { value: 'balance_adjustment', label: 'Ajuste' },
    ],
    editAccountOptions: computed(() => [
      { id: 1, name: 'Cuenta corriente', currency: 'EUR', account_type: 'asset' },
    ]),
    editCounterpartyOptions: computed(() => []),
    editCounterpartyMissingHint: computed(() => ''),
    editKindNeedsCounterparty: computed(() => false),
    editKindNeedsClassification: computed(() => true),
    editCounterpartyLabel: computed(() => 'Contracuenta'),
    editSelectedAccountCurrentBalance: computed(() => '2100.00'),
    editCategoryOptions: computed(() => [{ value: 'salary', label: 'Salarios y trabajo' }]),
    editSubcategoryOptions: computed(() => [{ value: 'employee_salary', label: 'Nomina' }]),
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
    moneyWizImportFile: ref<File | null>(null),
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
      value_date: '2026-03-15',
      booking_time: '12:00',
      description: 'Nomina marzo',
      notes: '',
      account_id: 1,
      counterparty_account_id: null,
      amount: '2100.00',
      currency: 'EUR',
      kind: 'income',
      initial_kind: 'income',
      category_key: 'salary',
      subcategory_key: 'employee_salary',
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
    accountPositionMetaByAccountId: computed(() => new Map()),
    availableManualPositionOptions: computed(() => [
      {
        id: 91,
        name: 'Broker manual',
        category: 'cash',
        currency: 'EUR',
      },
    ]),
    accountDisplayName: vi.fn((account) => account.name),
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
    editEntryReady: computed(() => true),
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
    setMoneyWizImportFile: vi.fn(),
    previewMoneyWizImport: vi.fn(),
    commitMoneyWizImport: vi.fn(),
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

  it('renders accounting workspace shell and primary actions', () => {
    mockUseAccountingPage.mockReturnValue(makeState());
    const wrapper = mount(AccountingMovementsView);

    expect(wrapper.text()).toContain('Libro diario operativo');
    expect(wrapper.text()).toContain('Saldo neto contable');
    expect(wrapper.find('button[title="Activar tracking contable"]').exists()).toBe(true);
    expect(wrapper.find('button[title="Importar CSV MoneyWiz"]').exists()).toBe(true);
    expect(wrapper.find('button[title="Registrar movimiento diario"]').exists()).toBe(true);
    expect(wrapper.text()).toContain('Cuentas');
    expect(wrapper.text()).toContain('Todos los movimientos');
    expect(wrapper.text()).toContain('Estadísticas');
  });

  it('shows error message when present', () => {
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

  it('opens the MoneyWiz import modal and triggers preview', async () => {
    const state = makeState();
    mockUseAccountingPage.mockReturnValue(state);
    const wrapper = mount(AccountingMovementsView, {
      attachTo: document.body,
    });

    await wrapper.find('button[title="Importar CSV MoneyWiz"]').trigger('click');
    const previewButton = Array.from(document.body.querySelectorAll('button')).find((button) =>
      button.textContent?.includes('Generar preview'),
    ) as HTMLButtonElement | undefined;
    previewButton?.click();
    await wrapper.vm.$nextTick();

    expect(state.previewMoneyWizImport).toHaveBeenCalled();
  });

  it('renders tab controls', () => {
    mockUseAccountingPage.mockReturnValue(makeState());
    const wrapper = mount(AccountingMovementsView);

    expect(wrapper.text()).toContain('Cuentas');
    expect(wrapper.text()).toContain('Todos los movimientos');
    expect(wrapper.text()).toContain('Estadísticas');
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
    const activationForm = checkbox?.closest('form') as HTMLFormElement | null;
    activationForm?.dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
    await wrapper.vm.$nextTick();

    expect(state.activateNetWorthPositions).toHaveBeenCalledWith('asset', [91]);
  });
});
