<script setup lang="ts">
import { onMounted, ref, watch, computed } from "vue";
import { useNetWorthStore } from "@/stores/netWorth";
import ItemForm from "@/components/ItemForm.vue";
import ItemList from "@/components/ItemList.vue";
import BaseModal from "@/components/BaseModal.vue";
import NetWorthDonut from "@/components/NetWorthDonut.vue";
import SettingsPopover from "@/components/SettingsPopover.vue";
import NetWorthByMemberBar from "@/components/NetWorthByMemberBar.vue";
import NetWorthByCategoryBar from "@/components/NetWorthByCategoryBar.vue";


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
  { value: "furnishings", label: "Mobiliario" },
  { value: "other", label: "Otros" },
];

const assetSubcategories = [
  { category: "cash", value: "bank_account", label: "Cuenta bancaria" },
  { category: "cash", value: "wallet", label: "Monedero" },
  { category: "cash", value: "crypto_spot_earn", label: "Spot/Earn Cripto" },
  { category: "cash", value: "other", label: "Otros" },

  { category: "investments", value: "deposits", label: "Depósitos" },
  { category: "investments", value: "funds", label: "Fondos" },
  { category: "investments", value: "etfs", label: "ETFs" },
  { category: "investments", value: "roboadvisor", label: "Roboadvisor" },
  { category: "investments", value: "stocks", label: "Stocks" },
  { category: "investments", value: "pension_plans", label: "Planes de pensiones" },
  { category: "investments", value: "cryptocurrencies", label: "Criptomonedas" },
  { category: "investments", value: "real_estate_crowd", label: "Crowdfunding Inmobiliario" },
  { category: "investments", value: "crowdlending", label: "Crowdlending" },
  { category: "investments", value: "other", label: "Otros" },

  { category: "real_estate", value: "primary_home", label: "Vivienda habitual" },
  { category: "real_estate", value: "second_home", label: "Segunda vivienda" },
  { category: "real_estate", value: "rental", label: "Rentas" },
  { category: "real_estate", value: "other", label: "Otros" },

  { category: "furnishings", value: "vehicles", label: "Vehículos" },
  { category: "furnishings", value: "technology", label: "Tecnología" },
  { category: "furnishings", value: "home_furnishings", label: "Muebles vivienda" },
  { category: "furnishings", value: "sports_equipment", label: "Equipamiento deportivo" },
  { category: "furnishings", value: "jewelry", label: "Joyería" },
  { category: "furnishings", value: "other", label: "Otros" },

  { category: "other", value: "other", label: "Otros" },
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
const showBreakdown = ref(false);
const showEditModal = ref(false);
const editItem = ref<any>(null);
const editKind = ref<"asset" | "liability" | null>(null);

async function submitAsset(payload: any) {
  await store.createAsset(payload);
  showAssetModal.value = false;
}

async function submitLiability(payload: any) {
  await store.createLiability(payload);
  showLiabilityModal.value = false;
}

function openEdit(item: any, kind: "asset" | "liability") {
  editItem.value = item;
  editKind.value = kind;
  showEditModal.value = true;
}

function closeEdit() {
  showEditModal.value = false;
  editItem.value = null;
  editKind.value = null;
}

function confirmDeleteSnapshot(id: number) {
  if (store.loading) return;
  if (confirm("Eliminar este snapshot?")) {
    store.deleteSnapshot(id);
  }
}

const editTitle = computed(() =>
  editKind.value === "liability" ? "Editar pasivo" : "Editar activo"
);

const editCategories = computed(() =>
  editKind.value === "liability" ? liabilityCategories : assetCategories
);

const decimalsByCurrency: Record<string, number> = {
  EUR: 2,
  USD: 2,
  BTC: 8,
  ETH: 8,
};

function formatEditAmount(raw: unknown, currency: string) {
  const max = decimalsByCurrency[currency] ?? 2;
  let s = String(raw ?? "").trim().replace(/\s/g, "").replace(/,/g, ".");
  if (!s) return "";

  const isNegative = s.startsWith("-");
  if (isNegative) s = s.slice(1);

  if ((s.match(/\./g) || []).length > 1) {
    return isNegative ? `-${s}` : s;
  }

  const [i, d = ""] = s.split(".");
  let out = d ? `${i}.${d.slice(0, max)}` : i;
  out = out.replace(/\.?0+$/, "");
  if (out.startsWith(".")) out = `0${out}`;
  return isNegative ? `-${out}` : out;
}

const editInitial = computed(() => {
  const item = editItem.value;
  if (!item) return null;
  return {
    name: item.name ?? "",
    category: item.category ?? "",
    subcategory: item.subcategory ?? "",
    amount: formatEditAmount(item.amount, item.currency ?? "EUR"),
    notes: item.notes ?? "",
    currency: item.currency ?? "",
    tracking_mode: item.tracking_mode ?? "manual",
    is_active: item.is_active ?? true,
    ownership_id: item.ownership_ref ?? null,
    financed_asset_id: item.financed_asset_ref ?? null,
  };
});

async function submitEdit(payload: any) {
  if (!editItem.value || !editKind.value) return;
  const id = editItem.value.id;

  if (editKind.value === "asset") {
    delete payload.financed_asset_id;
    await store.updateAsset(id, payload);
  } else {
    await store.updateLiability(id, payload);
  }

  closeEdit();
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

const byMemberChart = computed(() => store.byMemberChart);

const byCategoryChart = computed(() => store.byCategoryChart);

const categoryLabelMap = computed(() => {
  const m = new Map<string, string>();
  assetCategories.forEach(c => m.set(c.value, c.label));
  liabilityCategories.forEach(c => m.set(c.value, c.label));
  return m;
});

const byCategoryFiltered = computed(() => {
  const keys = byCategoryChart.value.keys;
  const assets = byCategoryChart.value.assets;
  const liabs = byCategoryChart.value.liabilities;

  const out = [];
  for (let i = 0; i < keys.length; i++) {
    if ((assets[i] ?? 0) !== 0 || (liabs[i] ?? 0) !== 0) {
      out.push({ key: keys[i], a: assets[i] ?? 0, l: liabs[i] ?? 0 });
    }
  }
  return out;
});

const byCategoryLabels = computed(() =>
  byCategoryFiltered.value.map(r => categoryLabelMap.value.get(r.key) ?? r.key)
);
const byCategoryAssets = computed(() => byCategoryFiltered.value.map(r => r.a));
const byCategoryLiabilities = computed(() => byCategoryFiltered.value.map(r => r.l));
const byCategoryUnit = computed(() => byCategoryChart.value.unit);

const summaryAssetBackedLiabilities = computed(() =>
  valueMode.value === "real"
    ? (store.summary as any)?.liabilities_asset_backed_real
    : (store.summary as any)?.liabilities_asset_backed
);

const summaryUnbackedLiabilities = computed(() =>
  valueMode.value === "real"
    ? (store.summary as any)?.liabilities_unbacked_real
    : (store.summary as any)?.liabilities_unbacked
);



onMounted(async () => {
  await store.fetchSettings();
  await store.refreshAll();
});

</script>

<template>
  <div class="container networth-container">
    <div class="networth-header">
      <div class="networth-title-row">
      <h1 class="h1 networth-title">Patrimonio</h1>
      <button
        class="icon-btn networth-refresh"
        type="button"
        @click="store.refreshAll()"
        :disabled="store.loading"
        aria-label="Refrescar"
      >
        <span class="icon" aria-hidden="true">&#8635;</span>
      </button>
      <button
        class="icon-btn networth-snapshot"
        type="button"
        @click="store.createTodaySnapshot()"
        :disabled="store.loading"
        aria-label="Guardar snapshot"
        title="Guardar snapshot"
      >
        <span class="icon" aria-hidden="true">&#128190;</span>
      </button>
    </div>

      <div class="networth-actions">
        <button class="btn" type="button" @click="$router.push('/people')">
          Personas
        </button>

        <SettingsPopover
          :loading="store.loading"
          :baseCurrency="store.baseCurrency ?? 'EUR'"
          :currencies="currencies"
          :valueMode="valueMode"
          :canShowReal="canShowReal()"
          :modeHelp="modeLabel()"
          :realBaseLabel="realBaseLabel"
          :showRefresh="false"
          :showSnapshot="false"
          :iconOnly="true"
          @update:baseCurrency="store.updateBaseCurrency"
          @update:valueMode="(v) => (valueMode = v)"
          @snapshot="store.createTodaySnapshot()"
          @refresh="store.refreshAll()"
        />
      </div>
    </div>

    <div v-if="store.error" class="alert networth-alert">
      {{ prettyError() }}
    </div>

    <!-- Resumen principal -->
    <div class="card networth-summary-card">
  
    <NetWorthDonut
      :totalAssets="summaryAssets"
      :totalLiabilities="summaryLiabilities"
      :assetBackedLiabilities="summaryAssetBackedLiabilities"
      :unbackedLiabilities="summaryUnbackedLiabilities"
      :netWorth="summaryNetWorth"
      :unit="unitLabel()"
    />
    

    <div class="networth-breakdown-inline">
      <div class="networth-breakdown" v-if="store.summary || store.byMemberSummary">
      <div class="panel-header">
        <h2 class="panel-title">Desglose</h2>
        <button class="btn btn-sm panel-toggle" type="button" @click="showBreakdown = !showBreakdown">
          <span aria-hidden="true">{{ showBreakdown ? "&#9660;" : "&#9654;" }}</span>
          <span>{{ showBreakdown ? "Ocultar" : "Mostrar" }}</span>
        </button>
      </div>

      <div v-if="showBreakdown" class="networth-panels">
        <div v-if="store.summary">
          <h3 class="panel-subtitle">Por categoria</h3>
          <NetWorthByCategoryBar
            :labels="byCategoryLabels"
            :assets="byCategoryAssets"
            :liabilities="byCategoryLiabilities"
            :unit="byCategoryUnit"
          />

          
        </div>

        <div v-if="store.byMemberSummary">
          <h3 class="panel-subtitle">Por miembro</h3>
          <div v-if="byMemberChart && byMemberChart.labels.length" class="panel-chart">
            <NetWorthByMemberBar
              :labels="byMemberChart.labels"
              :assets="byMemberChart.assets"
              :liabilities="byMemberChart.liabilities"
              :unit="byMemberChart.unit"
            />
          </div>

          <div v-if="hasUnassigned()" class="alert panel-alert">
            Hay activos/pasivos sin titularidad asignada (ownership = null).
            <div class="subtle panel-help">
              Sin asignar &mdash; Activos: {{ formatMoney(store.byMemberSummary.unassigned.assets, 2) }} {{ store.byMemberSummary.base_currency }},
              Pasivos: {{ formatMoney(store.byMemberSummary.unassigned.liabilities, 2) }} {{ store.byMemberSummary.base_currency }}
            </div>
          </div>

          <table class="panel-table">
            <thead>
              <tr>
                <th class="panel-th">Miembro</th>
                <th class="panel-th panel-th-right">
                  Activos ({{ store.byMemberSummary.base_currency }})
                </th>
                <th class="panel-th panel-th-right">
                  Pasivos ({{ store.byMemberSummary.base_currency }})
                </th>
                <th class="panel-th panel-th-right">
                  Neto ({{ store.byMemberSummary.base_currency }})
                </th>
              </tr>
            </thead>

            <tbody>
              <tr v-for="row in store.byMemberSummary.by_member" :key="row.member.id">
                <td class="panel-td">
                  {{ row.member.name }}
                  <span class="subtle panel-role">
                    ({{ row.member.role === 'adult' ? 'Adulto' : 'Nino' }})
                  </span>
                </td>
                <td class="panel-td panel-td-right">{{ formatMoney(row.total_assets, 2) }}</td>
                <td class="panel-td panel-td-right">{{ formatMoney(row.total_liabilities, 2) }}</td>
                <td class="panel-td panel-td-right">{{ formatMoney(row.net_worth, 2) }}</td>
              </tr>

              <tr>
                <td class="panel-td panel-total-left">
                  <span class="subtle">Total</span>
                </td>
                <td class="panel-td panel-td-right panel-total">
                  {{ formatMoney(store.byMemberSummary.totals.total_assets, 2) }}
                </td>
                <td class="panel-td panel-td-right panel-total">
                  {{ formatMoney(store.byMemberSummary.totals.total_liabilities, 2) }}
                </td>
                <td class="panel-td panel-td-right panel-total">
                  {{ formatMoney(store.byMemberSummary.totals.net_worth, 2) }}
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </div>
    </div>
</div>

        <!-- Activos / Pasivos -->


    <div class="grid-2 section">
      <ItemList
        title="Activos"
        :items="store.assets"
        :categories="assetCategories"
        :subcategories="assetSubcategories"
        :baseCurrency="store.baseCurrency ?? store.summary?.base_currency ?? 'EUR'"
        :categoryTotalsBase="store.summary?.assets_by_category ?? {}"
        :subcategoryTotalsBase="store.summary?.assets_by_subcategory ?? {}"
        :totalBase="store.summary?.total_assets ?? '0'"
        :ownerships="store.ownerships"
        :onUpdate="store.updateAsset"
        :onArchive="store.archiveAsset"
        :onAdd="() => (showAssetModal = true)"
        :onEdit="(it) => openEdit(it, 'asset')"
      />

      <ItemList
        title="Pasivos"
        :items="store.liabilities"
        :categories="liabilityCategories"
        :baseCurrency="store.baseCurrency ?? store.summary?.base_currency ?? 'EUR'"
        :categoryTotalsBase="store.summary?.liabilities_by_category ?? {}"
        :totalBase="store.summary?.total_liabilities ?? '0'"
        :ownerships="store.ownerships"
        :assets="store.assets"  
        :onUpdate="store.updateLiability"
        :onArchive="store.archiveLiability"
        :onAdd="() => (showLiabilityModal = true)"
        :onEdit="(it) => openEdit(it, 'liability')"
      />
    </div>


    <!-- Snapshots -->
    <div class="section card">
      <h2 style="margin-top: 0;">Snapshots</h2>

      <ul v-if="store.snapshots.length" class="snapshot-list">
        <li v-for="s in store.snapshots" :key="s.id" class="snapshot-row">
          <div class="snapshot-main">
            {{ s.snapshot_date }} — neto: {{ formatMoney(s.net_worth, 2) }} {{ s.base_currency }}
            <span class="subtle">
              (activos {{ formatMoney(s.total_assets, 2) }} {{ s.base_currency }},
              pasivos {{ formatMoney(s.total_liabilities, 2) }} {{ s.base_currency }})
            </span>
          </div>
          <button
            class="icon-btn snapshot-delete"
            type="button"
            @click="confirmDeleteSnapshot(s.id)"
            :disabled="store.loading"
            aria-label="Eliminar snapshot"
            title="Eliminar snapshot"
          >
            <span class="icon" aria-hidden="true">&#128465;</span>
          </button>
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
        :subcategories="assetSubcategories"
        :ownerships="store.ownerships"
        :allowNegative="true"
        :onSubmit="submitAsset"
        :onCancel="() => (showAssetModal = false)"
      />
    </BaseModal>

    <BaseModal :open="showLiabilityModal" title="Nuevo pasivo" @close="showLiabilityModal = false">
      <ItemForm
        title="Nuevo pasivo"
        :categories="liabilityCategories"
        :ownerships="store.ownerships"
        :assets="store.assets"
        :showFinancedAsset="true"
        :onSubmit="submitLiability"
        :onCancel="() => (showLiabilityModal = false)"
      />
    </BaseModal>

    <BaseModal :open="showEditModal" :title="editTitle" @close="closeEdit">
      <ItemForm
        v-if="editInitial"
        :title="editTitle"
        :categories="editCategories"
        :subcategories="editKind === 'asset' ? assetSubcategories : undefined"
        :ownerships="store.ownerships"
        :assets="editKind === 'liability' ? store.assets : []"
        :showFinancedAsset="editKind === 'liability'"
        :allowNegative="editKind === 'asset'"
        mode="edit"
        :initial="editInitial"
        :onSubmit="submitEdit"
        :onCancel="closeEdit"
      />
    </BaseModal>
  </div>
</template>

<style scoped>
.networth-container{
  position: relative;
}

.networth-top-right{
  position: absolute;
  right: 0;
  top: -52px;
}

.networth-header{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.networth-title{
  margin: 0;
}

.networth-title-row{
  display: flex;
  align-items: center;
  gap: 8px;
}

.networth-refresh:disabled{
  opacity: 0.5;
  cursor: not-allowed;
}

.networth-snapshot:disabled{
  opacity: 0.5;
  cursor: not-allowed;
}

.networth-actions{
  display: flex;
  align-items: center;
  gap: 10px;
}

.networth-alert{
  margin-top: 12px;
}

.networth-summary-card{
  margin-top: 14px;
  margin-bottom: 14px;
}

.networth-breakdown-inline{
  margin-top: 14px;
  border-top: 1px solid rgba(255,255,255,0.08);
  padding-top: 14px;
}

.networth-panels{
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 14px;
}

.networth-panels > .card{
  min-width: 0;
}

.panel-header{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.panel-title{
  margin: 0;
  font-size: 16px;
}

.panel-toggle{
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.panel-help{
  margin-top: 8px;
}

.panel-chart{
  margin: 12px 0 16px;
}

.panel-alert{
  margin-bottom: 12px;
}

.panel-table{
  width: 100%;
  border-collapse: collapse;
}

.panel-th{
  text-align: left;
  padding: 8px 6px;
  border-bottom: 1px solid rgba(0,0,0,.08);
}

.panel-th-right{
  text-align: right;
}

.panel-td{
  padding: 8px 6px;
}

.panel-td-right{
  text-align: right;
}

.panel-role{
  margin-left: 6px;
  font-size: 12px;
}

.panel-total-left{
  padding-top: 10px;
  border-top: 1px solid rgba(0,0,0,.08);
}

.panel-total{
  padding-top: 10px;
  border-top: 1px solid rgba(0,0,0,.08);
}

.panel-subtitle{
  margin: 0 0 8px 0;
  font-size: 15px;
}

.networth-breakdown{
}

.snapshot-list{
  margin: 0;
  padding-left: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}

.snapshot-row{
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.snapshot-main{
  min-width: 0;
}

.snapshot-delete:disabled{
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 700px){
  .networth-panels{
    grid-template-columns: 1fr;
  }
}
</style>
