export type PortableAnnualIncomeRecord = {
  id: number;
  name: string;
  category: string;
  subcategory: string;
  owner_name?: string;
  income_type: 'recurrent' | 'one_off';
  time_profile?: 'structural_recurrent' | 'term_recurrent' | 'one_off';
  cashflow_role?: 'operating' | 'transfer' | 'asset_sale' | 'tax_adjustment' | 'other';
  event_group?: string;
  target_month?: number | null;
  term_end_month?: number | null;
  term_end_year?: number | null;
  amount_input_period?: 'annual' | 'monthly';
  amount_annual: string;
  fiscal_year: number;
  currency: string;
  notes: string;
  is_active?: boolean;
};

export type PortableAnnualExpenseRecord = {
  id: number;
  name: string;
  category: string;
  subcategory: string;
  owner_name?: string;
  expense_type: 'recurrent' | 'one_off';
  time_profile?: 'structural_recurrent' | 'term_recurrent' | 'one_off';
  cashflow_role?:
    | 'operating'
    | 'temporary_commitment'
    | 'savings'
    | 'investment'
    | 'asset_purchase'
    | 'tax_fee'
    | 'transfer'
    | 'other';
  event_group?: string;
  target_month?: number | null;
  term_end_month?: number | null;
  term_end_year?: number | null;
  amount_input_period?: 'annual' | 'monthly';
  amount_annual: string;
  fiscal_year: number;
  currency: string;
  notes: string;
  is_active?: boolean;
};

export type PortableAssetRecord = {
  id: number;
  name: string;
  category: string;
  subcategory: string;
  tracking_mode: string;
  accounting_account_id: number | null;
  currency: string;
  start_date?: string;
  expected_end_date?: string | null;
  investment_contribution_mode?: 'one_time' | 'periodic_contribution';
  investment_contribution_frequency?: 'monthly' | 'weekly';
  investment_contribution_currency?: string | null;
  monthly_contribution_amount?: string | null;
  contribution_intervals?: PortableInvestmentContributionIntervalRecord[];
  market_value_override?: string | null;
  market_value_override_date?: string | null;
  initial_purchase_value?: string | null;
  amortization_method?: string;
  amortization_term_years?: number | null;
  valuation_model?: 'manual' | 'real_estate_auto';
  land_value_share_percent?: string | null;
  land_annual_appreciation_percent?: string | null;
  building_annual_depreciation_percent?: string | null;
  improvements?: PortableAssetImprovementRecord[];
  annual_interest_tae?: string | null;
  estimated_average_balance_for_interest?: string | null;
  deposit_term_months?: number | null;
  amount: string;
  is_active: boolean;
  notes?: string;
};

export type PortableLiabilityRecord = {
  id: number;
  name: string;
  category: string;
  tracking_mode: string;
  accounting_account_id: number | null;
  currency: string;
  start_date?: string;
  payment_start_date?: string | null;
  expected_end_date?: string | null;
  term_months?: number | null;
  rate_type?: string;
  payment_frequency?: string;
  expense_subcategory_override?: string | null;
  amortization_system?: string | null;
  annual_interest_tae?: string | null;
  monthly_payment_amount?: string | null;
  principal_amount?: string | null;
  opening_fees_amount?: string | null;
  early_repayment_fee_percent?: string | null;
  novation_subrogation_fee_amount?: string | null;
  linked_products_monthly_cost?: string | null;
  cancellation_forecast_enabled?: boolean;
  cancellation_date?: string | null;
  cancellation_fee_amount?: string | null;
  amount: string;
  is_active: boolean;
  is_asset_backed?: boolean;
  notes?: string;
  financed_asset_ref?: number | null;
};

export type PortableInvestmentContributionIntervalRecord = {
  id?: number;
  start_date: string;
  end_date?: string | null;
  amount: string;
  frequency: 'monthly' | 'weekly';
  currency?: string | null;
};

export type PortableAssetImprovementRecord = {
  id?: number;
  name: string;
  reform_date: string;
  amount: string;
  amortization_method?: 'none' | 'straight_line' | 'manual';
  amortization_term_years?: number | null;
  annual_interest_tae?: string | null;
  capitalize_interest?: boolean;
  manual_current_value?: string | null;
  notes?: string;
};

