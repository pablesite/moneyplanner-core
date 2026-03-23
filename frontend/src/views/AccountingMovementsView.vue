<script setup lang="ts">
import '@/domains/accounting/styles/movements.css';
import { useAccountingMovementsPage } from '@/domains/accounting/useAccountingMovementsPage';
import AccountingMovementsHero from '@/domains/accounting/components/AccountingMovementsHero.vue';
import AccountingAccountCatalog from '@/domains/accounting/components/AccountingAccountCatalog.vue';
import AccountingMovementsAllTransactions from '@/domains/accounting/components/AccountingMovementsAllTransactions.vue';
import AccountingBalances from '@/domains/accounting/components/AccountingBalances.vue';
import AccountingMovementsActivationModal from '@/domains/accounting/components/AccountingMovementsActivationModal.vue';
import AccountingMovementsEditTransactionModal from '@/domains/accounting/components/AccountingMovementsEditTransactionModal.vue';
import AccountingMovementsMoneyWizModal from '@/domains/accounting/components/AccountingMovementsMoneyWizModal.vue';
import AccountingMovementsQuickEntryModal from '@/domains/accounting/components/AccountingMovementsQuickEntryModal.vue';

const page = useAccountingMovementsPage();
</script>

<template>
  <div class="container ui-page-shell">
    <AccountingMovementsHero :page="page" />

    <div class="ui-section-card ui-accounting-unified-card">
      <div class="ui-accounting-incard-tabs">
        <div class="ui-view-tabs">
          <button
            class="ui-view-tab"
            :class="{ 'ui-view-tab-active': page.activeTab === 'cuentas' }"
            type="button"
            @click="page.activeTab = 'cuentas'"
          >
            Cuentas
          </button>
          <button
            class="ui-view-tab"
            :class="{ 'ui-view-tab-active': page.activeTab === 'todos' }"
            type="button"
            @click="page.activeTab = 'todos'"
          >
            Todos los movimientos
          </button>
          <button
            class="ui-view-tab"
            :class="{ 'ui-view-tab-active': page.activeTab === 'estadisticas' }"
            type="button"
            @click="page.activeTab = 'estadisticas'"
          >
            Estadisticas
          </button>
        </div>
      </div>
      <AccountingAccountCatalog v-if="page.activeTab === 'cuentas'" :page="page" />
      <AccountingMovementsAllTransactions v-else-if="page.activeTab === 'todos'" :page="page" />
      <AccountingBalances v-else-if="page.activeTab === 'estadisticas'" :page="page" />
    </div>

    <AccountingMovementsActivationModal :page="page" />
    <AccountingMovementsEditTransactionModal :page="page" />
    <AccountingMovementsMoneyWizModal :page="page" :show-unmapped-categories="true" />
    <AccountingMovementsQuickEntryModal :page="page" />
  </div>
</template>
