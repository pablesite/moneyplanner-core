<script setup lang="ts">
import { onMounted, ref, watch, computed } from "vue";
import { useNetWorthStore } from "@/stores/netWorth";
import ItemForm from "@/components/ItemForm.vue";
import ItemList from "@/components/ItemList.vue";
import BaseModal from "@/components/BaseModal.vue";
import NetWorthDonut from "@/components/NetWorthDonut.vue";
import SettingsPopover from "@/components/SettingsPopover.vue";

const store = useNetWorthStore();

const valueMode = ref<"nominal" | "real">("nominal");

/**
 * Real solo si:
 * - EUR
 * - tenemos inflation_base_period
 * - tenemos net_worth_real (no null)
 */
const canShowReal = () =>
  store.baseCurrency === "EUR" &&
  !!store.summary?.inflation_base_period &&
  store.summary?.net_worth_real !== null;

watch(
  () => store.baseCurrency,
  (c) => {
    if (c !== "EUR" && valueMode.value === "real") valueMode.value = "nominal";
  }
);

watch(
  () => store.summary?.inflation_base_period,
  () => {
    if (!canShowReal() && valueMode.value === "real") valueMode.value = "nominal";
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

/** -------------------------
 * Modales crear activo/pasivo
 * ------------------------- */
const showAssetModal = ref(false);
const showLiabilityModal = ref(false);

async function submitAsset(payload: any) {
  await store.createAsset(payload);
  showAssetModal.value = false;
}

async function submitLiability(payload: any) {
  await store.createLiability(payload);
  showLiabilityModal.value = false;
}

/** -------------------------
 * Formatting (one place)
 * - Force thousands grouping everywhere
 * - Default 2 decimals (summary/snapshots in base currency)
 * ------------------------- */
function normalizeNumberInput(raw: unknown) {
  return String(raw ?? "").trim().replace(/\s/g, "").replace(/,/g, ".");
}

function formatMoney(v?: string | null, decimals = 2) {
  if (v == null) return "-";
  const s = normalizeNumberInput(v);
  const n = Number(s);
  if (Number.isNaN(n)) return v;

  return new Intl.NumberFormat("es-ES", {
    useGrouping: true,
    minimumFractionDigits: decimals,
    maximumFractionDigits: decimals,
  }).format(n);
}

function pickMoney(nominal?: string | null, real?: string | null, decimals = 2) {
  const raw = valueMode.value === "real" ? real : nominal;
  return formatMoney(raw, decimals);
}

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

const realBaseLabel = computed(() =>
  store.summary?.inflation_base_period ? `Base: ${store.summary.inflation_base_period}` : ""
);

const hasUnassigned = () => {
  const u = store.byMemberSummary?.unassigned;
  if (!u) return false;
  return (u.assets !== "0" && u.assets !== "0.00") || (u.liabilities !== "0" && u.liabilities !== "0.00");
};

// Resumen “grande” (donut usa estos)
const summaryAssets = computed(() =>
  valueMode.value === "real" ? store.summary?.total_assets_real : store.summary?.total_assets
);
const summaryLiabilities = computed(() =>
  valueMode.value === "real" ? store.summary?.total_liabilities_real : store.summary?.total_liabilities
);
const summaryNetWorth = computed(() =>
  valueMode.value === "real" ? store.summary?.net_worth_real : store.summary?.net_worth
);

onMounted(async () => {
  await store.fetchSettings();
  await store.refreshAll();
});
</script>

<template>
  <div class="container">
    <div style="display:flex; align-items:center; justify-content: space-between; gap: 12px;">
      <h1 class="h1" style="margin: 0;">Patrimonio</h1>

      <SettingsPopover
        :loading="store.loading"
        :baseCurrency="store.baseCurrency ?? 'EUR'"
        :currencies="currencies"
        :valueMode="valueMode"
        :canShowReal="canShowReal()"
        :modeHelp="modeLabel()"
        :realBaseLabel="realBaseLabel"
        @update:baseCurrency="store.updateBaseCurrency"
        @update:valueMode="(v) => (valueMode = v)"
        @snapshot="store.createTodaySnapshot()"
        @refresh="store.refreshAll()"
      />
    </div>

    <div v-if="store.error" class="alert" style="margin-top: 12px;">
      {{ prettyError() }}
    </div>

    <!-- Resumen principal -->
    <div class="card" style="margin-top: 14px; margin-bottom: 14px;">
  
      <NetWorthDonut
        :totalAssets="summaryAssets"
        :totalLiabilities="summaryLiabilities"
        :netWorth="summaryNetWorth"
        :unit="unitLabel()"
      />
    </div>

    <!-- Por miembro -->
    <div class="section card" v-if="store.byMemberSummary">
      <h2 style="margin-top: 0;">Por miembro</h2>

      <div v-if="hasUnassigned()" class="alert" style="margin-bottom: 12px;">
        Hay activos/pasivos sin titularidad asignada (ownership = null).
        <div class="subtle" style="margin-top:6px;">
          Sin asignar — Activos: {{ formatMoney(store.byMemberSummary.unassigned.assets, 2) }} {{ store.byMemberSummary.base_currency }},
          Pasivos: {{ formatMoney(store.byMemberSummary.unassigned.liabilities, 2) }} {{ store.byMemberSummary.base_currency }}
        </div>
      </div>

      <table style="width:100%; border-collapse: collapse;">
        <thead>
          <tr>
            <th style="text-align:left; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">Miembro</th>
            <th style="text-align:right; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">
              Activos ({{ store.byMemberSummary.base_currency }})
            </th>
            <th style="text-align:right; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">
              Pasivos ({{ store.byMemberSummary.base_currency }})
            </th>
            <th style="text-align:right; padding:8px 6px; border-bottom: 1px solid rgba(0,0,0,.08);">
              Neto ({{ store.byMemberSummary.base_currency }})
            </th>
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
            <td style="padding:8px 6px; text-align:right;">{{ formatMoney(row.total_assets, 2) }}</td>
            <td style="padding:8px 6px; text-align:right;">{{ formatMoney(row.total_liabilities, 2) }}</td>
            <td style="padding:8px 6px; text-align:right;">{{ formatMoney(row.net_worth, 2) }}</td>
          </tr>

          <tr>
            <td style="padding:10px 6px; text-align:left; border-top: 1px solid rgba(0,0,0,.08);">
              <span class="subtle">Total</span>
            </td>
            <td style="padding:10px 6px; text-align:right; border-top: 1px solid rgba(0,0,0,.08);">
              {{ formatMoney(store.byMemberSummary.totals.total_assets, 2) }}
            </td>
            <td style="padding:10px 6px; text-align:right; border-top: 1px solid rgba(0,0,0,.08);">
              {{ formatMoney(store.byMemberSummary.totals.total_liabilities, 2) }}
            </td>
            <td style="padding:10px 6px; text-align:right; border-top: 1px solid rgba(0,0,0,.08);">
              {{ formatMoney(store.byMemberSummary.totals.net_worth, 2) }}
            </td>
          </tr>
        </tbody>
      </table>
    </div>

    <!-- Activos / Pasivos -->
    <div class="grid-2">
      <div>
        <button class="btn btn-primary" @click="showAssetModal = true" :disabled="store.loading">
          Añadir activo
        </button>

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
        <button class="btn btn-primary" @click="showLiabilityModal = true" :disabled="store.loading">
          Añadir pasivo
        </button>

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

    <!-- Snapshots -->
    <div class="section card">
      <h2 style="margin-top: 0;">Snapshots</h2>

      <ul v-if="store.snapshots.length" style="margin: 0; padding-left: 18px; display: grid; gap: 8px;">
        <li v-for="s in store.snapshots" :key="s.id">
          {{ s.snapshot_date }} — neto: {{ formatMoney(s.net_worth, 2) }} {{ s.base_currency }}
          <span class="subtle">
            (activos {{ formatMoney(s.total_assets, 2) }} {{ s.base_currency }},
            pasivos {{ formatMoney(s.total_liabilities, 2) }} {{ s.base_currency }})
          </span>
        </li>
      </ul>

      <div v-else class="subtle">No hay snapshots todavía.</div>
    </div>

    <div v-if="store.loading" class="section subtle">Cargando...</div>

    <!-- Modales -->
    <BaseModal :open="showAssetModal" title="Nuevo activo" @close="showAssetModal = false">
      <ItemForm
        title="Nuevo activo"
        :categories="assetCategories"
        :ownerships="store.ownerships"
        :onSubmit="submitAsset"
      />
    </BaseModal>

    <BaseModal :open="showLiabilityModal" title="Nuevo pasivo" @close="showLiabilityModal = false">
      <ItemForm
        title="Nuevo pasivo"
        :categories="liabilityCategories"
        :ownerships="store.ownerships"
        :onSubmit="submitLiability"
      />
    </BaseModal>
  </div>
</template>