export type PortableSnapshotRecord = {
  id: number;
  snapshot_date: string;
  base_currency: string;
  total_assets: string;
  total_liabilities: string;
  net_worth: string;
  created_at?: string;
};

export type PortableLedgerAccountRecord = {
  id: number;
  name: string;
  account_type: 'asset' | 'liability' | 'equity' | 'income' | 'expense';
  currency: string;
  origin: 'user' | 'system';
  asset_id?: number | null;
  liability_id?: number | null;
  is_active?: boolean;
  notes?: string;
};

export type PortableLedgerEntryRecord = {
  id?: number;
  account_id: number;
  side: 'debit' | 'credit';
  amount: string;
  currency: string;
  flow_family?: 'income' | 'expense' | '';
  category_key?: string;
  subcategory_key?: string;
  annual_income_entry_id?: number | null;
  annual_expense_entry_id?: number | null;
  asset_id?: number | null;
  liability_id?: number | null;
  notes?: string;
};

export type PortableLedgerTransactionRecord = {
  id: number;
  booking_date: string;
  value_date: string;
  description: string;
  status?: 'draft' | 'posted';
  origin?: 'manual' | 'import' | 'system';
  notes?: string;
  ownership_id?: number | null;
  quick_entry_kind?: string;
  investment_direction?: 'inflow' | 'outflow' | '';
  entries: PortableLedgerEntryRecord[];
};

export type PortableSettingsRecord = {
  base_currency: string;
};

export type PortableAssetValuationRecord = {
  id?: number;
  asset_ref: number;
  valuation_date: string;
  value: string;
  source?: 'manual_checkpoint' | 'imported' | 'system';
  note?: string;
};

export type PortableInvestmentEventRecord = {
  id?: number;
  asset_ref: number;
  event_date: string;
  event_type: 'contribution' | 'withdrawal' | 'fee' | 'passive_income';
  amount: string;
  is_reinvested?: boolean;
  note?: string;
};

export type PortableLiquidityEventRecord = {
  id?: number;
  asset_ref: number;
  event_date: string;
  event_type: 'inflow' | 'outflow' | 'fee' | 'interest';
  amount: string;
  note?: string;
};

export type PortableLiabilityEventRecord = {
  id?: number;
  liability_ref: number;
  event_date: string;
  event_type: 'charge' | 'payment' | 'fee' | 'interest' | 'adjustment';
  amount: string;
  note?: string;
};

export type PortableLiabilityValuationRecord = {
  id?: number;
  liability_ref: number;
  valuation_date: string;
  value: string;
  source?: 'manual_checkpoint' | 'imported' | 'system';
  note?: string;
};

export type PortableFamilyMemberRecord = {
  id: number;
  name: string;
  role: 'adult' | 'child';
  is_active: boolean;
};

export type PortableOwnershipRecord = {
  id: number;
  kind: 'individual' | 'shared';
  member: { id: number; name: string; role: 'adult' | 'child' } | null;
  splits: { member: { id: number; name: string; role: 'adult' | 'child' }; percent: string }[];
  notes?: string;
  is_in_use?: boolean;
};

export type PortableOwnershipLinkRecord = {
  target_type: 'asset' | 'liability';
  target_id: number;
  ownership_id: number;
};

export type PortablePremiumData = {
  family_members: PortableFamilyMemberRecord[];
  ownerships: PortableOwnershipRecord[];
  ownership_links: PortableOwnershipLinkRecord[];
};

export type PortableDataBundle = {
  schema_version: 1;
  exported_at: string;
  source_app: 'core' | 'saas';
  exported_app_version?: string;
  settings?: PortableSettingsRecord;
  data: {
    annual_income: PortableAnnualIncomeRecord[];
    annual_expense: PortableAnnualExpenseRecord[];
    assets: PortableAssetRecord[];
    liabilities: PortableLiabilityRecord[];
    snapshots?: PortableSnapshotRecord[];
    asset_valuations?: PortableAssetValuationRecord[];
    investment_events?: PortableInvestmentEventRecord[];
    liquidity_events?: PortableLiquidityEventRecord[];
    liability_events?: PortableLiabilityEventRecord[];
    liability_valuations?: PortableLiabilityValuationRecord[];
    accounting: {
      accounts: PortableLedgerAccountRecord[];
      transactions: PortableLedgerTransactionRecord[];
    };
  };
  premium?: PortablePremiumData;
};

