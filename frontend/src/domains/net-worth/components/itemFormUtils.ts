import type {
  AssetImprovement,
  ContributionInterval,
  NetWorthWritePayload,
  Ownership,
} from '@/domains/net-worth/models';

// ── Types ─────────────────────────────────────────────────────────────────────

export type ItemFormPayload = NetWorthWritePayload & {
  ownership_id?: number | null;
  estimated_average_balance_for_interest?: string;
  deposit_term_months?: number;
};

export type ItemFormProps = {
  title: string;
  defaultCurrency?: string;
  categories: { value: string; label: string }[];
  subcategories?: { value: string; label: string; category: string }[];
  ownerships?: Ownership[];
  onSubmit: (payload: ItemFormPayload) => Promise<void>;
  onCancel?: () => void;
  assets?: { id: number; name: string; category: string }[];
  showFinancedAsset?: boolean;
  allowNegative?: boolean;
  mode?: 'create' | 'edit';
  submitError?: string | null;
  initial?: Partial<{
    name: string;
    category: string;
    subcategory?: string;
    amount: string;
    annual_interest_tae?: string | null;
    estimated_average_balance_for_interest?: string | null;
    deposit_term_months?: number | string | null;
    monthly_payment_amount?: string | null;
    start_date: string;
    payment_start_date?: string | null;
    expected_end_date?: string | null;
    contribution_intervals?: ContributionInterval[] | null;
    market_value_override?: string | null;
    market_value_override_date?: string | null;
    term_months?: number | string | null;
    rate_type?: string;
    payment_frequency?: string;
    expense_subcategory_override?: string | null;
    amortization_system?: string | null;
    opening_fees_amount?: string | null;
    early_repayment_fee_percent?: string | null;
    novation_subrogation_fee_amount?: string | null;
    linked_products_monthly_cost?: string | null;
    cancellation_forecast_enabled?: boolean;
    cancellation_date?: string | null;
    cancellation_include_payment_month?: boolean;
    cancellation_fee_amount?: string | null;
    amortization_method?: string;
    amortization_term_years?: number | string | null;
    valuation_model?: string;
    land_value_share_percent?: string | null;
    land_annual_appreciation_percent?: string | null;
    building_annual_depreciation_percent?: string | null;
    improvements?: AssetImprovement[] | null;
    notes: string;
    currency: string;
    tracking_mode: string;
    is_active: boolean;
    ownership_id: number | null;
    financed_asset_id: number | null;
  }>;
};

export type PrimaryHomeImprovementDraft = {
  id?: number;
  name: string;
  reform_date: string;
  amount: string;
  amortization_method: 'none' | 'straight_line' | 'manual';
  amortization_term_years: string;
  annual_interest_tae: string;
  capitalize_interest: boolean;
  manual_current_value: string;
  notes: string;
};

export type ContributionIntervalDraft = {
  _key: string;
  id?: number;
  start_date: string;
  end_date: string;
  amount: string;
  frequency: 'monthly' | 'weekly';
  currency: string;
};

type SimpleDate = { year: number; month: number; day: number };

// ── Constants ─────────────────────────────────────────────────────────────────

export const currencies = [
  { value: 'EUR', label: 'EUR' },
  { value: 'USD', label: 'USD' },
  { value: 'BTC', label: 'BTC' },
  { value: 'ETH', label: 'ETH' },
];

export const decimalsByCurrency: Record<string, number> = {
  EUR: 2,
  USD: 2,
  BTC: 8,
  ETH: 8,
};

export const ASSET_CASH_SUBCATEGORIES_REQUIRING_TAE = [
  'bank_account',
  'short_term_deposit',
  'crypto_spot_earn',
  'other',
];

export const DEPOSIT_TERM_MONTH_OPTIONS = Array.from({ length: 12 }, (_, index) => index + 1);

export const LIABILITY_PAYMENT_FREQUENCIES = [
  { value: 'monthly', label: 'Mensual' },
  { value: 'quarterly', label: 'Trimestral' },
];

