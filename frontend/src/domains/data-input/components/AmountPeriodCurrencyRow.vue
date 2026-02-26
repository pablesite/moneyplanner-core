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

function togglePeriod(): void {
  if (props.periodDisabled) return;
  emit('update:period', props.period === 'annual' ? 'monthly' : 'annual');
}
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
    <div class="ui-amount-period-toggle-wrap">
      <button
        type="button"
        class="ui-amount-period-toggle"
        :class="{
          'ui-amount-period-toggle-on': period === 'monthly',
          'ui-amount-period-toggle-off': period !== 'monthly',
        }"
        :disabled="periodDisabled"
        aria-label="Cambiar periodicidad mensual/anual"
        @click="togglePeriod"
      >
        <span
          class="ui-amount-period-toggle-thumb"
          :class="{
            'ui-amount-period-toggle-thumb-on': period === 'monthly',
            'ui-amount-period-toggle-thumb-off': period !== 'monthly',
          }"
        />
      </button>
      <span class="subtle ui-amount-period-toggle-label">
        <span :class="{ 'ui-amount-period-toggle-label-active': period === 'annual' }">Anual</span>
        /
        <span :class="{ 'ui-amount-period-toggle-label-active': period === 'monthly' }">
          Mensual
        </span>
      </span>
    </div>
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
