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
  amount: string;
  currency: string;
  notes: string;
  is_active: boolean;
  ownership_ref?: number | null;

  // SOLO para pasivos (si el backend lo devuelve)
  financed_asset_ref?: number | null;
};

type Props = {
  title: string;
  items: Item[];
  categories: { value: string; label: string }[];
  ownerships: Ownership[];
  onUpdate: (
    id: number,
    payload: Partial<Item> & { ownership_id?: number | null; financed_asset_id?: number | null }
  ) => Promise<void>;
  onArchive: (id: number) => Promise<void>;
  onAdd?: () => void;
  addLabel?: string;

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

const isLiabilitiesList = computed(() => props.title === "Pasivos");

const ownershipLabel = (o: any) => {
  if (!o) return "";

  if (o.kind === "individual") {
    const m = o.member;
    if (m && typeof m === "object") return `Individual · ${m.name}`;
    if (typeof m === "number") return `Individual · #${m}`;
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

const ownershipById = computed(() => {
  const m = new Map<number, Ownership>();
  (props.ownerships ?? []).forEach((o) => m.set(o.id, o));
  return m;
});

function ownershipShortLabel(ownershipRef?: number | null) {
  if (!ownershipRef) return null;

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

const grouped = computed(() => {
  const list = Array.isArray(props.items) ? props.items : [];
  const map = new Map<string, Item[]>();

  for (const it of list) {
    const key = it.category ?? "other";
    if (!map.has(key)) map.set(key, []);
    map.get(key)!.push(it);
  }

  return Array.from(map.entries())
    .sort(([a], [b]) => categoryLabel(a).localeCompare(categoryLabel(b)))
    .map(([category, items]) => ({
      category,
      label: categoryLabel(category),
      items: items.sort((x, y) => x.name.localeCompare(y.name)),
    }));
});

function toNumberAmount(raw: string) {
  const s = String(raw ?? "").trim().replace(/\s/g, "").replace(/,/g, ".");
  const n = Number(s);
  return Number.isFinite(n) ? n : 0;
}

function categoryTotals(items: Item[]) {
  const acc: Record<string, number> = {};
  for (const it of items) {
    const cur = it.currency || "???";
    acc[cur] = (acc[cur] ?? 0) + toNumberAmount(it.amount);
  }
  return acc;
}

function formatTotalsLine(totals: Record<string, number>) {
  const parts = Object.entries(totals)
    .filter(([, v]) => v !== 0)
    .map(([cur, v]) => `${formatAmount(String(v), { currency: cur })} ${cur}`);
  return parts.join(" · ");
}

function startEdit(item: Item) {
  editingId.value = item.id;

  const max = getMaxDecimals(item.currency, item.category);
  const prettyAmount = trimTrailingZeros(clampDecimals(item.amount, max));

  draft.value = {
    name: item.name,
    category: item.category,
    amount: prettyAmount,
    currency: item.currency,
    notes: item.notes,
    is_active: item.is_active,
    ownership_id: item.ownership_ref ?? null,

    // SOLO pasivos
    financed_asset_id: item.financed_asset_ref ?? null,
  };
}

watch(
  () => [draft.value.currency, draft.value.category],
  () => {
    if (!draft.value?.amount) return;
    const max = getMaxDecimals(draft.value.currency, draft.value.category);
    draft.value.amount = trimTrailingZeros(clampDecimals(draft.value.amount, max));
  }
);

function cancelEdit() {
  editingId.value = null;
  draft.value = {};
}

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
      <h2 style="margin-top: 0" class="card-header-title">{{ title }}</h2>

      <button v-if="onAdd" class="btn btn-primary btn-sm" type="button" @click="onAdd">
        <span class="btn-icon">＋</span>
        {{ addLabel ?? "Añadir" }}
      </button>
    </div>

    <div v-if="!items.length" class="subtle">No hay elementos todavía.</div>

    <div v-else style="display:grid; gap:16px;">
      <section v-for="g in grouped" :key="g.category" class="cat-block">
        <div class="cat-header">
          <div class="cat-left">
            <div style="font-size:16px;">{{ g.label }}</div>
            <span class="badge">{{ g.items.length }}</span>
          </div>

          <div class="cat-total">
            {{ formatTotalsLine(categoryTotals(g.items)) }}
          </div>
        </div>

        <ul class="list list-plain" style="display:grid; gap:10px;">
          <li v-for="it in g.items" :key="it.id">
            <div v-if="editingId !== it.id" class="item-row">
              <div class="item-main">
                <div class="item-name">
                  <span>{{ it.name }}</span>
                  <span class="subtle">—</span>
                  <span>{{ formatAmount(it.amount, { currency: it.currency }) }} {{ it.currency }}</span>
                </div>

                <span v-if="!it.is_active" class="badge">archivado</span>

                <span v-if="ownershipShortLabel(it.ownership_ref)" class="badge">
                  {{ ownershipShortLabel(it.ownership_ref) }}
                </span>

                <!-- SOLO pasivos: badge de financiación -->
                <span v-if="isLiabilitiesList && it.financed_asset_ref" class="badge">
                  Financia: {{ financedAssetName(it.financed_asset_ref) }}
                </span>
              </div>

              <div class="actions">
                <button @click="startEdit(it)" class="icon-btn" title="Editar" aria-label="Editar">✏️</button>
                <button @click="onArchive(it.id)" class="icon-btn" title="Archivar" aria-label="Archivar">🗑️</button>
              </div>
            </div>

            <div v-else class="form-grid" style="max-width: 520px;">
              <input v-model="draft.name" class="input" />

              <select v-model="draft.category" class="select">
                <option v-for="c in categories" :key="c.value" :value="c.value">
                  {{ c.label }}
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

              <!-- SOLO pasivos: selector de activo financiado -->
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
      </section>
    </div>
  </div>
</template>
