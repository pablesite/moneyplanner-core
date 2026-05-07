<script setup lang="ts">
import { computed, ref } from 'vue';
import { useRouter } from 'vue-router';
import {
  type AnnualExpenseEntry,
  type AnnualIncomeEntry,
  AnnualEntryModalForm,
  normalizeExpenseTaxonomy,
} from '@/domains/data-input';
import { effectiveAnnualAmountForEntry } from '@/domains/data-input/annualEntryUtils';

const router = useRouter();

type BudgetSection = {
  id: 'income' | 'expense';
  title: string;
  subtitle: string;
  emptyMessage: string;
  toneClass: string;
  totalAnnual: number;
  filterMode: 'all' | 'recurrent' | 'one_off';
  categoryCount: number;
  subcategoryCount: number;
  groups: any[];
};

type BudgetRow = {
  key: string;
  categoryKey: string;
  categoryLabel: string;
  subcategoryKey: string;
  subcategoryLabel: string;
  plannedAnnual: number;
  itemsCount: number;
};

type ContextPanel = {
  sectionId: 'income' | 'expense';
  row: BudgetRow;
};

type RowEntry = AnnualIncomeEntry | AnnualExpenseEntry;
type BudgetExecutionTone = 'neutral' | 'good' | 'warn' | 'danger';
type BudgetExecutionPreview = {
  ratio: number;
  widthPct: number;
  tone: BudgetExecutionTone;
  overflow: boolean;
};
type BudgetActualExecution = BudgetExecutionPreview & {
  planned: number;
  executed: number;
  deviation: number;
  completionRatio: number;
};

const props = defineProps<{
  isMonthlyCloseView: boolean;
  hasAnyPlannedData: boolean;
  isLoading: boolean;
  fiscalYear: number;
  sections: BudgetSection[];
  monthLabels: string[];
  incomeEvolutionMonths: any[];
  incomeEvolutionBaseMonthly: number;
  expenseEvolutionMonths: any[];
  expenseEvolutionBaseMonthly: number;
  selectedExecutionMonthLabel: string;
  budgetDetailMonth: number;
  budgetDetailMonthLabel: string;
  updateBudgetDetailMonth: (month: number) => void;
  budgetSectionActualExecution: (sectionId: 'income' | 'expense') => BudgetActualExecution | null;
  formatMoney: (value: number, decimals?: number) => string;
  formatCompactMoney: (value: number, decimals?: number) => string;
  formatPercent: (value: number | null, decimals?: number) => string;
  formatSignedMoney: (value: number, decimals?: number) => string;
  isSectionExpanded: (sectionId: 'income' | 'expense') => boolean;
  toggleSectionExpanded: (sectionId: 'income' | 'expense') => void;
  budgetCategoryActualExecution: (...args: any[]) => any;
  budgetSubcategoryActualExecution: (...args: any[]) => any;
  incomeInvestmentRotationCategoryAdjustment?: (...args: any[]) => number;
  incomeInvestmentRotationSubcategoryAdjustment?: (...args: any[]) => number;
  incomeExecutionYtdTotals: {
    planned: number;
    executedBudgeted: number;
    executedUnbudgeted: number;
    executedTotal: number;
  };
  expenseExecutionYtdTotals: {
    planned: number;
    executedBudgeted: number;
    executedUnbudgeted: number;
    executedTotal: number;
  };
  executionPreview: (...args: any[]) => any;
  updateIncomeViewMode: (mode: 'all' | 'recurrent' | 'one_off') => void;
  updateExpenseViewMode: (mode: 'all' | 'recurrent' | 'one_off') => void;
  onSubmitAnnualIncome?: () => Promise<void> | void;
  onSubmitAnnualExpense?: () => Promise<void> | void;
  onRemoveAnnualIncome?: (entryId: number) => Promise<void> | void;
  onRemoveAnnualExpense?: (entryId: number) => Promise<void> | void;
  annualEntriesPage: any | null;
  filteredIncomeEntries: AnnualIncomeEntry[];
  filteredExpenseEntries: AnnualExpenseEntry[];
  ownershipFilter: string;
  selectedOwnershipFilterLabel: string;
}>();

const activeContext = ref<ContextPanel | null>(null);
const expandedGroups = ref<Record<string, boolean>>({});

function isGroupExpanded(categoryKey: string): boolean {
  return !!expandedGroups.value[categoryKey];
}

function toggleGroup(categoryKey: string): void {
  expandedGroups.value = {
    ...expandedGroups.value,
    [categoryKey]: !expandedGroups.value[categoryKey],
  };
}

function isDepositRotationIncomeCategory(
  sectionId: 'income' | 'expense',
  categoryKey: string,
): boolean {
  return sectionId === 'income' && categoryKey === 'capital_gains';
}

function isDepositRotationIncomeSubcategory(
  sectionId: 'income' | 'expense',
  rowKey: string,
): boolean {
  return sectionId === 'income' && rowKey === 'capital_gains::sale_financial_assets';
}

function categoryExecutedLabel(sectionId: 'income' | 'expense', categoryKey: string): string {
  const adjustment =
    props.incomeInvestmentRotationCategoryAdjustment?.(sectionId, categoryKey) ?? 0;
  if (adjustment > 0 && isDepositRotationIncomeCategory(sectionId, categoryKey)) {
    return 'Cambio neto dep. YTD';
  }
  return 'Ejecutado YTD';
}

