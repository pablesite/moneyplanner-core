/** @vitest-environment jsdom */
import { computed, reactive, ref } from 'vue';
import { describe, expect, it, vi, beforeEach } from 'vitest';
import { mount } from '@vue/test-utils';
import OwnershipManager from '../OwnershipManager.vue';

const mockUsePeopleOwnerships = vi.fn();

vi.mock('@/domains/people/composables', () => ({
  usePeopleOwnerships: () => mockUsePeopleOwnerships(),
}));

function makeState(overrides: Record<string, unknown> = {}) {
  return {
    store: { loading: false, error: null },
    showModal: ref(false),
    editId: ref<number | null>(null),
    successMessage: ref<string | null>(null),
    form: reactive({ memberIds: [] as number[], percents: {} as Record<number, string> }),
    adults: computed(() => []),
    canCreate: computed(() => false),
    ownershipsSorted: computed(() => []),
    ensureLoaded: vi.fn(async () => {}),
    refreshOwnerships: vi.fn(async () => {}),
    resetModal: vi.fn(),
    openCreate: vi.fn(),
    openEdit: vi.fn(),
    toggleMember: vi.fn(),
    setEqualSplit: vi.fn(),
    submit: vi.fn(async () => {}),
    removeOwnership: vi.fn(async () => {}),
    ...overrides,
  };
}

describe('OwnershipManager', () => {
  beforeEach(() => {
    mockUsePeopleOwnerships.mockReset();
  });

  it('shows success and empty states', () => {
    mockUsePeopleOwnerships.mockReturnValue(
      makeState({
        successMessage: ref('Titularidad compartida creada correctamente.'),
      }),
    );

    const wrapper = mount(OwnershipManager, {
      global: {
        stubs: {
          BaseModal: { template: '<div />' },
          OwnershipLabel: { template: '<span>ownership</span>' },
        },
      },
    });

    expect(wrapper.text()).toContain('Titularidad compartida creada correctamente.');
    expect(wrapper.text()).toContain('No hay titularidades');
  });

  it('calls create action from header button', async () => {
    const state = makeState();
    mockUsePeopleOwnerships.mockReturnValue(state);

    const wrapper = mount(OwnershipManager, {
      global: {
        stubs: {
          BaseModal: { template: '<div />' },
          OwnershipLabel: { template: '<span>ownership</span>' },
        },
      },
    });

    await wrapper.get('button.btn.btn-primary').trigger('click');
    expect(state.openCreate).toHaveBeenCalled();
    expect(state.ensureLoaded).toHaveBeenCalled();
  });
});
