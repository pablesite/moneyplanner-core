<script setup lang="ts">
import { BaseModal } from '@/domains/ui';
import AmountPeriodCurrencyRow from './AmountPeriodCurrencyRow.vue';

type SelectOption = {
  value: string;
  label: string;
};

type OwnerOption = SelectOption & {
  key: string;
};

type AnnualEntryModalFormModel = {
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
};

const props = withDefaults(
  defineProps<{
    open: boolean;
    title: string;
    form: AnnualEntryModalFormModel;
    loading?: boolean;
    submitLabel: string;
    categoryOptions: ReadonlyArray<SelectOption>;
    subcategoryOptions: ReadonlyArray<SelectOption>;
    showOwnerField?: boolean;
    ownerOptions?: ReadonlyArray<OwnerOption>;
    timeProfileOptions: ReadonlyArray<SelectOption>;
    timeProfileFieldLabel?: string;
    cashflowRoleOptions: ReadonlyArray<SelectOption>;
    showCashflowRoleField?: boolean;
    showEventGroupField?: boolean;
    showTermEndYearField?: boolean;
    namePlaceholder: string;
    amountPlaceholder: string;
    eventGroupPlaceholder?: string;
    termEndYearPlaceholder?: string;
    termEndMonthPlaceholder?: string;
    notesPlaceholder?: string;
    currencyOptions?: string[];
    eventGroupOptions?: ReadonlyArray<string>;
    eventGroupDatalistId?: string;
  }>(),
  {
    loading: false,
    showOwnerField: false,
    showCashflowRoleField: true,
    showEventGroupField: true,
    showTermEndYearField: true,
    ownerOptions: () => [],
    timeProfileFieldLabel: '',
    eventGroupPlaceholder: 'Grupo de evento (opcional, ej: vivienda_2026)',
    termEndYearPlaceholder: 'Ano fin compromiso (ej: 2027)',
    termEndMonthPlaceholder: 'Mes fin (1-12)',
    notesPlaceholder: 'Notas (opcional)',
    currencyOptions: () => ['EUR', 'USD'],
    eventGroupOptions: () => [],
    eventGroupDatalistId: 'annual-entry-event-groups',
  },
);

const emit = defineEmits<{
  close: [];
  submit: [];
  patch: [patch: Partial<AnnualEntryModalFormModel>];
}>();
</script>

<template>
  <BaseModal :open="open" :title="title" @close="emit('close')">
    <div class="grid gap-2.5 md:grid-cols-2">
      <select
        :value="form.category"
        class="select ui-data-field"
        @change="
          emit('patch', { category: String(($event.target as HTMLSelectElement).value ?? '') })
        "
      >
        <option v-for="category in categoryOptions" :key="category.value" :value="category.value">
          {{ category.label }}
        </option>
      </select>

      <select
        :value="form.subcategory"
        class="select ui-data-field"
        @change="
          emit('patch', { subcategory: String(($event.target as HTMLSelectElement).value ?? '') })
        "
      >
        <option
          v-for="subcategory in subcategoryOptions"
          :key="subcategory.value"
          :value="subcategory.value"
        >
          {{ subcategory.label }}
        </option>
      </select>

      <input
        :value="form.name"
        class="input ui-data-field"
        :class="{ 'md:col-span-2': !showOwnerField }"
        :placeholder="namePlaceholder"
        @input="emit('patch', { name: String(($event.target as HTMLInputElement).value ?? '') })"
      />

      <select
        v-if="showOwnerField"
        :value="form.owner"
        class="select ui-data-field"
        @change="emit('patch', { owner: String(($event.target as HTMLSelectElement).value ?? '') })"
      >
        <option value="">Titular (opcional)</option>
        <option v-for="option in ownerOptions" :key="option.key" :value="option.value">
          {{ option.label }}
        </option>
      </select>

      <label class="ui-item-form-field">
        <span v-if="timeProfileFieldLabel" class="ui-item-form-label">{{
          timeProfileFieldLabel
        }}</span>
        <select
          :value="form.timeProfile"
          class="select ui-data-field"
          @change="
            emit('patch', { timeProfile: String(($event.target as HTMLSelectElement).value ?? '') })
          "
        >
          <option v-for="option in timeProfileOptions" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>

      <select
        v-if="showCashflowRoleField"
        :value="form.cashflowRole"
        class="select ui-data-field"
        @change="
          emit('patch', { cashflowRole: String(($event.target as HTMLSelectElement).value ?? '') })
        "
      >
        <option v-for="option in cashflowRoleOptions" :key="option.value" :value="option.value">
          {{ option.label }}
        </option>
      </select>

      <input
        v-if="showEventGroupField"
        :value="form.eventGroup"
        class="input ui-data-field"
        :list="eventGroupOptions.length ? eventGroupDatalistId : undefined"
        :placeholder="eventGroupPlaceholder"
        @input="
          emit('patch', { eventGroup: String(($event.target as HTMLInputElement).value ?? '') })
        "
      />
      <datalist v-if="showEventGroupField && eventGroupOptions.length" :id="eventGroupDatalistId">
        <option v-for="eventGroup in eventGroupOptions" :key="eventGroup" :value="eventGroup">
          {{ eventGroup }}
        </option>
      </datalist>

      <input
        v-if="form.timeProfile === 'one_off'"
        :value="form.targetMonth"
        class="input ui-data-field"
        inputmode="numeric"
        placeholder="Mes objetivo (1-12)"
        @input="
          emit('patch', { targetMonth: String(($event.target as HTMLInputElement).value ?? '') })
        "
      />

      <input
        v-if="showTermEndYearField && form.timeProfile === 'term_recurrent'"
        :value="form.termEndMonth"
        class="input ui-data-field"
        inputmode="numeric"
        :placeholder="termEndMonthPlaceholder"
        @input="
          emit('patch', { termEndMonth: String(($event.target as HTMLInputElement).value ?? '') })
        "
      />

      <input
        v-if="showTermEndYearField && form.timeProfile === 'term_recurrent'"
        :value="form.termEndYear"
        class="input ui-data-field"
        inputmode="numeric"
        :placeholder="termEndYearPlaceholder"
        @input="
          emit('patch', { termEndYear: String(($event.target as HTMLInputElement).value ?? '') })
        "
      />

      <AmountPeriodCurrencyRow
        class="md:col-span-2"
        :amount-value="form.amountAnnual"
        :period="form.amountInputPeriod"
        :currency="form.currency"
        :placeholder="amountPlaceholder"
        :period-disabled="form.timeProfile === 'one_off'"
        :hide-period-toggle="form.timeProfile === 'one_off'"
        :currency-options="currencyOptions"
        @update:amount-value="emit('patch', { amountAnnual: $event })"
        @update:period="emit('patch', { amountInputPeriod: $event })"
        @update:currency="emit('patch', { currency: $event })"
      />

      <textarea
        :value="form.notes"
        class="textarea ui-data-field ui-notes-field md:col-span-2"
        rows="2"
        :placeholder="notesPlaceholder"
        @input="
          emit('patch', { notes: String(($event.target as HTMLTextAreaElement).value ?? '') })
        "
      />

      <div class="actions md:col-span-2">
        <button class="btn btn-ghost" type="button" @click="emit('close')">Cancelar</button>
        <button class="btn btn-primary" type="button" :disabled="loading" @click="emit('submit')">
          {{ submitLabel }}
        </button>
      </div>
    </div>
  </BaseModal>
</template>
