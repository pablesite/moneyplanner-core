import { describe, expect, it } from 'vitest';
import { expenseCategories, expenseSubcategories } from '../expenseTaxonomy';

describe('expense taxonomy (core)', () => {
  it('defines subcategories for every category', () => {
    const categories = expenseCategories.map((c) => c.value);
    for (const category of categories) {
      const rows = expenseSubcategories.filter((sub) => sub.category === category);
      expect(rows.length).toBeGreaterThan(0);
    }
  });

  it('includes at least one fallback subcategory per category', () => {
    const categories = expenseCategories.map((c) => c.value);
    for (const category of categories) {
      const rows = expenseSubcategories.filter((sub) => sub.category === category);
      const hasFallback = rows.some(
        (sub) => sub.value.startsWith('other') || sub.value === 'other',
      );
      expect(hasFallback).toBe(true);
    }
  });
});
