import { beforeEach, describe, expect, it, vi } from 'vitest';
import { createPinia, setActivePinia } from 'pinia';
import { usePeopleStore } from '@/domains/people/store';

const mocks = vi.hoisted(() => ({
  peopleApi: {
    getMembers: vi.fn(),
    createMember: vi.fn(),
    updateMember: vi.fn(),
    deleteMember: vi.fn(),
    getOwnerships: vi.fn(),
    createSharedOwnership: vi.fn(),
    updateSharedOwnership: vi.fn(),
    deleteOwnership: vi.fn(),
  },
  toPeopleErrorMessage: vi.fn(() => 'people-error'),
}));

vi.mock('@/domains/people/api', () => ({
  peopleApi: mocks.peopleApi,
}));

vi.mock('@/domains/people/errors', () => ({
  toPeopleErrorMessage: mocks.toPeopleErrorMessage,
}));

describe('people store (saas)', () => {
  beforeEach(() => {
    setActivePinia(createPinia());
    vi.clearAllMocks();
  });

  it('fetches members and computes active adults', async () => {
    mocks.peopleApi.getMembers.mockResolvedValue({
      data: [
        { id: 1, name: 'Ana', role: 'adult', is_active: true },
        { id: 2, name: 'Leo', role: 'child', is_active: true },
        { id: 3, name: 'Bob', role: 'adult', is_active: false },
      ],
    });
    const store = usePeopleStore();

    await store.fetchMembers();

    expect(store.members).toHaveLength(3);
    expect(store.activeAdults).toEqual([{ id: 1, name: 'Ana', role: 'adult', is_active: true }]);
    expect(store.loading).toBe(false);
  });

  it('maps fetch errors and clears explicit error state', async () => {
    mocks.peopleApi.getMembers.mockRejectedValue(new Error('boom'));
    const store = usePeopleStore();
    store.error = 'existing';

    await store.fetchMembers();
    expect(store.error).toBe('people-error');

    store.clearError();
    expect(store.error).toBeNull();
  });

  it('creates, updates and deletes members', async () => {
    mocks.peopleApi.createMember.mockResolvedValue({
      data: { id: 3, name: 'Ada', role: 'adult', is_active: true },
    });
    mocks.peopleApi.updateMember.mockResolvedValue({
      data: { id: 3, name: 'Ada Lovelace', role: 'adult', is_active: false },
    });
    mocks.peopleApi.deleteMember.mockResolvedValue({});

    const store = usePeopleStore();
    store.members = [
      { id: 1, name: 'Zoe', role: 'adult', is_active: true },
      { id: 2, name: 'Pepe', role: 'child', is_active: true },
    ];

    await store.createMember({ name: 'Ada', role: 'adult' });
    expect(mocks.peopleApi.createMember).toHaveBeenCalledWith({
      name: 'Ada',
      role: 'adult',
      is_active: true,
    });
    expect(store.members.map((m) => m.name)).toEqual(['Ada', 'Zoe', 'Pepe']);

    await store.updateMember(3, { name: 'Ada Lovelace', is_active: false });
    expect(store.members.find((m) => m.id === 3)?.name).toBe('Ada Lovelace');
    expect(store.members.find((m) => m.id === 3)?.is_active).toBe(false);

    await store.deleteMember(2);
    expect(mocks.peopleApi.deleteMember).toHaveBeenCalledWith(2);
    expect(store.members.some((m) => m.id === 2)).toBe(false);
  });

  it('rethrows member write errors with mapped message', async () => {
    mocks.peopleApi.createMember.mockRejectedValue(new Error('boom'));
    const store = usePeopleStore();

    await expect(store.createMember({ name: 'Ada', role: 'adult' })).rejects.toThrow('boom');
    expect(store.error).toBe('people-error');
    expect(store.loading).toBe(false);
  });

  it('handles ownership list/create/update/delete flows', async () => {
    mocks.peopleApi.getOwnerships.mockResolvedValue({
      data: [{ id: 5, kind: 'shared', member: null, splits: [], is_in_use: false }],
    });
    mocks.peopleApi.createSharedOwnership.mockResolvedValue({});
    mocks.peopleApi.updateSharedOwnership.mockResolvedValue({});
    mocks.peopleApi.deleteOwnership.mockResolvedValue({});
    const store = usePeopleStore();
    store.ownerships = [
      {
        id: 1,
        kind: 'individual',
        member: { id: 1, name: 'Ana', role: 'adult' },
        splits: [],
        is_in_use: false,
      },
      { id: 5, kind: 'shared', member: null, splits: [], is_in_use: false },
    ];

    await store.fetchOwnerships();
    expect(store.ownerships).toHaveLength(1);

    await store.createSharedOwnership({ splits: [{ member_id: 1, percent: '100' }] });
    expect(mocks.peopleApi.createSharedOwnership).toHaveBeenCalled();
    expect(mocks.peopleApi.getOwnerships).toHaveBeenCalledTimes(2);

    await store.updateSharedOwnership(5, { splits: [{ member_id: 1, percent: '60' }] });
    expect(mocks.peopleApi.updateSharedOwnership).toHaveBeenCalledWith(5, {
      splits: [{ member_id: 1, percent: '60' }],
    });

    await store.deleteOwnership(5);
    expect(store.ownerships).toEqual([]);
  });
});
