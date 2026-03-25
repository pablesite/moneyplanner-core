<script setup lang="ts">
import { ref, onBeforeUnmount } from 'vue';
import type { LedgerTransaction } from '@/domains/accounting/models';
import type { AccountingMovementsPageState } from '@/domains/accounting/useAccountingMovementsPage';

const props = defineProps<{ page: AccountingMovementsPageState }>();
const state = props.page;

const dateDropdownOpen = ref(false);

function toggleDateDropdown() {
  dateDropdownOpen.value = !dateDropdownOpen.value;
}

function selectDatePreset(preset: (typeof state.datePresetOptions)[number]['value']) {
  state.applyDatePreset(preset);
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
  const opt = state.datePresetOptions.find((o) => o.value === state.todosDatePreset);
  return opt?.label ?? 'Período';
};

function typeBadgeVariant(transaction: LedgerTransaction): string {
  if (transaction.activity_kind === 'income') return 'income';
  if (transaction.activity_kind === 'expense') return 'expense';
  if (transaction.activity_kind === 'transfer') return 'transfer';
  if (transaction.activity_kind === 'investment_purchase') {
    return transaction.investment_direction === 'outflow'
      ? 'investment-outflow'
      : 'investment-inflow';
  }
  if (transaction.activity_kind === 'debt_payment') return 'debt-payment';
  if (transaction.activity_kind === 'revaluation') return 'revaluation';
  return 'other';
}

function signedImpactForRow(transaction: LedgerTransaction): number {
  const baseAmount = state.transactionMainAmount(transaction);
  if (transaction.activity_kind === 'income') return baseAmount;
  if (transaction.activity_kind === 'expense' || transaction.activity_kind === 'debt_payment') {
    return -baseAmount;
  }
  if (transaction.activity_kind === 'investment_purchase') {
    return transaction.investment_direction === 'outflow' ? baseAmount : -baseAmount;
  }
  if (transaction.activity_kind === 'revaluation') {
    const linkedEntry = transaction.entries.find(
      (entry) => entry.asset_id != null || entry.liability_id != null,
    );
    if (!linkedEntry) return 0;
    return linkedEntry.side === 'debit' ? baseAmount : -baseAmount;
  }
  return 0;
}

function amountTone(transaction: LedgerTransaction): 'positive' | 'negative' | 'neutral' {
  const impact = signedImpactForRow(transaction);
  if (impact > 0) return 'positive';
  if (impact < 0) return 'negative';
  return 'neutral';
}

function originLabel(origin: LedgerTransaction['origin']): string {
  if (origin === 'import') return 'Importado';
  return origin;
}
</script>

