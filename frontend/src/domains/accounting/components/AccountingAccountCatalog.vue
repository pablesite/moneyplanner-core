<script setup lang="ts">
import type { AccountingMovementsPageState } from '@/domains/accounting/useAccountingMovementsPage';

const props = defineProps<{ page: AccountingMovementsPageState }>();
const state = props.page;
</script>

<template>
  <section class="ui-section-card">
    <div class="ui-section-head">
      <div class="ui-section-copy">
        <h2 class="ui-section-title">Cuentas</h2>
        <p v-if="state.cuentasSelectedAccount" class="ui-section-subtitle">
          {{ state.cuentasVisibleTransactions.length }} de
          {{ state.cuentasRawTransactions.length }} movimientos
        </p>
        <p v-else class="ui-section-subtitle">Selecciona una cuenta para ver sus movimientos</p>
      </div>
    </div>

    <div class="ui-accounting-filters ui-accounting-filters-3col">
      <select v-model="state.cuentasSelectedAccountId" class="select">
        <option :value="null">Selecciona una cuenta...</option>
        <option v-for="account in state.operationalAccounts" :key="account.id" :value="account.id">
          {{ state.accountDisplayName(account) }}
          ({{ state.formatCompact(account.current_balance, account.currency) }})
        </option>
      </select>
      <input
        v-model="state.cuentasDateFrom"
        type="date"
        class="input"
        title="Desde"
        placeholder="Desde"
      />
      <input
        v-model="state.cuentasDateTo"
        type="date"
        class="input"
        title="Hasta"
        placeholder="Hasta"
      />
    </div>

    <div v-if="state.loading && !state.transactions.length" class="ui-state-block ui-state-loading">
      Cargando movimientos...
    </div>
    <div v-else-if="!state.cuentasSelectedAccountId" class="ui-state-block ui-state-empty">
      Selecciona una cuenta para ver sus movimientos recientes.
    </div>
    <div v-else-if="!state.cuentasRawTransactions.length" class="ui-state-block ui-state-empty">
      Sin movimientos para los filtros actuales.
    </div>
    <ul v-else class="ui-entry-list">
      <li
        v-for="movement in state.cuentasVisibleTransactions"
        :key="movement.id"
        class="ui-entry-row"
      >
        <span class="ui-entry-date">{{ state.formatDate(movement.booking_date) }}</span>
        <div class="ui-entry-body">
          <strong class="ui-entry-desc">{{ movement.description }}</strong>
          <div class="ui-action-bar ui-entry-tags">
            <span :class="`ui-type-badge ui-type-badge-${movement.tone}`">
              {{ state.activityKindLabel(movement) }}
            </span>
            <span class="ui-entry-status">
              {{ movement.status === 'posted' ? '?' : '?' }}
              {{ movement.origin !== 'system' ? movement.origin : '' }}
            </span>
          </div>
        </div>
        <span
          class="ui-accounting-balance-delta"
          :class="`ui-accounting-balance-delta-${movement.tone}`"
        >
          {{
            state.formatSignedMoney(movement.impactValue, state.cuentasSelectedAccount?.currency)
          }}
        </span>
        <div class="ui-entry-actions">
          <button
            v-if="movement.origin !== 'system'"
            class="icon-btn ui-accounting-entry-action-btn"
            type="button"
            title="Editar movimiento"
            aria-label="Editar movimiento"
            :disabled="state.transactionCreationLoading"
            @click="state.openEditTransactionModal(movement.id)"
          >
            ??
          </button>
          <button
            v-if="movement.origin !== 'system'"
            class="icon-btn ui-accounting-entry-action-btn"
            type="button"
            title="Eliminar movimiento"
            aria-label="Eliminar movimiento"
            :disabled="state.transactionCreationLoading"
            @click="state.deleteTransactionFromTimeline(movement.id, movement.description)"
          >
            ???
          </button>
        </div>
      </li>
    </ul>
    <div v-if="state.cuentasHasMore" class="ui-load-more">
      <button class="btn" type="button" @click="state.loadMoreCuentas">Cargar m�s</button>
    </div>
    <p
      v-else-if="state.cuentasSelectedAccountId && state.cuentasRawTransactions.length"
      class="ui-load-more-hint"
    >
      Todos los movimientos cargados
    </p>
  </section>
</template>
