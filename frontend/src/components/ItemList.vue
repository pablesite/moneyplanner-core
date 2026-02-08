<script setup lang="ts">
import { computed, ref, watch } from "vue";
import { formatAmount } from "@/lib/format";

type Ownership = {
  id: number;
  kind: "individual" | "shared";
  member: { id: number; name: string; role: "adult" | "child" } | null;
  splits: { member: { id: number; name: string; role: "adult" | "child" }; percent: string }[];
  notes: string;
};

type AssetMini = {
  id: number;
  name: string;
  category: string;
};

type Item = {
  id: number;
  name: string;
  category: string;
  subcategory?: string;
  amount: string;
  amount_base?: string;
  currency: string;
  notes: string;
  is_active: boolean;
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
  ownerships: Ownership[];
  onUpdate: (
    id: number,
    payload: Partial<Item> & { ownership_id?: number | null; financed_asset_id?: number | null }
  ) => Promise<void>;
  onArchive: (id: number) => Promise<void>;
  onAdd?: () => void;
  addLabel?: string;
  onEdit?: (item: Item) => void;

  // SOLO para pasivos: lista de activos activos del usuario
  assets?: AssetMini[];
};

const props = defineProps<Props>();

const currencies = [
  { value: "EUR", label: "EUR" },
  { value: "USD", label: "USD" },
  { value: "BTC", label: "BTC" },
  { value: "ETH", label: "ETH" },
];

const editingId = ref<number | null>(null);
const draft = ref<any>({});
const ownershipFilter = ref<number | "all" | "unassigned">("all");
const expandedCats = ref<Set<string>>(new Set());

const isLiabilitiesList = computed(() => props.title === "Pasivos");

const ownershipLabel = (o: any) => {
  if (!o) return "";

  if (o.kind === "individual") {
    const m = o.member;
    if (m && typeof m === "object") return m.name;
    if (typeof m === "number") return `#${m}`;
    return "Individual";
  }

  const splits = Array.isArray(o.splits) ? o.splits : [];
  const parts = splits.map((s: any) => {
    const m = s.member;
    const name =
      m && typeof m === "object"
        ? m.name
        : typeof m === "number"
        ? `#${m}`
        : s.member_id != null
        ? `#${s.member_id}`
        : "¿?";
    return `${name} ${s.percent ?? ""}%`.trim();
  });

  return `Compartido · ${parts.join(" · ") || "sin splits"}`;
};

const ownershipOptions = computed(() => {
  const list = Array.isArray(props.ownerships) ? props.ownerships : [];
  return [
    { value: null, label: "— Sin asignar —" },
    ...list.map((o: any) => ({
      value: o.id,
      label: ownershipLabel(o) || `Ownership #${o.id}`,
    })),
  ];
});