export type ImportMode = 'append' | 'replace';
export type ImportCompatibility =
  | 'compatible'
  | 'legacy_replace_blocked'
  | 'newer_than_app'
  | 'unknown';

export function normalizeOptionalText(raw: unknown): string | null {
  if (raw == null) return null;
  const text = String(raw).trim();
  return text ? text : null;
}

export function normalizeImportedAssetTae(asset: PortableAssetRecord): string | null {
  const normalized = normalizeOptionalText(asset.annual_interest_tae);
  if (normalized != null) return normalized;

  const category = String(asset.category ?? '').trim();
  const subcategory = String(asset.subcategory ?? '').trim();
  const requiresTae =
    category === 'cash' &&
    (subcategory === 'bank_account' ||
      subcategory === 'short_term_deposit' ||
      subcategory === 'crypto_spot_earn' ||
      subcategory === 'other');

  return requiresTae ? '0' : null;
}

export function normalizeImportedLiabilityTae(liability: PortableLiabilityRecord): string | null {
  const normalized = normalizeOptionalText(liability.annual_interest_tae);
  if (normalized != null) return normalized;

  const category = String(liability.category ?? '').trim();
  const requiresTae =
    category === 'mortgage' || category === 'personal_loan' || category === 'credit_card';

  return requiresTae ? '0' : null;
}

function formatImportYearSummary(
  entries: Array<{ fiscal_year: number; amount_annual: string | number }>,
  label: string,
): string {
  if (!entries.length) return `${label}: 0`;
  const totals = new Map<number, { count: number; amount: number }>();
  for (const entry of entries) {
    const year = Number(entry.fiscal_year);
    const amount = Number(entry.amount_annual ?? 0);
    const prev = totals.get(year) ?? { count: 0, amount: 0 };
    totals.set(year, {
      count: prev.count + 1,
      amount: prev.amount + (Number.isFinite(amount) ? amount : 0),
    });
  }
  const segments = [...totals.entries()]
    .sort((a, b) => a[0] - b[0])
    .map(
      ([year, info]) =>
        `${year}: ${info.count} (${new Intl.NumberFormat('es-ES', {
          maximumFractionDigits: 2,
          minimumFractionDigits: 0,
        }).format(info.amount)})`,
    );
  return `${label}: ${segments.join(' | ')}`;
}

export function buildImportPreviewMessage(
  bundle: PortableDataBundle,
  mode: ImportMode,
  currentAppVersion?: string | null,
): string {
  return buildImportPreviewMessageWithVersion(bundle, mode, currentAppVersion);
}

function parseVersion(version: string): number[] {
  return version
    .split('.')
    .map((part) => Number(part.trim()))
    .map((part) => (Number.isFinite(part) ? part : 0));
}

export function comparePortableVersions(left: string, right: string): number {
  const leftParts = parseVersion(left);
  const rightParts = parseVersion(right);
  const maxLength = Math.max(leftParts.length, rightParts.length);
  for (let index = 0; index < maxLength; index += 1) {
    const leftValue = leftParts[index] ?? 0;
    const rightValue = rightParts[index] ?? 0;
    if (leftValue < rightValue) return -1;
    if (leftValue > rightValue) return 1;
  }
  return 0;
}

export function evaluateImportCompatibility(
  bundle: PortableDataBundle,
  mode: ImportMode,
  currentAppVersion?: string | null,
): ImportCompatibility {
  const exportedVersion = normalizeOptionalText(bundle.exported_app_version);
  if (mode === 'replace' && exportedVersion == null) {
    return 'legacy_replace_blocked';
  }
  if (exportedVersion == null || !currentAppVersion) {
    return 'unknown';
  }
  if (comparePortableVersions(exportedVersion, currentAppVersion) > 0) {
    return 'newer_than_app';
  }
  return 'compatible';
}

