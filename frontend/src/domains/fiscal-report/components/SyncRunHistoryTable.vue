<script setup lang="ts">
import type { SyncRunSummary } from '@/domains/fiscal-report/api';

const props = defineProps<{
  rows: SyncRunSummary[];
  loading: boolean;
  activeRunId: number | null;
}>();

const emit = defineEmits<{
  open: [syncRunId: number];
}>();

function toStatusLabel(value: SyncRunSummary['status']) {
  if (value === 'ok') return 'OK';
  if (value === 'partial') return 'Partial';
  if (value === 'failed') return 'Failed';
  return 'Running';
}

function toDateLabel(value: string | null) {
  if (!value) return '-';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString('es-ES');
}
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h2 class="ui-section-title">Historial de syncs</h2>
        <p class="ui-section-subtitle">
          Runs ejecutados para el año seleccionado con drill-down por ejecución.
        </p>
      </div>
    </header>

    <div v-if="props.loading" class="ui-state-block ui-state-loading">Cargando historial...</div>
    <div v-else-if="!props.rows.length" class="ui-state-block ui-state-empty">
      No hay sync runs para este año.
    </div>
    <table v-else class="fiscal-table">
      <thead>
        <tr>
          <th>ID</th>
          <th>Status</th>
          <th>Inicio</th>
          <th>Fin</th>
          <th>Trades</th>
          <th>Ingresos</th>
          <th>Bots</th>
          <th>Acción</th>
        </tr>
      </thead>
      <tbody>
        <tr
          v-for="row in props.rows"
          :key="row.id"
          :class="{ 'fiscal-row-active': props.activeRunId === row.id }"
        >
          <td>#{{ row.id }}</td>
          <td>
            <span class="badge">{{ toStatusLabel(row.status) }}</span>
          </td>
          <td>{{ toDateLabel(row.started_at) }}</td>
          <td>{{ toDateLabel(row.finished_at) }}</td>
          <td>{{ Number(row.stats.new_trades ?? 0) + Number(row.stats.updated_trades ?? 0) }}</td>
          <td>
            {{
              Number(row.stats.new_income_events ?? 0) +
              Number(row.stats.updated_income_events ?? 0)
            }}
          </td>
          <td>
            {{
              Number(row.stats.new_bot_results ?? 0) + Number(row.stats.updated_bot_results ?? 0)
            }}
          </td>
          <td>
            <button class="btn btn-sm" type="button" @click="emit('open', row.id)">
              {{ props.activeRunId === row.id ? 'Abierto' : 'Abrir detalle' }}
            </button>
          </td>
        </tr>
      </tbody>
    </table>
  </section>
</template>
