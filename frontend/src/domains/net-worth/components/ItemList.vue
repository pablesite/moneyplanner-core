<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { formatAmount } from '@/lib/format';
import type { Asset, NetWorthWritePayload, Ownership } from '@/domains/net-worth/models';
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
  ownership_ref?: number | null;
  _displayAmount?: number;
  _sharePercent?: number;
  _source?: Item;

  // SOLO para pasivos (si el backend lo devuelve)
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
  ownerships?: Ownership[];
  ownershipFilterValue?: number | 'all' | 'unassigned' | null;
  showArchived?: boolean;
  onUpdate: (
    id: number,
    payload: NetWorthWritePayload & { ownership_id?: number | null },
  ) => Promise<void>;
  onArchive: (id: number) => Promise<void>;
  onDelete?: (id: number) => Promise<void>;
  onAdd?: () => void;
  addLabel?: string;
  onEdit?: (item: Item) => void;

  // SOLO para pasivos: lista de activos activos del usuario
  assets?: AssetMini[];
};

const props = defineProps<Props>();
const emit = defineEmits<{
  (e: 'update:ownershipFilterValue', value: number | 'all' | 'unassigned'): void;
}>();

const currencies = [
  { value: 'EUR', label: 'EUR' },
  { value: 'USD', label: 'USD' },
  { value: 'BTC', label: 'BTC' },
  { value: 'ETH', label: 'ETH' },
];

const editingId = ref<number | null>(null);
type EditDraft = {
  name?: string;
  category?: string;
  subcategory?: string;
  amount?: string;
  currency?: string;
  notes?: string;
  is_active?: boolean;
  ownership_id?: number | null;
  financed_asset_id?: number | null;
};
const draft = ref<EditDraft>({});
function normalizeOwnershipFilterValue(raw: unknown): number | 'all' | 'unassigned' {
  if (raw === 'all' || raw === 'unassigned') return raw;
  if (typeof raw === 'number' && Number.isInteger(raw)) return raw;
  if (typeof raw === 'string' && raw.trim() !== '') {
    const parsed = Number(raw);
    if (Number.isInteger(parsed)) return parsed;
  }
  return 'all';
}

const ownershipFilter = ref<number | 'all' | 'unassigned'>(
  normalizeOwnershipFilterValue(props.ownershipFilterValue),
);
const expandedCats = ref<Set<string>>(new Set());

const isLiabilitiesList = computed(() => props.title === 'Pasivos');

const ownershipLabel = (o: Ownership | null | undefined) => {
  if (!o) return '';

  if (o.kind === 'individual') {
    const m = o.member;
    if (m && typeof m === 'object') return m.name;
    if (typeof m === 'number') return `#${m}`;
    return 'Individual';
  }

  const splits = Array.isArray(o.splits) ? o.splits : [];
  const parts = splits.map((s) => {
    const m = s.member;
    const name = m && typeof m === 'object' ? m.name : typeof m === 'number' ? `#${m}` : '?';
    return `${name} ${s.percent ?? ''}%`.trim();
  });

  return `Compartido | ${parts.join(' | ') || 'sin splits'}`;
};

const ownershipOptions = computed(() => {
  const list = Array.isArray(props.ownerships) ? props.ownerships : [];
  return [
    { value: null, label: 'Sin asignar' },
    ...list.map((o) => ({
      value: o.id,
      label: ownershipLabel(o) || `Ownership #${o.id}`,
    })),
  ];
});

const memberFilterOptions = computed(() => {
  const list = Array.isArray(props.ownerships) ? props.ownerships : [];
  const members = list
    .filter((o) => o.kind === 'individual' && o.member)
    .map((o) => o.member)
    .filter((m): m is NonNullable<typeof m> => m != null);
  const unique = new Map<number, { id: number; name: string }>();
  for (const m of members) {
    if (!unique.has(m.id)) unique.set(m.id, { id: m.id, name: m.name });
  }
  return Array.from(unique.values()).sort((a, b) => a.name.localeCompare(b.name));
});

const ownershipById = computed(() => {
  const m = new Map<number, Ownership>();
  (props.ownerships ?? []).forEach((o) => m.set(o.id, o));
  return m;
});