export function buildImportPreviewMessageWithVersion(
  bundle: PortableDataBundle,
  mode: ImportMode,
  currentAppVersion?: string | null,
): string {
  const snapshots = bundle.data.snapshots ?? [];
  const hasPremium = Boolean(bundle.premium);
  const exportedVersion = normalizeOptionalText(bundle.exported_app_version);
  const compatibility = evaluateImportCompatibility(bundle, mode, currentAppVersion);
  const lines = [
    mode === 'replace'
      ? 'Se reemplazaran los datos actuales por el archivo:'
      : 'Se importaran datos (modo aditivo):',
    `- Origen: ${bundle.source_app}`,
    `- Version exportada: ${exportedVersion ?? 'legacy/sin version'}`,
    `- Version actual: ${currentAppVersion ?? 'no disponible'}`,
    `- Ingresos: ${bundle.data.annual_income.length}`,
    `- Gastos: ${bundle.data.annual_expense.length}`,
    `- Activos: ${bundle.data.assets.length}`,
    `- Pasivos: ${bundle.data.liabilities.length}`,
    `- Cuentas contables: ${bundle.data.accounting.accounts.length}`,
    `- Movimientos contables: ${bundle.data.accounting.transactions.length}`,
    snapshots.length > 0 ? `- Snapshots legacy detectados: ${snapshots.length}` : null,
    `- Configuracion base_currency: ${bundle.settings?.base_currency ?? 'sin incluir'}`,
    hasPremium
      ? `- Miembros: ${bundle.premium?.family_members.length ?? 0} | Titularidades: ${bundle.premium?.ownerships.length ?? 0} | Enlaces: ${bundle.premium?.ownership_links.length ?? 0}`
      : '- Bloque premium: no incluido',
    '',
    formatImportYearSummary(bundle.data.annual_income, 'Ingresos por ano'),
    formatImportYearSummary(bundle.data.annual_expense, 'Gastos por ano'),
    '',
    mode === 'replace'
      ? 'Se borraran primero los datos actuales de estos bloques.'
      : 'La importacion anade registros y actualiza settings/relaciones importados.',
    compatibility === 'legacy_replace_blocked'
      ? 'Aviso: este archivo no incluye version exportada. El backend bloqueara `replace` por seguridad.'
      : compatibility === 'newer_than_app'
        ? 'Aviso: el archivo viene de una version mas nueva. El backend bloqueara `replace` para evitar perdida de datos.'
        : compatibility === 'unknown'
          ? 'Aviso: no se pudo determinar toda la compatibilidad antes de importar.'
          : 'Compatibilidad preliminar: OK.',
    'Continuar?',
  ];
  return lines.filter((line): line is string => Boolean(line)).join('\n');
}

export function buildPortableFilename(): string {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  return `moneyplanner-saas-data-${timestamp}.json`;
}

export function toPortableAnnualIncomeRecord(
  entry: PortableAnnualIncomeRecord,
): PortableAnnualIncomeRecord {
  return {
    id: Number(entry.id),
    name: String(entry.name ?? ''),
    category: String(entry.category ?? ''),
    subcategory: String(entry.subcategory ?? ''),
    owner_name: String(entry.owner_name ?? ''),
    income_type: entry.income_type === 'one_off' ? 'one_off' : 'recurrent',
    time_profile: entry.time_profile,
    cashflow_role: entry.cashflow_role,
    event_group: String(entry.event_group ?? ''),
    target_month: entry.target_month ?? null,
    term_end_month: entry.term_end_month ?? null,
    term_end_year: entry.term_end_year ?? null,
    amount_input_period: entry.amount_input_period === 'monthly' ? 'monthly' : 'annual',
    amount_annual: String(entry.amount_annual ?? '0'),
    fiscal_year: Number(entry.fiscal_year ?? 0),
    currency: String(entry.currency ?? 'EUR').toUpperCase(),
    notes: String(entry.notes ?? ''),
    is_active: entry.is_active ?? true,
  };
}

export function toPortableAnnualExpenseRecord(
  entry: PortableAnnualExpenseRecord,
): PortableAnnualExpenseRecord {
  return {
    id: Number(entry.id),
    name: String(entry.name ?? ''),
    category: String(entry.category ?? ''),
    subcategory: String(entry.subcategory ?? ''),
    owner_name: String(entry.owner_name ?? ''),
    expense_type: entry.expense_type === 'one_off' ? 'one_off' : 'recurrent',
    time_profile: entry.time_profile,
    cashflow_role: entry.cashflow_role,
    event_group: String(entry.event_group ?? ''),
    target_month: entry.target_month ?? null,
    term_end_month: entry.term_end_month ?? null,
    term_end_year: entry.term_end_year ?? null,
    amount_input_period: entry.amount_input_period === 'monthly' ? 'monthly' : 'annual',
    amount_annual: String(entry.amount_annual ?? '0'),
    fiscal_year: Number(entry.fiscal_year ?? 0),
    currency: String(entry.currency ?? 'EUR').toUpperCase(),
    notes: String(entry.notes ?? ''),
    is_active: entry.is_active ?? true,
  };
}

