import { defineStore } from 'pinia';
import { toApiErrorMessage } from '@/lib/errors';
import { coreNetWorthApi, premiumOwnershipApi } from '@/domains/net-worth/api';
import { buildByCategoryChart } from '@/domains/net-worth/charts';
import { attachOwnershipRef, buildOwnershipMaps } from '@/domains/net-worth/ownership';
import type {
  Asset,
  Liability,
  NetWorthWritePayload,
  Ownership,
  Snapshot,
  Summary,
} from '@/domains/net-worth/models';

export type { Asset, Liability, Ownership, Snapshot, Summary } from '@/domains/net-worth/models';

type OwnershipAwarePayload = NetWorthWritePayload & { ownership_id?: number | null };

export const useNetWorthStore = defineStore('netWorth', {
  state: () => ({
    loading: false as boolean,
    error: null as string | null,

    baseCurrency: null as string | null,

    summary: null as Summary | null,
    assets: [] as Asset[],
    liabilities: [] as Liability[],
    snapshots: [] as Snapshot[],

    ownerships: [] as Ownership[],
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
        const [ownershipsRes, linksRes] = await Promise.all([
          premiumOwnershipApi.getOwnerships(),
          premiumOwnershipApi.getOwnershipLinks(),
        ]);
        const links = linksRes.data;
        const { assetOwnership, liabilityOwnership } = buildOwnershipMaps(links);

        this.summary = summaryRes.data;
        this.baseCurrency = summaryRes.data.base_currency;
        this.assets = attachOwnershipRef(assetsRes.data, assetOwnership);
        this.liabilities = attachOwnershipRef(liabilitiesRes.data, liabilityOwnership);
        this.snapshots = snapshotsRes.data;
        this.ownerships = ownershipsRes.data;
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

    async createAsset(
      payload: OwnershipAwarePayload & {
        estimated_average_balance_for_interest?: string | null;
        deposit_term_months?: number | null;
      },
    ) {
      this.loading = true;
      this.error = null;
      let createdAsset: Asset | null = null;
      try {
        const { ownership_id = null, ...corePayload } = payload;
        const res = await coreNetWorthApi.createAsset(corePayload);
        createdAsset = res?.data ?? null;
        if (res?.data?.id) {
          await premiumOwnershipApi.syncOwnershipLink({
            target_type: 'asset',
            target_id: res.data.id,
            ownership_id,
          });
        }
        await this.refreshAll();
        return createdAsset;
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
        if (createdAsset) {
          try {
            await this.refreshAll();
          } catch {
            // keep original error; activo ya fue creado en core
          }
          return createdAsset;
        }
        return null;
      } finally {
        this.loading = false;
      }
    },

    async updateAsset(id: number, payload: OwnershipAwarePayload) {
      this.loading = true;
      this.error = null;
      try {
        const { ownership_id = null, ...corePayload } = payload;
        await coreNetWorthApi.updateAsset(id, corePayload);
        await premiumOwnershipApi.syncOwnershipLink({
          target_type: 'asset',
          target_id: id,
          ownership_id,
        });
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

    async deleteAsset(id: number) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.deleteAsset(id);
        await this.refreshAll();
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.loading = false;
      }
    },

    async createLiability(payload: OwnershipAwarePayload) {
      this.loading = true;
      this.error = null;
      let createdLiability: Liability | null = null;
      try {
        const { ownership_id = null, ...corePayload } = payload;
        const res = await coreNetWorthApi.createLiability(corePayload);
        createdLiability = res?.data ?? null;
        if (res?.data?.id) {
          await premiumOwnershipApi.syncOwnershipLink({
            target_type: 'liability',
            target_id: res.data.id,
            ownership_id,
          });
        }
        await this.refreshAll();
        return createdLiability;
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
        if (createdLiability) {
          try {
            await this.refreshAll();
          } catch {
            // keep original error; pasivo ya fue creado en core
          }
          return createdLiability;
        }
        return null;
      } finally {
        this.loading = false;
      }
    },

    async updateLiability(id: number, payload: OwnershipAwarePayload) {
      this.loading = true;
      this.error = null;
      try {
        const { ownership_id = null, ...corePayload } = payload;
        await coreNetWorthApi.updateLiability(id, corePayload);
        await premiumOwnershipApi.syncOwnershipLink({
          target_type: 'liability',
          target_id: id,
          ownership_id,
        });
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

    async deleteLiability(id: number) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.deleteLiability(id);
        await this.refreshAll();
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.loading = false;
      }
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
