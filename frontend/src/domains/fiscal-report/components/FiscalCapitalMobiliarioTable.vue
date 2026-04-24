<script setup lang="ts">
import { computed } from 'vue';
import { formatMoney } from '@/lib/format';
import type { FiscalCapitalMobiliarioRow } from '@/domains/fiscal-report/api';

const props = defineProps<{
  rows: FiscalCapitalMobiliarioRow[];
}>();

const total = computed(() => props.rows.reduce((acc, row) => acc + row.importe_eur, 0));
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h3 class="ui-section-title">Capital mobiliario</h3>
        <p class="ui-section-subtitle">Seccion I · Casilla 029</p>
      </div>
    </header>

    <div v-if="!props.rows.length" class="ui-state-block ui-state-empty">
      Sin movimientos para esta seccion.
    </div>

    <table v-else class="fiscal-table">
      <thead>
        <tr>
          <th>Fuente</th>
          <th>Activo</th>
          <th>Importe EUR</th>
          <th>Casilla</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in props.rows" :key="index">
          <td>{{ row.fuente }}</td>
          <td>{{ row.asset }}</td>
          <td>{{ formatMoney(row.importe_eur, 'EUR') }}</td>
          <td>{{ row.casilla }}</td>
        </tr>
      </tbody>
      <tfoot>
        <tr>
          <td colspan="2"><strong>Total Casilla 029</strong></td>
          <td>{{ formatMoney(total, 'EUR') }}</td>
          <td>029</td>
        </tr>
      </tfoot>
    </table>
  </section>
</template>
