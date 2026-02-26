import { beforeEach, describe, expect, it, vi } from 'vitest';
import { reactive } from 'vue';
import { usePeopleMembers, usePeopleOwnerships } from '@/domains/people/composables';
import type { FamilyMember, OwnershipRead } from '@/domains/people/types';

const mocks = vi.hoisted(() => ({
  usePeopleStore: vi.fn(),
}));

vi.mock('@/domains/people/store', () => ({
  usePeopleStore: mocks.usePeopleStore,
}));

function makeMember(overrides: Partial<FamilyMember> = {}): FamilyMember {
  return {
    id: 1,
    name: 'Ada',
    role: 'adult',
    is_active: true,
    ...overrides,
  };
}

function makeOwnership(overrides: Partial<OwnershipRead> = {}): OwnershipRead {
  return {
    id: 1,
    kind: 'shared',
    member: null,
    splits: [
      { member: { id: 1, name: 'Ada', role: 'adult' }, percent: '50' },
      { member: { id: 2, name: 'Bob', role: 'adult' }, percent: '50' },
    ],
    is_in_use: false,
    ...overrides,
  };
}

describe('people composables (saas)', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    vi.stubGlobal(
      'confirm',
      vi.fn(() => true),
    );
  });

  it('handles member flows and success messages', async () => {
    const store = reactive({
      error: null as string | null,
      members: [] as FamilyMember[],
      ownerships: [] as OwnershipRead[],
      activeAdults: [makeMember(), makeMember({ id: 2, name: 'Bob' })],
      clearError: vi.fn(),
      fetchMembers: vi.fn(async () => undefined),
      createMember: vi.fn(async () => undefined),
      updateMember: vi.fn(async () => undefined),
      deleteMember: vi.fn(async () => undefined),
      fetchOwnerships: vi.fn(async () => undefined),
      updateSharedOwnership: vi.fn(async () => undefined),
      createSharedOwnership: vi.fn(async () => undefined),
      deleteOwnership: vi.fn(async () => undefined),
    });
    mocks.usePeopleStore.mockReturnValue(store);

    const members = usePeopleMembers();
    await members.ensureLoaded();
    expect(store.fetchMembers).toHaveBeenCalled();

    members.openCreate();
    expect(members.createOpen.value).toBe(true);
    members.form.name = ' Ada ';
    members.form.role = 'adult';
    await members.submit();
    expect(store.createMember).toHaveBeenCalledWith({ name: 'Ada', role: 'adult' });
    expect(members.successMessage.value).toContain('creado');

    const member = makeMember();
    members.openEdit(member);
    members.editForm.name = ' Ada Lovelace ';
    await members.saveEdit();
    expect(store.updateMember).toHaveBeenCalledWith(1, { name: 'Ada Lovelace', role: 'adult' });
    expect(members.editOpen.value).toBe(false);

    await members.toggleActive(1, false);
    expect(store.updateMember).toHaveBeenCalledWith(1, { is_active: false });

    await members.removeMember(member);
    expect(store.deleteMember).toHaveBeenCalledWith(1);
  });

  it('sorts and validates ownership flows', async () => {
    const store = reactive({
      error: null as string | null,
      members: [makeMember(), makeMember({ id: 2, name: 'Bob' })] as FamilyMember[],
      ownerships: [
        makeOwnership({ id: 2, kind: 'shared' }),
        makeOwnership({ id: 1, kind: 'individual', member: { id: 1, name: 'Ada', role: 'adult' } }),
      ] as OwnershipRead[],
      activeAdults: [makeMember(), makeMember({ id: 2, name: 'Bob' })],
      clearError: vi.fn(),
      fetchMembers: vi.fn(async () => undefined),
      createMember: vi.fn(async () => undefined),
      updateMember: vi.fn(async () => undefined),
      deleteMember: vi.fn(async () => undefined),
      fetchOwnerships: vi.fn(async () => undefined),
      updateSharedOwnership: vi.fn(async () => undefined),
      createSharedOwnership: vi.fn(async () => undefined),
      deleteOwnership: vi.fn(async () => undefined),
    });
    mocks.usePeopleStore.mockReturnValue(store);

    const ownerships = usePeopleOwnerships();
    await ownerships.ensureLoaded();
    expect(store.fetchOwnerships).not.toHaveBeenCalled();
    expect(store.fetchMembers).not.toHaveBeenCalled();

    expect(ownerships.ownershipsSorted.value.map((item) => item.id)).toEqual([2]);
    expect(ownerships.ownershipsSorted.value[0]?.kind).toBe('shared');
    ownerships.openCreate();
    ownerships.toggleMember(1);
    ownerships.toggleMember(2);
    ownerships.setEqualSplit();
    expect(ownerships.canCreate.value).toBe(true);
    await ownerships.submit();
    expect(store.createSharedOwnership).toHaveBeenCalled();

    ownerships.openEdit(makeOwnership({ id: 9 }));
    expect(ownerships.editId.value).toBe(9);
    ownerships.form.percents[1] = '60';
    ownerships.form.percents[2] = '40';
    await ownerships.submit();
    expect(store.updateSharedOwnership).toHaveBeenCalledWith(9, {
      splits: [
        { member_id: 1, percent: '60' },
        { member_id: 2, percent: '40' },
      ],
    });

    await ownerships.removeOwnership(9);
    expect(store.deleteOwnership).toHaveBeenCalledWith(9);
  });
});
