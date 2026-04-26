<script setup lang="ts">
import { computed, ref } from 'vue';
import { formatAmount, formatMoney } from '@/lib/format';
import type {
  BotResultDrilldownRow,
  BrokerSyncGap,
  BrokerTradeDrilldownRow,
  IncomeEventDrilldownRow,
  SyncRunSummary,
} from '@/domains/fiscal-report/api';

type DrilldownFilters = {
  source: string;
  symbol: string;
  tax_id: string;
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
const botFillGapRows = computed(() => {
  const gaps = props.activeRun?.gaps ?? [];
  return gaps.filter(
    (gap) => gap.reason === 'public_api_no_fill_history' && gap.source.startsWith('bot_fills:'),
  );
});
const otherGapRows = computed(() => {
  const gaps = props.activeRun?.gaps ?? [];
  return gaps.filter(
    (gap) => !(gap.reason === 'public_api_no_fill_history' && gap.source.startsWith('bot_fills:')),
  );
});

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

function onTaxIdInput(event: Event) {
  emit('updateFilters', { tax_id: (event.target as HTMLInputElement).value.trim() });
}

function onSideChange(event: Event) {
  emit('updateFilters', {
    side: (event.target as HTMLSelectElement).value as DrilldownFilters['side'],
  });
}

function formatBotProfit(value: string | null, asset: string) {
  if (!value) return '-';
  return `${formatAmount(value, { maxDecimals: 8 })} ${asset}`;
}

function formatGridProfit(row: BotResultDrilldownRow) {
  if (row.bot_type !== 'spot_grid') return '-';
  return formatBotProfit(row.grid_profit, row.quote_asset);
}

function botIdFromGap(gap: BrokerSyncGap) {
  return gap.source.replace('bot_fills:', '').trim() || 'desconocido';
}
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h2 class="ui-section-title">Detalle de sync run</h2>
        <p class="ui-section-subtitle">
          Trades, ingresos y bots tocados por la ejecucion seleccionada.
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
      <div v-if="botFillGapRows.length" class="ui-state-block ui-state-empty">
        Pionex no ha devuelto fills individuales para algunos bots en este run. Importa
        `trading.csv` como fallback si necesitas recuperar esos movimientos.
      </div>

      <div v-if="botFillGapRows.length" class="ui-state-block ui-state-empty">
        Los trades CSV pueden traer `tax_id`, pero no existe una clave publica fiable para enlazar
        ese `tax_id` con un `bot_id` o `buOrderId` concreto de Pionex.
      </div>

      <table v-if="botFillGapRows.length" class="fiscal-table">
        <thead>
          <tr>
            <th>Bot</th>
            <th>Incidencia</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="gap in botFillGapRows" :key="`${gap.source}-${gap.reason}`">
            <td>{{ botIdFromGap(gap) }}</td>
            <td>La Bot API publica no expone historial de fills por bot.</td>
          </tr>
        </tbody>
      </table>

      <div v-if="otherGapRows.length" class="ui-state-block ui-state-empty">
        Este run tiene {{ otherGapRows.length }} gap<span v-if="otherGapRows.length !== 1">s</span>
        adicional<span v-if="otherGapRows.length !== 1">es</span>. Revisa la conciliacion y el
        historial si necesitas trazabilidad completa.
      </div>

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
          placeholder="Filtrar simbolo"
          @input="onSymbolInput"
        />
        <input
          class="input"
          :value="props.filters.tax_id"
          placeholder="Filtrar tax_id"
          @input="onTaxIdInput"
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
            <th>Simbolo</th>
            <th>Side</th>
            <th>Cantidad</th>
            <th>Precio EUR</th>
            <th>Fee EUR</th>
            <th>Tax ID</th>
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
            <td>{{ row.tax_id || '-' }}</td>
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
            <th>Ganancia rejilla</th>
            <th>Ganancia total</th>
            <th>Fills</th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="row in props.botResults" :key="row.id">
            <td>{{ row.label }}</td>
            <td>{{ row.bot_type }}</td>
            <td>{{ toDateLabel(row.period_start) }} -> {{ toDateLabel(row.period_end) }}</td>
            <td>{{ formatGridProfit(row) }}</td>
            <td>{{ formatBotProfit(row.total_profit_quote, row.quote_asset) }}</td>
            <td>{{ row.fill_count }}</td>
          </tr>
        </tbody>
      </table>
    </template>
  </section>
</template>
