<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { formatAmount } from '@/lib/format';
import type { Asset, NetWorthWritePayload } from '@/domains/net-worth/models';
import EditableItemRow from './EditableItemRow.vue';
import ItemCategoryHeader from './ItemCategoryHeader.vue';
import ItemDisplayRow from './ItemDisplayRow.vue';
import ItemSubgroupHeader from './ItemSubgroupHeader.vue';

type AssetMini = {
  id: number;
  name: string;
  category: string;
};

type Item = Asset & {
  financed_asset_ref?: number | null;
};

type Props = {
  title: string;
  items: Item[];
  categories: { value: string; label: string }[];
  subcategories?: { value: string; label: string; category: string }[];
  baseCurrency?: string;
  categoryTotalsBase?: Record<string, string>;
  subcategoryTotalsBase?: Record<string, string>;
  totalBase?: string;
  onUpdate: (id: number, payload: NetWorthWritePayload) => Promise<void>;
  onArchive: (id: number) => Promise<void>;
  onAdd?: () => void;
  onEdit?: (item: Item) => void;
  assets?: AssetMini[];
};

const props = defineProps<Props>();

const currencies = [
  { value: 'EUR', label: 'EUR' },
  { value: 'USD', label: 'USD' },
  { value: 'BTC', label: 'BTC' },
  { value: 'ETH', label: 'ETH' },
];

const editingId = ref<number | null>(null);
const expandedCats = ref<Set<string>>(new Set());

const isLiabilitiesList = computed(() => props.title === 'Pasivos');

type EditDraft = {
  name?: string;
  category?: string;
  subcategory?: string;
  amount?: string;
  currency?: string;
  notes?: string;
  is_active?: boolean;
  financed_asset_id?: number | null;
};

const draft = ref<EditDraft>({});

const assetsById = computed(() => {
  const m = new Map<number, AssetMini>();
  (props.assets ?? []).forEach((a) => m.set(a.id, a));
  return m;
});

function financedAssetName(financedAssetRef?: number | null) {
  if (!financedAssetRef) return null;
  const a = assetsById.value.get(financedAssetRef);
  return a ? a.name : `#${financedAssetRef}`;
}

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

const decimalsByCurrency: Record<string, number> = {
  EUR: 2,
  USD: 2,
  BTC: 8,
  ETH: 8,
};

function getMaxDecimals(currency: unknown) {
  return decimalsByCurrency[String(currency ?? '')] ?? 2;
}

const amountHint = computed(() => {
  const max = getMaxDecimals(draft.value.currency);
  return `Hasta ${max} decimales`;
});

function normalizeAmountInput(raw: unknown) {
  return String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
}

function clampDecimals(amount: unknown, maxDecimals: number) {
  const s = normalizeAmountInput(amount);
  if (!s) return '';
  if ((s.match(/\./g) || []).length > 1) return s;

  const [i = '', d = ''] = s.split('.');
  return d ? `${i}.${d.slice(0, maxDecimals)}` : i;
}

function trimTrailingZeros(amount: string) {
  if (!amount.includes('.')) return amount;
  return amount.replace(/\.?0+$/, '');
}

const amountError = computed(() => {
  const max = getMaxDecimals(draft.value.currency);
  const clamped = clampDecimals(draft.value.amount, max);

  if (!draft.value.amount) return '';
  if ((normalizeAmountInput(draft.value.amount).match(/\./g) || []).length > 1)
    return 'Importe inválido';
  if (Number.isNaN(Number(normalizeAmountInput(clamped)))) return 'Importe inválido';
  return '';
});

const categoryLabel = (key: string) => {
  const found = props.categories.find((c) => c.value === key);
  return found?.label ?? key;
};

const subcategoryLabel = (key: string) => {
  const list = props.subcategories ?? [];
  const found = list.find((c) => c.value === key);
  return found?.label ?? key;
};

function categoryClass(category: string) {
  if (isLiabilitiesList.value) return `liab-cat-${category || 'other'}`;
  return `asset-cat-${category || 'other'}`;
}

const filteredItems = computed(() => (Array.isArray(props.items) ? props.items : []));

type Subgroup = {
  subcategory: string | null;
  label: string | null;
  items: Item[];
};