function toNumberOrNull(raw: unknown): number | null {
  return raw == null ? null : Number(raw);
}

function toUpperText(raw: unknown, fallback: string): string {
  return String(raw ?? fallback).toUpperCase();
}

function toOptionalText(raw: unknown): string | null {
  return raw == null ? null : String(raw);
}

function toOptionalDateText(raw: unknown): string | undefined {
  return raw ? String(raw) : undefined;
}

function toAssetContributionMode(raw: unknown): 'one_time' | 'periodic_contribution' {
  return raw == null ? 'one_time' : (String(raw) as 'one_time' | 'periodic_contribution');
}

function toAssetContributionFrequency(raw: unknown): 'monthly' | 'weekly' {
  return raw == null ? 'monthly' : (String(raw) as 'monthly' | 'weekly');
}

function toLedgerAccountType(
  raw: unknown,
): 'asset' | 'liability' | 'equity' | 'income' | 'expense' {
  const candidate = String(raw ?? '').trim();
  if (
    candidate === 'asset' ||
    candidate === 'liability' ||
    candidate === 'equity' ||
    candidate === 'income' ||
    candidate === 'expense'
  ) {
    return candidate;
  }
  return 'asset';
}

function toLedgerOrigin(raw: unknown): 'user' | 'system' {
  return String(raw ?? '').trim() === 'system' ? 'system' : 'user';
}

function toLedgerSide(raw: unknown): 'debit' | 'credit' {
  return String(raw ?? '').trim() === 'credit' ? 'credit' : 'debit';
}

function toFlowFamily(raw: unknown): 'income' | 'expense' | '' {
  const candidate = String(raw ?? '').trim();
  if (candidate === 'income' || candidate === 'expense') return candidate;
  return '';
}

export function toPortableLedgerAccountRecord(
  raw: Partial<PortableLedgerAccountRecord>,
): PortableLedgerAccountRecord {
  return {
    id: Number(raw.id ?? 0),
    name: String(raw.name ?? ''),
    account_type: toLedgerAccountType(raw.account_type),
    currency: toUpperText(raw.currency, 'EUR'),
    origin: toLedgerOrigin(raw.origin),
    asset_id: toNumberOrNull(raw.asset_id),
    liability_id: toNumberOrNull(raw.liability_id),
    is_active: raw.is_active ?? true,
    notes: raw.notes == null ? '' : String(raw.notes),
  };
}

export function toPortableLedgerEntryRecord(
  raw: Partial<PortableLedgerEntryRecord>,
): PortableLedgerEntryRecord {
  return {
    id: raw.id == null ? undefined : Number(raw.id),
    account_id: Number(raw.account_id ?? 0),
    side: toLedgerSide(raw.side),
    amount: String(raw.amount ?? '0'),
    currency: toUpperText(raw.currency, 'EUR'),
    flow_family: toFlowFamily(raw.flow_family),
    category_key: String(raw.category_key ?? ''),
    subcategory_key: String(raw.subcategory_key ?? ''),
    annual_income_entry_id: toNumberOrNull(raw.annual_income_entry_id),
    annual_expense_entry_id: toNumberOrNull(raw.annual_expense_entry_id),
    asset_id: toNumberOrNull(raw.asset_id),
    liability_id: toNumberOrNull(raw.liability_id),
    notes: raw.notes == null ? '' : String(raw.notes),
  };
}

export function toPortableLedgerTransactionRecord(
  raw: Partial<PortableLedgerTransactionRecord>,
): PortableLedgerTransactionRecord {
  return {
    id: Number(raw.id ?? 0),
    booking_date: String(raw.booking_date ?? ''),
    value_date: String(raw.value_date ?? ''),
    description: String(raw.description ?? ''),
    status: raw.status === 'draft' ? 'draft' : 'posted',
    origin:
      raw.origin === 'import' || raw.origin === 'system'
        ? raw.origin
        : ('manual' as const),
    notes: raw.notes == null ? '' : String(raw.notes),
    ownership_id: toNumberOrNull(raw.ownership_id),
    quick_entry_kind: raw.quick_entry_kind == null ? '' : String(raw.quick_entry_kind),
    investment_direction:
      raw.investment_direction === 'inflow' || raw.investment_direction === 'outflow'
        ? raw.investment_direction
        : '',
    entries: Array.isArray(raw.entries)
      ? raw.entries.map((row) => toPortableLedgerEntryRecord(row))
      : [],
  };
}

