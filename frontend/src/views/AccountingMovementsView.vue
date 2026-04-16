<script setup lang="ts">
import { nextTick, onMounted } from 'vue';
import { useRoute } from 'vue-router';
import '@/domains/accounting/styles/movements.css';
import { useAccountingMovementsPage } from '@/domains/accounting/useAccountingMovementsPage';
import AccountingMovementsHero from '@/domains/accounting/components/AccountingMovementsHero.vue';
import AccountingAccountCatalog from '@/domains/accounting/components/AccountingAccountCatalog.vue';
import AccountingMovementsAllTransactions from '@/domains/accounting/components/AccountingMovementsAllTransactions.vue';
import AccountingBalances from '@/domains/accounting/components/AccountingBalances.vue';
import AccountingMovementsActivationModal from '@/domains/accounting/components/AccountingMovementsActivationModal.vue';
import AccountingMovementsEditTransactionModal from '@/domains/accounting/components/AccountingMovementsEditTransactionModal.vue';
import AccountingMovementsQuickEntryModal from '@/domains/accounting/components/AccountingMovementsQuickEntryModal.vue';

const route = useRoute();
const page = useAccountingMovementsPage();

onMounted(async () => {
  const { tab, date_from, date_to, kind, category_key, subcategory_key } = route.query;
  if (tab === 'todos') {
    page.activeTab = 'todos';
  }
  if (date_from || date_to) {
    page.todosDatePreset = 'custom';
    page.todosDateFrom = String(date_from ?? '');
    page.todosDateTo = String(date_to ?? '');
  }
  if (kind && kind !== 'all') {
    page.activityFilters.kind = String(kind) as typeof page.activityFilters.kind;
    // Wait for the watcher on filterCategoryOptions (triggered by kind change) to fire
    // before setting categoryKey, otherwise it would be cleared.
    await nextTick();
  }
  if (category_key) {
    page.activityFilters.categoryKey = String(category_key);
    // Wait for the watcher on categoryKey (which resets subcategoryKey) to fire
    // before setting subcategoryKey.
    await nextTick();
  }
  if (subcategory_key) {
    page.activityFilters.subcategoryKey = String(subcategory_key);
  }
});
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
        <button
          v-if="page.activeTab === 'cuentas' && page.hasAvailableManualPositions"
          class="btn ui-accounting-cta-secondary"
          type="button"
          aria-label="Añadir cuenta al libro contable"
          title="Añadir cuenta al libro contable"
          @click="page.openActivationModal"
        >
          ⊕
        </button>
        <button
          class="btn btn-primary ui-accounting-cta"
          type="button"
          aria-label="Registrar movimiento diario"
          title="Registrar movimiento diario"
          :disabled="!page.liquidityAccounts.length"
          @click="page.showQuickEntryModal = true"
        >
          +
        </button>
      </div>
      <AccountingAccountCatalog v-if="page.activeTab === 'cuentas'" :page="page" />
      <AccountingMovementsAllTransactions v-else-if="page.activeTab === 'todos'" :page="page" />
      <AccountingBalances v-else-if="page.activeTab === 'estadisticas'" :page="page" />
    </div>

    <AccountingMovementsActivationModal :page="page" />
    <AccountingMovementsEditTransactionModal :page="page" />
    <AccountingMovementsQuickEntryModal :page="page" />
  </div>
</template>
