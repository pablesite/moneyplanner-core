<script setup lang="ts">
import { computed, reactive } from "vue";

type Ownership = {
  id: number;
  kind: "individual" | "shared";
  member: { id: number; name: string; role: "adult" | "child" } | null;
  splits: { member: { id: number; name: string; role: "adult" | "child" }; percent: string }[];
  notes: string;
};

type Props = {
  title: string;
  categories: { value: string; label: string }[];
  ownerships: Ownership[];
  onSubmit: (payload: any) => Promise<void>;
};

const props = defineProps<Props>();

const currencies = [
  { value: "EUR", label: "EUR" },
  { value: "USD", label: "USD" },
  { value: "BTC", label: "BTC" },
  { value: "ETH", label: "ETH" },
];

const ownershipLabel = (o: Ownership) => {
  if (o.kind === "individual") {
    return o.member ? `Individual · ${o.member.name}` : "Individual";
  }
  const parts = (o.splits || []).map((s) => `${s.member.name} ${s.percent}%`);
  return `Compartido · ${parts.join(" · ") || "sin splits"}`;
};

const ownershipOptions = computed(() => {
  return [
    { value: null, label: "— Sin asignar —" },
    ...(props.ownerships || []).map((o) => ({ value: o.id, label: ownershipLabel(o) })),
  ];
});

const form = reactive({
  name: "",
  category: "",
  amount: "",
  notes: "",
  currency: "EUR",
  tracking_mode: "manual",
  is_active: true,
  ownership_id: null as number | null,
});

async function submit() {
  if (!form.name || !form.category || !form.amount) return;

  const normalizedAmount = String(form.amount).replace(",", ".");

  await props.onSubmit({
    name: form.name,
    category: form.category,
    // amount: form.amount,
    amount: normalizedAmount,
    notes: form.notes,
    currency: form.currency,
    tracking_mode: form.tracking_mode,
    is_active: form.is_active,
    ownership_id: form.ownership_id, // <-- clave
  });

  form.name = "";
  form.category = "";
  form.amount = "";
  form.notes = "";
  form.ownership_id = null;
}
</script>

<template>
  <div class="card" style="margin-bottom: 12px;">
    <h3 class="h3">{{ title }}</h3>

    <div class="form-grid">
      <input v-model="form.name" placeholder="Nombre" class="input" />

      <select v-model="form.category" class="select">
        <option value="" disabled>Selecciona categoría</option>
        <option v-for="c in categories" :key="c.value" :value="c.value">
          {{ c.label }}
        </option>
      </select>

      <select v-model="form.currency" class="select">
        <option v-for="c in currencies" :key="c.value" :value="c.value">
          {{ c.label }}
        </option>
      </select>

      <!-- <input v-model="form.amount" type="number" step="0.01" placeholder="Importe" class="input" /> -->
      <input v-model="form.amount" inputmode="decimal" placeholder="Importe" class="input" />
      

      <!-- Ownership -->
      <select v-model="form.ownership_id" class="select">
        <option v-for="o in ownershipOptions" :key="String(o.value)" :value="o.value">
          {{ o.label }}
        </option>
      </select>

      <textarea v-model="form.notes" placeholder="Notas" rows="2" class="textarea"></textarea>

      <button @click="submit" class="btn btn-primary">
        Crear
      </button>
    </div>
  </div>
</template>
