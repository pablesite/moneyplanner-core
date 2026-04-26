<script setup lang="ts">
import { computed, reactive, watch } from 'vue';
import type {
  BrokerCredential,
  BrokerCsvFileType,
  BrokerName,
  CsvTaxIdGroup,
  BrokerTradeDrilldownRow,
} from '@/domains/fiscal-report/api';

const props = defineProps<{
  credentials: BrokerCredential[];
  importing: boolean;
  loadingTrades: boolean;
  trades: BrokerTradeDrilldownRow[];
  tradesCount: number;
  results: {
    broker: BrokerName;
    credential_id: number | null;
    file_type: BrokerCsvFileType;
    created: number;
    updated: number;
    skipped: number;
  }[];
}>();

const emit = defineEmits<{
  submit: [
    payload: {
      broker: BrokerName;
      credential_id?: number;
      file_type: BrokerCsvFileType;
      files: File[];
    },
  ];
  preview: [
    payload: {
      broker: BrokerName;
      credential_id?: number;
      file_type: BrokerCsvFileType;
    },
  ];
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
  credential_id: 0,
  file_type: 'pionex_trading' as BrokerCsvFileType,
  files: [] as File[],
});

const availableTypes = computed(() => fileTypeByBroker[state.broker]);
const availableCredentials = computed(() =>
  props.credentials.filter((credential) => credential.broker === state.broker),
);
const tradeGroups = computed<CsvTaxIdGroup[]>(() => {
  const grouped = new Map<string, CsvTaxIdGroup>();
  for (const row of props.trades) {
    const taxId = row.tax_id.trim();
    if (!taxId) continue;
    const current = grouped.get(taxId);
    if (!current) {
      grouped.set(taxId, {
        tax_id: taxId,
        count: 1,
        symbols: row.symbol ? [row.symbol] : [],
        first_timestamp: row.timestamp,
        last_timestamp: row.timestamp,
      });
      continue;
    }
    current.count += 1;
    if (row.symbol && !current.symbols.includes(row.symbol)) {
      current.symbols.push(row.symbol);
    }
    if (row.timestamp < current.first_timestamp) {
      current.first_timestamp = row.timestamp;
    }
    if (row.timestamp > current.last_timestamp) {
      current.last_timestamp = row.timestamp;
    }
  }
  return Array.from(grouped.values())
    .sort((left, right) => right.count - left.count)
    .slice(0, 8);
});

const canSubmit = computed(() => state.files.length > 0 && state.file_type.length > 0);

function onFilesSelected(event: Event) {
  const input = event.target as HTMLInputElement;
  state.files = Array.from(input.files ?? []);
}

function onBrokerChanged() {
  const firstType = availableTypes.value[0];
  state.file_type = firstType ? firstType.value : state.file_type;
  state.credential_id = availableCredentials.value[0]?.id ?? 0;
}

function submitFiles() {
  if (!canSubmit.value) return;
  emit('submit', {
    broker: state.broker,
    credential_id: state.credential_id > 0 ? state.credential_id : undefined,
    file_type: state.file_type,
    files: state.files,
  });
}

function toDateLabel(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('es-ES');
}

watch(
  () => [state.broker, state.credential_id, state.file_type],
  () => {
    emit('preview', {
      broker: state.broker,
      credential_id: state.credential_id > 0 ? state.credential_id : undefined,
      file_type: state.file_type,
    });
  },
  { immediate: true },
);

watch(
  availableCredentials,
  (credentials) => {
    if (state.credential_id === 0 && credentials.length) {
      state.credential_id = credentials[0]?.id ?? 0;
    }
  },
  { immediate: true },
);
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
        <span>Credencial destino</span>
        <select v-model.number="state.credential_id" class="select">
          <option :value="0">Sin asociar</option>
          <option
            v-for="credential in availableCredentials"
            :key="credential.id"
            :value="credential.id"
          >
            {{ credential.label }}
          </option>
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
          {{ result.broker }} · credencial {{ result.credential_id ?? 'sin asociar' }} ·
          {{ result.file_type }} · creados {{ result.created }} · actualizados
          {{ result.updated }} · omitidos {{ result.skipped }}
        </li>
      </ul>
    </div>

    <div v-if="props.loadingTrades" class="ui-state-block ui-state-loading">
      Cargando ultimos trades CSV importados...
    </div>

    <div v-else-if="props.trades.length" class="fiscal-import-results">
      <h3 class="h3">Ultimos trades CSV visibles en la app</h3>
      <p class="ui-section-subtitle">
        Total ligados a la credencial y ejercicio actual: {{ props.tradesCount }}. `tax_id` ayuda a
        detectar grupos repetidos tipicos de bot, aunque Pionex no publica una clave fiable para
        enlazar cada `tax_id` con un `bot_id` concreto.
      </p>

      <table v-if="tradeGroups.length" class="fiscal-table">
        <thead>
          <tr>
            <th>Tax ID</th>
            <th>Trades</th>
            <th>Simbolos</th>
            <th>Primero</th>
            <th>Ultimo</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="group in tradeGroups" :key="group.tax_id">
            <td>{{ group.tax_id }}</td>
            <td>{{ group.count }}</td>
            <td>{{ group.symbols.join(', ') || '-' }}</td>
            <td>{{ toDateLabel(group.first_timestamp) }}</td>
            <td>{{ toDateLabel(group.last_timestamp) }}</td>
          </tr>
        </tbody>
      </table>

      <table class="fiscal-table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Simbolo</th>
            <th>Side</th>
            <th>Cantidad</th>
            <th>Precio</th>
            <th>Tax ID</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in props.trades" :key="row.id">
            <td>{{ toDateLabel(row.timestamp) }}</td>
            <td>{{ row.symbol }}</td>
            <td>{{ row.side.toUpperCase() }}</td>
            <td>{{ row.quantity }}</td>
            <td>{{ row.price }}</td>
            <td>{{ row.tax_id || '-' }}</td>
          </tr>
        </tbody>
      </table>
    </div>
  </section>
</template>