export function toPortableAssetRecord(raw: Partial<PortableAssetRecord>): PortableAssetRecord {
  return {
    id: Number(raw.id ?? 0),
    name: String(raw.name ?? ''),
    category: String(raw.category ?? ''),
    subcategory: String(raw.subcategory ?? 'other'),
    tracking_mode: String(raw.tracking_mode ?? 'manual'),
    accounting_account_id: toNumberOrNull(raw.accounting_account_id),
    currency: toUpperText(raw.currency, 'EUR'),
    start_date: toOptionalDateText(raw.start_date),
    expected_end_date: toOptionalDateText(raw.expected_end_date),
    investment_contribution_mode: toAssetContributionMode(raw.investment_contribution_mode),
    investment_contribution_frequency: toAssetContributionFrequency(
      raw.investment_contribution_frequency,
    ),
    contribution_intervals: Array.isArray(raw.contribution_intervals)
      ? raw.contribution_intervals.map((row) => ({
          id: row.id == null ? undefined : Number(row.id),
          start_date: String(row.start_date ?? ''),
          end_date: row.end_date == null ? null : String(row.end_date),
          amount: String(row.amount ?? '0'),
          frequency: row.frequency === 'weekly' ? 'weekly' : 'monthly',
          currency: row.currency == null ? null : String(row.currency).toUpperCase(),
        }))
      : [],
    investment_contribution_currency:
      raw.investment_contribution_currency == null
        ? null
        : toUpperText(raw.investment_contribution_currency, ''),
    monthly_contribution_amount: toOptionalText(raw.monthly_contribution_amount),
    market_value_override: toOptionalText(raw.market_value_override),
    market_value_override_date: toOptionalText(raw.market_value_override_date),
    initial_purchase_value: toOptionalText(raw.initial_purchase_value),
    amortization_method: raw.amortization_method == null ? 'none' : String(raw.amortization_method),
    amortization_term_years: toNumberOrNull(raw.amortization_term_years),
    valuation_model:
      raw.valuation_model === 'real_estate_auto' ? 'real_estate_auto' : 'manual',
    land_value_share_percent: toOptionalText(raw.land_value_share_percent),
    land_annual_appreciation_percent: toOptionalText(raw.land_annual_appreciation_percent),
    building_annual_depreciation_percent: toOptionalText(raw.building_annual_depreciation_percent),
    improvements: Array.isArray(raw.improvements)
      ? raw.improvements.map((row) => ({
          id: row.id == null ? undefined : Number(row.id),
          name: String(row.name ?? ''),
          reform_date: String(row.reform_date ?? ''),
          amount: String(row.amount ?? '0'),
          amortization_method:
            row.amortization_method === 'straight_line' || row.amortization_method === 'manual'
              ? row.amortization_method
              : 'none',
          amortization_term_years: toNumberOrNull(row.amortization_term_years),
          annual_interest_tae: toOptionalText(row.annual_interest_tae),
          capitalize_interest: row.capitalize_interest ?? false,
          manual_current_value: toOptionalText(row.manual_current_value),
          notes: row.notes == null ? '' : String(row.notes),
        }))
      : [],
    annual_interest_tae: toOptionalText(raw.annual_interest_tae),
    estimated_average_balance_for_interest: toOptionalText(
      raw.estimated_average_balance_for_interest,
    ),
    deposit_term_months: toNumberOrNull(raw.deposit_term_months),
    amount: String(raw.amount ?? '0'),
    is_active: raw.is_active ?? true,
    notes: raw.notes == null ? '' : String(raw.notes),
  };
}

