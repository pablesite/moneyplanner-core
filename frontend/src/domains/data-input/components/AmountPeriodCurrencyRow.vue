<script setup lang="ts">
type AmountInputPeriod = 'annual' | 'monthly';

const props = withDefaults(
  defineProps<{
    amountValue: string;
    period: AmountInputPeriod;
    currency: string;
    placeholder: string;
    periodDisabled?: boolean;
    hidePeriodToggle?: boolean;
    currencyOptions?: string[];
  }>(),
  {
    periodDisabled: false,
    hidePeriodToggle: false,
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
    <div v-if="!hidePeriodToggle" class="ui-amount-period-toggle-wrap">
      <button
        type="button"
        class="ui-amount-period-toggle"
        :class="period === 'monthly' ? 'ui-amount-period-toggle-on' : 'ui-amount-period-toggle-off'"
        :disabled="periodDisabled"
        :aria-pressed="period === 'monthly'"
        :title="period === 'monthly' ? 'Mensual' : 'Anual'"
        @click="emit('update:period', period === 'monthly' ? 'annual' : 'monthly')"
      >
        <span
          class="ui-amount-period-toggle-thumb"
          :class="
            period === 'monthly'
              ? 'ui-amount-period-toggle-thumb-on'
              : 'ui-amount-period-toggle-thumb-off'
          "
        ></span>
      </button>
      <span
        class="ui-amount-period-toggle-label"
        :class="{ 'ui-amount-period-toggle-label-active': period === 'monthly' }"
      >
        {{ period === 'monthly' ? 'Mensual' : 'Anual' }}
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
