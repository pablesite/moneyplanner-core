import { describe, expect, it } from 'vitest';
import {
  comparePortableVersions,
  buildPortableFilename,
  toPortableAnnualIncomeRecord,
  toPortableAnnualExpenseRecord,
  toPortableAssetRecord,
  toPortableLiabilityRecord,
  toPortableLedgerAccountRecord,
  toPortableLedgerTransactionRecord,
  toPortableFamilyMemberRecord,
  toPortableOwnershipRecord,
  toPortableOwnershipLinkRecord,
  parsePortableDataBundle,
  buildImportPreviewMessage,
  evaluateImportCompatibility,
} from '@/domains/portable-data/portableBundle';
import type { PortableDataBundle } from '@/domains/portable-data/portableBundle';

function minimalBundle(overrides: Partial<PortableDataBundle> = {}): PortableDataBundle {
  return {
    schema_version: 1,
    exported_at: '2025-01-01T00:00:00Z',
    source_app: 'core',
    exported_app_version: '1.0.0',
    data: {
      annual_income: [],
      annual_expense: [],
      assets: [],
      liabilities: [],
      snapshots: [],
      asset_valuations: [],
      investment_events: [],
      liquidity_events: [],
      liquidity_checkins: [],
      liability_events: [],
      liability_valuations: [],
      accounting: { accounts: [], transactions: [] },
    },
    ...overrides,
  };
}

describe('comparePortableVersions', () => {
  it('returns 0 for equal versions', () => {
    expect(comparePortableVersions('1.2.3', '1.2.3')).toBe(0);
  });

  it('returns -1 when left is older', () => {
    expect(comparePortableVersions('1.0.0', '2.0.0')).toBe(-1);
    expect(comparePortableVersions('1.2.0', '1.2.1')).toBe(-1);
  });

  it('returns 1 when left is newer', () => {
    expect(comparePortableVersions('2.0.0', '1.9.9')).toBe(1);
    expect(comparePortableVersions('1.2.1', '1.2.0')).toBe(1);
  });

  it('handles versions with different segment counts', () => {
    expect(comparePortableVersions('1.0', '1.0.0')).toBe(0);
    expect(comparePortableVersions('1.1', '1.0.9')).toBe(1);
  });
});

describe('buildPortableFilename', () => {
  it('starts with moneyplanner prefix and ends with .json', () => {
    const name = buildPortableFilename();
    expect(name).toMatch(/^moneyplanner-saas-data-.*\.json$/);
  });

  it('generates unique filenames for different calls in the same second', () => {
    const a = buildPortableFilename();
    const b = buildPortableFilename();
    expect(typeof a).toBe('string');
    expect(typeof b).toBe('string');
  });
});