function subcategoryExecutedLabel(sectionId: 'income' | 'expense', rowKey: string): string {
  const adjustment = props.incomeInvestmentRotationSubcategoryAdjustment?.(sectionId, rowKey) ?? 0;
  if (adjustment > 0 && isDepositRotationIncomeSubcategory(sectionId, rowKey)) {
    return 'Cambio neto dep. YTD';
  }
  return 'Ejecutado YTD';
}

function goToMovements(categoryKey: string, subcategoryKey?: string): void {
  const fmt = (d: Date) => {
    const y = d.getFullYear();
    const m = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    return `${y}-${m}-${day}`;
  };
  const dateFrom = fmt(new Date(props.fiscalYear, 0, 1));
  const dateTo = fmt(new Date(props.fiscalYear, props.budgetDetailMonth, 0));
  const query: Record<string, string> = {
    tab: 'todos',
    date_from: dateFrom,
    date_to: dateTo,
    category_key: categoryKey,
  };
  if (subcategoryKey) query.subcategory_key = subcategoryKey;
  router.push({ name: 'accounting-movements', query });
}

function matchesRowTaxonomy(
  sectionId: 'income' | 'expense',
  entry: RowEntry,
  row: BudgetRow,
): boolean {
  if (sectionId === 'income') {
    return entry.category === row.categoryKey && entry.subcategory === row.subcategoryKey;
  }
  const normalized = normalizeExpenseTaxonomy(entry.category, entry.subcategory);
  return normalized.category === row.categoryKey && normalized.subcategory === row.subcategoryKey;
}

const contextIncomeEntries = computed(() => {
  const context = activeContext.value;
  if (!context || context.sectionId !== 'income') return [];
  return props.filteredIncomeEntries.filter((entry) => {
    if (!matchesRowTaxonomy('income', entry, context.row)) return false;
    if (props.sections.find((section) => section.id === 'income')?.filterMode === 'recurrent') {
      return entry.incomeType === 'recurrent';
    }
    if (props.sections.find((section) => section.id === 'income')?.filterMode === 'one_off') {
      return entry.incomeType === 'one_off';
    }
    return true;
  });
});

const contextExpenseEntries = computed(() => {
  const context = activeContext.value;
  if (!context || context.sectionId !== 'expense') return [];
  return props.filteredExpenseEntries.filter((entry) => {
    if (!matchesRowTaxonomy('expense', entry, context.row)) return false;
    if (props.sections.find((section) => section.id === 'expense')?.filterMode === 'recurrent') {
      return entry.expenseType === 'recurrent';
    }
    if (props.sections.find((section) => section.id === 'expense')?.filterMode === 'one_off') {
      return entry.expenseType === 'one_off';
    }
    return true;
  });
});

function isContextOpen(sectionId: 'income' | 'expense', rowKey: string): boolean {
  return activeContext.value?.sectionId === sectionId && activeContext.value?.row.key === rowKey;
}

function toggleContext(sectionId: 'income' | 'expense', row: BudgetRow): void {
  if (isContextOpen(sectionId, row.key)) {
    activeContext.value = null;
    return;
  }
  activeContext.value = { sectionId, row };
}

const OVERFLOW_FILL_COLORS: Record<BudgetExecutionTone, [string, string]> = {
  good: ['hsl(142 71% 48%)', 'hsl(142 50% 65%)'],
  warn: ['hsl(56 92% 49%)', 'hsl(56 70% 65%)'],
  danger: ['hsl(0 82% 52%)', 'hsl(0 60% 68%)'],
  neutral: ['rgba(255,255,255,0.34)', 'rgba(255,255,255,0.15)'],
};

function overflowFillStyle(
  exec: { tone: BudgetExecutionTone; ratio: number; overflow: boolean; widthPct: number } | null | undefined,
  fallbackWidthPct = 8,
): Record<string, string> {
  if (!exec?.overflow) return { width: `${exec?.widthPct ?? fallbackWidthPct}%` };
  const threshold = (1 / exec.ratio) * 100;
  const [base, over] = OVERFLOW_FILL_COLORS[exec.tone];
  return {
    width: '100%',
    background: `linear-gradient(to right, ${base} ${threshold}%, ${over} ${threshold}%)`,
  };
}

function openCreateForCategory(sectionId: 'income' | 'expense', categoryKey: string): void {
  if (!props.annualEntriesPage) return;
  if (sectionId === 'income') {
    props.annualEntriesPage.openIncomeModal();
    props.annualEntriesPage.patchAnnualIncomeForm({
      category: categoryKey,
      owner: props.ownershipFilter === 'all' ? '' : props.selectedOwnershipFilterLabel,
    });
    return;
  }
  props.annualEntriesPage.openExpenseModal();
  props.annualEntriesPage.patchAnnualExpenseForm({
    category: categoryKey,
    owner: props.ownershipFilter === 'all' ? '' : props.selectedOwnershipFilterLabel,
  });
}

function openCreateDirect(sectionId: 'income' | 'expense', row: BudgetRow): void {
  if (!props.annualEntriesPage) return;
  if (sectionId === 'income') {
    props.annualEntriesPage.openIncomeModal();
    props.annualEntriesPage.patchAnnualIncomeForm({
      category: row.categoryKey,
      subcategory: row.subcategoryKey,
      owner: props.ownershipFilter === 'all' ? '' : props.selectedOwnershipFilterLabel,
    });
    return;
  }
  props.annualEntriesPage.openExpenseModal();
  props.annualEntriesPage.patchAnnualExpenseForm({
    category: row.categoryKey,
    subcategory: row.subcategoryKey,
    owner: props.ownershipFilter === 'all' ? '' : props.selectedOwnershipFilterLabel,
  });
}