type Group = {
  category: string;
  label: string;
  items: Item[];
  subgroups: Subgroup[];
  hasSubgroups: boolean;
};

const grouped = computed<Group[]>(() => {
  const list = filteredItems.value;
  const map = new Map<string, Item[]>();

  for (const it of list) {
    const key = it.category ?? 'other';
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(it);
  }

  const orderedAssetCats = ['cash', 'investments', 'real_estate', 'furnishings', 'other'];
  const orderedLiabCats = ['credit_card', 'personal_loan', 'mortgage', 'other'];
  const assetOrder = new Map<string, number>(orderedAssetCats.map((k, i) => [k, i]));
  const liabOrder = new Map<string, number>(orderedLiabCats.map((k, i) => [k, i]));

  return Array.from(map.entries())
    .sort(([a], [b]) => {
      if (!isLiabilitiesList.value) {
        const ai = assetOrder.get(a) ?? Number.MAX_SAFE_INTEGER;
        const bi = assetOrder.get(b) ?? Number.MAX_SAFE_INTEGER;
        if (ai !== bi) return ai - bi;
      } else {
        const ai = liabOrder.get(a) ?? Number.MAX_SAFE_INTEGER;
        const bi = liabOrder.get(b) ?? Number.MAX_SAFE_INTEGER;
        if (ai !== bi) return ai - bi;
      }
      return categoryLabel(a).localeCompare(categoryLabel(b));
    })
    .map(([category, items]) => {
      const base: Group = {
        category,
        label: categoryLabel(category),
        items: items.sort((x, y) => x.name.localeCompare(y.name)),
        subgroups: [],
        hasSubgroups: false,
      };

      if (!props.subcategories) {
        base.subgroups = [{ subcategory: null, label: null, items: base.items }];
        return base;
      }

      const subMap = new Map<string, Item[]>();
      for (const it of items) {
        const subKey = it.subcategory || 'other';
        if (!subMap.has(subKey)) subMap.set(subKey, []);
        subMap.get(subKey)!.push(it);
      }

      base.subgroups = Array.from(subMap.entries())
        .sort(([a], [b]) => subcategoryLabel(a).localeCompare(subcategoryLabel(b)))
        .map(([subcategory, subitems]) => ({
          subcategory,
          label: subcategoryLabel(subcategory),
          items: subitems.sort((x, y) => x.name.localeCompare(y.name)),
        }));
      base.hasSubgroups = true;
      return base;
    });
});

function shouldShowGroupDetails(group: Group) {
  if (group.hasSubgroups) return expandedCats.value.has(group.category);
  return !isLiabilitiesList.value || expandedCats.value.has(group.category);
}

function subgroupKey(group: Group, subgroup: Subgroup, index: number) {
  if (group.hasSubgroups) return subgroup.subcategory ?? `sub-${index}`;
  return `${group.category}-all`;
}

const headerTotals = computed(() => categoryTotals(filteredItems.value));
const headerBaseValue = computed(() => totalBaseAll());

function headerBaseLabel() {
  if (!props.baseCurrency) return null;
  const v = headerBaseValue.value;
  if (v == null) return null;
  return `${formatAmount(String(v), { currency: props.baseCurrency })} ${props.baseCurrency}`;
}

