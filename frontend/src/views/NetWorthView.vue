<script setup lang="ts">
import {
  ItemForm,
  ItemList,
  NetWorthByCategoryBar,
  NetWorthDonut,
  SettingsPopover,
  useNetWorthViewExtensions,
  useNetWorthViewState,
} from '@/domains/net-worth';
import { BaseModal } from '@/domains/ui';

const {
  store,
  valueMode,
  currencies,
  assetCategories,
  assetSubcategories,
  liabilityCategories,
  prettyError,
  showAssetModal,
  showLiabilityModal,
  showBreakdown,
  showEditModal,
  editKind,
  canShowReal,
  submitAsset,
  submitLiability,
  openEdit,
  closeEdit,
  confirmDeleteSnapshot,
  editTitle,
  editCategories,
  editInitial,
  submitEdit,
  formatMoney,
  unitLabel,
  modeLabel,
  realBaseLabel,
  summaryAssets,
  summaryLiabilities,
  summaryNetWorth,
  byCategoryLabels,
  byCategoryAssets,
  byCategoryLiabilities,
  byCategoryUnit,
  summaryAssetBackedLiabilities,
  summaryUnbackedLiabilities,
} = useNetWorthViewState();

const { HeaderActions, itemFormProps, itemListProps } = useNetWorthViewExtensions(store);
</script>

<template>
  <div class="container networth-container">
    <div class="networth-header">
      <div class="networth-title-row">
        <h1 class="h1 networth-title">Patrimonio</h1>
        <button
          class="icon-btn networth-refresh"
          type="button"
          :disabled="store.loading"
          aria-label="Refrescar"
          @click="store.refreshAll()"
        >
          <span class="icon" aria-hidden="true">&#8635;</span>
        </button>
        <button
          class="icon-btn networth-snapshot"
          type="button"
          :disabled="store.loading"
          aria-label="Guardar snapshot"
          title="Guardar snapshot"
          @click="store.createTodaySnapshot()"
        >
          <span class="icon" aria-hidden="true">&#128190;</span>
        </button>
      </div>

      <div class="networth-actions">
        <component :is="HeaderActions" v-if="HeaderActions" />
        <button class="btn" type="button" @click="$router.push('/data')">Datos auxiliares</button>

        <SettingsPopover
          :loading="store.loading"
          :base-currency="store.baseCurrency ?? 'EUR'"
          :currencies="currencies"
          :value-mode="valueMode"
          :can-show-real="canShowReal()"
          :mode-help="modeLabel()"
          :real-base-label="realBaseLabel"
          :show-refresh="false"
          :show-snapshot="false"
          :icon-only="true"
          @update:base-currency="store.updateBaseCurrency"
          @update:value-mode="(v) => (valueMode = v)"
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
        :total-assets="summaryAssets"
        :total-liabilities="summaryLiabilities"
        :asset-backed-liabilities="summaryAssetBackedLiabilities"
        :unbacked-liabilities="summaryUnbackedLiabilities"
        :net-worth="summaryNetWorth"
        :unit="unitLabel()"
      />

      <div class="networth-breakdown-inline">
        <div v-if="store.summary" class="networth-breakdown">
          <div class="panel-header">
            <h2 class="panel-title">Desglose</h2>
            <button
              class="btn btn-sm panel-toggle"
              type="button"
              @click="showBreakdown = !showBreakdown"
            >
              <span aria-hidden="true">{{ showBreakdown ? '&#9660;' : '&#9654;' }}</span>
              <span>{{ showBreakdown ? 'Ocultar' : 'Mostrar' }}</span>
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
        :base-currency="store.baseCurrency ?? store.summary?.base_currency ?? 'EUR'"
        :category-totals-base="store.summary?.assets_by_category ?? {}"
        :subcategory-totals-base="store.summary?.assets_by_subcategory ?? {}"
        :total-base="store.summary?.total_assets ?? '0'"
        v-bind="itemListProps"
        :on-update="store.updateAsset"
        :on-archive="store.archiveAsset"
        :on-add="() => (showAssetModal = true)"
        :on-edit="(it) => openEdit(it, 'asset')"
      />

      <ItemList
        title="Pasivos"
        :items="store.liabilities"
        :categories="liabilityCategories"
        :base-currency="store.baseCurrency ?? store.summary?.base_currency ?? 'EUR'"
        :category-totals-base="store.summary?.liabilities_by_category ?? {}"
        :total-base="store.summary?.total_liabilities ?? '0'"
        v-bind="itemListProps"
        :assets="store.assets"
        :on-update="store.updateLiability"
        :on-archive="store.archiveLiability"
        :on-add="() => (showLiabilityModal = true)"
        :on-edit="(it) => openEdit(it, 'liability')"
      />
    </div>

    <!-- Snapshots -->
    <div class="section card">
      <h2 style="margin-top: 0">Snapshots</h2>

      <ul v-if="store.snapshots.length" class="snapshot-list">
        <li v-for="s in store.snapshots" :key="s.id" class="snapshot-row">
          <div class="snapshot-main">
            {{ s.snapshot_date }} — neto: {{ formatMoney(s.net_worth, 2) }} {{ s.base_currency }}
            <span class="subtle">
              (activos {{ formatMoney(s.total_assets, 2) }} {{ s.base_currency }}, pasivos
              {{ formatMoney(s.total_liabilities, 2) }} {{ s.base_currency }})
            </span>
          </div>
          <button
            class="icon-btn snapshot-delete"
            type="button"
            :disabled="store.loading"
            aria-label="Eliminar snapshot"
            title="Eliminar snapshot"
            @click="confirmDeleteSnapshot(s.id)"
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
        v-bind="itemFormProps"
        :allow-negative="true"
        :on-submit="submitAsset"
        :on-cancel="() => (showAssetModal = false)"
      />
    </BaseModal>

    <BaseModal :open="showLiabilityModal" title="Nuevo pasivo" @close="showLiabilityModal = false">
      <ItemForm
        title="Nuevo pasivo"
        :categories="liabilityCategories"
        v-bind="itemFormProps"
        :assets="store.assets"
        :show-financed-asset="true"
        :on-submit="submitLiability"
        :on-cancel="() => (showLiabilityModal = false)"
      />
    </BaseModal>

    <BaseModal :open="showEditModal" :title="editTitle" @close="closeEdit">
      <ItemForm
        v-if="editInitial"
        :title="editTitle"
        :categories="editCategories"
        :subcategories="editKind === 'asset' ? assetSubcategories : undefined"
        v-bind="itemFormProps"
        :assets="editKind === 'liability' ? store.assets : []"
        :show-financed-asset="editKind === 'liability'"
        :allow-negative="editKind === 'asset'"
        mode="edit"
        :initial="editInitial"
        :on-submit="submitEdit"
        :on-cancel="closeEdit"
      />
    </BaseModal>
  </div>
