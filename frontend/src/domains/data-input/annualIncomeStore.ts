import { ref } from 'vue';
import { api } from '@/lib/api';
import { toApiErrorMessage } from '@/lib/errors';
import { incomeSubcategories, type IncomeCategoryKey } from '@/domains/data-input/incomeTaxonomy';

export type AnnualIncomeType = 'recurrent' | 'one_off';

export type AnnualIncomeEntry = {
  id: number;
  name: string;
  category: IncomeCategoryKey;
  subcategory: string;
  owner: string;
  incomeType: AnnualIncomeType;
  amountAnnual: number;
  currency: string;
  notes: string;
  createdAt: string;
};

export type AnnualIncomeDraft = {
  name: string;
  category: IncomeCategoryKey;
  subcategory: string;
  owner: string;
  incomeType: AnnualIncomeType;
  amountAnnual: string;
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
  amount_annual: string;
  currency: string;
  notes: string;
  created_at: string;
};

type TotalsResponse = {
  total_annual: string;
  currency_hint: string;
};

function parseAmount(raw: string): number {
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/\./g, '')
    .replace(',', '.');
  const value = Number(normalized);
  if (!Number.isFinite(value) || value <= 0) return 0;
  return value;
}

function mapApiItem(item: AnnualIncomeApiItem): AnnualIncomeEntry {
  return {
    id: item.id,
    name: item.name,
    category: item.category,
    subcategory: item.subcategory,
    owner: item.owner_name || '',
    incomeType: item.income_type,
    amountAnnual: Number(item.amount_annual),
    currency: item.currency,
    notes: item.notes || '',
    createdAt: item.created_at,
  };
}

export function useAnnualIncomeStore(_scope: 'saas' | 'core' = 'core') {
  const entries = ref<AnnualIncomeEntry[]>([]);
  const totalAnnual = ref(0);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function loadAll(): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const [listRes, totalsRes] = await Promise.all([
        api.get<AnnualIncomeApiItem[]>('/api/budget/annual-income/'),
        api.get<TotalsResponse>('/api/budget/annual-income/totals/'),
      ]);
      entries.value = (listRes.data ?? []).map(mapApiItem);
      totalAnnual.value = Number(totalsRes.data?.total_annual ?? '0');
    } catch (e: unknown) {
      error.value = toApiErrorMessage(e);
    } finally {
      loading.value = false;
    }
  }

  async function addEntry(draft: AnnualIncomeDraft): Promise<AddResult> {
    const name = draft.name.trim();
    if (!name) return { ok: false, error: 'El nombre es obligatorio.' };

    const validSubcategory = incomeSubcategories.some(
      (row) => row.category === draft.category && row.value === draft.subcategory,
    );
    if (!validSubcategory) {
      return { ok: false, error: 'La subcategoria no corresponde con la categoria elegida.' };
    }

    const amount = parseAmount(draft.amountAnnual);
    if (amount <= 0) return { ok: false, error: 'El importe anual debe ser mayor que cero.' };

    loading.value = true;
    error.value = null;
    try {
      await api.post('/api/budget/annual-income/', {
        name,
        category: draft.category,
        subcategory: draft.subcategory,
        owner_name: draft.owner.trim(),
        income_type: draft.incomeType,
        amount_annual: amount.toFixed(2),
        currency: (draft.currency || 'EUR').toUpperCase(),
        notes: draft.notes.trim(),
        is_active: true,
      });
      await loadAll();
      return { ok: true };
    } catch (e: unknown) {
      const message = toApiErrorMessage(e);
      error.value = message;
      return { ok: false, error: message };
    } finally {
      loading.value = false;
    }
  }

  async function deleteEntry(id: number): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      await api.delete(`/api/budget/annual-income/${id}/`);
      await loadAll();
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
    deleteEntry,
  };
}
