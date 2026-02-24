<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import type { NetWorthWritePayload } from '@/domains/net-worth/models';

type Props = {
  title: string;
  defaultCurrency?: string;
  categories: { value: string; label: string }[];
  subcategories?: { value: string; label: string; category: string }[];
  onSubmit: (payload: NetWorthWritePayload) => Promise<void>;
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
    notes: string;
    currency: string;
    tracking_mode: string;
    is_active: boolean;
    financed_asset_id: number | null;
  }>;
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

const decimalsByCurrency: Record<string, number> = {
  EUR: 2,
  USD: 2,
  BTC: 8,
  ETH: 8,
};
const LIABILITY_CATEGORIES_REQUIRING_TAE = ['mortgage', 'personal_loan', 'credit_card'];
const LIABILITY_RATE_TYPES = [
  { value: 'fixed', label: 'Tipo fijo' },
  { value: 'variable', label: 'Tipo variable' },
  { value: 'mixed', label: 'Tipo mixto' },
];
const LIABILITY_PAYMENT_FREQUENCIES = [
  { value: 'monthly', label: 'Mensual' },
  { value: 'quarterly', label: 'Trimestral' },
  { value: 'yearly', label: 'Anual' },
];
const LIABILITY_AMORTIZATION_SYSTEMS = [
  { value: '', label: 'Sistema amortizacion (opcional)' },
  { value: 'french', label: 'Frances' },
  { value: 'german', label: 'Aleman' },
  { value: 'american', label: 'Americano' },
  { value: 'manual', label: 'Manual' },
];
const ASSET_AMORTIZATION_METHODS = [
  { value: 'none', label: 'Sin amortizacion' },
  { value: 'straight_line', label: 'Lineal' },
  { value: 'manual', label: 'Manual' },
];

