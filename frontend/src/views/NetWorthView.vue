<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useNetWorthStore } from "@/stores/netWorth";
import ItemForm from "@/components/ItemForm.vue";
import ItemList from "@/components/ItemList.vue";


const store = useNetWorthStore();

const valueMode = ref<"nominal" | "real">("nominal");

const canShowReal = () => store.baseCurrency === "EUR" && !!store.summary?.net_worth_real;

watch(
  () => store.baseCurrency,
  (c) => {
    if (c !== "EUR" && valueMode.value === "real") {
      valueMode.value = "nominal";
    }
  }
);

const currencies = [
  { value: "EUR", label: "EUR" },
  { value: "USD", label: "USD" },
  { value: "BTC", label: "BTC" },
  { value: "ETH", label: "ETH" },
];

const assetCategories = [
  { value: "cash", label: "Liquidez" },
  { value: "investments", label: "Inversiones" },
  { value: "real_estate", label: "Inmuebles" },
  { value: "vehicle", label: "Vehículo" },
  { value: "other", label: "Otros" },
];

const liabilityCategories = [
  { value: "mortgage", label: "Hipoteca" },
  { value: "personal_loan", label: "Préstamo personal" },
  { value: "credit_card", label: "Tarjeta" },
  { value: "other", label: "Otros" },
];

const prettyError = () => {
  if (!store.error) return null;
  try {
    const parsed = JSON.parse(store.error);
    if (parsed?.detail) return parsed.detail;
    return store.error;
  } catch {
    return store.error;
  }
};

const pick = (nominal?: string, real?: string) => {
  if (valueMode.value === "real") return real ?? "-";
  return nominal ?? "-";
};


onMounted(async () => {
  await store.fetchSettings();
  await store.refreshAll();
});
</script>

<template>
  <div class="container">
    <h1 class="h1">Patrimonio</h1>

    <div v-if="store.error" class="alert">
      {{ prettyError() }}
    </div>

    <div class="toolbar">
      <div class="grid-3" style="flex: 1; min-width: 320px;">
        <div class="card">
          <div class="card-title">Total activos</div>
          <div class="card-value">
            {{ pick(store.summary?.total_assets, store.summary?.total_assets_real) }}
            <span class="subtle" style="margin-left:6px;">{{ store.baseCurrency ?? "" }}</span>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Total pasivos</div>
          <div class="card-value">
            {{ pick(store.summary?.total_liabilities, store.summary?.total_liabilities_real) }}
            <span class="subtle" style="margin-left:6px;">{{ store.baseCurrency ?? "" }}</span>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Patrimonio neto</div>
          <div class="card-value">
            {{ pick(store.summary?.net_worth, store.summary?.net_worth_real) }}
            <span class="subtle" style="margin-left:6px;">{{ store.baseCurrency ?? "" }}</span>
          </div>
        </div>
      </div>

      <!-- Moneda base -->
      <div class="card" style="display:flex; align-items:center; gap:12px; padding:12px 14px;">
        <div style="display:flex; flex-direction:column; gap:4px;">
          <div class="card-title">Moneda base</div>
          <div class="subtle" style="font-size:12px;">Totales y snapshots en esta moneda</div>
        </div>

        <select
          class="input"
          style="width: 110px;"
          :value="store.baseCurrency ?? 'EUR'"
          @change="store.updateBaseCurrency(($event.target as HTMLSelectElement).value)"
          :disabled="store.loading"
        >
          <option v-for="c in currencies" :key="c.value" :value="c.value">
            {{ c.label }}
          </option>
        </select>
      </div>

      <!-- Modo nominal/real -->
      <div class="card" style="display:flex; align-items:center; gap:12px; padding:12px 14px;">
        <div style="display:flex; flex-direction:column; gap:4px;">
          <div class="card-title">Modo</div>
          <div class="subtle" style="font-size:12px;">
            {{ valueMode === "real" ? "Euros constantes (IPC)" : "Nominal" }}
          </div>
          <div
            v-if="valueMode === 'real' && store.summary?.inflation_base_period"
            class="subtle"
            style="font-size:12px;"
          >
            Base: {{ store.summary.inflation_base_period }}
          </div>
        </div>

        <select class="input" style="width: 150px;" v-model="valueMode">
          <option value="nominal">Nominal</option>
          <option value="real" :disabled="!canShowReal()">Real (IPC)</option>
        </select>

        <div v-if="store.baseCurrency !== 'EUR'" class="subtle" style="font-size:12px;">
          Solo disponible con EUR
        </div>
      </div>

      <button class="btn btn-primary" @click="store.createTodaySnapshot()" :disabled="store.loading">
        Guardar snapshot de hoy
      </button>

      <button class="btn" @click="store.refreshAll()" :disabled="store.loading">
        Refrescar
      </button>
    </div>

    <div class="grid-2">
      <div>
        <ItemForm title="Nuevo activo" :categories="assetCategories" :onSubmit="store.createAsset" />
        <ItemList
          title="Activos"
          :items="store.assets"
          :categories="assetCategories"
          :onUpdate="store.updateAsset"
          :onArchive="store.archiveAsset"
        />
      </div>

      <div>
        <ItemForm title="Nuevo pasivo" :categories="liabilityCategories" :onSubmit="store.createLiability" />
        <ItemList
          title="Pasivos"
          :items="store.liabilities"
          :categories="liabilityCategories"
          :onUpdate="store.updateLiability"
          :onArchive="store.archiveLiability"
        />
      </div>
    </div>

    <div class="section card">
      <h2 style="margin-top: 0;">Snapshots</h2>

      <ul v-if="store.snapshots.length" style="margin: 0; padding-left: 18px; display: grid; gap: 8px;">
        <li v-for="s in store.snapshots" :key="s.id">
          {{ s.snapshot_date }} — neto: {{ s.net_worth }} {{ s.base_currency }}
          <span class="subtle">
            (activos {{ s.total_assets }} {{ s.base_currency }}, pasivos {{ s.total_liabilities }} {{ s.base_currency }})
          </span>
        </li>
      </ul>

      <div v-else class="subtle">No hay snapshots todavía.</div>
    </div>

    <div v-if="store.loading" class="section subtle">Cargando...</div>
  </div>
</template>
