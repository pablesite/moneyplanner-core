<script setup lang="ts">
type ItemView = {
  id: number;
  name: string;
  is_active: boolean;
  currency: string;
};

type Props = {
  item: ItemView;
  formattedAmount: string;
  isLiabilitiesList: boolean;
  financedAssetName: string | null;
  ownershipLabel?: string | null;
  sharePercent?: number | null;
};

defineProps<Props>();

const emit = defineEmits<{
  (e: 'edit', id: number): void;
  (e: 'archive', id: number): void;
}>();
</script>

<template>
  <div class="item-row">
    <div class="item-main">
      <div class="item-name">
        <span class="item-name-text">{{ item.name }}</span>
        <span v-if="!item.is_active" class="badge">archivado</span>
        <span v-if="ownershipLabel" class="badge">{{ ownershipLabel }}</span>
        <span v-if="sharePercent && sharePercent < 100" class="badge">{{ sharePercent }}%</span>
      </div>
      <div v-if="isLiabilitiesList && financedAssetName" class="item-submeta">
        <span class="financed-text">. Financia: {{ financedAssetName }}</span>
      </div>
    </div>
    <div class="item-amount">{{ formattedAmount }} {{ item.currency }}</div>
    <div class="actions">
      <button class="icon-btn" title="Editar" aria-label="Editar" @click="emit('edit', item.id)">
        &#9998;&#65039;
      </button>
      <button class="icon-btn" title="Archivar" aria-label="Archivar" @click="emit('archive', item.id)">
        &#128465;&#65039;
      </button>
    </div>
  </div>
</template>

<style scoped>
.item-row {
  border: none;
  background: transparent;
  box-shadow: none;
  border-radius: 0;
  padding: 3px 2px;
  display: grid;
  grid-template-columns: minmax(0, 1fr) auto auto;
  align-items: center;
  column-gap: 12px;
}

.item-main {
  min-width: 0;
  padding-left: 12px;
  display: block;
}

.item-name {
  font-size: 14px;
  font-weight: 500;
}

.item-submeta {
  margin-top: 2px;
  font-size: 12px;
  color: rgba(255, 255, 255, 0.65);
}

.item-submeta .financed-text {
  display: inline-block;
  padding: 0;
  border: none;
  background: transparent;
}

.item-amount {
  text-align: right;
  white-space: nowrap;
  font-weight: 600;
  font-size: 13px;
  font-variant-numeric: tabular-nums;
}

.actions {
  justify-self: end;
  min-width: var(--item-actions-width, 72px);
}

.actions .icon-btn {
  width: 28px;
  height: 28px;
  padding: 0;
  font-size: 12px;
}
</style>
