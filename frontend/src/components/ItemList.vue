<script setup lang="ts">
import { ref } from "vue";

type Item = {
  id: number;
  name: string;
  category: string;
  amount: string;
  currency: string;
  notes: string;
  is_active: boolean;
};

type Props = {
  title: string;
  items: Item[];
  categories: { value: string; label: string }[];
  onUpdate: (id: number, payload: Partial<Item>) => Promise<void>;
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

function startEdit(item: Item) {
  editingId.value = item.id;
  draft.value = {
    name: item.name,
    category: item.category,
    amount: item.amount,
    currency: item.currency,
    notes: item.notes,
    is_active: item.is_active,
  };
}

function cancelEdit() {
  editingId.value = null;
  draft.value = {};
}

async function saveEdit(id: number) {
  await props.onUpdate(id, draft.value);
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

          <input v-model="draft.amount" type="number" step="0.01" class="input" />          

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
