<script setup lang="ts">
import {
  useItemForm,
  currencies,
  DEPOSIT_TERM_MONTH_OPTIONS,
  LIABILITY_EXPENSE_SUBCATEGORY_OPTIONS,
  TRACKING_MODE_OPTIONS,
  REAL_ESTATE_USAGE_OPTIONS,
} from './useItemForm';
import type { ItemFormProps } from './useItemForm';
import InvestmentContributionIntervals from './InvestmentContributionIntervals.vue';
import PrimaryHomeValuationSection from './PrimaryHomeValuationSection.vue';
import LiabilityScheduleSection from './LiabilityScheduleSection.vue';

const props = defineProps<ItemFormProps>();
const {
  form,
  saving,
  isEdit,
  contributionIntervals,
  primaryHomeImprovements,
  primaryHomeValuationProfile,
  realEstateUsage,
  ownershipOptions,
  financedAssetOptions,
  subcategoriesForCategory,
  showFinancedAsset,
  isLiabilityForm,
  isInvestmentCategory,
  showAssetAnnualInterestInput,
  showEstimatedAverageBalanceForInterestInput,
  showInvestmentMarketValueFields,
  showDepositTermMonthsInput,
  showLiabilityAdvancedFields,
  showLiabilityExpenseSubcategoryField,
  showLiabilityTaeOnlyField,
  showMortgageFeeFields,
  showMortgageCancellationForecastFields,
  showAssetAmortizationFields,
  showPrimaryHomeValuationFields,
  showPrimaryHomeAutoValuationFields,
  showRealEstateUsageField,
  requiresAssetAmortizationTermInput,
  assetAmortizationMethodOptions,
  assetAmortizationModelHint,
  defaultDegressiveTermYearsForFurnishings,
  estimatedAverageBalanceCurrencyLabel,
  liabilityTermFieldLabel,
  liabilityTermFieldPlaceholder,
  liabilityTermFieldHint,
  estimatedMonthlyPaymentPreviewText,
  estimatedPaymentPreviewLabel,
  financedAssetSuggestionHelp,
  amountError,
  annualInterestError,
  estimatedAverageBalanceForInterestError,
  depositTermMonthsError,
  monthlyPaymentError,
  investmentContributionError,
  requiredFieldsError,
  assetAmortizationError,
  primaryHomeValuationError,
  primaryHomeImprovementsError,
  liabilityDatesError,
  liabilityScheduleError,
  cancellationForecastError,
  addContributionInterval,
  removeContributionInterval,
  addPrimaryHomeImprovement,
  removePrimaryHomeImprovement,
  isImprovementExpanded,
  toggleImprovementExpanded,
  onLiabilityTermInput,
  onLiabilityEndDateInput,
  onLiabilityPaymentStartDateInput,
  onFinancedAssetChange,
  submit,
} = useItemForm(props);
</script>