export const LIABILITY_EXPENSE_SUBCATEGORY_OPTIONS = [
  { value: 'housing_home', label: 'Vivienda y hogar' },
  { value: 'living_expenses', label: 'Alimentacion' },
  { value: 'family_childcare', label: 'Familia y bebe' },
  { value: 'transport_mobility', label: 'Transporte y movilidad' },
  { value: 'health_wellbeing', label: 'Salud y bienestar' },
  { value: 'education_growth', label: 'Formacion y desarrollo' },
  { value: 'leisure_lifestyle', label: 'Ocio y estilo de vida' },
  { value: 'gifts_donations', label: 'Regalos y donaciones' },
  { value: 'financial_commitments', label: 'Compromisos financieros' },
  { value: 'other_consumption_expenses', label: 'Otros gastos de consumo' },
];

export const TRACKING_MODE_OPTIONS = [
  { value: 'manual', label: 'Manual' },
  { value: 'accounting', label: 'Contable (libro)' },
];

export const LIABILITY_CATEGORY_DEFAULTS: Record<
  string,
  { paymentFrequency?: 'monthly' | 'quarterly'; preferredAssetCategories?: string[] }
> = {
  mortgage: { paymentFrequency: 'monthly', preferredAssetCategories: ['real_estate'] },
  personal_loan: {
    paymentFrequency: 'monthly',
    preferredAssetCategories: ['furnishings', 'other'],
  },
  credit_card: { paymentFrequency: 'monthly', preferredAssetCategories: [] },
  other: { paymentFrequency: 'monthly', preferredAssetCategories: ['furnishings', 'other'] },
};

export const ASSET_AMORTIZATION_METHODS = [
  { value: 'none', label: 'Sin amortización' },
  { value: 'straight_line', label: 'Lineal' },
];

export const REAL_ESTATE_USAGE_OPTIONS = [
  { value: 'self_use', label: 'Propio' },
  { value: 'rental', label: 'Alquiler' },
] as const;

export const PRIMARY_HOME_VALUATION_MODE_OPTIONS = [
  { value: 'manual', label: 'Manual' },
  { value: 'real_estate_auto', label: 'Automática (suelo + construcción)' },
];

export const PRIMARY_HOME_VALUATION_PROFILES = [
  {
    value: 'conservative',
    label: 'Conservador',
    landAnnualAppreciationPercent: '5.5',
    buildingAnnualDepreciationPercent: '0.4',
  },
  {
    value: 'balanced',
    label: 'Equilibrado',
    landAnnualAppreciationPercent: '6.8',
    buildingAnnualDepreciationPercent: '0.3',
  },
  {
    value: 'dynamic',
    label: 'Dinámico',
    landAnnualAppreciationPercent: '8',
    buildingAnnualDepreciationPercent: '0.2',
  },
];

export const PRIMARY_HOME_CUSTOM_PROFILE_VALUE = 'custom';
export const PRIMARY_HOME_DEFAULT_PROFILE_VALUE = 'dynamic';

export const PRIMARY_HOME_IMPROVEMENT_AMORTIZATION_OPTIONS = [
  { value: 'none', label: 'Sin amortización' },
  { value: 'straight_line', label: 'Lineal' },
  { value: 'manual', label: 'Manual' },
] as const;

// ── Pure utility functions ─────────────────────────────────────────────────────

export function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

export function parseIsoDate(raw: string): SimpleDate | null {
  const value = String(raw ?? '').trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!year || month < 1 || month > 12 || day < 1 || day > 31) return null;
  return { year, month, day };
}

export function simpleDateToIso(value: SimpleDate): string {
  return `${value.year.toString().padStart(4, '0')}-${value.month
    .toString()
    .padStart(2, '0')}-${value.day.toString().padStart(2, '0')}`;
}

export function lastDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

