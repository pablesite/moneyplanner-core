import { ref } from 'vue';
import { api } from '@/lib/api';
import { toApiErrorMessage } from '@/lib/errors';
import { incomeSubcategories, type IncomeCategoryKey } from '@/domains/data-input/incomeTaxonomy';
import { normalizeOwnerName, parseAnnualAmount } from '@/domains/data-input/annualEntryUtils';

export type AnnualIncomeType = 'recurrent' | 'one_off';
export type AnnualTimeProfile = 'structural_recurrent' | 'term_recurrent' | 'one_off';
export type AnnualIncomeCashflowRole =
  | 'operating'
  | 'transfer'
  | 'asset_sale'
  | 'tax_adjustment'
  | 'other';

export type AnnualIncomeEntry = {
  id: number;
  name: string;
  category: IncomeCategoryKey;
  subcategory: string;
  owner: string;
  incomeType: AnnualIncomeType;
  timeProfile: AnnualTimeProfile;
  cashflowRole: AnnualIncomeCashflowRole;
  eventGroup: string;
  targetMonth: number | null;
  termEndMonth: number | null;
  termEndYear: number | null;
  amountInputPeriod: 'annual' | 'monthly';
  amountAnnual: number;
  fiscalYear: number;
  currency: string;
  notes: string;
  isActive?: boolean;
  createdAt: string;
};

export type AnnualIncomeDraft = {
  name: string;
  category: IncomeCategoryKey;
  subcategory: string;
  owner?: string;
  incomeType: AnnualIncomeType;
  timeProfile?: AnnualTimeProfile;
  cashflowRole?: AnnualIncomeCashflowRole;
  eventGroup?: string;
  targetMonth?: number | null;
  termEndMonth?: number | null;
  termEndYear?: number | null;
  amountInputPeriod?: 'annual' | 'monthly';
  amountAnnual: string;
  fiscalYear: number;
  currency: string;
  notes: string;
};

type AddResult = { ok: true } | { ok: false; error: string };

type AnnualIncomeApiItem = {
  id: number;
  name: string;
  category: IncomeCategoryKey;
  subcategory: string;
  owner_name: string;
  income_type: AnnualIncomeType;
  time_profile?: AnnualTimeProfile;
  cashflow_role?: AnnualIncomeCashflowRole;
  event_group?: string;
  target_month?: number | null;
  term_end_month?: number | null;
  term_end_year?: number | null;
  amount_input_period?: 'annual' | 'monthly';
  amount_annual: string;
  fiscal_year: number;
  currency: string;
  notes: string;
  is_active?: boolean;
  created_at: string;
};

type TotalsResponse = {
  total_annual: string;
  currency_hint: string;
};

type StoreScope = 'saas' | 'core';

type AnnualIncomeStore = ReturnType<typeof createAnnualIncomeStore>;

function mapApiItem(item: AnnualIncomeApiItem): AnnualIncomeEntry {
  const timeProfile =
    item.time_profile ?? (item.income_type === 'one_off' ? 'one_off' : 'structural_recurrent');
  return {
    id: item.id,
    name: item.name,
    category: item.category,
    subcategory: item.subcategory,
    owner: item.owner_name || '',
    incomeType: item.income_type,
    timeProfile,
    cashflowRole: item.cashflow_role ?? 'operating',
    eventGroup: item.event_group ?? '',
    targetMonth: item.target_month == null ? null : Number(item.target_month),
    termEndMonth: item.term_end_month == null ? null : Number(item.term_end_month),
    termEndYear: item.term_end_year == null ? null : Number(item.term_end_year),
    amountInputPeriod: item.amount_input_period === 'monthly' ? 'monthly' : 'annual',
    amountAnnual: Number(item.amount_annual),
    fiscalYear: Number(item.fiscal_year),
    currency: item.currency,
    notes: item.notes || '',
    isActive: item.is_active !== false,
    createdAt: item.created_at,
  };
}

