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
  term_end_year?: number | null;
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
  term_end_year?: number | null;
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
  initial_purchase_value?: string | null;
  amortization_method?: string;
  amortization_term_years?: number | null;
  annual_interest_tae?: string | null;
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
  expected_end_date?: string | null;
  term_months?: number | null;
  rate_type?: string;
  payment_frequency?: string;
  amortization_system?: string | null;
  annual_interest_tae?: string | null;
  monthly_payment_amount?: string | null;
  principal_amount?: string | null;
  opening_fees_amount?: string | null;
  early_repayment_fee_percent?: string | null;
  novation_subrogation_fee_amount?: string | null;
  linked_products_monthly_cost?: string | null;
  amount: string;
  is_active: boolean;
  notes?: string;
  financed_asset_ref?: number | null;
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

export type PortableSettingsRecord = {
  base_currency: string;
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
  settings?: PortableSettingsRecord;
  data: {
    annual_income: PortableAnnualIncomeRecord[];
    annual_expense: PortableAnnualExpenseRecord[];
    assets: PortableAssetRecord[];
    liabilities: PortableLiabilityRecord[];
    snapshots?: PortableSnapshotRecord[];
  };
  premium?: PortablePremiumData;
};

export type ImportMode = 'append' | 'replace';

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

export function buildImportPreviewMessage(bundle: PortableDataBundle, mode: ImportMode): string {
  const snapshots = bundle.data.snapshots ?? [];
  const sortedDates = snapshots.map((s) => s.snapshot_date).sort();
  const snapshotRange =
    sortedDates.length > 0
      ? `${sortedDates[0]} .. ${sortedDates[sortedDates.length - 1]}`
      : 'sin snapshots';
  const hasPremium = Boolean(bundle.premium);
  const lines = [
    mode === 'replace'
      ? 'Se reemplazaran los datos actuales por el archivo:'
      : 'Se importaran datos (modo aditivo):',
    `- Ingresos: ${bundle.data.annual_income.length}`,
    `- Gastos: ${bundle.data.annual_expense.length}`,
    `- Activos: ${bundle.data.assets.length}`,
    `- Pasivos: ${bundle.data.liabilities.length}`,
    `- Snapshots: ${snapshots.length} (${snapshotRange})`,
    `- Configuracion base_currency: ${bundle.settings?.base_currency ?? 'sin incluir'}`,
    hasPremium
      ? `- Miembros: ${bundle.premium?.family_members.length ?? 0} | Titularidades: ${bundle.premium?.ownerships.length ?? 0} | Enlaces: ${bundle.premium?.ownership_links.length ?? 0}`
      : '- Bloque premium: no incluido',
    '',
    formatImportYearSummary(bundle.data.annual_income, 'Ingresos por ano'),
    formatImportYearSummary(bundle.data.annual_expense, 'Gastos por ano'),
    '',
    mode === 'replace'
      ? 'Se borraran primero los datos actuales de estos bloques (incluidos snapshots).'
      : 'La importacion anade registros y actualiza settings/snapshots/relaciones importados.',
    'Continuar?',
  ];
  return lines.join('\n');
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
    term_end_year: entry.term_end_year ?? null,
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
    term_end_year: entry.term_end_year ?? null,
    amount_annual: String(entry.amount_annual ?? '0'),
    fiscal_year: Number(entry.fiscal_year ?? 0),
    currency: String(entry.currency ?? 'EUR').toUpperCase(),
    notes: String(entry.notes ?? ''),
    is_active: entry.is_active ?? true,
  };
}

