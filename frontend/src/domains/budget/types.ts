export type MonthlyCloseStatus = 'draft' | 'finalized' | 'locked';
export type CoverageMode = 'ledger' | 'checkin' | 'mixed' | 'none';

export type MonthlyCloseStateResponse = {
  monthly_close: {
    id: number;
    fiscal_year: number;
    month: number;
    status: MonthlyCloseStatus;
    finalized_at: string | null;
    locked_at: string | null;
    income_total_snapshot: string | null;
    expense_total_snapshot: string | null;
    liquidity_total_snapshot: string | null;
    notes: string;
  };
  income: {
    executed: string;
    planned: string;
    coverage_mode: CoverageMode;
    completion_ratio: number;
  };
  expense: {
    executed: string;
    planned: string;
    coverage_mode: CoverageMode;
    completion_ratio: number;
  };
  liquidity: {
    current_total: string | null;
    previous_total: string | null;
    delta: string | null;
    completion_ratio: number;
    has_checkins: boolean;
  };
  financial_result: {
    eligible_income: string;
    total_outflows: string;
    living_expense: string;
    financial_contributions: string;
    financial_savings: string;
    net_savings: string;
    savings_rate: string | null;
    real_estate_formation: string;
    tangible_asset_purchases: string;
    debt_principal_repayment: string;
    other_outflows: string;
  };
  has_gaps: boolean;
  suggestions: {
    income: Record<string, string>;
    expense: Record<string, string>;
  };
};
