<script setup lang="ts">
type AmountInputPeriod = 'annual' | 'monthly';

const props = withDefaults(
  defineProps<{
    amountValue: string;
    period: AmountInputPeriod;
    currency: string;
    placeholder: string;
    periodDisabled?: boolean;
    currencyOptions?: string[];
  }>(),
  {
    periodDisabled: false,
    currencyOptions: () => ['EUR', 'USD'],
  },
);

const emit = defineEmits<{
  'update:amountValue': [value: string];
  'update:period': [value: AmountInputPeriod];
  'update:currency': [value: string];
}>();
</script>

<template>
  <div class="ui-amount-period-row">
    <input
      :value="amountValue"
      class="input ui-data-field"
      inputmode="decimal"
      :placeholder="placeholder"
      @input="emit('update:amountValue', String(($event.target as HTMLInputElement).value ?? ''))"
    />
    <select
      :value="period"
      class="select ui-data-field"
      :disabled="periodDisabled"
      @change="
        emit(
          'update:period',
          String(($event.target as HTMLSelectElement).value ?? 'annual') as AmountInputPeriod,
        )
      "
    >
      <option value="annual">Anual</option>
      <option value="monthly">Mensual</option>
    </select>
    <select
      :value="currency"
      class="select ui-data-field"
      @change="emit('update:currency', String(($event.target as HTMLSelectElement).value ?? ''))"
    >
      <option v-for="option in currencyOptions" :key="option" :value="option">
        {{ option }}
      </option>
    </select>
  </div>
</template>
