<script setup lang="ts">
import { computed, reactive, ref, watch } from 'vue';
import {
  ItemForm,
  ItemList,
  useNetWorthViewExtensions,
  useNetWorthViewState,
} from '@/domains/net-worth';
import { BaseModal } from '@/domains/ui';
import { useAnnualIncomeStore } from '@/domains/data-input/annualIncomeStore';
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
  addEntry,
  deleteEntry,
} = useAnnualIncomeStore('core');
const annualIncomeError = ref<string | null>(null);
const showIncomeModal = ref(false);
const expandedIncomeCats = ref<Set<string>>(new Set());
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
  amountInputPeriod: 'annual' as 'annual' | 'monthly',
  amountAnnual: '',
  currency: 'EUR',
  notes: '',
});

const annualSubcategoryOptions = computed(() =>
  incomeSubcategories.filter((row) => row.category === annualIncomeForm.category),
);
const filteredAnnualIncomeEntries = computed(() => annualIncomeEntries.value);

const filteredAnnualIncomeTotal = computed(() =>
  filteredAnnualIncomeEntries.value.reduce((sum, entry) => sum + entry.amountAnnual, 0),
);
const annualIncomeCount = computed(() => annualIncomeEntries.value.length);
const assetsCount = computed(() => store.assets.length);
const liabilitiesCount = computed(() => store.liabilities.length);
const hasIncomeData = computed(() => annualIncomeCount.value > 0);
const hasAssetData = computed(() => assetsCount.value > 0);
const hasLiabilityData = computed(() => liabilitiesCount.value > 0);
const hasCompleteDataInput = computed(
  () => hasIncomeData.value && hasAssetData.value && hasLiabilityData.value,
);
const dataInputCheckTitle = computed(() =>
  hasCompleteDataInput.value ? 'Check de datos: completo' : 'Check de datos: pendiente',
);
const dataInputSummary = computed(() => {
  const incomePart = hasIncomeData.value
    ? `${annualIncomeCount.value} ingresos registrados`
    : 'sin ingresos registrados';
  const assetsPart = hasAssetData.value
    ? `${assetsCount.value} activos registrados`
    : 'sin activos registrados';
  const liabilitiesPart = hasLiabilityData.value
    ? `${liabilitiesCount.value} pasivos registrados`
    : 'sin pasivos registrados';
  return `Estado actual: ${incomePart}, ${assetsPart} y ${liabilitiesPart}. Completa los tres bloques para un diagnostico patrimonial fiable.`;
});

