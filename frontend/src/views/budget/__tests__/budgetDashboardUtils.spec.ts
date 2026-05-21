import { describe, expect, it } from 'vitest';
import {
  aggregateBudgetRows,
  buildActualExecution,
  buildMonthlyResultBreakdown,
  executionSourceLabel,
  executionToneFor,
  hashToUnitInterval,
  isLockedExecutionRow,
  mockExecutionRatio,
  parseSharedOwnerShares,
  ownerNamesFromLabel,
  allocationFractionForOwnerLabel,
  sumPlanned,
  toNumberOrZero,
  monthlySummaryExecutedTotal,
  budgetTaxonomyKey,
  budgetMonthTaxonomyKey,
  budgetMonthEntryKey,
  parseBudgetTaxonomyKey,
  incomeEntryMonthKey,
  expenseEntryMonthKey,
  cleanedExpenseCheckinName,
  checkinStatusLabel,
  shortExpenseCategoryLabel,
  expenseCheckinCategorySortWeight,
  expenseCategorySortIndex,
  amountsEqualCents,
  shortLiquiditySubcategoryLabel,
  liquidityCheckinRowSummary,
  suggestedLiquidityClosingBalanceForRow,
  suggestedIncomeExecutedAmountForRow,
  suggestedExecutedAmountForRow,
  incomeCheckinRowSummary,
  expenseCheckinRowSummary,
} from '@/views/budget/budgetDashboardUtils';
import type {
  LiquidityExecutionRow,
  IncomeExecutionRow,
  ExpenseExecutionRow,
} from '@/views/budget/budgetDashboardUtils';
import type { AnnualIncomeEntry, AnnualExpenseEntry } from '@/domains/budget/annual-entries';

// ── aggregateBudgetRows ───────────────────────────────────────────────────────

describe('aggregateBudgetRows', () => {
  const catLabels = new Map([['consumption_expenses', 'Gastos']]);
  const subLabels = new Map([
    ['food', 'Alimentación'],
    ['transport', 'Transporte'],
  ]);

  it('groups a single entry into a BudgetGroup', () => {
    const entries = [{ category: 'consumption_expenses', subcategory: 'food', amountAnnual: 500 }];
    const groups = aggregateBudgetRows(entries, catLabels, subLabels);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.categoryKey).toBe('consumption_expenses');
    expect(groups[0]!.plannedAnnual).toBe(500);
    expect(groups[0]!.rows).toHaveLength(1);
  });

  it('merges two entries in the same category into one group', () => {
    const entries = [
      { category: 'consumption_expenses', subcategory: 'food', amountAnnual: 200 },
      { category: 'consumption_expenses', subcategory: 'transport', amountAnnual: 100 },
    ];
    const groups = aggregateBudgetRows(entries, catLabels, subLabels);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.plannedAnnual).toBe(300);
    expect(groups[0]!.rows).toHaveLength(2);
  });

  it('accumulates multiple entries in the same subcategory bucket', () => {
    const entries = [
      { category: 'consumption_expenses', subcategory: 'food', amountAnnual: 100 },
      { category: 'consumption_expenses', subcategory: 'food', amountAnnual: 150 },
    ];
    const groups = aggregateBudgetRows(entries, catLabels, subLabels);
    expect(groups[0]!.rows[0]!.plannedAnnual).toBe(250);
  });

  it('skips entries with zero or negative amount', () => {
    const entries = [
      { category: 'consumption_expenses', subcategory: 'food', amountAnnual: 0 },
      { category: 'consumption_expenses', subcategory: 'food', amountAnnual: -10 },
    ];
    const groups = aggregateBudgetRows(entries, catLabels, subLabels);
    expect(groups).toHaveLength(0);
  });

  it('sorts rows with equal plannedAnnual by subcategoryLabel', () => {
    const entries = [
      { category: 'consumption_expenses', subcategory: 'transport', amountAnnual: 100 },
      { category: 'consumption_expenses', subcategory: 'food', amountAnnual: 100 },
    ];
    const groups = aggregateBudgetRows(entries, catLabels, subLabels);
    expect(groups[0]!.rows[0]!.subcategoryLabel).toBe('Alimentación');
    expect(groups[0]!.rows[1]!.subcategoryLabel).toBe('Transporte');
  });
});

