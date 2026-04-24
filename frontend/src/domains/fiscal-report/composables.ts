import { computed, onMounted } from 'vue';
import { useFiscalReportStore } from './store';

export function useFiscalReport() {
  const store = useFiscalReportStore();

  const selectedYear = computed({
    get: () => store.selectedYear,
    set: (value: number) => store.setSelectedYear(value),
  });

  onMounted(async () => {
    if (!store.initialized) {
      await store.initializeLanding();
    }
  });

  async function generate(year?: number) {
    if (typeof year === 'number') {
      store.setSelectedYear(year);
    }
    await store.generateReport();
  }

  return {
    store,
    selectedYear,
    generate,
  };
}

export function useBrokerSync() {
  const store = useFiscalReportStore();

  async function sync(credentialId: number, year?: number) {
    if (typeof year === 'number') {
      store.setSelectedYear(year);
    }
    await store.syncCredential(credentialId);
  }

  return {
    store,
    sync,
  };
}
