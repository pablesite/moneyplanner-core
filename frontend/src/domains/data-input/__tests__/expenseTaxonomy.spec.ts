import { describe, expect, it } from 'vitest';
import { normalizeExpenseTaxonomy } from '../expenseTaxonomy';

describe('expenseTaxonomy (core)', () => {
  it('normalizes the legacy financial investment alias to the canonical ETF key', () => {
    expect(normalizeExpenseTaxonomy('financial_investments', 'index_funds_etf')).toEqual({
      category: 'financial_investments',
      subcategory: 'etf_indexed',
    });
  });

  it('keeps unrelated taxonomy keys unchanged', () => {
    expect(normalizeExpenseTaxonomy('financial_investments', 'crypto')).toEqual({
      category: 'financial_investments',
      subcategory: 'crypto',
    });
  });

  it('accepts deposits fixed income as a first-class investment subcategory', () => {
    expect(normalizeExpenseTaxonomy('financial_investments', 'deposits_fixed_income')).toEqual({
      category: 'financial_investments',
      subcategory: 'deposits_fixed_income',
    });
  });
});
