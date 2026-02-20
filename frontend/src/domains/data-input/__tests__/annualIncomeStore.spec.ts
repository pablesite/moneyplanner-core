import { beforeEach, describe, expect, it } from 'vitest';
import { useAnnualIncomeStore } from '../annualIncomeStore';

describe('annual income store (core)', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it('adds a valid annual income entry and computes total', () => {
    const store = useAnnualIncomeStore('core');
    const result = store.addEntry({
      name: 'CTN',
      category: 'salary',
      subcategory: 'employee_salary',
      owner: 'Pablo',
      incomeType: 'recurrent',
      amountAnnual: '32460,00',
      currency: 'EUR',
      notes: '',
    });

    expect(result.ok).toBe(true);
    expect(store.entries.value).toHaveLength(1);
    expect(store.totalAnnual.value).toBe(32460);
  });

  it('rejects mismatched category/subcategory', () => {
    const store = useAnnualIncomeStore('core');
    const result = store.addEntry({
      name: 'Linea invalida',
      category: 'salary',
      subcategory: 'inheritance',
      owner: '',
      incomeType: 'one_off',
      amountAnnual: '1000',
      currency: 'EUR',
      notes: '',
    });

    expect(result.ok).toBe(false);
    expect(store.entries.value).toHaveLength(0);
  });
});