describe('toPortableAnnualIncomeRecord', () => {
  it('normalizes a well-formed record unchanged', () => {
    const input = {
      id: 1,
      name: 'Salary',
      category: 'salary',
      subcategory: 'regular',
      income_type: 'recurrent' as const,
      amount_annual: '24000',
      fiscal_year: 2025,
      currency: 'EUR',
      notes: '',
    };
    const result = toPortableAnnualIncomeRecord(input);
    expect(result.id).toBe(1);
    expect(result.income_type).toBe('recurrent');
    expect(result.currency).toBe('EUR');
    expect(result.is_active).toBe(true);
  });

  it('preserves one_off income_type', () => {
    const input = {
      id: 2,
      name: 'Bonus',
      category: 'a',
      subcategory: 'b',
      income_type: 'one_off' as const,
      amount_annual: '1000',
      fiscal_year: 2025,
      currency: 'EUR',
      notes: '',
    };
    expect(toPortableAnnualIncomeRecord(input).income_type).toBe('one_off');
  });

  it('defaults income_type to recurrent for unknown values', () => {
    const input = {
      id: 2,
      name: 'X',
      category: 'a',
      subcategory: 'b',
      income_type: 'unknown' as 'recurrent',
      amount_annual: '0',
      fiscal_year: 2025,
      currency: 'USD',
      notes: '',
    };
    expect(toPortableAnnualIncomeRecord(input).income_type).toBe('recurrent');
  });

  it('preserves monthly amount_input_period', () => {
    const input = {
      id: 3,
      name: 'X',
      category: 'a',
      subcategory: 'b',
      income_type: 'recurrent' as const,
      amount_input_period: 'monthly' as const,
      amount_annual: '0',
      fiscal_year: 2025,
      currency: 'EUR',
      notes: '',
    };
    expect(toPortableAnnualIncomeRecord(input).amount_input_period).toBe('monthly');
  });

  it('defaults amount_input_period to annual', () => {
    const input = {
      id: 4,
      name: 'X',
      category: 'a',
      subcategory: 'b',
      income_type: 'recurrent' as const,
      amount_annual: '0',
      fiscal_year: 2025,
      currency: 'EUR',
      notes: '',
    };
    expect(toPortableAnnualIncomeRecord(input).amount_input_period).toBe('annual');
  });

  it('uppercases currency', () => {
    const input = {
      id: 5,
      name: 'X',
      category: 'a',
      subcategory: 'b',
      income_type: 'recurrent' as const,
      amount_annual: '0',
      fiscal_year: 2025,
      currency: 'eur',
      notes: '',
    };
    expect(toPortableAnnualIncomeRecord(input).currency).toBe('EUR');
  });

  it('respects explicit is_active false', () => {
    const input = {
      id: 6,
      name: 'X',
      category: 'a',
      subcategory: 'b',
      income_type: 'recurrent' as const,
      amount_annual: '0',
      fiscal_year: 2025,
      currency: 'EUR',
      notes: '',
      is_active: false,
    };
    expect(toPortableAnnualIncomeRecord(input).is_active).toBe(false);
  });
});

describe('toPortableAnnualExpenseRecord', () => {
  it('normalizes a well-formed record', () => {
    const input = {
      id: 10,
      name: 'Rent',
      category: 'housing',
      subcategory: 'rent',
      expense_type: 'recurrent' as const,
      amount_annual: '12000',
      fiscal_year: 2025,
      currency: 'EUR',
      notes: 'monthly',
    };
    const result = toPortableAnnualExpenseRecord(input);
    expect(result.id).toBe(10);
    expect(result.expense_type).toBe('recurrent');
    expect(result.currency).toBe('EUR');
    expect(result.is_active).toBe(true);
  });

  it('preserves one_off expense_type', () => {
    const input = {
      id: 11,
      name: 'Vacation',
      category: 'leisure',
      subcategory: 'travel',
      expense_type: 'one_off' as const,
      amount_annual: '1000',
      fiscal_year: 2025,
      currency: 'EUR',
      notes: '',
    };
    expect(toPortableAnnualExpenseRecord(input).expense_type).toBe('one_off');
  });

  it('preserves monthly amount_input_period', () => {
    const input = {
      id: 12,
      name: 'X',
      category: 'a',
      subcategory: 'b',
      expense_type: 'recurrent' as const,
      amount_input_period: 'monthly' as const,
      amount_annual: '0',
      fiscal_year: 2025,
      currency: 'EUR',
      notes: '',
    };
    expect(toPortableAnnualExpenseRecord(input).amount_input_period).toBe('monthly');
  });

  it('respects explicit is_active false', () => {
    const input = {
      id: 13,
      name: 'X',
      category: 'a',
      subcategory: 'b',
      expense_type: 'recurrent' as const,
      amount_annual: '0',
      fiscal_year: 2025,
      currency: 'EUR',
      notes: '',
      is_active: false,
    };
    expect(toPortableAnnualExpenseRecord(input).is_active).toBe(false);
  });
});

