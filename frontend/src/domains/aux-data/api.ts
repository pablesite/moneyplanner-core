import { api } from '@/lib/api';
import type { FxRate, InflationIndex } from '@/domains/aux-data/types';

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
  getFxRates(): ReturnType<typeof api.get<FxRate[]>>;
  getInflation(): ReturnType<typeof api.get<InflationIndex[]>>;
  createFxRate(payload: CreateFxRatePayload): ReturnType<typeof api.post>;
  deleteFxRate(id: number): ReturnType<typeof api.delete>;
  createInflation(payload: CreateInflationPayload): ReturnType<typeof api.post>;
  deleteInflation(id: number): ReturnType<typeof api.delete>;
};

export const coreAuxDataApi: AuxDataApiAdapter = {
  getFxRates() {
    return api.get<FxRate[]>('/api/core/fx-rates/');
  },
  getInflation() {
    return api.get<InflationIndex[]>('/api/core/inflation/');
  },
  createFxRate(payload: CreateFxRatePayload) {
    return api.post('/api/core/fx-rates/', payload);
  },
  deleteFxRate(id: number) {
    return api.delete(`/api/core/fx-rates/${id}/`);
  },
  createInflation(payload: CreateInflationPayload) {
    return api.post('/api/core/inflation/', payload);
  },
  deleteInflation(id: number) {
    return api.delete(`/api/core/inflation/${id}/`);
  },
};

export const auxDataApi: AuxDataApiAdapter = coreAuxDataApi;
