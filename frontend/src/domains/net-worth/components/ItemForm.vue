<script setup lang="ts">
import { computed, reactive, watch } from 'vue';
import type { NetWorthWritePayload } from '@/domains/net-worth/models';

type Props = {
  title: string;
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
    start_date: string;
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

const form = reactive({
  name: '',
  category: '',
  subcategory: '',
  amount: '',
  annual_interest_tae: '',
  start_date: todayIsoDate(),
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
const showAnnualInterestInput = computed(
  () => showFinancedAsset.value && LIABILITY_CATEGORIES_REQUIRING_TAE.includes(form.category),
);
const subcategoriesForCategory = computed(() => {
  if (!props.subcategories || !form.category) return [];
  return props.subcategories.filter((s) => s.category === form.category);
});

const maxDecimals = computed(() => decimalsByCurrency[form.currency] ?? 2);

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

async function submit() {
  if (!form.name || !form.category || !form.currency || !form.amount || !form.start_date) return;
  if (props.subcategories && !form.subcategory) return;
  if (annualInterestError.value) return;

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
  form.start_date = todayIsoDate();
  form.notes = '';
  form.currency = '';
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
    form.start_date = initial.start_date ?? todayIsoDate();
    form.notes = initial.notes ?? '';
    form.currency = initial.currency ?? '';
    form.tracking_mode = initial.tracking_mode ?? 'manual';
    form.is_active = initial.is_active ?? true;
    form.financed_asset_id = initial.financed_asset_id ?? null;
  },
  { immediate: true, deep: true },
);
</script>

<template>
  <div class="card mb-3">
    <h3 class="h3">{{ title }}</h3>

    <div class="form-grid">
      <input v-model="form.name" placeholder="Nombre" class="input" />

      <select
        v-model="form.category"
        :class="['select', { 'ui-select-placeholder': !form.category }]"
      >
        <option value="" disabled>Selecciona categoría</option>
        <option v-for="c in categories" :key="c.value" :value="c.value">
          {{ c.label }}
        </option>
      </select>

      <select
        v-if="props.subcategories"
        v-model="form.subcategory"
        :class="['select', { 'ui-select-placeholder': !form.subcategory }]"
      >
        <option value="" disabled>Selecciona subcategoría</option>
        <option v-for="s in subcategoriesForCategory" :key="s.value" :value="s.value">
          {{ s.label }}
        </option>
      </select>

      <select
        v-model="form.currency"
        :class="['select', { 'ui-select-placeholder': !form.currency }]"
      >
        <option value="" disabled>Selecciona moneda</option>
        <option v-for="c in currencies" :key="c.value" :value="c.value">
          {{ c.label }}
        </option>
      </select>

      <input v-model="form.amount" inputmode="decimal" placeholder="Importe" class="input" />

      <input v-model="form.start_date" type="date" class="input" />

      <div v-if="amountError" class="ui-form-help ui-form-help-error">
        {{ amountError }}
      </div>
      <div v-if="annualInterestError" class="ui-form-help ui-form-help-error">
        {{ annualInterestError }}
      </div>

      <input
        v-if="showAnnualInterestInput"
        v-model="form.annual_interest_tae"
        inputmode="decimal"
        placeholder="TAE anual (%)"
        class="input"
      />

      <select
        v-if="showFinancedAsset"
        v-model="form.financed_asset_id"
        :class="['select', { 'ui-select-placeholder': form.financed_asset_id == null }]"
      >
        <option v-for="a in financedAssetOptions" :key="String(a.value)" :value="a.value">
          {{ a.label }}
        </option>
      </select>

      <textarea v-model="form.notes" placeholder="Notas" rows="2" class="textarea"></textarea>

      <label class="checkbox-row">
        <input v-model="form.is_active" type="checkbox" />
        Activo
      </label>

      <div class="ui-form-actions">
        <button v-if="onCancel" class="btn ui-form-action-btn" type="button" @click="onCancel">
          Cancelar
        </button>
        <button
          class="btn btn-primary ui-form-action-btn"
          :disabled="!!amountError || !!annualInterestError"
          @click="submit"
        >
          {{ isEdit ? 'Guardar' : 'Crear' }}
        </button>
      </div>
    </div>
  </div>
</template>
