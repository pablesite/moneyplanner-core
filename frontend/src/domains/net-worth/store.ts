import { defineStore } from 'pinia';
import { toApiErrorMessage } from '@/lib/errors';
import { coreNetWorthApi } from '@/domains/net-worth/api';
import { buildByCategoryChart } from '@/domains/net-worth/charts';
import type { Asset, Liability, NetWorthWritePayload, Snapshot, Summary } from '@/domains/net-worth/models';

export type { Asset, Liability, Snapshot, Summary } from '@/domains/net-worth/models';

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
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
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
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
        this.loading = false;
      }
    },

    async deleteSnapshot(id: number) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.deleteSnapshot(id);
        await this.refreshAll();
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.loading = false;
      }
    },

    async createAsset(payload: NetWorthWritePayload) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.createAsset(payload);
        await this.refreshAll();
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.loading = false;
      }
    },

    async updateAsset(id: number, payload: NetWorthWritePayload) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.updateAsset(id, payload);
        await this.refreshAll();
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.loading = false;
      }
    },

    async archiveAsset(id: number) {
      return this.updateAsset(id, { is_active: false });
    },

    async createLiability(payload: NetWorthWritePayload) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.createLiability(payload);
        await this.refreshAll();
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.loading = false;
      }
    },

    async updateLiability(id: number, payload: NetWorthWritePayload) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.updateLiability(id, payload);
        await this.refreshAll();
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
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
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      }
    },

    async updateBaseCurrency(currency: string) {
      this.loading = true;
      this.error = null;
      try {
        const res = await coreNetWorthApi.updateSettings({ base_currency: currency });
        this.baseCurrency = res.data.base_currency;
        await this.refreshAll();
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.loading = false;
      }
    },
  },
});
