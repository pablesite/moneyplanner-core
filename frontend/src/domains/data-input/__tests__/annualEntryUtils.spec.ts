import { describe, expect, it } from 'vitest';
import { normalizeOwnerName, parseAnnualAmount } from '../annualEntryUtils';

describe('annualEntryUtils (core)', () => {
  it('parses annual amounts with locale/thousand separators', () => {
    expect(parseAnnualAmount('1.234,56')).toBe(1234.56);
    expect(parseAnnualAmount('1,234.56')).toBe(1234.56);
    expect(parseAnnualAmount(' 2 500,00 ')).toBe(2500);
  });

  it('returns zero for invalid or non-positive amounts', () => {
    expect(parseAnnualAmount('0')).toBe(0);
    expect(parseAnnualAmount('-20')).toBe(0);
    expect(parseAnnualAmount('abc')).toBe(0);
  });

  it('normalizes owner name safely', () => {
    expect(normalizeOwnerName('   Ana   López   ')).toBe('Ana López');
  });
});