export function toPortableAssetRecord(raw: Partial<PortableAssetRecord>): PortableAssetRecord {
  return {
    id: Number(raw.id ?? 0),
    name: String(raw.name ?? ''),
    category: String(raw.category ?? ''),
    subcategory: String(raw.subcategory ?? 'other'),
    tracking_mode: String(raw.tracking_mode ?? 'manual'),
    accounting_account_id:
      raw.accounting_account_id == null ? null : Number(raw.accounting_account_id),
    currency: String(raw.currency ?? 'EUR').toUpperCase(),
    start_date: raw.start_date ? String(raw.start_date) : undefined,
    initial_purchase_value:
      raw.initial_purchase_value == null ? null : String(raw.initial_purchase_value),
    amortization_method: raw.amortization_method == null ? 'none' : String(raw.amortization_method),
    amortization_term_years:
      raw.amortization_term_years == null ? null : Number(raw.amortization_term_years),
    annual_interest_tae: raw.annual_interest_tae == null ? null : String(raw.annual_interest_tae),
    deposit_term_months:
      raw.deposit_term_months == null ? null : Number(raw.deposit_term_months),
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
    accounting_account_id:
      raw.accounting_account_id == null ? null : Number(raw.accounting_account_id),
    currency: String(raw.currency ?? 'EUR').toUpperCase(),
    start_date: raw.start_date ? String(raw.start_date) : undefined,
    expected_end_date: raw.expected_end_date ? String(raw.expected_end_date) : undefined,
    term_months: raw.term_months == null ? null : Number(raw.term_months),
    rate_type: raw.rate_type == null ? 'fixed' : String(raw.rate_type),
    payment_frequency: raw.payment_frequency == null ? 'monthly' : String(raw.payment_frequency),
    amortization_system:
      raw.amortization_system == null ? null : String(raw.amortization_system),
    annual_interest_tae: raw.annual_interest_tae == null ? null : String(raw.annual_interest_tae),
    monthly_payment_amount:
      raw.monthly_payment_amount == null ? null : String(raw.monthly_payment_amount),
    principal_amount: raw.principal_amount == null ? null : String(raw.principal_amount),
    opening_fees_amount:
      raw.opening_fees_amount == null ? null : String(raw.opening_fees_amount),
    early_repayment_fee_percent:
      raw.early_repayment_fee_percent == null ? null : String(raw.early_repayment_fee_percent),
    novation_subrogation_fee_amount:
      raw.novation_subrogation_fee_amount == null
        ? null
        : String(raw.novation_subrogation_fee_amount),
    linked_products_monthly_cost:
      raw.linked_products_monthly_cost == null ? null : String(raw.linked_products_monthly_cost),
    amount: String(raw.amount ?? '0'),
    is_active: raw.is_active ?? true,
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

export function parsePortableDataBundle(raw: string): PortableDataBundle {
  const parsed = JSON.parse(raw) as Partial<PortableDataBundle>;
  if (parsed?.schema_version !== 1 || !parsed.data) {
    throw new Error('Formato de archivo no compatible.');
  }
  const { annual_income, annual_expense, assets, liabilities, snapshots } =
    parsed.data as PortableDataBundle['data'];
  if (
    !Array.isArray(annual_income) ||
    !Array.isArray(annual_expense) ||
    !Array.isArray(assets) ||
    !Array.isArray(liabilities)
  ) {
    throw new Error('El archivo no contiene las colecciones esperadas.');
  }
  const sourceApp = parsed.source_app === 'saas' ? 'saas' : 'core';
  let premium: PortablePremiumData | undefined;
  if (parsed.premium != null) {
    const premiumRaw = parsed.premium as Partial<PortablePremiumData>;
    if (
      !Array.isArray(premiumRaw.family_members) ||
      !Array.isArray(premiumRaw.ownerships) ||
      !Array.isArray(premiumRaw.ownership_links)
    ) {
      throw new Error('El bloque premium del archivo no es valido.');
    }
    premium = {
      family_members: premiumRaw.family_members.map((row) => toPortableFamilyMemberRecord(row)),
      ownerships: premiumRaw.ownerships.map((row) => toPortableOwnershipRecord(row)),
      ownership_links: premiumRaw.ownership_links.map((row) => toPortableOwnershipLinkRecord(row)),
    };
  }
  return {
    schema_version: 1,
    exported_at: String(parsed.exported_at ?? ''),
    source_app: sourceApp,
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
    },
    premium,
  };
}
