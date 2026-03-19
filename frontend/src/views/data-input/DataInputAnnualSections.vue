<script setup lang="ts">
import { computed, unref } from 'vue';
import { AnnualEntryModalForm } from '@/domains/data-input';

const props = defineProps<{
  page: any;
}>();

const page = props.page;

const fiscalYearModel = computed({
  get: () => page.fiscalYear.value,
  set: (value: number) => {
    page.fiscalYear.value = value;
  },
});

const visibilityFilterModeModel = computed({
  get: () => page.visibilityFilterMode.value,
  set: (value: 'active' | 'archived' | 'all') => {
    page.visibilityFilterMode.value = value;
  },
});

const globalOwnershipFilterModel = computed({
  get: () => page.globalOwnershipFilter.value,
  set: (value: number | 'all' | 'unassigned') => {
    page.globalOwnershipFilter.value = value;
  },
});

const showIncomeModalModel = computed({
  get: () => page.showIncomeModal.value,
  set: (value: boolean) => {
    page.showIncomeModal.value = value;
  },
});

const showExpenseModalModel = computed({
  get: () => page.showExpenseModal.value,
  set: (value: boolean) => {
    page.showExpenseModal.value = value;
  },
});

const fiscalYearOptions = computed(() => unref(page.fiscalYearOptions) ?? []);
const globalOwnershipFilterOptions = computed(() => unref(page.globalOwnershipFilterOptions) ?? []);
const annualIncomeEntries = computed(() => unref(page.annualIncomeEntries) ?? []);
const filteredAnnualIncomeEntries = computed(() => unref(page.filteredAnnualIncomeEntries) ?? []);
const annualIncomeGroups = computed(() => unref(page.annualIncomeGroups) ?? []);
const annualExpenseEntries = computed(() => unref(page.annualExpenseEntries) ?? []);
const filteredAnnualExpenseEntries = computed(() => unref(page.filteredAnnualExpenseEntries) ?? []);
const annualExpenseGroups = computed(() => unref(page.annualExpenseGroups) ?? []);
</script>

