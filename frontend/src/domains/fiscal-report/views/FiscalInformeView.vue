<script setup lang="ts">
import { useFiscalReport } from '@/domains/fiscal-report/composables';
import FiscalReportView from '@/domains/fiscal-report/components/FiscalReportView.vue';

const { store, selectedYear, generate } = useFiscalReport();

async function onGenerate(year: number) {
  await generate(year);
}

function onUpdateYear(year: number) {
  selectedYear.value = year;
}
</script>

<template>
  <div class="container ui-page-shell fiscal-page-shell">
    <header class="ui-page-head">
      <div class="ui-section-copy">
        <p class="ui-page-eyebrow">Informe Fiscal Crypto</p>
        <h1 class="ui-page-title">Informe anual</h1>
        <p class="ui-page-lead">
          Visualiza capital mobiliario, transmisiones FIFO, bots y futuros en formato de
          declaración.
        </p>
      </div>
    </header>

    <FiscalReportView
      :report="store.report"
      :loading="store.loadingReport"
      :error="store.reportError"
      :selected-year="store.selectedYear"
      @generate="onGenerate"
      @update-year="onUpdateYear"
    />
  </div>
</template>
