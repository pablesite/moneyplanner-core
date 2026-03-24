export type LedgerAccountType = 'asset' | 'liability' | 'equity' | 'income' | 'expense';
export type LedgerAccountOrigin = 'user' | 'system';
export type LedgerTransactionStatus = 'draft' | 'posted';
export type LedgerTransactionOrigin = 'manual' | 'import' | 'system';
export type LedgerEntrySide = 'debit' | 'credit';
export type QuickLedgerMovementType =
  | 'income'
  | 'expense'
  | 'transfer'
  | 'investment'
  | 'investment_purchase'
  | 'debt_payment'
  | 'revaluation';

export type InvestmentDirection = 'inflow' | 'outflow';

export type LedgerAccount = {
  id: number;
  name: string;
  display_name: string;
  account_type: LedgerAccountType;
  currency: string;
  origin: LedgerAccountOrigin;
  asset_id: number | null;
  liability_id: number | null;
  is_active: boolean;
  notes: string;
  current_balance: string;
  created_at: string;
  updated_at: string;
};

export type LedgerEntry = {
  id: number;
  account_id: number;
  account_name: string;
  side: LedgerEntrySide;
  amount: string;
  currency: string;
  flow_family: '' | 'income' | 'expense';
  category_key: string;
  subcategory_key: string;
  annual_income_entry_id: number | null;
  annual_expense_entry_id: number | null;
  asset_id: number | null;
  liability_id: number | null;
  notes: string;
  created_at: string;
  updated_at: string;
};

export type LedgerTransaction = {
  id: number;
  booking_date: string;
  value_date: string;
  description: string;
  status: LedgerTransactionStatus;
  origin: LedgerTransactionOrigin;
  notes: string;
  ownership_id: number | null;
  quick_entry_kind: '' | QuickLedgerMovementType;
  investment_direction: '' | InvestmentDirection;
  realized_cost_basis: string | null;
  realized_gain_loss: string | null;
  activity_kind: string;
  entries: LedgerEntry[];
  created_at: string;
  updated_at: string;
};

export type PaginatedTransactionsResponse = {
  results: LedgerTransaction[];
  next_cursor: string | null;
  total_count: number;
};

export type MonthlyAccountingSummaryMonth = {
  month: number;
  income_total: string;
  expense_total: string;
  uncategorized_total: string;
};

export type MonthlyAccountingSummary = {
  fiscal_year: number;
  months: MonthlyAccountingSummaryMonth[];
};

export type BudgetSuggestionMonthlyPoint = {
  year: number;
  month: number;
  executed_total: string;
};

export type BudgetSuggestionCategoryRow = {
  category: string;
  months: BudgetSuggestionMonthlyPoint[];
  window_total: string;
  observed_months: number;
  average_monthly: string;
  suggested_annual: string;
};

export type BudgetSuggestionSubcategoryRow = BudgetSuggestionCategoryRow & {
  subcategory: string;
};

export type BudgetSuggestionSection = {
  series: BudgetSuggestionMonthlyPoint[];
  categories: BudgetSuggestionCategoryRow[];
  subcategories: BudgetSuggestionSubcategoryRow[];
};

export type BudgetDerivedSuggestions = {
  fiscal_year: number;
  lookback_years: number;
  window_months: number;
  income: BudgetSuggestionSection;
  expense: BudgetSuggestionSection;
  method_note: string;
};

export type LedgerAccountBalanceSummaryItem = {
  account_id: number;
  name: string;
  account_type: LedgerAccountType;
  currency: string;
  origin: LedgerAccountOrigin;
  current_balance: string;
  period_debit_total: string;
  period_credit_total: string;
  period_net_change: string;
};

export type LedgerAccountBalanceSummary = {
  filters: {
    year: number | null;
    month: number | null;
    account_type: LedgerAccountType | null;
    status: LedgerTransactionStatus | null;
  };
  totals_by_account_type: Partial<Record<LedgerAccountType, string>>;
  accounts: LedgerAccountBalanceSummaryItem[];
};

