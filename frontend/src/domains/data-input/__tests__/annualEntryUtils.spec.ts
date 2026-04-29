import { describe, expect, it } from 'vitest';
import {
  amountInputValueFromStoredAnnual,
  effectiveAnnualAmountForEntry,
  normalizeOwnerName,
  parseAnnualAmount,
} from '../annualEntryUtils';

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
    expect(normalizeOwnerName('   Ana   LÃ³pez   ')).toBe('Ana LÃ³pez');
  });

  it('scales monthly temporary commitments to active months in the selected fiscal year', () => {
    expect(
      effectiveAnnualAmountForEntry({
        amountAnnual: 16488,
        amountInputPeriod: 'monthly',
        timeProfile: 'term_recurrent',
        termEndMonth: 9,
        termEndYear: 2026,
        fiscalYear: 2026,
      }),
    ).toBe(12366);
  });

  it('recovers the original monthly input for monthly temporary commitments', () => {
    expect(
      amountInputValueFromStoredAnnual(
        {
          amountAnnual: 16488,
          amountInputPeriod: 'monthly',
          timeProfile: 'term_recurrent',
          termEndMonth: 9,
          termEndYear: 2026,
          fiscalYear: 2026,
        },
        'monthly',
      ),
    ).toBe('1374');
  });
});
