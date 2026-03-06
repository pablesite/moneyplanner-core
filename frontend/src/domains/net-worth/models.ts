export type AssetImprovement = {
  id?: number;
  name: string;
  reform_date: string;
  amount: string;
  amortization_method: 'none' | 'straight_line' | 'manual';
  amortization_term_years?: number | null;
  annual_interest_tae?: string | null;
  capitalize_interest?: boolean;
  manual_current_value?: string | null;
  notes?: string;
  created_at?: string;
  updated_at?: string;
};

export type Asset = {
  id: number;
  name: string;
  category: string;
  subcategory: string;
  tracking_mode: string;
  accounting_account_id: number | null;
  currency: string;
  start_date?: string;
  investment_contribution_mode?: 'one_time' | 'periodic_contribution';
  investment_contribution_frequency?: 'monthly' | 'weekly';
  monthly_contribution_amount?: string | null;
  initial_purchase_value?: string | null;
  amortization_method?: string;
  amortization_term_years?: number | null;
  valuation_model?: string;
  land_value_share_percent?: string | null;
  land_annual_appreciation_percent?: string | null;
  building_annual_depreciation_percent?: string | null;
  improvements?: AssetImprovement[];
  amount: string;
  annual_interest_tae?: string | null;
  estimated_average_balance_for_interest?: string | null;
  deposit_term_months?: number | null;
  monthly_payment_amount?: string | null;
  estimated_monthly_payment_amount?: string | null;
  estimated_outstanding_amount?: string | null;
  effective_amount?: string | null;
  expected_end_date?: string | null;
  term_months?: number | null;
  principal_amount?: string | null;
  rate_type?: string;
  payment_frequency?: string;
  amortization_system?: string | null;
  opening_fees_amount?: string | null;
  early_repayment_fee_percent?: string | null;
  novation_subrogation_fee_amount?: string | null;
  linked_products_monthly_cost?: string | null;
  amount_base?: string;
  is_active: boolean;
  notes: string;
  ownership_ref?: number | null;
  financed_asset_ref?: number | null;
};

export type Liability = Asset;

export type Snapshot = {
  id: number;
  snapshot_date: string;
  base_currency: string;
  total_assets: string;
  total_liabilities: string;
  net_worth: string;
  created_at: string;
};

export type Summary = {
  base_currency: string;

  total_assets: string;
  total_liabilities: string;
  net_worth: string;

  assets_by_category: Record<string, string>;
  assets_by_subcategory: Record<string, string>;
  liabilities_by_category: Record<string, string>;

  inflation_region: string | null;
  inflation_base_period: string | null;

  total_assets_real: string | null;
  total_liabilities_real: string | null;
  net_worth_real: string | null;

  assets_by_category_real: Record<string, string> | null;
  liabilities_by_category_real: Record<string, string> | null;
};

export type Ownership = {
  id: number;
  kind: 'individual' | 'shared';
  member: { id: number; name: string; role: 'adult' | 'child' } | null;
  splits: { member: { id: number; name: string; role: 'adult' | 'child' }; percent: string }[];
  notes: string;
};

export type NetWorthWritePayload = Partial<Asset> & {
  financed_asset_id?: number | null;
};
