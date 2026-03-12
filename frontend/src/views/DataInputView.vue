<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { api, coreApi } from '@/lib/api';
import { toApiErrorMessage } from '@/lib/errors';
import {
  ItemForm,
  ItemList,
  type Ownership,
  useNetWorthViewExtensions,
  useNetWorthViewState,
} from '@/domains/net-worth';
import type { NetWorthWritePayload } from '@/domains/net-worth/models';
import { BaseModal } from '@/domains/ui';
import {
  AnnualEntryModalForm,
  expenseCategories,
  expenseSubcategories,
  type ExpenseCategoryKey,
  incomeCategories,
  incomeSubcategories,
  type IncomeCategoryKey,
  useAnnualIncomeStore,
  type AnnualIncomeCashflowRole,
  type AnnualIncomeTimeProfile as IncomeTimeProfile,
  useAnnualExpenseStore,
  type AnnualExpenseCashflowRole,
  type AnnualExpenseTimeProfile as ExpenseTimeProfile,
} from '@/domains/data-input';
import {
  buildImportPreviewMessage,
  buildPortableFilename,
  type ImportMode,
  parsePortableDataBundle,
  type PortableAnnualExpenseRecord,
  type PortableAnnualIncomeRecord,
  type PortableAssetRecord,
  type PortableDataBundle,
  type PortableFamilyMemberRecord,
  type PortableLiabilityRecord,
  type PortableOwnershipLinkRecord,
  type PortableOwnershipRecord,
  type PortableSettingsRecord,
  type PortableSnapshotRecord,
  toPortableAnnualExpenseRecord,
  toPortableAnnualIncomeRecord,
  toPortableAssetRecord,
  toPortableLiabilityRecord,
  toPortableOwnershipRecord,
} from '@/domains/data-input/portableBundle';

const {
  store,
  assetCategories,
  assetSubcategories,
  liabilityCategories,
  prettyError,
  showAssetModal,
  showLiabilityModal,
  showEditModal,
  editItem,
  editKind,
  openEdit,
  closeEdit,
  editTitle,
  editCategories,
  editInitial,
  submitEdit,
} = useNetWorthViewState();

type AssetFormSubmitPayload = NetWorthWritePayload & {
  ownership_id?: number | null;
  estimated_average_balance_for_interest?: string;
  deposit_term_months?: number | null;
};

const { itemFormProps, itemListProps } = useNetWorthViewExtensions(store);

const {
  entries: annualIncomeEntries,
  loading: annualIncomeLoading,
  error: annualIncomeApiError,
  loadAll: loadAnnualIncome,
  addEntry: addIncomeEntry,
  updateEntry: updateIncomeEntry,
  deleteEntry: deleteIncomeEntry,
} = useAnnualIncomeStore('core');
const {
  entries: annualExpenseEntries,
  loading: annualExpenseLoading,
  error: annualExpenseApiError,
  loadAll: loadAnnualExpense,
  addEntry: addExpenseEntry,
  updateEntry: updateExpenseEntry,
  deleteEntry: deleteExpenseEntry,
  listBySourceLiability,
} = useAnnualExpenseStore('core');
const annualIncomeError = ref<string | null>(null);
const annualExpenseError = ref<string | null>(null);
const showIncomeModal = ref(false);
const editingIncomeId = ref<number | null>(null);
const editingExpenseId = ref<number | null>(null);
const showExpenseModal = ref(false);
const showGeneratedLiabilityExpenseModal = ref(false);
const bulkEditingGeneratedLiabilityId = ref<number | null>(null);
const bulkEditingGeneratedExpenseIds = ref<number[]>([]);
const hydratingAnnualIncomeForm = ref(false);
const hydratingAnnualExpenseForm = ref(false);
const expandedIncomeCats = ref<Set<string>>(new Set());
const expandedExpenseCats = ref<Set<string>>(new Set());
const globalOwnershipFilter = ref<number | 'all' | 'unassigned'>('all');
const assetOwnershipFilter = ref<number | 'all' | 'unassigned'>('all');
const liabilityOwnershipFilter = ref<number | 'all' | 'unassigned'>('all');
type VisibilityFilterMode = 'active' | 'archived' | 'all';
const visibilityFilterMode = ref<VisibilityFilterMode>('active');
const generatedLiabilityExpenseReview = ref<{
  liabilityId: number;
  liabilityName: string;
  entries: {
    id: number;
    fiscalYear: number;
    name: string;
    owner: string;
    category: string;
    subcategory: string;
    expenseType: string;
    cashflowRole: string;
    timeProfile: string;
    eventGroup: string;
    targetMonth: number | null;
    termEndMonth: number | null;
    termEndYear: number | null;
    amountInputPeriod: 'annual' | 'monthly';
    amountAnnual: number;
    currency: string;
    notes: string;
  }[];
} | null>(null);
const generatedLiabilityExpenseReviewChangeMessage = ref<string | null>(null);

const annualIncomeForm = reactive({
  category: 'salary' as IncomeCategoryKey,
  subcategory: 'employee_salary',
  name: '',
  owner: '',
  isRecurrent: true,
  timeProfile: 'structural_recurrent' as IncomeTimeProfile,
  cashflowRole: 'operating' as AnnualIncomeCashflowRole,
  eventGroup: '',
  targetMonth: '',
  termEndMonth: '',
  termEndYear: '',
  amountInputPeriod: 'annual' as 'annual' | 'monthly',
  amountAnnual: '',
  currency: 'EUR',
  notes: '',
});
const annualExpenseForm = reactive({
  category: 'consumption_expenses' as ExpenseCategoryKey,
  subcategory: 'living_expenses',
  name: '',
  owner: '',
  isRecurrent: true,
  timeProfile: 'structural_recurrent' as ExpenseTimeProfile,
  cashflowRole: 'operating' as AnnualExpenseCashflowRole,
  eventGroup: '',
  targetMonth: '',
  termEndMonth: '',
  termEndYear: '',
  amountInputPeriod: 'annual' as 'annual' | 'monthly',
  amountAnnual: '',
  currency: 'EUR',
  notes: '',
});

type AnnualModalPatch = Partial<{
  category: string;
  subcategory: string;
  name: string;
  owner: string;
  timeProfile: string;
  cashflowRole: string;
  eventGroup: string;
  targetMonth: string;
  termEndMonth: string;
  termEndYear: string;
  amountInputPeriod: 'annual' | 'monthly';
  amountAnnual: string;
  currency: string;
  notes: string;
}>;

function patchAnnualIncomeForm(patch: AnnualModalPatch): void {
  Object.assign(annualIncomeForm, patch);
}

function patchAnnualExpenseForm(patch: AnnualModalPatch): void {
  Object.assign(annualExpenseForm, patch);
  normalizeExpenseCashflowRoleForCurrentTimeProfile();
}

const annualSubcategoryOptions = computed(() =>
  incomeSubcategories.filter((row) => row.category === annualIncomeForm.category),
);
const LEGACY_SAVINGS_SUBCATEGORIES = new Set(['short_term_savings', 'long_term_savings']);

function normalizeExpenseSubcategoryForUi(category: string, subcategory: string): string {
  if (category === 'savings_allocation' && LEGACY_SAVINGS_SUBCATEGORIES.has(subcategory)) {
    return 'other_savings_allocation';
  }
  return subcategory;
}

const annualExpenseSubcategoryOptions = computed(() =>
  expenseSubcategories.filter(
    (row) =>
      row.category === annualExpenseForm.category &&
      !(row.category === 'savings_allocation' && LEGACY_SAVINGS_SUBCATEGORIES.has(row.value)),
  ),
);
const annualEventGroupOptions = computed(() => {
  const groups = new Set<string>();
  for (const entry of annualIncomeEntries.value) {
    const group = String(entry.eventGroup ?? '').trim();
    if (group) groups.add(group);
  }
  for (const entry of annualExpenseEntries.value) {
    const group = String(entry.eventGroup ?? '').trim();
    if (group) groups.add(group);
  }
  return Array.from(groups).sort((a, b) => a.localeCompare(b, 'es', { sensitivity: 'base' }));
});
type OwnerOption = { key: string; value: string; label: string };
type SelectOption = { value: string; label: string };

const incomeTimeProfileOptions = computed<SelectOption[]>(() => {
  if (annualIncomeForm.category === 'capital_gains') {
    return [{ value: 'one_off', label: 'Puntual / extraordinario' }];
  }
  return [
    { value: 'structural_recurrent', label: 'Recurrente estructural (base)' },
    { value: 'term_recurrent', label: 'Recurrente temporal (con fin)' },
    { value: 'one_off', label: 'Puntual / extraordinario' },
  ];
});

const incomeCashflowRoleOptions: SelectOption[] = [
  { value: 'operating', label: 'Naturaleza: Operativo' },
  { value: 'transfer', label: 'Naturaleza: Transferencia/apoyo' },
  { value: 'asset_sale', label: 'Naturaleza: Venta de activo' },
  { value: 'tax_adjustment', label: 'Naturaleza: Ajuste fiscal' },
  { value: 'other', label: 'Naturaleza: Otro' },
];

const expenseTimeProfileOptions: SelectOption[] = [
  { value: 'structural_recurrent', label: 'Gasto recurrente' },
  { value: 'term_recurrent', label: 'Cuotas o compromisos temporales' },
  { value: 'one_off', label: 'Gasto puntual o extraordinario' },
];

const expenseCashflowRoleOptions: SelectOption[] = [
  { value: 'operating', label: 'Naturaleza: Operativo' },
  { value: 'temporary_commitment', label: 'Naturaleza: Compromiso temporal' },
  { value: 'savings', label: 'Naturaleza: Ahorro' },
  { value: 'investment', label: 'Naturaleza: Inversion' },
  { value: 'asset_purchase', label: 'Naturaleza: Compra de activo' },
  { value: 'tax_fee', label: 'Naturaleza: Impuestos/gastos' },
  { value: 'transfer', label: 'Naturaleza: Transferencia' },
  { value: 'other', label: 'Naturaleza: Otro' },
];

const EXPENSE_STRUCTURAL_ALLOWED_CASHFLOW_ROLES: AnnualExpenseCashflowRole[] = [
  'operating',
  'savings',
  'investment',
  'tax_fee',
  'other',
];
const EXPENSE_ONE_OFF_ALLOWED_CASHFLOW_ROLES: AnnualExpenseCashflowRole[] = [
  'savings',
  'investment',
  'tax_fee',
  'asset_purchase',
  'transfer',
  'other',
];

function allowedExpenseCashflowRolesForTimeProfile(
  timeProfile: ExpenseTimeProfile,
): AnnualExpenseCashflowRole[] {
  if (timeProfile === 'term_recurrent') return ['temporary_commitment'];
  if (timeProfile === 'one_off') return EXPENSE_ONE_OFF_ALLOWED_CASHFLOW_ROLES;
  return EXPENSE_STRUCTURAL_ALLOWED_CASHFLOW_ROLES;
}

const filteredExpenseCashflowRoleOptions = computed<SelectOption[]>(() => {
  const allowed = new Set(allowedExpenseCashflowRolesForTimeProfile(annualExpenseForm.timeProfile));
  return expenseCashflowRoleOptions.filter((option) =>
    allowed.has(option.value as AnnualExpenseCashflowRole),
  );
});

const showExpenseCashflowRoleField = computed(
  () => annualExpenseForm.timeProfile !== 'term_recurrent',
);

function normalizeExpenseCashflowRoleForCurrentTimeProfile(): void {
  const allowed = allowedExpenseCashflowRolesForTimeProfile(annualExpenseForm.timeProfile);
  if (!allowed.length) return;
  if (allowed.includes(annualExpenseForm.cashflowRole)) return;

  if (annualExpenseForm.timeProfile === 'term_recurrent') {
    annualExpenseForm.cashflowRole = 'temporary_commitment';
    return;
  }

  const suggested = defaultExpenseCashflowRole(
    annualExpenseForm.category,
    annualExpenseForm.subcategory,
  );
  annualExpenseForm.cashflowRole = allowed.includes(suggested) ? suggested : allowed[0]!;
}

function formatOwnershipPercent(raw: string): string {
  const value = Number(String(raw).replace(',', '.'));
  if (!Number.isFinite(value)) return `${raw}%`;
  const rounded = Math.round(value * 100) / 100;
  const normalized = Number.isInteger(rounded)
    ? String(rounded)
    : String(rounded).replace(/\.?0+$/, '');
  return `${normalized}%`;
}

function sharedOwnershipLabel(
  splits: { member: { id: number; name: string; role: 'adult' | 'child' }; percent: string }[],
): string {
  if (!splits.length) return 'Compartido';
  const details = splits.map(
    (split) => `${split.member.name} ${formatOwnershipPercent(split.percent)}`,
  );
  return `Compartido (${details.join(' / ')})`;
}