export type LedgerAccountWritePayload = {
  name: string;
  account_type: LedgerAccountType;
  currency: string;
  origin?: LedgerAccountOrigin;
  asset_id?: number | null;
  liability_id?: number | null;
  is_active?: boolean;
  notes?: string;
};

export type LedgerEntryWritePayload = {
  account_id: number;
  side: LedgerEntrySide;
  amount: string;
  currency?: string;
  flow_family?: '' | 'income' | 'expense';
  category_key?: string;
  subcategory_key?: string;
  annual_income_entry_id?: number | null;
  annual_expense_entry_id?: number | null;
  asset_id?: number | null;
  liability_id?: number | null;
  notes?: string;
};

export type LedgerTransactionWritePayload = {
  booking_date: string;
  value_date: string;
  description: string;
  status?: LedgerTransactionStatus;
  origin?: LedgerTransactionOrigin;
  notes?: string;
  ownership_id?: number | null;
  entries: LedgerEntryWritePayload[];
};

export type QuickLedgerTransactionWritePayload = {
  movement_type: QuickLedgerMovementType;
  investment_direction?: '' | InvestmentDirection;
  booking_date: string;
  value_date: string;
  description: string;
  amount: string;
  account_id: number;
  ownership_id?: number | null;
  flow_family?: '' | 'income' | 'expense';
  category_key?: string;
  subcategory_key?: string;
  counterparty_account_id?: number | null;
  liability_account_id?: number | null;
  interest_account_id?: number | null;
  principal_amount?: string | null;
  interest_amount?: string | null;
  realized_cost_basis?: string | null;
  realized_gain_loss?: string | null;
  annual_income_entry_id?: number | null;
  annual_expense_entry_id?: number | null;
  notes?: string;
  status?: LedgerTransactionStatus;
  origin?: LedgerTransactionOrigin;
};

export type MoneyWizImportStats = {
  income: number;
  expense: number;
  transfer: number;
  investment_purchase: number;
  debt_payment: number;
  fallback_classifications?: number;
  auto_created_accounts?: number;
  existing_rows?: number;
  duplicate_rows?: number;
  created_transactions?: number;
  skipped_existing?: number;
};

export type MoneyWizImportDetectedAccount = {
  name: string;
  account_type: LedgerAccountType;
  currency: string;
  role: 'source' | 'counterparty';
  status: 'existing_or_created';
};

export type MoneyWizImportPreviewRow = {
  row_number: number;
  booking_date: string;
  description: string;
  memo: string;
  category: string;
  account_name: string;
  counterparty_name: string;
  currency: string;
  amount: string;
  movement_type: QuickLedgerMovementType;
  movement_direction?: '' | InvestmentDirection;
  flow_family: '' | 'income' | 'expense';
  category_key: string;
  subcategory_key: string;
  fingerprint: string;
  existing_transaction_id: number | null;
  warnings: string[];
  errors: string[];
};

export type MoneyWizUnmappedCategory = {
  category_raw: string;
  movement_type: 'income' | 'expense';
  fallback_category_key: string;
  fallback_subcategory_key: string;
  row_count: number;
};

export type MoneyWizImportPreview = {
  delimiter: string;
  row_count: number;
  valid_row_count: number;
  error_row_count: number;
  duplicate_row_count: number;
  existing_row_count: number;
  warnings: string[];
  stats: MoneyWizImportStats;
  detected_accounts: MoneyWizImportDetectedAccount[];
  unmapped_categories: MoneyWizUnmappedCategory[];
  rows: MoneyWizImportPreviewRow[];
};

export type MoneyWizImportCommit = {
  source: string;
  row_count: number;
  created_count: number;
  skipped_existing_count: number;
  warning_count: number;
  rows: Array<
    Pick<
      MoneyWizImportPreviewRow,
      | 'row_number'
      | 'fingerprint'
      | 'movement_type'
      | 'description'
      | 'amount'
      | 'account_name'
      | 'counterparty_name'
      | 'warnings'
    > & {
      imported: boolean;
    }
  >;
  preview: MoneyWizImportPreview;
  created_transaction_ids: number[];
};

export type DeleteImportedTransactionsResult = {
  deleted_count: number;
};
