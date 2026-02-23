<script setup lang="ts">
import { computed, nextTick, onBeforeUnmount, reactive, ref, watch } from 'vue';
import { api } from '@/lib/api';
import { toApiErrorMessage } from '@/lib/errors';
import {
  ItemForm,
  ItemList,
  useNetWorthViewExtensions,
  useNetWorthViewState,
} from '@/domains/net-worth';
import { BaseModal } from '@/domains/ui';
import {
  useAnnualIncomeStore,
  type AnnualIncomeCashflowRole,
  type AnnualTimeProfile as IncomeTimeProfile,
} from '@/domains/data-input/annualIncomeStore';
import {
  useAnnualExpenseStore,
  type AnnualExpenseCashflowRole,
  type AnnualTimeProfile as ExpenseTimeProfile,
} from '@/domains/data-input/annualExpenseStore';
import {
  expenseCategories,
  expenseSubcategories,
  type ExpenseCategoryKey,
} from '@/domains/data-input/expenseTaxonomy';
import {
  incomeCategories,
  incomeSubcategories,
  type IncomeCategoryKey,
} from '@/domains/data-input/incomeTaxonomy';

const {
  store,
  assetCategories,
  assetSubcategories,
  liabilityCategories,
  prettyError,
  showAssetModal,
  showLiabilityModal,
  showEditModal,
  editKind,
  submitAsset,
  submitLiability,
  openEdit,
  closeEdit,
  editTitle,
  editCategories,
  editInitial,
  submitEdit,
} = useNetWorthViewState();

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
} = useAnnualExpenseStore('core');
const annualIncomeError = ref<string | null>(null);
const annualExpenseError = ref<string | null>(null);
const showIncomeModal = ref(false);
const editingIncomeId = ref<number | null>(null);
const editingExpenseId = ref<number | null>(null);
const showExpenseModal = ref(false);
const hydratingAnnualIncomeForm = ref(false);
const hydratingAnnualExpenseForm = ref(false);
const expandedIncomeCats = ref<Set<string>>(new Set());
const expandedExpenseCats = ref<Set<string>>(new Set());
const fiscalYear = ref(2026);
const fiscalYearOptions = computed(() => {
  const current = new Date().getFullYear();
  const years = new Set<number>([current - 1, current, current + 1, 2026]);
  return Array.from(years).sort((a, b) => b - a);
});

const annualIncomeForm = reactive({
  category: 'salary' as IncomeCategoryKey,
  subcategory: 'employee_salary',
  name: '',
  isRecurrent: true,
  timeProfile: 'structural_recurrent' as IncomeTimeProfile,
  cashflowRole: 'operating' as AnnualIncomeCashflowRole,
  eventGroup: '',
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
  isRecurrent: true,
  timeProfile: 'structural_recurrent' as ExpenseTimeProfile,
  cashflowRole: 'operating' as AnnualExpenseCashflowRole,
  eventGroup: '',
  termEndYear: '',
  amountInputPeriod: 'annual' as 'annual' | 'monthly',
  amountAnnual: '',
  currency: 'EUR',
  notes: '',
});

const annualSubcategoryOptions = computed(() =>
  incomeSubcategories.filter((row) => row.category === annualIncomeForm.category),
);
const annualExpenseSubcategoryOptions = computed(() =>
  expenseSubcategories.filter((row) => row.category === annualExpenseForm.category),
);
const filteredAnnualIncomeEntries = computed(() => annualIncomeEntries.value);
const filteredAnnualExpenseEntries = computed(() => annualExpenseEntries.value);

const filteredAnnualIncomeTotal = computed(() =>
  filteredAnnualIncomeEntries.value.reduce((sum, entry) => sum + entry.amountAnnual, 0),
);
const filteredAnnualExpenseTotal = computed(() =>
  filteredAnnualExpenseEntries.value.reduce((sum, entry) => sum + entry.amountAnnual, 0),
);
const annualBalanceTotal = computed(
  () => filteredAnnualIncomeTotal.value - filteredAnnualExpenseTotal.value,
);
const annualIncomeCount = computed(() => annualIncomeEntries.value.length);
const annualExpenseCount = computed(() => annualExpenseEntries.value.length);
const assetsCount = computed(() => store.assets.length);
const liabilitiesCount = computed(() => store.liabilities.length);
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

const assetsTotalBase = computed(() => parseNumeric(store.summary?.total_assets ?? '0'));
const liabilitiesTotalBase = computed(() => parseNumeric(store.summary?.total_liabilities ?? '0'));
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
  return expenseSubcategories.find((subcategory) => subcategory.value === key)?.label ?? key;
}

