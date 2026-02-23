import { describe, expect, it } from 'vitest';
import { computeGuidePhaseDiagnostics } from '../phaseDiagnostics';

describe('computeGuidePhaseDiagnostics', () => {
  it('scores phase 2 higher for stable recurring surplus than volatile deficit flow', () => {
    const stable = computeGuidePhaseDiagnostics({
      summary: null,
      assets: [],
      liabilities: [],
      annualIncomeEntries: [
        { incomeType: 'recurrent', amountAnnual: 24000 },
        { incomeType: 'one_off', amountAnnual: 1000 },
      ],
      annualExpenseEntries: [
        { expenseType: 'recurrent', amountAnnual: 18000 },
        { expenseType: 'one_off', amountAnnual: 500 },
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
        { expenseType: 'recurrent', amountAnnual: 17000 },
        { expenseType: 'one_off', amountAnnual: 4000 },
      ],
    });

    expect(stable.phase2GlobalScore).toBeGreaterThan(volatile.phase2GlobalScore);
    expect(stable.phase2GlobalScore).toBeGreaterThan(70);
    expect(volatile.phase2GlobalScore).toBeLessThan(40);
  });
});
