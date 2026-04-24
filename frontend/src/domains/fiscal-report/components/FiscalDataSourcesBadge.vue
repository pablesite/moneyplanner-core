<script setup lang="ts">
import { computed } from 'vue';
import type { FiscalDataSources } from '@/domains/fiscal-report/api';

const props = defineProps<{
  dataSources: FiscalDataSources;
}>();

const text = computed(() => {
  const apiParts = [
    props.dataSources.pionex_api ? 'Pionex API ✓' : 'Pionex API -',
    props.dataSources.binance_api ? 'Binance API ✓' : 'Binance API -',
  ];
  const csvFallback = [
    ...props.dataSources.pionex_csv_fallback.map((item) => `pionex:${item}`),
    ...props.dataSources.binance_csv_fallback.map((item) => `binance:${item}`),
  ];
  return `Datos: ${apiParts.join(' | ')} · CSV fallback: ${
    csvFallback.length ? csvFallback.join(', ') : 'ninguno'
  }`;
});
</script>

<template>
  <div class="badge fiscal-data-source-badge" :title="text">
    {{ text }}
  </div>
</template>
