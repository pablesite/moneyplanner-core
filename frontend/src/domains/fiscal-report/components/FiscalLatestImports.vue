<script setup lang="ts">
import { computed } from 'vue';
import type { BrokerCredential, BrokerSyncStatusResponse } from '@/domains/fiscal-report/api';

const props = defineProps<{
  credentials: BrokerCredential[];
  syncStatusByCredential: Record<number, BrokerSyncStatusResponse | undefined>;
}>();

const latestRows = computed(() =>
  props.credentials
    .map((credential) => {
      const status = props.syncStatusByCredential[credential.id];
      const stats = status?.stats;
      return {
        id: credential.id,
        label: credential.label,
        broker: credential.broker,
        lastSyncAt: credential.last_sync_at,
        newTrades: Number(stats?.new_trades ?? 0),
        updatedTrades: Number(stats?.updated_trades ?? 0),
        newIncomeEvents: Number(stats?.new_income_events ?? 0),
        updatedIncomeEvents: Number(stats?.updated_income_events ?? 0),
        newBotResults: Number(stats?.new_bot_results ?? 0),
        updatedBotResults: Number(stats?.updated_bot_results ?? 0),
      };
    })
    .filter((row) => Boolean(row.lastSyncAt))
    .sort((a, b) => new Date(b.lastSyncAt ?? 0).getTime() - new Date(a.lastSyncAt ?? 0).getTime())
    .slice(0, 6),
);

function toTimestampLabel(value: string | null | undefined): string {
  if (!value) return '-';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString('es-ES');
}

function toBrokerLabel(broker: string): string {
  return broker === 'binance' ? 'Binance' : 'Pionex';
}
</script>

<template>
  <section class="ui-section-card fiscal-section">
    <header class="ui-section-head">
      <div class="ui-section-copy">
        <h2 class="ui-section-title">Últimos datos importados</h2>
        <p class="ui-section-subtitle">
          Resumen de las últimas sincronizaciones con detalle de registros nuevos y actualizados.
        </p>
      </div>
    </header>

    <div v-if="!latestRows.length" class="ui-state-block ui-state-empty">
      Aún no hay sincronizaciones con datos para mostrar.
    </div>

    <ul v-else class="fiscal-credential-list list-plain">
      <li v-for="row in latestRows" :key="row.id" class="fiscal-credential-row">
        <div class="fiscal-credential-main">
          <div class="fiscal-credential-head">
            <strong>{{ row.label }}</strong>
            <span class="badge">{{ toBrokerLabel(row.broker) }}</span>
          </div>
          <div class="fiscal-credential-meta">
            <span>Último sync: {{ toTimestampLabel(row.lastSyncAt) }}</span>
          </div>
          <p class="fiscal-credential-stats">
            Trades nuevos/actualizados: {{ row.newTrades }}/{{ row.updatedTrades }} · Ingresos
            nuevos/actualizados: {{ row.newIncomeEvents }}/{{ row.updatedIncomeEvents }} · Bots
            nuevos/actualizados: {{ row.newBotResults }}/{{ row.updatedBotResults }}
          </p>
        </div>
      </li>
    </ul>
  </section>
</template>