function isOneOffEntry(entry: RowEntry): boolean {
  if ('incomeType' in entry) return entry.incomeType === 'one_off';
  return entry.expenseType === 'one_off';
}

function targetMonthLabel(targetMonth?: number | null): string {
  const month = Number(targetMonth ?? 0);
  if (Number.isFinite(month) && month >= 1 && month <= 12) {
    return props.monthLabels[month - 1] ?? `mes ${month}`;
  }
  return 'mes objetivo';
}

function recurringMonthlyPlannedAmount(entry: RowEntry): number {
  const annual = effectiveAnnualAmountForEntry(entry, entry.fiscalYear);
  if (!Number.isFinite(annual) || annual <= 0 || isOneOffEntry(entry)) return 0;
  if (
    'timeProfile' in entry &&
    entry.timeProfile === 'term_recurrent' &&
    (entry.termEndYear == null || entry.termEndYear === entry.fiscalYear)
  ) {
    const months = Math.min(12, Math.max(1, Number(entry.termEndMonth ?? 12)));
    return annual / months;
  }
  return annual / 12;
}

function entriesForRow(sectionId: 'income' | 'expense', row: BudgetRow): RowEntry[] {
  const source =
    sectionId === 'income' ? props.filteredIncomeEntries : props.filteredExpenseEntries;
  return source.filter((entry) => matchesRowTaxonomy(sectionId, entry, row));
}

function rowPlannedMeta(sectionId: 'income' | 'expense', row: BudgetRow): string {
  const entries = entriesForRow(sectionId, row);
  const total = entries.reduce(
    (sum, entry) => sum + effectiveAnnualAmountForEntry(entry, entry.fiscalYear),
    0,
  );
  const count = entries.length || row.itemsCount;
  const countText = `${count} registro${count === 1 ? '' : 's'}`;
  if (!entries.length) {
    return `${countText} - ${props.formatMoney(row.plannedAnnual / 12)} EUR/mes previsto`;
  }
  const oneOffEntries = entries.filter((entry) => isOneOffEntry(entry));
  if (oneOffEntries.length === entries.length) {
    const uniqueMonths = new Set<number>(
      oneOffEntries
        .map((entry) => Number(entry.targetMonth))
        .filter((month) => Number.isFinite(month) && month >= 1 && month <= 12),
    );
    if (uniqueMonths.size === 1) {
      const month = Array.from(uniqueMonths)[0];
      return `${countText} - ${props.formatMoney(total)} EUR en ${targetMonthLabel(month)} previsto`;
    }
    return `${countText} - ${props.formatMoney(total)} EUR puntual previsto`;
  }
  if (oneOffEntries.length > 0) {
    const recurringEntries = entries.filter((entry) => !isOneOffEntry(entry));
    const recurringMonthly = recurringEntries.reduce(
      (sum, entry) => sum + recurringMonthlyPlannedAmount(entry),
      0,
    );
    const oneOffTotal = oneOffEntries.reduce(
      (sum, entry) => sum + Number(entry.amountAnnual ?? 0),
      0,
    );
    const uniqueMonths = new Set<number>(
      oneOffEntries
        .map((entry) => Number(entry.targetMonth))
        .filter((month) => Number.isFinite(month) && month >= 1 && month <= 12),
    );
    if (recurringMonthly > 0 && uniqueMonths.size === 1) {
      const month = Array.from(uniqueMonths)[0];
      return `${countText} - ${props.formatMoney(recurringMonthly)} EUR/mes + ${props.formatMoney(oneOffTotal)} EUR en ${targetMonthLabel(month)}`;
    }
    if (recurringMonthly > 0) {
      return `${countText} - ${props.formatMoney(recurringMonthly)} EUR/mes + ${props.formatMoney(oneOffTotal)} EUR puntual`;
    }
  }
  const entriesWithTargetMonth = entries.filter((entry) => entry.targetMonth != null);
  if (entriesWithTargetMonth.length === entries.length) {
    const uniqueMonths = new Set<number>(
      entriesWithTargetMonth
        .map((entry) => Number(entry.targetMonth))
        .filter((month) => Number.isFinite(month) && month >= 1 && month <= 12),
    );
    if (uniqueMonths.size === 1) {
      const month = Array.from(uniqueMonths)[0];
      return `${countText} - ${props.formatMoney(total)} EUR en ${targetMonthLabel(month)} previsto`;
    }
    return `${countText} - ${props.formatMoney(total)} EUR en meses previstos`;
  }
  return `${countText} - ${props.formatMoney(total / 12)} EUR/mes previsto`;
}

function groupExecutionPreview(
  sectionId: 'income' | 'expense',
  group: { categoryKey: string; plannedAnnual: number },
): BudgetExecutionPreview {
  if ((Number(group.plannedAnnual) || 0) <= 0) {
    return { ratio: 0, widthPct: 0, tone: 'neutral', overflow: false };
  }
  return props.executionPreview(sectionId, `group:${group.categoryKey}`) as BudgetExecutionPreview;
}

function sectionYtdTotals(sectionId: 'income' | 'expense') {
  return sectionId === 'income' ? props.incomeExecutionYtdTotals : props.expenseExecutionYtdTotals;
}

