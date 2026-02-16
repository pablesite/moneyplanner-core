import { computed, ref } from 'vue';
import { auxDataApi } from '@/domains/aux-data/api';
import { toApiErrorMessage } from '@/lib/errors';
import type { FxPair, FxRate, InflationIndex } from '@/domains/aux-data/types';

export function useAuxData() {
  const loading = ref(false);
  const error = ref<string | null>(null);

  const fxRates = ref<FxRate[]>([]);
  const inflation = ref<InflationIndex[]>([]);

  const fxForm = ref({
    rate_date: '',
    pair: 'USD_EUR',
    rate: '',
  });

  const fxPairs: FxPair[] = [
    { value: 'BTC_USD', label: 'BTC -> USD', from: 'BTC', to: 'USD', hint: '70000' },
    { value: 'ETH_USD', label: 'ETH -> USD', from: 'ETH', to: 'USD', hint: '2000' },
    { value: 'USD_EUR', label: 'USD -> EUR', from: 'USD', to: 'EUR', hint: '0.92' },
  ];

  const fxRatePlaceholder = computed(() => {
    const pair = fxPairs.find((p) => p.value === fxForm.value.pair);
    return pair?.hint ?? '0.00';
  });

  const ipcForm = ref({
    region: 'ES',
    period: '',
    index: '',
  });

  async function loadAll() {
    loading.value = true;
    error.value = null;
    try {
      const [fxRes, ipcRes] = await Promise.all([auxDataApi.getFxRates(), auxDataApi.getInflation()]);
      fxRates.value = fxRes.data ?? [];
      inflation.value = ipcRes.data ?? [];
    } catch (e: unknown) {
      error.value = toApiErrorMessage(e);
    } finally {
      loading.value = false;
    }
  }

  async function createFxRate() {
    if (!fxForm.value.rate_date || !fxForm.value.pair || !fxForm.value.rate) return;
    loading.value = true;
    error.value = null;
    const pair = fxPairs.find((p) => p.value === fxForm.value.pair);
    if (!pair) return;
    try {
      await auxDataApi.createFxRate({
        rate_date: fxForm.value.rate_date,
        from_currency: pair.from,
        to_currency: pair.to,
        rate: fxForm.value.rate,
      });
      fxForm.value.rate = '';
      await loadAll();
    } catch (e: unknown) {
      error.value = toApiErrorMessage(e);
    } finally {
      loading.value = false;
    }
  }

  async function deleteFxRate(id: number) {
    if (!confirm('Eliminar este FX rate?')) return;
    loading.value = true;
    error.value = null;
    try {
      await auxDataApi.deleteFxRate(id);
      await loadAll();
    } catch (e: unknown) {
      error.value = toApiErrorMessage(e);
    } finally {
      loading.value = false;
    }
  }

  async function createInflation() {
    if (!ipcForm.value.region || !ipcForm.value.period || !ipcForm.value.index) return;
    loading.value = true;
    error.value = null;
    const monthValue = ipcForm.value.period;
    const period = monthValue.includes('-') ? `${monthValue}-01` : monthValue;
    try {
      await auxDataApi.createInflation({
        region: ipcForm.value.region,
        period,
        index: ipcForm.value.index,
      });
      ipcForm.value.index = '';
      await loadAll();
    } catch (e: unknown) {
      error.value = toApiErrorMessage(e);
    } finally {
      loading.value = false;
    }
  }

  async function deleteInflation(id: number) {
    if (!confirm('Eliminar este IPC?')) return;
    loading.value = true;
    error.value = null;
    try {
      await auxDataApi.deleteInflation(id);
      await loadAll();
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
    return n.toFixed(1);
  }

  return {
    loading,
    error,
    fxRates,
    inflation,
    fxForm,
    fxPairs,
    fxRatePlaceholder,
    ipcForm,
    loadAll,
    createFxRate,
    deleteFxRate,
    createInflation,
    deleteInflation,
    formatFxRate,
    formatInflationIndex,
  };
}
