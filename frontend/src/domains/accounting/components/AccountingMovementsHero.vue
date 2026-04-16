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
