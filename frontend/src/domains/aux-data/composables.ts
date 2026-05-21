import { onMounted, ref } from 'vue';
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
  const syncError = ref<string | null>(null);
  const syncSuccess = ref<string | null>(null);
  const syncingInflation = ref(false);
  const syncingFx = ref(false);
  const status = ref<MarketDataStatus | null>(null);

  const fxStates = ref<MarketDataState[]>([]);
  const inflationStates = ref<MarketDataState[]>([]);
  const supportedInflationRegions = ref<{ code: string; label: string }[]>([]);

  const inflation = ref<InflationIndex[]>([]);
  const inflationPage = ref(1);
  const inflationHasMore = ref(true);
  const inflationLoadingMore = ref(false);

  const fxRates = ref<FxRate[]>([]);
  const fxPage = ref(1);
  const fxHasMore = ref(true);
  const fxLoadingMore = ref(false);

  async function loadAll() {
    inflation.value = [];
    inflationPage.value = 1;
    inflationHasMore.value = true;
    fxRates.value = [];
    fxPage.value = 1;
    fxHasMore.value = true;

    loading.value = true;
    error.value = null;
    try {
      const response = await auxDataApi.getStatus();
      const data = response.data ?? null;
      status.value = data;
      fxStates.value = data?.datasets.fx.states ?? [];
      inflationStates.value = data?.datasets.inflation.states ?? [];
      supportedInflationRegions.value = data?.supported_inflation_regions ?? [];
    } catch (e: unknown) {
      error.value = toApiErrorMessage(e);
    } finally {
      loading.value = false;
    }

    await Promise.all([loadMoreInflation(), loadMoreFx()]);
  }

  async function syncInflationNow() {
    syncingInflation.value = true;
    syncError.value = null;
    syncSuccess.value = null;
    try {
      const response = await auxDataApi.syncMarketData({ datasets: ['inflation'], mode: 'reconcile' });
      const rows = response.data?.summary?.inflation ?? 0;
      syncSuccess.value = `Sincronizacion IPC completada (${rows} filas actualizadas).`;
      await loadAll();
    } catch (e: unknown) {
      syncError.value = toApiErrorMessage(e);
    } finally {
      syncingInflation.value = false;
    }
  }

  async function syncFxHistoryNow() {
    syncingFx.value = true;
    syncError.value = null;
    syncSuccess.value = null;
    try {
      const response = await auxDataApi.syncMarketData({
        datasets: ['fx'],
        mode: 'reconcile',
        fx_full_history: true,
      });
      const rows = response.data?.summary?.fx ?? 0;
      syncSuccess.value = `Sincronizacion FX completada (${rows} filas actualizadas).`;
      await loadAll();
    } catch (e: unknown) {
      syncError.value = toApiErrorMessage(e);
    } finally {
      syncingFx.value = false;
    }
  }

  async function loadMoreInflation() {
    if (!inflationHasMore.value || inflationLoadingMore.value) return;
    inflationLoadingMore.value = true;
    try {
      const res = await auxDataApi.getInflationPage(inflationPage.value);
      inflation.value.push(...(res.data?.results ?? []));
      inflationHasMore.value = res.data?.next != null;
      inflationPage.value += 1;
    } catch {
      // silently stop
    } finally {
      inflationLoadingMore.value = false;
    }
  }

  async function loadMoreFx() {
    if (!fxHasMore.value || fxLoadingMore.value) return;
    fxLoadingMore.value = true;
    try {
      const res = await auxDataApi.getFxRatesPage(fxPage.value);
      fxRates.value.push(...(res.data?.results ?? []));
      fxHasMore.value = res.data?.next != null;
      fxPage.value += 1;
    } catch {
      // silently stop
    } finally {
      fxLoadingMore.value = false;
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
    syncError,
    syncSuccess,
    syncingInflation,
    syncingFx,
    status,
    fxRates,
    fxHasMore,
    fxLoadingMore,
    inflation,
    inflationHasMore,
    inflationLoadingMore,
    fxStates,
    inflationStates,
    supportedInflationRegions,
    loadAll,
    loadMoreInflation,
    loadMoreFx,
    syncInflationNow,
    syncFxHistoryNow,
    formatFxRate,
    formatInflationIndex,
  };
}

export function useAuxDataPage() {
  const state = useAuxData();
  onMounted(state.loadAll);
  return state;
}
