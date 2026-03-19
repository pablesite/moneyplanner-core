<script setup lang="ts">
import type { AccountingMovementsPageState } from '@/domains/accounting/useAccountingMovementsPage';

const props = defineProps<{ page: AccountingMovementsPageState }>();
const state = props.page;
</script>

<template>
  <section class="ui-section-card">
    <div class="ui-section-head">
      <div class="ui-section-copy">
        <h2 class="ui-section-title">Estad�sticas</h2>
      </div>
      <div class="ui-period-bar">
        <label class="ui-period-field">
          <span>Ejercicio</span>
          <select
            v-model="state.selectedYear"
            class="select ui-period-select"
            @change="state.reloadPeriod"
          >
            <option v-for="year in state.yearOptions" :key="year" :value="year">{{ year }}</option>
          </select>
        </label>
      </div>
    </div>

    <div class="ui-kpi-strip ui-kpi-strip-2col">
      <div class="ui-kpi-card">
        <span class="ui-kpi-label">Activos</span>
        <strong class="ui-kpi-value">{{ state.formatMoney(state.accountingAssetsTotal) }}</strong>
        <p class="ui-kpi-meta">{{ (state.accountsByType.get('asset') ?? []).length }} cuentas</p>
      </div>
      <div class="ui-kpi-card">
        <span class="ui-kpi-label">Pasivos</span>
        <strong class="ui-kpi-value">{{
          state.formatMoney(state.accountingLiabilitiesTotal)
        }}</strong>
        <p class="ui-kpi-meta">
          {{ (state.accountsByType.get('liability') ?? []).length }} cuentas
        </p>
      </div>
    </div>

    <div v-if="state.summaryRows.length" class="ui-cashflow-strip">
      <div v-for="row in state.summaryRows" :key="row.month" class="ui-cashflow-month">
        <span class="ui-cashflow-month-label">{{ state.monthLabel(row.month) }}</span>
        <strong
          class="ui-cashflow-month-value"
          :class="
            row.incomeValue - row.expenseValue >= 0
              ? 'ui-cashflow-positive'
              : 'ui-cashflow-negative'
          "
        >
          {{ state.formatMoney(row.incomeValue - row.expenseValue) }}
        </strong>
        <small class="ui-cashflow-month-meta">
          I {{ state.formatMoney(row.incomeValue) }} / G {{ state.formatMoney(row.expenseValue) }}
        </small>
      </div>
    </div>

    <p class="ui-page-lead">
      Este saldo solo incluye cuentas contables activas en esta vista. No incluye vivienda,
      mobiliario u otros activos fuera del ledger.
    </p>

    <details v-if="state.hasTechnicalAccounts" class="ui-ledger-technical">
      <summary>Contrapartidas tecnicas del sistema</summary>
      <p class="ui-page-lead">
        Estas cuentas siguen existiendo por compatibilidad interna, pero no forman parte del
        catalogo operativo que se gestiona manualmente.
      </p>
      <section
        v-for="type in state.technicalAccountTypeOptions"
        :key="type.value"
        class="ui-ledger-technical-group"
      >
        <div class="ui-section-head ui-ledger-technical-head">
          <strong>{{ type.label }}</strong>
          <span class="ui-pro-chip">{{ state.accountsByType.get(type.value)?.length ?? 0 }}</span>
        </div>
        <ul v-if="(state.accountsByType.get(type.value)?.length ?? 0) > 0" class="ui-entry-list">
          <li
            v-for="account in state.accountsByType.get(type.value)"
            :key="account.id"
            class="ui-entry-row"
          >
            <div class="ui-ledger-account-meta ui-ledger-account-meta-stretch">
              <strong>{{ account.name }}</strong>
              <div class="ui-action-bar ui-ledger-account-chips">
                <span class="ui-pro-chip">{{ account.currency }}</span>
                <span class="ui-pro-chip">{{ account.origin }}</span>
              </div>
            </div>
            <div class="ui-ledger-account-info">
              <span>{{ state.formatCompact(account.current_balance, account.currency) }}</span>
              <button
                v-if="account.asset_id != null || account.liability_id != null"
                class="icon-btn"
                type="button"
                title="Quitar tracking"
                :disabled="state.accountActivationLoading || state.accountCreationLoading"
                @click="state.removeNetWorthTracking(account)"
              >
                ??
              </button>
              <button
                v-if="account.origin === 'user'"
                class="icon-btn"
                type="button"
                title="Eliminar cuenta"
                :disabled="state.accountCreationLoading"
                @click="state.deleteAccount(account.id, account.name)"
              >
                ???
              </button>
            </div>
          </li>
        </ul>
      </section>
    </details>
  </section>
</template>
