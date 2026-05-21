import { defineStore } from 'pinia';
import { isCanceledRequestError, toApiErrorMessage } from '@/lib/errors';
import { coreAccountingApi } from '@/domains/accounting/api';
import { coreNetWorthApi, premiumOwnershipApi } from '@/domains/net-worth/api';
import { buildByCategoryChart } from '@/domains/net-worth/charts';
import { attachOwnershipRef, buildOwnershipMaps } from '@/domains/net-worth/ownership';
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

export type { Asset, Liability, Ownership, Summary } from '@/domains/net-worth/models';

type OwnershipAwarePayload = NetWorthWritePayload & { ownership_id?: number | null };

let timelineAbortController: AbortController | null = null;

export const useNetWorthStore = defineStore('netWorth', {
  state: () => ({
    loading: false as boolean,
    error: null as string | null,

    baseCurrency: null as string | null,
    inflationRegion: 'ES' as string,

    summary: null as Summary | null,
    assets: [] as Asset[],
    liabilities: [] as Liability[],
    timeline: null as NetWorthTimeline | null,
    timelineLoading: false as boolean,
    timelineCategoryFilter: null as string | null,
    timelineCategoryFilterType: 'asset' as 'asset' | 'liability',
    positionTimeline: null as PositionTimeline | null,
    positionTimelineLoading: false as boolean,
    positionActivityLoading: false as boolean,
    assetValuations: [] as AssetValuation[],
    liabilityValuations: [] as LiabilityValuation[],
    investmentEvents: [] as InvestmentAssetEvent[],
    liquidityEvents: [] as LiquidityAssetEvent[],
    liabilityEvents: [] as LiabilityEvent[],

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
        const [settingsRes, summaryRes, assetsRes, liabilitiesRes, ownershipsRes, linksRes] =
          await Promise.all([
            coreNetWorthApi.getSettings(),
            coreNetWorthApi.getSummary(),
            coreNetWorthApi.getAssets(),
            coreNetWorthApi.getLiabilities(),
            premiumOwnershipApi.getOwnerships(),
            premiumOwnershipApi.getOwnershipLinks(),
          ]);
        const links = linksRes.data;
        const { assetOwnership, liabilityOwnership } = buildOwnershipMaps(links);

        this.baseCurrency = settingsRes.data.base_currency;
        this.inflationRegion = settingsRes.data.inflation_region;
        this.summary = summaryRes.data;
        this.assets = attachOwnershipRef(assetsRes.data, assetOwnership);
        this.liabilities = attachOwnershipRef(liabilitiesRes.data, liabilityOwnership);
        this.ownerships = ownershipsRes.data;
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.loading = false;
      }
      // Fire timeline load independently — it has its own timelineLoading state
      this.fetchTimeline(this.timelineCategoryFilter, this.timelineCategoryFilterType);
    },

    async fetchTimeline(
      category: string | null = null,
      categoryType: 'asset' | 'liability' = 'asset',
    ) {
      timelineAbortController?.abort();
      timelineAbortController = new AbortController();
      const { signal } = timelineAbortController;

      this.timelineLoading = true;
      this.timelineCategoryFilter = category;
      this.timelineCategoryFilterType = categoryType;
      try {
        const timelineRes = await coreNetWorthApi.getTimeline(
          {
            asset_category: categoryType === 'asset' ? category : null,
            liability_category: categoryType === 'liability' ? category : null,
          },
          { signal },
        );
        this.timeline = timelineRes.data;
      } catch (e: unknown) {
        if (isCanceledRequestError(e)) return;
        this.error = toApiErrorMessage(e);
      } finally {
        this.timelineLoading = false;
      }
    },

    async fetchPositionTimeline(positionType: 'asset' | 'liability', id: number) {
      this.positionTimelineLoading = true;
      try {
        const timelineRes =
          positionType === 'asset'
            ? await coreNetWorthApi.getAssetTimeline(id)
            : await coreNetWorthApi.getLiabilityTimeline(id);
        this.positionTimeline = timelineRes.data;
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.positionTimelineLoading = false;
      }
    },

    async fetchPositionActivity(
      positionType: 'asset' | 'liability',
      id: number,
      category?: string | null,
    ) {
      this.positionActivityLoading = true;
      try {
        if (positionType === 'asset') {
          const requests: Promise<unknown>[] = [coreNetWorthApi.getAssetValuations()];
          const shouldLoadInvestment = category === 'investments';
          const shouldLoadLiquidity = category === 'cash';
          if (shouldLoadInvestment) requests.push(coreNetWorthApi.getInvestmentEvents());
          if (shouldLoadLiquidity) requests.push(coreNetWorthApi.getLiquidityEvents());

          const [valuationsRes, maybeInvestmentRes, maybeLiquidityRes] =
            await Promise.all(requests);
          const valuations = (valuationsRes as { data: AssetValuation[] }).data;
          this.assetValuations = valuations.filter((row) => row.asset_ref === id);
          this.investmentEvents = shouldLoadInvestment
            ? (maybeInvestmentRes as { data: InvestmentAssetEvent[] }).data.filter(
                (row) => row.asset_ref === id,
              )
            : [];
          this.liquidityEvents = shouldLoadLiquidity
            ? (
                (shouldLoadInvestment ? maybeLiquidityRes : maybeInvestmentRes) as {
                  data: LiquidityAssetEvent[];
                }
              ).data.filter((row) => row.asset_ref === id)
            : [];
          this.liabilityValuations = [];
          this.liabilityEvents = [];
        } else {
          const [valuationsRes, eventsRes] = await Promise.all([
            coreNetWorthApi.getLiabilityValuations(),
            coreNetWorthApi.getLiabilityEvents(),
          ]);
          this.liabilityValuations = valuationsRes.data.filter((row) => row.liability_ref === id);
          this.liabilityEvents = eventsRes.data.filter((row) => row.liability_ref === id);
          this.assetValuations = [];
          this.investmentEvents = [];
          this.liquidityEvents = [];
        }
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.positionActivityLoading = false;
      }
    },

    async _refreshSummary() {
      const res = await coreNetWorthApi.getSummary();
      this.summary = res.data;
      this.fetchTimeline(this.timelineCategoryFilter, this.timelineCategoryFilterType);
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
          this.assets = [...this.assets, { ...res.data, ownership_ref: ownership_id }];
        }
        await this._refreshSummary();
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
        const res = await coreNetWorthApi.updateAsset(id, corePayload);
        await premiumOwnershipApi.syncOwnershipLink({
          target_type: 'asset',
          target_id: id,
          ownership_id,
        });
        const updated = { ...res.data, ownership_ref: ownership_id };
        this.assets = this.assets.map((a) => (a.id === id ? updated : a));
        await this._refreshSummary();
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.loading = false;
      }
    },

    async archiveAsset(id: number) {
      const asset = this.assets.find((a) => a.id === id);
      if (asset?.accounting_account_id) {
        await coreAccountingApi.updateAccount(asset.accounting_account_id, { is_active: false });
      }
      return this.updateAsset(id, { is_active: false, ownership_id: asset?.ownership_ref ?? null });
    },

    async unarchiveAsset(id: number) {
      const asset = this.assets.find((a) => a.id === id);
      if (asset?.accounting_account_id) {
        await coreAccountingApi.updateAccount(asset.accounting_account_id, { is_active: true });
      }
      return this.updateAsset(id, { is_active: true, ownership_id: asset?.ownership_ref ?? null });
    },

    async deleteAsset(id: number) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.deleteAsset(id);
        this.assets = this.assets.filter((a) => a.id !== id);
        await this._refreshSummary();
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
          this.liabilities = [...this.liabilities, { ...res.data, ownership_ref: ownership_id }];
        }
        await this._refreshSummary();
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
        const res = await coreNetWorthApi.updateLiability(id, corePayload);
        await premiumOwnershipApi.syncOwnershipLink({
          target_type: 'liability',
          target_id: id,
          ownership_id,
        });
        const updated = { ...res.data, ownership_ref: ownership_id };
        this.liabilities = this.liabilities.map((l) => (l.id === id ? updated : l));
        await this._refreshSummary();
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.loading = false;
      }
    },

    async archiveLiability(id: number) {
      const liability = this.liabilities.find((l) => l.id === id);
      if (liability?.accounting_account_id) {
        await coreAccountingApi.updateAccount(liability.accounting_account_id, {
          is_active: false,
        });
      }
      return this.updateLiability(id, {
        is_active: false,
        ownership_id: liability?.ownership_ref ?? null,
      });
    },

    async unarchiveLiability(id: number) {
      const liability = this.liabilities.find((l) => l.id === id);
      if (liability?.accounting_account_id) {
        await coreAccountingApi.updateAccount(liability.accounting_account_id, { is_active: true });
      }
      return this.updateLiability(id, {
        is_active: true,
        ownership_id: liability?.ownership_ref ?? null,
      });
    },

    async deleteLiability(id: number) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.deleteLiability(id);
        this.liabilities = this.liabilities.filter((l) => l.id !== id);
        await this._refreshSummary();
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
        this.inflationRegion = res.data.inflation_region;
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      }
    },

    async updateSettings(payload: Partial<Settings>) {
      this.loading = true;
      this.error = null;
      try {
        await coreNetWorthApi.updateSettings({
          base_currency: payload.base_currency ?? this.baseCurrency ?? 'EUR',
          inflation_region: payload.inflation_region ?? this.inflationRegion ?? 'ES',
        });
        // Ownerships and links are unaffected by settings — rebuild maps from current state
        const assetOwnership = new Map(
          this.assets
            .filter((a) => a.ownership_ref != null)
            .map((a) => [a.id, a.ownership_ref as number]),
        );
        const liabilityOwnership = new Map(
          this.liabilities
            .filter((l) => l.ownership_ref != null)
            .map((l) => [l.id, l.ownership_ref as number]),
        );
        const [settingsRes, summaryRes, assetsRes, liabilitiesRes] = await Promise.all([
          coreNetWorthApi.getSettings(),
          coreNetWorthApi.getSummary(),
          coreNetWorthApi.getAssets(),
          coreNetWorthApi.getLiabilities(),
        ]);
        this.baseCurrency = settingsRes.data.base_currency;
        this.inflationRegion = settingsRes.data.inflation_region;
        this.summary = summaryRes.data;
        this.assets = attachOwnershipRef(assetsRes.data, assetOwnership);
        this.liabilities = attachOwnershipRef(liabilitiesRes.data, liabilityOwnership);
        this.fetchTimeline(this.timelineCategoryFilter, this.timelineCategoryFilterType);
        if (this.positionTimeline?.position_id && this.positionTimeline?.position_type) {
          void this.fetchPositionTimeline(
            this.positionTimeline.position_type,
            this.positionTimeline.position_id,
          );
        }
      } catch (e: unknown) {
        this.error = toApiErrorMessage(e);
      } finally {
        this.loading = false;
      }
    },

    async updateBaseCurrency(currency: string) {
      await this.updateSettings({ base_currency: currency });
    },

    async updateInflationRegion(region: string) {
      await this.updateSettings({ inflation_region: region });
    },
  },
});
