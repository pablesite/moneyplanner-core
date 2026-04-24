<script setup lang="ts">
import { computed, reactive } from 'vue';
import type { BrokerName } from '@/domains/fiscal-report/api';

type OwnershipOption = { value: number; label: string };

const props = defineProps<{
  ownershipOptions: OwnershipOption[];
  creating: boolean;
}>();

const emit = defineEmits<{
  submit: [
    payload: {
      broker: BrokerName;
      label: string;
      ownership_id: number;
      api_key: string;
      api_secret: string;
    },
  ];
}>();

const form = reactive({
  broker: 'pionex' as BrokerName,
  label: '',
  ownership_id: 0,
  api_key: '',
  api_secret: '',
});

const canSubmit = computed(
  () =>
    form.label.trim().length > 0 &&
    form.ownership_id > 0 &&
    form.api_key.trim().length > 0 &&
    form.api_secret.trim().length > 0,
);

function submitForm() {
  if (!canSubmit.value) return;
  emit('submit', {
    broker: form.broker,
    label: form.label.trim(),
    ownership_id: form.ownership_id,
    api_key: form.api_key.trim(),
    api_secret: form.api_secret.trim(),
  });
  form.label = '';
  form.api_key = '';
  form.api_secret = '';
}
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h2 class="ui-section-title">Nueva credencial</h2>
        <p class="ui-section-subtitle">Registra una API key para habilitar sync automático.</p>
      </div>
    </header>

    <form class="form-grid fiscal-form-grid" @submit.prevent="submitForm">
      <label class="fiscal-field">
        <span>Broker</span>
        <select v-model="form.broker" class="select">
          <option value="pionex">Pionex</option>
          <option value="binance">Binance</option>
        </select>
      </label>

      <label class="fiscal-field">
        <span>Ownership</span>
        <select v-model.number="form.ownership_id" class="select">
          <option :value="0">Selecciona ownership</option>
          <option
            v-for="ownershipOption in props.ownershipOptions"
            :key="ownershipOption.value"
            :value="ownershipOption.value"
          >
            {{ ownershipOption.label }}
          </option>
        </select>
      </label>

      <label class="fiscal-field">
        <span>Label</span>
        <input v-model="form.label" class="input" type="text" placeholder="Cuenta principal" />
      </label>

      <label class="fiscal-field">
        <span>API key</span>
        <input v-model="form.api_key" class="input" type="text" autocomplete="off" />
      </label>

      <label class="fiscal-field">
        <span>API secret</span>
        <input
          v-model="form.api_secret"
          class="input"
          type="password"
          autocomplete="new-password"
        />
      </label>

      <div class="fiscal-field fiscal-field-actions">
        <button class="btn btn-primary" type="submit" :disabled="props.creating || !canSubmit">
          {{ props.creating ? 'Guardando...' : 'Guardar credencial' }}
        </button>
      </div>
    </form>
  </section>
</template>
