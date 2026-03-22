<script setup lang="ts">
import type { LedgerTransaction } from '@/domains/accounting/models';
import type { AccountingMovementsPageState } from '@/domains/accounting/useAccountingMovementsPage';

const props = defineProps<{ page: AccountingMovementsPageState }>();
const state = props.page;

function kindTone(transaction: LedgerTransaction): 'positive' | 'negative' | 'neutral' {
  const label = state.activityKindLabel(transaction).toLowerCase();
  if (label.includes('ingreso')) return 'positive';
  if (label.includes('gasto') || label.includes('deuda')) return 'negative';
  return 'neutral';
}

function amountTone(transaction: LedgerTransaction): 'positive' | 'negative' | 'neutral' {
  return kindTone(transaction);
}

function statusLabel(status: LedgerTransaction['status']): string {
  return status === 'posted' ? 'Publicado' : 'Borrador';
}

function originLabel(origin: LedgerTransaction['origin']): string {
  if (origin === 'import') return 'Importado';
  if (origin === 'manual') return 'Manual';
  if (origin === 'system') return 'Sistema';
  return origin;
}

function accountTrail(transaction: LedgerTransaction): string {
  return transaction.entries.map((entry) => entry.account_name).join(' -> ');
}
</script>

<template>
  <section class="ui-section-card">
    <div class="ui-section-head">
      <div class="ui-section-copy">
        <h2 class="ui-section-title">Todos los movimientos</h2>
        <p class="ui-section-subtitle">
          {{ state.todosVisibleTransactions.length }} de
          {{ state.todosRawTransactions.length }} movimientos
        </p>
      </div>
    </div>

    <div class="ui-accounting-filters ui-accounting-filters-4col">
      <input
        v-model="state.activityFilters.query"
        class="input"
        placeholder="Buscar descripcion, cuenta o categoria..."
      />
      <select v-model="state.activityFilters.kind" class="select">
        <option value="all">Todos los tipos</option>
        <option value="income">Ingresos</option>
        <option value="expense">Gastos</option>
        <option value="transfer">Transferencias</option>
        <option value="investment_purchase">Inversion</option>
        <option value="debt_payment">Pago deuda</option>
        <option value="revaluation">Revalorizaciones</option>
      </select>
      <input v-model="state.todosDateFrom" type="date" class="input" title="Desde" />
      <input v-model="state.todosDateTo" type="date" class="input" title="Hasta" />
    </div>

    <div v-if="state.loading && !state.transactions.length" class="ui-state-block ui-state-loading">
      Cargando movimientos...
    </div>
    <div v-else-if="!state.todosRawTransactions.length" class="ui-state-block ui-state-empty">
      Sin movimientos para los filtros actuales.
    </div>
    <ul v-else class="ui-entry-list">
      <li
        v-for="transaction in state.todosVisibleTransactions"
        :key="transaction.id"
        class="ui-entry-row"
      >
        <span class="ui-entry-date">{{ state.formatDate(transaction.booking_date) }}</span>
        <div class="ui-entry-body">
          <strong class="ui-entry-desc">{{ transaction.description }}</strong>
          <div class="ui-action-bar ui-entry-meta">
            <span :class="`ui-type-badge ui-type-badge-${kindTone(transaction)}`">
              {{ state.activityKindLabel(transaction) }}
            </span>
            <span class="ui-pro-chip ui-entry-chip">
              {{ statusLabel(transaction.status) }}
            </span>
            <span v-if="transaction.origin !== 'system'" class="ui-pro-chip ui-entry-chip">
              {{ originLabel(transaction.origin) }}
            </span>
          </div>
          <span class="ui-entry-accounts">{{ accountTrail(transaction) }}</span>
        </div>
        <span
          class="ui-accounting-balance-delta"
          :class="`ui-accounting-balance-delta-${amountTone(transaction)}`"
        >
          {{ state.formatMoney(state.transactionMainAmount(transaction)) }}
        </span>
        <div class="ui-entry-actions">
          <button
            v-if="transaction.origin !== 'system'"
            class="btn btn-ghost btn-sm ui-entry-inline-btn"
            type="button"
            title="Editar movimiento"
            aria-label="Editar movimiento"
            :disabled="state.transactionCreationLoading"
            @click="state.openEditTransactionModal(transaction.id)"
          >
            Editar
          </button>
          <button
            v-if="transaction.origin !== 'system'"
            class="btn btn-ghost btn-sm ui-entry-inline-btn"
            type="button"
            title="Eliminar movimiento"
            aria-label="Eliminar movimiento"
            :disabled="state.transactionCreationLoading"
            @click="state.deleteTransactionFromTimeline(transaction.id, transaction.description)"
          >
            Eliminar
          </button>
        </div>
      </li>
    </ul>

    <div v-if="state.todosHasMore" class="ui-load-more">
      <button class="btn" type="button" @click="state.loadMoreTodos">Cargar mas</button>
    </div>
    <p v-else-if="state.todosRawTransactions.length" class="ui-load-more-hint">
      Todos los movimientos cargados
    </p>
  </section>
</template>
