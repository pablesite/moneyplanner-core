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
  <div class="container relative">
    <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
      <div class="flex items-center gap-2">
        <h1 class="h1 m-0">Patrimonio</h1>
        <button
          class="icon-btn disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          :disabled="store.loading"
          aria-label="Refrescar"
          @click="store.refreshAll()"
        >
          <span class="icon" aria-hidden="true">&#8635;</span>
        </button>
        <button
          class="icon-btn disabled:cursor-not-allowed disabled:opacity-50"
          type="button"
          :disabled="store.loading"
          aria-label="Guardar snapshot"
          title="Guardar snapshot"
          @click="store.createTodaySnapshot()"
        >
          <span class="icon" aria-hidden="true">&#128190;</span>
        </button>
      </div>

      <div class="flex flex-wrap items-center gap-2.5">
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

    <div v-if="store.error" class="alert mt-3">
      {{ prettyError() }}
    </div>

    <div class="card my-4">
      <NetWorthDonut
        :total-assets="summaryAssets"
        :total-liabilities="summaryLiabilities"
        :asset-backed-liabilities="summaryAssetBackedLiabilities"
        :unbacked-liabilities="summaryUnbackedLiabilities"
        :net-worth="summaryNetWorth"
        :unit="unitLabel()"
      />

      <div class="mt-4 border-t border-white/10 pt-4">
        <div v-if="store.summary">
          <div class="mb-2.5 flex items-center justify-between gap-2.5">
            <h2 class="m-0 text-base">Desglose</h2>
            <button
              class="btn btn-sm inline-flex items-center gap-2"
              type="button"
              @click="showBreakdown = !showBreakdown"
            >
              <span aria-hidden="true">{{ showBreakdown ? '&#9660;' : '&#9654;' }}</span>
              <span>{{ showBreakdown ? 'Ocultar' : 'Mostrar' }}</span>
            </button>
          </div>

          <div v-if="showBreakdown" class="grid gap-3.5 md:grid-cols-2">
            <div v-if="store.summary">
              <h3 class="mb-2 text-[15px]">Por categoria</h3>
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

    <div class="section card">
      <h2 class="mt-0 text-base">Snapshots</h2>

      <ul v-if="store.snapshots.length" class="m-0 grid list-none gap-2 pl-0">
        <li v-for="s in store.snapshots" :key="s.id" class="flex items-center justify-between gap-3">
          <div class="min-w-0">
            {{ s.snapshot_date }} - neto: {{ formatMoney(s.net_worth, 2) }} {{ s.base_currency }}
            <span class="subtle">
              (activos {{ formatMoney(s.total_assets, 2) }} {{ s.base_currency }}, pasivos
              {{ formatMoney(s.total_liabilities, 2) }} {{ s.base_currency }})
            </span>
          </div>
          <button
            class="icon-btn disabled:cursor-not-allowed disabled:opacity-50"
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

      <div v-else class="subtle">No hay snapshots todavia.</div>
    </div>

    <div v-if="store.loading" class="section subtle">Cargando...</div>

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
