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

type Item = {
  id: number;
  name: string;
  category: string;
  amount: string;
  currency: string;
  notes: string;
  is_active: boolean;

  // backend ya devuelve ownership_ref; en tu serializer lo llamaste ownership_ref
  ownership_ref?: number | null;
};

type Props = {
  title: string;
  items: Item[];
  categories: { value: string; label: string }[];
  ownerships: Ownership[];
  onUpdate: (id: number, payload: Partial<Item> & { ownership_id?: number | null }) => Promise<void>;
  onArchive: (id: number) => Promise<void>;
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

const ownershipLabel = (o: any) => {
  if (!o) return "";

  if (o.kind === "individual") {
    const m = o.member;
    if (m && typeof m === "object") return `Individual · ${m.name}`;
    if (typeof m === "number") return `Individual · #${m}`;
    return "Individual";
  }

  // shared
  const splits = Array.isArray(o.splits) ? o.splits : [];
  const parts = splits.map((s: any) => {
    const m = s.member;
    const name =
      m && typeof m === "object" ? m.name :
      typeof m === "number" ? `#${m}` :
      s.member_id != null ? `#${s.member_id}` :
      "¿?";
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
      label: ownershipLabel(o) || `Ownership #${o.id}`, // fallback
    })),
  ];
});

const decimalsByCurrency: Record<string, number> = {
  EUR: 2,
  USD: 2,
  BTC: 8,
  ETH: 8,
};

const amountHint = computed(() => {
  const max = getMaxDecimals(draft.value.currency, draft.value.category);
  return `Hasta ${max} decimales`;
});

const amountError = computed(() => {
  const max = getMaxDecimals(draft.value.currency, draft.value.category);
  const clamped = clampDecimals(draft.value.amount, max);

  if (!draft.value.amount) return "";
  if ((normalizeAmountInput(draft.value.amount).match(/\./g) || []).length > 1) return "Importe inválido";
  if (Number.isNaN(Number(normalizeAmountInput(clamped)))) return "Importe inválido";
  return "";
});


function getMaxDecimals(currency: string, category?: string) {
  // si quieres overrides por categoría, aquí:
  // if (category === "investments") return 6;
  return decimalsByCurrency[currency] ?? 2;
}


function startEdit(item: Item) {
  editingId.value = item.id;

  const max = getMaxDecimals(item.currency, item.category);
  const prettyAmount = trimTrailingZeros(clampDecimals(item.amount, max));

  draft.value = {
    name: item.name,
    category: item.category,
    amount: prettyAmount, // <-- aquí está la clave
    currency: item.currency,
    notes: item.notes,
    is_active: item.is_active,
    ownership_id: item.ownership_ref ?? null,
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

function normalizeAmountInput(raw: unknown) {
  return String(raw ?? "")
    .trim()
    .replace(/\s/g, "")
    .replace(/,/g, ".");
}

function clampDecimals(amount: string, maxDecimals: number) {
  const s = normalizeAmountInput(amount);
  if (!s) return "";
  if ((s.match(/\./g) || []).length > 1) return s; // ya lo validaremos aparte

  const [i, d = ""] = s.split(".");
  return d ? `${i}.${d.slice(0, maxDecimals)}` : i;
}

function trimTrailingZeros(amount: string) {
  // "123.4500" -> "123.45", "10.0000" -> "10"
  if (!amount.includes(".")) return amount;
  return amount.replace(/\.?0+$/, "");
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

  if (!isValidAmountString(clamped)) return; // aquí luego metemos error inline

  const payload = {
    ...draft.value,
    amount: clamped,
  };

  await props.onUpdate(id, payload);
  cancelEdit();
}


</script>

<template>
  <div class="card">
    <h2 class="h2">{{ title }}</h2>

    <ul v-if="items.length" class="list">
      <li v-for="it in items" :key="it.id">
        <div v-if="editingId !== it.id" class="row">
          <span>
            {{ it.name }} — {{ formatAmount(it.amount, { currency: it.currency }) }} {{ it.currency }}

            <span class="badge">{{ it.category }}</span>
            <span v-if="!it.is_active" class="badge">archivado</span>
            <span v-if="it.ownership_ref" class="badge">own #{{ it.ownership_ref }}</span>
          </span>

          <div class="actions">
            <button @click="startEdit(it)" class="btn">Editar</button>
            <button @click="onArchive(it.id)" class="btn">Archivar</button>
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

          <!-- <input v-model="draft.amount" type="number" step="0.01" class="input" /> -->
          <input v-model="draft.amount" inputmode="decimal" class="input" />



          <!-- Ownership -->

          <select v-model="draft.ownership_id" class="select">
            <option v-for="o in ownershipOptions" :key="String(o.value)" :value="o.value">
              {{ o.label }}
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
            <button @click="saveEdit(it.id)" class="btn btn-primary" :disabled="!!amountError"> Guardar </button>
            <button @click="cancelEdit" class="btn">Cancelar</button>
          </div>
        </div>
      </li>
    </ul>

    <div v-else class="subtle">No hay elementos todavía.</div>
  </div>
</template>