<template>
  <div class="grid-2">
    <section class="section ui-flow-air md:col-span-2">
      <div class="nw-list-header ui-flow-air-header">
        <div class="nw-list-header-left ui-flow-air-left">
          <h2 class="ui-flow-air-title">Balance anual</h2>
          <div class="ui-flow-air-meta">
            <span class="ui-flow-air-subtitle">Ingresos y gastos</span>
            <select
              id="fiscal-year-income-expense"
              v-model.number="fiscalYearModel"
              class="select nw-select-sm ui-flow-air-year-select"
              aria-label="Ejercicio"
            >
              <option v-for="year in fiscalYearOptions" :key="year" :value="year">
                {{ year }}
              </option>
            </select>
            <select
              id="visibility-filter-mode"
              v-model="visibilityFilterModeModel"
              class="select nw-select-sm ui-flow-air-year-select"
              aria-label="Filtro de visibilidad"
            >
              <option value="active">Solo activos</option>
              <option value="archived">Solo archivados</option>
              <option value="all">Todos</option>
            </select>
            <select
              id="ownership-filter-mode"
              v-model="globalOwnershipFilterModel"
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
            {{ page.formatMoneyAmount(page.annualBalanceTotal, 'EUR') }}
          </div>
          <div class="nw-list-total-details">Balance del ejercicio {{ page.fiscalYear }}</div>
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
            {{ page.formatMoneyAmount(page.filteredAnnualIncomeTotal, 'EUR') }}
          </div>
          <button
            class="btn btn-primary btn-sm nw-list-add-icon-only"
            type="button"
            aria-label="Anadir ingreso"
            :disabled="page.annualIncomeLoading"
            @click="() => page.openIncomeModal()"
          >
            <span class="btn-icon">+</span>
          </button>
        </div>
      </div>

      <div class="nw-list-header-totals">
        <div class="nw-list-total-details">Total anual</div>
      </div>

      <div v-if="page.annualIncomeError" class="alert mt-3">{{ page.annualIncomeError }}</div>
      <div v-else-if="page.annualIncomeApiError" class="alert mt-3">
        {{ page.annualIncomeApiError }}
      </div>

      <div v-if="!annualIncomeEntries.length && !page.annualIncomeLoading" class="subtle mt-3">
        No hay ingresos anuales todavia.
      </div>

      <div
        v-else-if="!filteredAnnualIncomeEntries.length && !page.annualIncomeLoading"
        class="subtle mt-3"
      >
        No hay ingresos con este filtro.
      </div>

      <div v-else class="mt-3 grid gap-4">
        <section
          v-for="group in annualIncomeGroups"
          :key="group.category"
          class="nw-cat-block"
          :class="page.incomeCategoryClass(group.category)"
        >
          <div class="nw-cat-header">
            <div class="nw-cat-left">
              <div>{{ group.label }}</div>
              <span class="badge">{{ group.entries?.length ?? 0 }}</span>
            </div>
            <div class="nw-cat-right">
              <div class="nw-cat-total">
                <div class="nw-cat-total-primary">
                  {{ page.formatTotalsLine(group.totals) }}
                  <span v-if="page.incomeCategoryPercent(group.entries)" class="nw-cat-percent">
                    . {{ page.incomeCategoryPercent(group.entries) }}%
                  </span>
                </div>
              </div>
              <button
                class="icon-btn nw-cat-toggle"
                type="button"
                :aria-label="
                  page.isIncomeGroupExpanded(group.category)
                    ? 'Ocultar desglose'
                    : 'Mostrar desglose'
                "
                :title="
                  page.isIncomeGroupExpanded(group.category)
                    ? 'Ocultar desglose'
                    : 'Mostrar desglose'
                "
                @click="page.toggleIncomeCategory(group.category)"
              >
                <span
                  v-if="page.isIncomeGroupExpanded(group.category)"
                  class="icon"
                  aria-hidden="true"
                  >&#9662;</span
                >
                <span v-else class="icon" aria-hidden="true">&#9656;</span>
              </button>
            </div>
          </div>

          <div v-if="page.isIncomeGroupExpanded(group.category)" class="subcat-list">
            <div
              v-for="subgroup in group.subgroups ?? []"
              :key="`${group.category}:${subgroup.subcategory}`"
              class="nw-subcat-block"
            >
              <div class="nw-subcat-header">
                <div class="nw-subcat-title">{{ subgroup.label }}</div>
                <div class="nw-subcat-total">
                  <div class="nw-subcat-total-primary">
                    {{ page.formatTotalsLine(subgroup.totals) }}
                  </div>
                </div>
                <div class="nw-subcat-actions-spacer" aria-hidden="true"></div>
              </div>

              <ul class="list list-plain nw-subcat-items">
                <li v-for="entry in subgroup.entries ?? []" :key="entry.id">
                  <div class="nw-item-row income-item-row">
                    <div class="nw-item-main">
                      <div class="nw-item-name income-item-name">
                        <span
                          class="income-rec-dot"
                          :class="page.timeProfileDotClass(entry.timeProfile)"
                          aria-hidden="true"
                        ></span>
                        <span class="item-name-text">{{ entry.name }}</span>
                        <span v-if="entry.owner" class="badge">{{ entry.owner }}</span>
                      </div>
                      <div class="nw-item-submeta">
                        {{ page.timeProfileLabel(entry.timeProfile) }}
                        <template v-if="entry.eventGroup">
                          . Evento {{ page.eventGroupLabel(entry.eventGroup) }}</template
                        >
                      </div>
                    </div>
                    <div class="nw-item-amount">
                      {{ page.formatMoneyAmount(entry.amountAnnual, entry.currency) }}
                    </div>
                    <div class="nw-item-actions">
                      <button
                        class="icon-btn"
                        title="Editar"
                        :disabled="page.annualIncomeLoading"
                        @click="() => page.openIncomeModal(entry)"
                      >
                        &#9998;
                      </button>
                      <button
                        class="icon-btn"
                        title="Eliminar"
                        :disabled="page.annualIncomeLoading"
                        @click="page.removeAnnualIncome(entry.id)"
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

      <div v-if="page.annualIncomeLoading" class="ui-status-line mt-2">
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
            {{ page.formatMoneyAmount(page.filteredAnnualExpenseTotal, 'EUR') }}
          </div>
          <button
            class="btn btn-primary btn-sm nw-list-add-icon-only"
            type="button"
            aria-label="Anadir salida"
            :disabled="page.annualExpenseLoading"
            @click="() => page.openExpenseModal()"
          >
            <span class="btn-icon">+</span>
          </button>
        </div>
      </div>

      <div class="nw-list-header-totals">
        <div class="nw-list-total-details">Total anual</div>
      </div>

      <div v-if="page.annualExpenseError" class="alert mt-3">{{ page.annualExpenseError }}</div>
      <div v-else-if="page.annualExpenseApiError" class="alert mt-3">
        {{ page.annualExpenseApiError }}
      </div>

      <div v-if="!annualExpenseEntries.length && !page.annualExpenseLoading" class="subtle mt-3">
        No hay salidas anuales todavia.
      </div>

      <div
        v-else-if="!filteredAnnualExpenseEntries.length && !page.annualExpenseLoading"
        class="subtle mt-3"
      >
        No hay salidas con este filtro.
      </div>

      <div v-else class="mt-3 grid gap-4">
        <section
          v-for="group in annualExpenseGroups"
          :key="group.category"
          class="nw-cat-block"
          :class="page.expenseCategoryClass(group.category)"
        >
          <div class="nw-cat-header">
            <div class="nw-cat-left">
              <div>{{ group.label }}</div>
              <span class="badge">{{ group.entries?.length ?? 0 }}</span>
            </div>
            <div class="nw-cat-right">
              <div class="nw-cat-total">
                <div class="nw-cat-total-primary">
                  {{ page.formatTotalsLine(group.totals) }}
                  <span v-if="page.expenseCategoryPercent(group.entries)" class="nw-cat-percent">
                    . {{ page.expenseCategoryPercent(group.entries) }}%
                  </span>
                </div>
              </div>
              <button
                class="icon-btn nw-cat-toggle"
                type="button"
                :aria-label="
                  page.isExpenseGroupExpanded(group.category)
                    ? 'Ocultar desglose'
                    : 'Mostrar desglose'
                "
                :title="
                  page.isExpenseGroupExpanded(group.category)
                    ? 'Ocultar desglose'
                    : 'Mostrar desglose'
                "
                @click="page.toggleExpenseCategory(group.category)"
              >
                <span
                  v-if="page.isExpenseGroupExpanded(group.category)"
                  class="icon"
                  aria-hidden="true"
                  >&#9662;</span
                >
                <span v-else class="icon" aria-hidden="true">&#9656;</span>
              </button>
            </div>
          </div>

          <div v-if="page.isExpenseGroupExpanded(group.category)" class="subcat-list">
            <div
              v-for="subgroup in group.subgroups ?? []"
              :key="`${group.category}:${subgroup.subcategory}`"
              class="nw-subcat-block"
            >
              <div class="nw-subcat-header">
                <div class="nw-subcat-title">{{ subgroup.label }}</div>
                <div class="nw-subcat-total">
                  <div class="nw-subcat-total-primary">
                    {{ page.formatTotalsLine(subgroup.totals) }}
                  </div>
                </div>
                <div class="nw-subcat-actions-spacer" aria-hidden="true"></div>
              </div>

              <ul class="list list-plain nw-subcat-items">
                <li v-for="entry in subgroup.entries ?? []" :key="entry.id">
                  <div class="nw-item-row income-item-row">
                    <div class="nw-item-main">
                      <div class="nw-item-name income-item-name">
                        <span
                          class="income-rec-dot"
                          :class="page.timeProfileDotClass(entry.timeProfile)"
                          aria-hidden="true"
                        ></span>
                        <span class="item-name-text">{{ entry.name }}</span>
                        <span v-if="entry.owner" class="badge">{{ entry.owner }}</span>
                      </div>
                      <div class="nw-item-submeta">
                        {{ page.timeProfileLabel(entry.timeProfile) }} .
                        <template
                          v-if="
                            !page.shouldHideExpenseCashflowRoleLabel({
                              timeProfile: entry.timeProfile,
                              cashflowRole: entry.cashflowRole,
                            })
                          "
                        >
                          {{ page.expenseCashflowRoleLabel(entry.cashflowRole) }}
                        </template>
                        <template v-if="entry.eventGroup">
                          . Evento {{ page.eventGroupLabel(entry.eventGroup) }}</template
                        >
                        <template
                          v-if="page.formatTermEndLabel(entry.termEndYear, entry.termEndMonth)"
                        >
                          .
                          {{ page.formatTermEndLabel(entry.termEndYear, entry.termEndMonth) }}
                        </template>
                      </div>
                    </div>
                    <div class="nw-item-amount">
                      {{ page.formatMoneyAmount(entry.amountAnnual, entry.currency) }}
                    </div>
                    <div class="nw-item-actions">
                      <button
                        class="icon-btn"
                        title="Editar"
                        :disabled="page.annualExpenseLoading"
                        @click="() => page.openExpenseModal(entry)"
                      >
                        &#9998;
                      </button>
                      <button
                        class="icon-btn"
                        title="Eliminar"
                        :disabled="page.annualExpenseLoading"
                        @click="page.removeAnnualExpense(entry.id)"
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

      <div v-if="page.annualExpenseLoading" class="ui-status-line mt-2">
        Cargando salidas anuales...
      </div>
    </article>
  </div>

  <AnnualEntryModalForm
    :open="showIncomeModalModel"
    :title="page.incomeModalTitle"
    :form="page.annualIncomeForm"
    :loading="page.annualIncomeLoading"
    :submit-label="page.incomeSubmitLabel"
    :category-options="page.incomeCategories"
    :subcategory-options="page.annualSubcategoryOptions"
    :show-owner-field="page.showOwnerField"
    :owner-options="page.ownerOptions"
    :time-profile-options="page.incomeTimeProfileOptions"
    :cashflow-role-options="page.incomeCashflowRoleOptions"
    :show-cashflow-role-field="false"
    :event-group-options="page.annualEventGroupOptions"
    event-group-datalist-id="income-event-groups"
    name-placeholder="Concepto (ej: CTN, Regalos Pablo)"
    :amount-placeholder="page.incomeAmountInputPlaceholder"
    @patch="page.patchAnnualIncomeForm"
    @close="page.closeIncomeModal"
    @submit="page.submitAnnualIncome"
  />

  <AnnualEntryModalForm
    :open="showExpenseModalModel"
    :title="page.expenseModalTitle"
    :form="page.annualExpenseForm"
    :loading="page.annualExpenseLoading"
    :submit-label="page.expenseSubmitLabel"
    :category-options="page.expenseCategories"
    :subcategory-options="page.annualExpenseSubcategoryOptions"
    :show-owner-field="page.showOwnerField"
    :owner-options="page.ownerOptions"
    :time-profile-options="page.expenseTimeProfileOptions"
    time-profile-field-label="Tipo de salida"
    :cashflow-role-options="page.filteredExpenseCashflowRoleOptions"
    :show-cashflow-role-field="page.showExpenseCashflowRoleField"
    :show-event-group-field="!page.editingSystemGeneratedLiabilityExpense"
    :show-term-end-year-field="!page.editingSystemGeneratedLiabilityExpense"
    :event-group-options="page.annualEventGroupOptions"
    event-group-datalist-id="expense-event-groups"
    name-placeholder="Concepto (ej: Alimentacion, Hipoteca)"
    :amount-placeholder="page.expenseAmountInputPlaceholder"
    :notes-placeholder="page.expenseBulkEditHint"
    @patch="page.patchAnnualExpenseForm"
    @close="page.closeExpenseModal"
    @submit="page.submitAnnualExpense"
  />
</template>