// ── buildMonthlyResultBreakdown ───────────────────────────────────────────────

describe('buildMonthlyResultBreakdown', () => {
  const catLabels = new Map([['consumption_expenses', 'Gastos']]);
  const subLabels = new Map([['food', 'Alimentación']]);

  it('returns empty array for no rows', () => {
    expect(buildMonthlyResultBreakdown([], catLabels, subLabels, 0)).toEqual([]);
  });

  it('groups a single row into a breakdown group', () => {
    const rows = [
      {
        entry: { category: 'consumption_expenses', subcategory: 'food' },
        planned: 100,
        checkin: { status: 'confirmed' as const },
        executed: 90,
        executionSource: 'categorized_ledger' as const,
      },
    ];
    const groups = buildMonthlyResultBreakdown(rows, catLabels, subLabels, 90);
    expect(groups).toHaveLength(1);
    expect(groups[0]!.categoryKey).toBe('consumption_expenses');
    expect(groups[0]!.plannedTotal).toBe(100);
    expect(groups[0]!.checkedCount).toBe(1);
  });
});

// ── isLockedExecutionRow ──────────────────────────────────────────────────────

describe('isLockedExecutionRow', () => {
  it('returns true for categorized_ledger origin', () => {
    expect(isLockedExecutionRow({ executionOrigin: 'categorized_ledger' })).toBe(true);
  });

  it('returns false for other origins', () => {
    expect(isLockedExecutionRow({ executionOrigin: 'none' as 'categorized_ledger' })).toBe(false);
    expect(
      isLockedExecutionRow({ executionOrigin: 'legacy_checkin' as 'categorized_ledger' }),
    ).toBe(false);
  });
});

// ── buildActualExecution ──────────────────────────────────────────────────────

describe('buildActualExecution', () => {
  it('returns zero state when both planned and executed are zero/invalid', () => {
    const result = buildActualExecution('income', 0, 0, 0);
    expect(result).not.toBeNull();
    expect(result?.planned).toBe(0);
    expect(result?.executed).toBe(0);
    expect(result?.tone).toBe('neutral');
  });

  it('returns unplanned execution when planned=0 but executed>0 for income', () => {
    const result = buildActualExecution('income', 0, 500, 1);
    expect(result).not.toBeNull();
    expect(result?.tone).toBe('neutral');
    expect(result?.executed).toBe(500);
  });

  it('returns unplanned execution as warn for expense', () => {
    const result = buildActualExecution('expense', 0, 500, 1);
    expect(result?.tone).toBe('warn');
  });

  it('returns normal execution when planned > 0', () => {
    const result = buildActualExecution('income', 1000, 1000, 1);
    expect(result).not.toBeNull();
    expect(result?.ratio).toBe(1);
    expect(result?.overflow).toBe(false);
  });

  it('marks overflow when executed > planned', () => {
    const result = buildActualExecution('expense', 1000, 1200, 1);
    expect(result?.overflow).toBe(true);
  });
});

// ── executionSourceLabel ──────────────────────────────────────────────────────

describe('executionSourceLabel', () => {
  it('maps categorized_ledger', () => {
    expect(executionSourceLabel('categorized_ledger')).toBe('Movimientos');
  });

  it('maps legacy_checkin', () => {
    expect(executionSourceLabel('legacy_checkin')).toBe('Manual');
  });

  it('maps user_override', () => {
    expect(executionSourceLabel('user_override')).toBe('Ajuste manual');
  });

  it('maps ambiguous_taxonomy', () => {
    expect(executionSourceLabel('ambiguous_taxonomy')).toBe('Pendiente clasificar');
  });

  it('returns empty string for unknown origin', () => {
    expect(executionSourceLabel('none' as 'categorized_ledger')).toBe('');
  });
});

