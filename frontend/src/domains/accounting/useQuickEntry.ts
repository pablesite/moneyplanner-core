import { computed, reactive, watch, type ComputedRef, type Ref } from 'vue';
import type { LedgerAccount, QuickLedgerMovementType } from '@/domains/accounting/models';
import type { Asset, Liability } from '@/domains/net-worth/models';
import {
  expenseCategories,
  expenseSubcategories,
  incomeCategories,
  incomeSubcategories,
  type ExpenseCategoryKey,
  type IncomeCategoryKey,
} from '@/domains/data-input';
import {
  isAutoInvestmentBridgeAccount,
  normalizeAccountId,
  EXPENSE_MOVEMENT_CATEGORY_KEYS,
  DEBT_PAYMENT_ALLOWED_CATEGORY_KEYS,
  ROTATORY_DEPOSIT_ASSET_SUBCATEGORIES,
} from '@/domains/accounting/useTransactionClassification';

type AccountPositionMeta = {
  position_type: 'asset' | 'liability';
  category: string;
  subcategory: string;
  amount_base?: string;
};

type LiabilityCategoryKey = 'mortgage' | 'personal_loan' | 'credit_card' | 'other';

type LastQuickClassification = {
  category_key: string;
  subcategory_key: string;
};

type DebtBreakdownResolution = {
  total: number;
  principal: number;
  interest: number;
  valid: boolean;
  error: string | null;
};

export interface QuickEntryContext {
  accounts: Ref<LedgerAccount[]>;
  accountMap: ComputedRef<Map<number, LedgerAccount>>;
  liabilityMap: ComputedRef<Map<number, Liability>>;
  accountPositionMetaByAccountId: ComputedRef<Map<number, AccountPositionMeta>>;
  manualAssets: Ref<Asset[]>;
}

function formatDecimalInput(raw: string): string {
  return raw.replace(',', '.').trim();
}

function toNumber(raw: string): number {
  const parsed = Number(formatDecimalInput(raw));
  return Number.isFinite(parsed) ? parsed : 0;
}

function round2(value: number): number {
  return Math.round(value * 100) / 100;
}

function currencyDecimals(currency: string): number {
  const code = currency.trim().toUpperCase();
  return code === 'BTC' || code === 'ETH' ? 8 : 2;
}

function roundByCurrency(value: number, currency: string): number {
  const decimals = currencyDecimals(currency);
  const factor = 10 ** decimals;
  return Math.round(value * factor) / factor;
}

