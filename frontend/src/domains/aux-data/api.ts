import { api } from '@/lib/api';
import type { FxRate, InflationIndex, MarketDataStatus } from '@/domains/aux-data/types';

export type CreateFxRatePayload = {
  rate_date: string;
  from_currency: string;
  to_currency: string;
  rate: string;
};

export type CreateInflationPayload = {
  region: string;
  period: string;
  index: string;
};

export type PagedResponse<T> = {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
};

export type AuxDataApiAdapter = {
  getStatus(): ReturnType<typeof api.get<MarketDataStatus>>;
  getInflationPage(page: number): ReturnType<typeof api.get<PagedResponse<InflationIndex>>>;
  getFxRatesPage(page: number): ReturnType<typeof api.get<PagedResponse<FxRate>>>;
};

export const coreAuxDataApi: AuxDataApiAdapter = {
  getStatus() {
    return api.get<MarketDataStatus>('/api/core/market-data/status/');
  },
  getInflationPage(page: number) {
    return api.get<PagedResponse<InflationIndex>>('/api/core/inflation/', { params: { page } });
  },
  getFxRatesPage(page: number) {
    return api.get<PagedResponse<FxRate>>('/api/core/fx-rates/', { params: { page } });
  },
};

export const auxDataApi: AuxDataApiAdapter = coreAuxDataApi;
