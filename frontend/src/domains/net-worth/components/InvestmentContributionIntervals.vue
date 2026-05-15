<script setup lang="ts">
import { currencies, type ContributionIntervalDraft } from './itemFormUtils';

defineProps<{
  intervals: ContributionIntervalDraft[];
}>();

const emit = defineEmits<{
  add: [];
  remove: [key: string];
}>();
</script>

<template>
  <div class="ui-item-form-section ui-item-form-field-span-2">
    <div class="ui-item-form-section-head">
      <div class="ui-item-form-section-title">Aportaciones periódicas</div>
      <button type="button" class="btn ui-item-form-mini-btn" @click="emit('add')">
        + Añadir intervalo
      </button>
    </div>
    <div v-if="!intervals.length" class="ui-form-help">
      Sin intervalos = activo sin aportaciones periódicas previstas.
    </div>
    <div
      v-for="interval in intervals"
      :key="interval._key"
      class="ui-item-form-inline-grid ui-item-form-inline-grid-4 ui-surface-muted mt-2 p-2"
    >
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Desde</span>
        <input v-model="interval.start_date" type="date" class="input ui-data-field" />
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Hasta (opcional)</span>
        <input v-model="interval.end_date" type="date" class="input ui-data-field" />
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Cuota</span>
        <input v-model="interval.amount" inputmode="decimal" class="input ui-data-field" />
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Moneda</span>
        <select v-model="interval.currency" class="select ui-data-field">
          <option v-for="c in currencies" :key="`${interval._key}-${c.value}`" :value="c.value">
            {{ c.label }}
          </option>
        </select>
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Frecuencia</span>
        <select v-model="interval.frequency" class="select ui-data-field">
          <option value="monthly">Mensual</option>
          <option value="weekly">Semanal</option>
        </select>
      </label>
      <div class="ui-item-form-field">
        <button
          type="button"
          class="btn ui-item-form-mini-btn"
          @click="emit('remove', interval._key)"
        >
          Eliminar
        </button>
      </div>
    </div>
  </div>
</template>