export function toPortableLiabilityRecord(
  raw: Partial<PortableLiabilityRecord>,
): PortableLiabilityRecord {
  const financedAssetRef =
    raw.financed_asset_ref ??
    (raw as Partial<PortableLiabilityRecord> & { financed_asset_id?: number | null })
      .financed_asset_id ??
    null;
  return {
    id: Number(raw.id ?? 0),
    name: String(raw.name ?? ''),
    category: String(raw.category ?? ''),
    tracking_mode: String(raw.tracking_mode ?? 'manual'),
    accounting_account_id: toNumberOrNull(raw.accounting_account_id),
    currency: toUpperText(raw.currency, 'EUR'),
    start_date: toOptionalDateText(raw.start_date),
    payment_start_date: toOptionalText(raw.payment_start_date),
    expected_end_date: toOptionalDateText(raw.expected_end_date),
    term_months: toNumberOrNull(raw.term_months),
    rate_type: raw.rate_type == null ? 'fixed' : String(raw.rate_type),
    payment_frequency: raw.payment_frequency == null ? 'monthly' : String(raw.payment_frequency),
    expense_subcategory_override: toOptionalText(raw.expense_subcategory_override),
    amortization_system: toOptionalText(raw.amortization_system),
    annual_interest_tae: toOptionalText(raw.annual_interest_tae),
    monthly_payment_amount: toOptionalText(raw.monthly_payment_amount),
    principal_amount: toOptionalText(raw.principal_amount),
    opening_fees_amount: toOptionalText(raw.opening_fees_amount),
    early_repayment_fee_percent: toOptionalText(raw.early_repayment_fee_percent),
    novation_subrogation_fee_amount: toOptionalText(raw.novation_subrogation_fee_amount),
    linked_products_monthly_cost: toOptionalText(raw.linked_products_monthly_cost),
    cancellation_forecast_enabled: raw.cancellation_forecast_enabled ?? false,
    cancellation_date: toOptionalText(raw.cancellation_date),
    cancellation_fee_amount: toOptionalText(raw.cancellation_fee_amount),
    amount: String(raw.amount ?? '0'),
    is_active: raw.is_active ?? true,
    is_asset_backed: raw.is_asset_backed ?? false,
    notes: raw.notes == null ? '' : String(raw.notes),
    financed_asset_ref: financedAssetRef == null ? null : Number(financedAssetRef),
  };
}

export function toPortableOwnershipRecord(
  raw: Partial<PortableOwnershipRecord>,
): PortableOwnershipRecord {
  return {
    id: Number(raw.id ?? 0),
    kind: raw.kind === 'shared' ? 'shared' : 'individual',
    member: raw.member
      ? {
          id: Number(raw.member.id),
          name: String(raw.member.name ?? ''),
          role: raw.member.role === 'child' ? 'child' : 'adult',
        }
      : null,
    splits: Array.isArray(raw.splits)
      ? raw.splits.map((split) => ({
          member: {
            id: Number(split.member.id),
            name: String(split.member.name ?? ''),
            role: split.member.role === 'child' ? 'child' : 'adult',
          },
          percent: String(split.percent ?? '0'),
        }))
      : [],
    notes: raw.notes == null ? undefined : String(raw.notes),
    is_in_use: raw.is_in_use,
  };
}

export function toPortableFamilyMemberRecord(
  raw: Partial<PortableFamilyMemberRecord>,
): PortableFamilyMemberRecord {
  return {
    id: Number(raw.id ?? 0),
    name: String(raw.name ?? ''),
    role: raw.role === 'child' ? 'child' : 'adult',
    is_active: raw.is_active ?? true,
  };
}

export function toPortableOwnershipLinkRecord(
  raw: Partial<PortableOwnershipLinkRecord>,
): PortableOwnershipLinkRecord {
  return {
    target_type: raw.target_type === 'liability' ? 'liability' : 'asset',
    target_id: Number(raw.target_id ?? 0),
    ownership_id: Number(raw.ownership_id ?? 0),
  };
}

function assertPortableDataCollections(
  data: PortableDataBundle['data'],
): {
  annual_income: PortableDataBundle['data']['annual_income'];
  annual_expense: PortableDataBundle['data']['annual_expense'];
  assets: PortableDataBundle['data']['assets'];
  liabilities: PortableDataBundle['data']['liabilities'];
  snapshots: PortableDataBundle['data']['snapshots'];
  asset_valuations: PortableDataBundle['data']['asset_valuations'];
  investment_events: PortableDataBundle['data']['investment_events'];
  liquidity_events: PortableDataBundle['data']['liquidity_events'];
  liability_events: PortableDataBundle['data']['liability_events'];
  liability_valuations: PortableDataBundle['data']['liability_valuations'];
  accounting: PortableDataBundle['data']['accounting'] | undefined;
} {
  const {
    annual_income,
    annual_expense,
    assets,
    liabilities,
    snapshots,
    asset_valuations,
    investment_events,
    liquidity_events,
    liability_events,
    liability_valuations,
    accounting,
  } = data;
  if (
    !Array.isArray(annual_income) ||
    !Array.isArray(annual_expense) ||
    !Array.isArray(assets) ||
    !Array.isArray(liabilities)
  ) {
    throw new Error('El archivo no contiene las colecciones esperadas.');
  }
  return {
    annual_income,
    annual_expense,
    assets,
    liabilities,
    snapshots,
    asset_valuations,
    investment_events,
    liquidity_events,
    liability_events,
    liability_valuations,
    accounting,
  };
}

