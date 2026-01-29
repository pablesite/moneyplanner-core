<script setup lang="ts">
import { computed, ref } from "vue";

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


function startEdit(item: Item) {
  editingId.value = item.id;
  draft.value = {
    name: item.name,
    category: item.category,
    amount: item.amount,
    currency: item.currency,
    notes: item.notes,
    is_active: item.is_active,
    ownership_id: item.ownership_ref ?? null,
  };
}

function cancelEdit() {
  editingId.value = null;
  draft.value = {};
}

async function saveEdit(id: number) {
    const payload = {
    ...draft.value,
    amount: String(draft.value.amount).replace(",", "."),
  };

  // await props.onUpdate(id, draft.value);
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
            {{ it.name }} — {{ it.amount }} {{ it.currency }}
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

          <div class="actions">
            <button @click="saveEdit(it.id)" class="btn btn-primary">Guardar</button>
            <button @click="cancelEdit" class="btn">Cancelar</button>
          </div>
        </div>
      </li>
    </ul>

    <div v-else class="subtle">No hay elementos todavía.</div>
  </div>
</template>
