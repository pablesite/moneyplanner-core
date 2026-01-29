<script setup lang="ts">
import { onMounted, ref, watch } from "vue";
import { useNetWorthStore } from "@/stores/netWorth";
import ItemForm from "@/components/ItemForm.vue";
import ItemList from "@/components/ItemList.vue";

const store = useNetWorthStore();

const valueMode = ref<"nominal" | "real">("nominal");

// Real solo si: EUR + tenemos base_period + tenemos net_worth_real
const canShowReal = () =>
  store.baseCurrency === "EUR" &&
  !!store.summary?.inflation_base_period &&
  store.summary?.net_worth_real !== null;

watch(
  () => store.baseCurrency,
  (c) => {
    if (c !== "EUR" && valueMode.value === "real") {
      valueMode.value = "nominal";
    }
  }
);

watch(
  () => store.summary?.inflation_base_period,
  () => {
    if (!canShowReal() && valueMode.value === "real") {
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

const pick = (nominal?: string | null, real?: string | null) => {
  if (valueMode.value === "real") return real ?? "-";
  return nominal ?? "-";
};

const unitLabel = () => {
  const c = store.baseCurrency ?? "";
  if (valueMode.value !== "real") return c;
  const base = store.summary?.inflation_base_period;
  return base ? `${c} (${base})` : `${c} (IPC)`;
};

const modeLabel = () => {
  if (valueMode.value === "nominal") return "Nominal (euros de hoy)";
  const base = store.summary?.inflation_base_period;
  return base ? `IPC: euros de ${base}` : "IPC: euros del mes base";
};

const money = (v?: string | null) => (v ?? "-");

const hasUnassigned = () => {
  const u = store.byMemberSummary?.unassigned;
  if (!u) return false;
  return (u.assets !== "0" && u.assets !== "0.00") || (u.liabilities !== "0" && u.liabilities !== "0.00");
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
            <span class="subtle" style="margin-left:6px;">{{ unitLabel() }}</span>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Total pasivos</div>
          <div class="card-value">
            {{ pick(store.summary?.total_liabilities, store.summary?.total_liabilities_real) }}
            <span class="subtle" style="margin-left:6px;">{{ unitLabel() }}</span>
          </div>
        </div>

        <div class="card">
          <div class="card-title">Patrimonio neto</div>
          <div class="card-value">
            {{ pick(store.summary?.net_worth, store.summary?.net_worth_real) }}
            <span class="subtle" style="margin-left:6px;">{{ unitLabel() }}</span>
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
            {{ modeLabel() }}
          </div>
          <div
            v-if="valueMode === 'real' && store.summary?.inflation_base_period"
            class="subtle"
            style="font-size:12px;"
          >
            Base: {{ store.summary.inflation_base_period }}
          </div>
        </div>

        <select
          class="input"
          style="width: 170px;"
          v-model="valueMode"
          :disabled="store.loading"
        >
          <option value="nominal">Nominal</option>
          <option value="real" :disabled="!canShowReal()">IPC (euros mes base)</option>
        </select>

        <div v-if="store.baseCurrency !== 'EUR'" class="subtle" style="font-size:12px;">
          Solo disponible con EUR
        </div>

        <div v-else-if="!canShowReal()" class="subtle" style="font-size:12px;">
          Requiere IPC cargado
        </div>
      </div>

      <button class="btn btn-primary" @click="store.createTodaySnapshot()" :disabled="store.loading">
        Guardar snapshot de hoy
      </button>

      <button class="btn" @click="store.refreshAll()" :disabled="store.loading">
        Refrescar
      </button>
    </div>


    <div class="section card" v-if="store.byMemberSummary">
      <h2 style="margin-top: 0;">Por miembro</h2>

      <div v-if="hasUnassigned()" class="alert" style="margin-bottom: 12px;">
        Hay activos/pasivos sin titularidad asignada (ownership = null).
        <div class="subtle" style="margin-top:6px;">
          Sin asignar — Activos: {{ money(store.byMemberSummary.unassigned.assets) }} {{ store.byMemberSummary.base_currency }},
          Pasivos: {{ money(store.byMemberSummary.unassigned.liabilities) }} {{ store.byMemberSummary.base_currency }}
        </div>
      </div>

      <table style="width:100%; border-collapse: collapse;">
        <thead>
          <tr>
            <th style="text-align:left; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">Miembro</th>
            <th style="text-align:right; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">Activos ({{ store.byMemberSummary.base_currency }})</th>
            <th style="text-align:right; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">Pasivos ({{ store.byMemberSummary.base_currency }})</th>
            <th style="text-align:right; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">Neto ({{ store.byMemberSummary.base_currency }})</th>
          </tr>
        </thead>

        <tbody>
          <tr v-for="row in store.byMemberSummary.by_member" :key="row.member.id">
            <td style="padding:8px 6px;">
              {{ row.member.name }}
              <span class="subtle" style="margin-left:6px; font-size:12px;">
                ({{ row.member.role === 'adult' ? 'Adulto' : 'Niño' }})
              </span>
            </td>
            <td style="padding:8px 6px; text-align:right;">{{ money(row.total_assets) }}</td>
            <td style="padding:8px 6px; text-align:right;">{{ money(row.total_liabilities) }}</td>
            <td style="padding:8px 6px; text-align:right;">{{ money(row.net_worth) }}</td>
          </tr>

          <tr>
            <td style="padding:10px 6px; text-align:left; border-top: 1px solid rgba(0,0,0,.08);">
              <span class="subtle">Total</span>
            </td>
            <td style="padding:10px 6px; text-align:right; border-top: 1px solid rgba(0,0,0,.08);">
              {{ money(store.byMemberSummary.totals.total_assets) }}
            </td>
            <td style="padding:10px 6px; text-align:right; border-top: 1px solid rgba(0,0,0,.08);">
              {{ money(store.byMemberSummary.totals.total_liabilities) }}
            </td>
            <td style="padding:10px 6px; text-align:right; border-top: 1px solid rgba(0,0,0,.08);">
              {{ money(store.byMemberSummary.totals.net_worth) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>


    <div class="grid-2">
      <div>

        <ItemForm
          title="Nuevo activo"
          :categories="assetCategories"
          :ownerships="store.ownerships"
          :onSubmit="store.createAsset"
        />

        <ItemList
          title="Activos"
          :items="store.assets"
          :categories="assetCategories"
          :ownerships="store.ownerships"
          :onUpdate="store.updateAsset"
          :onArchive="store.archiveAsset"
        />
      </div>

      <div>
        <ItemForm
          title="Nuevo pasivo"
          :categories="liabilityCategories"
          :ownerships="store.ownerships"
          :onSubmit="store.createLiability"
        />

        <ItemList
          title="Pasivos"
          :items="store.liabilities"
          :categories="liabilityCategories"
          :ownerships="store.ownerships"
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
