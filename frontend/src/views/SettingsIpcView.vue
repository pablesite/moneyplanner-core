<script setup lang="ts">
import { useRouter } from 'vue-router';
import { useAuxDataPage } from '@/domains/aux-data';

const router = useRouter();
const {
  loading,
  error,
  successMessage,
  inflation,
  ipcForm,
  createInflation,
  deleteInflation,
  formatInflationIndex,
} = useAuxDataPage();
</script>

<template>
  <div class="container ui-pro-page">
    <div class="ui-page-header">
      <h1 class="h1 ui-page-title">Settings | IPC</h1>

      <div class="ui-page-actions">
        <button class="btn" type="button" @click="router.push('/data')">Volver a Settings</button>
      </div>
    </div>

    <div v-if="error" class="alert mt-3">{{ error }}</div>
    <div v-if="successMessage" class="ui-alert-success">{{ successMessage }}</div>

    <section class="card ui-pro-panel">
      <div class="ui-section-header">
        <h2 class="h2">Modulo: IPC</h2>
      </div>

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
    </section>

    <div v-if="loading" class="ui-status-line">Cargando modulo IPC...</div>
  </div>
</template>
