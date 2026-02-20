<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
import { BaseModal } from '@/domains/ui';
import { useAnnualIncomeStore } from '@/domains/data-input/annualIncomeStore';
import {
  incomeCategories,
  incomeSubcategories,
  type IncomeCategoryKey,
} from '@/domains/data-input/incomeTaxonomy';

const {
  entries: annualIncomeEntries,
  totalAnnual,
  loading: annualIncomeLoading,
  error: annualIncomeApiError,
  loadAll: loadAnnualIncome,
  addEntry,
  deleteEntry,
} = useAnnualIncomeStore('core');
const annualIncomeError = ref<string | null>(null);
const showIncomeModal = ref(false);

const annualIncomeForm = reactive({
  category: 'salary' as IncomeCategoryKey,
  subcategory: 'employee_salary',
  name: '',
  owner: '',
  isRecurrent: true,
  amountInputPeriod: 'annual' as 'annual' | 'monthly',
  amountAnnual: '',
  currency: 'EUR',
  notes: '',
});

const annualSubcategoryOptions = computed(() =>
  incomeSubcategories.filter((row) => row.category === annualIncomeForm.category),
);

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
    .map(([currency, amount]) => `${formatMoneyAmount(amount, currency)} ${currency}`)
    .join(' | ');
}

function incomeCategoryClass(category: string): string {
  return `income-cat-${category || 'other_income'}`;
}

const annualIncomeGroups = computed<AnnualIncomeGroup[]>(() => {
  const categoryMap = new Map<string, AnnualIncomeEntry[]>();

  for (const entry of annualIncomeEntries.value) {
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
  annualIncomeForm.owner = '';
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
      ? rawAmount * 12
      : rawAmount
    : annualIncomeForm.amountAnnual;

  const result = await addEntry({
    name: annualIncomeForm.name,
    category: annualIncomeForm.category,
    subcategory: annualIncomeForm.subcategory,
    owner: annualIncomeForm.owner,
    incomeType: annualIncomeForm.isRecurrent ? 'recurrent' : 'one_off',
    amountAnnual: String(normalizedAmount),
    currency: annualIncomeForm.currency,
    notes: annualIncomeForm.notes,
  });
  if (!result.ok) {
    annualIncomeError.value = result.error;
    return;
  }
  annualIncomeError.value = null;
  closeIncomeModal();
  resetIncomeForm();
}

async function removeAnnualIncome(id: number): Promise<void> {
  await deleteEntry(id);
}

onMounted(loadAnnualIncome);
</script>

<template>
  <div class="container ui-pro-page">
    <section class="card">
      <h1 class="h1 m-0">Introduccion de datos</h1>
      <p class="subtle mt-2">
        Esta vista centraliza los datos de entrada. Primer bloque habilitado: ingresos anuales.
      </p>
    </section>

    <div class="grid-2">
      <section class="card ui-pro-panel">
        <div class="nw-list-header">
          <div class="nw-list-header-left">
            <h2 class="card-header-title mt-0">Ingresos anuales</h2>
          </div>
          <div class="nw-list-header-right">
            <div class="nw-list-total-inline">{{ formatMoneyAmount(totalAnnual, 'EUR') }}</div>
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
                  <div class="nw-cat-total-primary">{{ formatTotalsLine(group.totals) }}</div>
                </div>
              </div>
            </div>

            <div class="subcat-list">
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
                          <span v-if="entry.owner" class="badge">{{ entry.owner }}</span>
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
      </section>

      <section class="card ui-pro-panel">
        <div class="nw-list-header">
          <div class="nw-list-header-left">
            <h2 class="card-header-title mt-0">Gastos anuales</h2>
          </div>
        </div>
        <p class="subtle m-0">Proximamente en Milestone 08.</p>
      </section>
    </div>

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
          class="input ui-data-field"
          placeholder="Concepto (ej: CTN, Regalos Pablo)"
        />
        <input
          v-model="annualIncomeForm.owner"
          class="input ui-data-field"
          placeholder="Titular (opcional)"
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
