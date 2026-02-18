import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import ItemForm from '@/domains/net-worth/components/ItemForm.vue';

describe('ItemForm (core)', () => {
  it('submits normalized payload', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'cash', label: 'Cash' }],
        subcategories: [{ value: 'wallet', label: 'Wallet', category: 'cash' }],
        assets: [{ id: 1, name: 'Auto', category: 'real_estate' }],
        showFinancedAsset: true,
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Caja');
    const selects = wrapper.findAll('select');
    expect(selects.length).toBeGreaterThanOrEqual(4);
    const categorySelect = selects[0]!;
    const subcategorySelect = selects[1]!;
    const currencySelect = selects[2]!;
    const financedAssetSelect = selects[3]!;

    await categorySelect.setValue('cash');
    await subcategorySelect.setValue('wallet');
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('1.234,56');
    await financedAssetSelect.setValue('1');
    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Caja',
        category: 'cash',
        subcategory: 'wallet',
        currency: 'EUR',
        amount: '1234.56',
        financed_asset_id: 1,
      }),
    );
  });

  it('shows amount validation errors', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'cash', label: 'Cash' }],
        onSubmit: vi.fn().mockResolvedValue(undefined),
      },
    });

    await wrapper.find('input[placeholder="Importe"]').setValue('12.3.4');
    expect(wrapper.text()).toContain('Importe inválido');
  });
});
