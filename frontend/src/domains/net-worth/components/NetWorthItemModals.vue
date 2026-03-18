<script setup lang="ts">
import { ItemForm } from '@/domains/net-worth';
import type { NetWorthWritePayload, Ownership } from '@/domains/net-worth/models';
import { BaseModal } from '@/domains/ui';

type ItemFormPayload = NetWorthWritePayload & {
  ownership_id?: number | null;
  estimated_average_balance_for_interest?: string;
  deposit_term_months?: number;
};

type ItemFormExtensionProps = {
  defaultCurrency?: string;
  ownerships?: Ownership[];
};

type CategoryOption = { value: string; label: string };
type SubcategoryOption = { value: string; label: string; category: string };

defineProps<{
  showAssetModal: boolean;
  showLiabilityModal: boolean;
  showEditModal: boolean;
  editTitle: string;
  assetCategories: CategoryOption[];
  liabilityCategories: CategoryOption[];
  assetSubcategories: SubcategoryOption[];
  assetCreateInitial?: Record<string, unknown>;
  liabilityCreateInitial?: Record<string, unknown>;
  editInitial?: Record<string, unknown> | null;
  editCategories: CategoryOption[];
  editKind: 'asset' | 'liability' | null;
  activeAssets: Array<{ id: number; name: string; category: string }>;
  itemFormProps: ItemFormExtensionProps;
  submitAssetFromView: (payload: ItemFormPayload) => Promise<void>;
  submitLiabilityFromView: (payload: ItemFormPayload) => Promise<void>;
  submitEdit: (payload: ItemFormPayload) => Promise<void>;
  closeEdit: () => void;
  onCloseAssetModal: () => void;
  onCloseLiabilityModal: () => void;
}>();
</script>

<template>
  <BaseModal :open="showAssetModal" title="Nuevo activo" @close="onCloseAssetModal">
    <ItemForm
      title="Nuevo activo"
      :categories="assetCategories"
      :subcategories="assetSubcategories"
      :initial="assetCreateInitial"
      v-bind="itemFormProps"
      :allow-negative="true"
      :on-submit="submitAssetFromView"
      :on-cancel="onCloseAssetModal"
    />
  </BaseModal>

  <BaseModal :open="showLiabilityModal" title="Nuevo pasivo" @close="onCloseLiabilityModal">
    <ItemForm
      title="Nuevo pasivo"
      :categories="liabilityCategories"
      :initial="liabilityCreateInitial"
      v-bind="itemFormProps"
      :assets="activeAssets"
      :show-financed-asset="true"
      :on-submit="submitLiabilityFromView"
      :on-cancel="onCloseLiabilityModal"
    />
  </BaseModal>

  <BaseModal :open="showEditModal" :title="editTitle" @close="closeEdit">
    <ItemForm
      v-if="editInitial"
      :title="editTitle"
      :categories="editCategories"
      :subcategories="editKind === 'asset' ? assetSubcategories : undefined"
      v-bind="itemFormProps"
      :assets="editKind === 'liability' ? activeAssets : []"
      :show-financed-asset="editKind === 'liability'"
      :allow-negative="editKind === 'asset'"
      mode="edit"
      :initial="editInitial"
      :on-submit="submitEdit"
      :on-cancel="closeEdit"
    />
  </BaseModal>
</template>
