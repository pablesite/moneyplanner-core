<script setup lang="ts">
import { reactive } from 'vue';
import { useAuxDataPage } from '@/domains/aux-data';

const {
  loading,
  error,
  successMessage,
  inflation,
  ipcForm,
  createInflation,
  deleteInflation,
  formatInflationIndex,
  fxRates,
  fxForm,
  fxPairs,
  fxRatePlaceholder,
  createFxRate,
  deleteFxRate,
  formatFxRate,
} = useAuxDataPage();

const sections = reactive({
  ipc: true,
  fx: false,
});

function toggleSection(section: 'ipc' | 'fx'): void {
  sections[section] = !sections[section];
}
</script>

<template>
  <div class="container ui-pro-page">
    <h1 class="h1 ui-settings-page-title">Settings</h1>

    <div v-if="error" class="alert mt-3">{{ error }}</div>
    <div v-if="successMessage" class="ui-alert-success">{{ successMessage }}</div>

    <section class="card ui-pro-panel ui-settings-accordion-item">
      <button
        class="ui-settings-toggle"
        type="button"
        :aria-expanded="sections.ipc"
        @click="toggleSection('ipc')"
      >
        <span class="ui-settings-toggle-title">Datos IPC</span>
        <span class="ui-settings-toggle-icon" aria-hidden="true">
          {{ sections.ipc ? '-' : '+' }}
        </span>
      </button>
      <div v-if="sections.ipc" class="ui-settings-content">
        <div class="ui-data-form-grid">
          <select v-model="ipcForm.region" class="select ui-data-field">
            <option value="ES">Espana</option>
          </select>
          <input
            v-model="ipcForm.period"
            type="month"
            class="input ui-data-field"
            :class="{ 'ui-data-date-empty': !ipcForm.period }"
            placeholder="mm/aaaa"
          />
          <input
            v-model="ipcForm.index"
            class="input ui-data-field"
            inputmode="decimal"
            placeholder="118.0"
          />
          <button
            class="btn btn-primary ui-data-field px-[14px]"
            type="button"
            :disabled="loading"
            @click="createInflation"
          >
            Anadir
          </button>
        </div>

        <table class="ui-data-table">
          <thead>
            <tr>
              <th>Periodo</th>
              <th>Region</th>
              <th>Indice</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in inflation" :key="r.id">
              <td>{{ r.period }}</td>
              <td>{{ r.region }}</td>
              <td>{{ formatInflationIndex(r.index) }}</td>
              <td class="ui-data-table-actions">
                <button class="icon-btn" title="Eliminar" @click="deleteInflation(r.id)">
                  &#128465;
                </button>
              </td>
            </tr>
            <tr v-if="!inflation.length && !loading">
              <td colspan="4" class="ui-table-empty">No hay indices IPC todavia.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <section class="card ui-pro-panel ui-settings-accordion-item">
      <button
        class="ui-settings-toggle"
        type="button"
        :aria-expanded="sections.fx"
        @click="toggleSection('fx')"
      >
        <span class="ui-settings-toggle-title">Tasas de conversion</span>
        <span class="ui-settings-toggle-icon" aria-hidden="true">
          {{ sections.fx ? '-' : '+' }}
        </span>
      </button>
      <div v-if="sections.fx" class="ui-settings-content">
        <div class="ui-data-form-grid">
          <input
            v-model="fxForm.rate_date"
            type="date"
            class="input ui-data-field"
            :class="{ 'ui-data-date-empty': !fxForm.rate_date }"
            placeholder="dd/mm/aa"
          />
          <select v-model="fxForm.pair" class="select ui-data-field">
            <option v-for="p in fxPairs" :key="p.value" :value="p.value">
              {{ p.label }}
            </option>
          </select>
          <input
            v-model="fxForm.rate"
            class="input ui-data-field"
            inputmode="decimal"
            :placeholder="fxRatePlaceholder"
          />
          <button
            class="btn btn-primary ui-data-field px-[14px]"
            type="button"
            :disabled="loading"
            @click="createFxRate"
          >
            Anadir
          </button>
        </div>

        <table class="ui-data-table">
          <thead>
            <tr>
              <th>Fecha</th>
              <th>Par</th>
              <th>Rate</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="r in fxRates" :key="r.id">
              <td>{{ r.rate_date }}</td>
              <td>{{ r.from_currency }} -> {{ r.to_currency }}</td>
              <td>{{ formatFxRate(r.rate, r.from_currency, r.to_currency) }}</td>
              <td class="ui-data-table-actions">
                <button class="icon-btn" title="Eliminar" @click="deleteFxRate(r.id)">
                  &#128465;
                </button>
              </td>
            </tr>
            <tr v-if="!fxRates.length && !loading">
              <td colspan="4" class="ui-table-empty">No hay FX rates todavia.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </section>

    <div v-if="loading" class="ui-status-line">Cargando datos auxiliares...</div>
  </div>
</template>

<style scoped>
.ui-settings-page-title {
  margin: 0 0 4px;
}

.ui-settings-accordion-item {
  padding: 0;
  overflow: hidden;
}

.ui-settings-toggle {
  width: 100%;
  border: 0;
  background: transparent;
  color: var(--text);
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 14px 16px;
  cursor: pointer;
  font-size: 16px;
}

.ui-settings-toggle:hover {
  background: rgba(255, 255, 255, 0.03);
}

.ui-settings-toggle-title {
  text-align: left;
  font-weight: 600;
}

.ui-settings-toggle-icon {
  width: 28px;
  height: 28px;
  border-radius: 999px;
  border: 1px solid rgba(255, 255, 255, 0.2);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 18px;
}

.ui-settings-content {
  border-top: 1px solid rgba(255, 255, 255, 0.09);
  padding: 12px 14px 14px;
}
</style>