watch(
  () => annualIncomeForm.category,
  () => {
    const first = annualSubcategoryOptions.value[0];
    if (!first) return;
    annualIncomeForm.subcategory = first.value;
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

const incomeCategoryOrder = new Map(
  incomeCategories.map((category, index) => [category.value, index]),
);

function incomeCategoryLabel(key: string): string {
  return incomeCategories.find((category) => category.value === key)?.label ?? key;
}

function incomeSubcategoryLabel(key: string): string {
  return incomeSubcategories.find((subcategory) => subcategory.value === key)?.label ?? key;
}

function incomeTypeLabel(type: 'recurrent' | 'one_off'): string {
  return type === 'recurrent' ? 'Recurrente' : 'Puntual';
}

function sumByCurrency(entries: AnnualIncomeEntry[]): Record<string, number> {
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

function isIncomeGroupExpanded(category: string): boolean {
  return expandedIncomeCats.value.has(category);
}

function toggleIncomeCategory(category: string): void {
  const next = new Set(expandedIncomeCats.value);
  if (next.has(category)) next.delete(category);
  else next.add(category);
  expandedIncomeCats.value = next;
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

function resetIncomeForm(): void {
  annualIncomeForm.category = 'salary';
  annualIncomeForm.subcategory = 'employee_salary';
  annualIncomeForm.name = '';
  annualIncomeForm.isRecurrent = true;
  annualIncomeForm.amountInputPeriod = 'annual';
  annualIncomeForm.amountAnnual = '';
  annualIncomeForm.currency = 'EUR';
  annualIncomeForm.notes = '';
}

function openIncomeModal(): void {
  annualIncomeError.value = null;
  showIncomeModal.value = true;
}

function closeIncomeModal(): void {
  showIncomeModal.value = false;
}

const amountInputPlaceholder = computed(() =>
  annualIncomeForm.amountInputPeriod === 'monthly' ? 'Importe mensual' : 'Importe anual',
);

watch(
  () => annualIncomeForm.isRecurrent,
  (isRecurrent) => {
    if (!isRecurrent) annualIncomeForm.amountInputPeriod = 'annual';
  },
);

async function submitAnnualIncome(): Promise<void> {
  const rawAmount = Number(String(annualIncomeForm.amountAnnual).replace(',', '.'));
  const normalizedAmount = Number.isFinite(rawAmount)
    ? annualIncomeForm.amountInputPeriod === 'monthly'
      ? Math.round(rawAmount * 12 * 100) / 100
      : rawAmount
    : annualIncomeForm.amountAnnual;

  const result = await addEntry(
    {
      name: annualIncomeForm.name,
      category: annualIncomeForm.category,
      subcategory: annualIncomeForm.subcategory,
      incomeType: annualIncomeForm.isRecurrent ? 'recurrent' : 'one_off',
      amountAnnual: String(normalizedAmount),
      fiscalYear: fiscalYear.value,
      currency: annualIncomeForm.currency,
      notes: annualIncomeForm.notes,
    },
    fiscalYear.value,
  );
  if (!result.ok) {
    annualIncomeError.value = result.error;
    return;
  }
  annualIncomeError.value = null;
  closeIncomeModal();
  resetIncomeForm();
}

async function removeAnnualIncome(id: number): Promise<void> {
  await deleteEntry(id, fiscalYear.value);
}

watch(
  fiscalYear,
  (year) => {
    loadAnnualIncome(year);
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
    </section>

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
              {{ formatMoneyAmount(filteredAnnualIncomeTotal, 'EUR') }}
            </div>
            <div class="nw-list-total-details">Ingresos del ejercicio {{ fiscalYear }}</div>
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
              @click="openIncomeModal"
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
                            :class="
                              entry.incomeType === 'recurrent'
                                ? 'income-rec-dot-recurrent'
                                : 'income-rec-dot-one-off'
                            "
                            aria-hidden="true"
                          ></span>
                          <span class="item-name-text">{{ entry.name }}</span>
                        </div>
                        <div class="nw-item-submeta">{{ incomeTypeLabel(entry.incomeType) }}</div>
                      </div>
                      <div class="nw-item-amount">
                        {{ formatMoneyAmount(entry.amountAnnual, entry.currency) }}
                      </div>
                      <div class="nw-item-actions">
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
        </div>
        <p class="subtle m-0">Proximamente en Milestone 08.</p>
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

    <BaseModal :open="showIncomeModal" title="Nuevo ingreso anual" @close="closeIncomeModal">
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
        <div
          class="grid items-center gap-2.5 md:col-span-2 md:grid-cols-[minmax(0,1fr)_auto_auto_120px]"
        >
          <input
            v-model="annualIncomeForm.amountAnnual"
            class="input ui-data-field"
            inputmode="decimal"
            :placeholder="amountInputPlaceholder"
          />
          <label class="checkbox-row whitespace-nowrap">
            <input v-model="annualIncomeForm.isRecurrent" type="checkbox" />
            Recurrente
          </label>
          <div class="grid justify-items-center gap-1">
            <button
              type="button"
              class="relative inline-flex h-[34px] w-[58px] items-center rounded-full border transition"
              :class="
                annualIncomeForm.amountInputPeriod === 'monthly'
                  ? 'border-teal-300/60 bg-teal-400/20'
                  : 'border-white/20 bg-white/5'
              "
              :disabled="!annualIncomeForm.isRecurrent"
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
            Guardar ingreso
          </button>
        </div>
      </div>
    </BaseModal>
  </div>
</template>
