import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import ItemForm from '@/domains/net-worth/components/ItemForm.vue';

describe('ItemForm (core)', () => {
  it('submits normalized payload', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo pasivo',
        categories: [{ value: 'other', label: 'Otros' }],
        assets: [{ id: 1, name: 'Auto', category: 'real_estate' }],
        showFinancedAsset: true,
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Caja');
    const selects = wrapper.findAll('select');
    expect(selects.length).toBeGreaterThanOrEqual(4);
    const categorySelect = selects[0]!;
    const currencySelect = selects[1]!;
    const financedAssetSelect = selects.find((s) => s.text().includes('No financia'))!;

    await categorySelect.setValue('other');
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('1.234,56');
    await wrapper.find('input[placeholder="Ej: 24"]').setValue('24');
    await financedAssetSelect.setValue('1');
    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        name: 'Caja',
        category: 'other',
        currency: 'EUR',
        amount: '1234.56',
        term_months: 24,
        expected_end_date: expect.any(String),
        financed_asset_id: 1,
      }),
    );
  });

  it('links term months and expected end date for liabilities', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo pasivo',
        categories: [{ value: 'other', label: 'Otros' }],
        assets: [],
        showFinancedAsset: true,
        onSubmit: vi.fn().mockResolvedValue(undefined),
      },
    });

    await wrapper.find('input[type="date"]').setValue('2024-09-05');
    await wrapper.find('input[placeholder="Ej: 24"]').setValue('24');

    const dateInputs = wrapper.findAll('input[type="date"]');
    expect(dateInputs[1]?.element).toBeTruthy();
    expect((dateInputs[1]!.element as HTMLInputElement).value).toBe('2026-09-05');
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
    expect(wrapper.text()).toContain('Importe');
  });

  it('requires deposit duration for short-term deposits', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'cash', label: 'Liquidez' }],
        subcategories: [{ category: 'cash', value: 'short_term_deposit', label: 'Deposito a corto plazo' }],
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Deposito Facto');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('cash');
    await selects[1]!.setValue('short_term_deposit');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('10000');
    await wrapper.find('input[placeholder="TAE anual (%)"]').setValue('3');
    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain('duracion del deposito');

    const depositTermSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Selecciona duración'))!;
    await depositTermSelect.setValue('6');
    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'cash',
        subcategory: 'short_term_deposit',
        deposit_term_months: 6,
      }),
    );
  });

  it('updates estimated average balance label with selected currency', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'cash', label: 'Liquidez' }],
        subcategories: [{ category: 'cash', value: 'crypto_spot_earn', label: 'Spot/Earn Cripto' }],
        onSubmit: vi.fn().mockResolvedValue(undefined),
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Earn Binance');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('cash');
    await selects[1]!.setValue('crypto_spot_earn');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('USD');
    await wrapper.find('input[placeholder="TAE anual (%)"]').setValue('5');

    expect(wrapper.text()).toContain('Importe anual medio previsto (USD)');
    expect(wrapper.text()).not.toContain('Importe anual medio previsto (€)');
  });

  it('submits primary home auto valuation parameters', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [{ category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' }],
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Casa');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('real_estate');
    await selects[1]!.setValue('primary_home');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('100000');

    const modelSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Automatica (suelo + construccion)'))!;
    await modelSelect.setValue('real_estate_auto');
    await wrapper.find('input[placeholder="Ej: 30"]').setValue('35');
    await wrapper.find('input[placeholder="Ej: 3"]').setValue('4');
    await wrapper.find('input[placeholder="Ej: 1"]').setValue('1.2');

    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'real_estate',
        subcategory: 'primary_home',
        valuation_model: 'real_estate_auto',
        land_value_share_percent: '35',
        land_annual_appreciation_percent: '4',
        building_annual_depreciation_percent: '1.2',
      }),
    );
  });

  it('autofills valuation parameters when selecting a profile and allows custom edits', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [{ category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' }],
        onSubmit: vi.fn().mockResolvedValue(undefined),
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Casa');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('real_estate');
    await selects[1]!.setValue('primary_home');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('100000');

    const modelSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Automatica (suelo + construccion)'))!;
    await modelSelect.setValue('real_estate_auto');
    await wrapper.find('input[placeholder="Ej: 30"]').setValue('35');

    const profileSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Conservador') && s.text().includes('Personalizado'))!;
    await profileSelect.setValue('balanced');

    const landInput = wrapper.find('input[placeholder="Ej: 30"]');
    const growthInput = wrapper.find('input[placeholder="Ej: 3"]');
    const depreciationInput = wrapper.find('input[placeholder="Ej: 1"]');
    expect((landInput.element as HTMLInputElement).value).toBe('35');
    expect((growthInput.element as HTMLInputElement).value).toBe('6,8');
    expect((depreciationInput.element as HTMLInputElement).value).toBe('0.3');

    await growthInput.setValue('7.1');
    expect((profileSelect.element as HTMLSelectElement).value).toBe('custom');
  });

  it('limits land share and land appreciation to one decimal', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [{ category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' }],
        onSubmit: vi.fn().mockResolvedValue(undefined),
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Casa');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('real_estate');
    await selects[1]!.setValue('primary_home');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('100000');
    const modelSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Automatica (suelo + construccion)'))!;
    await modelSelect.setValue('real_estate_auto');

    const landInput = wrapper.find('input[placeholder="Ej: 30"]');
    const growthInput = wrapper.find('input[placeholder="Ej: 3"]');
    await landInput.setValue('42.37');
    await growthInput.setValue('7.58');

    expect((landInput.element as HTMLInputElement).value).toBe('42,3');
    expect((growthInput.element as HTMLInputElement).value).toBe('7,5');
  });

  it('allows typing intermediate decimal values in land appreciation input', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [{ category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' }],
        onSubmit: vi.fn().mockResolvedValue(undefined),
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Casa');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('real_estate');
    await selects[1]!.setValue('primary_home');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('100000');
    const modelSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Automatica (suelo + construccion)'))!;
    await modelSelect.setValue('real_estate_auto');

    const growthInput = wrapper.find('input[placeholder="Ej: 3"]');
    await growthInput.setValue('7.');
    expect((growthInput.element as HTMLInputElement).value).toBe('7,');
    await growthInput.setValue('7.5');
    expect((growthInput.element as HTMLInputElement).value).toBe('7,5');
  });

  it('does not require schedule fields for credit card liabilities', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo pasivo',
        categories: [{ value: 'credit_card', label: 'Tarjeta' }],
        showFinancedAsset: true,
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Tarjeta ECI');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('credit_card');
    await selects[1]!.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('213');
    await wrapper.find('input[placeholder="TAE anual (%)"]').setValue('19.5');

    expect(wrapper.text()).not.toContain('Indica cuotas o fecha fin');
    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'credit_card',
        amount: '213',
        annual_interest_tae: '19.5',
      }),
    );
  });
});