describe('evaluateImportCompatibility', () => {
  it('returns compatible when versions match', () => {
    const bundle = minimalBundle({ exported_app_version: '1.0.0' });
    expect(evaluateImportCompatibility(bundle, 'append', '1.0.0')).toBe('compatible');
  });

  it('returns newer_than_app when bundle is newer', () => {
    const bundle = minimalBundle({ exported_app_version: '2.0.0' });
    expect(evaluateImportCompatibility(bundle, 'append', '1.0.0')).toBe('newer_than_app');
  });

  it('returns legacy_replace_blocked when version is missing and mode is replace', () => {
    const bundle = minimalBundle({ exported_app_version: undefined });
    expect(evaluateImportCompatibility(bundle, 'replace')).toBe('legacy_replace_blocked');
  });

  it('returns unknown when currentAppVersion is not provided', () => {
    const bundle = minimalBundle({ exported_app_version: '1.0.0' });
    expect(evaluateImportCompatibility(bundle, 'append')).toBe('unknown');
  });
});

describe('buildImportPreviewMessage', () => {
  it('includes mode and source in output', () => {
    const bundle = minimalBundle({ source_app: 'core', exported_app_version: '1.0.0' });
    const msg = buildImportPreviewMessage(bundle, 'append', '1.0.0');
    expect(msg).toContain('Se importaran datos');
    expect(msg).toContain('core');
    expect(msg).toContain('Compatibilidad preliminar: OK.');
  });

  it('includes replace warning when mode is replace', () => {
    const bundle = minimalBundle({ exported_app_version: '1.0.0' });
    const msg = buildImportPreviewMessage(bundle, 'replace', '1.0.0');
    expect(msg).toContain('Se reemplazaran los datos actuales');
    expect(msg).toContain('Se borraran primero');
  });

  it('warns about newer version', () => {
    const bundle = minimalBundle({ exported_app_version: '5.0.0' });
    const msg = buildImportPreviewMessage(bundle, 'replace', '1.0.0');
    expect(msg).toContain('versión más nueva');
  });
});

describe('toPortableAssetRecord', () => {
  it('normalizes a minimal asset', () => {
    const result = toPortableAssetRecord({
      id: 5,
      name: 'House',
      category: 'real_estate',
      currency: 'eur',
    });
    expect(result.id).toBe(5);
    expect(result.currency).toBe('EUR');
    expect(result.tracking_mode).toBe('manual');
    expect(result.investment_contribution_mode).toBe('one_time');
    expect(result.valuation_model).toBe('manual');
    expect(result.contribution_intervals).toEqual([]);
    expect(result.improvements).toEqual([]);
  });

  it('preserves real_estate_auto valuation model', () => {
    const result = toPortableAssetRecord({ id: 1, valuation_model: 'real_estate_auto' });
    expect(result.valuation_model).toBe('real_estate_auto');
  });

  it('defaults contribution_mode to one_time when null', () => {
    const result = toPortableAssetRecord({
      id: 1,
      investment_contribution_mode: null as unknown as undefined,
    });
    expect(result.investment_contribution_mode).toBe('one_time');
  });
});

describe('toPortableLiabilityRecord', () => {
  it('normalizes a minimal liability', () => {
    const result = toPortableLiabilityRecord({
      id: 3,
      name: 'Mortgage',
      category: 'mortgage',
      currency: 'eur',
    });
    expect(result.id).toBe(3);
    expect(result.currency).toBe('EUR');
    expect(result.rate_type).toBe('fixed');
    expect(result.payment_frequency).toBe('monthly');
    expect(result.is_active).toBe(true);
    expect(result.cancellation_forecast_enabled).toBe(false);
  });
});

describe('toPortableLedgerAccountRecord', () => {
  it('normalizes a ledger account', () => {
    const result = toPortableLedgerAccountRecord({
      id: 10,
      name: 'Checking',
      account_type: 'asset',
      currency: 'EUR',
      origin: 'user',
    });
    expect(result.id).toBe(10);
    expect(result.account_type).toBe('asset');
    expect(result.origin).toBe('user');
    expect(result.is_active).toBe(true);
  });

  it('defaults account_type to asset for unknown values', () => {
    const result = toPortableLedgerAccountRecord({ id: 1, account_type: 'unknown' as 'asset' });
    expect(result.account_type).toBe('asset');
  });

  it('detects system origin', () => {
    const result = toPortableLedgerAccountRecord({ id: 1, origin: 'system' });
    expect(result.origin).toBe('system');
  });
});

