import { ref } from 'vue';
import { api } from '@/lib/api';
import { toApiErrorMessage } from '@/lib/errors';
import {
  expenseSubcategories,
  type ExpenseCategoryKey,
} from '@/domains/data-input/expenseTaxonomy';
import { normalizeOwnerName, parseAnnualAmount } from '@/domains/data-input/annualEntryUtils';

export type AnnualExpenseType = 'recurrent' | 'one_off';
export type AnnualTimeProfile = 'structural_recurrent' | 'term_recurrent' | 'one_off';
export type AnnualExpenseCashflowRole =
  | 'operating'
  | 'temporary_commitment'
  | 'savings'
  | 'investment'
  | 'asset_purchase'
  | 'tax_fee'
  | 'transfer'
  | 'other';

export type AnnualExpenseEntry = {
  id: number;
  sourceLiabilityId: number | null;
  sourceAssetId: number | null;
  isSystemGenerated: boolean;
  name: string;
  category: ExpenseCategoryKey;
  subcategory: string;
  owner: string;
  expenseType: AnnualExpenseType;
  timeProfile: AnnualTimeProfile;
  cashflowRole: AnnualExpenseCashflowRole;
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

export type AnnualExpenseDraft = {
  name: string;
  category: ExpenseCategoryKey;
  subcategory: string;
  owner?: string;
  expenseType: AnnualExpenseType;
  timeProfile?: AnnualTimeProfile;
  cashflowRole?: AnnualExpenseCashflowRole;
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

type AnnualExpenseApiItem = {
  id: number;
  source_liability_id?: number | null;
  source_asset_id?: number | null;
  is_system_generated?: boolean;
  name: string;
  category: ExpenseCategoryKey;
  subcategory: string;
  owner_name: string;
  expense_type: AnnualExpenseType;
  time_profile?: AnnualTimeProfile;
  cashflow_role?: AnnualExpenseCashflowRole;
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

type AnnualExpenseStore = ReturnType<typeof createAnnualExpenseStore>;

function mapApiItem(item: AnnualExpenseApiItem): AnnualExpenseEntry {
  const timeProfile =
    item.time_profile ?? (item.expense_type === 'one_off' ? 'one_off' : 'structural_recurrent');
  return {
    id: item.id,
    sourceLiabilityId: item.source_liability_id == null ? null : Number(item.source_liability_id),
    sourceAssetId: item.source_asset_id == null ? null : Number(item.source_asset_id),
    isSystemGenerated: Boolean(item.is_system_generated),
    name: item.name,
    category: item.category,
    subcategory: item.subcategory,
    owner: item.owner_name || '',
    expenseType: item.expense_type,
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

function createAnnualExpenseStore() {
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
    if (amount < 0) return { ok: false, error: 'El importe anual no puede ser negativo.' };

    loading.value = true;
    error.value = null;
    try {
      await api.post('/api/budget/annual-expense/', {
        name,
        category: draft.category,
        subcategory: draft.subcategory,
        owner_name: normalizeOwnerName(draft.owner ?? ''),
        expense_type: draft.expenseType,
        time_profile:
          draft.timeProfile ??
          (draft.expenseType === 'one_off' ? 'one_off' : 'structural_recurrent'),
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
    if (amount < 0) return { ok: false, error: 'El importe anual no puede ser negativo.' };

    loading.value = true;
    error.value = null;
    try {
      await api.patch(`/api/budget/annual-expense/${id}/`, {
        name,
        category: draft.category,
        subcategory: draft.subcategory,
        owner_name: normalizeOwnerName(draft.owner ?? ''),
        expense_type: draft.expenseType,
        time_profile:
          draft.timeProfile ??
          (draft.expenseType === 'one_off' ? 'one_off' : 'structural_recurrent'),
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
      await api.delete(`/api/budget/annual-expense/${id}/`);
      await loadAll(year);
    } catch (e: unknown) {
      error.value = toApiErrorMessage(e);
    } finally {
      loading.value = false;
    }
  }

  async function listBySourceLiability(sourceLiabilityId: number): Promise<AnnualExpenseEntry[]> {
    const response = await api.get<AnnualExpenseApiItem[]>('/api/budget/annual-expense/', {
      params: { source_liability_id: sourceLiabilityId },
    });
    return (response.data ?? []).map(mapApiItem);
  }

  async function listBySourceAsset(sourceAssetId: number): Promise<AnnualExpenseEntry[]> {
    const response = await api.get<AnnualExpenseApiItem[]>('/api/budget/annual-expense/', {
      params: { source_asset_id: sourceAssetId },
    });
    return (response.data ?? []).map(mapApiItem);
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
    listBySourceLiability,
    listBySourceAsset,
  };
}

const annualExpenseStoreCache = new Map<StoreScope, AnnualExpenseStore>();

export function useAnnualExpenseStore(scope: StoreScope = 'saas') {
  let store = annualExpenseStoreCache.get(scope);
  if (!store) {
    store = createAnnualExpenseStore();
    annualExpenseStoreCache.set(scope, store);
  }
  return store;
}
