<script setup lang="ts">
import { computed } from 'vue';
import { formatMoney } from '@/lib/format';
import type { FiscalTradeSectionRow } from '@/domains/fiscal-report/api';
import FifoSaleMatchRow from './FifoSaleMatchRow.vue';

const props = defineProps<{
  rows: FiscalTradeSectionRow[];
}>();

const emit = defineEmits<{
  manualCostBasis: [asset: string];
}>();

const totals = computed(() => {
  return props.rows.reduce(
    (acc, row) => {
      acc.adquisicion += row.valor_adquisicion_eur;
      acc.transmision += row.valor_transmision_eur;
      acc.ganancia += row.ganancia_eur;
      acc.perdida += row.perdida_eur;
      return acc;
    },
    { adquisicion: 0, transmision: 0, ganancia: 0, perdida: 0 },
  );
});
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h3 class="ui-section-title">Ganancias/perdidas por transmisiones</h3>
        <p class="ui-section-subtitle">Detalle FIFO por venta y lotes consumidos.</p>
      </div>
    </header>

    <div v-if="!props.rows.length" class="ui-state-block ui-state-empty">
      No hay transmisiones sujetas a FIFO para este año.
    </div>

    <div v-else class="fiscal-sale-groups">
      <section v-for="row in props.rows" :key="row.denominacion" class="fiscal-sale-group">
        <div class="fiscal-sale-group-head">
          <h4>{{ row.denominacion }}</h4>
          <div class="fiscal-sale-group-metrics">
            <span class="badge"
              >Adquisición: {{ formatMoney(row.valor_adquisicion_eur, 'EUR') }}</span
            >
            <span class="badge"
              >Transmisión: {{ formatMoney(row.valor_transmision_eur, 'EUR') }}</span
            >
            <span class="badge">Ganancia: {{ formatMoney(row.ganancia_eur, 'EUR') }}</span>
            <span class="badge">Pérdida: {{ formatMoney(row.perdida_eur, 'EUR') }}</span>
          </div>
        </div>
        <table class="fiscal-table">
          <thead>
            <tr>
              <th>Fecha venta</th>
              <th>Exchange venta</th>
              <th>Símbolo</th>
              <th>Cantidad venta</th>
              <th>Proceeds EUR</th>
              <th>Fee EUR</th>
              <th>Gap</th>
              <th>Lotes</th>
            </tr>
          </thead>
          <FifoSaleMatchRow
            v-for="sale in row.sales"
            :key="sale.sell_trade_id"
            :asset="row.denominacion"
            :sale="sale"
            @manual-cost-basis="emit('manualCostBasis', $event)"
          />
          <tfoot>
            <tr>
              <td>
                <strong>Total {{ row.denominacion }}</strong>
              </td>
              <td colspan="3"></td>
              <td>{{ formatMoney(row.valor_transmision_eur, 'EUR') }}</td>
              <td colspan="3">{{ row.casilla }}</td>
            </tr>
          </tfoot>
        </table>
      </section>
    </div>

    <footer v-if="props.rows.length" class="fiscal-total-summary">
      <span class="badge">Total adquisición: {{ formatMoney(totals.adquisicion, 'EUR') }}</span>
      <span class="badge">Total transmisión: {{ formatMoney(totals.transmision, 'EUR') }}</span>
      <span class="badge">Total ganancia: {{ formatMoney(totals.ganancia, 'EUR') }}</span>
      <span class="badge">Total pérdida: {{ formatMoney(totals.perdida, 'EUR') }}</span>
    </footer>
  </section>
</template>
