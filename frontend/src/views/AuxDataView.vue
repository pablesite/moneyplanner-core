<script setup lang="ts">
import { onMounted } from 'vue';
import { useRouter } from 'vue-router';
import { useAuxData } from '@/domains/aux-data/composables';

const router = useRouter();

const {
  loading,
  error,
  fxRates,
  inflation,
  fxForm,
  fxPairs,
  fxRatePlaceholder,
  ipcForm,
  loadAll,
  createFxRate,
  deleteFxRate,
  createInflation,
  deleteInflation,
  formatFxRate,
  formatInflationIndex,
} = useAuxData();

onMounted(loadAll);
</script>

<template>
  <div class="container">
    <div class="page-header">
      <h1 class="h1 page-title">Datos auxiliares</h1>

      <div class="page-actions">
        <button class="btn" type="button" @click="router.push('/')">Volver a Patrimonio</button>
      </div>
    </div>

    <div v-if="error" class="alert">{{ error }}</div>

    <div class="grid-2 section">
      <div class="card">
        <div class="section-header">
          <h2 class="h2">FX rates</h2>
        </div>

        <div class="form-grid">
          <input
            v-model="fxForm.rate_date"
            type="date"
            class="input date-input"
            :class="{ 'is-empty': !fxForm.rate_date }"
            placeholder="dd/mm/aa"
          />
          <select v-model="fxForm.pair" class="select">
            <option v-for="p in fxPairs" :key="p.value" :value="p.value">
              {{ p.label }}
            </option>
          </select>
          <input
            v-model="fxForm.rate"
            class="input"
            inputmode="decimal"
            :placeholder="fxRatePlaceholder"
          />
          <button class="btn btn-primary" type="button" :disabled="loading" @click="createFxRate">
            Añadir
          </button>
        </div>

        <table class="table">
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
              <td>{{ r.from_currency }} → {{ r.to_currency }}</td>
              <td>{{ formatFxRate(r.rate, r.from_currency, r.to_currency) }}</td>
              <td class="cell-actions">
                <button class="icon-btn" title="Eliminar" @click="deleteFxRate(r.id)">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>

      <div class="card">
        <div class="section-header">
          <h2 class="h2">IPC</h2>
        </div>

        <div class="form-grid">
          <select v-model="ipcForm.region" class="select">
            <option value="ES">España</option>
          </select>
          <input
            v-model="ipcForm.period"
            type="month"
            class="input month-input"
            :class="{ 'is-empty': !ipcForm.period }"
            placeholder="mm/aaaa"
          />
          <input v-model="ipcForm.index" class="input" inputmode="decimal" placeholder="118.0" />
          <button
            class="btn btn-primary"
            type="button"
            :disabled="loading"
            @click="createInflation"
          >
            Añadir
          </button>
        </div>

        <table class="table">
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
              <td class="cell-actions">
                <button class="icon-btn" title="Eliminar" @click="deleteInflation(r.id)">🗑️</button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>

    <div v-if="loading" class="section subtle">Cargando...</div>
  </div>
</template>

<style scoped>
.page-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.page-title {
  margin: 0;
}
.page-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}
.section-header {
  display: grid;
  gap: 4px;
  margin-bottom: 12px;
}
.form-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr)) auto;
  gap: 10px;
  align-items: end;
  margin-bottom: 14px;
}
.form-grid .input,
.form-grid .select,
.form-grid .btn {
  font-size: 13px;
  height: 38px;
  line-height: normal;
}
.form-grid .input,
.form-grid .select {
  padding-top: 8px;
  padding-bottom: 8px;
}
.form-grid .btn {
  line-height: 38px;
}
.form-grid .btn {
  padding: 0 14px;
}
.form-grid > * {
  min-width: 0;
}
.date-input,
.month-input {
  min-width: 0;
  max-width: 100%;
  padding-right: 30px;
}
.date-input.is-empty,
.month-input.is-empty {
  color: rgba(255, 255, 255, 0.5);
  background: rgba(255, 255, 255, 0.04);
}
.date-input::-webkit-datetime-edit,
.month-input::-webkit-datetime-edit {
  white-space: nowrap;
}
.date-input::-webkit-datetime-edit-fields-wrapper,
.month-input::-webkit-datetime-edit-fields-wrapper {
  padding-right: 6px;
}
.table {
  width: 100%;
  border-collapse: collapse;
}
.table th,
.table td {
  text-align: left;
  padding: 8px 6px;
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  font-size: 13px;
}
.cell-actions {
  text-align: right;
  width: 1%;
  white-space: nowrap;
}
@media (max-width: 900px) {
  .form-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