</template>

<style scoped>
.networth-container {
  position: relative;
}

.networth-top-right {
  position: absolute;
  right: 0;
  top: -52px;
}

.networth-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.networth-title {
  margin: 0;
}

.networth-title-row {
  display: flex;
  align-items: center;
  gap: 8px;
}

.networth-refresh:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.networth-snapshot:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.networth-actions {
  display: flex;
  align-items: center;
  gap: 10px;
}

.networth-alert {
  margin-top: 12px;
}

.networth-summary-card {
  margin-top: 14px;
  margin-bottom: 14px;
}

.networth-breakdown-inline {
  margin-top: 14px;
  border-top: 1px solid rgba(255, 255, 255, 0.08);
  padding-top: 14px;
}

.networth-panels {
  display: grid;
  grid-template-columns: minmax(0, 1fr) minmax(0, 1fr);
  gap: 14px;
}

.networth-panels > .card {
  min-width: 0;
}

.panel-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  margin-bottom: 10px;
}

.panel-title {
  margin: 0;
  font-size: 16px;
}

.panel-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.panel-help {
  margin-top: 8px;
}

.panel-chart {
  margin: 12px 0 16px;
}

.panel-alert {
  margin-bottom: 12px;
}

.panel-table {
  width: 100%;
  border-collapse: collapse;
}

.panel-th {
  text-align: left;
  padding: 8px 6px;
  border-bottom: 1px solid rgba(0, 0, 0, 0.08);
}

.panel-th-right {
  text-align: right;
}

.panel-td {
  padding: 8px 6px;
}

.panel-td-right {
  text-align: right;
}

.panel-role {
  margin-left: 6px;
  font-size: 12px;
}

.panel-total-left {
  padding-top: 10px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

.panel-total {
  padding-top: 10px;
  border-top: 1px solid rgba(0, 0, 0, 0.08);
}

.panel-subtitle {
  margin: 0 0 8px 0;
  font-size: 15px;
}

.networth-breakdown {
}

.snapshot-list {
  margin: 0;
  padding-left: 0;
  list-style: none;
  display: grid;
  gap: 8px;
}

.snapshot-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.snapshot-main {
  min-width: 0;
}

.snapshot-delete:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

@media (max-width: 700px) {
  .networth-panels {
    grid-template-columns: 1fr;
  }
}
</style>