export function useQuickEntry(ctx: QuickEntryContext) {
  const { accounts, accountMap, liabilityMap, accountPositionMetaByAccountId, manualAssets } = ctx;

  const quickEntryForm = reactive({
    movement_type: 'expense' as QuickLedgerMovementType,
    investment_direction: 'inflow' as 'inflow' | 'outflow' | 'reinvestment',
    booking_date: new Date().toISOString().slice(0, 10),
    value_date: new Date().toISOString().slice(0, 10),
    description: '',
    ownership_id: null as number | null,
    amount: '',
    destination_amount: '',
    account_id: null as number | null,
    counterparty_account_id: null as number | null,
    liability_account_id: null as number | null,
    interest_account_id: null as number | null,
    principal_amount: '',
    interest_amount: '',
    realized_cost_basis: '',
    realized_gain_loss: '',
    flow_family: '' as '' | 'income' | 'expense',
    category_key: '',
    subcategory_key: '',
    notes: '',
    revaluation_new_value: '',
  });

  const lastQuickClassification = reactive<
    Record<'income' | 'expense' | 'debt_payment', LastQuickClassification>
  >({
    income: { category_key: '', subcategory_key: '' },
    expense: { category_key: '', subcategory_key: '' },
    debt_payment: { category_key: '', subcategory_key: '' },
  });

  function resolveAccountById(value: unknown): LedgerAccount | null {
    const id = normalizeAccountId(value);
    if (id == null) return null;
    return (
      accountMap.value.get(id) ??
      accounts.value.find((account) => normalizeAccountId(account.id) === id) ??
      null
    );
  }

  function isLiquidityAssetAccount(account: LedgerAccount): boolean {
    if (account.account_type !== 'asset') return false;
    if (isAutoInvestmentBridgeAccount(account)) return false;
    if (account.asset_id == null) return true;
    const meta = accountPositionMetaByAccountId.value.get(account.id);
    return (meta?.category ?? '').trim() === 'cash';
  }

  function debtPaymentDefaultCategoryForAccount(
    liabilityAccountId: number | null,
  ): ExpenseCategoryKey {
    if (liabilityAccountId == null) return 'consumption_expenses';
    const liabilityId = accountMap.value.get(liabilityAccountId)?.liability_id ?? null;
    if (liabilityId == null) return 'consumption_expenses';
    const liability = liabilityMap.value.get(liabilityId);
    if (!liability) return 'consumption_expenses';
    if (liability.category === 'mortgage') return 'real_estate_assets';
    const financedAssetId = liability.financed_asset_ref ?? null;
    if (financedAssetId == null) return 'consumption_expenses';
    const financedAsset = manualAssets.value.find((asset) => asset.id === financedAssetId);
    if (!financedAsset) return 'consumption_expenses';
    if (financedAsset.category === 'real_estate') return 'real_estate_assets';
    if (financedAsset.category === 'furnishings' || financedAsset.category === 'vehicle') {
      return 'tangible_assets';
    }
    if (financedAsset.category === 'investments') return 'financial_investments';
    return 'consumption_expenses';
  }

  function resolveInvestmentExpenseSubcategoryFromAccount(accountId: number | null): string {
    if (accountId == null) return '';
    const meta = accountPositionMetaByAccountId.value.get(accountId);
    if (!meta || meta.position_type !== 'asset') return '';
    return ROTATORY_DEPOSIT_ASSET_SUBCATEGORIES.has(meta.subcategory)
      ? 'deposits_fixed_income'
      : '';
  }

  const debtInterestOptions = computed(() =>
    accounts.value.filter((account) => account.account_type === 'expense'),
  );

  function resolveDefaultDebtInterestAccountId(currency: string): number | null {
    const candidates = debtInterestOptions.value;
    if (!candidates.length) return null;
    const normalizedCurrency = currency.trim().toUpperCase();
    return (
      candidates.find(
        (account) => account.currency === normalizedCurrency && account.origin === 'system',
      )?.id ??
      candidates.find((account) => account.currency === normalizedCurrency)?.id ??
      candidates.find((account) => account.origin === 'system')?.id ??
      candidates[0]?.id ??
      null
    );
  }

  const quickAdjustmentAccountOptions = computed(() =>
    accounts.value.filter(
      (account) => account.account_type === 'asset' || account.account_type === 'liability',
    ),
  );

  const transferOriginOptions = computed(() =>
    accounts.value.filter((account) => isLiquidityAssetAccount(account)),
  );

  const transferCounterpartyOptions = computed(() =>
    accounts.value.filter((account) => {
      if (account.id === quickEntryForm.account_id) return false;
      if (isLiquidityAssetAccount(account)) return true;
      return account.account_type === 'liability' && account.liability_id != null;
    }),
  );

  const investmentCounterpartyOptions = computed(() =>
    accounts.value.filter(
      (account) =>
        account.account_type === 'asset' &&
        account.id !== normalizeAccountId(quickEntryForm.account_id) &&
        !isAutoInvestmentBridgeAccount(account) &&
        account.asset_id != null,
    ),
  );

  const investmentOriginOptions = computed(() =>
    accounts.value.filter(
      (account) =>
        account.account_type === 'asset' &&
        account.asset_id != null &&
        !isAutoInvestmentBridgeAccount(account) &&
        account.id !== normalizeAccountId(quickEntryForm.counterparty_account_id),
    ),
  );

  const quickSelectedLiquidityAccountId = computed(() =>
    normalizeAccountId(quickEntryForm.account_id),
  );

  const quickSelectedInvestmentAccountId = computed(() =>
    normalizeAccountId(quickEntryForm.counterparty_account_id),
  );

  const quickSelectedLiquidityAccount = computed(() =>
    resolveAccountById(quickEntryForm.account_id),
  );

  const quickSelectedInvestmentAccount = computed(() =>
    resolveAccountById(quickEntryForm.counterparty_account_id),
  );

  const quickTransferOriginCurrency = computed(() => {
    if (quickEntryForm.movement_type !== 'transfer') return '';
    return quickSelectedLiquidityAccount.value?.currency ?? '';
  });

  const quickTransferDestinationCurrency = computed(() => {
    if (quickEntryForm.movement_type !== 'transfer') return '';
    return quickSelectedInvestmentAccount.value?.currency ?? '';
  });

  const quickTransferIsCrossCurrency = computed(() => {
    const origin = quickTransferOriginCurrency.value.trim().toUpperCase();
    const destination = quickTransferDestinationCurrency.value.trim().toUpperCase();
    return Boolean(origin && destination && origin !== destination);
  });

  const quickSelectedAdjustmentAccount = computed(() =>
    quickEntryForm.movement_type === 'adjustment'
      ? resolveAccountById(quickEntryForm.account_id)
      : null,
  );

  const quickInvestmentOriginCurrency = computed(() => {
    if (quickEntryForm.movement_type !== 'investment') return '';
    if (quickEntryForm.investment_direction === 'outflow') {
      return quickSelectedInvestmentAccount.value?.currency ?? '';
    }
    if (quickEntryForm.investment_direction === 'reinvestment') {
      return quickSelectedLiquidityAccount.value?.currency ?? '';
    }
    return quickSelectedLiquidityAccount.value?.currency ?? '';
  });

  const quickInvestmentDestinationCurrency = computed(() => {
    if (quickEntryForm.movement_type !== 'investment') return '';
    if (quickEntryForm.investment_direction === 'outflow') {
      return quickSelectedLiquidityAccount.value?.currency ?? '';
    }
    if (quickEntryForm.investment_direction === 'reinvestment') {
      return quickSelectedInvestmentAccount.value?.currency ?? '';
    }
    return quickSelectedInvestmentAccount.value?.currency ?? '';
  });

  const quickInvestmentIsCrossCurrency = computed(() => {
    const origin = quickInvestmentOriginCurrency.value.trim().toUpperCase();
    const destination = quickInvestmentDestinationCurrency.value.trim().toUpperCase();
    return Boolean(origin && destination && origin !== destination);
  });

  const revaluationAccountOptions = computed(() =>
    accounts.value.filter(
      (account) => account.account_type === 'asset' && account.asset_id != null,
    ),
  );

  const revaluationCurrentBalance = computed((): number | null => {
    if (quickEntryForm.movement_type !== 'revaluation') return null;
    if (quickEntryForm.account_id == null) return null;
    const account = accountMap.value.get(quickEntryForm.account_id);
    return account != null ? toNumber(account.current_balance) : null;
  });

  const revaluationDelta = computed((): number | null => {
    const raw = quickEntryForm.revaluation_new_value.trim();
    if (!raw) return null;
    const currentBalance = revaluationCurrentBalance.value;
    if (currentBalance == null) return null;
    return round2(toNumber(raw) - currentBalance);
  });

  const quickAdjustmentCurrentBalance = computed((): number | null => {
    if (quickEntryForm.movement_type !== 'adjustment') return null;
    const account = quickSelectedAdjustmentAccount.value;
    if (!account) return null;
    return toNumber(account.current_balance);
  });

  const quickAdjustmentCurrency = computed(
    () => quickSelectedAdjustmentAccount.value?.currency.trim().toUpperCase() ?? '',
  );

  const quickAdjustmentDisplayDecimals = computed(() => {
    if (!quickAdjustmentCurrency.value) return 2;
    return currencyDecimals(quickAdjustmentCurrency.value);
  });

  const quickAdjustmentDelta = computed((): number | null => {
    if (quickEntryForm.movement_type !== 'adjustment') return null;
    const rawTarget = quickEntryForm.amount.trim();
    if (!rawTarget) return null;
    const account = quickSelectedAdjustmentAccount.value;
    const currentBalance = quickAdjustmentCurrentBalance.value;
    if (!account || currentBalance == null) return null;
    return roundByCurrency(toNumber(rawTarget) - currentBalance, account.currency);
  });

  const liabilityCounterpartyOptions = computed(() =>
    accounts.value.filter(
      (account) => account.account_type === 'liability' && account.liability_id != null,
    ),
  );

  const quickSelectedLiabilityCategory = computed<LiabilityCategoryKey | null>(() => {
    const liabilityAccountId = normalizeAccountId(quickEntryForm.liability_account_id);
    if (liabilityAccountId == null) return null;
    const liabilityId = accountMap.value.get(liabilityAccountId)?.liability_id ?? null;
    if (liabilityId == null) return null;
    const category = liabilityMap.value.get(liabilityId)?.category ?? null;
    if (
      category === 'mortgage' ||
      category === 'personal_loan' ||
      category === 'credit_card' ||
      category === 'other'
    ) {
      return category;
    }
    return null;
  });

  function hasQuickClassification(): boolean {
    return Boolean(quickEntryForm.category_key && quickEntryForm.subcategory_key);
  }

  // eslint-disable-next-line complexity
  function resolveFlexibleDebtBreakdown(
    totalRaw: string,
    principalRaw: string,
    interestRaw: string,
    currency: string,
  ): DebtBreakdownResolution {
    const parseAmount = (raw: string): number | null => {
      const normalized = formatDecimalInput(raw);
      if (!normalized) return null;
      const parsed = Number(normalized);
      return Number.isFinite(parsed) ? parsed : Number.NaN;
    };
    let total = parseAmount(totalRaw);
    let principal = parseAmount(principalRaw);
    let interest = parseAmount(interestRaw);
    if ([total, principal, interest].some((value) => Number.isNaN(value))) {
      return {
        total: 0,
        principal: 0,
        interest: 0,
        valid: false,
        error: 'Introduce importes válidos en total, principal o interés.',
      };
    }
    const filledValues = [total, principal, interest].filter((value) => value != null).length;
    if (filledValues < 2) {
      return {
        total: 0,
        principal: 0,
        interest: 0,
        valid: false,
        error: 'En pago deuda informa al menos dos campos: total, principal o interés.',
      };
    }
    if (filledValues === 2) {
      if (total == null && principal != null && interest != null) total = principal + interest;
      else if (principal == null && total != null && interest != null) principal = total - interest;
      else if (interest == null && total != null && principal != null) interest = total - principal;
    }
    if (total == null || principal == null || interest == null) {
      return {
        total: 0,
        principal: 0,
        interest: 0,
        valid: false,
        error: 'No se pudo resolver el desglose del pago deuda.',
      };
    }
    const roundedTotal = roundByCurrency(total, currency);
    const roundedPrincipal = roundByCurrency(principal, currency);
    const roundedInterest = roundByCurrency(interest, currency);
    if (roundedPrincipal < 0 || roundedInterest < 0 || roundedTotal <= 0) {
      return {
        total: 0,
        principal: 0,
        interest: 0,
        valid: false,
        error: 'Los importes de principal e interés deben ser positivos y el total mayor que cero.',
      };
    }
    return {
      total: roundedTotal,
      principal: roundedPrincipal,
      interest: roundedInterest,
      valid: true,
      error: null,
    };
  }

  function resolveQuickDebtBreakdown(): DebtBreakdownResolution {
    const currency = quickSelectedLiquidityAccount.value?.currency ?? 'EUR';
    return resolveFlexibleDebtBreakdown(
      quickEntryForm.amount,
      quickEntryForm.principal_amount,
      quickEntryForm.interest_amount,
      currency,
    );
  }

  function debtPaymentBreakdownReady(): boolean {
    if (quickEntryForm.liability_account_id == null) return false;
    if (!hasQuickClassification()) return false;
    const breakdown = resolveQuickDebtBreakdown();
    if (!breakdown.valid) return false;
    if (breakdown.interest > 0 && quickEntryForm.interest_account_id == null) return false;
    return true;
  }

  function quickInvestmentEntryReady(): boolean {
    if (quickSelectedInvestmentAccountId.value == null) return false;
    if (quickEntryForm.investment_direction === 'reinvestment') {
      const originAccount = quickSelectedLiquidityAccount.value;
      const destinationAccount = quickSelectedInvestmentAccount.value;
      if (
        !originAccount ||
        originAccount.asset_id == null ||
        isAutoInvestmentBridgeAccount(originAccount)
      ) {
        return false;
      }
      if (
        !destinationAccount ||
        destinationAccount.asset_id == null ||
        isAutoInvestmentBridgeAccount(destinationAccount)
      ) {
        return false;
      }
    }
    if (!quickInvestmentIsCrossCurrency.value) return true;
    return toNumber(quickEntryForm.destination_amount) > 0;
  }

  const quickEntryReady = computed(() => {
    if (!quickEntryForm.description.trim()) return false;
    if (!quickEntryForm.booking_date || !quickEntryForm.value_date) return false;
    if (quickEntryForm.movement_type === 'revaluation') {
      if (quickEntryForm.account_id == null) return false;
      const delta = revaluationDelta.value;
      return delta != null && Math.abs(delta) >= 0.005;
    }
    if (quickEntryForm.movement_type === 'adjustment') {
      const account = quickSelectedAdjustmentAccount.value;
      const delta = quickAdjustmentDelta.value;
      if (!account || delta == null) return false;
      const minUnit = 1 / 10 ** currencyDecimals(account.currency);
      return Math.abs(delta) >= minUnit;
    }
    if (quickSelectedLiquidityAccountId.value == null) return false;
    if (quickEntryForm.movement_type === 'debt_payment') {
      return debtPaymentBreakdownReady();
    }
    const amountValue = toNumber(quickEntryForm.amount);
    if (amountValue <= 0) {
      return false;
    }
    if (quickEntryForm.movement_type === 'transfer') {
      const hasCounterparty = normalizeAccountId(quickEntryForm.counterparty_account_id) != null;
      if (!hasCounterparty) return false;
      if (!quickTransferIsCrossCurrency.value) return true;
      return toNumber(quickEntryForm.destination_amount) > 0;
    }
    if (quickEntryForm.movement_type === 'investment') {
      return quickInvestmentEntryReady();
    }
    if (
      (quickEntryForm.movement_type === 'income' || quickEntryForm.movement_type === 'expense') &&
      !hasQuickClassification()
    ) {
      return false;
    }
    return true;
  });

  const quickEntryNeedsClassification = computed(
    () =>
      quickEntryForm.movement_type === 'income' ||
      quickEntryForm.movement_type === 'expense' ||
      (quickEntryForm.movement_type === 'investment' &&
        quickEntryForm.investment_direction !== 'reinvestment') ||
      quickEntryForm.movement_type === 'debt_payment',
  );

  const quickCategoryOptions = computed(() => {
    if (quickEntryForm.movement_type === 'income') return incomeCategories;
    if (quickEntryForm.movement_type === 'expense') {
      return expenseCategories.filter((row) =>
        EXPENSE_MOVEMENT_CATEGORY_KEYS.includes(row.value as ExpenseCategoryKey),
      );
    }
    if (quickEntryForm.movement_type === 'investment') {
      if (quickEntryForm.investment_direction === 'reinvestment') {
        return [];
      }
      if (quickEntryForm.investment_direction === 'outflow') {
        return incomeCategories.filter((row) => row.value === 'capital_gains');
      }
      return expenseCategories.filter((row) =>
        ['financial_investments', 'real_estate_assets', 'tangible_assets'].includes(row.value),
      );
    }
    if (quickEntryForm.movement_type === 'debt_payment') {
      if (quickSelectedLiabilityCategory.value === 'mortgage') {
        return expenseCategories.filter((row) => row.value === 'real_estate_assets');
      }
      return expenseCategories.filter((row) =>
        DEBT_PAYMENT_ALLOWED_CATEGORY_KEYS.includes(row.value as ExpenseCategoryKey),
      );
    }
    return [];
  });

  const quickSubcategoryOptions = computed(() => {
    if (!quickEntryForm.category_key) return [];
    if (quickEntryForm.movement_type === 'income') {
      return incomeSubcategories.filter(
        (row) => row.category === (quickEntryForm.category_key as IncomeCategoryKey),
      );
    }
    if (
      quickEntryForm.movement_type === 'expense' ||
      quickEntryForm.movement_type === 'debt_payment'
    ) {
      return expenseSubcategories.filter(
        (row) => row.category === (quickEntryForm.category_key as ExpenseCategoryKey),
      );
    }
    if (quickEntryForm.movement_type === 'investment') {
      if (quickEntryForm.investment_direction === 'reinvestment') {
        return [];
      }
      if (quickEntryForm.investment_direction === 'outflow') {
        return incomeSubcategories.filter(
          (row) => row.category === (quickEntryForm.category_key as IncomeCategoryKey),
        );
      }
      return expenseSubcategories.filter(
        (row) => row.category === (quickEntryForm.category_key as ExpenseCategoryKey),
      );
    }
    return [];
  });

  const quickCategoryLocked = computed(() => {
    if (quickEntryForm.movement_type === 'investment') {
      return quickEntryForm.investment_direction !== 'reinvestment';
    }
    if (quickEntryForm.movement_type === 'debt_payment') {
      return quickSelectedLiabilityCategory.value === 'mortgage';
    }
    return false;
  });

  const quickSubcategoryLocked = computed(() => {
    if (quickEntryForm.movement_type === 'investment') {
      return (
        quickEntryForm.investment_direction === 'outflow' ||
        quickEntryForm.investment_direction === 'reinvestment'
      );
    }
    if (quickEntryForm.movement_type === 'debt_payment') {
      return quickSelectedLiabilityCategory.value === 'mortgage';
    }
    return false;
  });

  const quickMovementTypeOptions: { value: QuickLedgerMovementType; label: string }[] = [
    { value: 'income', label: 'Ingreso' },
    { value: 'expense', label: 'Gasto' },
    { value: 'transfer', label: 'Transferencia' },
    { value: 'adjustment', label: 'Ajuste' },
    { value: 'investment', label: 'Inversion' },
    { value: 'debt_payment', label: 'Pago deuda' },
    { value: 'revaluation', label: 'Revalorizacion' },
  ];

  // ── Watches ────────────────────────────────────────────────────────────
  watch(
    () => quickEntryForm.movement_type,
    (movementType) => {
      quickEntryForm.counterparty_account_id = null;
      quickEntryForm.liability_account_id = null;
      quickEntryForm.interest_account_id = null;
      quickEntryForm.principal_amount = '';
      quickEntryForm.interest_amount = '';
      quickEntryForm.realized_cost_basis = '';
      quickEntryForm.realized_gain_loss = '';
      quickEntryForm.destination_amount = '';
      quickEntryForm.flow_family = '';
      quickEntryForm.revaluation_new_value = '';
      quickEntryForm.investment_direction = 'inflow';
      const remembered =
        movementType === 'income' || movementType === 'expense' || movementType === 'debt_payment'
          ? lastQuickClassification[movementType]
          : null;
      if (remembered) {
        quickEntryForm.category_key = remembered.category_key;
        quickEntryForm.subcategory_key = remembered.subcategory_key;
      } else {
        quickEntryForm.category_key = '';
        quickEntryForm.subcategory_key = '';
      }
    },
  );

  watch(
    () => [quickEntryForm.movement_type, quickEntryForm.investment_direction] as const,
    () => {
      if (quickEntryForm.movement_type !== 'investment') return;
      if (quickEntryForm.investment_direction === 'reinvestment') {
        quickEntryForm.category_key = '';
        quickEntryForm.subcategory_key = '';
        return;
      }
      if (quickEntryForm.investment_direction === 'outflow') {
        quickEntryForm.category_key = 'capital_gains';
        quickEntryForm.subcategory_key = 'sale_financial_assets';
      } else if (!quickEntryForm.category_key) {
        quickEntryForm.category_key = 'financial_investments';
      }
    },
    { immediate: true },
  );

  watch(
    () =>
      [
        quickEntryForm.movement_type,
        quickEntryForm.investment_direction,
        quickEntryForm.category_key,
        quickEntryForm.counterparty_account_id,
      ] as const,
    () => {
      if (quickEntryForm.movement_type !== 'investment') return;
      if (quickEntryForm.investment_direction === 'reinvestment') return;
      if (quickEntryForm.category_key !== 'financial_investments') return;
      const inferredSubcategory = resolveInvestmentExpenseSubcategoryFromAccount(
        normalizeAccountId(quickEntryForm.counterparty_account_id),
      );
      if (inferredSubcategory) {
        quickEntryForm.subcategory_key = inferredSubcategory;
        return;
      }
      if (quickEntryForm.subcategory_key === 'deposits_fixed_income') {
        quickEntryForm.subcategory_key = '';
      }
    },
    { immediate: true },
  );

  watch(
    () => [quickEntryForm.movement_type, quickEntryForm.liability_account_id] as const,
    () => {
      if (quickEntryForm.movement_type !== 'debt_payment') return;
      const defaultCategory = debtPaymentDefaultCategoryForAccount(
        normalizeAccountId(quickEntryForm.liability_account_id),
      );
      if (quickSelectedLiabilityCategory.value === 'mortgage') {
        quickEntryForm.category_key = 'real_estate_assets';
        quickEntryForm.subcategory_key = 'mortgage_principal';
      } else {
        if (
          !quickEntryForm.category_key ||
          !DEBT_PAYMENT_ALLOWED_CATEGORY_KEYS.includes(
            quickEntryForm.category_key as ExpenseCategoryKey,
          )
        ) {
          quickEntryForm.category_key = defaultCategory;
        }
        if (quickEntryForm.subcategory_key === 'mortgage_principal') {
          quickEntryForm.subcategory_key =
            quickEntryForm.category_key === 'consumption_expenses' ? 'financial_commitments' : '';
        }
      }
    },
    { immediate: true },
  );

  watch(
    () => quickEntryForm.movement_type,
    (movementType) => {
      if (movementType !== 'expense') return;
      if (
        !EXPENSE_MOVEMENT_CATEGORY_KEYS.includes(quickEntryForm.category_key as ExpenseCategoryKey)
      ) {
        quickEntryForm.category_key = 'consumption_expenses';
      }
    },
  );

  watch(
    () => quickEntryForm.category_key,
    () => {
      if (
        quickEntryForm.subcategory_key &&
        !quickSubcategoryOptions.value.some((row) => row.value === quickEntryForm.subcategory_key)
      ) {
        quickEntryForm.subcategory_key = '';
      }
    },
  );

  watch(
    () => quickEntryForm.subcategory_key,
    (value) => {
      if (!value) return;
      if (quickEntryForm.movement_type === 'income') {
        lastQuickClassification.income = {
          category_key: quickEntryForm.category_key,
          subcategory_key: value,
        };
      } else if (quickEntryForm.movement_type === 'expense') {
        lastQuickClassification.expense = {
          category_key: quickEntryForm.category_key,
          subcategory_key: value,
        };
      } else if (quickEntryForm.movement_type === 'debt_payment') {
        lastQuickClassification.debt_payment = {
          category_key: quickEntryForm.category_key,
          subcategory_key: value,
        };
      }
    },
  );

  function resetQuickEntryForm() {
    quickEntryForm.movement_type = 'expense';
    quickEntryForm.investment_direction = 'inflow';
    quickEntryForm.booking_date = new Date().toISOString().slice(0, 10);
    quickEntryForm.value_date = quickEntryForm.booking_date;
    quickEntryForm.description = '';
    quickEntryForm.ownership_id = null;
    quickEntryForm.amount = '';
    quickEntryForm.destination_amount = '';
    quickEntryForm.account_id = null;
    quickEntryForm.counterparty_account_id = null;
    quickEntryForm.liability_account_id = null;
    quickEntryForm.interest_account_id = null;
    quickEntryForm.principal_amount = '';
    quickEntryForm.interest_amount = '';
    quickEntryForm.realized_cost_basis = '';
    quickEntryForm.realized_gain_loss = '';
    quickEntryForm.flow_family = '';
    quickEntryForm.category_key = '';
    quickEntryForm.subcategory_key = '';
    quickEntryForm.notes = '';
    quickEntryForm.revaluation_new_value = '';
  }

  return {
    quickEntryForm,
    quickMovementTypeOptions,
    quickAdjustmentAccountOptions,
    transferOriginOptions,
    transferCounterpartyOptions,
    investmentOriginOptions,
    investmentCounterpartyOptions,
    quickSelectedLiquidityAccountId,
    quickSelectedInvestmentAccountId,
    quickSelectedLiquidityAccount,
    quickSelectedInvestmentAccount,
    quickTransferOriginCurrency,
    quickTransferDestinationCurrency,
    quickTransferIsCrossCurrency,
    quickInvestmentOriginCurrency,
    quickInvestmentDestinationCurrency,
    quickInvestmentIsCrossCurrency,
    revaluationAccountOptions,
    revaluationCurrentBalance,
    revaluationDelta,
    quickAdjustmentCurrentBalance,
    quickAdjustmentCurrency,
    quickAdjustmentDisplayDecimals,
    quickAdjustmentDelta,
    liabilityCounterpartyOptions,
    debtInterestOptions,
    quickEntryReady,
    quickEntryNeedsClassification,
    quickCategoryOptions,
    quickSubcategoryOptions,
    quickCategoryLocked,
    quickSubcategoryLocked,
    // exposed for submitQuickEntry / submitRevaluationEntry / edit form in parent
    resolveFlexibleDebtBreakdown,
    resolveQuickDebtBreakdown,
    resolveDefaultDebtInterestAccountId,
    debtPaymentDefaultCategoryForAccount,
    resolveInvestmentExpenseSubcategoryFromAccount,
    resetQuickEntryForm,
  };
}

export type UseQuickEntryReturn = ReturnType<typeof useQuickEntry>;
