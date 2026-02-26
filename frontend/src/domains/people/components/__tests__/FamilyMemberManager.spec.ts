/** @vitest-environment jsdom */
import { computed, reactive, ref } from 'vue';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import FamilyMemberManager from '../FamilyMemberManager.vue';

const mockUsePeopleMembers = vi.fn();

vi.mock('@/domains/people/composables', () => ({
  usePeopleMembers: () => mockUsePeopleMembers(),
}));

function makeState(overrides: Record<string, unknown> = {}) {
  return {
    store: { loading: false },
    form: reactive({ name: '', role: 'adult' }),
    saving: ref(false),
    rowBusy: ref<Record<number, boolean>>({}),
    createOpen: ref(false),
    successMessage: ref<string | null>(null),
    editOpen: ref(false),
    editForm: reactive({ id: null as number | null, name: '', role: 'adult' }),
    prettyError: computed(() => null),
    membersSorted: computed(() => []),
    ensureLoaded: vi.fn(async () => {}),
    refreshMembers: vi.fn(async () => {}),
    openCreate: vi.fn(),
    closeCreate: vi.fn(),
    submit: vi.fn(async () => {}),
    toggleActive: vi.fn(async () => {}),
    openEdit: vi.fn(),
    closeEdit: vi.fn(),
    saveEdit: vi.fn(async () => {}),
    removeMember: vi.fn(async () => {}),
    ...overrides,
  };
}

describe('FamilyMemberManager', () => {
  beforeEach(() => {
    mockUsePeopleMembers.mockReset();
  });

  it('shows empty and success states', () => {
    mockUsePeopleMembers.mockReturnValue(
      makeState({
        successMessage: ref('Miembro creado correctamente.'),
      }),
    );

    const wrapper = mount(FamilyMemberManager, {
      global: {
        stubs: {
          BaseModal: { template: '<div />' },
        },
      },
    });

    expect(wrapper.text()).toContain('Miembro creado correctamente.');
    expect(wrapper.text()).toContain('No hay miembros');
  });

  it('calls refresh action from header button', async () => {
    const state = makeState();
    mockUsePeopleMembers.mockReturnValue(state);

    const wrapper = mount(FamilyMemberManager, {
      global: {
        stubs: {
          BaseModal: { template: '<div />' },
        },
      },
    });

    await wrapper.get('button.btn').trigger('click');
    expect(state.refreshMembers).toHaveBeenCalled();
    expect(state.ensureLoaded).toHaveBeenCalled();
  });
});