<template>
  <div>
    <div class="ui-item-form-grid">
      <label
        :class="[
          'ui-item-form-field',
          { 'ui-item-form-field-span-2': isLiabilityForm || !props.subcategories },
        ]"
      >
        <span class="ui-item-form-label">Categoría</span>
        <select
          v-model="form.category"
          :class="['select ui-data-field', { 'ui-select-placeholder': !form.category }]"
        >
          <option value="" disabled>Selecciona categoría</option>
          <option v-for="c in categories" :key="c.value" :value="c.value">{{ c.label }}</option>
        </select>
      </label>

      <label v-if="props.subcategories" class="ui-item-form-field">
        <span class="ui-item-form-label">Subcategoría</span>
        <select
          v-model="form.subcategory"
          :class="['select ui-data-field', { 'ui-select-placeholder': !form.subcategory }]"
        >
          <option value="" disabled>Selecciona subcategoría</option>
          <option v-for="s in subcategoriesForCategory" :key="s.value" :value="s.value">
            {{ s.label }}
          </option>
        </select>
      </label>
      <label v-if="showRealEstateUsageField" class="ui-item-form-field">
        <span class="ui-item-form-label">Uso</span>
        <select v-model="realEstateUsage" class="select ui-data-field">
          <option v-for="opt in REAL_ESTATE_USAGE_OPTIONS" :key="opt.value" :value="opt.value">
            {{ opt.label }}
          </option>
        </select>
      </label>
      <label :class="['ui-item-form-field', { 'ui-item-form-field-span-2': isLiabilityForm }]">
        <span class="ui-item-form-label">Nombre</span>
        <input v-model="form.name" placeholder="Nombre" class="input ui-data-field" />
      </label>

      <label class="ui-item-form-field">
        <span class="ui-item-form-label">{{
          isLiabilityForm ? 'Fecha contratación préstamo' : 'Fecha inicio'
        }}</span>
        <input v-model="form.start_date" type="date" class="input ui-data-field" />
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">{{
          isLiabilityForm ? 'Principal / saldo actual' : 'Importe'
        }}</span>
        <input
          v-model="form.amount"
          inputmode="decimal"
          placeholder="Importe"
          class="input ui-data-field"
        />
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Moneda</span>
        <select
          v-model="form.currency"
          :class="['select ui-data-field', { 'ui-select-placeholder': !form.currency }]"
        >
          <option value="" disabled>Selecciona moneda</option>
          <option v-for="c in currencies" :key="c.value" :value="c.value">{{ c.label }}</option>
        </select>
      </label>
      <label class="ui-item-form-field">
        <span class="ui-item-form-label">Tracking mode</span>
        <select v-model="form.tracking_mode" class="select ui-data-field">
          <option v-for="option in TRACKING_MODE_OPTIONS" :key="option.value" :value="option.value">
            {{ option.label }}
          </option>
        </select>
      </label>
      <label v-if="showLiabilityExpenseSubcategoryField" class="ui-item-form-field">
        <span class="ui-item-form-label">Destino de la salida</span>
        <select
          v-model="form.expense_subcategory_override"
          :class="[
            'select ui-data-field',
            { 'ui-select-placeholder': !form.expense_subcategory_override },
          ]"
        >
          <option value="" disabled>Selecciona destino</option>
          <option
            v-for="option in LIABILITY_EXPENSE_SUBCATEGORY_OPTIONS"
            :key="option.value"
            :value="option.value"
          >
            {{ option.label }}
          </option>
        </select>
      </label>

      <InvestmentContributionIntervals
        v-if="isInvestmentCategory"
        :intervals="contributionIntervals"
        @add="addContributionInterval"
        @remove="removeContributionInterval"
      />

      <label v-if="showInvestmentMarketValueFields" class="ui-item-form-field">
        <span class="ui-item-form-label">Valor real actual</span>
        <input
          v-model="form.market_value_override"
          inputmode="decimal"
          placeholder="Opcional"
          class="input ui-data-field"
        />
      </label>
      <label v-if="showInvestmentMarketValueFields" class="ui-item-form-field">
        <span class="ui-item-form-label">Fecha valoración</span>
        <input v-model="form.market_value_override_date" type="date" class="input ui-data-field" />
      </label>

      <PrimaryHomeValuationSection
        v-if="showPrimaryHomeValuationFields"
        v-model:form="form"
        v-model:primary-home-valuation-profile="primaryHomeValuationProfile"
        :show-primary-home-auto-valuation-fields="showPrimaryHomeAutoValuationFields"
        :primary-home-improvements="primaryHomeImprovements"
        :is-improvement-expanded="isImprovementExpanded"
        :toggle-improvement-expanded="toggleImprovementExpanded"
        :add-primary-home-improvement="addPrimaryHomeImprovement"
        :remove-primary-home-improvement="removePrimaryHomeImprovement"
      />

      <label v-if="showAssetAnnualInterestInput" class="ui-item-form-field">
        <span class="ui-item-form-label">TAE anual (%)</span>
        <input
          v-model="form.annual_interest_tae"
          inputmode="decimal"
          placeholder="TAE anual (%)"
          class="input ui-data-field"
        />
      </label>
      <label v-if="showEstimatedAverageBalanceForInterestInput" class="ui-item-form-field">
        <span class="ui-item-form-label">
          Importe anual medio previsto ({{ estimatedAverageBalanceCurrencyLabel }})
        </span>
        <input
          v-model="form.estimated_average_balance_for_interest"
          inputmode="numeric"
          :placeholder="`Saldo medio anual previsto (${estimatedAverageBalanceCurrencyLabel})`"
          class="input ui-data-field"
        />
      </label>
      <label v-if="showDepositTermMonthsInput" class="ui-item-form-field">
        <span class="ui-item-form-label">Duración del depósito (meses)</span>
        <select
          v-model="form.deposit_term_months"
          :class="[
            'select ui-data-field',
            { 'ui-select-placeholder': !String(form.deposit_term_months ?? '').trim() },
          ]"
        >
          <option value="" disabled>Selecciona duración</option>
          <option v-for="month in DEPOSIT_TERM_MONTH_OPTIONS" :key="month" :value="String(month)">
            {{ month }}
          </option>
        </select>
      </label>
      <label v-if="showLiabilityTaeOnlyField" class="ui-item-form-field">
        <span class="ui-item-form-label">TAE anual (%)</span>
        <input
          v-model="form.annual_interest_tae"
          inputmode="decimal"
          placeholder="TAE anual (%)"
          class="input ui-data-field"
        />
      </label>

      <LiabilityScheduleSection
        v-model:form="form"
        :show-liability-advanced-fields="showLiabilityAdvancedFields"
        :show-mortgage-fee-fields="showMortgageFeeFields"
        :show-mortgage-cancellation-forecast-fields="showMortgageCancellationForecastFields"
        :liability-term-field-label="liabilityTermFieldLabel"
        :liability-term-field-placeholder="liabilityTermFieldPlaceholder"
        :liability-term-field-hint="liabilityTermFieldHint"
        :estimated-monthly-payment-preview-text="estimatedMonthlyPaymentPreviewText"
        :estimated-payment-preview-label="estimatedPaymentPreviewLabel"
        :on-liability-payment-start-date-input="onLiabilityPaymentStartDateInput"
        :on-liability-end-date-input="onLiabilityEndDateInput"
        :on-liability-term-input="onLiabilityTermInput"
      />

      <div
        v-if="showAssetAmortizationFields"
        class="ui-item-form-section ui-item-form-field-span-2"
      >
        <div class="ui-item-form-section-head">
          <div class="ui-item-form-section-title">Amortización del activo</div>
        </div>
        <div class="ui-item-form-inline-grid">
          <label class="ui-item-form-field"
            ><span class="ui-item-form-label">Método</span
            ><select v-model="form.amortization_method" class="select ui-data-field">
              <option
                v-for="opt in assetAmortizationMethodOptions"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select></label
          >
          <label v-if="requiresAssetAmortizationTermInput" class="ui-item-form-field"
            ><span class="ui-item-form-label">Plazo (años)</span
            ><input
              v-model="form.amortization_term_years"
              inputmode="numeric"
              placeholder="Ej: 10"
              class="input ui-data-field"
          /></label>
        </div>
        <div class="ui-form-help">Se usa el Importe como valor de compra inicial del activo.</div>
        <div v-if="assetAmortizationModelHint" class="ui-form-help">
          {{ assetAmortizationModelHint }}
        </div>
        <div v-if="defaultDegressiveTermYearsForFurnishings != null" class="ui-form-help">
          Plazo configurado automaticamente para esta subcategoria:
          {{ defaultDegressiveTermYearsForFurnishings }} años.
        </div>
      </div>

      <label class="ui-item-form-field ui-item-form-field-span-2">
        <span class="ui-item-form-label">Titularidad</span>
        <select
          v-model="form.ownership_id"
          :class="['select ui-data-field', { 'ui-select-placeholder': form.ownership_id == null }]"
        >
          <option v-for="o in ownershipOptions" :key="String(o.value)" :value="o.value">
            {{ o.label }}
          </option>
        </select>
      </label>

      <label v-if="showFinancedAsset" class="ui-item-form-field ui-item-form-field-span-2">
        <span class="ui-item-form-label">Activo financiado</span>
        <select
          v-model="form.financed_asset_id"
          :class="[
            'select ui-data-field',
            { 'ui-select-placeholder': form.financed_asset_id == null },
          ]"
          @change="onFinancedAssetChange"
        >
          <option v-for="a in financedAssetOptions" :key="String(a.value)" :value="a.value">
            {{ a.label }}
          </option>
        </select>
        <div v-if="financedAssetSuggestionHelp" class="ui-form-help">
          {{ financedAssetSuggestionHelp }}
        </div>
      </label>

      <label class="ui-item-form-field ui-item-form-field-span-2">
        <span class="ui-item-form-label">Notas</span>
        <textarea
          v-model="form.notes"
          placeholder="Notas"
          rows="2"
          class="textarea ui-data-field"
        ></textarea>
      </label>

      <div class="ui-item-form-feedback ui-item-form-field-span-2">
        <div v-if="amountError" class="ui-form-help ui-form-help-error">{{ amountError }}</div>
        <div v-if="annualInterestError" class="ui-form-help ui-form-help-error">
          {{ annualInterestError }}
        </div>
        <div v-if="estimatedAverageBalanceForInterestError" class="ui-form-help ui-form-help-error">
          {{ estimatedAverageBalanceForInterestError }}
        </div>
        <div v-if="depositTermMonthsError" class="ui-form-help ui-form-help-error">
          {{ depositTermMonthsError }}
        </div>
        <div v-if="requiredFieldsError" class="ui-form-help ui-form-help-error">
          {{ requiredFieldsError }}
        </div>
        <div v-if="monthlyPaymentError" class="ui-form-help ui-form-help-error">
          {{ monthlyPaymentError }}
        </div>
        <div v-if="assetAmortizationError" class="ui-form-help ui-form-help-error">
          {{ assetAmortizationError }}
        </div>
        <div v-if="investmentContributionError" class="ui-form-help ui-form-help-error">
          {{ investmentContributionError }}
        </div>
        <div v-if="primaryHomeValuationError" class="ui-form-help ui-form-help-error">
          {{ primaryHomeValuationError }}
        </div>
        <div v-if="primaryHomeImprovementsError" class="ui-form-help ui-form-help-error">
          {{ primaryHomeImprovementsError }}
        </div>
        <div v-if="liabilityDatesError" class="ui-form-help ui-form-help-error">
          {{ liabilityDatesError }}
        </div>
        <div v-if="liabilityScheduleError" class="ui-form-help ui-form-help-error">
          {{ liabilityScheduleError }}
        </div>
        <div v-if="cancellationForecastError" class="ui-form-help ui-form-help-error">
          {{ cancellationForecastError }}
        </div>
      </div>

      <div class="ui-item-form-footer ui-item-form-field-span-2">
        <div v-if="submitError" class="ui-form-help ui-form-help-error ui-item-form-submit-error">
          {{ submitError }}
        </div>
        <div class="ui-form-actions ui-item-form-actions">
          <button v-if="onCancel" class="btn ui-form-action-btn" type="button" @click="onCancel">
            Cancelar
          </button>
          <button
            class="btn btn-primary ui-form-action-btn"
            :disabled="
              saving ||
              !!requiredFieldsError ||
              !!amountError ||
              !!annualInterestError ||
              !!estimatedAverageBalanceForInterestError ||
              !!depositTermMonthsError ||
              !!monthlyPaymentError ||
              !!assetAmortizationError ||
              !!investmentContributionError ||
              !!primaryHomeValuationError ||
              !!primaryHomeImprovementsError ||
              !!liabilityDatesError ||
              !!liabilityScheduleError ||
              !!cancellationForecastError
            "
            @click="submit"
          >
            <span v-if="saving" class="ui-item-form-btn-spinner" />
            {{ saving ? 'Guardando...' : isEdit ? 'Guardar' : 'Crear' }}
          </button>
        </div>
      </div>
    </div>
  </div>
</template>