export function addMonthsPreserveDayIso(startIso: string, months: number): string | null {
  const start = parseIsoDate(startIso);
  if (!start || !Number.isInteger(months) || months < 0) return null;
  const totalMonth = start.month - 1 + months;
  const year = start.year + Math.floor(totalMonth / 12);
  const month = (totalMonth % 12) + 1;
  const day = Math.min(start.day, lastDayOfMonth(year, month));
  return simpleDateToIso({ year, month, day });
}

export function monthsBetweenPreserveDayIso(startIso: string, endIso: string): number | null {
  const start = parseIsoDate(startIso);
  const end = parseIsoDate(endIso);
  if (!start || !end) return null;
  const rawMonths = (end.year - start.year) * 12 + (end.month - start.month);
  if (rawMonths < 0) return null;
  const rebuilt = addMonthsPreserveDayIso(startIso, rawMonths);
  return rebuilt === endIso ? rawMonths : null;
}

export const ownershipLabel = (o: Ownership): string => {
  if (o.kind === 'individual') {
    return o.member ? `Individual - ${o.member.name}` : 'Individual';
  }
  const parts = (o.splits || []).map((s) => `${s.member.name} ${s.percent}%`);
  return `Compartido - ${parts.join(' - ') || 'sin splits'}`;
};

export function buildEmptyPrimaryHomeImprovement(): PrimaryHomeImprovementDraft {
  return {
    name: '',
    reform_date: todayIsoDate(),
    amount: '',
    amortization_method: 'none',
    amortization_term_years: '10',
    annual_interest_tae: '',
    capitalize_interest: false,
    manual_current_value: '',
    notes: '',
  };
}

export function buildIntervalKey(): string {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return crypto.randomUUID();
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
}