const memberFilterOptions = computed(() => {
  const list = Array.isArray(props.ownerships) ? props.ownerships : [];
  const members = list
    .filter((o) => o.kind === "individual" && o.member)
    .map((o) => o.member);
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

  if (o.kind === "individual") {
    const name = o.member?.name ?? `#${ownershipRef}`;
    return name;
  }

  const splits = Array.isArray(o.splits) ? o.splits : [];
  if (!splits.length) return "Compartido";

  const isAllHalf =
    splits.length === 2 &&
    String(splits[0].percent) === "50.00" &&
    String(splits[1].percent) === "50.00";

  const names = splits.map((s) => s.member?.name ?? "?");
  if (isAllHalf) return names.join("/");

  const parts = splits.map((s) => `${s.member?.name ?? "?"} ${s.percent}%`);
  return parts.join(" · ");
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
    { value: null, label: "— No financia ningún activo —" },
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

function getMaxDecimals(currency: string, category?: string) {
  return decimalsByCurrency[currency] ?? 2;
}

const amountHint = computed(() => {
  const max = getMaxDecimals(draft.value.currency, draft.value.category);
  return `Hasta ${max} decimales`;
});

function normalizeAmountInput(raw: unknown) {
  return String(raw ?? "").trim().replace(/\s/g, "").replace(/,/g, ".");
}

function clampDecimals(amount: string, maxDecimals: number) {
  const s = normalizeAmountInput(amount);
  if (!s) return "";
  if ((s.match(/\./g) || []).length > 1) return s;

  const [i, d = ""] = s.split(".");
  return d ? `${i}.${d.slice(0, maxDecimals)}` : i;
}

function trimTrailingZeros(amount: string) {
  if (!amount.includes(".")) return amount;
  return amount.replace(/\.?0+$/, "");
}

const amountError = computed(() => {
  const max = getMaxDecimals(draft.value.currency, draft.value.category);
  const clamped = clampDecimals(draft.value.amount, max);

  if (!draft.value.amount) return "";
  if ((normalizeAmountInput(draft.value.amount).match(/\./g) || []).length > 1) return "Importe inválido";
  if (Number.isNaN(Number(normalizeAmountInput(clamped)))) return "Importe inválido";
  return "";
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
    return `liab-cat-${category || "other"}`;
  }
  return `asset-cat-${category || "other"}`;
}

const filteredItems = computed(() => {
  const list = Array.isArray(props.items) ? props.items : [];
  if (ownershipFilter.value === "all") return list;
  if (ownershipFilter.value === "unassigned") {
    return list.filter((it) => it.ownership_ref == null);
  }
  const memberId = ownershipFilter.value;
  if (typeof memberId !== "number") return list;
  const out: Item[] = [];
  for (const it of list) {
    if (it.ownership_ref == null) continue;
    const o = ownershipById.value.get(it.ownership_ref);
    if (!o) continue;
    let pct = 0;
    if (o.kind === "individual" && o.member?.id === memberId) {
      pct = 100;
    } else if (o.kind === "shared") {
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
    const key = it.category ?? "other";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(it);
  }

  const orderedAssetCats = ["cash", "investments", "real_estate", "furnishings", "other"];
  const orderedLiabCats = ["credit_card", "personal_loan", "mortgage", "other"];
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
        const subKey = it.subcategory || "other";
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
  const s = String(raw ?? "").trim().replace(/\s/g, "").replace(/,/g, ".");
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

function categoryTotals(items: Item[]) {
  const acc: Record<string, number> = {};
  for (const it of items) {
    const cur = it.currency || "???";
    acc[cur] = (acc[cur] ?? 0) + toNumberAmount(displayAmount(it));
  }
  return acc;
}

function formatTotalsLine(totals: Record<string, number>) {
  const parts = Object.entries(totals)
    .filter(([, v]) => v !== 0)
    .map(([cur, v]) => `${formatAmount(String(v), { currency: cur })} ${cur}`);
  return parts.join(" · ");
}

function rawValue(v: string) {
  return String(v ?? "").trim().replace(/\s/g, "").replace(/,/g, ".");
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
  if (ownershipFilter.value === "all") {
    if (!props.totalBase) return null;
    const total = Number(rawValue(props.totalBase));
    return Number.isFinite(total) ? total : null;
  }
  return totalBaseForItems(filteredItems.value);
}

function categoryBaseValue(category: string, items: Item[]) {
  if (ownershipFilter.value === "all") {
    if (!props.categoryTotalsBase) return null;
    const raw = props.categoryTotalsBase[category];
    if (!raw) return null;
    const v = Number(rawValue(raw));
    return Number.isFinite(v) ? v : null;
  }
  return totalBaseForItems(items);
}

function subcategoryBaseValue(category: string, subcategory: string, items: Item[]) {
  if (ownershipFilter.value === "all") {
    if (!props.subcategoryTotalsBase) return null;
    const raw = props.subcategoryTotalsBase[`${category}:${subcategory}`];
    if (!raw) return null;
    const v = Number(rawValue(raw));
    return Number.isFinite(v) ? v : null;
  }
  return totalBaseForItems(items);
}

function shouldShowBaseTotal(totals: Record<string, number>, baseValue: number | null) {
  if (!props.baseCurrency) return false;
  if (baseValue == null) return false;
  const nonZero = Object.entries(totals).filter(([, v]) => v !== 0).map(([cur]) => cur);
  if (nonZero.length === 0) return false;
  return !(nonZero.length === 1 && nonZero[0] === props.baseCurrency);
}

function baseTotalLabel(category: string, items: Item[]) {
  if (!props.baseCurrency) return null;
  const v = categoryBaseValue(category, items);
  if (v == null) return null;
  return `${formatAmount(String(v), { currency: props.baseCurrency })} ${props.baseCurrency}`;
}

function subcategoryBaseLabel(category: string, subcategory: string, items: Item[]) {
  if (!props.baseCurrency) return null;
  const v = subcategoryBaseValue(category, subcategory, items);
  if (v == null) return null;
  return `${formatAmount(String(v), { currency: props.baseCurrency })} ${props.baseCurrency}`;
}

function subcategoryPercent(
  category: string,
  subcategory: string,
  items: Item[],
  categoryItems: Item[]
) {
  const sub = subcategoryBaseValue(category, subcategory, items);
  if (sub == null) return null;
  const cat = categoryBaseValue(category, categoryItems);
  if (cat == null || cat === 0) return null;
  const pct = (sub / cat) * 100;
  return new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1, minimumFractionDigits: 0 }).format(pct);
}

function categoryPercent(category: string, items: Item[]) {
  const v = categoryBaseValue(category, items);
  if (v == null) return null;
  const total = totalBaseAll();
  if (total == null || total === 0) return null;
  const pct = (v / total) * 100;
  return new Intl.NumberFormat("es-ES", { maximumFractionDigits: 1, minimumFractionDigits: 0 }).format(pct);
}

function startEdit(item: Item) {
  editingId.value = item.id;

  const max = getMaxDecimals(item.currency, item.category);
  const prettyAmount = trimTrailingZeros(clampDecimals(item.amount, max));

  draft.value = {
    name: item.name,
    category: item.category,
    subcategory: item.subcategory ?? "",
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
  return it._displayAmount ?? it.amount;
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
    const max = getMaxDecimals(draft.value.currency, draft.value.category);
    draft.value.amount = trimTrailingZeros(clampDecimals(draft.value.amount, max));
  }
);

watch(
  () => [ownershipFilter.value, filteredItems.value.length],
  () => {
    expandedCats.value = new Set();
  }
);

function cancelEdit() {
  editingId.value = null;
  draft.value = {};
};


function isValidAmountString(amount: string) {
  const s = normalizeAmountInput(amount);
  if (!s) return false;
  if ((s.match(/\./g) || []).length > 1) return false;
  if (s === "." || s === "-" || s === "-.") return false;
  return !Number.isNaN(Number(s));
}

async function saveEdit(id: number) {
  const max = getMaxDecimals(draft.value.currency, draft.value.category);

  const normalized = normalizeAmountInput(draft.value.amount);
  const clamped = clampDecimals(normalized, max);

  if (!isValidAmountString(clamped)) return;

  const payload: any = {
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
  <div class="card">
    <div class="card-header">
      <div class="card-header-left">
        <h2 style="margin-top: 0" class="card-header-title">{{ title }}</h2>
        <select v-model="ownershipFilter" class="select select-sm">
          <option value="all">Todos los miembros</option>
          <option value="unassigned">Sin asignar</option>
          <option v-for="m in memberFilterOptions" :key="String(m.id)" :value="m.id">
            {{ m.name }}
          </option>
        </select>
      </div>
      <div class="card-header-right">
        <div class="header-total-inline">
          <span v-if="headerBaseLabel()">{{ headerBaseLabel() }}</span>
          <span v-else>{{ formatTotalsLine(headerTotals) }}</span>
        </div>
        <button v-if="onAdd" class="btn btn-primary btn-sm add-icon-only" type="button" @click="onAdd" aria-label="Añadir">
          <span class="btn-icon">+</span>
        </button>
      </div>
    </div>

    <div class="card-header-totals">
      <div class="header-total-details">
        {{ formatTotalsLine(headerTotals) }}
      </div>
    </div>

    <div v-if="!items.length" class="subtle">No hay elementos todavía.</div>

    <div v-else-if="!filteredItems.length" class="subtle">No hay elementos con este filtro.</div>
    <div v-else style="display:grid; gap:16px;">
            <section
              v-for="g in grouped"
              :key="g.category"
              class="cat-block"
              :class="categoryClass(g.category)"
            >
        <div class="cat-header">
          <div class="cat-left">
            <div style="font-size:16px;">{{ g.label }}</div>
            <span class="badge">{{ g.items.length }}</span>
          </div>
          <div class="cat-right">
            <div class="cat-total">
              <div
                v-if="shouldShowBaseTotal(categoryTotals(g.items), categoryBaseValue(g.category, g.items)) && baseTotalLabel(g.category, g.items)"
                class="cat-total-primary"
              >
                {{ baseTotalLabel(g.category, g.items) }}
                <span v-if="categoryPercent(g.category, g.items)" class="cat-percent">
                  . {{ categoryPercent(g.category, g.items) }}%
                </span>
              </div>
              <div
                :class="shouldShowBaseTotal(categoryTotals(g.items), categoryBaseValue(g.category, g.items)) && baseTotalLabel(g.category, g.items) ? 'cat-total-details' : 'cat-total-primary'"
              >
                {{ formatTotalsLine(categoryTotals(g.items)) }}
                <span
                  v-if="!shouldShowBaseTotal(categoryTotals(g.items), categoryBaseValue(g.category, g.items)) && categoryPercent(g.category, g.items)"
                  class="cat-percent"
                >
                  . {{ categoryPercent(g.category, g.items) }}%
                </span>
              </div>
            </div>
            <button
              v-if="g.hasSubgroups || isLiabilitiesList"
              class="icon-btn cat-toggle"
              type="button"
              @click="toggleCategory(g.category)"
              :aria-label="expandedCats.has(g.category) ? 'Ocultar desglose' : 'Mostrar desglose'"
              :title="expandedCats.has(g.category) ? 'Ocultar desglose' : 'Mostrar desglose'"
            >
              <span class="icon" aria-hidden="true" v-if="expandedCats.has(g.category)">&#9662;</span><span class="icon" aria-hidden="true" v-else>&#9656;</span>
            </button>
          </div>
        </div>

        <div v-if="shouldShowGroupDetails(g)" :class="g.hasSubgroups ? 'subcat-list' : ''">
          <div
            v-for="(sg, sgIndex) in g.subgroups"
            :key="subgroupKey(g, sg, sgIndex)"
            :class="g.hasSubgroups ? 'subcat-block' : ''"
          >
            <div v-if="g.hasSubgroups" class="subcat-header">
              <div class="subcat-title">{{ sg.label }}</div>
              <div class="subcat-total">
                <div
                  v-if="shouldShowBaseTotal(categoryTotals(sg.items), subcategoryBaseValue(g.category, sg.subcategory, sg.items)) && subcategoryBaseLabel(g.category, sg.subcategory, sg.items)"
                  class="subcat-total-primary"
                >
                  {{ subcategoryBaseLabel(g.category, sg.subcategory, sg.items) }}
                  <span v-if="subcategoryPercent(g.category, sg.subcategory, sg.items, g.items)" class="subcat-percent">
                    · {{ subcategoryPercent(g.category, sg.subcategory, sg.items, g.items) }}%
                  </span>
                </div>
                <div
                  :class="shouldShowBaseTotal(categoryTotals(sg.items), subcategoryBaseValue(g.category, sg.subcategory, sg.items)) && subcategoryBaseLabel(g.category, sg.subcategory, sg.items) ? 'subcat-total-details' : 'subcat-total-primary'"
                >
                  {{ formatTotalsLine(categoryTotals(sg.items)) }}
                  <span
                    v-if="!shouldShowBaseTotal(categoryTotals(sg.items), subcategoryBaseValue(g.category, sg.subcategory, sg.items)) && subcategoryPercent(g.category, sg.subcategory, sg.items, g.items)"
                    class="subcat-percent"
                  >
                    · {{ subcategoryPercent(g.category, sg.subcategory, sg.items, g.items) }}%
                  </span>
                </div>
              </div>
              <div class="subcat-actions-spacer" aria-hidden="true"></div>
            </div>

            <ul class="list list-plain subcat-items">
              <li v-for="it in sg.items" :key="it.id">
                <div v-if="editingId !== it.id" class="item-row">
                  <div class="item-main">
                    <div class="item-name">
                      <span class="item-name-text">{{ it.name }}</span>
                      <span v-if="!it.is_active" class="badge">archivado</span>

                      <span v-if="ownershipShortLabel(it.ownership_ref)" class="badge">
                        {{ ownershipShortLabel(it.ownership_ref) }}
                      </span>
                      <span v-if="it._sharePercent && it._sharePercent < 100" class="badge">
                        {{ it._sharePercent }}%
                      </span>
                    </div>
                    <div v-if="isLiabilitiesList && it.financed_asset_ref" class="item-submeta inline">
                      <span class="financed-text">
                        · Financia: {{ financedAssetName(it.financed_asset_ref) }}
                      </span>
                    </div>
                  </div>
                  <div class="item-amount">
                    {{ formatAmount(String(displayAmount(it)), { currency: it.currency }) }} {{ it.currency }}
                  </div>
                  <div class="actions">
                    <button
                      @click="onEdit ? onEdit(editTarget(it)) : startEdit(editTarget(it))"
                      class="icon-btn"
                      title="Editar"
                      aria-label="Editar"
                    >
                      &#9998;&#65039;
                    </button>
                    <button @click="onArchive(it.id)" class="icon-btn" title="Archivar" aria-label="Archivar">&#128465;&#65039;</button>
                  </div>
                </div>

                <div v-else class="form-grid" style="max-width: 520px;">
                  <input v-model="draft.name" class="input" />

                  <select v-model="draft.category" class="select">
                    <option v-for="c in categories" :key="c.value" :value="c.value">
                      {{ c.label }}
                    </option>
                  </select>

                  <select v-if="props.subcategories" v-model="draft.subcategory" class="select">
                    <option v-for="s in props.subcategories.filter((sc) => sc.category === draft.category)" :key="s.value" :value="s.value">
                      {{ s.label }}
                    </option>
                  </select>

                  <select v-model="draft.currency" class="select">
                    <option v-for="c in currencies" :key="c.value" :value="c.value">
                      {{ c.label }}
                    </option>
                  </select>

                  <input v-model="draft.amount" inputmode="decimal" class="input" />

                  <select v-model="draft.ownership_id" class="select">
                    <option v-for="o in ownershipOptions" :key="String(o.value)" :value="o.value">
                      {{ o.label }}
                    </option>
                  </select>

                  <select
                    v-if="isLiabilitiesList"
                    v-model="draft.financed_asset_id"
                    class="select"
                  >
                    <option v-for="a in financedAssetOptions" :key="String(a.value)" :value="a.value">
                      {{ a.label }}
                    </option>
                  </select>

                  <textarea v-model="draft.notes" rows="2" class="textarea"></textarea>

                  <label class="checkbox-row">
                    <input v-model="draft.is_active" type="checkbox" />
                    Activo
                  </label>

                  <div style="grid-column: 1 / -1; font-size: 12px; opacity: 0.7;">
                    {{ amountHint }}
                  </div>

                  <div v-if="amountError" style="grid-column: 1 / -1; font-size: 12px; color: #b00020;">
                    {{ amountError }}
                  </div>

                  <div class="actions">
                    <button @click="saveEdit(it.id)" class="btn btn-primary" :disabled="!!amountError">Guardar</button>
                    <button @click="cancelEdit" class="btn">Cancelar</button>
                  </div>
                </div>
              </li>
            </ul>
          </div>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.card-header{
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto;
  align-items: center;
  gap: 12px;
}
.card-header-left{
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: nowrap;
}
.card-header-right{
  display: flex;
  align-items: center;
  gap: 10px;
}
.card-header-totals{
  display: flex;
  justify-content: flex-end;
  margin-top: 4px;
}
.header-total-inline{
  text-align: right;
  font-weight: 600;
  white-space: nowrap;
  font-variant-numeric: tabular-nums;
}

.header-total-details{
  text-align: right;
  color: rgba(255,255,255,0.55);
  font-size: 12px;
  font-weight: 500;
  white-space: normal;
  word-break: break-word;
}
.select-sm{
  padding: 6px 8px;
  border-radius: 10px;
  font-size: 12px;
  min-width: 170px;
  width: auto;
}

.add-icon-only{
  width: 34px;
  height: 34px;
  padding: 0;
  display: inline-flex;
  align-items: center;
  justify-content: center;
}

.add-icon-only .btn-icon{
  margin-right: 0;
  width: auto;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  line-height: 1;
  font-size: 16px;
}

.cat-right{
  display: flex;
  align-items: baseline;
  gap: 12px;
}

.cat-toggle{
  margin-left: 0;
}

.cat-header{
  display: flex;
  align-items: baseline;
  justify-content: space-between;
  gap: 12px;
}

.cat-block{
  position: relative;
  padding-left: 10px;
}
.cat-block::before{
  content: "";
  position: absolute;
  left: 0;
  top: 6px;
  bottom: 6px;
  width: 3px;
  border-radius: 999px;
  background: var(--cat-accent, rgba(255,255,255,0.2));
}
.cat-left{
  position: relative;
}
.cat-left > div{
  color: var(--cat-accent-text, rgba(255,255,255,0.92));
}
.cat-left .badge{
  border: 1px solid var(--cat-accent, rgba(255,255,255,0.2));
  color: var(--cat-accent-text, rgba(255,255,255,0.85));
}

/* Activos: familia frío/verde */
.asset-cat-cash{
  --cat-accent: rgba(92, 192, 255, 0.9);
  --cat-accent-text: rgba(180, 230, 255, 0.95);
}
.asset-cat-investments{
  --cat-accent: rgba(74, 209, 179, 0.9);
  --cat-accent-text: rgba(168, 241, 224, 0.95);
}
.asset-cat-real_estate{
  --cat-accent: rgba(111, 211, 122, 0.9);
  --cat-accent-text: rgba(190, 244, 200, 0.95);
}
.asset-cat-furnishings{
  --cat-accent: rgba(138, 203, 136, 0.85);
  --cat-accent-text: rgba(200, 238, 200, 0.95);
}
.asset-cat-other{
  --cat-accent: rgba(122, 161, 194, 0.85);
  --cat-accent-text: rgba(198, 216, 232, 0.95);
}

/* Pasivos: rojo estable para diferenciar */
.liab-cat-mortgage{
  --cat-accent: rgba(255, 99, 132, 0.85);
  --cat-accent-text: rgba(255, 200, 210, 0.95);
}
.liab-cat-personal_loan{
  --cat-accent: rgba(255, 120, 150, 0.85);
  --cat-accent-text: rgba(255, 210, 220, 0.95);
}
.liab-cat-credit_card{
  --cat-accent: rgba(255, 140, 110, 0.85);
  --cat-accent-text: rgba(255, 215, 200, 0.95);
}
.liab-cat-other{
  --cat-accent: rgba(255, 130, 130, 0.8);
  --cat-accent-text: rgba(255, 210, 210, 0.95);
}

.cat-left{
  display: flex;
  align-items: center;
  gap: 8px;
  min-width: 0;
}

.cat-total{
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  text-align: right;
  line-height: 1.15;
  max-width: 280px;
}
.cat-total > div{
  word-break: break-word;
}
.cat-total-primary{
  color: rgba(255,255,255,0.92);
  font-size: 13px;
  font-weight: 700;
}
.cat-total-details{
  color: rgba(255,255,255,0.55);
  font-size: 11px;
  font-weight: 500;
}

.cat-percent{
  color: rgba(255,255,255,0.55);
}
.subcat-header{
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: baseline;
  gap: 12px;
  margin-top: 12px;
  padding-top: 6px;
}
.subcat-title{
  font-size: 11px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: none;
  min-width: 0;
  text-transform: uppercase;
  color: rgba(255,255,255,0.75);
}
.subcat-block{
  --item-actions-width: 72px;
}
.subcat-total{
  display: grid;
  justify-items: end;
  text-align: right;
  font-size: 10px;
  font-weight: 600;
  line-height: 1.1;
  white-space: nowrap;
}
.subcat-total-primary{
  color: rgba(255,255,255,0.9);
  font-size: 11px;
  font-weight: 700;
}
.subcat-total-details{
  color: rgba(255,255,255,0.55);
  font-size: 10px;
  font-weight: 500;
}
.subcat-percent{
  color: rgba(255,255,255,0.55);
}
.subcat-actions-spacer{
  width: var(--item-actions-width, 72px);
}

.item-sep {
  margin: 0 8px;
  color: rgba(255, 255, 255, 0.25);
}
.subcat-items .item-row{
  border: none;
  background: transparent;
  box-shadow: none;
  border-radius: 0;
  padding: 3px 2px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  column-gap: 12px;
}
.subcat-items .item-row + .item-row{
  border-top: 1px solid rgba(255,255,255,0.06);
  padding-top: 6px;
  margin-top: 4px;
}
.subcat-items .item-main{
  min-width: 0;
  padding-left: 12px;
}
.subcat-items .item-name{
  font-size: 14px;
  font-weight: 500;
}
.subcat-items .item-submeta{
  margin-top: 2px;
  font-size: 12px;
  color: rgba(255,255,255,0.65);
}
.subcat-items .item-submeta .financed-text{
  display: inline-block;
  padding: 0;
  border: none;
  background: transparent;
}
.subcat-items .item-submeta.inline{
  display: inline;
  margin-top: 0;
}
.subcat-items .item-amount{
  text-align: right;
  white-space: nowrap;
  font-weight: 600;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}
.subcat-items .actions{
  justify-self: end;
  min-width: var(--item-actions-width, 72px);
}
.subcat-items .actions .icon-btn{
  width: 28px;
  height: 28px;
  padding: 0;
  font-size: 12px;
}</style>
