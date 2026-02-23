import { describe, expect, it } from 'vitest';
import { computeGuidePhaseDiagnostics } from '../phaseDiagnostics';

describe('computeGuidePhaseDiagnostics', () => {
  it('scores phase 2 from recurring operating flow and ignores extraordinary distortion in the main score', () => {
    const stable = computeGuidePhaseDiagnostics({
      summary: null,
      assets: [],
      liabilities: [],
      annualIncomeEntries: [
        { incomeType: 'recurrent', amountAnnual: 24000 },
        { incomeType: 'one_off', amountAnnual: 90000 },
      ],
      annualExpenseEntries: [
        { category: 'consumption_expenses', expenseType: 'recurrent', amountAnnual: 18000 },
        { category: 'savings_allocation', expenseType: 'recurrent', amountAnnual: 2000 },
        { category: 'real_estate_assets', expenseType: 'one_off', amountAnnual: 88000 },
      ],
    });

    const volatile = computeGuidePhaseDiagnostics({
      summary: null,
      assets: [],
      liabilities: [],
      annualIncomeEntries: [
        { incomeType: 'recurrent', amountAnnual: 12000 },
        { incomeType: 'one_off', amountAnnual: 12000 },
      ],
      annualExpenseEntries: [
        { category: 'consumption_expenses', expenseType: 'recurrent', amountAnnual: 17000 },
        { category: 'savings_allocation', expenseType: 'recurrent', amountAnnual: 0 },
        { category: 'real_estate_assets', expenseType: 'one_off', amountAnnual: 4000 },
      ],
    });

    expect(stable.phase2GlobalScore).toBeGreaterThan(volatile.phase2GlobalScore);
    expect(stable.phase2GlobalScore).toBeGreaterThan(45);
    expect(stable.phase2GlobalScore).toBeLessThan(55);
    expect(volatile.phase2GlobalScore).toBeLessThan(10);
  });

  it('ignores recurring savings and asset allocations in phase 2 operating ratio score', () => {
    const base = computeGuidePhaseDiagnostics({
      summary: null,
      assets: [],
      liabilities: [],
      annualIncomeEntries: [{ incomeType: 'recurrent', amountAnnual: 24000 }],
      annualExpenseEntries: [
        { category: 'consumption_expenses', expenseType: 'recurrent', amountAnnual: 14400 },
      ],
    });

    const withAllocations = computeGuidePhaseDiagnostics({
      summary: null,
      assets: [],
      liabilities: [],
      annualIncomeEntries: [{ incomeType: 'recurrent', amountAnnual: 24000 }],
      annualExpenseEntries: [
        { category: 'consumption_expenses', expenseType: 'recurrent', amountAnnual: 14400 },
        { category: 'savings_allocation', expenseType: 'recurrent', amountAnnual: 4000 },
        { category: 'financial_investments', expenseType: 'recurrent', amountAnnual: 3000 },
        { category: 'tangible_assets', expenseType: 'recurrent', amountAnnual: 1000 },
        { category: 'real_estate_assets', expenseType: 'recurrent', amountAnnual: 2000 },
        { category: 'real_estate_assets', expenseType: 'one_off', amountAnnual: 80000 },
      ],
    });

    expect(base.phase2GlobalScore).toBeCloseTo(withAllocations.phase2GlobalScore, 6);
    expect(base.phase2GlobalScore).toBeCloseTo(80, 6);
  });

  it('caps phase 2 score at top and bottom thresholds of operating expense ratio', () => {
    const top = computeGuidePhaseDiagnostics({
      summary: null,
      assets: [],
      liabilities: [],
      annualIncomeEntries: [{ incomeType: 'recurrent', amountAnnual: 24000 }],
      annualExpenseEntries: [
        { category: 'consumption_expenses', expenseType: 'recurrent', amountAnnual: 12000 },
      ],
    });

    const bottom = computeGuidePhaseDiagnostics({
      summary: null,
      assets: [],
      liabilities: [],
      annualIncomeEntries: [{ incomeType: 'recurrent', amountAnnual: 24000 }],
      annualExpenseEntries: [
        { category: 'consumption_expenses', expenseType: 'recurrent', amountAnnual: 24000 },
      ],
    });

    expect(top.phase2GlobalScore).toBeCloseTo(100, 6);
    expect(bottom.phase2GlobalScore).toBeCloseTo(0, 6);
  });
});