export function normalizeMatchText(raw: unknown): string {
  return String(raw ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

export function scoreAssetNameMatch(liabilityName: string, assetName: string): number {
  const left = normalizeMatchText(liabilityName);
  const right = normalizeMatchText(assetName);
  if (!left || !right) return 0;
  if (left === right) return 100;
  if (left.includes(right) || right.includes(left)) return 70;
  const leftTokens = new Set(left.split(' ').filter(Boolean));
  const rightTokens = new Set(right.split(' ').filter(Boolean));
  if (!leftTokens.size || !rightTokens.size) return 0;
  let overlap = 0;
  leftTokens.forEach((token) => {
    if (rightTokens.has(token)) overlap += 1;
  });
  if (!overlap) return 0;
  return Math.round((overlap / Math.max(leftTokens.size, rightTokens.size)) * 50);
}

export function normalizeLooseNumber(raw: unknown, allowNegative?: boolean): string {
  let s = String(raw ?? '')
    .trim()
    .replace(/\s/g, '');
  if (allowNegative && s.startsWith('-')) {
    s = `-${s.slice(1).replace(/[^\d.,]/g, '')}`;
  } else {
    s = s.replace(/[^\d.,]/g, '');
  }
  return s;
}

export function sanitizeAmount(
  raw: unknown,
  decimals: number,
  allowNegative?: boolean,
): { value: string; error: string } {
  let s = normalizeLooseNumber(raw, allowNegative);

  if (!s) return { value: '', error: '' };

  const isNegative = allowNegative && s.startsWith('-');
  if (isNegative) s = s.slice(1);

  const lastComma = s.lastIndexOf(',');
  const lastDot = s.lastIndexOf('.');
  if (lastComma !== -1 && lastDot !== -1) {
    const decimalSep = lastComma > lastDot ? ',' : '.';
    const thousandSep = decimalSep === ',' ? '.' : ',';
    s = s.split(thousandSep).join('');
    s = s.replace(decimalSep, '.');
  } else {
    s = s.replace(/,/g, '.');
  }

  if ((s.match(/\./g) || []).length > 1) return { value: '', error: 'Importe inválido' };

  const [intPart, decPart = ''] = s.split('.');
  const limitedDec = decPart.slice(0, decimals);
  const normalized = decPart.length ? `${intPart}.${limitedDec}` : intPart;

  if (!normalized || normalized === '.') return { value: '', error: '' };

  const finalValue = normalized.startsWith('.') ? `0${normalized}` : normalized;
  const signedValue = isNegative ? `-${finalValue}` : finalValue;

  if (Number.isNaN(Number(signedValue))) return { value: '', error: 'Importe inválido' };

  if (!allowNegative && finalValue.includes('-')) {
    return { value: '', error: 'No se permiten importes negativos' };
  }

  return { value: signedValue, error: '' };
}

export function formatAmountForEdit(raw: unknown, currency: string): string {
  const max = decimalsByCurrency[currency] ?? 2;
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
  const n = Number(normalized);
  if (!Number.isFinite(n)) return '';
  return n.toFixed(max).replace(/\.?0+$/, '');
}

export function sanitizePercent(raw: unknown): { value: string; error: string } {
  const normalized = String(raw ?? '')
    .trim()
    .replace(',', '.');
  if (!normalized) return { value: '', error: '' };
  if (!/^-?\d+(\.\d+)?$/.test(normalized)) return { value: '', error: 'Porcentaje invalido' };
  const n = Number(normalized);
  if (!Number.isFinite(n)) return { value: '', error: 'Porcentaje invalido' };
  return { value: normalized, error: '' };
}

export function normalizePercentWithMaxDecimals(
  raw: unknown,
  maxDecimals: number,
  preserveTrailingSeparator = false,
  outputSeparator: 'dot' | 'comma' = 'dot',
): string {
  const rawString = String(raw ?? '').trim();
  const normalized = rawString.replace(',', '.').replace(/[^\d.-]/g, '');
  if (!normalized) return '';
  const dots = normalized.match(/\./g) || [];
  if (dots.length > 1) return normalized;
  if (preserveTrailingSeparator && /[.,]$/.test(rawString) && dots.length === 1) {
    const [intPart = ''] = normalized.split('.');
    return outputSeparator === 'comma' ? `${intPart},` : `${intPart}.`;
  }
  const [intPart = '', decPart = ''] = normalized.split('.');
  const limitedDec = decPart.slice(0, Math.max(0, maxDecimals));
  const out = limitedDec ? `${intPart}.${limitedDec}` : intPart;
  return outputSeparator === 'comma' ? out.replace('.', ',') : out;
}

export function currencySymbol(currency: string): string {
  const code = String(currency ?? '')
    .trim()
    .toUpperCase();
  if (code === 'EUR') return '€';
  if (code === 'USD') return '$';
  if (code === 'GBP') return '£';
  if (code === 'JPY') return '¥';
  return code || '';
}

export function formatImprovementSummaryDate(raw: string): string {
  const value = String(raw ?? '').trim();
  if (!value) return 'Sin fecha';
  const parsed = parseIsoDate(value);
  if (!parsed) return value;
  return `${String(parsed.day).padStart(2, '0')}/${String(parsed.month).padStart(2, '0')}/${parsed.year}`;
}

export function formatImprovementSummaryAmount(raw: string, currency: string): string {
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
  const parsed = Number(normalized);
  const amountText = Number.isFinite(parsed)
    ? new Intl.NumberFormat('es-ES', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 2,
      }).format(parsed)
    : raw || '0';
  const symbol = currencySymbol(currency);
  return symbol ? `${amountText} ${symbol}` : amountText;
}

export function canCapitalizeImprovementInterest(
  improvement: PrimaryHomeImprovementDraft,
): boolean {
  const interestRaw = String(improvement.annual_interest_tae ?? '')
    .trim()
    .replace(',', '.');
  if (!interestRaw) return false;
  const interest = Number(interestRaw);
  return Number.isFinite(interest) && interest > 0;
}

export function improvementRemoveLabel(improvement: PrimaryHomeImprovementDraft): string {
  return improvement.id ? 'Eliminar reforma' : 'Descartar reforma';
}