// ── executionToneFor ──────────────────────────────────────────────────────────

describe('executionToneFor', () => {
  it('income: good when ratio >= 1', () => {
    expect(executionToneFor('income', 1.0)).toBe('good');
    expect(executionToneFor('income', 1.5)).toBe('good');
  });

  it('income: neutral when 0.8 <= ratio < 1', () => {
    expect(executionToneFor('income', 0.85)).toBe('neutral');
  });

  it('income: warn when 0.5 <= ratio < 0.8', () => {
    expect(executionToneFor('income', 0.65)).toBe('warn');
  });

  it('income: danger when ratio < 0.5', () => {
    expect(executionToneFor('income', 0.3)).toBe('danger');
  });

  it('expense: good when ratio <= 1', () => {
    expect(executionToneFor('expense', 0.9)).toBe('good');
  });

  it('expense: neutral when 1 < ratio <= 1.1', () => {
    expect(executionToneFor('expense', 1.05)).toBe('neutral');
  });

  it('expense: warn when 1.1 < ratio <= 1.25', () => {
    expect(executionToneFor('expense', 1.2)).toBe('warn');
  });

  it('expense: danger when ratio > 1.25', () => {
    expect(executionToneFor('expense', 1.5)).toBe('danger');
  });
});

// ── hashToUnitInterval ────────────────────────────────────────────────────────

describe('hashToUnitInterval', () => {
  it('returns a number in [0, 1]', () => {
    for (const seed of ['a', 'abc', 'test-seed', 'salary-2025', 'xy', '']) {
      const val = hashToUnitInterval(seed);
      expect(val).toBeGreaterThanOrEqual(0);
      expect(val).toBeLessThanOrEqual(1);
    }
  });

  it('is deterministic for the same input', () => {
    expect(hashToUnitInterval('same-seed')).toBe(hashToUnitInterval('same-seed'));
  });
});

// ── mockExecutionRatio ────────────────────────────────────────────────────────

describe('mockExecutionRatio', () => {
  const seeds = [
    'a',
    'b',
    'c',
    'd',
    'ab',
    'abc',
    'xyz',
    '1234',
    'seed1',
    'seed2',
    'income-2025-1',
    'expense-rent',
    'salary',
    'housing',
    'long-seed-key-for-hashing',
    'alpha',
    'beta',
    'gamma',
    'delta',
    'epsilon',
  ];

  it('always returns a finite positive number for income', () => {
    for (const seed of seeds) {
      const val = mockExecutionRatio('income', seed);
      expect(Number.isFinite(val)).toBe(true);
      expect(val).toBeGreaterThan(0);
    }
  });

  it('always returns a finite positive number for expense', () => {
    for (const seed of seeds) {
      const val = mockExecutionRatio('expense', seed);
      expect(Number.isFinite(val)).toBe(true);
      expect(val).toBeGreaterThan(0);
    }
  });
});

// ── parseSharedOwnerShares ────────────────────────────────────────────────────

describe('parseSharedOwnerShares', () => {
  it('returns empty array for empty string', () => {
    expect(parseSharedOwnerShares('')).toEqual([]);
  });

  it('returns empty array for non-shared label', () => {
    expect(parseSharedOwnerShares('Alice')).toEqual([]);
  });

  it('parses two-member shared ownership', () => {
    const result = parseSharedOwnerShares('Compartido (Alice 50% / Bob 50%)');
    expect(result).toHaveLength(2);
    expect(result[0]).toEqual({ name: 'Alice', share: 50 });
    expect(result[1]).toEqual({ name: 'Bob', share: 50 });
  });

  it('parses unequal shares', () => {
    const result = parseSharedOwnerShares('Compartido (Ana 70% / Juan 30%)');
    expect(result[0]).toMatchObject({ name: 'Ana', share: 70 });
    expect(result[1]).toMatchObject({ name: 'Juan', share: 30 });
  });
});

