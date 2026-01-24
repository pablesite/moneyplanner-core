<script setup lang="ts">
import { reactive } from "vue";

type Props = {
  title: string;
  categories: { value: string; label: string }[];
  onSubmit: (payload: any) => Promise<void>;
};

const props = defineProps<Props>();

const form = reactive({
  name: "",
  category: "",
  amount: "",
  notes: "",
  currency: "EUR",
  tracking_mode: "manual",
  is_active: true,
});

async function submit() {
  if (!form.name || !form.category || !form.amount) return;

  await props.onSubmit({
    name: form.name,
    category: form.category,
    amount: form.amount,
    notes: form.notes,
    currency: form.currency,
    tracking_mode: form.tracking_mode,
    is_active: form.is_active,
  });

  form.name = "";
  form.category = "";
  form.amount = "";
  form.notes = "";
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

      <input v-model="form.amount" type="number" step="0.01" placeholder="Importe" class="input" />

      <textarea v-model="form.notes" placeholder="Notas" rows="2" class="textarea"></textarea>

      <button @click="submit" class="btn btn-primary">
        Crear
      </button>
    </div>
  </div>
</template>
