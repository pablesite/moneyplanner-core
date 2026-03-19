<script setup lang="ts">
/* eslint-disable vue/no-mutating-props */
import { type PropType } from 'vue';
import BaseModal from '@/domains/ui/components/BaseModal.vue';

defineProps({
  page: {
    type: Object as PropType<any>,
    required: true,
  },
});
</script>

<template>
  <BaseModal
    :open="page.showActivationModal"
    title="Activar tracking contable"
    @close="page.showActivationModal = false"
  >
    <form
      class="ui-accounting-form ui-accounting-modal-form"
      @submit.prevent="page.activatePositionFromModal"
    >
      <p class="subtle">
        Selecciona una o varias posiciones manuales del patrimonio para activar su seguimiento
        contable en el ledger. Core generara automaticamente el saldo de apertura.
      </p>

      <div class="ui-accounting-form-grid">
        <select v-model="page.activationForm.position_type" class="select">
          <option
            v-for="type in page.manualPositionTypeOptions"
            :key="type.value"
            :value="type.value"
          >
            {{ type.label }}
          </option>
        </select>
        <input
          v-model="page.activationQuery"
          class="input"
          type="search"
          placeholder="Buscar posicion por nombre o divisa"
          :disabled="!page.availableManualPositionOptions.length"
        />
      </div>
      <label v-if="page.activationForm.position_type === 'asset'" class="ui-accounting-inline-note">
        <input v-model="page.activationOperationalOnly" type="checkbox" />
        Mostrar solo activos operativos recomendados (liquidez e inversiones)
      </label>
      <p
        v-if="
          page.activationExcludedByOperationalFilter > 0 &&
          page.activationForm.position_type === 'asset'
        "
        class="ui-accounting-inline-note"
      >
        Se han ocultado {{ page.activationExcludedByOperationalFilter }} activos no operativos (ej:
        vivienda/mobiliario). Desactiva el filtro para verlos.
      </p>

      <div v-if="page.availableManualPositionOptions.length" class="ui-accounting-inline-actions">
        <p class="ui-accounting-inline-note">
          {{ page.selectedActivationIds.length }} seleccionadas
        </p>
        <button class="btn" type="button" @click="page.toggleSelectAllFiltered">
          {{ page.allFilteredSelected ? 'Quitar seleccion visible' : 'Seleccionar visibles' }}
        </button>
      </div>

      <div v-if="page.groupedManualPositionOptions.length" class="ui-accounting-activation-list">
        <div v-for="group in page.groupedManualPositionOptions" :key="group.key">
          <p class="ui-accounting-inline-note">
            <strong>{{ group.label }}</strong>
          </p>
          <label
            v-for="position in group.positions"
            :key="position.id"
            class="ui-accounting-activation-option"
          >
            <input
              v-model="page.selectedActivationIds"
              class="ui-accounting-activation-checkbox"
              type="checkbox"
              :value="position.id"
            />
            <span class="ui-accounting-activation-meta">
              <strong>{{ position.name }}</strong>
              <small>{{ position.currency }}</small>
            </span>
          </label>
        </div>
      </div>
      <div
        v-else-if="page.availableManualPositionOptions.length && page.activationQuery.trim()"
        class="ui-accounting-empty"
      >
        No hay coincidencias para la busqueda actual.
      </div>

      <div v-if="!page.hasAvailableManualPositions" class="ui-accounting-empty">
        No hay activos ni pasivos manuales disponibles para activar desde esta vista.
      </div>
      <p v-else class="ui-accounting-inline-note">
        Al activar una posicion, Core la vincula al ledger y genera automaticamente el saldo de
        apertura contra patrimonio neto contable.
      </p>

      <div class="ui-accounting-submit-row">
        <p class="ui-accounting-inline-note">
          Solo se muestran posiciones del patrimonio con `tracking_mode=manual`.
        </p>
        <button
          class="btn btn-primary"
          type="submit"
          :disabled="page.accountActivationLoading || !page.selectedActivationIds.length"
        >
          {{
            page.accountActivationLoading
              ? 'Activando...'
              : `Activar tracking (${page.selectedActivationIds.length})`
          }}
        </button>
      </div>
    </form>
  </BaseModal>
</template>