function createAnnualIncomeStore() {
  const entries = ref<AnnualIncomeEntry[]>([]);
  const totalAnnual = ref(0);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function loadAll(year?: number): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const [listRes, totalsRes] = await Promise.all([
        api.get<AnnualIncomeApiItem[]>('/api/budget/annual-income/', {
          params: year ? { year } : undefined,
        }),
        api.get<TotalsResponse>('/api/budget/annual-income/totals/', {
          params: year ? { year } : undefined,
        }),
      ]);
      entries.value = (listRes.data ?? []).map(mapApiItem);
      totalAnnual.value = Number(totalsRes.data?.total_annual ?? '0');
    } catch (e: unknown) {
      error.value = toApiErrorMessage(e);
    } finally {
      loading.value = false;
    }
  }

  async function addEntry(draft: AnnualIncomeDraft, year?: number): Promise<AddResult> {
    const name = draft.name.trim();
    if (!name) return { ok: false, error: 'El nombre es obligatorio.' };

    const validSubcategory = incomeSubcategories.some(
      (row) => row.category === draft.category && row.value === draft.subcategory,
    );
    if (!validSubcategory) {
      return { ok: false, error: 'La subcategoria no corresponde con la categoria elegida.' };
    }

    const amount = parseAnnualAmount(draft.amountAnnual);
    if (amount < 0) return { ok: false, error: 'El importe anual no puede ser negativo.' };

    loading.value = true;
    error.value = null;
    try {
      await api.post('/api/budget/annual-income/', {
        name,
        category: draft.category,
        subcategory: draft.subcategory,
        owner_name: normalizeOwnerName(draft.owner ?? ''),
        income_type: draft.incomeType,
        time_profile:
          draft.timeProfile ??
          (draft.incomeType === 'one_off' ? 'one_off' : 'structural_recurrent'),
        cashflow_role: draft.cashflowRole ?? 'operating',
        event_group: (draft.eventGroup ?? '').trim(),
        target_month: draft.targetMonth ?? null,
        term_end_month: draft.termEndMonth ?? null,
        term_end_year: draft.termEndYear ?? null,
        amount_input_period: draft.amountInputPeriod === 'monthly' ? 'monthly' : 'annual',
        amount_annual: amount.toFixed(2),
        fiscal_year: draft.fiscalYear,
        currency: (draft.currency || 'EUR').toUpperCase(),
        notes: draft.notes.trim(),
        is_active: true,
      });
      await loadAll(year ?? draft.fiscalYear);
      return { ok: true };
    } catch (e: unknown) {
      const message = toApiErrorMessage(e);
      error.value = message;
      return { ok: false, error: message };
    } finally {
      loading.value = false;
    }
  }

  async function updateEntry(
    id: number,
    draft: AnnualIncomeDraft,
    year?: number,
  ): Promise<AddResult> {
    const name = draft.name.trim();
    if (!name) return { ok: false, error: 'El nombre es obligatorio.' };

    const validSubcategory = incomeSubcategories.some(
      (row) => row.category === draft.category && row.value === draft.subcategory,
    );
    if (!validSubcategory) {
      return { ok: false, error: 'La subcategoria no corresponde con la categoria elegida.' };
    }

    const amount = parseAnnualAmount(draft.amountAnnual);
    if (amount < 0) return { ok: false, error: 'El importe anual no puede ser negativo.' };

    loading.value = true;
    error.value = null;
    try {
      await api.patch(`/api/budget/annual-income/${id}/`, {
        name,
        category: draft.category,
        subcategory: draft.subcategory,
        owner_name: normalizeOwnerName(draft.owner ?? ''),
        income_type: draft.incomeType,
        time_profile:
          draft.timeProfile ??
          (draft.incomeType === 'one_off' ? 'one_off' : 'structural_recurrent'),
        cashflow_role: draft.cashflowRole ?? 'operating',
        event_group: (draft.eventGroup ?? '').trim(),
        target_month: draft.targetMonth ?? null,
        term_end_month: draft.termEndMonth ?? null,
        term_end_year: draft.termEndYear ?? null,
        amount_input_period: draft.amountInputPeriod === 'monthly' ? 'monthly' : 'annual',
        amount_annual: amount.toFixed(2),
        fiscal_year: draft.fiscalYear,
        currency: (draft.currency || 'EUR').toUpperCase(),
        notes: draft.notes.trim(),
      });
      await loadAll(year ?? draft.fiscalYear);
      return { ok: true };
    } catch (e: unknown) {
      const message = toApiErrorMessage(e);
      error.value = message;
      return { ok: false, error: message };
    } finally {
      loading.value = false;
    }
  }

  async function deleteEntry(id: number, year?: number): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      await api.delete(`/api/budget/annual-income/${id}/`);
      await loadAll(year);
    } catch (e: unknown) {
      error.value = toApiErrorMessage(e);
    } finally {
      loading.value = false;
    }
  }

  return {
    entries,
    totalAnnual,
    loading,
    error,
    loadAll,
    addEntry,
    updateEntry,
    deleteEntry,
  };
}

const annualIncomeStoreCache = new Map<StoreScope, AnnualIncomeStore>();

export function useAnnualIncomeStore(scope: StoreScope = 'saas') {
  let store = annualIncomeStoreCache.get(scope);
  if (!store) {
    store = createAnnualIncomeStore();
    annualIncomeStoreCache.set(scope, store);
  }
  return store;
}
