import { ref } from 'vue';
import { api } from '@/lib/api';
import { toApiErrorMessage } from '@/lib/errors';
import {
  expenseSubcategories,
  type ExpenseCategoryKey,
} from '@/domains/data-input/expenseTaxonomy';
import { parseAnnualAmount } from '@/domains/data-input/annualEntryUtils';

export type AnnualExpenseType = 'recurrent' | 'one_off';

export type AnnualExpenseEntry = {
  id: number;
  name: string;
  category: ExpenseCategoryKey;
  subcategory: string;
  owner: string;
  expenseType: AnnualExpenseType;
  amountAnnual: number;
  fiscalYear: number;
  currency: string;
  notes: string;
  createdAt: string;
};

export type AnnualExpenseDraft = {
  name: string;
  category: ExpenseCategoryKey;
  subcategory: string;
  expenseType: AnnualExpenseType;
  amountAnnual: string;
  fiscalYear: number;
  currency: string;
  notes: string;
};

type AddResult = { ok: true } | { ok: false; error: string };

type AnnualExpenseApiItem = {
  id: number;
  name: string;
  category: ExpenseCategoryKey;
  subcategory: string;
  owner_name: string;
  expense_type: AnnualExpenseType;
  amount_annual: string;
  fiscal_year: number;
  currency: string;
  notes: string;
  created_at: string;
};

type TotalsResponse = {
  total_annual: string;
  currency_hint: string;
};

function mapApiItem(item: AnnualExpenseApiItem): AnnualExpenseEntry {
  return {
    id: item.id,
    name: item.name,
    category: item.category,
    subcategory: item.subcategory,
    owner: item.owner_name || '',
    expenseType: item.expense_type,
    amountAnnual: Number(item.amount_annual),
    fiscalYear: Number(item.fiscal_year),
    currency: item.currency,
    notes: item.notes || '',
    createdAt: item.created_at,
  };
}

export function useAnnualExpenseStore(_scope: 'saas' | 'core' = 'core') {
  const entries = ref<AnnualExpenseEntry[]>([]);
  const totalAnnual = ref(0);
  const loading = ref(false);
  const error = ref<string | null>(null);

  async function loadAll(year?: number): Promise<void> {
    loading.value = true;
    error.value = null;
    try {
      const [listRes, totalsRes] = await Promise.all([
        api.get<AnnualExpenseApiItem[]>('/api/budget/annual-expense/', {
          params: year ? { year } : undefined,
        }),
        api.get<TotalsResponse>('/api/budget/annual-expense/totals/', {
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

  async function addEntry(draft: AnnualExpenseDraft, year?: number): Promise<AddResult> {
    const name = draft.name.trim();
    if (!name) return { ok: false, error: 'El nombre es obligatorio.' };

    const validSubcategory = expenseSubcategories.some(
      (row) => row.category === draft.category && row.value === draft.subcategory,
    );
    if (!validSubcategory) {
      return { ok: false, error: 'La subcategoria no corresponde con la categoria elegida.' };
    }

    const amount = parseAnnualAmount(draft.amountAnnual);
    if (amount <= 0) return { ok: false, error: 'El importe anual debe ser mayor que cero.' };

    loading.value = true;
    error.value = null;
    try {
      await api.post('/api/budget/annual-expense/', {
        name,
        category: draft.category,
        subcategory: draft.subcategory,
        expense_type: draft.expenseType,
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
    draft: AnnualExpenseDraft,
    year?: number,
  ): Promise<AddResult> {
    const name = draft.name.trim();
    if (!name) return { ok: false, error: 'El nombre es obligatorio.' };

    const validSubcategory = expenseSubcategories.some(
      (row) => row.category === draft.category && row.value === draft.subcategory,
    );
    if (!validSubcategory) {
      return { ok: false, error: 'La subcategoria no corresponde con la categoria elegida.' };
    }

    const amount = parseAnnualAmount(draft.amountAnnual);
    if (amount <= 0) return { ok: false, error: 'El importe anual debe ser mayor que cero.' };

    loading.value = true;
    error.value = null;
    try {
      await api.patch(`/api/budget/annual-expense/${id}/`, {
        name,
        category: draft.category,
        subcategory: draft.subcategory,
        expense_type: draft.expenseType,
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
      await api.delete(`/api/budget/annual-expense/${id}/`);
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
