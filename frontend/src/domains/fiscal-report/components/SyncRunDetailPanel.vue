<script setup lang="ts">
import { computed, ref } from 'vue';
import { formatAmount, formatMoney } from '@/lib/format';
import type {
  BotResultDrilldownRow,
  BrokerTradeDrilldownRow,
  IncomeEventDrilldownRow,
  SyncRunSummary,
} from '@/domains/fiscal-report/api';

type DrilldownFilters = {
  source: string;
  symbol: string;
  side: '' | 'buy' | 'sell';
};

const props = defineProps<{
  activeRun: SyncRunSummary | null;
  loading: boolean;
  filters: DrilldownFilters;
  trades: BrokerTradeDrilldownRow[];
  tradesCount: number;
  incomeEvents: IncomeEventDrilldownRow[];
  incomeEventsCount: number;
  botResults: BotResultDrilldownRow[];
  botResultsCount: number;
}>();

const emit = defineEmits<{
  updateFilters: [filters: Partial<DrilldownFilters>];
  refresh: [];
}>();

const activeTab = ref<'trades' | 'income' | 'bots'>('trades');

const hasRun = computed(() => Boolean(props.activeRun));

function toDateLabel(value: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('es-ES');
}

function onSourceInput(event: Event) {
  emit('updateFilters', { source: (event.target as HTMLInputElement).value.trim() });
}

function onSymbolInput(event: Event) {
  emit('updateFilters', { symbol: (event.target as HTMLInputElement).value.trim().toUpperCase() });
}

function onSideChange(event: Event) {
  emit('updateFilters', {
    side: (event.target as HTMLSelectElement).value as DrilldownFilters['side'],
  });
}
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h2 class="ui-section-title">Detalle de sync run</h2>
        <p class="ui-section-subtitle">
          Trades, ingresos y bots tocados por la ejecución seleccionada.
        </p>
      </div>
      <div v-if="props.activeRun" class="ui-section-actions">
        <span class="badge">Run #{{ props.activeRun.id }}</span>
        <span class="badge">{{ toDateLabel(props.activeRun.finished_at) }}</span>
      </div>
    </header>

    <div v-if="!hasRun" class="ui-state-block ui-state-empty">
      Selecciona un run del historial para abrir el drill-down.
    </div>
    <template v-else>
      <div class="ui-view-tabs">
        <button
          type="button"
          class="ui-view-tab"
          :class="{ 'ui-view-tab-active': activeTab === 'trades' }"
          @click="activeTab = 'trades'"
        >
          Trades ({{ props.tradesCount }})
        </button>
        <button
          type="button"
          class="ui-view-tab"
          :class="{ 'ui-view-tab-active': activeTab === 'income' }"
          @click="activeTab = 'income'"
        >
          Ingresos ({{ props.incomeEventsCount }})
        </button>
        <button
          type="button"
          class="ui-view-tab"
          :class="{ 'ui-view-tab-active': activeTab === 'bots' }"
          @click="activeTab = 'bots'"
        >
          Bots ({{ props.botResultsCount }})
        </button>
      </div>

      <div class="ui-action-bar">
        <input
          class="input"
          :value="props.filters.source"
          placeholder="Filtrar source"
          @input="onSourceInput"
        />
        <input
          class="input"
          :value="props.filters.symbol"
          placeholder="Filtrar símbolo"
          @input="onSymbolInput"
        />
        <select class="select" :value="props.filters.side" @change="onSideChange">
          <option value="">Todos los lados</option>
          <option value="buy">BUY</option>
          <option value="sell">SELL</option>
        </select>
        <button class="btn btn-sm" type="button" @click="emit('refresh')">Aplicar</button>
      </div>

      <div v-if="props.loading" class="ui-state-block ui-state-loading">Cargando detalle...</div>

      <table v-else-if="activeTab === 'trades'" class="fiscal-table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Source</th>
            <th>Símbolo</th>
            <th>Side</th>
            <th>Cantidad</th>
            <th>Precio EUR</th>
            <th>Fee EUR</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in props.trades" :key="row.id">
            <td>{{ toDateLabel(row.timestamp) }}</td>
            <td>{{ row.source }}</td>
            <td>{{ row.symbol }}</td>
            <td>{{ row.side.toUpperCase() }}</td>
            <td>{{ formatAmount(row.quantity, { maxDecimals: 8 }) }}</td>
            <td>{{ row.price_eur ? formatMoney(row.price_eur, 'EUR') : '-' }}</td>
            <td>{{ row.fee_eur ? formatMoney(row.fee_eur, 'EUR') : '-' }}</td>
          </tr>
        </tbody>
      </table>

      <table v-else-if="activeTab === 'income'" class="fiscal-table">
        <thead>
          <tr>
            <th>Fecha</th>
            <th>Source</th>
            <th>Tipo</th>
            <th>Asset</th>
            <th>Importe</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in props.incomeEvents" :key="row.id">
            <td>{{ toDateLabel(row.timestamp) }}</td>
            <td>{{ row.source }}</td>
            <td>{{ row.income_type }}</td>
            <td>{{ row.asset }}</td>
            <td>{{ formatAmount(row.amount, { maxDecimals: 8 }) }}</td>
          </tr>
        </tbody>
      </table>

      <table v-else class="fiscal-table">
        <thead>
          <tr>
            <th>Bot</th>
            <th>Tipo</th>
            <th>Periodo</th>
            <th>Realized</th>
            <th>Fills</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in props.botResults" :key="row.id">
            <td>{{ row.label }}</td>
            <td>{{ row.bot_type }}</td>
            <td>{{ toDateLabel(row.period_start) }} → {{ toDateLabel(row.period_end) }}</td>
            <td>{{ row.realized_profit }}</td>
            <td>{{ row.fill_count }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>