const ownerOptions = computed(() => {
  const options = new Map<string, OwnerOption>();
  for (const ownership of store.ownerships ?? []) {
    if (ownership.kind === 'individual' && ownership.member) {
      const value = ownership.member.name;
      options.set(`individual:${ownership.member.id}`, {
        key: `individual:${ownership.member.id}`,
        value,
        label: value,
      });
    }
    if (ownership.kind === 'shared') {
      const label = sharedOwnershipLabel(ownership.splits ?? []);
      options.set(`shared:${ownership.id}`, {
        key: `shared:${ownership.id}`,
        value: label,
        label,
      });
    }
  }
  return Array.from(options.values()).sort((a, b) => a.label.localeCompare(b.label));
});

const sharedOwnershipAllocationsByLabel = computed(() => {
  const map = new Map<string, { name: string; share: number }[]>();
  for (const ownership of store.ownerships ?? []) {
    if (ownership.kind !== 'shared') continue;
    const label = sharedOwnershipLabel(ownership.splits ?? []);
    const shares = (ownership.splits ?? [])
      .map((split) => {
        const share = Number(String(split.percent ?? '').replace(',', '.'));
        const name = split.member?.name?.trim() ?? '';
        if (!name || !Number.isFinite(share) || share <= 0) return null;
        return { name, share };
      })
      .filter((row): row is { name: string; share: number } => row != null);
    if (shares.length) {
      map.set(label, shares);
    }
  }
  return map;
});

function normalizeOwnerKey(raw: string): string {
  return String(raw ?? '')
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .trim()
    .replace(/\s+/g, ' ')
    .toLowerCase();
}

const annualOwnerFilterOptions = computed(() =>
  ownerOptions.value
    .filter((option) => option.key.startsWith('individual:'))
    .sort((a, b) => a.label.localeCompare(b.label)),
);
const globalOwnershipFilterOptions = computed(() =>
  annualOwnerFilterOptions.value
    .map((option) => {
      const id = Number(option.key.replace('individual:', ''));
      return Number.isInteger(id) ? { id, label: option.label } : null;
    })
    .filter((option): option is { id: number; label: string } => option != null),
);
const showOwnerField = computed(() => ownerOptions.value.length > 1);
const fiscalYear = ref(2026);
const fiscalYearOptions = computed(() => {
  const current = new Date().getFullYear();
  const years = new Set<number>([current - 1, current, current + 1, 2026]);
  return Array.from(years).sort((a, b) => b - a);
});

function parseSharedOwnerShares(ownerLabel: string): { name: string; share: number }[] {
  const text = String(ownerLabel ?? '').trim();
  if (!text) return [];
  const match = text.match(/^Compartido\s*\((.*)\)$/i);
  if (!match?.[1]) return [];
  return match[1]
    .split(/\s*(?:\/|,|;)\s*/)
    .map((part) => {
      const piece = part.trim();
      const parsed = piece.match(/^(.*)\s+(\d+(?:[.,]\d+)?)\s*%?$/);
      if (!parsed?.[1] || !parsed[2]) return null;
      const name = parsed[1].trim();
      const share = Number(parsed[2].replace(',', '.'));
      if (!name || !Number.isFinite(share) || share <= 0) return null;
      return { name, share };
    })
    .filter((row): row is { name: string; share: number } => row != null);
}

function allocatedFractionForAnnualOwner(ownerLabel: string, selectedOwner: string): number {
  if (selectedOwner === 'all') return 1;
  const text = String(ownerLabel ?? '').trim();
  if (!text) return 0;
  if (text.localeCompare(selectedOwner, 'es', { sensitivity: 'base' }) === 0) return 1;

  const normalizedText = normalizeOwnerKey(text);
  const sharedEntries = Array.from(sharedOwnershipAllocationsByLabel.value.entries());
  const sharedFromOwnerships = sharedEntries.find(
    ([label]) => normalizeOwnerKey(label) === normalizedText,
  )?.[1];
  const fallbackBareShared =
    normalizeOwnerKey(text) === 'compartido' && sharedEntries.length === 1
      ? sharedEntries[0]?.[1]
      : null;
  const shared = sharedFromOwnerships ?? fallbackBareShared ?? parseSharedOwnerShares(text);
  if (!shared.length) return 0;
  const totalShare = shared.reduce((sum, row) => sum + row.share, 0);
  const matchedShare = shared
    .filter((row) => normalizeOwnerKey(row.name) === normalizeOwnerKey(selectedOwner))
    .reduce((sum, row) => sum + row.share, 0);
  if (!Number.isFinite(matchedShare) || matchedShare <= 0) return 0;

  if (totalShare > 0 && totalShare <= 1.0001) {
    return matchedShare / totalShare;
  }
  if (totalShare > 0 && totalShare <= 100.0001) {
    return matchedShare / 100;
  }
  return matchedShare / totalShare;
}

function filterAnnualEntriesByOwner<T extends { owner: string; amountAnnual: number }>(
  list: T[],
  selectedOwner: string,
): T[] {
  if (selectedOwner === 'all') return list;
  if (selectedOwner === 'unassigned') {
    return list.filter((entry) => !String(entry.owner ?? '').trim());
  }
  return list
    .map((entry) => {
      const fraction = allocatedFractionForAnnualOwner(entry.owner, selectedOwner);
      return fraction > 0 ? { ...entry, amountAnnual: entry.amountAnnual * fraction } : null;
    })
    .filter((entry): entry is T => entry != null && entry.amountAnnual > 0);
}

function roundToMoney(value: number): number {
  return Math.round(value * 100) / 100;
}

function effectiveAnnualAmountForSelectedYear(
  entry: {
    amountAnnual: number;
    timeProfile: IncomeTimeProfile | ExpenseTimeProfile;
    termEndYear: number | null;
    termEndMonth: number | null;
  },
  selectedYear: number,
): number {
  if (entry.timeProfile !== 'term_recurrent') return entry.amountAnnual;
  if (entry.termEndYear == null || entry.termEndYear !== selectedYear) return entry.amountAnnual;
  const months = Math.min(12, Math.max(1, Number(entry.termEndMonth ?? 12)));
  return roundToMoney((entry.amountAnnual * months) / 12);
}

function isVisibleByFilterMode(isActive: boolean | undefined): boolean {
  if (visibilityFilterMode.value === 'all') return true;
  if (visibilityFilterMode.value === 'archived') return isActive === false;
  return isActive !== false;
}

const annualIncomeEntriesByVisibility = computed(() =>
  annualIncomeEntries.value
    .filter((entry) => isVisibleByFilterMode(entry.isActive))
    .map((entry) => ({
      ...entry,
      amountAnnual: effectiveAnnualAmountForSelectedYear(entry, fiscalYear.value),
    })),
);
const annualExpenseEntriesByVisibility = computed(() =>
  annualExpenseEntries.value
    .filter((entry) => isVisibleByFilterMode(entry.isActive))
    .map((entry) => ({
      ...entry,
      amountAnnual: effectiveAnnualAmountForSelectedYear(entry, fiscalYear.value),
    })),
);

const annualOwnerFilterValue = computed(() => {
  if (globalOwnershipFilter.value === 'all') return 'all';
  if (globalOwnershipFilter.value === 'unassigned') return 'unassigned';
  const member = globalOwnershipFilterOptions.value.find(
    (option) => option.id === globalOwnershipFilter.value,
  );
  return member?.label ?? 'all';
});

const filteredAnnualIncomeEntries = computed(() =>
  filterAnnualEntriesByOwner(annualIncomeEntriesByVisibility.value, annualOwnerFilterValue.value),
);
const filteredAnnualExpenseEntries = computed(() =>
  filterAnnualEntriesByOwner(annualExpenseEntriesByVisibility.value, annualOwnerFilterValue.value),
);

const filteredAnnualIncomeTotal = computed(() =>
  filteredAnnualIncomeEntries.value.reduce((sum, entry) => sum + entry.amountAnnual, 0),
);
const filteredAnnualExpenseTotal = computed(() =>
  filteredAnnualExpenseEntries.value.reduce((sum, entry) => sum + entry.amountAnnual, 0),
);
const annualBalanceTotal = computed(
  () => filteredAnnualIncomeTotal.value - filteredAnnualExpenseTotal.value,
);
const activeAssets = computed(() => store.assets.filter((item) => item.is_active !== false));
const activeLiabilities = computed(() =>
  store.liabilities.filter((item) => item.is_active !== false),
);
const archivedAssets = computed(() => store.assets.filter((item) => item.is_active === false));
const archivedLiabilities = computed(() =>
  store.liabilities.filter((item) => item.is_active === false),
);
const visibleAssets = computed(() =>
  visibilityFilterMode.value === 'all'
    ? store.assets
    : visibilityFilterMode.value === 'archived'
      ? archivedAssets.value
      : activeAssets.value,
);
const visibleLiabilities = computed(() =>
  visibilityFilterMode.value === 'all'
    ? store.liabilities
    : visibilityFilterMode.value === 'archived'
      ? archivedLiabilities.value
      : activeLiabilities.value,
);
const visibleAssetsByOwner = computed(() =>
  visibleAssets.value.filter(
    (item) => allocatedFractionForNetWorthOwner(item.ownership_ref, assetOwnershipFilter.value) > 0,
  ),
);
const visibleLiabilitiesByOwner = computed(() =>
  visibleLiabilities.value.filter(
    (item) =>
      allocatedFractionForNetWorthOwner(item.ownership_ref, liabilityOwnershipFilter.value) > 0,
  ),
);
const annualIncomeCount = computed(() => filteredAnnualIncomeEntries.value.length);
const annualExpenseCount = computed(() => filteredAnnualExpenseEntries.value.length);
const assetsCount = computed(() => visibleAssetsByOwner.value.length);
const liabilitiesCount = computed(() => visibleLiabilitiesByOwner.value.length);
const hasIncomeData = computed(() => annualIncomeCount.value > 0);
const hasExpenseData = computed(() => annualExpenseCount.value > 0);
const hasAssetData = computed(() => assetsCount.value > 0);
const hasLiabilityData = computed(() => liabilitiesCount.value > 0);
const hasCompleteDataInput = computed(
  () => hasIncomeData.value && hasExpenseData.value && hasAssetData.value && hasLiabilityData.value,
);
const dataInputCheckTitle = computed(() =>
  hasCompleteDataInput.value ? 'Check de datos: completo' : 'Check de datos: pendiente',
);
const dataInputSummary = computed(() => {
  const incomePart = hasIncomeData.value
    ? `${annualIncomeCount.value} ingresos registrados`
    : 'sin ingresos registrados';
  const expensePart = hasExpenseData.value
    ? `${annualExpenseCount.value} gastos registrados`
    : 'sin gastos registrados';
  const assetsPart = hasAssetData.value
    ? `${assetsCount.value} activos registrados`
    : 'sin activos registrados';
  const liabilitiesPart = hasLiabilityData.value
    ? `${liabilitiesCount.value} pasivos registrados`
    : 'sin pasivos registrados';
  return `Estado actual: ${incomePart}, ${expensePart}, ${assetsPart} y ${liabilitiesPart}. Completa los cuatro bloques para un diagnostico patrimonial fiable.`;
});

watch(
  () => annualIncomeForm.category,
  () => {
    const options = annualSubcategoryOptions.value;
    if (!options.length) return;
    const isCurrentValid = options.some((row) => row.value === annualIncomeForm.subcategory);
    if (!isCurrentValid) {
      annualIncomeForm.subcategory = options[0]!.value;
    }
  },
);
watch(
  () => annualExpenseForm.category,
  () => {
    const options = annualExpenseSubcategoryOptions.value;
    if (!options.length) return;
    const isCurrentValid = options.some((row) => row.value === annualExpenseForm.subcategory);
    if (!isCurrentValid) {
      annualExpenseForm.subcategory = options[0]!.value;
    }
  },
);
watch(
  ownerOptions,
  (options) => {
    const singleOwner = options[0];
    if (options.length === 1) {
      annualIncomeForm.owner = singleOwner?.value ?? '';
      annualExpenseForm.owner = singleOwner?.value ?? '';
      return;
    }
    if (options.length === 0) {
      annualIncomeForm.owner = '';
      annualExpenseForm.owner = '';
      return;
    }
    if (
      annualIncomeForm.owner &&
      !options.some((option) => option.value === annualIncomeForm.owner)
    ) {
      annualIncomeForm.owner = '';
    }
    if (
      annualExpenseForm.owner &&
      !options.some((option) => option.value === annualExpenseForm.owner)
    ) {
      annualExpenseForm.owner = '';
    }
  },
  { immediate: true },
);
watch(
  globalOwnershipFilterOptions,
  (options) => {
    const filter = globalOwnershipFilter.value;
    if (filter === 'all' || filter === 'unassigned') return;
    if (!options.some((option) => option.id === filter)) {
      globalOwnershipFilter.value = 'all';
    }
  },
  { immediate: true },
);
watch(
  globalOwnershipFilter,
  (value) => {
    assetOwnershipFilter.value = value;
    liabilityOwnershipFilter.value = value;
  },
  { immediate: true },
);

