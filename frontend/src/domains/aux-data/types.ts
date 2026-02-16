export type FxRate = {
  id: number;
  rate_date: string;
  from_currency: string;
  to_currency: string;
  rate: string;
  updated_at: string;
};

export type InflationIndex = {
  id: number;
  region: string;
  period: string;
  index: string;
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
