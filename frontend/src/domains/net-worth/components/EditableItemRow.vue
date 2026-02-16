<script setup lang="ts">
type SelectOption = {
  value: string | number | null;
  label: string;
};

type CategoryOption = {
  value: string;
  label: string;
};

type SubcategoryOption = {
  value: string;
  label: string;
  category: string;
};

type EditDraft = {
  name?: string;
  category?: string;
  subcategory?: string;
  amount?: string;
  currency?: string;
  notes?: string;
  is_active?: boolean;
  ownership_id?: number | null;
  financed_asset_id?: number | null;
};

type Props = {
  categories: CategoryOption[];
  subcategories?: SubcategoryOption[];
  currencies: CategoryOption[];
  ownershipOptions?: SelectOption[];
  showFinancedAsset: boolean;
  financedAssetOptions: SelectOption[];
  amountHint: string;
  amountError: string;
};

defineProps<Props>();
const draft = defineModel<EditDraft>('draft', { required: true });

const emit = defineEmits<{
  (e: 'save'): void;
  (e: 'cancel'): void;
}>();
</script>

<template>
  <div class="form-grid max-w-[520px]">
    <input v-model="draft.name" class="input" />

    <select v-model="draft.category" class="select">
      <option v-for="c in categories" :key="c.value" :value="c.value">
        {{ c.label }}
      </option>
    </select>

    <select v-if="subcategories" v-model="draft.subcategory" class="select">
      <option
        v-for="s in subcategories.filter((sc) => sc.category === draft.category)"
        :key="s.value"
        :value="s.value"
      >
        {{ s.label }}
      </option>
    </select>

    <select v-model="draft.currency" class="select">
      <option v-for="c in currencies" :key="c.value" :value="c.value">
        {{ c.label }}
      </option>
    </select>

    <input v-model="draft.amount" inputmode="decimal" class="input" />

    <select v-if="ownershipOptions?.length" v-model="draft.ownership_id" class="select">
      <option v-for="o in ownershipOptions" :key="String(o.value)" :value="o.value">
        {{ o.label }}
      </option>
    </select>

    <select v-if="showFinancedAsset" v-model="draft.financed_asset_id" class="select">
      <option v-for="a in financedAssetOptions" :key="String(a.value)" :value="a.value">
        {{ a.label }}
      </option>
    </select>

    <textarea v-model="draft.notes" rows="2" class="textarea"></textarea>

    <label class="checkbox-row">
      <input v-model="draft.is_active" type="checkbox" />
      Activo
    </label>

    <div class="ui-form-help">
      {{ amountHint }}
    </div>

    <div v-if="amountError" class="ui-form-help ui-form-help-error">
      {{ amountError }}
    </div>

    <div class="actions">
      <button class="btn btn-primary" :disabled="!!amountError" @click="emit('save')">Guardar</button>
      <button class="btn" @click="emit('cancel')">Cancelar</button>
    </div>
  </div>
</template>
