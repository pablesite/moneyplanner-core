<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue';
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

const annualIncomeForm = reactive({
  name: '',
  category: 'salary' as IncomeCategoryKey,
  subcategory: 'employee_salary',
  owner: '',
  incomeType: 'recurrent' as 'recurrent' | 'one_off',
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

function resetIncomeForm(): void {
  annualIncomeForm.name = '';
  annualIncomeForm.category = 'salary';
  annualIncomeForm.subcategory = 'employee_salary';
  annualIncomeForm.owner = '';
  annualIncomeForm.incomeType = 'recurrent';
  annualIncomeForm.amountAnnual = '';
  annualIncomeForm.currency = 'EUR';
  annualIncomeForm.notes = '';
}

async function submitAnnualIncome(): Promise<void> {
  const result = await addEntry({
    name: annualIncomeForm.name,
    category: annualIncomeForm.category,
    subcategory: annualIncomeForm.subcategory,
    owner: annualIncomeForm.owner,
    incomeType: annualIncomeForm.incomeType,
    amountAnnual: annualIncomeForm.amountAnnual,
    currency: annualIncomeForm.currency,
    notes: annualIncomeForm.notes,
  });
  if (!result.ok) {
    annualIncomeError.value = result.error;
    return;
  }
  annualIncomeError.value = null;
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

    <section class="card">
      <h2 class="h2">Ingresos anuales</h2>
      <div class="ui-data-form-grid">
        <input
          v-model="annualIncomeForm.name"
          class="input ui-data-field"
          placeholder="Concepto (ej: CTN, Regalos Pablo)"
        />
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
          v-model="annualIncomeForm.owner"
          class="input ui-data-field"
          placeholder="Titular (opcional)"
        />
        <select v-model="annualIncomeForm.incomeType" class="select ui-data-field">
          <option value="recurrent">Recurrente</option>
          <option value="one_off">Puntual</option>
        </select>
        <input
          v-model="annualIncomeForm.amountAnnual"
          class="input ui-data-field"
          inputmode="decimal"
          placeholder="Importe anual"
        />
        <select v-model="annualIncomeForm.currency" class="select ui-data-field">
          <option value="EUR">EUR</option>
          <option value="USD">USD</option>
        </select>
        <button
          class="btn btn-primary ui-data-field px-[14px]"
          type="button"
          :disabled="annualIncomeLoading"
          @click="submitAnnualIncome"
        >
          Anadir ingreso
        </button>
      </div>

      <textarea
        v-model="annualIncomeForm.notes"
        class="textarea mt-2"
        rows="2"
        placeholder="Notas (opcional)"
      />

      <div v-if="annualIncomeError" class="alert mt-3">{{ annualIncomeError }}</div>
      <div v-else-if="annualIncomeApiError" class="alert mt-3">{{ annualIncomeApiError }}</div>

      <table class="ui-data-table mt-3">
        <thead>
          <tr>
            <th>Concepto</th>
            <th>Categoria</th>
            <th>Titular</th>
            <th>Tipo</th>
            <th>Importe anual</th>
            <th></th>
          </tr>
        </thead>
        <tbody>
          <tr v-for="entry in annualIncomeEntries" :key="entry.id">
            <td>
              <strong>{{ entry.name }}</strong>
              <div class="subtle">{{ entry.subcategory }}</div>
            </td>
            <td>
              {{
                incomeCategories.find((category) => category.value === entry.category)?.label ??
                entry.category
              }}
            </td>
            <td>{{ entry.owner || '-' }}</td>
            <td>{{ entry.incomeType === 'recurrent' ? 'Recurrente' : 'Puntual' }}</td>
            <td>{{ formatMoneyAmount(entry.amountAnnual, entry.currency) }}</td>
            <td class="ui-data-table-actions">
              <button
                class="icon-btn"
                title="Eliminar"
                :disabled="annualIncomeLoading"
                @click="removeAnnualIncome(entry.id)"
              >
                &#128465;
              </button>
            </td>
          </tr>
          <tr v-if="!annualIncomeEntries.length && !annualIncomeLoading">
            <td colspan="6" class="ui-table-empty">No hay ingresos anuales todavia.</td>
          </tr>
        </tbody>
      </table>

      <div v-if="annualIncomeLoading" class="ui-status-line mt-2">Cargando ingresos anuales...</div>

      <div class="mt-3 text-right">
        <strong>Total anual:</strong> {{ formatMoneyAmount(totalAnnual, 'EUR') }}
      </div>
    </section>
  </div>
</template>
