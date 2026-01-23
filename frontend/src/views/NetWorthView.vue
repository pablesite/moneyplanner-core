<script setup lang="ts">
import { onMounted } from "vue";
import { useNetWorthStore } from "@/stores/netWorth";

const store = useNetWorthStore();

onMounted(() => {
  store.refreshAll();
});
</script>

<template>
  <div style="max-width: 1000px; margin: 0 auto; padding: 24px; font-family: system-ui;">
    <h1>Patrimonio</h1>

    <div v-if="store.error" style="padding: 12px; border: 1px solid #f99; background: #fee; margin: 12px 0;">
      {{ store.error }}
    </div>

    <div style="display: flex; gap: 12px; margin: 16px 0; flex-wrap: wrap;">
      <div style="border: 1px solid #ddd; border-radius: 8px; padding: 12px; min-width: 220px;">
        <div>Total activos</div>
        <div style="font-size: 24px;">{{ store.summary?.total_assets ?? "-" }}</div>
      </div>

      <div style="border: 1px solid #ddd; border-radius: 8px; padding: 12px; min-width: 220px;">
        <div>Total pasivos</div>
        <div style="font-size: 24px;">{{ store.summary?.total_liabilities ?? "-" }}</div>
      </div>

      <div style="border: 1px solid #ddd; border-radius: 8px; padding: 12px; min-width: 220px;">
        <div>Patrimonio neto</div>
        <div style="font-size: 24px;">{{ store.summary?.net_worth ?? "-" }}</div>
      </div>

      <button
        @click="store.createTodaySnapshot()"
        :disabled="store.loading"
        style="padding: 12px 16px; border-radius: 8px; border: 1px solid #111; background: #111; color: #fff; cursor: pointer;"
      >
        Guardar snapshot de hoy
      </button>

      <button
        @click="store.refreshAll()"
        :disabled="store.loading"
        style="padding: 12px 16px; border-radius: 8px; border: 1px solid #111; background: #fff; color: #111; cursor: pointer;"
      >
        Refrescar
      </button>
    </div>

    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px;">
      <div style="border: 1px solid #ddd; border-radius: 8px; padding: 12px;">
        <h2>Activos</h2>
        <ul v-if="store.assets.length">
          <li v-for="a in store.assets" :key="a.id">
            {{ a.name }} — {{ a.amount }} {{ a.currency }} ({{ a.category }}) <span v-if="!a.is_active">[archivado]</span>
          </li>
        </ul>
        <div v-else>No hay activos todavía.</div>
      </div>

      <div style="border: 1px solid #ddd; border-radius: 8px; padding: 12px;">
        <h2>Pasivos</h2>
        <ul v-if="store.liabilities.length">
          <li v-for="l in store.liabilities" :key="l.id">
            {{ l.name }} — {{ l.amount }} {{ l.currency }} ({{ l.category }}) <span v-if="!l.is_active">[archivado]</span>
          </li>
        </ul>
        <div v-else>No hay pasivos todavía.</div>
      </div>
    </div>

    <div style="margin-top: 24px; border: 1px solid #ddd; border-radius: 8px; padding: 12px;">
      <h2>Snapshots</h2>
      <ul v-if="store.snapshots.length">
        <li v-for="s in store.snapshots" :key="s.id">
          {{ s.snapshot_date }} — neto: {{ s.net_worth }} (activos {{ s.total_assets }}, pasivos {{ s.total_liabilities }})
        </li>
      </ul>
      <div v-else>No hay snapshots todavía.</div>
    </div>

    <div v-if="store.loading" style="margin-top: 12px;">Cargando...</div>
  </div>
</template>
