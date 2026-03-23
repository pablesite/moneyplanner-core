<script setup lang="ts">
import { ref } from 'vue';
import type { AccountingMovementsPageState } from '@/domains/accounting/useAccountingMovementsPage';

const props = defineProps<{ page: AccountingMovementsPageState }>();
const state = props.page;

const openGroups = ref(new Set<string>());

function toggleGroup(key: string) {
  const next = new Set(openGroups.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  openGroups.value = next;
}

function isGroupOpen(key: string) {
  return openGroups.value.has(key);
}

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
    <div v-if="state.cuentasSelectedAccount" class="ui-section-head ui-accounting-catalog-head">
      <p class="ui-section-subtitle ui-accounting-catalog-info">
        {{ state.cuentasVisibleTransactions.length }} de
        {{ state.cuentasRawTransactions.length }} movimientos —
        {{ state.accountDisplayName(state.cuentasSelectedAccount) }}
      </p>
      <div class="ui-accounting-filters ui-accounting-filters-2col">
        <input v-model="state.cuentasDateFrom" type="date" class="input" title="Desde" />
        <input v-model="state.cuentasDateTo" type="date" class="input" title="Hasta" />
      </div>
    </div>

    <div v-if="state.loading && !state.transactions.length" class="ui-section-loading">
      <div class="ui-import-spinner"></div>
      <span>Cargando cuentas...</span>
    </div>

    <div v-else class="ui-catalog-groups">
      <template v-for="(group, index) in state.groupedCuentasAccounts" :key="group.key">
        <div
          v-if="index === 0 || state.groupedCuentasAccounts[index - 1].positionType !== group.positionType"
          class="ui-catalog-section-label"
          :class="`ui-catalog-section-label-${group.positionType}`"
        >
          {{ group.positionType === 'asset' ? 'Activos' : 'Pasivos' }}
        </div>
      <div
        :class="`ui-catalog-group ui-catalog-group-${group.positionType}`"
      >
        <button
          class="ui-catalog-group-header"
          type="button"
          @click="toggleGroup(group.key)"
        >
          <span class="ui-catalog-group-label">{{ group.label }}</span>
          <span class="ui-catalog-group-count">{{ group.accounts.length }}</span>
          <span class="ui-catalog-group-chevron" :class="{ open: isGroupOpen(group.key) }">▾</span>
        </button>

        <div v-if="isGroupOpen(group.key)" class="ui-catalog-group-body">
          <template v-for="account in group.accounts" :key="account.id">
            <button
              class="ui-catalog-account-row"
              :class="{ selected: state.cuentasSelectedAccountId === account.id }"
              type="button"
              @click="state.cuentasSelectedAccountId = state.cuentasSelectedAccountId === account.id ? null : account.id"
            >
              <span class="ui-catalog-account-name">{{ state.accountDisplayName(account) }}</span>
              <span class="ui-catalog-account-balance">
                {{ state.formatCompact(account.current_balance, account.currency) }}
              </span>
            </button>

            <div
              v-if="state.cuentasSelectedAccountId === account.id"
              class="ui-catalog-transactions"
            >
              <div v-if="!state.cuentasRawTransactions.length" class="ui-state-block ui-state-empty">
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
              <p v-else-if="state.cuentasRawTransactions.length" class="ui-load-more-hint">
                Todos los movimientos cargados
              </p>
            </div>
          </template>
        </div>
      </div>
      </template>
    </div>
  </section>
</template>
