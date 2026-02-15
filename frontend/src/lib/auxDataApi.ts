import { api } from '@/lib/api';

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

export const auxDataApi = {
  getFxRates() {
    return api.get('/api/core/fx-rates/');
  },
  getInflation() {
    return api.get('/api/core/inflation/');
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
