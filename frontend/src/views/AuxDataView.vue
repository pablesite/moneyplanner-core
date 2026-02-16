<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useAuxDataPage } from '@/domains/aux-data';

const router = useRouter();

const {
  loading,
  error,
  successMessage,
  fxRates,
  inflation,
  fxForm,
  fxPairs,
  fxRatePlaceholder,
  ipcForm,
  createFxRate,
  deleteFxRate,
  createInflation,
  deleteInflation,
  formatFxRate,
  formatInflationIndex,
} = useAuxDataPage();
</script>

<template>
  <div class="container">
    <div class="ui-page-header">
      <h1 class="h1 ui-page-title">Datos auxiliares</h1>

      <div class="ui-page-actions">
        <button class="btn" type="button" @click="router.push('/')">Volver a Patrimonio</button>
      </div>
    </div>

    <div v-if="error" class="alert mt-3">{{ error }}</div>
    <div v-if="successMessage" class="ui-alert-success">{{ successMessage }}</div>

    <div class="grid-2 section">
      <div class="card">
        <div class="ui-section-header">
          <h2 class="h2">FX rates</h2>
        </div>

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
            Añadir
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
              <td>{{ r.from_currency }} &rarr; {{ r.to_currency }}</td>
              <td>{{ formatFxRate(r.rate, r.from_currency, r.to_currency) }}</td>
              <td class="ui-data-table-actions">
                <button class="icon-btn" title="Eliminar" @click="deleteFxRate(r.id)">
                  &#128465;
                </button>
              </td>
            </tr>
            <tr v-if="!fxRates.length && !loading">
              <td colspan="4" class="ui-table-empty">No hay FX rates todavía.</td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="ui-section-header">
          <h2 class="h2">IPC</h2>
        </div>

        <div class="ui-data-form-grid">
          <select v-model="ipcForm.region" class="select ui-data-field">
            <option value="ES">España</option>
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
            Añadir
          </button>
        </div>

        <table class="ui-data-table">
          <thead>
            <tr>
              <th>Periodo</th>
              <th>Región</th>
              <th>Índice</th>
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
              <td colspan="4" class="ui-table-empty">No hay índices IPC todavía.</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="loading" class="ui-status-line">Cargando datos auxiliares...</div>
  </div>
</template>
