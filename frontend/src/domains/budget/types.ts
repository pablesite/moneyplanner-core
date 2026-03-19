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
  has_gaps: boolean;
  suggestions: {
    income: Record<string, string>;
    expense: Record<string, string>;
  };
};
