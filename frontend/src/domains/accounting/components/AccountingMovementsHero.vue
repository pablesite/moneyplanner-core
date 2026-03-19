<script setup lang="ts">
import type { AccountingMovementsPageState } from '@/domains/accounting/useAccountingMovementsPage';

const props = defineProps<{ page: AccountingMovementsPageState }>();
const state = props.page;
</script>

<template>
  <section class="ui-section-card ui-accounting-hero-panel">
    <div class="ui-page-head">
      <div>
        <p class="ui-page-eyebrow">Accounting Movements</p>
        <h1 class="ui-accounting-hero-title">Libro diario operativo</h1>
      </div>
      <div class="ui-accounting-hero-right">
        <div class="ui-page-actions">
          <button
            class="btn"
            type="button"
            aria-label="Activar tracking contable"
            title="Activar tracking contable"
            :disabled="!state.hasAvailableManualPositions"
            @click="state.openActivationModal"
          >
            Activar tracking
          </button>
          <button
            class="btn"
            type="button"
            aria-label="Importar CSV MoneyWiz"
            title="Importar CSV MoneyWiz"
            @click="state.showMoneyWizImportModal = true"
          >
            Importar MoneyWiz
          </button>
          <button
            class="btn btn-primary ui-accounting-cta"
            type="button"
            aria-label="Registrar movimiento diario"
            title="Registrar movimiento diario"
            :disabled="!state.liquidityAccounts.length"
            @click="state.showQuickEntryModal = true"
          >
            + Registrar movimiento
          </button>
        </div>
      </div>
    </div>

    <div class="ui-accounting-net-kpi">
      <div class="ui-kpi-card ui-kpi-card-primary">
        <span class="ui-kpi-label">Saldo neto contable</span>
        <strong class="ui-kpi-value">{{ state.formatMoney(state.accountingNetBalance) }}</strong>
        <p class="ui-kpi-meta">Activo contable - Pasivo contable</p>
      </div>
    </div>

    <div v-if="state.error" class="ui-state-block ui-state-error">{{ state.error }}</div>
    <div v-if="state.successMessage" class="ui-state-block ui-state-success">
      {{ state.successMessage }}
    </div>
  </section>
</template>
