import { coreApi } from '@/lib/api';
import { capabilities } from '@/domains/capabilities';
import type { FamilyMember, OwnershipRead } from '@/domains/people/types';

type MemberCreatePayload = { name: string; role: 'adult' | 'child'; is_active: boolean };
type MemberPatchPayload = Partial<Pick<FamilyMember, 'name' | 'role' | 'is_active'>>;
type OwnershipSplitsPayload = { splits: { member_id: number; percent: string }[] };

export type PeopleApiAdapter = {
  getMembers(): ReturnType<typeof coreApi.get<FamilyMember[]>>;
  createMember(payload: MemberCreatePayload): ReturnType<typeof coreApi.post<FamilyMember>>;
  updateMember(
    id: number,
    patch: MemberPatchPayload,
  ): ReturnType<typeof coreApi.patch<FamilyMember>>;
  deleteMember(id: number): ReturnType<typeof coreApi.delete>;
  getOwnerships(): ReturnType<typeof coreApi.get<OwnershipRead[]>>;
  createSharedOwnership(payload: OwnershipSplitsPayload): ReturnType<typeof coreApi.post>;
  updateSharedOwnership(
    id: number,
    payload: OwnershipSplitsPayload,
  ): ReturnType<typeof coreApi.patch>;
  deleteOwnership(id: number): ReturnType<typeof coreApi.delete>;
};

export const premiumPeopleApi: PeopleApiAdapter = {
  getMembers() {
    return coreApi.get<FamilyMember[]>('/api/family-members/');
  },
  createMember(payload: MemberCreatePayload) {
    return coreApi.post<FamilyMember>('/api/family-members/', payload);
  },
  updateMember(id: number, patch: MemberPatchPayload) {
    return coreApi.patch<FamilyMember>(`/api/family-members/${id}/`, patch);
  },
  deleteMember(id: number) {
    return coreApi.delete(`/api/family-members/${id}/`);
  },
  getOwnerships() {
    return coreApi.get<OwnershipRead[]>('/api/ownerships/');
  },
  createSharedOwnership(payload: OwnershipSplitsPayload) {
    return coreApi.post('/api/ownerships/', {
      kind: 'shared',
      member: null,
      splits: payload.splits,
    });
  },
  updateSharedOwnership(id: number, payload: OwnershipSplitsPayload) {
    return coreApi.patch(`/api/ownerships/${id}/`, {
      kind: 'shared',
      member: null,
      splits: payload.splits,
    });
  },
  deleteOwnership(id: number) {
    return coreApi.delete(`/api/ownerships/${id}/`);
  },
};

// Transitional behavior for Core v0 consolidation:
// use the same endpoint contract as SaaS while the backend domain is ported into Core.
export const corePeopleApi: PeopleApiAdapter = premiumPeopleApi;

export const peopleApi: PeopleApiAdapter = capabilities.people ? premiumPeopleApi : corePeopleApi;
