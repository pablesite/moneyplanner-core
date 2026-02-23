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
    expect(stable.phase2GlobalScore).toBeGreaterThan(40);
    expect(stable.phase2GlobalScore).toBeLessThan(70);
    expect(volatile.phase2GlobalScore).toBeLessThan(20);
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
    expect(base.phase2GlobalScore).toBeGreaterThan(70);
  });

  it('rewards low structural operating load and penalizes full operating load in phase 2', () => {
    const healthy = computeGuidePhaseDiagnostics({
      summary: null,
      assets: [],
      liabilities: [],
      annualIncomeEntries: [{ incomeType: 'recurrent', amountAnnual: 24000 }],
      annualExpenseEntries: [
        { category: 'consumption_expenses', expenseType: 'recurrent', amountAnnual: 12000 },
      ],
    });

    const stressed = computeGuidePhaseDiagnostics({
      summary: null,
      assets: [],
      liabilities: [],
      annualIncomeEntries: [{ incomeType: 'recurrent', amountAnnual: 24000 }],
      annualExpenseEntries: [
        { category: 'consumption_expenses', expenseType: 'recurrent', amountAnnual: 24000 },
      ],
    });

    expect(healthy.phase2GlobalScore).toBeGreaterThan(stressed.phase2GlobalScore);
    expect(healthy.phase2GlobalScore).toBeGreaterThan(80);
    expect(stressed.phase2GlobalScore).toBeLessThan(30);
  });

  it('penalizes temporary recurring commitments in phase 2 tension score', () => {
    const noCommitments = computeGuidePhaseDiagnostics({
      summary: null,
      assets: [],
      liabilities: [],
      annualIncomeEntries: [{ incomeType: 'recurrent', amountAnnual: 36000 }],
      annualExpenseEntries: [
        {
          category: 'consumption_expenses',
          expenseType: 'recurrent',
          timeProfile: 'structural_recurrent',
          cashflowRole: 'operating',
          amountAnnual: 18000,
        },
      ],
    });

    const withTemporaryCommitments = computeGuidePhaseDiagnostics({
      summary: null,
      assets: [],
      liabilities: [],
      annualIncomeEntries: [{ incomeType: 'recurrent', amountAnnual: 36000 }],
      annualExpenseEntries: [
        {
          category: 'consumption_expenses',
          expenseType: 'recurrent',
          timeProfile: 'structural_recurrent',
          cashflowRole: 'operating',
          amountAnnual: 18000,
        },
        {
          category: 'consumption_expenses',
          expenseType: 'recurrent',
          timeProfile: 'term_recurrent',
          cashflowRole: 'temporary_commitment',
          amountAnnual: 9000,
        },
      ],
    });

    expect(withTemporaryCommitments.phase2GlobalScore).toBeLessThan(
      noCommitments.phase2GlobalScore,
    );
  });

  it('keeps diagnostics finite when liabilities exist but there is no recurrent income', () => {
    const diagnostics = computeGuidePhaseDiagnostics({
      summary: {
        total_assets: '50000',
        total_liabilities: '10000',
        net_worth: '40000',
        liabilities_unbacked: '10000',
        assets_by_category: { cash: '50000' },
        assets_by_subcategory: {},
        liabilities_by_category: { personal_loan: '10000' },
        base_currency: 'EUR',
      } as any,
      assets: [
        {
          id: 1,
          category: 'cash',
          subcategory: 'bank_account',
          amount_base: '50000',
          is_active: true,
        },
      ] as any,
      liabilities: [
        {
          id: 1,
          amount_base: '10000',
          annual_interest_tae: '12',
          monthly_payment_amount: '250',
          is_active: true,
        },
      ] as any,
      annualIncomeEntries: [{ incomeType: 'one_off', amountAnnual: 5000 }],
      annualExpenseEntries: [],
    });

    expect(Number.isFinite(diagnostics.phase1GlobalScore)).toBe(true);
    expect(diagnostics.phase1GlobalScore).toBeGreaterThanOrEqual(0);
    expect(diagnostics.phase1GlobalScore).toBeLessThanOrEqual(100);
  });

  it('handles liabilities without monthly payment inputs without penalizing debt-cost payment subscore path', () => {
    const diagnostics = computeGuidePhaseDiagnostics({
      summary: {
        total_assets: '20000',
        total_liabilities: '6000',
        net_worth: '14000',
        liabilities_unbacked: '6000',
        assets_by_category: { cash: '20000' },
        assets_by_subcategory: {},
        liabilities_by_category: { personal_loan: '6000' },
        base_currency: 'EUR',
      } as any,
      assets: [
        {
          id: 1,
          category: 'cash',
          subcategory: 'bank_account',
          amount_base: '20000',
          is_active: true,
        },
      ] as any,
      liabilities: [
        {
          id: 1,
          amount_base: '6000',
          annual_interest_tae: '6',
          monthly_payment_amount: '',
          is_active: true,
        },
      ] as any,
      annualIncomeEntries: [{ incomeType: 'recurrent', amountAnnual: 24000 }],
      annualExpenseEntries: [],
    });

    expect(Number.isFinite(diagnostics.phase1GlobalScore)).toBe(true);
    expect(Number.isFinite(diagnostics.phase4GlobalScore)).toBe(true);
  });
});