function formatMoneyAmount(value: number, currency: string): string {
  return new Intl.NumberFormat('es-ES', {
    style: 'currency',
    currency,
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function parseNumeric(raw: unknown): number {
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(',', '.');
  const value = Number(normalized);
  return Number.isFinite(value) ? value : 0;
}

const ownershipById = computed(() => {
  const map = new Map<number, Ownership>();
  for (const ownership of store.ownerships ?? []) {
    map.set(ownership.id, ownership);
  }
  return map;
});

function normalizeOwnershipSharePercent(raw: unknown): number {
  const value = parseNumeric(raw);
  if (!Number.isFinite(value) || value <= 0) return 0;
  return value <= 1 ? value * 100 : value;
}

function allocatedFractionForNetWorthOwner(
  ownershipRef: number | null | undefined,
  selectedOwner: number | 'all' | 'unassigned',
): number {
  if (selectedOwner === 'all') return 1;
  if (selectedOwner === 'unassigned') return ownershipRef == null ? 1 : 0;
  if (ownershipRef == null) return 0;

  const ownership = ownershipById.value.get(ownershipRef);
  if (!ownership) return 0;

  if (ownership.kind === 'individual') {
    return ownership.member?.id === selectedOwner ? 1 : 0;
  }

  const split = (ownership.splits ?? []).find((row) => row.member?.id === selectedOwner);
  if (!split) return 0;
  return normalizeOwnershipSharePercent(split.percent) / 100;
}

function annualOwnerLabelFromOwnershipId(ownershipId: number | null | undefined): string {
  if (ownershipId == null) return '';
  const ownership = ownershipById.value.get(ownershipId);
  if (!ownership) return '';
  if (ownership.kind === 'individual') {
    return ownership.member?.name?.trim() ?? '';
  }
  if (ownership.kind === 'shared') {
    return sharedOwnershipLabel(ownership.splits ?? []);
  }
  return '';
}

function filteredNetWorthTotalBase(
  items: Array<{ amount_base?: string | null; ownership_ref?: number | null }>,
  selectedOwner: number | 'all' | 'unassigned',
): number {
  let total = 0;
  for (const item of items) {
    const amountBase = parseNumeric(item.amount_base ?? '0');
    if (!Number.isFinite(amountBase) || amountBase === 0) continue;
    const fraction = allocatedFractionForNetWorthOwner(item.ownership_ref, selectedOwner);
    if (fraction <= 0) continue;
    total += amountBase * fraction;
  }
  return total;
}

const assetsTotalBase = computed(() =>
  assetOwnershipFilter.value === 'all'
    ? parseNumeric(store.summary?.total_assets ?? '0')
    : filteredNetWorthTotalBase(store.assets, assetOwnershipFilter.value),
);
const liabilitiesTotalBase = computed(() =>
  liabilityOwnershipFilter.value === 'all'
    ? parseNumeric(store.summary?.total_liabilities ?? '0')
    : filteredNetWorthTotalBase(store.liabilities, liabilityOwnershipFilter.value),
);
const netAssetsBase = computed(() => assetsTotalBase.value - liabilitiesTotalBase.value);
const netAssetsCurrency = computed(
  () => store.baseCurrency ?? store.summary?.base_currency ?? 'EUR',
);

type AnnualIncomeEntry = (typeof annualIncomeEntries.value)[number];
type AnnualIncomeSubgroup = {
  subcategory: string;
  label: string;
  entries: AnnualIncomeEntry[];
  totals: Record<string, number>;
};
type AnnualIncomeGroup = {
  category: string;
  label: string;
  entries: AnnualIncomeEntry[];
  subgroups: AnnualIncomeSubgroup[];
  totals: Record<string, number>;
};
type AnnualExpenseEntry = (typeof annualExpenseEntries.value)[number];
type AnnualExpenseSubgroup = {
  subcategory: string;
  label: string;
  entries: AnnualExpenseEntry[];
  totals: Record<string, number>;
};
type AnnualExpenseGroup = {
  category: string;
  label: string;
  entries: AnnualExpenseEntry[];
  subgroups: AnnualExpenseSubgroup[];
  totals: Record<string, number>;
};

const incomeCategoryOrder = new Map(
  incomeCategories.map((category, index) => [category.value, index]),
);
const expenseCategoryOrder = new Map(
  expenseCategories.map((category, index) => [category.value, index]),
);

function incomeCategoryLabel(key: string): string {
  return incomeCategories.find((category) => category.value === key)?.label ?? key;
}

function incomeSubcategoryLabel(key: string): string {
  return incomeSubcategories.find((subcategory) => subcategory.value === key)?.label ?? key;
}
function expenseCategoryLabel(key: string): string {
  return expenseCategories.find((category) => category.value === key)?.label ?? key;
}
function expenseSubcategoryLabel(key: string): string {
  if (LEGACY_SAVINGS_SUBCATEGORIES.has(key)) return 'Ahorro general';
  return expenseSubcategories.find((subcategory) => subcategory.value === key)?.label ?? key;
}

function timeProfileLabel(type: IncomeTimeProfile | ExpenseTimeProfile): string {
  if (type === 'structural_recurrent') return 'Recurrente estructural';
  if (type === 'term_recurrent') return 'Recurrente temporal';
  return 'Puntual';
}
function expenseCashflowRoleLabel(role: AnnualExpenseCashflowRole): string {
  if (role === 'operating') return 'Operativo';
  if (role === 'temporary_commitment') return 'Compromiso temporal';
  if (role === 'savings') return 'Ahorro';
  if (role === 'investment') return 'Inversion';
  if (role === 'asset_purchase') return 'Compra de activo';
  if (role === 'tax_fee') return 'Impuestos/gastos';
  if (role === 'transfer') return 'Transferencia';
  return 'Otro';
}

function eventGroupLabel(eventGroup: string): string {
  const principalCancellation = /^liability_(\d+)_cancellation_principal$/;
  const feeCancellation = /^liability_(\d+)_cancellation_fee$/;
  if (principalCancellation.test(eventGroup)) return 'Cancelacion anticipada principal';
  if (feeCancellation.test(eventGroup)) return 'Cancelacion anticipada comision';
  return eventGroup;
}

function formatTermEndLabel(
  termEndYear: number | null,
  termEndMonth: number | null,
): string | null {
  if (termEndYear == null) return null;
  if (termEndMonth == null) return `Fin ${termEndYear}`;
  return `Fin ${String(termEndMonth).padStart(2, '0')}/${termEndYear}`;
}

function amountInputValueFromAnnual(annualAmount: number, period: 'annual' | 'monthly'): string {
  if (period === 'monthly') return String(Math.round((annualAmount / 12) * 100) / 100);
  return String(annualAmount);
}

function shouldHideExpenseCashflowRoleLabel(params: {
  timeProfile: ExpenseTimeProfile;
  cashflowRole: AnnualExpenseCashflowRole;
}): boolean {
  return (
    (params.timeProfile === 'term_recurrent' && params.cashflowRole === 'temporary_commitment') ||
    (params.timeProfile === 'one_off' && params.cashflowRole === 'temporary_commitment')
  );
}

function timeProfileDotClass(
  timeProfile: IncomeTimeProfile | ExpenseTimeProfile | undefined,
): string {
  if (timeProfile === 'term_recurrent') return 'income-rec-dot-recurrent-term';
  if (timeProfile === 'one_off') return 'income-rec-dot-one-off';
  return 'income-rec-dot-recurrent';
}

function defaultIncomeCashflowRole(category: IncomeCategoryKey): AnnualIncomeCashflowRole {
  if (category === 'capital_gains') return 'asset_sale';
  if (category === 'transfers_support' || category === 'public_benefits') return 'transfer';
  if (category === 'other_income') return 'other';
  return 'operating';
}

function defaultExpenseCashflowRole(
  category: ExpenseCategoryKey,
  subcategory: string,
): AnnualExpenseCashflowRole {
  if (category === 'savings_allocation') return 'savings';
  if (category === 'financial_investments') return 'investment';
  if (category === 'real_estate_assets' || category === 'tangible_assets') {
    return subcategory === 'real_estate_fees_taxes' ? 'tax_fee' : 'asset_purchase';
  }
  return 'operating';
}

function sumByCurrency(
  entries: { currency: string; amountAnnual: number }[],
): Record<string, number> {
  const totals: Record<string, number> = {};
  for (const entry of entries) {
    const currency = entry.currency || 'EUR';
    totals[currency] = (totals[currency] ?? 0) + entry.amountAnnual;
  }
  return totals;
}

function formatTotalsLine(totals: Record<string, number>): string {
  return Object.entries(totals)
    .filter(([, amount]) => amount !== 0)
    .map(([currency, amount]) => formatMoneyAmount(amount, currency))
    .join(' | ');
}

function incomeCategoryClass(category: string): string {
  return `income-cat-${category || 'other_income'}`;
}
function expenseCategoryClass(category: string): string {
  return `expense-cat-${category || 'consumption_expenses'}`;
}

function incomeCategoryPercent(entries: AnnualIncomeEntry[]): string | null {
  if (!filteredAnnualIncomeTotal.value) return null;
  const categoryTotal = entries.reduce((sum, entry) => sum + entry.amountAnnual, 0);
  if (!categoryTotal) return null;
  const pct = (categoryTotal / filteredAnnualIncomeTotal.value) * 100;
  return new Intl.NumberFormat('es-ES', {
    maximumFractionDigits: 1,
    minimumFractionDigits: 0,
  }).format(pct);
}
function expenseCategoryPercent(entries: AnnualExpenseEntry[]): string | null {
  if (!filteredAnnualExpenseTotal.value) return null;
  const categoryTotal = entries.reduce((sum, entry) => sum + entry.amountAnnual, 0);
  if (!categoryTotal) return null;
  const pct = (categoryTotal / filteredAnnualExpenseTotal.value) * 100;
  return new Intl.NumberFormat('es-ES', {
    maximumFractionDigits: 1,
    minimumFractionDigits: 0,
  }).format(pct);
}

function isIncomeGroupExpanded(category: string): boolean {
  return expandedIncomeCats.value.has(category);
}

function toggleIncomeCategory(category: string): void {
  const next = new Set(expandedIncomeCats.value);
  if (next.has(category)) next.delete(category);
  else next.add(category);
  expandedIncomeCats.value = next;
}
function isExpenseGroupExpanded(category: string): boolean {
  return expandedExpenseCats.value.has(category);
}
function toggleExpenseCategory(category: string): void {
  const next = new Set(expandedExpenseCats.value);
  if (next.has(category)) next.delete(category);
  else next.add(category);
  expandedExpenseCats.value = next;
}

const annualIncomeGroups = computed<AnnualIncomeGroup[]>(() => {
  const categoryMap = new Map<string, AnnualIncomeEntry[]>();

  for (const entry of filteredAnnualIncomeEntries.value) {
    if (!categoryMap.has(entry.category)) categoryMap.set(entry.category, []);
    categoryMap.get(entry.category)!.push(entry);
  }

  return Array.from(categoryMap.entries())
    .sort(([a], [b]) => {
      const aOrder = incomeCategoryOrder.get(a as IncomeCategoryKey) ?? Number.MAX_SAFE_INTEGER;
      const bOrder = incomeCategoryOrder.get(b as IncomeCategoryKey) ?? Number.MAX_SAFE_INTEGER;
      if (aOrder !== bOrder) return aOrder - bOrder;
      return incomeCategoryLabel(a).localeCompare(incomeCategoryLabel(b));
    })
    .map(([category, entries]) => {
      const sortedEntries = entries.slice().sort((x, y) => x.name.localeCompare(y.name));
      const subcategoryMap = new Map<string, AnnualIncomeEntry[]>();

      for (const entry of sortedEntries) {
        const subcategory = entry.subcategory || 'other';
        if (!subcategoryMap.has(subcategory)) subcategoryMap.set(subcategory, []);
        subcategoryMap.get(subcategory)!.push(entry);
      }

      const subgroups = Array.from(subcategoryMap.entries())
        .sort(([a], [b]) => incomeSubcategoryLabel(a).localeCompare(incomeSubcategoryLabel(b)))
        .map(([subcategory, subgroupEntries]) => ({
          subcategory,
          label: incomeSubcategoryLabel(subcategory),
          entries: subgroupEntries,
          totals: sumByCurrency(subgroupEntries),
        }));

      return {
        category,
        label: incomeCategoryLabel(category),
        entries: sortedEntries,
        subgroups,
        totals: sumByCurrency(sortedEntries),
      };
    });
});
const annualExpenseGroups = computed<AnnualExpenseGroup[]>(() => {
  const categoryMap = new Map<string, AnnualExpenseEntry[]>();

  for (const entry of filteredAnnualExpenseEntries.value) {
    if (!categoryMap.has(entry.category)) categoryMap.set(entry.category, []);
    categoryMap.get(entry.category)!.push(entry);
  }

  return Array.from(categoryMap.entries())
    .sort(([a], [b]) => {
      const aOrder = expenseCategoryOrder.get(a as ExpenseCategoryKey) ?? Number.MAX_SAFE_INTEGER;
      const bOrder = expenseCategoryOrder.get(b as ExpenseCategoryKey) ?? Number.MAX_SAFE_INTEGER;
      if (aOrder !== bOrder) return aOrder - bOrder;
      return expenseCategoryLabel(a).localeCompare(expenseCategoryLabel(b));
    })
    .map(([category, entries]) => {
      const sortedEntries = entries.slice().sort((x, y) => x.name.localeCompare(y.name));
      const subcategoryMap = new Map<string, AnnualExpenseEntry[]>();

      for (const entry of sortedEntries) {
        const subcategory = entry.subcategory || 'other_consumption_expenses';
        if (!subcategoryMap.has(subcategory)) subcategoryMap.set(subcategory, []);
        subcategoryMap.get(subcategory)!.push(entry);
      }

      const subgroups = Array.from(subcategoryMap.entries())
        .sort(([a], [b]) => expenseSubcategoryLabel(a).localeCompare(expenseSubcategoryLabel(b)))
        .map(([subcategory, subgroupEntries]) => ({
          subcategory,
          label: expenseSubcategoryLabel(subcategory),
          entries: subgroupEntries,
          totals: sumByCurrency(subgroupEntries),
        }));

      return {
        category,
        label: expenseCategoryLabel(category),
        entries: sortedEntries,
        subgroups,
        totals: sumByCurrency(sortedEntries),
      };
    });
});

function resetIncomeForm(): void {
  const singleOwner = ownerOptions.value[0];
  annualIncomeForm.category = 'salary';
  annualIncomeForm.subcategory = 'employee_salary';
  annualIncomeForm.name = '';
  annualIncomeForm.owner = ownerOptions.value.length === 1 ? (singleOwner?.value ?? '') : '';
  annualIncomeForm.isRecurrent = true;
  annualIncomeForm.timeProfile = 'structural_recurrent';
  annualIncomeForm.cashflowRole = defaultIncomeCashflowRole(annualIncomeForm.category);
  annualIncomeForm.eventGroup = '';
  annualIncomeForm.targetMonth = '';
  annualIncomeForm.termEndMonth = '';
  annualIncomeForm.termEndYear = '';
  annualIncomeForm.amountInputPeriod = 'annual';
  annualIncomeForm.amountAnnual = '';
  annualIncomeForm.currency = 'EUR';
  annualIncomeForm.notes = '';
}
function resetExpenseForm(): void {
  const singleOwner = ownerOptions.value[0];
  annualExpenseForm.category = 'consumption_expenses';
  annualExpenseForm.subcategory = 'living_expenses';
  annualExpenseForm.name = '';
  annualExpenseForm.owner = ownerOptions.value.length === 1 ? (singleOwner?.value ?? '') : '';
  annualExpenseForm.isRecurrent = true;
  annualExpenseForm.timeProfile = 'structural_recurrent';
  annualExpenseForm.cashflowRole = defaultExpenseCashflowRole(
    annualExpenseForm.category,
    annualExpenseForm.subcategory,
  );
  annualExpenseForm.eventGroup = '';
  annualExpenseForm.targetMonth = '';
  annualExpenseForm.termEndMonth = '';
  annualExpenseForm.termEndYear = '';
  annualExpenseForm.amountInputPeriod = 'annual';
  annualExpenseForm.amountAnnual = '';
  annualExpenseForm.currency = 'EUR';
  annualExpenseForm.notes = '';
}

function openIncomeModal(entry?: AnnualIncomeEntry): void {
  annualIncomeError.value = null;
  hydratingAnnualIncomeForm.value = true;
  if (entry) {
    editingIncomeId.value = entry.id;
    annualIncomeForm.category = entry.category;
    annualIncomeForm.subcategory = entry.subcategory;
    annualIncomeForm.name = entry.name;
    annualIncomeForm.owner = entry.owner || '';
    annualIncomeForm.isRecurrent = entry.incomeType === 'recurrent';
    annualIncomeForm.timeProfile =
      entry.category === 'capital_gains' ? 'one_off' : entry.timeProfile;
    annualIncomeForm.cashflowRole = entry.cashflowRole;
    annualIncomeForm.eventGroup = entry.eventGroup || '';
    annualIncomeForm.targetMonth =
      entry.targetMonth == null ? '' : String(Number(entry.targetMonth));
    annualIncomeForm.termEndMonth =
      entry.termEndMonth == null ? '' : String(Number(entry.termEndMonth));
    annualIncomeForm.termEndYear =
      entry.termEndYear == null ? '' : String(Number(entry.termEndYear));
    annualIncomeForm.amountInputPeriod = entry.amountInputPeriod ?? 'annual';
    annualIncomeForm.amountAnnual = amountInputValueFromAnnual(
      entry.amountAnnual,
      annualIncomeForm.amountInputPeriod,
    );
    annualIncomeForm.currency = entry.currency;
    annualIncomeForm.notes = entry.notes || '';
  } else {
    editingIncomeId.value = null;
    resetIncomeForm();
  }
  showIncomeModal.value = true;
  void nextTick(() => {
    hydratingAnnualIncomeForm.value = false;
  });
}
function openExpenseModal(entry?: AnnualExpenseEntry): void {
  annualExpenseError.value = null;
  hydratingAnnualExpenseForm.value = true;
  if (entry) {
    editingExpenseId.value = entry.id;
    annualExpenseForm.category = entry.category;
    annualExpenseForm.subcategory = normalizeExpenseSubcategoryForUi(
      entry.category,
      entry.subcategory,
    );
    annualExpenseForm.name = entry.name;
    annualExpenseForm.owner = entry.owner || '';
    annualExpenseForm.isRecurrent = entry.expenseType === 'recurrent';
    annualExpenseForm.timeProfile = entry.timeProfile;
    annualExpenseForm.cashflowRole = entry.cashflowRole;
    annualExpenseForm.eventGroup = entry.eventGroup || '';
    annualExpenseForm.targetMonth =
      entry.targetMonth == null ? '' : String(Number(entry.targetMonth));
    annualExpenseForm.termEndMonth =
      entry.termEndMonth == null ? '' : String(Number(entry.termEndMonth));
    annualExpenseForm.termEndYear =
      entry.termEndYear == null ? '' : String(Number(entry.termEndYear));
    annualExpenseForm.amountInputPeriod = entry.amountInputPeriod ?? 'annual';
    annualExpenseForm.amountAnnual = amountInputValueFromAnnual(
      entry.amountAnnual,
      annualExpenseForm.amountInputPeriod,
    );
    annualExpenseForm.currency = entry.currency;
    annualExpenseForm.notes = entry.notes || '';
    normalizeExpenseCashflowRoleForCurrentTimeProfile();
  } else {
    editingExpenseId.value = null;
    resetExpenseForm();
  }
  showExpenseModal.value = true;
  void nextTick(() => {
    hydratingAnnualExpenseForm.value = false;
  });
}

function closeIncomeModal(): void {
  showIncomeModal.value = false;
  editingIncomeId.value = null;
  resetIncomeForm();
}
function closeExpenseModal(): void {
  showExpenseModal.value = false;
  editingExpenseId.value = null;
  bulkEditingGeneratedLiabilityId.value = null;
  bulkEditingGeneratedExpenseIds.value = [];
  resetExpenseForm();
}

const incomeAmountInputPlaceholder = computed(() =>
  annualIncomeForm.amountInputPeriod === 'monthly' ? 'Importe mensual' : 'Importe anual',
);
const incomeModalTitle = computed(() =>
  editingIncomeId.value === null ? 'Nuevo ingreso anual' : 'Editar ingreso anual',
);
const incomeSubmitLabel = computed(() =>
  editingIncomeId.value === null ? 'Guardar ingreso' : 'Guardar cambios',
);
const expenseAmountInputPlaceholder = computed(() =>
  annualExpenseForm.amountInputPeriod === 'monthly' ? 'Importe mensual' : 'Importe anual',
);
const expenseModalTitle = computed(() =>
  editingExpenseId.value === null
    ? 'Nueva salida anual'
    : bulkEditingGeneratedLiabilityId.value != null
      ? 'Editar salida generada (todos los ejercicios)'
      : 'Editar salida anual',
);
const expenseSubmitLabel = computed(() =>
  editingExpenseId.value === null
    ? 'Guardar salida'
    : bulkEditingGeneratedLiabilityId.value != null
      ? 'Aplicar a todos'
      : 'Guardar cambios',
);
const editingSystemGeneratedLiabilityExpense = computed(() => {
  if (bulkEditingGeneratedLiabilityId.value != null) return true;
  if (editingExpenseId.value == null) return false;
  const entry = annualExpenseEntries.value.find((row) => row.id === editingExpenseId.value);
  return Boolean(entry?.isSystemGenerated && entry?.sourceLiabilityId != null);
});
const expenseBulkEditHint = computed(() =>
  bulkEditingGeneratedLiabilityId.value != null
    ? 'Se aplicará en todos los ejercicios de este pasivo. Se mantiene el importe y el año de cada ejercicio.'
    : 'Notas (opcional)',
);
const generatedLiabilityExpenseReviewTitle = computed(() =>
  generatedLiabilityExpenseReview.value
    ? `Gasto generado por pasivo: ${generatedLiabilityExpenseReview.value.liabilityName}`
    : 'Gasto generado por pasivo',
);

function setGeneratedLiabilityExpenseReview(
  liabilityId: number,
  liabilityName: string,
  entries: AnnualExpenseEntry[],
): void {
  generatedLiabilityExpenseReview.value = {
    liabilityId,
    liabilityName,
    entries: entries.map((entry) => ({
      id: entry.id,
      fiscalYear: entry.fiscalYear,
      name: entry.name,
      owner: entry.owner,
      category: entry.category,
      subcategory: entry.subcategory,
      expenseType: entry.expenseType,
      cashflowRole: entry.cashflowRole,
      timeProfile: entry.timeProfile,
      eventGroup: entry.eventGroup,
      targetMonth: entry.targetMonth,
      termEndMonth: entry.termEndMonth,
      termEndYear: entry.termEndYear,
      amountInputPeriod: entry.amountInputPeriod,
      amountAnnual: entry.amountAnnual,
      currency: entry.currency,
      notes: entry.notes,
    })),
  };
}

function summarizeGeneratedLiabilityExpenseChanges(
  beforeEntries: AnnualExpenseEntry[],
  afterEntries: AnnualExpenseEntry[],
): string | null {
  const toYearTotals = (rows: AnnualExpenseEntry[]) => {
    const totals = new Map<number, number>();
    for (const row of rows) {
      totals.set(row.fiscalYear, (totals.get(row.fiscalYear) ?? 0) + Number(row.amountAnnual ?? 0));
    }
    return totals;
  };
  const beforeTotals = toYearTotals(beforeEntries);
  const afterTotals = toYearTotals(afterEntries);
  const years = Array.from(new Set([...beforeTotals.keys(), ...afterTotals.keys()])).sort(
    (a, b) => a - b,
  );
  const changedYears: number[] = [];
  for (const year of years) {
    const before = beforeTotals.get(year) ?? 0;
    const after = afterTotals.get(year) ?? 0;
    if (Math.abs(before - after) > 0.009) changedYears.push(year);
  }
  const addedYears = years.filter(
    (year) => (beforeTotals.get(year) ?? 0) <= 0 && (afterTotals.get(year) ?? 0) > 0,
  );
  const removedYears = years.filter(
    (year) => (beforeTotals.get(year) ?? 0) > 0 && (afterTotals.get(year) ?? 0) <= 0,
  );
  if (!changedYears.length && !addedYears.length && !removedYears.length) return null;
  const chunks: string[] = [];
  if (changedYears.length) {
    chunks.push(`Importes actualizados en: ${changedYears.join(', ')}`);
  }
  if (addedYears.length) {
    chunks.push(`Nuevas anualidades: ${addedYears.join(', ')}`);
  }
  if (removedYears.length) {
    chunks.push(`Anualidades eliminadas: ${removedYears.join(', ')}`);
  }
  return chunks.join(' | ');
}

function closeGeneratedLiabilityExpenseModal(): void {
  showGeneratedLiabilityExpenseModal.value = false;
  generatedLiabilityExpenseReview.value = null;
  generatedLiabilityExpenseReviewChangeMessage.value = null;
}

function openGeneratedExpenseReviewEntryFromVisibleYear(): void {
  const review = generatedLiabilityExpenseReview.value;
  if (!review) return;
  const entry = annualExpenseEntries.value.find(
    (row) => row.sourceLiabilityId === review.liabilityId && row.isSystemGenerated,
  );
  if (!entry) return;
  closeGeneratedLiabilityExpenseModal();
  openExpenseModal(entry);
}

function openGeneratedExpenseBulkEdit(): void {
  const review = generatedLiabilityExpenseReview.value;
  if (!review?.entries.length) return;
  const first = review.entries[0]!;

  annualExpenseError.value = null;
  hydratingAnnualExpenseForm.value = true;
  editingExpenseId.value = first.id;
  bulkEditingGeneratedLiabilityId.value = review.liabilityId;
  bulkEditingGeneratedExpenseIds.value = review.entries.map((entry) => entry.id);
  annualExpenseForm.category = first.category as ExpenseCategoryKey;
  annualExpenseForm.subcategory = normalizeExpenseSubcategoryForUi(
    first.category,
    first.subcategory,
  );
  annualExpenseForm.name = first.name;
  annualExpenseForm.owner = first.owner || '';
  annualExpenseForm.isRecurrent = first.expenseType === 'recurrent';
  annualExpenseForm.timeProfile = first.timeProfile as ExpenseTimeProfile;
  annualExpenseForm.cashflowRole = first.cashflowRole as AnnualExpenseCashflowRole;
  annualExpenseForm.eventGroup = first.eventGroup || '';
  annualExpenseForm.targetMonth =
    first.targetMonth == null ? '' : String(Number(first.targetMonth));
  annualExpenseForm.termEndMonth =
    first.termEndMonth == null ? '' : String(Number(first.termEndMonth));
  annualExpenseForm.termEndYear =
    first.termEndYear == null ? '' : String(Number(first.termEndYear));
  annualExpenseForm.amountInputPeriod = first.amountInputPeriod ?? 'annual';
  annualExpenseForm.amountAnnual = amountInputValueFromAnnual(
    first.amountAnnual,
    annualExpenseForm.amountInputPeriod,
  );
  annualExpenseForm.currency = first.currency;
  annualExpenseForm.notes = first.notes || '';
  normalizeExpenseCashflowRoleForCurrentTimeProfile();
  showGeneratedLiabilityExpenseModal.value = false;
  showExpenseModal.value = true;
  void nextTick(() => {
    hydratingAnnualExpenseForm.value = false;
  });
}

async function submitLiabilityWithExpenseReview(
  payload: NetWorthWritePayload & { ownership_id?: number | null },
): Promise<void> {
  const createdLiability = await store.createLiability(payload);
  if (!createdLiability) return;

  showLiabilityModal.value = false;
  void loadAnnualExpense(fiscalYear.value);

  try {
    const generatedEntries = await listBySourceLiability(createdLiability.id);
    const systemGeneratedEntries = generatedEntries
      .filter((entry) => entry.isSystemGenerated && entry.sourceLiabilityId === createdLiability.id)
      .sort((a, b) => a.fiscalYear - b.fiscalYear);

    if (!systemGeneratedEntries.length) return;

    generatedLiabilityExpenseReviewChangeMessage.value = null;
    setGeneratedLiabilityExpenseReview(
      createdLiability.id,
      createdLiability.name,
      systemGeneratedEntries,
    );
    showGeneratedLiabilityExpenseModal.value = true;
  } catch (e: unknown) {
    annualExpenseError.value = `Pasivo creado, pero no se pudo cargar el gasto generado: ${toApiErrorMessage(e)}`;
  }
}

async function updateLiabilityAndShowExpenseReview(
  id: number,
  payload: NetWorthWritePayload & { ownership_id?: number | null },
): Promise<void> {
  const beforeEntries = await listBySourceLiability(id);
  await store.updateLiability(id, payload);
  await loadAnnualExpense(fiscalYear.value);
  const refreshedEntries = await listBySourceLiability(id);
  const systemGeneratedEntries = refreshedEntries
    .filter((entry) => entry.isSystemGenerated && entry.sourceLiabilityId === id)
    .sort((a, b) => a.fiscalYear - b.fiscalYear);
  if (!systemGeneratedEntries.length) return;

  const liabilityName = store.liabilities.find((item) => item.id === id)?.name ?? 'Pasivo';
  generatedLiabilityExpenseReviewChangeMessage.value = summarizeGeneratedLiabilityExpenseChanges(
    beforeEntries.filter((entry) => entry.isSystemGenerated && entry.sourceLiabilityId === id),
    systemGeneratedEntries,
  );
  setGeneratedLiabilityExpenseReview(id, liabilityName, systemGeneratedEntries);
  showGeneratedLiabilityExpenseModal.value = true;
}

async function submitEditWithExpenseReview(
  payload: NetWorthWritePayload & { ownership_id?: number | null },
): Promise<void> {
  const current = editItem.value;
  if (!current || !editKind.value) return;
  if (editKind.value === 'asset') {
    await submitEdit(payload);
    await loadAnnualExpense(fiscalYear.value);
    return;
  }
  await updateLiabilityAndShowExpenseReview(current.id, payload);
  closeEdit();
}

function parseLooseDecimal(raw: unknown): number | null {
  const normalized = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(',', '.');
  if (!normalized) return null;
  const value = Number(normalized);
  return Number.isFinite(value) ? value : null;
}

function roundToCents(value: number): number {
  return Math.round(value * 100) / 100;
}

const INTEREST_WITHHOLDING_RATE = 0.19;

function applyInterestWithholding(grossInterest: number): number {
  return roundToCents(grossInterest * (1 - INTEREST_WITHHOLDING_RATE));
}

function isRemuneratedLiquidityAsset(payload: AssetFormSubmitPayload): boolean {
  const category = String(payload.category ?? '').trim();
  const tae = parseLooseDecimal(payload.annual_interest_tae);
  return category === 'cash' && tae != null && tae > 0;
}

function estimateRemuneratedLiquidityInterest(payload: AssetFormSubmitPayload): number | null {
  const category = String(payload.category ?? '').trim();
  const subcategory = String(payload.subcategory ?? '').trim();
  const tae = parseLooseDecimal(payload.annual_interest_tae);
  if (tae == null || tae <= 0) return null;

  if (category === 'cash' && subcategory === 'short_term_deposit') {
    const principalAmount = parseLooseDecimal(payload.amount);
    const depositTermMonths = Number(payload.deposit_term_months ?? 0);
    if (
      principalAmount == null ||
      principalAmount <= 0 ||
      !Number.isInteger(depositTermMonths) ||
      depositTermMonths < 1 ||
      depositTermMonths > 12
    ) {
      return null;
    }
    return roundToCents((principalAmount * tae * depositTermMonths) / 1200);
  }

  const averageBalance = parseLooseDecimal(payload.estimated_average_balance_for_interest);
  if (averageBalance == null || averageBalance <= 0) return null;
  return roundToCents((averageBalance * tae) / 100);
}

function normalizeAmountForMatch(raw: unknown): string {
  const value = String(raw ?? '')
    .trim()
    .replace(/\s/g, '')
    .replace(',', '.');
  return value;
}

function findLikelyCreatedAsset(
  payload: AssetFormSubmitPayload,
  previousAssetIds: Set<number>,
): { id: number; name: string } | null {
  const targetName = String(payload.name ?? '').trim();
  const targetCategory = String(payload.category ?? '').trim();
  const targetSubcategory = String(payload.subcategory ?? '').trim();
  const targetCurrency = String(payload.currency ?? '')
    .trim()
    .toUpperCase();
  const targetStartDate = String(payload.start_date ?? '').trim();
  const targetAmount = normalizeAmountForMatch(payload.amount);

  const candidates = store.assets
    .filter((asset) => !previousAssetIds.has(asset.id))
    .filter((asset) => String(asset.name ?? '').trim() === targetName)
    .filter((asset) => String(asset.category ?? '').trim() === targetCategory)
    .filter((asset) => String(asset.subcategory ?? '').trim() === targetSubcategory)
    .filter(
      (asset) =>
        String(asset.currency ?? '')
          .trim()
          .toUpperCase() === targetCurrency,
    )
    .filter((asset) => String(asset.start_date ?? '').trim() === targetStartDate)
    .filter((asset) => normalizeAmountForMatch(asset.amount) === targetAmount)
    .sort((a, b) => b.id - a.id);

  const picked = candidates[0];
  return picked ? { id: picked.id, name: picked.name } : null;
}

async function submitAsset(payload: AssetFormSubmitPayload): Promise<void> {
  const previousAssetIds = new Set(store.assets.map((asset) => asset.id));
  const createdAsset = await store.createAsset(payload);
  const createdOrMatchedAsset = createdAsset ?? findLikelyCreatedAsset(payload, previousAssetIds);
  if (!createdOrMatchedAsset) return;

  showAssetModal.value = false;
  await loadAnnualExpense(fiscalYear.value);

  if (!isRemuneratedLiquidityAsset(payload)) return;
  const estimatedAnnualInterestGross = estimateRemuneratedLiquidityInterest(payload);
  const currency =
    String(payload.currency ?? '')
      .trim()
      .toUpperCase() || 'EUR';
  const assetName = String(createdOrMatchedAsset.name ?? '').trim() || 'Activo remunerado';
  if (estimatedAnnualInterestGross == null || estimatedAnnualInterestGross <= 0) return;
  const estimatedAnnualInterestNet = applyInterestWithholding(estimatedAnnualInterestGross);
  if (!(estimatedAnnualInterestNet > 0)) return;
  const estimatedWithholdingAmount = roundToCents(
    estimatedAnnualInterestGross - estimatedAnnualInterestNet,
  );
  const ownerLabel = annualOwnerLabelFromOwnershipId(payload.ownership_id);

  const result = await addIncomeEntry(
    {
      name: `Intereses estimados - ${assetName}`,
      category: 'passive_income',
      subcategory: 'interest_income',
      owner: ownerLabel,
      incomeType: 'recurrent',
      timeProfile: 'structural_recurrent',
      cashflowRole: 'operating',
      eventGroup: '',
      termEndMonth: null,
      termEndYear: null,
      amountAnnual: estimatedAnnualInterestNet.toFixed(2),
      fiscalYear: fiscalYear.value,
      currency,
      notes: `Generado automaticamente desde activo de liquidez remunerado (${assetName}). Interes bruto estimado: ${estimatedAnnualInterestGross.toFixed(2)} ${currency}. Retencion estimada (19%): ${estimatedWithholdingAmount.toFixed(2)} ${currency}. Interes neto estimado: ${estimatedAnnualInterestNet.toFixed(2)} ${currency}.`,
    },
    fiscalYear.value,
  );
  if (!result.ok) {
    annualIncomeError.value = `Activo creado, pero no se pudo generar el ingreso anual estimado: ${result.error}`;
  }
}

async function updateAssetAndReloadExpenses(
  id: number,
  payload: NetWorthWritePayload & { ownership_id?: number | null },
): Promise<void> {
  await store.updateAsset(id, payload);
  await loadAnnualExpense(fiscalYear.value);
}

async function deleteAssetAndReloadExpenses(id: number): Promise<void> {
  await store.deleteAsset(id);
  await loadAnnualExpense(fiscalYear.value);
}

async function deleteLiabilityAndReloadExpenses(id: number): Promise<void> {
  await store.deleteLiability(id);
  await loadAnnualExpense(fiscalYear.value);
  if (generatedLiabilityExpenseReview.value?.liabilityId === id) {
    closeGeneratedLiabilityExpenseModal();
  }
}

watch(
  () => annualIncomeForm.isRecurrent,
  (isRecurrent) => {
    if (!isRecurrent) annualIncomeForm.amountInputPeriod = 'annual';
    if (!isRecurrent) annualIncomeForm.timeProfile = 'one_off';
    else if (annualIncomeForm.timeProfile === 'one_off')
      annualIncomeForm.timeProfile = 'structural_recurrent';
  },
);
watch(
  () => annualExpenseForm.isRecurrent,
  (isRecurrent) => {
    if (!isRecurrent) annualExpenseForm.amountInputPeriod = 'annual';
    if (!isRecurrent) annualExpenseForm.timeProfile = 'one_off';
    else if (annualExpenseForm.timeProfile === 'one_off')
      annualExpenseForm.timeProfile = 'structural_recurrent';
  },
);
watch(
  () => annualIncomeForm.timeProfile,
  (timeProfile) => {
    annualIncomeForm.isRecurrent = timeProfile !== 'one_off';
    if (timeProfile !== 'term_recurrent') annualIncomeForm.termEndMonth = '';
    if (timeProfile !== 'term_recurrent') annualIncomeForm.termEndYear = '';
    if (timeProfile !== 'one_off') annualIncomeForm.targetMonth = '';
  },
);
watch(
  () => annualExpenseForm.timeProfile,
  (timeProfile) => {
    annualExpenseForm.isRecurrent = timeProfile !== 'one_off';
    if (timeProfile !== 'term_recurrent') annualExpenseForm.termEndMonth = '';
    if (timeProfile !== 'term_recurrent') annualExpenseForm.termEndYear = '';
    if (timeProfile !== 'one_off') annualExpenseForm.targetMonth = '';
    normalizeExpenseCashflowRoleForCurrentTimeProfile();
  },
);
watch([() => annualIncomeForm.category], () => {
  if (hydratingAnnualIncomeForm.value) return;
  if (annualIncomeForm.category === 'capital_gains') {
    annualIncomeForm.timeProfile = 'one_off';
  }
  annualIncomeForm.cashflowRole = defaultIncomeCashflowRole(annualIncomeForm.category);
});
watch([() => annualExpenseForm.category, () => annualExpenseForm.subcategory], () => {
  if (hydratingAnnualExpenseForm.value) return;
  annualExpenseForm.cashflowRole = defaultExpenseCashflowRole(
    annualExpenseForm.category,
    annualExpenseForm.subcategory,
  );
  normalizeExpenseCashflowRoleForCurrentTimeProfile();
});

async function submitAnnualIncome(): Promise<void> {
  const rawAmount = Number(String(annualIncomeForm.amountAnnual).replace(',', '.'));
  const normalizedAmount = Number.isFinite(rawAmount)
    ? annualIncomeForm.amountInputPeriod === 'monthly'
      ? Math.round(rawAmount * 12 * 100) / 100
      : rawAmount
    : annualIncomeForm.amountAnnual;

  const draft = {
    name: annualIncomeForm.name,
    category: annualIncomeForm.category,
    subcategory: annualIncomeForm.subcategory,
    owner: annualIncomeForm.owner,
    incomeType: (annualIncomeForm.isRecurrent ? 'recurrent' : 'one_off') as 'recurrent' | 'one_off',
    timeProfile: annualIncomeForm.timeProfile,
    cashflowRole: defaultIncomeCashflowRole(annualIncomeForm.category),
    eventGroup: annualIncomeForm.eventGroup,
    targetMonth:
      annualIncomeForm.timeProfile === 'one_off' && String(annualIncomeForm.targetMonth).trim()
        ? Number(annualIncomeForm.targetMonth)
        : null,
    termEndMonth:
      annualIncomeForm.timeProfile === 'term_recurrent' &&
      String(annualIncomeForm.termEndMonth).trim()
        ? Number(annualIncomeForm.termEndMonth)
        : null,
    termEndYear:
      annualIncomeForm.timeProfile === 'term_recurrent' &&
      String(annualIncomeForm.termEndYear).trim()
        ? Number(annualIncomeForm.termEndYear)
        : null,
    amountInputPeriod: annualIncomeForm.amountInputPeriod,
    amountAnnual: String(normalizedAmount),
    fiscalYear: fiscalYear.value,
    currency: annualIncomeForm.currency,
    notes: annualIncomeForm.notes,
  };
  const result =
    editingIncomeId.value === null
      ? await addIncomeEntry(draft, fiscalYear.value)
      : await updateIncomeEntry(editingIncomeId.value, draft, fiscalYear.value);
  if (!result.ok) {
    annualIncomeError.value = result.error;
    return;
  }
  annualIncomeError.value = null;
  closeIncomeModal();
  resetIncomeForm();
}

async function removeAnnualIncome(id: number): Promise<void> {
  await deleteIncomeEntry(id, fiscalYear.value);
}

async function submitAnnualExpense(): Promise<void> {
  normalizeExpenseCashflowRoleForCurrentTimeProfile();
  const rawAmount = Number(String(annualExpenseForm.amountAnnual).replace(',', '.'));
  const normalizedAmount = Number.isFinite(rawAmount)
    ? annualExpenseForm.amountInputPeriod === 'monthly'
      ? Math.round(rawAmount * 12 * 100) / 100
      : rawAmount
    : annualExpenseForm.amountAnnual;

  const draft = {
    name: annualExpenseForm.name,
    category: annualExpenseForm.category,
    subcategory: annualExpenseForm.subcategory,
    owner: annualExpenseForm.owner,
    expenseType: (annualExpenseForm.isRecurrent ? 'recurrent' : 'one_off') as
      | 'recurrent'
      | 'one_off',
    timeProfile: annualExpenseForm.timeProfile,
    cashflowRole: annualExpenseForm.cashflowRole,
    eventGroup: annualExpenseForm.eventGroup,
    targetMonth:
      annualExpenseForm.timeProfile === 'one_off' && String(annualExpenseForm.targetMonth).trim()
        ? Number(annualExpenseForm.targetMonth)
        : null,
    termEndYear:
      annualExpenseForm.timeProfile === 'term_recurrent' &&
      String(annualExpenseForm.termEndYear).trim()
        ? Number(annualExpenseForm.termEndYear)
        : null,
    termEndMonth:
      annualExpenseForm.timeProfile === 'term_recurrent' &&
      String(annualExpenseForm.termEndMonth).trim()
        ? Number(annualExpenseForm.termEndMonth)
        : null,
    amountInputPeriod: annualExpenseForm.amountInputPeriod,
    amountAnnual: String(normalizedAmount),
    fiscalYear: fiscalYear.value,
    currency: annualExpenseForm.currency,
    notes: annualExpenseForm.notes,
  };

  if (
    bulkEditingGeneratedLiabilityId.value != null &&
    bulkEditingGeneratedExpenseIds.value.length
  ) {
    try {
      for (const id of bulkEditingGeneratedExpenseIds.value) {
        await coreApi.patch(`/api/budget/annual-expense/${id}/`, {
          name: draft.name,
          category: draft.category,
          subcategory: draft.subcategory,
          owner_name: draft.owner,
          expense_type: draft.expenseType,
          time_profile: draft.timeProfile,
          cashflow_role: draft.cashflowRole,
          event_group: draft.eventGroup,
          target_month: draft.targetMonth,
          term_end_month: draft.termEndMonth,
          term_end_year: draft.termEndYear,
          amount_input_period: draft.amountInputPeriod,
          notes: draft.notes,
        });
      }

      await loadAnnualExpense(fiscalYear.value);
      if (
        generatedLiabilityExpenseReview.value?.liabilityId === bulkEditingGeneratedLiabilityId.value
      ) {
        const refreshedEntries = await listBySourceLiability(
          generatedLiabilityExpenseReview.value.liabilityId,
        );
        const systemGeneratedEntries = refreshedEntries
          .filter(
            (entry) =>
              entry.isSystemGenerated &&
              entry.sourceLiabilityId === generatedLiabilityExpenseReview.value?.liabilityId,
          )
          .sort((a, b) => a.fiscalYear - b.fiscalYear);
        setGeneratedLiabilityExpenseReview(
          generatedLiabilityExpenseReview.value.liabilityId,
          generatedLiabilityExpenseReview.value.liabilityName,
          systemGeneratedEntries,
        );
      }
      annualExpenseError.value = null;
      closeExpenseModal();
      resetExpenseForm();
      showGeneratedLiabilityExpenseModal.value = true;
      return;
    } catch (e: unknown) {
      annualExpenseError.value = toApiErrorMessage(e);
      return;
    }
  }

  const result =
    editingExpenseId.value === null
      ? await addExpenseEntry(draft, fiscalYear.value)
      : await updateExpenseEntry(editingExpenseId.value, draft, fiscalYear.value);
  if (!result.ok) {
    annualExpenseError.value = result.error;
    return;
  }
  annualExpenseError.value = null;
  closeExpenseModal();
  resetExpenseForm();
}
async function removeAnnualExpense(id: number): Promise<void> {
  await deleteExpenseEntry(id, fiscalYear.value);
}

const dataTransferBusy = ref(false);
const dataTransferBusyLabel = ref<string | null>(null);
const dataTransferStatus = ref<string | null>(null);
const dataTransferError = ref<string | null>(null);
const dataTransferToastMessage = ref<string | null>(null);
const dataTransferToastKind = ref<'success' | 'error'>('success');
const importFileInputRef = ref<HTMLInputElement | null>(null);
const pendingImportMode = ref<ImportMode>('append');
const portableDataAppVersion = ref<string | null>(null);
let dataTransferToastTimer: number | null = null;

type PortableDataMeta = { app_version: string };
type PortableImportResponse = {
  ok: boolean;
  mode: ImportMode;
  meta: {
    schema_version: number;
    source_app: 'core' | 'saas';
    exported_at: string;
    exported_app_version?: string;
    imported_into_app_version: string;
  };
  counts: {
    annual_income: number;
    annual_expense: number;
    assets: number;
    liabilities: number;
    snapshots: number;
    family_members: number;
    ownerships: number;
    ownership_links: number;
  };
};

const dataTransferUiBusy = computed(
  () =>
    dataTransferBusy.value ||
    store.loading ||
    annualIncomeLoading.value ||
    annualExpenseLoading.value,
);

function clearDataTransferFeedback(): void {
  dataTransferStatus.value = null;
  dataTransferError.value = null;
}

function clearDataTransferToast(): void {
  if (dataTransferToastTimer != null) {
    window.clearTimeout(dataTransferToastTimer);
    dataTransferToastTimer = null;
  }
  dataTransferToastMessage.value = null;
}

function showDataTransferToast(message: string, kind: 'success' | 'error' = 'success'): void {
  clearDataTransferToast();
  dataTransferToastKind.value = kind;
  dataTransferToastMessage.value = message;
  dataTransferToastTimer = window.setTimeout(() => {
    dataTransferToastMessage.value = null;
    dataTransferToastTimer = null;
  }, 5000);
}

function triggerImportDialog(mode: ImportMode = 'append'): void {
  clearDataTransferFeedback();
  pendingImportMode.value = mode;
  importFileInputRef.value?.click();
}

async function ensurePortableDataAppVersion(): Promise<string> {
  if (portableDataAppVersion.value) return portableDataAppVersion.value;
  const response = await coreApi.get<PortableDataMeta>('/api/core/portable-data/meta/');
  portableDataAppVersion.value = response.data.app_version;
  return portableDataAppVersion.value;
}

async function exportDataBundle(): Promise<void> {
  clearDataTransferFeedback();
  dataTransferBusyLabel.value = 'Exportando datos...';
  dataTransferBusy.value = true;
  try {
    const appVersion = await ensurePortableDataAppVersion();
    const [
      incomeRes,
      expenseRes,
      assetsRes,
      liabilitiesRes,
      snapshotsRes,
      settingsRes,
      membersRes,
      ownershipsRes,
      linksRes,
    ] = await Promise.all([
      coreApi.get<PortableAnnualIncomeRecord[]>('/api/budget/annual-income/'),
      coreApi.get<PortableAnnualExpenseRecord[]>('/api/budget/annual-expense/'),
      coreApi.get<PortableAssetRecord[]>('/api/net-worth/assets/'),
      coreApi.get<PortableLiabilityRecord[]>('/api/net-worth/liabilities/'),
      coreApi.get<PortableSnapshotRecord[]>('/api/net-worth/snapshots/'),
      coreApi.get<PortableSettingsRecord>('/api/auth/settings/'),
      api.get<PortableFamilyMemberRecord[]>('/api/family-members/'),
      api.get<PortableOwnershipRecord[]>('/api/ownerships/'),
      api.get<PortableOwnershipLinkRecord[]>('/api/ownership-links/'),
    ]);

    const payload: PortableDataBundle = {
      schema_version: 1,
      exported_at: new Date().toISOString(),
      source_app: 'core',
      exported_app_version: appVersion,
      settings: settingsRes.data ?? undefined,
      data: {
        annual_income: (incomeRes.data ?? []).map(toPortableAnnualIncomeRecord),
        annual_expense: (expenseRes.data ?? []).map(toPortableAnnualExpenseRecord),
        assets: (assetsRes.data ?? []).map((row) => toPortableAssetRecord(row)),
        liabilities: (liabilitiesRes.data ?? []).map((row) => toPortableLiabilityRecord(row)),
        snapshots: (snapshotsRes.data ?? []).slice(),
      },
      premium: {
        family_members: (membersRes.data ?? []).slice(),
        ownerships: (ownershipsRes.data ?? []).map((row) => toPortableOwnershipRecord(row)),
        ownership_links: (linksRes.data ?? []).slice(),
      },
    };

    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = buildPortableFilename();
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);

    dataTransferStatus.value = `Exportacion completada: ${payload.data.annual_income.length} ingresos, ${payload.data.annual_expense.length} gastos, ${payload.data.assets.length} activos, ${payload.data.liabilities.length} pasivos, ${payload.data.snapshots?.length ?? 0} snapshots, ${payload.premium?.family_members.length ?? 0} miembros y ${payload.premium?.ownerships.length ?? 0} titularidades.`;
  } catch (e: unknown) {
    dataTransferError.value = `No se pudo exportar: ${toApiErrorMessage(e)}`;
  } finally {
    dataTransferBusy.value = false;
    dataTransferBusyLabel.value = null;
  }
}

function setDataImportBusyState(importMode: 'append' | 'replace') {
  dataTransferBusyLabel.value =
    importMode === 'replace'
      ? 'Reemplazando datos... Esto puede tardar unos segundos.'
      : 'Importando datos...';
  dataTransferBusy.value = true;
}

async function refreshImportedDataViews(): Promise<void> {
  await Promise.all([
    store.refreshAll(),
    loadAnnualIncome(fiscalYear.value),
    loadAnnualExpense(fiscalYear.value),
  ]);
}

function buildImportCompletionStatus(params: {
  importMode: 'append' | 'replace';
  response: PortableImportResponse;
}): string {
  const { importMode, response } = params;
  const counts = response.counts;
  return importMode === 'replace'
    ? `Reemplazo completado: ${counts.annual_income} ingresos, ${counts.annual_expense} gastos, ${counts.assets} activos, ${counts.liabilities} pasivos, ${counts.snapshots} snapshots, ${counts.family_members} miembros, ${counts.ownerships} titularidades y ${counts.ownership_links} enlaces de titularidad.`
    : `Importacion completada: ${counts.annual_income} ingresos, ${counts.annual_expense} gastos, ${counts.assets} activos, ${counts.liabilities} pasivos, ${counts.snapshots} snapshots, ${counts.family_members} miembros, ${counts.ownerships} titularidades y ${counts.ownership_links} enlaces de titularidad.`;
}

async function importDataFromFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement | null;
  const file = input?.files?.[0];
  if (!file) return;

  clearDataTransferFeedback();

  try {
    const appVersion = await ensurePortableDataAppVersion();
    const content = await file.text();
    const bundle = parsePortableDataBundle(content);
    const importMode = pendingImportMode.value;

    const proceed = window.confirm(buildImportPreviewMessage(bundle, importMode, appVersion));
    if (!proceed) return;

    setDataImportBusyState(importMode);

    const response = await coreApi.post<PortableImportResponse>('/api/core/portable-data/import/', {
      mode: importMode,
      bundle,
    });
    await refreshImportedDataViews();

    dataTransferStatus.value = buildImportCompletionStatus({
      importMode,
      response: response.data,
    });
  } catch (e: unknown) {
    dataTransferError.value = `No se pudo importar: ${toApiErrorMessage(e)}`;
  } finally {
    dataTransferBusy.value = false;
    dataTransferBusyLabel.value = null;
    if (input) input.value = '';
  }
}

watch(dataTransferStatus, (message) => {
  if (message) showDataTransferToast(message, 'success');
});

watch(dataTransferError, (message) => {
  if (message) showDataTransferToast(message, 'error');
});

onBeforeUnmount(() => {
  clearDataTransferToast();
});

watch(
  fiscalYear,
  (year) => {
    loadAnnualIncome(year);
    loadAnnualExpense(year);
  },
  { immediate: true },
);
</script>

<template>
  <div class="container ui-pro-page">
    <section class="card ui-pro-panel grid gap-2.5">
      <p class="ui-pro-kicker">Introduccion de datos</p>
      <h1 class="h1 m-0">{{ dataInputCheckTitle }}</h1>
      <p class="subtle m-0">
        {{ dataInputSummary }}
      </p>
      <p class="subtle m-0">
        Gestiona aqui la base financiera anual: ingresos, gastos, activos y pasivos para el analisis
        patrimonial.
      </p>
      <div class="actions m-0">
        <button
          class="btn btn-ghost"
          type="button"
          :disabled="dataTransferUiBusy"
          @click="exportDataBundle"
        >
          Exportar datos
        </button>
        <button
          class="btn btn-primary"
          type="button"
          :disabled="dataTransferUiBusy"
          @click="triggerImportDialog('append')"
        >
          Importar datos
        </button>
        <button
          class="btn btn-ghost"
          type="button"
          :disabled="dataTransferUiBusy"
          @click="triggerImportDialog('replace')"
        >
          Reemplazar datos
        </button>
        <input
          ref="importFileInputRef"
          type="file"
          accept="application/json,.json"
          class="sr-only"
          @change="importDataFromFile"
        />
      </div>
      <p v-if="dataTransferStatus" class="subtle m-0">{{ dataTransferStatus }}</p>
      <p v-if="dataTransferError" class="alert m-0">{{ dataTransferError }}</p>
    </section>

    <Transition
      enter-active-class="transition duration-200 ease-out"
      enter-from-class="-translate-y-2 opacity-0"
      enter-to-class="translate-y-0 opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="translate-y-0 opacity-100"
      leave-to-class="-translate-y-2 opacity-0"
    >
      <div
        v-if="dataTransferToastMessage"
        class="fixed right-4 top-4 z-[80] max-w-[min(92vw,560px)] rounded-xl px-4 py-3 text-sm shadow-2xl backdrop-blur"
        :class="
          dataTransferToastKind === 'error'
            ? 'border border-rose-300/30 bg-rose-950/90 text-rose-100'
            : 'border border-emerald-300/30 bg-emerald-950/90 text-emerald-100'
        "
        role="status"
        aria-live="polite"
      >
        <div class="flex items-start gap-2.5">
          <span
            class="mt-0.5 inline-block h-2.5 w-2.5 rounded-full"
            :class="dataTransferToastKind === 'error' ? 'bg-rose-300' : 'bg-emerald-300'"
          />
          <span>{{ dataTransferToastMessage }}</span>
        </div>
      </div>
    </Transition>

    <div
      v-if="dataTransferBusy"
      class="fixed inset-0 z-[70] flex items-center justify-center bg-black/45 px-4 backdrop-blur-[2px]"
      role="status"
      aria-live="polite"
      aria-busy="true"
    >
      <div class="w-full max-w-md rounded-2xl border border-white/15 bg-[#111827f2] p-4 shadow-2xl">
        <div class="flex items-center gap-3">
          <span
            class="inline-block h-5 w-5 animate-spin rounded-full border-2 border-white/30 border-t-teal-300"
            aria-hidden="true"
          />
          <div>
            <p class="m-0 text-sm font-medium text-white">
              {{ dataTransferBusyLabel ?? 'Procesando datos...' }}
            </p>
            <p class="m-0 text-xs text-white/65">No cierres la pestaña hasta que termine.</p>
          </div>
        </div>
      </div>
    </div>

    <div class="grid-2">
      <section class="section ui-flow-air md:col-span-2">
        <div class="nw-list-header ui-flow-air-header">
          <div class="nw-list-header-left ui-flow-air-left">
            <h2 class="ui-flow-air-title">Balance anual</h2>
            <div class="ui-flow-air-meta">
              <span class="ui-flow-air-subtitle">Ingresos y gastos</span>
              <select
                id="fiscal-year-income-expense"
                v-model.number="fiscalYear"
                class="select nw-select-sm ui-flow-air-year-select"
                aria-label="Ejercicio"
              >
                <option v-for="year in fiscalYearOptions" :key="year" :value="year">
                  {{ year }}
                </option>
              </select>
              <select
                id="visibility-filter-mode"
                v-model="visibilityFilterMode"
                class="select nw-select-sm ui-flow-air-year-select"
                aria-label="Filtro de visibilidad"
              >
                <option value="active">Solo activos</option>
                <option value="archived">Solo archivados</option>
                <option value="all">Todos</option>
              </select>
              <select
                id="ownership-filter-mode"
                v-model="globalOwnershipFilter"
                class="select nw-select-sm ui-flow-air-year-select"
                aria-label="Filtro de ownership"
              >
                <option value="all">Todos los miembros</option>
                <option value="unassigned">Sin asignar</option>
                <option
                  v-for="option in globalOwnershipFilterOptions"
                  :key="`global-owner-${option.id}`"
                  :value="option.id"
                >
                  {{ option.label }}
                </option>
              </select>
            </div>
          </div>
          <div class="nw-list-header-right ui-flow-air-right">
            <div class="nw-list-total-inline ui-flow-air-total">
              {{ formatMoneyAmount(annualBalanceTotal, 'EUR') }}
            </div>
            <div class="nw-list-total-details">Balance del ejercicio {{ fiscalYear }}</div>
          </div>
        </div>
      </section>

      <article class="card ui-pro-panel">
        <div class="nw-list-header">
          <div class="nw-list-header-left">
            <h2 class="card-header-title mt-0">Entradas anuales</h2>
          </div>
          <div class="nw-list-header-right">
            <div class="nw-list-total-inline">
              {{ formatMoneyAmount(filteredAnnualIncomeTotal, 'EUR') }}
            </div>
            <button
              class="btn btn-primary btn-sm nw-list-add-icon-only"
              type="button"
              aria-label="Anadir ingreso"
              :disabled="annualIncomeLoading"
              @click="() => openIncomeModal()"
            >
              <span class="btn-icon">+</span>
            </button>
          </div>
        </div>

        <div class="nw-list-header-totals">
          <div class="nw-list-total-details">Total anual</div>
        </div>

        <div v-if="annualIncomeError" class="alert mt-3">{{ annualIncomeError }}</div>
        <div v-else-if="annualIncomeApiError" class="alert mt-3">{{ annualIncomeApiError }}</div>

        <div v-if="!annualIncomeEntries.length && !annualIncomeLoading" class="subtle mt-3">
          No hay ingresos anuales todavia.
        </div>

        <div
          v-else-if="!filteredAnnualIncomeEntries.length && !annualIncomeLoading"
          class="subtle mt-3"
        >
          No hay ingresos con este filtro.
        </div>

        <div v-else class="mt-3 grid gap-4">
          <section
            v-for="group in annualIncomeGroups"
            :key="group.category"
            class="nw-cat-block"
            :class="incomeCategoryClass(group.category)"
          >
            <div class="nw-cat-header">
              <div class="nw-cat-left">
                <div>{{ group.label }}</div>
                <span class="badge">{{ group.entries.length }}</span>
              </div>
              <div class="nw-cat-right">
                <div class="nw-cat-total">
                  <div class="nw-cat-total-primary">
                    {{ formatTotalsLine(group.totals) }}
                    <span v-if="incomeCategoryPercent(group.entries)" class="nw-cat-percent">
                      . {{ incomeCategoryPercent(group.entries) }}%
                    </span>
                  </div>
                </div>
                <button
                  class="icon-btn nw-cat-toggle"
                  type="button"
                  :aria-label="
                    isIncomeGroupExpanded(group.category) ? 'Ocultar desglose' : 'Mostrar desglose'
                  "
                  :title="
                    isIncomeGroupExpanded(group.category) ? 'Ocultar desglose' : 'Mostrar desglose'
                  "
                  @click="toggleIncomeCategory(group.category)"
                >
                  <span v-if="isIncomeGroupExpanded(group.category)" class="icon" aria-hidden="true"
                    >&#9662;</span
                  >
                  <span v-else class="icon" aria-hidden="true">&#9656;</span>
                </button>
              </div>
            </div>

            <div v-if="isIncomeGroupExpanded(group.category)" class="subcat-list">
              <div
                v-for="subgroup in group.subgroups"
                :key="`${group.category}:${subgroup.subcategory}`"
                class="nw-subcat-block"
              >
                <div class="nw-subcat-header">
                  <div class="nw-subcat-title">{{ subgroup.label }}</div>
                  <div class="nw-subcat-total">
                    <div class="nw-subcat-total-primary">
                      {{ formatTotalsLine(subgroup.totals) }}
                    </div>
                  </div>
                  <div class="nw-subcat-actions-spacer" aria-hidden="true"></div>
                </div>

                <ul class="list list-plain nw-subcat-items">
                  <li v-for="entry in subgroup.entries" :key="entry.id">
                    <div class="nw-item-row income-item-row">
                      <div class="nw-item-main">
                        <div class="nw-item-name income-item-name">
                          <span
                            class="income-rec-dot"
                            :class="timeProfileDotClass(entry.timeProfile)"
                            aria-hidden="true"
                          ></span>
                          <span class="item-name-text">{{ entry.name }}</span>
                          <span v-if="entry.owner" class="badge">{{ entry.owner }}</span>
                        </div>
                        <div class="nw-item-submeta">
                          {{ timeProfileLabel(entry.timeProfile) }}
                          <template v-if="entry.eventGroup">
                            . Evento {{ eventGroupLabel(entry.eventGroup) }}</template
                          >
                        </div>
                      </div>
                      <div class="nw-item-amount">
                        {{ formatMoneyAmount(entry.amountAnnual, entry.currency) }}
                      </div>
                      <div class="nw-item-actions">
                        <button
                          class="icon-btn"
                          title="Editar"
                          :disabled="annualIncomeLoading"
                          @click="() => openIncomeModal(entry)"
                        >
                          &#9998;
                        </button>
                        <button
                          class="icon-btn"
                          title="Eliminar"
                          :disabled="annualIncomeLoading"
                          @click="removeAnnualIncome(entry.id)"
                        >
                          &#128465;
                        </button>
                      </div>
                    </div>
                  </li>
                </ul>
              </div>
            </div>
          </section>
        </div>

        <div v-if="annualIncomeLoading" class="ui-status-line mt-2">
          Cargando ingresos anuales...
        </div>
      </article>

      <article class="card ui-pro-panel">
        <div class="nw-list-header">
          <div class="nw-list-header-left">
            <h2 class="card-header-title mt-0">Salidas anuales</h2>
          </div>
          <div class="nw-list-header-right">
            <div class="nw-list-total-inline">
              {{ formatMoneyAmount(filteredAnnualExpenseTotal, 'EUR') }}
            </div>
            <button
              class="btn btn-primary btn-sm nw-list-add-icon-only"
              type="button"
              aria-label="Anadir salida"
              :disabled="annualExpenseLoading"
              @click="() => openExpenseModal()"
            >
              <span class="btn-icon">+</span>
            </button>
          </div>
        </div>
        <div class="nw-list-header-totals">
          <div class="nw-list-total-details">Total anual</div>
        </div>
        <div v-if="annualExpenseError" class="alert mt-3">{{ annualExpenseError }}</div>
        <div v-else-if="annualExpenseApiError" class="alert mt-3">{{ annualExpenseApiError }}</div>

        <div v-if="!annualExpenseEntries.length && !annualExpenseLoading" class="subtle mt-3">
          No hay salidas anuales todavia.
        </div>
        <div
          v-else-if="!filteredAnnualExpenseEntries.length && !annualExpenseLoading"
          class="subtle mt-3"
        >
          No hay salidas con este filtro.
        </div>

        <div v-else class="mt-3 grid gap-4">
          <section
            v-for="group in annualExpenseGroups"
            :key="group.category"
            class="nw-cat-block"
            :class="expenseCategoryClass(group.category)"
          >
            <div class="nw-cat-header">
              <div class="nw-cat-left">
                <div>{{ group.label }}</div>
                <span class="badge">{{ group.entries.length }}</span>
              </div>
              <div class="nw-cat-right">
                <div class="nw-cat-total">
                  <div class="nw-cat-total-primary">
                    {{ formatTotalsLine(group.totals) }}
                    <span v-if="expenseCategoryPercent(group.entries)" class="nw-cat-percent">
                      . {{ expenseCategoryPercent(group.entries) }}%
                    </span>
                  </div>
                </div>
                <button
                  class="icon-btn nw-cat-toggle"
                  type="button"
                  :aria-label="
                    isExpenseGroupExpanded(group.category) ? 'Ocultar desglose' : 'Mostrar desglose'
                  "
                  :title="
                    isExpenseGroupExpanded(group.category) ? 'Ocultar desglose' : 'Mostrar desglose'
                  "
                  @click="toggleExpenseCategory(group.category)"
                >
                  <span
                    v-if="isExpenseGroupExpanded(group.category)"
                    class="icon"
                    aria-hidden="true"
                    >&#9662;</span
                  >
                  <span v-else class="icon" aria-hidden="true">&#9656;</span>
                </button>
              </div>
            </div>

            <div v-if="isExpenseGroupExpanded(group.category)" class="subcat-list">
              <div
                v-for="subgroup in group.subgroups"
                :key="`${group.category}:${subgroup.subcategory}`"
                class="nw-subcat-block"
              >
                <div class="nw-subcat-header">
                  <div class="nw-subcat-title">{{ subgroup.label }}</div>
                  <div class="nw-subcat-total">
                    <div class="nw-subcat-total-primary">
                      {{ formatTotalsLine(subgroup.totals) }}
                    </div>
                  </div>
                  <div class="nw-subcat-actions-spacer" aria-hidden="true"></div>
                </div>

                <ul class="list list-plain nw-subcat-items">
                  <li v-for="entry in subgroup.entries" :key="entry.id">
                    <div class="nw-item-row income-item-row">
                      <div class="nw-item-main">
                        <div class="nw-item-name income-item-name">
                          <span
                            class="income-rec-dot"
                            :class="timeProfileDotClass(entry.timeProfile)"
                            aria-hidden="true"
                          ></span>
                          <span class="item-name-text">{{ entry.name }}</span>
                          <span v-if="entry.owner" class="badge">{{ entry.owner }}</span>
                        </div>
                        <div class="nw-item-submeta">
                          {{ timeProfileLabel(entry.timeProfile) }} .
                          <template
                            v-if="
                              !shouldHideExpenseCashflowRoleLabel({
                                timeProfile: entry.timeProfile,
                                cashflowRole: entry.cashflowRole,
                              })
                            "
                          >
                            {{ expenseCashflowRoleLabel(entry.cashflowRole) }}
                          </template>
                          <template v-if="entry.eventGroup">
                            . Evento {{ eventGroupLabel(entry.eventGroup) }}</template
                          >
                          <template
                            v-if="formatTermEndLabel(entry.termEndYear, entry.termEndMonth)"
                          >
                            .
                            {{
                              formatTermEndLabel(entry.termEndYear, entry.termEndMonth)
                            }}</template
                          >
                        </div>
                      </div>
                      <div class="nw-item-amount">
                        {{ formatMoneyAmount(entry.amountAnnual, entry.currency) }}
                      </div>
                      <div class="nw-item-actions">
                        <button
                          class="icon-btn"
                          title="Editar"
                          :disabled="annualExpenseLoading"
                          @click="() => openExpenseModal(entry)"
                        >
                          &#9998;
                        </button>
                        <button
                          class="icon-btn"
                          title="Eliminar"
                          :disabled="annualExpenseLoading"
                          @click="removeAnnualExpense(entry.id)"
                        >
                          &#128465;
                        </button>
                      </div>
                    </div>
                  </li>
                </ul>
              </div>
            </div>
          </section>
        </div>

        <div v-if="annualExpenseLoading" class="ui-status-line mt-2">
          Cargando salidas anuales...
        </div>
      </article>
    </div>

    <div v-if="store.error" class="alert mt-3">
      {{ prettyError() }}
    </div>

    <section class="section ui-balance-air">
      <div class="nw-list-header ui-balance-air-header">
        <div class="nw-list-header-left ui-balance-air-left">
          <h2 class="ui-balance-air-title">Balance patrimonial</h2>
          <span class="ui-balance-air-subtitle">Activos y pasivos</span>
        </div>
        <div class="nw-list-header-right ui-balance-air-right">
          <div class="nw-list-total-inline ui-balance-air-total">
            {{ formatMoneyAmount(netAssetsBase, netAssetsCurrency) }}
          </div>
          <div class="nw-list-total-details">Neto (activos - pasivos)</div>
        </div>
      </div>
    </section>

    <div class="grid-2">
      <ItemList
        v-model:ownership-filter-value="assetOwnershipFilter"
        title="Activos"
        :items="visibleAssets"
        :show-archived="visibilityFilterMode !== 'active'"
        :show-ownership-filter="false"
        :categories="assetCategories"
        :subcategories="assetSubcategories"
        :base-currency="store.baseCurrency ?? store.summary?.base_currency ?? 'EUR'"
        :category-totals-base="store.summary?.assets_by_category ?? {}"
        :subcategory-totals-base="store.summary?.assets_by_subcategory ?? {}"
        :total-base="store.summary?.total_assets ?? '0'"
        v-bind="itemListProps"
        :on-update="updateAssetAndReloadExpenses"
        :on-archive="store.archiveAsset"
        :on-delete="deleteAssetAndReloadExpenses"
        :on-add="() => (showAssetModal = true)"
        :on-edit="(it) => openEdit(it, 'asset')"
      />

      <ItemList
        v-model:ownership-filter-value="liabilityOwnershipFilter"
        title="Pasivos"
        :items="visibleLiabilities"
        :show-archived="visibilityFilterMode !== 'active'"
        :show-ownership-filter="false"
        :categories="liabilityCategories"
        :base-currency="store.baseCurrency ?? store.summary?.base_currency ?? 'EUR'"
        :category-totals-base="store.summary?.liabilities_by_category ?? {}"
        :total-base="store.summary?.total_liabilities ?? '0'"
        v-bind="itemListProps"
        :assets="activeAssets"
        :on-update="updateLiabilityAndShowExpenseReview"
        :on-archive="store.archiveLiability"
        :on-delete="deleteLiabilityAndReloadExpenses"
        :on-add="() => (showLiabilityModal = true)"
        :on-edit="(it) => openEdit(it, 'liability')"
      />
    </div>

    <div v-if="store.loading" class="ui-status-line">Cargando...</div>

    <BaseModal :open="showAssetModal" title="Nuevo activo" @close="showAssetModal = false">
      <ItemForm
        title="Nuevo activo"
        :categories="assetCategories"
        :subcategories="assetSubcategories"
        v-bind="itemFormProps"
        :allow-negative="true"
        :on-submit="submitAsset"
        :on-cancel="() => (showAssetModal = false)"
      />
    </BaseModal>

    <BaseModal :open="showLiabilityModal" title="Nuevo pasivo" @close="showLiabilityModal = false">
      <ItemForm
        title="Nuevo pasivo"
        :categories="liabilityCategories"
        v-bind="itemFormProps"
        :assets="activeAssets"
        :show-financed-asset="true"
        :on-submit="submitLiabilityWithExpenseReview"
        :on-cancel="() => (showLiabilityModal = false)"
      />
    </BaseModal>

    <BaseModal
      :open="showGeneratedLiabilityExpenseModal"
      :title="generatedLiabilityExpenseReviewTitle"
      @close="closeGeneratedLiabilityExpenseModal"
    >
      <div v-if="generatedLiabilityExpenseReview" class="grid gap-3">
        <div
          v-if="generatedLiabilityExpenseReviewChangeMessage"
          class="rounded-xl border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-sm text-white/90"
        >
          {{ generatedLiabilityExpenseReviewChangeMessage }}
        </div>
        <div
          class="rounded-xl border border-teal-300/20 bg-teal-400/10 px-3 py-2 text-sm text-white/90"
        >
          Se han generado gastos recurrentes en {{ generatedLiabilityExpenseReview.entries.length }}
          anualidades para este pasivo. Revisalos y confirma que la clasificacion
          (categoria/subcategoria/naturaleza) es correcta.
        </div>

        <div class="grid gap-2">
          <div
            v-for="entry in generatedLiabilityExpenseReview.entries"
            :key="entry.id"
            class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="text-sm font-medium">Ejercicio {{ entry.fiscalYear }}</div>
              <div class="text-sm text-white/90">
                {{ formatMoneyAmount(entry.amountAnnual, entry.currency) }}
              </div>
            </div>
            <div class="mt-1 text-xs text-white/70">
              {{ expenseCategoryLabel(entry.category) }} /
              {{ expenseSubcategoryLabel(entry.subcategory) }}
              <template
                v-if="
                  !shouldHideExpenseCashflowRoleLabel({
                    timeProfile: entry.timeProfile as ExpenseTimeProfile,
                    cashflowRole: entry.cashflowRole as AnnualExpenseCashflowRole,
                  })
                "
              >
                . {{ expenseCashflowRoleLabel(entry.cashflowRole as AnnualExpenseCashflowRole) }}
              </template>
              . {{ timeProfileLabel(entry.timeProfile as ExpenseTimeProfile) }}
            </div>
            <div v-if="entry.notes" class="mt-1 text-xs text-white/55">
              {{ entry.notes }}
            </div>
          </div>
        </div>

        <div class="actions justify-end">
          <button
            class="btn"
            type="button"
            :disabled="!generatedLiabilityExpenseReview.entries.length"
            @click="openGeneratedExpenseBulkEdit"
          >
            Editar todos los ejercicios
          </button>
          <button class="btn btn-ghost" type="button" @click="closeGeneratedLiabilityExpenseModal">
            Cerrar
          </button>
          <button
            class="btn btn-primary"
            type="button"
            :disabled="
              !annualExpenseEntries.some(
                (entry) =>
                  entry.sourceLiabilityId === generatedLiabilityExpenseReview?.liabilityId &&
                  entry.isSystemGenerated,
              )
            "
            @click="openGeneratedExpenseReviewEntryFromVisibleYear"
          >
            Revisar en gastos (año visible)
          </button>
        </div>
      </div>
    </BaseModal>

    <BaseModal :open="showEditModal" :title="editTitle" @close="closeEdit">
      <ItemForm
        v-if="editInitial"
        :title="editTitle"
        :categories="editCategories"
        :subcategories="editKind === 'asset' ? assetSubcategories : undefined"
        v-bind="itemFormProps"
        :assets="editKind === 'liability' ? activeAssets : []"
        :show-financed-asset="editKind === 'liability'"
        :allow-negative="editKind === 'asset'"
        mode="edit"
        :initial="editInitial"
        :on-submit="submitEditWithExpenseReview"
        :on-cancel="closeEdit"
      />
    </BaseModal>

    <AnnualEntryModalForm
      :open="showIncomeModal"
      :title="incomeModalTitle"
      :form="annualIncomeForm"
      :loading="annualIncomeLoading"
      :submit-label="incomeSubmitLabel"
      :category-options="incomeCategories"
      :subcategory-options="annualSubcategoryOptions"
      :show-owner-field="showOwnerField"
      :owner-options="ownerOptions"
      :time-profile-options="incomeTimeProfileOptions"
      :cashflow-role-options="incomeCashflowRoleOptions"
      :show-cashflow-role-field="false"
      :event-group-options="annualEventGroupOptions"
      event-group-datalist-id="income-event-groups"
      name-placeholder="Concepto (ej: CTN, Regalos Pablo)"
      :amount-placeholder="incomeAmountInputPlaceholder"
      @patch="patchAnnualIncomeForm"
      @close="closeIncomeModal"
      @submit="submitAnnualIncome"
    />

    <AnnualEntryModalForm
      :open="showExpenseModal"
      :title="expenseModalTitle"
      :form="annualExpenseForm"
      :loading="annualExpenseLoading"
      :submit-label="expenseSubmitLabel"
      :category-options="expenseCategories"
      :subcategory-options="annualExpenseSubcategoryOptions"
      :show-owner-field="showOwnerField"
      :owner-options="ownerOptions"
      :time-profile-options="expenseTimeProfileOptions"
      time-profile-field-label="Tipo de salida"
      :cashflow-role-options="filteredExpenseCashflowRoleOptions"
      :show-cashflow-role-field="showExpenseCashflowRoleField"
      :show-event-group-field="!editingSystemGeneratedLiabilityExpense"
      :show-term-end-year-field="!editingSystemGeneratedLiabilityExpense"
      :event-group-options="annualEventGroupOptions"
      event-group-datalist-id="expense-event-groups"
      name-placeholder="Concepto (ej: Alimentacion, Hipoteca)"
      :amount-placeholder="expenseAmountInputPlaceholder"
      :notes-placeholder="expenseBulkEditHint"
      @patch="patchAnnualExpenseForm"
      @close="closeExpenseModal"
      @submit="submitAnnualExpense"
    />
  </div>
</template>
