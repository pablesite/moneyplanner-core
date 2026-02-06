import { defineStore } from "pinia";
import { api } from "@/lib/api";
import axios from "axios";

export type FamilyMember = {
  id: number;
  name: string;
  role: "adult" | "child";
  is_active: boolean;
};

export type OwnershipKind = "individual" | "shared";

export type OwnershipRead = {
  id: number;
  kind: OwnershipKind;
  member: { id: number; name: string; role: "adult" | "child" } | null;
  splits: { member: { id: number; name: string; role: "adult" | "child" }; percent: string }[];
  is_in_use: boolean;
};

function extractAxiosError(err: unknown): string {
  if (!axios.isAxiosError(err)) return String(err);

  const data: any = err.response?.data;
  if (!data) return err.message;

  if (typeof data === "string") return data;
  if (data.detail) return data.detail;

  const firstKey = Object.keys(data)[0];
  const v = data[firstKey];
  if (Array.isArray(v)) return v[0] ?? err.message;
  if (typeof v === "string") return v;

  return err.message;
}

export const usePeopleStore = defineStore("people", {
  state: () => ({
    loading: false as boolean,
    error: null as string | null,
    members: [] as FamilyMember[],
    ownerships: [] as OwnershipRead[],
  }),

  getters: {
    activeAdults(state) {
      return state.members.filter((m) => m.is_active && m.role === "adult");
    },
  },

  actions: {
    clearError() {
      this.error = null;
    },

    // -------- Members --------

    async fetchMembers() {
      this.loading = true;
      this.error = null;
      try {
        const { data } = await api.get<FamilyMember[]>("/api/net-worth/family-members/");
        this.members = data;
      } catch (e) {
        this.error = extractAxiosError(e);
      } finally {
        this.loading = false;
      }
    },

    async createMember(payload: { name: string; role: "adult" | "child" }) {
      this.loading = true;
      this.error = null;
      try {
        const { data } = await api.post<FamilyMember>("/api/net-worth/family-members/", {
          ...payload,
          is_active: true,
        });

        this.members = [...this.members, data].sort((a, b) => {
          if (a.role !== b.role) return a.role === "adult" ? -1 : 1;
          return a.name.localeCompare(b.name);
        });

        return data;
      } catch (e) {
        this.error = extractAxiosError(e);
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async updateMember(
      id: number,
      patch: Partial<Pick<FamilyMember, "name" | "role" | "is_active">>
    ) {
      this.loading = true;
      this.error = null;
      try {
        const { data } = await api.patch<FamilyMember>(`/api/net-worth/family-members/${id}/`, patch);
        this.members = this.members.map((m) => (m.id === id ? data : m));
        return data;
      } catch (e) {
        this.error = extractAxiosError(e);
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async deleteMember(id: number) {
      this.loading = true;
      this.error = null;
      try {
        await api.delete(`/api/net-worth/family-members/${id}/`);
        this.members = this.members.filter((m) => m.id !== id);
      } catch (e) {
        this.error = extractAxiosError(e);
        throw e;
      } finally {
        this.loading = false;
      }
    },

    // -------- Ownerships --------

    async fetchOwnerships() {
      this.loading = true;
      this.error = null;
      try {
        const { data } = await api.get<OwnershipRead[]>("/api/net-worth/ownerships/");
        this.ownerships = data;
      } catch (e) {
        this.error = extractAxiosError(e);
      } finally {
        this.loading = false;
      }
    },

    async createSharedOwnership(payload: { splits: { member_id: number; percent: string }[] }) {
      this.loading = true;
      this.error = null;
      try {
        await api.post("/api/net-worth/ownerships/", {
          kind: "shared",
          member: null,
          splits: payload.splits,
        });

        await this.fetchOwnerships();
      } catch (e) {
        this.error = extractAxiosError(e);
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async updateSharedOwnership(id: number, payload: { splits: { member_id: number; percent: string }[] }) {
      this.loading = true;
      this.error = null;
      try {
        await api.patch(`/api/net-worth/ownerships/${id}/`, {
          kind: "shared",
          member: null,
          splits: payload.splits,
        });
        await this.fetchOwnerships();
      } catch (e) {
        this.error = extractAxiosError(e);
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async deleteOwnership(id: number) {
      this.loading = true;
      this.error = null;
      try {
        await api.delete(`/api/net-worth/ownerships/${id}/`);
        this.ownerships = this.ownerships.filter((o) => o.id !== id);
      } catch (e) {
        this.error = extractAxiosError(e);
        throw e;
      } finally {
        this.loading = false;
      }
    },
  },
});
