<script setup lang="ts">
import {
  PRIMARY_HOME_VALUATION_MODE_OPTIONS,
  PRIMARY_HOME_VALUATION_PROFILES,
  PRIMARY_HOME_CUSTOM_PROFILE_VALUE,
  PRIMARY_HOME_IMPROVEMENT_AMORTIZATION_OPTIONS,
  canCapitalizeImprovementInterest,
  improvementRemoveLabel,
  formatImprovementSummaryDate,
  formatImprovementSummaryAmount,
  currencySymbol,
  type PrimaryHomeImprovementDraft,
} from './itemFormUtils';

interface FormSlice {
  valuation_model: string;
  land_value_share_percent: string;
  land_annual_appreciation_percent: string;
  building_annual_depreciation_percent: string;
  currency: string;
}

const form = defineModel<FormSlice>('form', { required: true });
const profile = defineModel<string>('primaryHomeValuationProfile', { required: true });

defineProps<{
  showPrimaryHomeAutoValuationFields: boolean;
  primaryHomeImprovements: PrimaryHomeImprovementDraft[];
  isImprovementExpanded: (index: number) => boolean;
  toggleImprovementExpanded: (index: number) => void;
  addPrimaryHomeImprovement: () => void;
  removePrimaryHomeImprovement: (index: number) => void;
}>();
</script>

<template>
  <div class="ui-item-form-section ui-item-form-field-span-2">
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
        <select v-model="profile" class="select ui-data-field">
          <option v-for="p in PRIMARY_HOME_VALUATION_PROFILES" :key="p.value" :value="p.value">
            {{ p.label }}
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
            @click="addPrimaryHomeImprovement()"
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
              :aria-label="isImprovementExpanded(index) ? 'Compactar reforma' : 'Expandir reforma'"
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
              <input v-model="improvement.reform_date" type="date" class="input ui-data-field" />
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
            <label v-if="improvement.amortization_method === 'manual'" class="ui-item-form-field">
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
</template>
