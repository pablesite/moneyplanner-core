import { describe, expect, it } from 'vitest';
import { incomeCategories, incomeSubcategories } from '../incomeTaxonomy';

describe('income taxonomy (core)', () => {
  it('defines subcategories for every category', () => {
    const categories = incomeCategories.map((c) => c.value);
    for (const category of categories) {
      const rows = incomeSubcategories.filter((sub) => sub.category === category);
      expect(rows.length).toBeGreaterThan(0);
    }
  });

  it('includes at least one fallback subcategory per category', () => {
    const categories = incomeCategories.map((c) => c.value);
    for (const category of categories) {
      const rows = incomeSubcategories.filter((sub) => sub.category === category);
      const hasFallback = rows.some(
        (sub) => sub.value.startsWith('other') || sub.value === 'other',
      );
      expect(hasFallback).toBe(true);
    }
  });
});
