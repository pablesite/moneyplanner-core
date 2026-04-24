<script setup lang="ts">
import { computed } from 'vue';
import { useFiscalReport, useBrokerSync } from '@/domains/fiscal-report/composables';
import FiscalCredentialForm from '@/domains/fiscal-report/components/FiscalCredentialForm.vue';
import FiscalAccountList from '@/domains/fiscal-report/components/FiscalAccountList.vue';
import FiscalLatestImports from '@/domains/fiscal-report/components/FiscalLatestImports.vue';
import FiscalCsvImport from '@/domains/fiscal-report/components/FiscalCsvImport.vue';
import SyncRunHistoryTable from '@/domains/fiscal-report/components/SyncRunHistoryTable.vue';
import SyncRunDetailPanel from '@/domains/fiscal-report/components/SyncRunDetailPanel.vue';
import BalanceReconciliationTable from '@/domains/fiscal-report/components/BalanceReconciliationTable.vue';
import type { BrokerCsvFileType, BrokerName } from '@/domains/fiscal-report/api';

const { store, selectedYear } = useFiscalReport();
const { sync } = useBrokerSync();

const canShowContent = computed(() => store.initialized && !store.loadingCredentials);
const availableYears = computed(() => {
  const current = new Date().getFullYear();
  return Array.from({ length: 6 }, (_, index) => current - index);
});

async function onCredentialSubmit(payload: {
  broker: BrokerName;
  label: string;
  ownership_id: number;
  api_key: string;
  api_secret: string;
}) {
  await store.createCredential(payload);
}

async function onCredentialDelete(credentialId: number) {
  const confirmed = window.confirm('¿Eliminar credencial?');
  if (!confirmed) return;
  await store.deleteCredential(credentialId);
}

async function onSyncCredential(credentialId: number) {
  await sync(credentialId, selectedYear.value);
}

async function onOpenSyncRun(syncRunId: number) {
  await store.openSyncRun(syncRunId);
}

async function onRefreshDrilldown() {
  await store.fetchActiveRunDrilldown();
}

function onYearChange(event: Event) {
  const target = event.target as HTMLSelectElement;
  selectedYear.value = Number(target.value);
  void store.fetchSyncRuns();
}

async function onCsvSubmit(payload: {
  broker: BrokerName;
  file_type: BrokerCsvFileType;
  files: File[];
}) {
  for (const file of payload.files) {
    await store.importCsv({
      broker: payload.broker,
      file_type: payload.file_type,
      file,
    });
  }
}
</script>

<template>
  <div class="container ui-page-shell fiscal-page-shell">
    <header class="ui-page-head">
      <div class="ui-section-copy">
        <p class="ui-page-eyebrow">Informe Fiscal Crypto</p>
        <h1 class="ui-page-title">Integraciones de broker</h1>
        <p class="ui-page-lead">
          Gestiona credenciales, lanza sync y prepara datos antes de generar el informe anual.
        </p>
      </div>
      <div class="ui-section-actions">
        <select class="select fiscal-year-select" :value="selectedYear" @change="onYearChange">
          <option v-for="year in availableYears" :key="year" :value="year">{{ year }}</option>
        </select>
      </div>
    </header>

    <div v-if="store.loadingCredentials" class="ui-state-block ui-state-loading">
      Cargando configuración fiscal...
    </div>
    <div v-else-if="store.landingError" class="ui-state-block ui-state-error">
      {{ store.landingError }}
    </div>

    <div v-if="store.successMessage" class="ui-state-block ui-state-success">
      {{ store.successMessage }}
    </div>

    <template v-if="canShowContent">
      <FiscalCredentialForm
        :ownership-options="store.ownershipOptions"
        :creating="store.creatingCredential"
        @submit="onCredentialSubmit"
      />

      <FiscalAccountList
        :credentials="store.credentials"
        :sync-status-by-credential="store.syncStatusByCredential"
        :sync-runs-by-credential="store.lastSyncRunByCredential"
        :syncing-by-credential="store.syncingByCredential"
        :deleting-by-credential="store.deletingByCredential"
        @sync="onSyncCredential"
        @remove="onCredentialDelete"
      />

      <FiscalLatestImports
        :credentials="store.credentials"
        :sync-status-by-credential="store.syncStatusByCredential"
      />

      <SyncRunHistoryTable
        :rows="store.syncRuns"
        :loading="store.loadingSyncRuns"
        :active-run-id="store.activeSyncRunId"
        @open="onOpenSyncRun"
      />

      <SyncRunDetailPanel
        :active-run="store.activeSyncRun"
        :loading="store.loadingSyncRunDrilldown"
        :filters="store.syncRunFilters"
        :trades="store.syncRunTrades"
        :trades-count="store.syncRunTradesCount"
        :income-events="store.syncRunIncomeEvents"
        :income-events-count="store.syncRunIncomeEventsCount"
        :bot-results="store.syncRunBotResults"
        :bot-results-count="store.syncRunBotResultsCount"
        @update-filters="store.setSyncRunFilters"
        @refresh="onRefreshDrilldown"
      />

      <BalanceReconciliationTable
        :rows="store.balanceReconciliation"
        :loading="store.loadingSyncRuns || store.loadingBalanceReconciliation"
      />

      <FiscalCsvImport
        :importing="store.importingCsv"
        :results="store.csvImportResults"
        @submit="onCsvSubmit"
      />
    </template>
  </div>
</template>
