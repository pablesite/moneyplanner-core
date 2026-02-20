export type ExpenseCategoryKey =
  | 'savings_allocation'
  | 'financial_investments'
  | 'real_estate_assets'
  | 'tangible_assets'
  | 'consumption_expenses';

export type ExpenseSubcategory = {
  category: ExpenseCategoryKey;
  value: string;
  label: string;
};

export const expenseCategories: { value: ExpenseCategoryKey; label: string }[] = [
  { value: 'savings_allocation', label: 'Ahorro' },
  { value: 'financial_investments', label: 'Inversion financiera' },
  { value: 'real_estate_assets', label: 'Activos inmobiliarios' },
  { value: 'tangible_assets', label: 'Activos mobiliarios' },
  { value: 'consumption_expenses', label: 'Gasto puro y duro' },
];

export const expenseSubcategories: ExpenseSubcategory[] = [
  { category: 'savings_allocation', value: 'emergency_fund', label: 'Fondo de emergencia' },
  { category: 'savings_allocation', value: 'cash_reserve', label: 'Reserva de liquidez' },
  { category: 'savings_allocation', value: 'short_term_savings', label: 'Ahorro corto plazo' },
  { category: 'savings_allocation', value: 'long_term_savings', label: 'Ahorro largo plazo' },
  {
    category: 'savings_allocation',
    value: 'other_savings_allocation',
    label: 'Otros destinos de ahorro',
  },

  { category: 'financial_investments', value: 'index_funds_etf', label: 'Fondos indexados / ETF' },
  { category: 'financial_investments', value: 'pension_plan', label: 'Plan de pensiones' },
  { category: 'financial_investments', value: 'stocks_dividends', label: 'Acciones / dividendos' },
  { category: 'financial_investments', value: 'crypto', label: 'Criptomonedas' },
  { category: 'financial_investments', value: 'crowdlending_p2p', label: 'Crowdlending / P2P' },
  { category: 'financial_investments', value: 'roboadvisor', label: 'Roboadvisor' },
  {
    category: 'financial_investments',
    value: 'other_financial_investments',
    label: 'Otras inversiones financieras',
  },

  { category: 'real_estate_assets', value: 'property_purchase', label: 'Compra de inmueble' },
  {
    category: 'real_estate_assets',
    value: 'mortgage_principal',
    label: 'Amortizacion principal hipoteca',
  },
  { category: 'real_estate_assets', value: 'property_improvements', label: 'Reformas y mejoras' },
  {
    category: 'real_estate_assets',
    value: 'real_estate_fees_taxes',
    label: 'Gastos/impuestos de adquisicion',
  },
  {
    category: 'real_estate_assets',
    value: 'other_real_estate_assets',
    label: 'Otros destinos inmobiliarios',
  },

  { category: 'tangible_assets', value: 'vehicle_purchase', label: 'Compra de vehiculo' },
  {
    category: 'tangible_assets',
    value: 'home_furniture_appliances',
    label: 'Mobiliario y electrodomesticos',
  },
  { category: 'tangible_assets', value: 'technology_devices', label: 'Tecnologia y dispositivos' },
  {
    category: 'tangible_assets',
    value: 'jewelry_collectibles',
    label: 'Joyeria y coleccionables',
  },
  {
    category: 'tangible_assets',
    value: 'other_tangible_assets',
    label: 'Otros activos mobiliarios',
  },

  { category: 'consumption_expenses', value: 'housing_home', label: 'Vivienda y hogar' },
  { category: 'consumption_expenses', value: 'living_expenses', label: 'Gastos corrientes' },
  { category: 'consumption_expenses', value: 'family_childcare', label: 'Familia y bebe' },
  {
    category: 'consumption_expenses',
    value: 'transport_mobility',
    label: 'Transporte y movilidad',
  },
  { category: 'consumption_expenses', value: 'health_wellbeing', label: 'Salud y bienestar' },
  { category: 'consumption_expenses', value: 'education_growth', label: 'Formacion y desarrollo' },
  { category: 'consumption_expenses', value: 'leisure_lifestyle', label: 'Ocio y estilo de vida' },
  { category: 'consumption_expenses', value: 'gifts_donations', label: 'Regalos y donaciones' },
  {
    category: 'consumption_expenses',
    value: 'financial_commitments',
    label: 'Compromisos financieros',
  },
  {
    category: 'consumption_expenses',
    value: 'other_consumption_expenses',
    label: 'Otros gastos de consumo',
  },
];
