<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import type {
  AssetImprovement,
  NetWorthWritePayload,
  Ownership,
} from '@/domains/net-worth/models';

type ItemFormPayload = NetWorthWritePayload & {
  ownership_id?: number | null;
  estimated_average_balance_for_interest?: string;
  deposit_term_months?: number;
};

type Props = {
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
    expected_end_date?: string | null;
    term_months?: number | string | null;
    rate_type?: string;
    payment_frequency?: string;
    amortization_system?: string | null;
    opening_fees_amount?: string | null;
    early_repayment_fee_percent?: string | null;
    novation_subrogation_fee_amount?: string | null;
    linked_products_monthly_cost?: string | null;
    initial_purchase_value?: string | null;
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

type PrimaryHomeImprovementDraft = {
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

const props = defineProps<Props>();

function todayIsoDate(): string {
  return new Date().toISOString().slice(0, 10);
}

type SimpleDate = { year: number; month: number; day: number };

function parseIsoDate(raw: string): SimpleDate | null {
  const value = String(raw ?? '').trim();
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  if (!match) return null;
  const year = Number(match[1]);
  const month = Number(match[2]);
  const day = Number(match[3]);
  if (!year || month < 1 || month > 12 || day < 1 || day > 31) return null;
  return { year, month, day };
}

function simpleDateToIso(value: SimpleDate): string {
  return `${value.year.toString().padStart(4, '0')}-${value.month
    .toString()
    .padStart(2, '0')}-${value.day.toString().padStart(2, '0')}`;
}

function lastDayOfMonth(year: number, month: number): number {
  return new Date(year, month, 0).getDate();
}

function addMonthsPreserveDayIso(startIso: string, months: number): string | null {
  const start = parseIsoDate(startIso);
  if (!start || !Number.isInteger(months) || months < 0) return null;
  const totalMonth = start.month - 1 + months;
  const year = start.year + Math.floor(totalMonth / 12);
  const month = (totalMonth % 12) + 1;
  const day = Math.min(start.day, lastDayOfMonth(year, month));
  return simpleDateToIso({ year, month, day });
}

function monthsBetweenPreserveDayIso(startIso: string, endIso: string): number | null {
  const start = parseIsoDate(startIso);
  const end = parseIsoDate(endIso);
  if (!start || !end) return null;
  const rawMonths = (end.year - start.year) * 12 + (end.month - start.month);
  if (rawMonths < 0) return null;
  const rebuilt = addMonthsPreserveDayIso(startIso, rawMonths);
  return rebuilt === endIso ? rawMonths : null;
}

const currencies = [
  { value: 'EUR', label: 'EUR' },
  { value: 'USD', label: 'USD' },
  { value: 'BTC', label: 'BTC' },
  { value: 'ETH', label: 'ETH' },
];

const ownershipLabel = (o: Ownership) => {
  if (o.kind === 'individual') {
    return o.member ? `Individual - ${o.member.name}` : 'Individual';
  }
  const parts = (o.splits || []).map((s) => `${s.member.name} ${s.percent}%`);
  return `Compartido - ${parts.join(' - ') || 'sin splits'}`;
};

const ownershipOptions = computed(() => {
  return [
    { value: null, label: 'Selecciona titularidad' },
    ...(props.ownerships || []).map((o) => ({ value: o.id, label: ownershipLabel(o) })),
  ];
});

/** -------------------------
 * Amount handling
 * - Accept thousands separators (1.234,56 or 1,234.56)
 * - Normalize to dot decimal for API
 * - Limit decimals by currency
 * ------------------------- */
const decimalsByCurrency: Record<string, number> = {
  EUR: 2,
  USD: 2,
  BTC: 8,
  ETH: 8,
};
const ASSET_CASH_SUBCATEGORIES_REQUIRING_TAE = [
  'bank_account',
  'short_term_deposit',
  'crypto_spot_earn',
  'other',
];
const DEPOSIT_TERM_MONTH_OPTIONS = Array.from({ length: 12 }, (_, index) => index + 1);
const LIABILITY_PAYMENT_FREQUENCIES = [
  { value: 'monthly', label: 'Mensual' },
  { value: 'quarterly', label: 'Trimestral' },
];
const LIABILITY_CATEGORY_DEFAULTS: Record<
  string,
  { paymentFrequency?: 'monthly' | 'quarterly'; preferredAssetCategories?: string[] }
> = {
  mortgage: { paymentFrequency: 'monthly', preferredAssetCategories: ['real_estate'] },
  personal_loan: { paymentFrequency: 'monthly', preferredAssetCategories: ['furnishings', 'other'] },
  credit_card: { paymentFrequency: 'monthly', preferredAssetCategories: [] },
  other: { paymentFrequency: 'monthly', preferredAssetCategories: ['furnishings', 'other'] },
};
const ASSET_AMORTIZATION_METHODS = [
  { value: 'none', label: 'Sin amortizacion' },
  { value: 'straight_line', label: 'Lineal' },
];
const PRIMARY_HOME_VALUATION_MODE_OPTIONS = [
  { value: 'manual', label: 'Manual' },
  { value: 'real_estate_auto', label: 'Automatica (suelo + construccion)' },
];
const PRIMARY_HOME_VALUATION_PROFILES = [
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
    label: 'Dinamico',
    landAnnualAppreciationPercent: '8',
    buildingAnnualDepreciationPercent: '0.2',
  },
];
const PRIMARY_HOME_CUSTOM_PROFILE_VALUE = 'custom';
const PRIMARY_HOME_IMPROVEMENT_AMORTIZATION_OPTIONS = [
  { value: 'none', label: 'Sin amortizacion' },
  { value: 'straight_line', label: 'Lineal' },
  { value: 'manual', label: 'Manual' },
] as const;

function buildEmptyPrimaryHomeImprovement(): PrimaryHomeImprovementDraft {
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

const form = reactive({
  name: '',
  category: '',
  subcategory: '',
  amount: '',
  annual_interest_tae: props.showFinancedAsset ? '0' : '',
  estimated_average_balance_for_interest: '',
  deposit_term_months: '',
  monthly_payment_amount: '',
  start_date: todayIsoDate(),
  expected_end_date: '',
  term_months: '',
  rate_type: 'fixed',
  payment_frequency: 'monthly',
  amortization_system: 'french',
  opening_fees_amount: '',
  early_repayment_fee_percent: '',
  novation_subrogation_fee_amount: '',
  linked_products_monthly_cost: '',
  initial_purchase_value: '',
  amortization_method: 'none',
  amortization_term_years: '',
  valuation_model: 'manual',
  land_value_share_percent: '30',
  land_annual_appreciation_percent: '3',
  building_annual_depreciation_percent: '1',
  notes: '',
  currency: '',
  tracking_mode: 'manual',
  is_active: true,
  ownership_id: null as number | null,
  financed_asset_id: null as number | null,
});

const isEdit = computed(() => props.mode === 'edit');

const financedAssetOptions = computed(() => {
  const list = Array.isArray(props.assets) ? props.assets : [];
  return [
    { value: null, label: 'No financia ningún activo' },
    ...list
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((a) => ({ value: a.id, label: a.name })),
  ];
});

const showFinancedAsset = computed(() => !!props.showFinancedAsset);
const isLiabilityForm = computed(() => showFinancedAsset.value);
const isAssetForm = computed(() => !showFinancedAsset.value);
const requiresAssetTae = computed(
  () =>
    !!props.subcategories &&
    form.category === 'cash' &&
    ASSET_CASH_SUBCATEGORIES_REQUIRING_TAE.includes(form.subcategory),
);
const showAnnualInterestInput = computed(
  () => isLiabilityForm.value || requiresAssetTae.value,
);
const showAssetAnnualInterestInput = computed(
  () => isAssetForm.value && showAnnualInterestInput.value,
);
const isShortTermDepositAsset = computed(
  () => isAssetForm.value && form.category === 'cash' && form.subcategory === 'short_term_deposit',
);
const showEstimatedAverageBalanceForInterestInput = computed(() => {
  if (!showAssetAnnualInterestInput.value) return false;
  if (isShortTermDepositAsset.value) return false;
  const taeRaw = String(form.annual_interest_tae ?? '').trim().replace(',', '.');
  const taeValue = Number(taeRaw);
  return Number.isFinite(taeValue) && taeValue > 0;
});
const showDepositTermMonthsInput = computed(() => isShortTermDepositAsset.value);
const showMonthlyPaymentInput = computed(() => false);
const isCreditCardLiability = computed(
  () => isLiabilityForm.value && String(form.category ?? '').trim() === 'credit_card',
);
const showLiabilityAdvancedFields = computed(
  () => isLiabilityForm.value && !isCreditCardLiability.value,
);
const showLiabilityTaeOnlyField = computed(
  () => isLiabilityForm.value && !showLiabilityAdvancedFields.value,
);
const showMortgageFeeFields = computed(
  () => isLiabilityForm.value && form.category === 'mortgage',
);
const showAssetAmortizationFields = computed(
  () => isAssetForm.value && String(form.category ?? '').trim() === 'furnishings',
);
const isJewelryFurnishings = computed(
  () => showAssetAmortizationFields.value && String(form.subcategory ?? '').trim() === 'jewelry',
);
const showPrimaryHomeValuationFields = computed(
  () =>
    isAssetForm.value &&
    String(form.category ?? '').trim() === 'real_estate' &&
    String(form.subcategory ?? '').trim() === 'primary_home',
);
const showPrimaryHomeAutoValuationFields = computed(
  () => showPrimaryHomeValuationFields.value && form.valuation_model === 'real_estate_auto',
);
const requiresAssetAmortizationInputs = computed(
  () =>
    showAssetAmortizationFields.value &&
    String(form.amortization_method ?? '').trim() === 'straight_line',
);
const useDegressiveResidualProfileForFurnishings = computed(() => {
  if (!showAssetAmortizationFields.value) return false;
  const subcategory = String(form.subcategory ?? '').trim();
  return subcategory === 'vehicles' || subcategory === 'sports_equipment';
});
const assetAmortizationMethodOptions = computed(() => {
  if (isJewelryFurnishings.value) {
    return [{ value: 'none', label: 'Sin amortizacion (joyeria)' }];
  }
  if (!useDegressiveResidualProfileForFurnishings.value) return ASSET_AMORTIZATION_METHODS;
  return ASSET_AMORTIZATION_METHODS.map((option) =>
    option.value === 'straight_line'
      ? { ...option, label: 'Lineal (decreciente + residual por subcategoria)' }
      : option,
  );
});
const assetAmortizationModelHint = computed(() => {
  if (isJewelryFurnishings.value) {
    return "En 'Joyeria' no se aplica amortizacion automatica.";
  }
  if (!useDegressiveResidualProfileForFurnishings.value) return '';
  const subcategory = String(form.subcategory ?? '').trim();
  if (subcategory === 'vehicles') {
    return "En 'Vehiculos', este metodo aplica curva decreciente con suelo residual del 15%.";
  }
  if (subcategory === 'sports_equipment') {
    return "En 'Equipamiento deportivo', este metodo aplica curva decreciente con suelo residual del 20%.";
  }
  return '';
});
const defaultDegressiveTermYearsForFurnishings = computed(() => {
  if (!useDegressiveResidualProfileForFurnishings.value) return null;
  const subcategory = String(form.subcategory ?? '').trim();
  if (subcategory === 'vehicles') return 20;
  if (subcategory === 'sports_equipment') return 15;
  return null;
});
const requiresAssetAmortizationTermInput = computed(
  () => requiresAssetAmortizationInputs.value && !useDegressiveResidualProfileForFurnishings.value,
);
const financedAssetSuggestion = computed(() => {
  if (!showFinancedAsset.value) return null;
  const assets = Array.isArray(props.assets) ? props.assets : [];
  if (!assets.length) return null;
  const defaults = LIABILITY_CATEGORY_DEFAULTS[String(form.category ?? '').trim()] ?? {};
  const preferredCategories = new Set(defaults.preferredAssetCategories ?? []);
  const hasPreferredFilter = preferredCategories.size > 0;

  const candidates = assets
    .map((asset) => {
      let score = scoreAssetNameMatch(form.name, asset.name);
      if (hasPreferredFilter && preferredCategories.has(asset.category)) score += 15;
      return { asset, score };
    })
    .sort((a, b) => b.score - a.score || a.asset.name.localeCompare(b.asset.name));

  if (!candidates.length) return null;
  const best = candidates[0];
  const second = candidates[1];
  if (!best) return null;
  if (best.score >= 70) return best.asset;
  if (best.score >= 20 && (!second || best.score - second.score >= 15)) return best.asset;
  if (!String(form.name ?? '').trim() && hasPreferredFilter) {
    const preferredOnly = assets.filter((asset) => preferredCategories.has(asset.category));
    if (preferredOnly.length === 1) return preferredOnly[0];
  }
  return null;
});
const financedAssetSuggestionHelp = computed(() => {
  if (!showFinancedAsset.value || !financedAssetAutoMatched.value) return null;
  const suggestion = financedAssetSuggestion.value;
  if (!suggestion || form.financed_asset_id !== suggestion.id) return null;
  return 'Activo financiado sugerido automáticamente (editable).';
});
const subcategoriesForCategory = computed(() => {
  if (!props.subcategories || !form.category) return [];
  return props.subcategories.filter((s) => s.category === form.category);
});

const maxDecimals = computed(() => decimalsByCurrency[form.currency] ?? 2);
const estimatedAverageBalanceCurrencyLabel = computed(() => {
  const currency = String(form.currency ?? '').trim();
  return currency || 'EUR';
});
const normalizedDefaultCurrency = computed(() =>
  String(props.defaultCurrency ?? '')
    .trim()
    .toUpperCase(),
);
const activeLiabilityFieldGroup = ref<'term' | 'end' | null>(null);
const financedAssetManuallySelected = ref(false);
const financedAssetAutoMatched = ref(false);
const primaryHomeValuationProfile = ref<string>(PRIMARY_HOME_CUSTOM_PROFILE_VALUE);
const primaryHomeImprovements = ref<PrimaryHomeImprovementDraft[]>([]);
const expandedPrimaryHomeImprovementIndex = ref<number | null>(null);
let syncingScheduleFields = false;
let syncingPrimaryHomeProfile = false;

watch(
  () => form.category,
  () => {
    if (!props.subcategories) return;
    const valid = subcategoriesForCategory.value.some((s) => s.value === form.subcategory);
    if (!valid) form.subcategory = '';
  },
);
watch(
  () => form.subcategory,
  () => {
    if (showAssetAmortizationFields.value) {
      const valid = new Set(assetAmortizationMethodOptions.value.map((opt) => opt.value));
      if (!valid.has(String(form.amortization_method ?? '').trim())) {
        form.amortization_method = 'none';
      }
    }
    if (!isJewelryFurnishings.value) return;
    form.amortization_method = 'none';
    form.amortization_term_years = '';
  },
);

function normalizeMatchText(raw: unknown): string {
  return String(raw ?? '')
    .toLowerCase()
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .replace(/[^\p{L}\p{N}\s]/gu, ' ')
    .replace(/\s+/g, ' ')
    .trim();
}

function scoreAssetNameMatch(liabilityName: string, assetName: string): number {
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

function normalizeLooseNumber(raw: unknown) {
  // Allow only digits and separators, remove spaces (including NBSP)
  let s = String(raw ?? '')
    .trim()
    .replace(/\s/g, '');
  if (props.allowNegative && s.startsWith('-')) {
    s = `-${s.slice(1).replace(/[^\d.,]/g, '')}`;
  } else {
    s = s.replace(/[^\d.,]/g, '');
  }
  return s;
}

function sanitizeAmount(raw: unknown, decimals: number) {
  let s = normalizeLooseNumber(raw);

  if (!s) return { value: '', error: '' };

  const isNegative = props.allowNegative && s.startsWith('-');
  if (isNegative) s = s.slice(1);

  // If contains both ',' and '.', assume last separator is decimal and the other is thousands
  const lastComma = s.lastIndexOf(',');
  const lastDot = s.lastIndexOf('.');
  if (lastComma !== -1 && lastDot !== -1) {
    const decimalSep = lastComma > lastDot ? ',' : '.';
    const thousandSep = decimalSep === ',' ? '.' : ',';
    s = s.split(thousandSep).join(''); // remove thousand separators
    s = s.replace(decimalSep, '.'); // normalize decimal to dot
  } else {
    // Only comma -> decimal comma
    s = s.replace(/,/g, '.');
  }

  // More than one dot => invalid
  if ((s.match(/\./g) || []).length > 1) return { value: '', error: 'Importe inválido' };

  // Limit decimals
  const [intPart, decPart = ''] = s.split('.');
  const limitedDec = decPart.slice(0, decimals);
  const normalized = decPart.length ? `${intPart}.${limitedDec}` : intPart;

  // Avoid weird states
  if (!normalized || normalized === '.') return { value: '', error: '' };

  // If starts with dot, prefix 0
  const finalValue = normalized.startsWith('.') ? `0${normalized}` : normalized;
  const signedValue = isNegative ? `-${finalValue}` : finalValue;

  // Validate numeric
  if (Number.isNaN(Number(signedValue))) return { value: '', error: 'Importe inválido' };

  // Block negatives (we removed '-' already, but keep for safety)
  if (!props.allowNegative && finalValue.includes('-')) {
    return { value: '', error: 'No se permiten importes negativos' };
  }

  return { value: signedValue, error: '' };
}

function formatAmountForEdit(raw: unknown, currency: string): string {
  const max = decimalsByCurrency[currency] ?? 2;
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
  const n = Number(normalized);
  if (!Number.isFinite(n)) return '';
  return n.toFixed(max).replace(/\.?0+$/, '');
}
function sanitizePercent(raw: unknown) {
  const normalized = String(raw ?? '').trim().replace(',', '.');
  if (!normalized) return { value: '', error: '' };
  if (!/^-?\d+(\.\d+)?$/.test(normalized)) return { value: '', error: 'Porcentaje invalido' };
  const n = Number(normalized);
  if (!Number.isFinite(n)) return { value: '', error: 'Porcentaje invalido' };
  return { value: normalized, error: '' };
}
function normalizePercentWithMaxDecimals(
  raw: unknown,
  maxDecimals: number,
  preserveTrailingSeparator = false,
  outputSeparator: 'dot' | 'comma' = 'dot',
): string {
  const rawString = String(raw ?? '').trim();
  const normalized = rawString
    .replace(',', '.')
    .replace(/[^\d.-]/g, '');
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
function applyPrimaryHomeValuationProfile(profileValue: string): void {
  const profile = PRIMARY_HOME_VALUATION_PROFILES.find((p) => p.value === profileValue);
  if (!profile) return;
  syncingPrimaryHomeProfile = true;
  form.land_annual_appreciation_percent = profile.landAnnualAppreciationPercent;
  form.building_annual_depreciation_percent = profile.buildingAnnualDepreciationPercent;
  syncingPrimaryHomeProfile = false;
}
function detectPrimaryHomeValuationProfile(): string {
  const toComparableNumber = (raw: unknown): number | null => {
    const normalized = String(raw ?? '').trim().replace(',', '.');
    if (!normalized) return null;
    const parsed = Number(normalized);
    return Number.isFinite(parsed) ? parsed : null;
  };
  const landGrowth = toComparableNumber(form.land_annual_appreciation_percent);
  const buildingDep = toComparableNumber(form.building_annual_depreciation_percent);
  if (landGrowth == null || buildingDep == null) return PRIMARY_HOME_CUSTOM_PROFILE_VALUE;
  const profile = PRIMARY_HOME_VALUATION_PROFILES.find(
    (p) =>
      Number(p.landAnnualAppreciationPercent) === landGrowth &&
      Number(p.buildingAnnualDepreciationPercent) === buildingDep,
  );
  return profile?.value ?? PRIMARY_HOME_CUSTOM_PROFILE_VALUE;
}

function addPrimaryHomeImprovement(): void {
  primaryHomeImprovements.value.push(buildEmptyPrimaryHomeImprovement());
  expandedPrimaryHomeImprovementIndex.value = primaryHomeImprovements.value.length - 1;
}

function removePrimaryHomeImprovement(index: number): void {
  if (index < 0 || index >= primaryHomeImprovements.value.length) return;
  primaryHomeImprovements.value.splice(index, 1);
  if (!primaryHomeImprovements.value.length) {
    expandedPrimaryHomeImprovementIndex.value = null;
    return;
  }
  if (expandedPrimaryHomeImprovementIndex.value == null) return;
  if (expandedPrimaryHomeImprovementIndex.value > index) {
    expandedPrimaryHomeImprovementIndex.value -= 1;
    return;
  }
  if (expandedPrimaryHomeImprovementIndex.value === index) {
    expandedPrimaryHomeImprovementIndex.value = Math.min(
      index,
      primaryHomeImprovements.value.length - 1,
    );
  }
}

function canCapitalizeImprovementInterest(improvement: PrimaryHomeImprovementDraft): boolean {
  const interestRaw = String(improvement.annual_interest_tae ?? '')
    .trim()
    .replace(',', '.');
  if (!interestRaw) return false;
  const interest = Number(interestRaw);
  return Number.isFinite(interest) && interest > 0;
}

function improvementRemoveLabel(improvement: PrimaryHomeImprovementDraft): string {
  return improvement.id ? 'Eliminar reforma' : 'Descartar reforma';
}

function formatImprovementSummaryDate(raw: string): string {
  const value = String(raw ?? '').trim();
  if (!value) return 'Sin fecha';
  const parsed = parseIsoDate(value);
  if (!parsed) return value;
  return `${String(parsed.day).padStart(2, '0')}/${String(parsed.month).padStart(2, '0')}/${parsed.year}`;
}

function currencySymbol(currency: string): string {
  const code = String(currency ?? '').trim().toUpperCase();
  if (code === 'EUR') return '€';
  if (code === 'USD') return '$';
  if (code === 'GBP') return '£';
  if (code === 'JPY') return '¥';
  return code || '';
}

function formatImprovementSummaryAmount(raw: string, currency: string): string {
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

function isImprovementExpanded(index: number): boolean {
  return expandedPrimaryHomeImprovementIndex.value === index;
}

function toggleImprovementExpanded(index: number): void {
  if (expandedPrimaryHomeImprovementIndex.value === index) {
    expandedPrimaryHomeImprovementIndex.value = null;
    return;
  }
  expandedPrimaryHomeImprovementIndex.value = index;
}

const primaryHomeImprovementsError = computed(() => {
  if (!showPrimaryHomeAutoValuationFields.value) return '';
  for (let i = 0; i < primaryHomeImprovements.value.length; i += 1) {
    const item = primaryHomeImprovements.value[i]!;
    const label = `Reforma ${i + 1}`;
    if (!String(item.name ?? '').trim()) return `${label}: el nombre es obligatorio`;
    if (!String(item.reform_date ?? '').trim()) return `${label}: la fecha es obligatoria`;

    const amountSanitized = sanitizeAmount(item.amount, maxDecimals.value);
    if (!amountSanitized.value || amountSanitized.error) return `${label}: importe invalido`;

    if (item.amortization_method === 'straight_line') {
      const years = Number(String(item.amortization_term_years ?? '').trim());
      if (!Number.isInteger(years) || years <= 0) return `${label}: plazo de amortizacion invalido`;
    }
    if (item.amortization_method === 'manual') {
      const manualSanitized = sanitizeAmount(item.manual_current_value, maxDecimals.value);
      if (!manualSanitized.value || manualSanitized.error) {
        return `${label}: valor actual manual invalido`;
      }
    }
    if (item.capitalize_interest) {
      const interestRaw = String(item.annual_interest_tae ?? '')
        .trim()
        .replace(',', '.');
      const interest = Number(interestRaw);
      if (!interestRaw || !Number.isFinite(interest) || interest < 0) {
        return `${label}: TAE invalida`;
      }
    }
  }
  return '';
});

const amountError = computed(() => {
  const { error } = sanitizeAmount(form.amount, maxDecimals.value);
  return error;
});
const annualInterestError = computed(() => {
  if (!showAnnualInterestInput.value) return '';
  const raw = String(form.annual_interest_tae ?? '')
    .trim()
    .replace(',', '.');
  if (!raw) return 'La TAE es obligatoria para este indicador';
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 0) return 'TAE invalida';
  return '';
});
const estimatedAverageBalanceForInterestError = computed(() => {
  if (!showEstimatedAverageBalanceForInterestInput.value) return '';
  const { value, error } = sanitizeAmount(form.estimated_average_balance_for_interest, 0);
  if (error) return error;
  if (!value) return 'Indica el importe anual medio previsto para estimar intereses.';
  const parsed = Number(value);
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return 'El importe anual medio previsto debe ser mayor que 0.';
  }
  return '';
});
const depositTermMonthsError = computed(() => {
  if (!showDepositTermMonthsInput.value) return '';
  const raw = String(form.deposit_term_months ?? '').trim();
  if (!raw) return 'Indica la duracion del deposito (1-12 meses).';
  const months = Number(raw);
  if (!Number.isInteger(months) || months < 1 || months > 12) {
    return 'La duracion del deposito debe estar entre 1 y 12 meses.';
  }
  return '';
});
const monthlyPaymentError = computed(() => {
  if (!showMonthlyPaymentInput.value) return '';
  const raw = String(form.monthly_payment_amount ?? '').trim();
  if (!raw) return '';
  const { error } = sanitizeAmount(raw, maxDecimals.value);
  return error;
});
const requiredFieldsError = computed(() => {
  if (!String(form.name ?? '').trim()) return 'Nombre obligatorio';
  if (!String(form.category ?? '').trim()) return 'Categoria obligatoria';
  if (props.subcategories && !String(form.subcategory ?? '').trim()) {
    return 'Subcategoria obligatoria';
  }
  if (!String(form.start_date ?? '').trim()) return 'Fecha inicio obligatoria';
  if (!String(form.amount ?? '').trim()) return 'Importe obligatorio';
  if (!String(form.currency ?? '').trim()) return 'Moneda obligatoria';
  return '';
});
const assetAmortizationError = computed(() => {
  if (!requiresAssetAmortizationInputs.value) return '';
  const amount = String(form.amount ?? '').trim();
  if (!amount) return 'Importe obligatorio para modelar amortizacion';
  if (requiresAssetAmortizationTermInput.value) {
    const term = String(form.amortization_term_years ?? '').trim();
    if (!term) return 'Plazo de amortizacion (anos) obligatorio';
    const years = Number(term);
    if (!Number.isInteger(years) || years <= 0) return 'Plazo de amortizacion invalido';
  }
  const normalizedPurchase = sanitizeAmount(amount, maxDecimals.value);
  if (!normalizedPurchase.value || normalizedPurchase.error) return 'Valor de compra invalido';
  return '';
});
const primaryHomeValuationError = computed(() => {
  if (!showPrimaryHomeAutoValuationFields.value) return '';
  const purchase = sanitizeAmount(form.amount, maxDecimals.value);
  if (!purchase.value || purchase.error) return 'Valor de compra invalido';

  const landShare = sanitizePercent(form.land_value_share_percent);
  const landGrowth = sanitizePercent(form.land_annual_appreciation_percent);
  const buildingDep = sanitizePercent(form.building_annual_depreciation_percent);
  if (landShare.error || landGrowth.error || buildingDep.error) return 'Parametros de vivienda invalidos';

  const landShareN = Number(landShare.value);
  const landGrowthN = Number(landGrowth.value);
  const buildingDepN = Number(buildingDep.value);
  if (landShare.value === '' || landShareN < 0 || landShareN > 100) {
    return 'El porcentaje de suelo debe estar entre 0 y 100';
  }
  if (landGrowth.value === '' || landGrowthN < -100 || landGrowthN > 200) {
    return 'La revalorizacion del suelo debe estar entre -100 y 200';
  }
  if (buildingDep.value === '' || buildingDepN < 0 || buildingDepN > 100) {
    return 'La depreciacion de construccion debe estar entre 0 y 100';
  }
  return '';
});
const liabilityDatesError = computed(() => {
  if (!showLiabilityAdvancedFields.value) return '';
  if (!form.expected_end_date || !form.start_date) return '';
  return form.expected_end_date < form.start_date ? 'Fecha fin debe ser >= fecha inicio' : '';
});
const liabilityScheduleError = computed(() => {
  if (!showLiabilityAdvancedFields.value) return '';
  const hasTerm = String(form.term_months ?? '').trim().length > 0;
  const hasEndDate = String(form.expected_end_date ?? '').trim().length > 0;
  const paymentFrequency = String(form.payment_frequency ?? '').trim();
  if (!hasTerm && !hasEndDate) return 'Indica cuotas o fecha fin (uno de los dos es obligatorio)';
  if (hasTerm) {
    const term = Number(String(form.term_months).trim());
    if (!Number.isInteger(term) || term <= 0) return 'Cuotas/plazo debe ser un entero > 0';
    if (paymentFrequency === 'quarterly' && term % 3 !== 0) {
      return 'En frecuencia trimestral, el plazo se indica en meses y debe ser multiplo de 3 (ej: 12, 24).';
    }
  }
  if (hasEndDate && form.start_date) {
    const inferredMonths = monthsBetweenPreserveDayIso(String(form.start_date), String(form.expected_end_date));
    if (inferredMonths == null && !liabilityDatesError.value) {
      return 'La fecha fin no encaja con la fecha inicio y una cuota mensual exacta';
    }
  }
  if (hasTerm && hasEndDate && form.start_date) {
    const expectedFromTerm = addMonthsPreserveDayIso(
      String(form.start_date),
      Number(String(form.term_months).trim()),
    );
    if (expectedFromTerm && expectedFromTerm !== String(form.expected_end_date)) {
      return 'Cuotas y fecha fin no coinciden';
    }
  }
  return '';
});
const estimatedMonthlyPaymentPreview = computed(() => {
  if (!showLiabilityAdvancedFields.value) return null;
  const paymentFrequency = String(form.payment_frequency ?? '').trim();
  if (paymentFrequency !== 'monthly' && paymentFrequency !== 'quarterly') return null;
  if (String(form.rate_type ?? '') !== 'fixed') return null;
  const amortSystem = String(form.amortization_system ?? '').trim();
  if (amortSystem && amortSystem !== 'french' && amortSystem !== 'manual') return null;

  const amountSanitized = sanitizeAmount(form.amount, maxDecimals.value);
  if (!amountSanitized.value || amountSanitized.error) return null;
  const principal = Number(String(amountSanitized.value).replace(',', '.'));
  const term = Number(String(form.term_months ?? '').trim());
  const tae = Number(String(form.annual_interest_tae ?? '').trim().replace(',', '.'));
  if (!Number.isFinite(principal) || principal <= 0) return null;
  if (!Number.isFinite(term) || term <= 0) return null;
  if (!Number.isFinite(tae) || tae < 0) return null;
  const periodMonths = paymentFrequency === 'quarterly' ? 3 : 1;
  const periodsPerYear = paymentFrequency === 'quarterly' ? 4 : 12;
  if (!Number.isInteger(term) || term % periodMonths !== 0) return null;
  const installments = term / periodMonths;

  if (tae === 0) return principal / installments;
  const periodicRate = tae / 100 / periodsPerYear;
  const denominator = 1 - Math.pow(1 + periodicRate, -installments);
  if (!Number.isFinite(denominator) || denominator === 0) return null;
  const payment = (principal * periodicRate) / denominator;
  return Number.isFinite(payment) ? payment : null;
});
const estimatedMonthlyPaymentPreviewText = computed(() => {
  const value = estimatedMonthlyPaymentPreview.value;
  if (value == null) return null;
  return new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: 2,
    maximumFractionDigits: maxDecimals.value,
  }).format(value);
});
const estimatedPaymentPreviewLabel = computed(() => {
  const paymentFrequency = String(form.payment_frequency ?? '').trim();
  if (paymentFrequency === 'quarterly') return 'Cuota trimestral estimada';
  return 'Cuota mensual estimada';
});
const liabilityTermFieldLabel = computed(() => {
  const paymentFrequency = String(form.payment_frequency ?? '').trim();
  if (paymentFrequency === 'quarterly') return 'Plazo total (meses)';
  return 'Cuotas (meses)';
});
const liabilityTermFieldPlaceholder = computed(() => {
  const paymentFrequency = String(form.payment_frequency ?? '').trim();
  if (paymentFrequency === 'quarterly') return 'Ej: 12 o 24 (multiplo de 3)';
  return 'Ej: 24';
});
const liabilityTermFieldHint = computed(() => {
  const paymentFrequency = String(form.payment_frequency ?? '').trim();
  if (paymentFrequency !== 'quarterly') return null;
  return 'Trimestral: introduce plazo total en meses (ej: 24 = 8 cuotas trimestrales).';
});

async function submit() {
  if (requiredFieldsError.value) return;
  if (annualInterestError.value) return;
  if (estimatedAverageBalanceForInterestError.value) return;
  if (depositTermMonthsError.value) return;
  if (monthlyPaymentError.value) return;
  if (assetAmortizationError.value) return;
  if (primaryHomeValuationError.value) return;
  if (primaryHomeImprovementsError.value) return;
  if (liabilityDatesError.value) return;
  if (liabilityScheduleError.value) return;

  const { value: normalizedAmount, error } = sanitizeAmount(form.amount, maxDecimals.value);
  if (!normalizedAmount || error) return;

  const payload: ItemFormPayload = {
    name: form.name,
    category: form.category,
    subcategory: form.subcategory || undefined,
    amount: normalizedAmount, // normalized dot-decimal string
    start_date: form.start_date,
    annual_interest_tae: showAnnualInterestInput.value
      ? String(form.annual_interest_tae).trim().replace(',', '.')
      : undefined,
    estimated_average_balance_for_interest:
      showEstimatedAverageBalanceForInterestInput.value &&
      String(form.estimated_average_balance_for_interest ?? '').trim()
        ? sanitizeAmount(form.estimated_average_balance_for_interest, 0).value
        : undefined,
    deposit_term_months:
      showDepositTermMonthsInput.value && String(form.deposit_term_months ?? '').trim()
        ? Number(String(form.deposit_term_months).trim())
        : undefined,
    monthly_payment_amount:
      showMonthlyPaymentInput.value && String(form.monthly_payment_amount ?? '').trim()
        ? sanitizeAmount(form.monthly_payment_amount, maxDecimals.value).value
        : undefined,
    expected_end_date:
      showLiabilityAdvancedFields.value && String(form.expected_end_date ?? '').trim()
        ? String(form.expected_end_date).trim()
        : undefined,
    term_months:
      showLiabilityAdvancedFields.value && String(form.term_months ?? '').trim()
        ? Number(String(form.term_months).trim())
        : undefined,
    rate_type: showLiabilityAdvancedFields.value ? 'fixed' : undefined,
    payment_frequency: showLiabilityAdvancedFields.value ? form.payment_frequency : undefined,
    amortization_system:
      showLiabilityAdvancedFields.value && String(form.amortization_system ?? '').trim()
        ? String(form.amortization_system).trim()
        : undefined,
    opening_fees_amount:
      showMortgageFeeFields.value && String(form.opening_fees_amount ?? '').trim()
        ? sanitizeAmount(form.opening_fees_amount, maxDecimals.value).value
        : undefined,
    early_repayment_fee_percent:
      showMortgageFeeFields.value && String(form.early_repayment_fee_percent ?? '').trim()
        ? String(form.early_repayment_fee_percent).trim().replace(',', '.')
        : undefined,
    novation_subrogation_fee_amount:
      showMortgageFeeFields.value && String(form.novation_subrogation_fee_amount ?? '').trim()
        ? sanitizeAmount(form.novation_subrogation_fee_amount, maxDecimals.value).value
        : undefined,
    linked_products_monthly_cost:
      showMortgageFeeFields.value && String(form.linked_products_monthly_cost ?? '').trim()
        ? sanitizeAmount(form.linked_products_monthly_cost, maxDecimals.value).value
        : undefined,
    amortization_method: showAssetAmortizationFields.value ? form.amortization_method : undefined,
    amortization_term_years:
      requiresAssetAmortizationTermInput.value && String(form.amortization_term_years ?? '').trim()
        ? Number(String(form.amortization_term_years).trim())
        : undefined,
    valuation_model: showPrimaryHomeValuationFields.value ? form.valuation_model : undefined,
    land_value_share_percent:
      showPrimaryHomeAutoValuationFields.value && String(form.land_value_share_percent ?? '').trim()
        ? normalizePercentWithMaxDecimals(form.land_value_share_percent, 1)
        : undefined,
    land_annual_appreciation_percent:
      showPrimaryHomeAutoValuationFields.value &&
      String(form.land_annual_appreciation_percent ?? '').trim()
        ? normalizePercentWithMaxDecimals(form.land_annual_appreciation_percent, 1)
        : undefined,
    building_annual_depreciation_percent:
      showPrimaryHomeAutoValuationFields.value &&
      String(form.building_annual_depreciation_percent ?? '').trim()
        ? String(form.building_annual_depreciation_percent).trim().replace(',', '.')
        : undefined,
    improvements: showPrimaryHomeAutoValuationFields.value
      ? primaryHomeImprovements.value.map((item) => ({
          id: item.id,
          name: String(item.name ?? '').trim(),
          reform_date: String(item.reform_date ?? '').trim(),
          amount: sanitizeAmount(item.amount, maxDecimals.value).value,
          amortization_method: item.amortization_method,
          amortization_term_years:
            item.amortization_method === 'straight_line' &&
            String(item.amortization_term_years ?? '').trim()
              ? Number(String(item.amortization_term_years).trim())
              : null,
          annual_interest_tae: String(item.annual_interest_tae ?? '').trim()
            ? String(item.annual_interest_tae).trim().replace(',', '.')
            : null,
          capitalize_interest: !!item.capitalize_interest,
          manual_current_value:
            item.amortization_method === 'manual' &&
            String(item.manual_current_value ?? '').trim()
              ? sanitizeAmount(item.manual_current_value, maxDecimals.value).value
              : null,
          notes: String(item.notes ?? '').trim(),
        }))
      : undefined,
    notes: form.notes,
    currency: form.currency,
    tracking_mode: form.tracking_mode,
    is_active: form.is_active,
    ownership_id: form.ownership_id,
  };

  if (showFinancedAsset.value) {
    payload.financed_asset_id = form.financed_asset_id;
  }

  await props.onSubmit(payload);

  form.name = '';
  form.category = '';
  form.subcategory = '';
  form.amount = '';
  form.annual_interest_tae = props.showFinancedAsset ? '0' : '';
  form.estimated_average_balance_for_interest = '';
  form.deposit_term_months = '';
  form.monthly_payment_amount = '';
  form.start_date = todayIsoDate();
  form.expected_end_date = '';
  form.term_months = '';
  form.rate_type = 'fixed';
  form.payment_frequency = 'monthly';
  form.amortization_system = 'french';
  form.opening_fees_amount = '';
  form.early_repayment_fee_percent = '';
  form.novation_subrogation_fee_amount = '';
  form.linked_products_monthly_cost = '';
  form.initial_purchase_value = '';
  form.amortization_method = 'none';
  form.amortization_term_years = '';
  form.valuation_model = 'manual';
  form.land_value_share_percent = '30';
  form.land_annual_appreciation_percent = '3';
  form.building_annual_depreciation_percent = '1';
  primaryHomeValuationProfile.value = PRIMARY_HOME_CUSTOM_PROFILE_VALUE;
  primaryHomeImprovements.value = [];
  expandedPrimaryHomeImprovementIndex.value = null;
  form.notes = '';
  form.currency = normalizedDefaultCurrency.value || '';
  form.ownership_id = null;
  form.financed_asset_id = null;
  financedAssetManuallySelected.value = false;
  financedAssetAutoMatched.value = false;
}

watch(
  () => props.initial,
  (initial) => {
    if (!initial) return;
    form.name = initial.name ?? '';
    form.category = initial.category ?? '';
    form.subcategory = initial.subcategory ?? '';
    form.amount = initial.amount ?? '';
    form.annual_interest_tae = initial.annual_interest_tae ?? (props.showFinancedAsset ? '0' : '');
    form.estimated_average_balance_for_interest = String(
      sanitizeAmount(initial.estimated_average_balance_for_interest ?? '', 0).value ?? '',
    );
    form.deposit_term_months =
      initial.deposit_term_months == null ? '' : String(initial.deposit_term_months);
    form.monthly_payment_amount = initial.monthly_payment_amount ?? '';
    form.start_date = initial.start_date ?? todayIsoDate();
    form.expected_end_date = initial.expected_end_date ?? '';
    form.term_months = initial.term_months == null ? '' : String(initial.term_months);
    form.rate_type = props.showFinancedAsset ? 'fixed' : (initial.rate_type ?? 'fixed');
    form.payment_frequency = initial.payment_frequency ?? 'monthly';
    form.amortization_system = initial.amortization_system ?? '';
    form.opening_fees_amount = initial.opening_fees_amount ?? '';
    form.early_repayment_fee_percent = initial.early_repayment_fee_percent ?? '';
    form.novation_subrogation_fee_amount = initial.novation_subrogation_fee_amount ?? '';
    form.linked_products_monthly_cost = initial.linked_products_monthly_cost ?? '';
    form.initial_purchase_value = initial.initial_purchase_value ?? '';
    form.amortization_method = initial.amortization_method ?? 'none';
    form.amortization_term_years =
      initial.amortization_term_years == null ? '' : String(initial.amortization_term_years);
    form.valuation_model = initial.valuation_model ?? 'manual';
    form.land_value_share_percent = normalizePercentWithMaxDecimals(
      initial.land_value_share_percent ?? '30',
      1,
      false,
      'comma',
    );
    form.land_annual_appreciation_percent = normalizePercentWithMaxDecimals(
      initial.land_annual_appreciation_percent ?? '3',
      1,
      false,
      'comma',
    );
    form.building_annual_depreciation_percent =
      initial.building_annual_depreciation_percent ?? '1';
    primaryHomeValuationProfile.value = detectPrimaryHomeValuationProfile();
    primaryHomeImprovements.value = Array.isArray(initial.improvements)
      ? initial.improvements.map((row) => ({
          id: row.id,
          name: row.name ?? '',
          reform_date: row.reform_date ?? todayIsoDate(),
          amount: formatAmountForEdit(row.amount ?? '', initial.currency ?? 'EUR'),
          amortization_method: row.amortization_method ?? 'none',
          amortization_term_years:
            row.amortization_term_years == null ? '' : String(row.amortization_term_years),
          annual_interest_tae: row.annual_interest_tae ?? '',
          capitalize_interest: !!row.capitalize_interest,
          manual_current_value: formatAmountForEdit(
            row.manual_current_value ?? '',
            initial.currency ?? 'EUR',
          ),
          notes: row.notes ?? '',
        }))
      : [];
    expandedPrimaryHomeImprovementIndex.value = primaryHomeImprovements.value.length
      ? primaryHomeImprovements.value.length - 1
      : null;
    form.notes = initial.notes ?? '';
    form.currency = initial.currency ?? '';
    form.tracking_mode = initial.tracking_mode ?? 'manual';
    form.is_active = initial.is_active ?? true;
    form.ownership_id = initial.ownership_id ?? null;
    form.financed_asset_id = initial.financed_asset_id ?? null;
    financedAssetManuallySelected.value = form.financed_asset_id != null;
    financedAssetAutoMatched.value = false;
  },
  { immediate: true, deep: true },
);

watch(
  () =>
    primaryHomeImprovements.value.map((item) => ({
      amortization_method: item.amortization_method,
      annual_interest_tae: item.annual_interest_tae,
    })),
  () => {
    for (const item of primaryHomeImprovements.value) {
      if (item.amortization_method === 'straight_line' && !String(item.amortization_term_years ?? '').trim()) {
        item.amortization_term_years = '10';
      }
      if (!canCapitalizeImprovementInterest(item) && item.capitalize_interest) {
        item.capitalize_interest = false;
      }
    }
  },
  { deep: true },
);

watch(
  [() => props.defaultCurrency, () => props.initial],
  () => {
    if (props.initial) return;
    if (!String(form.currency ?? '').trim() && normalizedDefaultCurrency.value) {
      form.currency = normalizedDefaultCurrency.value;
    }
  },
  { immediate: true },
);

watch(
  () => form.category,
  (category) => {
    if (!isLiabilityForm.value || isEdit.value) return;
    const defaults = LIABILITY_CATEGORY_DEFAULTS[String(category ?? '').trim()];
    if (defaults?.paymentFrequency) form.payment_frequency = defaults.paymentFrequency;
    form.rate_type = 'fixed';
    form.amortization_system = 'french';
    if (!String(form.annual_interest_tae ?? '').trim()) form.annual_interest_tae = '0';
    if (category !== 'mortgage') {
      form.opening_fees_amount = '';
      form.early_repayment_fee_percent = '';
      form.novation_subrogation_fee_amount = '';
      form.linked_products_monthly_cost = '';
    }
  },
);

watch(
  [() => form.category, () => form.subcategory],
  () => {
    if (!showDepositTermMonthsInput.value) {
      form.deposit_term_months = '';
    }
    if (!showPrimaryHomeValuationFields.value) {
      form.valuation_model = 'manual';
      form.land_value_share_percent = '30';
      form.land_annual_appreciation_percent = '3';
      form.building_annual_depreciation_percent = '1';
      primaryHomeValuationProfile.value = PRIMARY_HOME_CUSTOM_PROFILE_VALUE;
      primaryHomeImprovements.value = [];
      expandedPrimaryHomeImprovementIndex.value = null;
    }
  },
);
watch(
  () => form.valuation_model,
  (model) => {
    if (model !== 'real_estate_auto') {
      primaryHomeValuationProfile.value = PRIMARY_HOME_CUSTOM_PROFILE_VALUE;
      primaryHomeImprovements.value = [];
      expandedPrimaryHomeImprovementIndex.value = null;
      return;
    }
    if (primaryHomeValuationProfile.value !== PRIMARY_HOME_CUSTOM_PROFILE_VALUE) {
      applyPrimaryHomeValuationProfile(primaryHomeValuationProfile.value);
      return;
    }
    primaryHomeValuationProfile.value = detectPrimaryHomeValuationProfile();
  },
);
watch(
  () => primaryHomeValuationProfile.value,
  (profile) => {
    if (!showPrimaryHomeAutoValuationFields.value) return;
    if (profile === PRIMARY_HOME_CUSTOM_PROFILE_VALUE) return;
    applyPrimaryHomeValuationProfile(profile);
  },
);
watch(
  [
    () => form.land_value_share_percent,
    () => form.land_annual_appreciation_percent,
    () => form.building_annual_depreciation_percent,
  ],
  () => {
    if (syncingPrimaryHomeProfile || !showPrimaryHomeAutoValuationFields.value) return;
    primaryHomeValuationProfile.value = detectPrimaryHomeValuationProfile();
  },
);
watch(
  () => form.land_value_share_percent,
  (value) => {
    const normalized = normalizePercentWithMaxDecimals(value, 1, true, 'comma');
    if (String(value ?? '') !== normalized) form.land_value_share_percent = normalized;
  },
  { immediate: true },
);
watch(
  () => form.land_annual_appreciation_percent,
  (value) => {
    const normalized = normalizePercentWithMaxDecimals(value, 1, true, 'comma');
    if (String(value ?? '') !== normalized) form.land_annual_appreciation_percent = normalized;
  },
  { immediate: true },
);

watch(
  [() => form.category, () => form.name, () => props.assets],
  () => {
    if (!showFinancedAsset.value || isEdit.value || financedAssetManuallySelected.value) return;
    financedAssetAutoMatched.value = false;
    const suggestion = financedAssetSuggestion.value;
    if (!suggestion) {
      form.financed_asset_id = null;
      return;
    }
    if (form.financed_asset_id !== suggestion.id) form.financed_asset_id = suggestion.id;
    financedAssetAutoMatched.value = true;
  },
  { deep: true },
);

function syncExpectedEndDateFromTerm(): void {
  if (!showLiabilityAdvancedFields.value) return;
  const startDate = String(form.start_date ?? '').trim();
  const termRaw = String(form.term_months ?? '').trim();
  if (!startDate || !termRaw) return;
  const term = Number(termRaw);
  if (!Number.isInteger(term) || term <= 0) return;
  const computedEndDate = addMonthsPreserveDayIso(startDate, term);
  if (computedEndDate && form.expected_end_date !== computedEndDate) {
    form.expected_end_date = computedEndDate;
  }
}

function syncTermFromExpectedEndDate(): void {
  if (!showLiabilityAdvancedFields.value) return;
  const startDate = String(form.start_date ?? '').trim();
  const endDate = String(form.expected_end_date ?? '').trim();
  if (!startDate || !endDate) return;
  const inferredMonths = monthsBetweenPreserveDayIso(startDate, endDate);
  if (inferredMonths == null || inferredMonths <= 0) return;
  const nextTerm = String(inferredMonths);
  if (String(form.term_months ?? '') !== nextTerm) {
    form.term_months = nextTerm;
  }
}

function syncLinkedLiabilityScheduleField(source: 'term' | 'end'): void {
  if (syncingScheduleFields) return;
  syncingScheduleFields = true;
  try {
    if (source === 'term') syncExpectedEndDateFromTerm();
    else syncTermFromExpectedEndDate();
  } finally {
    syncingScheduleFields = false;
  }
}

function onLiabilityTermInput(): void {
  activeLiabilityFieldGroup.value = 'term';
  syncLinkedLiabilityScheduleField('term');
}

function onLiabilityEndDateInput(): void {
  activeLiabilityFieldGroup.value = 'end';
  syncLinkedLiabilityScheduleField('end');
}

function onFinancedAssetChange(): void {
  financedAssetManuallySelected.value = true;
  financedAssetAutoMatched.value = false;
}

watch(
  () => form.start_date,
  () => {
    if (!showLiabilityAdvancedFields.value || syncingScheduleFields) return;
    if (activeLiabilityFieldGroup.value === 'end') {
      syncLinkedLiabilityScheduleField('end');
      return;
    }
    if (String(form.term_months ?? '').trim()) {
      syncLinkedLiabilityScheduleField('term');
      return;
    }
    if (String(form.expected_end_date ?? '').trim()) {
      syncLinkedLiabilityScheduleField('end');
    }
  },
);
</script>

<template>
  <div>
    <div class="ui-item-form-grid">
      <label
        :class="[
          'ui-item-form-field',
          { 'ui-item-form-field-span-2': isLiabilityForm || !props.subcategories },
        ]"
      >
        <span class="ui-item-form-label">Categoría</span>
        <select v-model="form.category" :class="['select ui-data-field', { 'ui-select-placeholder': !form.category }]">
          <option value="" disabled>Selecciona categoría</option>
          <option v-for="c in categories" :key="c.value" :value="c.value">{{ c.label }}</option>
        </select>
      </label>

      <label v-if="props.subcategories" class="ui-item-form-field">
        <span class="ui-item-form-label">Subcategoría</span>
        <select v-model="form.subcategory" :class="['select ui-data-field', { 'ui-select-placeholder': !form.subcategory }]">
          <option value="" disabled>Selecciona subcategoría</option>
          <option v-for="s in subcategoriesForCategory" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>
      </label>

      <label :class="['ui-item-form-field', { 'ui-item-form-field-span-2': isLiabilityForm }]">
        <span class="ui-item-form-label">Nombre</span>
        <input v-model="form.name" placeholder="Nombre" class="input ui-data-field" />
      </label>

      <label class="ui-item-form-field">
        <span class="ui-item-form-label">{{ isLiabilityForm ? 'Fecha inicio préstamo' : 'Fecha inicio' }}</span>
        <input v-model="form.start_date" type="date" class="input ui-data-field" />
      </label>

      <label class="ui-item-form-field">
        <span class="ui-item-form-label">{{ isLiabilityForm ? 'Principal / saldo actual' : 'Importe' }}</span>
        <input v-model="form.amount" inputmode="decimal" placeholder="Importe" class="input ui-data-field" />
      </label>

      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Moneda</span>
        <select v-model="form.currency" :class="['select ui-data-field', { 'ui-select-placeholder': !form.currency }]">
          <option value="" disabled>Selecciona moneda</option>
          <option v-for="c in currencies" :key="c.value" :value="c.value">{{ c.label }}</option>
        </select>
      </label>
      <div v-if="showPrimaryHomeValuationFields" class="ui-item-form-section ui-item-form-field-span-2">
        <div class="ui-item-form-section-head">
          <div class="ui-item-form-section-title">Valoracion vivienda habitual</div>
        </div>
        <div class="ui-item-form-inline-grid">
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Modelo</span>
            <select v-model="form.valuation_model" class="select ui-data-field">
              <option v-for="opt in PRIMARY_HOME_VALUATION_MODE_OPTIONS" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>
          <label v-if="showPrimaryHomeAutoValuationFields" class="ui-item-form-field">
            <span class="ui-item-form-label">Perfil</span>
            <select v-model="primaryHomeValuationProfile" class="select ui-data-field">
              <option v-for="profile in PRIMARY_HOME_VALUATION_PROFILES" :key="profile.value" :value="profile.value">
                {{ profile.label }}
              </option>
              <option :value="PRIMARY_HOME_CUSTOM_PROFILE_VALUE">Personalizado</option>
            </select>
          </label>
        </div>
        <div v-if="showPrimaryHomeAutoValuationFields" class="ui-item-form-inline-grid ui-item-form-inline-grid-3 mt-2">
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Suelo sobre compra (%)</span>
            <input v-model="form.land_value_share_percent" inputmode="decimal" placeholder="Ej: 30" class="input ui-data-field" />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Revalorizacion suelo anual (%)</span>
            <input v-model="form.land_annual_appreciation_percent" inputmode="decimal" placeholder="Ej: 3" class="input ui-data-field" />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Depreciacion construccion anual (%)</span>
            <input v-model="form.building_annual_depreciation_percent" inputmode="decimal" placeholder="Ej: 1" class="input ui-data-field" />
          </label>
        </div>
        <div v-if="showPrimaryHomeAutoValuationFields" class="ui-form-help">
          El perfil autocompleta tasas y no modifica el porcentaje de suelo.
        </div>
        <div v-if="showPrimaryHomeAutoValuationFields" class="ui-item-form-subsection mt-2">
          <div class="ui-item-form-section-head">
            <div>
              <div class="ui-item-form-section-title">Reformas capitalizables</div>
              <div class="ui-item-form-section-subtitle">
                Cada reforma suma valor a la vivienda y puede amortizarse.
              </div>
            </div>
            <div class="ui-item-form-section-actions">
              <button type="button" class="btn ui-item-form-mini-btn" @click="addPrimaryHomeImprovement">
                Anadir reforma
              </button>
            </div>
          </div>
          <div v-if="!primaryHomeImprovements.length" class="ui-form-help">
            Sin reformas registradas.
          </div>
          <div
            v-for="(improvement, index) in primaryHomeImprovements"
            :key="improvement.id ?? `new-${index}`"
            class="ui-item-form-improvement-card"
          >
            <div class="ui-item-form-improvement-head">
              <div class="ui-item-form-improvement-meta">
                <div class="ui-item-form-section-title">{{ improvement.name || `Reforma ${index + 1}` }}</div>
                <span class="subtle">
                  {{ formatImprovementSummaryDate(improvement.reform_date) }} ·
                  {{ formatImprovementSummaryAmount(improvement.amount, form.currency) }}
                </span>
              </div>
              <div class="ui-item-form-improvement-actions">
                <button
                  type="button"
                  class="btn ui-item-form-mini-btn"
                  @click="removePrimaryHomeImprovement(index)"
                >
                  {{ improvementRemoveLabel(improvement) }}
                </button>
                <button
                  type="button"
                  class="icon-btn nw-cat-toggle"
                  :aria-label="isImprovementExpanded(index) ? 'Compactar reforma' : 'Expandir reforma'"
                  :title="isImprovementExpanded(index) ? 'Compactar reforma' : 'Expandir reforma'"
                  @click="toggleImprovementExpanded(index)"
                >
                  <span v-if="isImprovementExpanded(index)" class="icon" aria-hidden="true">&#9662;</span>
                  <span v-else class="icon" aria-hidden="true">&#9656;</span>
                </button>
              </div>
            </div>
            <div v-if="isImprovementExpanded(index)">
              <div class="ui-item-form-inline-grid mt-2">
                <label class="ui-item-form-field">
                  <span class="ui-item-form-label">Nombre reforma</span>
                  <input v-model="improvement.name" placeholder="Ej: Reforma cocina" class="input ui-data-field" />
                </label>
                <label class="ui-item-form-field">
                  <span class="ui-item-form-label">Fecha</span>
                  <input v-model="improvement.reform_date" type="date" class="input ui-data-field" />
                </label>
                <label class="ui-item-form-field">
                  <span class="ui-item-form-label">
                    Importe{{ currencySymbol(form.currency) ? ` (${currencySymbol(form.currency)})` : '' }}
                  </span>
                  <input v-model="improvement.amount" inputmode="decimal" placeholder="Ej: 12000" class="input ui-data-field" />
                </label>
                <label class="ui-item-form-field">
                  <span class="ui-item-form-label">Amortizacion</span>
                  <select v-model="improvement.amortization_method" class="select ui-data-field">
                    <option
                      v-for="opt in PRIMARY_HOME_IMPROVEMENT_AMORTIZATION_OPTIONS"
                      :key="opt.value"
                      :value="opt.value"
                    >
                      {{ opt.label }}
                    </option>
                  </select>
                </label>
                <label v-if="improvement.amortization_method === 'straight_line'" class="ui-item-form-field">
                  <span class="ui-item-form-label">Plazo amortizacion (anos)</span>
                  <input v-model="improvement.amortization_term_years" inputmode="numeric" placeholder="Ej: 10" class="input ui-data-field" />
                </label>
                <label v-if="improvement.amortization_method === 'manual'" class="ui-item-form-field">
                  <span class="ui-item-form-label">Valor actual manual</span>
                  <input v-model="improvement.manual_current_value" inputmode="decimal" placeholder="Ej: 8500" class="input ui-data-field" />
                </label>
                <label class="ui-item-form-field">
                  <span class="ui-item-form-label">TAE financiacion (%)</span>
                  <input v-model="improvement.annual_interest_tae" inputmode="decimal" placeholder="Opcional" class="input ui-data-field" />
                </label>
              </div>
              <label class="checkbox-row mt-1">
                <input
                  v-model="improvement.capitalize_interest"
                  type="checkbox"
                  :disabled="!canCapitalizeImprovementInterest(improvement)"
                />
                <span>Capitalizar TAE en valor de reforma</span>
              </label>
              <div v-if="!canCapitalizeImprovementInterest(improvement)" class="ui-form-help">
                Disponible solo cuando la TAE de financiacion es mayor que 0.
              </div>
              <label class="ui-item-form-field mt-1">
                <span class="ui-item-form-label">Notas</span>
                <textarea v-model="improvement.notes" rows="2" class="textarea" placeholder="Notas de la reforma"></textarea>
              </label>
            </div>
          </div>
        </div>
      </div>

      <label v-if="showAssetAnnualInterestInput" class="ui-item-form-field">
        <span class="ui-item-form-label">TAE anual (%)</span>
        <input v-model="form.annual_interest_tae" inputmode="decimal" placeholder="TAE anual (%)" class="input ui-data-field" />
      </label>
      <label v-if="showEstimatedAverageBalanceForInterestInput" class="ui-item-form-field">
        <span class="ui-item-form-label">
          Importe anual medio previsto ({{ estimatedAverageBalanceCurrencyLabel }})
        </span>
        <input
          v-model="form.estimated_average_balance_for_interest"
          inputmode="numeric"
          :placeholder="`Saldo medio anual previsto (${estimatedAverageBalanceCurrencyLabel})`"
          class="input ui-data-field"
        />
      </label>
      <label v-if="showDepositTermMonthsInput" class="ui-item-form-field">
        <span class="ui-item-form-label">Duración del depósito (meses)</span>
        <select
          v-model="form.deposit_term_months"
          :class="['select ui-data-field', { 'ui-select-placeholder': !String(form.deposit_term_months ?? '').trim() }]"
        >
          <option value="" disabled>Selecciona duración</option>
          <option
            v-for="month in DEPOSIT_TERM_MONTH_OPTIONS"
            :key="month"
            :value="String(month)"
          >
            {{ month }}
          </option>
        </select>
      </label>
      <label v-if="showLiabilityTaeOnlyField" class="ui-item-form-field">
        <span class="ui-item-form-label">TAE anual (%)</span>
        <input v-model="form.annual_interest_tae" inputmode="decimal" placeholder="TAE anual (%)" class="input ui-data-field" />
      </label>

      <div v-if="showLiabilityAdvancedFields" class="ui-item-form-section ui-item-form-field-span-2">
        <div class="ui-item-form-section-head">
          <div>
            <div class="ui-item-form-section-title">Calendario y condiciones</div>
            <div class="ui-item-form-section-subtitle">Indica <strong>cuotas</strong> o <strong>fecha fin</strong>. Se calcula la otra.</div>
          </div>
          <span class="badge">Requerido</span>
        </div>
        <div class="ui-item-form-inline-grid">
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Fecha fin</span>
            <input v-model="form.expected_end_date" type="date" class="input ui-data-field" @change="onLiabilityEndDateInput" />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">TAE anual (%)</span>
            <input v-model="form.annual_interest_tae" inputmode="decimal" placeholder="0" class="input ui-data-field" />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">{{ liabilityTermFieldLabel }}</span>
            <input v-model="form.term_months" inputmode="numeric" :placeholder="liabilityTermFieldPlaceholder" class="input ui-data-field" @input="onLiabilityTermInput" />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Frecuencia</span>
            <select v-model="form.payment_frequency" class="select ui-data-field">
              <option v-for="opt in LIABILITY_PAYMENT_FREQUENCIES" :key="opt.value" :value="opt.value">{{ opt.label }}</option>
            </select>
          </label>
        </div>
        <div v-if="liabilityTermFieldHint" class="ui-form-help">
          {{ liabilityTermFieldHint }}
        </div>
        <div v-if="estimatedMonthlyPaymentPreviewText" class="ui-item-form-chipline">
          <span class="ui-item-form-chip">{{ estimatedPaymentPreviewLabel }}</span>
          <span>
            {{ estimatedMonthlyPaymentPreviewText }} {{ form.currency || '' }}
            <small class="subtle">(simple, tipo fijo)</small>
            <small v-if="showMortgageFeeFields" class="subtle">(sin incluir costes opcionales)</small>
          </span>
        </div>
      </div>

      <details v-if="showMortgageFeeFields" class="ui-item-form-section ui-item-form-field-span-2">
        <summary class="ui-item-form-details-summary">Costes hipotecarios opcionales</summary>
        <div class="ui-item-form-inline-grid mt-2">
          <label class="ui-item-form-field"><span class="ui-item-form-label">Comisión apertura</span><input v-model="form.opening_fees_amount" inputmode="decimal" placeholder="Opcional" class="input ui-data-field" /></label>
          <label class="ui-item-form-field"><span class="ui-item-form-label">Amortización anticipada (%)</span><input v-model="form.early_repayment_fee_percent" inputmode="decimal" placeholder="Opcional" class="input ui-data-field" /></label>
          <label class="ui-item-form-field"><span class="ui-item-form-label">Novación / subrogación</span><input v-model="form.novation_subrogation_fee_amount" inputmode="decimal" placeholder="Opcional" class="input ui-data-field" /></label>
          <label class="ui-item-form-field"><span class="ui-item-form-label">Vinculados (mensual)</span><input v-model="form.linked_products_monthly_cost" inputmode="decimal" placeholder="Opcional" class="input ui-data-field" /></label>
        </div>
      </details>

      <div v-if="showAssetAmortizationFields" class="ui-item-form-section ui-item-form-field-span-2">
        <div class="ui-item-form-section-head"><div class="ui-item-form-section-title">Amortización del activo</div></div>
        <div class="ui-item-form-inline-grid">
          <label class="ui-item-form-field"><span class="ui-item-form-label">Método</span><select v-model="form.amortization_method" class="select ui-data-field"><option v-for="opt in assetAmortizationMethodOptions" :key="opt.value" :value="opt.value">{{ opt.label }}</option></select></label>
          <label v-if="requiresAssetAmortizationTermInput" class="ui-item-form-field"><span class="ui-item-form-label">Plazo (años)</span><input v-model="form.amortization_term_years" inputmode="numeric" placeholder="Ej: 10" class="input ui-data-field" /></label>
        </div>
        <div class="ui-form-help">Se usa el Importe como valor de compra inicial del activo.</div>
        <div v-if="assetAmortizationModelHint" class="ui-form-help">{{ assetAmortizationModelHint }}</div>
        <div v-if="defaultDegressiveTermYearsForFurnishings != null" class="ui-form-help">
          Plazo configurado automaticamente para esta subcategoria: {{ defaultDegressiveTermYearsForFurnishings }} años.
        </div>
      </div>

      <label class="ui-item-form-field ui-item-form-field-span-2">
        <span class="ui-item-form-label">Titularidad</span>
        <select v-model="form.ownership_id" :class="['select ui-data-field', { 'ui-select-placeholder': form.ownership_id == null }]">
          <option v-for="o in ownershipOptions" :key="String(o.value)" :value="o.value">{{ o.label }}</option>
        </select>
      </label>

      <label v-if="showFinancedAsset" class="ui-item-form-field ui-item-form-field-span-2">
        <span class="ui-item-form-label">Activo financiado</span>
        <select v-model="form.financed_asset_id" :class="['select ui-data-field', { 'ui-select-placeholder': form.financed_asset_id == null }]" @change="onFinancedAssetChange">
          <option v-for="a in financedAssetOptions" :key="String(a.value)" :value="a.value">{{ a.label }}</option>
        </select>
        <div v-if="financedAssetSuggestionHelp" class="ui-form-help">{{ financedAssetSuggestionHelp }}</div>
      </label>

      <label class="ui-item-form-field ui-item-form-field-span-2">
        <span class="ui-item-form-label">Notas</span>
        <textarea v-model="form.notes" placeholder="Notas" rows="2" class="textarea ui-data-field"></textarea>
      </label>

      <div class="ui-item-form-feedback ui-item-form-field-span-2">
        <div v-if="amountError" class="ui-form-help ui-form-help-error">{{ amountError }}</div>
        <div v-if="annualInterestError" class="ui-form-help ui-form-help-error">{{ annualInterestError }}</div>
        <div
          v-if="estimatedAverageBalanceForInterestError"
          class="ui-form-help ui-form-help-error"
        >
          {{ estimatedAverageBalanceForInterestError }}
        </div>
        <div v-if="depositTermMonthsError" class="ui-form-help ui-form-help-error">
          {{ depositTermMonthsError }}
        </div>
        <div v-if="requiredFieldsError" class="ui-form-help ui-form-help-error">{{ requiredFieldsError }}</div>
        <div v-if="monthlyPaymentError" class="ui-form-help ui-form-help-error">{{ monthlyPaymentError }}</div>
        <div v-if="assetAmortizationError" class="ui-form-help ui-form-help-error">{{ assetAmortizationError }}</div>
        <div v-if="primaryHomeValuationError" class="ui-form-help ui-form-help-error">{{ primaryHomeValuationError }}</div>
        <div v-if="primaryHomeImprovementsError" class="ui-form-help ui-form-help-error">{{ primaryHomeImprovementsError }}</div>
        <div v-if="liabilityDatesError" class="ui-form-help ui-form-help-error">{{ liabilityDatesError }}</div>
        <div v-if="liabilityScheduleError" class="ui-form-help ui-form-help-error">{{ liabilityScheduleError }}</div>
      </div>

      <div class="ui-item-form-footer ui-item-form-field-span-2">
        <div class="ui-form-actions ui-item-form-actions">
          <button v-if="onCancel" class="btn ui-form-action-btn" type="button" @click="onCancel">Cancelar</button>
          <button
            class="btn btn-primary ui-form-action-btn"
            :disabled="
              !!requiredFieldsError ||
              !!amountError ||
              !!annualInterestError ||
              !!estimatedAverageBalanceForInterestError ||
              !!depositTermMonthsError ||
              !!monthlyPaymentError ||
              !!assetAmortizationError ||
              !!primaryHomeValuationError ||
              !!primaryHomeImprovementsError ||
              !!liabilityDatesError ||
              !!liabilityScheduleError
            "
            @click="submit"
          >
            {{ isEdit ? 'Guardar' : 'Crear' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<style scoped>
.ui-item-form-subsection {
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 0.75rem;
}

.ui-item-form-improvement-card {
  border: 1px solid rgba(255, 255, 255, 0.1);
  border-radius: 12px;
  padding: 0.75rem;
  margin-top: 0.75rem;
}

.ui-item-form-improvement-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 0.75rem;
}

.ui-item-form-improvement-meta {
  display: flex;
  flex-direction: column;
  gap: 0.15rem;
}

.ui-item-form-improvement-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.ui-item-form-section-actions {
  display: flex;
  gap: 0.5rem;
  align-items: center;
}

.ui-item-form-mini-btn {
  padding: 0.35rem 0.75rem;
  font-size: 0.85rem;
}

@media (min-width: 768px) {
  .ui-item-form-inline-grid.ui-item-form-inline-grid-3 {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }
  .ui-item-form-inline-grid.ui-item-form-inline-grid-3 .ui-item-form-label {
    min-height: 2.4em;
    line-height: 1.2;
    display: block;
  }
}
</style>
