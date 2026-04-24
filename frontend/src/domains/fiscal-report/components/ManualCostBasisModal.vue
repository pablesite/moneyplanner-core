<script setup lang="ts">
import { reactive, watch } from 'vue';
import BaseModal from '@/domains/ui/components/BaseModal.vue';
import type { ManualCostBasisInput, ManualCostBasisRow } from '@/domains/fiscal-report/api';

type OwnershipOption = { value: number; label: string };

const props = defineProps<{
  open: boolean;
  asset: string;
  ownershipOptions: OwnershipOption[];
  rows: ManualCostBasisRow[];
  creating: boolean;
  deletingById: Record<number, boolean>;
}>();

const emit = defineEmits<{
  close: [];
  submit: [payload: ManualCostBasisInput];
  remove: [rowId: number, asset: string];
}>();

const form = reactive({
  ownership_id: undefined as number | undefined,
  quantity: '',
  acquired_at: '',
  cost_eur: '',
  exchange_origin: 'manual',
  notes: '',
});

watch(
  () => props.open,
  (open) => {
    if (!open) return;
    form.ownership_id = props.ownershipOptions[0]?.value;
    form.quantity = '';
    form.acquired_at = '';
    form.cost_eur = '';
    form.exchange_origin = 'manual';
    form.notes = '';
  },
);

function onSubmit() {
  emit('submit', {
    ownership_id: form.ownership_id,
    asset: props.asset,
    quantity: form.quantity,
    acquired_at: form.acquired_at,
    cost_eur: form.cost_eur,
    exchange_origin: form.exchange_origin || 'manual',
    notes: form.notes || undefined,
  });
}
</script>

<template>
  <BaseModal
    :open="props.open"
    title="Asignar coste de adquisición manual"
    close-on-backdrop
    @close="emit('close')"
  >
    <div class="fiscal-modal-grid">
      <label class="fiscal-field">
        <span>Asset</span>
        <input class="input" :value="props.asset" type="text" disabled />
      </label>
      <label class="fiscal-field">
        <span>Ownership</span>
        <select v-model.number="form.ownership_id" class="select">
          <option
            v-for="option in props.ownershipOptions"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>
      </label>
      <label class="fiscal-field">
        <span>Cantidad</span>
        <input v-model="form.quantity" class="input" type="number" min="0" step="0.00000001" />
      </label>
      <label class="fiscal-field">
        <span>Fecha adquisición</span>
        <input v-model="form.acquired_at" class="input" type="datetime-local" />
      </label>
      <label class="fiscal-field">
        <span>Coste total EUR</span>
        <input v-model="form.cost_eur" class="input" type="number" min="0" step="0.01" />
      </label>
      <label class="fiscal-field">
        <span>Origen</span>
        <input v-model="form.exchange_origin" class="input" type="text" />
      </label>
      <label class="fiscal-field fiscal-field-full">
        <span>Notas</span>
        <textarea v-model="form.notes" class="textarea" rows="2" />
      </label>
      <div class="fiscal-field-actions fiscal-field-full">
        <button class="btn btn-primary" type="button" :disabled="props.creating" @click="onSubmit">
          {{ props.creating ? 'Guardando...' : 'Guardar coste manual' }}
        </button>
      </div>
    </div>

    <section class="ui-section-card fiscal-section">
      <header class="ui-section-head">
        <div class="ui-section-copy">
          <h3 class="ui-section-title">Costes manuales existentes</h3>
        </div>
      </header>
      <div v-if="!props.rows.length" class="ui-state-block ui-state-empty">
        No hay registros para {{ props.asset }}.
      </div>
      <table v-else class="fiscal-table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Cantidad</th>
            <th>Coste EUR</th>
            <th>Origen</th>
            <th>Acción</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in props.rows" :key="row.id">
            <td>{{ row.acquired_at }}</td>
            <td>{{ row.quantity }}</td>
            <td>{{ row.cost_eur }}</td>
            <td>{{ row.exchange_origin }}</td>
            <td>
              <button
                class="btn btn-ghost btn-sm"
                type="button"
                :disabled="Boolean(props.deletingById[row.id])"
                @click="emit('remove', row.id, props.asset)"
              >
                {{ props.deletingById[row.id] ? 'Eliminando...' : 'Eliminar' }}
              </button>
            </td>
          </tr>
        </tbody>
      </table>
    </section>
  </BaseModal>
</template>
