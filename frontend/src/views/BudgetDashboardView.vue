<script setup lang="ts">
import { computed, ref, watch } from 'vue';
import { useAnnualExpenseStore } from '@/domains/data-input/annualExpenseStore';
import { useAnnualIncomeStore } from '@/domains/data-input/annualIncomeStore';
import { expenseCategories, expenseSubcategories } from '@/domains/data-input/expenseTaxonomy';
import { incomeCategories, incomeSubcategories } from '@/domains/data-input/incomeTaxonomy';

type BudgetRow = {
  key: string;
  categoryKey: string;
  categoryLabel: string;
  subcategoryKey: string;
  subcategoryLabel: string;
  plannedAnnual: number;
  itemsCount: number;
};

type BudgetGroup = {
  categoryKey: string;
  categoryLabel: string;
  plannedAnnual: number;
  shareOfSection: number;
  rows: BudgetRow[];
};

type BudgetSectionModel = {
  id: 'income' | 'expense';
  title: string;
  subtitle: string;
  emptyMessage: string;
  toneClass: string;
  totalAnnual: number;
  filterMode: BudgetEntryViewMode;
  categoryCount: number;
  subcategoryCount: number;
  groups: BudgetGroup[];
};

type BudgetEntryViewMode = 'all' | 'recurrent' | 'one_off';
type BudgetExecutionTone = 'neutral' | 'good' | 'warn' | 'danger';
type BudgetExecutionPreview = {
  ratio: number;
  widthPct: number;
  tone: BudgetExecutionTone;
  overflow: boolean;
};

const incomeStore = useAnnualIncomeStore('saas');
const expenseStore = useAnnualExpenseStore('saas');

const fiscalYear = ref(new Date().getFullYear());
const ownershipFilter = ref<string>('all');
const incomeViewMode = ref<BudgetEntryViewMode>('all');
const expenseViewMode = ref<BudgetEntryViewMode>('all');
const incomeDetailsExpanded = ref(false);
const expenseDetailsExpanded = ref(false);
const currentCalendarYear = new Date().getFullYear();
const monthLabels = [
  'Ene',
  'Feb',
  'Mar',
  'Abr',
  'May',
  'Jun',
  'Jul',
  'Ago',
  'Sep',
  'Oct',
  'Nov',
  'Dic',
];

const incomeCategoryLabels = new Map(
  incomeCategories.map((row) => [row.value, row.label] as const),
);
const incomeSubcategoryLabels = new Map(
  incomeSubcategories.map((row) => [row.value, row.label] as const),
);
const expenseCategoryLabels = new Map(
  expenseCategories.map((row) => [row.value, row.label] as const),
);
const expenseSubcategoryLabels = new Map(
  expenseSubcategories.map((row) => [row.value, row.label] as const),
);

const fiscalYearOptions = computed(() => {
  const years = new Set<number>([
    currentCalendarYear - 1,
    currentCalendarYear,
    currentCalendarYear + 1,
    2026,
  ]);
  for (const entry of incomeStore.entries.value) years.add(entry.fiscalYear);
  for (const entry of expenseStore.entries.value) years.add(entry.fiscalYear);
  years.add(fiscalYear.value);
  return Array.from(years).sort((a, b) => b - a);
});
const selectedOwnershipFilterLabel = computed(() => {
  if (ownershipFilter.value === 'all') return 'Todos';
  return (
    ownershipOptions.value.find((option) => option.value === ownershipFilter.value)?.label ??
    ownershipFilter.value
  );
});
const selectedFiscalYearLabel = computed(() => String(fiscalYear.value));

const isLoading = computed(() => incomeStore.loading.value || expenseStore.loading.value);
const firstError = computed(() => incomeStore.error.value || expenseStore.error.value);
const incomeEntries = computed(() => incomeStore.entries.value);
const expenseEntries = computed(() => expenseStore.entries.value);

type OwnerOption = { value: string; label: string };

function parseSharedOwnerShares(ownerLabel: string): { name: string; share: number }[] {
  const text = ownerLabel.trim();
  if (!text) return [];
  const match = text.match(/^Compartido\s*\((.*)\)$/i);
  if (!match?.[1]) return [];
  return match[1]
    .split(/\s*\/\s*/)
    .map((part) => {
      const piece = part.trim();
      const m = piece.match(/^(.*)\s+(\d+(?:[.,]\d+)?)\s*%$/);
      if (!m?.[1] || !m[2]) return null;
      const name = m[1].trim();
      const share = Number(m[2].replace(',', '.'));
      if (!name || !Number.isFinite(share) || share <= 0) return null;
      return { name, share };
    })
    .filter((row): row is { name: string; share: number } => row != null);
}

function ownerNamesFromLabel(ownerLabel: string): string[] {
  const text = ownerLabel.trim();
  if (!text) return [];
  const shared = parseSharedOwnerShares(text);
  if (shared.length > 0) return shared.map((row) => row.name);
  return [text];
}

function allocationFractionForOwnerLabel(ownerLabel: string, selectedOwner: string): number {
  if (selectedOwner === 'all') return 1;
  const text = ownerLabel.trim();
  if (!text) return 0;
  if (text.localeCompare(selectedOwner, 'es', { sensitivity: 'base' }) === 0) return 1;

  const shared = parseSharedOwnerShares(text);
  if (!shared.length) return 0;
  const totalShare = shared.reduce((sum, row) => sum + row.share, 0);
  const matchedShare = shared
    .filter((row) => row.name.localeCompare(selectedOwner, 'es', { sensitivity: 'base' }) === 0)
    .reduce((sum, row) => sum + row.share, 0);
  if (!Number.isFinite(matchedShare) || matchedShare <= 0) return 0;

  // Compatibility: older labels may encode shares as 0-1 fractions instead of 0-100 percentages.
  if (totalShare > 0 && totalShare <= 1.0001) {
    return clamp(matchedShare / totalShare, 0, 1);
  }
  if (totalShare > 0 && totalShare <= 100.0001) {
    return clamp(matchedShare / 100, 0, 1);
  }
  return clamp(matchedShare / totalShare, 0, 1);
}

