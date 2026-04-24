<script setup lang="ts">
import { formatMoney } from '@/lib/format';
import type { FiscalFuturesRow } from '@/domains/fiscal-report/api';

defineProps<{
  rows: FiscalFuturesRow[];
}>();

function toDateTimeLabel(value: string): string {
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('es-ES');
}
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h3 class="ui-section-title">Ganancias/perdidas futuros</h3>
        <p class="ui-section-subtitle">Posiciones derivadas cerradas</p>
      </div>
    </header>

    <div v-if="!rows.length" class="ui-state-block ui-state-empty">
      No hay posiciones de futuros cerradas para este año.
    </div>

    <table v-else class="fiscal-table">
      <thead>
        <tr>
          <th>Simbolo</th>
          <th>Direccion</th>
          <th>Apertura</th>
          <th>Cierre</th>
          <th>PNL EUR</th>
          <th>Casilla</th>
          <th>⚠</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="(row, index) in rows" :key="index">
          <td>{{ row.symbol }}</td>
          <td>{{ row.side }}</td>
          <td>{{ toDateTimeLabel(row.open_time) }}</td>
          <td>{{ toDateTimeLabel(row.close_time) }}</td>
          <td>{{ formatMoney(row.net_pnl_eur, 'EUR') }}</td>
          <td>{{ row.casilla }}</td>
          <td>
            <span
              v-if="row.aviso_derivados"
              class="badge"
              title="Derivados perpetuos: tratamiento fiscal puede diferir"
            >
              ⚠
            </span>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
