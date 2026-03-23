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
  accounting_integration_state?: 'linked' | 'auto_created' | 'needs_review' | null;
  currency: string;
  start_date?: string;
  payment_start_date?: string | null;
  investment_contribution_mode?: 'one_time' | 'periodic_contribution';
  investment_contribution_frequency?: 'monthly' | 'weekly';
  investment_contribution_currency?: string | null;
  monthly_contribution_amount?: string | null;
  market_value_override?: string | null;
  market_value_override_date?: string | null;
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
  expense_subcategory_override?: string | null;
  amortization_system?: string | null;
  opening_fees_amount?: string | null;
  early_repayment_fee_percent?: string | null;
  novation_subrogation_fee_amount?: string | null;
  linked_products_monthly_cost?: string | null;
  cancellation_forecast_enabled?: boolean;
  cancellation_date?: string | null;
  cancellation_fee_amount?: string | null;
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
  inflation_available: boolean;
  inflation_status: string;

  total_assets_real: string | null;
  total_liabilities_real: string | null;
  net_worth_real: string | null;

  assets_by_category_real: Record<string, string> | null;
  liabilities_by_category_real: Record<string, string> | null;
};

export type Settings = {
  base_currency: string;
  inflation_region: string;
};

export type TimelineRow = {
  date: string;
  total_assets: string;
  total_liabilities: string;
  net_worth: string;
  asset_positions: number;
  liability_positions: number;
};

export type TimelineFilters = {
  asset_category: string | null;
  liability_category: string | null;
};

export type NetWorthTimeline = {
  group_by: 'month';
  start_date: string;
  end_date: string;
  base_currency: string;
  filters: TimelineFilters;
  rows: TimelineRow[];
};

export type PositionTimelineRow = {
  date: string;
  value: string;
  value_base: string;
};

export type PositionTimeline = {
  group_by: 'month';
  position_type: 'asset' | 'liability';
  position_id: number;
  currency: string;
  base_currency: string;
  rows: PositionTimelineRow[];
};

export type AssetValuation = {
  id: number;
  asset_ref: number;
  asset_detail?: { id: number; name: string; category: string; subcategory: string } | null;
  valuation_date: string;
  value: string;
  source: string;
  note?: string;
  created_at?: string;
  updated_at?: string;
};

export type LiabilityValuation = {
  id: number;
  liability_ref: number;
  liability_detail?: { id: number; name: string; category: string } | null;
  valuation_date: string;
  value: string;
  source: string;
  note?: string;
  created_at?: string;
  updated_at?: string;
};

export type InvestmentAssetEvent = {
  id: number;
  asset_ref: number;
  asset_detail?: { id: number; name: string; category: string; subcategory: string } | null;
  event_date: string;
  event_type: string;
  amount: string;
  is_reinvested?: boolean;
  note?: string;
  created_at?: string;
  updated_at?: string;
};

export type LiquidityAssetEvent = {
  id: number;
  asset_ref: number;
  asset_detail?: { id: number; name: string; category: string; subcategory: string } | null;
  event_date: string;
  event_type: string;
  amount: string;
  note?: string;
  created_at?: string;
  updated_at?: string;
};

export type LiabilityEvent = {
  id: number;
  liability_ref: number;
  liability_detail?: { id: number; name: string; category: string } | null;
  event_date: string;
  event_type: string;
  amount: string;
  note?: string;
  created_at?: string;
  updated_at?: string;
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
