/** @vitest-environment jsdom */
import { describe, expect, it } from 'vitest';
import { mount } from '@vue/test-utils';
import ItemDisplayRow from '../ItemDisplayRow.vue';

describe('ItemDisplayRow', () => {
  it('renders main item data', () => {
    const wrapper = mount(ItemDisplayRow, {
      props: {
        item: { id: 7, name: 'Cuenta corriente', is_active: true, currency: 'EUR' },
        formattedAmount: '1,000.00',
        isLiabilitiesList: false,
        financedAssetName: null,
      },
    });

    expect(wrapper.text()).toContain('Cuenta corriente');
    expect(wrapper.text()).toContain('1,000.00');
  });

  it('emits edit, archive and delete events with item id', async () => {
    const wrapper = mount(ItemDisplayRow, {
      props: {
        item: { id: 11, name: 'Hipoteca', is_active: false, currency: 'EUR' },
        formattedAmount: '800.00',
        isLiabilitiesList: true,
        financedAssetName: 'Casa',
        ownershipLabel: 'Ana',
        sharePercent: 50,
      },
    });

    await wrapper.get('button[aria-label="Editar"]').trigger('click');
    await wrapper.get('button[aria-label="Archivar"]').trigger('click');
    await wrapper.get('button[aria-label="Eliminar"]').trigger('click');

    expect(wrapper.emitted('edit')?.[0]).toEqual([11]);
    expect(wrapper.emitted('archive')?.[0]).toEqual([11]);
    expect(wrapper.emitted('delete')?.[0]).toEqual([11]);
    expect(wrapper.text()).toContain('Financia: Casa');
  });
});
