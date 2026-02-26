import { defineStore } from 'pinia';
import { peopleApi } from '@/domains/people/api';
import { toPeopleErrorMessage } from '@/domains/people/errors';
import type { FamilyMember, OwnershipRead } from '@/domains/people/types';

export type { FamilyMember, OwnershipKind, OwnershipRead } from '@/domains/people/types';

export const usePeopleStore = defineStore('people', {
  state: () => ({
    loading: false as boolean,
    error: null as string | null,
    members: [] as FamilyMember[],
    ownerships: [] as OwnershipRead[],
  }),

  getters: {
    activeAdults(state) {
      return state.members.filter((m) => m.is_active && m.role === 'adult');
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
        const { data } = await peopleApi.getMembers();
        this.members = data;
      } catch (e) {
        this.error = toPeopleErrorMessage(e);
      } finally {
        this.loading = false;
      }
    },

    async createMember(payload: { name: string; role: 'adult' | 'child' }) {
      this.loading = true;
      this.error = null;
      try {
        const { data } = await peopleApi.createMember({
          ...payload,
          is_active: true,
        });

        this.members = [...this.members, data].sort((a, b) => {
          if (a.role !== b.role) return a.role === 'adult' ? -1 : 1;
          return a.name.localeCompare(b.name);
        });

        return data;
      } catch (e) {
        this.error = toPeopleErrorMessage(e);
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async updateMember(
      id: number,
      patch: Partial<Pick<FamilyMember, 'name' | 'role' | 'is_active'>>,
    ) {
      this.loading = true;
      this.error = null;
      try {
        const { data } = await peopleApi.updateMember(id, patch);
        this.members = this.members.map((m) => (m.id === id ? data : m));
        return data;
      } catch (e) {
        this.error = toPeopleErrorMessage(e);
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async deleteMember(id: number) {
      this.loading = true;
      this.error = null;
      try {
        await peopleApi.deleteMember(id);
        this.members = this.members.filter((m) => m.id !== id);
      } catch (e) {
        this.error = toPeopleErrorMessage(e);
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
        const { data } = await peopleApi.getOwnerships();
        this.ownerships = data;
      } catch (e) {
        this.error = toPeopleErrorMessage(e);
      } finally {
        this.loading = false;
      }
    },

    async createSharedOwnership(payload: { splits: { member_id: number; percent: string }[] }) {
      this.loading = true;
      this.error = null;
      try {
        await peopleApi.createSharedOwnership(payload);
        await this.fetchOwnerships();
      } catch (e) {
        this.error = toPeopleErrorMessage(e);
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async updateSharedOwnership(
      id: number,
      payload: { splits: { member_id: number; percent: string }[] },
    ) {
      this.loading = true;
      this.error = null;
      try {
        await peopleApi.updateSharedOwnership(id, payload);
        await this.fetchOwnerships();
      } catch (e) {
        this.error = toPeopleErrorMessage(e);
        throw e;
      } finally {
        this.loading = false;
      }
    },

    async deleteOwnership(id: number) {
      this.loading = true;
      this.error = null;
      try {
        await peopleApi.deleteOwnership(id);
        this.ownerships = this.ownerships.filter((o) => o.id !== id);
      } catch (e) {
        this.error = toPeopleErrorMessage(e);
        throw e;
      } finally {
        this.loading = false;
      }
    },
  },
});
