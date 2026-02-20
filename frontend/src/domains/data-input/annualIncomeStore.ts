import { computed, ref, watch } from 'vue';
import { incomeSubcategories, type IncomeCategoryKey } from '@/domains/data-input/incomeTaxonomy';

export type AnnualIncomeType = 'recurrent' | 'one_off';

export type AnnualIncomeEntry = {
  id: string;
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

function makeId(): string {
  return `${Date.now()}-${Math.floor(Math.random() * 1_000_000)}`;
}

function isBrowser(): boolean {
  return typeof window !== 'undefined' && !!window.localStorage;
}

export function useAnnualIncomeStore(scope: 'saas' | 'core' = 'core') {
  const storageKey = `moneyplanner:${scope}:annual-income:v1`;
  const entries = ref<AnnualIncomeEntry[]>([]);

  if (isBrowser()) {
    try {
      const raw = window.localStorage.getItem(storageKey);
      if (raw) {
        const parsed = JSON.parse(raw) as AnnualIncomeEntry[];
        if (Array.isArray(parsed)) {
          entries.value = parsed;
        }
      }
    } catch {
      entries.value = [];
    }
  }

  watch(
    entries,
    (next) => {
      if (!isBrowser()) return;
      window.localStorage.setItem(storageKey, JSON.stringify(next));
    },
    { deep: true },
  );

  const totalAnnual = computed(() =>
    entries.value.reduce((acc, entry) => acc + Math.max(0, entry.amountAnnual), 0),
  );

  function addEntry(draft: AnnualIncomeDraft): AddResult {
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

    entries.value.unshift({
      id: makeId(),
      name,
      category: draft.category,
      subcategory: draft.subcategory,
      owner: draft.owner.trim(),
      incomeType: draft.incomeType,
      amountAnnual: amount,
      currency: draft.currency || 'EUR',
      notes: draft.notes.trim(),
      createdAt: new Date().toISOString(),
    });

    return { ok: true };
  }

  function deleteEntry(id: string): void {
    entries.value = entries.value.filter((entry) => entry.id !== id);
  }

  return {
    entries,
    totalAnnual,
    addEntry,
    deleteEntry,
  };
}
