import { api } from '@/lib/api';
import type { Asset, Liability, NetWorthWritePayload, Snapshot, Summary } from '@/domains/net-worth/models';

type Settings = { base_currency: string };

export const coreNetWorthApi = {
  getSummary() {
    return api.get<Summary>('/api/net-worth/summary/');
  },
  getAssets() {
    return api.get<Asset[]>('/api/net-worth/assets/');
  },
  getLiabilities() {
    return api.get<Liability[]>('/api/net-worth/liabilities/');
  },
  getSnapshots() {
    return api.get<Snapshot[]>('/api/net-worth/snapshots/');
  },
  createSnapshotFromCurrent() {
    return api.post<Snapshot>('/api/net-worth/snapshots/from-current/');
  },
  deleteSnapshot(id: number) {
    return api.delete(`/api/net-worth/snapshots/${id}/`);
  },
  createAsset(payload: NetWorthWritePayload) {
    return api.post<Asset>('/api/net-worth/assets/', payload);
  },
  updateAsset(id: number, payload: NetWorthWritePayload) {
    return api.patch<Asset>(`/api/net-worth/assets/${id}/`, payload);
  },
  createLiability(payload: NetWorthWritePayload) {
    return api.post<Liability>('/api/net-worth/liabilities/', payload);
  },
  updateLiability(id: number, payload: NetWorthWritePayload) {
    return api.patch<Liability>(`/api/net-worth/liabilities/${id}/`, payload);
  },
  getSettings() {
    return api.get<Settings>('/api/auth/settings/');
  },
  updateSettings(payload: Settings) {
    return api.put<Settings>('/api/auth/settings/', payload);
  },
};
