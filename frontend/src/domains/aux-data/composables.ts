import { computed, onMounted, ref } from 'vue';
import { auxDataApi } from '@/domains/aux-data/api';
import { toApiErrorMessage } from '@/lib/errors';
import type {
  FxRate,
  InflationIndex,
  MarketDataState,
  MarketDataStatus,
} from '@/domains/aux-data/types';

export function useAuxData() {
  const loading = ref(false);
  const error = ref<string | null>(null);
  const status = ref<MarketDataStatus | null>(null);

  const fxRates = computed<FxRate[]>(() => status.value?.datasets.fx.latest_rows ?? []);
  const inflation = computed<InflationIndex[]>(
    () => status.value?.datasets.inflation.latest_rows ?? [],
  );
  const fxStates = computed<MarketDataState[]>(() => status.value?.datasets.fx.states ?? []);
  const inflationStates = computed<MarketDataState[]>(
    () => status.value?.datasets.inflation.states ?? [],
  );
  const supportedInflationRegions = computed(() => status.value?.supported_inflation_regions ?? []);

  async function loadAll() {
    loading.value = true;
    error.value = null;
    try {
      const response = await auxDataApi.getStatus();
      status.value = response.data ?? null;
    } catch (e: unknown) {
      error.value = toApiErrorMessage(e);
    } finally {
      loading.value = false;
    }
  }

  function formatFxRate(rate: string, from: string, to: string) {
    const n = Number(String(rate ?? '').replace(',', '.'));
    if (!Number.isFinite(n)) return rate;
    if (from === 'BTC' && to === 'USD') return n.toFixed(2);
    if (from === 'ETH' && to === 'USD') return n.toFixed(2);
    if (from === 'USD' && to === 'EUR') return n.toFixed(4);
    return String(rate);
  }

  function formatInflationIndex(value: string) {
    const n = Number(String(value ?? '').replace(',', '.'));
    if (!Number.isFinite(n)) return value;
    return n.toFixed(3);
  }

  return {
    loading,
    error,
    status,
    fxRates,
    inflation,
    fxStates,
    inflationStates,
    supportedInflationRegions,
    loadAll,
    formatFxRate,
    formatInflationIndex,
  };
}

export function useAuxDataPage() {
  const state = useAuxData();
  onMounted(state.loadAll);
  return state;
}
