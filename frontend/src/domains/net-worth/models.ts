export type Asset = {
  id: number;
  name: string;
  category: string;
  subcategory: string;
  tracking_mode: string;
  accounting_account_id: number | null;
  currency: string;
  amount: string;
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

export type NetWorthWritePayload = Partial<Asset> & {
  financed_asset_id?: number | null;
};