function timeProfileLabel(type: IncomeTimeProfile | ExpenseTimeProfile): string {
  if (type === 'structural_recurrent') return 'Recurrente estructural';
  if (type === 'term_recurrent') return 'Recurrente temporal';
  return 'Puntual';
}
function incomeCashflowRoleLabel(role: AnnualIncomeCashflowRole): string {
  if (role === 'operating') return 'Operativo';
  if (role === 'transfer') return 'Transferencia';
  if (role === 'asset_sale') return 'Venta de activo';
  if (role === 'tax_adjustment') return 'Ajuste fiscal';
  return 'Otro';
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
  annualIncomeForm.category = 'salary';
  annualIncomeForm.subcategory = 'employee_salary';
  annualIncomeForm.name = '';
  annualIncomeForm.isRecurrent = true;
  annualIncomeForm.timeProfile = 'structural_recurrent';
  annualIncomeForm.cashflowRole = defaultIncomeCashflowRole(annualIncomeForm.category);
  annualIncomeForm.eventGroup = '';
  annualIncomeForm.termEndYear = '';
  annualIncomeForm.amountInputPeriod = 'annual';
  annualIncomeForm.amountAnnual = '';
  annualIncomeForm.currency = 'EUR';
  annualIncomeForm.notes = '';
}
function resetExpenseForm(): void {
  annualExpenseForm.category = 'consumption_expenses';
  annualExpenseForm.subcategory = 'living_expenses';
  annualExpenseForm.name = '';
  annualExpenseForm.isRecurrent = true;
  annualExpenseForm.timeProfile = 'structural_recurrent';
  annualExpenseForm.cashflowRole = defaultExpenseCashflowRole(
    annualExpenseForm.category,
    annualExpenseForm.subcategory,
  );
  annualExpenseForm.eventGroup = '';
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
    annualIncomeForm.isRecurrent = entry.incomeType === 'recurrent';
    annualIncomeForm.timeProfile = entry.timeProfile;
    annualIncomeForm.cashflowRole = entry.cashflowRole;
    annualIncomeForm.eventGroup = entry.eventGroup || '';
    annualIncomeForm.termEndYear =
      entry.termEndYear == null ? '' : String(Number(entry.termEndYear));
    annualIncomeForm.amountInputPeriod = 'annual';
    annualIncomeForm.amountAnnual = String(entry.amountAnnual);
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
    annualExpenseForm.subcategory = entry.subcategory;
    annualExpenseForm.name = entry.name;
    annualExpenseForm.isRecurrent = entry.expenseType === 'recurrent';
    annualExpenseForm.timeProfile = entry.timeProfile;
    annualExpenseForm.cashflowRole = entry.cashflowRole;
    annualExpenseForm.eventGroup = entry.eventGroup || '';
    annualExpenseForm.termEndYear =
      entry.termEndYear == null ? '' : String(Number(entry.termEndYear));
    annualExpenseForm.amountInputPeriod = 'annual';
    annualExpenseForm.amountAnnual = String(entry.amountAnnual);
    annualExpenseForm.currency = entry.currency;
    annualExpenseForm.notes = entry.notes || '';
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
  editingExpenseId.value === null ? 'Nuevo gasto anual' : 'Editar gasto anual',
);
const expenseSubmitLabel = computed(() =>
  editingExpenseId.value === null ? 'Guardar gasto' : 'Guardar cambios',
);

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
    if (timeProfile !== 'term_recurrent') annualIncomeForm.termEndYear = '';
  },
);
watch(
  () => annualExpenseForm.timeProfile,
  (timeProfile) => {
    annualExpenseForm.isRecurrent = timeProfile !== 'one_off';
    if (timeProfile !== 'term_recurrent') annualExpenseForm.termEndYear = '';
  },
);
watch(
  () => annualIncomeForm.category,
  () => {
    if (hydratingAnnualIncomeForm.value) return;
    annualIncomeForm.cashflowRole = defaultIncomeCashflowRole(annualIncomeForm.category);
  },
);
watch([() => annualExpenseForm.category, () => annualExpenseForm.subcategory], () => {
  if (hydratingAnnualExpenseForm.value) return;
  annualExpenseForm.cashflowRole = defaultExpenseCashflowRole(
    annualExpenseForm.category,
    annualExpenseForm.subcategory,
  );
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
    incomeType: (annualIncomeForm.isRecurrent ? 'recurrent' : 'one_off') as 'recurrent' | 'one_off',
    timeProfile: annualIncomeForm.timeProfile,
    cashflowRole: annualIncomeForm.cashflowRole,
    eventGroup: annualIncomeForm.eventGroup,
    termEndYear:
      annualIncomeForm.timeProfile === 'term_recurrent' &&
      String(annualIncomeForm.termEndYear).trim()
        ? Number(annualIncomeForm.termEndYear)
        : null,
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
    expenseType: (annualExpenseForm.isRecurrent ? 'recurrent' : 'one_off') as
      | 'recurrent'
      | 'one_off',
    timeProfile: annualExpenseForm.timeProfile,
    cashflowRole: annualExpenseForm.cashflowRole,
    eventGroup: annualExpenseForm.eventGroup,
    termEndYear:
      annualExpenseForm.timeProfile === 'term_recurrent' &&
      String(annualExpenseForm.termEndYear).trim()
        ? Number(annualExpenseForm.termEndYear)
        : null,
    amountAnnual: String(normalizedAmount),
    fiscalYear: fiscalYear.value,
    currency: annualExpenseForm.currency,
    notes: annualExpenseForm.notes,
  };
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

type PortableAnnualIncomeRecord = {
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

type PortableAnnualExpenseRecord = {
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

type PortableAssetRecord = {
  id: number;
  name: string;
  category: string;
  subcategory: string;
  tracking_mode: string;
  accounting_account_id: number | null;
  currency: string;
  start_date?: string;
  annual_interest_tae?: string | null;
  amount: string;
  is_active: boolean;
  notes: string;
};

type PortableLiabilityRecord = {
  id: number;
  name: string;
  category: string;
  tracking_mode: string;
  accounting_account_id: number | null;
  currency: string;
  start_date?: string;
  annual_interest_tae?: string | null;
  monthly_payment_amount?: string | null;
  amount: string;
  is_active: boolean;
  notes: string;
  financed_asset_ref?: number | null;
};

type PortableSnapshotRecord = {
  id: number;
  snapshot_date: string;
  base_currency: string;
  total_assets: string;
  total_liabilities: string;
  net_worth: string;
  created_at?: string;
};

type PortableSettingsRecord = {
  base_currency: string;
};

type PortableDataBundle = {
  schema_version: 1;
  exported_at: string;
  source_app: 'core';
  settings?: PortableSettingsRecord;
  data: {
    annual_income: PortableAnnualIncomeRecord[];
    annual_expense: PortableAnnualExpenseRecord[];
    assets: PortableAssetRecord[];
    liabilities: PortableLiabilityRecord[];
    snapshots?: PortableSnapshotRecord[];
  };
};

const dataTransferBusy = ref(false);
const dataTransferBusyLabel = ref<string | null>(null);
const dataTransferStatus = ref<string | null>(null);
const dataTransferError = ref<string | null>(null);
const dataTransferToastMessage = ref<string | null>(null);
const dataTransferToastKind = ref<'success' | 'error'>('success');
const importFileInputRef = ref<HTMLInputElement | null>(null);
type ImportMode = 'append' | 'replace';
const pendingImportMode = ref<ImportMode>('append');
let dataTransferToastTimer: number | null = null;

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

function normalizeOptionalText(raw: unknown): string | null {
  if (raw == null) return null;
  const text = String(raw).trim();
  return text ? text : null;
}

function normalizeImportedAssetTae(asset: PortableAssetRecord): string | null {
  const normalized = normalizeOptionalText(asset.annual_interest_tae);
  if (normalized != null) return normalized;

  const category = String(asset.category ?? '').trim();
  const subcategory = String(asset.subcategory ?? '').trim();
  const requiresTae =
    category === 'cash' &&
    (subcategory === 'bank_account' ||
      subcategory === 'crypto_spot_earn' ||
      subcategory === 'other');

  // Backward compatibility: older exports may not include TAE for assets that are now required.
  return requiresTae ? '0' : null;
}

function normalizeImportedLiabilityTae(liability: PortableLiabilityRecord): string | null {
  const normalized = normalizeOptionalText(liability.annual_interest_tae);
  if (normalized != null) return normalized;

  const category = String(liability.category ?? '').trim();
  const requiresTae =
    category === 'mortgage' || category === 'personal_loan' || category === 'credit_card';

  // Backward compatibility: older exports may not include TAE for liabilities that are now required.
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

function buildImportPreviewMessage(bundle: PortableDataBundle, mode: ImportMode): string {
  const snapshots = bundle.data.snapshots ?? [];
  const snapshotRange =
    snapshots.length > 0
      ? `${[...snapshots].map((s) => s.snapshot_date).sort()[0]} .. ${
          [...snapshots]
            .map((s) => s.snapshot_date)
            .sort()
            .slice(-1)[0]
        }`
      : 'sin snapshots';
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
    '',
    formatImportYearSummary(bundle.data.annual_income, 'Ingresos por ano'),
    formatImportYearSummary(bundle.data.annual_expense, 'Gastos por ano'),
    '',
    mode === 'replace'
      ? 'Se borraran primero los datos actuales de estos bloques (incluidos snapshots).'
      : 'La importacion anade registros y actualiza settings/snapshots importados.',
    'Continuar?',
  ];
  return lines.join('\n');
}

function buildPortableFilename(): string {
  const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
  return `moneyplanner-core-data-${timestamp}.json`;
}

function triggerImportDialog(mode: ImportMode = 'append'): void {
  clearDataTransferFeedback();
  pendingImportMode.value = mode;
  importFileInputRef.value?.click();
}

async function exportDataBundle(): Promise<void> {
  clearDataTransferFeedback();
  dataTransferBusyLabel.value = 'Exportando datos...';
  dataTransferBusy.value = true;
  try {
    const [incomeRes, expenseRes, assetsRes, liabilitiesRes, snapshotsRes, settingsRes] =
      await Promise.all([
        api.get<PortableAnnualIncomeRecord[]>('/api/budget/annual-income/'),
        api.get<PortableAnnualExpenseRecord[]>('/api/budget/annual-expense/'),
        api.get<PortableAssetRecord[]>('/api/net-worth/assets/'),
        api.get<PortableLiabilityRecord[]>('/api/net-worth/liabilities/'),
        api.get<PortableSnapshotRecord[]>('/api/net-worth/snapshots/'),
        api.get<PortableSettingsRecord>('/api/auth/settings/'),
      ]);

    const payload: PortableDataBundle = {
      schema_version: 1,
      exported_at: new Date().toISOString(),
      source_app: 'core',
      settings: settingsRes.data ?? undefined,
      data: {
        annual_income: (incomeRes.data ?? []).slice(),
        annual_expense: (expenseRes.data ?? []).slice(),
        assets: (assetsRes.data ?? []).slice(),
        liabilities: (liabilitiesRes.data ?? []).slice(),
        snapshots: (snapshotsRes.data ?? []).slice(),
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

    dataTransferStatus.value = `Exportacion completada: ${payload.data.annual_income.length} ingresos, ${payload.data.annual_expense.length} gastos, ${payload.data.assets.length} activos, ${payload.data.liabilities.length} pasivos y ${payload.data.snapshots?.length ?? 0} snapshots.`;
  } catch (e: unknown) {
    dataTransferError.value = `No se pudo exportar: ${toApiErrorMessage(e)}`;
  } finally {
    dataTransferBusy.value = false;
    dataTransferBusyLabel.value = null;
  }
}

function parsePortableDataBundle(raw: string): PortableDataBundle {
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
  return {
    schema_version: 1,
    exported_at: String(parsed.exported_at ?? ''),
    source_app: 'core',
    settings:
      parsed.settings && typeof parsed.settings === 'object'
        ? { base_currency: String((parsed.settings as PortableSettingsRecord).base_currency ?? '') }
        : undefined,
    data: {
      annual_income,
      annual_expense,
      assets,
      liabilities,
      snapshots: Array.isArray(snapshots) ? snapshots : [],
    },
  };
}

async function clearExistingDataForReplace(): Promise<void> {
  const [incomeRes, expenseRes, assetsRes, liabilitiesRes, snapshotsRes] = await Promise.all([
    api.get<{ id: number }[]>('/api/budget/annual-income/'),
    api.get<{ id: number }[]>('/api/budget/annual-expense/'),
    api.get<{ id: number }[]>('/api/net-worth/assets/'),
    api.get<{ id: number }[]>('/api/net-worth/liabilities/'),
    api.get<{ id: number }[]>('/api/net-worth/snapshots/'),
  ]);

  for (const item of [...(liabilitiesRes.data ?? [])].sort((a, b) => b.id - a.id)) {
    await api.delete(`/api/net-worth/liabilities/${item.id}/`);
  }
  for (const item of [...(assetsRes.data ?? [])].sort((a, b) => b.id - a.id)) {
    await api.delete(`/api/net-worth/assets/${item.id}/`);
  }
  for (const item of [...(incomeRes.data ?? [])].sort((a, b) => b.id - a.id)) {
    await api.delete(`/api/budget/annual-income/${item.id}/`);
  }
  for (const item of [...(expenseRes.data ?? [])].sort((a, b) => b.id - a.id)) {
    await api.delete(`/api/budget/annual-expense/${item.id}/`);
  }
  for (const item of [...(snapshotsRes.data ?? [])].sort((a, b) => b.id - a.id)) {
    await api.delete(`/api/net-worth/snapshots/${item.id}/`);
  }
}

function setDataImportBusyState(importMode: 'append' | 'replace') {
  dataTransferBusyLabel.value =
    importMode === 'replace'
      ? 'Reemplazando datos... Esto puede tardar unos segundos.'
      : 'Importando datos...';
  dataTransferBusy.value = true;
}

async function importPortableAssets(
  assets: PortableAssetRecord[],
): Promise<{ sortedAssets: PortableAssetRecord[]; assetIdMap: Map<number, number> }> {
  const assetIdMap = new Map<number, number>();
  const sortedAssets = [...assets].sort((a, b) => a.id - b.id);
  for (const asset of sortedAssets) {
    const assetPayload = {
      name: asset.name,
      category: asset.category,
      subcategory: asset.subcategory,
      tracking_mode: asset.tracking_mode,
      accounting_account_id: asset.accounting_account_id,
      currency: asset.currency,
      start_date: asset.start_date,
      annual_interest_tae: normalizeImportedAssetTae(asset),
      amount: String(asset.amount),
      is_active: asset.is_active ?? true,
      notes: asset.notes ?? '',
    };
    const res = await api.post<{ id: number }>('/api/net-worth/assets/', assetPayload);
    if (typeof res.data?.id === 'number') assetIdMap.set(asset.id, res.data.id);
  }
  return { sortedAssets, assetIdMap };
}

async function importPortableLiabilities(
  liabilities: PortableLiabilityRecord[],
  assetIdMap: Map<number, number>,
): Promise<PortableLiabilityRecord[]> {
  const sortedLiabilities = [...liabilities].sort((a, b) => a.id - b.id);
  for (const liability of sortedLiabilities) {
    const financedAssetId =
      liability.financed_asset_ref != null
        ? (assetIdMap.get(liability.financed_asset_ref) ?? null)
        : null;
    const liabilityPayload = {
      name: liability.name,
      category: liability.category,
      tracking_mode: liability.tracking_mode,
      accounting_account_id: liability.accounting_account_id,
      currency: liability.currency,
      start_date: liability.start_date,
      annual_interest_tae: normalizeImportedLiabilityTae(liability),
      monthly_payment_amount: normalizeOptionalText(liability.monthly_payment_amount),
      amount: String(liability.amount),
      is_active: liability.is_active ?? true,
      notes: liability.notes ?? '',
      financed_asset_id: financedAssetId,
    };
    await api.post('/api/net-worth/liabilities/', liabilityPayload);
  }
  return sortedLiabilities;
}

async function importPortableAnnualIncomeEntries(
  annualIncome: PortableAnnualIncomeRecord[],
): Promise<PortableAnnualIncomeRecord[]> {
  const sortedIncome = [...annualIncome].sort((a, b) => a.id - b.id);
  for (const entry of sortedIncome) {
    await api.post('/api/budget/annual-income/', {
      name: entry.name,
      category: entry.category,
      subcategory: entry.subcategory,
      owner_name: String(entry.owner_name ?? '').trim(),
      income_type: entry.income_type,
      time_profile: entry.time_profile,
      cashflow_role: entry.cashflow_role,
      event_group: String(entry.event_group ?? ''),
      term_end_year: entry.term_end_year ?? null,
      amount_annual: String(entry.amount_annual),
      fiscal_year: Number(entry.fiscal_year),
      currency: (entry.currency || 'EUR').toUpperCase(),
      notes: entry.notes ?? '',
      is_active: entry.is_active ?? true,
    });
  }
  return sortedIncome;
}

async function importPortableAnnualExpenseEntries(
  annualExpense: PortableAnnualExpenseRecord[],
): Promise<PortableAnnualExpenseRecord[]> {
  const sortedExpense = [...annualExpense].sort((a, b) => a.id - b.id);
  for (const entry of sortedExpense) {
    await api.post('/api/budget/annual-expense/', {
      name: entry.name,
      category: entry.category,
      subcategory: entry.subcategory,
      owner_name: String(entry.owner_name ?? '').trim(),
      expense_type: entry.expense_type,
      time_profile: entry.time_profile,
      cashflow_role: entry.cashflow_role,
      event_group: String(entry.event_group ?? ''),
      term_end_year: entry.term_end_year ?? null,
      amount_annual: String(entry.amount_annual),
      fiscal_year: Number(entry.fiscal_year),
      currency: (entry.currency || 'EUR').toUpperCase(),
      notes: entry.notes ?? '',
      is_active: entry.is_active ?? true,
    });
  }
  return sortedExpense;
}

async function importPortableSettingsAndSnapshots(bundle: PortableDataBundle): Promise<void> {
  if (bundle.settings?.base_currency) {
    await api.put('/api/auth/settings/', { base_currency: bundle.settings.base_currency });
  }
  if (!Array.isArray(bundle.data.snapshots) || !bundle.data.snapshots.length) return;
  await api.post(
    '/api/net-worth/snapshots/import-bulk/',
    bundle.data.snapshots.map((snapshot) => ({
      snapshot_date: snapshot.snapshot_date,
      base_currency: snapshot.base_currency,
      total_assets: snapshot.total_assets,
      total_liabilities: snapshot.total_liabilities,
      net_worth: snapshot.net_worth,
    })),
  );
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
  bundle: PortableDataBundle;
  sortedIncomeCount: number;
  sortedExpenseCount: number;
  sortedAssetsCount: number;
  sortedLiabilitiesCount: number;
}): string {
  const {
    importMode,
    bundle,
    sortedIncomeCount,
    sortedExpenseCount,
    sortedAssetsCount,
    sortedLiabilitiesCount,
  } = params;
  return importMode === 'replace'
    ? `Reemplazo completado: ${sortedIncomeCount} ingresos, ${sortedExpenseCount} gastos, ${sortedAssetsCount} activos, ${sortedLiabilitiesCount} pasivos y ${bundle.data.snapshots?.length ?? 0} snapshots.`
    : `Importacion completada: ${sortedIncomeCount} ingresos, ${sortedExpenseCount} gastos, ${sortedAssetsCount} activos, ${sortedLiabilitiesCount} pasivos y ${bundle.data.snapshots?.length ?? 0} snapshots.`;
}

async function importDataFromFile(event: Event): Promise<void> {
  const input = event.target as HTMLInputElement | null;
  const file = input?.files?.[0];
  if (!file) return;

  clearDataTransferFeedback();

  try {
    const content = await file.text();
    const bundle = parsePortableDataBundle(content);
    const importMode = pendingImportMode.value;

    const proceed = window.confirm(buildImportPreviewMessage(bundle, importMode));
    if (!proceed) return;

    setDataImportBusyState(importMode);

    if (importMode === 'replace') {
      await clearExistingDataForReplace();
    }

    const { sortedAssets, assetIdMap } = await importPortableAssets(bundle.data.assets);
    const sortedLiabilities = await importPortableLiabilities(bundle.data.liabilities, assetIdMap);
    const sortedIncome = await importPortableAnnualIncomeEntries(bundle.data.annual_income);
    const sortedExpense = await importPortableAnnualExpenseEntries(bundle.data.annual_expense);
    await importPortableSettingsAndSnapshots(bundle);
    await refreshImportedDataViews();

    dataTransferStatus.value = buildImportCompletionStatus({
      importMode,
      bundle,
      sortedIncomeCount: sortedIncome.length,
      sortedExpenseCount: sortedExpense.length,
      sortedAssetsCount: sortedAssets.length,
      sortedLiabilitiesCount: sortedLiabilities.length,
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
        Gestiona aqui la base financiera anual: ingresos, activos y pasivos con interes para el
        analisis de patrimonio.
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
                id="fiscal-year-income-expense-core"
                v-model.number="fiscalYear"
                class="select nw-select-sm ui-flow-air-year-select"
                aria-label="Ejercicio"
              >
                <option v-for="year in fiscalYearOptions" :key="year" :value="year">
                  {{ year }}
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
            <h2 class="card-header-title mt-0">Ingresos anuales</h2>
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
          No hay ingresos en el ejercicio {{ fiscalYear }}.
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
                        </div>
                        <div class="nw-item-submeta">
                          {{ timeProfileLabel(entry.timeProfile) }} .
                          {{ incomeCashflowRoleLabel(entry.cashflowRole) }}
                          <template v-if="entry.eventGroup">
                            . Evento {{ entry.eventGroup }}</template
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
            <h2 class="card-header-title mt-0">Gastos anuales</h2>
          </div>
          <div class="nw-list-header-right">
            <div class="nw-list-total-inline">
              {{ formatMoneyAmount(filteredAnnualExpenseTotal, 'EUR') }}
            </div>
            <button
              class="btn btn-primary btn-sm nw-list-add-icon-only"
              type="button"
              aria-label="Anadir gasto"
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
          No hay gastos anuales todavia.
        </div>
        <div
          v-else-if="!filteredAnnualExpenseEntries.length && !annualExpenseLoading"
          class="subtle mt-3"
        >
          No hay gastos en el ejercicio {{ fiscalYear }}.
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
                        </div>
                        <div class="nw-item-submeta">
                          {{ timeProfileLabel(entry.timeProfile) }} .
                          {{ expenseCashflowRoleLabel(entry.cashflowRole) }}
                          <template v-if="entry.eventGroup">
                            . Evento {{ entry.eventGroup }}</template
                          >
                          <template v-if="entry.termEndYear != null">
                            . Fin {{ entry.termEndYear }}</template
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
          Cargando gastos anuales...
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
        title="Activos"
        :items="store.assets"
        :categories="assetCategories"
        :subcategories="assetSubcategories"
        :base-currency="store.baseCurrency ?? store.summary?.base_currency ?? 'EUR'"
        :category-totals-base="store.summary?.assets_by_category ?? {}"
        :subcategory-totals-base="store.summary?.assets_by_subcategory ?? {}"
        :total-base="store.summary?.total_assets ?? '0'"
        v-bind="itemListProps"
        :on-update="store.updateAsset"
        :on-archive="store.archiveAsset"
        :on-add="() => (showAssetModal = true)"
        :on-edit="(it) => openEdit(it, 'asset')"
      />

      <ItemList
        title="Pasivos"
        :items="store.liabilities"
        :categories="liabilityCategories"
        :base-currency="store.baseCurrency ?? store.summary?.base_currency ?? 'EUR'"
        :category-totals-base="store.summary?.liabilities_by_category ?? {}"
        :total-base="store.summary?.total_liabilities ?? '0'"
        v-bind="itemListProps"
        :assets="store.assets"
        :on-update="store.updateLiability"
        :on-archive="store.archiveLiability"
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
        :assets="store.assets"
        :show-financed-asset="true"
        :on-submit="submitLiability"
        :on-cancel="() => (showLiabilityModal = false)"
      />
    </BaseModal>

    <BaseModal :open="showEditModal" :title="editTitle" @close="closeEdit">
      <ItemForm
        v-if="editInitial"
        :title="editTitle"
        :categories="editCategories"
        :subcategories="editKind === 'asset' ? assetSubcategories : undefined"
        v-bind="itemFormProps"
        :assets="editKind === 'liability' ? store.assets : []"
        :show-financed-asset="editKind === 'liability'"
        :allow-negative="editKind === 'asset'"
        mode="edit"
        :initial="editInitial"
        :on-submit="submitEdit"
        :on-cancel="closeEdit"
      />
    </BaseModal>

    <BaseModal :open="showIncomeModal" :title="incomeModalTitle" @close="closeIncomeModal">
      <div class="grid gap-2.5 md:grid-cols-2">
        <select v-model="annualIncomeForm.category" class="select ui-data-field">
          <option
            v-for="category in incomeCategories"
            :key="category.value"
            :value="category.value"
          >
            {{ category.label }}
          </option>
        </select>
        <select v-model="annualIncomeForm.subcategory" class="select ui-data-field">
          <option
            v-for="subcategory in annualSubcategoryOptions"
            :key="subcategory.value"
            :value="subcategory.value"
          >
            {{ subcategory.label }}
          </option>
        </select>
        <input
          v-model="annualIncomeForm.name"
          class="input ui-data-field md:col-span-2"
          placeholder="Concepto (ej: CTN, Regalos Pablo)"
        />
        <select v-model="annualIncomeForm.timeProfile" class="select ui-data-field">
          <option value="structural_recurrent">Recurrente estructural (base)</option>
          <option value="term_recurrent">Recurrente temporal (con fin)</option>
          <option value="one_off">Puntual / extraordinario</option>
        </select>
        <select v-model="annualIncomeForm.cashflowRole" class="select ui-data-field">
          <option value="operating">Naturaleza: Operativo</option>
          <option value="transfer">Naturaleza: Transferencia/apoyo</option>
          <option value="asset_sale">Naturaleza: Venta de activo</option>
          <option value="tax_adjustment">Naturaleza: Ajuste fiscal</option>
          <option value="other">Naturaleza: Otro</option>
        </select>
        <input
          v-model="annualIncomeForm.eventGroup"
          class="input ui-data-field"
          placeholder="Grupo de evento (opcional, ej: vivienda_2026)"
        />
        <input
          v-if="annualIncomeForm.timeProfile === 'term_recurrent'"
          v-model="annualIncomeForm.termEndYear"
          class="input ui-data-field"
          inputmode="numeric"
          placeholder="Ano fin compromiso (ej: 2027)"
        />
        <div
          class="grid items-center gap-2.5 md:col-span-2 md:grid-cols-[minmax(0,1fr)_auto_120px]"
        >
          <input
            v-model="annualIncomeForm.amountAnnual"
            class="input ui-data-field"
            inputmode="decimal"
            :placeholder="incomeAmountInputPlaceholder"
          />
          <div class="grid justify-items-center gap-1">
            <button
              type="button"
              class="relative inline-flex h-[34px] w-[58px] items-center rounded-full border transition"
              :class="
                annualIncomeForm.amountInputPeriod === 'monthly'
                  ? 'border-teal-300/60 bg-teal-400/20'
                  : 'border-white/20 bg-white/5'
              "
              :disabled="annualIncomeForm.timeProfile === 'one_off'"
              aria-label="Cambiar periodicidad mensual/anual"
              @click="
                annualIncomeForm.amountInputPeriod =
                  annualIncomeForm.amountInputPeriod === 'annual' ? 'monthly' : 'annual'
              "
            >
              <span
                class="inline-block h-6 w-6 rounded-full bg-white/90 transition-transform"
                :class="
                  annualIncomeForm.amountInputPeriod === 'monthly'
                    ? 'translate-x-7'
                    : 'translate-x-1'
                "
              />
            </button>
            <span class="subtle text-[11px]">
              <span :class="annualIncomeForm.amountInputPeriod === 'annual' ? 'text-white/90' : ''">
                Anual
              </span>
              /
              <span
                :class="annualIncomeForm.amountInputPeriod === 'monthly' ? 'text-white/90' : ''"
              >
                Mensual
              </span>
            </span>
          </div>
          <select v-model="annualIncomeForm.currency" class="select ui-data-field">
            <option value="EUR">EUR</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <textarea
          v-model="annualIncomeForm.notes"
          class="textarea md:col-span-2"
          rows="2"
          placeholder="Notas (opcional)"
        />
        <div class="actions md:col-span-2">
          <button class="btn btn-ghost" type="button" @click="closeIncomeModal">Cancelar</button>
          <button
            class="btn btn-primary"
            type="button"
            :disabled="annualIncomeLoading"
            @click="submitAnnualIncome"
          >
            {{ incomeSubmitLabel }}
          </button>
        </div>
      </div>
    </BaseModal>

    <BaseModal :open="showExpenseModal" :title="expenseModalTitle" @close="closeExpenseModal">
      <div class="grid gap-2.5 md:grid-cols-2">
        <select v-model="annualExpenseForm.category" class="select ui-data-field">
          <option
            v-for="category in expenseCategories"
            :key="category.value"
            :value="category.value"
          >
            {{ category.label }}
          </option>
        </select>
        <select v-model="annualExpenseForm.subcategory" class="select ui-data-field">
          <option
            v-for="subcategory in annualExpenseSubcategoryOptions"
            :key="subcategory.value"
            :value="subcategory.value"
          >
            {{ subcategory.label }}
          </option>
        </select>
        <input
          v-model="annualExpenseForm.name"
          class="input ui-data-field md:col-span-2"
          placeholder="Concepto (ej: Alimentacion, Hipoteca)"
        />
        <select v-model="annualExpenseForm.timeProfile" class="select ui-data-field">
          <option value="structural_recurrent">Recurrente estructural (estilo de vida)</option>
          <option value="term_recurrent">Recurrente temporal (cuotas/compromiso)</option>
          <option value="one_off">Puntual / extraordinario</option>
        </select>
        <select v-model="annualExpenseForm.cashflowRole" class="select ui-data-field">
          <option value="operating">Naturaleza: Operativo</option>
          <option value="temporary_commitment">Naturaleza: Compromiso temporal</option>
          <option value="savings">Naturaleza: Ahorro</option>
          <option value="investment">Naturaleza: Inversion</option>
          <option value="asset_purchase">Naturaleza: Compra de activo</option>
          <option value="tax_fee">Naturaleza: Impuestos/gastos</option>
          <option value="transfer">Naturaleza: Transferencia</option>
          <option value="other">Naturaleza: Otro</option>
        </select>
        <input
          v-model="annualExpenseForm.eventGroup"
          class="input ui-data-field"
          placeholder="Grupo de evento (opcional, ej: vivienda_2026)"
        />
        <input
          v-if="annualExpenseForm.timeProfile === 'term_recurrent'"
          v-model="annualExpenseForm.termEndYear"
          class="input ui-data-field"
          inputmode="numeric"
          placeholder="Ano fin compromiso (ej: 2027)"
        />
        <div
          class="grid items-center gap-2.5 md:col-span-2 md:grid-cols-[minmax(0,1fr)_auto_120px]"
        >
          <input
            v-model="annualExpenseForm.amountAnnual"
            class="input ui-data-field"
            inputmode="decimal"
            :placeholder="expenseAmountInputPlaceholder"
          />
          <div class="grid justify-items-center gap-1">
            <button
              type="button"
              class="relative inline-flex h-[34px] w-[58px] items-center rounded-full border transition"
              :class="
                annualExpenseForm.amountInputPeriod === 'monthly'
                  ? 'border-teal-300/60 bg-teal-400/20'
                  : 'border-white/20 bg-white/5'
              "
              :disabled="annualExpenseForm.timeProfile === 'one_off'"
              aria-label="Cambiar periodicidad mensual/anual"
              @click="
                annualExpenseForm.amountInputPeriod =
                  annualExpenseForm.amountInputPeriod === 'annual' ? 'monthly' : 'annual'
              "
            >
              <span
                class="inline-block h-6 w-6 rounded-full bg-white/90 transition-transform"
                :class="
                  annualExpenseForm.amountInputPeriod === 'monthly'
                    ? 'translate-x-7'
                    : 'translate-x-1'
                "
              />
            </button>
            <span class="subtle text-[11px]">
              <span
                :class="annualExpenseForm.amountInputPeriod === 'annual' ? 'text-white/90' : ''"
              >
                Anual
              </span>
              /
              <span
                :class="annualExpenseForm.amountInputPeriod === 'monthly' ? 'text-white/90' : ''"
              >
                Mensual
              </span>
            </span>
          </div>
          <select v-model="annualExpenseForm.currency" class="select ui-data-field">
            <option value="EUR">EUR</option>
            <option value="USD">USD</option>
          </select>
        </div>
        <textarea
          v-model="annualExpenseForm.notes"
          class="textarea md:col-span-2"
          rows="2"
          placeholder="Notas (opcional)"
        />
        <div class="actions md:col-span-2">
          <button class="btn btn-ghost" type="button" @click="closeExpenseModal">Cancelar</button>
          <button
            class="btn btn-primary"
            type="button"
            :disabled="annualExpenseLoading"
            @click="submitAnnualExpense"
          >
            {{ expenseSubmitLabel }}
          </button>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
