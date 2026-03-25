import { coreApi } from '@/lib/api';
import type {
  Asset,
  AssetValuation,
  InvestmentAssetEvent,
  Liability,
  LiabilityEvent,
  LiabilityValuation,
  LiquidityAssetEvent,
  NetWorthTimeline,
  NetWorthWritePayload,
  Ownership,
  PositionTimeline,
  Settings,
  Summary,
} from '@/domains/net-worth/models';
import type { OwnershipLink } from '@/domains/net-worth/ownership';

type TargetType = 'asset' | 'liability';
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
  getTimeline(params?: { asset_category?: string | null; liability_category?: string | null }) {
    return coreApi.get<NetWorthTimeline>('/api/net-worth/timeline/', {
      params:
        params?.asset_category || params?.liability_category
          ? {
              ...(params?.asset_category ? { asset_category: params.asset_category } : {}),
              ...(params?.liability_category
                ? { liability_category: params.liability_category }
                : {}),
            }
          : undefined,
    });
  },
  getAssetTimeline(id: number) {
    return coreApi.get<PositionTimeline>(`/api/net-worth/assets/${id}/timeline/`);
  },
  getLiabilityTimeline(id: number) {
    return coreApi.get<PositionTimeline>(`/api/net-worth/liabilities/${id}/timeline/`);
  },
  getAssetValuations() {
    return coreApi.get<AssetValuation[]>('/api/net-worth/asset-valuations/');
  },
  getLiabilityValuations() {
    return coreApi.get<LiabilityValuation[]>('/api/net-worth/liability-valuations/');
  },
  getInvestmentEvents() {
    return coreApi.get<InvestmentAssetEvent[]>('/api/net-worth/investment-events/');
  },
  getLiquidityEvents() {
    return coreApi.get<LiquidityAssetEvent[]>('/api/net-worth/liquidity-events/');
  },
  getLiabilityEvents() {
    return coreApi.get<LiabilityEvent[]>('/api/net-worth/liability-events/');
  },
  createAsset(payload: NetWorthWritePayload) {
    return coreApi.post<Asset>('/api/net-worth/assets/', payload);
  },
  updateAsset(id: number, payload: NetWorthWritePayload) {
    return coreApi.patch<Asset>(`/api/net-worth/assets/${id}/`, payload);
  },
  deleteAsset(id: number) {
    return coreApi.delete(`/api/net-worth/assets/${id}/`);
  },
  createLiability(payload: NetWorthWritePayload) {
    return coreApi.post<Liability>('/api/net-worth/liabilities/', payload);
  },
  updateLiability(id: number, payload: NetWorthWritePayload) {
    return coreApi.patch<Liability>(`/api/net-worth/liabilities/${id}/`, payload);
  },
  deleteLiability(id: number) {
    return coreApi.delete(`/api/net-worth/liabilities/${id}/`);
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
    return coreApi.get<Ownership[]>('/api/ownerships/');
  },
  getOwnershipLinks() {
    return coreApi.get<OwnershipLink[]>('/api/ownership-links/');
  },
  syncOwnershipLink(payload: OwnershipSyncPayload) {
    return coreApi.post('/api/ownership-links/sync/', payload);
  },
};
