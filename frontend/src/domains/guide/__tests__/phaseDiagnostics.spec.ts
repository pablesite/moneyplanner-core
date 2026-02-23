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
    expect(stable.phase2GlobalScore).toBeGreaterThan(85);
    expect(volatile.phase2GlobalScore).toBeLessThan(10);
  });
});
