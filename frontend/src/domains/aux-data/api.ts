import { api } from '@/lib/api';
import type { MarketDataStatus } from '@/domains/aux-data/types';

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

export type AuxDataApiAdapter = {
  getStatus(): ReturnType<typeof api.get<MarketDataStatus>>;
};

export const coreAuxDataApi: AuxDataApiAdapter = {
  getStatus() {
    return api.get<MarketDataStatus>('/api/core/market-data/status/');
  },
};

export const auxDataApi: AuxDataApiAdapter = coreAuxDataApi;
