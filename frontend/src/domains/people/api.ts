import { api } from '@/lib/api';
import { capabilities } from '@/domains/capabilities';
import type { FamilyMember, OwnershipRead } from '@/domains/people/types';

type MemberCreatePayload = { name: string; role: 'adult' | 'child'; is_active: boolean };
type MemberPatchPayload = Partial<Pick<FamilyMember, 'name' | 'role' | 'is_active'>>;
type OwnershipSplitsPayload = { splits: { member_id: number; percent: string }[] };

export type PeopleApiAdapter = {
  getMembers(): ReturnType<typeof api.get<FamilyMember[]>>;
  createMember(payload: MemberCreatePayload): ReturnType<typeof api.post<FamilyMember>>;
  updateMember(id: number, patch: MemberPatchPayload): ReturnType<typeof api.patch<FamilyMember>>;
  deleteMember(id: number): ReturnType<typeof api.delete>;
  getOwnerships(): ReturnType<typeof api.get<OwnershipRead[]>>;
  createSharedOwnership(payload: OwnershipSplitsPayload): ReturnType<typeof api.post>;
  updateSharedOwnership(id: number, payload: OwnershipSplitsPayload): ReturnType<typeof api.patch>;
  deleteOwnership(id: number): ReturnType<typeof api.delete>;
};

export const premiumPeopleApi: PeopleApiAdapter = {
  getMembers() {
    return api.get<FamilyMember[]>('/api/family-members/');
  },
  createMember(payload: MemberCreatePayload) {
    return api.post<FamilyMember>('/api/family-members/', payload);
  },
  updateMember(id: number, patch: MemberPatchPayload) {
    return api.patch<FamilyMember>(`/api/family-members/${id}/`, patch);
  },
  deleteMember(id: number) {
    return api.delete(`/api/family-members/${id}/`);
  },
  getOwnerships() {
    return api.get<OwnershipRead[]>('/api/ownerships/');
  },
  createSharedOwnership(payload: OwnershipSplitsPayload) {
    return api.post('/api/ownerships/', {
      kind: 'shared',
      member: null,
      splits: payload.splits,
    });
  },
  updateSharedOwnership(id: number, payload: OwnershipSplitsPayload) {
    return api.patch(`/api/ownerships/${id}/`, {
      kind: 'shared',
      member: null,
      splits: payload.splits,
    });
  },
  deleteOwnership(id: number) {
    return api.delete(`/api/ownerships/${id}/`);
  },
};

// Transitional behavior for Core v0 consolidation:
// use the same endpoint contract as SaaS while the backend domain is ported into Core.
export const corePeopleApi: PeopleApiAdapter = premiumPeopleApi;

export const peopleApi: PeopleApiAdapter = capabilities.people ? premiumPeopleApi : corePeopleApi;
