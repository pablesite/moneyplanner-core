<script setup lang="ts">
import { formatAmount } from '@/lib/format';
import type { BalanceReconciliationEntry } from '@/domains/fiscal-report/api';

defineProps<{
  rows: BalanceReconciliationEntry[];
  loading: boolean;
}>();
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h2 class="ui-section-title">Conciliación de saldos</h2>
        <p class="ui-section-subtitle">
          Comparativa expected vs actual por asset en balance_reconciliation.
        </p>
      </div>
    </header>

    <div v-if="loading" class="ui-state-block ui-state-loading">Cargando conciliación...</div>
    <div v-else-if="!rows.length" class="ui-state-block ui-state-empty">
      No hay incidencias de conciliación para el periodo seleccionado.
    </div>
    <table v-else class="fiscal-table">
      <thead>
        <tr>
          <th>Asset</th>
          <th>Expected</th>
          <th>Actual</th>
          <th>Delta</th>
          <th>Status</th>
          <th>Sync run</th>
        </tr>
      </thead>
      <tbody>
        <tr v-for="row in rows" :key="`${row.asset}-${row.sync_run_id}`">
          <td>{{ row.asset }}</td>
          <td>{{ formatAmount(row.expected, { maxDecimals: 8 }) }}</td>
          <td>{{ formatAmount(row.actual, { maxDecimals: 8 }) }}</td>
          <td>{{ formatAmount(row.diff, { maxDecimals: 8 }) }}</td>
          <td>
            <span
              class="badge"
              :class="row.status === 'mismatch' ? 'fiscal-badge-danger' : 'fiscal-badge-ok'"
            >
              {{ row.status }}
            </span>
          </td>
          <td>#{{ row.sync_run_id }}</td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
