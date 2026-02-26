import { beforeEach, describe, expect, it, vi } from 'vitest';
import { corePeopleApi, peopleApi, premiumPeopleApi } from '@/domains/people/api';

const mocks = vi.hoisted(() => ({
  api: {
    get: vi.fn(),
    post: vi.fn(),
    patch: vi.fn(),
    delete: vi.fn(),
  },
}));

vi.mock('@/lib/api', () => ({
  api: mocks.api,
}));

describe('people api (saas)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('exports premium adapter as active api in saas', () => {
    expect(peopleApi).toBe(premiumPeopleApi);
    expect(peopleApi).not.toBe(corePeopleApi);
  });

  it('maps premium endpoints and payload shape', async () => {
    const memberPayload = { name: 'Ada', role: 'adult' as const, is_active: true };
    const patchPayload = { name: 'Ada Lovelace' };
    const splitsPayload = {
      splits: [
        { member_id: 1, percent: '60' },
        { member_id: 2, percent: '40' },
      ],
    };

    await premiumPeopleApi.getMembers();
    await premiumPeopleApi.createMember(memberPayload);
    await premiumPeopleApi.updateMember(1, patchPayload);
    await premiumPeopleApi.deleteMember(1);
    await premiumPeopleApi.getOwnerships();
    await premiumPeopleApi.createSharedOwnership(splitsPayload);
    await premiumPeopleApi.updateSharedOwnership(5, splitsPayload);
    await premiumPeopleApi.deleteOwnership(5);

    expect(mocks.api.get).toHaveBeenCalledWith('/api/family-members/');
    expect(mocks.api.post).toHaveBeenCalledWith('/api/family-members/', memberPayload);
    expect(mocks.api.patch).toHaveBeenCalledWith('/api/family-members/1/', patchPayload);
    expect(mocks.api.delete).toHaveBeenCalledWith('/api/family-members/1/');
    expect(mocks.api.get).toHaveBeenCalledWith('/api/ownerships/');
    expect(mocks.api.post).toHaveBeenCalledWith('/api/ownerships/', {
      kind: 'shared',
      member: null,
      splits: splitsPayload.splits,
    });
    expect(mocks.api.patch).toHaveBeenCalledWith('/api/ownerships/5/', {
      kind: 'shared',
      member: null,
      splits: splitsPayload.splits,
    });
    expect(mocks.api.delete).toHaveBeenCalledWith('/api/ownerships/5/');
  });

  it('rejects all core people operations as unsupported', async () => {
    await expect(corePeopleApi.getMembers()).rejects.toThrow('not enabled');
    await expect(
      corePeopleApi.createMember({ name: 'Ada', role: 'adult', is_active: true }),
    ).rejects.toThrow('not enabled');
    await expect(corePeopleApi.updateMember(1, { name: 'Ada' })).rejects.toThrow('not enabled');
    await expect(corePeopleApi.deleteMember(1)).rejects.toThrow('not enabled');
    await expect(corePeopleApi.getOwnerships()).rejects.toThrow('not enabled');
    await expect(
      corePeopleApi.createSharedOwnership({ splits: [{ member_id: 1, percent: '100' }] }),
    ).rejects.toThrow('not enabled');
    await expect(
      corePeopleApi.updateSharedOwnership(1, { splits: [{ member_id: 1, percent: '100' }] }),
    ).rejects.toThrow('not enabled');
    await expect(corePeopleApi.deleteOwnership(1)).rejects.toThrow('not enabled');
  });
});
