<script setup lang="ts">
import { computed, unref } from 'vue';
import { BaseModal } from '@/domains/ui';
import { ItemForm, ItemList } from '@/domains/net-worth';

const props = defineProps<{
  page: any;
}>();

const page = props.page;

const assetOwnershipFilterModel = computed({
  get: () => page.assetOwnershipFilter.value,
  set: (value: number | 'all' | 'unassigned') => {
    page.assetOwnershipFilter.value = value;
  },
});

const liabilityOwnershipFilterModel = computed({
  get: () => page.liabilityOwnershipFilter.value,
  set: (value: number | 'all' | 'unassigned') => {
    page.liabilityOwnershipFilter.value = value;
  },
});

const showAssetModalModel = computed({
  get: () => page.showAssetModal.value,
  set: (value: boolean) => {
    page.showAssetModal.value = value;
  },
});

const showLiabilityModalModel = computed({
  get: () => page.showLiabilityModal.value,
  set: (value: boolean) => {
    page.showLiabilityModal.value = value;
  },
});

const showGeneratedLiabilityExpenseModalModel = computed({
  get: () => page.showGeneratedLiabilityExpenseModal.value,
  set: (value: boolean) => {
    page.showGeneratedLiabilityExpenseModal.value = value;
  },
});

const showEditModalModel = computed({
  get: () => page.showEditModal.value,
  set: (value: boolean) => {
    page.showEditModal.value = value;
  },
});

const hasGeneratedLiabilityExpenseEntry = computed(() => {
  const review = unref(page.generatedLiabilityExpenseReview);
  if (!review) return false;
  return (unref(page.annualExpenseEntries) ?? []).some(
    (entry: { sourceLiabilityId: number | null; isSystemGenerated: boolean }) =>
      entry.sourceLiabilityId === review.liabilityId && entry.isSystemGenerated,
  );
});

const netAssetsBase = computed(() => unref(page.netAssetsBase) ?? 0);
const netAssetsCurrency = computed(() => unref(page.netAssetsCurrency) ?? 'EUR');
const visibleAssets = computed(() => unref(page.visibleAssets) ?? []);
const visibleLiabilities = computed(() => unref(page.visibleLiabilities) ?? []);
const activeAssets = computed(() => unref(page.activeAssets) ?? []);
const generatedLiabilityExpenseReview = computed(
  () => unref(page.generatedLiabilityExpenseReview) ?? null,
);
const generatedLiabilityExpenseEntries = computed(
  () => generatedLiabilityExpenseReview.value?.entries ?? [],
);
</script>

