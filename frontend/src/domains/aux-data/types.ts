export type FxRate = {
  id: number;
  rate_date: string;
  from_currency: string;
  to_currency: string;
  rate: string;
  source?: string;
  managed_by_system?: boolean;
  last_synced_at?: string | null;
  updated_at: string;
};

export type InflationIndex = {
  id: number;
  region: string;
  period: string;
  index: string;
  source?: string;
  managed_by_system?: boolean;
  last_synced_at?: string | null;
  created_at: string;
  updated_at: string;
};

export type FxPair = {
  value: string;
  label: string;
  from: string;
  to: string;
  hint: string;
};

export type MarketDataState = {
  scope: string;
  required_start_date: string | null;
  covered_until: string | null;
  last_attempt_at: string | null;
  last_success_at: string | null;
  last_error: string | null;
};

export type MarketDataStatus = {
  supported_inflation_regions: { code: string; label: string }[];
  datasets: {
    fx: {
      states: MarketDataState[];
      latest_rows: FxRate[];
    };
    inflation: {
      states: MarketDataState[];
      latest_rows: InflationIndex[];
    };
  };
};
