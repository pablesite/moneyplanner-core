import { api } from '@/lib/api';

export const coreNetWorthApi = {
  getSummary() {
    return api.get('/api/net-worth/summary/');
  },
  getAssets() {
    return api.get('/api/net-worth/assets/');
  },
  getLiabilities() {
    return api.get('/api/net-worth/liabilities/');
  },
  getSnapshots() {
    return api.get('/api/net-worth/snapshots/');
  },
  createSnapshotFromCurrent() {
    return api.post('/api/net-worth/snapshots/from-current/');
  },
  deleteSnapshot(id: number) {
    return api.delete(`/api/net-worth/snapshots/${id}/`);
  },
  createAsset(payload: Record<string, unknown>) {
    return api.post('/api/net-worth/assets/', payload);
  },
  updateAsset(id: number, payload: Record<string, unknown>) {
    return api.patch(`/api/net-worth/assets/${id}/`, payload);
  },
  createLiability(payload: Record<string, unknown>) {
    return api.post('/api/net-worth/liabilities/', payload);
  },
  updateLiability(id: number, payload: Record<string, unknown>) {
    return api.patch(`/api/net-worth/liabilities/${id}/`, payload);
  },
  getSettings() {
    return api.get('/api/auth/settings/');
  },
  updateSettings(payload: { base_currency: string }) {
    return api.put('/api/auth/settings/', payload);
  },
};