describe('toPortableLedgerTransactionRecord', () => {
  it('normalizes a basic transaction', () => {
    const result = toPortableLedgerTransactionRecord({
      id: 20,
      booking_date: '2025-01-15',
      value_date: '2025-01-15',
      description: 'Test',
      status: 'posted',
      origin: 'manual',
    });
    expect(result.id).toBe(20);
    expect(result.status).toBe('posted');
    expect(result.origin).toBe('manual');
    expect(result.entries).toEqual([]);
  });

  it('defaults status to posted for unknown values', () => {
    const result = toPortableLedgerTransactionRecord({ id: 1, status: 'unknown' as 'posted' });
    expect(result.status).toBe('posted');
  });

  it('accepts draft status', () => {
    const result = toPortableLedgerTransactionRecord({ id: 1, status: 'draft' });
    expect(result.status).toBe('draft');
  });

  it('accepts import origin', () => {
    const result = toPortableLedgerTransactionRecord({ id: 1, origin: 'import' });
    expect(result.origin).toBe('import');
  });
});

describe('toPortableFamilyMemberRecord', () => {
  it('normalizes an adult member', () => {
    const result = toPortableFamilyMemberRecord({
      id: 1,
      name: 'Alice',
      role: 'adult',
      is_active: true,
    });
    expect(result.id).toBe(1);
    expect(result.role).toBe('adult');
    expect(result.is_active).toBe(true);
  });

  it('preserves child role', () => {
    const result = toPortableFamilyMemberRecord({ id: 2, name: 'Junior', role: 'child' });
    expect(result.role).toBe('child');
  });

  it('defaults role to adult for unknown values', () => {
    const result = toPortableFamilyMemberRecord({ id: 3, role: 'unknown' as 'adult' });
    expect(result.role).toBe('adult');
  });
});

describe('toPortableOwnershipRecord', () => {
  it('normalizes an individual ownership', () => {
    const result = toPortableOwnershipRecord({
      id: 1,
      kind: 'individual',
      member: { id: 1, name: 'Alice', role: 'adult' },
      splits: [],
    });
    expect(result.kind).toBe('individual');
    expect(result.member?.name).toBe('Alice');
    expect(result.splits).toEqual([]);
  });

  it('handles null member', () => {
    const result = toPortableOwnershipRecord({ id: 2, kind: 'shared', member: null });
    expect(result.member).toBeNull();
  });

  it('defaults kind to individual for unknown values', () => {
    const result = toPortableOwnershipRecord({ id: 1, kind: 'unknown' as 'individual' });
    expect(result.kind).toBe('individual');
  });
});

describe('toPortableOwnershipLinkRecord', () => {
  it('normalizes an asset link', () => {
    const result = toPortableOwnershipLinkRecord({
      target_type: 'asset',
      target_id: 5,
      ownership_id: 2,
    });
    expect(result.target_type).toBe('asset');
    expect(result.target_id).toBe(5);
    expect(result.ownership_id).toBe(2);
  });

  it('normalizes a liability link', () => {
    const result = toPortableOwnershipLinkRecord({
      target_type: 'liability',
      target_id: 3,
      ownership_id: 1,
    });
    expect(result.target_type).toBe('liability');
  });
});

describe('parsePortableDataBundle', () => {
  it('parses a minimal valid bundle', () => {
    const bundle = minimalBundle();
    const result = parsePortableDataBundle(JSON.stringify(bundle));
    expect(result.schema_version).toBe(1);
    expect(result.source_app).toBe('core');
    expect(result.data.annual_income).toEqual([]);
    expect(result.data.accounting.accounts).toEqual([]);
  });

  it('throws on invalid schema_version', () => {
    const bad = { schema_version: 2, data: {} };
    expect(() => parsePortableDataBundle(JSON.stringify(bad))).toThrow();
  });

  it('throws when required collections are missing', () => {
    const bad = { schema_version: 1, data: { annual_income: [] } };
    expect(() => parsePortableDataBundle(JSON.stringify(bad))).toThrow();
  });
});
