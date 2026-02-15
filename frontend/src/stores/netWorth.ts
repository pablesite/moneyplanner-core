import { defineStore } from 'pinia';
import { coreNetWorthApi } from '@/lib/netWorthApi';
import { buildByCategoryChart } from '@/lib/netWorthCharts';

export type Asset = {
  id: number;
  name: string;
  category: string;
  subcategory: string;
  tracking_mode: string;
  accounting_account_id: number | null;
  currency: string;
  amount: string;
  amount_base?: string;
  is_active: boolean;
  notes: string;
};

export type Liability = Asset;

export type Snapshot = {
  id: number;
  snapshot_date: string;
  base_currency: string;
  total_assets: string;
  total_liabilities: string;
  net_worth: string;
  created_at: string;
};

export type Summary = {
  base_currency: string;
  total_assets: string;
  total_liabilities: string;
  net_worth: string;
  assets_by_category: Record<string, string>;
  assets_by_subcategory: Record<string, string>;
  liabilities_by_category: Record<string, string>;
  inflation_region: string | null;
  inflation_base_period: string | null;
  total_assets_real: string | null;
  total_liabilities_real: string | null;
  net_worth_real: string | null;
  assets_by_category_real: Record<string, string> | null;
  liabilities_by_category_real: Record<string, string> | null;
};

export const useNetWorthStore = defineStore('netWorth', {
  state: () => ({
    loading: false as boolean,
    error: null as string | null,
    baseCurrency: null as string | null,
    summary: null as Summary | null,
    assets: [] as Asset[],
    liabilities: [] as Liability[],
    snapshots: [] as Snapshot[],
  }),

  getters: {
    byCategoryChart(state) {
      return buildByCategoryChart(state.summary, state.baseCurrency);
    },
  },

  actions: {
    async refreshAll() {
      this.loading = true;
      this.error = null;
      try {
        const [summaryRes, assetsRes, liabilitiesRes, snapshotsRes] = await Promise.all([
          coreNetWorthApi.getSummary(),
          coreNetWorthApi.getAssets(),
          coreNetWorthApi.getLiabilities(),
          coreNetWorthApi.getSnapshots(),
        ]);

        this.summary = summaryRes.data;
        this.baseCurrency = summaryRes.data.base_currency;
        this.assets = assetsRes.data;
        this.liabilities = liabilitiesRes.data;
        this.snapshots = snapshotsRes.data;
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : e?.message || 'Error';
      } finally {
        this.loading = false;
      }
    },

    async createTodaySnapshot() {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.createSnapshotFromCurrent();
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : e?.message || 'Error';
        this.loading = false;
      }
    },

    async deleteSnapshot(id: number) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.deleteSnapshot(id);
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : e?.message || 'Error';
      } finally {
        this.loading = false;
      }
    },

    async createAsset(payload: Partial<Asset>) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.createAsset(payload as Record<string, unknown>);
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : e?.message || 'Error';
      } finally {
        this.loading = false;
      }
    },

    async updateAsset(id: number, payload: Partial<Asset>) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.updateAsset(id, payload as Record<string, unknown>);
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : e?.message || 'Error';
      } finally {
        this.loading = false;
      }
    },

    async archiveAsset(id: number) {
      return this.updateAsset(id, { is_active: false });
    },

    async createLiability(payload: Partial<Liability>) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.createLiability(payload as Record<string, unknown>);
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : e?.message || 'Error';
      } finally {
        this.loading = false;
      }
    },

    async updateLiability(id: number, payload: Partial<Liability>) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.updateLiability(id, payload as Record<string, unknown>);
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : e?.message || 'Error';
      } finally {
        this.loading = false;
      }
    },

    async archiveLiability(id: number) {
      return this.updateLiability(id, { is_active: false });
    },

    async fetchSettings() {
      try {
        const res = await coreNetWorthApi.getSettings();
        this.baseCurrency = res.data.base_currency;
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : e?.message || 'Error';
      }
    },

    async updateBaseCurrency(currency: string) {
      this.loading = true;
      this.error = null;
      try {
        const res = await coreNetWorthApi.updateSettings({ base_currency: currency });
        this.baseCurrency = res.data.base_currency;
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : e?.message || 'Error';
      } finally {
        this.loading = false;
      }
    },
  },
});
