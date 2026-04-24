<script setup lang="ts">
import { computed, ref } from 'vue';
import { formatAmount, formatMoney } from '@/lib/format';
import type {
  BotResultDetail,
  BotResultDrilldownRow,
  FiscalBotResultRow,
} from '@/domains/fiscal-report/api';

const props = withDefaults(
  defineProps<{
    rows: BotResultDrilldownRow[];
    reportRows: FiscalBotResultRow[];
    detailById: Record<number, BotResultDetail | undefined>;
    tolerance?: number;
  }>(),
  {
    tolerance: 0.01,
  },
);

const emit = defineEmits<{
  openDetail: [botResultId: number];
}>();

const expandedById = ref<Record<number, boolean>>({});

const reportByLabel = computed(() => {
  const map = new Map<string, number>();
  for (const row of props.reportRows) {
    map.set(row.bot_label, Number(row.ganancia_neta_eur ?? 0));
  }
  return map;
});

function toggleRow(id: number) {
  const next = !expandedById.value[id];
  expandedById.value = {
    ...expandedById.value,
    [id]: next,
  };
  if (next) emit('openDetail', id);
}

function toDateLabel(value: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('es-ES');
}

function toFillValueEur(fill: BotResultDetail['fills']['results'][number]) {
  const qty = Number(fill.quantity ?? 0);
  const unitEur = Number(fill.price_eur ?? 0);
  const feeEur = Number(fill.fee_eur ?? 0);
  const gross = qty * unitEur;
  return fill.side === 'buy' ? -gross - feeEur : gross - feeEur;
}

function toFillNetEur(rowId: number) {
  const detail = props.detailById[rowId];
  if (!detail) return 0;
  return detail.fills.results.reduce((acc, fill) => acc + toFillValueEur(fill), 0);
}

function toDiffClass(diff: number) {
  return Math.abs(diff) > props.tolerance ? 'fiscal-text-warning' : 'fiscal-text-ok';
}
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h3 class="ui-section-title">Conciliación bots con fills</h3>
        <p class="ui-section-subtitle">
          Detalle expandible por bot y comparación con neto fiscal en EUR.
        </p>
      </div>
    </header>

    <div v-if="!props.rows.length" class="ui-state-block ui-state-empty">
      No hay bots sincronizados para este ejercicio.
    </div>

    <table v-else class="fiscal-table">
      <thead>
        <tr>
          <th>Bot</th>
          <th>Tipo</th>
          <th>Fills</th>
          <th>Neto reporte EUR</th>
          <th>Neto fills EUR</th>
          <th>Diff</th>
          <th>Acción</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="row in props.rows" :key="row.id">
          <tr>
            <td>{{ row.label }}</td>
            <td>{{ row.bot_type }}</td>
            <td>{{ row.fill_count }}</td>
            <td>{{ formatMoney(reportByLabel.get(row.label) ?? 0, 'EUR') }}</td>
            <td>{{ formatMoney(toFillNetEur(row.id), 'EUR') }}</td>
            <td
              :class="toDiffClass(toFillNetEur(row.id) - Number(reportByLabel.get(row.label) ?? 0))"
            >
              {{
                formatMoney(toFillNetEur(row.id) - Number(reportByLabel.get(row.label) ?? 0), 'EUR')
              }}
            </td>
            <td>
              <button class="btn btn-sm" type="button" @click="toggleRow(row.id)">
                {{ expandedById[row.id] ? 'Ocultar fills' : 'Ver fills' }}
              </button>
            </td>
          </tr>
          <tr v-if="expandedById[row.id]" class="fiscal-lot-row">
            <td colspan="7">
              <table class="fiscal-lot-table">
                <thead>
                  <tr>
                    <th>Fecha</th>
                    <th>Símbolo</th>
                    <th>Side</th>
                    <th>Cantidad</th>
                    <th>Precio EUR</th>
                    <th>Fee EUR</th>
                    <th>Impacto EUR</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="fill in props.detailById[row.id]?.fills.results ?? []" :key="fill.id">
                    <td>{{ toDateLabel(fill.timestamp) }}</td>
                    <td>{{ fill.symbol }}</td>
                    <td>{{ fill.side.toUpperCase() }}</td>
                    <td>{{ formatAmount(fill.quantity, { maxDecimals: 8 }) }}</td>
                    <td>{{ fill.price_eur ? formatMoney(fill.price_eur, 'EUR') : '-' }}</td>
                    <td>{{ fill.fee_eur ? formatMoney(fill.fee_eur, 'EUR') : '-' }}</td>
                    <td>{{ formatMoney(toFillValueEur(fill), 'EUR') }}</td>
                  </tr>
                </tbody>
              </table>
            </td>
          </tr>
        </template>
      </tbody>
    </table>
  </section>
</template>
