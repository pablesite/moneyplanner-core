import { api, coreApi } from '@/lib/api';
import type {
  Asset,
  Liability,
  NetWorthWritePayload,
  Ownership,
  Snapshot,
  Summary,
} from '@/domains/net-worth/models';
import type { OwnershipLink } from '@/domains/net-worth/ownership';

type TargetType = 'asset' | 'liability';
type Settings = { base_currency: string };
type OwnershipSyncPayload = {
  target_type: TargetType;
  target_id: number;
  ownership_id: number | null;
};

export const coreNetWorthApi = {
  getSummary() {
    return coreApi.get<Summary>('/api/net-worth/summary/');
  },
  getAssets() {
    return coreApi.get<Asset[]>('/api/net-worth/assets/');
  },
  getLiabilities() {
    return coreApi.get<Liability[]>('/api/net-worth/liabilities/');
  },
  getSnapshots() {
    return coreApi.get<Snapshot[]>('/api/net-worth/snapshots/');
  },
  createSnapshotFromCurrent() {
    return coreApi.post<Snapshot>('/api/net-worth/snapshots/from-current/');
  },
  deleteSnapshot(id: number) {
    return coreApi.delete(`/api/net-worth/snapshots/${id}/`);
  },
  createAsset(payload: NetWorthWritePayload) {
    return coreApi.post<Asset>('/api/net-worth/assets/', payload);
  },
  updateAsset(id: number, payload: NetWorthWritePayload) {
    return coreApi.patch<Asset>(`/api/net-worth/assets/${id}/`, payload);
  },
  createLiability(payload: NetWorthWritePayload) {
    return coreApi.post<Liability>('/api/net-worth/liabilities/', payload);
  },
  updateLiability(id: number, payload: NetWorthWritePayload) {
    return coreApi.patch<Liability>(`/api/net-worth/liabilities/${id}/`, payload);
  },
  getSettings() {
    return coreApi.get<Settings>('/api/auth/settings/');
  },
  updateSettings(payload: Settings) {
    return coreApi.put<Settings>('/api/auth/settings/', payload);
  },
};

export const premiumOwnershipApi = {
  getOwnerships() {
    return api.get<Ownership[]>('/api/ownerships/');
  },
  getOwnershipLinks() {
    return api.get<OwnershipLink[]>('/api/ownership-links/');
  },
  syncOwnershipLink(payload: OwnershipSyncPayload) {
    return api.post('/api/ownership-links/sync/', payload);
  },
};
