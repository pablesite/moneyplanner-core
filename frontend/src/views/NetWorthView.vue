<script setup lang="ts">
import { onMounted } from "vue";
import { useNetWorthStore } from "@/stores/netWorth";
import ItemForm from "@/components/ItemForm.vue";
import ItemList from "@/components/ItemList.vue";

const store = useNetWorthStore();

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

onMounted(() => {
  store.refreshAll();
});
</script>

<template>
  <div class="container">
    <h1 class="h1">Patrimonio</h1>

    <div v-if="store.error" class="alert">
      {{ store.error }}
    </div>

    <div class="toolbar">
      <div class="grid-3" style="flex: 1; min-width: 320px;">
        <div class="card">
          <div class="card-title">Total activos</div>
          <div class="card-value">{{ store.summary?.total_assets ?? "-" }}</div>
        </div>

        <div class="card">
          <div class="card-title">Total pasivos</div>
          <div class="card-value">{{ store.summary?.total_liabilities ?? "-" }}</div>
        </div>

        <div class="card">
          <div class="card-title">Patrimonio neto</div>
          <div class="card-value">{{ store.summary?.net_worth ?? "-" }}</div>
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
          {{ s.snapshot_date }} — neto: {{ s.net_worth }}
          <span class="subtle">(activos {{ s.total_assets }}, pasivos {{ s.total_liabilities }})</span>
        </li>
      </ul>

      <div v-else class="subtle">No hay snapshots todavía.</div>
    </div>

    <div v-if="store.loading" class="section subtle">Cargando...</div>
  </div>
</template>
