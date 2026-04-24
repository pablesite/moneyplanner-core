<script setup lang="ts">
import { computed, reactive } from 'vue';
import type { BrokerCsvFileType, BrokerName } from '@/domains/fiscal-report/api';

const props = defineProps<{
  importing: boolean;
  results: {
    broker: BrokerName;
    file_type: BrokerCsvFileType;
    created: number;
    updated: number;
    skipped: number;
  }[];
}>();

const emit = defineEmits<{
  submit: [payload: { broker: BrokerName; file_type: BrokerCsvFileType; files: File[] }];
}>();

const fileTypeByBroker: Record<BrokerName, { value: BrokerCsvFileType; label: string }[]> = {
  pionex: [
    { value: 'pionex_trading', label: 'trading' },
    { value: 'pionex_futures', label: 'position_futures' },
    { value: 'pionex_staking', label: 'staking' },
    { value: 'pionex_others', label: 'others' },
    { value: 'pionex_dust', label: 'dust' },
  ],
  binance: [
    { value: 'binance_transactions', label: 'transacciones' },
    { value: 'binance_convert', label: 'convert' },
    { value: 'binance_recurring', label: 'recurring' },
  ],
};

const state = reactive({
  broker: 'pionex' as BrokerName,
  file_type: 'pionex_trading' as BrokerCsvFileType,
  files: [] as File[],
});

const availableTypes = computed(() => fileTypeByBroker[state.broker]);

const canSubmit = computed(() => state.files.length > 0 && state.file_type.length > 0);

function onFilesSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  state.files = Array.from(input.files ?? []);
}

function onBrokerChanged() {
  const firstType = availableTypes.value[0];
  state.file_type = firstType ? firstType.value : state.file_type;
}

function submitFiles() {
  if (!canSubmit.value) return;
  emit('submit', {
    broker: state.broker,
    file_type: state.file_type,
    files: state.files,
  });
}
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h2 class="ui-section-title">Importar CSV</h2>
        <p class="ui-section-subtitle">
          Sube uno o varios ficheros y aplica fallback CSV al dataset fiscal.
        </p>
      </div>
    </header>

    <form class="form-grid fiscal-form-grid" @submit.prevent="submitFiles">
      <label class="fiscal-field">
        <span>Broker</span>
        <select v-model="state.broker" class="select" @change="onBrokerChanged">
          <option value="pionex">Pionex</option>
          <option value="binance">Binance</option>
        </select>
      </label>

      <label class="fiscal-field">
        <span>Tipo de fichero</span>
        <select v-model="state.file_type" class="select">
          <option v-for="item in availableTypes" :key="item.value" :value="item.value">
            {{ item.label }}
          </option>
        </select>
      </label>

      <label class="fiscal-field">
        <span>Archivos CSV</span>
        <input
          class="input"
          type="file"
          multiple
          accept=".csv,text/csv"
          @change="onFilesSelected"
        />
      </label>

      <div class="fiscal-field fiscal-field-actions">
        <button class="btn btn-primary" type="submit" :disabled="props.importing || !canSubmit">
          {{ props.importing ? 'Importando...' : 'Importar CSV' }}
        </button>
      </div>
    </form>

    <div v-if="props.results.length" class="fiscal-import-results">
      <h3 class="h3">Ultimos resultados</h3>
      <ul class="list-plain fiscal-import-results-list">
        <li v-for="(result, index) in props.results" :key="index">
          {{ result.broker }} · {{ result.file_type }} · creados {{ result.created }} · actualizados
          {{ result.updated }} · omitidos {{ result.skipped }}
        </li>
      </ul>
    </div>
  </section>
</template>