function toNumberAmount(raw: string) {
  const s = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

function categoryTotals(items: Item[]) {
  const acc: Record<string, number> = {};
  for (const it of items) {
    const cur = it.currency || '???';
    acc[cur] = (acc[cur] ?? 0) + toNumberAmount(String(it.amount));
  }
  return acc;
}

function formatTotalsLine(totals: Record<string, number>) {
  const parts = Object.entries(totals)
    .filter(([, v]) => v !== 0)
    .map(([cur, v]) => `${formatAmount(String(v), { currency: cur })} ${cur}`);
  return parts.join(' | ');
}

function rawValue(v: string) {
  return String(v ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
}

function totalBaseForItems(items: Item[]) {
  let sum = 0;
  let hasAny = false;
  for (const it of items) {
    if (!it.amount_base) continue;
    const v = Number(rawValue(it.amount_base));
    if (!Number.isFinite(v)) continue;
    hasAny = true;
    sum += v;
  }
  return hasAny ? sum : null;
}

function totalBaseAll() {
  if (props.totalBase) {
    const total = Number(rawValue(props.totalBase));
    if (Number.isFinite(total)) return total;
  }
  return totalBaseForItems(filteredItems.value);
}

function categoryBaseValue(category: string, items: Item[]) {
  if (props.categoryTotalsBase) {
    const raw = props.categoryTotalsBase[category];
    if (raw) {
      const v = Number(rawValue(raw));
      if (Number.isFinite(v)) return v;
    }
  }
  return totalBaseForItems(items);
}

function subcategoryBaseValue(category: string, subcategory: string | null, items: Item[]) {
  const subKey = subcategory ?? 'other';
  if (props.subcategoryTotalsBase) {
    const raw = props.subcategoryTotalsBase[`${category}:${subKey}`];
    if (raw) {
      const v = Number(rawValue(raw));
      if (Number.isFinite(v)) return v;
    }
  }
  return totalBaseForItems(items);
}

function shouldShowBaseTotal(totals: Record<string, number>, baseValue: number | null) {
  if (!props.baseCurrency) return false;
  if (baseValue == null) return false;
  const nonZero = Object.entries(totals)
    .filter(([, v]) => v !== 0)
    .map(([cur]) => cur);
  if (nonZero.length === 0) return false;
  return !(nonZero.length === 1 && nonZero[0] === props.baseCurrency);
}

function baseTotalLabel(category: string, items: Item[]) {
  if (!props.baseCurrency) return null;
  const v = categoryBaseValue(category, items);
  if (v == null) return null;
  return `${formatAmount(String(v), { currency: props.baseCurrency })} ${props.baseCurrency}`;
}

function subcategoryBaseLabel(category: string, subcategory: string | null, items: Item[]) {
  if (!props.baseCurrency) return null;
  const v = subcategoryBaseValue(category, subcategory, items);
  if (v == null) return null;
  return `${formatAmount(String(v), { currency: props.baseCurrency })} ${props.baseCurrency}`;
}

function subcategoryPercent(
  category: string,
  subcategory: string | null,
  items: Item[],
  categoryItems: Item[],
) {
  const sub = subcategoryBaseValue(category, subcategory, items);
  if (sub == null) return null;
  const cat = categoryBaseValue(category, categoryItems);
  if (cat == null || cat === 0) return null;
  const pct = (sub / cat) * 100;
  return new Intl.NumberFormat('es-ES', {
    maximumFractionDigits: 1,
    minimumFractionDigits: 0,
  }).format(pct);
}

function categoryPercent(category: string, items: Item[]) {
  const v = categoryBaseValue(category, items);
  if (v == null) return null;
  const total = totalBaseAll();
  if (total == null || total === 0) return null;
  const pct = (v / total) * 100;
  return new Intl.NumberFormat('es-ES', {
    maximumFractionDigits: 1,
    minimumFractionDigits: 0,
  }).format(pct);
}

function startEdit(item: Item) {
  editingId.value = item.id;
  const max = getMaxDecimals(item.currency);
  const prettyAmount = trimTrailingZeros(clampDecimals(item.amount, max));

  draft.value = {
    name: item.name,
    category: item.category,
    subcategory: item.subcategory ?? '',
    amount: prettyAmount,
    currency: item.currency,
    notes: item.notes,
    is_active: item.is_active,
    financed_asset_id: item.financed_asset_ref ?? null,
  };
}

function toggleCategory(key: string) {
  const next = new Set(expandedCats.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  expandedCats.value = next;
}

watch(
  () => [draft.value.currency, draft.value.category],
  () => {
    if (!draft.value?.amount) return;
    const max = getMaxDecimals(draft.value.currency);
    draft.value.amount = trimTrailingZeros(clampDecimals(draft.value.amount, max));
  },
);

function cancelEdit() {
  editingId.value = null;
  draft.value = {};
}

function isValidAmountString(amount: string) {
  const s = normalizeAmountInput(amount);
  if (!s) return false;
  if ((s.match(/\./g) || []).length > 1) return false;
  if (s === '.' || s === '-' || s === '-.') return false;
  return !Number.isNaN(Number(s));
}

async function saveEdit(id: number) {
  const max = getMaxDecimals(draft.value.currency);
  const normalized = normalizeAmountInput(draft.value.amount);
  const clamped = clampDecimals(normalized, max);
  if (!isValidAmountString(clamped)) return;

  const payload: NetWorthWritePayload = {
    ...draft.value,
    amount: clamped,
    subcategory: draft.value.subcategory || undefined,
  };

  if (!isLiabilitiesList.value) {
    delete payload.financed_asset_id;
  }

  await props.onUpdate(id, payload);
  cancelEdit();
}
</script>

<template>
  <div class="card">
    <div class="nw-list-header">
      <div class="nw-list-header-left">
        <h2 class="card-header-title mt-0">{{ title }}</h2>
      </div>
      <div class="nw-list-header-right">
        <div class="nw-list-total-inline">
          <span v-if="headerBaseLabel()">{{ headerBaseLabel() }}</span>
          <span v-else>{{ formatTotalsLine(headerTotals) }}</span>
        </div>
        <button
          v-if="onAdd"
          class="btn btn-primary btn-sm nw-list-add-icon-only"
          type="button"
          aria-label="Añadir"
          @click="onAdd"
        >
          <span class="btn-icon">+</span>
        </button>
      </div>
    </div>

    <div class="nw-list-header-totals">
      <div class="nw-list-total-details">
        {{ formatTotalsLine(headerTotals) }}
      </div>
    </div>

    <div v-if="!items.length" class="subtle">No hay elementos todavía.</div>

    <div v-else class="grid gap-4">
      <section
        v-for="g in grouped"
        :key="g.category"
        class="nw-cat-block"
        :class="categoryClass(g.category)"
      >
        <ItemCategoryHeader
          :label="g.label"
          :count="g.items.length"
          :totals-line="formatTotalsLine(categoryTotals(g.items))"
          :base-label="baseTotalLabel(g.category, g.items)"
          :percent="categoryPercent(g.category, g.items)"
          :show-base-total="
            shouldShowBaseTotal(categoryTotals(g.items), categoryBaseValue(g.category, g.items))
          "
          :show-toggle="g.hasSubgroups || isLiabilitiesList"
          :expanded="expandedCats.has(g.category)"
          @toggle="toggleCategory(g.category)"
        />

        <div v-if="shouldShowGroupDetails(g)" :class="g.hasSubgroups ? 'subcat-list' : ''">
          <div
            v-for="(sg, sgIndex) in g.subgroups"
            :key="subgroupKey(g, sg, sgIndex)"
            :class="g.hasSubgroups ? 'nw-subcat-block' : ''"
          >
            <ItemSubgroupHeader
              v-if="g.hasSubgroups"
              :label="sg.label"
              :totals-line="formatTotalsLine(categoryTotals(sg.items))"
              :base-label="subcategoryBaseLabel(g.category, sg.subcategory, sg.items)"
              :percent="subcategoryPercent(g.category, sg.subcategory, sg.items, g.items)"
              :show-base-total="
                shouldShowBaseTotal(
                  categoryTotals(sg.items),
                  subcategoryBaseValue(g.category, sg.subcategory, sg.items),
                )
              "
            />

            <ul class="list list-plain nw-subcat-items">
              <li v-for="it in sg.items" :key="it.id">
                <ItemDisplayRow
                  v-if="editingId !== it.id"
                  :item="it"
                  :formatted-amount="formatAmount(String(it.amount), { currency: it.currency })"
                  :is-liabilities-list="isLiabilitiesList"
                  :financed-asset-name="financedAssetName(it.financed_asset_ref)"
                  @edit="onEdit ? onEdit(it) : startEdit(it)"
                  @archive="onArchive(it.id)"
                />

                <EditableItemRow
                  v-else
                  v-model:draft="draft"
                  :categories="categories"
                  :subcategories="props.subcategories"
                  :currencies="currencies"
                  :show-financed-asset="isLiabilitiesList"
                  :financed-asset-options="financedAssetOptions"
                  :amount-hint="amountHint"
                  :amount-error="amountError"
                  @save="saveEdit(it.id)"
                  @cancel="cancelEdit"
                />
              </li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>
