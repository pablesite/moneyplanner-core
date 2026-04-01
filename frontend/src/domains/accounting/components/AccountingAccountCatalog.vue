<script setup lang="ts">
import { onBeforeUnmount, ref } from 'vue';
import type { AccountingMovementsPageState } from '@/domains/accounting/useAccountingMovementsPage';

const props = defineProps<{ page: AccountingMovementsPageState }>();
const state = props.page;

const openGroups = ref(new Set<string>());
const dateDropdownOpen = ref(false);

function toggleGroup(key: string) {
  const next = new Set(openGroups.value);
  if (next.has(key)) next.delete(key);
  else next.add(key);
  openGroups.value = next;
}

function isGroupOpen(key: string) {
  return openGroups.value.has(key);
}

function toggleDateDropdown() {
  dateDropdownOpen.value = !dateDropdownOpen.value;
}

function selectDatePreset(preset: (typeof state.datePresetOptions)[number]['value']) {
  state.applyCuentasDatePreset(preset);
  if (preset !== 'custom') {
    dateDropdownOpen.value = false;
  }
}

function closeDateDropdown(e: MouseEvent) {
  const target = e.target as HTMLElement;
  if (!target.closest('.ui-accounting-date-dropdown')) {
    dateDropdownOpen.value = false;
  }
}

document.addEventListener('click', closeDateDropdown, true);
onBeforeUnmount(() => document.removeEventListener('click', closeDateDropdown, true));

const activeDateLabel = () => {
  const opt = state.datePresetOptions.find((o) => o.value === state.cuentasDatePreset);
  return opt?.label ?? 'Período';
};

function movementOriginLabel(origin: string): string {
  if (origin === 'import') return 'Importado';
  return origin;
}

function typeBadgeVariant(movement: {
  activity_kind: string;
  investment_direction?: string;
}): string {
  if (movement.activity_kind === 'income') return 'income';
  if (movement.activity_kind === 'expense') return 'expense';
  if (movement.activity_kind === 'transfer') return 'transfer';
  if (movement.activity_kind === 'adjustment') return 'transfer';
  if (movement.activity_kind === 'investment_purchase') {
    return movement.investment_direction === 'outflow' ? 'investment-outflow' : 'investment-inflow';
  }
  if (movement.activity_kind === 'debt_payment') return 'debt-payment';
  if (movement.activity_kind === 'opening_balance') return 'transfer';
  if (movement.activity_kind === 'revaluation') return 'revaluation';
  return 'other';
}
</script>