const form = reactive({
  name: '',
  category: '',
  subcategory: '',
  amount: '',
  annual_interest_tae: '',
  monthly_payment_amount: '',
  start_date: todayIsoDate(),
  expected_end_date: '',
  term_months: '',
  rate_type: 'fixed',
  payment_frequency: 'monthly',
  amortization_system: '',
  opening_fees_amount: '',
  early_repayment_fee_percent: '',
  novation_subrogation_fee_amount: '',
  linked_products_monthly_cost: '',
  initial_purchase_value: '',
  amortization_method: 'none',
  amortization_term_years: '',
  notes: '',
  currency: '',
  tracking_mode: 'manual',
  is_active: true,
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
const showAnnualInterestInput = computed(
  () => showFinancedAsset.value && LIABILITY_CATEGORIES_REQUIRING_TAE.includes(form.category),
);
const showMonthlyPaymentInput = computed(() => false);
const showLiabilityAdvancedFields = computed(() => isLiabilityForm.value);
const showMortgageFeeFields = computed(
  () => isLiabilityForm.value && form.category === 'mortgage',
);
const showAssetAmortizationFields = computed(() => isAssetForm.value);
const requiresAssetAmortizationInputs = computed(
  () => showAssetAmortizationFields.value && form.amortization_method !== 'none',
);
const subcategoriesForCategory = computed(() => {
  if (!props.subcategories || !form.category) return [];
  return props.subcategories.filter((s) => s.category === form.category);
});

const maxDecimals = computed(() => decimalsByCurrency[form.currency] ?? 2);
const normalizedDefaultCurrency = computed(() =>
  String(props.defaultCurrency ?? '')
    .trim()
    .toUpperCase(),
);
const activeLiabilityFieldGroup = ref<'term' | 'end' | null>(null);
let syncingScheduleFields = false;

watch(
  () => form.category,
  () => {
    if (!props.subcategories) return;
    const valid = subcategoriesForCategory.value.some((s) => s.value === form.subcategory);
    if (!valid) form.subcategory = '';
  },
);

function normalizeLooseNumber(raw: unknown) {
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
  if (!props.allowNegative && finalValue.includes('-')) {
    return { value: '', error: 'No se permiten importes negativos' };
  }

  return { value: signedValue, error: '' };
}

const amountError = computed(() => {
  const { error } = sanitizeAmount(form.amount, maxDecimals.value);
  return error;
});
const annualInterestError = computed(() => {
  if (!showAnnualInterestInput.value) return '';
  const raw = String(form.annual_interest_tae ?? '')
    .trim()
    .replace(',', '.');
  if (!raw) return 'La TAE es obligatoria para este pasivo';
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 0) return 'TAE invalida';
  return '';
});
const monthlyPaymentError = computed(() => {
  if (!showMonthlyPaymentInput.value) return '';
  const raw = String(form.monthly_payment_amount ?? '').trim();
  if (!raw) return '';
  const { error } = sanitizeAmount(raw, maxDecimals.value);
  return error;
});
const assetAmortizationError = computed(() => {
  if (!requiresAssetAmortizationInputs.value) return '';
  const purchase = String(form.initial_purchase_value ?? '').trim();
  if (!purchase) return 'Valor de compra inicial obligatorio si hay amortizacion';
  const term = String(form.amortization_term_years ?? '').trim();
  if (!term) return 'Plazo de amortizacion (anos) obligatorio';
  const years = Number(term);
  if (!Number.isInteger(years) || years <= 0) return 'Plazo de amortizacion invalido';
  const normalizedPurchase = sanitizeAmount(purchase, maxDecimals.value);
  if (!normalizedPurchase.value || normalizedPurchase.error) return 'Valor de compra invalido';
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
  if (!hasTerm && !hasEndDate) {
    return 'Indica cuotas o fecha fin (uno de los dos es obligatorio)';
  }
  if (hasTerm) {
    const term = Number(String(form.term_months).trim());
    if (!Number.isInteger(term) || term <= 0) return 'Cuotas/plazo debe ser un entero > 0';
  }
  if (hasEndDate && form.start_date) {
    const inferredMonths = monthsBetweenPreserveDayIso(
      String(form.start_date),
      String(form.expected_end_date),
    );
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
  if (String(form.payment_frequency ?? '') !== 'monthly') return null;
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

  if (tae === 0) return principal / term;
  const monthlyRate = tae / 100 / 12;
  const denominator = 1 - Math.pow(1 + monthlyRate, -term);
  if (!Number.isFinite(denominator) || denominator === 0) return null;
  const payment = (principal * monthlyRate) / denominator;
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

async function submit() {
  if (!form.name || !form.category || !form.currency || !form.amount || !form.start_date) return;
  if (props.subcategories && !form.subcategory) return;
  if (annualInterestError.value) return;
  if (monthlyPaymentError.value) return;
  if (assetAmortizationError.value) return;
  if (liabilityDatesError.value) return;
  if (liabilityScheduleError.value) return;

  const { value: normalizedAmount, error } = sanitizeAmount(form.amount, maxDecimals.value);
  if (!normalizedAmount || error) return;

  const payload: NetWorthWritePayload = {
    name: form.name,
    category: form.category,
    subcategory: form.subcategory || undefined,
    amount: normalizedAmount,
    start_date: form.start_date,
    annual_interest_tae: showAnnualInterestInput.value
      ? String(form.annual_interest_tae).trim().replace(',', '.')
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
    rate_type: showLiabilityAdvancedFields.value ? form.rate_type : undefined,
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
    initial_purchase_value:
      showAssetAmortizationFields.value && String(form.initial_purchase_value ?? '').trim()
        ? sanitizeAmount(form.initial_purchase_value, maxDecimals.value).value
        : undefined,
    amortization_method: showAssetAmortizationFields.value ? form.amortization_method : undefined,
    amortization_term_years:
      requiresAssetAmortizationInputs.value && String(form.amortization_term_years ?? '').trim()
        ? Number(String(form.amortization_term_years).trim())
        : undefined,
    notes: form.notes,
    currency: form.currency,
    tracking_mode: form.tracking_mode,
    is_active: form.is_active,
  };

  if (showFinancedAsset.value) {
    payload.financed_asset_id = form.financed_asset_id;
  }

  await props.onSubmit(payload);

  form.name = '';
  form.category = '';
  form.subcategory = '';
  form.amount = '';
  form.annual_interest_tae = '';
  form.monthly_payment_amount = '';
  form.start_date = todayIsoDate();
  form.expected_end_date = '';
  form.term_months = '';
  form.rate_type = 'fixed';
  form.payment_frequency = 'monthly';
  form.amortization_system = '';
  form.opening_fees_amount = '';
  form.early_repayment_fee_percent = '';
  form.novation_subrogation_fee_amount = '';
  form.linked_products_monthly_cost = '';
  form.initial_purchase_value = '';
  form.amortization_method = 'none';
  form.amortization_term_years = '';
  form.notes = '';
  form.currency = normalizedDefaultCurrency.value || '';
  form.financed_asset_id = null;
}

watch(
  () => props.initial,
  (initial) => {
    if (!initial) return;
    form.name = initial.name ?? '';
    form.category = initial.category ?? '';
    form.subcategory = initial.subcategory ?? '';
    form.amount = initial.amount ?? '';
    form.annual_interest_tae = initial.annual_interest_tae ?? '';
    form.monthly_payment_amount = initial.monthly_payment_amount ?? '';
    form.start_date = initial.start_date ?? todayIsoDate();
    form.expected_end_date = initial.expected_end_date ?? '';
    form.term_months =
      initial.term_months == null ? '' : String(initial.term_months);
    form.rate_type = initial.rate_type ?? 'fixed';
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
    form.notes = initial.notes ?? '';
    form.currency = initial.currency ?? '';
    form.tracking_mode = initial.tracking_mode ?? 'manual';
    form.is_active = initial.is_active ?? true;
    form.financed_asset_id = initial.financed_asset_id ?? null;
  },
  { immediate: true, deep: true },
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
  <div class="card mb-3 ui-item-form-shell">
    <h3 class="h3 ui-item-form-title">{{ title }}</h3>

    <div class="ui-item-form-grid">
      <label class="ui-item-form-field ui-item-form-field-span-2">
        <span class="ui-item-form-label">Nombre</span>
        <input v-model="form.name" placeholder="Nombre" class="input" />
      </label>

      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Categoría</span>
        <select
          v-model="form.category"
          :class="['select', { 'ui-select-placeholder': !form.category }]"
        >
          <option value="" disabled>Selecciona categoría</option>
          <option v-for="c in categories" :key="c.value" :value="c.value">
            {{ c.label }}
          </option>
        </select>
      </label>

      <label v-if="props.subcategories" class="ui-item-form-field">
        <span class="ui-item-form-label">Subcategoría</span>
        <select
          v-model="form.subcategory"
          :class="['select', { 'ui-select-placeholder': !form.subcategory }]"
        >
          <option value="" disabled>Selecciona subcategoría</option>
          <option v-for="s in subcategoriesForCategory" :key="s.value" :value="s.value">
            {{ s.label }}
          </option>
        </select>
      </label>

      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Moneda</span>
        <select
          v-model="form.currency"
          :class="['select', { 'ui-select-placeholder': !form.currency }]"
        >
          <option value="" disabled>Selecciona moneda</option>
          <option v-for="c in currencies" :key="c.value" :value="c.value">
            {{ c.label }}
          </option>
        </select>
      </label>

      <label class="ui-item-form-field">
        <span class="ui-item-form-label">
          {{ isLiabilityForm ? 'Principal / saldo actual' : 'Importe' }}
        </span>
        <input v-model="form.amount" inputmode="decimal" placeholder="Importe" class="input" />
      </label>

      <label class="ui-item-form-field">
        <span class="ui-item-form-label">
          {{ isLiabilityForm ? 'Fecha inicio préstamo' : 'Fecha inicio' }}
        </span>
        <input v-model="form.start_date" type="date" class="input" />
      </label>

      <label v-if="showAnnualInterestInput" class="ui-item-form-field">
        <span class="ui-item-form-label">TAE anual (%)</span>
        <input
          v-model="form.annual_interest_tae"
          inputmode="decimal"
          placeholder="TAE anual (%)"
          class="input"
        />
      </label>

      <div v-if="showLiabilityAdvancedFields" class="ui-item-form-section ui-item-form-field-span-2">
        <div class="ui-item-form-section-head">
          <div>
            <div class="ui-item-form-section-title">Calendario de cuotas</div>
            <div class="ui-item-form-section-subtitle">
              Indica <strong>cuotas</strong> o <strong>fecha fin</strong>. Se calcula la otra.
            </div>
          </div>
          <span class="badge">Requerido</span>
        </div>

        <div class="ui-item-form-inline-grid">
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Fecha fin</span>
            <input
              v-model="form.expected_end_date"
              type="date"
              class="input"
              @change="onLiabilityEndDateInput"
            />
          </label>

          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Cuotas (meses)</span>
            <input
              v-model="form.term_months"
              inputmode="numeric"
              placeholder="Ej: 24"
              class="input"
              @input="onLiabilityTermInput"
            />
          </label>
        </div>

        <div
          v-if="showLiabilityAdvancedFields && estimatedMonthlyPaymentPreviewText"
          class="ui-item-form-chipline"
        >
          <span class="ui-item-form-chip">Cuota estimada</span>
          <span>
            {{ estimatedMonthlyPaymentPreviewText }} {{ form.currency || '' }}
            <small class="subtle">(simple, tipo fijo)</small>
          </span>
        </div>
      </div>

      <div v-if="showLiabilityAdvancedFields" class="ui-item-form-section ui-item-form-field-span-2">
        <div class="ui-item-form-section-head">
          <div class="ui-item-form-section-title">Condiciones</div>
        </div>
        <div class="ui-item-form-inline-grid">
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Tipo de interés</span>
            <select v-model="form.rate_type" class="select">
              <option v-for="opt in LIABILITY_RATE_TYPES" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </label>

          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Frecuencia</span>
            <select v-model="form.payment_frequency" class="select">
              <option v-for="opt in LIABILITY_PAYMENT_FREQUENCIES" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </label>

          <label class="ui-item-form-field ui-item-form-field-span-2">
            <span class="ui-item-form-label">Sistema de amortización</span>
            <select v-model="form.amortization_system" class="select">
              <option v-for="opt in LIABILITY_AMORTIZATION_SYSTEMS" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </label>
        </div>
      </div>

      <details v-if="showMortgageFeeFields" class="ui-item-form-section ui-item-form-field-span-2">
        <summary class="ui-item-form-details-summary">Costes hipotecarios opcionales</summary>
        <div class="ui-item-form-inline-grid mt-2">
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Comisión apertura</span>
            <input v-model="form.opening_fees_amount" inputmode="decimal" placeholder="Opcional" class="input" />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Amortización anticipada (%)</span>
            <input
              v-model="form.early_repayment_fee_percent"
              inputmode="decimal"
              placeholder="Opcional"
              class="input"
            />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Novación / subrogación</span>
            <input
              v-model="form.novation_subrogation_fee_amount"
              inputmode="decimal"
              placeholder="Opcional"
              class="input"
            />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Vinculados (mensual)</span>
            <input
              v-model="form.linked_products_monthly_cost"
              inputmode="decimal"
              placeholder="Opcional"
              class="input"
            />
          </label>
        </div>
      </details>

      <div v-if="showAssetAmortizationFields" class="ui-item-form-section ui-item-form-field-span-2">
        <div class="ui-item-form-section-head">
          <div class="ui-item-form-section-title">Amortización del activo</div>
        </div>
        <div class="ui-item-form-inline-grid">
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Método</span>
            <select v-model="form.amortization_method" class="select">
              <option v-for="opt in ASSET_AMORTIZATION_METHODS" :key="opt.value" :value="opt.value">
                {{ opt.label }}
              </option>
            </select>
          </label>

          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Valor compra inicial</span>
            <input
              v-model="form.initial_purchase_value"
              inputmode="decimal"
              placeholder="Opcional"
              class="input"
            />
          </label>

          <label v-if="requiresAssetAmortizationInputs" class="ui-item-form-field">
            <span class="ui-item-form-label">Plazo (años)</span>
            <input
              v-model="form.amortization_term_years"
              inputmode="numeric"
              placeholder="Ej: 10"
              class="input"
            />
          </label>
        </div>
      </div>

      <label v-if="showFinancedAsset" class="ui-item-form-field ui-item-form-field-span-2">
        <span class="ui-item-form-label">Activo financiado</span>
        <select
          v-model="form.financed_asset_id"
          :class="['select', { 'ui-select-placeholder': form.financed_asset_id == null }]"
        >
          <option v-for="a in financedAssetOptions" :key="String(a.value)" :value="a.value">
            {{ a.label }}
          </option>
        </select>
      </label>

      <label class="ui-item-form-field ui-item-form-field-span-2">
        <span class="ui-item-form-label">Notas</span>
        <textarea v-model="form.notes" placeholder="Notas" rows="2" class="textarea"></textarea>
      </label>

      <div class="ui-item-form-feedback ui-item-form-field-span-2">
        <div v-if="amountError" class="ui-form-help ui-form-help-error">{{ amountError }}</div>
        <div v-if="annualInterestError" class="ui-form-help ui-form-help-error">
          {{ annualInterestError }}
        </div>
        <div v-if="monthlyPaymentError" class="ui-form-help ui-form-help-error">
          {{ monthlyPaymentError }}
        </div>
        <div v-if="assetAmortizationError" class="ui-form-help ui-form-help-error">
          {{ assetAmortizationError }}
        </div>
        <div v-if="liabilityDatesError" class="ui-form-help ui-form-help-error">
          {{ liabilityDatesError }}
        </div>
        <div v-if="liabilityScheduleError" class="ui-form-help ui-form-help-error">
          {{ liabilityScheduleError }}
        </div>
      </div>

      <div class="ui-item-form-footer ui-item-form-field-span-2">
        <label class="checkbox-row">
          <input v-model="form.is_active" type="checkbox" />
          Activo
        </label>

        <div class="ui-form-actions ui-item-form-actions">
          <button v-if="onCancel" class="btn ui-form-action-btn" type="button" @click="onCancel">
            Cancelar
          </button>
          <button
            class="btn btn-primary ui-form-action-btn"
            :disabled="
              !!amountError ||
              !!annualInterestError ||
              !!monthlyPaymentError ||
              !!assetAmortizationError ||
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
