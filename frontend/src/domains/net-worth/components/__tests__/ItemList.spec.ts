import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import ItemList from '@/domains/net-worth/components/ItemList.vue';

const stubs = {
  ItemCategoryHeader: {
    props: ['label', 'baseLabel'],
    template:
      '<button data-test="toggle" @click="$emit(\'toggle\')">{{ label }}</button><span data-test="category-base">{{ baseLabel }}</span>',
  },
  ItemSubgroupHeader: {
    template: '<div data-test="subgroup"></div>',
  },
  ItemDisplayRow: {
    template:
      '<div><button data-test="edit" @click="$emit(\'edit\')">edit</button><button data-test="archive" @click="$emit(\'archive\')">archive</button><button data-test="delete" @click="$emit(\'delete\')">delete</button></div>',
  },
  EditableItemRow: {
    template:
      '<div><button data-test="save" @click="$emit(\'save\')">save</button><button data-test="cancel" @click="$emit(\'cancel\')">cancel</button></div>',
  },
};

describe('ItemList (core)', () => {
  it('handles add, archive, delete and edit/update flow', async () => {
    const onAdd = vi.fn();
    const onArchive = vi.fn().mockResolvedValue(undefined);
    const onDelete = vi.fn().mockResolvedValue(undefined);
    const onUpdate = vi.fn().mockResolvedValue(undefined);
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    const wrapper = mount(ItemList, {
      props: {
        title: 'Activos',
        items: [
          {
            id: 1,
            name: 'Caja',
            category: 'cash',
            subcategory: 'wallet',
            amount: '100.00',
            currency: 'EUR',
            notes: '',
            is_active: true,
            tracking_mode: 'manual',
            accounting_account_id: null,
          },
          {
            id: 2,
            name: 'Archivado',
            category: 'cash',
            subcategory: 'wallet',
            amount: '1.00',
            currency: 'EUR',
            notes: '',
            is_active: false,
            tracking_mode: 'manual',
            accounting_account_id: null,
          },
        ],
        categories: [{ value: 'cash', label: 'Cash' }],
        subcategories: [{ value: 'wallet', label: 'Wallet', category: 'cash' }],
        onUpdate,
        onArchive,
        onDelete,
        onAdd,
      },
      global: { stubs },
    });

    await wrapper.find('button[aria-label="Anadir"]').trigger('click');
    expect(onAdd).toHaveBeenCalled();

    await wrapper.find('[data-test="toggle"]').trigger('click');
    await wrapper.find('[data-test="archive"]').trigger('click');
    expect(onArchive).toHaveBeenCalledWith(1);
    await wrapper.find('[data-test="delete"]').trigger('click');
    expect(onDelete).toHaveBeenCalledWith(1);

    await wrapper.find('[data-test="edit"]').trigger('click');
    await wrapper.find('[data-test="save"]').trigger('click');
    await flushPromises();

    expect(onUpdate).toHaveBeenCalledWith(
      1,
      expect.objectContaining({
        name: 'Caja',
        category: 'cash',
        amount: '100',
      }),
    );
    expect(wrapper.findAll('[data-test="edit"]')).toHaveLength(1);
  });

  it('applies ownership share over effective_amount when present', () => {
    const amountRowStub = {
      props: ['formattedAmount'],
      template: '<div data-test="amount">{{ formattedAmount }}</div>',
    };
    const wrapper = mount(ItemList, {
      props: {
        title: 'Activos',
        ownershipFilterValue: 1,
        items: [
          {
            id: 10,
            name: 'Palmito',
            category: 'real_estate',
            subcategory: 'primary_home',
            amount: '91000.00',
            effective_amount: '145905.37',
            currency: 'EUR',
            notes: '',
            is_active: true,
            tracking_mode: 'manual',
            accounting_account_id: null,
            ownership_ref: 22,
          },
        ],
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [
          { value: 'primary_home', label: 'Vivienda habitual', category: 'real_estate' },
        ],
        ownerships: [
          {
            id: 22,
            kind: 'shared',
            member: null,
            splits: [
              { member: { id: 1, name: 'Ana', role: 'adult' }, percent: '50.00' },
              { member: { id: 2, name: 'Pablo', role: 'adult' }, percent: '50.00' },
            ],
            notes: '',
          },
        ],
        onUpdate: vi.fn().mockResolvedValue(undefined),
        onArchive: vi.fn().mockResolvedValue(undefined),
      },
      global: {
        stubs: {
          ...stubs,
          ItemDisplayRow: amountRowStub,
        },
      },
    });

    expect(wrapper.text()).toContain('72.952,69');
  });

  it('uses visible rows total when archived rows are hidden', () => {
    const wrapper = mount(ItemList, {
      props: {
        title: 'Activos',
        showArchived: false,
        totalBase: '101.00',
        baseCurrency: 'EUR',
        items: [
          {
            id: 1,
            name: 'Caja',
            category: 'cash',
            subcategory: 'wallet',
            amount: '100.00',
            amount_base: '100.00',
            currency: 'EUR',
            notes: '',
            is_active: true,
            tracking_mode: 'manual',
            accounting_account_id: null,
          },
          {
            id: 2,
            name: 'Archivado',
            category: 'cash',
            subcategory: 'wallet',
            amount: '1.00',
            amount_base: '1.00',
            currency: 'EUR',
            notes: '',
            is_active: false,
            tracking_mode: 'manual',
            accounting_account_id: null,
          },
        ],
        categories: [{ value: 'cash', label: 'Cash' }],
        subcategories: [{ value: 'wallet', label: 'Wallet', category: 'cash' }],
        onUpdate: vi.fn().mockResolvedValue(undefined),
        onArchive: vi.fn().mockResolvedValue(undefined),
      },
      global: { stubs },
    });

    expect(wrapper.text()).toContain('100');
    expect(wrapper.text()).not.toContain('101');
    expect(wrapper.find('[data-test="category-base"]').text()).toContain('100');
    expect(wrapper.find('[data-test="category-base"]').text()).not.toContain('101');
  });
});