// ── ownerNamesFromLabel ───────────────────────────────────────────────────────

describe('ownerNamesFromLabel', () => {
  it('returns empty for empty string', () => {
    expect(ownerNamesFromLabel('')).toEqual([]);
  });

  it('returns single name for individual label', () => {
    expect(ownerNamesFromLabel('Alice')).toEqual(['Alice']);
  });

  it('returns both names for shared label', () => {
    const names = ownerNamesFromLabel('Compartido (Alice 60% / Bob 40%)');
    expect(names).toEqual(['Alice', 'Bob']);
  });
});

// ── allocationFractionForOwnerLabel ──────────────────────────────────────────

describe('allocationFractionForOwnerLabel', () => {
  it('returns 1 when selectedOwner is all', () => {
    expect(allocationFractionForOwnerLabel('Alice', 'all')).toBe(1);
  });

  it('returns 1 for exact individual match', () => {
    expect(allocationFractionForOwnerLabel('Alice', 'Alice')).toBe(1);
  });

  it('returns 0 for non-matching individual', () => {
    expect(allocationFractionForOwnerLabel('Alice', 'Bob')).toBe(0);
  });

  it('returns correct fraction for shared 50/50', () => {
    const label = 'Compartido (Alice 50% / Bob 50%)';
    expect(allocationFractionForOwnerLabel(label, 'Alice')).toBeCloseTo(0.5);
    expect(allocationFractionForOwnerLabel(label, 'Bob')).toBeCloseTo(0.5);
  });

  it('returns 0 for unknown owner in shared label', () => {
    const label = 'Compartido (Alice 50% / Bob 50%)';
    expect(allocationFractionForOwnerLabel(label, 'Carlos')).toBe(0);
  });
});

// ── sumPlanned ────────────────────────────────────────────────────────────────

describe('sumPlanned', () => {
  it('returns 0 for empty array', () => {
    expect(sumPlanned([])).toBe(0);
  });

  it('sums amountAnnual values', () => {
    expect(sumPlanned([{ amountAnnual: 100 }, { amountAnnual: 200 }])).toBe(300);
  });
});

// ── toNumberOrZero ────────────────────────────────────────────────────────────

describe('toNumberOrZero', () => {
  it('converts valid number string', () => {
    expect(toNumberOrZero('42.5')).toBe(42.5);
  });

  it('returns 0 for null', () => {
    expect(toNumberOrZero(null)).toBe(0);
  });

  it('returns 0 for NaN input', () => {
    expect(toNumberOrZero('not-a-number')).toBe(0);
  });
});

// ── monthlySummaryExecutedTotal ───────────────────────────────────────────────

describe('monthlySummaryExecutedTotal', () => {
  it('returns null for null input', () => {
    expect(monthlySummaryExecutedTotal(null)).toBeNull();
  });

  it('prefers executed_total when available', () => {
    const row = {
      month: 1,
      planned: '100',
      executed: '90',
      pending: '10',
      completion_ratio: 0.9,
      checkins_confirmed: 1,
      checkins_expected: 1,
      executed_total: '90',
    };
    expect(monthlySummaryExecutedTotal(row)).toBe(90);
  });

  it('falls back to executed when executed_total missing', () => {
    const row = {
      month: 1,
      planned: '100',
      executed: '85',
      pending: '15',
      completion_ratio: 0.85,
      checkins_confirmed: 1,
      checkins_expected: 1,
    };
    expect(monthlySummaryExecutedTotal(row)).toBe(85);
  });
});

// ── taxonomy key builders ─────────────────────────────────────────────────────

describe('budgetTaxonomyKey', () => {
  it('builds category::subcategory key', () => {
    const key = budgetTaxonomyKey('consumption_expenses', 'food');
    expect(key).toMatch(/consumption_expenses::food/);
  });
});

describe('budgetMonthTaxonomyKey', () => {
  it('prepends month to taxonomy key', () => {
    const key = budgetMonthTaxonomyKey(3, 'salary', 'regular');
    expect(key.startsWith('3::')).toBe(true);
  });
});