<template>
  <section class="ui-section-card">
    <div class="ui-accounting-filters-floating">
      <div class="ui-accounting-filters-row">
        <input
          v-model="state.activityFilters.query"
          class="input"
          placeholder="Buscar..."
        />
        <select v-model="state.activityFilters.kind" class="select">
          <option value="all">Tipo</option>
          <option value="income">Ingresos</option>
          <option value="expense">Gastos</option>
          <option value="transfer">Transferencias</option>
          <option value="investment">Inversion</option>
          <option value="debt_payment">Pago deuda</option>
          <option value="revaluation">Revalorizaciones</option>
        </select>
        <select
          v-if="state.activityFilters.kind === 'income' || state.activityFilters.kind === 'expense'"
          v-model="state.activityFilters.categoryKey"
          class="select"
        >
          <option value="">Categoría</option>
          <option
            v-for="cat in state.filterCategoryOptions"
            :key="cat.value"
            :value="cat.value"
          >
            {{ cat.label }}
          </option>
        </select>
        <select
          v-if="state.filterSubcategoryOptions.length"
          v-model="state.activityFilters.subcategoryKey"
          class="select"
        >
          <option value="">Subcategoria</option>
          <option
            v-for="sub in state.filterSubcategoryOptions"
            :key="sub.value"
            :value="sub.value"
          >
            {{ sub.label }}
          </option>
        </select>
        <div class="ui-accounting-date-dropdown">
          <button
            type="button"
            class="ui-accounting-date-trigger"
            @click="toggleDateDropdown"
          >
            {{ activeDateLabel() }}
            <span class="ui-accounting-date-trigger-arrow">▾</span>
          </button>
          <div v-if="dateDropdownOpen" class="ui-accounting-date-menu">
            <button
              v-for="preset in state.datePresetOptions"
              :key="preset.value"
              type="button"
              class="ui-accounting-date-menu-item"
              :class="{ 'ui-accounting-date-menu-item-active': state.todosDatePreset === preset.value }"
              @click="selectDatePreset(preset.value)"
            >
              {{ preset.label }}
            </button>
            <template v-if="state.todosDatePreset === 'custom'">
              <div class="ui-accounting-date-menu-custom">
                <input v-model="state.todosDateFrom" type="date" class="input" title="Desde" />
                <input v-model="state.todosDateTo" type="date" class="input" title="Hasta" />
              </div>
            </template>
          </div>
        </div>
        <span class="ui-accounting-filters-count">
          {{ state.todosTransactions.length }} de {{ state.todosTotalCount }}
        </span>
      </div>
    </div>

    <div v-if="state.todosLoading && !state.todosTransactions.length" class="ui-section-loading">
      <div class="ui-import-spinner"></div>
      <span>Cargando movimientos...</span>
    </div>
    <div
      v-else-if="!state.todosTransactions.length"
      class="ui-state-block ui-state-empty ui-accounting-empty-state"
    >
      <p class="ui-state-title">Sin movimientos para estos filtros</p>
      <p class="ui-state-hint">Prueba otro periodo o ajusta la búsqueda para ver actividad.</p>
    </div>
    <ul v-else class="ui-entry-list">
      <li v-for="transaction in state.todosTransactions" :key="transaction.id" class="ui-entry-row">
        <span class="ui-entry-date">{{ state.formatDate(transaction.booking_date) }}</span>
        <div class="ui-entry-body">
          <strong class="ui-entry-desc">{{ transaction.description }}</strong>
          <div class="ui-action-bar ui-entry-meta">
            <span :class="`ui-type-badge ui-type-badge-${typeBadgeVariant(transaction)}`">
              {{ state.activityKindLabel(transaction) }}
            </span>
            <span class="ui-pro-chip ui-entry-chip">
              {{ state.transactionAccountTrailLabel(transaction) }}
            </span>
            <span
              v-if="state.transactionOwnershipLabel(transaction)"
              class="ui-pro-chip ui-entry-chip"
            >
              {{ state.transactionOwnershipLabel(transaction) }}
            </span>
            <span v-if="transaction.origin === 'import'" class="ui-pro-chip ui-entry-chip">
              {{ originLabel(transaction.origin) }}
            </span>
          </div>
          <span v-if="state.transactionClassificationLabel(transaction)" class="ui-entry-accounts">
            {{ state.transactionClassificationLabel(transaction) }}
          </span>
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
            class="icon-btn ui-accounting-entry-action-btn ui-entry-action-edit"
            type="button"
            title="Editar movimiento"
            aria-label="Editar movimiento"
            :disabled="state.transactionCreationLoading"
            @click="state.openEditTransactionModal(transaction.id)"
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
            v-if="transaction.origin !== 'system'"
            class="icon-btn ui-accounting-entry-action-btn ui-entry-action-delete"
            type="button"
            title="Eliminar movimiento"
            aria-label="Eliminar movimiento"
            :disabled="state.transactionCreationLoading"
            @click="state.deleteTransactionFromTimeline(transaction.id, transaction.description)"
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

    <div v-if="state.todosHasMore" class="ui-load-more">
      <button
        class="btn"
        type="button"
        :disabled="state.todosLoadingMore"
        @click="state.loadMoreTodos"
      >
        {{ state.todosLoadingMore ? 'Cargando...' : 'Cargar mas' }}
      </button>
    </div>
    <p v-else-if="state.todosTransactions.length" class="ui-load-more-hint">
      Todos los movimientos cargados
    </p>
  </section>
</template>
