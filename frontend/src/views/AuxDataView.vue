<script setup lang="ts">
import { computed, onMounted, ref } from "vue";
import { useRouter } from "vue-router";
import { api } from "@/lib/api";

type FxRate = {
  id: number;
  rate_date: string;
  from_currency: string;
  to_currency: string;
  rate: string;
  updated_at: string;
};

type InflationIndex = {
  id: number;
  region: string;
  period: string;
  index: string;
  created_at: string;
  updated_at: string;
};

const router = useRouter();

const loading = ref(false);
const error = ref<string | null>(null);

const fxRates = ref<FxRate[]>([]);
const inflation = ref<InflationIndex[]>([]);

const fxForm = ref({
  rate_date: "",
  pair: "USD_EUR",
  rate: "",
});

const fxPairs = [
  { value: "BTC_USD", label: "BTC \u2192 USD", from: "BTC", to: "USD", hint: "70000" },
  { value: "ETH_USD", label: "ETH \u2192 USD", from: "ETH", to: "USD", hint: "2000" },
  { value: "USD_EUR", label: "USD \u2192 EUR", from: "USD", to: "EUR", hint: "0.92" },
];

const fxRatePlaceholder = computed(() => {
  const pair = fxPairs.find((p) => p.value === fxForm.value.pair);
  return pair?.hint ?? "0.00";
});

const ipcForm = ref({
  region: "ES",
  period: "",
  index: "",
});

async function loadAll() {
  loading.value = true;
  error.value = null;
  try {
    const [fxRes, ipcRes] = await Promise.all([
      api.get("/api/core/fx-rates/"),
      api.get("/api/core/inflation/"),
    ]);
    fxRates.value = fxRes.data ?? [];
    inflation.value = ipcRes.data ?? [];
  } catch (e: any) {
    error.value = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
  } finally {
    loading.value = false;
  }
}

async function createFxRate() {
  if (!fxForm.value.rate_date || !fxForm.value.pair || !fxForm.value.rate) return;
  loading.value = true;
  error.value = null;
  const pair = fxPairs.find((p) => p.value === fxForm.value.pair);
  if (!pair) return;
  try {
    await api.post("/api/core/fx-rates/", {
      rate_date: fxForm.value.rate_date,
      from_currency: pair.from,
      to_currency: pair.to,
      rate: fxForm.value.rate,
    });
    fxForm.value.rate = "";
    await loadAll();
  } catch (e: any) {
    error.value = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
  } finally {
    loading.value = false;
  }
}

async function deleteFxRate(id: number) {
  if (!confirm("Eliminar este FX rate?")) return;
  loading.value = true;
  error.value = null;
  try {
    await api.delete(`/api/core/fx-rates/${id}/`);
    await loadAll();
  } catch (e: any) {
    error.value = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
  } finally {
    loading.value = false;
  }
}

async function createInflation() {
  if (!ipcForm.value.region || !ipcForm.value.period || !ipcForm.value.index) return;
  loading.value = true;
  error.value = null;
  const monthValue = ipcForm.value.period;
  const period = monthValue.includes("-") ? `${monthValue}-01` : monthValue;
  try {
    await api.post("/api/core/inflation/", {
      region: ipcForm.value.region,
      period,
      index: ipcForm.value.index,
    });
    ipcForm.value.index = "";
    await loadAll();
  } catch (e: any) {
    error.value = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
  } finally {
    loading.value = false;
  }
}

async function deleteInflation(id: number) {
  if (!confirm("Eliminar este IPC?")) return;
  loading.value = true;
  error.value = null;
  try {
    await api.delete(`/api/core/inflation/${id}/`);
    await loadAll();
  } catch (e: any) {
    error.value = e?.response?.data ? JSON.stringify(e.response.data) : (e?.message || "Error");
  } finally {
    loading.value = false;
  }
}

onMounted(loadAll);

function formatFxRate(rate: string, from: string, to: string) {
  const n = Number(String(rate ?? "").replace(",", "."));
  if (!Number.isFinite(n)) return rate;
  if (from === "BTC" && to === "USD") return n.toFixed(2);
  if (from === "ETH" && to === "USD") return n.toFixed(2);
  if (from === "USD" && to === "EUR") return n.toFixed(4);
  return String(rate);
}

function formatInflationIndex(value: string) {
  const n = Number(String(value ?? "").replace(",", "."));
  if (!Number.isFinite(n)) return value;
  return n.toFixed(1);
}
</script>

<template>
  <div class="container">
    <div class="page-header">
      <h1 class="h1 page-title">Datos auxiliares</h1>

      <div class="page-actions">
        <button class="btn" type="button" @click="router.push('/')">
          Volver a Patrimonio
        </button>
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
          <input v-model="fxForm.rate" class="input" inputmode="decimal" :placeholder="fxRatePlaceholder" />
          <button class="btn btn-primary" type="button" @click="createFxRate" :disabled="loading">
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
                <button class="icon-btn" @click="deleteFxRate(r.id)" title="Eliminar">🗑️</button>
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
          <button class="btn btn-primary" type="button" @click="createInflation" :disabled="loading">
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
                <button class="icon-btn" @click="deleteInflation(r.id)" title="Eliminar">🗑️</button>
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
.page-header{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}
.page-title{
  margin: 0;
}
.page-actions{
  display: flex;
  align-items: center;
  gap: 10px;
}
.section-header{
  display: grid;
  gap: 4px;
  margin-bottom: 12px;
}
.form-grid{
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr)) auto;
  gap: 10px;
  align-items: end;
  margin-bottom: 14px;
}
.form-grid .input,
.form-grid .select,
.form-grid .btn{
  font-size: 13px;
  height: 38px;
  line-height: normal;
}
.form-grid .input,
.form-grid .select{
  padding-top: 8px;
  padding-bottom: 8px;
}
.form-grid .btn{
  line-height: 38px;
}
.form-grid .btn{
  padding: 0 14px;
}
.form-grid > *{
  min-width: 0;
}
.date-input,
.month-input{
  min-width: 0;
  max-width: 100%;
  padding-right: 30px;
}
.date-input.is-empty,
.month-input.is-empty{
  color: rgba(255,255,255,0.5);
  background: rgba(255,255,255,0.04);
}
.date-input::-webkit-datetime-edit,
.month-input::-webkit-datetime-edit{
  white-space: nowrap;
}
.date-input::-webkit-datetime-edit-fields-wrapper,
.month-input::-webkit-datetime-edit-fields-wrapper{
  padding-right: 6px;
}
.table{
  width: 100%;
  border-collapse: collapse;
}
.table th,
.table td{
  text-align: left;
  padding: 8px 6px;
  border-bottom: 1px solid rgba(255,255,255,0.08);
  font-size: 13px;
}
.cell-actions{
  text-align: right;
  width: 1%;
  white-space: nowrap;
}
@media (max-width: 900px){
  .form-grid{
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}
</style>
