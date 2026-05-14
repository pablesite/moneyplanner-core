<script setup lang="ts">
import {
  useItemForm,
  currencies,
  DEPOSIT_TERM_MONTH_OPTIONS,
  LIABILITY_PAYMENT_FREQUENCIES,
  LIABILITY_EXPENSE_SUBCATEGORY_OPTIONS,
  TRACKING_MODE_OPTIONS,
  REAL_ESTATE_USAGE_OPTIONS,
  PRIMARY_HOME_VALUATION_MODE_OPTIONS,
  PRIMARY_HOME_VALUATION_PROFILES,
  PRIMARY_HOME_CUSTOM_PROFILE_VALUE,
  PRIMARY_HOME_IMPROVEMENT_AMORTIZATION_OPTIONS,
} from './useItemForm';
import type { ItemFormProps } from './useItemForm';

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
  canCapitalizeImprovementInterest,
  improvementRemoveLabel,
  formatImprovementSummaryDate,
  formatImprovementSummaryAmount,
  currencySymbol,
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
      <div v-if="isInvestmentCategory" class="ui-item-form-section ui-item-form-field-span-2">
        <div class="ui-item-form-section-head">
          <div class="ui-item-form-section-title">Aportaciones periódicas</div>
          <button type="button" class="btn ui-item-form-mini-btn" @click="addContributionInterval">
            + Añadir intervalo
          </button>
        </div>
        <div v-if="!contributionIntervals.length" class="ui-form-help">
          Sin intervalos = activo sin aportaciones periódicas previstas.
        </div>
        <div
          v-for="interval in contributionIntervals"
          :key="interval._key"
          class="ui-item-form-inline-grid ui-item-form-inline-grid-4 ui-surface-muted mt-2 p-2"
        >
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Desde</span>
            <input v-model="interval.start_date" type="date" class="input ui-data-field" />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Hasta (opcional)</span>
            <input v-model="interval.end_date" type="date" class="input ui-data-field" />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Cuota</span>
            <input v-model="interval.amount" inputmode="decimal" class="input ui-data-field" />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Moneda</span>
            <select v-model="interval.currency" class="select ui-data-field">
              <option v-for="c in currencies" :key="`${interval._key}-${c.value}`" :value="c.value">
                {{ c.label }}
              </option>
            </select>
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Frecuencia</span>
            <select v-model="interval.frequency" class="select ui-data-field">
              <option value="monthly">Mensual</option>
              <option value="weekly">Semanal</option>
            </select>
          </label>
          <div class="ui-item-form-field">
            <button
              type="button"
              class="btn ui-item-form-mini-btn"
              @click="removeContributionInterval(interval._key)"
            >
              Eliminar
            </button>
          </div>
        </div>
      </div>
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
      <div
        v-if="showPrimaryHomeValuationFields"
        class="ui-item-form-section ui-item-form-field-span-2"
      >
        <div class="ui-item-form-section-head">
          <div class="ui-item-form-section-title">Valoracion de inmueble residencial</div>
        </div>
        <div class="ui-item-form-inline-grid">
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Modelo</span>
            <select v-model="form.valuation_model" class="select ui-data-field">
              <option
                v-for="opt in PRIMARY_HOME_VALUATION_MODE_OPTIONS"
                :key="opt.value"
                :value="opt.value"
              >
                {{ opt.label }}
              </option>
            </select>
          </label>
          <label v-if="showPrimaryHomeAutoValuationFields" class="ui-item-form-field">
            <span class="ui-item-form-label">Perfil</span>
            <select v-model="primaryHomeValuationProfile" class="select ui-data-field">
              <option
                v-for="profile in PRIMARY_HOME_VALUATION_PROFILES"
                :key="profile.value"
                :value="profile.value"
              >
                {{ profile.label }}
              </option>
              <option :value="PRIMARY_HOME_CUSTOM_PROFILE_VALUE">Personalizado</option>
            </select>
          </label>
        </div>
        <div
          v-if="showPrimaryHomeAutoValuationFields"
          class="ui-item-form-inline-grid ui-item-form-inline-grid-3 mt-2"
        >
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Suelo sobre compra (%)</span>
            <input
              v-model="form.land_value_share_percent"
              inputmode="decimal"
              placeholder="Ej: 30"
              class="input ui-data-field"
            />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Revalorización suelo anual (%)</span>
            <input
              v-model="form.land_annual_appreciation_percent"
              inputmode="decimal"
              placeholder="Ej: 3"
              class="input ui-data-field"
            />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Depreciación construcción anual (%)</span>
            <input
              v-model="form.building_annual_depreciation_percent"
              inputmode="decimal"
              placeholder="Ej: 1"
              class="input ui-data-field"
            />
          </label>
        </div>
        <div v-if="showPrimaryHomeAutoValuationFields" class="ui-form-help">
          El perfil autocompleta tasas y no modifica el porcentaje de suelo.
        </div>
        <div v-if="showPrimaryHomeAutoValuationFields" class="ui-item-form-subsection mt-2">
          <div class="ui-item-form-section-head">
            <div>
              <div class="ui-item-form-section-title">Reformas capitalizables</div>
              <div class="ui-item-form-section-subtitle">
                Cada reforma suma valor a la vivienda y puede amortizarse.
              </div>
            </div>
            <div class="ui-item-form-section-actions">
              <button
                type="button"
                class="btn ui-item-form-mini-btn"
                @click="addPrimaryHomeImprovement"
              >
                Añadir reforma
              </button>
            </div>
          </div>
          <div v-if="!primaryHomeImprovements.length" class="ui-form-help">
            Sin reformas registradas.
          </div>
          <div
            v-for="(improvement, index) in primaryHomeImprovements"
            :key="improvement.id ?? `new-${index}`"
            class="ui-item-form-improvement-card"
          >
            <div class="ui-item-form-improvement-head">
              <div class="ui-item-form-improvement-meta">
                <div class="ui-item-form-section-title">
                  {{ improvement.name || `Reforma ${index + 1}` }}
                </div>
                <span class="subtle">
                  {{ formatImprovementSummaryDate(improvement.reform_date) }} ·
                  {{ formatImprovementSummaryAmount(improvement.amount, form.currency) }}
                </span>
              </div>
              <div class="ui-item-form-improvement-actions">
                <button
                  type="button"
                  class="btn ui-item-form-mini-btn"
                  @click="removePrimaryHomeImprovement(index)"
                >
                  {{ improvementRemoveLabel(improvement) }}
                </button>
                <button
                  type="button"
                  class="icon-btn nw-cat-toggle"
                  :aria-label="
                    isImprovementExpanded(index) ? 'Compactar reforma' : 'Expandir reforma'
                  "
                  :title="isImprovementExpanded(index) ? 'Compactar reforma' : 'Expandir reforma'"
                  @click="toggleImprovementExpanded(index)"
                >
                  <span v-if="isImprovementExpanded(index)" class="icon" aria-hidden="true"
                    >&#9662;</span
                  >
                  <span v-else class="icon" aria-hidden="true">&#9656;</span>
                </button>
              </div>
            </div>
            <div v-if="isImprovementExpanded(index)">
              <div class="ui-item-form-inline-grid mt-2">
                <label class="ui-item-form-field">
                  <span class="ui-item-form-label">Nombre reforma</span>
                  <input
                    v-model="improvement.name"
                    placeholder="Ej: Reforma cocina"
                    class="input ui-data-field"
                  />
                </label>
                <label class="ui-item-form-field">
                  <span class="ui-item-form-label">Fecha</span>
                  <input
                    v-model="improvement.reform_date"
                    type="date"
                    class="input ui-data-field"
                  />
                </label>
                <label class="ui-item-form-field">
                  <span class="ui-item-form-label">
                    Importe{{
                      currencySymbol(form.currency) ? ` (${currencySymbol(form.currency)})` : ''
                    }}
                  </span>
                  <input
                    v-model="improvement.amount"
                    inputmode="decimal"
                    placeholder="Ej: 12000"
                    class="input ui-data-field"
                  />
                </label>
                <label class="ui-item-form-field">
                  <span class="ui-item-form-label">Amortizacion</span>
                  <select v-model="improvement.amortization_method" class="select ui-data-field">
                    <option
                      v-for="opt in PRIMARY_HOME_IMPROVEMENT_AMORTIZATION_OPTIONS"
                      :key="opt.value"
                      :value="opt.value"
                    >
                      {{ opt.label }}
                    </option>
                  </select>
                </label>
                <label
                  v-if="improvement.amortization_method === 'straight_line'"
                  class="ui-item-form-field"
                >
                  <span class="ui-item-form-label">Plazo amortización (años)</span>
                  <input
                    v-model="improvement.amortization_term_years"
                    inputmode="numeric"
                    placeholder="Ej: 10"
                    class="input ui-data-field"
                  />
                </label>
                <label
                  v-if="improvement.amortization_method === 'manual'"
                  class="ui-item-form-field"
                >
                  <span class="ui-item-form-label">Valor actual manual</span>
                  <input
                    v-model="improvement.manual_current_value"
                    inputmode="decimal"
                    placeholder="Ej: 8500"
                    class="input ui-data-field"
                  />
                </label>
                <label class="ui-item-form-field">
                  <span class="ui-item-form-label">TAE financiacion (%)</span>
                  <input
                    v-model="improvement.annual_interest_tae"
                    inputmode="decimal"
                    placeholder="Opcional"
                    class="input ui-data-field"
                  />
                </label>
              </div>
              <label class="checkbox-row mt-1">
                <input
                  v-model="improvement.capitalize_interest"
                  type="checkbox"
                  :disabled="!canCapitalizeImprovementInterest(improvement)"
                />
                <span>Capitalizar TAE en valor de reforma</span>
              </label>
              <div v-if="!canCapitalizeImprovementInterest(improvement)" class="ui-form-help">
                Disponible solo cuando la TAE de financiacion es mayor que 0.
              </div>
              <label class="ui-item-form-field mt-1">
                <span class="ui-item-form-label">Notas</span>
                <textarea
                  v-model="improvement.notes"
                  rows="2"
                  class="textarea"
                  placeholder="Notas de la reforma"
                ></textarea>
              </label>
            </div>
          </div>
        </div>
      </div>

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

      <div
        v-if="showLiabilityAdvancedFields"
        class="ui-item-form-section ui-item-form-field-span-2"
      >
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
              @change="onLiabilityPaymentStartDateInput"
            />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Fecha fin</span>
            <input
              v-model="form.expected_end_date"
              type="date"
              class="input ui-data-field"
              @change="onLiabilityEndDateInput"
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
              @input="onLiabilityTermInput"
            />
          </label>
          <label class="ui-item-form-field">
            <span class="ui-item-form-label">Frecuencia</span>
            <select v-model="form.payment_frequency" class="select ui-data-field">
              <option
                v-for="opt in LIABILITY_PAYMENT_FREQUENCIES"
                :key="opt.value"
                :value="opt.value"
              >
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
            <small v-if="showMortgageFeeFields" class="subtle"
              >(sin incluir costes opcionales)</small
            >
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
          Si no indicas importe, se estimará con "Amortización anticipada (%)" sobre el saldo
          pendiente. La opción de cuota decide si el mes de cancelación sigue contando como pago
          recurrente o si el presupuesto corta un mes antes.
        </div>
      </details>

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
