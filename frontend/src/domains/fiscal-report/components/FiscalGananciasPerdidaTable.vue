<script setup lang="ts">
import { computed, ref } from 'vue';
import { formatAmount, formatMoney } from '@/lib/format';
import type { FiscalTradeSectionRow } from '@/domains/fiscal-report/api';

const props = defineProps<{
  rows: FiscalTradeSectionRow[];
}>();

const expandedByAsset = ref<Record<string, boolean>>({});

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

function isExpanded(asset: string): boolean {
  return Boolean(expandedByAsset.value[asset]);
}

function toggleAsset(asset: string) {
  expandedByAsset.value = {
    ...expandedByAsset.value,
    [asset]: !expandedByAsset.value[asset],
  };
}
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h3 class="ui-section-title">Ganancias/perdidas por transmisiones</h3>
        <p class="ui-section-subtitle">Agrupado por denominacion y expandible por lotes FIFO</p>
      </div>
    </header>

    <div v-if="!props.rows.length" class="ui-state-block ui-state-empty">
      No hay transmisiones sujetas a FIFO para este año.
    </div>

    <table v-else class="fiscal-table">
      <thead>
        <tr>
          <th>Denominacion</th>
          <th>V. Adquisicion EUR</th>
          <th>V. Transmision EUR</th>
          <th>Ganancia</th>
          <th>Perdida</th>
          <th>Casilla</th>
          <th>Lotes</th>
        </tr>
      </thead>
      <tbody>
        <template v-for="row in props.rows" :key="row.denominacion">
          <tr>
            <td>{{ row.denominacion }}</td>
            <td>{{ formatMoney(row.valor_adquisicion_eur, 'EUR') }}</td>
            <td>{{ formatMoney(row.valor_transmision_eur, 'EUR') }}</td>
            <td>{{ formatMoney(row.ganancia_eur, 'EUR') }}</td>
            <td>{{ formatMoney(row.perdida_eur, 'EUR') }}</td>
            <td>{{ row.casilla }}</td>
            <td>
              <button class="btn btn-sm" type="button" @click="toggleAsset(row.denominacion)">
                {{ isExpanded(row.denominacion) ? 'Ocultar' : 'Ver lotes' }}
              </button>
            </td>
          </tr>
          <tr v-if="isExpanded(row.denominacion)" class="fiscal-lot-row">
            <td colspan="7">
              <table class="fiscal-lot-table">
                <thead>
                  <tr>
                    <th>Buy date</th>
                    <th>Sell date</th>
                    <th>Exchange buy</th>
                    <th>Exchange sell</th>
                    <th>Qty</th>
                    <th>Cost EUR</th>
                    <th>Proceeds EUR</th>
                    <th>Gain/Loss EUR</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(lot, lotIndex) in row.lotes" :key="lotIndex">
                    <td>{{ lot.buy_date ?? '-' }}</td>
                    <td>{{ lot.sell_date }}</td>
                    <td>{{ lot.exchange_buy }}</td>
                    <td>{{ lot.exchange_sell }}</td>
                    <td>{{ formatAmount(lot.quantity, { maxDecimals: 8 }) }}</td>
                    <td>{{ formatMoney(lot.cost_eur, 'EUR') }}</td>
                    <td>{{ formatMoney(lot.proceeds_eur, 'EUR') }}</td>
                    <td>{{ formatMoney(lot.gain_loss_eur, 'EUR') }}</td>
                  </tr>
                </tbody>
              </table>
            </td>
          </tr>
        </template>
      </tbody>
      <tfoot>
        <tr>
          <td><strong>Totales</strong></td>
          <td>{{ formatMoney(totals.adquisicion, 'EUR') }}</td>
          <td>{{ formatMoney(totals.transmision, 'EUR') }}</td>
          <td>{{ formatMoney(totals.ganancia, 'EUR') }}</td>
          <td>{{ formatMoney(totals.perdida, 'EUR') }}</td>
          <td colspan="2">332</td>
        </tr>
      </tfoot>
    </table>
  </section>
</template>
