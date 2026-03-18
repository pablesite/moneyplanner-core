<script setup lang="ts">
type SnapshotRow = {
  id: number;
  snapshot_date: string;
  net_worth: string;
  total_assets: string;
  total_liabilities: string;
  base_currency: string | null;
};

defineProps<{
  snapshots: SnapshotRow[];
  loading: boolean;
  formatMoney: (value?: string | null, decimals?: number) => string;
  displayCurrencyUnit: (currency: string | null | undefined) => string;
  confirmDeleteSnapshot: (snapshotId: number) => void;
}>();
</script>

<template>
  <div class="section card ui-pro-panel">
    <h2 class="mt-0 text-base">Snapshots</h2>

    <ul v-if="snapshots.length" class="m-0 grid list-none gap-2 pl-0">
      <li v-for="snapshot in snapshots" :key="snapshot.id" class="ui-nw-snapshot-row">
        <div class="min-w-0">
          {{ snapshot.snapshot_date }} - neto: {{ formatMoney(snapshot.net_worth, 2) }}
          {{ displayCurrencyUnit(snapshot.base_currency) }}
          <span class="subtle">
            (activos {{ formatMoney(snapshot.total_assets, 2) }}
            {{ displayCurrencyUnit(snapshot.base_currency) }}, pasivos
            {{ formatMoney(snapshot.total_liabilities, 2) }}
            {{ displayCurrencyUnit(snapshot.base_currency) }})
          </span>
        </div>
        <button
          class="icon-btn disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          :disabled="loading"
          aria-label="Eliminar snapshot"
          title="Eliminar snapshot"
          @click="confirmDeleteSnapshot(snapshot.id)"
        >
          <span class="icon" aria-hidden="true">&#128465;</span>
        </button>
      </li>
    </ul>

    <div v-else class="subtle">No hay snapshots todavia.</div>
  </div>
</template>