describe('budgetMonthEntryKey', () => {
  it('builds month::id key', () => {
    expect(budgetMonthEntryKey(5, 42)).toBe('5::42');
  });
});

describe('parseBudgetTaxonomyKey', () => {
  it('splits category and subcategory', () => {
    expect(parseBudgetTaxonomyKey('salary::regular')).toEqual({
      categoryKey: 'salary',
      subcategoryKey: 'regular',
    });
  });

  it('handles missing subcategory gracefully', () => {
    const result = parseBudgetTaxonomyKey('salary');
    expect(result.categoryKey).toBe('salary');
    expect(result.subcategoryKey).toBe('');
  });
});

// ── entry/month key builders ──────────────────────────────────────────────────

describe('incomeEntryMonthKey', () => {
  it('builds entryId:month string', () => {
    expect(incomeEntryMonthKey(7, 3)).toBe('7:3');
  });
});

describe('expenseEntryMonthKey', () => {
  it('builds entryId:month string', () => {
    expect(expenseEntryMonthKey(12, 11)).toBe('12:11');
  });
});

// ── cleanedExpenseCheckinName ─────────────────────────────────────────────────

describe('cleanedExpenseCheckinName', () => {
  it('removes "Compromiso pasivo:" prefix', () => {
    expect(cleanedExpenseCheckinName('Compromiso pasivo: Hipoteca')).toBe('Hipoteca');
  });

  it('returns unchanged string without prefix', () => {
    expect(cleanedExpenseCheckinName('Alquiler')).toBe('Alquiler');
  });

  it('is case-insensitive for prefix', () => {
    expect(cleanedExpenseCheckinName('COMPROMISO PASIVO: X')).toBe('X');
  });
});

// ── shortExpenseCategoryLabel ─────────────────────────────────────────────────

describe('shortExpenseCategoryLabel', () => {
  it('maps real_estate_assets', () => {
    expect(shortExpenseCategoryLabel('real_estate_assets')).toBe('Activos inmobiliarios');
  });

  it('maps tangible_assets', () => {
    expect(shortExpenseCategoryLabel('tangible_assets')).toBe('Activos mobiliarios');
  });

  it('maps consumption_expenses', () => {
    expect(shortExpenseCategoryLabel('consumption_expenses')).toBe('Gastos');
  });

  it('maps financial_investments', () => {
    expect(shortExpenseCategoryLabel('financial_investments')).toBe('Inversion financiera');
  });

  it('maps savings_allocation', () => {
    expect(shortExpenseCategoryLabel('savings_allocation')).toBe('Ahorro');
  });

  it('returns the key for unknown categories', () => {
    expect(shortExpenseCategoryLabel('unknown_cat')).toBe('unknown_cat');
  });
});

// ── expenseCheckinCategorySortWeight ──────────────────────────────────────────

describe('expenseCheckinCategorySortWeight', () => {
  it('real_estate_assets has weight 0', () => {
    expect(expenseCheckinCategorySortWeight('real_estate_assets')).toBe(0);
  });

  it('unknown category returns 99', () => {
    expect(expenseCheckinCategorySortWeight('other')).toBe(99);
  });

  it('correct relative order', () => {
    const w = (c: string) => expenseCheckinCategorySortWeight(c);
    expect(w('real_estate_assets')).toBeLessThan(w('tangible_assets'));
    expect(w('tangible_assets')).toBeLessThan(w('financial_investments'));
    expect(w('financial_investments')).toBeLessThan(w('consumption_expenses'));
    expect(w('consumption_expenses')).toBeLessThan(w('savings_allocation'));
  });
});

// ── amountsEqualCents ─────────────────────────────────────────────────────────

