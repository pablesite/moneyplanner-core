<script setup lang="ts">
import { LIABILITY_PAYMENT_FREQUENCIES } from './itemFormUtils';

interface FormSlice {
  payment_start_date: string;
  expected_end_date: string;
  annual_interest_tae: string;
  term_months: string;
  payment_frequency: string;
  opening_fees_amount: string;
  early_repayment_fee_percent: string;
  novation_subrogation_fee_amount: string;
  linked_products_monthly_cost: string;
  cancellation_forecast_enabled: boolean;
  cancellation_date: string;
  cancellation_include_payment_month: boolean;
  cancellation_fee_amount: string;
  currency: string;
}

const form = defineModel<FormSlice>('form', { required: true });

defineProps<{
  showLiabilityAdvancedFields: boolean;
  showMortgageFeeFields: boolean;
  showMortgageCancellationForecastFields: boolean;
  liabilityTermFieldLabel: string;
  liabilityTermFieldPlaceholder: string;
  liabilityTermFieldHint: string | null;
  estimatedMonthlyPaymentPreviewText: string | null;
  estimatedPaymentPreviewLabel: string;
  onLiabilityPaymentStartDateInput: () => void;
  onLiabilityEndDateInput: () => void;
  onLiabilityTermInput: () => void;
}>();
</script>

<template>
  <div v-if="showLiabilityAdvancedFields" class="ui-item-form-section ui-item-form-field-span-2">
    <div class="ui-item-form-section-head">
      <div>
        <div class="ui-item-form-section-title">Calendario y condiciones</div>
        <div class="ui-item-form-section-subtitle">
          Indica <strong>inicio de pago</strong>, y despues <strong>cuotas</strong> o
          <strong>fecha fin</strong>. Se calcula la otra.
        </div>
      </div>
      <span class="badge">Requerido</span>
    </div>
    <div class="ui-item-form-inline-grid">
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Fecha inicio pago</span>
        <input
          v-model="form.payment_start_date"
          type="date"
          class="input ui-data-field"
          @change="onLiabilityPaymentStartDateInput()"
        />
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Fecha fin</span>
        <input
          v-model="form.expected_end_date"
          type="date"
          class="input ui-data-field"
          @change="onLiabilityEndDateInput()"
        />
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">TAE anual (%)</span>
        <input
          v-model="form.annual_interest_tae"
          inputmode="decimal"
          placeholder="0"
          class="input ui-data-field"
        />
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">{{ liabilityTermFieldLabel }}</span>
        <input
          v-model="form.term_months"
          inputmode="numeric"
          :placeholder="liabilityTermFieldPlaceholder"
          class="input ui-data-field"
          @input="onLiabilityTermInput()"
        />
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Frecuencia</span>
        <select v-model="form.payment_frequency" class="select ui-data-field">
          <option v-for="opt in LIABILITY_PAYMENT_FREQUENCIES" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </label>
    </div>
    <div v-if="liabilityTermFieldHint" class="ui-form-help">
      {{ liabilityTermFieldHint }}
    </div>
    <div v-if="estimatedMonthlyPaymentPreviewText" class="ui-item-form-chipline">
      <span class="ui-item-form-chip">{{ estimatedPaymentPreviewLabel }}</span>
      <span>
        {{ estimatedMonthlyPaymentPreviewText }} {{ form.currency || '' }}
        <small class="subtle">(simple, tipo fijo)</small>
        <small v-if="showMortgageFeeFields" class="subtle">(sin incluir costes opcionales)</small>
      </span>
    </div>
  </div>

  <details v-if="showMortgageFeeFields" class="ui-item-form-section ui-item-form-field-span-2">
    <summary class="ui-item-form-details-summary">Costes hipotecarios opcionales</summary>
    <div class="ui-item-form-inline-grid mt-2">
      <label class="ui-item-form-field"
        ><span class="ui-item-form-label">Comisión apertura</span
        ><input
          v-model="form.opening_fees_amount"
          inputmode="decimal"
          placeholder="Opcional"
          class="input ui-data-field"
      /></label>
      <label class="ui-item-form-field"
        ><span class="ui-item-form-label">Amortización anticipada (%)</span
        ><input
          v-model="form.early_repayment_fee_percent"
          inputmode="decimal"
          placeholder="Opcional"
          class="input ui-data-field"
      /></label>
      <label class="ui-item-form-field"
        ><span class="ui-item-form-label">Novación / subrogación</span
        ><input
          v-model="form.novation_subrogation_fee_amount"
          inputmode="decimal"
          placeholder="Opcional"
          class="input ui-data-field"
      /></label>
      <label class="ui-item-form-field"
        ><span class="ui-item-form-label">Vinculados (mensual)</span
        ><input
          v-model="form.linked_products_monthly_cost"
          inputmode="decimal"
          placeholder="Opcional"
          class="input ui-data-field"
      /></label>
    </div>
  </details>

  <details
    v-if="showMortgageCancellationForecastFields"
    class="ui-item-form-section ui-item-form-field-span-2"
  >
    <summary class="ui-item-form-details-summary">Prevision de cancelacion</summary>
    <div class="mt-2">
      <label class="checkbox-row">
        <input v-model="form.cancellation_forecast_enabled" type="checkbox" />
        <span>Activar prevision de cancelacion anticipada</span>
      </label>
    </div>
    <div v-if="form.cancellation_forecast_enabled" class="ui-item-form-inline-grid mt-2">
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Fecha cancelacion</span>
        <input v-model="form.cancellation_date" type="date" class="input ui-data-field" />
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Cuota del mes de cancelación</span>
        <select v-model="form.cancellation_include_payment_month" class="select ui-data-field">
          <option :value="true">Sí, se paga</option>
          <option :value="false">No, se omite</option>
        </select>
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Comision cancelacion (importe)</span>
        <input
          v-model="form.cancellation_fee_amount"
          inputmode="decimal"
          placeholder="Opcional"
          class="input ui-data-field"
        />
      </label>
    </div>
    <div v-if="form.cancellation_forecast_enabled" class="ui-form-help">
      Si no indicas importe, se estimará con "Amortización anticipada (%)" sobre el saldo pendiente.
      La opción de cuota decide si el mes de cancelación sigue contando como pago recurrente o si el
      presupuesto corta un mes antes.
    </div>
  </details>
</template>
