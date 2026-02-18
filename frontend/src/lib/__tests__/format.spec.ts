import { describe, expect, it } from 'vitest';
import { formatAmount, formatMoney, getMaxDecimals, normalizeNumberInput } from '@/lib/format';

describe('format helpers', () => {
  it('normalizes number input with spaces and commas', () => {
    expect(normalizeNumberInput(' 1 234,56 ')).toBe('1234.56');
    expect(normalizeNumberInput(undefined)).toBe('');
  });

  it('resolves max decimals by currency with fallback', () => {
    expect(getMaxDecimals('EUR')).toBe(2);
    expect(getMaxDecimals('BTC')).toBe(8);
    expect(getMaxDecimals('UNKNOWN')).toBe(2);
    expect(getMaxDecimals()).toBe(2);
  });

  it('formats amount and money values', () => {
    expect(formatAmount('1234,567', { currency: 'EUR' })).toBe('1.234,57');
    expect(formatAmount('0.12345678', { currency: 'BTC' })).toBe('0,12345678');
    expect(formatAmount('abc')).toBe('abc');

    const eur = formatMoney('1234,5', 'EUR');
    const usd = formatMoney('1234,5', 'USD');
    expect(eur).toContain('1.234,50');
    expect(usd).toContain('1.234,50');
    expect(formatMoney('abc')).toBe('abc');
  });
});