const ownershipOptions = computed<OwnerOption[]>(() => {
  const names = new Set<string>();
  for (const entry of incomeEntries.value) {
    for (const name of ownerNamesFromLabel(entry.owner ?? '')) names.add(name);
  }
  for (const entry of expenseEntries.value) {
    for (const name of ownerNamesFromLabel(entry.owner ?? '')) names.add(name);
  }
  return Array.from(names)
    .sort((a, b) => a.localeCompare(b, 'es'))
    .map((name) => ({ value: name, label: name }));
});

watch(ownershipOptions, (options) => {
  if (ownershipFilter.value === 'all') return;
  if (!options.some((option) => option.value === ownershipFilter.value)) {
    ownershipFilter.value = 'all';
  }
});

function closePopoverFromClick(event: Event): void {
  const target = event.currentTarget as HTMLElement | null;
  const details = target?.closest('details') as HTMLDetailsElement | null;
  if (details) details.open = false;
}

function selectOwnershipFilterOption(value: string, event: Event): void {
  ownershipFilter.value = value;
  closePopoverFromClick(event);
}

function selectFiscalYearOption(year: number, event: Event): void {
  fiscalYear.value = year;
  closePopoverFromClick(event);
}

const ownerAdjustedIncomeEntries = computed(() =>
  incomeEntries.value
    .map((entry) => {
      const fraction = allocationFractionForOwnerLabel(entry.owner ?? '', ownershipFilter.value);
      return { ...entry, amountAnnual: entry.amountAnnual * fraction };
    })
    .filter((entry) => entry.amountAnnual > 0),
);

const ownerAdjustedExpenseEntries = computed(() =>
  expenseEntries.value
    .map((entry) => {
      const fraction = allocationFractionForOwnerLabel(entry.owner ?? '', ownershipFilter.value);
      return { ...entry, amountAnnual: entry.amountAnnual * fraction };
    })
    .filter((entry) => entry.amountAnnual > 0),
);

function matchesIncomeViewMode(
  entry: (typeof incomeEntries.value)[number],
  mode: BudgetEntryViewMode,
): boolean {
  if (mode === 'all') return true;
  return mode === 'recurrent' ? entry.incomeType === 'recurrent' : entry.incomeType === 'one_off';
}

function matchesExpenseViewMode(
  entry: (typeof expenseEntries.value)[number],
  mode: BudgetEntryViewMode,
): boolean {
  if (mode === 'all') return true;
  return mode === 'recurrent' ? entry.expenseType === 'recurrent' : entry.expenseType === 'one_off';
}

function sumPlanned<T extends { amountAnnual: number }>(entries: T[]): number {
  return entries.reduce(
    (sum, entry) => sum + (Number.isFinite(entry.amountAnnual) ? entry.amountAnnual : 0),
    0,
  );
}

const filteredIncomeEntries = computed(() =>
  ownerAdjustedIncomeEntries.value.filter((entry) =>
    matchesIncomeViewMode(entry, incomeViewMode.value),
  ),
);
const filteredExpenseEntries = computed(() =>
  ownerAdjustedExpenseEntries.value.filter((entry) =>
    matchesExpenseViewMode(entry, expenseViewMode.value),
  ),
);

const plannedIncomeTotal = computed(() => sumPlanned(filteredIncomeEntries.value));
const plannedExpenseTotal = computed(() => sumPlanned(filteredExpenseEntries.value));
const plannedBalanceTotal = computed(() => plannedIncomeTotal.value - plannedExpenseTotal.value);

const executionStatusLabel = computed(() => 'Pendiente modulo contabilidad');
const executionStatusDetail = computed(
  () =>
    'Las barras de ejecucion se activaran cuando exista el read-model agregado del modulo de contabilidad (hito 14).',
);

function formatMoney(value: number, decimals = 2): string {
  return new Intl.NumberFormat('es-ES', {
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
    useGrouping: true,
  }).format(Number.isFinite(value) ? value : 0);
}

