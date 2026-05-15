import {
  expenseCategories,
  expenseSubcategories,
  incomeCategories,
  incomeSubcategories,
  type ExpenseCategoryKey,
  type IncomeCategoryKey,
} from '@/domains/data-input';

export type ActivityFilter =
  | 'all'
  | 'income'
  | 'expense'
  | 'transfer'
  | 'adjustment'
  | 'investment'
  | 'debt_payment'
  | 'opening_balance'
  | 'revaluation';

export type EditableActivityKind =
  | 'income'
  | 'expense'
  | 'transfer'
  | 'investment'
  | 'debt_payment'
  | 'balance_adjustment'
  | 'revaluation';

export type ClassificationActivityKind = 'income' | 'expense';
export type CounterpartyEditableKind = 'transfer' | 'investment' | 'debt_payment';
export type LiabilityCategoryKey = 'mortgage' | 'personal_loan' | 'credit_card' | 'other';

export const EXPENSE_MOVEMENT_CATEGORY_KEYS: ExpenseCategoryKey[] = [
  'consumption_expenses',
  'real_estate_assets',
  'tangible_assets',
];

export const DEBT_PAYMENT_ALLOWED_CATEGORY_KEYS: ExpenseCategoryKey[] = [
  'consumption_expenses',
  'real_estate_assets',
  'tangible_assets',
  'financial_investments',
];

export const ROTATORY_DEPOSIT_ASSET_SUBCATEGORIES = new Set(['deposits', 'short_term_deposit']);

export function normalizeAccountId(value: unknown): number | null {
  if (typeof value === 'number') return Number.isFinite(value) ? value : null;
  if (typeof value === 'string') {
    const trimmed = value.trim();
    if (!trimmed) return null;
    const parsed = Number(trimmed);
    return Number.isFinite(parsed) ? parsed : null;
  }
  return null;
}

export function isAutoInvestmentBridgeAccount(account: { origin: string; name: string }): boolean {
  if (account.origin !== 'system') return false;
  const normalizedName = String(account.name ?? '')
    .trim()
    .toLowerCase();
  return normalizedName.startsWith('puente traspasos inversion (auto)');
}

export function categoryOptionsByKind(kind: ActivityFilter) {
  if (kind === 'income') return incomeCategories;
  if (kind === 'expense') {
    return expenseCategories.filter((row) =>
      EXPENSE_MOVEMENT_CATEGORY_KEYS.includes(row.value as ExpenseCategoryKey),
    );
  }
  if (kind === 'investment') {
    return [
      ...expenseCategories.filter((row) =>
        [
          'savings_allocation',
          'financial_investments',
          'real_estate_assets',
          'tangible_assets',
        ].includes(row.value),
      ),
      ...incomeCategories.filter((row) => row.value === 'capital_gains'),
    ];
  }
  if (kind === 'debt_payment') {
    return expenseCategories.filter((row) =>
      ['real_estate_assets', 'tangible_assets', 'consumption_expenses'].includes(row.value),
    );
  }
  return [...incomeCategories, ...expenseCategories];
}

export function subcategoryOptionsByCategory(categoryKey: string) {
  if (!categoryKey) return [];
  const asIncome = incomeSubcategories.filter((row) => row.category === categoryKey);
  if (asIncome.length) return asIncome;
  return expenseSubcategories.filter((row) => row.category === categoryKey);
}

export function kindUsesClassification(
  kind: EditableActivityKind,
  investmentDirection: 'inflow' | 'outflow' | 'reinvestment',
): boolean {
  if (kind === 'investment') return investmentDirection !== 'reinvestment';
  return kind === 'income' || kind === 'expense' || kind === 'debt_payment';
}

export function isCounterpartyKind(kind: EditableActivityKind): kind is CounterpartyEditableKind {
  return kind === 'transfer' || kind === 'investment' || kind === 'debt_payment';
}

export {
  incomeCategories,
  incomeSubcategories,
  expenseCategories,
  expenseSubcategories,
  type IncomeCategoryKey,
  type ExpenseCategoryKey,
};
