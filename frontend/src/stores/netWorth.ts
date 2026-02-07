import { defineStore } from "pinia";
import { api } from "@/lib/api";

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

  // IPC (solo si base_currency === "EUR")
  inflation_region: string | null;
  inflation_base_period: string | null;

  total_assets_real: string | null;
  total_liabilities_real: string | null;
  net_worth_real: string | null;

  assets_by_category_real: Record<string, string> | null;
  liabilities_by_category_real: Record<string, string> | null;

};

export type MemberMini = {
  id: number;
  name: string;
  role: "adult" | "child";
};

export type ByMemberRow = {
  member: MemberMini;
  total_assets: string;
  total_liabilities: string;
  net_worth: string;
};

export type ByMemberSummary = {
  base_currency: string;
  totals: {
    total_assets: string;
    total_liabilities: string;
    net_worth: string;
  };
  by_member: ByMemberRow[];
  unassigned: {
    assets: string;
    liabilities: string;
    net_worth: string;
  };
};


export type Ownership = {
  id: number;
  kind: "individual" | "shared";
  member: { id: number; name: string; role: "adult" | "child" } | null;
  splits: { member: { id: number; name: string; role: "adult" | "child" }; percent: string }[];
  notes: string;
};


function normalizeNumberInput(raw: unknown) {
  return String(raw ?? "").trim().replace(/\s/g, "").replace(/,/g, ".");
}

function toNumber(v: unknown) {
  const n = Number(normalizeNumberInput(v));
  return Number.isFinite(n) ? n : 0;
}

export const useNetWorthStore = defineStore("netWorth", {
  state: () => ({
    loading: false as boolean,
    error: null as string | null,

    baseCurrency: null as string | null,

    summary: null as Summary | null,
    assets: [] as Asset[],
    liabilities: [] as Liability[],
    snapshots: [] as Snapshot[],

    byMemberSummary: null as ByMemberSummary | null,
    ownerships: [] as Ownership[],

  }),

  getters: {
    byMemberRows(state): ByMemberRow[] {
      return state.byMemberSummary?.by_member ?? [];
    },

    byMemberChart(state) {
      const rows = state.byMemberSummary?.by_member ?? [];
      const unit = state.byMemberSummary?.base_currency ?? state.baseCurrency ?? "EUR";

      return {
        unit,
        labels: rows.map(r => r.member.name),
        assets: rows.map(r => Math.max(0, toNumber(r.total_assets))),
        liabilities: rows.map(r => Math.max(0, toNumber(r.total_liabilities))),
        net: rows.map(r => toNumber(r.net_worth)),
      };
    },

    byCategoryChart(state) {
        const s = state.summary;
        const unit = state.baseCurrency ?? s?.base_currency ?? "EUR";

        const assetsBy = s?.assets_by_category ?? {};
        const liabsBy = s?.liabilities_by_category ?? {};

        // Unificamos claves para que el gráfico tenga filas consistentes
        const keys = Array.from(
          new Set<string>([...Object.keys(assetsBy), ...Object.keys(liabsBy)])
        );

        return {
          unit,
          keys,
          assets: keys.map((k) => Math.max(0, toNumber(assetsBy[k]))),
          liabilities: keys.map((k) => Math.max(0, toNumber(liabsBy[k]))),
        };
      },

  },

  actions: {
    async refreshAll() {
      this.loading = true;
      this.error = null;
      try {
        const [summaryRes, assetsRes, liabilitiesRes, snapshotsRes, byMemberRes, ownershipsRes] = await Promise.all([
          api.get("/api/net-worth/summary/"),
          api.get("/api/net-worth/assets/"),
          api.get("/api/net-worth/liabilities/"),
          api.get("/api/net-worth/snapshots/"),
          api.get("/api/net-worth/summary/by-member/"),
          api.get("/api/net-worth/ownerships/"),
        ]);

        this.summary = summaryRes.data;
        this.baseCurrency = summaryRes.data.base_currency;
        this.assets = assetsRes.data;
        this.liabilities = liabilitiesRes.data;
        this.snapshots = snapshotsRes.data;
        this.byMemberSummary = byMemberRes.data;
        this.ownerships = ownershipsRes.data;

      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
      } finally {
        this.loading = false;
      }
    },

    async createTodaySnapshot() {
      this.loading = true;
      this.error = null;
      try {
        await api.post("/api/net-worth/snapshots/from-current/");
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
        this.loading = false;
      }
    },

    async deleteSnapshot(id: number) {
      this.loading = true;
      this.error = null;
      try {
        await api.delete(`/api/net-worth/snapshots/${id}/`);
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
      } finally {
        this.loading = false;
      }
    },

    async createAsset(payload: Partial<Asset>) {
      this.loading = true;
      this.error = null;
      try {
        await api.post("/api/net-worth/assets/", payload);
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
      } finally {
        this.loading = false;
      }
    },

    async updateAsset(id: number, payload: Partial<Asset>) {
      this.loading = true;
      this.error = null;
      try {
        await api.patch(`/api/net-worth/assets/${id}/`, payload);
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
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
        await api.post("/api/net-worth/liabilities/", payload);
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
      } finally {
        this.loading = false;
      }
    },

    async updateLiability(id: number, payload: Partial<Liability>) {
      this.loading = true;
      this.error = null;
      try {
        await api.patch(`/api/net-worth/liabilities/${id}/`, payload);
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
      } finally {
        this.loading = false;
      }
    },

    async archiveLiability(id: number) {
      return this.updateLiability(id, { is_active: false });
    },


    async fetchSettings() {
      try {
        const res = await api.get("/api/auth/settings/");
        this.baseCurrency = res.data.base_currency;
      } catch (e: any) {
        this.error = e?.response?.data
          ? JSON.stringify(e.response.data)
          : (e?.message || "Error");
      }
    },

    async updateBaseCurrency(currency: string) {
      this.loading = true;
      this.error = null;
      try {
        const res = await api.put("/api/auth/settings/", {
          base_currency: currency,
        });
        this.baseCurrency = res.data.base_currency;
        await this.refreshAll();
      } catch (e: any) {
        this.error = e?.response?.data
          ? JSON.stringify(e.response.data)
          : (e?.message || "Error");
      } finally {
        this.loading = false;
      }
    },

    async fetchByMemberSummary() {
      this.loading = true;
      this.error = null;
      try {
        const res = await api.get("/api/net-worth/summary/by-member/");
        this.byMemberSummary = res.data;
      } catch (e: any) {
        this.error = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
      } finally {
        this.loading = false;
      }
    },

  },

});