function ownershipShortLabel(ownershipRef?: number | null) {
  if (ownershipRef == null) return null;

  const o = ownershipById.value.get(ownershipRef);
  if (!o) return `own #${ownershipRef}`;

  if (o.kind === 'individual') {
    const name = o.member?.name ?? `#${ownershipRef}`;
    return name;
  }

  const splits = Array.isArray(o.splits) ? o.splits : [];
  if (!splits.length) return 'Compartido';

  const first = splits[0];
  const second = splits[1];
  const isAllHalf =
    splits.length === 2 &&
    first != null &&
    second != null &&
    String(first.percent) === '50.00' &&
    String(second.percent) === '50.00';

  const names = splits.map((s) => s.member?.name ?? '?');
  if (isAllHalf) return names.join('/');

  const parts = splits.map((s) => `${s.member?.name ?? '?'} ${s.percent}%`);
  return parts.join(' | ');
}

// ---- financed asset helpers (solo pasivos) ----
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
    { value: null, label: 'No financia ningun activo' },
    ...list
      .slice()
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((a) => ({
        value: a.id,
        label: a.name,
      })),
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
    return 'Importe invalido';
  if (Number.isNaN(Number(normalizeAmountInput(clamped)))) return 'Importe invalido';
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
  if (isLiabilitiesList.value) {
    return `liab-cat-${category || 'other'}`;
  }
  return `asset-cat-${category || 'other'}`;
}

const filteredItems = computed(() => {
  const rawList = Array.isArray(props.items) ? props.items : [];
  const list = props.showArchived ? rawList : rawList.filter((it) => it.is_active !== false);
  if (ownershipFilter.value === 'all') return list;
  if (ownershipFilter.value === 'unassigned') {
    return list.filter((it) => it.ownership_ref == null);
  }
  const memberId = ownershipFilter.value;
  if (typeof memberId !== 'number') return list;
  const out: Item[] = [];
  for (const it of list) {
    if (it.ownership_ref == null) continue;
    const o = ownershipById.value.get(it.ownership_ref);
    if (!o) continue;
    let pct = 0;
    if (o.kind === 'individual' && o.member?.id === memberId) {
      pct = 100;
    } else if (o.kind === 'shared') {
      const split = (o.splits ?? []).find((s) => s.member?.id === memberId);
      if (split) pct = Number(normalizeAmountInput(split.percent));
    }
    if (!pct || pct <= 0) continue;
    const displayAmount = toNumberAmount(it.amount) * (pct / 100);
    out.push({
      ...it,
      _displayAmount: displayAmount,
      _sharePercent: pct,
      _source: it,
    });
  }
  return out;
});

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
      const base = {
        category,
        label: categoryLabel(category),
        items: items.sort((x, y) => x.name.localeCompare(y.name)),
        subgroups: [] as Subgroup[],
        hasSubgroups: false,
      } as Group;

      if (!props.subcategories) {
        base.subgroups = [
          {
            subcategory: null,
            label: null,
            items: base.items,
          },
        ];
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
  return formatAmountWithUnit(v, props.baseCurrency);
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
    acc[cur] = (acc[cur] ?? 0) + toNumberAmount(String(displayAmount(it)));
  }
  return acc;
}

function formatTotalsLine(totals: Record<string, number>) {
  const parts = Object.entries(totals)
    .filter(([, v]) => v !== 0)
    .map(([cur, v]) => formatAmountWithUnit(v, cur));
  return parts.join(' | ');
}

function formatAmountWithUnit(value: unknown, currency: string) {
  const amount = formatAmount(String(value), { currency });
  if (currency === 'EUR') return `${amount} €`;
  if (currency === 'USD') return `${amount} $`;
  return `${amount} ${currency}`.trim();
}