describe('amountsEqualCents', () => {
  it('returns true for equal amounts', () => {
    expect(amountsEqualCents(10.5, 10.5)).toBe(true);
  });

  it('returns false for differing amounts', () => {
    expect(amountsEqualCents(10.5, 10.51)).toBe(false);
  });

  it('tolerates sub-cent floating point difference', () => {
    expect(amountsEqualCents(10.001, 10.002)).toBe(true);
  });
});

// ── shortLiquiditySubcategoryLabel ───────────────────────────────────────────

describe('shortLiquiditySubcategoryLabel', () => {
  it('maps credit_card', () => {
    expect(shortLiquiditySubcategoryLabel('credit_card')).toBe('Tarjeta de crédito');
  });

  it('maps bank_account', () => {
    expect(shortLiquiditySubcategoryLabel('bank_account')).toBe('Cuenta bancaria');
  });

  it('returns Liquidez for unknown subcategory', () => {
    expect(shortLiquiditySubcategoryLabel('other')).toBe('Liquidez');
  });
});

// ── row summary helpers ───────────────────────────────────────────────────────

function makeLiquidityRow(overrides: Partial<LiquidityExecutionRow> = {}): LiquidityExecutionRow {
  return {
    row_type: 'asset',
    asset_id: 1,
    asset_name: 'Cuenta corriente',
    asset_category: 'liquidity',
    asset_subcategory: 'bank_account',
    currency: 'EUR',
    planned_closing_balance: '1000',
    executed_closing_balance: null,
    effective_closing_balance: '1000',
    deviation: '0',
    planned_closing_balance_base: '1000',
    executed_closing_balance_base: null,
    effective_closing_balance_base: '1000',
    deviation_base: '0',
    checkin: null,
    planned: 1000,
    executed: null,
    ...overrides,
  };
}

describe('liquidityCheckinRowSummary', () => {
  it('builds asset row summary', () => {
    const row = makeLiquidityRow({ asset_subcategory: 'bank_account', asset_name: 'BBVA' });
    expect(liquidityCheckinRowSummary(row)).toBe('Cuenta bancaria - BBVA');
  });

  it('builds liability row summary', () => {
    const row = makeLiquidityRow({
      row_type: 'liability',
      liability_category: 'credit_card',
      liability_name: 'Visa',
    });
    expect(liquidityCheckinRowSummary(row)).toBe('Tarjeta de crédito - Visa');
  });
});

describe('suggestedLiquidityClosingBalanceForRow', () => {
  it('returns executed amount when present', () => {
    const row = makeLiquidityRow({ executed: 950.5 });
    expect(suggestedLiquidityClosingBalanceForRow(row)).toBe('950.50');
  });

  it('falls back to planned when executed is null', () => {
    const row = makeLiquidityRow({ planned: 1000, executed: null });
    expect(suggestedLiquidityClosingBalanceForRow(row)).toBe('1000.00');
  });
});

function makeIncomeRow(overrides: Partial<IncomeExecutionRow> = {}): IncomeExecutionRow {
  return {
    entry: {
      id: 1,
      name: 'Sueldo',
      category: 'salary',
      subcategory: 'regular',
      income_type: 'recurrent',
      amount_annual: '24000',
      fiscal_year: 2025,
      currency: 'EUR',
      notes: '',
      is_active: true,
    } as unknown as AnnualIncomeEntry,
    planned: 2000,
    checkin: null,
    executed: null,
    executionOrigin: 'none',
    categorizedLedgerExecuted: null,
    executionSource: 'none',
    ...overrides,
  };
}

describe('suggestedIncomeExecutedAmountForRow', () => {
  it('returns 0.00 when checkin is skipped', () => {
    const row = makeIncomeRow({
      checkin: {
        id: 1,
        annual_income_entry_id: 1,
        fiscal_year: 2025,
        month: 1,
        status: 'skipped',
        executed_amount: null,
        note: '',
        confirmed_at: null,
        created_at: '',
        updated_at: '',
      },
    });
    expect(suggestedIncomeExecutedAmountForRow(row)).toBe('0.00');
  });

  it('returns executed amount when present', () => {
    const row = makeIncomeRow({ executed: 1800 });
    expect(suggestedIncomeExecutedAmountForRow(row)).toBe('1800.00');
  });

  it('falls back to planned', () => {
    const row = makeIncomeRow({ planned: 2000, executed: null });
    expect(suggestedIncomeExecutedAmountForRow(row)).toBe('2000.00');
  });
});