function execBarClass(point: any, sectionId: 'income' | 'expense'): string {
  if (!('hasExecuted' in point) || !point.hasExecuted) return 'ui-budget-month-exec-pending';
  const planned = Number(point.planned ?? 0);
  const executed = Number(point.executed ?? 0);
  if (planned <= 0) return 'ui-budget-month-exec-good';
  const ratio = executed / planned;
  if (sectionId === 'income') {
    if (ratio >= 1) return 'ui-budget-month-exec-good';
    if (ratio >= 0.85) return 'ui-budget-month-exec-warn';
    return 'ui-budget-month-exec-danger';
  } else {
    if (ratio > 1.05) return 'ui-budget-month-exec-danger';
    if (ratio >= 0.95) return 'ui-budget-month-exec-warn';
    return 'ui-budget-month-exec-good';
  }
}

function visibleEvolutionMonths(sectionId: 'income' | 'expense') {
  const months = sectionId === 'income' ? props.incomeEvolutionMonths : props.expenseEvolutionMonths;
  const visible = months.slice(0, props.budgetDetailMonth);
  const maxVal = Math.max(1, ...visible.map((m: any) => Math.max(Number(m.planned ?? 0), Number(m.executed ?? 0))));
  return visible.map((m: any) => ({
    ...m,
    planHeightPct: Number(m.planned) > 0 ? Math.max(6, Math.min(100, (Number(m.planned) / maxVal) * 100)) : 0,
    execHeightPct: Number(m.executed) > 0 ? Math.max(6, Math.min(100, (Number(m.executed) / maxVal) * 100)) : 0,
  }));
}

function openEditIncome(entry: AnnualIncomeEntry): void {
  props.annualEntriesPage?.openIncomeModal(entry);
}

function openEditExpense(entry: AnnualExpenseEntry): void {
  props.annualEntriesPage?.openExpenseModal(entry);
}

async function removeIncome(entry: AnnualIncomeEntry): Promise<void> {
  if (!props.annualEntriesPage) return;
  if (props.onRemoveAnnualIncome) {
    await props.onRemoveAnnualIncome(entry.id);
    return;
  }
  await props.annualEntriesPage.removeAnnualIncome(entry.id);
}

async function removeExpense(entry: AnnualExpenseEntry): Promise<void> {
  if (!props.annualEntriesPage) return;
  if (props.onRemoveAnnualExpense) {
    await props.onRemoveAnnualExpense(entry.id);
    return;
  }
  await props.annualEntriesPage.removeAnnualExpense(entry.id);
}
</script>