<template>
  <section class="ui-section-card">
    <div v-if="state.cuentasSelectedAccount" class="ui-section-head ui-accounting-catalog-head">
      <p class="ui-section-subtitle ui-accounting-catalog-info">
        Movimientos — {{ state.accountDisplayName(state.cuentasSelectedAccount) }}
      </p>
    </div>

    <div v-if="state.cuentasSelectedAccount" class="ui-accounting-filters-floating">
      <div class="ui-accounting-filters-row">
        <input v-model="state.cuentasFilters.query" class="input" placeholder="Buscar..." />
        <select v-model="state.cuentasFilters.kind" class="select">
          <option value="all">Tipo</option>
          <option value="income">Ingresos</option>
          <option value="expense">Gastos</option>
          <option value="transfer">Transferencias</option>
          <option value="adjustment">Ajustes</option>
          <option value="investment">Inversion</option>
          <option value="debt_payment">Pago deuda</option>
          <option value="opening_balance">Saldo inicial</option>
          <option value="revaluation">Revalorizaciones</option>
        </select>
        <select
          v-if="state.cuentasFilters.kind === 'income' || state.cuentasFilters.kind === 'expense'"
          v-model="state.cuentasFilters.categoryKey"
          class="select"
        >
          <option value="">Categoría</option>
          <option
            v-for="cat in state.cuentasFilterCategoryOptions"
            :key="cat.value"
            :value="cat.value"
          >
            {{ cat.label }}
          </option>
        </select>
        <select
          v-if="state.cuentasFilterSubcategoryOptions.length"
          v-model="state.cuentasFilters.subcategoryKey"
          class="select"
        >
          <option value="">Subcategoría</option>
          <option
            v-for="sub in state.cuentasFilterSubcategoryOptions"
            :key="sub.value"
            :value="sub.value"
          >
            {{ sub.label }}
          </option>
        </select>
        <div class="ui-accounting-date-dropdown">
          <button type="button" class="ui-accounting-date-trigger" @click="toggleDateDropdown">
            {{ activeDateLabel() }}
            <span class="ui-accounting-date-trigger-arrow">▾</span>
          </button>
          <div v-if="dateDropdownOpen" class="ui-accounting-date-menu">
            <button
              v-for="preset in state.datePresetOptions"
              :key="preset.value"
              type="button"
              class="ui-accounting-date-menu-item"
              :class="{
                'ui-accounting-date-menu-item-active': state.cuentasDatePreset === preset.value,
              }"
              @click="selectDatePreset(preset.value)"
            >
              {{ preset.label }}
            </button>
            <template v-if="state.cuentasDatePreset === 'custom'">
              <div class="ui-accounting-date-menu-custom">
                <input v-model="state.cuentasDateFrom" type="date" class="input" title="Desde" />
                <input v-model="state.cuentasDateTo" type="date" class="input" title="Hasta" />
              </div>
            </template>
          </div>
        </div>
        <span class="ui-accounting-filters-count">
          {{ state.cuentasTransactions.length }} de {{ state.cuentasTotalCount }}
        </span>
      </div>
    </div>

    <div
      v-if="state.cuentasLoading && state.cuentasSelectedAccountId == null"
      class="ui-section-loading"
    >
      <div class="ui-import-spinner"></div>
      <span>Cargando cuentas...</span>
    </div>

    <div v-else class="ui-catalog-groups">
      <template v-for="(group, index) in state.groupedCuentasAccounts" :key="group.key">
        <div
          v-if="
            index === 0 ||
            state.groupedCuentasAccounts[index - 1]?.positionType !== group.positionType
          "
          class="ui-catalog-section-label"
          :class="`ui-catalog-section-label-${group.positionType}`"
        >
          {{ group.positionType === 'asset' ? 'Activos' : 'Pasivos' }}
        </div>
        <div :class="`ui-catalog-group ui-catalog-group-${group.positionType}`">
          <button class="ui-catalog-group-header" type="button" @click="toggleGroup(group.key)">
            <span class="ui-catalog-group-label">{{ group.label }}</span>
            <span class="ui-catalog-group-count">{{ group.accounts.length }}</span>
            <span class="ui-catalog-group-chevron" :class="{ open: isGroupOpen(group.key) }"
              >▾</span
            >
          </button>

          <div v-if="isGroupOpen(group.key)" class="ui-catalog-group-body">
            <template v-for="account in group.accounts" :key="account.id">
              <button
                class="ui-catalog-account-row"
                :class="{ selected: state.cuentasSelectedAccountId === account.id }"
                type="button"
                @click="
                  state.cuentasSelectedAccountId =
                    state.cuentasSelectedAccountId === account.id ? null : account.id
                "
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
                <div
                  v-if="!state.cuentasTransactions.length"
                  class="ui-state-block ui-state-empty ui-accounting-empty-state"
                >
                  <p class="ui-state-title">Sin movimientos para estos filtros</p>
                  <p class="ui-state-hint">
                    Prueba otro periodo o ajusta la búsqueda para ver actividad.
                  </p>
                </div>
                <ul v-else class="ui-entry-list">
                  <li
                    v-for="movement in state.cuentasTransactions"
                    :key="movement.id"
                    class="ui-entry-row"
                  >
                    <span class="ui-entry-date">{{ state.formatDate(movement.booking_date) }}</span>
                    <div class="ui-entry-body">
                      <strong class="ui-entry-desc">{{ movement.description }}</strong>
                      <div class="ui-action-bar ui-entry-meta">
                        <span :class="`ui-type-badge ui-type-badge-${typeBadgeVariant(movement)}`">
                          {{ state.activityKindLabel(movement) }}
                        </span>
                        <span class="ui-pro-chip ui-entry-chip">
                          {{ state.transactionAccountTrailLabel(movement) }}
                        </span>
                        <span
                          v-if="state.transactionOwnershipLabel(movement)"
                          class="ui-pro-chip ui-entry-chip"
                        >
                          {{ state.transactionOwnershipLabel(movement) }}
                        </span>
                        <span v-if="movement.origin === 'import'" class="ui-pro-chip ui-entry-chip">
                          {{ movementOriginLabel(movement.origin) }}
                        </span>
                      </div>
                      <span
                        v-if="state.transactionClassificationLabel(movement)"
                        class="ui-entry-accounts"
                      >
                        {{ state.transactionClassificationLabel(movement) }}
                      </span>
                    </div>
                    <span
                      class="ui-accounting-balance-delta"
                      :class="`ui-accounting-balance-delta-${movement.tone}`"
                    >
                      {{
                        state.formatSignedMoney(
                          movement.impactValue,
                          state.cuentasSelectedAccount?.currency,
                        )
                      }}
                    </span>
                    <div class="ui-entry-actions">
                      <button
                        v-if="movement.origin !== 'system'"
                        class="icon-btn ui-accounting-entry-action-btn"
                        type="button"
                        title="Duplicar movimiento"
                        aria-label="Duplicar movimiento"
                        :disabled="state.transactionCreationLoading"
                        @click="state.openDuplicateFromTransaction(movement)"
                      >
                        <svg
                          class="ui-entry-action-icon"
                          viewBox="0 0 24 24"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                          aria-hidden="true"
                        >
                          <rect
                            x="9"
                            y="9"
                            width="13"
                            height="13"
                            rx="2"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linejoin="round"
                          />
                          <path
                            d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                          />
                        </svg>
                      </button>
                      <button
                        v-if="movement.origin !== 'system'"
                        class="icon-btn ui-accounting-entry-action-btn ui-entry-action-edit"
                        type="button"
                        title="Editar movimiento"
                        aria-label="Editar movimiento"
                        :disabled="state.transactionCreationLoading"
                        @click="state.openEditTransactionModal(movement.id)"
                      >
                        <svg
                          class="ui-entry-action-icon"
                          viewBox="0 0 24 24"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                          aria-hidden="true"
                        >
                          <path
                            d="M12 20h9"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                          />
                          <path
                            d="M16.5 3.5a2.12 2.12 0 0 1 3 3L8 18l-4 1 1-4 11.5-11.5Z"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                          />
                        </svg>
                      </button>
                      <button
                        v-if="movement.origin !== 'system'"
                        class="icon-btn ui-accounting-entry-action-btn ui-entry-action-delete"
                        type="button"
                        title="Eliminar movimiento"
                        aria-label="Eliminar movimiento"
                        :disabled="state.transactionCreationLoading"
                        @click="
                          state.deleteTransactionFromTimeline(movement.id, movement.description)
                        "
                      >
                        <svg
                          class="ui-entry-action-icon"
                          viewBox="0 0 24 24"
                          fill="none"
                          xmlns="http://www.w3.org/2000/svg"
                          aria-hidden="true"
                        >
                          <path
                            d="M3 6h18"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                          />
                          <path
                            d="M8 6V4a1 1 0 0 1 1-1h6a1 1 0 0 1 1 1v2"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                          />
                          <path
                            d="M19 6l-1 14a1 1 0 0 1-1 .93H7a1 1 0 0 1-1-.93L5 6"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                          />
                          <path
                            d="M10 11v6M14 11v6"
                            stroke="currentColor"
                            stroke-width="1.8"
                            stroke-linecap="round"
                            stroke-linejoin="round"
                          />
                        </svg>
                      </button>
                    </div>
                  </li>
                </ul>
                <div v-if="state.cuentasHasMore" class="ui-load-more">
                  <button
                    class="btn"
                    type="button"
                    :disabled="state.cuentasLoadingMore"
                    @click="state.loadMoreCuentas"
                  >
                    {{ state.cuentasLoadingMore ? 'Cargando...' : 'Cargar mas' }}
                  </button>
                </div>
                <p v-else-if="state.cuentasTransactions.length" class="ui-load-more-hint">
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
