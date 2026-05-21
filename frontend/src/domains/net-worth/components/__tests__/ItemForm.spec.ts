import { flushPromises, mount } from '@vue/test-utils';
import { describe, expect, it, vi } from 'vitest';
import ItemForm from '@/domains/net-worth/components/ItemForm.vue';

describe('ItemForm (saas)', () => {
  it('submits normalized payload including ownership and financed asset', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo pasivo',
        categories: [{ value: 'other', label: 'Otros' }],
        ownerships: [
          {
            id: 10,
            kind: 'individual',
            member: { id: 1, name: 'Pablo', role: 'adult' },
            splits: [],
            notes: '',
          },
        ],
        assets: [{ id: 1, name: 'Auto', category: 'real_estate' }],
        showFinancedAsset: true,
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Caja');
    const selects = wrapper.findAll('select');
    expect(selects.length).toBeGreaterThanOrEqual(5);
    const categorySelect = selects[0]!;
    const currencySelect = selects[1]!;
    const ownershipSelect = selects.find((s) => s.text().includes('Selecciona titularidad'))!;
    const financedAssetSelect = selects.find((s) => s.text().includes('No financia'))!;

    await categorySelect.setValue('other');
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('1.234,56');
    await wrapper.find('input[placeholder="Ej: 24"]').setValue('24');
    await ownershipSelect.setValue('10');
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
        ownership_id: 10,
        financed_asset_id: 1,
      }),
    );
  });

  it('links term months and expected end date for liabilities', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo pasivo',
        categories: [{ value: 'other', label: 'Otros' }],
        ownerships: [],
        assets: [],
        showFinancedAsset: true,
        onSubmit: vi.fn().mockResolvedValue(undefined),
      },
    });

    await wrapper.find('input[type="date"]').setValue('2024-09-05');
    await wrapper.find('input[placeholder="Ej: 24"]').setValue('24');

    const dateInputs = wrapper.findAll('input[type="date"]');
    expect((dateInputs[2]!.element as HTMLInputElement).value).toBe('2026-09-05');
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
    expect(wrapper.text()).toContain('Importe inv');
  });

  it('shows required field message and blocks submit when name is missing', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'furnishings', label: 'Mobiliario' }],
        subcategories: [{ category: 'furnishings', value: 'technology', label: 'Tecnologia' }],
        onSubmit,
      },
    });

    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('furnishings');
    await selects[1]!.setValue('technology');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('10000');
    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).not.toHaveBeenCalled();
    expect(wrapper.text()).toContain('Nombre obligatorio');
  });

  it('allows straight-line amortization without initial purchase value when amount is provided', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'furnishings', label: 'Mobiliario' }],
        subcategories: [{ category: 'furnishings', value: 'technology', label: 'Tecnologia' }],
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Portatil');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('furnishings');
    await selects[1]!.setValue('technology');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('1800');

    const amortizationMethodSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Sin amortización') && s.text().includes('Lineal'))!;
    await amortizationMethodSelect.setValue('straight_line');
    await wrapper.find('input[placeholder="Ej: 10"]').setValue('4');

    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0]![0] as Record<string, unknown>;
    expect(payload.amount).toBe('1800');
    expect(payload.amortization_method).toBe('straight_line');
    expect(payload.amortization_term_years).toBe(4);
    expect(payload.initial_purchase_value).toBeUndefined();
  });

  it('shows degressive residual hint for sports equipment furnishings', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'furnishings', label: 'Mobiliario' }],
        subcategories: [
          { category: 'furnishings', value: 'sports_equipment', label: 'Equipamiento deportivo' },
        ],
        onSubmit: vi.fn().mockResolvedValue(undefined),
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Bici');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('furnishings');
    await selects[1]!.setValue('sports_equipment');

    expect(wrapper.text()).toContain('decreciente + residual por subcategoría');
    expect(wrapper.text()).toContain('suelo residual del 20%');
  });

  it('does not render initial purchase value field for furnishings amortization', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'furnishings', label: 'Mobiliario' }],
        subcategories: [{ category: 'furnishings', value: 'vehicles', label: 'Vehiculos' }],
        onSubmit: vi.fn().mockResolvedValue(undefined),
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Coche');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('furnishings');
    await selects[1]!.setValue('vehicles');

    expect(wrapper.text()).not.toContain('Valor compra inicial');
  });

  it('forces non-amortized method for jewelry furnishings', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'furnishings', label: 'Mobiliario' }],
        subcategories: [{ category: 'furnishings', value: 'jewelry', label: 'Joyeria' }],
        onSubmit: vi.fn().mockResolvedValue(undefined),
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Anillo');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('furnishings');
    await selects[1]!.setValue('jewelry');

    const amortizationMethodSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Sin amortización (joyería)'))!;
    expect(amortizationMethodSelect.text()).not.toContain('Lineal');
    expect(amortizationMethodSelect.text()).not.toContain('Manual');
    expect(wrapper.text()).toContain("En 'Joyería' no se aplica amortización automática.");
  });

  it('submits sports equipment without manual term years', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'furnishings', label: 'Mobiliario' }],
        subcategories: [
          { category: 'furnishings', value: 'sports_equipment', label: 'Equipamiento deportivo' },
        ],
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Bici');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('furnishings');
    await selects[1]!.setValue('sports_equipment');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('1800');

    const amortizationMethodSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('decreciente + residual por subcategoría'))!;
    await amortizationMethodSelect.setValue('straight_line');

    expect(wrapper.text()).not.toContain('Plazo de amortización (anos) obligatorio');
    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0]![0] as Record<string, unknown>;
    expect(payload.amortization_method).toBe('straight_line');
    expect(payload.amortization_term_years).toBeUndefined();
  });

  it('requires deposit duration for short-term deposits', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'cash', label: 'Liquidez' }],
        subcategories: [
          { category: 'cash', value: 'short_term_deposit', label: 'Deposito a corto plazo' },
        ],
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
    expect(wrapper.text()).toContain('duración del depósito');

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
        subcategories: [
          { category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' },
        ],
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
      .find((s) => s.text().includes('Automática (suelo + construcción)'))!;
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

  it('submits primary home improvements along with auto valuation', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [
          { category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' },
        ],
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
      .find((s) => s.text().includes('Automática (suelo + construcción)'))!;
    await modelSelect.setValue('real_estate_auto');

    await wrapper.find('button.ui-item-form-mini-btn').trigger('click');
    await wrapper.find('input[placeholder="Ej: Reforma cocina"]').setValue('Reforma cocina');
    const dateInputs = wrapper.findAll('input[type="date"]');
    await dateInputs[1]!.setValue('2025-06-01');
    await wrapper.find('input[placeholder="Ej: 12000"]').setValue('12000');

    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        valuation_model: 'real_estate_auto',
        improvements: [
          expect.objectContaining({
            name: 'Reforma cocina',
            reform_date: '2025-06-01',
            amount: '12000',
            amortization_method: 'none',
          }),
        ],
      }),
    );
  });

  it('uses default term years, disables capitalized interest with TAE 0, and shows discard label for new improvements', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [
          { category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' },
        ],
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
      .find((s) => s.text().includes('Automática (suelo + construcción)'))!;
    await modelSelect.setValue('real_estate_auto');
    await wrapper.find('button.ui-item-form-mini-btn').trigger('click');

    const reformAmortizationSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Sin amortización') && s.text().includes('Lineal'))!;
    await reformAmortizationSelect.setValue('straight_line');

    const termInput = wrapper.find('input[placeholder="Ej: 10"]');
    expect((termInput.element as HTMLInputElement).value).toBe('10');

    expect(wrapper.text()).toContain(
      'Disponible solo cuando la TAE de financiación es mayor que 0.',
    );
    expect(wrapper.text()).toContain('Descartar reforma');
  });

  it('autofills valuation parameters when selecting a profile and allows custom edits', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [
          { category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' },
        ],
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
      .find((s) => s.text().includes('Automática (suelo + construcción)'))!;
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

  it('detects conservative profile in edit mode when backend returns trailing zeros', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Editar activo',
        mode: 'edit',
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [
          { category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' },
        ],
        onSubmit: vi.fn().mockResolvedValue(undefined),
        initial: {
          name: 'Casa',
          category: 'real_estate',
          subcategory: 'primary_home',
          amount: '91000',
          start_date: '2016-02-21',
          valuation_model: 'real_estate_auto',
          land_value_share_percent: '42.6',
          land_annual_appreciation_percent: '5.5',
          building_annual_depreciation_percent: '0.40',
          notes: '',
          currency: 'EUR',
          tracking_mode: 'manual',
          is_active: true,
        },
      },
    });

    const profileSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Conservador') && s.text().includes('Personalizado'))!;
    expect((profileSelect.element as HTMLSelectElement).value).toBe('conservative');
  });

  it('limits land share and land appreciation to one decimal', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [
          { category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' },
        ],
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
      .find((s) => s.text().includes('Automática (suelo + construcción)'))!;
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
        subcategories: [
          { category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' },
        ],
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
      .find((s) => s.text().includes('Automática (suelo + construcción)'))!;
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
        ownerships: [],
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

  it('submits mortgage cancellation forecast fields', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nueva hipoteca',
        categories: [{ value: 'mortgage', label: 'Hipoteca' }],
        showFinancedAsset: true,
        ownerships: [],
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Hipoteca casa');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('mortgage');
    await selects[1]!.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('120000');
    await wrapper.find('input[placeholder="Ej: 24"]').setValue('360');
    await wrapper.find('input[placeholder="0"]').setValue('2.5');

    const cancellationToggle = wrapper
      .findAll('input[type="checkbox"]')
      .find((input) =>
        input.element.closest('label')?.textContent?.includes('prevision de cancelacion'),
      )!;
    await cancellationToggle.setValue(true);

    const dateInputs = wrapper.findAll('input[type="date"]');
    await dateInputs[dateInputs.length - 1]!.setValue('2027-06-15');
    const cancellationDetails = wrapper
      .findAll('details')
      .find((details) => details.find('summary').text().includes('Prevision de cancelacion'))!;
    await cancellationDetails.find('input[placeholder="Opcional"]').setValue('450');

    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'mortgage',
        cancellation_forecast_enabled: true,
        cancellation_date: '2027-06-15',
        cancellation_fee_amount: '450',
      }),
    );
  });

  it('maps non-habitual real estate usage to rental subcategory on submit', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [
          { category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' },
          { category: 'real_estate', value: 'second_home', label: 'Vivienda no habitual' },
          { category: 'real_estate', value: 'rental', label: 'Vivienda no habitual (alquiler)' },
        ],
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Apartamento playa');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('real_estate');
    await selects[1]!.setValue('second_home');
    const usageSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Propio') && s.text().includes('Alquiler'))!;
    await usageSelect.setValue('rental');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('120000');

    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'real_estate',
        subcategory: 'rental',
      }),
    );
  });

  it('allows auto valuation fields for non-habitual real estate', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [
          { category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' },
          { category: 'real_estate', value: 'second_home', label: 'Vivienda no habitual' },
          { category: 'real_estate', value: 'rental', label: 'Vivienda no habitual (alquiler)' },
        ],
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Atico');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('real_estate');
    await selects[1]!.setValue('second_home');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('200000');

    const modelSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Automática (suelo + construcción)'))!;
    await modelSelect.setValue('real_estate_auto');
    await wrapper.find('input[placeholder="Ej: 30"]').setValue('40');
    await wrapper.find('input[placeholder="Ej: 3"]').setValue('5');
    await wrapper.find('input[placeholder="Ej: 1"]').setValue('1.1');

    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'real_estate',
        subcategory: 'second_home',
        valuation_model: 'real_estate_auto',
        land_value_share_percent: '40',
        land_annual_appreciation_percent: '5',
        building_annual_depreciation_percent: '1.1',
      }),
    );
  });

  it('defaults auto valuation profile to dynamic values', async () => {
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'real_estate', label: 'Inmuebles' }],
        subcategories: [
          { category: 'real_estate', value: 'primary_home', label: 'Vivienda habitual' },
          { category: 'real_estate', value: 'second_home', label: 'Vivienda no habitual' },
        ],
        onSubmit: vi.fn().mockResolvedValue(undefined),
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Piso');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('real_estate');
    await selects[1]!.setValue('second_home');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('180000');

    const modelSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Automática (suelo + construcción)'))!;
    await modelSelect.setValue('real_estate_auto');

    const profileSelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Dinámico') && s.text().includes('Personalizado'))!;
    expect((profileSelect.element as HTMLSelectElement).value).toBe('dynamic');
    expect((wrapper.find('input[placeholder="Ej: 3"]').element as HTMLInputElement).value).toBe(
      '8',
    );
    expect((wrapper.find('input[placeholder="Ej: 1"]').element as HTMLInputElement).value).toBe(
      '0.2',
    );
  });

  it('submits interval contribution payload for investment assets', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'investments', label: 'Inversiones' }],
        subcategories: [{ category: 'investments', value: 'funds', label: 'Fondos' }],
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('Reserva vivienda');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('investments');
    await selects[1]!.setValue('funds');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('5000');
    await wrapper.find('button.btn.ui-item-form-mini-btn').trigger('click');
    const dateInputs = wrapper.findAll('input[type="date"]');
    await dateInputs[0]!.setValue('2026-01-15');
    await dateInputs[1]!.setValue('2026-01-15');
    await dateInputs[2]!.setValue('2027-12-15');
    const decimalInputs = wrapper.findAll('input[inputmode="decimal"]');
    await decimalInputs[1]!.setValue('300');

    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        category: 'investments',
        amount: '5000',
        initial_purchase_value: '5000',
        contribution_intervals: [
          {
            start_date: '2026-01-15',
            end_date: '2027-12-15',
            amount: '300',
            frequency: 'monthly',
            currency: 'EUR',
          },
        ],
      }),
    );
  });

  it('allows indefinite investment interval with weekly frequency', async () => {
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    const wrapper = mount(ItemForm, {
      props: {
        title: 'Nuevo activo',
        categories: [{ value: 'investments', label: 'Inversiones' }],
        subcategories: [{ category: 'investments', value: 'etfs', label: 'ETFs' }],
        onSubmit,
      },
    });

    await wrapper.find('input[placeholder="Nombre"]').setValue('ETF Physical Gold');
    const selects = wrapper.findAll('select');
    await selects[0]!.setValue('investments');
    await selects[1]!.setValue('etfs');
    await wrapper.find('button.btn.ui-item-form-mini-btn').trigger('click');
    const frequencySelect = wrapper
      .findAll('select')
      .find((s) => s.text().includes('Mensual') && s.text().includes('Semanal'))!;
    await frequencySelect.setValue('weekly');
    const currencySelect = selects.find((s) => s.text().includes('Selecciona moneda'))!;
    await currencySelect.setValue('EUR');
    await wrapper.find('input[placeholder="Importe"]').setValue('1645.99');
    const dateInputs = wrapper.findAll('input[type="date"]');
    await dateInputs[0]!.setValue('2026-03-06');
    await dateInputs[1]!.setValue('2026-03-06');
    const decimalInputs = wrapper.findAll('input[inputmode="decimal"]');
    await decimalInputs[1]!.setValue('137.4');

    await wrapper.find('button.btn-primary').trigger('click');
    await flushPromises();

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        contribution_intervals: [
          expect.objectContaining({
            start_date: '2026-03-06',
            end_date: null,
            amount: '137.4',
            frequency: 'weekly',
          }),
        ],
      }),
    );
  });
});
