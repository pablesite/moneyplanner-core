import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import ItemList from '@/domains/net-worth/components/ItemList.vue';

const stubs = {
  ItemCategoryHeader: {
    props: ['label'],
    template: '<button data-test="toggle" @click="$emit(\'toggle\')">{{ label }}</button>',
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
});