function rawValue(v: string) {
  return String(v ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(/,/g, '.');
}

function displayAmountBase(it: Item) {
  if (!it.amount_base) return null;
  const base = toNumberAmount(String(it.amount_base));
  if (!Number.isFinite(base)) return null;
  if (it._sharePercent != null) {
    return base * (it._sharePercent / 100);
  }
  return base;
}

function totalBaseForItems(items: Item[]) {
  let sum = 0;
  let hasAny = false;
  for (const it of items) {
    const v = displayAmountBase(it);
    if (v == null) continue;
    hasAny = true;
    sum += v;
  }
  return hasAny ? sum : null;
}

function totalBaseAll() {
  if (ownershipFilter.value === 'all') {
    if (!props.totalBase) return null;
    const total = Number(rawValue(props.totalBase));
    return Number.isFinite(total) ? total : null;
  }
  return totalBaseForItems(filteredItems.value);
}

function categoryBaseValue(category: string, items: Item[]) {
  if (ownershipFilter.value === 'all') {
    if (!props.categoryTotalsBase) return null;
    const raw = props.categoryTotalsBase[category];
    if (!raw) return null;
    const v = Number(rawValue(raw));
    return Number.isFinite(v) ? v : null;
  }
  return totalBaseForItems(items);
}

function subcategoryBaseValue(category: string, subcategory: string | null, items: Item[]) {
  const subKey = subcategory ?? 'other';
  if (ownershipFilter.value === 'all') {
    if (!props.subcategoryTotalsBase) return null;
    const raw = props.subcategoryTotalsBase[`${category}:${subKey}`];
    if (!raw) return null;
    const v = Number(rawValue(raw));
    return Number.isFinite(v) ? v : null;
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
  return formatAmountWithUnit(v, props.baseCurrency);
}

function subcategoryBaseLabel(category: string, subcategory: string | null, items: Item[]) {
  if (!props.baseCurrency) return null;
  const v = subcategoryBaseValue(category, subcategory, items);
  if (v == null) return null;
  return formatAmountWithUnit(v, props.baseCurrency);
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
    ownership_id: item.ownership_ref ?? null,

    // SOLO pasivos
    financed_asset_id: item.financed_asset_ref ?? null,
  };
}

function editTarget(it: Item) {
  return it._source ?? it;
}

function displayAmount(it: Item) {
  const base = it._displayAmount ?? it.amount;
  if (!it._displayAmount && it.effective_amount) {
    return it.effective_amount;
  }
  return base;
}

function toggleCategory(key: string) {
  const next = new Set(expandedCats.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  expandedCats.value = next;
}

async function handleDelete(id: number) {
  if (!props.onDelete) return;
  const label = isLiabilitiesList.value ? 'pasivo' : 'activo';
  if (!confirm(`Eliminar este ${label} de forma permanente? Esta accion no se puede deshacer.`)) {
    return;
  }
  await props.onDelete(id);
}

watch(
  () => [draft.value.currency, draft.value.category],
  () => {
    if (!draft.value?.amount) return;
    const max = getMaxDecimals(draft.value.currency);
    draft.value.amount = trimTrailingZeros(clampDecimals(draft.value.amount, max));
  },
);

watch(
  () => [ownershipFilter.value, filteredItems.value.length],
  () => {
    expandedCats.value = new Set();
  },
);

watch(
  () => props.ownershipFilterValue,
  (next) => {
    const normalized = normalizeOwnershipFilterValue(next);
    if (ownershipFilter.value !== normalized) {
      ownershipFilter.value = normalized;
    }
  },
);

watch(
  ownershipFilter,
  (next) => {
    emit('update:ownershipFilterValue', next);
  },
  { immediate: true },
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

  const payload: NetWorthWritePayload & { ownership_id?: number | null } = {
    ...draft.value,
    amount: clamped,
    subcategory: draft.value.subcategory || undefined,
  };

  // Seguridad: si no es lista de pasivos, no mandes financed_asset_id
  if (!isLiabilitiesList.value) {
    delete payload.financed_asset_id;
  }

  await props.onUpdate(id, payload);
  cancelEdit();
}
</script>

<template>
  <div class="card ui-pro-panel ui-nw-list-panel">
    <div class="nw-list-header">
      <div class="nw-list-header-left">
        <h2 class="card-header-title mt-0">{{ title }}</h2>
        <select v-model="ownershipFilter" class="select nw-select-sm">
          <option value="all">Todos los miembros</option>
          <option value="unassigned">Sin asignar</option>
          <option v-for="m in memberFilterOptions" :key="String(m.id)" :value="m.id">
            {{ m.name }}
          </option>
        </select>
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
          aria-label="Anadir"
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

    <div v-if="!items.length" class="subtle">No hay elementos todavia.</div>

    <div v-else-if="!filteredItems.length" class="subtle">No hay elementos con este filtro.</div>
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
                  :formatted-amount="formatAmountWithUnit(displayAmount(it), it.currency)"
                  :is-liabilities-list="isLiabilitiesList"
                  :financed-asset-name="financedAssetName(it.financed_asset_ref)"
                  :ownership-label="ownershipShortLabel(it.ownership_ref)"
                  :share-percent="it._sharePercent"
                  @edit="onEdit ? onEdit(editTarget(it)) : startEdit(editTarget(it))"
                  @archive="onArchive(it.id)"
                  @delete="handleDelete(it.id)"
                />

                <EditableItemRow
                  v-else
                  v-model:draft="draft"
                  :categories="categories"
                  :subcategories="props.subcategories"
                  :currencies="currencies"
                  :ownership-options="ownershipOptions"
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
