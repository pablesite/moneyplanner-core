export type IncomeCategoryKey =
  | 'salary'
  | 'business'
  | 'passive_income'
  | 'capital_gains'
  | 'transfers_support'
  | 'public_benefits'
  | 'other_income';

export type IncomeSubcategory = {
  category: IncomeCategoryKey;
  value: string;
  label: string;
};

export const incomeCategories: { value: IncomeCategoryKey; label: string }[] = [
  { value: 'salary', label: 'Salarios y trabajo' },
  { value: 'business', label: 'Actividad profesional/negocio' },
  { value: 'passive_income', label: 'Ingresos pasivos' },
  { value: 'capital_gains', label: 'Ganancias de capital' },
  { value: 'transfers_support', label: 'Transferencias recibidas' },
  { value: 'public_benefits', label: 'Prestaciones y ayudas' },
  { value: 'other_income', label: 'Otros ingresos' },
];

export const incomeSubcategories: IncomeSubcategory[] = [
  { category: 'salary', value: 'employee_salary', label: 'Nómina' },
  { category: 'salary', value: 'bonus_commission', label: 'Bonus/comisiones' },
  { category: 'salary', value: 'overtime', label: 'Horas extra' },
  { category: 'salary', value: 'severance', label: 'Indemnización' },
  { category: 'salary', value: 'other_salary', label: 'Otros salarios' },

  { category: 'business', value: 'self_employed_services', label: 'Autónomo/freelance' },
  { category: 'business', value: 'business_profit', label: 'Beneficio de negocio' },
  { category: 'business', value: 'professional_fees', label: 'Honorarios' },
  { category: 'business', value: 'royalties', label: 'Regalías' },
  { category: 'business', value: 'other_business', label: 'Otros ingresos de negocio' },

  { category: 'passive_income', value: 'real_estate_rent', label: 'Alquileres' },
  { category: 'passive_income', value: 'dividends', label: 'Dividendos' },
  { category: 'passive_income', value: 'interest_income', label: 'Intereses' },
  { category: 'passive_income', value: 'staking_yield', label: 'Staking/rendimiento cripto' },
  { category: 'passive_income', value: 'p2p_lending', label: 'Crowdlending/P2P' },
  { category: 'passive_income', value: 'other_passive', label: 'Otros ingresos pasivos' },

  {
    category: 'capital_gains',
    value: 'sale_financial_assets',
    label: 'Venta de activos financieros',
  },
  { category: 'capital_gains', value: 'sale_real_estate', label: 'Venta de inmueble' },
  {
    category: 'capital_gains',
    value: 'sale_business_asset',
    label: 'Venta de activo de negocio',
  },
  {
    category: 'capital_gains',
    value: 'sale_personal_asset',
    label: 'Venta de activo personal',
  },
  { category: 'capital_gains', value: 'fx_gain', label: 'Ganancia por divisa' },
  {
    category: 'capital_gains',
    value: 'other_capital_gains',
    label: 'Otras ganancias de capital',
  },

  { category: 'transfers_support', value: 'family_support', label: 'Apoyo familiar' },
  { category: 'transfers_support', value: 'gifts_received', label: 'Regalos recibidos' },
  { category: 'transfers_support', value: 'inheritance', label: 'Herencia' },
  {
    category: 'transfers_support',
    value: 'alimony_received',
    label: 'Pensión/alimentos recibidos',
  },
  {
    category: 'transfers_support',
    value: 'insurance_payout',
    label: 'Indemnización de seguro',
  },
  {
    category: 'transfers_support',
    value: 'other_transfers_support',
    label: 'Otras transferencias',
  },

  {
    category: 'public_benefits',
    value: 'unemployment_benefit',
    label: 'Prestación por desempleo',
  },
  {
    category: 'public_benefits',
    value: 'retirement_pension',
    label: 'Pensión de jubilación',
  },
  {
    category: 'public_benefits',
    value: 'disability_benefit',
    label: 'Prestación por incapacidad',
  },
  { category: 'public_benefits', value: 'scholarship', label: 'Beca' },
  { category: 'public_benefits', value: 'subsidy_grant', label: 'Subsidio/ayuda pública' },
  {
    category: 'public_benefits',
    value: 'other_public_benefits',
    label: 'Otras prestaciones públicas',
  },

  { category: 'other_income', value: 'tax_refund', label: 'Devolución de impuestos' },
  { category: 'other_income', value: 'one_off_adjustment', label: 'Ajuste puntual' },
  { category: 'other_income', value: 'misc', label: 'Miscelánea' },
  { category: 'other_income', value: 'other', label: 'Otros ingresos' },
];