<template>
  <div>
    <div v-if="page.store.error" class="alert mt-3">
      {{ page.prettyError() }}
    </div>

    <section class="section ui-balance-air">
      <div class="nw-list-header ui-balance-air-header">
        <div class="nw-list-header-left ui-balance-air-left">
          <h2 class="ui-balance-air-title">Balance patrimonial</h2>
          <span class="ui-balance-air-subtitle">Activos y pasivos</span>
        </div>
        <div class="nw-list-header-right ui-balance-air-right">
          <div class="nw-list-total-inline ui-balance-air-total">
            {{ page.formatMoneyAmount(netAssetsBase, netAssetsCurrency) }}
          </div>
          <div class="nw-list-total-details">Neto (activos - pasivos)</div>
        </div>
      </div>
    </section>

    <div class="grid-2">
      <ItemList
        v-model:ownership-filter-value="assetOwnershipFilterModel"
        title="Activos"
        :items="visibleAssets"
        :show-archived="page.visibilityFilterMode !== 'active'"
        :show-ownership-filter="false"
        :categories="page.assetCategories"
        :subcategories="page.assetSubcategories"
        :base-currency="page.store.baseCurrency ?? page.store.summary?.base_currency ?? 'EUR'"
        :category-totals-base="page.store.summary?.assets_by_category ?? {}"
        :subcategory-totals-base="page.store.summary?.assets_by_subcategory ?? {}"
        :total-base="page.store.summary?.total_assets ?? '0'"
        v-bind="page.itemListProps"
        :on-update="page.updateAssetAndReloadExpenses"
        :on-archive="page.store.archiveAsset"
        :on-delete="page.deleteAssetAndReloadExpenses"
        :on-add="page.openAssetModal"
        :on-edit="(it) => page.openEdit(it, 'asset')"
      />

      <ItemList
        v-model:ownership-filter-value="liabilityOwnershipFilterModel"
        title="Pasivos"
        :items="visibleLiabilities"
        :show-archived="page.visibilityFilterMode !== 'active'"
        :show-ownership-filter="false"
        :categories="page.liabilityCategories"
        :base-currency="page.store.baseCurrency ?? page.store.summary?.base_currency ?? 'EUR'"
        :category-totals-base="page.store.summary?.liabilities_by_category ?? {}"
        :total-base="page.store.summary?.total_liabilities ?? '0'"
        v-bind="page.itemListProps"
        :assets="activeAssets"
        :on-update="page.updateLiabilityAndShowExpenseReview"
        :on-archive="page.store.archiveLiability"
        :on-delete="page.deleteLiabilityAndReloadExpenses"
        :on-add="page.openLiabilityModal"
        :on-edit="(it) => page.openEdit(it, 'liability')"
      />
    </div>

    <div v-if="page.store.loading" class="ui-status-line">Cargando...</div>

    <BaseModal :open="showAssetModalModel" title="Nuevo activo" @close="page.closeAssetModal">
      <ItemForm
        title="Nuevo activo"
        :categories="page.assetCategories"
        :subcategories="page.assetSubcategories"
        v-bind="page.itemFormProps"
        :allow-negative="true"
        :on-submit="page.submitAsset"
        :on-cancel="page.closeAssetModal"
      />
    </BaseModal>

    <BaseModal
      :open="showLiabilityModalModel"
      title="Nuevo pasivo"
      @close="page.closeLiabilityModal"
    >
      <ItemForm
        title="Nuevo pasivo"
        :categories="page.liabilityCategories"
        v-bind="page.itemFormProps"
        :assets="page.activeAssets"
        :show-financed-asset="true"
        :on-submit="page.submitLiabilityWithExpenseReview"
        :on-cancel="page.closeLiabilityModal"
      />
    </BaseModal>

    <BaseModal
      :open="showGeneratedLiabilityExpenseModalModel"
      :title="page.generatedLiabilityExpenseReviewTitle"
      @close="page.closeGeneratedLiabilityExpenseModal"
    >
      <div v-if="generatedLiabilityExpenseReview" class="grid gap-3">
        <div
          v-if="page.generatedLiabilityExpenseReviewChangeMessage"
          class="rounded-xl border border-amber-300/20 bg-amber-400/10 px-3 py-2 text-sm text-white/90"
        >
          {{ page.generatedLiabilityExpenseReviewChangeMessage }}
        </div>
        <div
          class="rounded-xl border border-teal-300/20 bg-teal-400/10 px-3 py-2 text-sm text-white/90"
        >
          Se han generado gastos recurrentes en
          {{ generatedLiabilityExpenseEntries.length }}
          anualidades para este pasivo. Revisalos y confirma que la clasificacion
          (categoria/subcategoria/naturaleza) es correcta.
        </div>

        <div class="grid gap-2">
          <div
            v-for="entry in generatedLiabilityExpenseEntries"
            :key="entry.id"
            class="rounded-xl border border-white/10 bg-white/[0.03] px-3 py-2.5"
          >
            <div class="flex flex-wrap items-center justify-between gap-2">
              <div class="text-sm font-medium">Ejercicio {{ entry.fiscalYear }}</div>
              <div class="text-sm text-white/90">
                {{ page.formatMoneyAmount(entry.amountAnnual, entry.currency) }}
              </div>
            </div>
            <div class="mt-1 text-xs text-white/70">
              {{ page.expenseCategoryLabel(entry.category) }} /
              {{ page.expenseSubcategoryLabel(entry.subcategory) }}
              <template
                v-if="
                  !page.shouldHideExpenseCashflowRoleLabel({
                    timeProfile: entry.timeProfile,
                    cashflowRole: entry.cashflowRole,
                  })
                "
              >
                . {{ page.expenseCashflowRoleLabel(entry.cashflowRole) }}
              </template>
              . {{ page.timeProfileLabel(entry.timeProfile) }}
            </div>
            <div v-if="entry.notes" class="mt-1 text-xs text-white/55">
              {{ entry.notes }}
            </div>
          </div>
        </div>

        <div class="actions justify-end">
          <button
            class="btn"
            type="button"
            :disabled="!generatedLiabilityExpenseEntries.length"
            @click="page.openGeneratedExpenseBulkEdit"
          >
            Editar todos los ejercicios
          </button>
          <button
            class="btn btn-ghost"
            type="button"
            @click="page.closeGeneratedLiabilityExpenseModal"
          >
            Cerrar
          </button>
          <button
            class="btn btn-primary"
            type="button"
            :disabled="!hasGeneratedLiabilityExpenseEntry"
            @click="page.openGeneratedExpenseReviewEntryFromVisibleYear"
          >
            Revisar en gastos (año visible)
          </button>
        </div>
      </div>
    </BaseModal>

    <BaseModal :open="showEditModalModel" :title="page.editTitle" @close="page.closeEdit">
      <ItemForm
        v-if="page.editInitial"
        :title="page.editTitle"
        :categories="page.editCategories"
        :subcategories="page.editKind === 'asset' ? page.assetSubcategories : undefined"
        v-bind="page.itemFormProps"
        :assets="page.editKind === 'liability' ? activeAssets : []"
        :show-financed-asset="page.editKind === 'liability'"
        :allow-negative="page.editKind === 'asset'"
        mode="edit"
        :initial="page.editInitial"
        :on-submit="page.submitEditWithExpenseReview"
        :on-cancel="page.closeEdit"
      />
    </BaseModal>
  </div>
</template>