function makeExpenseRow(overrides: Partial<ExpenseExecutionRow> = {}): ExpenseExecutionRow {
  return {
    entry: {
      id: 1,
      name: 'Alquiler',
      category: 'housing',
      subcategory: 'rent',
      expense_type: 'recurrent',
      amount_annual: '12000',
      fiscal_year: 2025,
      currency: 'EUR',
      notes: '',
      is_active: true,
    } as unknown as AnnualExpenseEntry,
    planned: 1000,
    checkin: null,
    executed: null,
    executionOrigin: 'none',
    categorizedLedgerExecuted: null,
    executionSource: 'none',
    ...overrides,
  };
}

describe('suggestedExecutedAmountForRow', () => {
  it('returns 0.00 when checkin is skipped', () => {
    const row = makeExpenseRow({
      checkin: {
        id: 1,
        annual_expense_entry_id: 1,
        fiscal_year: 2025,
        month: 1,
        status: 'skipped',
        executed_amount: null,
        note: '',
        confirmed_at: null,
        created_at: '',
        updated_at: '',
      },
    });
    expect(suggestedExecutedAmountForRow(row)).toBe('0.00');
  });

  it('returns executed when present', () => {
    const row = makeExpenseRow({ executed: 850.25 });
    expect(suggestedExecutedAmountForRow(row)).toBe('850.25');
  });

  it('falls back to planned', () => {
    const row = makeExpenseRow({ planned: 1000, executed: null });
    expect(suggestedExecutedAmountForRow(row)).toBe('1000.00');
  });
});

describe('incomeCheckinRowSummary', () => {
  it('builds subcategory - name summary', () => {
    const row = makeIncomeRow();
    const summary = incomeCheckinRowSummary(row);
    expect(summary).toContain('Sueldo');
    expect(summary).toContain(' - ');
  });
});

describe('expenseCheckinRowSummary', () => {
  it('builds subcategory - name summary, stripping passive prefix', () => {
    const row = makeExpenseRow({
      entry: {
        id: 1,
        name: 'Compromiso pasivo: Hipoteca',
        category: 'housing',
        subcategory: 'rent',
        expense_type: 'recurrent',
        amount_annual: '12000',
        fiscal_year: 2025,
        currency: 'EUR',
        notes: '',
        is_active: true,
      } as unknown as AnnualExpenseEntry,
    });
    const summary = expenseCheckinRowSummary(row);
    expect(summary).toContain('Hipoteca');
    expect(summary).not.toContain('Compromiso pasivo');
  });
});

// ── expenseCategorySortIndex ──────────────────────────────────────────────────

describe('expenseCategorySortIndex', () => {
  it('returns a finite index for known categories', () => {
    const idx = expenseCategorySortIndex('consumption_expenses');
    expect(typeof idx).toBe('number');
    expect(Number.isFinite(idx)).toBe(true);
  });

  it('returns 999 for unknown category', () => {
    expect(expenseCategorySortIndex('completely_unknown')).toBe(999);
  });
});

// ── checkinStatusLabel ────────────────────────────────────────────────────────

describe('checkinStatusLabel', () => {
  it('maps confirmed', () => {
    expect(checkinStatusLabel('confirmed')).toBe('Confirmado');
  });

  it('maps adjusted', () => {
    expect(checkinStatusLabel('adjusted')).toBe('Ajustado');
  });

  it('maps estimated', () => {
    expect(checkinStatusLabel('estimated')).toBe('Estimado');
  });

  it('maps skipped to No ocurrió', () => {
    expect(checkinStatusLabel('skipped')).toBe('No ocurrió');
  });
});
