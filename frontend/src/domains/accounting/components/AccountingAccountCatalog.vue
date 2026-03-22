<script setup lang="ts">
import { computed } from 'vue';
import type { AccountingMovementsPageState } from '@/domains/accounting/useAccountingMovementsPage';

const props = defineProps<{ page: AccountingMovementsPageState }>();
const state = props.page;

type AccountGroup = {
  key: string;
  label: string;
  accounts: any[];
};

function accountTypeLabel(accountType: string): string {
  if (accountType === 'asset') return 'Activos';
  if (accountType === 'liability') return 'Pasivos';
  return 'Otras cuentas';
}

function accountLabel(account: any): string {
  if (typeof state.accountDisplayName === 'function') {
    return state.accountDisplayName(account);
  }
  return account.display_name || account.name;
}

const groupedOperationalAccounts = computed<AccountGroup[]>(() => {
  const groups = new Map<string, AccountGroup['accounts']>();
  for (const account of state.operationalAccounts) {
    const key = account.account_type ?? 'other';
    const existing = groups.get(key) ?? [];
    existing.push(account);
    groups.set(key, existing);
  }
  const order = ['asset', 'liability', 'other'];
  return Array.from(groups.entries())
    .sort((a, b) => order.indexOf(a[0]) - order.indexOf(b[0]))
    .map(([key, accounts]) => ({
      key,
      label: accountTypeLabel(key),
      accounts: accounts
        .slice()
        .sort((left, right) =>
          accountLabel(left).localeCompare(accountLabel(right), 'es', { sensitivity: 'base' }),
        ),
    }));
});

function movementStatusLabel(status: string): string {
  return status === 'posted' ? 'Publicado' : 'Borrador';
}

function movementOriginLabel(origin: string): string {
  if (origin === 'import') return 'Importado';
  if (origin === 'manual') return 'Manual';
  if (origin === 'system') return 'Sistema';
  return origin;
}
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
        <optgroup v-for="group in groupedOperationalAccounts" :key="group.key" :label="group.label">
          <option v-for="account in group.accounts" :key="account.id" :value="account.id">
            {{ accountLabel(account) }}
            ({{ state.formatCompact(account.current_balance, account.currency) }})
          </option>
        </optgroup>
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
          <div class="ui-action-bar ui-entry-meta">
            <span :class="`ui-type-badge ui-type-badge-${movement.tone}`">
              {{ state.activityKindLabel(movement) }}
            </span>
            <span class="ui-pro-chip ui-entry-chip">{{
              movementStatusLabel(movement.status)
            }}</span>
            <span v-if="movement.origin !== 'system'" class="ui-pro-chip ui-entry-chip">
              {{ movementOriginLabel(movement.origin) }}
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
            class="btn btn-ghost btn-sm ui-entry-inline-btn"
            type="button"
            title="Editar movimiento"
            aria-label="Editar movimiento"
            :disabled="state.transactionCreationLoading"
            @click="state.openEditTransactionModal(movement.id)"
          >
            Editar
          </button>
          <button
            v-if="movement.origin !== 'system'"
            class="btn btn-ghost btn-sm ui-entry-inline-btn"
            type="button"
            title="Eliminar movimiento"
            aria-label="Eliminar movimiento"
            :disabled="state.transactionCreationLoading"
            @click="state.deleteTransactionFromTimeline(movement.id, movement.description)"
          >
            Eliminar
          </button>
        </div>
      </li>
    </ul>
    <div v-if="state.cuentasHasMore" class="ui-load-more">
      <button class="btn" type="button" @click="state.loadMoreCuentas">Cargar mas</button>
    </div>
    <p
      v-else-if="state.cuentasSelectedAccountId && state.cuentasRawTransactions.length"
      class="ui-load-more-hint"
    >
      Todos los movimientos cargados
    </p>
  </section>
</template>
