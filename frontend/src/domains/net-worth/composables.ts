import { computed, onMounted, ref, watch } from 'vue';
import { useNetWorthStore } from '@/stores/netWorth';
import type { Asset, Liability, NetWorthWritePayload, Summary } from '@/domains/net-worth/models';

type ByCategoryRow = { key: string; a: number; l: number };

type SummaryExtended = Summary & {
  liabilities_asset_backed?: string | null;
  liabilities_unbacked?: string | null;
  liabilities_asset_backed_real?: string | null;
  liabilities_unbacked_real?: string | null;
};

const currencies = [
  { value: 'EUR', label: 'EUR' },
  { value: 'USD', label: 'USD' },
  { value: 'BTC', label: 'BTC' },
  { value: 'ETH', label: 'ETH' },
];

const assetCategories = [
  { value: 'cash', label: 'Liquidez' },
  { value: 'investments', label: 'Inversiones' },
  { value: 'real_estate', label: 'Inmuebles' },
  { value: 'furnishings', label: 'Mobiliario' },
  { value: 'other', label: 'Otros' },
];

const assetSubcategories = [
  { category: 'cash', value: 'bank_account', label: 'Cuenta bancaria' },
  { category: 'cash', value: 'short_term_deposit', label: 'Deposito a corto plazo' },
  { category: 'cash', value: 'wallet', label: 'Monedero' },
  { category: 'cash', value: 'crypto_spot_earn', label: 'Spot/Earn Cripto' },
  { category: 'cash', value: 'other', label: 'Otros' },

  { category: 'investments', value: 'deposits', label: 'Depósitos' },
  { category: 'investments', value: 'funds', label: 'Fondos' },
  { category: 'investments', value: 'etfs', label: 'ETFs' },
  { category: 'investments', value: 'roboadvisor', label: 'Roboadvisor' },
  { category: 'investments', value: 'stocks', label: 'Stocks' },
  { category: 'investments', value: 'pension_plans', label: 'Planes de pensiones' },
  { category: 'investments', value: 'cryptocurrencies', label: 'Criptomonedas' },
  { category: 'investments', value: 'real_estate_crowd', label: 'Crowdfunding Inmobiliario' },
  { category: 'investments', value: 'crowdlending', label: 'Crowdlending' },
  { category: 'investments', value: 'other', label: 'Otros' },

  { category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' },
  { category: 'real_estate', value: 'second_home', label: 'Segunda vivienda' },
  { category: 'real_estate', value: 'rental', label: 'Rentas' },
  { category: 'real_estate', value: 'other', label: 'Otros' },

  { category: 'furnishings', value: 'vehicles', label: 'Vehículos' },
  { category: 'furnishings', value: 'technology', label: 'Tecnología' },
  { category: 'furnishings', value: 'home_furnishings', label: 'Muebles vivienda' },
  { category: 'furnishings', value: 'sports_equipment', label: 'Equipamiento deportivo' },
  { category: 'furnishings', value: 'jewelry', label: 'Joyería' },
  { category: 'furnishings', value: 'other', label: 'Otros' },

  { category: 'other', value: 'other', label: 'Otros' },
];

const liabilityCategories = [
  { value: 'mortgage', label: 'Hipoteca' },
  { value: 'personal_loan', label: 'Prestamo personal' },
  { value: 'credit_card', label: 'Tarjeta' },
  { value: 'other', label: 'Otros' },
];

const decimalsByCurrency: Record<string, number> = {
  EUR: 2,
  USD: 2,
  BTC: 8,
  ETH: 8,
};

function normalizeNumberInput(raw: unknown) {
  return String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
}

function formatEditAmount(raw: unknown, currency: string) {
  const max = decimalsByCurrency[currency] ?? 2;
  let s = normalizeNumberInput(raw);
  if (!s) return '';

  const isNegative = s.startsWith('-');
  if (isNegative) s = s.slice(1);

  if ((s.match(/\./g) || []).length > 1) {
    return isNegative ? `-${s}` : s;
  }

  const [i = '', d = ''] = s.split('.');
  let out = d ? `${i}.${d.slice(0, max)}` : i;
  out = out.replace(/\.?0+$/, '');
  if (out.startsWith('.')) out = `0${out}`;
  return isNegative ? `-${out}` : out;
}

function formatMoney(v?: string | null, decimals = 2) {
  if (v == null) return '-';
  const s = normalizeNumberInput(v);
  const n = Number(s);
  if (Number.isNaN(n)) return v;

  return new Intl.NumberFormat('es-ES', {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

export function useNetWorthViewState() {
  const store = useNetWorthStore();
  const valueMode = ref<'nominal' | 'real'>('nominal');

  const showAssetModal = ref(false);
  const showLiabilityModal = ref(false);
  const showBreakdown = ref(false);
  const showEditModal = ref(false);
  const editItem = ref<Asset | Liability | null>(null);
  const editKind = ref<'asset' | 'liability' | null>(null);

  const canShowReal = () =>
    store.baseCurrency === 'EUR' &&
    !!store.summary?.inflation_base_period &&
    store.summary?.net_worth_real !== null;

  watch(
    () => store.baseCurrency,
    (c) => {
      if (c !== 'EUR' && valueMode.value === 'real') valueMode.value = 'nominal';
    },
  );

  watch(
    () => store.summary?.inflation_base_period,
    () => {
      if (!canShowReal() && valueMode.value === 'real') valueMode.value = 'nominal';
    },
  );

  const prettyError = () => {
    if (!store.error) return null;
    try {
      const parsed = JSON.parse(store.error);
      if (parsed?.detail) return parsed.detail;
      return store.error;
    } catch {
      return store.error;
    }
  };

  async function submitAsset(payload: NetWorthWritePayload & { ownership_id?: number | null }) {
    await store.createAsset(payload);
    showAssetModal.value = false;
  }

  async function submitLiability(payload: NetWorthWritePayload & { ownership_id?: number | null }) {
    await store.createLiability(payload);
    showLiabilityModal.value = false;
  }

  function openEdit(item: Asset | Liability, kind: 'asset' | 'liability') {
    editItem.value = item;
    editKind.value = kind;
    showEditModal.value = true;
  }

  function closeEdit() {
    showEditModal.value = false;
    editItem.value = null;
    editKind.value = null;
  }

  function confirmDeleteSnapshot(id: number) {
    if (store.loading) return;
    if (confirm('Eliminar este snapshot?')) {
      store.deleteSnapshot(id);
    }
  }

  const editTitle = computed(() =>
    editKind.value === 'liability' ? 'Editar pasivo' : 'Editar activo',
  );

  const editCategories = computed(() =>
    editKind.value === 'liability' ? liabilityCategories : assetCategories,
  );

  const editInitial = computed(() => {
    const item = editItem.value;
    if (!item) return null;
    return {
      name: item.name ?? '',
      category: item.category ?? '',
      subcategory: item.subcategory ?? '',
      amount: formatEditAmount(item.amount, item.currency ?? 'EUR'),
      annual_interest_tae: item.annual_interest_tae ?? '',
      estimated_average_balance_for_interest:
        item.estimated_average_balance_for_interest ?? '',
      deposit_term_months: item.deposit_term_months ?? '',
      monthly_payment_amount: item.monthly_payment_amount ?? '',
      start_date: item.start_date ?? '',
      expected_end_date: item.expected_end_date ?? '',
      term_months: item.term_months ?? '',
      rate_type: item.rate_type ?? 'fixed',
      payment_frequency: item.payment_frequency ?? 'monthly',
      amortization_system: item.amortization_system ?? '',
      opening_fees_amount: item.opening_fees_amount ?? '',
      early_repayment_fee_percent: item.early_repayment_fee_percent ?? '',
      novation_subrogation_fee_amount: item.novation_subrogation_fee_amount ?? '',
      linked_products_monthly_cost: item.linked_products_monthly_cost ?? '',
      initial_purchase_value: item.initial_purchase_value ?? '',
      amortization_method: item.amortization_method ?? 'none',
      amortization_term_years: item.amortization_term_years ?? '',
      valuation_model: item.valuation_model ?? 'manual',
      land_value_share_percent: item.land_value_share_percent ?? '',
      land_annual_appreciation_percent: item.land_annual_appreciation_percent ?? '',
      building_annual_depreciation_percent: item.building_annual_depreciation_percent ?? '',
      notes: item.notes ?? '',
      currency: item.currency ?? '',
      tracking_mode: item.tracking_mode ?? 'manual',
      is_active: item.is_active ?? true,
      ownership_id: item.ownership_ref ?? null,
      financed_asset_id: item.financed_asset_ref ?? null,
    };
  });

  async function submitEdit(payload: NetWorthWritePayload & { ownership_id?: number | null }) {
    if (!editItem.value || !editKind.value) return;
    const id = editItem.value.id;

    if (editKind.value === 'asset') {
      delete payload.financed_asset_id;
      await store.updateAsset(id, payload);
    } else {
      await store.updateLiability(id, payload);
    }

    closeEdit();
  }

  const unitLabel = () => {
    const c = store.baseCurrency ?? '';
    if (valueMode.value !== 'real') return c;
    const base = store.summary?.inflation_base_period;
    return base ? `${c} (${base})` : `${c} (IPC)`;
  };

  const modeLabel = () => {
    if (valueMode.value === 'nominal') return 'Nominal (euros de hoy)';
    const base = store.summary?.inflation_base_period;
    return base ? `IPC: euros de ${base}` : 'IPC: euros del mes base';
  };

  const realBaseLabel = computed(() =>
    store.summary?.inflation_base_period ? `Base: ${store.summary.inflation_base_period}` : '',
  );

  const summaryAssets = computed(() =>
    valueMode.value === 'real' ? store.summary?.total_assets_real : store.summary?.total_assets,
  );
  const summaryLiabilities = computed(() =>
    valueMode.value === 'real'
      ? store.summary?.total_liabilities_real
      : store.summary?.total_liabilities,
  );
  const summaryNetWorth = computed(() =>
    valueMode.value === 'real' ? store.summary?.net_worth_real : store.summary?.net_worth,
  );

  const byCategoryChart = computed(() => store.byCategoryChart);

  const categoryLabelMap = computed(() => {
    const m = new Map<string, string>();
    assetCategories.forEach((c) => m.set(c.value, c.label));
    liabilityCategories.forEach((c) => m.set(c.value, c.label));
    return m;
  });

  const byCategoryFiltered = computed<ByCategoryRow[]>(() => {
    const keys = byCategoryChart.value.keys;
    const assets = byCategoryChart.value.assets;
    const liabs = byCategoryChart.value.liabilities;

    const out: ByCategoryRow[] = [];
    for (let i = 0; i < keys.length; i++) {
      const key = keys[i];
      if (!key) continue;
      if ((assets[i] ?? 0) !== 0 || (liabs[i] ?? 0) !== 0) {
        out.push({ key, a: assets[i] ?? 0, l: liabs[i] ?? 0 });
      }
    }
    return out;
  });

  const byCategoryLabels = computed(() =>
    byCategoryFiltered.value.map((r) => categoryLabelMap.value.get(r.key) ?? r.key),
  );
  const byCategoryAssets = computed(() => byCategoryFiltered.value.map((r) => r.a));
  const byCategoryLiabilities = computed(() => byCategoryFiltered.value.map((r) => r.l));
  const byCategoryUnit = computed(() => byCategoryChart.value.unit);

  const summaryExtended = computed<SummaryExtended | null>(
    () => store.summary as SummaryExtended | null,
  );

  const summaryAssetBackedLiabilities = computed(() =>
    valueMode.value === 'real'
      ? summaryExtended.value?.liabilities_asset_backed_real
      : summaryExtended.value?.liabilities_asset_backed,
  );

  const summaryUnbackedLiabilities = computed(() =>
    valueMode.value === 'real'
      ? summaryExtended.value?.liabilities_unbacked_real
      : summaryExtended.value?.liabilities_unbacked,
  );

  onMounted(async () => {
    await store.fetchSettings();
    await store.refreshAll();
  });

  return {
    store,
    valueMode,
    currencies,
    assetCategories,
    assetSubcategories,
    liabilityCategories,
    prettyError,
    showAssetModal,
    showLiabilityModal,
    showBreakdown,
    showEditModal,
    editKind,
    canShowReal,
    submitAsset,
    submitLiability,
    openEdit,
    closeEdit,
    confirmDeleteSnapshot,
    editTitle,
    editCategories,
    editInitial,
    submitEdit,
    formatMoney,
    unitLabel,
    modeLabel,
    realBaseLabel,
    summaryAssets,
    summaryLiabilities,
    summaryNetWorth,
    byCategoryLabels,
    byCategoryAssets,
    byCategoryLiabilities,
    byCategoryUnit,
    summaryAssetBackedLiabilities,
    summaryUnbackedLiabilities,
  };
}
