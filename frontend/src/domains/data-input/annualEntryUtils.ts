export function parseAnnualAmount(raw: string): number {
  let normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '');

  const hasComma = normalized.includes(',');
  const hasDot = normalized.includes('.');
  if (hasComma && hasDot) {
    const lastComma = normalized.lastIndexOf(',');
    const lastDot = normalized.lastIndexOf('.');
    if (lastComma > lastDot) {
      normalized = normalized.replace(/\./g, '').replace(',', '.');
    } else {
      normalized = normalized.replace(/,/g, '');
    }
  } else if (hasComma) {
    normalized = normalized.replace(',', '.');
  }

  const value = Number(normalized);
  if (!Number.isFinite(value) || value <= 0) return 0;
  return value;
}

export function normalizeOwnerName(raw: string): string {
  return String(raw ?? '')
    .trim()
    .replace(/\s+/g, ' ')
    .slice(0, 120);
}

type AnnualizedEntryLike = {
  amountAnnual: number;
  amountInputPeriod?: 'annual' | 'monthly' | null;
  timeProfile?: string | null;
  termEndMonth?: number | null;
  termEndYear?: number | null;
  fiscalYear?: number | null;
};

function roundToMoney(value: number): number {
  return Math.round(value * 100) / 100;
}

function clampTermMonths(rawMonth: number | null | undefined): number {
  return Math.min(12, Math.max(1, Number(rawMonth ?? 12)));
}

function termEntryMonthsInSelectedYear(
  entry: AnnualizedEntryLike,
  selectedYear?: number | null,
): number {
  if (entry.timeProfile !== 'term_recurrent') return 12;
  if (entry.amountInputPeriod !== 'monthly') return 12;
  const targetYear = selectedYear ?? entry.fiscalYear ?? null;
  if (targetYear == null) return 12;
  if (entry.termEndYear != null && entry.termEndYear !== targetYear) return 12;
  return clampTermMonths(entry.termEndMonth);
}

export function effectiveAnnualAmountForEntry(
  entry: AnnualizedEntryLike,
  selectedYear?: number | null,
): number {
  const annualAmount = Number(entry.amountAnnual ?? 0);
  if (!Number.isFinite(annualAmount)) return 0;
  const months = termEntryMonthsInSelectedYear(entry, selectedYear);
  if (months === 12) return annualAmount;
  return roundToMoney((annualAmount * months) / 12);
}

export function amountInputValueFromStoredAnnual(
  entry: AnnualizedEntryLike,
  period: 'annual' | 'monthly',
  _selectedYear?: number | null,
): string {
  const annualAmount = Number(entry.amountAnnual ?? 0);
  if (!Number.isFinite(annualAmount)) return '0';
  if (period !== 'monthly') return String(annualAmount);
  return String(roundToMoney(annualAmount / 12));
}