function parsePortablePremium(raw: unknown): PortablePremiumData | undefined {
  if (raw == null) return undefined;
  const premiumRaw = raw as Partial<PortablePremiumData>;
  if (
    !Array.isArray(premiumRaw.family_members) ||
    !Array.isArray(premiumRaw.ownerships) ||
    !Array.isArray(premiumRaw.ownership_links)
  ) {
    throw new Error('El bloque premium del archivo no es valido.');
  }
  return {
    family_members: premiumRaw.family_members.map((row) => toPortableFamilyMemberRecord(row)),
    ownerships: premiumRaw.ownerships.map((row) => toPortableOwnershipRecord(row)),
    ownership_links: premiumRaw.ownership_links.map((row) => toPortableOwnershipLinkRecord(row)),
  };
}

function parsePortableAccounting(
  raw: PortableDataBundle['data']['accounting'] | undefined,
): PortableDataBundle['data']['accounting'] {
  const accountingAccounts = raw?.accounts;
  const accountingTransactions = raw?.transactions;
  if (raw != null && (!Array.isArray(accountingAccounts) || !Array.isArray(accountingTransactions))) {
    throw new Error('El bloque accounting del archivo no es valido.');
  }
  return {
    accounts: Array.isArray(accountingAccounts)
      ? accountingAccounts.map((row) => toPortableLedgerAccountRecord(row))
      : [],
    transactions: Array.isArray(accountingTransactions)
      ? accountingTransactions.map((row) => toPortableLedgerTransactionRecord(row))
      : [],
  };
}

export function parsePortableDataBundle(raw: string): PortableDataBundle {
  const parsed = JSON.parse(raw) as Partial<PortableDataBundle>;
  if (parsed?.schema_version !== 1 || !parsed.data) {
    throw new Error('Formato de archivo no compatible.');
  }
  const {
    annual_income,
    annual_expense,
    assets,
    liabilities,
    snapshots,
    asset_valuations,
    investment_events,
    liquidity_events,
    liability_events,
    liability_valuations,
    accounting,
  } =
    assertPortableDataCollections(parsed.data as PortableDataBundle['data']);
  const sourceApp = parsed.source_app === 'saas' ? 'saas' : 'core';
  const premium = parsePortablePremium(parsed.premium);
  return {
    schema_version: 1,
    exported_at: String(parsed.exported_at ?? ''),
    source_app: sourceApp,
    exported_app_version:
      parsed.exported_app_version == null ? undefined : String(parsed.exported_app_version),
    settings:
      parsed.settings && typeof parsed.settings === 'object'
        ? { base_currency: String((parsed.settings as PortableSettingsRecord).base_currency ?? '') }
        : undefined,
    data: {
      annual_income: annual_income.map((row) => toPortableAnnualIncomeRecord(row)),
      annual_expense: annual_expense.map((row) => toPortableAnnualExpenseRecord(row)),
      assets: assets.map((row) => toPortableAssetRecord(row)),
      liabilities: liabilities.map((row) => toPortableLiabilityRecord(row)),
      snapshots: Array.isArray(snapshots) ? snapshots : [],
      asset_valuations: Array.isArray(asset_valuations) ? asset_valuations : [],
      investment_events: Array.isArray(investment_events) ? investment_events : [],
      liquidity_events: Array.isArray(liquidity_events) ? liquidity_events : [],
      liability_events: Array.isArray(liability_events) ? liability_events : [],
      liability_valuations: Array.isArray(liability_valuations) ? liability_valuations : [],
      accounting: parsePortableAccounting(accounting),
    },
    premium,
  };
}