function formatPercent(value: number | null, decimals = 0): string {
  if (value == null || !Number.isFinite(value)) return '-';
  return new Intl.NumberFormat('es-ES', {
    style: 'percent',
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(value);
}

function formatCompactMoney(value: number): string {
  const abs = Math.abs(value);
  if (abs >= 1_000_000) return `${formatMoney(value / 1_000_000, 1)} M`;
  if (abs >= 1_000) return `${formatMoney(value / 1_000, 1)} k`;
  return formatMoney(value, 0);
}

function clamp(value: number, min: number, max: number): number {
  return Math.min(max, Math.max(min, value));
}

function hashToUnitInterval(input: string): number {
  let hash = 0;
  for (let i = 0; i < input.length; i++) {
    hash = (hash * 31 + input.charCodeAt(i)) >>> 0;
  }
  return (hash % 1000) / 1000;
}

function executionToneFor(sectionId: BudgetSectionModel['id'], ratio: number): BudgetExecutionTone {
  if (!Number.isFinite(ratio) || ratio <= 0) return 'neutral';
  if (sectionId === 'expense') {
    if (ratio > 1) return 'danger';
    if (ratio > 0.85) return 'warn';
    return 'good';
  }
  if (ratio >= 1) return 'good';
  if (ratio >= 0.85) return 'warn';
  return 'danger';
}

function mockExecutionRatio(sectionId: BudgetSectionModel['id'], seedKey: string): number {
  const u = hashToUnitInterval(seedKey);
  if (sectionId === 'expense') {
    if (u < 0.34) return 0.62 + u * 0.55;
    if (u < 0.72) return 0.86 + (u - 0.34) * 0.34;
    return 1.01 + (u - 0.72) * 0.62;
  }
  if (u < 0.34) return 0.62 + u * 0.5;
  if (u < 0.72) return 0.85 + (u - 0.34) * 0.34;
  return 1.0 + (u - 0.72) * 0.72;
}

function executionPreview(
  sectionId: BudgetSectionModel['id'],
  seedKey: string,
): BudgetExecutionPreview {
  const ratio = mockExecutionRatio(sectionId, seedKey);
  return {
    ratio,
    widthPct: clamp(ratio * 100, 8, 100),
    tone: executionToneFor(sectionId, ratio),
    overflow: ratio > 1,
  };
}

function aggregateBudgetRows<
  T extends { category: string; subcategory: string; amountAnnual: number },
>(
  entries: T[],
  categoryLabels: Map<string, string>,
  subcategoryLabels: Map<string, string>,
): BudgetGroup[] {
  const bucket = new Map<string, BudgetRow>();

  for (const entry of entries) {
    const amount = Number(entry.amountAnnual ?? 0);
    if (!Number.isFinite(amount) || amount <= 0) continue;
    const key = `${entry.category}::${entry.subcategory}`;
    const prev = bucket.get(key);
    if (prev) {
      prev.plannedAnnual += amount;
      prev.itemsCount += 1;
      continue;
    }
    bucket.set(key, {
      key,
      categoryKey: entry.category,
      categoryLabel: categoryLabels.get(entry.category) ?? entry.category,
      subcategoryKey: entry.subcategory,
      subcategoryLabel: subcategoryLabels.get(entry.subcategory) ?? entry.subcategory,
      plannedAnnual: amount,
      itemsCount: 1,
    });
  }

  const rows = Array.from(bucket.values()).sort((a, b) => {
    if (b.plannedAnnual !== a.plannedAnnual) return b.plannedAnnual - a.plannedAnnual;
    return a.subcategoryLabel.localeCompare(b.subcategoryLabel, 'es');
  });

  const sectionTotal = rows.reduce((sum, row) => sum + row.plannedAnnual, 0);
  const byCategory = new Map<string, BudgetGroup>();
  for (const row of rows) {
    const group = byCategory.get(row.categoryKey);
    if (group) {
      group.plannedAnnual += row.plannedAnnual;
      group.rows.push(row);
      continue;
    }
    byCategory.set(row.categoryKey, {
      categoryKey: row.categoryKey,
      categoryLabel: row.categoryLabel,
      plannedAnnual: row.plannedAnnual,
      shareOfSection: 0,
      rows: [row],
    });
  }

  return Array.from(byCategory.values())
    .map((group) => ({
      ...group,
      rows: group.rows.sort((a, b) => b.plannedAnnual - a.plannedAnnual),
      shareOfSection: sectionTotal > 0 ? group.plannedAnnual / sectionTotal : 0,
    }))
    .sort((a, b) => b.plannedAnnual - a.plannedAnnual);
}

const incomeGroups = computed(() =>
  aggregateBudgetRows(filteredIncomeEntries.value, incomeCategoryLabels, incomeSubcategoryLabels),
);
const expenseGroups = computed(() =>
  aggregateBudgetRows(
    filteredExpenseEntries.value,
    expenseCategoryLabels,
    expenseSubcategoryLabels,
  ),
);

function viewModeLabel(mode: BudgetEntryViewMode): string {
  if (mode === 'recurrent') return 'Solo recurrentes';
  if (mode === 'one_off') return 'Solo puntuales';
  return 'Todos';
}

function isSectionExpanded(sectionId: BudgetSectionModel['id']): boolean {
  return sectionId === 'income' ? incomeDetailsExpanded.value : expenseDetailsExpanded.value;
}

function toggleSectionExpanded(sectionId: BudgetSectionModel['id']): void {
  if (sectionId === 'income') {
    incomeDetailsExpanded.value = !incomeDetailsExpanded.value;
    return;
  }
  expenseDetailsExpanded.value = !expenseDetailsExpanded.value;
}

const sections = computed<BudgetSectionModel[]>(() => [
  {
    id: 'income',
    title: 'Ingresos',
    subtitle: 'Detalle previsto por categorias y subcategorias del balance anual',
    emptyMessage: 'No hay ingresos anuales cargados para este ejercicio.',
    toneClass: 'ui-budget-section-income',
    totalAnnual: plannedIncomeTotal.value,
    filterMode: incomeViewMode.value,
    categoryCount: incomeGroups.value.length,
    subcategoryCount: incomeGroups.value.reduce((sum, group) => sum + group.rows.length, 0),
    groups: incomeGroups.value,
  },
  {
    id: 'expense',
    title: 'Gastos',
    subtitle: 'Detalle previsto por categorias y subcategorias del balance anual',
    emptyMessage: 'No hay gastos anuales cargados para este ejercicio.',
    toneClass: 'ui-budget-section-expense',
    totalAnnual: plannedExpenseTotal.value,
    filterMode: expenseViewMode.value,
    categoryCount: expenseGroups.value.length,
    subcategoryCount: expenseGroups.value.reduce((sum, group) => sum + group.rows.length, 0),
    groups: expenseGroups.value,
  },
]);

const hasAnyPlannedData = computed(
  () => plannedIncomeTotal.value > 0 || plannedExpenseTotal.value > 0,
);

const activeViewSummary = computed(
  () =>
    `Ingresos: ${viewModeLabel(incomeViewMode.value)} · Gastos: ${viewModeLabel(expenseViewMode.value)}`,
);

async function refreshBudgetData(year = fiscalYear.value): Promise<void> {
  await Promise.all([incomeStore.loadAll(year), expenseStore.loadAll(year)]);
}

watch(
  fiscalYear,
  (year) => {
    void refreshBudgetData(year);
  },
  { immediate: true },
);
</script>

<template>
  <div class="container ui-pro-page relative">
    <section class="card ui-pro-panel ui-budget-hero">
      <div class="ui-budget-hero-header">
        <div>
          <p class="ui-pro-kicker">Presupuesto</p>
          <h1 class="ui-budget-title">Dashboard de presupuesto</h1>
          <p class="ui-budget-subtitle">
            Compara el presupuesto anual previsto con la ejecucion real (cuando se active
            contabilidad).
          </p>
        </div>

        <div class="ui-budget-toolbar">
          <label class="ui-budget-owner-picker">
            <span>Titularidad</span>
            <details class="ui-select-popover">
              <summary class="ui-select-popover-trigger">
                <span class="ui-select-popover-text">{{ selectedOwnershipFilterLabel }}</span>
                <span class="ui-select-popover-caret" aria-hidden="true">⌄</span>
              </summary>
              <div class="ui-select-popover-menu" role="listbox" aria-label="Titularidad">
                <button
                  type="button"
                  class="ui-select-popover-option"
                  :class="{ 'ui-select-popover-option-active': ownershipFilter === 'all' }"
                  @click="selectOwnershipFilterOption('all', $event)"
                >
                  Todos
                </button>
                <button
                  v-for="ownerOption in ownershipOptions"
                  :key="ownerOption.value"
                  type="button"
                  class="ui-select-popover-option"
                  :class="{
                    'ui-select-popover-option-active': ownershipFilter === ownerOption.value,
                  }"
                  @click="selectOwnershipFilterOption(ownerOption.value, $event)"
                >
                  {{ ownerOption.label }}
                </button>
              </div>
            </details>
          </label>
          <label class="ui-budget-year-picker">
            <span>Ejercicio</span>
            <details class="ui-select-popover" :class="{ 'opacity-60': isLoading }">
              <summary class="ui-select-popover-trigger">
                <span class="ui-select-popover-text">{{ selectedFiscalYearLabel }}</span>
                <span class="ui-select-popover-caret" aria-hidden="true">⌄</span>
              </summary>
              <div class="ui-select-popover-menu" role="listbox" aria-label="Ejercicio">
                <button
                  v-for="year in fiscalYearOptions"
                  :key="year"
                  type="button"
                  class="ui-select-popover-option"
                  :class="{ 'ui-select-popover-option-active': fiscalYear === year }"
                  :disabled="isLoading"
                  @click="selectFiscalYearOption(year, $event)"
                >
                  {{ year }}
                </button>
              </div>
            </details>
          </label>
        </div>
      </div>

      <div class="ui-budget-kpi-grid">
        <article class="ui-budget-kpi ui-budget-kpi-income">
          <div class="ui-budget-kpi-label">Ingresos previstos</div>
          <div class="ui-budget-kpi-value">{{ formatMoney(plannedIncomeTotal) }} EUR</div>
          <div class="ui-budget-kpi-meta">
            {{ formatMoney(plannedIncomeTotal / 12) }} EUR/mes (promedio) ·
            {{ viewModeLabel(incomeViewMode) }}
          </div>
        </article>

        <article class="ui-budget-kpi ui-budget-kpi-expense">
          <div class="ui-budget-kpi-label">Gastos previstos</div>
          <div class="ui-budget-kpi-value">{{ formatMoney(plannedExpenseTotal) }} EUR</div>
          <div class="ui-budget-kpi-meta">
            {{ formatMoney(plannedExpenseTotal / 12) }} EUR/mes (promedio) ·
            {{ viewModeLabel(expenseViewMode) }}
          </div>
        </article>

        <article
          class="ui-budget-kpi"
          :class="
            plannedBalanceTotal >= 0 ? 'ui-budget-kpi-balance-good' : 'ui-budget-kpi-balance-bad'
          "
        >
          <div class="ui-budget-kpi-label">Saldo anual previsto</div>
          <div class="ui-budget-kpi-value">{{ formatMoney(plannedBalanceTotal) }} EUR</div>
          <div class="ui-budget-kpi-meta">
            {{
              plannedIncomeTotal > 0
                ? `${formatPercent(plannedBalanceTotal / plannedIncomeTotal, 0)} sobre ingresos`
                : 'Sin base de ingresos'
            }}
          </div>
        </article>

        <article class="ui-budget-kpi ui-budget-kpi-muted">
          <div class="ui-budget-kpi-label">Estado de ejecucion</div>
          <div class="ui-budget-kpi-value ui-budget-kpi-value-sm">{{ executionStatusLabel }}</div>
          <div class="ui-budget-kpi-meta">
            {{ executionStatusDetail }}
            <br />
            {{ activeViewSummary }}
          </div>
        </article>
      </div>
    </section>

    <div v-if="firstError" class="alert mt-3">
      {{ firstError }}
    </div>

    <section v-if="!hasAnyPlannedData && !isLoading" class="card ui-pro-panel ui-budget-empty mt-3">
      <h2 class="mt-0">Sin presupuesto anual para {{ fiscalYear }}</h2>
      <p class="subtle mb-0">
        Carga primero `Ingresos anuales` y `Gastos anuales` en `Introduccion de datos` para ver el
        dashboard.
      </p>
      <RouterLink class="ui-budget-empty-link" to="/introduccion-datos">
        Ir a Introduccion de datos
      </RouterLink>
    </section>

    <section
      v-for="section in sections"
      :key="section.id"
      class="card ui-pro-panel ui-budget-section mt-3"
      :class="section.toneClass"
    >
      <div class="ui-budget-section-header">
        <div>
          <h2 class="ui-budget-section-title">{{ section.title }}</h2>
          <p class="ui-budget-section-subtitle">{{ section.subtitle }}</p>
        </div>
        <div class="ui-budget-section-header-side">
          <div class="ui-budget-section-controls">
            <button
              v-if="section.groups.length"
              type="button"
              class="ui-budget-detail-toggle"
              :aria-expanded="isSectionExpanded(section.id)"
              @click="toggleSectionExpanded(section.id)"
            >
              <span class="ui-budget-detail-toggle-icon" aria-hidden="true">
                {{ isSectionExpanded(section.id) ? '−' : '+' }}
              </span>
              <span>
                {{
                  isSectionExpanded(section.id)
                    ? 'Ocultar detalle'
                    : `Ver detalle (${section.categoryCount} categorias · ${section.subcategoryCount} subcategorias)`
                }}
              </span>
            </button>

            <div
              class="ui-budget-filter-segment"
              role="tablist"
              :aria-label="`Filtro de ${section.title}`"
            >
              <button
                type="button"
                class="ui-budget-filter-btn"
                :class="{ 'ui-budget-filter-btn-active': section.filterMode === 'all' }"
                @click="
                  section.id === 'income' ? (incomeViewMode = 'all') : (expenseViewMode = 'all')
                "
              >
                Todos
              </button>
              <button
                type="button"
                class="ui-budget-filter-btn"
                :class="{ 'ui-budget-filter-btn-active': section.filterMode === 'recurrent' }"
                @click="
                  section.id === 'income'
                    ? (incomeViewMode = 'recurrent')
                    : (expenseViewMode = 'recurrent')
                "
              >
                Recurrentes
              </button>
              <button
                type="button"
                class="ui-budget-filter-btn"
                :class="{ 'ui-budget-filter-btn-active': section.filterMode === 'one_off' }"
                @click="
                  section.id === 'income'
                    ? (incomeViewMode = 'one_off')
                    : (expenseViewMode = 'one_off')
                "
              >
                Puntuales
              </button>
            </div>
          </div>

          <div class="ui-budget-section-total">
            <strong>{{ formatMoney(section.totalAnnual) }} EUR</strong>
            <small>{{ formatMoney(section.totalAnnual / 12) }} EUR/mes</small>
          </div>
        </div>
      </div>

      <div class="ui-budget-evolution-card">
        <div class="ui-budget-evolution-head">
          <div>
            <h3>Evolucion ejecutada (barras)</h3>
            <p>
              Preparado para comparar `Previsto` vs `Ejecutado` por mes. Actualmente en modo
              placeholder hasta implementar contabilidad.
            </p>
          </div>
          <span class="ui-budget-pill">Pendiente contabilidad</span>
        </div>

        <div class="ui-budget-evolution-bars" aria-label="Placeholder de barras de evolucion">
          <div
            v-for="month in monthLabels"
            :key="`${section.id}-${month}`"
            class="ui-budget-month-col"
          >
            <div class="ui-budget-month-rail">
              <div class="ui-budget-month-plan" />
              <div class="ui-budget-month-exec-pending" />
            </div>
            <span class="ui-budget-month-label">{{ month }}</span>
          </div>
        </div>

        <div class="ui-budget-evolution-legend">
          <span><i class="ui-budget-legend-dot ui-budget-legend-plan" /> Previsto</span>
          <span
            ><i class="ui-budget-legend-dot ui-budget-legend-exec" /> Ejecutado (pendiente)</span
          >
          <span>
            Base mensual orientativa:
            <strong>{{ formatCompactMoney(section.totalAnnual / 12) }} EUR</strong>
          </span>
        </div>
      </div>

      <div v-if="section.groups.length && isSectionExpanded(section.id)" class="ui-budget-groups">
        <article
          v-for="group in section.groups"
          :key="`${section.id}-${group.categoryKey}`"
          class="ui-budget-group"
        >
          <header class="ui-budget-group-header">
            <div class="ui-budget-group-title-wrap">
              <div class="ui-budget-group-kicker">Categoria</div>
              <h3>{{ group.categoryLabel }}</h3>
              <p>
                {{ group.rows.length }} subcategorias ·
                {{ formatPercent(group.shareOfSection, 0) }} de {{ section.title.toLowerCase() }}
              </p>
              <div class="ui-budget-inline-progress" aria-label="Placeholder ejecucion categoria">
                <div class="ui-budget-inline-progress-labels">
                  <span>Previsto vs Ejecutado</span>
                  <span>
                    Pendiente contabilidad
                    <span
                      class="ui-budget-inline-progress-preview-pill"
                      :class="`ui-budget-inline-progress-preview-pill-${
                        executionPreview(section.id, `group:${group.categoryKey}`).tone
                      }`"
                    >
                      {{
                        formatPercent(
                          executionPreview(section.id, `group:${group.categoryKey}`).ratio,
                          0,
                        )
                      }}
                    </span>
                  </span>
                </div>
                <div class="ui-budget-inline-progress-track ui-budget-inline-progress-track-lg">
                  <div
                    class="ui-budget-inline-progress-fill"
                    :class="`ui-budget-inline-progress-fill-${executionPreview(section.id, `group:${group.categoryKey}`).tone}`"
                    :style="{
                      width: `${executionPreview(section.id, `group:${group.categoryKey}`).widthPct}%`,
                    }"
                  />
                  <span
                    v-if="executionPreview(section.id, `group:${group.categoryKey}`).overflow"
                    class="ui-budget-inline-progress-overflow-marker"
                    aria-hidden="true"
                  />
                </div>
              </div>
            </div>
            <div class="ui-budget-group-amount">{{ formatMoney(group.plannedAnnual) }} EUR</div>
          </header>

          <ul class="ui-budget-rows">
            <li v-for="row in group.rows" :key="row.key" class="ui-budget-row">
              <div class="ui-budget-row-main">
                <div class="ui-budget-row-kicker">Subcategoria</div>
                <div class="ui-budget-row-title">{{ row.subcategoryLabel }}</div>
                <div class="ui-budget-row-meta">
                  {{ row.itemsCount }} registro{{ row.itemsCount === 1 ? '' : 's' }} ·
                  {{ formatMoney(row.plannedAnnual / 12) }} EUR/mes previsto
                </div>
                <div
                  class="ui-budget-inline-progress ui-budget-inline-progress-row"
                  aria-label="Placeholder ejecucion subcategoria"
                >
                  <div class="ui-budget-inline-progress-track">
                    <div
                      class="ui-budget-inline-progress-fill"
                      :class="`ui-budget-inline-progress-fill-${executionPreview(section.id, `row:${row.key}`).tone}`"
                      :style="{
                        width: `${executionPreview(section.id, `row:${row.key}`).widthPct}%`,
                      }"
                    />
                    <span
                      v-if="executionPreview(section.id, `row:${row.key}`).overflow"
                      class="ui-budget-inline-progress-overflow-marker"
                      aria-hidden="true"
                    />
                  </div>
                  <div class="ui-budget-inline-progress-caption">
                    Ejecucion pendiente · preview
                    <span
                      :class="`ui-budget-inline-progress-caption-tone-${
                        executionPreview(section.id, `row:${row.key}`).tone
                      }`"
                    >
                      {{ formatPercent(executionPreview(section.id, `row:${row.key}`).ratio, 0) }}
                    </span>
                  </div>
                </div>
              </div>
              <div class="ui-budget-row-metrics">
                <div class="ui-budget-row-metric">
                  <span>Previsto</span>
                  <strong>{{ formatMoney(row.plannedAnnual) }} EUR</strong>
                </div>
                <div class="ui-budget-row-metric">
                  <span>Ejecutado</span>
                  <strong
                    class="ui-budget-pending-text"
                    :class="`ui-budget-pending-text-${executionPreview(section.id, `row:${row.key}`).tone}`"
                  >
                    Pendiente
                  </strong>
                </div>
                <div class="ui-budget-row-metric">
                  <span>Desviacion</span>
                  <strong
                    class="ui-budget-pending-text"
                    :class="`ui-budget-pending-text-${executionPreview(section.id, `row:${row.key}`).tone}`"
                  >
                    Pendiente
                  </strong>
                </div>
              </div>
            </li>
          </ul>
        </article>
      </div>
      <div
        v-else-if="section.groups.length && !isSectionExpanded(section.id)"
        class="ui-budget-detail-collapsed-note"
      >
        Vista compacta activa. Se muestran resumen y evolucion ejecutada. Pulsa en `Ver detalle`
        para desplegar categorias y subcategorias.
      </div>

      <div v-else class="subtle">
        {{ section.emptyMessage }}
        <template v-if="section.filterMode !== 'all'">
          Prueba con la vista `Todos` si quieres incluir movimientos puntuales.
        </template>
      </div>
    </section>

    <div v-if="isLoading" class="ui-status-line">Cargando presupuesto...</div>
  </div>
</template>

<style scoped>
.ui-budget-hero {
  display: grid;
  gap: 14px;
}

.ui-budget-hero-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 16px;
}

.ui-budget-title {
  margin: 2px 0 0;
  font-size: 1.1rem;
  font-weight: 700;
}

.ui-budget-subtitle {
  margin: 6px 0 0;
  color: rgba(255, 255, 255, 0.7);
  max-width: 68ch;
}

.ui-budget-toolbar {
  display: flex;
  align-items: center;
  gap: 10px;
}

.ui-budget-year-picker {
  display: grid;
  gap: 4px;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.72);
}

.ui-budget-owner-picker {
  display: grid;
  gap: 4px;
  font-size: 0.75rem;
  color: rgba(255, 255, 255, 0.72);
}

.ui-budget-year-picker select,
.ui-budget-owner-picker select {
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.14);
  background: rgba(255, 255, 255, 0.04);
  color: #fff;
  color-scheme: dark;
  padding: 8px 10px;
  min-width: 116px;
}

.ui-budget-owner-picker select {
  min-width: 180px;
}

.ui-budget-year-picker select option,
.ui-budget-owner-picker select option {
  background: rgb(15, 20, 31);
  color: rgb(244, 247, 252);
}

.ui-budget-kpi-grid {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 12px;
}

.ui-budget-kpi {
  grid-column: span 3;
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background:
    linear-gradient(180deg, rgba(255, 255, 255, 0.045), rgba(255, 255, 255, 0.02)),
    rgba(255, 255, 255, 0.015);
  padding: 12px;
  display: grid;
  gap: 6px;
}

.ui-budget-kpi-income {
  border-color: rgba(36, 208, 139, 0.22);
}

.ui-budget-kpi-expense {
  border-color: rgba(255, 131, 112, 0.22);
}

.ui-budget-kpi-balance-good {
  border-color: rgba(115, 234, 176, 0.25);
  box-shadow: inset 0 0 0 1px rgba(115, 234, 176, 0.06);
}

.ui-budget-kpi-balance-bad {
  border-color: rgba(255, 119, 95, 0.26);
  box-shadow: inset 0 0 0 1px rgba(255, 119, 95, 0.06);
}

.ui-budget-kpi-muted {
  border-style: dashed;
}

.ui-budget-kpi-label {
  font-size: 0.78rem;
  color: rgba(255, 255, 255, 0.74);
}

.ui-budget-kpi-value {
  font-size: 1.15rem;
  font-weight: 700;
  line-height: 1.1;
}

.ui-budget-kpi-value-sm {
  font-size: 0.98rem;
}

.ui-budget-kpi-meta {
  color: rgba(255, 255, 255, 0.68);
  font-size: 0.76rem;
  line-height: 1.35;
}

.ui-budget-empty {
  display: grid;
  gap: 10px;
}

.ui-budget-empty-link {
  width: fit-content;
  padding: 8px 12px;
  border-radius: 10px;
  border: 1px solid rgba(120, 241, 212, 0.28);
  color: #ccfff1;
  text-decoration: none;
  background: rgba(55, 191, 163, 0.08);
}

.ui-budget-section {
  display: grid;
  gap: 14px;
}

.ui-budget-section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.ui-budget-section-header-side {
  display: grid;
  gap: 8px;
  justify-items: end;
}

.ui-budget-section-controls {
  display: flex;
  align-items: center;
  justify-content: flex-end;
  gap: 8px;
  width: 100%;
}

.ui-budget-filter-segment {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px;
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.1);
  background: rgba(255, 255, 255, 0.02);
}

.ui-budget-filter-btn {
  border: none;
  background: transparent;
  color: rgba(255, 255, 255, 0.72);
  font-size: 0.74rem;
  padding: 6px 9px;
  border-radius: 8px;
  cursor: pointer;
}

.ui-budget-filter-btn:hover {
  background: rgba(255, 255, 255, 0.04);
  color: rgba(255, 255, 255, 0.88);
}

.ui-budget-filter-btn-active {
  background: rgba(110, 209, 255, 0.14);
  color: #def6ff;
  box-shadow: inset 0 0 0 1px rgba(110, 209, 255, 0.16);
}

.ui-budget-section-title {
  margin: 0;
  font-size: 1.08rem;
  font-weight: 700;
  color: rgba(255, 255, 255, 0.96);
}

.ui-budget-section-subtitle {
  margin: 4px 0 0;
  color: rgba(255, 255, 255, 0.68);
  font-size: 0.82rem;
}

.ui-budget-section-total {
  display: grid;
  gap: 2px;
  text-align: right;
  color: rgba(255, 255, 255, 0.76);
  font-size: 0.76rem;
}

.ui-budget-section-total strong {
  color: #fff;
  font-size: 0.98rem;
}

.ui-budget-section-total small {
  color: rgba(255, 255, 255, 0.6);
}

.ui-budget-section-income .ui-budget-section-title {
  color: rgba(167, 255, 228, 0.98);
  text-shadow: 0 0 0 transparent;
}

.ui-budget-section-expense .ui-budget-section-title {
  color: rgba(255, 214, 206, 0.98);
  text-shadow: 0 0 0 transparent;
}

.ui-budget-detail-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  justify-content: center;
  width: fit-content;
  margin-left: 0;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.02);
  color: rgba(255, 255, 255, 0.9);
  font-size: 0.78rem;
  padding: 6px 10px;
  cursor: pointer;
}

.ui-budget-detail-toggle:hover {
  background: rgba(255, 255, 255, 0.04);
}

.ui-budget-detail-toggle-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 18px;
  height: 18px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.16);
  font-size: 0.8rem;
  line-height: 1;
}

.ui-budget-evolution-card {
  border-radius: 14px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  padding: 12px;
  display: grid;
  gap: 10px;
}

.ui-budget-evolution-head {
  display: flex;
  justify-content: space-between;
  gap: 10px;
  align-items: flex-start;
}

.ui-budget-evolution-head h3 {
  margin: 0;
  font-size: 0.92rem;
}

.ui-budget-evolution-head p {
  margin: 4px 0 0;
  color: rgba(255, 255, 255, 0.66);
  font-size: 0.75rem;
  max-width: 72ch;
}

.ui-budget-pill {
  white-space: nowrap;
  border-radius: 999px;
  padding: 5px 9px;
  border: 1px dashed rgba(255, 255, 255, 0.2);
  color: rgba(255, 255, 255, 0.78);
  font-size: 0.72rem;
}

.ui-budget-evolution-bars {
  display: grid;
  grid-template-columns: repeat(12, minmax(0, 1fr));
  gap: 8px;
  align-items: end;
}

.ui-budget-month-col {
  display: grid;
  gap: 6px;
  justify-items: center;
}

.ui-budget-month-rail {
  height: 96px;
  width: 100%;
  min-width: 12px;
  border-radius: 10px;
  border: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.02);
  padding: 6px 4px;
  display: flex;
  flex-direction: column;
  justify-content: flex-end;
  gap: 4px;
}

.ui-budget-month-plan {
  height: 38%;
  border-radius: 6px;
  background: linear-gradient(180deg, rgba(110, 209, 255, 0.28), rgba(110, 209, 255, 0.12));
  border: 1px solid rgba(110, 209, 255, 0.2);
}

.ui-budget-month-exec-pending {
  height: 22%;
  border-radius: 6px;
  border: 1px dashed rgba(255, 255, 255, 0.24);
  background-image: repeating-linear-gradient(
    135deg,
    rgba(255, 255, 255, 0.08) 0 4px,
    rgba(255, 255, 255, 0.02) 4px 8px
  );
}

.ui-budget-month-label {
  font-size: 0.68rem;
  color: rgba(255, 255, 255, 0.68);
}

.ui-budget-evolution-legend {
  display: flex;
  flex-wrap: wrap;
  gap: 10px 14px;
  color: rgba(255, 255, 255, 0.72);
  font-size: 0.74rem;
}

.ui-budget-legend-dot {
  display: inline-block;
  width: 9px;
  height: 9px;
  border-radius: 999px;
  margin-right: 5px;
  vertical-align: -1px;
}

.ui-budget-legend-plan {
  background: rgba(110, 209, 255, 0.7);
}

.ui-budget-legend-exec {
  background: rgba(255, 255, 255, 0.2);
  border: 1px dashed rgba(255, 255, 255, 0.35);
}

.ui-budget-groups {
  display: grid;
  gap: 12px;
}

.ui-budget-group {
  border-radius: 12px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.02);
  overflow: hidden;
}

.ui-budget-group-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  padding: 12px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  background: rgba(255, 255, 255, 0.01);
}

.ui-budget-group-title-wrap {
  display: grid;
  gap: 4px;
  width: 100%;
  min-width: 0;
}

.ui-budget-group-kicker {
  font-size: 0.72rem;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--muted);
  font-weight: 600;
}

.ui-budget-group-header h3 {
  margin: 0;
  font-size: 1.18rem;
  line-height: 1.2;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.ui-budget-group-header p {
  margin: 0;
  color: var(--muted);
  font-size: 0.82rem;
}

.ui-budget-inline-progress {
  display: grid;
  gap: 4px;
  margin-top: 8px;
}

.ui-budget-inline-progress-row {
  margin-top: 6px;
  max-width: 340px;
}

.ui-budget-inline-progress-labels {
  display: flex;
  justify-content: space-between;
  gap: 8px;
  color: var(--muted);
  font-size: 0.76rem;
  align-items: center;
}

.ui-budget-inline-progress-track {
  position: relative;
  height: 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.1);
  overflow: hidden;
}

.ui-budget-inline-progress-track-lg {
  height: 10px;
  max-width: 520px;
}

.ui-budget-inline-progress-fill {
  position: absolute;
  inset: 0 auto 0 0;
  height: 100%;
  border-radius: 999px;
  display: block;
}

.ui-budget-inline-progress-fill-neutral {
  background: rgba(255, 255, 255, 0.34);
}

.ui-budget-inline-progress-fill-good {
  background: hsl(142 71% 48%);
}

.ui-budget-inline-progress-fill-warn {
  background: hsl(56 92% 49%);
}

.ui-budget-inline-progress-fill-danger {
  background: hsl(0 82% 52%);
}

.ui-budget-inline-progress-overflow-marker {
  position: absolute;
  top: 0;
  bottom: 0;
  right: 0;
  width: 2px;
  background: rgba(255, 255, 255, 0.92);
  opacity: 0.95;
}

.ui-budget-inline-progress-preview-pill {
  display: inline-flex;
  align-items: center;
  margin-left: 6px;
  padding: 2px 6px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.03);
  font-size: 0.7rem;
  font-weight: 600;
}

.ui-budget-inline-progress-preview-pill-neutral {
  color: rgba(255, 255, 255, 0.85);
}

.ui-budget-inline-progress-preview-pill-good {
  color: rgba(134, 239, 172, 0.98);
  border-color: rgba(74, 222, 128, 0.28);
  background: rgba(74, 222, 128, 0.1);
}

.ui-budget-inline-progress-preview-pill-warn {
  color: rgba(253, 224, 71, 0.98);
  border-color: rgba(250, 204, 21, 0.28);
  background: rgba(250, 204, 21, 0.08);
}

.ui-budget-inline-progress-preview-pill-danger {
  color: rgba(252, 165, 165, 0.98);
  border-color: rgba(239, 68, 68, 0.28);
  background: rgba(239, 68, 68, 0.08);
}

.ui-budget-inline-progress-caption {
  color: var(--muted);
  font-size: 0.74rem;
}

.ui-budget-inline-progress-caption-tone-neutral {
  color: rgba(255, 255, 255, 0.82);
}

.ui-budget-inline-progress-caption-tone-good {
  color: rgba(134, 239, 172, 0.95);
}

.ui-budget-inline-progress-caption-tone-warn {
  color: rgba(253, 224, 71, 0.95);
}

.ui-budget-inline-progress-caption-tone-danger {
  color: rgba(252, 165, 165, 0.95);
}

.ui-budget-group-amount {
  font-weight: 700;
  font-size: 1.05rem;
  white-space: nowrap;
  align-self: center;
  color: rgba(255, 255, 255, 0.96);
}

.ui-budget-rows {
  list-style: none;
  margin: 0;
  padding: 0;
}

.ui-budget-row {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px;
  border-top: 1px solid rgba(255, 255, 255, 0.05);
  background: rgba(255, 255, 255, 0.01);
}

.ui-budget-row:first-child {
  border-top: none;
}

.ui-budget-row-main {
  min-width: 0;
  width: 100%;
}

.ui-budget-row-kicker {
  font-size: 0.72rem;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  margin-bottom: 2px;
}

.ui-budget-row-title {
  font-weight: 600;
  font-size: 0.96rem;
  color: rgba(255, 255, 255, 0.96);
  letter-spacing: -0.01em;
}

.ui-budget-row-meta {
  margin-top: 3px;
  color: var(--muted);
  font-size: 0.76rem;
}

.ui-budget-row-metrics {
  display: grid;
  grid-template-columns: repeat(3, minmax(120px, auto));
  gap: 12px;
  align-items: start;
}

.ui-budget-row-metric {
  display: grid;
  gap: 2px;
  text-align: right;
  font-size: 0.82rem;
  color: var(--muted);
}

.ui-budget-row-metric strong {
  color: #fff;
  font-size: 0.9rem;
  font-weight: 700;
}

.ui-budget-pending-text {
  color: rgba(255, 255, 255, 0.78);
  font-weight: 600;
}

.ui-budget-pending-text-neutral {
  color: rgba(255, 255, 255, 0.78);
}

.ui-budget-pending-text-good {
  color: rgba(145, 255, 196, 0.96);
}

.ui-budget-pending-text-warn {
  color: rgba(255, 220, 126, 0.98);
}

.ui-budget-pending-text-danger {
  color: rgba(255, 146, 146, 0.98);
}

.ui-budget-detail-collapsed-note {
  border-radius: 12px;
  border: 1px dashed rgba(255, 255, 255, 0.12);
  background: rgba(255, 255, 255, 0.015);
  color: var(--muted);
  font-size: 0.82rem;
  padding: 10px 12px;
}

@media (max-width: 980px) {
  .ui-budget-kpi {
    grid-column: span 6;
  }

  .ui-budget-row {
    display: grid;
    gap: 8px;
  }

  .ui-budget-row-metrics {
    grid-template-columns: repeat(3, minmax(0, 1fr));
  }

  .ui-budget-inline-progress-row {
    max-width: none;
  }
}

@media (max-width: 720px) {
  .ui-budget-hero-header,
  .ui-budget-section-header,
  .ui-budget-evolution-head,
  .ui-budget-group-header {
    display: grid;
  }

  .ui-budget-section-header-side {
    justify-items: start;
  }

  .ui-budget-section-controls {
    justify-content: flex-start;
    flex-wrap: wrap;
  }

  .ui-budget-detail-toggle {
    margin-left: 0;
  }

  .ui-budget-toolbar {
    justify-content: flex-start;
  }

  .ui-budget-filter-segment {
    flex-wrap: wrap;
  }

  .ui-budget-kpi {
    grid-column: span 12;
  }

  .ui-budget-evolution-bars {
    gap: 6px;
  }

  .ui-budget-month-rail {
    height: 82px;
    padding: 5px 3px;
  }

  .ui-budget-row-metrics {
    grid-template-columns: 1fr;
  }

  .ui-budget-row-metric {
    text-align: left;
    border-top: 1px dashed rgba(255, 255, 255, 0.08);
    padding-top: 5px;
  }
}
</style>