<template>
  <section
    v-if="!isMonthlyCloseView && !hasAnyPlannedData && !isLoading"
    class="card ui-pro-panel ui-budget-empty mt-3"
  >
    <h2 class="mt-0">Sin presupuesto anual para {{ fiscalYear }}</h2>
    <p class="subtle mb-0">
      Usa el bloque `Balance anual` de esta misma vista para añadir ingresos y gastos previstos.
    </p>
  </section>

  <div
    v-show="!isMonthlyCloseView && sections.some(s => s.groups.length > 0)"
    class="ui-budget-detail-month-bar mt-3"
  >
    <span class="ui-budget-detail-month-bar-label">Ver acumulado hasta:</span>
    <div class="ui-budget-filter-segment" role="group" aria-label="Mes de detalle">
      <button
        v-for="(label, i) in monthLabels"
        :key="i"
        type="button"
        class="ui-budget-filter-btn"
        :class="{ 'ui-budget-filter-btn-active': budgetDetailMonth === i + 1 }"
        @click="updateBudgetDetailMonth(i + 1)"
      >
        {{ label }}
      </button>
    </div>
  </div>

  <div v-show="!isMonthlyCloseView" class="ui-budget-sections-grid mt-2">
  <section
    v-for="section in sections"
    :key="section.id"
    class="card ui-pro-panel ui-budget-section"
    :class="section.toneClass"
  >
    <div class="ui-budget-section-header">
      <div>
        <h2 class="ui-budget-section-title">{{ section.title }}</h2>
        <p class="ui-budget-section-subtitle">{{ section.subtitle }}</p>
      </div>
      <div class="ui-budget-section-header-side">
        <div class="ui-budget-section-controls">
          <span
            v-if="section.groups.length && !isSectionExpanded(section.id)"
            class="ui-budget-compact-badge"
          >
            Vista compacta activa
          </span>
        </div>

        <div class="ui-budget-section-total">
          <strong>{{ formatMoney(section.totalAnnual) }} EUR</strong>
          <small>{{ formatMoney(section.totalAnnual / 12) }} EUR/mes</small>
        </div>
      </div>
    </div>

    <div v-if="section.id === 'expense'" class="ui-budget-expense-coverage-kpis">
      <div class="ui-budget-expense-coverage-kpi">
        <span class="ui-budget-expense-coverage-kpi-label">Ejecutado real (YTD)</span>
        <strong>{{ formatMoney(expenseExecutionYtdTotals.executedTotal) }} EUR</strong>
      </div>
      <div class="ui-budget-expense-coverage-kpi">
        <span class="ui-budget-expense-coverage-kpi-label">Presupuesto previsto (YTD)</span>
        <strong>{{ formatMoney(expenseExecutionYtdTotals.planned) }} EUR</strong>
      </div>
      <div class="ui-budget-expense-coverage-kpi ui-budget-expense-coverage-kpi-alert">
        <span class="ui-budget-expense-coverage-kpi-label">Fuera de presupuesto (YTD)</span>
        <strong>{{ formatMoney(expenseExecutionYtdTotals.executedUnbudgeted) }} EUR</strong>
      </div>
    </div>
    <div v-else class="ui-budget-expense-coverage-kpis">
      <div class="ui-budget-expense-coverage-kpi">
        <span class="ui-budget-expense-coverage-kpi-label">Ejecutado real (YTD)</span>
        <strong>{{ formatMoney(incomeExecutionYtdTotals.executedTotal) }} EUR</strong>
      </div>
      <div class="ui-budget-expense-coverage-kpi">
        <span class="ui-budget-expense-coverage-kpi-label">Presupuesto previsto (YTD)</span>
        <strong>{{ formatMoney(incomeExecutionYtdTotals.planned) }} EUR</strong>
      </div>
      <div class="ui-budget-expense-coverage-kpi ui-budget-expense-coverage-kpi-alert">
        <span class="ui-budget-expense-coverage-kpi-label">Fuera de presupuesto (YTD)</span>
        <strong>{{ formatMoney(incomeExecutionYtdTotals.executedUnbudgeted) }} EUR</strong>
      </div>
    </div>

    <div class="ui-budget-evolution-card">
      <div class="ui-budget-evolution-head">
        <div>
          <h3>Evolucion ejecutada (barras)</h3>
          <p v-if="section.id === 'income'">
            Compara `Previsto` vs `Ejecutado` por mes usando los check-ins del cierre mensual
            {{
              section.filterMode === 'recurrent'
                ? '(ingresos recurrentes).'
                : section.filterMode === 'one_off'
                  ? '(ingresos puntuales).'
                  : '(todos los ingresos).'
            }}
          </p>
          <p v-else>
            Compara `Previsto` vs `Ejecutado` por mes usando los check-ins del cierre mensual
            {{
              section.filterMode === 'recurrent'
                ? '(gastos recurrentes).'
                : section.filterMode === 'one_off'
                  ? '(gastos puntuales).'
                  : '(todos los gastos).'
            }}
          </p>
        </div>
        <span class="ui-budget-pill">Cierre mensual activo</span>
      </div>

      <div
        class="ui-budget-evolution-bars"
        :style="{ gridTemplateColumns: `repeat(${budgetDetailMonth}, minmax(0, 1fr))` }"
        :aria-label="
          section.id === 'income'
            ? 'Barras de evolucion de ingresos previsto vs ejecutado por mes'
            : 'Barras de evolucion de gastos previsto vs ejecutado por mes'
        "
      >
        <div
          v-for="point in visibleEvolutionMonths(section.id)"
          :key="`${section.id}-${point.label}`"
          class="ui-budget-month-col"
        >
          <div class="ui-budget-month-rail">
            <div
              class="ui-budget-month-plan"
              :style="'planHeightPct' in point ? { height: `${point.planHeightPct}%` } : undefined"
              :title="
                'planned' in point
                  ? `Previsto ${point.label}: ${formatMoney(Number(point.planned))} EUR`
                  : undefined
              "
            />
            <div
              :class="execBarClass(point, section.id)"
              :style="'execHeightPct' in point ? { height: `${point.execHeightPct}%` } : undefined"
              :title="
                'executed' in point
                  ? `Ejecutado ${point.label}: ${formatMoney(Number(point.executed))} EUR`
                  : undefined
              "
            />
          </div>
          <span class="ui-budget-month-label">{{ point.label }}</span>
        </div>
      </div>

      <div class="ui-budget-evolution-legend">
        <span><i class="ui-budget-legend-dot ui-budget-legend-plan" /> Previsto</span>
        <span> <i class="ui-budget-legend-dot ui-budget-legend-exec-solid" /> Ejecutado </span>
        <span>
          {{ section.id === 'income' ? 'Base recurrente mensual:' : 'Base mensual orientativa:' }}
          <strong>
            {{
              formatCompactMoney(
                section.id === 'income' ? incomeEvolutionBaseMonthly : expenseEvolutionBaseMonthly,
              )
            }}
            EUR
          </strong>
        </span>
      </div>
    </div>

    <div v-if="section.groups.length" class="ui-budget-detail-toggle-bar">
      <div class="ui-budget-section-rollup" :aria-label="`Resumen YTD ${section.title}`">
        <div v-if="budgetSectionActualExecution(section.id)" class="ui-budget-rich-bar-wrap">
          <div class="ui-budget-rich-bar-track">
            <div
              class="ui-budget-rich-bar-fill"
              :class="`ui-budget-inline-progress-fill-${budgetSectionActualExecution(section.id)?.tone}`"
              :style="overflowFillStyle(budgetSectionActualExecution(section.id))"
            />
            <span
              v-if="budgetSectionActualExecution(section.id)?.overflow"
              class="ui-budget-inline-progress-overflow-marker"
              :style="{ left: `${(1 / budgetSectionActualExecution(section.id)!.ratio) * 100}%` }"
              aria-hidden="true"
            />
            <span class="ui-budget-rich-bar-exec-label">
              {{ formatMoney(sectionYtdTotals(section.id).executedTotal) }} EUR
            </span>
            <span class="ui-budget-rich-bar-plan-label">
              {{ formatMoney(sectionYtdTotals(section.id).planned) }} EUR
            </span>
          </div>
          <span
            class="ui-budget-rich-bar-deviation"
            :class="`ui-budget-pending-text-${budgetSectionActualExecution(section.id)?.tone}`"
          >
            {{ formatSignedMoney(budgetSectionActualExecution(section.id)?.deviation ?? 0) }} EUR
          </span>
        </div>

        <div class="ui-budget-section-rollup-controls">
          <button
            type="button"
            class="ui-budget-expand-link"
            :aria-expanded="isSectionExpanded(section.id)"
            @click="toggleSectionExpanded(section.id)"
          >
            {{ isSectionExpanded(section.id) ? 'Ocultar ↑' : 'Ver desglose ↓' }}
          </button>
        </div>
      </div>
    </div>

    <div
      v-if="section.groups.length && isSectionExpanded(section.id)"
      class="ui-budget-detail-area"
    >
      <div class="ui-budget-groups">
        <article
          v-for="group in section.groups"
          :key="`${section.id}-${group.categoryKey}`"
          class="ui-budget-group"
          :class="{
            'ui-budget-group-catalog':
              group.plannedAnnual === 0 && !group.rows.some((r: any) => r.detectedUnbudgeted),
          }"
        >
          <header
            class="ui-budget-group-header"
            role="button"
            tabindex="0"
            :aria-expanded="isGroupExpanded(group.categoryKey)"
            @click="toggleGroup(group.categoryKey)"
            @keydown.enter.prevent="toggleGroup(group.categoryKey)"
            @keydown.space.prevent="toggleGroup(group.categoryKey)"
          >
            <div class="ui-budget-group-title-wrap">
              <div class="ui-budget-group-kicker">Categoría</div>
              <div class="ui-budget-group-name-row">
                <h3 class="ui-budget-name-link" @click.stop="goToMovements(group.categoryKey)">
                  {{ group.categoryLabel }}
                </h3>
                <button
                  type="button"
                  class="ui-budget-group-add-btn"
                  :title="`Añadir en ${group.categoryLabel}`"
                  @click.stop="openCreateForCategory(section.id, group.categoryKey)"
                >
                  +
                </button>
              </div>
              <p
                v-if="
                  (incomeInvestmentRotationCategoryAdjustment?.(section.id, group.categoryKey) ??
                    0) > 0
                "
                class="subtle mb-0"
              >
                Cambio neto en depósitos aplicado (YTD): -{{
                  formatMoney(
                    incomeInvestmentRotationCategoryAdjustment?.(section.id, group.categoryKey) ??
                      0,
                  )
                }}
                EUR
              </p>

              <div
                v-if="budgetCategoryActualExecution(section.id, group.categoryKey)"
                class="ui-budget-rich-bar-wrap"
                :aria-label="`Ejecución YTD categoría ${group.categoryLabel}`"
              >
                <div class="ui-budget-rich-bar-track">
                  <div
                    class="ui-budget-rich-bar-fill"
                    :class="`ui-budget-inline-progress-fill-${budgetCategoryActualExecution(section.id, group.categoryKey)?.tone}`"
                    :style="overflowFillStyle(budgetCategoryActualExecution(section.id, group.categoryKey))"
                  />
                  <span
                    v-if="budgetCategoryActualExecution(section.id, group.categoryKey)?.overflow"
                    class="ui-budget-inline-progress-overflow-marker"
                    :style="{ left: `${(1 / budgetCategoryActualExecution(section.id, group.categoryKey)!.ratio) * 100}%` }"
                    aria-hidden="true"
                  />
                  <span class="ui-budget-rich-bar-exec-label">
                    {{ formatMoney(budgetCategoryActualExecution(section.id, group.categoryKey)?.executed ?? 0) }} EUR
                  </span>
                  <span class="ui-budget-rich-bar-plan-label">
                    {{ formatMoney(budgetCategoryActualExecution(section.id, group.categoryKey)?.planned ?? 0) }} EUR
                  </span>
                </div>
                <span
                  class="ui-budget-rich-bar-deviation"
                  :class="`ui-budget-pending-text-${budgetCategoryActualExecution(section.id, group.categoryKey)?.tone}`"
                >
                  {{ formatSignedMoney(budgetCategoryActualExecution(section.id, group.categoryKey)?.deviation ?? 0) }} EUR
                </span>
              </div>

              <div
                v-else-if="
                  group.plannedAnnual > 0 || group.rows.some((r: any) => r.detectedUnbudgeted)
                "
                class="ui-budget-rich-bar-wrap"
                aria-label="Placeholder ejecución categoría"
              >
                <div class="ui-budget-rich-bar-track">
                  <div
                    class="ui-budget-rich-bar-fill"
                    :class="`ui-budget-inline-progress-fill-${groupExecutionPreview(section.id, group).tone}`"
                    :style="overflowFillStyle(groupExecutionPreview(section.id, group))"
                  />
                  <span
                    v-if="groupExecutionPreview(section.id, group).overflow"
                    class="ui-budget-inline-progress-overflow-marker"
                    :style="{ left: `${(1 / groupExecutionPreview(section.id, group).ratio) * 100}%` }"
                    aria-hidden="true"
                  />
                  <span class="ui-budget-rich-bar-exec-label ui-budget-rich-bar-exec-label-pending">
                    Pendiente contabilidad
                  </span>
                  <span class="ui-budget-rich-bar-plan-label">
                    {{ formatMoney(group.plannedAnnual) }} EUR
                  </span>
                </div>
              </div>
            </div>

            <div class="ui-budget-group-header-right">
              <span class="ui-budget-group-chevron" aria-hidden="true" />
            </div>
          </header>

          <ul v-show="isGroupExpanded(group.categoryKey)" class="ui-budget-rows">
            <li
              v-for="row in group.rows"
              :key="row.key"
              class="ui-budget-row"
              :class="{ 'ui-budget-row-expandable': !row.detectedUnbudgeted && row.itemsCount > 0 }"
              :aria-expanded="(!row.detectedUnbudgeted && row.itemsCount > 0) ? isContextOpen(section.id, row.key) : undefined"
              @click="!row.detectedUnbudgeted && row.itemsCount > 0 && toggleContext(section.id, row)"
            >
              <div class="ui-budget-row-main">
                <div class="ui-budget-row-kicker">Subcategoría</div>
                <div class="ui-budget-row-title">
                  <span
                    class="ui-budget-name-link"
                    @click.stop="goToMovements(group.categoryKey, row.subcategoryKey)"
                    >{{ row.subcategoryLabel }}</span
                  >
                  <button
                    type="button"
                    class="ui-budget-row-inline-add"
                    :title="`Añadir en ${row.subcategoryLabel}`"
                    @click.stop="openCreateDirect(section.id, row)"
                  >
                    <svg
                      width="8"
                      height="8"
                      viewBox="0 0 8 8"
                      fill="currentColor"
                      aria-hidden="true"
                    >
                      <rect x="3.5" y="0" width="1" height="8" />
                      <rect x="0" y="3.5" width="8" height="1" />
                    </svg>
                  </button>
                </div>
                <div class="ui-budget-row-meta">
                  <template v-if="row.detectedUnbudgeted">
                    Detectado en movimientos -
                    {{ formatMoney(row.detectedExecutedYtd ?? 0) }} EUR fuera de presupuesto (YTD)
                  </template>
                  <template v-else>
                    {{ rowPlannedMeta(section.id, row) }}
                  </template>
                </div>
                <div
                  v-if="
                    (incomeInvestmentRotationSubcategoryAdjustment?.(section.id, row.key) ?? 0) > 0
                  "
                  class="ui-budget-row-meta"
                >
                  Cambio neto en depósitos aplicado (YTD): -{{
                    formatMoney(
                      incomeInvestmentRotationSubcategoryAdjustment?.(section.id, row.key) ?? 0,
                    )
                  }}
                  EUR
                </div>

                <div
                  v-if="budgetSubcategoryActualExecution(section.id, row.key)"
                  class="ui-budget-rich-bar-wrap"
                  :aria-label="`Ejecución YTD subcategoría ${row.subcategoryLabel}`"
                >
                  <div class="ui-budget-rich-bar-track">
                    <div
                      class="ui-budget-rich-bar-fill"
                      :class="`ui-budget-inline-progress-fill-${budgetSubcategoryActualExecution(section.id, row.key)?.tone}`"
                      :style="overflowFillStyle(budgetSubcategoryActualExecution(section.id, row.key))"
                    />
                    <span
                      v-if="budgetSubcategoryActualExecution(section.id, row.key)?.overflow"
                      class="ui-budget-inline-progress-overflow-marker"
                      :style="{ left: `${(1 / budgetSubcategoryActualExecution(section.id, row.key)!.ratio) * 100}%` }"
                      aria-hidden="true"
                    />
                    <span class="ui-budget-rich-bar-exec-label">
                      {{ formatMoney(budgetSubcategoryActualExecution(section.id, row.key)?.executed ?? 0) }} EUR
                    </span>
                    <span class="ui-budget-rich-bar-plan-label">
                      {{ formatMoney(budgetSubcategoryActualExecution(section.id, row.key)?.planned ?? 0) }} EUR
                    </span>
                  </div>
                  <span
                    class="ui-budget-rich-bar-deviation"
                    :class="`ui-budget-pending-text-${budgetSubcategoryActualExecution(section.id, row.key)?.tone}`"
                  >
                    {{ formatSignedMoney(budgetSubcategoryActualExecution(section.id, row.key)?.deviation ?? 0) }} EUR
                  </span>
                </div>

                <div
                  v-else-if="row.itemsCount > 0 || row.detectedUnbudgeted"
                  class="ui-budget-rich-bar-wrap"
                  aria-label="Placeholder ejecución subcategoría"
                >
                  <div class="ui-budget-rich-bar-track">
                    <div
                      class="ui-budget-rich-bar-fill ui-budget-inline-progress-fill-neutral"
                      :style="{ width: '0%' }"
                    />
                    <span class="ui-budget-rich-bar-exec-label ui-budget-rich-bar-exec-label-pending">
                      Ejecución pendiente
                    </span>
                    <span class="ui-budget-rich-bar-plan-label">
                      {{ formatMoney(row.plannedAnnual) }} EUR
                    </span>
                  </div>
                </div>

              </div>
              <span
                v-if="!row.detectedUnbudgeted && row.itemsCount > 0"
                class="ui-budget-group-chevron ui-budget-row-chevron"
                aria-hidden="true"
              />


              <div
                v-if="isContextOpen(section.id, row.key) && !row.detectedUnbudgeted"
                class="ui-budget-context-panel"
              >
                <ul
                  v-if="section.id === 'income' && contextIncomeEntries.length"
                  class="ui-budget-context-list"
                >
                  <li v-for="entry in contextIncomeEntries" :key="`income-${entry.id}`">
                    <div class="ui-budget-context-item">
                      <div class="ui-budget-context-main">
                        <strong>{{ entry.name }}</strong>
                        <small>
                          {{ entry.incomeType === 'recurrent' ? 'Recurrente' : 'Puntual' }}
                          <template v-if="entry.owner"> - {{ entry.owner }}</template>
                        </small>
                      </div>
                      <div class="ui-budget-context-actions">
                        <span class="ui-budget-context-amount"
                          >{{ formatMoney(entry.amountAnnual) }} {{ entry.currency }}</span
                        >
                        <button
                          type="button"
                          class="icon-btn"
                          title="Editar"
                          @click="openEditIncome(entry)"
                        >
                          &#9998;
                        </button>
                        <button
                          type="button"
                          class="icon-btn"
                          title="Eliminar"
                          @click="removeIncome(entry)"
                        >
                          &#128465;
                        </button>
                      </div>
                    </div>
                  </li>
                </ul>

                <ul
                  v-else-if="section.id === 'expense' && contextExpenseEntries.length"
                  class="ui-budget-context-list"
                >
                  <li v-for="entry in contextExpenseEntries" :key="`expense-${entry.id}`">
                    <div class="ui-budget-context-item">
                      <div class="ui-budget-context-main">
                        <strong>{{ entry.name }}</strong>
                        <small>
                          {{ entry.expenseType === 'recurrent' ? 'Recurrente' : 'Puntual' }}
                          <template v-if="entry.owner"> - {{ entry.owner }}</template>
                        </small>
                      </div>
                      <div class="ui-budget-context-actions">
                        <span class="ui-budget-context-amount"
                          >{{ formatMoney(entry.amountAnnual) }} {{ entry.currency }}</span
                        >
                        <button
                          type="button"
                          class="icon-btn"
                          title="Editar"
                          @click="openEditExpense(entry)"
                        >
                          &#9998;
                        </button>
                        <button
                          type="button"
                          class="icon-btn"
                          title="Eliminar"
                          @click="removeExpense(entry)"
                        >
                          &#128465;
                        </button>
                      </div>
                    </div>
                  </li>
                </ul>

                <p v-else class="subtle mb-0">
                  No hay registros con los filtros actuales para esta subcategoría.
                </p>
              </div>
            </li>
          </ul>
        </article>
      </div>
    </div>

    <div v-if="!section.groups.length" class="subtle">
      {{ section.emptyMessage }}
      <template v-if="section.filterMode !== 'all'">
        Prueba con la vista `Todos` si quieres incluir movimientos puntuales.
      </template>
    </div>
  </section>
  </div>

  <div v-if="isLoading" class="ui-status-line">Cargando presupuesto...</div>

  <AnnualEntryModalForm
    v-if="annualEntriesPage"
    :open="annualEntriesPage.showIncomeModal.value"
    :title="annualEntriesPage.incomeModalTitle.value"
    :form="annualEntriesPage.annualIncomeForm"
    :loading="annualEntriesPage.annualIncomeLoading.value"
    :submit-label="annualEntriesPage.incomeSubmitLabel.value"
    :category-options="annualEntriesPage.incomeCategories"
    :subcategory-options="annualEntriesPage.annualSubcategoryOptions.value"
    :show-owner-field="annualEntriesPage.showOwnerField.value"
    :owner-options="annualEntriesPage.ownerOptions.value"
    :time-profile-options="annualEntriesPage.incomeTimeProfileOptions.value"
    :cashflow-role-options="annualEntriesPage.incomeCashflowRoleOptions"
    :show-cashflow-role-field="false"
    :show-recurring-target-month-field="true"
    :event-group-options="annualEntriesPage.annualEventGroupOptions.value"
    event-group-datalist-id="budget-income-event-groups"
    name-placeholder="Concepto (ej: Nomina, Regalo)"
    :amount-placeholder="annualEntriesPage.incomeAmountInputPlaceholder.value"
    @patch="annualEntriesPage.patchAnnualIncomeForm"
    @close="annualEntriesPage.closeIncomeModal"
    @submit="onSubmitAnnualIncome ? onSubmitAnnualIncome() : annualEntriesPage.submitAnnualIncome()"
  />

  <AnnualEntryModalForm
    v-if="annualEntriesPage"
    :open="annualEntriesPage.showExpenseModal.value"
    :title="annualEntriesPage.expenseModalTitle.value"
    :form="annualEntriesPage.annualExpenseForm"
    :loading="annualEntriesPage.annualExpenseLoading.value"
    :submit-label="annualEntriesPage.expenseSubmitLabel.value"
    :category-options="annualEntriesPage.expenseCategories"
    :subcategory-options="annualEntriesPage.annualExpenseSubcategoryOptions.value"
    :show-owner-field="annualEntriesPage.showOwnerField.value"
    :owner-options="annualEntriesPage.ownerOptions.value"
    :time-profile-options="annualEntriesPage.expenseTimeProfileOptions"
    time-profile-field-label="Tipo de salida"
    :cashflow-role-options="annualEntriesPage.filteredExpenseCashflowRoleOptions.value"
    :show-cashflow-role-field="annualEntriesPage.showExpenseCashflowRoleField.value"
    :show-event-group-field="!annualEntriesPage.editingSystemGeneratedLiabilityExpense.value"
    :show-term-end-year-field="!annualEntriesPage.editingSystemGeneratedLiabilityExpense.value"
    :event-group-options="annualEntriesPage.annualEventGroupOptions.value"
    event-group-datalist-id="budget-expense-event-groups"
    name-placeholder="Concepto (ej: Alimentacion, Hipoteca)"
    :amount-placeholder="annualEntriesPage.expenseAmountInputPlaceholder.value"
    :notes-placeholder="annualEntriesPage.expenseBulkEditHint.value"
    @patch="annualEntriesPage.patchAnnualExpenseForm"
    @close="annualEntriesPage.closeExpenseModal"
    @submit="
      onSubmitAnnualExpense ? onSubmitAnnualExpense() : annualEntriesPage.submitAnnualExpense()
    "
  />
</template>
