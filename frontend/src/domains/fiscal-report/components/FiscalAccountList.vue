<script setup lang="ts">
import { computed } from 'vue';
import type {
  BrokerCredential,
  BrokerSyncStatusResponse,
  BrokerSyncTriggerResponse,
} from '@/domains/fiscal-report/api';

const props = defineProps<{
  credentials: BrokerCredential[];
  syncStatusByCredential: Record<number, BrokerSyncStatusResponse | undefined>;
  syncRunsByCredential: Record<number, BrokerSyncTriggerResponse | undefined>;
  syncingByCredential: Record<number, boolean>;
  deletingByCredential: Record<number, boolean>;
}>();

const emit = defineEmits<{
  sync: [credentialId: number];
  remove: [credentialId: number];
}>();

const rows = computed(() =>
  props.credentials.map((credential) => ({
    credential,
    syncStatus: props.syncStatusByCredential[credential.id],
    syncRun: props.syncRunsByCredential[credential.id],
    isSyncing: Boolean(props.syncingByCredential[credential.id]),
    isDeleting: Boolean(props.deletingByCredential[credential.id]),
  })),
);

function toBrokerLabel(broker: string): string {
  return broker === 'binance' ? 'Binance' : 'Pionex';
}

function toTimestampLabel(value: string | null | undefined): string {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('es-ES');
}

function toStatsText(
  syncRun: BrokerSyncTriggerResponse | undefined,
  syncStatus: BrokerSyncStatusResponse | undefined,
): string {
  const stats = syncRun?.stats ?? syncStatus?.stats;
  if (!stats) return 'Sin ejecuciones de sync todavia.';
  const newTrades = Number(stats.new_trades ?? 0);
  const updatedTrades = Number(stats.updated_trades ?? 0);
  const newIncome = Number(stats.new_income_events ?? 0);
  const updatedIncome = Number(stats.updated_income_events ?? 0);
  return `Trades nuevos/actualizados: ${newTrades}/${updatedTrades} · Ingresos nuevos/actualizados: ${newIncome}/${updatedIncome}`;
}
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h2 class="ui-section-title">Credenciales</h2>
        <p class="ui-section-subtitle">
          Conecta cuentas de Pionex y Binance para sincronizar datos.
        </p>
      </div>
    </header>

    <div v-if="!rows.length" class="ui-state-block ui-state-empty">
      No hay credenciales cargadas todavia.
    </div>

    <ul v-else class="fiscal-credential-list list-plain">
      <li v-for="row in rows" :key="row.credential.id" class="fiscal-credential-row">
        <div class="fiscal-credential-main">
          <div class="fiscal-credential-head">
            <strong>{{ row.credential.label }}</strong>
            <span class="badge">{{ toBrokerLabel(row.credential.broker) }}</span>
            <span class="badge">{{ row.credential.api_key_masked }}</span>
          </div>
          <div class="fiscal-credential-meta">
            <span>Ultimo sync: {{ toTimestampLabel(row.credential.last_sync_at) }}</span>
            <span v-if="row.syncStatus?.gaps_detected" class="fiscal-text-warning"
              >Gaps detectados ({{ row.syncStatus?.gaps?.length ?? 0 }})</span
            >
          </div>
          <p class="fiscal-credential-stats">{{ toStatsText(row.syncRun, row.syncStatus) }}</p>
        </div>
        <div class="fiscal-credential-actions">
          <button
            class="btn btn-primary"
            type="button"
            :disabled="row.isSyncing || row.isDeleting"
            @click="emit('sync', row.credential.id)"
          >
            {{ row.isSyncing ? 'Sincronizando...' : 'Sync' }}
          </button>
          <button
            class="btn btn-ghost"
            type="button"
            :disabled="row.isDeleting || row.isSyncing"
            @click="emit('remove', row.credential.id)"
          >
            {{ row.isDeleting ? 'Eliminando...' : 'Eliminar' }}
          </button>
        </div>
      </li>
    </ul>
  </section>
</template>
